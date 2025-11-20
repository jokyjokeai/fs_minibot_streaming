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

        # High-pass filter pour réduction bruit (filtre fréquences <80Hz)
        self.enable_highpass_filter = SCIPY_AVAILABLE  # Auto-enable si scipy disponible
        if self.enable_highpass_filter:
            # Butterworth high-pass filter: 80Hz cutoff, ordre 5
            self.hp_cutoff = 80  # Hz
            self.hp_order = 5
            self.hp_sos = signal.butter(self.hp_order, self.hp_cutoff, btype='highpass',
                                         fs=self.sample_rate, output='sos')
            # État du filtre par appel (pour continuité entre frames)
            self.hp_filter_states = {}  # {call_uuid: zi}
            logger.info(f"✅ High-pass filter enabled (cutoff: {self.hp_cutoff}Hz)")
        else:
            logger.warning("⚠️ High-pass filter disabled (scipy not available)")

        # NoiseReduce pour suppression avancée bruits (spectral gating)
        # DÉSACTIVÉ: Cause des problèmes de latence/qualité
        self.enable_noisereduce = False  # Forcé à False (Phase 2 revert)

        # Noise Gate Dynamique (filtre le bruit sous un seuil RMS)
        # Combiné avec high-pass filter pour réduction de bruit optimale
        # Paramètres configurables via .env
        self.enable_noise_gate = config.NOISE_GATE_ENABLED
        self.noise_gate_threshold_db = config.NOISE_GATE_THRESHOLD_DB
        self.noise_gate_attack_ms = config.NOISE_GATE_ATTACK_MS
        self.noise_gate_release_ms = config.NOISE_GATE_RELEASE_MS
        self.noise_gate_attenuation_db = config.NOISE_GATE_ATTENUATION_DB

        # États du noise gate par appel
        self.noise_gate_states = {}  # {call_uuid: {"gain": 1.0, "is_open": False}}

        if self.enable_noise_gate:
            # Précalculer coefficients attack/release
            # attack_coef = exp(-1 / (sample_rate * attack_time))
            self.noise_gate_attack_coef = np.exp(-1.0 / (self.sample_rate * self.noise_gate_attack_ms / 1000.0))
            self.noise_gate_release_coef = np.exp(-1.0 / (self.sample_rate * self.noise_gate_release_ms / 1000.0))
            # Convertir dB en linéaire
            self.noise_gate_threshold_linear = 10 ** (self.noise_gate_threshold_db / 20.0) * 32768
            self.noise_gate_attenuation_linear = 10 ** (self.noise_gate_attenuation_db / 20.0)
            logger.info(f"✅ Noise Gate enabled (threshold: {self.noise_gate_threshold_db}dB, attenuation: {self.noise_gate_attenuation_db}dB)")
        else:
            logger.info("ℹ️ Noise Gate disabled")

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

    def _apply_highpass_filter(self, call_uuid: str, frame_bytes: bytes) -> bytes:
        """
        Applique high-pass filter sur frame audio pour réduire bruits bas (<80Hz).
        Maintient l'état du filtre entre frames pour continuité (évite discontinuités de phase).

        Args:
            call_uuid: UUID de l'appel (pour gestion état)
            frame_bytes: Audio brut (16-bit PCM mono)

        Returns:
            Audio filtré (16-bit PCM mono)
        """
        if not self.enable_highpass_filter:
            return frame_bytes

        # Validation input (Fix #5)
        if not frame_bytes or len(frame_bytes) == 0:
            return frame_bytes
        if len(frame_bytes) % 2 != 0:
            logger.warning(f"⚠️ Invalid frame size: {len(frame_bytes)} bytes (not even)")
            return frame_bytes

        try:
            # Initialiser état du filtre pour ce call_uuid (si premier frame)
            if call_uuid not in self.hp_filter_states:
                # sosfilt_zi calcule l'état initial pour step response = 0 (pas de transient)
                self.hp_filter_states[call_uuid] = signal.sosfilt_zi(self.hp_sos)

            # Convertir bytes → numpy array int16 → float32
            audio_int16 = np.frombuffer(frame_bytes, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32)

            # Appliquer filtre avec état (sos = second-order sections, plus stable que ba)
            # zi maintient la continuité entre frames → pas de discontinuités
            filtered_float, self.hp_filter_states[call_uuid] = signal.sosfilt(
                self.hp_sos,
                audio_float,
                zi=self.hp_filter_states[call_uuid]
            )

            # Reconvertir → int16 (clamp pour éviter overflow)
            filtered_int16 = np.clip(filtered_float, -32768, 32767).astype(np.int16)

            # Reconvertir → bytes
            return filtered_int16.tobytes()

        except Exception as e:
            logger.warning(f"⚠️ High-pass filter failed for {call_uuid[:8]}: {e}, using original audio")
            return frame_bytes

    def _apply_noise_gate(self, call_uuid: str, frame_bytes: bytes) -> bytes:
        """
        Applique un Noise Gate Dynamique sur frame audio.

        Le gate s'ouvre quand le signal dépasse le seuil (parole) et se ferme
        quand le signal est sous le seuil (bruit de fond).
        Utilise attack/release pour des transitions douces.

        Args:
            call_uuid: UUID de l'appel (pour gestion état)
            frame_bytes: Audio brut (16-bit PCM mono)

        Returns:
            Audio avec gate appliqué (16-bit PCM mono)
        """
        if not self.enable_noise_gate:
            return frame_bytes

        # Validation input
        if not frame_bytes or len(frame_bytes) == 0:
            return frame_bytes
        if len(frame_bytes) % 2 != 0:
            return frame_bytes

        try:
            # Initialiser état pour ce call_uuid (si premier frame)
            if call_uuid not in self.noise_gate_states:
                self.noise_gate_states[call_uuid] = {
                    "gain": self.noise_gate_attenuation_linear,  # Commence fermé
                    "envelope": 0.0
                }

            state = self.noise_gate_states[call_uuid]

            # Convertir bytes → numpy array int16
            audio_int16 = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)

            # Calculer RMS du frame pour déterminer si parole ou bruit
            rms = np.sqrt(np.mean(audio_int16 ** 2))

            # Mettre à jour l'envelope avec attack/release
            if rms > state["envelope"]:
                # Attack (signal monte)
                state["envelope"] = self.noise_gate_attack_coef * state["envelope"] + \
                                   (1 - self.noise_gate_attack_coef) * rms
            else:
                # Release (signal descend)
                state["envelope"] = self.noise_gate_release_coef * state["envelope"] + \
                                   (1 - self.noise_gate_release_coef) * rms

            # Déterminer le gain cible basé sur l'envelope
            if state["envelope"] > self.noise_gate_threshold_linear:
                # Gate ouvert - laisser passer
                target_gain = 1.0
            else:
                # Gate fermé - atténuer
                target_gain = self.noise_gate_attenuation_linear

            # Smooth transition vers le gain cible (évite les clics)
            # Utilise une interpolation exponentielle
            smooth_coef = 0.1  # Plus petit = plus lisse
            state["gain"] = state["gain"] + smooth_coef * (target_gain - state["gain"])

            # Appliquer le gain
            gated_audio = audio_int16 * state["gain"]

            # Reconvertir → int16 (clamp pour éviter overflow)
            gated_int16 = np.clip(gated_audio, -32768, 32767).astype(np.int16)

            return gated_int16.tobytes()

        except Exception as e:
            logger.warning(f"⚠️ Noise gate failed for {call_uuid[:8]}: {e}, using original audio")
            return frame_bytes

    def _apply_noise_reduction(self, frame_bytes: bytes) -> bytes:
        """
        Applique noise reduction (spectral gating) pour bruits variables.

        Args:
            frame_bytes: Audio brut (16-bit PCM mono)

        Returns:
            Audio nettoyé (16-bit PCM mono)
        """
        if not self.enable_noisereduce:
            return frame_bytes

        try:
            # Convertir bytes → numpy array int16 → float normalized
            audio_int16 = np.frombuffer(frame_bytes, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0  # Normalize to [-1, 1]

            # Appliquer NoiseReduce (stationary mode - bruits constants)
            # stationary=True: Plus rapide et efficace pour bruits constants (AC, ventilateur, musique)
            # prop_decrease=1.0: Réduction agressive (0.0-1.0, default=1.0)
            reduced_float = nr.reduce_noise(
                y=audio_float,
                sr=self.sample_rate,
                stationary=True,
                prop_decrease=1.0
            )

            # Reconvertir → int16 (clamp pour éviter overflow)
            reduced_int16 = np.clip(reduced_float * 32768, -32768, 32767).astype(np.int16)

            # Reconvertir → bytes
            return reduced_int16.tobytes()

        except Exception as e:
            logger.warning(f"⚠️ Noise reduction failed: {e}, using original audio")
            return frame_bytes

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
            "last_speech_time": 0.0
        }

        self.stats["active_streams"] += 1
        logger.debug(f"🎤 Initialized stream for {call_uuid[:8]}")

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
                stream_info["current_silence_duration"] += frame_duration_s
                stream_info["current_speech_duration"] = max(0, stream_info["current_speech_duration"] - frame_duration_s)
                self.stats["silence_frames"] += 1

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

            # AUDIO PREPROCESSING pour Vosk ASR (pas pour VAD qui utilise frame_bytes original)
            # 1. High-pass filter: Réduction bruits bas (<80Hz: ventilateurs, rumble, etc.)
            filtered_frame = self._apply_highpass_filter(call_uuid, frame_bytes)
            # 2. Noise Gate: Atténue le bruit de fond quand pas de parole
            filtered_frame = self._apply_noise_gate(call_uuid, filtered_frame)

            # ASR - Transcription streaming (sur audio filtré + gated)
            if recognizer.AcceptWaveform(filtered_frame):
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
                    logger.debug(f"📝 FINAL transcription [{call_uuid[:8]}]: (empty - Vosk couldn't transcribe) [VAD state: {in_speech_state}]")

                # Envoyer callback FINAL (même si vide)
                await self._notify_transcription(call_uuid, text, "final", latency_ms)

            else:
                # Transcription partielle
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "").strip()

                if partial_text and partial_text != stream_info["partial_transcription"]:
                    stream_info["partial_transcription"] = partial_text

                    latency_ms = (time.time() - start_time) * 1000
                    logger.debug(f"📝 PARTIAL transcription [{call_uuid[:8]}]: '{partial_text}'")
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
        logger.debug(f"🧹 [{call_uuid[:8]}] Cleaning up WebSocket stream")

        if call_uuid in self.active_streams:
            del self.active_streams[call_uuid]
            logger.debug(f"🧹 [{call_uuid[:8]}] Removed active_stream")

        if call_uuid in self.recognizers:
            del self.recognizers[call_uuid]
            logger.debug(f"🧹 [{call_uuid[:8]}] Removed recognizer")

        # Nettoyer état du high-pass filter
        if self.enable_highpass_filter and call_uuid in self.hp_filter_states:
            del self.hp_filter_states[call_uuid]
            logger.debug(f"🧹 [{call_uuid[:8]}] Removed high-pass filter state")

        # Nettoyer état du noise gate
        if self.enable_noise_gate and call_uuid in self.noise_gate_states:
            del self.noise_gate_states[call_uuid]
            logger.debug(f"🧹 [{call_uuid[:8]}] Removed noise gate state")

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
