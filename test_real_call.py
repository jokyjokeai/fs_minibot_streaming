#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Real Call - MiniBotPanel v3
Lance un appel reel avec logs detailles et stats de latence
"""

import sys
import time
import logging
from pathlib import Path

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s'
)

# ===== MINIMAL LOGGING SETUP (garder strict minimum + focus HANGUP) =====
def setup_minimal_logging():
    """Configure logs pour garder SEULEMENT essentiels + focus HANGUP debug"""

    import sys
    import os

    # Masquer COMPLÈTEMENT les logs websockets (même les erreurs)
    logging.getLogger('websockets.server').setLevel(logging.CRITICAL)
    logging.getLogger('websockets').setLevel(logging.CRITICAL)

    # Masquer logs Vosk (très verbeux)
    logging.getLogger('minibot.system.services.streaming_asr').setLevel(logging.ERROR)

    # Masquer logs services (warmup, init, etc.)
    logging.getLogger('system.services').setLevel(logging.ERROR)
    logging.getLogger('system.services.amd_service').setLevel(logging.ERROR)
    logging.getLogger('system.services.faster_whisper_stt').setLevel(logging.ERROR)

    # Masquer logs cache/objections/intents (sauf erreurs critiques)
    logging.getLogger('system.cache_manager').setLevel(logging.ERROR)
    logging.getLogger('system.objections_db').setLevel(logging.ERROR)
    logging.getLogger('system.objection_matcher').setLevel(logging.ERROR)
    logging.getLogger('system.intents_db').setLevel(logging.ERROR)
    logging.getLogger('system.scenarios').setLevel(logging.ERROR)
    logging.getLogger('system.config').setLevel(logging.ERROR)

    # GARDER logs importants (INFO level)
    logging.getLogger('system.robot_freeswitch').setLevel(logging.INFO)

    # Supprimer les logs Vosk C++ (rediriger stderr vers /dev/null temporairement)
    # On le fait pendant l'init seulement
    global vosk_stderr_backup
    vosk_stderr_backup = sys.stderr
    sys.stderr = open(os.devnull, 'w')

    print("✅ Logs configurés: mode ULTRA minimal + focus HANGUP")

def restore_stderr():
    """Restaure stderr après init Vosk"""
    import sys
    if 'vosk_stderr_backup' in globals():
        # Restaurer stderr sans fermer /dev/null (évite logging errors)
        sys.stderr = vosk_stderr_backup

setup_minimal_logging()

logger = logging.getLogger(__name__)


def main():
    """Lance un appel reel avec scenario dfdf.json"""

    print("\n" + "=" * 80)
    print("  TEST APPEL REEL - MiniBotPanel v3")
    print("=" * 80)

    # Configuration
    phone_number = "33743130341"  # Ton numero
    scenario_name = "scen_test"   # Scenario de test OPTION B

    print(f"\n📋 Configuration:")
    print(f"   Numero: {phone_number}")
    print(f"   Scenario: {scenario_name}.json")

    try:
        from system.robot_freeswitch import RobotFreeSWITCH
        from system.scenarios import ScenarioManager

        # Load scenario BEFORE robot init to get theme_file for warmup
        print("\n🔄 Chargement scenario pour detecter theme objections...")
        scenario_manager = ScenarioManager()
        try:
            scenario = scenario_manager.load_scenario(scenario_name)
            theme_file = scenario_manager.get_theme_file(scenario)
            print(f"✅ Scenario charge: theme_file = '{theme_file}'")
        except Exception as e:
            print(f"⚠️  Scenario non charge ({e}), utilisation theme general")
            theme_file = "objections_general"

        # Initialize robot (PRELOADING with scenario theme)
        print(f"\n🔄 Initialisation robot (PRELOADING services AI + {theme_file})...")
        start_time = time.time()

        robot = RobotFreeSWITCH(default_theme=theme_file)

        # Restaurer stderr après init (pour voir les vraies erreurs ensuite)
        restore_stderr()

        init_time = (time.time() - start_time) * 1000
        print(f"✅ Robot initialise en {init_time:.0f}ms")

        # Connect to FreeSWITCH
        print("\n🔄 Connexion a FreeSWITCH ESL...")
        if not robot.connect():
            print("❌ Echec connexion FreeSWITCH")
            print("   Verifier que FreeSWITCH est demarre")
            return 1

        print("✅ Connecte a FreeSWITCH")

        # Start robot event loop
        print("\n🔄 Demarrage boucle evenements robot...")
        robot.start()
        print("✅ Robot demarre")

        # Lance l'appel SORTANT
        print(f"\n📞 Lancement appel SORTANT vers {phone_number}...")
        call_uuid = robot.originate_call(phone_number, 0, scenario_name)

        if call_uuid:
            print(f"✅ Appel lance avec UUID: {call_uuid}")
            print("\n⏳ Conversation en cours...")
            print("=" * 80)
            print("\n📊 LOGS DETAILLES (avec latences):")
            print("-" * 80)

            # Wait for call to complete (120 seconds)
            time.sleep(120)

            print("\n" + "=" * 80)
            print("📊 STATISTIQUES APPEL")
            print("=" * 80)

            # Get call stats
            if call_uuid in robot.call_sessions:
                session = robot.call_sessions[call_uuid]
                print(f"\nSession UUID: {call_uuid}")
                print(f"Statut final: {session.get('final_status', 'N/A')}")
                print(f"Duree totale: {session.get('duration', 0):.1f}s")

                # Display latencies if available
                if 'latencies' in session:
                    print("\nLatences par phase:")
                    for phase, latency in session['latencies'].items():
                        print(f"   {phase}: {latency:.0f}ms")
        else:
            print("❌ Echec lancement appel")
            return 1

        # Stop robot
        print("\n\n🛑 Arret du robot...")
        robot.stop()
        print("✅ Robot arrete")

        return 0

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
