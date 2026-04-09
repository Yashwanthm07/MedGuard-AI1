"""Patient safety analysis engine for drug interactions and safety assessment."""
import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PatientSafetyEngine:
    """Analyzes patient profiles for drug interactions and safety concerns using multi-provider AI."""

    def __init__(self):
        self.openai_client = None
        self.gemini_client = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available AI providers for text analysis."""
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GOOGLE_API_KEY")

        if openai_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_key)
                logger.info("OpenAI provider initialized for patient safety analysis")
            except ImportError:
                logger.warning("OpenAI SDK not installed")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")

        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self.gemini_client = genai
                logger.info("Google Gemini provider initialized for patient safety analysis")
            except ImportError:
                logger.warning("Google Generative AI SDK not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

        if not self.openai_client and not self.gemini_client:
            logger.warning("⚠️  NO TEXT AI PROVIDERS CONFIGURED for patient safety analysis")

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 80:
            return "CRITICAL"
        if score >= 51:
            return "HIGH"
        if score >= 21:
            return "MODERATE"
        return "LOW"

    def _heuristic_safety(self, age: Optional[int], allergies: Optional[str],
                          medications: Optional[str], conditions: Optional[str],
                          reason: str) -> Dict:
        """Compute a deterministic local safety assessment when LLM calls are unavailable."""
        meds = [m.strip() for m in (medications or "").split(",") if m.strip()]
        meds_l = [m.lower() for m in meds]
        allergy_items = [a.strip() for a in (allergies or "").split(",") if a.strip()]
        allergy_l = [a.lower() for a in allergy_items]

        interactions = []
        allergy_concerns = []
        age_considerations = []
        recommendations = [
            "Review this assessment with a licensed healthcare provider.",
            "Do not start or stop medications without medical advice.",
        ]

        score = 0

        if "warfarin" in meds_l and "aspirin" in meds_l:
            interactions.append({
                "drug1": "Warfarin",
                "drug2": "Aspirin",
                "severity": "SEVERE",
                "description": "Increased bleeding risk when combined.",
            })
            score += 65

        if "ibuprofen" in meds_l and "warfarin" in meds_l:
            interactions.append({
                "drug1": "Warfarin",
                "drug2": "Ibuprofen",
                "severity": "MODERATE",
                "description": "NSAIDs can increase bleeding risk with anticoagulants.",
            })
            score += 20

        for allergy in allergy_l:
            for med in meds_l:
                if allergy and allergy in med:
                    allergy_concerns.append({
                        "drug": med,
                        "concern": f"Medication name overlaps with reported allergy '{allergy}'.",
                    })
                    score += 25

        if age is not None and age < 12 and meds:
            age_considerations.append({
                "concern": "Pediatric patient on active medication list.",
                "recommendation": "Confirm pediatric dosing and indication with clinician.",
            })
            score += 10

        if age is not None and age >= 65 and meds:
            age_considerations.append({
                "concern": "Older adult may have increased sensitivity to side effects.",
                "recommendation": "Review dose appropriateness and renal/hepatic function.",
            })
            score += 10

        if conditions:
            score += 5

        if meds and score == 0:
            score = 15

        score = min(100, score)
        level = self._risk_level(score)

        recommendations.append(f"Fallback mode used ({reason}); consider rerunning with valid AI provider API key.")

        return {
            "risk_level": level,
            "risk_score": score,
            "interactions": interactions,
            "allergy_concerns": allergy_concerns,
            "age_considerations": age_considerations,
            "recommendations": recommendations,
            "requires_immediate_attention": score >= 80,
            "clinical_summary": f"Local heuristic safety analysis complete (reason: {reason}).",
        }

    def analyze_patient_safety(self, age: Optional[int] = None, allergies: Optional[str] = None,
                               medications: Optional[str] = None, conditions: Optional[str] = None) -> Dict:
        """
        Analyze patient profile for safety concerns using multi-provider AI.

        Providers tried in priority order with automatic fallback:
        1. OpenAI (primary)
        2. Google Gemini (fallback)
        3. Heuristic analysis (if all fail)

        Args:
            age: Patient age
            allergies: Comma-separated allergies
            medications: Comma-separated current medications
            conditions: Comma-separated medical conditions

        Returns: Safety analysis dictionary
        """
        if not any([age, allergies, medications, conditions]):
            return {
                "risk_level": "LOW",
                "risk_score": 0,
                "interactions": [],
                "allergy_concerns": [],
                "age_considerations": [],
                "recommendations": ["Provide patient information to perform safety analysis"],
                "requires_immediate_attention": False,
                "clinical_summary": "No patient data provided.",
            }

        try:
            # Try OpenAI first
            if self.openai_client:
                logger.info("Attempting patient safety analysis with OpenAI...")
                result = self._analyze_with_openai(age, allergies, medications, conditions)
                if result:
                    return result
                else:
                    logger.warning("OpenAI analysis failed, trying Gemini...")

            # Try Gemini as fallback
            if self.gemini_client:
                logger.info("Attempting patient safety analysis with Google Gemini...")
                result = self._analyze_with_gemini(age, allergies, medications, conditions)
                if result:
                    return result
                else:
                    logger.warning("Gemini analysis failed, using heuristic fallback...")

            # Fall back to heuristic analysis
            logger.error("All AI providers failed for patient safety analysis. Using heuristic fallback.")
            return self._heuristic_safety(age, allergies, medications, conditions, reason="all providers unavailable")

        except Exception as e:
            logger.error(f"Unexpected error in patient safety analysis: {e}", exc_info=True)
            return self._heuristic_safety(age, allergies, medications, conditions, reason="unexpected error")

    def _analyze_with_openai(self, age: Optional[int], allergies: Optional[str],
                            medications: Optional[str], conditions: Optional[str]) -> Optional[Dict]:
        """Analyze patient safety using OpenAI."""
        try:
            system_prompt = self._get_system_prompt()
            user_content = self._get_user_prompt(age, allergies, medications, conditions)

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_content,
                    }
                ],
            )

            response_text = response.choices[0].message.content
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(response_text)

            result = {
                "risk_level": analysis.get("risk_level", "LOW"),
                "risk_score": int(analysis.get("risk_score", 0)),
                "interactions": analysis.get("interactions", []),
                "allergy_concerns": analysis.get("allergy_concerns", []),
                "age_considerations": analysis.get("age_considerations", []),
                "recommendations": analysis.get("recommendations", ["Consult with healthcare provider"]),
                "requires_immediate_attention": analysis.get("requires_immediate_attention", False),
                "clinical_summary": analysis.get("clinical_summary", "Safety analysis complete"),
            }

            logger.info(f"✓ OpenAI patient safety analysis successful. Risk: {result['risk_level']}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"OpenAI response JSON parsing failed: {e}")
            return None
        except Exception as e:
            logger.error(f"OpenAI patient safety analysis failed: {e}")
            return None

    def _analyze_with_gemini(self, age: Optional[int], allergies: Optional[str],
                            medications: Optional[str], conditions: Optional[str]) -> Optional[Dict]:
        """Analyze patient safety using Google Gemini."""
        try:
            system_prompt = self._get_system_prompt()
            user_content = self._get_user_prompt(age, allergies, medications, conditions)

            model = self.gemini_client.GenerativeModel("gemini-2.0-flash-thinking-exp-1219")
            response = model.generate_content(
                f"{system_prompt}\n\n{user_content}",
                generation_config=self.gemini_client.types.GenerationConfig(
                    max_output_tokens=1024,
                ),
            )

            response_text = response.text
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(response_text)

            result = {
                "risk_level": analysis.get("risk_level", "LOW"),
                "risk_score": int(analysis.get("risk_score", 0)),
                "interactions": analysis.get("interactions", []),
                "allergy_concerns": analysis.get("allergy_concerns", []),
                "age_considerations": analysis.get("age_considerations", []),
                "recommendations": analysis.get("recommendations", ["Consult with healthcare provider"]),
                "requires_immediate_attention": analysis.get("requires_immediate_attention", False),
                "clinical_summary": analysis.get("clinical_summary", "Safety analysis complete"),
            }

            logger.info(f"✓ Gemini patient safety analysis successful. Risk: {result['risk_level']}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini response JSON parsing failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Gemini patient safety analysis failed: {e}")
            return None

    @staticmethod
    def _get_system_prompt() -> str:
        """Get system prompt for patient safety analysis."""
        return """You are a clinical pharmacist with 25 years of experience in drug interactions and patient safety assessment.

Analyze the patient profile for potential drug interactions, allergy concerns, age-related considerations, and overall safety risks.

Return ONLY valid raw JSON (no markdown, no extra text) in this exact structure:
{
  "risk_level": "LOW|MODERATE|HIGH|CRITICAL",
  "risk_score": 0-100,
  "interactions": [
    {"drug1": "Drug A", "drug2": "Drug B", "severity": "MILD|MODERATE|SEVERE", "description": "..."}
  ],
  "allergy_concerns": [
    {"drug": "Drug name", "concern": "Describes allergy concern"}
  ],
  "age_considerations": [
    {"concern": "Age-related concern", "recommendation": "Suggested action"}
  ],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "requires_immediate_attention": false,
  "clinical_summary": "Summary of key findings"
}

Critical rules:
- Only identify REAL drug interactions (use medical knowledge)
- Age considerations: elderly (65+) requires special consideration for dosing/metabolism
- Allergy concerns: cross-check medications against allergies list
- Risk scoring: 0-20 LOW, 21-50 MODERATE, 51-79 HIGH, 80+ CRITICAL
- Immediate attention flag: Use ONLY for life-threatening interactions or critical concerns
- Never make up interactions - if unsure, mark as minor or omit"""

    @staticmethod
    def _get_user_prompt(age: Optional[int], allergies: Optional[str],
                        medications: Optional[str], conditions: Optional[str]) -> str:
        """Generate user prompt with patient information."""
        return f"""Please analyze this patient profile for safety concerns:

Age: {age if age else 'Not provided'}
Allergies: {allergies if allergies else 'None reported'}
Current Medications: {medications if medications else 'None'}
Medical Conditions: {conditions if conditions else 'None'}

Assess:
1. Drug-drug interactions
2. Drug-allergy contraindications
3. Age-related medication appropriateness
4. Overall risk level and score
5. Clinical recommendations
6. Whether immediate medical attention is needed

Return ONLY the JSON structure. No additional text."""

    @staticmethod
    def calculate_risk_score_from_interactions(interactions: List[Dict], allergy_concerns: List[Dict]) -> int:
        """
        Calculate risk score based on number and severity of interactions.
        """
        score = 0

        # Score interactions by severity
        for interaction in interactions:
            severity = interaction.get("severity", "MILD").upper()
            if severity == "SEVERE":
                score += 30
            elif severity == "MODERATE":
                score += 15
            elif severity == "MILD":
                score += 5

        # Add points for allergy concerns
        score += len(allergy_concerns) * 10

        return min(100, score)
