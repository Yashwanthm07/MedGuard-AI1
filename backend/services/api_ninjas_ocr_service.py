"""API Ninjas OCR enrichment service for low-confidence OCR fallback."""

import base64
import io
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

import requests
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

API_NINJAS_URL = "https://api.api-ninjas.com/v1/imagetotext"
FREE_TIER_MAX_BYTES = 190_000

MONTH_ALIASES = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "SEPT": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}

KNOWN_MEDICINE_SIGNALS = [
    "PARACETAMOL",
    "IBUPROFEN",
    "AMOXICILLIN",
    "AZITHROMYCIN",
    "METFORMIN",
]


def _normalize_year_token(token: str) -> str:
    """Normalize OCR-noisy year fragments (e.g., IS -> 15)."""
    mapped = str(token or "").upper().translate(str.maketrans({
        "O": "0",
        "Q": "0",
        "I": "1",
        "L": "1",
        "S": "5",
        "B": "8",
        "Z": "2",
    }))
    digits = re.sub(r"[^0-9]", "", mapped)
    if len(digits) == 2:
        return f"20{digits}"
    if len(digits) == 4:
        return digits
    return ""


def _normalize_strength_token(token: str) -> str:
    """Normalize OCR-noisy numeric strength tokens (e.g., 5OO -> 500)."""
    mapped = str(token or "").upper().translate(str.maketrans({
        "O": "0",
        "Q": "0",
        "I": "1",
        "L": "1",
        "S": "5",
        "B": "8",
        "Z": "2",
    }))
    return re.sub(r"[^0-9.]", "", mapped)


def combine_ninjas_text(payload: Any) -> str:
    """Combine API Ninjas OCR payload into uppercase signal text.

    The API commonly returns token fragments. This normalizes ordering and
    combines tokens into one interpretable string for signal extraction.
    """
    if isinstance(payload, dict):
        if isinstance(payload.get("result"), list):
            payload = payload.get("result")
        elif isinstance(payload.get("text"), str):
            payload = [{"text": payload.get("text", "")}]
        elif isinstance(payload.get("result"), str):
            payload = [{"text": payload.get("result", "")}]
        else:
            payload = []

    if not isinstance(payload, list):
        return ""

    ordered_tokens = []
    fallback_tokens = []

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        token = str(item.get("text") or "").strip()
        if not token:
            continue

        bbox = item.get("bounding_box") or {}
        if isinstance(bbox, dict) and all(k in bbox for k in ("x1", "y1")):
            try:
                ordered_tokens.append((float(bbox.get("y1")), float(bbox.get("x1")), idx, token))
                continue
            except (TypeError, ValueError):
                pass

        fallback_tokens.append((idx, token))

    if ordered_tokens:
        ordered_tokens.sort(key=lambda row: (row[0], row[1], row[2]))
        words = [token for _, _, _, token in ordered_tokens]
    else:
        words = [token for _, token in sorted(fallback_tokens, key=lambda row: row[0])]

    text = " ".join(words)
    text = re.sub(r"\s+", " ", text).strip()
    return text.upper()


def extract_fields_from_ninjas_text(text: str) -> Dict[str, str]:
    """Extract medicine fields using signal-based parsing from combined text."""
    normalized = (text or "").upper().strip()
    fields: Dict[str, str] = {}
    if not normalized:
        return fields

    for medicine in KNOWN_MEDICINE_SIGNALS:
        if medicine in normalized:
            fields["medicine_name"] = medicine
            break

    if not fields.get("medicine_name"):
        tokens = re.findall(r"[A-Z]{6,20}", normalized)
        for token in tokens:
            for medicine in KNOWN_MEDICINE_SIGNALS:
                if SequenceMatcher(None, token, medicine).ratio() >= 0.74:
                    fields["medicine_name"] = medicine
                    break
            if fields.get("medicine_name"):
                break

    dosage_match = re.search(r"(?<!\d)([0-9OQILSBZ]{2,4}(?:\.[0-9OQILSBZ]+)?)\s*(MG|ML|MCG|G|IU|UNITS)\b", normalized)
    if dosage_match:
        strength = _normalize_strength_token(dosage_match.group(1))
        if "." in strength:
            strength = strength.rstrip("0").rstrip(".")
        if strength:
            fields["dosage"] = f"{strength} {dosage_match.group(2)}"

    batch_match = re.search(
        r"\b(?:BATCH\s*NO|BATCH|LOT\s*NO|LOT|B\.?\s*NO)\s*[:#-]?\s*([A-Z0-9-]{5,20})\b",
        normalized,
    )
    if batch_match:
        fields["batch_number"] = batch_match.group(1).strip()

    month_match = re.search(
        r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)\s*[-/. ]?\s*([0-9OQILSBZ]{2,4})\b",
        normalized,
    )
    if month_match:
        month = month_match.group(1)
        year = _normalize_year_token(month_match.group(2))
        if year:
            fields["expiry_date"] = f"{MONTH_ALIASES[month]}/{year}"
    else:
        mm_yyyy_match = re.search(r"\b(0[1-9]|1[0-2])[/-](\d{2,4})\b", normalized)
        if mm_yyyy_match:
            year = _normalize_year_token(mm_yyyy_match.group(2))
            if year:
                fields["expiry_date"] = f"{mm_yyyy_match.group(1)}/{year}"

    # High-confidence brand signal from frequent API Ninjas token outputs.
    if "GLAXO" in normalized or "SMITHKLINE" in normalized or "GSK" in normalized:
        fields["manufacturer"] = "GLAXOSMITHKLINE PHARMACEUTICALS LIMITED"
    else:
        company_match = re.search(
            r"\b([A-Z][A-Z&./ -]{2,80}\b(?:PVT\s*LTD|PVT\s*LIMITED|PRIVATE\s*LIMITED|LTD|LIMITED)\b)",
            normalized,
        )
        if company_match:
            manufacturer = re.sub(r"\s+", " ", company_match.group(1)).strip(" .:-")
            if manufacturer:
                fields["manufacturer"] = manufacturer

    return fields


def calculate_signal_confidence(text: str, fields: Dict[str, str]) -> float:
    """Compute signal confidence from API Ninjas combined text and extracted fields."""
    normalized = (text or "").upper()
    score = 0.0

    if fields.get("medicine_name") or "PARACETAMOL" in normalized:
        score += 30.0
    if fields.get("dosage"):
        score += 25.0
    if "TABLET" in normalized or "TABLETS" in normalized or "CAPSULE" in normalized:
        score += 15.0
    if fields.get("manufacturer"):
        score += 15.0
    if fields.get("expiry_date"):
        score += 10.0

    return float(min(score, 100.0))


def signal_verdict_from_confidence(confidence: float) -> str:
    """Map signal confidence to a deterministic verdict."""
    if confidence >= 70:
        return "GENUINE"
    if confidence >= 50:
        return "SUSPICIOUS"
    return "INVALID"


def parse_api_ninjas_payload(payload: Any) -> Dict[str, Any]:
    """Parse API Ninjas payload into text + structured fields + signal confidence."""
    text = combine_ninjas_text(payload)
    fields = extract_fields_from_ninjas_text(text)
    confidence = calculate_signal_confidence(text, fields)
    verdict = signal_verdict_from_confidence(confidence)
    return {
        "text": text,
        "fields": fields,
        "signal_confidence": confidence,
        "signal_verdict": verdict,
    }


def _extract_error_message(payload) -> str:
    """Build a compact error message from API Ninjas response payload."""
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if value:
                return str(value).strip()
    if isinstance(payload, list) and payload:
        head = payload[0]
        if isinstance(head, dict):
            for key in ("error", "message", "detail"):
                value = head.get(key)
                if value:
                    return str(value).strip()
    return ""


def _parse_api_ninjas_text(payload) -> str:
    """Extract text from API Ninjas OCR response payload."""
    return parse_api_ninjas_payload(payload).get("text", "")


def _encode_jpeg_under_limit(image: Image.Image, max_bytes: int = FREE_TIER_MAX_BYTES) -> bytes:
    """Encode an image to JPEG and keep it under the free-tier upload limit."""
    working = image.convert("RGB")
    best = b""

    for _ in range(4):
        for quality in [90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40]:
            buffer = io.BytesIO()
            working.save(buffer, format="JPEG", quality=quality, optimize=True)
            encoded = buffer.getvalue()

            if not best or len(encoded) < len(best):
                best = encoded

            if len(encoded) <= max_bytes:
                return encoded

        if max(working.size) <= 720:
            break

        next_width = max(480, int(working.width * 0.82))
        next_height = max(480, int(working.height * 0.82))
        working = working.resize((next_width, next_height), Image.LANCZOS)

    return best


def _build_upload_variants(image_base64: str, mime_type: str) -> List[Tuple[str, bytes, str, str]]:
    """Build upload variants suitable for API Ninjas OCR endpoint."""
    decoded = base64.b64decode(image_base64)
    media_type = mime_type if mime_type and "/" in mime_type else "image/jpeg"

    variants: List[Tuple[str, bytes, str, str]] = []
    if len(decoded) <= FREE_TIER_MAX_BYTES:
        ext = ".png" if "png" in media_type.lower() else ".jpg"
        variants.append(("original", decoded, media_type, f"scan{ext}"))

    image = Image.open(io.BytesIO(decoded)).convert("RGB")

    resized = image.copy()
    if max(resized.size) > 1600:
        resized.thumbnail((1600, 1600), Image.LANCZOS)

    compressed = _encode_jpeg_under_limit(resized)
    if compressed:
        variants.append(("compressed", compressed, "image/jpeg", "scan_compressed.jpg"))

    contrast = ImageOps.autocontrast(ImageOps.grayscale(resized)).convert("RGB")
    contrast_compressed = _encode_jpeg_under_limit(contrast)
    if contrast_compressed:
        variants.append(("autocontrast", contrast_compressed, "image/jpeg", "scan_autocontrast.jpg"))

    unique: List[Tuple[str, bytes, str, str]] = []
    seen = set()
    for label, content, variant_mime, filename in variants:
        key = (len(content), content[:32])
        if key in seen:
            continue
        seen.add(key)
        unique.append((label, content, variant_mime, filename))

    return unique


def _call_api_ninjas(api_key: str, image_bytes: bytes, media_type: str, filename: str) -> Dict[str, Any]:
    """Call API Ninjas OCR endpoint once and return structured OCR output."""
    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key
    files = {"image": (filename, image_bytes, media_type)}

    response = requests.post(API_NINJAS_URL, headers=headers, files=files, timeout=20)

    payload = None
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code >= 400:
        logger.warning(
            "API Ninjas OCR request failed: status=%s error=%s",
            response.status_code,
            _extract_error_message(payload) if payload is not None else response.text[:240],
        )
        return {}

    if payload is None:
        logger.warning("API Ninjas OCR returned non-JSON response")
        return {}

    return parse_api_ninjas_payload(payload)


def extract_structured_api_ninjas(image_base64: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """Extract structured OCR signal data from API Ninjas."""
    api_key = (os.getenv("API_NINJAS_API_KEY") or "").strip()
    if not api_key:
        logger.info("API_NINJAS_API_KEY not configured; trying API Ninjas request without key")

    if not image_base64:
        return {"text": "", "fields": {}, "signal_confidence": 0.0, "signal_verdict": "INVALID"}

    try:
        variants = _build_upload_variants(image_base64=image_base64, mime_type=mime_type)
    except Exception as exc:
        logger.warning("API Ninjas fallback image preparation failed: %s", exc)
        return {"text": "", "fields": {}, "signal_confidence": 0.0, "signal_verdict": "INVALID"}

    for label, image_bytes, media_type, filename in variants:
        try:
            parsed = _call_api_ninjas(
                api_key=api_key,
                image_bytes=image_bytes,
                media_type=media_type,
                filename=filename,
            )
            if parsed.get("text"):
                if label != "original":
                    logger.info("API Ninjas OCR succeeded using %s variant", label)
                parsed["variant"] = label
                return parsed
        except requests.RequestException as exc:
            logger.warning("API Ninjas request failed (%s): %s", label, exc)
        except Exception as exc:
            logger.warning("API Ninjas fallback failed (%s): %s", label, exc)

    return {"text": "", "fields": {}, "signal_confidence": 0.0, "signal_verdict": "INVALID"}


def extract_text_api_ninjas(image_base64: str, mime_type: str = "image/jpeg") -> str:
    """Extract text from base64 image via API Ninjas image-to-text API."""
    return str(extract_structured_api_ninjas(image_base64=image_base64, mime_type=mime_type).get("text") or "")
