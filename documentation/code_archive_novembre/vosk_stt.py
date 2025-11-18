"""
Vosk STT Service - MiniBotPanel v3

Service de transcription audio en texte (Speech-to-Text).
Adapté de live_asr_vad.py pour FreeSWITCH.

Technologie: Vosk (offline, français)

Fonctionnalités:
- Transcription fichier WAV
- Transcription streaming temps réel
- Support audio 8kHz et 16kHz
- Détection fin de parole
- Confiance par transcription

Utilisation:
    from system.services.vosk_stt import VoskSTT

    stt = VoskSTT()

    # Transcription fichier
    result = stt.transcribe_file("audio.wav")
    print(result["text"], result["confidence"])

    # Transcription streaming
    recognizer = stt.create_recognizer()
    for audio_chunk in audio_stream:
        if stt.accept_waveform(recognizer, audio_chunk):
            result = stt.get_result(recognizer)
            print(result["text"])
"""

import json
import time
import wave
from pathlib import Path
from typing import Optional, Dict, Any

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

# Import Vosk
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
    logger.info("✅ Vosk imported successfully")
except ImportError as e:
    VOSK_AVAILABLE = False
    logger.warning(f"⚠️ Vosk not available: {e}")
    # Mock classes pour éviter erreurs
    class Model:
        def __init__(self, path): pass
    class KaldiRecognizer:
        def __init__(self, model, rate): pass


class VoskSTT:
    """
    Service de transcription Vosk.
    Version simplifiée basée sur live_asr_vad.py
    """

    def __init__(self):
        """Initialise le service Vosk STT."""
        logger.info("Initializing VoskSTT...")

        self.model = None
        self.is_available = VOSK_AVAILABLE
        self.sample_rate = config.VOSK_SAMPLE_RATE

        if not self.is_available:
            logger.warning("🚫 VoskSTT not available - missing dependencies")
            return

        # Charger modèle
        if config.PRELOAD_MODELS:
            self._load_model()

        logger.info(f"{'✅' if self.is_available else '❌'} VoskSTT initialized")

    def _load_model(self):
        """Charge le modèle Vosk en mémoire."""
        try:
            model_path = Path(config.VOSK_MODEL_PATH)

            if not model_path.exists():
                logger.error(f"Vosk model not found: {model_path}")
                self.is_available = False
                return

            logger.info(f"🧠 Loading Vosk model from {model_path}")
            start_time = time.time()

            self.model = Model(str(model_path))

            load_time = time.time() - start_time
            logger.info(f"✅ Vosk model loaded in {load_time:.2f}s")

            # Test recognizer
            test_rec = KaldiRecognizer(self.model, self.sample_rate)
            test_rec.SetWords(True)
            logger.info("✅ Vosk test recognizer created successfully")

            self.is_available = True

        except Exception as e:
            logger.error(f"❌ Failed to load Vosk model: {e}")
            self.is_available = False

    def create_recognizer(self, sample_rate: int = None):
        """
        Crée un recognizer Vosk pour transcription streaming.

        Args:
            sample_rate: Fréquence échantillonnage (défaut: config)

        Returns:
            KaldiRecognizer instance
        """
        if not self.is_available or not self.model:
            logger.error("Vosk model not loaded")
            return None

        sample_rate = sample_rate or self.sample_rate

        try:
            recognizer = KaldiRecognizer(self.model, sample_rate)
            recognizer.SetWords(True)  # Activer timestamps mots
            return recognizer

        except Exception as e:
            logger.error(f"Failed to create recognizer: {e}")
            return None

    def accept_waveform(self, recognizer, audio_data: bytes) -> bool:
        """
        Envoie audio chunk au recognizer.

        Args:
            recognizer: KaldiRecognizer
            audio_data: Chunk audio (bytes)

        Returns:
            True si transcription complète disponible
        """
        if not recognizer:
            return False

        try:
            return recognizer.AcceptWaveform(audio_data)
        except Exception as e:
            logger.error(f"AcceptWaveform error: {e}")
            return False

    def get_result(self, recognizer) -> Dict[str, Any]:
        """
        Récupère résultat transcription finale.

        Args:
            recognizer: KaldiRecognizer

        Returns:
            Dict avec text, confidence, words
        """
        if not recognizer:
            return {"text": "", "confidence": 0.0}

        try:
            result = json.loads(recognizer.Result())
            return {
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0.0),
                "words": result.get("result", [])
            }
        except Exception as e:
            logger.error(f"Get result error: {e}")
            return {"text": "", "confidence": 0.0}

    def get_partial_result(self, recognizer) -> str:
        """
        Récupère résultat partiel (en cours).

        Args:
            recognizer: KaldiRecognizer

        Returns:
            Texte partiel
        """
        if not recognizer:
            return ""

        try:
            result = json.loads(recognizer.PartialResult())
            return result.get("partial", "")
        except Exception as e:
            logger.error(f"Get partial result error: {e}")
            return ""

    def transcribe_file(self, audio_file: str) -> Dict[str, Any]:
        """
        Transcrit un fichier audio complet.

        Args:
            audio_file: Chemin vers fichier WAV

        Returns:
            Dict avec text, confidence, duration
        """
        if not self.is_available or not self.model:
            return {"text": "", "confidence": 0.0, "error": "Vosk not available"}

        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                return {"text": "", "confidence": 0.0, "error": "File not found"}

            # Ouvrir fichier WAV
            wf = wave.open(str(audio_path), "rb")

            # Vérifier format
            if wf.getnchannels() != 1:
                wf.close()
                return {"text": "", "confidence": 0.0, "error": "Audio must be mono"}

            sample_rate = wf.getframerate()
            if sample_rate not in [8000, 16000, 32000, 48000]:
                wf.close()
                return {"text": "", "confidence": 0.0, "error": f"Unsupported sample rate: {sample_rate}"}

            # Créer recognizer
            recognizer = self.create_recognizer(sample_rate)
            if not recognizer:
                wf.close()
                return {"text": "", "confidence": 0.0, "error": "Failed to create recognizer"}

            # Traiter par chunks
            chunk_size = 4000
            full_text = []

            start_time = time.time()

            while True:
                data = wf.readframes(chunk_size)
                if len(data) == 0:
                    break

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        full_text.append(text)

            # Résultat final
            final_result = json.loads(recognizer.FinalResult())
            text = final_result.get("text", "")
            if text:
                full_text.append(text)

            wf.close()

            duration = time.time() - start_time
            transcription = " ".join(full_text).strip()

            logger.info(f"Transcribed {audio_path.name} in {duration:.2f}s: {transcription[:100]}")

            return {
                "text": transcription,
                "confidence": final_result.get("confidence", 0.0),
                "duration": duration,
                "audio_duration": wf.getnframes() / sample_rate if wf else 0
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return {"text": "", "confidence": 0.0, "error": str(e)}

    def cleanup(self, recognizer):
        """
        Nettoie un recognizer.

        Args:
            recognizer: KaldiRecognizer à nettoyer
        """
        # Vosk n'a pas besoin de cleanup explicite
        pass
