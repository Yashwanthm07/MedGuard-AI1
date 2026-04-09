"""Free local multi-OCR enrichment utilities.

This module avoids paid API dependencies by combining local OCR engines:
- PaddleOCR (primary local enhancer)
- EasyOCR (optional local enhancer when installed)
"""

import base64
import importlib
import io
import logging
import os
import tempfile
from typing import List

from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

# Avoid startup/network delays when Paddle checks remote model sources.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

_paddle_ocr = None
_paddle_init_failed = False
_easy_reader = None
_easy_init_failed = False


def _get_paddle_ocr():
    """Lazily initialize PaddleOCR once."""
    global _paddle_ocr, _paddle_init_failed
    if _paddle_ocr is not None:
        return _paddle_ocr
    if _paddle_init_failed:
        return None

    try:
        if importlib.util.find_spec("paddleocr") is None:
            _paddle_init_failed = True
            return None

        from paddleocr import PaddleOCR

        _paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en")
        logger.info("PaddleOCR initialized for free OCR enrichment")
        return _paddle_ocr
    except Exception as exc:
        _paddle_init_failed = True
        logger.warning("PaddleOCR unavailable: %s", exc)
        return None


def _get_easy_reader():
    """Lazily initialize EasyOCR once (optional)."""
    global _easy_reader, _easy_init_failed
    if _easy_reader is not None:
        return _easy_reader
    if _easy_init_failed:
        return None

    try:
        if importlib.util.find_spec("easyocr") is None:
            _easy_init_failed = True
            return None

        easyocr_module = importlib.import_module("easyocr")
        _easy_reader = easyocr_module.Reader(["en"], gpu=False)
        logger.info("EasyOCR initialized for free OCR enrichment")
        return _easy_reader
    except Exception as exc:
        _easy_init_failed = True
        logger.warning("EasyOCR unavailable (continuing with Paddle/Tesseract): %s", exc)
        return None


def _decode_base64_image(image_base64: str) -> Image.Image:
    """Decode a base64 image payload into a PIL image."""
    image_bytes = base64.b64decode(image_base64)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _unique_nonempty(items: List[str]) -> List[str]:
    """Return deduplicated, non-empty strings preserving order."""
    out = []
    seen = set()
    for item in items:
        text = (item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def extract_text_multi_ocr(image_path: str) -> str:
    """Extract text using available local OCR engines from an image path."""
    text_data: List[str] = []

    paddle = _get_paddle_ocr()
    if paddle is not None:
        try:
            result = paddle.ocr(image_path)
            if result and result[0]:
                for line in result[0]:
                    if isinstance(line, list) and len(line) > 1:
                        value = line[1][0] if isinstance(line[1], tuple) else ""
                        if value:
                            text_data.append(str(value))
        except Exception as exc:
            logger.warning("PaddleOCR extraction failed: %s", exc)

    easy = _get_easy_reader()
    if easy is not None:
        try:
            result2 = easy.readtext(image_path)
            for row in result2:
                if isinstance(row, (list, tuple)) and len(row) > 1:
                    text_data.append(str(row[1]))
        except Exception as exc:
            logger.warning("EasyOCR extraction failed: %s", exc)

    # Deterministic local fallback: run multiple Tesseract passes to recover extra text.
    if not text_data:
        try:
            image = Image.open(image_path)
            configs = [
                "--oem 3 --psm 6 -l eng",
                "--oem 3 --psm 11 -l eng",
            ]
            for config in configs:
                extracted = (pytesseract.image_to_string(image, config=config) or "").strip()
                if extracted:
                    text_data.append(extracted)
        except Exception as exc:
            logger.warning("Tesseract fallback extraction failed: %s", exc)

    merged = _unique_nonempty(text_data)
    return " ".join(merged)


def extract_text_multi_ocr_from_base64(image_base64: str, mime_type: str = "image/jpeg") -> str:
    """Extract text from a base64 image payload using local multi-OCR engines."""
    suffix = ".jpg"
    if "png" in (mime_type or "").lower():
        suffix = ".png"

    temp_path = None
    try:
        pil_image = _decode_base64_image(image_base64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            pil_image.save(temp_path)

        return extract_text_multi_ocr(temp_path)
    except Exception as exc:
        logger.warning("Multi-OCR base64 extraction failed: %s", exc)
        return ""
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
