"""
Streaming ASR Service V3 - SIMPLIFIÉ

Changements V3:
- ❌ SUPPRIMÉ reset_recognizer() (causait crash Vosk)
- ✅ AJOUTÉ durée dans événements speech_end
- ✅ AJOUTÉ durée dans événements transcription
- ✅ Gestion événements simplifiée

Architecture:
- Serveur WebSocket qui reçoit audio depuis FreeSWITCH
- WebRTC VAD pour détection parole/silence
- Vosk ASR pour transcription streaming
- Callbacks pour barge-in avec durée incluse
"""

import asyncio
import json
import time
import struct
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

from system.config_v3 import config
from system.logger import get_logger

logger = get_logger(__name__)


class StreamingASRV3:
    """
    Service de transcription streaming V3 avec VAD pour FreeSWITCH.
    Version simplifiée sans reset_recognizer, avec durée de parole incluse.
    """

    def __init__(self):
        """Initialise le service streaming ASR V3"""
        logger.info("🚀 Initializing StreamingASR V3...")

        self.is_available = WEBSOCKETS_AVAILABLE and VAD_AVAILABLE and VOSK_AVAILABLE

        if not self.is_available:
            missing = []
            if not WEBSOCKETS_AVAILABLE:
                missing.append("websockets")
            if not VAD_AVAILABLE:
                missing.append("webrtcvad")
            if not VOSK_AVAILABLE:
                missing.append("vosk")
            logger.warning(f"🚫 StreamingASR V3 not available - missing: {', '.join(missing)}")
            return

        # Configuration VAD
        self.vad = webrtcvad.Vad(2)  # Mode 2 = balance qualité/réactivité
        self.sample_rate = config.VOSK_SAMPLE_RATE  # 16000 Hz
        self.frame_duration_ms = 30  # 30ms frames
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)

        # Seuils V3 (depuis config_v3)
        self.silence_threshold = config.VAD_SILENCE_THRESHOLD  # 0.8s
        self.speech_start_threshold = config.VAD_SPEECH_START_THRESHOLD  # 0.5s

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

        logger.info(f"{'✅' if self.is_available else '❌'} StreamingASR V3 initialized")

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

    async def start_server(self, host: str = None, port: int = None):
        """
        Démarre le serveur WebSocket pour recevoir audio depuis FreeSWITCH

        Args:
            host: Host à écouter (défaut: config.WEBSOCKET_HOST)
            port: Port à écouter (défaut: config.WEBSOCKET_PORT)
        """
        if not self.is_available:
            logger.error("🚫 Cannot start server - dependencies not available")
            return

        host = host or config.WEBSOCKET_HOST
        port = port or config.WEBSOCKET_PORT

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

        # V3: Ajout de speech_start_time pour calcul durée
        self.active_streams[call_uuid] = {
            "start_time": time.time(),
            "frame_count": 0,
            "speech_frames": 0,
            "silence_frames": 0,
            "current_speech_duration": 0.0,
            "current_silence_duration": 0.0,
            "in_speech": False,
            "speech_start_time": 0.0,  # ← NOUVEAU V3
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
            # VAD - Détection activité vocale
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
                        stream_info["speech_start_time"] = time.time()  # ← V3: Enregistrer temps début
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

                        # V3: Calculer durée totale de la parole
                        speech_duration = time.time() - stream_info["speech_start_time"]

                        logger.info(f"🤐 Speech END detected: {call_uuid[:8]} (durée: {speech_duration:.2f}s, silence: {stream_info['current_silence_duration']:.1f}s)")
                        await self._notify_speech_end(call_uuid, speech_duration)

                        # V3 FIX: Réinitialiser speech_start_time pour éviter accumulation
                        stream_info["speech_start_time"] = 0.0

            # ASR - Transcription streaming
            if recognizer.AcceptWaveform(frame_bytes):
                # Transcription finale
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()

                if text:
                    stream_info["final_transcription"] = text
                    self.stats["transcriptions"] += 1

                    latency_ms = (time.time() - start_time) * 1000
                    self._update_latency_stats(latency_ms)

                    # V3: Calculer durée de parole pour transcription
                    speech_duration = 0.0
                    if stream_info["speech_start_time"] > 0:
                        speech_duration = time.time() - stream_info["speech_start_time"]

                    in_speech_state = "IN_SPEECH" if stream_info["in_speech"] else "SILENCE"
                    logger.info(f"📝 FINAL transcription [{call_uuid[:8]}]: '{text}' (durée: {speech_duration:.2f}s, latency: {latency_ms:.1f}ms) [VAD state: {in_speech_state}]")

                    await self._notify_transcription(call_uuid, text, "final", speech_duration, latency_ms)

            else:
                # Transcription partielle
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "").strip()

                if partial_text and partial_text != stream_info["partial_transcription"]:
                    stream_info["partial_transcription"] = partial_text

                    latency_ms = (time.time() - start_time) * 1000

                    # V3: Durée partielle
                    speech_duration = 0.0
                    if stream_info["speech_start_time"] > 0:
                        speech_duration = time.time() - stream_info["speech_start_time"]

                    logger.debug(f"📝 PARTIAL transcription [{call_uuid[:8]}]: '{partial_text}' (durée: {speech_duration:.2f}s)")
                    await self._notify_transcription(call_uuid, partial_text, "partial", speech_duration, latency_ms)

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
        """
        V3: Notifie début de parole (pour barge-in)

        Événement envoyé:
        {
            "type": "speech_start",
            "call_uuid": str,
            "timestamp": float
        }
        """
        if call_uuid in self.callbacks:
            try:
                callback = self.callbacks[call_uuid]
                event_data = {
                    "type": "speech_start",  # V3: type au lieu de event
                    "call_uuid": call_uuid,
                    "timestamp": time.time()
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)

            except Exception as e:
                logger.error(f"❌ Callback error (speech_start): {e}")

    async def _notify_speech_end(self, call_uuid: str, duration: float):
        """
        V3: Notifie fin de parole AVEC durée incluse

        Événement envoyé:
        {
            "type": "speech_end",
            "call_uuid": str,
            "duration": float,  ← NOUVEAU V3
            "timestamp": float
        }
        """
        if call_uuid in self.callbacks:
            try:
                callback = self.callbacks[call_uuid]

                event_data = {
                    "type": "speech_end",  # V3: type au lieu de event
                    "call_uuid": call_uuid,
                    "duration": duration,  # ← NOUVEAU V3
                    "timestamp": time.time()
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)

            except Exception as e:
                logger.error(f"❌ Callback error (speech_end): {e}")

    async def _notify_transcription(self, call_uuid: str, text: str, transcription_type: str, duration: float, latency_ms: float):
        """
        V3: Notifie transcription AVEC durée incluse

        Événement envoyé:
        {
            "type": "transcription",
            "call_uuid": str,
            "text": str,
            "transcription_type": str,  (final/partial)
            "duration": float,  ← NOUVEAU V3
            "latency_ms": float,
            "timestamp": float
        }
        """
        if call_uuid in self.callbacks:
            try:
                callback = self.callbacks[call_uuid]

                event_data = {
                    "type": "transcription",  # V3: type au lieu de event
                    "call_uuid": call_uuid,
                    "text": text,
                    "transcription_type": transcription_type,  # V3: transcription_type au lieu de type
                    "duration": duration,  # ← NOUVEAU V3
                    "latency_ms": latency_ms,
                    "timestamp": time.time()
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)

            except Exception as e:
                logger.error(f"❌ Callback error (transcription): {e}")

    def register_callback(self, call_uuid: str, callback: Callable):
        """
        Enregistre un callback pour un appel

        Args:
            call_uuid: UUID de l'appel
            callback: Fonction à appeler (peut être async)
        """
        self.callbacks[call_uuid] = callback
        logger.debug(f"✅ Callback registered for {call_uuid[:8]}")

    def unregister_callback(self, call_uuid: str):
        """Désenregistre callback"""
        if call_uuid in self.callbacks:
            del self.callbacks[call_uuid]
            logger.debug(f"❌ Callback unregistered for {call_uuid[:8]}")

    # ============================================================================
    # V3: reset_recognizer() SUPPRIMÉ
    # ============================================================================
    # ANCIENNE MÉTHODE V2 (CAUSAIT CRASH):
    # def reset_recognizer(self, call_uuid: str):
    #     self.recognizers[call_uuid].Reset()  # ❌ corrupted double-linked list
    #
    # RAISON SUPPRESSION:
    # - Vosk ne supporte pas Reset() pendant traitement audio actif
    # - Causait crash "corrupted double-linked list"
    # - Pas nécessaire: Vosk se nettoie automatiquement
    # ============================================================================

    def _cleanup_stream(self, call_uuid: str):
        """Nettoie un stream"""
        if call_uuid in self.active_streams:
            del self.active_streams[call_uuid]

        if call_uuid in self.recognizers:
            del self.recognizers[call_uuid]

        if call_uuid in self.callbacks:
            del self.callbacks[call_uuid]

        self.stats["active_streams"] = len(self.active_streams)
        logger.debug(f"🧹 Cleaned up stream for {call_uuid[:8]}")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques"""
        return {
            **self.stats,
            "is_available": self.is_available,
            "active_streams_list": list(self.active_streams.keys())
        }


# Instance globale V3
streaming_asr_v3 = StreamingASRV3()


# Fonction helper pour démarrer le serveur V3
async def start_streaming_asr_server_v3():
    """Démarre le serveur ASR streaming V3"""
    if streaming_asr_v3.is_available:
        await streaming_asr_v3.start_server()
    else:
        logger.error("❌ Cannot start streaming ASR V3 server - dependencies not available")
