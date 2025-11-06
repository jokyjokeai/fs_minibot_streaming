#!/usr/bin/env python3
"""
Test script for RobotFreeSWITCH V2
"""

import sys
import time
import threading

# Import V2
from system.robot_freeswitch_v2 import RobotFreeSwitchV2

def main():
    print("🚀 Initialisation du robot V2...")

    # Créer instance
    robot = RobotFreeSwitchV2()

    print("🎬 Démarrage du robot en arrière-plan...")

    # Démarrer robot
    if not robot.start():
        print("❌ Failed to start robot")
        return 1

    # Attendre démarrage complet
    print("⏳ Attente démarrage complet (10 secondes)...")
    time.sleep(10)

    # Lancer appel de test
    print(f"📞 Lancement appel vers 33743130341...")
    call_uuid = robot.originate_call('33743130341', 0, 'dfdf')

    if call_uuid:
        print(f"✅ Appel lancé avec UUID: {call_uuid}")

        # Attendre pendant conversation
        print("⏳ Conversation en cours (120 secondes)...")
        print("   Surveillez les logs: tail -f logs/misc/system.robot_freeswitch_v2_*.log")
        time.sleep(120)
    else:
        print("❌ Échec lancement appel")

    # Arrêter robot
    print("🛑 Arrêt du robot...")
    robot.stop()

    print("✅ Terminé")
    return 0

if __name__ == "__main__":
    sys.exit(main())
