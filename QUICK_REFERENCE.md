# MedGuard AI - Multi-Provider Quick Reference

## 🚀 Quick Start (5 minutes)

### 1️⃣ Install Dependencies
```bash
cd backend
pip install -r requirements.txt
# Adds: openai, google-generativeai, groq
```

### 2️⃣ Set API Keys
```bash
# Edit .env
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIza...
GROQ_API_KEY=gsk_...
```

### 3️⃣ Run Backend
```bash
python main.py
# API available at http://localhost:8000
```

---

## 📋 Code Examples

### Analyze Medicine Image
```python
from services.medicine_analyzer import MedicineAnalyzer

analyzer = MedicineAnalyzer()  # Auto-detects available providers

result = analyzer.analyze_medicine_image(
    image_base64="iVBORw0KGgo...",  # Base64 encoded image
    mime_type="image/jpeg",
    ocr_text="Aspirin 500mg, Batch ABC123"
)

print(f"Medicine: {result['medicine_name']}")
print(f"Confidence: {result['overall_confidence']}%")
print(f"Verdict: {result.get('verdict', 'N/A')}")
```

### Patient Safety Analysis
```python
from services.patient_safety_engine import PatientSafetyEngine

engine = PatientSafetyEngine()

safety = engine.analyze_patient_safety(
    age=45,
    allergies="Penicillin, Sulfa",
    medications="Warfarin, Aspirin",
    conditions="Atrial fibrillation"
)

print(f"Risk Level: {safety['risk_level']}")
print(f"Risk Score: {safety['risk_score']}")
if safety['requires_immediate_attention']:
    print("⚠️  CRITICAL - Immediate medical attention needed!")
```

### Get Provider Manager (Advanced)
```python
from services.ai_provider import get_provider_manager

manager = get_provider_manager()

# Direct access (usually not needed)
analysis = manager.analyze_medicine_image(
    image_base64="...",
    mime_type="image/jpeg",
    ocr_text="..."
)
```

### Check Available Providers
```python
from services.ai_provider import get_provider_manager

manager = get_provider_manager()

# In logs, you'll see:
# INFO: Available AI providers: ['openai', 'gemini', 'groq']

# Or check programmatically:
for name, provider in manager.providers.items():
    if provider.is_available():
        print(f"✓ {name.upper()} is available")
    else:
        print(f"✗ {name.upper()} is NOT configured")
```

---

## 🔍 Debugging

### Enable Verbose Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now see all provider attempts:
# INFO: Attempting analysis with OPENAI...
# ✓ Analysis successful with OPENAI
```

### Check Provider Status
```bash
# View initialization log
tail -100 logs/medguard.log | grep "Available\|initialized"

# Example output:
# INFO: OpenAI provider initialized with model: gpt-4o-mini
# INFO: Google Gemini provider initialized with model: gemini-2.0-flash-thinking-exp-1219
# INFO: Available AI providers: ['openai', 'gemini']
```

### Test Provider Fallback
```bash
# Temporarily disable primary provider
unset OPENAI_API_KEY

# Run analysis - will automatically fall back to Gemini
python test_medicine_analysis.py

# Check logs for:
# INFO: Attempting analysis with OPENAI...
# WARNING: ✗ OPENAI analysis failed, trying next provider...
# INFO: Attempting analysis with GEMINI...
# INFO: ✓ Analysis successful with GEMINI
```

### Simulate All Providers Down
```bash
# Disable all providers
unset OPENAI_API_KEY GOOGLE_API_KEY GROQ_API_KEY

# Run analysis - will use fallback
python test_medicine_analysis.py

# Result: Still returns valid JSON with fallback analysis
```

---

## 🔧 Configuration Tweaks

### Change Primary Provider
**Current Priority Order**:
1. OpenAI (fastest, most reliable)
2. Gemini (good quality, fallback)
3. Groq (fastest but optional)

To change order, edit `ai_provider.py`:
```python
# In AIProviderManager.analyze_medicine_image()
provider_order = ["openai", "gemini", "groq"]  # Edit this line
```

### Change Model
```python
# In OpenAIProvider.__init__():
self.model = "gpt-4o-mini"  # Change to gpt-4, gpt-4-turbo, etc.

# In GeminiProvider.__init__():
self.model = "gemini-2.0-flash-thinking-exp-1219"  # Change model

# In GroqProvider.__init__():
self.model = "llama-3.2-90b-vision-preview"  # Change model
```

### Adjust Timeouts (if needed)
```python
# In services/ai_provider.py
# Note: timeout is in request library, not exposed in SDK
# For OpenAI, adjust via:
self.client = OpenAI(
    api_key=self.api_key,
    timeout=60.0  # seconds
)
```

---

## 📊 Response Examples

### Successful Medicine Analysis
```json
{
  "is_medicine": true,
  "medicine_name": "Aspirin 500mg",
  "manufacturer": "Example Pharma Ltd",
  "batch_number": "ABC123456",
  "expiry_date": "2025-12-31",
  "dosage": "500mg",
  "overall_confidence": 87.5,
  "authenticity_indicators": [
    "Clear security hologram",
    "Proper barcode format",
    "Standard pharmaceutical packaging"
  ],
  "suspicious_signs": [],
  "verdict": "GENUINE",
  "explanation": "Medicine appears authentic with all required regulatory information clearly visible..."
}
```

### Suspicious Medicine Analysis
```json
{
  "is_medicine": true,
  "medicine_name": "Unknown Medicine",
  "overall_confidence": 62.3,
  "authenticity_indicators": [
    "Basic packaging structure detected"
  ],
  "suspicious_signs": [
    "Blurry manufacturer text",
    "Inconsistent font sizing",
    "Missing security features"
  ],
  "missing_fields": [
    "Manufacturer",
    "Batch Number",
    "Expiry Date"
  ],
  "verdict": "SUSPICIOUS",
  "explanation": "Minor concerns detected. Missing critical fields..."
}
```

### All Providers Failed (Fallback)
```json
{
  "is_medicine": true,
  "medicine_name": null,
  "overall_confidence": 45.0,
  "authenticity_indicators": [],
  "suspicious_signs": [
    "AI service unavailable - unable to verify authenticity"
  ],
  "missing_fields": [
    "medicine_name",
    "manufacturer",
    "batch_number",
    "expiry_date",
    "dosage"
  ],
  "verdict": "INVALID",
  "explanation": "Unable to complete AI-powered analysis. All providers are currently unavailable. Please try again later..."
}
```

### Patient Safety - High Risk
```json
{
  "risk_level": "HIGH",
  "risk_score": 65,
  "interactions": [
    {
      "drug1": "Warfarin",
      "drug2": "Aspirin",
      "severity": "SEVERE",
      "description": "Increased bleeding risk when combined"
    }
  ],
  "allergy_concerns": [
    {
      "drug": "Aspirin",
      "concern": "Patient allergic to salicylates"
    }
  ],
  "recommendations": [
    "Contact prescribing physician immediately",
    "Review medication list with pharmacist",
    "Consider alternative to Aspirin"
  ],
  "requires_immediate_attention": true,
  "clinical_summary": "Serious drug-drug interaction identified requiring immediate clinical review"
}
```

---

## ✅ Verification Checklist

### After Installation
- [ ] Run `pip install -r requirements.txt` successfully
- [ ] Set at least one API key in `.env`
- [ ] Backend starts without import errors
- [ ] Logs show "Available AI providers: [...]"

### After First Use
- [ ] Medicine analysis returns valid JSON
- [ ] Confidence score is reasonable (0-100)
- [ ] Verdict is one of: GENUINE, SUSPICIOUS, FAKE, INVALID
- [ ] All required fields present in response

### For Redundancy
- [ ] Set both OPENAI_API_KEY and GOOGLE_API_KEY
- [ ] Test with only OPENAI_API_KEY → works
- [ ] Test with only GOOGLE_API_KEY → works
- [ ] Test with both → uses OpenAI first
- [ ] Test with neither → returns fallback analysis

---

## 🚨 Troubleshooting

### "No AI providers available"
```bash
# Check .env file
cat .env | grep -i api_key

# Expected output:
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AIza...

# If missing, add keys to .env
```

### "Analysis returned low confidence"
```python
# Check OCR text quality
result = analyzer.analyze_medicine_image(
    image_base64=image,
    ocr_text="your_ocr_text"
)

# If confidence < 30% and ocr_text is good:
# → Provider may have had network issue
# → Recommend retry
```

### "API Key Invalid" Error
```bash
# Verify key format
# OpenAI: Starts with "sk-"
# Google: Starts with "AIza"
# Groq: Starts with "gsk_"

# Test with cURL
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -20
```

### "JSON Parsing Failed"
```python
# Provider returned non-JSON response
# Usually means:
# 1. Rate limited (429) - wait and retry
# 2. API key expired - refresh key
# 3. Model not available - check model name
# 4. Service error (5xx) - retry later

# Check logs for exact error
tail -50 logs/medguard.log | grep -i "error"
```

### "Medicine image not recognized"
```python
# Try with different image
# Ensure: High quality, clear text, good lighting
# Avoid: Blurry, low contrast, sideways text

# Check OCR extraction
ocr_text = extract_text_with_tesseract(image)
if len(ocr_text.strip()) < 20:
    print("⚠️  OCR extracted minimal text - may affect analysis")
```

---

## 🎯 Performance Tips

### Optimize for Speed
```bash
# Use Groq (fastest)
export OPENAI_API_KEY=              # Unset
export GOOGLE_API_KEY=              # Unset
export GROQ_API_KEY=gsk_...         # Set this
# Response time: 1-2 seconds vs 3-5 seconds
```

### Optimize for Quality
```bash
# Use OpenAI (most accurate)
export OPENAI_API_KEY=sk-proj-...   # Set
export GOOGLE_API_KEY=AIza...       # Keep as fallback
export GROQ_API_KEY=                # Unset (optional)
# Response time: 2-4 seconds, best accuracy
```

### Optimize for Cost
```bash
# Use Gemini Free Tier
# - Remove other API keys
# - Use Google account with free tier
# - Limit to free tier quotas
export GOOGLE_API_KEY=AIza...       # Only this
# Cost: ~free (with limits)
```

### Add Local Caching
```python
# In routes/analyze.py, add:
import hashlib

image_hash = hashlib.sha256(image_data).hexdigest()
if image_hash in analysis_cache:
    return analysis_cache[image_hash]

result = analyzer.analyze_medicine_image(...)

analysis_cache[image_hash] = result
return result
```

---

## 📚 Reference Links

### Official Docs
- [OpenAI Vision API](https://platform.openai.com/docs/guides/vision)
- [Google Gemini API](https://ai.google.dev/)
- [Groq SDK](https://console.groq.com)

### Error Codes
- **OpenAI 401**: Invalid API key
- **OpenAI 429**: Rate limited
- **Google 403**: API not enabled
- **Groq 400**: Invalid model name

### API Key Generation
- [OpenAI API Keys](https://platform.openai.com/account/api-keys)
- [Google AI Studio](https://ai.google.dev/tutorials/python_quickstart)
- [Groq Console](https://console.groq.com)

---

## 🎓 Best Practices

### DO ✅
- Store API keys in `.env` file
- Use environment variables only
- Implement request validation
- Log provider selection
- Handle errors gracefully
- Test with multiple providers
- Monitor API usage

### DON'T ❌
- Hardcode API keys in code
- Commit `.env` to version control
- Ignore fallback scenarios
- Skip error handling
- Make assumptions about provider speed
- Mix personal API keys with dev keys
- Leave default models unchanged

---

**Version**: 1.0  
**Last Updated**: 2026-04-07  
**Status**: Production Ready ✅
