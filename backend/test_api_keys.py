"""Test if AI providers are configured and working."""
import os
import sys
from dotenv import load_dotenv

# Load .env
load_dotenv()

print("=" * 60)
print("CHECKING AI PROVIDER CONFIGURATION")
print("=" * 60)

# Check OpenAI
openai_key = os.getenv("OPENAI_API_KEY")
print(f"\n✓ OPENAI_API_KEY: {'SET' if openai_key else 'NOT SET'}")
if openai_key:
    print(f"  Key preview: {openai_key[:20]}...{openai_key[-10:]}")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        print("  ✓ OpenAI SDK imported successfully")
        # Try to list models
        models = client.models.list()
        print(f"  ✓ OpenAI API accessible (found {len(models.data)} models)")
    except Exception as e:
        print(f"  ✗ OpenAI error: {e}")

# Check Google Gemini
google_key = os.getenv("GOOGLE_API_KEY")
print(f"\n✓ GOOGLE_API_KEY: {'SET' if google_key else 'NOT SET'}")
if google_key:
    print(f"  Key preview: {google_key[:20]}...{google_key[-10:]}")
    try:
        import google.generativeai as genai
        genai.configure(api_key=google_key)
        print("  ✓ Google Generative AI SDK imported successfully")
        # Try to list models
        models = genai.list_models()
        print(f"  ✓ Google API accessible")
    except Exception as e:
        print(f"  ✗ Google error: {e}")

# Check Groq
groq_key = os.getenv("GROQ_API_KEY")
print(f"\n✓ GROQ_API_KEY: {'SET' if groq_key else 'NOT SET'}")
if groq_key:
    print(f"  Key preview: {groq_key[:20]}...{groq_key[-10:]}")
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        print("  ✓ Groq SDK imported successfully")
    except Exception as e:
        print(f"  ✗ Groq error: {e}")

# Check AI Provider Manager
print("\n" + "=" * 60)
print("CHECKING AI PROVIDER MANAGER")
print("=" * 60)
try:
    from services.ai_provider import get_provider_manager
    manager = get_provider_manager()
    print("\n✓ Provider Manager initialized")
    
    # Check which providers are available
    for name, provider in manager.providers.items():
        is_avail = provider.is_available()
        print(f"  {name.upper()}: {'✓ AVAILABLE' if is_avail else '✗ NOT AVAILABLE'}")
        
except Exception as e:
    print(f"\n✗ Provider Manager error: {e}")

print("\n" + "=" * 60)
