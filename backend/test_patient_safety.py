"""Comprehensive test suite for Patient Safety Engine."""
import asyncio
import sys
import json
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.patient_safety_engine import PatientSafetyEngine


def test_no_patient_data():
    """Test with no patient data - should return LOW risk."""
    print("\n" + "="*60)
    print("TEST 1: No Patient Data")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety()
    
    print(json.dumps(result, indent=2))
    assert result['risk_level'] == 'LOW', "Should be LOW risk with no data"
    assert result['risk_score'] == 0, "Score should be 0 with no data"
    print("✓ PASSED: No data returns LOW risk")
    return result


def test_warfarin_aspirin_interaction():
    """Test dangerous drug interaction - Warfarin + Aspirin = HIGH risk."""
    print("\n" + "="*60)
    print("TEST 2: Dangerous Drug Interaction (Warfarin + Aspirin)")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=65,
        medications="Warfarin, Aspirin, Lisinopril",
        conditions="Atrial Fibrillation"
    )
    
    print(json.dumps(result, indent=2))
    assert result['risk_level'] in ['HIGH', 'CRITICAL'], f"Should be HIGH/CRITICAL risk, got {result['risk_level']}"
    assert result['risk_score'] > 50, f"Score should be >50, got {result['risk_score']}"
    assert len(result['interactions']) > 0, "Should detect drug interactions"
    print(f"✓ PASSED: Detected dangerous interaction with risk level {result['risk_level']}")
    return result


def test_elderly_patient():
    """Test elderly patient (65+) with medications."""
    print("\n" + "="*60)
    print("TEST 3: Elderly Patient (65+ years)")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=75,
        medications="Metformin, Atorvastatin, Amlodipine",
        conditions="Type 2 Diabetes, Hypertension"
    )
    
    print(json.dumps(result, indent=2))
    assert len(result['age_considerations']) > 0, "Should have age-related considerations"
    assert "older" in result['clinical_summary'].lower() or result['age_considerations'], "Should flag elderly concerns"
    print(f"✓ PASSED: Flagged elderly patient concerns. Risk level: {result['risk_level']}")
    return result


def test_pediatric_patient():
    """Test child (under 12) with medications."""
    print("\n" + "="*60)
    print("TEST 4: Pediatric Patient (Under 12)")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=8,
        medications="Amoxicillin, Acetaminophen",
        conditions="Ear Infection"
    )
    
    print(json.dumps(result, indent=2))
    assert len(result['age_considerations']) > 0, "Should have pediatric considerations"
    print(f"✓ PASSED: Flagged pediatric patient concerns. Risk level: {result['risk_level']}")
    return result


def test_allergy_concern():
    """Test medication with allergy keyword overlap."""
    print("\n" + "="*60)
    print("TEST 5: Medication-Allergy Concern")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=45,
        medications="Penicillin, Ibuprofen",
        allergies="Penicillin, Sulfonamides"
    )
    
    print(json.dumps(result, indent=2))
    assert len(result['allergy_concerns']) > 0, "Should detect allergy concerns"
    assert result['requires_immediate_attention'] == True, "Should require immediate attention"
    print(f"✓ PASSED: Detected allergy-medication concern. Risk level: {result['risk_level']}")
    return result


def test_warfarin_ibuprofen_interaction():
    """Test moderate interaction - Warfarin + Ibuprofen."""
    print("\n" + "="*60)
    print("TEST 6: Moderate Interaction (Warfarin + Ibuprofen)")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=60,
        medications="Warfarin, Ibuprofen",
        conditions="Atrial Fibrillation, Arthritis"
    )
    
    print(json.dumps(result, indent=2))
    assert result['risk_level'] in ['MODERATE', 'HIGH', 'CRITICAL'], f"Should detect risk, got {result['risk_level']}"
    assert result['risk_score'] > 0, "Score should be > 0"
    assert len(result['interactions']) > 0, "Should detect interaction"
    print(f"✓ PASSED: Detected warfarin-ibuprofen interaction. Risk level: {result['risk_level']}")
    return result


def test_safe_medications():
    """Test with common safe medications."""
    print("\n" + "="*60)
    print("TEST 7: Safe Medication Combination")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=50,
        medications="Vitamin D, Vitamin B12",
        conditions="None"
    )
    
    print(json.dumps(result, indent=2))
    assert result['risk_level'] == 'LOW', f"Should be LOW risk for safe meds, got {result['risk_level']}"
    print(f"✓ PASSED: Safe medications detected. Risk level: {result['risk_level']}")
    return result


def test_complete_patient_profile():
    """Test with comprehensive patient profile."""
    print("\n" + "="*60)
    print("TEST 8: Comprehensive Patient Profile")
    print("="*60)
    
    engine = PatientSafetyEngine()
    result = engine.analyze_patient_safety(
        age=72,
        medications="Warfarin, Metformin, Lisinopril, Amlodipine, Atorvastatin",
        allergies="Penicillin, NSAIDs",
        conditions="Atrial Fibrillation, Type 2 Diabetes, Hypertension, Hyperlipidemia"
    )
    
    print(json.dumps(result, indent=2))
    assert result['risk_level'] in ['MODERATE', 'HIGH', 'CRITICAL'], f"Should detect some risk, got {result['risk_level']}"
    assert len(result['recommendations']) > 0, "Should provide recommendations"
    print(f"✓ PASSED: Comprehensive profile analyzed. Risk level: {result['risk_level']}")
    print(f"  - Interactions found: {len(result['interactions'])}")
    print(f"  - Allergy concerns: {len(result['allergy_concerns'])}")
    print(f"  - Age considerations: {len(result['age_considerations'])}")
    return result


def test_engine_initialization():
    """Test that engine initializes properly."""
    print("\n" + "="*60)
    print("TEST 0: Engine Initialization")
    print("="*60)
    
    engine = PatientSafetyEngine()
    print(f"✓ Engine initialized")
    print(f"  - OpenAI client: {'✓ Available' if engine.openai_client else '✗ Not available'}")
    print(f"  - Gemini client: {'✓ Available' if engine.gemini_client else '✗ Not available (will use heuristic)'}")
    if not engine.openai_client and not engine.gemini_client:
        print("  - ⚠️  No AI providers configured - will use heuristic fallback (deterministic)")
    return True


def run_all_tests():
    """Run all tests and print summary."""
    print("\n" + "="*70)
    print("PATIENT SAFETY ENGINE - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    tests = [
        ("Engine Initialization", test_engine_initialization),
        ("No Patient Data", test_no_patient_data),
        ("Warfarin + Aspirin", test_warfarin_aspirin_interaction),
        ("Elderly Patient", test_elderly_patient),
        ("Pediatric Patient", test_pediatric_patient),
        ("Allergy Concern", test_allergy_concern),
        ("Warfarin + Ibuprofen", test_warfarin_ibuprofen_interaction),
        ("Safe Medications", test_safe_medications),
        ("Comprehensive Profile", test_complete_patient_profile),
    ]
    
    passed = 0
    failed = 0
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            passed += 1
            results.append((test_name, "✓ PASSED", result))
        except AssertionError as e:
            failed += 1
            results.append((test_name, f"✗ FAILED: {str(e)}", None))
            print(f"\n✗ FAILED: {e}")
        except Exception as e:
            failed += 1
            results.append((test_name, f"✗ ERROR: {str(e)}", None))
            print(f"\n✗ ERROR: {e}")
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")
    print(f"Success Rate: {(passed/len(tests)*100):.1f}%")
    
    print("\nDetailed Results:")
    for test_name, status, _ in results:
        print(f"  {status:30} - {test_name}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
    
    print("="*70 + "\n")
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
