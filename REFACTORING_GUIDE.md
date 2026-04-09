# MedGuard AI - Multi-Provider Refactoring Guide

## 🎯 Overview

All Anthropic (Claude) API usage has been completely removed and replaced with a **production-ready multi-provider AI architecture**. The system now supports:

- **Primary**: OpenAI GPT-4 Vision (gpt-4o-mini)
- **Fallback**: Google Gemini (gemini-2.0-flash-thinking-exp-1219)
- **Optional**: Groq (llama-3.2-90b-vision-preview)

---

## ✅ What Was Changed

### 1. Removed Dependencies
- ❌ `anthropic==0.25.0` - REMOVED
- ❌ All Anthropic API imports - REMOVED

### 2. Added Dependencies
- ✅ `openai>=1.3.0` - Multi-modal language model
- ✅ `google-generativeai>=0.3.0` - Google Gemini integration
- ✅ `groq>=0.4.1` - Optional fast inference layer

### 3. New Architecture Files
- ✅ `services/ai_provider.py` - Multi-provider abstraction layer
  - `OpenAIProvider` - Primary provider
  - `GeminiProvider` - Fallback provider
  - `GroqProvider` - Optional fast layer
  - `AIProviderManager` - Orchestrates fallback logic

### 4. Refactored Services
- ✅ `services/medicine_analyzer.py` - Now uses `AIProviderManager`
- ✅ `services/patient_safety_engine.py` - Updated for multi-provider
- ✅ `services/decision_engine.py` - No changes needed (receives analysis data)
- ✅ `services/explanation_engine.py` - No changes needed (receives analysis data)

### 5. Configuration Files
- ✅ `.env.example` - Updated with new API key variables
- ✅ `.env` - Updated with multi-provider keys
- ✅ `requirements.txt` - Updated dependencies

### 6. Documentation
- ✅ `main.py` - Updated comments
- ✅ `routes/analyze.py` - Updated docstrings

---

## 🔑 Environment Variables

### Required (at least ONE must be set)
```bash
# Primary provider (Recommended)
OPENAI_API_KEY=sk-...your-key-here...

# Fallback provider
GOOGLE_API_KEY=AIza...your-key-here...

# Optional fast inference
GROQ_API_KEY=gsk_...your-key-here...
```

### Recommended Setup
For maximum reliability and cost optimization:
1. Set `OPENAI_API_KEY` (primary, most reliable)
2. Set `GOOGLE_API_KEY` (fallback, free tier available)
3. Optional: Set `GROQ_API_KEY` (for faster/cheaper inference)

---

## 🏗️ Architecture

### Provider Priority & Fallback Flow

```
┌──────────────────────────────────────┐
│   Medical Image Analysis Request     │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  AIProviderManager.analyze_medicine  │
└────────────┬─────────────────────────┘
             │
             ├─► Try OpenAI ──────┐
             │                     │
             ├─► Try Gemini ──┐   │
             │                 │   │
             ├─► Try Groq ──┐ │   │
             │              │ │   │
             └────────────────┼─┼──┘
                              │ │
                        Success? │
                         │  or │
                         ▼  ▼
                    All Fail? ▼
                         │
                         ▼
                ┌─────────────────────┐
                │ Fallback Analysis   │
                │ (Deterministic,     │
                │  OCR-based)         │
                └─────────────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │ Return Standardized │
                │ JSON Analysis       │
                └─────────────────────┘
```

### Data Flow

```
Frontend (Image Upload)
         │
         ▼
routes/analyze.py
         │
    ┌────┴────┐
    ▼         ▼
ImageProcessor  ImageProcessor
OCRService      parse_medicine_data
    │              │
    └──────┬───────┘
           ▼
    MedicineAnalyzer
    (uses AIProviderManager)
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
   AI    AI      AI
 Provider Fallback
  Logic
    │
    ▼
DecisionEngine ─────► verdict
ExplanationEngine ──► explanation
    │
    ▼
Response JSON
(to Frontend)
```

---

## 📋 Output Format (Unchanged)

### Decision Engine Output
```json
{
  "status": "GENUINE | SUSPICIOUS | FAKE | INVALID",
  "confidence": 0.0-100.0,
  "signals": []
}
```

### Explanation Engine Output
```json
{
  "summary": "Natural language explanation",
  "issues": [],
  "confidence_reason": "Why this confidence level"
}
```

### Medicine Analysis Output (AI Provider)
```json
{
  "is_medicine": true,
  "rejection_reason": null,
  "medicine_name": "Aspirin 500mg",
  "manufacturer": "Example Pharma",
  "batch_number": "ABC123456",
  "expiry_date": "2025-12-31",
  "dosage": "500mg",
  "active_ingredients": ["Acetylsalicylic acid"],
  "extracted_text": "...",
  "visual_authenticity_score": 85.0,
  "text_clarity_score": 90.0,
  "data_completeness_score": 80.0,
  "format_validity_score": 95.0,
  "overall_confidence": 87.0,
  "authenticity_indicators": ["Security features visible"],
  "suspicious_signs": [],
  "missing_fields": [],
  "explanation": "Detailed explanation..."
}
```

---

## 🚀 Installation & Setup

### Step 1: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
```bash
# Copy example to .env
cp .env.example .env

# Edit .env with your API keys
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

### Step 3: Verify Setup
```bash
python3 -c "from services.ai_provider import get_provider_manager; pm = get_provider_manager()"
```

---

## 🧪 Testing

### Test 1: Different OCR Inputs → Different Outputs

**Objective**: Verify dynamic output based on input

```python
from services.medicine_analyzer import MedicineAnalyzer

analyzer = MedicineAnalyzer()

# Test 1: Full medicine info
result1 = analyzer.analyze_medicine_image(
    image_base64="...",
    ocr_text="Aspirin 500mg, Batch: ABC123, Expiry: 2025-12"
)
# Expected: High confidence, all fields populated

# Test 2: Minimal medicine info
result2 = analyzer.analyze_medicine_image(
    image_base64="...",
    ocr_text="Medicine Label"
)
# Expected: Lower confidence, some fields missing

# Verify outputs are different
assert result1["overall_confidence"] != result2["overall_confidence"]
print("✓ Dynamic output test passed")
```

### Test 2: Empty OCR → Invalid

**Objective**: Verify fallback behavior with no data

```python
result = analyzer.analyze_medicine_image(
    image_base64="...",
    ocr_text=""
)
# Expected: is_medicine=False, low confidence
assert result["is_medicine"] == False
print("✓ Empty OCR test passed")
```

### Test 3: API Failure → Fallback Works

**Objective**: Verify fallback when all providers fail

```bash
# Unset all API keys
unset OPENAI_API_KEY
unset GOOGLE_API_KEY
unset GROQ_API_KEY

# Run analysis - should still return valid JSON
# (using deterministic fallback)
python3 -c "
from services.medicine_analyzer import MedicineAnalyzer
analyzer = MedicineAnalyzer()
result = analyzer.analyze_medicine_image(
    image_base64='...',
    ocr_text='Test medicine'
)
assert 'overall_confidence' in result
print('✓ Fallback test passed')
"
```

### Test 4: Verify No Repeated/Hardcoded Responses

**Objective**: Ensure responses aren't static

```python
from services.medicine_analyzer import MedicineAnalyzer

analyzer = MedicineAnalyzer()

# Same image, should get consistent results
results = []
for i in range(3):
    result = analyzer.analyze_medicine_image(
        image_base64="...",
        ocr_text=f"Medicine variant {i}"
    )
    results.append(result["overall_confidence"])

# With different OCR, should get different values
assert len(set(results)) > 1  # At least some variation
print("✓ No hardcoded responses test passed")
```

### Test 5: Patient Safety Multi-Provider

**Objective**: Verify patient safety engine also uses multi-provider

```python
from services.patient_safety_engine import PatientSafetyEngine

engine = PatientSafetyEngine()

result = engine.analyze_patient_safety(
    age=45,
    allergies="Penicillin",
    medications="Warfarin, Aspirin",
    conditions="Hypertension"
)

# Should get valid response with fallback
assert "risk_level" in result
assert result["risk_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
print("✓ Patient safety multi-provider test passed")
```

---

## 📊 Logging & Debugging

### Enable Debug Logging
```bash
DEBUG=true python3 backend/main.py
```

### Monitor Provider Selection
```bash
# Check logs for provider being used
tail -f logs/medguard.log | grep "Attempting analysis"
```

### Example Log Output
```
INFO: Available AI providers: ['openai', 'gemini', 'groq']
INFO: Attempting analysis with OPENAI...
INFO: ✓ Analysis successful with OPENAI
INFO: Medicine analysis completed. Confidence: 85.0%
```

### Fallback Logging
```
WARNING: ✗ OPENAI analysis failed, trying next provider...
INFO: Attempting analysis with GEMINI...
INFO: ✓ Analysis successful with GEMINI
```

---

## ⚠️ Error Handling

### All Providers Unavailable
When all providers fail or aren't configured:
- Returns **deterministic fallback analysis**
- Uses OCR-extracted text to determine if medicine
- Sets confidence to 45% (low, indicating service issue)
- Adds `suspicious_signs` with explanation
- **Backend continues working** (doesn't crash)

### Invalid OCR Data
- Empty or minimal OCR: Marked as `is_medicine=False`
- Missing fields: Listed in `missing_fields` array
- Low confidence: Returned but not hidden

### Retry Logic
- Each provider is tried once per request
- No automatic retry within same request
- Retry at HTTP level (client can retry)

---

## 🔐 Security Considerations

### API Key Management
- Never commit `.env` with real keys
- Use `.env.example` template
- Rotate keys periodically
- Use read-only API keys where available

### Rate Limiting
- OpenAI: Standard tier limits
- Gemini: Free tier ~60 RPM
- Groq: Free tier ~30 RPM
- Implement request queuing if needed

### Request Validation
- All OCR input is validated
- Image base64 is verified before processing
- API responses are validated for JSON structure

---

## 📈 Performance Optimization

### Latency Profile
- OpenAI response: ~2-4 seconds
- Gemini response: ~3-5 seconds
- Groq response: ~1-2 seconds (if available)
- Fallback: <100ms

### Cost Optimization
1. **Free Tier**: Use Google Gemini (free tier available)
2. **Budget**: Groq offers cheap inference
3. **Best Quality**: OpenAI (primary tier)
4. **Production**: OpenAI + Gemini fallback

### Caching Recommendations
- Cache analysis results by image hash
- TTL: 24 hours
- Skip cache for developmental/testing

---

## 🔄 Migration Path (If Needed)

### From Old Claude-Only System
```python
# Old code:
from services.medicine_analyzer import MedicineAnalyzer
analyzer = MedicineAnalyzer(api_key="claude_key")

# New code (automatically picks best provider):
analyzer = MedicineAnalyzer()
# No parameters needed - uses configured env vars
```

### Configuration Only Change
No code changes needed if:
- Using same API calls
- Expecting same JSON response format
- Not tied to Claude-specific features

---

## 📞 Troubleshooting

### "No AI providers available"
**Solution**: Set at least one API key in `.env`:
```bash
OPENAI_API_KEY=sk-...
```

### "All providers failed"
**Check logs**:
```bash
grep "error\|Error\|ERROR" logs/medguard.log
```

**Common causes**:
- Invalid API key format
- Quota exceeded
- Network connectivity issue
- Service down

### Provider-Specific Issues

#### OpenAI Errors
- Invalid key: `403 Forbidden`
- Quota exceeded: `429 Too Many Requests`
- Model not found: Check model name

#### Gemini Errors
- API not enabled: Enable in Google Cloud Console
- Invalid key: Check key format
- Quota: Free tier limited

#### Groq Errors
- Model not available: Check model name
- Rate limited: Implement backoff

---

## 🎓 Code Examples

### Using Provider Manager Directly
```python
from services.ai_provider import get_provider_manager

manager = get_provider_manager()
analysis = manager.analyze_medicine_image(
    image_base64="...",
    mime_type="image/jpeg",
    ocr_text="OCR extracted text"
)
```

### Using Medicine Analyzer (Recommended)
```python
from services.medicine_analyzer import MedicineAnalyzer

analyzer = MedicineAnalyzer()
analysis = analyzer.analyze_medicine_image(
    image_base64="...",
    ocr_text="OCR extracted text"
)
```

### Using Patient Safety Engine
```python
from services.patient_safety_engine import PatientSafetyEngine

engine = PatientSafetyEngine()
safety = engine.analyze_patient_safety(
    age=45,
    allergies="Penicillin",
    medications="Warfarin",
    conditions="Hypertension"
)
```

---

## 📚 Additional Resources

- [OpenAI Vision Documentation](https://platform.openai.com/docs/guides/vision)
- [Google Gemini API](https://ai.google.dev/tutorials/python_quickstart)
- [Groq API Documentation](https://console.groq.com)

---

## ✨ Summary

✅ **Anthropic API completely removed**  
✅ **Multi-provider architecture implemented**  
✅ **Real-time, dynamic AI pipeline maintained**  
✅ **Automatic fallback logic working**  
✅ **No breaking changes to API contracts**  
✅ **Production-ready and scalable**  

---

**Last Updated**: April 7, 2026  
**Status**: ✅ Complete and Ready for Production
