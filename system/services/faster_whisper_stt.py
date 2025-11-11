"""
Faster-Whisper STT Service - MiniBotPanel v3

Service de transcription audio optimisé GPU avec Faster-Whisper.
Drop-in replacement pour VoskSTT avec performance 3-5x supérieure.

Technologie: Faster-Whisper (CTranslate2 optimized OpenAI Whisper)

Fonctionnalités:
- Transcription fichier WAV (MONO/STEREO)
- Support GPU CUDA (RTX 4090 optimisé)
- Fallback intelligent CPU
- Support audio 8kHz et 16kHz téléphonie
- Extraction automatique canal gauche (stereo)
- API compatible VoskSTT (drop-in replacement)

Avantages vs Vosk:
- 3-5x plus rapide sur GPU (0.3-0.5s vs 1.5s)
- Meilleure qualité transcription
- GPU accelerated (vs Vosk CPU-only)
- Modèles actifs (OpenAI Whisper)
- Meilleur gestion accents/dialectes

Utilisation:
    from system.services.faster_whisper_stt import FasterWhisperSTT

    stt = FasterWhisperSTT(
        model_name="base",  # tiny, base, small, medium
        device="cuda",      # cuda, cpu, auto
        compute_type="float16"  # float16, int8, auto
    )

    # Transcription fichier (même API que VoskSTT!)
    result = stt.transcribe_file("audio.wav")
    print(result["text"], result["confidence"])
"""

import json
import time
import wave
import struct
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

# Import Faster-Whisper avec gestion erreur
try:
    from faster_whisper import WhisperModel
    import torch
    FASTER_WHISPER_AVAILABLE = True
    logger.info("✅ Faster-Whisper imported successfully")
except ImportError as e:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning(f"⚠️ Faster-Whisper not available: {e}")
    # Mock class pour éviter erreurs
    class WhisperModel:
        def __init__(self, *args, **kwargs): pass


class FasterWhisperSTT:
    """
    Service de transcription Faster-Whisper.
    API compatible VoskSTT pour drop-in replacement.
    """

    @staticmethod
    def _extract_left_channel(stereo_wav_path: str, output_wav_path: str) -> bool:
        """
        Extrait le canal gauche (client) d'un fichier WAV stereo.

        Args:
            stereo_wav_path: Chemin fichier WAV stereo source
            output_wav_path: Chemin fichier WAV mono destination

        Returns:
            True si succès, False sinon
        """
        try:
            # Lire WAV stereo
            with wave.open(stereo_wav_path, 'rb') as wf_in:
                if wf_in.getnchannels() != 2:
                    logger.warning(f"File is not stereo ({wf_in.getnchannels()} channels), skipping extraction")
                    return False

                params = wf_in.getparams()
                frames = wf_in.readframes(wf_in.getnframes())

                # Convertir bytes → array int16
                num_samples = len(frames) // 2
                stereo_samples = struct.unpack(f'<{num_samples}h', frames)

                # Extraire canal gauche (indices pairs: 0,2,4,6...)
                left_samples = stereo_samples[::2]

                # Reconvertir → bytes
                left_frames = struct.pack(f'<{len(left_samples)}h', *left_samples)

            # Écrire WAV mono
            with wave.open(output_wav_path, 'wb') as wf_out:
                wf_out.setnchannels(1)  # MONO
                wf_out.setsampwidth(params.sampwidth)
                wf_out.setframerate(params.framerate)
                wf_out.writeframes(left_frames)

            logger.debug(f"✅ Extracted left channel: {stereo_wav_path} → {output_wav_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Error extracting left channel: {e}")
            return False

    def __init__(
        self,
        model_name: str = "base",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        """
        Initialise le service Faster-Whisper STT.

        Args:
            model_name: Taille modèle (tiny, base, small, medium, large-v2, large-v3)
            device: Device (cuda, cpu, auto)
            compute_type: Type calcul (float16, int8, auto)
        """
        logger.info("Initializing FasterWhisperSTT...")

        self.model = None
        self.is_available = FASTER_WHISPER_AVAILABLE
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

        if not self.is_available:
            logger.warning("🚫 FasterWhisperSTT not available - missing dependencies")
            logger.warning("💡 Install with: pip install faster-whisper")
            return

        # Auto-detect device et compute_type
        self._auto_configure()

        # Charger modèle
        self._load_model()

        logger.info(f"{'✅' if self.is_available else '❌'} FasterWhisperSTT initialized")

    def _auto_configure(self):
        """Auto-détecte meilleur device et compute_type."""
        try:
            import torch

            # Auto-detect device
            if self.device == "auto":
                if torch.cuda.is_available():
                    self.device = "cuda"
                    logger.info(f"🎮 GPU detected: {torch.cuda.get_device_name(0)}")
                    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    logger.info(f"💾 VRAM available: {vram_gb:.1f} GB")
                else:
                    self.device = "cpu"
                    logger.info("💻 No GPU detected, using CPU")

            # Auto-detect compute_type
            if self.compute_type == "auto":
                if self.device == "cuda":
                    # RTX 4090/3090/A100 → float16 optimal
                    # Older GPUs → int8 better
                    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
                    if any(x in gpu_name for x in ["4090", "4080", "3090", "A100", "A6000"]):
                        self.compute_type = "float16"
                        logger.info("⚙️ Compute type: float16 (optimal for modern GPU)")
                    else:
                        self.compute_type = "int8"
                        logger.info("⚙️ Compute type: int8 (good balance)")
                else:
                    self.compute_type = "int8"
                    logger.info("⚙️ Compute type: int8 (CPU optimized)")

        except Exception as e:
            logger.warning(f"⚠️ Auto-config error: {e}, using defaults")
            self.device = "cpu"
            self.compute_type = "int8"

    def _load_model(self):
        """Charge le modèle Faster-Whisper en mémoire."""
        try:
            logger.info(f"🧠 Loading Faster-Whisper model: {self.model_name}")
            logger.info(f"   Device: {self.device} | Compute: {self.compute_type}")
            start_time = time.time()

            # Charger modèle avec fallback intelligent
            try:
                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=None,  # Default cache
                    local_files_only=False  # Auto-download si besoin
                )
                load_time = time.time() - start_time
                logger.info(f"✅ Faster-Whisper model loaded in {load_time:.2f}s")

            except Exception as e:
                logger.warning(f"⚠️ Failed to load with {self.compute_type}, trying fallback...")

                # Fallback 1: Si float16 fail, essayer int8
                if self.compute_type == "float16":
                    logger.info("🔄 Trying int8 compute type...")
                    self.compute_type = "int8"
                    self.model = WhisperModel(
                        self.model_name,
                        device=self.device,
                        compute_type=self.compute_type
                    )
                    logger.info(f"✅ Model loaded with int8 fallback")

                # Fallback 2: Si CUDA fail, essayer CPU
                elif self.device == "cuda":
                    logger.info("🔄 CUDA failed, falling back to CPU...")
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self.model = WhisperModel(
                        self.model_name,
                        device=self.device,
                        compute_type=self.compute_type
                    )
                    logger.info(f"✅ Model loaded on CPU (fallback)")
                else:
                    raise e

            self.is_available = True

        except Exception as e:
            logger.error(f"❌ Failed to load Faster-Whisper model: {e}")
            self.is_available = False

    def transcribe_file(self, audio_file: str) -> Dict[str, Any]:
        """
        Transcrit un fichier audio complet.

        Compatible API VoskSTT pour drop-in replacement!

        Supporte MONO et STEREO (extrait automatiquement canal gauche si stereo)

        Args:
            audio_file: Chemin vers fichier WAV

        Returns:
            Dict avec text, confidence, duration (même format que VoskSTT!)
        """
        if not self.is_available or not self.model:
            return {"text": "", "confidence": 0.0, "error": "Faster-Whisper not available"}

        temp_file = None  # Initialize to None to avoid UnboundLocalError in except block

        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                return {"text": "", "confidence": 0.0, "error": "File not found"}

            start_time = time.time()

            # Vérifier format audio avec retry (FreeSWITCH peut prendre du temps pour finaliser header WAV)
            num_channels = None
            sample_rate = None
            max_retries = 2  # Réduit de 3→2 pour réactivité (0.5s + 1.0s = 1.5s max au lieu de 3.0s)
            retry_delays = [0.5, 1.0]  # Progressive backoff

            for retry in range(max_retries):
                try:
                    wf = wave.open(str(audio_path), "rb")
                    num_channels = wf.getnchannels()
                    sample_rate = wf.getframerate()
                    wf.close()
                    break  # Success
                except wave.Error as e:
                    if retry < max_retries - 1:
                        delay = retry_delays[retry]
                        logger.warning(f"WAV header not ready (attempt {retry + 1}/{max_retries}), waiting {delay}s: {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"WAV header still invalid after {max_retries} retries ({sum(retry_delays)}s total wait): {e}")
                        raise

            if num_channels is None or sample_rate is None:
                return {"text": "", "confidence": 0.0, "error": "Failed to read WAV header"}

            # Log info audio
            logger.debug(f"Audio: {num_channels}ch, {sample_rate}Hz, {audio_path.name}")

            # Si STEREO: extraire canal gauche (client) AVANT transcription
            # Fix critical bug: Faster-Whisper moyenne les canaux par défaut → transcrit robot + client
            # On doit extraire SEULEMENT le canal gauche (client)
            transcribe_path = audio_path
            temp_file = None

            if num_channels == 2:
                extract_start = time.time()
                logger.info(f"Stereo audio detected → Extracting left channel (client)")

                # Créer fichier temporaire pour canal gauche
                temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                temp_path = temp_file.name
                temp_file.close()

                # Extraire canal gauche
                if self._extract_left_channel(str(audio_path), temp_path):
                    transcribe_path = Path(temp_path)
                    extract_time = time.time() - extract_start
                    logger.info(f"⏱️  PERF: Left channel extraction: {extract_time:.3f}s")
                    logger.debug(f"Using extracted left channel: {temp_path}")
                else:
                    logger.warning("Failed to extract left channel, using original stereo file")

            # Transcription avec Faster-Whisper (sur fichier MONO maintenant!)
            whisper_start = time.time()
            segments, info = self.model.transcribe(
                str(transcribe_path),
                language="fr",  # Force français
                beam_size=5,    # Default beam search
                vad_filter=False,  # Pas de VAD (on a déjà géré avec FreeSWITCH)
                without_timestamps=False,  # Timestamps utiles pour confidence
                word_timestamps=False  # Pas besoin timestamps mots
            )

            # Collecter segments
            full_text = []
            total_confidence = 0.0
            segment_count = 0

            for segment in segments:
                full_text.append(segment.text)
                # Whisper n'a pas de confidence par défaut, on utilise avg_logprob
                # avg_logprob range: -inf à 0 (0 = parfait)
                # On convertit en 0-1: confidence ≈ exp(avg_logprob)
                confidence = min(1.0, max(0.0, 1.0 + segment.avg_logprob / 5.0))
                total_confidence += confidence
                segment_count += 1

            whisper_time = time.time() - whisper_start
            transcription_time = time.time() - start_time
            transcription = " ".join(full_text).strip()

            logger.info(f"⏱️  PERF: Whisper model inference: {whisper_time:.3f}s (audio: {info.duration:.2f}s, RTF: {whisper_time/info.duration:.2f}x)")

            # Calculer confidence moyenne
            avg_confidence = total_confidence / segment_count if segment_count > 0 else 0.0

            # Log résultat
            logger.info(f"Transcribed {audio_path.name} in {transcription_time:.2f}s: {transcription[:100]}")
            logger.debug(f"Confidence: {avg_confidence:.2f} | Language: {info.language} (prob: {info.language_probability:.2f})")

            # Cleanup fichier temporaire si créé
            if temp_file:
                try:
                    import os
                    os.unlink(transcribe_path)
                    logger.debug(f"Cleaned up temp file: {transcribe_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

            return {
                "text": transcription,
                "confidence": avg_confidence,
                "duration": transcription_time,
                "audio_duration": info.duration,
                "language": info.language,
                "language_probability": info.language_probability
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)

            # Cleanup fichier temporaire en cas d'erreur
            if temp_file:
                try:
                    import os
                    os.unlink(transcribe_path)
                except:
                    pass

            return {"text": "", "confidence": 0.0, "error": str(e)}

    def cleanup(self):
        """
        Nettoie les ressources.

        Faster-Whisper gère automatiquement le cleanup via garbage collection.
        """
        pass
