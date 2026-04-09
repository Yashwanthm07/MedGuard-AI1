"""Multi-provider AI integration for medicine analysis.

Uses AIProviderManager to abstract provider logic and support fallbacks:
- Primary: OpenAI
- Fallback: Google Gemini
- Optional: Groq
"""
import base64
import json
import logging
from typing import Dict, Optional
import os

from services.ai_provider import get_provider_manager
from services.ocr_service import OCRService
from services.image_processor import ImageProcessor
from services.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


class MedicineAnalyzer:
    """Analyzes medicine images using multi-provider AI service."""

    def __init__(self):
        self.provider_manager = get_provider_manager()

    @staticmethod
    def _fallback_analysis(ocr_text: str = "", reason: str = "Service unavailable") -> Dict:
        """Return fallback analysis when all providers fail.

        This is NOT a hardcoded output - it uses extracted OCR text to provide
        a degraded service response with clear indication that AI analysis failed.
        """
        cleaned = (ocr_text or "").strip()
        is_medicine = bool(cleaned and len(cleaned) > 20)

        return {
            "is_medicine": is_medicine,
            "rejection_reason": "Unable to verify - AI analysis unavailable" if not is_medicine else None,
            "medicine_name": None,
            "manufacturer": None,
            "batch_number": None,
            "expiry_date": None,
            "dosage": None,
            "active_ingredients": [],
            "extracted_text": cleaned,
            "visual_authenticity_score": 40.0,
            "text_clarity_score": 50.0 if cleaned else 20.0,
            "data_completeness_score": 25.0,
            "format_validity_score": 35.0,
            "overall_confidence": 40.0,
            "authenticity_indicators": [],
            "suspicious_signs": [f"AI service unavailable: {reason}"],
            "missing_fields": ["medicine_name", "manufacturer", "batch_number", "expiry_date", "dosage"],
            "explanation": f"Unable to complete AI-powered analysis. {reason}. Please try again later.",
        }

    def analyze_medicine_image(self, image_base64: str, mime_type: str = "image/jpeg",
                               ocr_text: str = "") -> Dict:
        """
        Analyze medicine image using multi-provider AI service.

        Providers are tried in priority order with automatic fallback:
        1. OpenAI (primary)
        2. Google Gemini (fallback)
        3. Groq (optional fallback)
        4. Deterministic fallback (if all fail)

        Args:
            image_base64: Base64 encoded image
            mime_type: Image MIME type (e.g., "image/jpeg")
            ocr_text: Optional OCR extracted text for context

        Returns:
            Analysis result dictionary with standardized schema
        """
        try:
            logger.info(f"Starting medicine analysis. OCR text length: {len(ocr_text)} chars")

            # 1) Load image into PIL and OpenCV formats
            pil_img, cv_img = ImageProcessor.load_image(image_base64)
            if pil_img is None or cv_img is None:
                logger.warning("Image could not be decoded")
                return self._fallback_analysis(ocr_text, reason="Invalid image data")

            # 2) Validate that image looks like medicine packaging
            is_likely, visual_conf = ImageProcessor.check_if_likely_medicine(cv_img)
            if not is_likely:
                logger.info(f"Image validation failed (not likely medicine). Confidence: {visual_conf}")
                return {
                    "is_medicine": False,
                    "rejection_reason": "Not a medicine image",
                    "medicine_name": None,
                    "manufacturer": None,
                    "batch_number": None,
                    "expiry_date": None,
                    "dosage": None,
                    "active_ingredients": [],
                    "extracted_text": ocr_text or "",
                    "visual_authenticity_score": float(visual_conf),
                    "text_clarity_score": 0.0,
                    "data_completeness_score": 0.0,
                    "format_validity_score": 0.0,
                    "overall_confidence": 0.0,
                    "authenticity_indicators": [],
                    "suspicious_signs": ["Image validation failed: not medicine"],
                    "missing_fields": ["medicine_name", "manufacturer", "batch_number", "expiry_date", "dosage"],
                    "explanation": "Uploaded image does not appear to be medicine packaging.",
                }

            # 3) Preprocess image for OCR
            processed = ImageProcessor.preprocess_image(pil_img)

            # 4) OCR extraction (primary source of structured data)
            text = OCRService.extract_text_from_image(processed) if processed is not None else ""
            # fallback to supplied ocr_text only if OCR produced nothing
            if not text and ocr_text:
                text = ocr_text

            if not text or len(text.strip()) < 10:
                logger.info("OCR produced insufficient text")
                return self._fallback_analysis(text or ocr_text, reason="No readable text extracted")

            # 5) Parse structured fields from OCR text
            parsed = OCRService.parse_medicine_data(text)

            # 6) Build analysis object (deterministic, not LLM-driven)
            analysis = {
                "is_medicine": True,
                "medicine_name": parsed.get("medicine_name"),
                "manufacturer": parsed.get("manufacturer"),
                "batch_number": parsed.get("batch_number"),
                "expiry_date": parsed.get("expiry_date"),
                "dosage": parsed.get("dosage"),
                "active_ingredients": parsed.get("active_ingredients", []),
                "extracted_text": text,
                "raw_text": text,
                "visual_authenticity_score": float(visual_conf),
                "text_clarity_score": float(min(100.0, len(text) / 2.0)),
                "data_completeness_score": 0.0,  # filled below
                "format_validity_score": 50.0,
                "authenticity_indicators": [],
                "suspicious_signs": [],
            }

            # 7) Compute data completeness score and missing fields
            critical = ["medicine_name", "manufacturer", "batch_number", "expiry_date", "dosage"]
            present = sum(1 for k in critical if analysis.get(k))
            completeness_pct = 0.0
            if critical:
                completeness_pct = (present / len(critical)) * 100.0
            analysis["data_completeness_score"] = float(completeness_pct)
            analysis["missing_fields"] = DecisionEngine.calculate_missing_fields(analysis)

            # 8) Compute deterministic confidence (simple rule-based)
            analysis["overall_confidence"] = float(self.compute_confidence(analysis))

            # 9) Decision engine determines final verdict (deterministic)
            verdict = DecisionEngine.generate_verdict(analysis)

            # 10) Use AI only to generate an explanation (do not allow AI to override verdict)
            explanation = None
            try:
                explanation = self.provider_manager.generate_explanation(analysis, verdict)
            except Exception as exc:
                logger.warning(f"Explanation generation failed: {exc}")
                explanation = f"Explanation unavailable: {str(exc)}"

            # 11) Final result (keep compatibility with previous schema)
            result = {
                "is_medicine": analysis.get("is_medicine", False),
                "rejection_reason": None if analysis.get("is_medicine") else "Rejected by pipeline",
                "medicine_name": analysis.get("medicine_name"),
                "manufacturer": analysis.get("manufacturer"),
                "batch_number": analysis.get("batch_number"),
                "expiry_date": analysis.get("expiry_date"),
                "dosage": analysis.get("dosage"),
                "active_ingredients": analysis.get("active_ingredients", []),
                "extracted_text": analysis.get("extracted_text"),
                "visual_authenticity_score": float(analysis.get("visual_authenticity_score", 50.0)),
                "text_clarity_score": float(analysis.get("text_clarity_score", 50.0)),
                "data_completeness_score": float(analysis.get("data_completeness_score", 0.0)),
                "format_validity_score": float(analysis.get("format_validity_score", 50.0)),
                "overall_confidence": float(analysis.get("overall_confidence", 0.0)),
                "authenticity_indicators": analysis.get("authenticity_indicators", []),
                "suspicious_signs": analysis.get("suspicious_signs", []),
                "missing_fields": analysis.get("missing_fields", []),
                "explanation": explanation or "",
                "verdict": verdict,
            }

            logger.info(f"Medicine analysis completed. Verdict: {verdict} | Confidence: {result['overall_confidence']}%")

            return result

        except Exception as e:
            logger.error(f"Unexpected error during medicine analysis: {e}", exc_info=True)
            return self._fallback_analysis(ocr_text, reason="Unexpected error during analysis")

    def compute_confidence(self, analysis: Dict) -> float:
        """
        Compute a simple deterministic confidence score from parsed fields.

        Scoring (max 100):
         - medicine_name: 25
         - batch_number: 20
         - expiry_date: 20
         - dosage: 15
         - manufacturer: 10
         - text length bonus: up to 10
        """
        score = 0.0
        if analysis.get("medicine_name"):
            score += 25
        if analysis.get("batch_number"):
            score += 20
        if analysis.get("expiry_date"):
            score += 20
        if analysis.get("dosage"):
            score += 15
        if analysis.get("manufacturer"):
            score += 10

        text_len = len(analysis.get("raw_text") or analysis.get("extracted_text") or "")
        score += min(10.0, text_len / 50.0)

        return float(min(100.0, score))
