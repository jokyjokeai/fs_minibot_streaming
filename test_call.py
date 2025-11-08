#!/usr/bin/env python3
"""
Script de test pour lancer un appel simple
"""
import time
import threading
from system.robot_freeswitch_v2 import RobotFreeSwitchV2 as RobotFreeSWITCH

def main():
    print("🚀 Initialisation du robot...")
    robot = RobotFreeSWITCH()
    robot.connect()

    # Démarrer le robot dans un thread séparé
    print("🎬 Démarrage du robot en arrière-plan...")
    robot_thread = threading.Thread(target=robot.start, daemon=True)
    robot_thread.start()

    # Attendre que le robot soit bien démarré
    print("⏳ Attente démarrage complet (10 secondes)...")
    time.sleep(10)

    # Lancer l'appel
    print("📞 Lancement appel vers 33743130341...")
    call_uuid = robot.originate_call('33743130341', 0, 'dfdf')

    if call_uuid:
        print(f"✅ Appel lancé avec UUID: {call_uuid}")
    else:
        print("❌ Échec lancement appel")
        print("💡 Vérifier les logs dans logs/errors/system.robot_freeswitch_errors.log")

    # Attendre la fin de la conversation
    print("⏳ Conversation en cours (120 secondes)...")
    print("   Surveillez les logs: tail -f logs/misc/system.robot_freeswitch_20251106.log")
    time.sleep(120)

    print("🛑 Arrêt du robot...")
    robot.stop()
    print("✅ Terminé")

if __name__ == "__main__":
    main()
