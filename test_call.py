#!/usr/bin/env python3
"""
Script de test pour lancer un appel simple - VERSION V3 OPTIMISÉE

Utilise robot_freeswitch_v3.py avec:
- Barge-in simplifié (durée >= 2.5s)
- Transcription parallèle (latence < 500ms)
- États PLAYING_AUDIO / WAITING_RESPONSE séparés
- Pas de backchannel keywords (juste durée)
"""
import time
import threading
from system.robot_freeswitch_v3 import RobotFreeSwitchV3 as RobotFreeSWITCH

def main():
    print("="*60)
    print("🚀 TEST V3 OPTIMISÉ - Initialisation du robot...")
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
    print("\n⏳ V3 OPTIMISÉ Conversation en cours (120 secondes)...")
    print("   📊 Surveillez les logs V3:")
    print("   tail -f logs/misc/system.robot_freeswitch_v3_*.log")
    print("\n   🔍 Nouveaux logs à surveiller:")
    print("   - 'threshold: 2.5s' (nouveau seuil barge-in)")
    print("   - 'STATE: PLAYING_AUDIO' (état explicite)")
    print("   - 'STATE: WAITING_RESPONSE' (état explicite)")
    print("   - 'latency: XXXms' (latence transcription finale)")
    print()
    time.sleep(120)

    print("\n🛑 Arrêt du robot V3...")
    robot.stop()
    print("✅ V3 OPTIMISÉ Test terminé")
    print("="*60)

if __name__ == "__main__":
    main()
