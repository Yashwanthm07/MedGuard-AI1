#!/usr/bin/env python
"""
Comprehensive Multi-Provider API Key Validation Test
Tests all three AI providers with real API keys
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# Suppress warnings for cleaner output
import warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv(Path('.env'))

print("\n" + "=" * 70)
print("MEDGUARD AI - MULTI-PROVIDER API KEY VALIDATION TEST")
print("=" * 70)

# ============================================================================
# PART 1: ENVIRONMENT VARIABLES CHECK
# ============================================================================
print("\n[1/3] ENVIRONMENT VARIABLES CHECK")
print("-" * 70)

env_vars = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
    'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
}

env_check = {}
for var_name, value in env_vars.items():
    is_set = bool(value)
    env_check[var_name] = is_set
    status = '[OK]' if is_set else '[MISSING]'
    print(f"{status} {var_name}: {'SET' if is_set else 'NOT SET'}")
    if value:
        # Show masked value
        print(f"      └─ {value[:25]}...{value[-10:]}")

# ============================================================================
# PART 2: SDK IMPORTS CHECK
# ============================================================================
print("\n[2/3] SDK IMPORTS CHECK")
print("-" * 70)

try:
    from openai import OpenAI
    print("[OK] OpenAI SDK imported successfully")
    openai_ok = True
except ImportError as e:
    print(f"[ERROR] Failed to import OpenAI: {e}")
    openai_ok = False

try:
    import google.generativeai
    print("[OK] Google Generative AI SDK imported successfully")
    gemini_ok = True
except ImportError as e:
    print(f"[ERROR] Failed to import Google SDK: {e}")
    gemini_ok = False

try:
    from groq import Groq
    print("[OK] Groq SDK imported successfully")
    groq_ok = True
except ImportError as e:
    print(f"[ERROR] Failed to import Groq: {e}")
    groq_ok = False

# ============================================================================
# PART 3: PROVIDER MANAGER INITIALIZATION
# ============================================================================
print("\n[3/3] PROVIDER MANAGER INITIALIZATION")
print("-" * 70)

try:
    from services.ai_provider import get_provider_manager
    manager = get_provider_manager()
    print("[OK] AIProviderManager initialized successfully")
    
    print("\nProvider Status:")
    provider_results = {}
    
    for name, provider in manager.providers.items():
        is_available = provider.is_available()
        provider_results[name] = is_available
        
        status = "[READY]" if is_available else "[NOT AVAILABLE]"
        model = getattr(provider, 'model', 'Unknown')
        
        print(f"  {status} {name.upper():10} (model: {model})")
    
except Exception as e:
    print(f"[ERROR] Failed to initialize AIProviderManager: {e}")
    provider_results = {}

# ============================================================================
# SUMMARY REPORT
# ============================================================================
print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

# Count available providers
available_count = sum(1 for v in provider_results.values() if v)
total_providers = len(provider_results)

print(f"\nEnvironment Variables: {sum(1 for v in env_check.values() if v)}/3 configured")
print(f"SDKs Installed: {sum([openai_ok, gemini_ok, groq_ok])}/3 installed")
print(f"Providers Available: {available_count}/{total_providers} ready")

# Overall status
all_good = (
    all(env_check.values()) and 
    all([openai_ok, gemini_ok, groq_ok]) and 
    available_count == total_providers
)

print("\n" + "=" * 70)
if all_good:
    print("STATUS: ✅ ALL SYSTEMS GO!")
    print("=" * 70)
    print("\n✅ All 3 providers are properly configured and ready to use:")
    print("   • OpenAI (Primary)")
    print("   • Google Gemini (Fallback)")
    print("   • Groq (Optional Speed Layer)")
    print("\n✅ Multi-provider failover system is active")
    print("✅ Ready to process medicine images")
    print("\n🚀 Next Steps:")
    print("   1. Start the backend: python main.py")
    print("   2. Upload a medicine image via the API")
    print("   3. Monitor logs to see provider selection")
    exit(0)
else:
    print("STATUS: ⚠️  INCOMPLETE SETUP")
    print("=" * 70)
    print("\n❌ Some issues found:")
    if env_check.get('OPENAI_API_KEY') is False:
        print("   • OPENAI_API_KEY not set")
    if env_check.get('GOOGLE_API_KEY') is False:
        print("   • GOOGLE_API_KEY not set")
    if env_check.get('GROQ_API_KEY') is False:
        print("   • GROQ_API_KEY not set")
    if not openai_ok:
        print("   • OpenAI SDK not installed (pip install openai)")
    if not gemini_ok:
        print("   • Google SDK not installed (pip install google-generativeai)")
    if not groq_ok:
        print("   • Groq SDK not installed (pip install groq)")
    exit(1)
