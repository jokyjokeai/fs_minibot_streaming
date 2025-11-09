#!/usr/bin/env python3
"""
Script de test pour lancer un appel simple - VERSION V3

Utilise robot_freeswitch_v3.py avec:
- Barge-in simplifié (durée >= 2s)
- Pas de crash Vosk (reset_recognizer supprimé)
- Pas de race conditions (durée dans événements)
- Logs debug détaillés
"""
import time
import threading
from system.robot_freeswitch_v3 import RobotFreeSwitchV3 as RobotFreeSWITCH

def main():
    print("="*60)
    print("🚀 TEST V3 - Initialisation du robot...")
    print("="*60)
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
    print("\n⏳ V3 Conversation en cours (120 secondes)...")
    print("   📊 Surveillez les logs V3:")
    print("   tail -f logs/misc/system.robot_freeswitch_*.log")
    print("\n   🔍 Cherchez les logs V3 avec:")
    print("   grep 'V3' logs/misc/system.robot_freeswitch_*.log")
    print()
    time.sleep(120)

    print("\n🛑 Arrêt du robot V3...")
    robot.stop()
    print("✅ V3 Test terminé")
    print("="*60)

if __name__ == "__main__":
    main()
