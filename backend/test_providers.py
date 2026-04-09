import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_file = Path('.env')
if env_file.exists():
    load_dotenv(env_file)
    print(f"? Loaded .env file")
else:
    print("? .env file not found")

# Check which API keys are configured
print("\n?? API Keys Status:")
print("-" * 50)

keys_status = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
    'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
}

for key_name, key_value in keys_status.items():
    if key_value:
        # Show first 20 and last 10 chars
        masked = f"{key_value[:20]}...{key_value[-10:]}"
        print(f"? {key_name}: {masked}")
    else:
        print(f"? {key_name}: NOT SET")

# Now test provider initialization
print("\n?? Testing Provider Initialization:")
print("-" * 50)

try:
    from services.ai_provider import get_provider_manager
    
    manager = get_provider_manager()
    
    print(f"\n?? Provider Manager Status:")
    print("-" * 50)
    
    for name, provider in manager.providers.items():
        availability = "? AVAILABLE" if provider.is_available() else "? NOT AVAILABLE"
        print(f"{name.upper():15} ? {availability}")
    
    # Count available
    available_count = sum(1 for p in manager.providers.values() if p.is_available())
    print(f"\n? Total available providers: {available_count}/3")
    
except Exception as e:
    print(f"? ERROR: {e}")
    import traceback
    traceback.print_exc()
