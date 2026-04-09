from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class VerdictType(str, Enum):
    GENUINE = "GENUINE"
    SUSPICIOUS = "SUSPICIOUS"
    FAKE = "FAKE"
    INVALID = "INVALID"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Medicine Analysis Schemas
class MedicineAnalysisRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded image")
    mime_type: str = Field(default="image/jpeg", description="Image MIME type")


class MedicineAnalysisResult(BaseModel):
    is_medicine: bool
    rejection_reason: Optional[str] = None
    medicine_name: Optional[str] = None
    manufacturer: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    dosage: Optional[str] = None
    active_ingredients: List[str] = []
    extracted_text: str
    text_boxes: List[dict] = []
    image_size: Optional[dict] = None
    visual_authenticity_score: float  # 0-100
    text_clarity_score: float  # 0-100
    data_completeness_score: float  # 0-100
    format_validity_score: float  # 0-100
    overall_confidence: float  # 0-100
    ai_assisted: bool = False
    authenticity_indicators: List[str] = []
    suspicious_signs: List[str] = []
    missing_fields: List[str] = []
    verdict: VerdictType
    explanation: str


class PatientProfile(BaseModel):
    age: Optional[int] = None
    allergies: Optional[str] = Field(default=None, description="Comma-separated allergies")
    current_medications: Optional[str] = Field(default=None, description="Comma-separated medications")
    medical_conditions: Optional[str] = Field(default=None, description="Comma-separated conditions")


class DrugInteraction(BaseModel):
    drug1: str
    drug2: str
    severity: str  # MILD, MODERATE, SEVERE
    description: str


class AlergyConcern(BaseModel):
    drug: str
    concern: str


class AgeConsideration(BaseModel):
    concern: str
    recommendation: str


class PatientSafetyResult(BaseModel):
    risk_level: RiskLevel
    risk_score: int  # 0-100
    interactions: List[DrugInteraction] = []
    allergy_concerns: List[AlergyConcern] = []
    age_considerations: List[AgeConsideration] = []
    recommendations: List[str] = []
    requires_immediate_attention: bool = False
    clinical_summary: str


class DashboardStats(BaseModel):
    total_scans: int = 0
    genuine_count: int = 0
    suspicious_count: int = 0
    fake_count: int = 0
    invalid_count: int = 0
    average_confidence: float = 0.0
