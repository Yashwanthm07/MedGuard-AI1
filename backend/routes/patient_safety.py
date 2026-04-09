"""Patient safety analysis routes."""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging
from services.patient_safety_engine import PatientSafetyEngine
from models.schemas import PatientProfile, PatientSafetyResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patient-safety", tags=["patient-safety"])


@router.post("")
async def analyze_patient_safety(profile: PatientProfile):
    """
    Analyze patient profile for drug interactions and safety concerns.

    - Checks drug-drug interactions
    - Checks drug-allergy contraindications
    - Evaluates age-related considerations
    - Calculates risk level and score
    - Returns recommendations
    """
    try:
        engine = PatientSafetyEngine()
        analysis = engine.analyze_patient_safety(
            age=profile.age,
            allergies=profile.allergies,
            medications=profile.current_medications,
            conditions=profile.medical_conditions
        )

        result = PatientSafetyResult(**analysis)
        logger.info(f"Patient safety analysis complete. Risk level: {result.risk_level}")
        return result.dict()

    except Exception as e:
        logger.error(f"Patient safety analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Safety analysis failed: {str(e)}")


@router.get("/check")
async def quick_check(medications: Optional[str] = None, allergies: Optional[str] = None):
    """
    Quick safety check for medications and allergies.

    Query parameters:
    - medications: Comma-separated medication names
    - allergies: Comma-separated allergy names
    """
    try:
        engine = PatientSafetyEngine()
        analysis = engine.analyze_patient_safety(
            medications=medications,
            allergies=allergies
        )

        result = PatientSafetyResult(**analysis)
        return result.dict()

    except Exception as e:
        logger.error(f"Quick check error: {e}")
        raise HTTPException(status_code=500, detail="Quick check failed")
