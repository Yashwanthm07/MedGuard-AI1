"""OCR service for text extraction from medicine images."""
import pytesseract
import re
from difflib import SequenceMatcher
from PIL import Image
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def merge_texts(local_text: str, api_text: str) -> str:
    """Combine local and API OCR outputs while removing duplicate lines."""
    local = (local_text or "").strip()
    api = (api_text or "").strip()

    if not local:
        return api
    if not api:
        return local

    combined = f"{local}\n{api}"
    merged_lines: List[str] = []
    seen = set()

    for raw_line in combined.splitlines():
        line = raw_line.strip()
        if len(line) <= 3:
            continue

        key = " ".join(line.lower().split())
        if key in seen:
            continue

        seen.add(key)
        merged_lines.append(line)

    return "\n".join(merged_lines).strip()


class OCRService:
    """Extracts and parses text data from medicine images."""

    KNOWN_MEDICINES = [
        "PARACETAMOL",
        "CROCIN",
        "DOLO",
        "AZITHROMYCIN",
        "IBUPROFEN",
        "AMOXICILLIN",
        "METFORMIN",
    ]

    MEDICINE_FORM_MARKERS = ["TABLET", "TABLETS", "CAPSULE", "CAPSULES", "SYRUP", "INJECTION"]
    MEDICINE_NOISE_MARKERS = [
        "MANUFACTURED",
        "MARKETED",
        "BATCH",
        "EXP",
        "DOSAGE",
        "MRP",
        "SECTOR",
        "ROAD",
        "FLOOR",
        "PIN",
        "VERDICT",
        "CONFIDENCE",
        "MISSING",
    ]

    MANUFACTURER_LEGAL_MARKERS = {"PVT", "LTD", "LIMITED", "PRIVATE"}
    MANUFACTURER_DOMAIN_MARKERS = {"PHARMA", "PHARMACEUT", "HEALTH", "CARE", "DRUG", "LAB", "MEDIC"}
    MANUFACTURER_NOISE_MARKERS = {
        "BATCH",
        "EXP",
        "DOSAGE",
        "TABLET",
        "CAPSULE",
        "MRP",
        "VERDICT",
        "CONFIDENCE",
        "SCAN RESULT",
        "MISSING",
    }

    COMPANY_TOKEN_FIXES = {
        "LID": "LTD",
        "LITA": "LTD",
        "LIT": "LTD",
        "LTD0": "LTD",
        "LTDO": "LTD",
        "LTO": "LTD",
        "PRARMACE": "PHARMA",
        "PRARMACEUTICALS": "PHARMACEUTICALS",
        "PRARMACEUTLCALS": "PHARMACEUTICALS",
        "CURD": "CURE",
        "PVT": "PVT",
        "LMTD": "LTD",
    }

    COMPANY_FUZZY_LEXICON = [
        "HEALTHCARE",
        "PHARMACEUTICALS",
        "PHARMA",
        "LABORATORIES",
        "LIMITED",
        "PRIVATE",
        "CURE",
        "DRUGS",
    ]

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

    COMMON_TEXT_CORRECTIONS = {
        "GLAXOSRNITHKLINE": "GLAXOSMITHKLINE",
        "GLANOSRNITHKLINE": "GLAXOSMITHKLINE",
        "GLANOSMITHKLINE": "GLAXOSMITHKLINE",
        "GLAX0SMITHKLINE": "GLAXOSMITHKLINE",
        "ILANOSRRTHRLINE": "GLAXOSMITHKLINE",
        "USOSMITHRLINE": "GLAXOSMITHKLINE",
        "PHARMACEUTLCALS": "PHARMACEUTICALS",
        "PHARMACEUTLCAL": "PHARMACEUTICAL",
        "PRARMACE": "PHARMA",
        "PRARMACEUTICALS": "PHARMACEUTICALS",
        "PRARMACEUTLCALS": "PHARMACEUTICALS",
        "HOATTHCARE": "HEALTHCARE",
        " LIT ": " LTD ",
        "LITA": "LTD",
        "LTD0": "LTD",
        "LTO": "LTD",
        "PARACEMETER": "PARACETAMOL",
        "PARACEMETR": "PARACETAMOL",
    }

    @staticmethod
    def fix_common_names(text: str) -> str:
        """Apply domain-specific OCR corrections for known medicine/company strings."""
        if not text:
            return ""

        out = text
        for wrong, correct in OCRService.COMMON_TEXT_CORRECTIONS.items():
            out = out.replace(wrong, correct)
        return out

    @staticmethod
    def _normalize_company_token(token: str) -> str:
        """Normalize OCR-noisy company tokens using explicit + fuzzy corrections."""
        raw = (token or "").upper().strip(" .:-")
        if not raw:
            return ""

        fixed = OCRService.COMPANY_TOKEN_FIXES.get(raw, raw)

        # Keep short/symbol/digit tokens unchanged.
        if len(fixed) < 4 or any(ch.isdigit() for ch in fixed) or fixed in {"PVT", "LTD", "LIMITED", "&"}:
            return fixed

        best_word = fixed
        best_score = 0.0
        for target in OCRService.COMPANY_FUZZY_LEXICON:
            score = SequenceMatcher(None, fixed, target).ratio()
            if score > best_score:
                best_score = score
                best_word = target

        if best_score >= 0.78:
            return best_word

        return fixed

    @staticmethod
    def correct_common_ocr_errors(text: str) -> str:
        """Fix frequent OCR misreads observed on medicine labels."""
        if not text:
            return ""

        replacements = {
            "IEPARACETAMOL": "PARACETAMOL",
            "PARACETAM0L": "PARACETAMOL",
            "IRJA00": "IP 500",
            " 1P ": " IP ",
            "MGG": "MG",
        }

        out = text
        for wrong, correct in replacements.items():
            out = out.replace(wrong, correct)

        # Handle 1P token correction at boundaries too.
        out = re.sub(r"\b1P\b", "IP", out)
        out = re.sub(r"\bEXP([A-Z]{3}[A-Z0-9]{2,4})\b", r"EXP \1", out)
        out = re.sub(r"\bEXPIRY([A-Z]{3}[A-Z0-9]{2,4})\b", r"EXPIRY \1", out)
        out = OCRService.fix_common_names(out)
        return out

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean noisy OCR output while preserving line structure for parsing."""
        if not text:
            return ""

        cleaned_lines = []
        for raw_line in text.splitlines():
            line = raw_line.upper()
            line = line.replace("|", "I")
            line = line.replace(";", ":")
            line = re.sub(r"[^A-Z0-9\s./:&-]", " ", line)
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        """Normalize common OCR artifacts before parsing structured fields."""
        if not text:
            return ""

        normalized = text.upper()
        normalized = normalized.replace("\n", " ")
        normalized = normalized.replace("|", "I")
        normalized = normalized.replace(";", ":")
        normalized = OCRService.correct_common_ocr_errors(normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    @staticmethod
    def extract_lines(text: str) -> List[str]:
        """Split OCR text into useful lines for logic-first field extraction."""
        if not text:
            return []
        return [line.strip() for line in text.split("\n") if len(line.strip()) > 3]

    @staticmethod
    def _normalize_year_token(token: str) -> Optional[str]:
        """Normalize OCR-noisy year fragments (e.g., IS -> 15)."""
        if not token:
            return None

        mapped = str(token).upper().translate(str.maketrans({
            "O": "0",
            "Q": "0",
            "I": "1",
            "L": "1",
            "S": "5",
            "B": "8",
            "Z": "2",
        }))
        digits = re.sub(r"[^0-9]", "", mapped)
        # Keep only well-formed 2-digit or 4-digit years.
        if len(digits) not in {2, 4}:
            return None
        return digits

    # Common date formats
    DATE_PATTERNS = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY or MM/DD/YYYY
        r'\d{1,2}[/-]\d{4}',  # MM/YYYY
        r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',  # 01 Jan 2024
    ]

    # Batch number patterns
    BATCH_PATTERNS = [
        r'(?:BATCH\s*NO|BATCH|LOT|B\.NO)\s*[:\s=#-]+([A-Z0-9 .-]{4,24})',
        r'(?:BATCH\s*N[O0]|B\s*NO|BNO|BCH\s*NO|LOT\s*NO)\s*[:\s=#-]+([A-Z0-9 .-]{4,24})',
    ]

    # Dosage patterns (IMPROVED)
    DOSAGE_PATTERNS = [
        r'(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|μg|iu|units))',
        r'(\d+(?:\.\d+)?\s*(?:tablets?|tabs|capsules?))',
    ]

    # Active ingredient markers
    INGREDIENT_MARKERS = ['contains', 'active ingredient', 'composition', 'ingredients']

    @staticmethod
    def _score_ocr_candidate(text: str) -> float:
        """Score OCR candidate text quality for medicine-label extraction."""
        if not text:
            return 0.0

        normalized = OCRService._normalize_ocr_text(text)
        if len(normalized) < 10:
            return 0.0

        tokens = re.findall(r"[A-Z0-9]{2,}", normalized)
        if not tokens:
            return 0.0

        keywords = [
            "PARACETAMOL", "TABLET", "TABLETS", "CAPSULE", "CAPSULES", "MG", "ML",
            "MANUFACTURED", "MFG", "MARKETED", "BATCH", "EXP", "DOSAGE", "LTD", "PVT",
            "PHARMACEUTICALS", "PHARMA",
        ]
        keyword_hits = sum(1 for kw in keywords if kw in normalized)

        alpha_tokens = [t for t in tokens if any(c.isalpha() for c in t)]
        gibberish_like = 0
        for token in alpha_tokens:
            if len(token) >= 8 and not re.search(r"[AEIOU]", token):
                gibberish_like += 1

        score = 0.0
        score += keyword_hits * 12.0
        score += min(len(tokens), 120) * 0.25
        score += min(len(normalized), 2500) / 250.0
        score -= gibberish_like * 1.5

        if re.search(r"\b(PARACETAMOL|IBUPROFEN|AMOXICILLIN|AZITHROMYCIN)\b", normalized):
            score += 12.0
        if re.search(r"\b(MANUFACTURED|MFG|MARKETED)\b", normalized):
            score += 8.0
        if re.search(r"\b(BATCH|EXP|DOSAGE)\b", normalized):
            score += 8.0

        return score

    @staticmethod
    def _normalize_medicine_name(candidate: str) -> Optional[str]:
        """Normalize noisy medicine-name candidate into a cleaner label string."""
        if not candidate:
            return None

        value = OCRService.correct_common_ocr_errors(candidate.upper())
        value = re.sub(r"[^A-Z0-9\s./-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()

        anchors = [
            "PARACETAMOL", "IBUPROFEN", "AMOXICILLIN", "AZITHROMYCIN", "METFORMIN",
            "CETIRIZINE", "OMEPRAZOLE", "DOLO", "CALPOL",
        ]
        for anchor in anchors:
            idx = value.find(anchor)
            if idx != -1:
                value = value[idx:]
                break

        # Trim leading junk tokens that survived OCR normalization.
        value = re.sub(r"^(?:[A-Z]{1,3}\s+)+(?=(?:TABLET|CAPSULE|IP|\d|PARACETAMOL|IBUPROFEN))", "", value)
        value = re.sub(r"\s+", " ", value).strip()

        # Keep primary strength phrase when present.
        strength_match = re.search(r"^(.*?\b\d{2,4}\s*\.?\s*(?:MG|ML|MCG|G)\b)", value)
        if strength_match and len(strength_match.group(1).split()) >= 3:
            value = strength_match.group(1).strip()

        return value or None

    @staticmethod
    def correct_medicine_name(text: Optional[str]) -> Optional[str]:
        """Map noisy medicine labels to known medicine anchors when possible."""
        if not text:
            return None

        normalized = OCRService._normalize_medicine_name(text) or str(text).upper().strip()
        upper = normalized.upper()

        for medicine in OCRService.KNOWN_MEDICINES:
            if medicine in upper:
                has_context = bool(re.search(r"\b(TABLET|TABLETS|CAPSULE|CAPSULES|SYRUP|INJECTION)\b", upper))
                has_strength = bool(re.search(r"\b\d{2,4}\s*\.?\s*(?:MG|ML|MCG|G)\b", upper))
                if has_context or has_strength:
                    return normalized
                return medicine

        return normalized

    @staticmethod
    def _is_plausible_medicine_name(value: Optional[str]) -> bool:
        """Reject noisy OCR lines that look unlike medicine labels."""
        if not value:
            return False

        upper = OCRService._normalize_ocr_text(str(value))
        if not upper:
            return False

        tokens = re.findall(r"[A-Z0-9]+", upper)
        if not tokens:
            return False

        has_known = any(med in upper for med in OCRService.KNOWN_MEDICINES)
        has_strength = bool(re.search(r"\b\d{2,4}(?:\.\d+)?\s*(MG|ML|MCG|G)\b", upper))
        has_form = any(marker in upper for marker in OCRService.MEDICINE_FORM_MARKERS) or (" IP " in f" {upper} ")

        if not has_known:
            if not ((has_strength and has_form) or (has_strength and len(tokens) <= 4)):
                return False

        if len(tokens) > 10 and not has_known:
            return False

        noise_hits = sum(1 for marker in OCRService.MEDICINE_NOISE_MARKERS if marker in upper)
        if noise_hits >= 2 and not has_known:
            return False

        single_letter_tokens = sum(1 for tok in tokens if tok.isalpha() and len(tok) == 1)
        if single_letter_tokens >= 2 and not has_known:
            return False

        gibberish_tokens = sum(
            1 for tok in tokens
            if len(tok) >= 8 and not re.search(r"[AEIOU]", tok)
        )
        if gibberish_tokens >= 2 and not has_known:
            return False

        return True

    @staticmethod
    def _normalize_strength_value(value: str, unit: str) -> Optional[str]:
        """Normalize dosage strength tokens to canonical format (e.g., 500 MG)."""
        digits = re.sub(r"[^0-9]", "", str(value or ""))
        if not digits:
            return None

        try:
            numeric = int(digits)
        except ValueError:
            return None

        if numeric <= 0:
            return None

        return f"{numeric} {str(unit).upper()}"

    @staticmethod
    def _sanitize_manufacturer_name(value: str) -> str:
        """Normalize manufacturer string and trim common address/noise tails."""
        text = OCRService.fix_common_names((value or "").upper())
        text = text.replace("|", "I")
        text = re.sub(r"[^A-Z0-9\s./:&-]", " ", text)
        text = re.sub(r"\bPVTLTD\b", "PVT LTD", text)
        text = re.sub(r"\bPVTLIMITED\b", "PVT LIMITED", text)
        text = re.sub(r"\bLITA\b", "LTD", text)
        text = re.sub(r"\bLTO\b", "LTD", text)
        text = re.sub(r"\bLTD0\b", "LTD", text)
        text = re.sub(r"\bLTDO\b", "LTD", text)
        text = re.sub(r"\bLTD[A-Z]\b", "LTD", text)
        text = re.sub(r"\bLID\b", "LTD", text)
        text = re.sub(r"\bPVT\.?\b", "PVT", text)
        text = re.sub(r"\bLTD\.?\b", "LTD", text)
        text = re.sub(r"\(.*?\)", " ", text)
        text = re.split(
            r"\b(PLOT|SECTOR|ROAD|FLOOR|SIDCUL|PIN|INDIA|RANIPUR|HARIDWAR|UTTARAKHAND|MOHALI)\b",
            text,
        )[0]

        legal_match = re.search(r"\b(?:PVT\s+LTD|PVT\s+LIMITED|PRIVATE\s+LIMITED|LIMITED|LTD)\b", text)
        if legal_match:
            text = text[:legal_match.end()]
        else:
            # If no legal suffix is available, keep compact pharma-like phrase and drop noisy tail tokens.
            domain_match = re.search(
                r"\b(PHARMACEUTICALS?|PHARMA|HEALTHCARE|LABORATORIES?|DRUGS?)\b",
                text,
            )
            if domain_match:
                text = text[:domain_match.end()]

        text = re.sub(r"\s+", " ", text).strip(" .:-")
        return text

    @staticmethod
    def _is_plausible_manufacturer_name(value: Optional[str]) -> bool:
        """Validate manufacturer field quality to suppress OCR gibberish."""
        if not value:
            return False

        normalized = OCRService._sanitize_manufacturer_name(str(value))
        if not normalized:
            return False

        tokens = re.findall(r"[A-Z0-9&.-]+", normalized)
        if len(tokens) < 2 or len(tokens) > 9:
            return False

        if any(marker in normalized for marker in OCRService.MANUFACTURER_NOISE_MARKERS):
            return False

        legal_hits = sum(1 for tok in tokens if tok in OCRService.MANUFACTURER_LEGAL_MARKERS)
        domain_hits = sum(
            1 for tok in tokens
            if any(marker in tok for marker in OCRService.MANUFACTURER_DOMAIN_MARKERS)
        )

        if legal_hits == 0 and domain_hits == 0:
            return False
        if legal_hits == 0 and len(tokens) > 4:
            return False

        digit_heavy = sum(1 for tok in tokens if sum(1 for ch in tok if ch.isdigit()) >= 2)
        if digit_heavy >= 2:
            return False

        single_letter_tokens = sum(1 for tok in tokens if tok.isalpha() and len(tok) == 1)
        if single_letter_tokens >= 2:
            return False

        gibberish_tokens = 0
        for tok in tokens:
            letters = re.sub(r"[^A-Z]", "", tok)
            if len(letters) >= 8 and not re.search(r"[AEIOU]", letters):
                gibberish_tokens += 1
        if gibberish_tokens >= 2:
            return False

        return True

    @staticmethod
    def is_manufacturer_supported_by_text(raw_text: str, manufacturer: Optional[str]) -> bool:
        """Verify that a manufacturer candidate is actually supported by OCR text evidence."""
        if not manufacturer:
            return False

        manufacturer_clean = OCRService._sanitize_manufacturer_name(str(manufacturer))
        if not manufacturer_clean or not OCRService._is_plausible_manufacturer_name(manufacturer_clean):
            return False

        normalized_text = OCRService._normalize_ocr_text(raw_text or "")
        if not normalized_text:
            return False

        normalized_manufacturer = OCRService._normalize_ocr_text(manufacturer_clean)

        manufacturer_tokens = []
        for token in re.findall(r"[A-Z]{3,}", manufacturer_clean.upper()):
            norm = OCRService._normalize_company_token(token)
            if norm and norm not in {"PVT", "LTD", "LIMITED", "PRIVATE"}:
                manufacturer_tokens.append(norm)

        if not manufacturer_tokens:
            return False

        lines = OCRService.extract_lines(OCRService.clean_text(raw_text or ""))
        marker_re = re.compile(r"\b(MANUF[A-Z]*|MFG|MFD|MARKETED)\b", re.IGNORECASE)
        legal_line_re = re.compile(r"\b(PVT|LTD|LIMITED|PRIVATE|PVTLTD|PVTLIMITED|LITA|LIT|LTO|LTDO|LTD0)\b")

        marker_windows: List[tuple[str, bool]] = []
        marker_found = False
        for idx, line in enumerate(lines):
            if marker_re.search(line):
                marker_found = True
                # Keep same-line and next-line context; previous lines can leak unrelated noise.
                marker_windows.append((lines[idx], True))
                if idx + 1 < len(lines):
                    marker_windows.append((lines[idx + 1], False))

        if marker_found:
            for window, has_marker in marker_windows:
                window_norm = OCRService._normalize_ocr_text(window)
                if not window_norm:
                    continue

                has_direct_phrase = bool(normalized_manufacturer and normalized_manufacturer in window_norm)
                token_hits = [token for token in manufacturer_tokens if token in window_norm]
                if len(token_hits) < 2 and not has_direct_phrase:
                    continue

                if not legal_line_re.search(window_norm):
                    continue

                line_tokens = re.findall(r"[A-Z0-9&.-]+", window_norm)
                if not line_tokens:
                    continue

                first_company_idx = None
                for token_idx, token in enumerate(line_tokens):
                    token_norm = OCRService._normalize_company_token(token)
                    if any(hit in token_norm for hit in token_hits):
                        first_company_idx = token_idx
                        break

                # In marker lines allow slightly longer prefixes, but still reject address-like noise.
                max_prefix_tokens = 5 if has_marker else 3
                if first_company_idx is None or first_company_idx > max_prefix_tokens:
                    continue

                gibberish = 0
                for token in line_tokens:
                    letters = re.sub(r"[^A-Z]", "", token)
                    if len(letters) >= 8 and not re.search(r"[AEIOU]", letters):
                        gibberish += 1
                if gibberish >= 2:
                    continue

                return True

            return False

        # If explicit manufacturer markers are absent, only trust short company-only snippets.
        # Full medicine-label OCR text often includes accidental company-like phrases.
        pack_context_re = re.compile(
            r"\b(PARACETAMOL|IBUPROFEN|AMOXICILLIN|AZITHROMYCIN|METFORMIN|"
            r"TABLET|TABLETS|CAPSULE|CAPSULES|BATCH|EXP|EXPIRY|DOSAGE|MRP|"
            r"\d{2,4}\s*(MG|ML|MCG|G))\b"
        )
        if pack_context_re.search(normalized_text):
            return False

        if len(normalized_text) > 260:
            return False

        line_candidates = OCRService.extract_lines(OCRService.clean_text(raw_text or ""))
        for line in line_candidates:
            line_norm = OCRService._normalize_ocr_text(line)
            if not line_norm:
                continue

            if any(marker in line_norm for marker in ["BATCH", "EXP", "DOSAGE", "MRP", "TABLET", "CAPSULE"]):
                continue

            has_direct_phrase = bool(normalized_manufacturer and normalized_manufacturer in line_norm)

            token_hits = [token for token in manufacturer_tokens if token in line_norm]
            if len(token_hits) < 2 and not has_direct_phrase:
                continue

            if not legal_line_re.search(line_norm):
                continue

            line_tokens = re.findall(r"[A-Z0-9&.-]+", line_norm)
            if not line_tokens:
                continue

            if len(line_tokens) > 7:
                continue

            first_company_idx = None
            for idx, token in enumerate(line_tokens):
                token_norm = OCRService._normalize_company_token(token)
                if any(hit in token_norm for hit in token_hits):
                    first_company_idx = idx
                    break

            # Too much non-company noise before the detected company phrase.
            if first_company_idx is None or first_company_idx > 3:
                continue

            gibberish = 0
            for token in line_tokens:
                letters = re.sub(r"[^A-Z]", "", token)
                if len(letters) >= 8 and not re.search(r"[AEIOU]", letters):
                    gibberish += 1
            if gibberish >= 2:
                continue

            # Without manufacturer markers, only accept direct phrase matches in clean company-like lines.
            if not has_direct_phrase:
                continue

            return True

        return False

    @staticmethod
    def detect_medicine_from_lines(lines: List[str]) -> Optional[str]:
        """Logic-first medicine name extraction from OCR lines."""
        if not lines:
            return None

        candidates = []
        for line in lines:
            upper = line.upper()
            score = 0

            has_form = any(marker in upper for marker in OCRService.MEDICINE_FORM_MARKERS)
            has_strength = bool(re.search(r"\b\d{2,4}\s*\.?\s*(?:MG|ML|MCG|G)\b", upper))
            has_known_medicine = any(med in upper for med in OCRService.KNOWN_MEDICINES)
            has_ip_hint = " IP " in f" {upper} "

            if has_form:
                score += 2
            if has_strength:
                score += 4
            if has_known_medicine:
                score += 5
            if has_form and has_ip_hint:
                score += 2

            if any(noise in upper for noise in ["MANUFACTURED", "MARKETED", "BATCH", "EXP", "DOSAGE", "MFG", "MRP", "STORE"]):
                score -= 5

            if score >= 4 and (has_strength or has_known_medicine or (has_form and has_ip_hint)):
                normalized = OCRService.correct_medicine_name(line)
                if normalized and OCRService._is_plausible_medicine_name(normalized):
                    candidates.append((score, normalized))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        return candidates[0][1]

    @staticmethod
    def extract_text_from_image(pil_image: Image.Image) -> str:
        """
        Extract all text from image using Tesseract OCR with preprocessing.

        Returns: Raw extracted text
        """
        try:
            import cv2
            import numpy as np

            def to_bgr(image_array):
                if len(image_array.shape) == 2:
                    return cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
                return cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

            def build_variants(cv_image):
                gray_local = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                # Low-contrast boost (explicit): histogram equalization + threshold.
                equalized_local = cv2.equalizeHist(gray_local)
                _, thresh_local = cv2.threshold(equalized_local, 150, 255, cv2.THRESH_BINARY)
                adaptive_local = cv2.adaptiveThreshold(
                    equalized_local, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
                )
                return gray_local, equalized_local, thresh_local, adaptive_local

            def run_pass_plan(cv_image):
                gray_local, equalized_local, thresh_local, adaptive_local = build_variants(cv_image)
                best_text_local = ""
                best_score_local = -1.0

                pass_plan = [
                    (gray_local, '--oem 3 --psm 6 -l eng'),
                    (adaptive_local, '--oem 3 --psm 6 -l eng'),
                    (equalized_local, '--oem 3 --psm 11 -l eng'),
                    (thresh_local, '--oem 3 --psm 6 -l eng'),
                ]

                for idx, (variant, config) in enumerate(pass_plan):
                    if best_score_local >= 72 and len(best_text_local) >= 24:
                        break
                    if idx >= 1 and best_score_local >= 52 and len(best_text_local) >= 28:
                        break

                    text_local = (pytesseract.image_to_string(variant, config=config) or "").strip()
                    if len(text_local) < 8:
                        continue
                    score_local = OCRService._score_ocr_candidate(text_local)
                    if score_local > best_score_local or (score_local == best_score_local and len(text_local) > len(best_text_local)):
                        best_text_local = text_local
                        best_score_local = score_local

                return best_text_local, best_score_local

            def merge_chunks(chunks: List[str]) -> str:
                merged = []
                seen = set()
                for chunk in chunks:
                    text_chunk = (chunk or "").strip()
                    if not text_chunk:
                        continue
                    key = " ".join(text_chunk.lower().split())
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(text_chunk)
                return "\n".join(merged)

            img = to_bgr(np.array(pil_image))
            best_text, best_score = run_pass_plan(img)
            rotation_candidates = [best_text] if best_text else []

            upper_best = (best_text or "").upper()
            needs_rotation_fallback = (
                best_score < 58
                or not re.search(r"\b(EXP|EXPIRY|MANUFACTURED|MFG|PVT|LTD)\b", upper_best)
            )

            if needs_rotation_fallback:
                rotation_map = {
                    90: cv2.ROTATE_90_CLOCKWISE,
                    180: cv2.ROTATE_180,
                    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
                }
                for angle in [90, 270, 180]:
                    rotated = cv2.rotate(img, rotation_map[angle])
                    rotated_text, rotated_score = run_pass_plan(rotated)
                    if not rotated_text:
                        continue

                    if rotated_score > best_score:
                        best_text, best_score = rotated_text, rotated_score

                    if rotated_score >= max(22.0, best_score * 0.72):
                        rotation_candidates.append(rotated_text)

                    # Enough orientation coverage; stop early.
                    if len(rotation_candidates) >= 3:
                        break

            text = merge_chunks(rotation_candidates) if rotation_candidates else best_text
            text = OCRService.fix_common_names(text)
            
            # Quality check: garbage text has < 10 chars
            if len(text) < 10:
                logger.warning(f"OCR returned low-quality text (length: {len(text)})")
                return ""
            
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return ""

    @staticmethod
    def extract_text_with_boxes(pil_image: Image.Image) -> Dict[str, any]:
        """
        Extract OCR text plus per-word bounding boxes.

        Returns:
            {
                "text": str,
                "boxes": [{"text": str, "x": int, "y": int, "w": int, "h": int, "conf": float}],
                "image_size": {"width": int, "height": int}
            }
        """
        try:
            config = '--psm 6 -l eng'
            data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)

            boxes = []
            tokens = []
            n = len(data.get("text", []))
            for i in range(n):
                text = (data["text"][i] or "").strip()
                conf_raw = data.get("conf", ["-1"])[i]
                try:
                    conf = float(conf_raw)
                except Exception:
                    conf = -1.0

                if not text or conf < 35:
                    continue

                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])

                tokens.append(text)
                boxes.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "conf": conf,
                })

            return {
                "text": " ".join(tokens).strip(),
                "boxes": boxes,
                "image_size": {"width": pil_image.width, "height": pil_image.height},
            }
        except Exception as e:
            logger.error(f"OCR extraction with boxes failed: {e}")
            return {
                "text": OCRService.extract_text_from_image(pil_image),
                "boxes": [],
                "image_size": {"width": pil_image.width, "height": pil_image.height},
            }

    @staticmethod
    def detect_medicine_name(text: str) -> Optional[str]:
        """
        Detect medicine name by selecting the strongest meaningful line.
        """
        lines = text.split('\n') if '\n' in text else [text]

        candidates = []
        positive_markers = {
            "PARACETAMOL", "IBUPROFEN", "AMOXICILLIN", "AZITHROMYCIN", "METFORMIN",
            "TABLET", "TABLETS", "CAPSULE", "CAPSULES", "SYRUP", "INJECTION", "MG", "ML", "IP",
        }
        negative_markers = {
            "MANUFACTURED", "MARKETED", "DOSAGE", "STORAGE", "BATCH", "EXP", "MFG", "MRP",
            "SECTOR", "FLOOR", "ROAD", "INDIA", "PHYSICIAN", "KEEP", "PROTECTED",
        }

        for line in lines:
            line_clean = line.strip()
            if not (7 < len(line_clean) < 100):
                continue

            upper = line_clean.upper()
            tokens = re.findall(r"[A-Z0-9]+", upper)
            if not tokens:
                continue

            pos_hits = sum(1 for marker in positive_markers if marker in upper)
            neg_hits = sum(1 for marker in negative_markers if marker in upper)

            score = 0
            score += pos_hits * 4
            score -= neg_hits * 4
            score += min(4, len(tokens) // 3)

            # Strongly prefer lines that look like medicine labels.
            has_primary_marker = any(anchor in upper for anchor in [
                "PARACETAMOL", "IBUPROFEN", "AMOXICILLIN", "AZITHROMYCIN", "METFORMIN",
                "TABLET", "TABLETS", "CAPSULE", "CAPSULES", "SYRUP", "INJECTION",
            ])
            has_strength = bool(re.search(r"\b\d{2,4}\s*\.?\s*(?:MG|ML|MCG|G)\b", upper))
            has_form_hint = any(hint in upper for hint in ["TABLET", "CAPSULE", " IP", "IP "])
            has_medicine_marker = has_primary_marker or (has_strength and has_form_hint)
            if has_medicine_marker:
                score += 3

            candidates.append((score, line_clean, has_medicine_marker))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        for score, candidate, has_medicine_marker in candidates[:6]:
            if score < -3:
                continue

            normalized = OCRService._normalize_medicine_name(candidate)
            if not normalized:
                continue

            normalized_upper = normalized.upper()
            if any(bad in normalized_upper for bad in ["MANUFACTURED", "MARKETED", "DOSAGE", "STORAGE"]):
                continue
            if not OCRService._is_plausible_medicine_name(normalized):
                continue

            return normalized

        return None

    @staticmethod
    def detect_batch_number(text: str) -> Optional[str]:
        """
        Extract batch/lot number from text.
        """
        def _normalize_batch_candidate(value: str) -> str:
            candidate = (value or "").strip().upper().strip(" .:-#")
            candidate = re.sub(r"^(?:NO|N0|BNO|HNO)[.:-]?", "", candidate).strip(" .:-#")
            # OCR.space may split numeric batches as "6252 29".
            candidate = re.sub(r"\s+", "", candidate)
            return candidate

        search_text = OCRService._normalize_ocr_text(text)

        for pattern in OCRService.BATCH_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                batch = match.group(1) if match.lastindex else match.group(0)
                batch = _normalize_batch_candidate(batch)
                if OCRService.is_valid_batch(batch):
                    return batch

        # Fuzzy fallback for noisy OCR: BATCH/B.NO/LOT followed by token.
        fuzzy_patterns = [
            r"(?:BATCH\s*NO|BATCH|B\.?\s*NO|LOT|L0T)\s*[:#-]?\s*([A-Z0-9-]{4,20})",
        ]
        for pattern in fuzzy_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                batch = _normalize_batch_candidate(match.group(1))
                if OCRService.is_valid_batch(batch):
                    return batch

        # Final heuristic: only inspect lines that contain batch markers,
        # then pick the best candidate token near that marker.
        lines = search_text.split('\n') if '\n' in search_text else [search_text]
        marker_re = re.compile(r'\b(BATCH|LOT|B\.?\s*NO|BNO|BCH|HNO)\b', re.IGNORECASE)
        for line in lines:
            marker_match = marker_re.search(line)
            if not marker_match:
                continue

            # Only inspect text after the marker to avoid unrelated tokens (e.g., medicine strength).
            marker_window = line[marker_match.start():]
            token_matches = re.findall(r'\b[A-Z0-9.-]{4,20}\b', marker_window)
            for token in token_matches:
                normalized = _normalize_batch_candidate(token)
                if not normalized:
                    continue
                if normalized in {"BATCH", "LOT", "BNO", "HNO", "NO", "B"}:
                    continue
                if re.fullmatch(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', normalized):
                    continue
                if not any(ch.isdigit() for ch in normalized):
                    continue
                if OCRService.is_valid_batch(normalized):
                    return normalized

        # Last fallback: consider globally plausible batch-like tokens.
        all_tokens = re.findall(r"(?<![A-Z0-9.-])[A-Z0-9.-]{5,20}(?![A-Z0-9.-])", search_text)
        alnum_candidates = []
        numeric_candidates = []
        for token in all_tokens:
            candidate = _normalize_batch_candidate(token)
            if not candidate:
                continue
            if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", candidate):
                continue
            if re.search(r"(?:MG|ML|MCG|TABLET|CAPSULE|DOSAGE|IP)$", candidate):
                continue
            if not OCRService.is_valid_batch(candidate):
                continue

            if any(ch.isalpha() for ch in candidate) and any(ch.isdigit() for ch in candidate):
                alnum_candidates.append(candidate)
            elif re.fullmatch(r"\d{5,10}", candidate) and not candidate.startswith(("19", "20")):
                numeric_candidates.append(candidate)

        if alnum_candidates:
            return alnum_candidates[0]
        if numeric_candidates:
            return numeric_candidates[0]

        return None

    @staticmethod
    def is_valid_batch(batch: Optional[str]) -> bool:
        """Validate batch values to reject noisy OCR tokens."""
        if not batch:
            return False

        raw = str(batch).strip().upper().strip(" .,:;-")
        raw = re.sub(r"\s+", "", raw)
        if len(raw) < 5:
            return False
        if len(raw) > 20:
            return False
        if "." in raw:
            return False
        if not re.fullmatch(r"[A-Z0-9-]+", raw):
            return False
        digit_count = sum(1 for c in raw if c.isdigit())
        if digit_count < 3:
            return False

        if any(med in raw for med in OCRService.KNOWN_MEDICINES):
            return False

        # Reject dosage-like strength tokens that are frequently misread as batch IDs.
        if re.fullmatch(r"IP\d{2,4}", raw):
            return False
        if re.fullmatch(r"\d{2,4}(?:MG|ML|MCG|G)", raw):
            return False

        if re.search(r"(?:MG|ML|MCG|TABLET|CAPSULE|DOSAGE|EXP|MRP)$", raw):
            return False

        # Reject common price-like short decimals.
        if re.fullmatch(r"\d{1,2}\.\d{1,2}", raw):
            return False

        # If pure digits, require meaningful length.
        if re.fullmatch(r"\d+", raw):
            if len(raw) < 5:
                return False
            if raw.startswith(("19", "20")) and len(raw) in {6, 8}:
                return False

        return True

    @staticmethod
    def detect_expiry_date(text: str) -> Optional[str]:
        """
        Extract expiry/expiration date from text.
        """
        search_text = OCRService._normalize_ocr_text(text)

        # Look for expiry-related keywords first
        expiry_keywords = ['EXP', 'EXPIRY', 'EXPIRES', 'EXP DATE', 'EXPIRATION', 'VALID TILL', 'USE BEFORE', 'USE BY']

        lines = search_text.split(' ')
        scan_line = " ".join(lines)
        for keyword in expiry_keywords:
            idx = scan_line.find(keyword)
            if idx != -1:
                window = scan_line[idx: idx + 80]
                m = re.search(r"\b\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", window)
                if m:
                    candidate = m.group(0)
                    return candidate if OCRService.is_valid_expiry(candidate) else None

                month_window = scan_line[idx: idx + 100]
                month_match = re.search(
                    r"\b(?:\d{1,2}\s*)?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)(?:[\s./-]?)([0-9OQILSBZ]{2,4})\b",
                    month_window,
                )
                if month_match:
                    month = month_match.group(1)
                    year = OCRService._normalize_year_token(month_match.group(2))
                    if not year:
                        continue
                    if len(year) == 2:
                        year = f"20{year}"
                    return f"{OCRService.MONTH_ALIASES[month]}/{year}"

        # More permissive whole-text matches
        permissive_patterns = [
            r"\b\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        ]
        for pattern in permissive_patterns:
            matches = re.findall(pattern, search_text)
            if matches:
                candidate = matches[-1]
                if OCRService.is_valid_expiry(candidate):
                    return candidate

        # Legacy line-based fallback for mixed-case OCR text.
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            for keyword in expiry_keywords:
                if keyword.lower() in line_lower:
                    # Try to extract date from this line
                    for pattern in OCRService.DATE_PATTERNS:
                        match = re.search(pattern, line)
                        if match:
                            candidate = match.group(0).strip()
                            if OCRService.is_valid_expiry(candidate):
                                return candidate

        # If no keyword match, search entire text for dates
        for pattern in OCRService.DATE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                # Return the last date found (usually expiry is at end)
                candidate = matches[-1] if isinstance(matches[-1], str) else matches[-1][0]
                if OCRService.is_valid_expiry(candidate):
                    return candidate

        month_match = re.search(
            r"\b(?:\d{1,2}\s*)?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)(?:[\s./-]?)([0-9OQILSBZ]{2,4})\b",
            search_text,
        )
        if month_match:
            month = month_match.group(1)
            year = OCRService._normalize_year_token(month_match.group(2))
            if not year:
                return None
            if len(year) == 2:
                year = f"20{year}"
            return f"{OCRService.MONTH_ALIASES[month]}/{year}"

        return None

    @staticmethod
    def is_valid_expiry(val: Optional[str]) -> bool:
        """Validate expiry in MM/YY or MM/YYYY style to avoid noisy tokens like 34-35."""
        raw = (val or "").upper().strip()
        if re.fullmatch(r'(0[1-9]|1[0-2])[/-]\d{2,4}', raw):
            return True
        if re.fullmatch(r'(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)\s*[/-]?\s*\d{2,4}', raw):
            return True
        if re.fullmatch(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', raw):
            return True
        return False

    @staticmethod
    def detect_dosage(text: str) -> Optional[str]:
        """
        Extract medicine dosage/strength from text.
        """
        search_text = OCRService._normalize_ocr_text(text)

        if not search_text:
            return None

        # High-confidence medicine-context strength patterns.
        strong_context_patterns = [
            r"\b(?:PARACETAMOL|IBUPROFEN|AMOXICILLIN|AZITHROMYCIN|METFORMIN|DOLO|CALPOL)[A-Z0-9\s./-]{0,40}?\b(\d{2,4})(?:[.,]\d+)?\s*(MG|ML|MCG|G)\b",
            r"\b(?:TABLET|TABLETS|CAPSULE|CAPSULES)\s+IP\s*(\d{2,4})(?:[.,]\d+)?\s*(MG|ML|MCG|G)\b",
            r"\bIP\s*[-:]?\s*(\d{2,4})(?:[.,]\d+)?\s*(MG|ML|MCG|G)\b",
            r"\b(\d{2,4})(?:[.,]\d+)?\s*(MG|ML|MCG|G)\s+(?:TABLET|TABLETS|CAPSULE|CAPSULES)\b",
        ]
        for pattern in strong_context_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if not match:
                continue
            normalized = OCRService._normalize_strength_value(match.group(1), match.group(2))
            if normalized:
                return normalized

        candidate_scores: Dict[str, int] = {}
        candidate_counts: Dict[str, int] = {}
        lines = OCRService.extract_lines(OCRService.clean_text(text))
        if not lines:
            lines = [search_text]

        for line in lines:
            line_upper = OCRService._normalize_ocr_text(line)
            if not line_upper:
                continue

            line_score = 1
            if any(marker in line_upper for marker in OCRService.MEDICINE_FORM_MARKERS) or (" IP " in f" {line_upper} "):
                line_score += 3
            if any(med in line_upper for med in OCRService.KNOWN_MEDICINES):
                line_score += 3
            if "DOSAGE" in line_upper:
                line_score += 1
            if any(marker in line_upper for marker in ["EACH", "CONTAINS", "COMPOSITION", "INGREDIENT", "PER TABLET", "PER CAPSULE"]):
                line_score -= 3
            if any(marker in line_upper for marker in ["MRP", "BATCH", "EXP", "MANUFACTURED", "MARKETED"]):
                line_score -= 2

            for match in re.finditer(r"\b(\d{2,4})(?:[.,]\d+)?\s*(MG|ML|MCG|G|IU|UNITS)\b", line_upper, re.IGNORECASE):
                normalized = OCRService._normalize_strength_value(match.group(1), match.group(2))
                if not normalized:
                    continue

                score = max(1, line_score)
                prefix = line_upper[max(0, match.start() - 12):match.start()]
                suffix = line_upper[match.end():match.end() + 12]
                if "IP" in prefix or "IP" in suffix:
                    score += 2

                candidate_scores[normalized] = candidate_scores.get(normalized, 0) + score
                candidate_counts[normalized] = candidate_counts.get(normalized, 0) + 1

        if candidate_scores:
            best = max(
                candidate_scores.keys(),
                key=lambda item: (
                    candidate_scores[item],
                    candidate_counts.get(item, 0),
                    len(item),
                ),
            )
            return best

        # Common instruction-style dosage text often present on labels.
        instruction_patterns = [
            r'DOSAGE\s*[:\-]?\s*AS\s+DIRECTED(?:\s+BY\s+THE\s+PHYSICIAN)?',
            r'AS\s+DIRECTED\s+BY\s+THE\s+PHYSICIAN',
        ]
        for pattern in instruction_patterns:
            instruction_match = re.search(pattern, search_text, re.IGNORECASE)
            if instruction_match:
                return "AS DIRECTED BY PHYSICIAN"

        # Last attempt: infer from medicine-name style tokens like "IP 500" + nearby MG marker.
        ip_strength = re.search(r'\bIP\s*\d{2,4}\b', search_text)
        has_mg_marker = bool(re.search(r'\bMG\b', search_text))
        if ip_strength and has_mg_marker:
            value = re.search(r'\d{2,4}', ip_strength.group(0))
            if value:
                normalized = OCRService._normalize_strength_value(value.group(0), "MG")
                if normalized:
                    return normalized

        return None

    @staticmethod
    def detect_manufacturer_from_lines(lines: List[str]) -> Optional[str]:
        """Detect manufacturer from structured OCR lines before full-text fallbacks."""
        if not lines:
            return None

        for line in lines:
            upper = line.upper()
            if not any(marker in upper for marker in ["PVT", "LTD", "LIMITED", "PHARMA", "PHARMACEUT", "HEALTHCARE"]):
                continue
            if any(skip in upper for skip in ["BATCH", "EXP", "DOSAGE", "STORE", "MRP", "VERDICT", "CONFIDENCE", "MISSING"]):
                continue

            compact = re.sub(
                r"^(?:MANUFACTURED|MFG|MFD|MARKETED|MANUF[A-Z]*|M[A-Z]{2,16}ACTURED)\s*BY\s*[:\-]?\s*",
                "",
                upper,
            ).strip()
            if not compact:
                continue

            strict = OCRService.detect_manufacturer(compact)
            if strict and OCRService._is_plausible_manufacturer_name(strict):
                return OCRService._sanitize_manufacturer_name(strict)

            fallback = OCRService._sanitize_manufacturer_name(compact)
            if OCRService._is_plausible_manufacturer_name(fallback):
                return fallback

        return None

    @staticmethod
    def detect_batch_from_lines(lines: List[str]) -> Optional[str]:
        """Detect batch from OCR lines with marker-first strategy."""
        if not lines:
            return None

        for line in lines:
            upper = line.upper()
            if "BATCH" in upper or "LOT" in upper or re.search(r"\bB\.?\s*NO\b", upper):
                candidate = OCRService.detect_batch_number(upper)
                if candidate:
                    return candidate

        return None

    @staticmethod
    def detect_expiry_from_lines(lines: List[str]) -> Optional[str]:
        """Detect expiry from OCR lines with strict month/year validation."""
        if not lines:
            return None

        for line in lines:
            upper = line.upper()
            if any(key in upper for key in ["EXP", "EXPIRY", "VALID", "USE BEFORE", "USE BY"]):
                candidate = OCRService.detect_expiry_date(upper)
                if candidate and OCRService.is_valid_expiry(candidate):
                    return candidate

        return None

    @staticmethod
    def validate_fields(data: Dict[str, Optional[any]]) -> Dict[str, Optional[any]]:
        """Validate parsed fields to drop common OCR false positives."""
        validated = dict(data or {})

        dosage = validated.get("dosage")
        if dosage:
            dosage_upper = str(dosage).upper()
            has_numeric_strength = bool(re.search(r"\b\d{2,4}(?:\.\d+)?\s*(MG|ML|MCG|G|IU|UNITS)\b", dosage_upper))
            is_instruction = "AS DIRECTED" in dosage_upper
            if has_numeric_strength:
                strength_match = re.search(r"\b(\d{2,4})(?:\.\d+)?\s*(MG|ML|MCG|G|IU|UNITS)\b", dosage_upper)
                if strength_match:
                    normalized = OCRService._normalize_strength_value(strength_match.group(1), strength_match.group(2))
                    validated["dosage"] = normalized or dosage_upper
            elif is_instruction:
                validated["dosage"] = "AS DIRECTED BY PHYSICIAN"
            else:
                validated["dosage"] = None

        expiry = validated.get("expiry_date")
        if expiry:
            expiry_text = str(expiry).strip()
            if len(expiry_text) < 5 or not OCRService.is_valid_expiry(expiry_text):
                validated["expiry_date"] = None

        batch = validated.get("batch_number")
        if batch and not OCRService.is_valid_batch(str(batch)):
            validated["batch_number"] = None

        manufacturer = validated.get("manufacturer")
        if manufacturer:
            cleaned_manufacturer = OCRService._sanitize_manufacturer_name(str(manufacturer))
            if OCRService._is_plausible_manufacturer_name(cleaned_manufacturer):
                validated["manufacturer"] = cleaned_manufacturer
            else:
                validated["manufacturer"] = None

        medicine_name = validated.get("medicine_name")
        if medicine_name:
            corrected_name = OCRService.correct_medicine_name(str(medicine_name))
            corrected_upper = str(corrected_name or "").upper()

            # Reject quantity-only pack descriptors misread as medicine names.
            quantity_only = bool(re.fullmatch(r"\d+\s*(TABLET|TABLETS|CAPSULE|CAPSULES)\b.*", corrected_upper))
            has_known = any(med in corrected_upper for med in OCRService.KNOWN_MEDICINES)
            if quantity_only and not has_known:
                corrected_name = None

            if corrected_name and not OCRService._is_plausible_medicine_name(corrected_name):
                corrected_name = None

            validated["medicine_name"] = corrected_name

        # Reconcile dosage with medicine-name strength when both are present but inconsistent.
        medicine_name = validated.get("medicine_name")
        dosage = validated.get("dosage")
        if medicine_name and dosage:
            name_strength_match = re.search(
                r"\b(\d{2,4})(?:\.\d+)?\s*(MG|ML|MCG|G|IU|UNITS)\b",
                str(medicine_name).upper(),
            )
            dosage_match = re.search(
                r"\b(\d{2,4})(?:\.\d+)?\s*(MG|ML|MCG|G|IU|UNITS)\b",
                str(dosage).upper(),
            )
            if name_strength_match and dosage_match:
                normalized_name_strength = OCRService._normalize_strength_value(
                    name_strength_match.group(1),
                    name_strength_match.group(2),
                )
                normalized_dosage = OCRService._normalize_strength_value(
                    dosage_match.group(1),
                    dosage_match.group(2),
                )
                if normalized_name_strength and normalized_dosage and normalized_name_strength != normalized_dosage:
                    validated["dosage"] = normalized_name_strength

        return validated

    @staticmethod
    def detect_manufacturer(text: str) -> Optional[str]:
        """
        Extract manufacturer name from text.
        """
        def normalize_candidate(value: str) -> str:
            candidate = (value or "").upper()
            candidate = candidate.replace("|", "I")
            candidate = re.sub(r"[^A-Z0-9\s./:&-]", " ", candidate)
            candidate = re.sub(
                r"^(?:MANUFACTURED|MFG|MFD|MARKETED|MANUF[A-Z]*|M[A-Z]{2,16}ACTURED)\s+BY\s*[:\-]?\s*",
                "",
                candidate,
            )
            candidate = re.sub(r"\bPVTLTD\b", "PVT LTD", candidate)
            candidate = re.sub(r"\bPVTLIMITED\b", "PVT LIMITED", candidate)
            candidate = re.sub(r"\bLID\b", "LTD", candidate)
            candidate = re.sub(r"\bLTD\.?\b", "LTD", candidate)
            candidate = re.sub(r"\bPVT\.?\b", "PVT", candidate)
            candidate = re.sub(r"\s+", " ", candidate).strip(" .:-")

            normalized_tokens = []
            for token in candidate.split():
                normalized_tokens.append(OCRService._normalize_company_token(token))

            candidate = " ".join(t for t in normalized_tokens if t).strip()
            candidate = re.sub(r"\s+", " ", candidate)
            return candidate

        def score_candidate(value: str) -> int:
            cand = normalize_candidate(value)
            if not cand:
                return -100

            score = 0
            if "PVT" in cand:
                score += 3
            if "LTD" in cand or "LIMITED" in cand:
                score += 3

            for kw in ["HEALTH", "CARE", "PHARMA", "PHARMACEUT", "DRUG", "LAB", "MEDIC"]:
                if kw in cand:
                    score += 2
                    break

            if len(cand.split()) >= 2:
                score += 1

            legal_or_domain_hits = sum(
                1 for kw in ["PVT", "LTD", "LIMITED", "PHARMA", "PHARMACEUT", "HEALTH", "LAB", "DRUG"]
                if kw in cand
            )
            score += min(4, legal_or_domain_hits)

            # Penalize long noisy address-like captures.
            token_count = len(cand.split())
            if token_count > 10:
                score -= 4
            if len(cand) > 90:
                score -= 3
            if sum(1 for sw in stop_words if sw in cand) >= 2:
                score -= 4

            digit_heavy_tokens = 0
            for token in cand.split():
                if sum(1 for ch in token if ch.isdigit()) >= 2:
                    digit_heavy_tokens += 1
            if token_count > 0 and (digit_heavy_tokens / token_count) > 0.25:
                score -= 4

            # Penalize heavy OCR gibberish words.
            for token in cand.split():
                letters = re.sub(r"[^A-Z]", "", token)
                if len(letters) >= 8 and not re.search(r"[AEIOU]", letters):
                    score -= 1

            return score

        stop_words = {
            "PLOT", "SECTOR", "SIDCUL", "RANIPUR", "HARIDWAR", "UTTARAKHAND", "MOHALI", "FLOOR",
            "MARKET", "ENCLAVE", "ROAD", "DIST", "STATE", "INDIA", "PIN", "BATCH", "EXP", "DOSAGE",
            "HNO", "BNO", "BCH", "NO",
        }

        raw_text = OCRService.fix_common_names((text or "").upper())

        # Strong pattern first: MANUFACTURED BY: <company>
        for raw_line in raw_text.splitlines():
            strong_match = re.search(r"\b(?:MANUFACTURED|MFG|MARKETED)\s+BY\s*[:\-]?\s*(.+)", raw_line, re.IGNORECASE)
            if not strong_match:
                continue

            candidate_line = strong_match.group(1).strip()
            candidate_line = re.split(r"\b(BATCH|EXP|DOSAGE|MRP|STORE|STORAGE|PIN|ROAD|SECTOR)\b", candidate_line)[0].strip(" .:-")
            candidate = normalize_candidate(candidate_line)
            if candidate and any(marker in candidate for marker in ["PVT", "LTD", "LIMITED", "PHARMA", "PHARMACEUT", "HEALTH"]):
                return candidate

        # Fallback: company-like line detection for common pharma names.
        for raw_line in raw_text.splitlines():
            stripped = raw_line.strip()
            if not stripped or len(stripped) > 140:
                continue
            fallback_match = re.search(
                r"([A-Z][A-Z\s.&/-]{2,120}(?:SMITHKLINE|PHARMA|PHARMACEUTICALS|LTD|LIMITED)[A-Z\s.&/-]{0,24})",
                stripped,
                re.IGNORECASE,
            )
            if fallback_match:
                candidate = normalize_candidate(fallback_match.group(1))
                if candidate and not any(sw in candidate for sw in ["PLOT", "SECTOR", "ROAD", "PIN"]):
                    return candidate

        candidates: List[str] = []
        lines = [normalize_candidate(line) for line in (text or "").split("\n") if line and line.strip()]

        for line in lines:
            tokens = line.split()
            if not tokens:
                continue

            has_marker = any(tok.startswith("MAN") or tok in {"MFG", "MFD", "MARKETED"} for tok in tokens)
            if not has_marker or "BY" not in tokens:
                continue

            by_idx = tokens.index("BY")
            company_tokens = []
            for token in tokens[by_idx + 1:]:
                cleaned = token.strip(" .:-")
                if not cleaned:
                    continue
                if cleaned in stop_words:
                    break
                if any(ch.isdigit() for ch in cleaned) and company_tokens:
                    break
                company_tokens.append(cleaned)
                if len(company_tokens) >= 12:
                    break

            candidate = normalize_candidate(" ".join(company_tokens))
            if candidate:
                candidates.append(candidate)

        normalized_all = normalize_candidate(text or "")

        # High-value brand fallback for common packs where marker line is noisy.
        if any(tag in normalized_all for tag in ["GLAXO", "SMITHKLINE", "GSK"]):
            return "GLAXOSMITHKLINE PHARMACEUTICALS LIMITED"

        for match in re.finditer(r"([A-Z][A-Z\s.&/-]{3,90}\bPVT\s*(?:LTD|LIMITED)\b)", normalized_all):
            candidates.append(normalize_candidate(match.group(1)))

        for match in re.finditer(r"([A-Z][A-Z\s.&/-]{3,120}\b(?:PHARMACEUTICALS|PHARMA|LABORATORIES|HEALTHCARE)\s*(?:LTD|LIMITED)?\b)", normalized_all):
            candidate = normalize_candidate(match.group(1))
            if not any(stop in candidate for stop in ["PLOT", "ROAD", "SECTOR", "SIDCUL", "MOHALI", "PIN"]):
                candidates.append(candidate)

        if not candidates:
            return None

        best = max(candidates, key=score_candidate)
        return best if score_candidate(best) >= 3 else None

    @staticmethod
    def detect_manufacturer_from_tokens(tokens: List[str]) -> Optional[str]:
        """Extract manufacturer from OCR token stream (e.g., text boxes)."""
        if not tokens:
            return None

        cleaned_tokens = []
        for token in tokens:
            value = (token or "").upper().strip()
            value = value.replace("|", "I")
            value = re.sub(r"[^A-Z0-9./:&-]", "", value)
            value = re.sub(r"\bLID\b", "LTD", value)
            if value == "PVTLTD":
                cleaned_tokens.extend(["PVT", "LTD"])
                continue
            if value == "PVTLIMITED":
                cleaned_tokens.extend(["PVT", "LIMITED"])
                continue
            value = OCRService._normalize_company_token(value)
            if value:
                cleaned_tokens.append(value)

        if not cleaned_tokens:
            return None

        joined_tokens = " ".join(cleaned_tokens)
        if any(tag in joined_tokens for tag in ["GLAXO", "SMITHKLINE", "GSK"]):
            return "GLAXOSMITHKLINE PHARMACEUTICALS LIMITED"

        stop_words = {
            "PLOT", "SECTOR", "SIDCUL", "RANIPUR", "HARIDWAR", "UTTARAKHAND", "MOHALI", "FLOOR",
            "MARKET", "ENCLAVE", "ROAD", "DIST", "STATE", "INDIA", "PIN", "BATCH", "EXP", "DOSAGE",
            "HNO", "BNO", "BCH", "NO",
        }
        company_keywords = {"PVT", "LTD", "LIMITED", "PHARMA", "PHARMACEUT", "HEALTH", "CARE", "DRUG", "LAB"}
        candidates: List[str] = []

        for idx in range(len(cleaned_tokens) - 1):
            token = cleaned_tokens[idx]
            next_token = cleaned_tokens[idx + 1]
            marker = token.startswith("MAN") or token in {"MFG", "MFD", "MARKETED"}
            if not marker:
                continue

            start_idx = None
            if next_token == "BY":
                start_idx = idx + 2
            elif token.endswith("BY"):
                start_idx = idx + 1

            if start_idx is None:
                continue

            company_tokens = []
            for j in range(start_idx, min(start_idx + 12, len(cleaned_tokens))):
                item = cleaned_tokens[j].strip(" .:-")
                if not item:
                    continue
                if item in stop_words:
                    break
                if j + 1 < len(cleaned_tokens) and cleaned_tokens[j + 1] in {"HNO", "BNO", "BCH", "NO"}:
                    break
                if any(ch.isdigit() for ch in item) and company_tokens:
                    break
                company_tokens.append(item)

            candidate = " ".join(company_tokens).strip()
            if candidate and any(k in candidate for k in company_keywords):
                candidates.append(candidate)

        # Fallback: search short token windows containing company suffixes.
        if not candidates:
            for i in range(len(cleaned_tokens)):
                for j in range(i + 2, min(i + 9, len(cleaned_tokens) + 1)):
                    phrase = " ".join(cleaned_tokens[i:j])
                    if "PVT" in phrase and ("LTD" in phrase or "LIMITED" in phrase):
                        if not any(sw in phrase for sw in stop_words):
                            candidates.append(phrase)

        if not candidates:
            return None

        # Prefer richer company descriptors over short/noisy phrases.
        def score(phrase: str) -> int:
            value = phrase.upper()
            s = 0
            if "PVT" in value:
                s += 2
            if "LTD" in value or "LIMITED" in value:
                s += 2
            if any(k in value for k in ["HEALTH", "PHARMA", "PHARMACEUT", "DRUG", "LAB", "CARE"]):
                s += 2
            s += min(2, len(value.split()) // 3)
            return s

        return max(candidates, key=score)

    @staticmethod
    def detect_active_ingredients(text: str) -> List[str]:
        """
        Extract active ingredients from text.
        """
        ingredients = []

        # Look for ingredients section
        lines = text.split('\n')
        in_ingredients_section = False

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Check if entering ingredients section
            for marker in OCRService.INGREDIENT_MARKERS:
                if marker in line_lower:
                    in_ingredients_section = True
                    # Look at next few lines
                    for j in range(i + 1, min(i + 6, len(lines))):
                        ingredient_line = lines[j].strip()
                        if ingredient_line and not ingredient_line.endswith(':'):
                            # Filter out common non-ingredient words
                            if 'each' not in ingredient_line.lower() and len(ingredient_line) > 2:
                                ingredients.append(ingredient_line)
                    break

        return ingredients[:5]  # Limit to 5 ingredients

    @staticmethod
    def detect_batch_number_from_tokens(tokens: List[str]) -> Optional[str]:
        """Extract batch number from OCR token stream (e.g., text boxes)."""
        if not tokens:
            return None

        def _normalize_batch_candidate(value: str) -> str:
            candidate = (value or "").strip().upper().strip(" .:-#")
            candidate = re.sub(r"^(?:NO|N0|BNO|HNO)[.:-]?", "", candidate).strip(" .:-#")
            candidate = re.sub(r"\s+", "", candidate)
            return candidate

        cleaned_tokens = []
        for token in tokens:
            value = (token or "").upper().strip()
            value = value.replace("|", "I")
            value = re.sub(r"[^A-Z0-9./:-]", "", value)
            if value:
                cleaned_tokens.append(value)

        if not cleaned_tokens:
            return None

        marker_re = re.compile(r"^(?:BATCH|LOT|B\.?(?:NO)?|BNO|HNO|BCH)$")
        for idx, token in enumerate(cleaned_tokens):
            if not marker_re.match(token):
                continue
            for next_idx in range(idx + 1, min(idx + 6, len(cleaned_tokens))):
                candidate = _normalize_batch_candidate(cleaned_tokens[next_idx])
                if candidate in {"NO", "BATCH", "LOT"}:
                    continue
                if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", candidate):
                    continue
                if OCRService.is_valid_batch(candidate):
                    return candidate

        # Fallback for common numeric batch shapes when marker was missed.
        alnum_candidates = []
        numeric_candidates = []

        for token in cleaned_tokens:
            candidate = _normalize_batch_candidate(token)
            if not candidate:
                continue

            if re.fullmatch(r"[A-Z0-9.-]{5,20}", candidate) and any(ch.isdigit() for ch in candidate) and any(ch.isalpha() for ch in candidate):
                if OCRService.is_valid_batch(candidate):
                    alnum_candidates.append(candidate)
                continue

            if re.fullmatch(r"\d{5,8}", candidate):
                # Prefer non-year-like integers as a last resort.
                if not candidate.startswith(("19", "20")) and OCRService.is_valid_batch(candidate):
                    numeric_candidates.append(candidate)

        for group in (alnum_candidates, numeric_candidates):
            if group:
                return group[0]

        return None

    @staticmethod
    def detect_expiry_date_from_tokens(tokens: List[str]) -> Optional[str]:
        """Extract expiry date from OCR token stream (e.g., text boxes)."""
        if not tokens:
            return None

        cleaned_tokens = []
        for token in tokens:
            value = (token or "").upper().strip()
            value = value.replace("|", "I")
            value = re.sub(r"[^A-Z0-9./:-]", "", value)
            if value:
                cleaned_tokens.append(value)

        if not cleaned_tokens:
            return None

        # Month + year token-pair pattern (e.g., APR 26, 15 APR 2026).
        for idx, token in enumerate(cleaned_tokens):
            month_key = None
            for alias in OCRService.MONTH_ALIASES:
                if token.startswith(alias):
                    month_key = alias
                    break

            if not month_key:
                continue

            for j in range(idx + 1, min(idx + 4, len(cleaned_tokens))):
                year_tok = cleaned_tokens[j].strip(" .:-")
                normalized_year = OCRService._normalize_year_token(year_tok)
                if normalized_year:
                    year = normalized_year
                    if len(year) == 2:
                        year = f"20{year}"
                    return f"{OCRService.MONTH_ALIASES[month_key]}/{year}"

            compact_match = re.fullmatch(
                r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)(?:[./-]?)([0-9OQILSBZ]{2,4})",
                token,
            )
            if compact_match:
                month = compact_match.group(1)
                year = OCRService._normalize_year_token(compact_match.group(2))
                if not year:
                    continue
                if len(year) == 2:
                    year = f"20{year}"
                return f"{OCRService.MONTH_ALIASES[month]}/{year}"

        expiry_marker_re = re.compile(r"^(?:EXP|EXPIRY|EXPIRES|VALIDTILL|USEBY|USEBEFORE)$")
        date_re = re.compile(r"\b(?:0[1-9]|1[0-2])[/-]\d{2,4}\b|\b\d{1,2}[/-](?:0[1-9]|1[0-2])[/-]\d{2,4}\b")

        for idx, token in enumerate(cleaned_tokens):
            if not expiry_marker_re.match(token):
                continue
            window = " ".join(cleaned_tokens[idx: idx + 6])
            match = date_re.search(window)
            if match:
                candidate = match.group(0)
                if OCRService.is_valid_expiry(candidate):
                    return candidate

        for token in cleaned_tokens:
            match = date_re.search(token)
            if match:
                candidate = match.group(0)
                if OCRService.is_valid_expiry(candidate):
                    return candidate

        candidate_from_text = OCRService.detect_expiry_date(" ".join(cleaned_tokens))
        if candidate_from_text:
            return candidate_from_text

        return None

    @staticmethod
    def parse_medicine_data(text: str) -> Dict[str, Optional[any]]:
        """
        Parse all extractable medicine data from OCR text.
        
        Pipeline:
        OCR text -> line extraction -> logic-first field detection -> validation -> correction.
        Returns: Dictionary with extracted fields
        """
        # Clean text while preserving line structure for field-wise detection.
        cleaned_text = OCRService.clean_text(text)
        cleaned_text = OCRService.correct_common_ocr_errors(cleaned_text)
        cleaned_text = OCRService.fix_common_names(cleaned_text)
        lines = OCRService.extract_lines(cleaned_text)
        line_text = "\n".join(lines)
        normalized_text = OCRService._normalize_ocr_text(line_text)

        medicine_name = OCRService.detect_medicine_from_lines(lines) or OCRService.detect_medicine_name(cleaned_text)
        medicine_name = OCRService.correct_medicine_name(medicine_name)

        parsed = {
            'medicine_name': medicine_name,
            'batch_number': OCRService.detect_batch_from_lines(lines) or OCRService.detect_batch_number(normalized_text),
            'expiry_date': OCRService.detect_expiry_from_lines(lines) or OCRService.detect_expiry_date(normalized_text),
            'dosage': OCRService.detect_dosage(line_text),
            'manufacturer': OCRService.detect_manufacturer_from_lines(lines) or OCRService.detect_manufacturer(cleaned_text),
            'active_ingredients': OCRService.detect_active_ingredients(cleaned_text),
        }
        validated = OCRService.validate_fields(parsed)

        manufacturer = validated.get('manufacturer')
        if manufacturer and not OCRService.is_manufacturer_supported_by_text(cleaned_text, manufacturer):
            validated['manufacturer'] = None

        return validated
