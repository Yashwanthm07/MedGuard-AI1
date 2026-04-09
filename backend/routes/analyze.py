"""Medicine authenticity analysis routes."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import base64
import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from services.image_processor import ImageProcessor
from services.ocr_service import OCRService, merge_texts
from services.free_ai import extract_text_multi_ocr_from_base64
from services.api_ninjas_ocr_service import extract_structured_api_ninjas
from services.decision_engine import DecisionEngine
from models.schemas import MedicineAnalysisResult
from routes.dashboard import update_scan_stat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analyze"])

# Global cache for analysis results (medicine image hash → result)
_analysis_cache = {}
CACHE_PIPELINE_VERSION = "free-ocr-v15"
FREE_OCR_ENRICHMENT_TIMEOUT_SEC = 1.8
API_NINJAS_FALLBACK_MIN_CONFIDENCE = 68.0
API_NINJAS_FALLBACK_MIN_TEXT_LEN = 90
API_NINJAS_FALLBACK_MIN_MISSING_FIELDS = 2
API_NINJAS_FALLBACK_MAX_LOCAL_OCR_SCORE = 58.0

_UI_SCREENSHOT_MARKERS = [
    "VERDICT",
    "CONFIDENCE",
    "MISSING FIELDS",
    "OCR",
    "DETECTIONS",
    "OCR DETECTIONS",
    "WHY THIS VERDICT",
    "VOICE OUTPUT",
    "BLOCKCHAIN",
    "SUSPICIOUS SIGNALS",
    "DETECTED DATA",
    "MULTI-IMAGE COMPARISON",
    "SCAN RESULT",
    "VERDICT FOR",
    "RUN AUTHENTICITY SCAN",
]

_UI_BOX_NOISE_MARKERS = [
    "OCR",
    "SCAN",
    "VERDICT",
    "CONFIDENCE",
    "MISSING",
    "BLOCKCHAIN",
    "VOICE",
    "CURRENT",
    "PREVIOUS",
    "DELTA",
    "COMPARISON",
]

_MEDICINE_SIGNAL_MARKERS = [
    "PARACETAMOL",
    "TABLET",
    "TABLETS",
    "CAPSULE",
    "CAPSULES",
    "BATCH",
    "EXP",
    "DOSAGE",
    "MG",
    "ML",
    "IP",
]


def compute_confidence(data: dict) -> float:
    """Deterministic confidence based on extracted OCR fields and text length."""
    score = 0.0
    if data.get("medicine_name"):
        score += 25
    if data.get("batch_number"):
        score += 20
    if data.get("expiry_date"):
        score += 20
    if data.get("dosage"):
        score += 15
    if data.get("manufacturer"):
        score += 10

    score += min(10.0, len(data.get("raw_text", "")) / 50.0)
    return float(min(100.0, score))


class AnalyzeRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"


def _merge_ocr_text(*chunks: str) -> str:
    """Merge OCR chunks while preserving order and dropping near-duplicates."""
    merged = ""
    for chunk in chunks:
        merged = merge_texts(merged, chunk)
    return merged


def _count_marker_hits(text: str, markers: list[str]) -> int:
    """Count marker phrase hits in normalized OCR text."""
    normalized = (text or "").upper()
    if not normalized:
        return 0
    return sum(1 for marker in markers if marker in normalized)


def _focus_score(text: str) -> float:
    """Score OCR text quality while penalizing UI screenshot contamination."""
    base = OCRService._score_ocr_candidate(text)
    medicine_hits = _count_marker_hits(text, _MEDICINE_SIGNAL_MARKERS)
    ui_hits = _count_marker_hits(text, _UI_SCREENSHOT_MARKERS)
    return float(base + (medicine_hits * 8.0) - (ui_hits * 11.0))


def _recover_from_screenshot_noise(raw_pil_image, current_text: str) -> str:
    """Recover OCR by tightly cropping likely pack region when UI screenshot markers dominate."""
    if not current_text:
        return current_text

    ui_hits = _count_marker_hits(current_text, _UI_SCREENSHOT_MARKERS)
    if ui_hits < 2:
        return current_text

    width, height = raw_pil_image.size
    if width < 360 or height < 360:
        return current_text

    current_score = _focus_score(current_text)
    best_text = current_text
    best_score = current_score
    best_ui_hits = ui_hits

    focus_regions = [
        ("focus_mid", (0.24, 0.20, 0.76, 0.94)),
        ("focus_tight", (0.30, 0.28, 0.70, 0.96)),
        ("focus_wide", (0.20, 0.16, 0.80, 0.90)),
    ]

    for region_name, (left_r, top_r, right_r, bottom_r) in focus_regions:
        left = int(width * left_r)
        top = int(height * top_r)
        right = int(width * right_r)
        bottom = int(height * bottom_r)
        if right - left < 140 or bottom - top < 140:
            continue

        crop = raw_pil_image.crop((left, top, right, bottom))
        crop_text = _extract_best_ocr_text(crop)
        if not crop_text:
            continue

        crop_ui_hits = _count_marker_hits(crop_text, _UI_SCREENSHOT_MARKERS)
        crop_medicine_hits = _count_marker_hits(crop_text, _MEDICINE_SIGNAL_MARKERS)
        crop_score = _focus_score(crop_text)

        better_candidate = crop_score > best_score and (crop_ui_hits <= best_ui_hits or crop_medicine_hits >= 3)
        if better_candidate:
            logger.info(
                "Screenshot-noise recovery candidate selected: %s (score=%.2f ui_hits=%s)",
                region_name,
                crop_score,
                crop_ui_hits,
            )
            best_text = crop_text
            best_score = crop_score
            best_ui_hits = crop_ui_hits

    if best_text != current_text and best_score >= current_score + 6.0:
        logger.info(
            "Applied screenshot-noise OCR recovery (ui_hits %s -> %s, score %.2f -> %.2f)",
            ui_hits,
            best_ui_hits,
            current_score,
            best_score,
        )
        return best_text

    return current_text


def _extract_best_ocr_text(pil_image) -> str:
    """Extract OCR text from full image and focused crops, then keep strongest signals."""
    candidates = []

    full_text = OCRService.extract_text_from_image(pil_image)
    if full_text:
        full_score = OCRService._score_ocr_candidate(full_text)
        candidates.append(("full", full_text, full_score))

        # Fast path: when full-frame OCR is already strong, skip crop OCR calls.
        if full_score >= 46 and len(full_text) >= 32:
            logger.info("Selected OCR fast-path candidate: full (score=%.2f)", full_score)
            return full_text

    width, height = pil_image.size
    if width >= 320 and height >= 320:
        crop_regions = {
            "center": (0.12, 0.08, 0.88, 0.92),
            "lower_center": (0.12, 0.26, 0.88, 0.98),
        }
        for name, (left_r, top_r, right_r, bottom_r) in crop_regions.items():
            # Only attempt second crop when first signals are still weak.
            if name == "lower_center" and candidates:
                best_so_far = max(c[2] for c in candidates)
                if best_so_far >= 48:
                    break

            left = int(width * left_r)
            top = int(height * top_r)
            right = int(width * right_r)
            bottom = int(height * bottom_r)
            if right - left < 120 or bottom - top < 120:
                continue

            cropped = pil_image.crop((left, top, right, bottom))
            crop_text = OCRService.extract_text_from_image(cropped)
            if crop_text:
                crop_score = OCRService._score_ocr_candidate(crop_text)
                candidates.append((name, crop_text, crop_score))

    if not candidates:
        return ""

    scored = sorted(candidates, key=lambda item: (item[2], len(item[1])), reverse=True)
    best_name, best_text, best_score = scored[0]

    merged_chunks = [best_text]
    for name, text, score in scored[1:]:
        # Merge only reasonably strong alternate OCR variants.
        if score >= max(10.0, best_score * 0.55):
            merged_chunks.append(text)
        if len(merged_chunks) >= 2:
            break

    if len(merged_chunks) > 1:
        logger.info("Merged OCR candidates (best=%s score=%.2f)", best_name, best_score)
    else:
        logger.info("Selected OCR candidate: %s (score=%.2f)", best_name, best_score)

    return _merge_ocr_text(*merged_chunks)


def _run_free_ocr_enrichment_with_timeout(image_base64: str, mime_type: str) -> str:
    """Run optional free OCR enrichment with a strict timeout budget."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(extract_text_multi_ocr_from_base64, image_base64, mime_type)
    try:
        return (future.result(timeout=FREE_OCR_ENRICHMENT_TIMEOUT_SEC) or "").strip()
    except FutureTimeoutError:
        future.cancel()
        logger.warning("Free OCR enrichment timed out after %.1fs", FREE_OCR_ENRICHMENT_TIMEOUT_SEC)
        return ""
    except Exception as exc:
        logger.warning("Free OCR enrichment failed: %s", exc)
        return ""
    finally:
        # Do not block request thread waiting for slow enrichment worker shutdown.
        executor.shutdown(wait=False, cancel_futures=True)


def _select_field_boxes(text_boxes: list, image_size: dict) -> list:
    """Select likely medicine-pack region boxes for field extraction.

    This reduces noise when users upload UI screenshots that contain many
    unrelated overlay labels around the product image.
    """
    if not text_boxes:
        return []

    if not image_size:
        return text_boxes

    width = float(image_size.get("width") or 0)
    height = float(image_size.get("height") or 0)
    if width <= 0 or height <= 0:
        return text_boxes

    ui_filtered = []
    for box in text_boxes:
        token = str(box.get("text") or "").upper().strip()
        if token and any(marker in token for marker in _UI_BOX_NOISE_MARKERS):
            continue
        ui_filtered.append(box)

    min_after_filter = max(6, int(len(text_boxes) * 0.35))
    if len(ui_filtered) >= min_after_filter:
        text_boxes = ui_filtered

    x_min = width * 0.18
    x_max = width * 0.82
    y_min = height * 0.05
    y_max = height * 0.95

    central_boxes = []
    for box in text_boxes:
        x = float(box.get("x") or 0)
        y = float(box.get("y") or 0)
        w = float(box.get("w") or 0)
        h = float(box.get("h") or 0)
        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        if x_min <= cx <= x_max and y_min <= cy <= y_max:
            central_boxes.append(box)

    min_needed = max(8, int(len(text_boxes) * 0.2))
    return central_boxes if len(central_boxes) >= min_needed else text_boxes


def build_local_explanation(analysis: dict, verdict: str) -> str:
    """Build a concise, deterministic explanation without external AI providers."""
    name = analysis.get("medicine_name") or "the uploaded medicine"
    conf = float(analysis.get("overall_confidence", 0))
    missing = analysis.get("missing_fields") or []
    concerns = analysis.get("suspicious_signs") or []

    missing_norm = {str(item).strip().lower() for item in missing if str(item).strip()}
    filtered_concerns = []
    for concern in concerns:
        if not isinstance(concern, str):
            continue
        text = concern.strip()
        if not text:
            continue
        lowered = text.lower()
        if "ai service unavailable" in lowered:
            continue
        if lowered.startswith("missing:"):
            field_part = text.split(":", 1)[1].strip().lower() if ":" in text else ""
            if field_part in missing_norm:
                continue
        if "missing" in lowered and any(field in lowered for field in missing_norm):
            continue
        filtered_concerns.append(text)

    filtered_concerns = list(dict.fromkeys(filtered_concerns))
    missing_part = f" Missing fields: {', '.join(missing[:3])}." if missing else ""
    concerns_part = f" Key concerns: {', '.join(filtered_concerns[:3])}." if filtered_concerns else ""
    return f"Verdict for {name}: {verdict} with {conf:.0f}% confidence.{missing_part}{concerns_part}".strip()


@router.post("")
async def analyze_medicine(request: AnalyzeRequest):
    """
    Analyze medicine image for authenticity.

    - Validates image
    - Extracts OCR text
    - Runs deterministic OCR/CV pipeline for decisioning
    - Uses free local multi-OCR enrichment for weak extraction cases
    - Uses API Ninjas OCR fallback for stubborn low-confidence scans
    - Generates verdict
    - Returns detailed analysis
    """
    try:
        # Decode base64 image
        try:
            image_data = base64.b64decode(request.image_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid base64 image")

        # Validate image
        is_valid, error_msg = ImageProcessor.validate_image_file(image_data, request.mime_type)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Check cache using stable content hash to avoid collisions/stale mismatches.
        image_hash = hashlib.sha256(
            image_data + request.mime_type.encode("utf-8") + CACHE_PIPELINE_VERSION.encode("utf-8")
        ).hexdigest()
        if image_hash in _analysis_cache:
            cached_result = _analysis_cache[image_hash]
            # Avoid serving degraded cached results so new scans can retry AI enrichment.
            is_degraded_cache = (
                float(cached_result.get("overall_confidence", 0)) < 70
                or bool(cached_result.get("missing_fields"))
            )
            if is_degraded_cache:
                logger.info("Ignoring degraded cached analysis and re-running pipeline")
                del _analysis_cache[image_hash]
            else:
                logger.info("Returning cached analysis")
                return cached_result

        # Load image
        pil_image, cv_image = ImageProcessor.load_image(request.image_base64)
        if pil_image is None:
            raise HTTPException(status_code=400, detail="Failed to load image")

        raw_pil_image = pil_image

        # Check if likely medicine
        is_likely_medicine, medicine_confidence = ImageProcessor.check_if_likely_medicine(cv_image)

        # Preprocess for OCR
        preprocessed_pil_image = ImageProcessor.preprocess_image(raw_pil_image)

        # Extract text with OCR (primary signal for all downstream logic)
        ocr_text = _extract_best_ocr_text(preprocessed_pil_image)
        ocr_score = OCRService._score_ocr_candidate(ocr_text)

        # Fallback to original image when aggressive preprocessing hurts OCR (e.g., rotated/low-contrast text).
        if ocr_score < 30 or len((ocr_text or "").strip()) < 18:
            raw_text = _extract_best_ocr_text(raw_pil_image)
            raw_score = OCRService._score_ocr_candidate(raw_text)
            if raw_score > max(ocr_score * 1.08, 18.0):
                logger.info("Using raw-image OCR fallback (preprocessed_score=%.2f raw_score=%.2f)", ocr_score, raw_score)
                ocr_text = raw_text
                ocr_score = raw_score

        recovered_text = _recover_from_screenshot_noise(raw_pil_image, ocr_text)
        if recovered_text and recovered_text != ocr_text:
            ocr_text = recovered_text
            ocr_score = OCRService._score_ocr_candidate(ocr_text)

        text_boxes = []
        image_size = {"width": pil_image.width, "height": pil_image.height}
        box_tokens = []

        # Do not reject too early: allow API Ninjas fallback to rescue difficult low-signal scans.
        if not is_likely_medicine and len(ocr_text.strip()) < 6:
            logger.info(
                "Low visual confidence and very short local OCR; continuing to API Ninjas fallback before rejection"
            )

        # Build deterministic analysis from OCR and CV pipeline (AI only for explanation)
        # 1) Parse OCR structured data (fast path)
        ocr_data = OCRService.parse_medicine_data(ocr_text)

        # Only run expensive box OCR when confidence is weak or key fields are missing.
        missing_key_fields = sum(
            1 for key in ["medicine_name", "dosage", "manufacturer", "batch_number"] if not ocr_data.get(key)
        )
        needs_box_recovery = (ocr_score < 42 or missing_key_fields >= 2)

        if needs_box_recovery:
            box_source_image = raw_pil_image if ocr_score < 42 else preprocessed_pil_image
            ocr_result = OCRService.extract_text_with_boxes(box_source_image)
            text_boxes = ocr_result.get("boxes", [])
            image_size = ocr_result.get("image_size") or image_size

            field_boxes = _select_field_boxes(text_boxes, image_size)
            field_box_text = " ".join(str(b.get("text", "")).strip() for b in field_boxes if b.get("text")).strip()

            box_score = OCRService._score_ocr_candidate(field_box_text)
            if field_box_text and box_score >= max(10.0, ocr_score * 0.45):
                merged_text = _merge_ocr_text(ocr_text, field_box_text)
                if merged_text and merged_text != ocr_text:
                    ocr_text = merged_text
                    ocr_score = OCRService._score_ocr_candidate(ocr_text)
                    ocr_data = OCRService.parse_medicine_data(ocr_text)
            else:
                logger.info("Skipped noisy box-text merge (ocr_score=%.2f box_score=%.2f)", ocr_score, box_score)

            box_tokens = [str(b.get("text", "")) for b in field_boxes if b.get("text")]

            # Recover key fields from OCR token stream when line OCR misses them.
            if not ocr_data.get("batch_number"):
                token_batch = OCRService.detect_batch_number_from_tokens(box_tokens)
                if token_batch:
                    ocr_data["batch_number"] = token_batch

            if not ocr_data.get("expiry_date"):
                token_expiry = OCRService.detect_expiry_date_from_tokens(box_tokens)
                if token_expiry:
                    ocr_data["expiry_date"] = token_expiry

            token_manufacturer = OCRService.detect_manufacturer_from_tokens(box_tokens)
            if token_manufacturer:
                existing_manufacturer = ocr_data.get("manufacturer")
                if not existing_manufacturer:
                    ocr_data["manufacturer"] = token_manufacturer
                else:
                    existing_upper = str(existing_manufacturer).upper()
                    token_upper = str(token_manufacturer).upper()
                    company_markers = ["PVT", "LTD", "LIMITED", "PHARMA", "PHARMACEUT", "HEALTH", "DRUG", "CARE"]
                    existing_score = sum(1 for marker in company_markers if marker in existing_upper)
                    token_score = sum(1 for marker in company_markers if marker in token_upper)

                    # Prefer token-derived manufacturer when it looks like a stronger company-name candidate.
                    if token_score > existing_score or (token_score == existing_score and len(token_upper) > len(existing_upper)):
                        ocr_data["manufacturer"] = token_manufacturer
        else:
            logger.info("Fast path: skipped OCR box extraction (ocr_score=%.2f)", ocr_score)

        # 2) Build analysis from real OCR/CV data
        analysis = {
            **ocr_data,
            "raw_text": ocr_text,
            "extracted_text": ocr_text,
            "ai_assisted": False,
            "is_medicine": bool(is_likely_medicine),
            "text_boxes": text_boxes,
            "image_size": image_size,
            "visual_authenticity_score": float(medicine_confidence),
            "text_clarity_score": float(min(100.0, len((ocr_text or "").strip()) * 2.5)),
            "data_completeness_score": 0.0,
            "format_validity_score": 50.0,
            "authenticity_indicators": [],
            "suspicious_signs": [],
        }

        if analysis.get("manufacturer") and not OCRService.is_manufacturer_supported_by_text(
            analysis.get("extracted_text") or "",
            analysis.get("manufacturer"),
        ):
            logger.info("Dropped unsupported manufacturer candidate from local OCR")
            analysis["manufacturer"] = None

        # 3) If OCR strongly indicates medicine, prefer that signal
        ocr_lower = (ocr_text or "").lower()
        medicine_markers = ["tablet", "tablets", "capsule", "capsules", "syrup", "injection", "mg", "ml", "ip"]
        marker_hits = sum(1 for marker in medicine_markers if marker in ocr_lower)
        has_structured_fields = bool(ocr_data.get("medicine_name") or ocr_data.get("dosage") or ocr_data.get("batch_number"))
        if (marker_hits >= 2 or has_structured_fields) and not analysis.get("is_medicine"):
            analysis["is_medicine"] = True
            logger.info("OCR signal overrode visual classifier for medicine detection")

        # 3b) Force keyword-based medicine validation for common medicine text patterns.
        keyword_markers = ["tablet", "mg", "paracetamol", "capsule"]
        if any(k in ocr_lower for k in keyword_markers):
            analysis["is_medicine"] = True

        # Debug visibility for OCR/parsing quality.
        logger.info("OCR TEXT:\n%s", (ocr_text or "")[:3000])
        logger.info("PARSED DATA: %s", ocr_data)

        # 4) Compute confidence from real extracted data
        analysis["overall_confidence"] = compute_confidence(analysis)

        # 4b) Boost confidence for strong dual-keyword signal.
        ocr_upper = (ocr_text or "").upper()
        has_para = bool(re.search(r"\bPARACETAMOL\b", ocr_upper))
        has_strength = bool(re.search(r"\b\d{2,4}\s*\.?\s*MG\b", ocr_upper))
        if has_para and has_strength:
            analysis["overall_confidence"] = min(100.0, float(analysis["overall_confidence"]) + 15.0)

        # 4c) Free multi-OCR enrichment for low-confidence or incomplete OCR outcomes.
        critical_fields = ["medicine_name", "manufacturer", "batch_number", "expiry_date", "dosage"]
        missing_critical_before_ai = [k for k in critical_fields if not analysis.get(k)]
        confidence_now = float(analysis.get("overall_confidence", 0))
        essential_fields = {"medicine_name", "dosage", "manufacturer"}
        essential_missing = [field for field in missing_critical_before_ai if field in essential_fields]

        # Performance-first trigger: avoid expensive enrichment for minor misses
        # (e.g., expiry-only) when confidence is already moderate.
        needs_ai_enrichment = (
            confidence_now < 56
            or len(missing_critical_before_ai) >= 3
            or bool(essential_missing)
        )

        if needs_ai_enrichment:
            logger.info("Free multi-OCR enrichment triggered: confidence=%s missing_fields=%s",
                        analysis.get("overall_confidence"), missing_critical_before_ai)
            extra_text = _run_free_ocr_enrichment_with_timeout(
                request.image_base64,
                request.mime_type,
            )

            combined_text = merge_texts((ocr_text or "").strip(), extra_text)

            enriched_data = OCRService.parse_medicine_data(combined_text) if combined_text else {}

            filled_count = 0
            for key in critical_fields:
                if not analysis.get(key) and enriched_data.get(key):
                    analysis[key] = enriched_data[key]
                    filled_count += 1

            if combined_text and len(combined_text) > len(analysis.get("extracted_text") or ""):
                analysis["raw_text"] = combined_text
                analysis["extracted_text"] = combined_text
                analysis["text_clarity_score"] = float(min(100.0, len(combined_text.strip()) * 2.5))

            if filled_count > 0 or (combined_text and len(combined_text) > len((ocr_text or ""))):
                analysis["ai_assisted"] = True
                # Recompute confidence after enrichment.
                analysis["overall_confidence"] = compute_confidence(analysis)
                if has_para and has_strength:
                    analysis["overall_confidence"] = min(100.0, float(analysis["overall_confidence"]) + 15.0)
            else:
                logger.info("Free multi-OCR enrichment did not add additional fields")

        # 4d) API Ninjas fallback: trigger earlier on weak OCR to improve real-image recall.
        confidence_after_local = float(analysis.get("overall_confidence", 0))
        local_text_for_hybrid = (analysis.get("extracted_text") or "").strip()

        if analysis.get("manufacturer") and not OCRService.is_manufacturer_supported_by_text(
            local_text_for_hybrid,
            analysis.get("manufacturer"),
        ):
            logger.info("Cleared unsupported manufacturer before API Ninjas fallback")
            analysis["manufacturer"] = None

        missing_critical_after_local = [k for k in critical_fields if not analysis.get(k)]
        should_call_api_ninjas = (
            len(local_text_for_hybrid) < API_NINJAS_FALLBACK_MIN_TEXT_LEN
            or confidence_after_local < API_NINJAS_FALLBACK_MIN_CONFIDENCE
            or len(missing_critical_after_local) >= API_NINJAS_FALLBACK_MIN_MISSING_FIELDS
            or ocr_score < API_NINJAS_FALLBACK_MAX_LOCAL_OCR_SCORE
            or (not analysis.get("manufacturer") and bool(analysis.get("medicine_name") or analysis.get("dosage")))
        )

        if should_call_api_ninjas:
            logger.info(
                "API Ninjas OCR fallback triggered: text_len=%s confidence=%.2f missing=%s ocr_score=%.2f",
                len(local_text_for_hybrid),
                confidence_after_local,
                missing_critical_after_local,
                float(ocr_score),
            )
            api_ninjas_result = extract_structured_api_ninjas(
                request.image_base64,
                request.mime_type,
            )
            api_ninjas_text = (api_ninjas_result.get("text") or "").strip()
            api_ninjas_signal_fields = OCRService.validate_fields(api_ninjas_result.get("fields") or {})
            api_ninjas_signal_confidence = float(api_ninjas_result.get("signal_confidence") or 0.0)
            api_ninjas_signal_verdict = str(api_ninjas_result.get("signal_verdict") or "INVALID")

            # Preserve high-confidence API Ninjas manufacturer anchors (e.g., GLAXOSMITHKLINE)
            # so the final pass does not drop clearly signaled brand names.
            signal_locked_manufacturer = None
            signal_manufacturer = str(api_ninjas_signal_fields.get("manufacturer") or "").strip()
            if signal_manufacturer:
                upper_text = api_ninjas_text.upper()
                if (
                    "GLAXO" in signal_manufacturer.upper()
                    and ("GLAXO" in upper_text or "SMITHKLINE" in upper_text or "GSK" in upper_text)
                    and api_ninjas_signal_confidence >= 65.0
                ):
                    signal_locked_manufacturer = signal_manufacturer

            if api_ninjas_text:
                final_text = merge_texts(local_text_for_hybrid, api_ninjas_text)
                ninjas_data = OCRService.parse_medicine_data(final_text)

                for key in critical_fields:
                    if not analysis.get(key) and api_ninjas_signal_fields.get(key):
                        analysis[key] = api_ninjas_signal_fields[key]

                for key in critical_fields:
                    if not analysis.get(key) and ninjas_data.get(key):
                        analysis[key] = ninjas_data[key]

                if signal_locked_manufacturer:
                    if not analysis.get("manufacturer"):
                        analysis["manufacturer"] = signal_locked_manufacturer

                    if str(analysis.get("manufacturer") or "").upper() == signal_locked_manufacturer.upper():
                        analysis["_ninjas_signal_locked_manufacturer"] = True
                        logger.info("Applied locked API Ninjas manufacturer signal: %s", signal_locked_manufacturer)

                if final_text:
                    analysis["raw_text"] = final_text
                    analysis["extracted_text"] = final_text
                    analysis["text_clarity_score"] = float(min(100.0, len(final_text.strip()) * 2.5))

                analysis["ai_assisted"] = True
                analysis["overall_confidence"] = max(
                    compute_confidence(analysis),
                    api_ninjas_signal_confidence,
                )
                analysis["authenticity_indicators"] = list(dict.fromkeys([
                    *(analysis.get("authenticity_indicators") or []),
                    f"API Ninjas signal verdict: {api_ninjas_signal_verdict}",
                ]))

                post_ninjas_text = (analysis.get("extracted_text") or "").upper()
                has_para_after_ninjas = bool(re.search(r"\bPARACETAMOL\b", post_ninjas_text))
                has_strength_after_ninjas = bool(re.search(r"\b\d{2,4}\s*\.?\s*MG\b", post_ninjas_text))
                if has_para_after_ninjas and has_strength_after_ninjas:
                    analysis["overall_confidence"] = min(100.0, float(analysis["overall_confidence"]) + 15.0)
            else:
                logger.info("API Ninjas OCR fallback skipped or returned empty text")

        # 4e) Final manufacturer rescue from merged extracted text.
        if not analysis.get("manufacturer"):
            manufacturer_candidate = OCRService.detect_manufacturer(analysis.get("extracted_text") or "")
            if manufacturer_candidate:
                manufacturer_validated = OCRService.validate_fields({"manufacturer": manufacturer_candidate}).get("manufacturer")
                if manufacturer_validated:
                    analysis["manufacturer"] = manufacturer_validated
                    logger.info("Recovered manufacturer using final text pass: %s", manufacturer_validated)

        if analysis.get("manufacturer") and not OCRService.is_manufacturer_supported_by_text(
            analysis.get("extracted_text") or "",
            analysis.get("manufacturer"),
        ):
            if analysis.get("_ninjas_signal_locked_manufacturer"):
                logger.info("Retained locked API Ninjas manufacturer signal after fallback checks")
            else:
                logger.info("Dropped unsupported manufacturer candidate after fallbacks")
                analysis["manufacturer"] = None

        analysis.pop("_ninjas_signal_locked_manufacturer", None)

        # 5b) Data completeness score from critical fields
        found_fields = sum(1 for field in critical_fields if analysis.get(field))
        analysis["data_completeness_score"] = float((found_fields / len(critical_fields)) * 100.0)

        # Attach OCR context and geometry for frontend overlays.
        if not analysis.get("extracted_text"):
            analysis["extracted_text"] = ocr_text
        analysis["text_boxes"] = text_boxes
        analysis["image_size"] = image_size

        ui_contamination_hits = _count_marker_hits(analysis.get("extracted_text") or "", _UI_SCREENSHOT_MARKERS)
        if ui_contamination_hits >= 2:
            analysis["suspicious_signs"] = list(dict.fromkeys([
                *(analysis.get("suspicious_signs") or []),
                "UI/screenshot overlay text detected; upload a close-up medicine photo for best accuracy",
            ]))
            confidence_penalty = min(28.0, float(ui_contamination_hits) * 6.0)
            analysis["overall_confidence"] = max(35.0, float(analysis.get("overall_confidence", 0)) - confidence_penalty)

        # Generate verdict
        verdict = DecisionEngine.generate_verdict(analysis)
        analysis["verdict"] = verdict

        # Identify missing fields
        missing = DecisionEngine.calculate_missing_fields(analysis)
        analysis["missing_fields"] = missing

        # Generate deterministic local explanation (no external API dependency).
        analysis["explanation"] = build_local_explanation(analysis=analysis, verdict=verdict)

        # Create response
        result = MedicineAnalysisResult(**analysis)
        result_dict = result.dict()

        # Record in dashboard history (persist to DB when configured).
        await update_scan_stat(
            verdict=result_dict.get("verdict", "INVALID"),
            medicine_name=result_dict.get("medicine_name") or "Unknown",
            confidence=float(result_dict.get("overall_confidence", 0)),
        )

        # Cache only non-fallback responses; avoid sticky degraded results.
        is_low_quality = (
            float(result_dict.get("overall_confidence", 0)) < 70
            or bool(result_dict.get("missing_fields"))
        )
        if not is_low_quality:
            _analysis_cache[image_hash] = result_dict
            if len(_analysis_cache) > 100:  # Limit cache size
                oldest_key = next(iter(_analysis_cache))
                del _analysis_cache[oldest_key]

        logger.info(f"Analysis complete. Verdict: {verdict}, Confidence: {analysis.get('overall_confidence')}%")
        return result_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/image")
async def analyze_image_upload(file: UploadFile = File(...)):
    """
    Analyze uploaded image file for medicine authenticity.
    """
    try:
        contents = await file.read()

        # Convert to base64
        image_base64 = base64.b64encode(contents).decode('utf-8')

        # Use analyze endpoint
        request = AnalyzeRequest(
            image_base64=image_base64,
            mime_type=file.content_type or "image/jpeg"
        )
        return await analyze_medicine(request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        raise HTTPException(status_code=500, detail="Image upload failed")
