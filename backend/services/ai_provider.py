"""Multi-provider AI service abstraction for medicine analysis.

Supports:
- OpenAI (primary)
- Google Gemini (fallback)
- Groq (optional speed layer)
- DeepSeek (optional cost layer)
"""
import json
import logging
import os
from typing import Dict, Optional, Tuple
from abc import ABC, abstractmethod
import base64

logger = logging.getLogger(__name__)


class AIProviderBase(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def analyze_medicine_image(self, image_base64: str, mime_type: str = "image/jpeg", ocr_text: str = "") -> Dict:
        """Analyze medicine image and return structured JSON analysis."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass

    @staticmethod
    def _get_system_prompt() -> str:
        """Return the system prompt for medicine authenticity analysis."""
        return """You are a pharmaceutical authenticity verification expert with 20 years of experience in detecting counterfeit medicines.

Analyze the provided medicine image for authenticity indicators and return ONLY valid raw JSON (no markdown, no extra text).

Your analysis must evaluate:
1. Visual authenticity (packaging quality, printing clarity, label consistency)
2. Text clarity and OCR readability
3. Data completeness (presence of required fields)
4. Format validity (standard medicine packaging structure)
5. Authenticity indicators (holographic elements, serial numbers, security features)
6. Suspicious signs (poor printing, pixelated fonts, spelling errors, unusual colors)

Return exactly this JSON structure with no additional text:
{
  "is_medicine": boolean,
  "rejection_reason": "reason if not medicine or null",
  "medicine_name": "detected name or null",
  "manufacturer": "detected manufacturer or null",
  "batch_number": "detected batch or null",
  "expiry_date": "detected expiry or null",
  "dosage": "detected dosage or null",
  "active_ingredients": ["ingredient1", "ingredient2"],
  "extracted_text": "all visible text from image",
  "visual_authenticity_score": float (0-100),
  "text_clarity_score": float (0-100),
  "data_completeness_score": float (0-100),
  "format_validity_score": float (0-100),
  "overall_confidence": float (0-100),
  "authenticity_indicators": ["security feature 1", "security feature 2"],
  "suspicious_signs": [],
  "missing_fields": [],
  "explanation": "Natural language explanation of the verdict"
}"""

    @staticmethod
    def _get_user_prompt(ocr_text: str = "") -> str:
        """Generate user prompt with OCR context."""
        base_prompt = """Analyze this medicine image for authenticity.

Evaluate:
1. Is this a real medicine packaging image?
2. Extract all visible information
3. Assess visual and textual authenticity
4. Identify security features and suspicious signs
5. Calculate confidence scores for each aspect
6. Provide verdict: GENUINE (80%+ confidence, no red flags), SUSPICIOUS (50-80%, minor concerns), FAKE (<50% or major red flags), or INVALID (not medicine)"""

        if ocr_text:
            base_prompt += f"\n\nOCR Context from image:\n{ocr_text}"

        base_prompt += "\n\nReturn ONLY the JSON structure specified. No markdown, no additional text."
        return base_prompt


class OpenAIProvider(AIProviderBase):
    """OpenAI GPT-4 Vision provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.available = bool(self.api_key)
        self.model = "gpt-4o-mini"  # Latest vision model
        self.client = None

        if self.available:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI provider initialized with model: {self.model}")
            except ImportError:
                logger.error("OpenAI SDK not installed. Install with: pip install openai")
                self.available = False
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.available = False

    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        return self.available and self.client is not None

    def analyze_medicine_image(self, image_base64: str, mime_type: str = "image/jpeg",
                              ocr_text: str = "") -> Tuple[Dict, bool]:
        """
        Analyze medicine image using OpenAI Vision API.

        Returns:
            Tuple of (analysis_dict, success_bool)
        """
        if not self.is_available():
            return {}, False

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}",
                                    "detail": "high",
                                },
                            },
                            {
                                "type": "text",
                                "text": self._get_user_prompt(ocr_text),
                            },
                        ],
                    }
                ],
            )

            response_text = response.choices[0].message.content
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(response_text)

            logger.info(f"OpenAI analysis successful. Confidence: {analysis.get('overall_confidence')}")
            return self._normalize_response(analysis), True

        except json.JSONDecodeError as e:
            logger.error(f"OpenAI response JSON parsing failed: {e}")
            return {}, False
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            if "insufficient_quota" in str(e).lower() or "quota" in str(e).lower():
                self.available = False
            return {}, False

    @staticmethod
    def _normalize_response(analysis: Dict) -> Dict:
        """Normalize OpenAI response to standard format."""
        return {
            "is_medicine": analysis.get("is_medicine", False),
            "rejection_reason": analysis.get("rejection_reason"),
            "medicine_name": analysis.get("medicine_name"),
            "manufacturer": analysis.get("manufacturer"),
            "batch_number": analysis.get("batch_number"),
            "expiry_date": analysis.get("expiry_date"),
            "dosage": analysis.get("dosage"),
            "active_ingredients": analysis.get("active_ingredients", []),
            "extracted_text": analysis.get("extracted_text", ""),
            "visual_authenticity_score": float(analysis.get("visual_authenticity_score", 50)),
            "text_clarity_score": float(analysis.get("text_clarity_score", 50)),
            "data_completeness_score": float(analysis.get("data_completeness_score", 50)),
            "format_validity_score": float(analysis.get("format_validity_score", 50)),
            "overall_confidence": float(analysis.get("overall_confidence", 50)),
            "authenticity_indicators": analysis.get("authenticity_indicators", []),
            "suspicious_signs": analysis.get("suspicious_signs", []),
            "missing_fields": analysis.get("missing_fields", []),
            "explanation": analysis.get("explanation", "Analysis complete"),
        }


class GeminiProvider(AIProviderBase):
    """Google Gemini Vision provider (fallback)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.available = bool(self.api_key)
        # Use fully qualified model id for google-generativeai v1beta compatibility.
        self.model = "models/gemini-2.0-flash"
        self.client = None

        if self.available:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
                logger.info(f"Google Gemini provider initialized with model: {self.model}")
            except ImportError:
                logger.error("Google Generative AI SDK not installed. Install with: pip install google-generativeai")
                self.available = False
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.available = False

    def is_available(self) -> bool:
        """Check if Gemini provider is available."""
        return self.available and self.client is not None

    def analyze_medicine_image(self, image_base64: str, mime_type: str = "image/jpeg",
                              ocr_text: str = "") -> Tuple[Dict, bool]:
        """
        Analyze medicine image using Google Gemini Vision API.

        Returns:
            Tuple of (analysis_dict, success_bool)
        """
        if not self.is_available():
            return {}, False

        try:
            # Convert base64 to bytes for Gemini
            image_bytes = base64.b64decode(image_base64)

            # Determine media type
            media_type = mime_type or "image/jpeg"

            model = self.client.GenerativeModel(self.model)

            response = model.generate_content(
                [
                    self._get_system_prompt(),
                    "\n\n",
                    {"mime_type": media_type, "data": image_bytes},
                    "\n\n",
                    self._get_user_prompt(ocr_text),
                ],
                generation_config=self.client.types.GenerationConfig(
                    max_output_tokens=1024,
                ),
            )

            response_text = response.text
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(response_text)

            logger.info(f"Gemini analysis successful. Confidence: {analysis.get('overall_confidence')}")
            return self._normalize_response(analysis), True

        except json.JSONDecodeError as e:
            logger.error(f"Gemini response JSON parsing failed: {e}")
            return {}, False
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            if "quota" in str(e).lower() or "429" in str(e):
                self.available = False
            return {}, False

    @staticmethod
    def _normalize_response(analysis: Dict) -> Dict:
        """Normalize Gemini response to standard format."""
        return {
            "is_medicine": analysis.get("is_medicine", False),
            "rejection_reason": analysis.get("rejection_reason"),
            "medicine_name": analysis.get("medicine_name"),
            "manufacturer": analysis.get("manufacturer"),
            "batch_number": analysis.get("batch_number"),
            "expiry_date": analysis.get("expiry_date"),
            "dosage": analysis.get("dosage"),
            "active_ingredients": analysis.get("active_ingredients", []),
            "extracted_text": analysis.get("extracted_text", ""),
            "visual_authenticity_score": float(analysis.get("visual_authenticity_score", 50)),
            "text_clarity_score": float(analysis.get("text_clarity_score", 50)),
            "data_completeness_score": float(analysis.get("data_completeness_score", 50)),
            "format_validity_score": float(analysis.get("format_validity_score", 50)),
            "overall_confidence": float(analysis.get("overall_confidence", 50)),
            "authenticity_indicators": analysis.get("authenticity_indicators", []),
            "suspicious_signs": analysis.get("suspicious_signs", []),
            "missing_fields": analysis.get("missing_fields", []),
            "explanation": analysis.get("explanation", "Analysis complete"),
        }


class GroqProvider(AIProviderBase):
    """Groq provider for fast inference (optional speed layer)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.available = bool(self.api_key)
        # Groq vision model for medicine image analysis
        self.model = "llama-3.2-90b-vision-preview"
        self.client = None

        if self.available:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info(f"Groq provider initialized with model: {self.model}")
            except ImportError:
                logger.error("Groq SDK not installed. Install with: pip install groq")
                self.available = False
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                self.available = False

    def is_available(self) -> bool:
        """Check if Groq provider is available."""
        return self.available and self.client is not None

    def analyze_medicine_image(self, image_base64: str, mime_type: str = "image/jpeg",
                              ocr_text: str = "") -> Tuple[Dict, bool]:
        """
        Analyze medicine image using Groq Vision API.

        Returns:
            Tuple of (analysis_dict, success_bool)
        """
        if not self.is_available():
            return {}, False

        try:
            # Groq vision model: send image + OCR context for analysis
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": self._get_user_prompt(ocr_text),
                            }
                        ],
                    }
                ],
            )

            response_text = response.choices[0].message.content
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(response_text)

            logger.info(f"Groq analysis successful. Confidence: {analysis.get('overall_confidence')}")
            return self._normalize_response(analysis), True

        except json.JSONDecodeError as e:
            logger.error(f"Groq response JSON parsing failed: {e}")
            return {}, False
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            if "decommissioned" in str(e).lower() or "model_decommissioned" in str(e).lower():
                self.available = False
            return {}, False

    @staticmethod
    def _normalize_response(analysis: Dict) -> Dict:
        """Normalize Groq response to standard format."""
        return {
            "is_medicine": analysis.get("is_medicine", False),
            "rejection_reason": analysis.get("rejection_reason"),
            "medicine_name": analysis.get("medicine_name"),
            "manufacturer": analysis.get("manufacturer"),
            "batch_number": analysis.get("batch_number"),
            "expiry_date": analysis.get("expiry_date"),
            "dosage": analysis.get("dosage"),
            "active_ingredients": analysis.get("active_ingredients", []),
            "extracted_text": analysis.get("extracted_text", ""),
            "visual_authenticity_score": float(analysis.get("visual_authenticity_score", 50)),
            "text_clarity_score": float(analysis.get("text_clarity_score", 50)),
            "data_completeness_score": float(analysis.get("data_completeness_score", 50)),
            "format_validity_score": float(analysis.get("format_validity_score", 50)),
            "overall_confidence": float(analysis.get("overall_confidence", 50)),
            "authenticity_indicators": analysis.get("authenticity_indicators", []),
            "suspicious_signs": analysis.get("suspicious_signs", []),
            "missing_fields": analysis.get("missing_fields", []),
            "explanation": analysis.get("explanation", "Analysis complete"),
        }


class AIProviderManager:
    """Manages multiple AI providers with automatic fallback."""

    def __init__(self):
        """Initialize all available providers."""
        self.providers = {
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
        }

        available = [name for name, provider in self.providers.items() if provider.is_available()]
        logger.info(f"Available AI providers: {available if available else 'NONE'}")

        if not available:
            logger.warning("⚠️  NO AI PROVIDERS CONFIGURED. Set OPENAI_API_KEY, GOOGLE_API_KEY, or GROQ_API_KEY")

    def analyze_medicine_image(self, image_base64: str, mime_type: str = "image/jpeg",
                              ocr_text: str = "") -> Dict:
        """
        Analyze medicine image using available providers with fallback strategy.

        Priority:
        1. OpenAI (primary - has vision)
        2. Gemini (fallback - has vision)
        3. Groq (optional fallback - text-only, uses OCR)
        4. Deterministic fallback

        Returns:
            Structured analysis dictionary (always returns a dict)
        """
        # Try in priority order
        # Vision models first (OpenAI/Gemini can see the actual image).
        # Groq last as fallback (text-only, analyzes OCR text only).
        provider_order = ["openai", "gemini", "groq"]

        for provider_name in provider_order:
            provider = self.providers.get(provider_name)
            if provider and provider.is_available():
                logger.info(f"Attempting analysis with {provider_name.upper()}...")
                analysis, success = provider.analyze_medicine_image(image_base64, mime_type, ocr_text)

                if success and analysis:
                    logger.info(f"✓ Analysis successful with {provider_name.upper()}")
                    return analysis
                else:
                    logger.warning(f"✗ {provider_name.upper()} analysis failed, trying next provider...")

        # All providers failed - return deterministic fallback
        logger.error("All AI providers failed. Using deterministic fallback.")
        return self._fallback_analysis(ocr_text)

    def generate_explanation(self, analysis: Dict, verdict: str) -> str:
        """
        Generate human-readable explanation from deterministic analysis.

        AI is used only as a narration/explanation layer and never for verdicting.
        """
        prompt = (
            "You are a pharmaceutical safety assistant. "
            "Write a concise, user-friendly explanation in 2-4 sentences based ONLY on the provided structured analysis. "
            "Do not change the verdict, do not invent fields, and do not provide medical treatment advice.\n\n"
            f"Verdict: {verdict}\n"
            f"Medicine Name: {analysis.get('medicine_name')}\n"
            f"Manufacturer: {analysis.get('manufacturer')}\n"
            f"Batch Number: {analysis.get('batch_number')}\n"
            f"Expiry Date: {analysis.get('expiry_date')}\n"
            f"Dosage: {analysis.get('dosage')}\n"
            f"Overall Confidence: {analysis.get('overall_confidence')}\n"
            f"Missing Fields: {analysis.get('missing_fields', [])}\n"
            f"Suspicious Signs: {analysis.get('suspicious_signs', [])}\n"
            "Return plain text only."
        )

        # Prefer fast and reliable providers in order.
        provider_order = ["openai", "gemini", "groq"]

        for provider_name in provider_order:
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_available():
                continue

            try:
                if provider_name == "openai" and getattr(provider, "client", None):
                    resp = provider.client.chat.completions.create(
                        model=provider.model,
                        max_tokens=220,
                        messages=[
                            {"role": "system", "content": "You explain medicine scan results clearly and safely."},
                            {"role": "user", "content": prompt},
                        ],
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if text:
                        return text

                if provider_name == "gemini" and getattr(provider, "client", None):
                    model = provider.client.GenerativeModel(provider.model)
                    resp = model.generate_content(prompt)
                    text = (getattr(resp, "text", "") or "").strip()
                    if text:
                        return text

                if provider_name == "groq" and getattr(provider, "client", None):
                    resp = provider.client.chat.completions.create(
                        model=provider.model,
                        max_tokens=220,
                        messages=[
                            {"role": "system", "content": "You explain medicine scan results clearly and safely."},
                            {"role": "user", "content": prompt},
                        ],
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if text:
                        return text

            except Exception as e:
                logger.warning(f"Explanation generation failed with {provider_name.upper()}: {e}")

        # Deterministic fallback explanation when no provider is available.
        name = analysis.get("medicine_name") or "the uploaded medicine"
        conf = float(analysis.get("overall_confidence", 0))
        missing = analysis.get("missing_fields") or []
        concerns = analysis.get("suspicious_signs") or []

        missing_normalized = {str(item).strip().lower() for item in missing if str(item).strip()}
        filtered_concerns = []
        for concern in concerns:
            if not isinstance(concern, str):
                continue
            cleaned = concern.strip()
            if not cleaned:
                continue
            normalized = cleaned.lower()
            # Operational issue; keep it in logs, but do not present as authenticity concern.
            if "ai service unavailable" in normalized:
                continue
            # Avoid repeating missing fields in the concerns section.
            if normalized.startswith("missing:"):
                field_part = cleaned.split(":", 1)[1].strip().lower() if ":" in cleaned else ""
                if field_part in missing_normalized:
                    continue
            if "missing" in normalized and any(field in normalized for field in missing_normalized):
                continue
            filtered_concerns.append(cleaned)

        # Stable de-duplication preserving order.
        deduped_concerns = list(dict.fromkeys(filtered_concerns))
        missing_part = f" Missing fields: {', '.join(missing[:3])}." if missing else ""
        concerns_part = f" Key concerns: {', '.join(deduped_concerns[:3])}." if deduped_concerns else ""
        return f"Verdict for {name}: {verdict} with {conf:.0f}% confidence.{missing_part}{concerns_part}".strip()

    @staticmethod
    def _fallback_analysis(ocr_text: str = "") -> Dict:
        """
        Return deterministic fallback analysis when all providers fail.

        This is NOT a simulation - it's an error state with clear messaging.
        """
        cleaned = (ocr_text or "").strip()
        first_line = cleaned.split('\n')[0].strip() if cleaned else ""
        detected_name = first_line[:80] if first_line else None
        is_medicine = bool(cleaned and len(cleaned) > 20)
        confidence = 45.0  # Lower confidence for fallback

        return {
            "is_medicine": is_medicine,
            "rejection_reason": None if is_medicine else "Unable to verify - AI service unavailable",
            "medicine_name": detected_name if is_medicine else None,
            "manufacturer": None,
            "batch_number": None,
            "expiry_date": None,
            "dosage": None,
            "active_ingredients": [],
            "extracted_text": cleaned,
            "visual_authenticity_score": 45.0,
            "text_clarity_score": 50.0 if cleaned else 20.0,
            "data_completeness_score": 30.0,
            "format_validity_score": 40.0,
            "overall_confidence": confidence,
            "authenticity_indicators": [],
            "suspicious_signs": ["AI service unavailable - unable to verify authenticity"],
            "missing_fields": ["manufacturer", "batch_number", "expiry_date", "dosage"],
            "explanation": "Unable to complete AI analysis. All providers are currently unavailable. Please try again later or contact support.",
        }


# Global provider manager instance
_provider_manager = None


def get_provider_manager() -> AIProviderManager:
    """Get or create the global provider manager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = AIProviderManager()
    return _provider_manager
