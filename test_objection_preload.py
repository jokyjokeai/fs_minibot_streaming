#!/usr/bin/env python3
"""
Test Objection Preload - MiniBotPanel v3

Test du nouveau système de preload des objections avec cache 4h.

Usage:
    python test_objection_preload.py
"""

import time
import logging
from system.cache_manager import get_cache
from system.objection_matcher import ObjectionMatcher
from system.scenarios import ScenarioManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_preload_timing():
    """
    Test 1: Mesurer le temps de chargement avec/sans cache
    """
    print("\n" + "="*70)
    print("TEST 1: Performance Cache (Preload vs Cache Hit)")
    print("="*70)

    # Nettoyer cache
    cache = get_cache()
    cache.clear_objections()
    print("✅ Cache cleared\n")

    # Test 1: Premier chargement (MISS - avec preload)
    print("🔄 First load (cache MISS)...")
    start = time.time()
    matcher1 = ObjectionMatcher.load_objections_from_file("objections_finance")
    duration_miss = (time.time() - start) * 1000
    print(f"   ⏱️  Duration: {duration_miss:.2f}ms")

    if matcher1:
        print(f"   ✅ Loaded {len(matcher1.objections)} objections\n")
    else:
        print("   ❌ Failed to load objections\n")
        return

    # Test 2: Deuxième chargement (HIT)
    print("🔄 Second load (cache HIT)...")
    start = time.time()
    matcher2 = ObjectionMatcher.load_objections_from_file("objections_finance")
    duration_hit = (time.time() - start) * 1000
    print(f"   ⏱️  Duration: {duration_hit:.2f}ms")
    print(f"   ✅ Loaded {len(matcher2.objections)} objections\n")

    # Speedup
    speedup = duration_miss / duration_hit if duration_hit > 0 else 0
    print(f"📊 Performance gain: {speedup:.1f}x faster (cache hit vs miss)")
    print(f"   Cache MISS: {duration_miss:.2f}ms")
    print(f"   Cache HIT:  {duration_hit:.2f}ms\n")


def test_cache_ttl():
    """
    Test 2: Vérifier la configuration TTL (doit être 4h)
    """
    print("\n" + "="*70)
    print("TEST 2: Cache TTL Configuration")
    print("="*70)

    cache = get_cache()
    stats = cache.get_stats()

    ttl_seconds = stats["config"]["objections_ttl"]
    ttl_hours = ttl_seconds / 3600

    print(f"⚙️  Objections TTL: {ttl_seconds}s ({ttl_hours:.1f}h)")

    if ttl_hours >= 3:
        print(f"✅ TTL is sufficient for long campaigns (3+ hours)")
    else:
        print(f"⚠️  WARNING: TTL too short for campaigns lasting 3+ hours")

    print()


def test_theme_file_loading():
    """
    Test 3: Tester le chargement de différentes thématiques
    """
    print("\n" + "="*70)
    print("TEST 3: Multiple Theme Loading")
    print("="*70)

    cache = get_cache()
    cache.clear_objections()

    themes = [
        "objections_general",
        "objections_finance",
        "objections_crypto",
        "objections_energie"
    ]

    for theme in themes:
        print(f"\n🔄 Loading: {theme}")
        matcher = ObjectionMatcher.load_objections_from_file(theme)

        if matcher:
            print(f"   ✅ Loaded {len(matcher.objections)} objections")
        else:
            print(f"   ⚠️  Failed to load {theme}")

    # Afficher stats cache
    print("\n📊 Cache Statistics:")
    stats = cache.get_stats()
    print(f"   Themes in cache: {stats['objections']['cache_size']}")
    print(f"   Cached themes: {', '.join(stats['objections']['cached_themes'])}")
    print(f"   Hit rate: {stats['objections']['hit_rate_pct']}%")
    print()


def test_scenario_theme_file():
    """
    Test 4: Tester get_theme_file() avec différents scénarios
    """
    print("\n" + "="*70)
    print("TEST 4: Scenario Theme File Detection")
    print("="*70)

    scenario_mgr = ScenarioManager()

    # Test avec scenario réel
    try:
        scenario = scenario_mgr.load_scenario("scenario_finance_b2c")
        if scenario:
            theme_file = scenario_mgr.get_theme_file(scenario)
            print(f"✅ Scenario: scenario_finance_b2c")
            print(f"   Theme file: {theme_file}")
            print(f"   Expected: objections_finance")

            if theme_file == "objections_finance":
                print("   ✅ PASS: Theme file correctly detected\n")
            else:
                print(f"   ⚠️  FAIL: Got '{theme_file}' instead of 'objections_finance'\n")
        else:
            print("⚠️  Scenario 'scenario_finance_b2c' not found\n")
    except Exception as e:
        print(f"⚠️  Error loading scenario: {e}\n")

    # Test avec scénario fictif (ancien système)
    print("Testing backward compatibility (old 'theme' field):")
    fake_scenario_old = {"theme": "finance"}
    theme_file = scenario_mgr.get_theme_file(fake_scenario_old)
    print(f"   Input: {{'theme': 'finance'}}")
    print(f"   Output: {theme_file}")
    print(f"   Expected: objections_finance")

    if theme_file == "objections_finance":
        print("   ✅ PASS: Backward compatibility works\n")
    else:
        print(f"   ⚠️  FAIL: Got '{theme_file}'\n")

    # Test avec nouveau système
    print("Testing new system ('theme_file' field):")
    fake_scenario_new = {"theme_file": "objections_crypto"}
    theme_file = scenario_mgr.get_theme_file(fake_scenario_new)
    print(f"   Input: {{'theme_file': 'objections_crypto'}}")
    print(f"   Output: {theme_file}")
    print(f"   Expected: objections_crypto")

    if theme_file == "objections_crypto":
        print("   ✅ PASS: New system works\n")
    else:
        print(f"   ⚠️  FAIL: Got '{theme_file}'\n")


def test_cache_persistence():
    """
    Test 5: Vérifier que le cache persiste entre plusieurs accès
    """
    print("\n" + "="*70)
    print("TEST 5: Cache Persistence")
    print("="*70)

    cache = get_cache()

    # Load objections
    print("🔄 Loading objections_finance...")
    matcher = ObjectionMatcher.load_objections_from_file("objections_finance")

    if not matcher:
        print("❌ Failed to load objections\n")
        return

    print(f"✅ Loaded {len(matcher.objections)} objections\n")

    # Vérifier que c'est en cache
    cached = cache.get_objections("objections_finance")
    if cached:
        print(f"✅ Objections found in cache ({len(cached)} entries)")
    else:
        print("❌ Objections NOT in cache")
        return

    # Attendre 2 secondes
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)

    # Re-vérifier cache
    cached_after = cache.get_objections("objections_finance")
    if cached_after:
        print(f"✅ Objections STILL in cache after 2s ({len(cached_after)} entries)")
        print("   Cache persists correctly")
    else:
        print("❌ Objections EXPIRED from cache (should not happen)")

    print()


def main():
    """Lance tous les tests"""
    print("\n" + "="*70)
    print("🧪 OBJECTION PRELOAD & CACHE TESTS - MiniBotPanel v3")
    print("="*70)

    try:
        test_preload_timing()
        test_cache_ttl()
        test_theme_file_loading()
        test_scenario_theme_file()
        test_cache_persistence()

        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED")
        print("="*70)

        # Afficher stats finales
        cache = get_cache()
        cache.print_stats()

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
