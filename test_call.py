#!/usr/bin/env python3
"""
Script de test pour lancer un appel simple

Utilise RobotFreeSWITCH avec:
- Barge-in VAD (durée >= 2.5s)
- Transcription mode fichier + modèle Vosk large
- États PLAYING_AUDIO / WAITING_RESPONSE séparés
- Détection interruption naturelle
"""
import time
import threading
from system.robot_freeswitch import RobotFreeSWITCH

def main():
    print("="*60)
    print("🚀 TEST - Initialisation du robot...")
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
    print("\n⏳ Conversation en cours (120 secondes)...")
    print("   📊 Surveillez les logs:")
    print("   tail -f logs/misc/system.robot_freeswitch_*.log")
    print("\n   🔍 Logs à surveiller:")
    print("   - 'threshold: 2.5s' (seuil barge-in)")
    print("   - 'STATE: PLAYING_AUDIO' (état explicite)")
    print("   - 'STATE: WAITING_RESPONSE' (état explicite)")
    print("   - 'latency: XXXms' (latence transcription)")
    print()
    time.sleep(120)

    print("\n🛑 Arrêt du robot...")
    robot.stop()
    print("✅ Test terminé")
    print("="*60)

if __name__ == "__main__":
    main()
