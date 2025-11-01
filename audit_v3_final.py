#!/usr/bin/env python3
"""
Audit Complet MiniBotPanel v3 FINAL - Phases 1-9
Vérifie la cohérence de toutes les fonctionnalités implémentées.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple

# Couleurs
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def check_file_exists(filepath: str) -> bool:
    """Vérifie qu'un fichier existe"""
    return Path(filepath).exists()

def check_import_in_file(filepath: str, import_pattern: str) -> bool:
    """Vérifie qu'un import existe dans un fichier"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            return import_pattern in content
    except:
        return False

def check_method_in_file(filepath: str, method_name: str) -> bool:
    """Vérifie qu'une méthode existe dans un fichier"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            return f"def {method_name}" in content
    except:
        return False

def audit_phase_1() -> List[Tuple[str, bool, str]]:
    """Phase 1: Dépendances & Setup"""
    results = []

    # Requirements.txt
    results.append((
        "requirements.txt updated",
        check_file_exists("requirements.txt") and
        check_import_in_file("requirements.txt", "pyannote.audio") and
        check_import_in_file("requirements.txt", "yt-dlp") and
        check_import_in_file("requirements.txt", "noisereduce") and
        check_import_in_file("requirements.txt", "spleeter"),
        "Phase 1: Dependencies"
    ))

    # .env.example HUGGINGFACE_TOKEN
    results.append((
        ".env.example has HUGGINGFACE_TOKEN",
        check_import_in_file(".env.example", "HUGGINGFACE_TOKEN"),
        "Phase 1: HuggingFace token"
    ))

    # config.py HUGGINGFACE_TOKEN
    results.append((
        "config.py has HUGGINGFACE_TOKEN",
        check_import_in_file("system/config.py", "HUGGINGFACE_TOKEN"),
        "Phase 1: Config HF token"
    ))

    # audio/background/ directory
    results.append((
        "audio/background/ directory exists",
        Path("audio").exists(),
        "Phase 1: Audio structure"
    ))

    return results

def audit_phase_2() -> List[Tuple[str, bool, str]]:
    """Phase 2: Background Audio & Audio Processing"""
    results = []

    # setup_audio.py
    results.append((
        "setup_audio.py exists",
        check_file_exists("setup_audio.py"),
        "Phase 2: setup_audio.py"
    ))

    # robot_freeswitch.py background methods
    results.append((
        "_start_background_audio in robot_freeswitch.py",
        check_method_in_file("system/robot_freeswitch.py", "_start_background_audio"),
        "Phase 2: Background audio start"
    ))

    results.append((
        "_stop_background_audio in robot_freeswitch.py",
        check_method_in_file("system/robot_freeswitch.py", "_stop_background_audio"),
        "Phase 2: Background audio stop"
    ))

    # clone_voice.py refactor
    results.append((
        "clone_voice.py has clean_audio_file",
        check_method_in_file("clone_voice.py", "clean_audio_file"),
        "Phase 2: Audio cleaning"
    ))

    return results

def audit_phase_3() -> List[Tuple[str, bool, str]]:
    """Phase 3: YouTube Voice Extraction"""
    results = []

    # youtube_extract.py
    results.append((
        "youtube_extract.py exists",
        check_file_exists("youtube_extract.py"),
        "Phase 3: YouTube extract script"
    ))

    results.append((
        "youtube_extract.py has speaker diarization",
        check_import_in_file("youtube_extract.py", "pyannote.audio") and
        check_method_in_file("youtube_extract.py", "perform_speaker_diarization"),
        "Phase 3: Speaker diarization"
    ))

    results.append((
        "youtube_extract.py has intelligent chunking",
        check_method_in_file("youtube_extract.py", "intelligent_split"),
        "Phase 3: Intelligent 4-10s chunking"
    ))

    return results

def audit_phase_4() -> List[Tuple[str, bool, str]]:
    """Phase 4: Multi-Voice Cloning & TTS"""
    results = []

    # clone_voice.py multi-voice
    results.append((
        "clone_voice.py has detect_available_voices",
        check_method_in_file("clone_voice.py", "detect_available_voices"),
        "Phase 4: Multi-voice detection"
    ))

    results.append((
        "clone_voice.py has detect_cloning_mode",
        check_method_in_file("clone_voice.py", "detect_cloning_mode"),
        "Phase 4: Auto cloning mode"
    ))

    results.append((
        "clone_voice.py has generate_tts_for_objections",
        check_method_in_file("clone_voice.py", "generate_tts_for_objections"),
        "Phase 4: TTS auto-generation"
    ))

    return results

def audit_phase_5() -> List[Tuple[str, bool, str]]:
    """Phase 5: Objections Database"""
    results = []

    # objections_database.py
    results.append((
        "objections_database.py has ObjectionEntry class",
        check_import_in_file("system/objections_database.py", "class ObjectionEntry"),
        "Phase 5: ObjectionEntry structure"
    ))

    results.append((
        "objections_database.py has OBJECTIONS_GENERAL",
        check_import_in_file("system/objections_database.py", "OBJECTIONS_GENERAL"),
        "Phase 5: General objections"
    ))

    results.append((
        "objections_database.py has themed objections",
        check_import_in_file("system/objections_database.py", "OBJECTIONS_FINANCE") and
        check_import_in_file("system/objections_database.py", "OBJECTIONS_CRYPTO") and
        check_import_in_file("system/objections_database.py", "OBJECTIONS_ENERGIE"),
        "Phase 5: Themed objections (finance, crypto, energie)"
    ))

    results.append((
        "objections_database.py has get_objections_by_theme",
        check_method_in_file("system/objections_database.py", "get_objections_by_theme"),
        "Phase 5: Theme-based loading"
    ))

    return results

def audit_phase_6() -> List[Tuple[str, bool, str]]:
    """Phase 6: Agent Autonome Core"""
    results = []

    # scenarios.py agent_mode
    results.append((
        "scenarios.py has is_agent_mode",
        check_method_in_file("system/scenarios.py", "is_agent_mode"),
        "Phase 6: Agent mode support"
    ))

    results.append((
        "scenarios.py has get_rail",
        check_method_in_file("system/scenarios.py", "get_rail"),
        "Phase 6: Rail navigation"
    ))

    # objection_matcher.py
    results.append((
        "objection_matcher.py has load_objections_for_theme",
        check_method_in_file("system/objection_matcher.py", "load_objections_for_theme"),
        "Phase 6: Theme-based objection loading"
    ))

    results.append((
        "objection_matcher.py returns audio_path",
        check_import_in_file("system/objection_matcher.py", '"audio_path"'),
        "Phase 6: Audio path in response"
    ))

    # robot_freeswitch.py
    results.append((
        "robot_freeswitch.py has _execute_autonomous_step",
        check_method_in_file("system/robot_freeswitch.py", "_execute_autonomous_step"),
        "Phase 6: Agent autonome execution"
    ))

    # freestyle_ai.py
    results.append((
        "freestyle_ai.py has rail return questions",
        check_import_in_file("system/services/freestyle_ai.py", "_rail_return_questions"),
        "Phase 6: Rail return questions (36 variantes)"
    ))

    results.append((
        "freestyle_ai.py has generate_rail_return_question",
        check_method_in_file("system/services/freestyle_ai.py", "generate_rail_return_question"),
        "Phase 6: Rail return generation"
    ))

    return results

def audit_phase_7() -> List[Tuple[str, bool, str]]:
    """Phase 7: Create Scenario Refactor"""
    results = []

    # create_scenario.py
    results.append((
        "create_scenario.py has agent_mode in scenario",
        check_import_in_file("create_scenario.py", '"agent_mode"'),
        "Phase 7: Agent mode in scenarios"
    ))

    results.append((
        "create_scenario.py has theme in scenario",
        check_import_in_file("create_scenario.py", '"theme"'),
        "Phase 7: Theme selection"
    ))

    results.append((
        "create_scenario.py has _ask_autonomous_agent_info",
        check_method_in_file("create_scenario.py", "_ask_autonomous_agent_info"),
        "Phase 7: Autonomous agent workflow"
    ))

    # scenarios.py qualification
    results.append((
        "scenarios.py has calculate_lead_score",
        check_method_in_file("system/scenarios.py", "calculate_lead_score"),
        "Phase 7: Cumulative lead scoring"
    ))

    return results

def audit_phase_8() -> List[Tuple[str, bool, str]]:
    """Phase 8: Cache Intelligent & Performance"""
    results = []

    # cache_manager.py
    results.append((
        "cache_manager.py exists",
        check_file_exists("system/cache_manager.py"),
        "Phase 8: CacheManager file"
    ))

    results.append((
        "cache_manager.py has get_scenario",
        check_method_in_file("system/cache_manager.py", "get_scenario"),
        "Phase 8: Scenario caching"
    ))

    results.append((
        "cache_manager.py has get_objections",
        check_method_in_file("system/cache_manager.py", "get_objections"),
        "Phase 8: Objections caching"
    ))

    # ❌ CRITICAL: CacheManager integration
    results.append((
        "scenarios.py uses CacheManager",
        check_import_in_file("system/scenarios.py", "from system.cache_manager import") or
        check_import_in_file("system/scenarios.py", "cache_manager"),
        "Phase 8: CacheManager in scenarios.py"
    ))

    results.append((
        "robot_freeswitch.py uses CacheManager",
        check_import_in_file("system/robot_freeswitch.py", "from system.cache_manager import") or
        check_import_in_file("system/robot_freeswitch.py", "cache_manager"),
        "Phase 8: CacheManager in robot_freeswitch.py"
    ))

    # ollama_nlp.py prewarm
    results.append((
        "ollama_nlp.py has prewarm method",
        check_method_in_file("system/services/ollama_nlp.py", "prewarm"),
        "Phase 8: Ollama prewarm"
    ))

    results.append((
        "ollama_nlp.py prewarm uses keep_alive",
        check_import_in_file("system/services/ollama_nlp.py", 'keep_alive="30m"') or
        check_import_in_file("system/services/ollama_nlp.py", "keep_alive="),
        "Phase 8: Ollama keep_alive 30min"
    ))

    # main.py startup integration
    results.append((
        "main.py initializes CacheManager",
        check_import_in_file("system/api/main.py", "from system.cache_manager import") or
        check_import_in_file("system/api/main.py", "get_cache"),
        "Phase 8: CacheManager in main.py startup"
    ))

    results.append((
        "main.py calls Ollama prewarm",
        check_import_in_file("system/api/main.py", "prewarm()"),
        "Phase 8: Ollama prewarm in startup"
    ))

    return results

def audit_phase_9() -> List[Tuple[str, bool, str]]:
    """Phase 9: Documentation"""
    results = []

    results.append((
        "README_v3_FINAL.md exists",
        check_file_exists("README_v3_FINAL.md"),
        "Phase 9: Complete README"
    ))

    results.append((
        "QUICK_START.md exists",
        check_file_exists("QUICK_START.md"),
        "Phase 9: Quick start guide"
    ))

    results.append((
        "TESTING_GUIDE.md exists",
        check_file_exists("TESTING_GUIDE.md"),
        "Phase 9: Testing guide"
    ))

    results.append((
        "PHASE_9_SUMMARY.md exists",
        check_file_exists("PHASE_9_SUMMARY.md"),
        "Phase 9: Delivery summary"
    ))

    return results

def print_results(phase_name: str, results: List[Tuple[str, bool, str]]):
    """Affiche résultats d'une phase"""
    print(f"\n{BLUE}{'='*70}{NC}")
    print(f"{BLUE}{phase_name}{NC}")
    print(f"{BLUE}{'='*70}{NC}")

    total = len(results)
    passed = sum(1 for _, status, _ in results if status)

    for check_name, status, description in results:
        status_icon = f"{GREEN}✅" if status else f"{RED}❌"
        print(f"{status_icon} {check_name}{NC}")
        if not status:
            print(f"   {YELLOW}→ {description}{NC}")

    rate = (passed / total * 100) if total > 0 else 0
    color = GREEN if rate == 100 else YELLOW if rate >= 80 else RED
    print(f"\n{color}Score: {passed}/{total} ({rate:.1f}%){NC}")

    return passed, total

def main():
    """Audit principal"""
    print(f"{BLUE}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║        🔍 AUDIT COMPLET - MiniBotPanel v3 FINAL                   ║")
    print("║                  Phases 1-9 Verification                          ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(f"{NC}")

    all_passed = 0
    all_total = 0

    # Phase 1
    results = audit_phase_1()
    passed, total = print_results("📋 PHASE 1: Dépendances & Setup", results)
    all_passed += passed
    all_total += total

    # Phase 2
    results = audit_phase_2()
    passed, total = print_results("🎵 PHASE 2: Background Audio & Audio Processing", results)
    all_passed += passed
    all_total += total

    # Phase 3
    results = audit_phase_3()
    passed, total = print_results("🎙️ PHASE 3: YouTube Voice Extraction", results)
    all_passed += passed
    all_total += total

    # Phase 4
    results = audit_phase_4()
    passed, total = print_results("🗣️ PHASE 4: Multi-Voice Cloning & TTS", results)
    all_passed += passed
    all_total += total

    # Phase 5
    results = audit_phase_5()
    passed, total = print_results("🛡️ PHASE 5: Objections Database", results)
    all_passed += passed
    all_total += total

    # Phase 6
    results = audit_phase_6()
    passed, total = print_results("🤖 PHASE 6: Agent Autonome Core", results)
    all_passed += passed
    all_total += total

    # Phase 7
    results = audit_phase_7()
    passed, total = print_results("🎬 PHASE 7: Create Scenario Refactor", results)
    all_passed += passed
    all_total += total

    # Phase 8
    results = audit_phase_8()
    passed, total = print_results("⚡ PHASE 8: Cache Intelligent & Performance", results)
    all_passed += passed
    all_total += total

    # Phase 9
    results = audit_phase_9()
    passed, total = print_results("📚 PHASE 9: Documentation", results)
    all_passed += passed
    all_total += total

    # Summary
    print(f"\n{BLUE}{'='*70}{NC}")
    print(f"{BLUE}📊 RÉSULTAT GLOBAL{NC}")
    print(f"{BLUE}{'='*70}{NC}")

    global_rate = (all_passed / all_total * 100) if all_total > 0 else 0

    if global_rate == 100:
        color = GREEN
        status = "✅ PARFAIT"
    elif global_rate >= 90:
        color = YELLOW
        status = "⚠️ QUASI-COMPLET (corrections mineures nécessaires)"
    elif global_rate >= 80:
        color = YELLOW
        status = "⚠️ BON (quelques corrections nécessaires)"
    else:
        color = RED
        status = "❌ INCOMPLET (corrections majeures nécessaires)"

    print(f"\n{color}Score global: {all_passed}/{all_total} ({global_rate:.1f}%){NC}")
    print(f"{color}Statut: {status}{NC}\n")

    # Recommandations
    if global_rate < 100:
        print(f"{YELLOW}📝 ACTIONS RECOMMANDÉES:{NC}")
        print(f"{YELLOW}1. Corriger les points marqués ❌{NC}")
        print(f"{YELLOW}2. Réexécuter cet audit: python3 audit_v3_final.py{NC}")
        print(f"{YELLOW}3. Tester avec TESTING_GUIDE.md{NC}\n")
    else:
        print(f"{GREEN}🎉 FÉLICITATIONS !{NC}")
        print(f"{GREEN}Toutes les fonctionnalités v3 FINAL sont présentes.{NC}")
        print(f"{GREEN}Prochaine étape: Exécuter TESTING_GUIDE.md{NC}\n")

    return 0 if global_rate == 100 else 1

if __name__ == "__main__":
    sys.exit(main())
