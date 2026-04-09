"""OCR.space enrichment service for low-confidence OCR fallback."""

import base64
import io
import logging
import os
from typing import Dict, List

import requests
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

OCR_API_URL = "https://api.ocr.space/parse/image"


def _extract_error_message(payload: Dict) -> str:
    """Build a compact error message from OCR.space response payload."""
    messages: List[str] = []

    errors = payload.get("ErrorMessage")
    if isinstance(errors, list):
        messages.extend(str(item).strip() for item in errors if str(item).strip())
    elif errors:
        messages.append(str(errors).strip())

    details = payload.get("ErrorDetails")
    if details:
        messages.append(str(details).strip())

    return " | ".join(messages).strip()


def _parse_ocr_space_text(payload: Dict) -> str:
    """Extract parsed text from an OCR.space JSON payload."""
    if not isinstance(payload, dict):
        logger.warning("OCR.space returned unexpected response type")
        return ""

    if payload.get("IsErroredOnProcessing"):
        logger.warning("OCR.space processing error: %s", _extract_error_message(payload) or payload)
        return ""

    parsed_results = payload.get("ParsedResults") or []
    if not isinstance(parsed_results, list) or not parsed_results:
        return ""

    chunks = []
    for item in parsed_results:
        if not isinstance(item, dict):
            continue
        text = str(item.get("ParsedText") or "").strip()
        if text:
            chunks.append(text)

    return "\n".join(chunks).strip()


def _call_ocr_space(api_key: str, image_base64: str, media_type: str) -> str:
    """Call OCR.space once and return parsed text."""
    payload = {
        "apikey": api_key,
        "base64Image": f"data:{media_type};base64,{image_base64}",
        "language": "eng",
        "isOverlayRequired": False,
        # Useful for low-quality label photos.
        "scale": True,
        "detectOrientation": True,
        "OCREngine": 2,
    }

    response = requests.post(OCR_API_URL, data=payload, timeout=18)
    response.raise_for_status()
    return _parse_ocr_space_text(response.json())


def _build_autocontrast_variant_base64(image_base64: str, media_type: str) -> str:
    """Build a high-contrast grayscale variant to rescue hard OCR cases."""
    image_bytes = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    enhanced = ImageOps.autocontrast(ImageOps.grayscale(image)).convert("RGB")

    image_format = "PNG" if "png" in media_type.lower() else "JPEG"
    buffer = io.BytesIO()
    save_kwargs = {"format": image_format}
    if image_format == "JPEG":
        save_kwargs["quality"] = 95
    enhanced.save(buffer, **save_kwargs)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_text_ocr_space(image_base64: str, mime_type: str = "image/jpeg") -> str:
    """Extract text from base64 image via OCR.space API.

    Returns empty string when key is missing, API fails, or no text is parsed.
    """
    api_key = (os.getenv("OCR_SPACE_API_KEY") or "").strip()
    if not api_key:
        logger.info("OCR.space fallback skipped: OCR_SPACE_API_KEY not configured")
        return ""

    if not image_base64:
        return ""

    media_type = mime_type if mime_type and "/" in mime_type else "image/jpeg"

    try:
        primary_text = _call_ocr_space(api_key=api_key, image_base64=image_base64, media_type=media_type)
        if primary_text:
            return primary_text

        # Retry with high-contrast variant for difficult low-contrast scans.
        retry_base64 = _build_autocontrast_variant_base64(image_base64, media_type)
        retry_text = _call_ocr_space(api_key=api_key, image_base64=retry_base64, media_type=media_type)
        if retry_text:
            logger.info("OCR.space retry succeeded with autocontrast variant")
            return retry_text

        return ""

    except requests.RequestException as exc:
        logger.warning("OCR.space request failed: %s", exc)
        return ""
    except Exception as exc:
        logger.warning("OCR.space fallback failed: %s", exc)
        return ""
