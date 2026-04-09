import os
from pathlib import Path
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv(Path('.env'))

print("🔬 COMPREHENSIVE PROVIDER TESTING")
print("=" * 60)

# Test with a simple OCR text
test_ocr = """
Medicine Box Label
Aspirin 500mg
Manufacturer: Example Pharma Ltd
Batch: ABC123456
Expiry: 2025-12-31
Dosage: 500mg
"""

print(f"\n📝 Test OCR Text Length: {len(test_ocr)} characters")
print(f"📝 Test OCR Sample: {test_ocr[:50]}...")

# Import manager
from services.ai_provider import get_provider_manager

manager = get_provider_manager()

print(f"\n✅ AIProviderManager initialized")
print(f"📊 Available providers: {len([p for p in manager.providers.values() if p.is_available()])}/3")

print("\n" + "=" * 60)
print("🧪 TESTING INDIVIDUAL PROVIDERS")
print("=" * 60)

# Test 1: Check each provider's availability and configuration
for name, provider in manager.providers.items():
    print(f"\n{name.upper()}:")
    print(f"  Available: {'✅ YES' if provider.is_available() else '❌ NO'}")
    if provider.is_available():
        print(f"  Model: {getattr(provider, 'model', 'Unknown')}")
        api_key = os.getenv(f'{name.upper()}_API_KEY')
        if api_key:
            print(f"  API Key: {api_key[:20]}...")
        else:
            print(f"  API Key: NOT SET")

print("\n" + "=" * 60)
print("✅ PROVIDER TEST SUMMARY")
print("=" * 60)

summary = {
    "openai_available": manager.providers['openai'].is_available(),
    "gemini_available": manager.providers['gemini'].is_available(),
    "groq_available": manager.providers['groq'].is_available(),
    "fallback_available": True,
    "total_providers": sum(1 for p in manager.providers.values() if p.is_available()),
}

print("\n📋 Results:")
for key, value in summary.items():
    status = "✅" if value else "❌"
    print(f"  {status} {key}: {value}")

print("\n" + "=" * 60)
if summary['total_providers'] == 3:
    print("🎉 SUCCESS! All 3 providers are configured and ready!")
    print("\n🚀 Next steps:")
    print("   1. Connect with real medicine images")
    print("   2. Test classification accuracy")
    print("   3. Monitor provider selection in logs")
else:
    print(f"⚠️  Only {summary['total_providers']}/3 providers available")
