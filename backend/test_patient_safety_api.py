"""Test Patient Safety Engine via HTTP API."""
import requests
import json

BASE_URL = "http://localhost:8000/api"


def test_api_endpoint(name: str, method: str, endpoint: str, payload=None, params=None):
    """Test API endpoint and return formatted result."""
    print(f"\n{'='*70}")
    print(f"API TEST: {name}")
    print(f"{'='*70}")
    
    url = f"{BASE_URL}{endpoint}"
    print(f"📍 {method} {url}")
    
    try:
        if method == "POST":
            response = requests.post(url, json=payload, timeout=10)
        elif method == "GET":
            response = requests.get(url, params=params, timeout=10)
        
        print(f"✓ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Response:")
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Backend not running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_api_tests():
    """Run API tests for patient safety endpoints."""
    print("\n" + "="*70)
    print("PATIENT SAFETY ENGINE - API INTEGRATION TESTS")
    print("="*70)
    
    results = []
    
    # Test 1: POST /api/patient-safety with dangerous interaction
    test1_payload = {
        "age": 65,
        "current_medications": "Warfarin, Aspirin",
        "allergies": None,
        "medical_conditions": "Atrial Fibrillation"
    }
    r1 = test_api_endpoint(
        "Dangerous Drug Interaction (POST)",
        "POST",
        "/patient-safety",
        payload=test1_payload
    )
    results.append(("Dangerous Drug Interaction", r1))
    
    # Test 2: POST /api/patient-safety with elderly + medication
    test2_payload = {
        "age": 72,
        "current_medications": "Metformin, Lisinopril, Atorvastatin",
        "allergies": None,
        "medical_conditions": "Type 2 Diabetes, Hypertension"
    }
    r2 = test_api_endpoint(
        "Elderly Patient Profile (POST)",
        "POST",
        "/patient-safety",
        payload=test2_payload
    )
    results.append(("Elderly Patient Profile", r2))
    
    # Test 3: POST /api/patient-safety with allergy concern
    test3_payload = {
        "age": 45,
        "current_medications": "Penicillin, Ibuprofen",
        "allergies": "Penicillin",
        "medical_conditions": "Bacterial Infection"
    }
    r3 = test_api_endpoint(
        "Medication-Allergy Concern (POST)",
        "POST",
        "/patient-safety",
        payload=test3_payload
    )
    results.append(("Medication-Allergy Concern", r3))
    
    # Test 4: POST /api/patient-safety with no data
    test4_payload = {}
    r4 = test_api_endpoint(
        "No Patient Data (POST)",
        "POST",
        "/patient-safety",
        payload=test4_payload
    )
    results.append(("No Patient Data", r4))
    
    # Test 5: GET /api/patient-safety/check with query params
    r5 = test_api_endpoint(
        "Quick Safety Check (GET)",
        "GET",
        "/patient-safety/check",
        params={
            "medications": "Warfarin,Aspirin",
            "allergies": "NSAIDs"
        }
    )
    results.append(("Quick Safety Check", r5))
    
    # Summary
    print(f"\n{'='*70}")
    print("API TEST SUMMARY")
    print(f"{'='*70}")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"  {status:10} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*70 + "\n")
    
    return passed, total


if __name__ == "__main__":
    import sys
    passed, total = run_api_tests()
    sys.exit(0 if passed == total else 1)
