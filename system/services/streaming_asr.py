"""
Streaming ASR Service - MiniBotPanel v3

Service de transcription audio temps réel avec détection d'activité vocale (VAD).
Adapté de live_asr_vad.py pour FreeSWITCH.

Architecture:
- Serveur WebSocket qui reçoit audio depuis FreeSWITCH
- WebRTC VAD pour détection parole/silence
- Vosk ASR pour transcription streaming
- Callbacks pour barge-in et IA Freestyle

Utilisation:
    from system.services.streaming_asr import StreamingASR

    asr = StreamingASR()

    # Démarrer serveur
    await asr.start_server()

    # Register callback pour un call
    asr.register_callback(call_uuid, callback_function)
"""

import asyncio
import json
import time
import struct
import numpy as np
from typing import Dict, Optional, Any, Callable
from pathlib import Path

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# NoiseReduce import désactivé (non utilisé - enable_noisereduce = False)
# try:
#     import noisereduce as nr
#     NOISEREDUCE_AVAILABLE = True
# except ImportError:
#     NOISEREDUCE_AVAILABLE = False
NOISEREDUCE_AVAILABLE = False  # Forcé à False

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)


class StreamingASR:
    """
    Service de transcription streaming avec VAD pour FreeSWITCH.
    Gère le barge-in et la détection de silence.
    """

    def __init__(self):
        """Initialise le service streaming ASR"""
        logger.info("Initializing StreamingASR...")

        self.is_available = WEBSOCKETS_AVAILABLE and VAD_AVAILABLE and VOSK_AVAILABLE

        if not self.is_available:
            missing = []
            if not WEBSOCKETS_AVAILABLE:
                missing.append("websockets")
            if not VAD_AVAILABLE:
                missing.append("webrtcvad")
            if not VOSK_AVAILABLE:
                missing.append("vosk")
            logger.warning(f"🚫 StreamingASR not available - missing: {', '.join(missing)}")
            return

        # Configuration VAD
        self.vad = webrtcvad.Vad(2)  # Mode 2 = balance qualité/réactivité
        self.sample_rate = config.VOSK_SAMPLE_RATE  # 16000 Hz
        self.frame_duration_ms = 30  # 30ms frames
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)

        # Seuils (lus depuis config pour cohérence)
        self.silence_threshold = config.VAD_SILENCE_THRESHOLD_MS / 1000.0  # 500ms → 0.5s (optimisé bruits)
        self.speech_start_threshold = config.VAD_SPEECH_START_THRESHOLD_MS / 1000.0  # 500ms → 0.5s

        # Audio filters DÉSACTIVÉS (causaient des problèmes de transcription)
        # Les filtres high-pass et noise gate ont été supprimés
        logger.info("ℹ️ Audio filters disabled (raw audio to Vosk)")

        # Modèle Vosk
        self.model = None
        self.recognizers = {}  # {call_uuid: KaldiRecognizer}

        # État streams
        self.active_streams = {}  # {call_uuid: stream_info}
        self.callbacks = {}  # {call_uuid: callback_function}

        # Serveur WebSocket
        self.websocket_server = None
        self.server_task = None

        # Statistiques
        self.stats = {
            "active_streams": 0,
            "total_frames_processed": 0,
            "speech_frames": 0,
            "silence_frames": 0,
            "transcriptions": 0,
            "avg_latency_ms": 0.0
        }

        # Charger modèle Vosk
        self._load_vosk_model()

        logger.info(f"{'✅' if self.is_available else '❌'} StreamingASR initialized")

    def _load_vosk_model(self):
        """Charge le modèle Vosk"""
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

        except Exception as e:
            logger.error(f"❌ Failed to load Vosk model: {e}")
            self.is_available = False

    async def start_server(self, host: str = "127.0.0.1", port: int = 8080):
        """
        Démarre le serveur WebSocket pour recevoir audio depuis FreeSWITCH

        Args:
            host: Host à écouter
            port: Port à écouter
        """
        if not self.is_available:
            logger.error("🚫 Cannot start server - dependencies not available")
            return

        try:
            logger.info(f"🌐 Starting WebSocket server on {host}:{port}")

            self.websocket_server = await websockets.serve(
                self._handle_websocket_connection,
                host,
                port,
                max_size=None,  # Pas de limite pour audio
                ping_interval=None  # Désactiver ping pour performance
            )

            logger.info("✅ WebSocket server started successfully")
            logger.info("   Waiting for audio streams from FreeSWITCH...")

            # Garder le serveur actif
            await self.websocket_server.wait_closed()

        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}")
            raise

    async def _handle_websocket_connection(self, websocket):
        """Gère une connexion WebSocket depuis FreeSWITCH"""
        call_uuid = None
        try:
            # Extraire call_uuid du path: /stream/{UUID}
            # websockets 15+ utilise websocket.request.path
            path = websocket.request.path if hasattr(websocket, 'request') else websocket.path
            call_uuid = path.split('/')[-1]
            logger.info(f"📞 New audio stream for call: {call_uuid[:8]}")

            # Initialiser stream
            self._initialize_stream(call_uuid)

            # Buffer pour accumuler frames
            audio_buffer = b''

            async for message in websocket:
                if isinstance(message, bytes):
                    # Audio brut (SLIN16, 16kHz, mono, 16-bit)
                    audio_buffer += message

                    # Traiter par frames de 30ms
                    bytes_per_frame = self.frame_size * 2  # 2 bytes par sample

                    while len(audio_buffer) >= bytes_per_frame:
                        frame_bytes = audio_buffer[:bytes_per_frame]
                        audio_buffer = audio_buffer[bytes_per_frame:]

                        # Traitement temps réel
                        await self._process_audio_frame(call_uuid, frame_bytes)

        except websockets.exceptions.ConnectionClosed:
            if call_uuid:
                logger.info(f"📞 Audio stream closed for call: {call_uuid[:8]}")
        except Exception as e:
            if call_uuid:
                logger.error(f"❌ Error handling audio stream for {call_uuid[:8]}: {e}", exc_info=True)
            else:
                logger.error(f"❌ Error handling audio stream: {e}", exc_info=True)
        finally:
            if call_uuid:
                self._cleanup_stream(call_uuid)

    def _initialize_stream(self, call_uuid: str):
        """Initialise un stream pour un appel"""
        # Créer recognizer Vosk
        if self.model:
            recognizer = KaldiRecognizer(self.model, self.sample_rate)
            recognizer.SetWords(True)
            self.recognizers[call_uuid] = recognizer
            logger.info(f"🎤 [{call_uuid[:8]}] NEW Vosk recognizer created")
        else:
            logger.error(f"❌ [{call_uuid[:8]}] No Vosk model loaded!")

        self.active_streams[call_uuid] = {
            "start_time": time.time(),
            "frame_count": 0,
            "speech_frames": 0,
            "silence_frames": 0,
            "current_speech_duration": 0.0,
            "current_silence_duration": 0.0,
            "in_speech": False,
            "partial_transcription": "",
            "final_transcription": "",
            "last_speech_time": 0.0,
            "audio_warmup_done": False,  # Flag pour ignorer silence initial (RMS=0)
            "first_audio_time": None,  # Timestamp du premier audio réel reçu
            # Energy gate adaptatif
            "noise_floor_rms": None,  # Plancher de bruit calibré
            "calibration_samples": [],  # RMS samples pendant calibration
            "is_calibrating": False  # Mode calibration actif
        }

        # Vérifier état des autres structures
        num_callbacks = len(self.callbacks)
        num_recognizers = len(self.recognizers)
        num_streams = len(self.active_streams)

        self.stats["active_streams"] += 1
        logger.info(
            f"✅ [{call_uuid[:8]}] Stream initialized: "
            f"callbacks={num_callbacks}, recognizers={num_recognizers}, streams={num_streams}"
        )

    async def _process_audio_frame(self, call_uuid: str, frame_bytes: bytes):
        """Traite une frame audio en temps réel"""
        if call_uuid not in self.active_streams:
            return

        start_time = time.time()
        stream_info = self.active_streams[call_uuid]
        recognizer = self.recognizers.get(call_uuid)

        if not recognizer:
            return

        try:
            # VAD - Détection activité vocale (sur audio ORIGINAL, non filtré)
            # WebRTC VAD a été entraîné sur audio complet (toutes fréquences)
            is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)

            # Mise à jour statistiques
            stream_info["frame_count"] += 1
            self.stats["total_frames_processed"] += 1

            frame_duration_s = self.frame_duration_ms / 1000.0

            # === AUDIO WARMUP: Ignorer silence initial (frames avec RMS≈0) ===
            # FreeSWITCH peut envoyer des frames vides au début du stream
            # On ne compte le silence qu'après avoir reçu du vrai audio
            import numpy as np
            audio_samples_check = np.frombuffer(frame_bytes, dtype=np.int16)
            frame_rms = np.sqrt(np.mean(audio_samples_check.astype(np.float32) ** 2))

            # === ENERGY GATE ADAPTATIF ===
            # Pendant calibration: collecter les samples RMS
            if stream_info["is_calibrating"]:
                stream_info["calibration_samples"].append(frame_rms)

            # Après calibration: appliquer le filtre de bruit
            noise_floor = stream_info.get("noise_floor_rms")
            if noise_floor and frame_rms < noise_floor:
                # Frame sous le seuil de bruit → forcer silence
                is_speech = False

            # Seuil très bas - juste pour détecter les frames totalement vides (RMS=0)
            # L'audio téléphonique peut avoir un RMS de 8-15 même en silence
            MIN_AUDIO_RMS = 5
            MAX_WARMUP_FRAMES = 30  # Max 30 frames (~0.9s) de warmup

            if not stream_info["audio_warmup_done"]:
                # Terminer warmup si : audio réel OU VAD détecte parole OU timeout warmup
                if frame_rms > MIN_AUDIO_RMS or is_speech or stream_info["frame_count"] >= MAX_WARMUP_FRAMES:
                    stream_info["audio_warmup_done"] = True
                    stream_info["first_audio_time"] = time.time()
                    warmup_frames = stream_info["frame_count"]
                    reason = "RMS" if frame_rms > MIN_AUDIO_RMS else ("VAD" if is_speech else "TIMEOUT")
                    logger.info(
                        f"🔊 [{call_uuid[:8]}] Audio warmup complete after {warmup_frames} frames "
                        f"(RMS={frame_rms:.0f}, is_speech={is_speech}, reason={reason})"
                    )

            if is_speech:
                # Parole détectée
                stream_info["speech_frames"] += 1
                stream_info["current_speech_duration"] += frame_duration_s
                stream_info["current_silence_duration"] = 0.0
                stream_info["last_speech_time"] = time.time()
                self.stats["speech_frames"] += 1

                if not stream_info["in_speech"]:
                    # Début de parole
                    if stream_info["current_speech_duration"] >= self.speech_start_threshold:
                        stream_info["in_speech"] = True
                        logger.debug(f"🗣️ Speech START detected: {call_uuid[:8]}")
                        await self._notify_speech_start(call_uuid)

            else:
                # Silence détecté
                stream_info["silence_frames"] += 1
                stream_info["current_speech_duration"] = max(0, stream_info["current_speech_duration"] - frame_duration_s)
                self.stats["silence_frames"] += 1

                # NE PAS compter le silence pendant le warmup (évite faux positifs)
                if stream_info["audio_warmup_done"]:
                    stream_info["current_silence_duration"] += frame_duration_s
                else:
                    # Pendant warmup, reset silence pour éviter accumulation
                    stream_info["current_silence_duration"] = 0.0

                if stream_info["in_speech"]:
                    # Vérifier si fin de parole
                    if stream_info["current_silence_duration"] >= self.silence_threshold:
                        stream_info["in_speech"] = False
                        logger.info(f"🤐 Speech END detected: {call_uuid[:8]} (silence: {stream_info['current_silence_duration']:.1f}s, threshold: {self.silence_threshold}s)")
                        await self._notify_speech_end(call_uuid)
                    else:
                        # Log progression du silence
                        if stream_info["current_silence_duration"] % 0.5 < frame_duration_s:  # Log tous les 0.5s
                            logger.debug(f"⏱️ Silence accumulating: {call_uuid[:8]} ({stream_info['current_silence_duration']:.1f}s / {self.silence_threshold}s)")
                else:
                    # NOUVEAU: Détecter paroles courtes (< 500ms) qui ne triggent pas in_speech
                    # Si on a reçu une transcription FINAL et qu'on a du silence suffisant
                    if stream_info.get("final_transcription") and stream_info["current_silence_duration"] >= self.silence_threshold:
                        logger.info(
                            f"🤐 Speech END detected (short utterance): {call_uuid[:8]} "
                            f"(transcription: '{stream_info['final_transcription']}')"
                        )
                        await self._notify_speech_end(call_uuid)
                        stream_info["final_transcription"] = None  # Reset pour éviter double détection

            # Audio brut envoyé directement à Vosk (filtres désactivés)
            # Utiliser les valeurs RMS déjà calculées dans le warmup check
            audio_rms = frame_rms
            audio_max = np.max(np.abs(audio_samples_check))

            # Log toutes les 50 frames (~1.5s) pour voir l'état
            if stream_info["frame_count"] % 50 == 0:
                warmup_status = "✅" if stream_info["audio_warmup_done"] else "⏳WARMUP"
                logger.info(
                    f"🔊 [{call_uuid[:8]}] Audio stats: frame={stream_info['frame_count']}, "
                    f"RMS={audio_rms:.0f}, MAX={audio_max}, "
                    f"in_speech={stream_info['in_speech']}, "
                    f"silence_dur={stream_info['current_silence_duration']:.1f}s, "
                    f"warmup={warmup_status}"
                )

            # ASR - Transcription streaming avec boost audio
            # Boost pour améliorer la qualité de transcription Vosk
            AUDIO_BOOST_FACTOR = 3.3  # Multiplier le volume par 3.3

            # Appliquer boost avec clipping pour éviter overflow int16
            boosted_samples = np.clip(
                audio_samples_check.astype(np.float32) * AUDIO_BOOST_FACTOR,
                -32768, 32767
            ).astype(np.int16)
            boosted_frame = boosted_samples.tobytes()

            if recognizer.AcceptWaveform(boosted_frame):
                # Transcription finale
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()

                # IMPORTANT: Envoyer le FINAL même si text est vide!
                # Sinon Phase 3 attend indéfiniment un FINAL qui ne viendra jamais
                stream_info["final_transcription"] = text if text else None

                if text:
                    self.stats["transcriptions"] += 1

                latency_ms = (time.time() - start_time) * 1000
                if text:
                    self._update_latency_stats(latency_ms)

                # Log avec info sur in_speech state
                in_speech_state = "IN_SPEECH" if stream_info["in_speech"] else "SILENCE"
                if text:
                    logger.info(f"📝 FINAL transcription [{call_uuid[:8]}]: '{text}' ({latency_ms:.1f}ms) [VAD state: {in_speech_state}, silence_duration: {stream_info['current_silence_duration']:.1f}s]")
                else:
                    logger.info(f"📝 FINAL transcription [{call_uuid[:8]}]: (empty - Vosk couldn't transcribe) [VAD state: {in_speech_state}, RMS={audio_rms:.0f}]")

                # Envoyer callback FINAL (même si vide)
                await self._notify_transcription(call_uuid, text, "final", latency_ms)

            else:
                # Transcription partielle
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "").strip()

                if partial_text and partial_text != stream_info["partial_transcription"]:
                    stream_info["partial_transcription"] = partial_text

                    latency_ms = (time.time() - start_time) * 1000
                    logger.info(f"📝 PARTIAL [{call_uuid[:8]}]: '{partial_text}' (RMS={audio_rms:.0f}, frame={stream_info['frame_count']})")
                    await self._notify_transcription(call_uuid, partial_text, "partial", latency_ms)

        except Exception as e:
            logger.error(f"❌ Error processing frame for {call_uuid[:8]}: {e}")

    def _update_latency_stats(self, latency_ms: float):
        """Met à jour stats de latence"""
        if self.stats["transcriptions"] == 1:
            self.stats["avg_latency_ms"] = latency_ms
        else:
            # Moyenne mobile
            self.stats["avg_latency_ms"] = self.stats["avg_latency_ms"] * 0.9 + latency_ms * 0.1

    async def _notify_speech_start(self, call_uuid: str):
        """Notifie début de parole (pour barge-in)"""
        if call_uuid in self.callbacks:
            try:
                callback = self.callbacks[call_uuid]
                event_data = {
                    "event": "speech_start",
                    "call_uuid": call_uuid,
                    "timestamp": time.time()
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)

            except Exception as e:
                logger.error(f"❌ Callback error (speech_start): {e}")

    async def _notify_speech_end(self, call_uuid: str):
        """Notifie fin de parole"""
        if call_uuid in self.callbacks:
            try:
                callback = self.callbacks[call_uuid]
                stream_info = self.active_streams[call_uuid]

                event_data = {
                    "event": "speech_end",
                    "call_uuid": call_uuid,
                    "timestamp": time.time(),
                    "silence_duration": stream_info["current_silence_duration"]
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)

            except Exception as e:
                logger.error(f"❌ Callback error (speech_end): {e}")

    def start_noise_calibration(self, call_uuid: str):
        """
        Démarre la calibration du bruit de fond.
        Appelé au début de Phase 2 hello pendant que le robot parle.
        """
        if call_uuid in self.active_streams:
            self.active_streams[call_uuid]["is_calibrating"] = True
            self.active_streams[call_uuid]["calibration_samples"] = []
            logger.info(f"🎚️ [{call_uuid[:8]}] Noise calibration STARTED")

    def stop_noise_calibration(self, call_uuid: str) -> float:
        """
        Arrête la calibration et calcule le plancher de bruit.
        Accepte N'IMPORTE QUEL nombre de samples (même 1 sample c'est mieux que rien).

        Logique intelligente:
        - 0 samples → fallback 500 (par sécurité)
        - 1-10 samples → moyenne des samples
        - 10+ samples → percentile 90 (optimal)

        Returns:
            float: Le noise floor calculé (threshold), ou 0 si pas de samples
        """
        noise_floor_threshold = 0.0
        MIN_NOISE_THRESHOLD = 500  # Fallback absolu si pas assez de données

        if call_uuid in self.active_streams:
            stream_info = self.active_streams[call_uuid]
            stream_info["is_calibrating"] = False

            samples = stream_info["calibration_samples"]
            num_samples = len(samples)

            logger.info(f"🎚️ [{call_uuid[:8]}] stop_noise_calibration called: {num_samples} samples collected")

            if num_samples == 0:
                # Aucun sample (barge-in instantané?) → fallback
                noise_floor_threshold = MIN_NOISE_THRESHOLD
                stream_info["noise_floor_rms"] = noise_floor_threshold
                logger.warning(
                    f"⚠️ [{call_uuid[:8]}] Noise calibration: 0 samples → "
                    f"using FALLBACK threshold={noise_floor_threshold:.0f}"
                )

            elif num_samples < 10:
                # Peu de samples (1-9) → utiliser moyenne simple
                import numpy as np
                avg_rms = np.mean(samples)
                noise_floor_threshold = max(avg_rms * 4, MIN_NOISE_THRESHOLD)
                stream_info["noise_floor_rms"] = noise_floor_threshold
                logger.info(
                    f"🎚️ [{call_uuid[:8]}] Noise calibration PARTIAL: "
                    f"samples={num_samples} (LOW, using AVG), avg={avg_rms:.0f}, "
                    f"threshold={noise_floor_threshold:.0f} (avg x4, min={MIN_NOISE_THRESHOLD})"
                )

            else:
                # Suffisamment de samples (10+) → utiliser percentile 90 (optimal)
                sorted_samples = sorted(samples)
                percentile_90_idx = int(len(sorted_samples) * 0.9)
                noise_floor = sorted_samples[percentile_90_idx]
                noise_floor_threshold = max(noise_floor * 4, MIN_NOISE_THRESHOLD)
                stream_info["noise_floor_rms"] = noise_floor_threshold
                logger.info(
                    f"🎚️ [{call_uuid[:8]}] Noise calibration COMPLETE: "
                    f"samples={num_samples} (GOOD), p90={noise_floor:.0f}, "
                    f"threshold={noise_floor_threshold:.0f} (p90 x4, min={MIN_NOISE_THRESHOLD})"
                )

        else:
            logger.warning(f"⚠️ [{call_uuid[:8]}] stop_noise_calibration: call_uuid not in active_streams")

        logger.info(f"🎚️ [{call_uuid[:8]}] stop_noise_calibration returning: {noise_floor_threshold:.0f}")
        return noise_floor_threshold

    def set_noise_floor(self, call_uuid: str, noise_floor_rms: float):
        """
        Applique un noise floor calibré à un stream existant.
        Utilisé pour persister le threshold entre les phases.

        Args:
            call_uuid: UUID de l'appel
            noise_floor_rms: Le threshold RMS à appliquer
        """
        if call_uuid in self.active_streams and noise_floor_rms > 0:
            self.active_streams[call_uuid]["noise_floor_rms"] = noise_floor_rms
            logger.info(f"🎚️ [{call_uuid[:8]}] Noise floor SET: threshold={noise_floor_rms:.0f}")

    async def _notify_transcription(self, call_uuid: str, text: str, transcription_type: str, latency_ms: float):
        """Notifie transcription"""
        logger.debug(f"🔔 [{call_uuid[:8]}] _notify_transcription called: type={transcription_type}, text='{text[:50]}'")
        logger.debug(f"🔔 [{call_uuid[:8]}] Registered callbacks: {list(self.callbacks.keys())}")

        if call_uuid in self.callbacks:
            try:
                callback = self.callbacks[call_uuid]
                logger.debug(f"🔔 [{call_uuid[:8]}] Calling transcription callback (type={transcription_type})")

                event_data = {
                    "event": "transcription",
                    "call_uuid": call_uuid,
                    "text": text,
                    "type": transcription_type,  # "final" ou "partial"
                    "latency_ms": latency_ms,
                    "timestamp": time.time()
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)

            except Exception as e:
                logger.error(f"❌ Callback error (transcription): {e}", exc_info=True)
        else:
            logger.warning(f"⚠️ [{call_uuid[:8]}] No callback registered for transcription (UUID: {call_uuid})")

    def register_callback(self, call_uuid: str, callback: Callable):
        """
        Enregistre un callback pour un appel

        Args:
            call_uuid: UUID de l'appel
            callback: Fonction à appeler (peut être async)
        """
        logger.debug(f"🔧 Registering callback for UUID: {call_uuid} (short: {call_uuid[:8]})")
        logger.debug(f"🔧 Callback function: {callback.__name__ if hasattr(callback, '__name__') else callback}")
        logger.debug(f"🔧 Current callbacks before: {list(self.callbacks.keys())}")

        self.callbacks[call_uuid] = callback

        logger.debug(f"✅ Callback registered for {call_uuid[:8]}")
        logger.debug(f"🔧 Current callbacks after: {list(self.callbacks.keys())}")

    def unregister_callback(self, call_uuid: str):
        """Désenregistre callback"""
        logger.debug(f"🔧 Unregistering callback for UUID: {call_uuid} (short: {call_uuid[:8]})")
        logger.debug(f"🔧 Current callbacks before: {list(self.callbacks.keys())}")

        if call_uuid in self.callbacks:
            del self.callbacks[call_uuid]
            logger.debug(f"❌ Callback unregistered for {call_uuid[:8]}")
        else:
            logger.warning(f"⚠️ No callback to unregister for {call_uuid[:8]}")

        logger.debug(f"🔧 Current callbacks after: {list(self.callbacks.keys())}")

    def reset_recognizer(self, call_uuid: str):
        """
        Réinitialise le recognizer Vosk pour vider le buffer audio

        Utilisé après un barge-in pour éviter l'accumulation de transcriptions partielles.
        Basé sur la méthode Reset() de KaldiRecognizer (vosk-api).

        Args:
            call_uuid: UUID de l'appel
        """
        if call_uuid in self.recognizers:
            try:
                self.recognizers[call_uuid].Reset()
                logger.debug(f"[{call_uuid[:8]}] 🔄 Vosk recognizer reset (buffer cleared)")

                # Réinitialiser aussi les transcriptions partielles dans stream_info
                if call_uuid in self.active_streams:
                    self.active_streams[call_uuid]["partial_transcription"] = ""
                    self.active_streams[call_uuid]["final_transcription"] = ""

            except Exception as e:
                logger.error(f"[{call_uuid[:8]}] ❌ Failed to reset recognizer: {e}")
        else:
            logger.warning(f"[{call_uuid[:8]}] ⚠️ Cannot reset - recognizer not found")

    def _cleanup_stream(self, call_uuid: str):
        """Nettoie un stream"""
        # Log état avant cleanup
        had_stream = call_uuid in self.active_streams
        had_recognizer = call_uuid in self.recognizers
        frame_count = 0
        if had_stream:
            frame_count = self.active_streams[call_uuid].get("frame_count", 0)

        logger.info(
            f"🧹 [{call_uuid[:8]}] Cleanup stream: "
            f"had_stream={had_stream}, had_recognizer={had_recognizer}, frames={frame_count}"
        )

        if call_uuid in self.active_streams:
            del self.active_streams[call_uuid]

        if call_uuid in self.recognizers:
            # IMPORTANT: Vider le buffer interne de Vosk avant de supprimer
            # Sinon l'état peut s'accumuler et causer des problèmes
            try:
                recognizer = self.recognizers[call_uuid]
                # FinalResult() vide le buffer et retourne la dernière transcription
                final = recognizer.FinalResult()
                logger.debug(f"🧹 [{call_uuid[:8]}] Vosk buffer flushed: {final[:50] if final else 'empty'}...")
            except Exception as e:
                logger.warning(f"⚠️ [{call_uuid[:8]}] Error flushing Vosk buffer: {e}")
            del self.recognizers[call_uuid]

        # ❌ NE PAS supprimer le callback automatiquement !
        # Le callback est géré explicitement par register/unregister
        # Sinon, quand une connexion WebSocket se ferme (ex: AMD),
        # elle supprime le callback de la phase suivante (Phase 2/3)
        #
        # if call_uuid in self.callbacks:
        #     del self.callbacks[call_uuid]

        self.stats["active_streams"] = len(self.active_streams)
        logger.debug(f"🧹 [{call_uuid[:8]}] Stream cleanup completed (callback preserved)")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques"""
        return {
            **self.stats,
            "is_available": self.is_available,
            "active_streams_list": list(self.active_streams.keys())
        }


# Instance globale
streaming_asr = StreamingASR()


# Fonction helper pour démarrer le serveur
async def start_streaming_asr_server():
    """Démarre le serveur ASR streaming"""
    if streaming_asr.is_available:
        await streaming_asr.start_server()
    else:
        logger.error("❌ Cannot start streaming ASR server - dependencies not available")
