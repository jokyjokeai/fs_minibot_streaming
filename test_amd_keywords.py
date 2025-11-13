#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test AMD Service - Keywords Matching & Confidence
Tests la logique de détection HUMAN vs MACHINE sans dépendre de Whisper
"""

import sys
from pathlib import Path

# Add system to path
sys.path.insert(0, str(Path(__file__).parent))

from system.services.amd_service import AMDService
from system.config import config

# Init AMD service
amd = AMDService()

# 50+ test cases
TEST_CASES = [
    # ============================================
    # HUMAN - Keywords uniques
    # ============================================
    {"text": "oui", "expected": "HUMAN", "min_conf": 0.6},
    {"text": "allo", "expected": "HUMAN", "min_conf": 0.6},
    {"text": "allô", "expected": "HUMAN", "min_conf": 0.6},
    {"text": "ouais", "expected": "HUMAN", "min_conf": 0.6},
    {"text": "bonjour", "expected": "HUMAN", "min_conf": 0.6},
    {"text": "bonsoir", "expected": "HUMAN", "min_conf": 0.6},

    # HUMAN - 2 keywords (confidence 0.8)
    {"text": "oui allo", "expected": "HUMAN", "min_conf": 0.8},
    {"text": "allo oui", "expected": "HUMAN", "min_conf": 0.8},
    {"text": "bonjour j'écoute", "expected": "HUMAN", "min_conf": 0.8},
    {"text": "oui je vous écoute", "expected": "HUMAN", "min_conf": 0.8},

    # HUMAN - 3+ keywords (confidence 0.95)
    {"text": "oui allô bonjour", "expected": "HUMAN", "min_conf": 0.95},
    {"text": "bonjour oui j'écoute", "expected": "HUMAN", "min_conf": 0.95},

    # ============================================
    # MACHINE - Répondeurs classiques
    # ============================================
    {"text": "messagerie", "expected": "MACHINE", "min_conf": 0.6},
    {"text": "messagerie vocale", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "repondeur", "expected": "MACHINE", "min_conf": 0.6},
    {"text": "vous etes bien", "expected": "MACHINE", "min_conf": 0.6},
    {"text": "bonjour vous etes bien", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "laissez un message", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "apres le bip", "expected": "MACHINE", "min_conf": 0.8},

    # MACHINE - Opérateurs (CRITIQUES!)
    {"text": "repondeur sfr", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "messagerie sfr", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "messagerie orange", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "repondeur free", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "messagerie bouygues", "expected": "MACHINE", "min_conf": 0.8},

    # MACHINE - Variations phonétiques (APRÈS ajout keywords)
    {"text": "repondeur c'est fer", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "messagerie ses fers", "expected": "MACHINE", "min_conf": 0.8},

    # MACHINE - Messages longs
    {"text": "bonjour vous etes bien sur le repondeur", "expected": "MACHINE", "min_conf": 0.95},
    {"text": "vous etes sur la messagerie vocale", "expected": "MACHINE", "min_conf": 0.95},

    # ============================================
    # MIX - MACHINE doit TOUJOURS gagner
    # ============================================
    {"text": "bonjour vous etes bien", "expected": "MACHINE", "min_conf": 0.8},
    {"text": "repondeur sfr bonjour", "expected": "MACHINE", "min_conf": 0.95},
    {"text": "oui bonjour vous etes bien", "expected": "MACHINE", "min_conf": 0.95},

    # ============================================
    # UNKNOWN - Pas de keywords
    # ============================================
    {"text": "", "expected": "UNKNOWN", "min_conf": 0.0},
    {"text": "euh", "expected": "UNKNOWN", "min_conf": 0.0},
    {"text": "hmm", "expected": "UNKNOWN", "min_conf": 0.0},
    {"text": "bah", "expected": "UNKNOWN", "min_conf": 0.0},
    {"text": "je sais pas", "expected": "UNKNOWN", "min_conf": 0.0},

    # UNKNOWN - Interrogatives (pas dans keywords)
    {"text": "où est-ce", "expected": "UNKNOWN", "min_conf": 0.0},
    {"text": "c'est qui", "expected": "HUMAN", "min_conf": 0.6},  # "c'est qui" dans HUMAN keywords

    # ============================================
    # EDGE CASES - Transcriptions réelles problématiques
    # ============================================
    {"text": "Où est-ce ?", "expected": "UNKNOWN", "min_conf": 0.0},  # Test 1 actuel
    {"text": "Bonjour, j'écoute ta...", "expected": "HUMAN", "min_conf": 0.8},  # Test 2 actuel
    {"text": "Répondeur et c'est fer !", "expected": "MACHINE", "min_conf": 0.6},  # Test 3 actuel (si pas variation)
]

def run_tests():
    """Run all test cases"""
    print("=" * 80)
    print("AMD SERVICE - KEYWORDS MATCHING TEST")
    print("=" * 80)
    print(f"\nKeywords HUMAN: {len(config.AMD_KEYWORDS_HUMAN)}")
    print(f"Keywords MACHINE: {len(config.AMD_KEYWORDS_MACHINE)}")
    print(f"\n{len(TEST_CASES)} test cases\n")
    print("=" * 80)

    passed = 0
    failed = 0
    errors = []

    for i, test in enumerate(TEST_CASES, 1):
        text = test["text"]
        expected = test["expected"]
        min_conf = test.get("min_conf", 0.0)

        # Run AMD detection
        result = amd.detect(text)
        detected = result["result"]
        confidence = result["confidence"]
        keywords = result.get("keywords_matched", [])

        # Check result
        result_ok = detected == expected
        conf_ok = confidence >= min_conf if expected != "UNKNOWN" else True

        if result_ok and conf_ok:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
            errors.append({
                "test": i,
                "text": text,
                "expected": expected,
                "detected": detected,
                "confidence": confidence,
                "min_conf": min_conf,
                "keywords": keywords
            })

        # Print result
        print(f"[{i:2d}] {status} | '{text[:40]:<40}' → {detected:8} (conf: {confidence:.2f}, expected: {expected})")

    # Summary
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} PASS, {failed} FAIL")
    accuracy = (passed / len(TEST_CASES)) * 100
    print(f"ACCURACY: {accuracy:.1f}%")
    print("=" * 80)

    # Show errors
    if errors:
        print(f"\n❌ FAILED TESTS ({len(errors)}):\n")
        for error in errors:
            print(f"Test {error['test']}: '{error['text']}'")
            print(f"  Expected: {error['expected']} (min_conf: {error['min_conf']})")
            print(f"  Got:      {error['detected']} (conf: {error['confidence']:.2f})")
            print(f"  Keywords: {error['keywords']}")
            print()

    return accuracy >= 95.0  # Success if 95%+ accuracy

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
