#!/usr/bin/env python3
"""Quick test of AI provider functionality."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

print(f"OPENAI_API_KEY loaded: {bool(os.getenv('OPENAI_API_KEY'))}")
print(f"GOOGLE_API_KEY loaded: {bool(os.getenv('GOOGLE_API_KEY'))}")
print(f"GROQ_API_KEY loaded: {bool(os.getenv('GROQ_API_KEY'))}")

from services.ai_provider import get_provider_manager
import base64
from PIL import Image
import io

# Create a simple test image (10x10 pixel medicine-like image)
def create_test_image():
    img = Image.new('RGB', (100, 100), color='white')
    # Add some text to make it look like medicine
    try:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "MEDICINE", fill='black')
    except:
        pass
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return image_base64

print("=" * 70)
print("TESTING AI PROVIDER MANAGER")
print("=" * 70)

try:
    manager = get_provider_manager()
    print("✓ Provider Manager initialized")
    
    # Create test image
    test_image = create_test_image()
    print(f"✓ Test image created ({len(test_image)} bytes base64)")
    
    print("\nAttempting analysis...")
    print("-" * 70)
    
    result = manager.analyze_medicine_image(
        image_base64=test_image,
        mime_type="image/jpeg",
        ocr_text="PARACETAMOL 500MG"
    )
    
    print("\n✓ Analysis completed!")
    print("-" * 70)
    print(f"Result keys: {list(result.keys())}")
    print(f"Is Medicine: {result.get('is_medicine')}")
    print(f"Confidence: {result.get('overall_confidence')}%")
    print(f"Verdict: {result.get('verdict_status', 'N/A')}")
    print(f"Explanation: {result.get('explanation', 'N/A')[:100]}...")
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
