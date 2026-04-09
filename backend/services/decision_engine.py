"""Decision engine for generating medicine authenticity verdicts."""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Generates verdicts based on analysis confidence and indicators."""

    # Verdict thresholds
    GENUINE_THRESHOLD = 80.0
    SUSPICIOUS_THRESHOLD = 60.0
    INVALID_THRESHOLD = 30.0

    @staticmethod
    def _normalize_signal(signal: str) -> str:
        """Normalize a signal string for case-insensitive deduplication."""
        return " ".join((signal or "").strip().lower().split())

    @staticmethod
    def generate_verdict(analysis: Dict) -> str:
        """
        Generate verdict (GENUINE | SUSPICIOUS | FAKE | INVALID) based on analysis.

        Logic:
        This method now computes a data-driven confidence score from OCR and
        parsed fields (name, batch, expiry, dosage, manufacturer, text length)
        and builds simple, explainable signals from OCR-derived data.
        Verdict rules (simplified, data-driven):
         - If OCR text too short or no medicine keywords → INVALID
         - If name+batch+expiry present and confidence > 70 → GENUINE
         - If confidence > 40 → SUSPICIOUS
         - Otherwise → FAKE
        """
        # Use extracted OCR text (normalized) for basic quality checks
        raw_text = analysis.get("extracted_text") or analysis.get("raw_text") or ""
        if len(raw_text or "") < 10:
            return "INVALID"

        # Basic text-based medicine detection keywords
        keywords = ["tablet", "capsule", "mg", "ml", "pharma", "batch", "tablets", "capsules"]
        text_lower = raw_text.lower()
        if not any(k in text_lower for k in keywords):
            return "INVALID"

        # Build missing-field signals (critical fields only).
        missing = analysis.get("missing_fields") or DecisionEngine.calculate_missing_fields(analysis)

        # Batch-only-missing case should not heavily penalize confidence.
        if missing == ["Batch Number"]:
            analysis["overall_confidence"] = min(100.0, float(analysis.get("overall_confidence", 0)) + 10.0)

        suspicious_signs = analysis.get("suspicious_signs") or []
        existing_signals = {
            DecisionEngine._normalize_signal(s)
            for s in suspicious_signs
            if isinstance(s, str) and s.strip()
        }
        for field in missing:
            candidate = f"Missing: {field}"
            normalized = DecisionEngine._normalize_signal(candidate)
            field_norm = DecisionEngine._normalize_signal(field)
            has_equivalent_missing_signal = any(
                ("missing" in sig and field_norm and field_norm in sig)
                for sig in existing_signals
            )
            if normalized not in existing_signals and not has_equivalent_missing_signal:
                suspicious_signs.append(candidate)
                existing_signals.add(normalized)

        # If medicine_name looks too short, flag it
        name = analysis.get("medicine_name") or ""
        if isinstance(name, str) and len(name.strip()) < 3:
            candidate = "Invalid or short medicine name"
            normalized = DecisionEngine._normalize_signal(candidate)
            if normalized not in existing_signals:
                suspicious_signs.append(candidate)
                existing_signals.add(normalized)

        # Compute confidence using existing score as base when available.
        confidence = float(analysis.get("overall_confidence", 0))
        if confidence <= 0:
            confidence = DecisionEngine.compute_confidence_from_data(analysis)
        # Allow completeness-based adjustment as a final step
        confidence = DecisionEngine.update_confidence_based_on_completeness({**analysis, "overall_confidence": confidence})

        # Persist computed values back into analysis for downstream use
        analysis["overall_confidence"] = float(confidence)
        analysis["suspicious_signs"] = suspicious_signs

        # Strong genuine condition: name + dosage + high confidence.
        if analysis.get("medicine_name") and analysis.get("dosage") and confidence >= 70:
            return "GENUINE"

        if confidence > 40:
            return "SUSPICIOUS"

        return "FAKE"

    @staticmethod
    def calculate_missing_fields(analysis: Dict) -> List[str]:
        """
        Identify critical missing fields that reduce authenticity.
        Batch and manufacturer are treated as optional.
        """
        critical_fields = {
            "medicine_name": "Medicine Name",
            "expiry_date": "Expiry Date",
            "dosage": "Dosage",
        }

        missing = []
        for field, label in critical_fields.items():
            value = analysis.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(label)

        return missing

    @staticmethod
    def update_confidence_based_on_completeness(analysis: Dict) -> float:
        """
        Adjust overall confidence based on field completeness.
        """
        base_confidence = float(analysis.get("overall_confidence", 50))
        missing = DecisionEngine.calculate_missing_fields(analysis)

        # Penalize for missing fields (10 percentage points per missing critical field)
        completeness_penalty = len(missing) * 10
        adjusted_confidence = max(0, base_confidence - completeness_penalty)

        return float(adjusted_confidence)

    @staticmethod
    def compute_confidence_from_data(analysis: Dict) -> float:
        """
        Compute a data-driven confidence score from OCR and parsed fields.

        Scoring model (total capped to 100):
         - medicine_name: 20
         - batch_number: 20
         - expiry_date: 20
         - dosage: 15
         - manufacturer: 15
         - OCR text length contribution: up to 10
        """
        score = 0.0

        if analysis.get("medicine_name"):
            score += 20
        if analysis.get("batch_number"):
            score += 10
        if analysis.get("expiry_date"):
            score += 20
        if analysis.get("dosage"):
            score += 25
        if analysis.get("manufacturer"):
            score += 10

        # OCR raw text length contribution (small bonus for richer text)
        raw_text = analysis.get("extracted_text") or analysis.get("raw_text") or ""
        text_length = len(raw_text)
        score += min(10, text_length / 50)

        # Clamp to 0-100
        return float(min(100, score))

    @staticmethod
    def get_verdict_reasoning(verdict: str, analysis: Dict) -> Dict:
        """
        Generate detailed reasoning for verdict.
        """
        confidence = float(analysis.get("overall_confidence", 0))
        missing_fields = analysis.get("missing_fields", [])
        suspicious_signs = analysis.get("suspicious_signs", [])
        authenticity_indicators = analysis.get("authenticity_indicators", [])

        # Dynamic reasoning based on actual signals
        issues = ", ".join(missing_fields) if missing_fields else "None"
        concerns = ", ".join(suspicious_signs[:3]) if suspicious_signs else "None"

        reasoning = {
            "verdict": verdict,
            "confidence_percent": int(confidence),
            "key_indicators": authenticity_indicators[:3],
            "concerns": suspicious_signs[:3],
            "missing_info": missing_fields[:3],
        }

        # Build a concise dynamic summary
        reasoning["summary"] = (
            f"Detected medicine: {analysis.get('medicine_name') or 'Unknown'}. "
            f"Missing fields: {issues}. "
            f"Concerns: {concerns}. "
            f"Confidence: {confidence:.0f}%.")

        return reasoning
