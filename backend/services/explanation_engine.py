"""Dynamic explanation generation for medicine analysis results."""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ExplanationEngine:
    """Generates natural language explanations dynamically based on analysis data."""

    @staticmethod
    def generate_explanation(verdict: str, analysis: Dict) -> str:
        """
        Generate human-readable explanation for analysis result.

        Context-aware: Changes based on actual input data, NOT hardcoded.
        """
        is_medicine = analysis.get("is_medicine", False)
        medicine_name = analysis.get("medicine_name")
        confidence = float(analysis.get("overall_confidence", 0))
        missing_fields = analysis.get("missing_fields", [])
        suspicious_signs = analysis.get("suspicious_signs", [])
        authenticity_indicators = analysis.get("authenticity_indicators", [])
        extracted_text = analysis.get("extracted_text", "")

        # Case 1: Not a medicine image
        if not is_medicine:
            rejection_reason = analysis.get("rejection_reason", "Does not appear to be medicine packaging")
            return f"This image does not contain a medicine package or label. {rejection_reason}. Please upload a clear photo of a medicine box, bottle, blister pack, or label."

        # Case 2: Very low confidence (likely invalid)
        if confidence < 30:
            return f"Unable to analyze this image ({confidence:.0f}% confidence). The image quality is too poor or the medicine details are not clearly visible. Please upload a clearer, high-resolution image with visible text and packaging."

        # Case 3: Missing critical information
        if missing_fields and len(missing_fields) >= 3:
            fields_str = ", ".join(missing_fields[:3])
            return f"Critical information is missing from this medicine packaging: {fields_str}. While the image appears to be a medicine product, the absence of these required fields raises authenticity concerns. Genuine medicines should clearly display all regulatory information."

        # Case 4: High confidence - Genuine
        if confidence >= 80 and not suspicious_signs:
            name_str = f"'{medicine_name}'" if medicine_name else "this medicine"
            explanation = f"✓ {name_str} appears genuine ({confidence:.0f}% confidence). "

            # Add specific indicators
            if authenticity_indicators:
                top_indicators = authenticity_indicators[:2]
                explanation += f"Key authenticity features detected: {', '.join(top_indicators)}. "

            if any(field not in missing_fields for field in ["Medicine Name", "Manufacturer", "Batch Number", "Expiry Date"]):
                explanation += "All essential regulatory information is clearly visible and properly formatted. "

            explanation += "This medicine packaging meets authenticity standards."
            return explanation

        # Case 5: Medium confidence - Suspicious
        if 60 <= confidence < 80 and suspicious_signs:
            name_str = f"'{medicine_name}'" if medicine_name else "this medicine"
            explanation = f"⚠ {name_str} shows mixed authenticity signals ({confidence:.0f}% confidence). "

            if len(suspicious_signs) > 0:
                top_concern = suspicious_signs[0]
                explanation += f"Concern: {top_concern}. "

            if missing_fields:
                missing_str = ", ".join(missing_fields[:2])
                explanation += f"Missing information: {missing_str}. "

            explanation += "Recommend obtaining a second opinion or purchasing from an authorized pharmacy."
            return explanation

        # Case 6: Low confidence or multiple red flags - Fake/Counterfeit
        if confidence < 60 or len(suspicious_signs) >= 3:
            name_str = f"'{medicine_name}'" if medicine_name else "this medicine"
            explanation = f"✕ WARNING: {name_str} shows signs of being counterfeit or substandard ({confidence:.0f}% confidence). "

            if suspicious_signs:
                top_3_concerns = suspicious_signs[:3]
                explanation += f"Red flags: {'; '.join(top_3_concerns)}. "

            explanation += "Do NOT use this medicine. Purchase from authorized and verified pharmaceutical retailers only. Report to local health authorities if found in stores."
            return explanation

        # Default fallback
        return f"Analysis for {medicine_name or 'medicine'} complete. Confidence: {confidence:.0f}%. {analysis.get('explanation', '')}"

    @staticmethod
    def generate_verdict_message(verdict: str, medicine_name: Optional[str] = None) -> str:
        """Generate concise verdict message for UI display."""
        messages = {
            "GENUINE": f"✓ Genuine" + (f": {medicine_name}" if medicine_name else ""),
            "SUSPICIOUS": f"⚠ Suspicious" + (f": {medicine_name}" if medicine_name else ""),
            "FAKE": "✕ Counterfeit / Fake",
            "INVALID": "? Image cannot be analyzed",
        }
        return messages.get(verdict, "Analysis complete")

    @staticmethod
    def generate_voice_text(verdict: str, medicine_name: str, confidence: float,
                            explanation: str) -> str:
        """
        Generate natural language text for text-to-speech.
        """
        if verdict == "GENUINE":
            return f"Analysis complete. {medicine_name}. Verdict: Genuine with {int(confidence)} percent confidence. {explanation}"
        elif verdict == "SUSPICIOUS":
            return f"Analysis complete. {medicine_name}. Verdict: Suspicious with {int(confidence)} percent confidence. {explanation}"
        elif verdict == "FAKE":
            return f"Warning. Analysis shows counterfeit signs. Do not use. {explanation}"
        elif verdict == "INVALID":
            return f"Image rejected. This is not medicine packaging. {explanation}"
        else:
            return f"Analysis for {medicine_name} complete. {explanation}"

    @staticmethod
    def generate_summary_statistics(analysis: Dict) -> Dict[str, any]:
        """
        Generate human-readable summary of all scores.
        """
        return {
            "visual_quality": f"{int(analysis.get('visual_authenticity_score', 50))}%",
            "text_clarity": f"{int(analysis.get('text_clarity_score', 50))}%",
            "data_completeness": f"{int(analysis.get('data_completeness_score', 50))}%",
            "format_validity": f"{int(analysis.get('format_validity_score', 50))}%",
            "overall_confidence": f"{int(analysis.get('overall_confidence', 50))}%",
        }
