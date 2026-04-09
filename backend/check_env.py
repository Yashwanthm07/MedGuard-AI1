import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path('.env'))

print('API Key Environment Check:')
print('-' * 50)

keys = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
    'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
}

for key_name, key_value in keys.items():
    status = 'SET' if key_value else 'NOT SET'
    print(f"{key_name}: {status}")
    if key_value:
        print(f"  -> {key_value[:30]}...")
