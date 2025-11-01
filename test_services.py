#!/usr/bin/env python3
"""
Test Services - MiniBotPanel v3

Teste la disponibilité et le fonctionnement de tous les services IA.

Services testés:
- Vosk STT (Speech-to-Text)
- Ollama NLP (Intent + Sentiment)
- Coqui TTS (Text-to-Speech)
- AMD Service (Answering Machine Detection)
- FreeSWITCH ESL (Event Socket Library)

Utilisation:
    python test_services.py
    python test_services.py --service vosk
    python test_services.py --verbose
"""

import argparse
import logging
from pathlib import Path

from system.config import config
from system.services.vosk_stt import VoskSTT
from system.services.ollama_nlp import OllamaNLP
from system.services.coqui_tts import CoquiTTS
from system.services.amd_service import AMDService

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_vosk() -> bool:
    """
    Teste le service Vosk STT.

    Returns:
        True si disponible, False sinon
    """
    logger.info("\n🎤 TEST VOSK STT")
    logger.info("=" * 60)

    try:
        stt = VoskSTT()

        if stt.is_available:
            logger.info(f"✅ Vosk disponible")
            logger.info(f"📁 Modèle: {config.VOSK_MODEL_PATH}")
            logger.info(f"🔊 Sample rate: {config.VOSK_SAMPLE_RATE} Hz")
            return True
        else:
            logger.error("❌ Vosk non disponible")
            logger.info(f"💡 Vérifiez que le modèle existe: {config.VOSK_MODEL_PATH}")
            return False

    except Exception as e:
        logger.error(f"❌ Erreur Vosk: {e}")
        return False


def test_ollama() -> bool:
    """
    Teste le service Ollama NLP.

    Returns:
        True si disponible, False sinon
    """
    logger.info("\n🧠 TEST OLLAMA NLP")
    logger.info("=" * 60)

    try:
        nlp = OllamaNLP()

        if nlp.is_available:
            logger.info(f"✅ Ollama disponible")
            logger.info(f"🌐 URL: {config.OLLAMA_URL}")
            logger.info(f"🤖 Modèle: {config.OLLAMA_MODEL}")

            # Test analyse
            test_text = "Oui, je suis intéressé"
            logger.info(f"\n📝 Test analyse: '{test_text}'")
            result = nlp.analyze(test_text)
            logger.info(f"🎯 Intent: {result['intent']} (confidence: {result['confidence']:.2f})")
            logger.info(f"😊 Sentiment: {result['sentiment']}")

            return True
        else:
            logger.error("❌ Ollama non disponible")
            logger.info(f"💡 Démarrez Ollama: ollama serve")
            logger.info(f"💡 Téléchargez le modèle: ollama pull {config.OLLAMA_MODEL}")
            return False

    except Exception as e:
        logger.error(f"❌ Erreur Ollama: {e}")
        return False


def test_coqui() -> bool:
    """
    Teste le service Coqui TTS.

    Returns:
        True si disponible, False sinon
    """
    logger.info("\n🗣️ TEST COQUI TTS")
    logger.info("=" * 60)

    try:
        tts = CoquiTTS()

        if tts.is_available:
            logger.info(f"✅ Coqui disponible")
            logger.info(f"🤖 Modèle: {config.COQUI_MODEL}")
            logger.info(f"🎮 GPU: {'Activé' if config.COQUI_USE_GPU else 'Désactivé'}")

            # Test génération
            test_text = "Bonjour, ceci est un test de synthèse vocale."
            logger.info(f"\n📝 Test génération: '{test_text}'")

            output_path = config.BASE_DIR / "test_tts.wav"
            audio_path = tts.generate(
                text=test_text,
                voice_name="test",
                output_path=str(output_path)
            )

            if audio_path:
                logger.info(f"✅ Audio généré: {audio_path}")
                logger.info(f"💡 Écoutez le fichier pour valider la qualité")
            else:
                logger.warning("⚠️ Génération TTS échouée (mais service disponible)")

            return True
        else:
            logger.error("❌ Coqui non disponible")
            logger.info(f"💡 Installez Coqui: pip install TTS")
            return False

    except Exception as e:
        logger.error(f"❌ Erreur Coqui: {e}")
        return False


def test_amd() -> bool:
    """
    Teste le service AMD.

    Returns:
        True si disponible, False sinon
    """
    logger.info("\n📞 TEST AMD SERVICE")
    logger.info("=" * 60)

    try:
        amd = AMDService()

        logger.info(f"✅ AMD Service initialisé")
        logger.info(f"🔀 Dual Layer: {'Activé' if config.AMD_DUAL_LAYER else 'Désactivé'}")
        logger.info(f"⏱️ Max greeting time: {config.AMD_MAX_GREETING_TIME}s")
        logger.info(f"📏 Max words: {config.AMD_MAX_WORDS}")

        return True

    except Exception as e:
        logger.error(f"❌ Erreur AMD: {e}")
        return False


def test_freeswitch() -> bool:
    """
    Teste la connexion FreeSWITCH ESL.

    Returns:
        True si connecté, False sinon
    """
    logger.info("\n📡 TEST FREESWITCH ESL")
    logger.info("=" * 60)

    try:
        # TODO: Tester connexion ESL
        logger.info(f"🌐 Host: {config.FREESWITCH_ESL_HOST}:{config.FREESWITCH_ESL_PORT}")
        logger.info(f"⚠️ Test connexion ESL pas encore implémenté")

        return False

    except Exception as e:
        logger.error(f"❌ Erreur FreeSWITCH: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Tester les services IA")
    parser.add_argument(
        "--service",
        choices=["vosk", "ollama", "coqui", "amd", "freeswitch"],
        help="Tester un service spécifique"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mode verbeux"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("🧪 TEST SERVICES IA - MiniBotPanel v3")
    logger.info("=" * 60)

    results = {}

    # Tester service spécifique ou tous
    if args.service:
        if args.service == "vosk":
            results["Vosk STT"] = test_vosk()
        elif args.service == "ollama":
            results["Ollama NLP"] = test_ollama()
        elif args.service == "coqui":
            results["Coqui TTS"] = test_coqui()
        elif args.service == "amd":
            results["AMD Service"] = test_amd()
        elif args.service == "freeswitch":
            results["FreeSWITCH ESL"] = test_freeswitch()
    else:
        # Tester tous les services
        results["Vosk STT"] = test_vosk()
        results["Ollama NLP"] = test_ollama()
        results["Coqui TTS"] = test_coqui()
        results["AMD Service"] = test_amd()
        results["FreeSWITCH ESL"] = test_freeswitch()

    # Résumé
    logger.info("\n" + "=" * 60)
    logger.info("📊 RÉSUMÉ DES TESTS")
    logger.info("=" * 60)

    for service, status in results.items():
        icon = "✅" if status else "❌"
        logger.info(f"{icon} {service}: {'OK' if status else 'ERREUR'}")

    success_count = sum(results.values())
    total_count = len(results)

    logger.info("=" * 60)
    logger.info(f"🎯 {success_count}/{total_count} services opérationnels")

    if success_count == total_count:
        logger.info("\n🎉 Tous les services sont opérationnels!")
    else:
        logger.warning(f"\n⚠️ {total_count - success_count} service(s) non opérationnel(s)")


if __name__ == "__main__":
    main()
