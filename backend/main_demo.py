"""
MedGuard AI - FastAPI Backend (Demo Version)
Works without problematic numpy/opencv dependencies for local testing
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MedGuard AI API",
    description="Intelligent Fake Medicine & Patient Safety System",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# Health Check
# ==============================================================================
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "medguard-backend",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

# ==============================================================================
# Medicine Analysis Endpoint
# ==============================================================================
@app.post("/api/analyze", tags=["analyze"])
async def analyze_medicine(image_base64: str, mime_type: str = "image/jpeg"):
    """
    Analyze medicine image for authenticity.

    For demo: Returns mock analysis based on image size
    """
    if not image_base64:
        raise HTTPException(status_code=400, detail="image_base64 required")

    # Mock analysis based on image data length
    confidence = min(95, 50 + (len(image_base64) % 50))

    return {
        "is_medicine": True,
        "medicine_name": "Paracetamol 500mg",
        "manufacturer": "PharmaCorp Industries",
        "batch_number": "B2024156",
        "expiry_date": "12/2025",
        "dosage": "500mg",
        "active_ingredients": ["Paracetamol"],
        "extracted_text": "PARACETAMOL 500MG TABLETS",
        "visual_authenticity_score": 85.0,
        "text_clarity_score": 90.0,
        "data_completeness_score": 80.0,
        "format_validity_score": 95.0,
        "overall_confidence": float(confidence),
        "authenticity_indicators": ["Clear packaging", "Valid printing", "Security hologram"],
        "suspicious_signs": [],
        "missing_fields": [],
        "verdict": "GENUINE" if confidence > 80 else "SUSPICIOUS" if confidence > 60 else "FAKE",
        "explanation": f"Medicine analysis complete at {confidence:.1f}% confidence. Standard packaging format with clear labeling detected."
    }

# ==============================================================================
# Patient Safety Endpoint
# ==============================================================================
@app.post("/api/patient-safety", tags=["safety"])
async def analyze_patient_safety(
    age: int = None,
    allergies: str = None,
    current_medications: str = None,
    medical_conditions: str = None
):
    """
    Analyze patient profile for drug interactions and safety concerns.

    For demo: Returns mock safety analysis
    """

    risk_score = 0
    interactions = []

    # Simple logic for demo
    if current_medications and "warfarin" in current_medications.lower():
        if "aspirin" in current_medications.lower():
            risk_score = 72
            interactions.append({
                "drug1": "Warfarin",
                "drug2": "Aspirin",
                "severity": "SEVERE",
                "description": "Increased bleeding risk when combined"
            })

    if allergies and current_medications:
        allergy_list = [x.strip().lower() for x in allergies.split(",")]
        med_list = [x.strip().lower() for x in current_medications.split(",")]
        if any(allergy in med for allergy in allergy_list for med in med_list):
            risk_score = max(risk_score, 80)

    if not risk_score:
        risk_score = 20 if current_medications else 0

    # Determine risk level
    if risk_score < 20:
        risk_level = "LOW"
    elif risk_score < 50:
        risk_level = "MODERATE"
    elif risk_score < 80:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "interactions": interactions,
        "allergy_concerns": [],
        "age_considerations": [],
        "recommendations": [
            "Consult with healthcare provider for personalized advice",
            "Monitor for adverse reactions",
            "Maintain regular follow-ups"
        ],
        "requires_immediate_attention": risk_score > 75,
        "clinical_summary": f"Patient safety analysis complete. Risk level: {risk_level}. Score: {risk_score}/100"
    }

# ==============================================================================
# Dashboard Endpoint
# ==============================================================================
@app.get("/api/dashboard/stats", tags=["dashboard"])
async def get_dashboard_stats():
    """Get dashboard statistics."""
    return {
        "total_scans": 142,
        "genuine_count": 98,
        "suspicious_count": 28,
        "fake_count": 14,
        "invalid_count": 2,
        "average_confidence": 81.5
    }

@app.get("/api/dashboard/history", tags=["dashboard"])
async def get_scan_history(limit: int = 20):
    """Get recent scan history."""
    return {
        "total": 142,
        "recent": [
            {
                "medicine_name": "Paracetamol 500mg",
                "verdict": "GENUINE",
                "confidence": 87.5,
                "timestamp": "2026-04-05T13:20:00Z"
            },
            {
                "medicine_name": "Ibuprofen 200mg",
                "verdict": "SUSPICIOUS",
                "confidence": 62.0,
                "timestamp": "2026-04-05T13:15:00Z"
            },
            {
                "medicine_name": "Aspirin",
                "verdict": "GENUINE",
                "confidence": 91.0,
                "timestamp": "2026-04-05T13:10:00Z"
            }
        ]
    }

@app.get("/api/dashboard/verdict-breakdown", tags=["dashboard"])
async def get_verdict_breakdown():
    """Get verdict breakdown statistics."""
    return {
        "genuine_percent": 69.0,
        "suspicious_percent": 19.7,
        "fake_percent": 9.9,
        "invalid_percent": 1.4,
        "total_scans": 142
    }

# ==============================================================================
# Root Endpoint
# ==============================================================================
@app.get("/", tags=["info"])
async def root():
    """API information endpoint."""
    return {
        "name": "MedGuard AI API (Demo)",
        "description": "Intelligent Fake Medicine & Patient Safety System",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "analyze": "/api/analyze",
            "patient_safety": "/api/patient-safety",
            "dashboard": "/api/dashboard/stats",
            "docs": "/api/docs"
        }
    }

# ==============================================================================
# Error Handlers
# ==============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
    }

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
    return {
        "error": "Internal server error",
        "status_code": 500,
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting MedGuard AI Backend (Demo)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
