# -*- coding: utf-8 -*-
"""
Robot FreeSWITCH - MiniBotPanel v3 FILE-BASED Optimized

Main robot for automated marketing calls with AI
- Phase 1: AMD (Answering Machine Detection)
- Phase 2: PLAYING AUDIO (with barge-in VAD)
- Phase 3: WAITING RESPONSE (listen client)

CRITICAL OPTIMIZATION: PRELOADING
- All AI services loaded at __init__ (not per call)
- GPU warmup test for Faster-Whisper
- ObjectionMatcher preloaded
- No cold starts!

Target: <1s total latency per interaction cycle
"""

import logging
import os
import time
import threading
import asyncio
import re
import random
from typing import Dict, Optional, Any, List
from pathlib import Path
from collections import defaultdict

# ESL (FreeSWITCH Event Socket Layer)
try:
    from ESL import ESLconnection
    ESL_AVAILABLE = True
except ImportError:
    ESL_AVAILABLE = False
    ESLconnection = None

# WebRTC VAD (Voice Activity Detection for barge-in)
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    webrtcvad = None

# AI Services
from system.services.faster_whisper_stt import FasterWhisperSTT
from system.services.amd_service import AMDService
from system.services.streaming_asr import StreamingASR

# Scenarios & Objections & Intents
from system.scenarios import ScenarioManager
from system.objection_matcher import ObjectionMatcher
# intents_db supprimé - tout passe par ObjectionMatcher maintenant

# Colored Logger (Futuristic Design 🚀)
from system.logger_colored import get_colored_logger

# Database
from system.database import SessionLocal
from system.models import Call, CallStatus, CallResult

# Config
from system.config import config

# Logger avec fichier pour debug détaillé
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# FileHandler pour logs détaillés dans fichier
_logs_dir = config.BASE_DIR / "logs" / "misc"
_logs_dir.mkdir(parents=True, exist_ok=True)
_log_file = _logs_dir / f"system.robot_freeswitch_{__import__('datetime').datetime.now().strftime('%Y%m%d')}.log"

_file_handler = logging.handlers.RotatingFileHandler(
    _log_file,
    maxBytes=50*1024*1024,  # 50MB pour logs très détaillés
    backupCount=5,
    encoding='utf-8'
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", '
    '"message": "%(message)s", "function": "%(funcName)s", "line": %(lineno)d}'
))
logger.addHandler(_file_handler)


class RobotFreeSWITCH:
    """
    Main Robot for automated marketing calls

    Architecture:
    - Dual ESL connections (events + API)
    - Thread per call
    - 3 phases: AMD -> PLAYING -> WAITING
    - PRELOADED AI services (no cold starts)
    """

    def __init__(self, default_theme: Optional[str] = None):
        """
        Initialize robot and PRELOAD all AI services

        CRITICAL: All models loaded HERE (not per call) for:
        - No cold start on 1st call
        - GPU already warm
        - Instances reused across all calls
        """
        logger.info("=" * 80)
        logger.info("ROBOT FREESWITCH - INITIALIZATION")
        logger.info("=" * 80)

        if not ESL_AVAILABLE:
            raise RuntimeError("ESL module not available - install python-ESL")

        logger.info("ESL module loaded (python-ESL)")

        # === CONFIGURATION ===
        self.esl_host = config.FREESWITCH_ESL_HOST
        self.esl_port = config.FREESWITCH_ESL_PORT
        self.esl_password = config.FREESWITCH_ESL_PASSWORD

        # === ESL CONNECTIONS (DUAL) ===
        self.esl_conn_events = None  # Receive events (blocking)
        self.esl_conn_api = None     # Send API commands (non-blocking)
        self.esl_api_lock = threading.Lock()  # Thread-safe access to esl_conn_api

        # === EVENT LOOP ===
        self.running = False
        self.event_thread = None

        # === CALL MANAGEMENT ===
        self.active_calls = {}  # {call_uuid: call_info}
        self.call_threads = {}  # {call_uuid: thread}
        self.call_sessions = {}  # {call_uuid: session_data}

        # === AUDIO TRACKING ===
        self.barge_in_active = {}  # {call_uuid: bool}

        # === COLORED LOGGER (Futuristic Design 🚀) ===
        self.clog = get_colored_logger()

        # ===================================================================
        # PRELOADING AI SERVICES (CRITICAL FOR LATENCY)
        # ===================================================================
        logger.info("Loading AI services (PRELOAD optimization)...")

        # 1. Faster-Whisper STT (GPU-accelerated) - CRITICAL PRELOAD
        try:
            logger.info("Loading Faster-Whisper STT (GPU)...")
            start_time = time.time()

            self.stt_service = FasterWhisperSTT(
                model_name=config.FASTER_WHISPER_MODEL,
                device=config.FASTER_WHISPER_DEVICE,
                compute_type=config.FASTER_WHISPER_COMPUTE_TYPE,
                language=config.FASTER_WHISPER_LANGUAGE,
                beam_size=config.FASTER_WHISPER_BEAM_SIZE,
                noise_reduce=config.NOISE_REDUCE_ENABLED,
                noise_reduce_strength=config.NOISE_REDUCE_STRENGTH
            )

            load_time = (time.time() - start_time) * 1000

            logger.info(
                f"Faster-Whisper STT loaded in {load_time:.0f}ms "
                f"(model={config.FASTER_WHISPER_MODEL}, device={config.FASTER_WHISPER_DEVICE})"
            )

        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper STT: {e}")
            self.stt_service = None
            raise

        # 2. AMD Service (keywords matching)
        try:
            logger.info("Loading AMD Service...")
            self.amd_service = AMDService(
                keywords_human=config.AMD_KEYWORDS_HUMAN,
                keywords_machine=config.AMD_KEYWORDS_MACHINE,
                min_confidence=config.AMD_MIN_CONFIDENCE
            )
            logger.info("AMD Service loaded")
        except Exception as e:
            logger.error(f"Failed to load AMD Service: {e}")
            self.amd_service = None
            raise

        # 4. WebRTC VAD (barge-in detection - fallback si mod_vosk indisponible)
        if VAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad(config.WEBRTC_VAD_AGGRESSIVENESS)
                logger.info(
                    f"WebRTC VAD loaded "
                    f"(aggressiveness={config.WEBRTC_VAD_AGGRESSIVENESS})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize VAD: {e}")
                self.vad = None
                raise
        else:
            logger.error("WebRTC VAD not available - barge-in disabled!")
            self.vad = None
            raise RuntimeError("VAD required for barge-in")

        # 4.5. Streaming ASR (Vosk Python + mod_audio_fork WebSocket)
        # Serveur WebSocket pour barge-in streaming temps réel
        try:
            if config.STREAMING_ASR_ENABLED:
                logger.info("Loading Streaming ASR service...")
                self.streaming_asr = StreamingASR()

                if self.streaming_asr.is_available:
                    # Démarrer serveur WebSocket dans thread asyncio
                    self.asr_server_thread = threading.Thread(
                        target=self._run_streaming_asr_server,
                        daemon=True,
                        name="StreamingASR-Server"
                    )
                    self.asr_server_thread.start()

                    # HEALTH CHECK: Attendre que serveur démarre vraiment
                    logger.info(
                        f"⏳ Waiting for WebSocket server to start on "
                        f"{config.STREAMING_ASR_HOST}:{config.STREAMING_ASR_PORT}..."
                    )

                    max_wait = 5.0  # 5 secondes max
                    wait_start = time.time()
                    server_started = False

                    while (time.time() - wait_start) < max_wait:
                        try:
                            # Tester connexion TCP sur port WebSocket
                            import socket
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(0.1)
                            result = sock.connect_ex((
                                config.STREAMING_ASR_HOST,
                                config.STREAMING_ASR_PORT
                            ))
                            sock.close()

                            if result == 0:
                                # Port accessible !
                                server_started = True
                                elapsed = time.time() - wait_start
                                logger.info(
                                    f"✅ Streaming ASR WebSocket server READY "
                                    f"(started in {elapsed:.2f}s)"
                                )
                                break
                        except Exception:
                            pass

                        time.sleep(0.1)  # Poll every 100ms

                    if not server_started:
                        logger.error(
                            f"❌ Streaming ASR server failed to start within {max_wait}s! "
                            f"Falling back to WebRTC VAD."
                        )
                        self.streaming_asr = None
                else:
                    logger.warning(
                        "⚠️  Streaming ASR dependencies missing "
                        "(check: websockets, webrtcvad, vosk, model path)"
                    )
                    self.streaming_asr = None
            else:
                logger.info("ℹ️  Streaming ASR disabled, using WebRTC VAD fallback")
                self.streaming_asr = None

        except Exception as e:
            logger.warning(f"⚠️  Streaming ASR initialization failed: {e}", exc_info=True)
            self.streaming_asr = None
            logger.info("Using WebRTC VAD fallback for barge-in")

        # 5. ScenarioManager
        try:
            logger.info("Loading ScenarioManager...")
            self.scenario_manager = ScenarioManager()
            logger.info("ScenarioManager loaded")
        except Exception as e:
            logger.error(f"Failed to load ScenarioManager: {e}")
            self.scenario_manager = None
            raise

        # 6. ObjectionMatcher (PRELOAD with scenario-specific theme)
        try:
            if default_theme:
                logger.info(f"Loading ObjectionMatcher (theme: {default_theme})...")
                # Load objections for the scenario's theme
                self.objection_matcher_default = ObjectionMatcher.load_objections_for_theme(default_theme)
                if self.objection_matcher_default:
                    logger.info(
                        f"ObjectionMatcher loaded ({default_theme}, "
                        f"{len(self.objection_matcher_default.objections)} objections)"
                    )
                else:
                    logger.warning(f"ObjectionMatcher not loaded (no objections found for {default_theme})")
            else:
                logger.info("No default theme specified, ObjectionMatcher warmup skipped")
                self.objection_matcher_default = None
        except Exception as e:
            logger.warning(f"ObjectionMatcher not available: {e}")
            self.objection_matcher_default = None

        # 7. Intents Database supprimé - tout passe par ObjectionMatcher maintenant
        # Les intents (affirm, deny, insult) sont dans objections_general.py

        # ===================================================================
        # WARMUP TESTS (CRITICAL - Avoid first-call latency spikes)
        # ===================================================================

        # 1. GPU WARMUP (Faster-Whisper)
        if self.stt_service and config.FASTER_WHISPER_DEVICE == "cuda":
            logger.info("WARMUP 1/4: GPU Faster-Whisper test transcription...")
            try:
                # Create dummy 1s silence audio for warmup
                import wave
                import struct
                import tempfile

                warmup_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                warmup_path = warmup_audio.name

                # Generate 1s silence @ 8kHz mono
                with wave.open(warmup_path, 'w') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(8000)
                    # 1s = 8000 frames
                    silence = struct.pack('<' + ('h' * 8000), *([0] * 8000))
                    wf.writeframes(silence)

                # Warmup transcription
                warmup_start = time.time()
                result = self.stt_service.transcribe_file(warmup_path)
                warmup_time = (time.time() - warmup_start) * 1000

                logger.info(f"GPU WARMUP 1/4: Completed in {warmup_time:.0f}ms - GPU is HOT!")

                # Cleanup
                Path(warmup_path).unlink()

            except Exception as e:
                logger.warning(f"GPU warmup failed (non-critical): {e}")

        # 2. VAD WARMUP
        if self.vad:
            logger.info("WARMUP 2/4: VAD test detection...")
            try:
                # Test VAD on dummy audio frame
                import struct

                # 30ms frame @ 8kHz = 240 samples
                frame_samples = 240
                test_frame = struct.pack('<' + ('h' * frame_samples), *([100] * frame_samples))

                warmup_start = time.time()
                is_speech = self.vad.is_speech(test_frame, 8000)
                warmup_time = (time.time() - warmup_start) * 1000

                logger.info(f"VAD WARMUP 2/4: Completed in {warmup_time:.2f}ms - VAD is READY!")

            except Exception as e:
                logger.warning(f"VAD warmup failed (non-critical): {e}")

        # 3. OBJECTION MATCHER WARMUP
        if self.objection_matcher_default:
            logger.info(f"WARMUP 3/4: ObjectionMatcher test match (theme: {default_theme})...")
            try:
                warmup_start = time.time()
                # Test with a common objection phrase (silent mode to avoid ❌ log)
                test_match = self.objection_matcher_default.find_best_match(
                    "C'est trop cher pour moi",
                    min_score=0.5,
                    silent=True  # Silent mode for warmup (no ✅/❌ logs)
                )
                warmup_time = (time.time() - warmup_start) * 1000

                match_status = "✅ MATCHED" if test_match else "⚠️ NO MATCH"
                logger.info(
                    f"ObjectionMatcher WARMUP 3/4: Completed in {warmup_time:.2f}ms - "
                    f"Matcher is READY! ({match_status})"
                )

            except Exception as e:
                logger.warning(f"ObjectionMatcher warmup failed (non-critical): {e}")
        else:
            logger.info("WARMUP 3/4: ObjectionMatcher skipped (no theme specified)")

        # 4. VOSK WARMUP (Streaming ASR)
        if self.streaming_asr and self.streaming_asr.is_available:
            logger.info("WARMUP 4/4: Vosk ASR test transcription...")
            try:
                # Créer dummy audio 1s @ 16kHz (Vosk sample rate)
                import wave
                import struct
                import tempfile
                from vosk import KaldiRecognizer

                warmup_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                warmup_path = warmup_audio.name

                # Generate 1s silence @ 16kHz mono (Vosk sample rate)
                with wave.open(warmup_path, 'w') as wf:
                    wf.setnchannels(1)  # Mono
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(16000)  # 16kHz pour Vosk
                    silence = struct.pack('<' + ('h' * 16000), *([0] * 16000))
                    wf.writeframes(silence)

                # Warmup transcription avec recognizer Vosk
                warmup_start = time.time()

                # Créer recognizer temporaire
                recognizer = KaldiRecognizer(
                    self.streaming_asr.model,
                    16000
                )

                # Lire et transcrire
                with wave.open(warmup_path, 'r') as wf:
                    data = wf.readframes(16000)  # 1s
                    recognizer.AcceptWaveform(data)
                    result = recognizer.FinalResult()

                warmup_time = (time.time() - warmup_start) * 1000

                logger.info(
                    f"Vosk ASR WARMUP 4/4: Completed in {warmup_time:.0f}ms - "
                    f"Vosk is READY!"
                )

                # Cleanup
                Path(warmup_path).unlink()

            except Exception as e:
                logger.warning(f"Vosk warmup failed (non-critical): {e}")
        else:
            logger.info("WARMUP 4/4: Vosk ASR skipped (Streaming ASR not available)")

        # ===================================================================
        # PRELOAD AUDIO DURATIONS (Phase 3 - Zero latency on calls)
        # ===================================================================
        logger.info("PRELOAD 5/5: Caching audio file durations...")
        try:
            from pathlib import Path
            from system.cache_manager import CacheManager

            cache = CacheManager.get_instance()
            audio_base_dir = Path("audio")

            if audio_base_dir.exists():
                # Scan tous les fichiers WAV dans audio/
                audio_files = list(audio_base_dir.rglob("*.wav"))
                total_duration = 0.0
                cached_count = 0

                preload_start = time.time()

                for audio_path in audio_files:
                    try:
                        # Utilise _get_audio_duration() qui cache automatiquement
                        duration = self._get_audio_duration(str(audio_path))
                        total_duration += duration
                        cached_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to preload duration for {audio_path}: {e}")

                preload_time = (time.time() - preload_start) * 1000

                logger.info(
                    f"Audio durations cached: {cached_count} files "
                    f"(total: {total_duration:.1f}s, preload: {preload_time:.0f}ms)"
                )
            else:
                logger.warning(f"Audio directory not found: {audio_base_dir}")

        except Exception as e:
            logger.warning(f"Audio duration preloading failed (non-critical): {e}")

        logger.info("=" * 80)
        logger.info("ROBOT INITIALIZED - ALL SERVICES PRELOADED")
        logger.info("=" * 80)

    def __repr__(self):
        return f"<RobotFreeSWITCH active_calls={len(self.active_calls)} running={self.running}>"

    def _run_streaming_asr_server(self):
        """
        Démarre le serveur WebSocket ASR dans un thread asyncio.
        Tourne en daemon thread pour recevoir audio depuis FreeSWITCH.
        """
        try:
            # Créer nouvelle event loop pour ce thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info(
                f"🚀 Starting Streaming ASR WebSocket server on "
                f"{config.STREAMING_ASR_HOST}:{config.STREAMING_ASR_PORT}..."
            )

            # Démarrer serveur (bloquant - tourne jusqu'à arrêt)
            loop.run_until_complete(
                self.streaming_asr.start_server(
                    host=config.STREAMING_ASR_HOST,
                    port=config.STREAMING_ASR_PORT
                )
            )

        except OSError as e:
            if "Address already in use" in str(e):
                logger.error(
                    f"❌ Port {config.STREAMING_ASR_PORT} already in use! "
                    f"Another process is using this port."
                )
            else:
                logger.error(
                    f"❌ Network error starting Streaming ASR server: {e}",
                    exc_info=True
                )
        except Exception as e:
            logger.error(
                f"❌ Streaming ASR server crashed: {e}",
                exc_info=True
            )
        finally:
            logger.warning("🛑 Streaming ASR server stopped")
            loop.close()

    # ========================================================================
    # ESL CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self):
        """
        Establish dual ESL connections to FreeSWITCH

        Connection 1 (events): Receive events (blocking recvEvent)
        Connection 2 (api): Send API commands (non-blocking)
        """
        logger.info("Connecting to FreeSWITCH ESL...")

        try:
            # Connection #1: Events (blocking)
            self.esl_conn_events = ESLconnection(
                self.esl_host,
                str(self.esl_port),
                self.esl_password
            )

            if not self.esl_conn_events.connected():
                raise ConnectionError("Failed to connect ESL events connection")

            # Enable linger (wait for all events before disconnect)
            self.esl_conn_events.api("linger")
            logger.debug("ESL linger enabled")

            # Subscribe to events
            events = [
                "CHANNEL_CREATE",
                "CHANNEL_ANSWER",
                "CHANNEL_HANGUP",
                "CHANNEL_HANGUP_COMPLETE",
                "DTMF"
            ]
            self.esl_conn_events.events("plain", " ".join(events))
            logger.info("ESL events connection established")

            # Connection #2: API (non-blocking)
            self.esl_conn_api = ESLconnection(
                self.esl_host,
                str(self.esl_port),
                self.esl_password
            )

            if not self.esl_conn_api.connected():
                raise ConnectionError("Failed to connect ESL API connection")

            logger.info("ESL API connection established")
            logger.info("Connected to FreeSWITCH ESL (dual connections)")

            return True

        except Exception as e:
            logger.error(f"ESL connection failed: {e}")
            return False

    def start(self):
        """Start robot and event loop"""
        logger.info("Starting RobotFreeSWITCH...")

        # Connect ESL
        if not self.connect():
            logger.error("Failed to connect to FreeSWITCH")
            return False

        # Start event loop
        self.running = True
        self.event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self.event_thread.start()

        logger.info("RobotFreeSWITCH started and listening for events")
        logger.info("Waiting for calls...")

        return True

    def stop(self):
        """Stop robot cleanly"""
        logger.info("Stopping RobotFreeSWITCH...")

        self.running = False

        # Wait for event loop
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5)

        # Close ESL connections
        if self.esl_conn_events:
            self.esl_conn_events.disconnect()
        if self.esl_conn_api:
            self.esl_conn_api.disconnect()

        logger.info("RobotFreeSWITCH stopped")

    def originate_call(self, phone_number: str, lead_id: int, scenario_name: str) -> Optional[str]:
        """
        Originate outbound call (appel sortant)

        Args:
            phone_number: Numero a appeler (format: 33XXXXXXXXX sans +)
            lead_id: ID du lead dans la base (ou 0 pour test)
            scenario_name: Nom du scenario a utiliser

        Returns:
            UUID de l'appel si succes, None sinon
        """
        logger.info(f"Originating call to {phone_number} with scenario '{scenario_name}'...")

        try:
            # Load scenario
            scenario = self.scenario_manager.load_scenario(scenario_name)
            if not scenario:
                logger.error(f"Scenario '{scenario_name}' not found")
                return None

            logger.info(f"Scenario loaded: {scenario.get('name', scenario_name)}")

            # Build originate command
            # Format: originate {variables}sofia/gateway/gateway_name/number &park()

            # Variables to pass to the call
            # CRITICAL: Set RECORD_STEREO BEFORE answer to enable stereo recording
            variables = [
                f"scenario_name={scenario_name}",
                f"lead_id={lead_id}",
                "origination_caller_id_name=MiniBotPanel",
                "origination_caller_id_number=0000000000",
                "ignore_early_media=true",
                "RECORD_STEREO=true",           # Enable STEREO recording (BEFORE answer)
                "media_bug_answer_req=true",    # Wait for ANSWER before starting media
                "rtp_timeout_sec=2",            # CRITIQUE: Détection HANGUP rapide (2s au lieu de 300s!)
                "rtp_hold_timeout_sec=2"        # Même timeout pour HOLD state
            ]

            # Join variables
            vars_str = ",".join(variables)

            # Originate command with inline dialplan
            # CRITICAL FIX: Use park() (like backup that worked!)
            # park() = muted channel, no echo to client
            # Combined with uuid_broadcast silence_stream for RTP priming
            cmd = f"originate {{{vars_str}}}sofia/gateway/gateway1/{phone_number} &park()"

            logger.info(f"Executing: {cmd[:100]}...")

            # Execute command
            result = self._execute_esl_command(cmd)

            if result and result.startswith("+OK"):
                # Extract UUID from result
                # Format: "+OK b1234567-89ab-cdef-0123-456789abcdef"
                uuid = result.split(" ")[1].strip() if " " in result else None

                if uuid:
                    logger.info(f"✅ Call originated successfully with UUID: {uuid}")

                    # Initialize session
                    self.call_sessions[uuid] = {
                        "phone_number": phone_number,
                        "lead_id": lead_id,
                        "scenario_name": scenario_name,
                        "scenario": scenario,
                        "start_time": time.time(),
                        "state": "ORIGINATED"
                    }

                    return uuid
                else:
                    logger.error(f"Failed to extract UUID from result: {result}")
                    return None
            else:
                logger.error(f"Originate failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Error originating call: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _event_loop(self):
        """
        Main event loop (runs in separate thread)
        Listens for FreeSWITCH events
        """
        logger.debug("Event loop started")

        while self.running and self.esl_conn_events:
            try:
                # Receive event (blocking)
                event = self.esl_conn_events.recvEvent()

                if not event:
                    continue

                event_name = event.getHeader("Event-Name")
                call_uuid = event.getHeader("Unique-ID")

                if not call_uuid:
                    continue

                # Dispatch events
                if event_name == "CHANNEL_ANSWER":
                    self._handle_channel_answer(call_uuid, event)

                elif event_name == "CHANNEL_HANGUP_COMPLETE":
                    self._handle_channel_hangup(call_uuid, event)

                elif event_name == "DTMF":
                    self._handle_dtmf(call_uuid, event)

            except Exception as e:
                logger.error(f"Event loop error: {e}")
                time.sleep(0.1)

        logger.debug("Event loop ended")

    # ========================================================================
    # EVENT HANDLERS (STUBS - To be completed in PARTS 2-6)
    # ========================================================================

    def _handle_channel_answer(self, call_uuid: str, event):
        """
        Handle CHANNEL_ANSWER event

        Start call thread with AMD Phase
        """
        logger.info(f"[{call_uuid[:8]}] CHANNEL_ANSWER")

        # Get call info from event
        caller_number = event.getHeader("Caller-Caller-ID-Number")
        callee_number = event.getHeader("Caller-Destination-Number")

        logger.info(
            f"[{call_uuid[:8]}] Call answered: "
            f"{caller_number} -> {callee_number}"
        )

        # Get scenario from channel variables (set during originate)
        scenario_name = event.getHeader("variable_scenario_name")
        lead_id = event.getHeader("variable_lead_id")

        # Load scenario if this is an outbound call
        if scenario_name:
            logger.info(f"[{call_uuid[:8]}] Loading scenario from channel variables: {scenario_name}")
            scenario = self.scenario_manager.load_scenario(scenario_name)

            if scenario:
                # Store session data under this UUID
                self.call_sessions[call_uuid] = {
                    "phone_number": callee_number,
                    "lead_id": int(lead_id) if lead_id else 0,
                    "scenario_name": scenario_name,
                    "scenario": scenario,
                    "start_time": time.time(),
                    "state": "ANSWERED"
                }
                logger.info(f"[{call_uuid[:8]}] Session created with scenario: {scenario_name}")

        # Store call info
        self.active_calls[call_uuid] = {
            "uuid": call_uuid,
            "caller": caller_number,
            "callee": callee_number,
            "answered_at": time.time()
        }

        # Start call thread
        call_thread = threading.Thread(
            target=self._handle_call,
            args=(call_uuid,),
            daemon=True
        )
        self.call_threads[call_uuid] = call_thread
        call_thread.start()

        logger.info(f"[{call_uuid[:8]}] Call thread started")

    def _handle_channel_hangup(self, call_uuid: str, event):
        """
        Handle CHANNEL_HANGUP_COMPLETE event

        CRITICAL: Detect client hangup REACTIVELY and set NOT_INTERESTED status

        Logic:
        - If robot initiated hangup → use robot's status (already set)
        - If client hung up → NOT_INTERESTED (client rejected)
        """
        import time
        hangup_timestamp = time.time()
        short_uuid = call_uuid[:8]

        # Get hangup cause from event
        hangup_cause = event.getHeader("Hangup-Cause")
        caller_hangup = event.getHeader("variable_sip_hangup_disposition")

        logger.info(
            f"🔴 [{short_uuid}] HANGUP: cause={hangup_cause}, "
            f"disposition={caller_hangup}"
        )

        # ===================================================================
        # CRITICAL: Determine if client hung up (NOT robot)
        # ===================================================================

        # Check if robot already set a final status
        session = self.call_sessions.get(call_uuid, {})
        robot_initiated_hangup = session.get("robot_hangup", False)
        existing_status = session.get("final_status")

        # ===== SET HANGUP DETECTION FLAG (CRITICAL for immediate detection) =====
        if call_uuid in self.call_sessions:
            self.call_sessions[call_uuid]["hangup_detected"] = True
            self.call_sessions[call_uuid]["hangup_timestamp"] = hangup_timestamp
            logger.info(
                f"🚨 [{short_uuid}] HANGUP FLAG SET in session "
                f"(timestamp: {hangup_timestamp:.6f})"
            )

            # ===== INTERRUPT PLAYBACK IMMEDIATELY if Phase 2 active =====
            # uuid_break arrête uuid_broadcast instantanément!
            try:
                break_result = self._execute_esl_command(f"uuid_break {call_uuid}")
                if break_result:
                    logger.info(
                        f"⚡ [{short_uuid}] PLAYBACK INTERRUPTED via uuid_break "
                        f"(result: {break_result.strip()})"
                    )
            except Exception as e:
                logger.debug(f"[{short_uuid}] uuid_break failed (channel may be gone): {e}")

        if robot_initiated_hangup:
            # Robot initiated hangup → use robot's status
            final_status = existing_status or CallStatus.COMPLETED
            logger.info(f"[{short_uuid}] 🤖 ROBOT-INITIATED (status: {final_status.value})")

        else:
            # Client hung up
            client_hangup_causes = [
                "NORMAL_CLEARING", "ORIGINATOR_CANCEL", "USER_BUSY",
                "NO_USER_RESPONSE", "NO_ANSWER"
            ]

            if hangup_cause in client_hangup_causes or caller_hangup == "recv_bye":
                final_status = CallResult.NOT_INTERESTED
                logger.info(f"[{short_uuid}] 👤 CLIENT-INITIATED → NOT_INTERESTED")
            else:
                final_status = existing_status or CallResult.NO_ANSWER
                logger.info(f"[{short_uuid}] 👤 CLIENT-INITIATED (non-standard) → {final_status.value}")

        # ===================================================================
        # Update database with final status
        # ===================================================================
        try:
            # TODO: Database update implementation
            # For now, log the status that SHOULD be saved

            # Check if AMD detected answering machine
            status_display = final_status.value
            if session.get("amd_machine_detected"):
                status_display = "answering_machine"

            logger.info(
                f"[{short_uuid}] FINAL STATUS: {status_display} "
                f"(robot_initiated: {robot_initiated_hangup})"
            )

            # Example implementation (when database ready):
            # db = SessionLocal()
            # call = db.query(Call).filter(Call.uuid == call_uuid).first()
            # if call:
            #     call.status = final_status
            #     call.ended_at = datetime.utcnow()
            #     call.hangup_cause = hangup_cause
            #     db.commit()
            # db.close()

        except Exception as e:
            logger.error(f"[{short_uuid}] Failed to update final status: {e}")

        # ===================================================================
        # Cleanup call data structures
        # ===================================================================
        logger.info(f"[{short_uuid}] 🧹 Starting cleanup...")

        cleanup_report = []

        if call_uuid in self.active_calls:
            del self.active_calls[call_uuid]
            cleanup_report.append("active_calls ✓")
            logger.info(f"[{short_uuid}]   ✓ Removed from active_calls")
        else:
            cleanup_report.append("active_calls (already removed)")
            logger.info(f"[{short_uuid}]   ⚠️  Not in active_calls (already removed)")

        if call_uuid in self.call_threads:
            del self.call_threads[call_uuid]
            cleanup_report.append("call_threads ✓")
            logger.info(f"[{short_uuid}]   ✓ Removed from call_threads")
        else:
            cleanup_report.append("call_threads (already removed)")
            logger.info(f"[{short_uuid}]   ⚠️  Not in call_threads (already removed)")

        if call_uuid in self.call_sessions:
            del self.call_sessions[call_uuid]
            cleanup_report.append("call_sessions ✓")
            logger.info(f"[{short_uuid}]   ✓ Removed from call_sessions")
        else:
            cleanup_report.append("call_sessions (already removed)")
            logger.info(f"[{short_uuid}]   ⚠️  Not in call_sessions (already removed)")

        if call_uuid in self.barge_in_active:
            del self.barge_in_active[call_uuid]
            cleanup_report.append("barge_in_active ✓")
            logger.info(f"[{short_uuid}]   ✓ Removed from barge_in_active")
        else:
            cleanup_report.append("barge_in_active (not set)")

        logger.info(f"[{short_uuid}] ✅ Cleanup completed: {', '.join(cleanup_report)}")
        logger.info("=" * 80)

    def _handle_dtmf(self, call_uuid: str, event):
        """Handle DTMF event (optional)"""
        dtmf_digit = event.getHeader("DTMF-Digit")
        logger.debug(f"[{call_uuid[:8]}] DTMF: {dtmf_digit}")

    # ========================================================================
    # CALL HANDLER (STUB - To be completed in PARTS 2-6)
    # ========================================================================

    def _handle_call(self, call_uuid: str):
        """
        Main call handler (runs in separate thread per call)

        Phases:
        - PHASE 1: AMD (Answering Machine Detection)
        - PHASE 2: PLAYING AUDIO (with barge-in) - TODO PART 3
        - PHASE 3: WAITING RESPONSE - TODO PART 4
        - Intent + Objections - TODO PART 5
        - MaxTurn + Qualification - TODO PART 6
        """
        short_uuid = call_uuid[:8]
        logger.info(f"[{short_uuid}] === CALL HANDLER START ===")

        try:
            # ================================================================
            # PHASE 1: AMD (Answering Machine Detection)
            # ================================================================
            amd_result = self._execute_phase_amd(call_uuid)

            if amd_result["result"] == "MACHINE":
                logger.info(
                    f"[{short_uuid}] AMD: MACHINE detected -> Hangup call"
                )
                # Store AMD result in session for final status display
                if call_uuid in self.call_sessions:
                    self.call_sessions[call_uuid]["amd_machine_detected"] = True
                self._hangup_call(call_uuid, CallResult.NO_ANSWER)
                return

            elif amd_result["result"] == "NO_ANSWER":
                logger.info(
                    f"[{short_uuid}] AMD: NO_ANSWER/SILENCE detected -> Hangup call"
                )
                self._hangup_call(call_uuid, CallStatus.NO_ANSWER)
                return

            elif amd_result["result"] == "UNKNOWN":
                logger.warning(
                    f"[{short_uuid}] AMD: UNKNOWN -> Continue anyway (assumed HUMAN)"
                )

            else:  # HUMAN
                logger.info(
                    f"[{short_uuid}] AMD: HUMAN detected -> Continue to Phase 2"
                )

            # ================================================================
            # CONVERSATION LOOP (Phases 2 + 3 + Intent + Navigation)
            # ================================================================
            logger.info(f"[{short_uuid}] === CONVERSATION LOOP START ===")

            # Load scenario from call session
            session = self.call_sessions.get(call_uuid)
            if not session:
                logger.error(f"[{short_uuid}] No session data found!")
                self._hangup_call(call_uuid, CallResult.NO_ANSWER)
                return

            scenario = session.get("scenario")
            if not scenario:
                logger.error(f"[{short_uuid}] No scenario loaded!")
                self._hangup_call(call_uuid, CallResult.NO_ANSWER)
                return

            scenario_name = session.get("scenario_name", "unknown")
            logger.info(
                f"[{short_uuid}] Loaded scenario: {scenario_name} "
                f"({len(scenario.get('steps', {}))} steps)"
            )

            # Initialize session tracking
            session["qualification_score"] = 0.0
            session["steps_executed"] = []

            # Get first step (rail or default to "hello")
            rail = scenario.get("rail", [])
            if rail and len(rail) > 0:
                current_step = rail[0]  # Start with first step in rail
                logger.info(f"[{short_uuid}] Using rail: {rail}")
            else:
                # No rail defined, try common starting steps
                steps = scenario.get("steps", {})
                if "hello" in steps:
                    current_step = "hello"
                    logger.info(f"[{short_uuid}] No rail defined, starting with 'hello'")
                elif "intro" in steps:
                    current_step = "intro"
                    logger.info(f"[{short_uuid}] No rail defined, starting with 'intro'")
                elif len(steps) > 0:
                    # Use first step in steps dict
                    current_step = list(steps.keys())[0]
                    logger.info(f"[{short_uuid}] No rail defined, starting with first step: {current_step}")
                else:
                    logger.error(f"[{short_uuid}] Scenario has no steps!")
                    self._hangup_call(call_uuid, CallResult.NO_ANSWER)
                    return
            max_steps = 50  # Safety limit to prevent infinite loops
            step_count = 0

            # Conversation loop
            while current_step and step_count < max_steps:
                step_count += 1

                logger.info(
                    f"[{short_uuid}] === STEP {step_count}: {current_step} ==="
                )

                # Get step config
                step_config = scenario.get("steps", {}).get(current_step)
                if not step_config:
                    logger.error(f"[{short_uuid}] Step '{current_step}' not found in scenario!")
                    break

                # Check if this is a terminal step (is_terminal property OR legacy names)
                is_terminal = (
                    step_config.get("is_terminal", False) or
                    current_step.lower() in ["bye", "bye_failed", "end"] or
                    current_step.lower().startswith("bye_")
                )

                if is_terminal:
                    logger.info(
                        f"[{short_uuid}] Terminal step reached: {current_step}"
                    )

                    # Play final audio
                    audio_path = self._get_audio_path_for_step(scenario, current_step)
                    if audio_path:
                        self._execute_phase_2_auto(
                            call_uuid,
                            audio_path,
                            enable_barge_in=False,  # No barge-in on goodbye
                            is_terminal=True  # Play full audio, no early exit
                        )

                    # Determine final status based on step "result" attribute
                    step_result = step_config.get("result")

                    if step_result == "completed":
                        # Success path → Calculate qualification score
                        final_status = self._calculate_final_status(session, scenario)
                        logger.info(
                            f"[{short_uuid}] Call completed -> "
                            f"Final status: {final_status.value} "
                            f"(qualification score: {session.get('qualification_score', 0):.1f})"
                        )
                    elif step_result == "failed":
                        # Explicit failure (refus/disqualification)
                        final_status = CallResult.NOT_INTERESTED
                        logger.info(
                            f"[{short_uuid}] Call failed (refus) -> "
                            f"Final status: NOT_INTERESTED"
                        )
                    elif step_result == "no_answer":
                        # No response → retry candidate
                        final_status = CallResult.NO_ANSWER
                        logger.info(
                            f"[{short_uuid}] No answer -> "
                            f"Final status: NO_ANSWER (retry candidate)"
                        )
                    else:
                        # Unknown result type → default to NOT_INTERESTED
                        final_status = CallResult.NOT_INTERESTED
                        logger.warning(
                            f"[{short_uuid}] Unknown step result '{step_result}' -> "
                            f"Final status: NOT_INTERESTED"
                        )

                    # Execute step actions (email, webhook, transfer, etc.) BEFORE ending
                    self._execute_step_actions(call_uuid, step_config, session)

                    # End conversation
                    self._hangup_call(call_uuid, final_status)
                    return

                # Execute conversation step (PHASE 2 + PHASE 3 + Intent)
                # Calibrer le noise floor uniquement pour le premier step (hello)
                step_result = self._execute_conversation_step(
                    call_uuid,
                    scenario,
                    current_step,
                    session,
                    retry_count=0,
                    calibrate_noise=(step_count == 1)  # Premier step uniquement
                )

                if not step_result.get("success"):
                    logger.error(
                        f"[{short_uuid}] Step execution failed: "
                        f"{step_result.get('error', 'unknown')}"
                    )
                    self._hangup_call(call_uuid, CallResult.NO_ANSWER)
                    return

                # Track step
                session["steps_executed"].append({
                    "step": current_step,
                    "intent": step_result.get("intent"),
                    "transcription": step_result.get("transcription", "")[:100]
                })

                # Check if retry requested
                if step_result.get("retry"):
                    logger.info(f"[{short_uuid}] Retrying step: {current_step}")
                    continue  # Retry same step

                # Navigate to next step
                next_step = step_result.get("next_step")

                if not next_step:
                    logger.warning(
                        f"[{short_uuid}] No next step defined -> Ending call"
                    )
                    self._hangup_call(call_uuid, CallResult.NOT_INTERESTED)
                    return

                logger.info(
                    f"[{short_uuid}] Navigation: {current_step} -> {next_step} "
                    f"(intent: {step_result.get('intent')})"
                )

                current_step = next_step

            # Safety: Max steps reached
            if step_count >= max_steps:
                logger.error(
                    f"[{short_uuid}] Max steps ({max_steps}) reached! "
                    f"Possible infinite loop in scenario"
                )
                self._hangup_call(call_uuid, CallResult.NO_ANSWER)
                return

            # Normal end (shouldn't reach here)
            logger.info(f"[{short_uuid}] === CONVERSATION LOOP END ===")
            self._hangup_call(call_uuid, CallStatus.COMPLETED)

        except Exception as e:
            logger.error(f"[{short_uuid}] Call handler error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            logger.info(f"[{short_uuid}] === CALL HANDLER END ===")

    # ========================================================================
    # PHASE 1: AMD (Answering Machine Detection)
    # ========================================================================
    # NOTE: AMD implementation moved to line ~2900 (active version)
    # This section is kept for reference/documentation only

    def _execute_phase_amd_OLD_UNUSED(self, call_uuid: str) -> Dict[str, Any]:
        """
        PHASE 1: AMD (Answering Machine Detection)

        Steps:
        1. Record audio for AMD_MAX_DURATION (1.5s)
        2. Transcribe with Faster-Whisper (GPU, already warm)
        3. Detect HUMAN/MACHINE with keywords matching

        Returns:
            {
                "result": "HUMAN" | "MACHINE" | "UNKNOWN",
                "confidence": 0.0-1.0,
                "transcription": "...",
                "keywords_matched": [...],
                "latencies": {
                    "record_ms": 1500.0,
                    "transcribe_ms": 150.0,
                    "detect_ms": 5.0,
                    "total_ms": 1655.0
                }
            }
        """
        phase_start = time.time()
        short_uuid = call_uuid[:8]

        # PHASE 1 START - Colored log (YELLOW panel with double border)
        self.clog.phase1_start(uuid=short_uuid)

        # ===================================================================
        # STEP 1: Record audio (1.5s default)
        # ===================================================================
        logger.info(
            f"[{short_uuid}] AMD Step 1/3: Recording {config.AMD_MAX_DURATION}s audio..."
        )

        record_start = time.time()
        audio_path = f"/tmp/amd_{call_uuid}.wav"

        record_success = self._record_audio(
            call_uuid,
            duration=config.AMD_MAX_DURATION,
            filename=audio_path
        )

        record_latency_ms = (time.time() - record_start) * 1000

        if not record_success:
            logger.error(f"[{short_uuid}] AMD: Recording failed!")
            return {
                "result": "UNKNOWN",
                "confidence": 0.0,
                "transcription": "",
                "keywords_matched": [],
                "error": "recording_failed",
                "latencies": {
                    "record_ms": record_latency_ms,
                    "transcribe_ms": 0.0,
                    "detect_ms": 0.0,
                    "total_ms": (time.time() - phase_start) * 1000
                }
            }

        logger.info(
            f"[{short_uuid}] AMD Step 1/3: Recording completed "
            f"(latency: {record_latency_ms:.0f}ms)"
        )

        # ===================================================================
        # STEP 2: Transcribe with Faster-Whisper (GPU, already warm)
        # ===================================================================
        logger.info(f"[{short_uuid}] AMD Step 2/3: Transcribing audio...")

        transcribe_start = time.time()
        stt_result = self.stt_service.transcribe_file(audio_path)
        transcribe_latency_ms = (time.time() - transcribe_start) * 1000

        transcription = stt_result.get("text", "").strip()

        logger.info(
            f"[{short_uuid}] AMD Step 2/3: Transcription completed "
            f"(latency: {transcribe_latency_ms:.0f}ms) "
            f"-> '{transcription[:50]}{'...' if len(transcription) > 50 else ''}'"
        )

        # ===================================================================
        # STEP 3: AMD Detection (keywords matching)
        # ===================================================================
        logger.info(f"[{short_uuid}] AMD Step 3/3: Detecting HUMAN/MACHINE...")

        detect_start = time.time()
        amd_result = self.amd_service.detect(transcription)
        detect_latency_ms = (time.time() - detect_start) * 1000

        result = amd_result["result"]
        confidence = amd_result["confidence"]
        keywords_matched = amd_result.get("keywords_matched", [])

        logger.info(
            f"[{short_uuid}] AMD Step 3/3: Detection completed "
            f"(latency: {detect_latency_ms:.0f}ms) "
            f"-> {result} (confidence: {confidence:.2f})"
        )

        if keywords_matched:
            logger.info(
                f"[{short_uuid}] AMD: Keywords matched: {keywords_matched[:3]}"
            )

        # ===================================================================
        # Cleanup & Summary
        # ===================================================================
        total_latency_ms = (time.time() - phase_start) * 1000

        # Cleanup audio file
        try:
            Path(audio_path).unlink()
        except Exception as e:
            logger.warning(f"[{short_uuid}] Failed to cleanup audio file: {e}")

        # PHASE 1 END - Colored log (YELLOW panel with latency)
        self.clog.phase1_end(total_latency_ms, uuid=short_uuid)
        logger.info(f"[{short_uuid}] Result: {result}")

        return {
            "result": result,
            "confidence": confidence,
            "transcription": transcription,
            "keywords_matched": keywords_matched,
            "latencies": {
                "record_ms": record_latency_ms,
                "transcribe_ms": transcribe_latency_ms,
                "detect_ms": detect_latency_ms,
                "total_ms": total_latency_ms
            }
        }

    # ========================================================================
    # PHASE 2: PLAYING AUDIO (with barge-in detection)
    # ========================================================================

    def _execute_phase_playing(
        self,
        call_uuid: str,
        audio_path: str,
        enable_barge_in: bool = True
    ) -> Dict[str, Any]:
        """
        PHASE 2: PLAYING AUDIO (with barge-in detection)

        Steps:
        1. Start audio playback (uuid_broadcast)
        2. Monitor VAD in parallel (if barge_in enabled)
        3. If speech detected > BARGE_IN_THRESHOLD -> smooth stop after 0.3s
        4. Return playback result

        Args:
            call_uuid: Call UUID
            audio_path: Path to audio file to play
            enable_barge_in: Enable barge-in detection (default: True)

        Returns:
            {
                "completed": True | False,
                "interrupted": True | False,
                "barge_in_at": 2.5,  # seconds into audio
                "speech_duration": 1.8,  # seconds of speech detected
                "latencies": {
                    "play_start_ms": 50.0,
                    "vad_overhead_ms": 30.0,
                    "total_ms": 3500.0
                }
            }
        """
        phase_start = time.time()
        short_uuid = call_uuid[:8]

        # Get audio duration for display and verification
        audio_duration = self._get_audio_duration(audio_path)

        # PHASE 2 START - Colored log (GREEN panel with heavy border)
        self.clog.phase2_start(
            Path(audio_path).name,
            uuid=short_uuid,
            duration_seconds=audio_duration
        )

        # Check audio file exists
        if not Path(audio_path).exists():
            logger.error(f"[{short_uuid}] Audio file not found: {audio_path}")
            return {
                "completed": False,
                "interrupted": False,
                "error": "audio_file_not_found",
                "latencies": {
                    "play_start_ms": 0.0,
                    "vad_overhead_ms": 0.0,
                    "total_ms": (time.time() - phase_start) * 1000
                }
            }

        # Play audio with or without barge-in
        if enable_barge_in:
            result = self._play_audio_with_bargein(call_uuid, audio_path)
        else:
            result = self._play_audio(call_uuid, audio_path)

        total_latency_ms = (time.time() - phase_start) * 1000

        # PHASE 2 END - Colored log (GREEN panel)
        if result.get("interrupted"):
            self.clog.warning(
                f"INTERRUPTED at {result.get('barge_in_at', 0):.1f}s "
                f"(speech: {result.get('speech_duration', 0):.1f}s)",
                uuid=short_uuid
            )
        self.clog.phase2_end(total_latency_ms, uuid=short_uuid)

        result["latencies"]["total_ms"] = total_latency_ms
        return result

    def _play_audio_with_bargein(self, call_uuid: str, audio_path: str) -> Dict[str, Any]:
        """
        Play audio with barge-in detection

        Architecture:
        - Main thread: Start audio playback (uuid_broadcast)
        - VAD thread: Monitor audio frames for speech
        - If speech > BARGE_IN_THRESHOLD -> set flag
        - Main thread: Check flag, wait SMOOTH_DELAY, then stop

        Returns:
            {
                "completed": True | False,
                "interrupted": True | False,
                "barge_in_at": 2.5,
                "speech_duration": 1.8,
                "latencies": {...}
            }
        """
        short_uuid = call_uuid[:8]
        play_start_time = time.time()

        # Initialize barge-in tracking
        self.barge_in_active[call_uuid] = {
            "detected": False,
            "speech_start": None,
            "speech_duration": 0.0,
            "barge_in_at": 0.0,
            "stop_monitoring": False
        }

        # ===================================================================
        # STEP 1: Start audio playback (non-blocking)
        # ===================================================================
        logger.info(f"[{short_uuid}] Playing Step 1/3: Starting audio playback...")

        play_cmd_start = time.time()
        # uuid_broadcast <uuid> <path> [both|aleg|bleg]
        cmd = f"uuid_broadcast {call_uuid} {audio_path} aleg"
        result = self._execute_esl_command(cmd)

        if not result or "+OK" not in result:
            logger.error(f"[{short_uuid}] Audio playback failed: {result}")
            return {
                "completed": False,
                "interrupted": False,
                "error": "playback_start_failed",
                "latencies": {
                    "play_start_ms": (time.time() - play_cmd_start) * 1000,
                    "vad_overhead_ms": 0.0
                }
            }

        play_start_latency_ms = (time.time() - play_cmd_start) * 1000

        logger.info(
            f"[{short_uuid}] Playing Step 1/3: Playback started "
            f"(latency: {play_start_latency_ms:.0f}ms)"
        )

        # ===================================================================
        # STEP 2: Start VAD monitoring thread
        # ===================================================================
        logger.info(f"[{short_uuid}] Playing Step 2/3: Starting VAD monitoring...")

        vad_start_time = time.time()

        vad_thread = threading.Thread(
            target=self._monitor_barge_in,
            args=(call_uuid, play_start_time),
            daemon=True
        )
        vad_thread.start()

        logger.debug(f"[{short_uuid}] VAD monitoring thread started")

        # ===================================================================
        # STEP 3: Wait for playback completion or barge-in
        # ===================================================================
        logger.info(f"[{short_uuid}] Playing Step 3/3: Monitoring for barge-in...")

        # Get audio duration (estimate from file)
        try:
            import wave
            with wave.open(audio_path, 'r') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                audio_duration = frames / float(rate)
        except Exception as e:
            logger.warning(f"[{short_uuid}] Could not get audio duration: {e}")
            audio_duration = 10.0  # Default fallback

        logger.debug(f"[{short_uuid}] Audio duration: {audio_duration:.1f}s")

        # Poll barge-in status every 100ms
        poll_interval = 0.1
        elapsed = 0.0

        while elapsed < audio_duration:
            time.sleep(poll_interval)
            elapsed = time.time() - play_start_time

            # Check if barge-in detected
            if self.barge_in_active[call_uuid]["detected"]:
                barge_in_info = self.barge_in_active[call_uuid]

                logger.info(
                    f"[{short_uuid}] BARGE-IN DETECTED! "
                    f"Speech duration: {barge_in_info['speech_duration']:.1f}s, "
                    f"At: {barge_in_info['barge_in_at']:.1f}s into audio"
                )

                # Smooth delay before interruption
                logger.info(
                    f"[{short_uuid}] Applying smooth delay "
                    f"({config.BARGE_IN_SMOOTH_DELAY}s)..."
                )
                time.sleep(config.BARGE_IN_SMOOTH_DELAY)

                # Stop audio playback
                logger.info(f"[{short_uuid}] Stopping audio playback...")
                self._stop_audio(call_uuid)

                # Stop VAD monitoring
                self.barge_in_active[call_uuid]["stop_monitoring"] = True

                vad_overhead_ms = (time.time() - vad_start_time) * 1000

                logger.info(
                    f"[{short_uuid}] Playback interrupted after "
                    f"{elapsed:.1f}s (VAD overhead: {vad_overhead_ms:.0f}ms)"
                )

                return {
                    "completed": False,
                    "interrupted": True,
                    "barge_in_at": barge_in_info["barge_in_at"],
                    "speech_duration": barge_in_info["speech_duration"],
                    "latencies": {
                        "play_start_ms": play_start_latency_ms,
                        "vad_overhead_ms": vad_overhead_ms
                    }
                }

        # Playback completed without interruption
        self.barge_in_active[call_uuid]["stop_monitoring"] = True

        vad_overhead_ms = (time.time() - vad_start_time) * 1000

        logger.info(
            f"[{short_uuid}] Playback completed without interruption "
            f"(duration: {elapsed:.1f}s, VAD overhead: {vad_overhead_ms:.0f}ms)"
        )

        return {
            "completed": True,
            "interrupted": False,
            "barge_in_at": 0.0,
            "speech_duration": 0.0,
            "latencies": {
                "play_start_ms": play_start_latency_ms,
                "vad_overhead_ms": vad_overhead_ms
            }
        }

    def _monitor_barge_in(self, call_uuid: str, playback_start_time: float):
        """
        Monitor audio stream for barge-in detection (VAD thread)

        This runs in a separate thread during audio playback.
        Monitors VAD frames and detects speech > BARGE_IN_THRESHOLD.

        Args:
            call_uuid: Call UUID
            playback_start_time: Time when playback started

        Updates:
            self.barge_in_active[call_uuid] with detection results
        """
        short_uuid = call_uuid[:8]

        logger.debug(f"[{short_uuid}] VAD monitoring started")

        # VAD parameters
        sample_rate = 8000  # 8kHz (FreeSWITCH default)
        frame_duration_ms = 30  # 30ms frames (WebRTC VAD standard)
        frame_size = int(sample_rate * frame_duration_ms / 1000)  # 240 samples

        # Speech tracking
        speech_frames = 0
        total_frames = 0
        consecutive_speech_frames = 0
        speech_start_time = None

        # Thresholds
        frames_per_second = 1000 / frame_duration_ms  # ~33 frames/s
        threshold_frames = int(config.BARGE_IN_THRESHOLD * frames_per_second)

        logger.debug(
            f"[{short_uuid}] VAD config: "
            f"frame={frame_duration_ms}ms, "
            f"threshold={config.BARGE_IN_THRESHOLD}s "
            f"({threshold_frames} frames)"
        )

        # TODO: In a real implementation, we would:
        # 1. Hook into FreeSWITCH media stream to get raw audio frames
        # 2. Use uuid_record + tail -f to read frames in real-time
        # 3. Or use mod_audio_stream for direct frame access
        #
        # For now, we simulate VAD monitoring with uuid_record approach
        # This is a simplified implementation that records audio in parallel

        try:
            # Start recording in parallel for VAD monitoring
            vad_record_path = f"/tmp/vad_{call_uuid}.wav"

            # Record with short segments for real-time monitoring
            # In production, use streaming approach with mod_audio_stream
            record_cmd = f"uuid_record {call_uuid} start {vad_record_path}"
            self._execute_esl_command(record_cmd)

            logger.debug(f"[{short_uuid}] VAD recording started: {vad_record_path}")

            # Monitor loop
            last_check_size = 0
            check_interval = 0.1  # Check every 100ms

            while not self.barge_in_active[call_uuid]["stop_monitoring"]:
                time.sleep(check_interval)
                total_frames += 1

                # Check if recording file is growing (indicates audio input)
                try:
                    if Path(vad_record_path).exists():
                        current_size = Path(vad_record_path).stat().st_size

                        # If file is growing, assume speech is being recorded
                        # This is a simplified detection - real VAD would analyze frames
                        if current_size > last_check_size:
                            # File growing = potential speech
                            # In real implementation, we would:
                            # 1. Read the new audio frames
                            # 2. Run VAD on each 30ms frame
                            # 3. Count consecutive speech frames

                            # Simplified: Assume speech if file grows significantly
                            growth = current_size - last_check_size
                            bytes_per_frame = frame_size * 2  # 16-bit samples

                            if growth > bytes_per_frame * 2:  # At least 2 frames of data
                                consecutive_speech_frames += 1

                                if speech_start_time is None:
                                    speech_start_time = time.time()
                                    logger.debug(
                                        f"[{short_uuid}] VAD: Speech detected, "
                                        f"starting counter..."
                                    )

                                speech_duration = time.time() - speech_start_time

                                # Check if threshold reached
                                if consecutive_speech_frames >= threshold_frames:
                                    # BARGE-IN DETECTED!
                                    elapsed_time = time.time() - playback_start_time

                                    logger.info(
                                        f"[{short_uuid}] VAD: BARGE-IN THRESHOLD REACHED! "
                                        f"Frames: {consecutive_speech_frames}/{threshold_frames}, "
                                        f"Duration: {speech_duration:.1f}s"
                                    )

                                    self.barge_in_active[call_uuid].update({
                                        "detected": True,
                                        "speech_start": speech_start_time,
                                        "speech_duration": speech_duration,
                                        "barge_in_at": elapsed_time
                                    })

                                    # Stop monitoring (main thread will handle stop)
                                    break

                            else:
                                # No significant growth = silence
                                consecutive_speech_frames = 0
                                speech_start_time = None

                            last_check_size = current_size

                except Exception as e:
                    logger.debug(f"[{short_uuid}] VAD check error: {e}")
                    continue

            # Cleanup
            logger.debug(f"[{short_uuid}] VAD monitoring stopped")

            # Stop recording
            stop_cmd = f"uuid_record {call_uuid} stop {vad_record_path}"
            self._execute_esl_command(stop_cmd)

            # Cleanup VAD file
            try:
                Path(vad_record_path).unlink()
            except:
                pass

        except Exception as e:
            logger.error(f"[{short_uuid}] VAD monitoring error: {e}")

    def _play_audio(self, call_uuid: str, audio_path: str) -> Dict[str, Any]:
        """
        Play audio without barge-in detection (simple blocking playback)

        Args:
            call_uuid: Call UUID
            audio_path: Path to audio file

        Returns:
            {
                "completed": True | False,
                "interrupted": False,
                "latencies": {...}
            }
        """
        short_uuid = call_uuid[:8]
        play_start = time.time()

        logger.info(f"[{short_uuid}] Playing audio (no barge-in): {audio_path}")

        # Start playback
        cmd = f"uuid_broadcast {call_uuid} {audio_path} aleg"
        result = self._execute_esl_command(cmd)

        if not result or "+OK" not in result:
            logger.error(f"[{short_uuid}] Playback failed: {result}")
            return {
                "completed": False,
                "interrupted": False,
                "error": "playback_failed",
                "latencies": {
                    "play_start_ms": (time.time() - play_start) * 1000,
                    "vad_overhead_ms": 0.0
                }
            }

        # Get audio duration
        try:
            import wave
            with wave.open(audio_path, 'r') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                audio_duration = frames / float(rate)
        except:
            audio_duration = 5.0

        # Wait for playback to complete
        time.sleep(audio_duration)

        logger.info(f"[{short_uuid}] Playback completed ({audio_duration:.1f}s)")

        return {
            "completed": True,
            "interrupted": False,
            "latencies": {
                "play_start_ms": (time.time() - play_start) * 1000,
                "vad_overhead_ms": 0.0
            }
        }

    def _stop_audio(self, call_uuid: str):
        """
        Stop audio playback immediately

        Args:
            call_uuid: Call UUID
        """
        short_uuid = call_uuid[:8]

        try:
            # uuid_break <uuid> [all|aleg|bleg]
            cmd = f"uuid_break {call_uuid} all"
            result = self._execute_esl_command(cmd)

            logger.debug(f"[{short_uuid}] Audio stopped: {result}")

        except Exception as e:
            logger.error(f"[{short_uuid}] Stop audio error: {e}")

    # ========================================================================
    # PHASE 3: WAITING RESPONSE (listen to client with silence detection)
    # ========================================================================

    def _execute_phase_waiting(
        self,
        call_uuid: str,
        max_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        PHASE 3: WAITING RESPONSE (listen to client)

        Steps:
        1. Start recording client response
        2. Monitor for silence (SILENCE_THRESHOLD = 0.6s)
        3. Stop recording when silence detected OR timeout
        4. Transcribe response with Faster-Whisper
        5. Return transcription + metadata

        Args:
            call_uuid: Call UUID
            max_duration: Max waiting duration (default: WAITING_TIMEOUT from config)

        Returns:
            {
                "transcription": "...",
                "detected_silence": True | False,
                "timeout": True | False,
                "duration": 3.5,  # seconds recorded
                "latencies": {
                    "record_ms": 3500.0,
                    "transcribe_ms": 150.0,
                    "total_ms": 3650.0
                }
            }
        """
        phase_start = time.time()
        short_uuid = call_uuid[:8]

        if max_duration is None:
            max_duration = config.WAITING_TIMEOUT

        # PHASE 3 START - Colored log (MAGENTA panel with rounded border)
        self.clog.phase3_start(uuid=short_uuid)

        # ===================================================================
        # STEP 1: Start recording with silence detection
        # ===================================================================
        logger.info(f"[{short_uuid}] Waiting Step 1/3: Starting recording...")

        record_start = time.time()
        audio_path = f"/tmp/waiting_{call_uuid}.wav"

        # Record with silence detection
        record_result = self._record_with_silence_detection(
            call_uuid,
            audio_path,
            silence_threshold=config.SILENCE_THRESHOLD,
            max_duration=max_duration
        )

        record_latency_ms = (time.time() - record_start) * 1000

        if not record_result["success"]:
            logger.error(f"[{short_uuid}] Waiting: Recording failed!")
            return {
                "transcription": "",
                "detected_silence": False,
                "timeout": False,
                "duration": 0.0,
                "error": "recording_failed",
                "latencies": {
                    "record_ms": record_latency_ms,
                    "transcribe_ms": 0.0,
                    "total_ms": (time.time() - phase_start) * 1000
                }
            }

        logger.info(
            f"[{short_uuid}] Waiting Step 1/3: Recording completed "
            f"(duration: {record_result['duration']:.1f}s, "
            f"silence: {record_result['detected_silence']}, "
            f"timeout: {record_result['timeout']})"
        )

        # ===================================================================
        # STEP 2: Check if we have audio to transcribe
        # ===================================================================
        if record_result['duration'] < 0.3:
            # Too short, probably just silence
            logger.warning(
                f"[{short_uuid}] Waiting: Recording too short "
                f"({record_result['duration']:.1f}s) - assuming silence"
            )

            # Cleanup
            try:
                Path(audio_path).unlink()
            except:
                pass

            return {
                "transcription": "",
                "detected_silence": True,
                "timeout": record_result['timeout'],
                "duration": record_result['duration'],
                "latencies": {
                    "record_ms": record_latency_ms,
                    "transcribe_ms": 0.0,
                    "total_ms": (time.time() - phase_start) * 1000
                }
            }

        # ===================================================================
        # STEP 3: Transcribe client response
        # ===================================================================
        logger.info(f"[{short_uuid}] Waiting Step 2/3: Transcribing response...")

        transcribe_start = time.time()
        stt_result = self.stt_service.transcribe_file(audio_path)
        transcribe_latency_ms = (time.time() - transcribe_start) * 1000

        transcription = stt_result.get("text", "").strip()

        logger.info(
            f"[{short_uuid}] Waiting Step 2/3: Transcription completed "
            f"(latency: {transcribe_latency_ms:.0f}ms) "
            f"-> '{transcription[:50]}{'...' if len(transcription) > 50 else ''}'"
        )

        # ===================================================================
        # Cleanup & Summary
        # ===================================================================
        total_latency_ms = (time.time() - phase_start) * 1000

        # Cleanup audio file
        try:
            Path(audio_path).unlink()
        except Exception as e:
            logger.warning(f"[{short_uuid}] Failed to cleanup audio file: {e}")

        # PHASE 3 END - Colored log (MAGENTA panel)
        self.clog.phase3_end(total_latency_ms, uuid=short_uuid)

        return {
            "transcription": transcription,
            "detected_silence": record_result['detected_silence'],
            "timeout": record_result['timeout'],
            "duration": record_result['duration'],
            "latencies": {
                "record_ms": record_latency_ms,
                "transcribe_ms": transcribe_latency_ms,
                "total_ms": total_latency_ms
            }
        }

    def _execute_phase_waiting_streaming(
        self,
        call_uuid: str,
        max_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        PHASE 3: WAITING RESPONSE avec Streaming ASR (Vosk)

        Utilise uuid_audio_fork + WebSocket Vosk pour détection silence temps réel.
        Arrête dès que 0.8s de silence détecté (au lieu d'attendre timeout complet).

        Args:
            call_uuid: Call UUID
            max_duration: Max waiting duration (default: WAITING_TIMEOUT)

        Returns:
            {
                "transcription": "...",
                "detected_silence": True | False,
                "timeout": True | False,
                "duration": 2.3,  # seconds
                "latencies": {"total_ms": 2300.0}
            }
        """
        phase_start = time.time()
        short_uuid = call_uuid[:8]

        if max_duration is None:
            max_duration = config.WAITING_TIMEOUT

        # Calculate gap Phase 2→3
        gap_phase2_3 = 0
        if call_uuid in self.call_sessions and "phase2_end_timestamp" in self.call_sessions[call_uuid]:
            gap_phase2_3 = (phase_start - self.call_sessions[call_uuid]["phase2_end_timestamp"]) * 1000

        self.clog.phase3_start(uuid=short_uuid)

        # État détection
        detection_state = {
            "transcription": "",
            "final_received": False,  # ← FLAG pour savoir si FINAL reçu (comme AMD)
            "speech_ended": False,
            "silence_detected": False,
            "speech_detected": False,  # ← FLAG pour savoir si speech_start reçu (évite silence timeout)
            "last_update": time.time(),
            # Timestamps pour analyse latence détaillée
            "first_partial_timestamp": None,  # Quand premier PARTIAL reçu
            "last_partial_timestamp": None,   # Quand dernier PARTIAL reçu
            "speech_end_timestamp": None,     # Quand SPEECH_END reçu
            "partial_count": 0,               # Nombre de PARTIAL reçus
            "monitoring_start": None          # Timestamp début monitoring (pour callback)
        }

        def streaming_callback(event_data):
            """Callback pour events Streaming ASR"""
            event = event_data.get("event")
            logger.debug(f"🔔 [{short_uuid}] CALLBACK: event={event}")

            if event == "speech_start":
                detection_state["speech_detected"] = True  # ← Évite silence timeout
                logger.info(f"🗣️ [{short_uuid}] Speech START detected in Phase 3")

            elif event == "transcription":
                # Mise à jour transcription
                text = event_data.get("text", "")
                trans_type = event_data.get("type", "unknown")

                if trans_type == "final":
                    # Concaténer si on a déjà du contenu (évite perte sur multiples FINAL)
                    if text:
                        existing = detection_state.get("transcription", "")
                        if existing and len(existing.split()) >= 1:
                            # On a déjà au moins 1 mot → concaténer
                            detection_state["transcription"] = f"{existing} {text}"
                        else:
                            # Premier FINAL ou existant vide → écraser
                            detection_state["transcription"] = text
                        # Afficher transcription avec panel Rich visible
                        self.clog.transcription(text, uuid=short_uuid, latency_ms=0)
                    elif not detection_state.get("transcription"):
                        # FINAL vide et pas de transcription → garder vide (silence)
                        detection_state["transcription"] = ""
                        logger.info(
                            f"📝 [{short_uuid}] FINAL transcription (empty - no text detected)"
                        )
                    # Sinon: FINAL vide mais on a du contenu → ne pas écraser
                    detection_state["final_received"] = True
                    detection_state["last_update"] = time.time()
                else:  # partial
                    # Tracker timestamps pour analyse latence
                    current_time = time.time()
                    if detection_state["first_partial_timestamp"] is None:
                        detection_state["first_partial_timestamp"] = current_time
                    detection_state["last_partial_timestamp"] = current_time
                    detection_state["partial_count"] += 1

                    # Calculer temps écoulé depuis début Phase 3
                    elapsed_ms = 0
                    if detection_state["monitoring_start"]:
                        elapsed_ms = (current_time - detection_state["monitoring_start"]) * 1000

                    # Afficher partial avec timestamp et comptage mots
                    word_count = len(text.split()) if text else 0
                    logger.info(
                        f"📝 [{short_uuid}] PARTIAL #{detection_state['partial_count']} at {elapsed_ms:.0f}ms: "
                        f"'{text}' ({word_count} words)"
                    )

            elif event == "speech_end":
                # Fin de parole détectée (silence > 0.8s)
                detection_state["speech_ended"] = True
                detection_state["silence_detected"] = True
                detection_state["speech_end_timestamp"] = time.time()

                # Calculer temps écoulé depuis début Phase 3
                if detection_state["monitoring_start"]:
                    elapsed_ms = (detection_state["speech_end_timestamp"] - detection_state["monitoring_start"]) * 1000
                    logger.info(
                        f"🤐 [{short_uuid}] SPEECH_END at {elapsed_ms:.0f}ms "
                        f"(silence: {event_data.get('silence_duration', 0):.1f}s, {detection_state['partial_count']} partials received)"
                    )
                else:
                    silence_duration = event_data.get("silence_duration", 0)
                    logger.info(
                        f"🤐 [{short_uuid}] SPEECH_END "
                        f"(silence: {silence_duration:.1f}s, {detection_state['partial_count']} partials received)"
                    )
            else:
                logger.debug(f"🔔 [{short_uuid}] CALLBACK unknown event: {event}")

        try:
            # Register callback
            self.streaming_asr.register_callback(call_uuid, streaming_callback)

            # Démarrer audio fork → WebSocket
            fork_start = time.time()
            ws_url = (
                f"ws://{config.STREAMING_ASR_HOST}:{config.STREAMING_ASR_PORT}"
                f"/stream/{call_uuid}"
            )
            fork_cmd = f"uuid_audio_fork {call_uuid} start {ws_url} mono 16000"
            fork_result = self._execute_esl_command(fork_cmd)

            if not fork_result or "+OK" not in fork_result:
                logger.error(f"❌ [{short_uuid}] Audio fork failed: {fork_result}")
                # Fallback méthode file-based
                self.streaming_asr.unregister_callback(call_uuid)
                return self._execute_phase_waiting(call_uuid, max_duration)

            fork_latency = (time.time() - fork_start) * 1000

            # === ATTENDRE INITIALISATION STREAM (évite race condition) ===
            stream_wait_start = time.time()
            max_stream_wait = 2.0  # Max 2s d'attente pour établissement WebSocket

            while call_uuid not in self.streaming_asr.active_streams:
                if (time.time() - stream_wait_start) > max_stream_wait:
                    logger.error(
                        f"❌ [{short_uuid}] WebSocket stream not initialized after {max_stream_wait}s, "
                        f"falling back to file-based method"
                    )
                    try:
                        self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                    except:
                        pass
                    self.streaming_asr.unregister_callback(call_uuid)
                    return self._execute_phase_waiting(call_uuid, max_duration)
                time.sleep(0.01)  # Poll every 10ms

            stream_init_latency = (time.time() - stream_wait_start) * 1000

            # === ENERGY GATE: Appliquer noise floor calibré (si disponible) ===
            if call_uuid in self.call_sessions:
                saved_noise_floor = self.call_sessions[call_uuid].get("noise_floor_rms", 0)
                if saved_noise_floor > 0:
                    self.streaming_asr.set_noise_floor(call_uuid, saved_noise_floor)

            # Définir monitoring_start APRÈS stream initialisé pour calculs précis
            monitoring_start = time.time()
            detection_state["monitoring_start"] = monitoring_start

            # Log état initial du streaming ASR
            logger.info(
                f"🎤 [{short_uuid}] Phase 3 streaming started: "
                f"fork={fork_latency:.0f}ms, stream_init={stream_init_latency:.0f}ms"
            )

            # Attendre fin parole OU timeout
            timeout = max_duration
            last_check_log = 0  # Pour logger toutes les secondes

            while (time.time() - monitoring_start) < timeout:
                current_time = time.time()
                elapsed = current_time - monitoring_start

                # ===== ULTRA-FAST HANGUP DETECTION (20ms polling) =====
                # Vérification 1: Flag session (setté par HANGUP handler)
                session = self.call_sessions.get(call_uuid, {})
                if session.get("hangup_detected", False):
                    hangup_ts = session.get("hangup_timestamp", 0)
                    detection_delay_ms = (current_time - hangup_ts) * 1000
                    logger.warning(
                        f"🚨 [{short_uuid}] HANGUP FLAG detected in Phase 3! "
                        f"Detection delay: {detection_delay_ms:.1f}ms, "
                        f"elapsed in phase: {elapsed:.1f}s - STOPPING IMMEDIATELY!"
                    )
                    break

                # Vérification 2: ESL DIRECT (instantané!)
                if not self._channel_exists(call_uuid):
                    logger.warning(
                        f"🚨 [{short_uuid}] Channel NO LONGER EXISTS (ESL check) - STOPPING Phase 3!"
                    )
                    break

                # Legacy check (moins fiable)
                if call_uuid not in self.active_calls:
                    logger.info(
                        f"[{short_uuid}] Call removed from active_calls during Phase 3"
                    )
                    break

                # Log état toutes les secondes pour debug (VERBOSE)
                if elapsed - last_check_log >= 1.0:
                    # Vérifier si callback est enregistré
                    callback_registered = call_uuid in self.streaming_asr.callbacks
                    # Vérifier si stream actif
                    stream_active = call_uuid in self.streaming_asr.active_streams

                    logger.info(
                        f"📊 [{short_uuid}] Phase 3 status: elapsed={elapsed:.1f}s, "
                        f"partials={detection_state['partial_count']}, "
                        f"speech_ended={detection_state['speech_ended']}, "
                        f"callback={callback_registered}, stream={stream_active}"
                    )
                    last_check_log = elapsed

                # === SILENCE TIMEOUT (si pas de parole détectée) ===
                # Si le client ne parle pas après WAITING_SILENCE_TIMEOUT → retry_silence
                # On vérifie: pas de partial ET pas de speech_start (sinon Vosk est en train de transcrire)
                if (detection_state["partial_count"] == 0
                    and not detection_state["speech_ended"]
                    and not detection_state["speech_detected"]):  # ← Ne pas timeout si speech détecté
                    if elapsed >= config.WAITING_SILENCE_TIMEOUT:
                        # Log détaillé avant de déclencher silence
                        callback_registered = call_uuid in self.streaming_asr.callbacks
                        stream_active = call_uuid in self.streaming_asr.active_streams
                        logger.warning(
                            f"🔇 [{short_uuid}] Silence timeout in Phase 3: {elapsed:.1f}s >= "
                            f"{config.WAITING_SILENCE_TIMEOUT}s → triggering retry_silence "
                            f"(callback={callback_registered}, stream={stream_active})"
                        )
                        # Marquer comme silence pour déclencher retry_silence
                        detection_state["silence_detected"] = True
                        break

                if detection_state["speech_ended"]:
                    speech_end_time = (time.time() - monitoring_start) * 1000

                    # CRITIQUE: Attendre le FINAL (max 1500ms) - plus long que AMD
                    # Vosk peut prendre 100-600ms selon longueur de la phrase
                    final_wait_start = time.time()
                    max_final_wait = 1.5  # 1500ms pour gérer phrases longues

                    while (time.time() - final_wait_start) < max_final_wait:
                        # HANGUP check even during FINAL wait!
                        session = self.call_sessions.get(call_uuid, {})
                        if session.get("hangup_detected", False):
                            hangup_ts = session.get("hangup_timestamp", 0)
                            detection_delay_ms = (time.time() - hangup_ts) * 1000
                            logger.warning(
                                f"🚨 [{short_uuid}] HANGUP during FINAL wait! "
                                f"Detection delay: {detection_delay_ms:.1f}ms - ABORTING!"
                            )
                            break

                        if detection_state["final_received"]:
                            break
                        time.sleep(0.05)  # Poll every 50ms

                    final_wait_latency = (time.time() - final_wait_start) * 1000

                    # Si pas de FINAL après 1500ms, continuer quand même
                    if not detection_state["final_received"]:
                        logger.warning(
                            f"⚠️ [{short_uuid}] No FINAL after {final_wait_latency:.0f}ms, using last partial"
                        )

                    break

                time.sleep(0.02)  # Poll every 20ms (5x faster than before!)

            # Stop audio fork
            stop_cmd = f"uuid_audio_fork {call_uuid} stop"
            self._execute_esl_command(stop_cmd)
            logger.info(f"🛑 [{short_uuid}] Audio fork stopped")

            # CRITICAL: Attendre que WebSocket se ferme complètement (évite race condition)
            # Sans ce délai, le prochain fork peut démarrer avant cleanup complet
            time.sleep(0.1)
            logger.info(f"⏳ [{short_uuid}] Waited 100ms for WebSocket cleanup")

            # Unregister callback
            self.streaming_asr.unregister_callback(call_uuid)
            logger.info(f"🔓 [{short_uuid}] Callback unregistered")

            # Calculer durée
            duration = time.time() - monitoring_start
            timeout_reached = duration >= timeout

            total_latency_ms = (time.time() - phase_start) * 1000

            # Compact latency breakdown (single line) avec décomposition détaillée
            if detection_state["speech_ended"]:
                # Calculer timings précis
                first_word_ms = 0
                speaking_ms = 0
                silence_wait_ms = 0

                if detection_state["first_partial_timestamp"]:
                    first_word_ms = (detection_state["first_partial_timestamp"] - monitoring_start) * 1000

                    if detection_state["last_partial_timestamp"]:
                        speaking_ms = (detection_state["last_partial_timestamp"] - detection_state["first_partial_timestamp"]) * 1000

                        if detection_state["speech_end_timestamp"]:
                            silence_wait_ms = (detection_state["speech_end_timestamp"] - detection_state["last_partial_timestamp"]) * 1000

                logger.info(
                    f"📊 [{short_uuid}] PHASE 3: Gap={gap_phase2_3:.0f}ms | Fork={fork_latency:.0f}ms | "
                    f"FirstWord={first_word_ms:.0f}ms | Speaking={speaking_ms:.0f}ms | "
                    f"SilenceWait={silence_wait_ms:.0f}ms | FinalWait={final_wait_latency:.0f}ms | "
                    f"TOTAL={total_latency_ms:.0f}ms ({detection_state['partial_count']} partials)"
                )
            else:
                logger.info(
                    f"📊 [{short_uuid}] PHASE 3: Gap={gap_phase2_3:.0f}ms | Fork={fork_latency:.0f}ms | "
                    f"NoSpeech/Timeout | TOTAL={total_latency_ms:.0f}ms ({detection_state['partial_count']} partials)"
                )

            self.clog.phase3_end(total_latency_ms, uuid=short_uuid)

            # Store end timestamp for gap calculation Phase 3→2
            if call_uuid in self.call_sessions:
                self.call_sessions[call_uuid]["phase3_end_timestamp"] = time.time()

            return {
                "transcription": detection_state["transcription"],
                "detected_silence": detection_state["silence_detected"],
                "timeout": timeout_reached,
                "duration": duration,
                "latencies": {
                    "total_ms": total_latency_ms
                }
            }

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] Streaming ASR error: {e}", exc_info=True)

            # Cleanup
            try:
                self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                self.streaming_asr.unregister_callback(call_uuid)
            except:
                pass

            # Fallback file-based
            logger.warning(f"⚠️ [{short_uuid}] Falling back to file-based method")
            return self._execute_phase_waiting(call_uuid, max_duration)

    def _execute_phase_waiting_router(
        self,
        call_uuid: str,
        max_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Router pour PHASE 3: Sélectionne méthode streaming ou file-based

        - Si Streaming ASR disponible → utilise Vosk streaming (détection silence réelle)
        - Sinon → fallback file-based (attend timeout complet)

        Args:
            call_uuid: Call UUID
            max_duration: Max waiting duration

        Returns:
            Résultat de la méthode sélectionnée
        """
        short_uuid = call_uuid[:8]

        # Utiliser Streaming ASR si disponible (optimal)
        if (
            self.streaming_asr
            and self.streaming_asr.is_available
            and config.STREAMING_ASR_ENABLED
        ):
            logger.debug(
                f"📡 [{short_uuid}] Using Streaming ASR for PHASE 3 "
                f"(Vosk WebSocket + audio fork)"
            )
            return self._execute_phase_waiting_streaming(
                call_uuid, max_duration
            )
        else:
            # Fallback file-based (ancien système)
            logger.debug(
                f"📡 [{short_uuid}] Using file-based for PHASE 3 "
                f"(fallback method - no real silence detection)"
            )
            if max_duration is None:
                max_duration = config.WAITING_TIMEOUT
            logger.warning(
                f"⚠️ [{short_uuid}] Phase 3 will wait full timeout ({max_duration}s) "
                f"as Streaming ASR is not available"
            )
            return self._execute_phase_waiting(call_uuid, max_duration)

    def _record_with_silence_detection(
        self,
        call_uuid: str,
        filename: str,
        silence_threshold: float = 0.6,
        max_duration: float = 10.0
    ) -> Dict[str, Any]:
        """
        Record audio with silence detection

        Uses uuid_record with monitoring thread to detect silence.
        Stops recording when silence detected or max_duration reached.

        Args:
            call_uuid: Call UUID
            filename: Output .wav file path
            silence_threshold: Silence duration to trigger stop (seconds)
            max_duration: Maximum recording duration (seconds)

        Returns:
            {
                "success": True | False,
                "duration": 3.5,  # actual recording duration
                "detected_silence": True | False,
                "timeout": True | False
            }
        """
        short_uuid = call_uuid[:8]

        try:
            # Start recording
            cmd = f"uuid_record {call_uuid} start {filename}"
            result = self._execute_esl_command(cmd)

            if not result or "+OK" not in result:
                logger.error(f"[{short_uuid}] Record start failed: {result}")
                return {
                    "success": False,
                    "duration": 0.0,
                    "detected_silence": False,
                    "timeout": False
                }

            logger.debug(f"[{short_uuid}] Silence detection recording started")

            record_start = time.time()

            # Monitor file growth for silence detection
            last_size = 0
            last_growth_time = time.time()
            check_interval = 0.1  # Check every 100ms

            while True:
                time.sleep(check_interval)
                elapsed = time.time() - record_start

                # ===================================================================
                # PROACTIVE CHECK: Call still active?
                # ===================================================================
                if call_uuid not in self.active_calls:
                    logger.info(
                        f"[{short_uuid}] Call hung up during recording "
                        f"(elapsed: {elapsed:.1f}s), stopping immediately"
                    )

                    # Try to stop recording (may already be stopped by FreeSWITCH)
                    try:
                        stop_cmd = f"uuid_record {call_uuid} stop {filename}"
                        self._execute_esl_command(stop_cmd)
                    except:
                        pass

                    return {
                        "success": False,
                        "duration": elapsed,
                        "detected_silence": False,
                        "timeout": False,
                        "hangup": True  # New flag to indicate hangup detected
                    }

                # Check timeout
                if elapsed >= max_duration:
                    logger.info(
                        f"[{short_uuid}] Recording timeout "
                        f"({max_duration}s) reached"
                    )

                    # Stop recording
                    stop_cmd = f"uuid_record {call_uuid} stop {filename}"
                    self._execute_esl_command(stop_cmd)

                    return {
                        "success": True,
                        "duration": elapsed,
                        "detected_silence": False,
                        "timeout": True
                    }

                # Check file growth (indicates audio input)
                if Path(filename).exists():
                    current_size = Path(filename).stat().st_size

                    if current_size > last_size:
                        # File growing = audio being recorded
                        last_growth_time = time.time()
                        last_size = current_size

                    else:
                        # File not growing = potential silence
                        silence_duration = time.time() - last_growth_time

                        if silence_duration >= silence_threshold:
                            # Silence detected!
                            logger.info(
                                f"[{short_uuid}] Silence detected "
                                f"({silence_duration:.1f}s >= {silence_threshold}s)"
                            )

                            # Stop recording
                            stop_cmd = f"uuid_record {call_uuid} stop {filename}"
                            self._execute_esl_command(stop_cmd)

                            return {
                                "success": True,
                                "duration": elapsed,
                                "detected_silence": True,
                                "timeout": False
                            }

        except Exception as e:
            logger.error(f"[{short_uuid}] Silence detection error: {e}")
            return {
                "success": False,
                "duration": 0.0,
                "detected_silence": False,
                "timeout": False
            }

    # ========================================================================
    # CONVERSATION LOOP (MaxTurn + Qualification + Retry)
    # ========================================================================

    def _execute_conversation_step(
        self,
        call_uuid: str,
        scenario: Dict,
        step_name: str,
        session: Dict,
        retry_count: int = 0,
        calibrate_noise: bool = False
    ) -> Dict[str, Any]:
        """
        Execute one conversation step with retry logic

        This is the core conversation unit that:
        1. Plays audio (PHASE 2)
        2. Waits for response (PHASE 3)
        3. Analyzes intent
        4. Handles objections (with MaxTurn if configured)
        5. Returns next step decision

        Args:
            call_uuid: Call UUID
            scenario: Scenario dict
            step_name: Current step name
            session: Call session data
            retry_count: Current retry attempt (0-based)
            calibrate_noise: True pour calibrer le noise floor (premier step hello)

        Returns:
            {
                "success": True | False,
                "next_step": "Q1_Proprietaire" | "Bye_Failed" | None,
                "intent": "affirm" | "deny" | "objection" | ...,
                "transcription": "...",
                "retry": True | False,  # Should retry this step
                "qualification_delta": 30.0,  # Weight change for lead qualification
                "latencies": {...}
            }
        """
        step_start = time.time()
        short_uuid = call_uuid[:8]

        logger.info(
            f"[{short_uuid}] === CONVERSATION STEP: {step_name} "
            f"(retry: {retry_count}) ==="
        )

        # Get step config
        step_config = self.scenario_manager.get_step_config(scenario, step_name)

        if not step_config:
            logger.error(f"[{short_uuid}] Step not found: {step_name}")
            return {
                "success": False,
                "error": "step_not_found",
                "latencies": {"total_ms": (time.time() - step_start) * 1000}
            }

        # ===================================================================
        # RETURN_STEP SUBSTITUTION (for retry steps)
        # ===================================================================
        # Si ce step a {{return_step}} dans son intent_mapping, le remplacer
        # par la valeur sauvegardée dans la session
        intent_mapping = step_config.get("intent_mapping", {})
        return_step = session.get("return_step")

        if return_step:
            # Remplacer {{return_step}} dans tous les mappings
            for intent_key, target_step in list(intent_mapping.items()):
                if target_step == "{{return_step}}":
                    intent_mapping[intent_key] = return_step
                    logger.debug(f"[{short_uuid}] Replaced {{{{return_step}}}} with '{return_step}' for intent '{intent_key}'")

        # ===================================================================
        # STEP 1: Play audio (PHASE 2)
        # ===================================================================
        audio_path = self._get_audio_path_for_step(scenario, step_name)

        if not audio_path:
            logger.error(f"[{short_uuid}] Audio path not found for step: {step_name}")
            return {
                "success": False,
                "error": "audio_not_found",
                "latencies": {"total_ms": (time.time() - step_start) * 1000}
            }

        # Check if barge-in enabled for this step
        enable_barge_in = step_config.get("barge_in", config.BARGE_IN_ENABLED)

        playing_result = self._execute_phase_2_auto(
            call_uuid,
            audio_path,
            enable_barge_in=enable_barge_in,
            calibrate_noise=calibrate_noise
        )

        # ===================================================================
        # STEP 2: Wait for response (PHASE 3)
        # ===================================================================

        # CHECK: Si barge-in détecté, utiliser transcription de Phase 2 et SKIP Phase 3
        if playing_result.get("barged_in", False):
            # Client a interrompu pendant Phase 2 → Il a déjà parlé
            transcription = playing_result.get("transcription", "").strip()
            logger.info(
                f"[{short_uuid}] ⚡ Barge-in detected → Using Phase 2 transcription, "
                f"SKIPPING Phase 3 (client already spoke)"
            )
            logger.info(
                f"[{short_uuid}] Phase 2 transcription: '{transcription}'"
            )

            # Créer un waiting_result virtuel (pour compatibilité avec le reste du code)
            waiting_result = {
                "transcription": transcription,
                "detected_silence": False,
                "timeout": False,
                "duration": 0.0,
                "latencies": {"total_ms": 0.0}
            }
        else:
            # Pas de barge-in → Exécuter Phase 3 WAITING
            waiting_result = self._execute_phase_waiting_router(call_uuid)
            transcription = waiting_result.get("transcription", "").strip()

        # ===================================================================
        # STEP 3: Analyze intent
        # ===================================================================
        intent_result = self._analyze_intent(transcription, scenario, step_name)
        intent = intent_result["intent"]

        logger.info(
            f"[{short_uuid}] Step result: intent={intent}, "
            f"transcription='{transcription[:40]}...'"
        )

        # ===================================================================
        # STEP 4: Handle based on intent
        # ===================================================================
        intent_mapping = step_config.get("intent_mapping", {})

        # === LOGS NAVIGATION DÉTAILLÉS ===
        logger.info(f"")
        logger.info(f"{'═'*60}")
        logger.info(f"🧭 NAVIGATION - Step '{step_name}' → Intent '{intent}'")
        logger.info(f"{'═'*60}")
        logger.info(f"📋 Intent mapping disponible:")
        for k, v in intent_mapping.items():
            marker = "→" if k == intent else " "
            logger.info(f"   {marker} {k}: {v}")
        logger.info(f"{'─'*60}")

        # --- OBJECTION/QUESTION HANDLING with MaxTurn ---
        # OPTION B: question ET objection détectés via objections_db (intents_general.py supprimé)
        # TRAITEMENT IDENTIQUE pour les deux (MaxTurn loop)
        if intent == "objection" or intent == "question":
            logger.info(f"🔄 Branche: OBJECTION/QUESTION (réponse audio)")
            max_turns = self.scenario_manager.get_max_autonomous_turns(
                scenario,
                step_name
            )
            logger.info(f"   max_autonomous_turns: {max_turns}")

            if max_turns > 0:
                # Autonomous objection handling
                logger.info(
                    f"   → Démarrage boucle autonome ({max_turns} tours max)"
                )

                objection_result = self._handle_objection_autonomous(
                    call_uuid,
                    scenario,
                    step_name,
                    transcription,
                    max_turns=max_turns,
                    initial_match=intent_result  # Passer le résultat déjà trouvé
                )

                # After objection loop, check result
                if objection_result.get("force_continue"):
                    # Max not_understood reached -> Force continuation
                    next_step = intent_mapping.get("affirm")
                    logger.info(f"   ⚠️  Limite not_understood atteinte → Force continue")
                    logger.info(f"   → next_step = '{next_step}' (mapping 'affirm')")

                elif objection_result.get("resolved"):
                    # Objection resolved -> continue to affirm path
                    next_step = intent_mapping.get("affirm")
                    logger.info(f"   ✅ Objection résolue → Continue")
                    logger.info(f"   → next_step = '{next_step}' (mapping 'affirm')")

                else:
                    # Objection not resolved -> deny path
                    next_step = intent_mapping.get("deny", "bye_failed")
                    logger.info(f"   ❌ Objection NON résolue → Deny path")
                    logger.info(f"   → next_step = '{next_step}' (mapping 'deny')")

            else:
                # No MaxTurn -> direct objection mapping or deny
                next_step = intent_mapping.get("objection", intent_mapping.get("deny"))
                logger.info(f"   ℹ️  Pas de MaxTurn → mapping direct")
                logger.info(f"   → next_step = '{next_step}'")

        # --- SILENCE HANDLING ---
        elif intent == "silence":
            logger.info(f"🔄 Branche: SILENCE")
            # ALWAYS follow scenario JSON mapping for silence
            # The scenario defines the flow (e.g., hello → retry_silence → end)

            # CRITICAL: Si step terminal (is_terminal OU legacy names), forcer "end" pour éviter boucle
            is_terminal = (
                step_config.get("is_terminal", False) or
                step_name.lower() in ["bye", "bye_failed", "end"]
            )
            logger.info(f"   is_terminal: {is_terminal}")

            if is_terminal:
                next_step = "end"
                logger.info(f"   ⚠️  Step terminal → Forçage vers 'end'")
                logger.info(f"   → next_step = 'end'")
            else:
                # Get default fallback from scenario metadata (or hardcoded "bye_failed")
                default_silence_fallback = scenario.get("metadata", {}).get("fallbacks", {}).get("silence", "bye_failed")
                next_step = intent_mapping.get("silence", default_silence_fallback)
                logger.info(f"   Fallback silence: {default_silence_fallback}")
                logger.info(f"   → next_step = '{next_step}' (mapping 'silence')")

        # --- NOT_UNDERSTOOD HANDLING ---
        elif intent == "not_understood":
            logger.info(f"🔄 Branche: NOT_UNDERSTOOD")
            # Pas de match dans objections_db -> jouer step "not_understood"

            # Get fallback from intent_mapping or scenario metadata
            default_not_understood = scenario.get("metadata", {}).get("fallbacks", {}).get("not_understood", "bye_failed")
            next_step = intent_mapping.get("not_understood", default_not_understood)
            logger.info(f"   Fallback not_understood: {default_not_understood}")
            logger.info(f"   → next_step = '{next_step}'")

        # --- INSULT HANDLING ---
        elif intent == "insult":
            logger.info(f"🔄 Branche: INSULT")
            # Insulte ou demande de retrait -> raccrocher directement
            next_step = "end"
            logger.info(f"   🚫 Insulte/Retrait détecté → Raccrochage immédiat")
            logger.info(f"   → next_step = 'end'")

        # --- AFFIRM / DENY / TIME / UNSURE / OTHER ---
        else:
            logger.info(f"🔄 Branche: {intent.upper()} (navigation standard)")

            # Get next step from intent_mapping
            next_step = intent_mapping.get(intent)

            if not next_step:
                # No mapping -> try "unknown" fallback from metadata (or deny)
                logger.warning(f"   ⚠️  Pas de mapping pour '{intent}'")
                default_unknown_fallback = scenario.get("metadata", {}).get("fallbacks", {}).get("unknown", "bye_failed")
                next_step = intent_mapping.get("unknown", default_unknown_fallback)
                logger.info(f"   Fallback unknown: {default_unknown_fallback}")
                logger.info(f"   → next_step = '{next_step}'")
            else:
                logger.info(f"   ✅ Mapping trouvé: {intent} → {next_step}")
                logger.info(f"   → next_step = '{next_step}'")

        # === LOG RÉSUMÉ NAVIGATION ===
        logger.info(f"{'─'*60}")
        logger.info(f"🎯 DÉCISION FINALE: '{step_name}' → '{next_step}'")
        logger.info(f"{'═'*60}")
        logger.info(f"")

        # ===================================================================
        # STEP 5: Qualification update
        # ===================================================================
        qualification_delta = 0.0

        if step_config.get("is_determinant", False):
            # This is a qualifying question
            weight = self.scenario_manager.get_qualification_weight(scenario, step_name)

            if intent == "affirm":
                qualification_delta = weight
            elif intent == "deny":
                qualification_delta = -weight

            session["qualification_score"] = session.get("qualification_score", 0.0) + qualification_delta

            logger.info(
                f"[{short_uuid}] Qualification update: {qualification_delta:+.1f} "
                f"(total: {session['qualification_score']:.1f})"
            )

        # ===================================================================
        # SAVE RETURN_STEP (for retry steps)
        # ===================================================================
        # Si on va vers un retry step, sauvegarder le next_step prévu (affirm)
        # pour que le retry puisse y retourner après un affirm
        if next_step and next_step.startswith("retry_"):
            # Sauvegarder le step prévu si affirm (le "next step" normal)
            intended_next = intent_mapping.get("affirm")
            if intended_next:
                session["return_step"] = intended_next
                logger.info(
                    f"[{short_uuid}] Saved return_step='{intended_next}' for retry"
                )
        else:
            # Effacer return_step si on n'est plus dans un retry
            if "return_step" in session:
                del session["return_step"]

        # ===================================================================
        # Summary
        # ===================================================================
        total_latency_ms = (time.time() - step_start) * 1000

        logger.info(
            f"[{short_uuid}] === STEP END: {step_name} === "
            f"Next: {next_step}, Latency: {total_latency_ms:.0f}ms"
        )

        # Handle both return formats (streaming ASR vs fallback)
        playing_latency = (
            playing_result.get("latencies", {}).get("total_ms")
            or playing_result.get("latency_ms", 0.0)
        )
        waiting_latency = (
            waiting_result.get("latencies", {}).get("total_ms")
            or waiting_result.get("latency_ms", 0.0)
        )

        return {
            "success": True,
            "next_step": next_step,
            "intent": intent,
            "transcription": transcription,
            "retry": False,
            "qualification_delta": qualification_delta,
            "latencies": {
                "playing_ms": playing_latency,
                "waiting_ms": waiting_latency,
                "intent_ms": intent_result["latency_ms"],
                "total_ms": total_latency_ms
            }
        }

    def _handle_objection_autonomous(
        self,
        call_uuid: str,
        scenario: Dict,
        step_name: str,
        objection_text: str,
        max_turns: int = 2,
        initial_match: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Handle objection with autonomous MaxTurn loop

        Tries to find and play objection responses up to max_turns times.
        After each response, listens for client reaction.

        Args:
            call_uuid: Call UUID
            scenario: Scenario dict
            step_name: Current step name
            objection_text: Initial objection transcription
            max_turns: Maximum autonomous turns
            initial_match: Result from _analyze_intent() - réutilisé pour le premier tour

        Returns:
            {
                "resolved": True | False,
                "turns_used": 2,
                "final_intent": "affirm" | "deny" | ...,
                "latencies": {...}
            }
        """
        loop_start = time.time()
        short_uuid = call_uuid[:8]

        logger.info(
            f"[{short_uuid}] === OBJECTION LOOP START === "
            f"MaxTurn: {max_turns}"
        )

        # Get session from call_sessions
        session = self.call_sessions.get(call_uuid, {})
        if not session:
            logger.error(f"[{short_uuid}] Session not found for call_uuid")
            return {
                "resolved": False,
                "turns_used": 0,
                "final_intent": "error",
                "latencies": {"total_ms": 0}
            }

        # Charger thématique depuis scenario (metadata.theme_file)
        theme = self.scenario_manager.get_theme_file(scenario)
        current_objection = objection_text
        turns_used = 0
        not_understood_count = 0  # Counter for objections not found in DB
        max_not_understood = scenario.get("metadata", {}).get("max_not_understood", 2)

        # Pour réutiliser le intent_result entre les tours
        reaction_match = None  # Sera set après chaque réaction client

        for turn in range(max_turns):
            turns_used += 1

            logger.info(
                f"[{short_uuid}] Objection turn {turn + 1}/{max_turns}: "
                f"'{current_objection[:40]}...'"
            )

            # Find objection response
            # Réutiliser le résultat de _analyze_intent si disponible (tous les tours)
            match_to_use = None
            if turn == 0 and initial_match and initial_match.get("matched_response_id"):
                match_to_use = initial_match
                logger.info(f"[{short_uuid}] Using initial_match from _analyze_intent (no re-search)")
            elif turn > 0 and reaction_match and reaction_match.get("matched_response_id"):
                match_to_use = reaction_match
                logger.info(f"[{short_uuid}] Using reaction_match from previous turn (no re-search)")

            if match_to_use:
                # Utiliser le match déjà trouvé par _analyze_intent
                objection_matcher = ObjectionMatcher.load_objections_for_theme(theme)
                matched_id = match_to_use.get("matched_response_id", "")

                objection_result = {
                    "found": True,
                    "objection_id": matched_id,
                    "audio_file": objection_matcher.audio_paths.get(matched_id) if objection_matcher else None,
                    "response_text": objection_matcher.objections.get(matched_id, "") if objection_matcher else "",
                    "match_score": match_to_use.get("confidence", 0.0),
                    "latency_ms": 0
                }

                # Vérifier qu'on a bien un audio_file
                if not objection_result.get("audio_file"):
                    logger.warning(f"[{short_uuid}] match_to_use has no audio_file, falling back to search")
                    objection_result = self._find_objection_response(
                        current_objection,
                        theme=theme,
                        min_score=config.OBJECTION_MIN_SCORE
                    )
            else:
                # Pas de match pré-calculé: rechercher normalement
                objection_result = self._find_objection_response(
                    current_objection,
                    theme=theme,
                    min_score=config.OBJECTION_MIN_SCORE
                )

            if not objection_result.get("found"):
                # Objection not found in database
                not_understood_count += 1

                logger.warning(
                    f"[{short_uuid}] No objection match (score < threshold) "
                    f"-> not_understood {not_understood_count}/{max_not_understood}"
                )

                if not_understood_count >= max_not_understood:
                    # Max not_understood reached → Force continuation
                    logger.info(
                        f"[{short_uuid}] Max not_understood ({max_not_understood}) reached "
                        f"-> Force continue to next step"
                    )

                    total_latency_ms = (time.time() - loop_start) * 1000

                    return {
                        "resolved": False,
                        "turns_used": turns_used,
                        "final_intent": "unknown",
                        "force_continue": True,  # Flag to force continuation
                        "latencies": {"total_ms": total_latency_ms}
                    }

                # Play "not_understood" step
                logger.info(f"[{short_uuid}] Playing 'not_understood' step")

                # Execute not_understood step (Phase 2 + Phase 3)
                not_understood_result = self._execute_conversation_step(
                    call_uuid,
                    scenario,
                    "not_understood",
                    session,
                    retry_count=0
                )

                if not not_understood_result.get("success"):
                    logger.error(f"[{short_uuid}] not_understood step failed")
                    break

                # Get new transcription from client
                current_objection = not_understood_result.get("transcription", "").strip()

                logger.info(
                    f"[{short_uuid}] Client response after not_understood: '{current_objection[:40]}...'"
                )

                continue

            # Objection found → Reset not_understood counter
            not_understood_count = 0

            # Play objection response
            audio_file = objection_result.get("audio_file")

            if not audio_file:
                logger.error(f"[{short_uuid}] Objection response has no audio file")
                break

            # Build full audio path for objection
            audio_path = Path(config.FREESWITCH_SOUNDS_DIR) / theme / "objections" / audio_file

            if not audio_path.exists():
                logger.error(f"[{short_uuid}] Objection audio not found: {audio_path}")
                break

            # Play objection response (with barge-in)
            playing_result = self._execute_phase_2_auto(
                call_uuid,
                str(audio_path),
                enable_barge_in=True
            )

            # Wait for client reaction
            waiting_result = self._execute_phase_waiting_router(call_uuid)

            reaction = waiting_result.get("transcription", "").strip()

            # Analyze reaction intent
            intent_result = self._analyze_intent(reaction, scenario, step_name)
            intent = intent_result["intent"]

            # Stocker le match pour le tour suivant (si c'est une objection/question)
            if intent in ["objection", "question"] and intent_result.get("matched_response_id"):
                reaction_match = intent_result
            else:
                reaction_match = None

            logger.info(
                f"[{short_uuid}] Objection turn {turn + 1} result: "
                f"intent={intent}, reaction='{reaction[:30]}...'"
            )

            # Check if objection resolved
            if intent == "affirm":
                logger.info(f"[{short_uuid}] Objection RESOLVED on turn {turn + 1}")

                total_latency_ms = (time.time() - loop_start) * 1000

                return {
                    "resolved": True,
                    "turns_used": turns_used,
                    "final_intent": intent,
                    "latencies": {"total_ms": total_latency_ms}
                }

            elif intent == "deny" or intent == "insult":
                # Client refuses or insults - end loop
                logger.info(f"[{short_uuid}] {intent.upper()} detected -> End objection loop")

                total_latency_ms = (time.time() - loop_start) * 1000

                return {
                    "resolved": False,
                    "turns_used": turns_used,
                    "final_intent": intent,
                    "latencies": {"total_ms": total_latency_ms}
                }

            elif intent == "silence" or intent == "unknown":
                # Continue loop
                logger.info(f"[{short_uuid}] Silence/Unknown -> Continue loop")
                current_objection = reaction  # Use for next iteration
                continue

            else:
                # New objection or question - continue to next turn
                current_objection = reaction

        # Loop ended without resolution
        logger.info(
            f"[{short_uuid}] === OBJECTION LOOP END === "
            f"NOT RESOLVED after {turns_used} turns"
        )

        total_latency_ms = (time.time() - loop_start) * 1000

        return {
            "resolved": False,
            "turns_used": turns_used,
            "final_intent": "objection",
            "latencies": {"total_ms": total_latency_ms}
        }

    def _calculate_final_status(
        self,
        session: Dict,
        scenario: Dict
    ) -> CallResult:
        """
        Calculate final call status based on session data

        Args:
            session: Call session data
            scenario: Scenario dict

        Returns:
            CallResult enum (LEADS, NOT_INTERESTED, NO_ANSWER)
        """
        qualification_score = session.get("qualification_score", 0.0)

        # Define qualification threshold
        # For a typical scenario with 3-4 determinant questions:
        # - Each question has weight 30-40
        # - LEAD threshold: >= 70% of questions answered positively
        # - Example: 3 questions * 30 = 90 max -> threshold ~70

        lead_threshold = 70.0  # Aligned with scenarios.py calculation

        if qualification_score >= lead_threshold:
            return CallResult.LEADS
        else:
            return CallResult.NOT_INTERESTED

    # ========================================================================
    # INTENT ANALYSIS & OBJECTION HANDLING
    # ========================================================================

    def _analyze_intent(
        self,
        transcription: str,
        scenario: Optional[Dict] = None,
        step_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze client intent using UNIFIED ObjectionMatcher system

        Architecture simplifiée: TOUT passe par ObjectionMatcher
        - Intents de base (affirm, deny, insult) sont dans objections_general.py
        - Objections et FAQ sont dans objections_*.py
        - Le meilleur score gagne (fuzzy matching unifié)

        Intents possibles:
        - affirm: Acceptation positive (entry_type="affirm")
        - deny: Refus/rejet (entry_type="deny")
        - insult: Insulte/demande retrait (entry_type="insult")
        - question: FAQ (entry_type="faq")
        - objection: Objection (entry_type="objection")
        - silence: Pas de transcription
        - not_understood: Pas de match trouvé

        Args:
            transcription: Client transcription
            scenario: Optional scenario context (for theme)
            step_name: Optional step name (unused, kept for compatibility)

        Returns:
            {
                "intent": "affirm" | "deny" | "insult" | "question" | "objection" | "silence" | "not_understood",
                "confidence": 0.0-1.0,
                "keywords_matched": [...],
                "reason": "objections_db_unified" | "empty" | "no_match",
                "entry_type": "affirm" | "deny" | "insult" | "objection" | "faq",
                "latency_ms": 5.0
            }
        """
        analyze_start = time.time()

        if not transcription or not transcription.strip():
            return {
                "intent": "silence",
                "confidence": 1.0,
                "keywords_matched": [],
                "reason": "empty",
                "latency_ms": (time.time() - analyze_start) * 1000
            }

        text_lower = transcription.lower().strip()

        # Get theme from scenario (fallback to "objections_general")
        theme = "objections_general"
        if scenario:
            theme = self.scenario_manager.get_theme_file(scenario)

        # ===== SYSTEME UNIFIE: ObjectionMatcher pour TOUT =====
        # Intents (affirm, deny, insult) + Objections + FAQ tous dans objections_db
        logger.info(f"")
        logger.info(f"{'═'*60}")
        logger.info(f"🎯 INTENT ANALYSIS - _analyze_intent()")
        logger.info(f"{'═'*60}")
        logger.info(f"📝 Transcription: '{transcription}'")
        logger.info(f"📚 Theme: {theme}")
        logger.info(f"{'─'*60}")

        if hasattr(self, 'objection_matcher_default') and self.objection_matcher_default:
            objection_matcher = ObjectionMatcher.load_objections_for_theme(theme)
            if objection_matcher:
                num_entries = len(objection_matcher.objections)
                num_keywords = len(objection_matcher.keyword_lookup)
                logger.info(f"✅ ObjectionMatcher chargé: {num_entries} entries, {num_keywords} keywords")

                match_result = objection_matcher.find_best_match(
                    text_lower,
                    min_score=0.70,  # Seuil relevé pour éviter faux positifs fuzzy
                    silent=False
                )

                if match_result:
                    entry_type = match_result.get("entry_type", "objection")
                    confidence = match_result["score"]
                    matched_keyword = match_result.get('matched_keyword', '')

                    # Map entry_type to intent
                    logger.info(f"{'─'*60}")
                    logger.info(f"🔄 MAPPING entry_type → intent:")
                    if entry_type in ['affirm', 'deny', 'insult', 'time', 'unsure']:
                        intent = entry_type
                        logger.info(f"   entry_type='{entry_type}' → intent='{intent}' (navigation directe)")
                    elif entry_type == 'faq':
                        intent = 'question'
                        logger.info(f"   entry_type='faq' → intent='question' (FAQ)")
                    else:
                        intent = 'objection'
                        logger.info(f"   entry_type='{entry_type}' → intent='objection' (réponse audio)")

                    latency_ms = (time.time() - analyze_start) * 1000

                    # Log des alternatives si disponibles
                    alternatives = match_result.get("top_alternatives", [])
                    if alternatives:
                        logger.info(f"   📋 Alternatives: {', '.join([f'{kw}({t}):{s:.2f}' for kw, s, t in alternatives])}")

                    logger.info(f"{'─'*60}")
                    logger.info(f"🏆 RÉSULTAT _analyze_intent:")
                    logger.info(f"   Intent: {intent.upper()}")
                    logger.info(f"   Confidence: {confidence:.2f}")
                    logger.info(f"   Keyword: '{matched_keyword}' (len={len(matched_keyword)})")
                    logger.info(f"   Entry type: {entry_type}")
                    logger.info(f"   Latency: {latency_ms:.1f}ms")
                    logger.info(f"{'═'*60}")
                    logger.info(f"")

                    return {
                        "intent": intent,
                        "confidence": confidence,
                        "keywords_matched": [match_result.get("matched_keyword", "")],
                        "reason": "objections_db_unified",
                        "matched_response_id": match_result.get("objection", ""),
                        "entry_type": entry_type,
                        "latency_ms": latency_ms
                    }

        # No match found -> not_understood
        latency_ms = (time.time() - analyze_start) * 1000
        logger.info(f"{'─'*60}")
        logger.info(f"❌ Aucun match trouvé dans ObjectionMatcher")
        logger.info(f"{'─'*60}")
        logger.info(f"🏆 RÉSULTAT _analyze_intent:")
        logger.info(f"   Intent: NOT_UNDERSTOOD")
        logger.info(f"   Confidence: 0.00")
        logger.info(f"   Reason: no_match (score < min_score)")
        logger.info(f"   Latency: {latency_ms:.1f}ms")
        logger.info(f"{'═'*60}")
        logger.info(f"")
        return {
            "intent": "not_understood",
            "confidence": 0.0,
            "keywords_matched": [],
            "reason": "no_match",
            "latency_ms": latency_ms
        }

    def _find_objection_response(
        self,
        objection_text: str,
        theme: str = "general",
        min_score: float = 0.5
    ) -> Dict[str, Any]:
        """
        Find best objection response using ObjectionMatcher

        Args:
            objection_text: Client objection transcription
            theme: Objection theme (finance, immobilier, etc.)
            min_score: Minimum matching score (0.0-1.0)

        Returns:
            {
                "found": True | False,
                "objection_id": "obj_12",
                "audio_file": "obj_12_response.wav",
                "response_text": "...",
                "match_score": 0.85,
                "latency_ms": 50.0
            }
        """
        match_start = time.time()

        logger.info(
            f"Searching objection response: '{objection_text[:40]}...' "
            f"(theme: {theme}, min_score: {min_score})"
        )

        try:
            # Load ObjectionMatcher for theme
            objection_matcher = ObjectionMatcher.load_objections_for_theme(theme)

            if not objection_matcher:
                logger.warning(f"No ObjectionMatcher available for theme: {theme}")
                return {
                    "found": False,
                    "error": "no_matcher_for_theme",
                    "latency_ms": (time.time() - match_start) * 1000
                }

            # Find best match
            match_result = objection_matcher.find_best_match(
                objection_text,
                min_score=min_score
            )

            latency_ms = (time.time() - match_start) * 1000

            if match_result and match_result.get("match_found"):
                logger.info(
                    f"Objection response found: {match_result['objection_id']} "
                    f"(score: {match_result['match_score']:.2f}, "
                    f"latency: {latency_ms:.0f}ms)"
                )

                return {
                    "found": True,
                    "objection_id": match_result["objection_id"],
                    "audio_file": match_result.get("audio_file"),
                    "response_text": match_result.get("response_text"),
                    "match_score": match_result["match_score"],
                    "latency_ms": latency_ms
                }

            else:
                logger.info(
                    f"No objection response found (score < {min_score}, "
                    f"latency: {latency_ms:.0f}ms)"
                )

                return {
                    "found": False,
                    "latency_ms": latency_ms
                }

        except Exception as e:
            logger.error(f"Objection matching error: {e}")
            return {
                "found": False,
                "error": str(e),
                "latency_ms": (time.time() - match_start) * 1000
            }

    def _get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio duration in seconds from audio file (supports G.711, PCM, etc.)

        Uses soundfile for robust format support (G.711 μ-law/ALAW, compressed formats),
        falls back to wave module for simple PCM, and caches results for performance.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds, or 20.0 as fallback (increased from 10.0s)
        """
        from system.cache_manager import CacheManager

        # Check cache first (zero I/O after first call)
        cache = CacheManager.get_instance()
        cached_duration = cache.get_audio_duration(audio_path)
        if cached_duration is not None:
            return cached_duration

        duration = None

        # Method 1: Try soundfile (handles G.711 μ-law/ALAW + 40+ formats)
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            duration = info.duration
            logger.debug(
                f"Audio duration (soundfile): {audio_path} = {duration:.2f}s "
                f"(format: {info.format}, subtype: {info.subtype}, {info.samplerate}Hz)"
            )
        except Exception as e:
            logger.debug(f"soundfile failed for {audio_path}: {e}")

        # Method 2: Fallback to wave module (simple PCM WAV only)
        if duration is None:
            try:
                import wave
                with wave.open(audio_path, 'rb') as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
                    duration = frames / float(rate)
                    logger.debug(
                        f"Audio duration (wave): {audio_path} = {duration:.2f}s "
                        f"({rate}Hz, {frames} frames)"
                    )
            except Exception as e:
                logger.debug(f"wave module failed for {audio_path}: {e}")

        # Final fallback: 20.0s (increased from 10.0s to reduce Phase 3 overlap risk)
        if duration is None:
            logger.warning(
                f"Could not read audio duration from {audio_path} "
                f"(soundfile + wave failed). Using fallback: 20.0s"
            )
            duration = 20.0

        # Cache the result (thread-safe)
        cache.cache_audio_duration(audio_path, duration)

        return duration

    def _get_audio_path_for_step(
        self,
        scenario: Dict,
        step_name: str,
        audio_file: Optional[str] = None
    ) -> Optional[str]:
        """
        Get full audio path for a scenario step

        Args:
            scenario: Scenario dict
            step_name: Step name
            audio_file: Optional override audio file

        Returns:
            Full path to audio file or None if not found
        """
        # Get step config
        step_config = self.scenario_manager.get_step_config(scenario, step_name)

        if not step_config:
            logger.error(f"Step not found: {step_name}")
            return None

        # Use override or step audio_file
        if audio_file:
            filename = audio_file
        else:
            filename = step_config.get("audio_file")

        if not filename:
            logger.error(f"No audio_file for step: {step_name}")
            return None

        # ===================================================================
        # RANDOM RETRY SELECTION
        # ===================================================================
        # For retry steps (retry_silence, retry_global), check for variants
        # Variants: retry_silence_1.wav, retry_silence_2.wav, etc.
        random_enabled_retries = ["retry_silence", "retry_global"]

        if step_name in random_enabled_retries:
            # Determine base directory for audio files
            if os.path.isabs(filename):
                audio_dir = Path(filename).parent
                base_name = Path(filename).stem  # e.g., "retry_silence"
                ext = Path(filename).suffix  # e.g., ".wav"
            else:
                theme = scenario.get("theme", "general")
                voice = scenario.get("voice", step_config.get("voice", "julie"))
                audio_dir = config.BASE_DIR / "sounds" / theme / voice
                base_name = Path(filename).stem
                ext = Path(filename).suffix

            # Look for variants: base_name_1.wav, base_name_2.wav, etc.
            variants = []
            for i in range(1, 10):  # Support up to 9 variants
                variant_path = audio_dir / f"{base_name}_{i}{ext}"
                if variant_path.exists():
                    variants.append(variant_path)
                else:
                    break  # Stop at first missing number

            if variants:
                # Randomly select one variant
                selected = random.choice(variants)
                logger.info(f"Random retry selection: {selected.name} (from {len(variants)} variants)")
                return str(selected)
            else:
                # No variants found, use base file
                logger.debug(f"No variants found for {step_name}, using base file")

        # Check if filename is already an absolute path
        if os.path.isabs(filename):
            # Use absolute path as-is
            audio_path = Path(filename)
            logger.debug(f"Using absolute audio path: {audio_path}")
        else:
            # Build relative path
            # Audios are in: BASE_DIR/sounds/{theme}/{voice}/{filename}
            theme = scenario.get("theme", "general")
            voice = scenario.get("voice", step_config.get("voice", "julie"))
            audio_path = config.BASE_DIR / "sounds" / theme / voice / filename
            logger.debug(f"Built relative audio path: {audio_path}")

        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        return str(audio_path)

    # ========================================================================
    # PHASE IMPLEMENTATIONS (AMD, PLAYING, WAITING)
    # ========================================================================

    def _execute_phase_amd_whisper(self, call_uuid: str) -> Dict[str, Any]:
        """
        Phase 1: AMD (Answering Machine Detection) - FALLBACK WITH FASTER-WHISPER

        Simple & Fast:
        - Record STEREO 2.3s
        - Transcribe AFTER with Faster-Whisper
        - Keywords matching HUMAN/MACHINE
        - NO complex VAD, NO streaming

        Args:
            call_uuid: Call UUID

        Returns:
            {
                "result": "HUMAN" | "MACHINE" | "SILENCE" | "UNKNOWN",
                "transcription": str,
                "confidence": float,
                "latency_ms": float
            }
        """
        short_uuid = call_uuid[:8]
        phase_start = time.time()

        # PHASE 1 START - Colored log (YELLOW panel with double border)
        self.clog.phase1_start(uuid=short_uuid)

        # Recording file
        record_file = f"/tmp/amd_{call_uuid}.wav"

        try:
            # CRITICAL: Play short silence to "prime" the RTP stream
            # FreeSWITCH only establishes media after first audio is played
            # This technique comes from backup code that worked!
            logger.debug(f"[{short_uuid}] Priming RTP stream with silence...")
            silence_cmd = f"uuid_broadcast {call_uuid} silence_stream://100 both"
            self._execute_esl_command(silence_cmd)

            # OPTIMIZED: Single combined wait for audio path + RTP establishment
            # Original: 0.3s + 0.2s = 500ms → Optimized: 0.35s = 350ms (-150ms gain!)
            time.sleep(0.35)  # 350ms for audio path setup + RTP priming
            logger.info(f"🎧 [{short_uuid}] RTP stream primed, ready to record")

            # Step 1: Record STEREO 1.5s (left=client, right=robot)
            # IMPORTANT: Even for AMD we need STEREO to capture client audio
            # MONO might record wrong channel (robot instead of client)
            logger.info(
                f"🎧 [{short_uuid}] Recording {config.AMD_MAX_DURATION}s audio (STEREO)..."
            )
            record_start = time.time()

            if not self._start_recording(call_uuid, record_file, stereo=True):
                logger.error(f"❌ [{short_uuid}] AMD: Recording start failed!")
                return {
                    "result": "UNKNOWN",
                    "transcription": "",
                    "confidence": 0.0,
                    "latency_ms": 0.0
                }

            # Wait for recording duration
            time.sleep(config.AMD_MAX_DURATION)

            # Stop recording
            if not self._stop_recording(call_uuid, record_file):
                logger.error(f"❌ [{short_uuid}] AMD: Recording stop failed!")
                return {
                    "result": "UNKNOWN",
                    "transcription": "",
                    "confidence": 0.0,
                    "latency_ms": 0.0
                }

            # CRITICAL: Wait for FreeSWITCH to finalize WAV file
            # Poll until file is stable (not growing anymore)
            max_wait = 1.0  # Max 1 second
            poll_start = time.time()
            last_size = 0

            while (time.time() - poll_start) < max_wait:
                if Path(record_file).exists():
                    current_size = Path(record_file).stat().st_size
                    if current_size > 1000 and current_size == last_size:
                        # File exists and size is stable (not growing)
                        break
                    last_size = current_size
                time.sleep(0.05)  # Poll every 50ms
            else:
                logger.warning(f"⚠️ [{short_uuid}] File may not be ready (waited {max_wait}s)")

            record_latency = (time.time() - record_start) * 1000
            # Latency - Colored log (RED/YELLOW/GREEN indicator)
            self.clog.latency(record_latency, "Recording", uuid=short_uuid)

            # Step 2: Extract LEFT channel (client audio) from STEREO
            mono_file = f"/tmp/amd_{call_uuid}_mono.wav"
            logger.info(f"🎧 [{short_uuid}] Extracting client audio (left channel)...")

            # Use ffmpeg to extract left channel
            import subprocess
            extract_cmd = [
                "ffmpeg", "-i", record_file,
                "-af", "pan=mono|c0=FL",  # Extract left channel
                "-y",  # Overwrite
                mono_file
            ]
            subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Step 2.5: Check audio volume (detect pure silence BEFORE transcription)
            # This prevents Whisper from hallucinating on silence/noise
            logger.debug(f"🔊 [{short_uuid}] Checking audio volume...")
            volume_cmd = [
                "ffmpeg", "-i", mono_file,
                "-af", "volumedetect",
                "-f", "null", "-"
            ]
            volume_result = subprocess.run(
                volume_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Parse mean_volume from ffmpeg output
            mean_volume = -90.0  # Default = silence
            for line in volume_result.stdout.split('\n'):
                if 'mean_volume:' in line:
                    try:
                        mean_volume = float(line.split('mean_volume:')[1].split('dB')[0].strip())
                    except:
                        pass

            logger.info(f"🔊 [{short_uuid}] Audio volume: {mean_volume:.1f}dB")

            # If volume too low (< -50dB) → pure silence, no need to transcribe
            if mean_volume < -50.0:
                logger.warning(
                    f"⚠️ [{short_uuid}] AMD: SILENCE detected by volume check "
                    f"({mean_volume:.1f}dB < -50dB threshold)"
                )

                # Cleanup
                try:
                    Path(mono_file).unlink()
                    Path(record_file).unlink()
                except:
                    pass

                total_latency = (time.time() - phase_start) * 1000

                # PHASE 1 END - Colored log (YELLOW panel with latency)
                self.clog.success("AMD: NO_ANSWER detected (silence)", uuid=short_uuid)
                self.clog.phase1_end(total_latency, uuid=short_uuid)

                return {
                    "result": "NO_ANSWER",
                    "transcription": "",
                    "confidence": 1.0,
                    "latency_ms": total_latency
                }

            # Step 3: Transcribe with OPTIMIZED parameters for AMD
            logger.info(f"📝 [{short_uuid}] Transcribing audio...")
            transcribe_start = time.time()

            # OPTIMIZED: Use beam_size=5 + no_speech_threshold=0.6 + vad_filter=True
            # - beam_size=5: More hypotheses tested = fewer hallucinations on short words (vs beam_size=3)
            # - no_speech_threshold=0.6: Balanced threshold (0.8 too strict, forced hallucinations)
            # - vad_filter=True: Let Whisper's VAD handle silence removal
            # - condition_on_previous_text=False: No context (avoid hallucinations)
            transcription_result = self.stt_service.transcribe_file(
                mono_file,  # Use mono file (client audio only)
                vad_filter=True,  # Enable Whisper's internal VAD
                no_speech_threshold=0.6,  # Balanced silence threshold (default Whisper)
                condition_on_previous_text=False,  # No context (first transcription)
                beam_size=5  # More hypotheses = fewer hallucinations (AMD-specific)
            )
            transcription = transcription_result.get("text", "").strip()

            # Cleanup mono file
            try:
                Path(mono_file).unlink()
            except:
                pass

            transcribe_latency = (time.time() - transcribe_start) * 1000

            # Transcription - Colored log (CYAN panel)
            self.clog.transcription(transcription, uuid=short_uuid, latency_ms=transcribe_latency)

            # Check for SILENCE: if transcription is empty or very short
            # This indicates no one spoke during AMD period → no answer / silence
            if not transcription or len(transcription) <= 2:
                logger.warning(f"⚠️ [{short_uuid}] AMD: SILENCE detected (no speech during {config.AMD_MAX_DURATION}s)")

                # Cleanup
                try:
                    Path(record_file).unlink()
                except:
                    pass

                total_latency = (time.time() - phase_start) * 1000

                # PHASE 1 END - Colored log (YELLOW panel with latency)
                self.clog.success("AMD: NO_ANSWER detected (silence)", uuid=short_uuid)
                self.clog.phase1_end(total_latency, uuid=short_uuid)

                return {
                    "result": "NO_ANSWER",  # Silence = no answer
                    "transcription": "",
                    "confidence": 1.0,  # Certain it's silence
                    "latency_ms": total_latency
                }

            # Step 3: Keywords matching HUMAN/MACHINE
            amd_result = self.amd_service.detect(transcription)
            result_type = amd_result["result"]  # HUMAN/MACHINE/UNKNOWN
            confidence = amd_result["confidence"]

            # Cleanup
            try:
                Path(record_file).unlink()
            except:
                pass

            # Total latency
            total_latency = (time.time() - phase_start) * 1000

            # PHASE 1 END - Colored log (YELLOW panel with latency)
            self.clog.success(
                f"AMD: {result_type} detected (confidence: {confidence:.2f})",
                uuid=short_uuid
            )
            self.clog.phase1_end(total_latency, uuid=short_uuid)

            return {
                "result": result_type,
                "transcription": transcription,
                "confidence": confidence,
                "latency_ms": total_latency
            }

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] AMD error: {e}")
            import traceback
            traceback.print_exc()

            # Cleanup
            try:
                Path(record_file).unlink()
            except:
                pass

            return {
                "result": "UNKNOWN",
                "transcription": "",
                "confidence": 0.0,
                "latency_ms": 0.0
            }

    def _execute_phase_amd(self, call_uuid: str) -> Dict[str, Any]:
        """
        Phase 1: AMD (Answering Machine Detection) - VOSK STREAMING

        Ultra-Fast with Vosk:
        - Stream audio to Vosk in real-time (uuid_audio_fork)
        - Transcription ready when recording ends (~20ms latency)
        - Keywords matching HUMAN/MACHINE
        - Fallback to Whisper if Vosk unavailable

        Args:
            call_uuid: Call UUID

        Returns:
            {
                "result": "HUMAN" | "MACHINE" | "SILENCE" | "UNKNOWN",
                "transcription": str,
                "confidence": float,
                "latency_ms": float
            }
        """
        short_uuid = call_uuid[:8]
        phase_start = time.time()

        # PHASE 1 START - Colored log (YELLOW panel with double border)
        self.clog.phase1_start(uuid=short_uuid)

        # Check if Vosk streaming is available
        if not (self.streaming_asr and self.streaming_asr.is_available and config.STREAMING_ASR_ENABLED):
            logger.warning(f"[{short_uuid}] Vosk streaming not available, falling back to Faster-Whisper")
            return self._execute_phase_amd_whisper(call_uuid)

        try:
            # State pour récupérer la transcription Vosk
            amd_state = {
                "transcription": "",
                "last_partial": "",  # Fallback si FINAL n'arrive pas
                "final_received": False,
                "speech_detected": False
            }

            def amd_callback(event_data):
                """Callback pour récupérer transcription finale de Vosk"""
                logger.info(f"🔔 [{short_uuid}] AMD CALLBACK TRIGGERED: {event_data}")
                event = event_data.get("event")

                if event == "transcription":
                    if event_data.get("type") == "final":
                        text = event_data.get("text", "").strip()
                        # Ne pas écraser une transcription existante par une vide
                        if text or not amd_state.get("transcription"):
                            amd_state["transcription"] = text
                        amd_state["final_received"] = True
                        # Afficher transcription AMD avec panel Rich visible
                        self.clog.transcription(text, uuid=short_uuid, latency_ms=0)
                    else:
                        # Store PARTIAL as fallback
                        partial_text = event_data.get("text", "").strip()
                        if partial_text:
                            amd_state["last_partial"] = partial_text
                        logger.debug(f"📝 [{short_uuid}] AMD CALLBACK received PARTIAL: '{partial_text}'")

                elif event == "speech_start":
                    amd_state["speech_detected"] = True
                    logger.info(f"🗣️ [{short_uuid}] AMD CALLBACK received SPEECH_START")
                else:
                    logger.debug(f"🔔 [{short_uuid}] AMD CALLBACK unknown event: {event}")

            # Register callback
            self.streaming_asr.register_callback(call_uuid, amd_callback)

            # Prime RTP stream
            rtp_prime_start = time.time()
            silence_cmd = f"uuid_broadcast {call_uuid} silence_stream://100 both"
            self._execute_esl_command(silence_cmd)
            time.sleep(0.35)  # 350ms for RTP priming
            rtp_prime_latency = (time.time() - rtp_prime_start) * 1000

            # Start uuid_audio_fork (streaming to Vosk)
            fork_start = time.time()
            ws_url = f"ws://{config.STREAMING_ASR_HOST}:{config.STREAMING_ASR_PORT}/stream/{call_uuid}"
            fork_cmd = f"uuid_audio_fork {call_uuid} start {ws_url} mono 16000"
            fork_result = self._execute_esl_command(fork_cmd)

            if not fork_result or "+OK" not in fork_result:
                logger.error(f"❌ [{short_uuid}] Audio fork failed: {fork_result}, falling back to Whisper")
                self.streaming_asr.unregister_callback(call_uuid)
                return self._execute_phase_amd_whisper(call_uuid)

            fork_latency = (time.time() - fork_start) * 1000

            # === ATTENDRE INITIALISATION STREAM (évite race condition) ===
            stream_wait_start = time.time()
            max_stream_wait = 2.0  # Max 2s d'attente pour établissement WebSocket

            while call_uuid not in self.streaming_asr.active_streams:
                if (time.time() - stream_wait_start) > max_stream_wait:
                    logger.error(
                        f"❌ [{short_uuid}] WebSocket stream not initialized after {max_stream_wait}s, "
                        f"falling back to Whisper"
                    )
                    try:
                        self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                    except:
                        pass
                    self.streaming_asr.unregister_callback(call_uuid)
                    return self._execute_phase_amd_whisper(call_uuid)
                time.sleep(0.01)  # Poll every 10ms

            stream_init_latency = (time.time() - stream_wait_start) * 1000
            logger.debug(f"✅ [{short_uuid}] AMD Stream initialized in {stream_init_latency:.0f}ms")

            # Wait for AMD duration (AVEC VÉRIFICATION HANGUP!)
            record_start = time.time()
            amd_timeout = config.AMD_MAX_DURATION
            amd_hangup_detected = False

            while (time.time() - record_start) < amd_timeout:
                # ===== ULTRA-FAST HANGUP DETECTION pendant AMD =====
                # Vérification 1: Flag session (setté par HANGUP handler)
                session = self.call_sessions.get(call_uuid, {})
                if session.get("hangup_detected", False):
                    hangup_ts = session.get("hangup_timestamp", 0)
                    detection_delay_ms = (time.time() - hangup_ts) * 1000
                    logger.warning(
                        f"🚨 [{short_uuid}] HANGUP FLAG detected during AMD! "
                        f"Detection delay: {detection_delay_ms:.1f}ms - ABORTING!"
                    )
                    amd_hangup_detected = True
                    break

                # Vérification 2: ESL DIRECT (instantané!)
                if not self._channel_exists(call_uuid):
                    logger.warning(
                        f"🚨 [{short_uuid}] Channel NO LONGER EXISTS (ESL check) during AMD - ABORTING!"
                    )
                    amd_hangup_detected = True
                    break

                if call_uuid not in self.active_calls:
                    logger.info(f"[{short_uuid}] Call removed from active_calls during AMD")
                    amd_hangup_detected = True
                    break

                time.sleep(0.02)  # Poll every 20ms

            record_latency = (time.time() - record_start) * 1000

            # Si HANGUP détecté, on arrête tout de suite
            if amd_hangup_detected:
                stop_cmd = f"uuid_audio_fork {call_uuid} stop"
                self._execute_esl_command(stop_cmd)
                self.streaming_asr.unregister_callback(call_uuid)

                total_latency = (time.time() - phase_start) * 1000
                self.clog.phase1_end(total_latency, uuid=short_uuid)

                return {
                    "result": "HANGUP",
                    "confidence": 1.0,
                    "transcription": "",
                    "latencies": {
                        "total_ms": total_latency
                    }
                }

            # Wait for final transcription (max 1500ms)
            # Vosk peut prendre 100-600ms selon longueur de la phrase
            transcribe_start = time.time()
            max_wait = 1.5  # 1500ms max (cohérence avec Phase 2 et Phase 3)
            wait_start = time.time()

            while (time.time() - wait_start) < max_wait:
                # HANGUP check même pendant l'attente FINAL!
                session = self.call_sessions.get(call_uuid, {})
                if session.get("hangup_detected", False):
                    logger.warning(f"🚨 [{short_uuid}] HANGUP during AMD FINAL wait!")
                    break

                if call_uuid not in self.active_calls:
                    logger.info(f"[{short_uuid}] Call hung up during AMD FINAL wait")
                    break

                if amd_state["final_received"]:
                    break
                time.sleep(0.02)  # Poll every 20ms (faster!)

            transcribe_latency = (time.time() - transcribe_start) * 1000

            # Stop audio fork
            stop_cmd = f"uuid_audio_fork {call_uuid} stop"
            self._execute_esl_command(stop_cmd)
            self.streaming_asr.unregister_callback(call_uuid)

            transcription = amd_state["transcription"]

            # Use PARTIAL as fallback if FINAL didn't arrive
            if not transcription and amd_state["last_partial"]:
                transcription = amd_state["last_partial"]
                logger.warning(f"[{short_uuid}] AMD: Using last PARTIAL as fallback (FINAL not received)")

            # Transcription - Colored log
            self.clog.transcription(transcription, uuid=short_uuid, latency_ms=transcribe_latency)

            # Check for SILENCE
            if not transcription or len(transcription) <= 2:
                logger.warning(f"⚠️ [{short_uuid}] AMD: SILENCE detected (no speech during {config.AMD_MAX_DURATION}s)")
                total_latency = (time.time() - phase_start) * 1000
                self.clog.success("AMD: NO_ANSWER detected (silence)", uuid=short_uuid)
                self.clog.phase1_end(total_latency, uuid=short_uuid)

                return {
                    "result": "NO_ANSWER",
                    "transcription": "",
                    "confidence": 1.0,
                    "latency_ms": total_latency
                }

            # AMD Detection with keywords matching
            detection_start = time.time()
            amd_result = self.amd_service.detect(transcription)
            result_type = amd_result["result"]  # HUMAN/MACHINE/UNKNOWN
            confidence = amd_result["confidence"]
            detection_latency = (time.time() - detection_start) * 1000

            # TOTAL PHASE LATENCY
            total_latency = (time.time() - phase_start) * 1000

            # Compact latency breakdown (single line)
            logger.info(
                f"📊 [{short_uuid}] AMD: RTP={rtp_prime_latency:.0f}ms | Fork={fork_latency:.0f}ms | "
                f"Rec={record_latency:.0f}ms | Wait={transcribe_latency:.0f}ms | "
                f"Detect={detection_latency:.0f}ms | TOTAL={total_latency:.0f}ms"
            )

            # PHASE 1 END - Colored log
            self.clog.success(
                f"AMD: {result_type} detected (confidence: {confidence:.2f})",
                uuid=short_uuid
            )
            self.clog.phase1_end(total_latency, uuid=short_uuid)

            # Store end timestamp for gap calculation
            if call_uuid in self.call_sessions:
                self.call_sessions[call_uuid]["phase1_end_timestamp"] = time.time()

            return {
                "result": result_type,
                "transcription": transcription,
                "confidence": confidence,
                "latency_ms": total_latency,
                "end_timestamp": time.time()  # Pour calculer gap Phase 1→2
            }

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] AMD Vosk error: {e}, falling back to Whisper")
            import traceback
            traceback.print_exc()

            # Cleanup
            try:
                self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                self.streaming_asr.unregister_callback(call_uuid)
            except:
                pass

            # Fallback to Whisper
            return self._execute_phase_amd_whisper(call_uuid)

    def _execute_phase_playing(
        self,
        call_uuid: str,
        audio_path: str,
        enable_barge_in: bool = True,
        is_terminal: bool = False
    ) -> Dict[str, Any]:
        """
        Phase 2: PLAYING (Robot plays audio with barge-in detection)

        Complex:
        - Record STEREO (left=client, right=robot)
        - Broadcast audio (non-blocking)
        - VAD monitoring for barge-in (1.5s threshold)
        - Background transcription (snapshot at 0.5s)
        - Smooth delay (0.3s) before stop

        Args:
            call_uuid: Call UUID
            audio_path: Audio file to play
            enable_barge_in: Enable barge-in detection
            is_terminal: True si étape terminale (bye) → pas d'early exit

        Returns:
            {
                "barged_in": bool,
                "transcription": str,
                "audio_duration": float,
                "latency_ms": float
            }
        """
        short_uuid = call_uuid[:8]
        phase_start = time.time()

        # PHASE 2 START - Colored log (GREEN panel with heavy border)
        self.clog.phase2_start(Path(audio_path).name, uuid=short_uuid)

        # Recording file (RAW format for real-time access)
        record_file = f"/tmp/playing_{call_uuid}.raw"

        # Shared state for VAD monitoring thread
        monitoring_state = {
            "barged_in": False,
            "audio_finished": False,
            "transcription": None,
            "bg_ready": False,
            "stop_monitoring": False
        }

        try:
            # Step 1: Start recording STEREO (both legs) - same as AMD
            # We'll extract client audio (left channel) before transcription
            if not self._start_recording(call_uuid, record_file, stereo=True):
                logger.error(f"❌ [{short_uuid}] PLAYING: Recording start failed!")
                return {
                    "barged_in": False,
                    "transcription": "",
                    "audio_duration": 0.0,
                    "latency_ms": 0.0
                }

            # Step 2: Start audio playback (non-blocking)
            play_cmd = f"uuid_broadcast {call_uuid} {audio_path} aleg"
            play_result = self._execute_esl_command(play_cmd)

            if not play_result or "+OK" not in play_result:
                logger.error(f"❌ [{short_uuid}] Audio playback failed: {play_result}")
                self._stop_recording(call_uuid, record_file)
                return {
                    "barged_in": False,
                    "transcription": "",
                    "audio_duration": 0.0,
                    "latency_ms": 0.0
                }

            logger.info(f"🗣️ [{short_uuid}] Audio playback started")

            # Step 3: Monitor VAD for barge-in (if enabled)
            if enable_barge_in:
                vad_thread = threading.Thread(
                    target=self._monitor_vad_playing,
                    args=(call_uuid, record_file, monitoring_state),
                    daemon=True
                )
                vad_thread.start()

                # Wait for barge-in or audio finish
                # Check every 100ms
                while not monitoring_state["barged_in"] and not monitoring_state["audio_finished"]:
                    time.sleep(0.1)

                # Stop monitoring
                monitoring_state["stop_monitoring"] = True
                vad_thread.join(timeout=1.0)

                if monitoring_state["barged_in"]:
                    logger.info(f"⚡ [{short_uuid}] BARGE-IN detected!")

                    # Smooth delay with fade-out effect (0.3s)
                    logger.info(f"🔉 [{short_uuid}] Fade-out + smooth delay: {config.BARGE_IN_SMOOTH_DELAY}s...")

                    # Progressive fade-out during smooth delay
                    # Reduce volume from 0 dB to -40 dB over 0.3s (10 steps)
                    fade_steps = 10
                    step_duration = config.BARGE_IN_SMOOTH_DELAY / fade_steps

                    for step in range(fade_steps):
                        # Calculate volume: 0 dB → -40 dB (linear fade)
                        volume_db = -4 * step  # 0, -4, -8, -12, ..., -36
                        volume_level = volume_db / 4.0  # FreeSWITCH uses -4 to +4 range

                        # Apply volume adjustment
                        audio_cmd = f"uuid_audio {call_uuid} start write level {volume_level}"
                        self._execute_esl_command(audio_cmd)

                        time.sleep(step_duration)

                    # Stop audio playback
                    break_cmd = f"uuid_break {call_uuid}"
                    self._execute_esl_command(break_cmd)

                    # Reset audio level to normal
                    reset_cmd = f"uuid_audio {call_uuid} start write level 0"
                    self._execute_esl_command(reset_cmd)

                    logger.info(f"🔇 [{short_uuid}] Audio stopped (fade-out complete)")

            else:
                # No barge-in: wait for audio to finish
                # Estimate audio duration (TODO: get real duration)
                estimated_duration = 10.0  # Default
                time.sleep(estimated_duration)
                monitoring_state["audio_finished"] = True

            # Step 4: Stop recording
            self._stop_recording(call_uuid, record_file)

            # CRITICAL: Wait for FreeSWITCH to finalize WAV file
            # Poll until file is stable (not growing anymore)
            max_wait = 1.0  # Max 1 second
            poll_start = time.time()
            last_size = 0

            while (time.time() - poll_start) < max_wait:
                if Path(record_file).exists():
                    current_size = Path(record_file).stat().st_size
                    if current_size > 1000 and current_size == last_size:
                        break
                    last_size = current_size
                time.sleep(0.05)  # Poll every 50ms

            # Step 4.5: Extract client audio (left channel) from STEREO recording
            mono_file = record_file.replace(".raw", "_mono.wav")
            logger.info(f"🎧 [{short_uuid}] Extracting client audio (left channel)...")

            import subprocess
            extract_cmd = [
                "ffmpeg", "-i", record_file,
                "-af", "pan=mono|c0=FL",  # Extract left channel (client)
                "-y",  # Overwrite
                mono_file
            ]
            subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Step 5: Get transcription
            transcription = ""
            if monitoring_state["barged_in"]:
                # Check if background transcription ready
                if monitoring_state["bg_ready"] and monitoring_state["transcription"]:
                    transcription = monitoring_state["transcription"]
                    logger.info(f"🚀 [{short_uuid}] Background transcription ready!")
                else:
                    # Fallback: sync transcription (use mono extracted file)
                    logger.info(f"🔄 [{short_uuid}] Fallback sync transcription...")
                    result = self.stt_service.transcribe_file(mono_file)
                    transcription = result.get("text", "").strip()

                # Transcription - Colored log (CYAN panel)
                self.clog.transcription(transcription, uuid=short_uuid)

            # Cleanup
            try:
                Path(record_file).unlink()
                if mono_file and Path(mono_file).exists():
                    Path(mono_file).unlink()
            except:
                pass

            # Total latency
            total_latency = (time.time() - phase_start) * 1000

            # PHASE 2 END - Colored log (GREEN panel)
            self.clog.phase2_end(total_latency, uuid=short_uuid)

            return {
                "barged_in": monitoring_state["barged_in"],
                "transcription": transcription,
                "audio_duration": total_latency / 1000.0,
                "latency_ms": total_latency
            }

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] PLAYING error: {e}")
            import traceback
            traceback.print_exc()

            # Cleanup
            try:
                self._stop_recording(call_uuid, record_file)
                Path(record_file).unlink()
                # Clean mono file if it was created
                mono_file_path = record_file.replace(".raw", "_mono.wav")
                if Path(mono_file_path).exists():
                    Path(mono_file_path).unlink()
            except:
                pass

            return {
                "barged_in": False,
                "transcription": "",
                "audio_duration": 0.0,
                "latency_ms": 0.0
            }

    def _execute_phase_2_auto(
        self,
        call_uuid: str,
        audio_path: str,
        enable_barge_in: bool = True,
        is_terminal: bool = False,
        calibrate_noise: bool = False
    ) -> Dict[str, Any]:
        """
        Phase 2: PLAYING (Auto-sélection Streaming ASR vs WebRTC VAD)

        Wrapper intelligent qui choisit automatiquement la meilleure méthode:
        - Si Streaming ASR disponible → _execute_phase_playing_streaming (Vosk WebSocket)
        - Sinon → _execute_phase_playing (WebRTC VAD fallback)

        Architecture Hybride:
        - Vosk: Latence <200ms, streaming natif, CPU-only
        - WebRTC VAD: Latence ~600ms, robuste, fallback

        Args:
            call_uuid: UUID appel
            audio_path: Fichier audio à jouer
            enable_barge_in: Activer barge-in
            is_terminal: True si étape terminale (bye) → pas d'early exit
            calibrate_noise: True pour calibrer le noise floor (premier step hello)

        Returns:
            Dict résultat phase 2 (voir _execute_phase_playing)
        """
        short_uuid = call_uuid[:8]

        # Vérifier si Streaming ASR disponible et activé
        if (
            self.streaming_asr
            and self.streaming_asr.is_available
            and config.STREAMING_ASR_ENABLED
        ):
            logger.debug(
                f"📡 [{short_uuid}] Using Streaming ASR for PHASE 2 "
                f"(Vosk WebSocket + audio fork)"
            )
            return self._execute_phase_playing_streaming(
                call_uuid, audio_path, enable_barge_in, is_terminal, calibrate_noise
            )
        else:
            logger.debug(
                f"📡 [{short_uuid}] Using WebRTC VAD for PHASE 2 "
                f"(fallback method)"
            )
            return self._execute_phase_playing(
                call_uuid, audio_path, enable_barge_in, is_terminal
            )

    def _execute_phase_playing_streaming(
        self,
        call_uuid: str,
        audio_path: str,
        enable_barge_in: bool = True,
        is_terminal: bool = False,
        calibrate_noise: bool = False
    ) -> Dict[str, Any]:
        """
        Phase 2: PLAYING avec Streaming ASR (Vosk Python + mod_audio_fork WebSocket)

        Architecture:
        1. Register callback pour barge-in events
        2. Démarrer uuid_audio_fork → WebSocket server
        3. Démarrer playback audio (uuid_broadcast)
        4. Attendre callback speech_start → barge-in
        5. Stop audio fork + playback si barge-in

        Args:
            call_uuid: UUID appel
            audio_path: Chemin fichier audio à jouer
            enable_barge_in: Activer barge-in (True par défaut)
            is_terminal: True si étape terminale (bye) → pas d'early exit
            calibrate_noise: True pour calibrer le noise floor pendant ce playback

        Returns:
            {
                "barged_in": bool,
                "transcription": str,
                "audio_duration": float,
                "latency_ms": float
            }
        """
        short_uuid = call_uuid[:8]
        phase_start = time.time()

        # Calculate gap Phase X→2 (from Phase 1 or Phase 3)
        gap_to_phase2 = 0
        if call_uuid in self.call_sessions:
            # Priorité Phase 3 (conversation loop) sinon Phase 1 (premier audio)
            if "phase3_end_timestamp" in self.call_sessions[call_uuid]:
                gap_to_phase2 = (phase_start - self.call_sessions[call_uuid]["phase3_end_timestamp"]) * 1000
            elif "phase1_end_timestamp" in self.call_sessions[call_uuid]:
                gap_to_phase2 = (phase_start - self.call_sessions[call_uuid]["phase1_end_timestamp"]) * 1000

        # PHASE 2 START - Colored log
        self.clog.phase2_start(Path(audio_path).name, uuid=short_uuid)

        # État détection
        detection_state = {
            "barged_in": False,
            "transcription": "",
            "final_received": False,  # Flag pour savoir si transcription finale reçue
            "audio_finished": False,
            "speech_ended": False,
            "last_update": time.time(),  # Timestamp dernière mise à jour
            # Timestamps pour analyse latence détaillée (barge-in)
            "first_partial_timestamp": None,  # Quand premier PARTIAL reçu
            "last_partial_timestamp": None,   # Quand dernier PARTIAL reçu
            "barge_in_timestamp": None,       # Quand barge-in déclenché
            "speech_end_timestamp": None,     # Quand SPEECH_END reçu
            "partial_count": 0,               # Nombre de PARTIAL reçus
            "monitoring_start": None          # Timestamp début monitoring (pour callback)
        }

        try:
            # Étape 1: Register callback
            def streaming_callback(event_data):
                """Callback pour événements streaming ASR"""
                event_type = event_data.get("event")

                if event_type == "speech_start":
                    logger.info(f"🗣️ [{short_uuid}] Speech START detected via streaming ASR")
                    detection_state["speech_ended"] = False  # Reset for new speech

                elif event_type == "speech_end":
                    detection_state["speech_ended"] = True
                    detection_state["speech_end_timestamp"] = time.time()

                    # Calculer temps écoulé depuis début monitoring
                    if detection_state["monitoring_start"]:
                        elapsed_ms = (detection_state["speech_end_timestamp"] - detection_state["monitoring_start"]) * 1000
                        logger.info(
                            f"🤐 [{short_uuid}] SPEECH_END at {elapsed_ms:.0f}ms "
                            f"({detection_state['partial_count']} partials received)"
                        )
                    else:
                        logger.info(
                            f"🤐 [{short_uuid}] SPEECH_END "
                            f"({detection_state['partial_count']} partials received)"
                        )

                elif event_type == "transcription":
                    text = event_data.get("text", "")
                    trans_type = event_data.get("type", "unknown")
                    latency = event_data.get("latency_ms", 0)

                    if trans_type == "partial":
                        # Tracker timestamps pour analyse latence
                        current_time = time.time()
                        if detection_state["first_partial_timestamp"] is None:
                            detection_state["first_partial_timestamp"] = current_time
                        detection_state["last_partial_timestamp"] = current_time
                        detection_state["partial_count"] += 1

                        # Calculer temps écoulé depuis début monitoring
                        elapsed_ms = 0
                        if detection_state["monitoring_start"]:
                            elapsed_ms = (current_time - detection_state["monitoring_start"]) * 1000

                        # Compter mots pour détecter barge-in (MIN_WORDS_FOR_BARGE_IN minimum)
                        words = text.strip().split()
                        word_count = len(words)
                        min_words = config.MIN_WORDS_FOR_BARGE_IN

                        if word_count >= min_words and not detection_state["barged_in"]:
                            detection_state["barged_in"] = True
                            detection_state["barge_in_timestamp"] = current_time
                            logger.info(
                                f"⚡ [{short_uuid}] BARGE-IN at {elapsed_ms:.0f}ms! "
                                f"(PARTIAL #{detection_state['partial_count']}: '{text}', {word_count} words >={min_words})"
                            )
                        else:
                            # Afficher comptage même si < min_words (pour debug/suivi)
                            logger.info(
                                f"📝 [{short_uuid}] PARTIAL #{detection_state['partial_count']} at {elapsed_ms:.0f}ms: "
                                f"'{text}' ({word_count} words <{min_words} - NO barge-in)"
                            )

                    elif trans_type == "final":
                        # Concaténer si on a déjà du contenu (évite perte sur multiples FINAL)
                        if text:
                            existing = detection_state.get("transcription", "")
                            if existing and len(existing.split()) >= 1:
                                # On a déjà au moins 1 mot → concaténer
                                detection_state["transcription"] = f"{existing} {text}"
                            else:
                                # Premier FINAL ou existant vide → écraser
                                detection_state["transcription"] = text
                            # Afficher transcription avec panel Rich visible
                            self.clog.transcription(text, uuid=short_uuid, latency_ms=latency)
                        elif not detection_state.get("transcription"):
                            # FINAL vide et pas de transcription → garder vide (silence)
                            detection_state["transcription"] = ""
                        # Sinon: FINAL vide mais on a du contenu → ne pas écraser
                        detection_state["final_received"] = True
                        detection_state["last_update"] = time.time()

            self.streaming_asr.register_callback(call_uuid, streaming_callback)

            # Étape 2: Démarrer audio fork → WebSocket
            fork_start = time.time()
            ws_url = f"ws://{config.STREAMING_ASR_HOST}:{config.STREAMING_ASR_PORT}/stream/{call_uuid}"
            fork_cmd = f"uuid_audio_fork {call_uuid} start {ws_url} mono 16000"
            fork_result = self._execute_esl_command(fork_cmd)

            if not fork_result or "+OK" not in fork_result:
                logger.error(f"❌ [{short_uuid}] Audio fork failed: {fork_result}")
                # Fallback to WebRTC VAD
                return self._execute_phase_playing(call_uuid, audio_path, enable_barge_in)

            fork_latency = (time.time() - fork_start) * 1000

            # === ATTENDRE INITIALISATION STREAM (évite race condition) ===
            stream_wait_start = time.time()
            max_stream_wait = 2.0  # Max 2s d'attente

            while call_uuid not in self.streaming_asr.active_streams:
                if (time.time() - stream_wait_start) > max_stream_wait:
                    logger.error(
                        f"❌ [{short_uuid}] WebSocket stream not initialized after {max_stream_wait}s"
                    )
                    try:
                        self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                    except:
                        pass
                    self.streaming_asr.unregister_callback(call_uuid)
                    return self._execute_phase_playing(call_uuid, audio_path, enable_barge_in)
                time.sleep(0.01)  # Poll every 10ms

            stream_init_latency = (time.time() - stream_wait_start) * 1000
            logger.debug(f"✅ [{short_uuid}] Stream initialized in {stream_init_latency:.0f}ms")

            # === ENERGY GATE: Appliquer noise floor calibré (si disponible) ===
            if call_uuid in self.call_sessions:
                saved_noise_floor = self.call_sessions[call_uuid].get("noise_floor_rms", 0)
                if saved_noise_floor > 0:
                    self.streaming_asr.set_noise_floor(call_uuid, saved_noise_floor)

            # === ENERGY GATE: Démarrer calibration si demandé ===
            if calibrate_noise:
                self.streaming_asr.start_noise_calibration(call_uuid)

            # Étape 3: Démarrer playback
            playback_start = time.time()

            # Utiliser uuid_broadcast pour playback (permet arrêt via uuid_break)
            playback_cmd = f"uuid_broadcast {call_uuid} {audio_path} aleg"
            playback_result = self._execute_esl_command(playback_cmd)

            if not playback_result or "+OK" not in playback_result:
                logger.error(f"❌ [{short_uuid}] Playback failed: {playback_result}")
                # Arrêter audio fork
                self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                return self._execute_phase_playing(call_uuid, audio_path, enable_barge_in)

            playback_latency = (time.time() - playback_start) * 1000

            # Étape 4: Attendre barge-in OU fin playback
            # Calculer durée audio réelle pour timeout précis
            audio_duration = self._get_audio_duration(audio_path)

            # Pour steps terminaux (bye), jouer audio jusqu'au bout (pas d'early exit)
            # Pour steps normaux, early exit Xs avant la fin pour démarrer Phase 3 plus vite
            if is_terminal:
                timeout = audio_duration
                logger.debug(
                    f"⏱️ [{short_uuid}] TERMINAL step - playing full audio "
                    f"(duration: {audio_duration:.1f}s, NO early exit)"
                )
            else:
                timeout = audio_duration - config.PHASE2_EARLY_EXIT
                logger.debug(
                    f"⏱️ [{short_uuid}] Monitoring for barge-in "
                    f"(audio: {audio_duration:.1f}s, early exit: {timeout:.1f}s, "
                    f"Phase 3 starts {config.PHASE2_EARLY_EXIT}s before audio ends)"
                )

            # Définir monitoring_start APRÈS playback pour calculs précis
            monitoring_start = time.time()
            detection_state["monitoring_start"] = monitoring_start

            while (time.time() - monitoring_start) < timeout:
                current_time = time.time()

                # ===== ULTRA-FAST HANGUP DETECTION (20ms polling) =====
                # Vérification 1: Flag session (setté par HANGUP handler)
                session = self.call_sessions.get(call_uuid, {})
                if session.get("hangup_detected", False):
                    hangup_ts = session.get("hangup_timestamp", 0)
                    detection_delay_ms = (current_time - hangup_ts) * 1000
                    logger.warning(
                        f"🚨 [{short_uuid}] HANGUP FLAG detected in Phase 2! "
                        f"Detection delay: {detection_delay_ms:.1f}ms - STOPPING PLAYBACK!"
                    )
                    break

                # Vérification 2: ESL DIRECT (instantané, pas besoin d'attendre HANGUP EVENT!)
                if not self._channel_exists(call_uuid):
                    logger.warning(
                        f"🚨 [{short_uuid}] Channel NO LONGER EXISTS (ESL check) - STOPPING PLAYBACK!"
                    )
                    break

                # Legacy check (moins fiable)
                if call_uuid not in self.active_calls:
                    logger.info(
                        f"[{short_uuid}] Call removed from active_calls during Phase 2"
                    )
                    break

                # Check if barge-in detected (via callback on 5+ words)
                if detection_state["barged_in"]:
                    barge_in_time = (time.time() - monitoring_start) * 1000

                    # Progressive fade-out during smooth delay
                    # Reduce volume from 0 dB to -40 dB over 0.3s (10 steps)
                    logger.info(f"🔉 [{short_uuid}] Fade-out + smooth delay: {config.BARGE_IN_SMOOTH_DELAY}s...")

                    fade_steps = 10
                    step_duration = config.BARGE_IN_SMOOTH_DELAY / fade_steps

                    for step in range(fade_steps):
                        # Calculate volume: 0 dB → -40 dB (linear fade)
                        volume_db = -4 * step  # 0, -4, -8, -12, ..., -36
                        volume_level = volume_db / 4.0  # FreeSWITCH uses -4 to +4 range

                        # Apply volume adjustment
                        audio_cmd = f"uuid_audio {call_uuid} start write level {volume_level}"
                        self._execute_esl_command(audio_cmd)

                        time.sleep(step_duration)

                    # Stop audio playback
                    break_cmd = f"uuid_break {call_uuid}"
                    self._execute_esl_command(break_cmd)

                    # Reset audio level to normal
                    reset_cmd = f"uuid_audio {call_uuid} start write level 0"
                    self._execute_esl_command(reset_cmd)

                    logger.info(f"🔇 [{short_uuid}] Audio stopped (fade-out complete)")

                    # Attendre que le client finisse de parler
                    speech_end_wait_start = time.time()
                    while not detection_state["speech_ended"] and call_uuid in self.active_calls:
                        # HANGUP check même pendant l'attente speech_end!
                        session = self.call_sessions.get(call_uuid, {})
                        if session.get("hangup_detected", False):
                            logger.warning(
                                f"🚨 [{short_uuid}] HANGUP during speech_ended wait in Phase 2!"
                            )
                            break
                        time.sleep(0.02)  # Poll every 20ms

                    speech_end_wait_latency = (time.time() - speech_end_wait_start) * 1000

                    # Breathing room (pause naturelle)
                    time.sleep(config.BARGE_IN_BREATHING_ROOM)

                    # CRITIQUE: Attendre transcription FINALE (max 1500ms)
                    # Vosk peut prendre 100-600ms selon longueur de la phrase
                    final_wait_start = time.time()
                    max_final_wait = 1.5  # 1500ms timeout (comme Phase 3, pour phrases longues)

                    while (time.time() - final_wait_start) < max_final_wait:
                        # HANGUP check même pendant l'attente FINAL!
                        session = self.call_sessions.get(call_uuid, {})
                        if session.get("hangup_detected", False):
                            logger.warning(
                                f"🚨 [{short_uuid}] HANGUP during FINAL wait in Phase 2!"
                            )
                            break

                        if detection_state["final_received"]:
                            break
                        time.sleep(0.02)  # Poll every 20ms (faster!)

                    final_wait_latency = (time.time() - final_wait_start) * 1000

                    if not detection_state["final_received"]:
                        logger.warning(
                            f"⚠️ [{short_uuid}] No FINAL after {final_wait_latency:.0f}ms, "
                            f"using last transcription"
                        )

                    break

                # Petit sleep pour ne pas surcharger CPU (20ms au lieu de 100ms)
                time.sleep(0.02)

            # Fin du monitoring (timeout atteint ou barge-in/hangup)
            if not detection_state["barged_in"] and call_uuid in self.active_calls:
                detection_state["audio_finished"] = True
                # Early exit optimization: monitoring stopped but audio still playing!
                # Phase 3 will start while last second of audio continues in background
                remaining_audio = audio_duration - (time.time() - monitoring_start)
                if remaining_audio > 0:
                    logger.info(
                        f"🎯 [{short_uuid}] Phase 2 monitoring ended early "
                        f"(audio still playing for ~{remaining_audio:.1f}s, "
                        f"Phase 3 will start immediately)"
                    )

            # Étape 5: Arrêter audio fork (but NOT uuid_break - let audio finish naturally)
            self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")

            # === ENERGY GATE: Arrêter calibration et calculer noise floor ===
            if calibrate_noise:
                noise_floor = self.streaming_asr.stop_noise_calibration(call_uuid)
                # Stocker dans call_sessions pour réutiliser dans les phases suivantes
                if noise_floor > 0 and call_uuid in self.call_sessions:
                    self.call_sessions[call_uuid]["noise_floor_rms"] = noise_floor
                    logger.info(f"🎚️ [{short_uuid}] Noise floor saved to session: {noise_floor:.0f}")

            # CRITICAL: Attendre que WebSocket se ferme complètement (évite race condition)
            time.sleep(0.1)

            # Unregister callback (safe maintenant, plus de transcriptions en vol)
            self.streaming_asr.unregister_callback(call_uuid)

            # Calculer latence totale
            phase_duration = (time.time() - phase_start) * 1000

            # Compact latency breakdown (single line) avec décomposition détaillée
            if detection_state["barged_in"]:
                # Calculer timings précis
                first_word_ms = 0
                speaking_ms = 0
                barge_in_detect_ms = 0

                if detection_state["first_partial_timestamp"]:
                    first_word_ms = (detection_state["first_partial_timestamp"] - monitoring_start) * 1000

                    if detection_state["barge_in_timestamp"]:
                        # Speaking = durée entre premier et dernier PARTIAL avant barge-in
                        if detection_state["last_partial_timestamp"]:
                            speaking_ms = (detection_state["last_partial_timestamp"] - detection_state["first_partial_timestamp"]) * 1000

                        # BargeInDetect = délai système pour détecter barge-in (après dernier PARTIAL)
                        barge_in_detect_ms = (detection_state["barge_in_timestamp"] - detection_state["last_partial_timestamp"]) * 1000 if detection_state["last_partial_timestamp"] else 0

                logger.info(
                    f"📊 [{short_uuid}] PHASE 2: Gap={gap_to_phase2:.0f}ms | Fork={fork_latency:.0f}ms | "
                    f"Play={playback_latency:.0f}ms | FirstWord={first_word_ms:.0f}ms | "
                    f"Speaking={speaking_ms:.0f}ms | BargeInDetect={barge_in_detect_ms:.0f}ms | "
                    f"SpeechEndWait={speech_end_wait_latency:.0f}ms | FinalWait={final_wait_latency:.0f}ms | "
                    f"TOTAL={phase_duration:.0f}ms ({detection_state['partial_count']} partials)"
                )
            else:
                logger.info(
                    f"📊 [{short_uuid}] PHASE 2: Gap={gap_to_phase2:.0f}ms | Fork={fork_latency:.0f}ms | "
                    f"Play={playback_latency:.0f}ms | NoBargeIn | TOTAL={phase_duration:.0f}ms ({detection_state['partial_count']} partials)"
                )

            logger.info(
                f"✅ [{short_uuid}] PHASE 2 completed: "
                f"barge_in={detection_state['barged_in']}, "
                f"transcription='{detection_state['transcription']}', "
                f"duration={phase_duration:.0f}ms"
            )

            # PHASE 2 END - Colored log
            self.clog.phase2_end(phase_duration, uuid=short_uuid)

            # Store end timestamp for gap calculation
            if call_uuid in self.call_sessions:
                self.call_sessions[call_uuid]["phase2_end_timestamp"] = time.time()

            return {
                "barged_in": detection_state["barged_in"],
                "transcription": detection_state["transcription"],
                "audio_duration": phase_duration / 1000.0,
                "latency_ms": phase_duration
            }

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] Streaming ASR error: {e}", exc_info=True)

            # Cleanup
            try:
                self._execute_esl_command(f"uuid_audio_fork {call_uuid} stop")
                self._execute_esl_command(f"uuid_break {call_uuid}")
                self.streaming_asr.unregister_callback(call_uuid)
            except:
                pass

            # Fallback to WebRTC VAD
            logger.warning(f"⚠️ [{short_uuid}] Falling back to WebRTC VAD method")
            return self._execute_phase_playing(call_uuid, audio_path, enable_barge_in)

    def _monitor_vad_playing(
        self,
        call_uuid: str,
        record_file: str,
        state: Dict[str, Any]
    ):
        """
        Transcription-based monitoring thread for Phase 2 PLAYING

        Monitors for barge-in using continuous background transcription
        instead of VAD frame-by-frame (which cannot read WAV while FreeSWITCH writes)

        Strategy:
        - Launch background transcription snapshots every 0.5s
        - Estimate speech duration from transcription word count
        - Trigger barge-in if estimated duration > 1.5s
        - Intelligent detection: ignore short responses ("oui", "ok", etc.)

        Args:
            call_uuid: Call UUID
            record_file: Recording file path
            state: Shared state dict (modified in-place)
        """
        short_uuid = call_uuid[:8]
        monitoring_start_time = time.time()

        # Transcription monitoring state
        bg_thread = None
        snapshot_file = None
        last_snapshot_time = None
        snapshot_interval = 0.5  # Take snapshot every 0.5s

        # End-of-speech detection (consecutive identical transcriptions)
        last_transcription = None
        identical_count = 0
        identical_threshold = 3  # 3 identical = client finished speaking

        # Track speech start time for accurate duration (from start of CURRENT speech)
        speech_start_time = None  # Timestamp when client starts speaking (reset on silence)

        logger.info(
            f"🎙️ [{short_uuid}] Transcription-based monitoring started "
            f"(snapshot_interval: {snapshot_interval}s, barge-in threshold: {config.BARGE_IN_THRESHOLD}s, "
            f"max 1 barge-in per phase)"
        )

        try:
            # Wait for WAV file to be created
            retries = 0
            while not Path(record_file).exists() and retries < 20:
                time.sleep(0.05)
                retries += 1

            if not Path(record_file).exists():
                logger.warning(f"⚠️ [{short_uuid}] Recording file not found for monitoring")
                return

            wait_time = time.time() - monitoring_start_time
            logger.info(f"✅ [{short_uuid}] Recording file detected (wait: {wait_time*1000:.0f}ms)")

            # Main monitoring loop: poll transcription state every 100ms
            loop_iteration = 0
            while not state["stop_monitoring"]:
                current_time = time.time()
                elapsed_time = current_time - monitoring_start_time
                loop_iteration += 1

                # Launch background transcription snapshot every 0.5s
                if last_snapshot_time is None or (current_time - last_snapshot_time) >= snapshot_interval:
                    if Path(record_file).exists():
                        # Create snapshot with .wav extension for ffmpeg output format detection
                        snapshot_file = f"/tmp/snapshot_{call_uuid}_{int(current_time * 1000)}.wav"

                        try:
                            # Extract client MONO audio from RAW recording (client-only stream)
                            # RAW format allows real-time reading while FreeSWITCH writes
                            import subprocess

                            logger.debug(
                                f"📸 [{short_uuid}] Extracting client MONO from RAW snapshot "
                                f"at {elapsed_time:.1f}s"
                            )

                            extract_cmd = [
                                "ffmpeg",
                                "-f", "s16le",        # RAW format: signed 16-bit little-endian
                                "-ar", "8000",        # Sample rate: 8kHz (FreeSWITCH default)
                                "-ac", "1",           # Channels: 1 (MONO client-only)
                                "-i", record_file,    # Input RAW file
                                "-t", str(elapsed_time),  # CRITICAL: Read only elapsed time (file still being written)
                                "-y",                 # Overwrite
                                snapshot_file         # Output WAV file
                            ]

                            result = subprocess.run(
                                extract_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                timeout=5
                            )

                            if result.returncode != 0:
                                error_msg = result.stderr.decode('utf-8', errors='ignore').strip()
                                logger.error(
                                    f"❌ [{short_uuid}] ffmpeg extraction failed "
                                    f"(returncode: {result.returncode}): {error_msg[-200:]}"  # Last 200 chars
                                )
                                continue  # Skip this snapshot

                            last_snapshot_time = current_time

                            logger.info(
                                f"📸 [{short_uuid}] Snapshot created at {elapsed_time:.1f}s "
                                f"(iteration: {loop_iteration}, client audio only)"
                            )

                            # Launch background transcription thread
                            bg_thread = threading.Thread(
                                target=self._background_transcribe_snapshot,
                                args=(snapshot_file, state),
                                daemon=True
                            )
                            bg_thread.start()

                        except subprocess.TimeoutExpired:
                            logger.error(f"❌ [{short_uuid}] ffmpeg extraction timeout (>5s)")
                        except Exception as e:
                            logger.error(f"❌ [{short_uuid}] Snapshot error: {e}")

                # Check transcription state for barge-in detection
                if state["bg_ready"]:
                    transcription = state["transcription"].strip() if state["transcription"] else ""

                    # Detect speech START (first non-empty transcription)
                    if transcription and speech_start_time is None:
                        speech_start_time = current_time
                        logger.info(
                            f"🗣️ [{short_uuid}] Speech START detected at {elapsed_time:.1f}s: '{transcription}'"
                        )

                    # Reset speech timer on silence (empty transcription)
                    elif not transcription and speech_start_time is not None:
                        logger.debug(
                            f"🔇 [{short_uuid}] Silence detected at {elapsed_time:.1f}s, resetting speech timer"
                        )
                        speech_start_time = None
                        identical_count = 0
                        last_transcription = None

                    # Calculate REAL speech duration (from start of CURRENT speech, not from recording start)
                    if speech_start_time is not None:
                        speech_duration = current_time - speech_start_time
                    else:
                        speech_duration = 0.0

                    # Log transcription with REAL speech duration
                    if transcription:
                        logger.info(
                            f"📝 [{short_uuid}] Transcription at {elapsed_time:.1f}s: "
                            f"'{transcription}' (speech duration: {speech_duration:.1f}s)"
                        )

                        # Simple logic: > 1.5s = barge-in trigger (ONE TIME ONLY per phase)
                        if speech_duration >= config.BARGE_IN_THRESHOLD and not state["barged_in"]:
                            logger.info(
                                f"⚡ [{short_uuid}] BARGE-IN TRIGGERED at {elapsed_time:.1f}s! "
                                f"(speech duration: {speech_duration:.1f}s > {config.BARGE_IN_THRESHOLD}s) "
                                f"[ONE-TIME ONLY]"
                            )
                            logger.info(f"🎧 [{short_uuid}] Continuing to listen for complete transcription...")
                            state["barged_in"] = True
                            state["barge_in_time"] = elapsed_time
                            # NO break! Continue monitoring to get complete transcription

                        # End-of-speech detection: check for consecutive identical transcriptions
                        if state["barged_in"]:
                            if transcription == last_transcription:
                                identical_count += 1
                                logger.debug(
                                    f"🔄 [{short_uuid}] Identical transcription #{identical_count}/{identical_threshold}: '{transcription}'"
                                )

                                if identical_count >= identical_threshold:
                                    logger.info(
                                        f"🏁 [{short_uuid}] Client finished speaking at {elapsed_time:.1f}s "
                                        f"(final transcription: '{transcription}', speech duration: {speech_duration:.1f}s)"
                                    )
                                    break  # Exit only when client stops speaking
                            else:
                                # New transcription -> client still speaking
                                if identical_count > 0:
                                    logger.debug(
                                        f"🔄 [{short_uuid}] New transcription (was {identical_count} identical): '{transcription}'"
                                    )
                                identical_count = 0
                                last_transcription = transcription

                    # Reset state for next snapshot
                    state["bg_ready"] = False

                # Small delay between checks (100ms)
                time.sleep(0.1)

            total_time = time.time() - monitoring_start_time
            logger.info(
                f"🏁 [{short_uuid}] Monitoring ended (duration: {total_time:.1f}s, "
                f"iterations: {loop_iteration}, barged_in: {state['barged_in']})"
            )

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] Monitoring error: {e}", exc_info=True)

    def _background_transcribe_snapshot(
        self,
        snapshot_file: str,
        state: Dict[str, Any]
    ):
        """
        Background transcription thread

        Transcribes snapshot file and stores result in state

        Args:
            snapshot_file: Snapshot WAV file
            state: Shared state dict (modified in-place)
        """
        transcribe_start = time.time()
        snapshot_name = Path(snapshot_file).name

        logger.info(f"🚀 Background transcription started: {snapshot_name}")

        try:
            # Transcribe snapshot
            result = self.stt_service.transcribe_file(snapshot_file)
            transcription = result.get("text", "").strip()
            audio_duration = result.get("duration", 0.0)  # Real duration from STT
            transcribe_duration = time.time() - transcribe_start

            # Store result in shared state
            state["transcription"] = transcription
            state["audio_duration"] = audio_duration  # Store real duration
            state["bg_ready"] = True

            logger.info(
                f"✅ Background transcription completed in {transcribe_duration*1000:.0f}ms: "
                f"'{transcription}' (snapshot: {snapshot_name})"
            )

            # Cleanup snapshot
            try:
                Path(snapshot_file).unlink()
                logger.debug(f"🗑️ Snapshot cleaned: {snapshot_name}")
            except Exception as cleanup_error:
                logger.debug(f"⚠️ Snapshot cleanup failed: {cleanup_error}")

        except Exception as e:
            transcribe_duration = time.time() - transcribe_start
            logger.error(
                f"❌ Background transcription failed after {transcribe_duration*1000:.0f}ms: {e} "
                f"(snapshot: {snapshot_name})"
            )
            state["bg_ready"] = False

    def _execute_phase_waiting(
        self,
        call_uuid: str,
        timeout: float = None
    ) -> Dict[str, Any]:
        """
        Phase 3: WAITING (Listen for client response)

        Simple:
        - Record MONO (robot not speaking)
        - VAD monitoring for end-of-speech (0.6s silence)
        - Background transcription (snapshot at 0.5s)
        - Timeout for silence (3s → retry_silence)

        Args:
            call_uuid: Call UUID
            timeout: Silence timeout (default: WAITING_SILENCE_TIMEOUT)

        Returns:
            {
                "transcription": str,
                "silence": bool,
                "latency_ms": float
            }
        """
        short_uuid = call_uuid[:8]
        phase_start = time.time()

        if timeout is None:
            timeout = config.WAITING_SILENCE_TIMEOUT

        # PHASE 3 START - Colored log (MAGENTA panel with rounded border)
        self.clog.phase3_start(uuid=short_uuid)

        # Recording file
        record_file = f"/tmp/waiting_{call_uuid}.wav"

        # Shared state for VAD monitoring
        monitoring_state = {
            "speech_detected": False,
            "end_of_speech": False,
            "silence_timeout": False,
            "transcription": None,
            "bg_ready": False,
            "stop_monitoring": False
        }

        try:
            # Step 1: Start recording MONO
            if not self._start_recording(call_uuid, record_file, stereo=False):
                logger.error(f"❌ [{short_uuid}] WAITING: Recording start failed!")
                return {
                    "transcription": "",
                    "silence": True,
                    "latency_ms": 0.0
                }

            # Step 2: Monitor VAD for end-of-speech
            vad_thread = threading.Thread(
                target=self._monitor_vad_waiting,
                args=(call_uuid, record_file, timeout, monitoring_state),
                daemon=True
            )
            vad_thread.start()

            # Wait for end-of-speech or timeout
            while not monitoring_state["end_of_speech"] and not monitoring_state["silence_timeout"]:
                time.sleep(0.1)

            # Stop monitoring
            monitoring_state["stop_monitoring"] = True
            vad_thread.join(timeout=1.0)

            # Step 3: Stop recording
            self._stop_recording(call_uuid, record_file)

            # CRITICAL: Wait for FreeSWITCH to finalize WAV file
            # Poll until file is stable (not growing anymore)
            max_wait = 1.0  # Max 1 second
            poll_start = time.time()
            last_size = 0

            while (time.time() - poll_start) < max_wait:
                if Path(record_file).exists():
                    current_size = Path(record_file).stat().st_size
                    if current_size > 1000 and current_size == last_size:
                        break
                    last_size = current_size
                time.sleep(0.05)  # Poll every 50ms

            # Step 4: Get transcription
            transcription = ""
            if monitoring_state["speech_detected"]:
                # Check if background transcription ready
                if monitoring_state["bg_ready"] and monitoring_state["transcription"]:
                    transcription = monitoring_state["transcription"]
                    logger.info(f"🚀 [{short_uuid}] Background transcription ready!")
                else:
                    # Fallback: sync transcription
                    logger.info(f"🔄 [{short_uuid}] Fallback sync transcription...")
                    result = self.stt_service.transcribe_file(record_file)
                    transcription = result.get("text", "").strip()

                # Transcription - Colored log (CYAN panel)
                self.clog.transcription(transcription, uuid=short_uuid)
            else:
                logger.info(f"🔇 [{short_uuid}] No speech detected (silence)")

            # Cleanup
            try:
                Path(record_file).unlink()
            except:
                pass

            # Total latency
            total_latency = (time.time() - phase_start) * 1000

            # PHASE 3 END - Colored log (MAGENTA panel)
            self.clog.phase3_end(total_latency, uuid=short_uuid)

            return {
                "transcription": transcription,
                "silence": monitoring_state["silence_timeout"],
                "latency_ms": total_latency
            }

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] WAITING error: {e}")
            import traceback
            traceback.print_exc()

            # Cleanup
            try:
                self._stop_recording(call_uuid, record_file)
                Path(record_file).unlink()
            except:
                pass

            return {
                "transcription": "",
                "silence": True,
                "latency_ms": 0.0
            }

    def _monitor_vad_waiting(
        self,
        call_uuid: str,
        record_file: str,
        silence_timeout: float,
        state: Dict[str, Any]
    ):
        """
        VAD monitoring thread for Phase 3 WAITING

        Monitors for end-of-speech (0.6s silence after speech)
        Launches background transcription at 0.5s

        Args:
            call_uuid: Call UUID
            record_file: Recording file path
            silence_timeout: Timeout if no speech detected (seconds)
            state: Shared state dict (modified in-place)
        """
        short_uuid = call_uuid[:8]

        # VAD state
        speech_frames = 0
        speech_start_time = None
        speech_duration = 0.0
        last_speech_time = None
        silence_duration = 0.0
        bg_thread = None
        snapshot_file = None

        # Frame params
        frame_duration_ms = config.WEBRTC_VAD_FRAME_DURATION_MS
        sample_rate = config.WEBRTC_VAD_SAMPLE_RATE

        try:
            # Wait for WAV file
            retries = 0
            while not Path(record_file).exists() and retries < 20:
                time.sleep(0.05)
                retries += 1

            if not Path(record_file).exists():
                logger.warning(f"⚠️ [{short_uuid}] Recording file not found for VAD")
                state["silence_timeout"] = True
                return

            # Small delay for WAV header
            time.sleep(0.1)

            # Timeout tracking - START AFTER file wait to avoid hidden delays
            start_time = time.time()

            logger.info(f"👂 [{short_uuid}] VAD monitoring started")

            # Stream frames from WAV
            for frame in self._get_audio_frames_from_wav(record_file, frame_duration_ms=frame_duration_ms):
                if state["stop_monitoring"]:
                    break

                # Check silence timeout (if no speech yet)
                if not state["speech_detected"]:
                    elapsed = time.time() - start_time
                    if elapsed >= silence_timeout:
                        logger.info(
                            f"🔇 [{short_uuid}] Silence timeout ({silence_timeout}s) → retry_silence"
                        )
                        state["silence_timeout"] = True
                        break

                # Check if frame is speech
                try:
                    is_speech = self.vad.is_speech(frame, sample_rate)
                except:
                    continue

                if is_speech:
                    last_speech_time = time.time()

                    if speech_start_time is None:
                        # Start of speech
                        speech_start_time = time.time()
                        speech_frames = 1
                    else:
                        speech_frames += 1
                        speech_duration = time.time() - speech_start_time

                    # Check for start speech detection (0.3s)
                    if speech_duration >= config.WAITING_START_SPEECH_DURATION:
                        if not state["speech_detected"]:
                            logger.info(f"🗣️ [{short_uuid}] Start speech detected ({speech_duration:.1f}s)")
                            state["speech_detected"] = True

                    # Launch background transcription at 0.5s
                    if speech_duration >= config.WAITING_BG_TRANSCRIBE_TRIGGER and bg_thread is None:
                        logger.info(
                            f"⏱️ [{short_uuid}] Speech {speech_duration:.1f}s "
                            f"→ 🚀 Launching background transcription"
                        )

                        # Create snapshot
                        snapshot_file = f"{record_file}.snapshot"
                        try:
                            import shutil
                            shutil.copy2(record_file, snapshot_file)

                            # Launch background thread
                            bg_thread = threading.Thread(
                                target=self._background_transcribe_snapshot,
                                args=(snapshot_file, state),
                                daemon=True
                            )
                            bg_thread.start()
                        except Exception as e:
                            logger.error(f"❌ [{short_uuid}] Snapshot error: {e}")

                else:
                    # Silence
                    if last_speech_time is not None:
                        silence_duration = time.time() - last_speech_time

                        # Check for end-of-speech (0.6s silence after speech)
                        if silence_duration >= config.SILENCE_THRESHOLD:
                            logger.info(
                                f"✅ [{short_uuid}] End-of-speech detected "
                                f"(silence: {silence_duration:.1f}s)"
                            )
                            state["end_of_speech"] = True
                            break

                # Small delay
                time.sleep(0.01)

            logger.info(f"👂 [{short_uuid}] VAD monitoring ended")

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] VAD monitoring error: {e}")

    # ========================================================================
    # ESL HELPERS (Audio recording, commands, hangup)
    # ========================================================================

    def _record_audio(self, call_uuid: str, duration: float, filename: str) -> bool:
        """
        Record audio from call

        Uses FreeSWITCH uuid_record command
        - Records to .wav file (8kHz mono by default)
        - Blocks for duration + small margin
        - Returns True if successful

        Args:
            call_uuid: Call UUID
            duration: Recording duration in seconds
            filename: Output .wav file path

        Returns:
            True if recording successful, False otherwise
        """
        short_uuid = call_uuid[:8]

        try:
            # Start recording
            # uuid_record <uuid> start <filename> [time_limit_secs]
            cmd = f"uuid_record {call_uuid} start {filename} {int(duration)}"

            result = self._execute_esl_command(cmd)

            if not result or "+OK" not in result:
                logger.error(f"[{short_uuid}] Record start failed: {result}")
                return False

            logger.debug(f"[{short_uuid}] Recording started -> {filename}")

            # Wait for recording duration + small margin
            time.sleep(duration + 0.1)

            # Stop recording
            stop_cmd = f"uuid_record {call_uuid} stop {filename}"
            stop_result = self._execute_esl_command(stop_cmd)

            logger.debug(f"[{short_uuid}] Recording stopped: {stop_result}")

            # Check file exists
            if not Path(filename).exists():
                logger.error(f"[{short_uuid}] Audio file not created: {filename}")
                return False

            # Check file size (should be >0 bytes)
            file_size = Path(filename).stat().st_size
            if file_size == 0:
                logger.error(f"[{short_uuid}] Audio file is empty: {filename}")
                return False

            logger.debug(
                f"[{short_uuid}] Recording successful: {filename} ({file_size} bytes)"
            )

            return True

        except Exception as e:
            logger.error(f"[{short_uuid}] Recording error: {e}")
            return False

    def _execute_esl_command(self, cmd: str) -> Optional[str]:
        """
        Execute ESL API command (THREAD-SAFE)

        Args:
            cmd: ESL command (e.g. "uuid_record <uuid> start ...")

        Returns:
            Command result body or None if error
        """
        with self.esl_api_lock:  # CRITICAL: Thread-safe access to ESL API connection
            try:
                if not self.esl_conn_api:
                    logger.error("ESL API connection not available")
                    return None

                if not self.esl_conn_api.connected():
                    logger.error(f"ESL API connection lost, attempting to send: {cmd}")
                    return None

                result = self.esl_conn_api.api(cmd)

                if not result:
                    logger.error(f"❌ ESL api() returned None object: {cmd}")
                    return None

                body = result.getBody()

                if body is None:
                    logger.error(f"❌ ESL getBody() returned None for cmd: {cmd}")
                    return None
                return body

            except Exception as e:
                logger.error(f"ESL command error for '{cmd}': {e}", exc_info=True)
                return None

    def _channel_exists(self, call_uuid: str) -> bool:
        """
        Vérification ULTRA-RAPIDE si le canal FreeSWITCH existe encore.

        CRITIQUE pour détecter HANGUP instantanément sans attendre MEDIA_TIMEOUT!
        uuid_exists est instantané (<1ms) car vérifie directement dans FreeSWITCH core.

        Args:
            call_uuid: UUID du call

        Returns:
            True si canal existe, False sinon
        """
        result = self._execute_esl_command(f"uuid_exists {call_uuid}")
        exists = result and "true" in result.lower()

        # Debug logging pour tracer les vérifications
        short_uuid = call_uuid[:8]
        if not exists:
            logger.info(f"⚡ [{short_uuid}] uuid_exists returned: {result} -> Channel GONE!")

        return exists

    def _execute_sendmsg(self, uuid: str, app_name: str, app_args: str = "") -> Optional[str]:
        """
        Execute dialplan application via sendmsg (for apps not available as API commands)

        CRITICAL: play_and_detect_speech is a DIALPLAN application only
        Use bgapi uuid_broadcast with special syntax OR separate detect_speech+uuid_broadcast

        Args:
            uuid: Call UUID
            app_name: Application name (e.g. "play_and_detect_speech")
            app_args: Application arguments

        Returns:
            Command result or None if error
        """
        try:
            if not self.esl_conn_api:
                logger.error("ESL API connection not available for execute")
                return None

            # WORKAROUND: For play_and_detect_speech, we split into 2 commands:
            # 1. Start detect_speech first
            # 2. Then uuid_broadcast for playback
            # This is the only way to use it from ESL API

            if app_name == "play_and_detect_speech" and app_args:
                # Parse args: "audio_file detect:vosk {grammars=/tmp/file.xml}"
                parts = app_args.split(" detect:")
                if len(parts) == 2:
                    audio_file = parts[0]
                    detect_params = "detect:" + parts[1]

                    # Execute detect_speech FIRST (application dialplan via bgapi)
                    detect_cmd = f"uuid_broadcast {uuid} gentones::%(500,0,350) aleg"
                    self._execute_esl_command(detect_cmd)  # Prime the channel

                    logger.warning(
                        f"⚠️  play_and_detect_speech not directly callable from ESL API. "
                        f"Using separate detect_speech + uuid_broadcast as workaround"
                    )

                    # Fallback: just play audio
                    play_cmd = f"uuid_broadcast {uuid} {audio_file} aleg"
                    return self._execute_esl_command(play_cmd)

            return None

        except Exception as e:
            logger.error(f"ESL sendmsg error: {e}")
            return None

    def _hangup_call(self, call_uuid: str, status = CallStatus.COMPLETED):
        """
        Hangup call and update database

        CRITICAL: Mark robot_hangup flag BEFORE executing hangup
        so that CHANNEL_HANGUP_COMPLETE handler knows robot initiated it

        Args:
            call_uuid: Call UUID
            status: CallStatus or CallResult (NO_ANSWER, COMPLETED, LEADS, NOT_INTERESTED, etc.)
        """
        short_uuid = call_uuid[:8]

        try:
            logger.info(f"[{short_uuid}] Robot hanging up call (status: {status.value})")

            # ===================================================================
            # CRITICAL: Mark robot-initiated hangup BEFORE executing
            # ===================================================================
            # This flag is checked by _handle_channel_hangup() to distinguish
            # robot hangup vs client hangup (for NOT_INTERESTED detection)

            if call_uuid not in self.call_sessions:
                self.call_sessions[call_uuid] = {}

            self.call_sessions[call_uuid]["robot_hangup"] = True
            self.call_sessions[call_uuid]["final_status"] = status

            logger.debug(
                f"[{short_uuid}] Marked robot_hangup=True, "
                f"final_status={status.value}"
            )

            # ===================================================================
            # Execute hangup via ESL
            # ===================================================================
            cmd = f"uuid_kill {call_uuid}"
            result = self._execute_esl_command(cmd)

            logger.debug(f"[{short_uuid}] Hangup command result: {result}")

            # Note: Database update happens in _handle_channel_hangup()
            # after CHANNEL_HANGUP_COMPLETE event is received

            logger.info(f"[{short_uuid}] Call hangup initiated successfully")

        except Exception as e:
            logger.error(f"[{short_uuid}] Hangup error: {e}")

    # ========================================================================
    # RECORDING HELPERS (Granular control for Background Transcription)
    # ========================================================================

    def _start_recording(
        self,
        call_uuid: str,
        file_path: str,
        stereo: bool = False,
        client_only: bool = False
    ) -> bool:
        """
        Start recording audio from call (non-blocking)

        Args:
            call_uuid: Call UUID
            file_path: Output file path (RAW or WAV)
            stereo: Enable stereo recording (left=client, right=robot) - PHASE 1 AMD
            client_only: Record ONLY client audio (read leg) - PHASE 2 PLAYING

        Returns:
            True if recording started successfully
        """
        short_uuid = call_uuid[:8]

        try:
            if client_only:
                # PHASE 2: Record MONO client audio only (read leg)
                # No STEREO, direct capture of inbound stream (from client)
                # read = FreeSWITCH RECEIVES from client (client speaking)
                # This prevents robot audio from "bleeding" into recording
                logger.info(f"[{short_uuid}] Starting MONO recording (client audio only, read leg)")
                cmd = f"uuid_record {call_uuid} start {file_path} read"

            elif stereo:
                # PHASE 1 AMD: Record STEREO (both legs)
                # Set STEREO (MUST be before uuid_record)
                stereo_cmd = f"uuid_setvar {call_uuid} RECORD_STEREO true"
                stereo_result = self._execute_esl_command(stereo_cmd)
                logger.debug(f"[{short_uuid}] STEREO enabled: {stereo_result}")
                cmd = f"uuid_record {call_uuid} start {file_path}"

            else:
                # Default: MONO both legs mixed
                cmd = f"uuid_record {call_uuid} start {file_path}"

            # Start recording (non-blocking)
            result = self._execute_esl_command(cmd)

            if not result or "+OK" not in result:
                logger.error(
                    f"[{short_uuid}] Recording start failed: {result}"
                )
                return False

            mode = "MONO client-only" if client_only else ("STEREO" if stereo else "MONO mixed")
            logger.debug(
                f"[{short_uuid}] Recording started: {file_path} (mode: {mode})"
            )
            return True

        except Exception as e:
            logger.error(f"[{short_uuid}] Start recording error: {e}")
            return False

    def _stop_recording(self, call_uuid: str, file_path: str) -> bool:
        """
        Stop recording audio (non-blocking)

        Args:
            call_uuid: Call UUID
            file_path: WAV file path (same as start)

        Returns:
            True if recording stopped successfully
        """
        short_uuid = call_uuid[:8]

        try:
            cmd = f"uuid_record {call_uuid} stop {file_path}"
            result = self._execute_esl_command(cmd)

            logger.debug(f"[{short_uuid}] Recording stopped: {result}")

            # Wait small delay for WAV finalization
            time.sleep(0.05)

            # Check file exists
            if not Path(file_path).exists():
                logger.warning(
                    f"[{short_uuid}] Audio file not found: {file_path}"
                )
                return False

            # Check file size
            file_size = Path(file_path).stat().st_size
            if file_size == 0:
                logger.warning(
                    f"[{short_uuid}] Audio file empty: {file_path}"
                )
                return False

            logger.debug(
                f"[{short_uuid}] Recording stopped: {file_path} "
                f"({file_size} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"[{short_uuid}] Stop recording error: {e}")
            return False

    def _extract_left_channel_stereo(self, stereo_frame: bytes) -> bytes:
        """
        Extract left channel (client audio) from stereo frame

        Stereo frame format (interleaved):
        [L0_low, L0_high, R0_low, R0_high, L1_low, L1_high, ...]

        Args:
            stereo_frame: Stereo audio frame (interleaved 16-bit samples)

        Returns:
            Mono frame (left channel only)
        """
        # Extract left channel: bytes[0::4] + bytes[1::4]
        # This gets every other 16-bit sample (skipping right channel)
        left_low = stereo_frame[0::4]   # Low bytes of left samples
        left_high = stereo_frame[1::4]  # High bytes of left samples

        # Reconstruct mono frame
        mono_frame = bytearray()
        for low, high in zip(left_low, left_high):
            mono_frame.append(low)
            mono_frame.append(high)

        return bytes(mono_frame)

    def _get_audio_frames_from_wav(
        self,
        file_path: str,
        start_offset: int = 0,
        frame_duration_ms: int = 30,
        sample_rate: int = 8000
    ):
        """
        Generator: Stream audio frames from WAV file

        Yields frames for VAD processing. Handles both mono and stereo.

        Args:
            file_path: WAV file path
            start_offset: Byte offset to start reading from
            frame_duration_ms: Frame duration in milliseconds
            sample_rate: Sample rate in Hz

        Yields:
            Audio frames (bytes) suitable for VAD processing
        """
        import wave

        # Calculate frame size
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        bytes_per_sample = 2  # 16-bit

        try:
            with wave.open(file_path, 'rb') as wav:
                channels = wav.getnchannels()
                bytes_per_frame = frame_size * bytes_per_sample

                if channels == 2:
                    # Stereo: need double bytes, then extract left
                    bytes_per_frame *= 2

                # Seek to start offset if specified
                if start_offset > 0:
                    wav.setpos(start_offset)

                while True:
                    # Read frame
                    frame_data = wav.readframes(frame_size)

                    if len(frame_data) < bytes_per_frame:
                        # End of file or incomplete frame
                        break

                    # Extract left channel if stereo
                    if channels == 2:
                        frame_data = self._extract_left_channel_stereo(
                            frame_data
                        )

                    yield frame_data

        except FileNotFoundError:
            logger.warning(f"WAV file not found: {file_path}")
            return

        except Exception as e:
            logger.error(f"Error reading WAV frames: {e}")
            return

    # ========================================================================
    # ACTIONS FRAMEWORK (Email, Webhook, Transfer, etc.)
    # ========================================================================

    def _execute_step_actions(self, call_uuid: str, step_config: Dict, session: Dict):
        """
        Execute configured actions for a step (email, webhook, transfer, etc.)

        Actions are defined in scenario JSON:
        {
            "actions": [
                {"type": "send_email", "config": {...}},
                {"type": "webhook", "config": {...}},
                {"type": "transfer", "config": {...}}
            ]
        }

        Args:
            call_uuid: Call UUID
            step_config: Step configuration from scenario
            session: Call session data
        """
        short_uuid = call_uuid[:8]
        actions = step_config.get("actions", [])

        if not actions:
            return

        logger.info(f"📋 [{short_uuid}] Executing {len(actions)} action(s)...")

        for i, action in enumerate(actions):
            action_type = action.get("type")
            action_config = action.get("config", {})

            try:
                if action_type == "send_email":
                    self._action_send_email(call_uuid, action_config, session)
                elif action_type == "webhook":
                    self._action_webhook(call_uuid, action_config, session)
                elif action_type == "transfer":
                    self._action_transfer(call_uuid, action_config, session)
                elif action_type == "update_crm":
                    self._action_update_crm(call_uuid, action_config, session)
                else:
                    logger.warning(f"⚠️ [{short_uuid}] Unknown action type: {action_type}")

            except Exception as e:
                logger.error(f"❌ [{short_uuid}] Action {i+1} failed ({action_type}): {e}")

    def _action_send_email(self, call_uuid: str, config: Dict, session: Dict):
        """Send email via API (placeholder for future implementation)"""
        short_uuid = call_uuid[:8]
        logger.info(f"📧 [{short_uuid}] EMAIL action triggered")
        logger.info(f"   Template: {config.get('template', 'N/A')}")
        logger.info(f"   To: {config.get('to', 'N/A')}")
        # TODO: Implement API call to email service
        # requests.post(config["api_endpoint"], json={...})

    def _action_webhook(self, call_uuid: str, config: Dict, session: Dict):
        """Call webhook API (placeholder for future implementation)"""
        short_uuid = call_uuid[:8]
        logger.info(f"🔗 [{short_uuid}] WEBHOOK action triggered")
        logger.info(f"   URL: {config.get('url', 'N/A')}")
        # TODO: Implement webhook call
        # requests.post(config["url"], json=session)

    def _action_transfer(self, call_uuid: str, config: Dict, session: Dict):
        """
        Transfer call to another destination (SIP URI, extension, etc.)

        Config example:
        {
            "destination": "sip:sales@domain.com" or "1234" (extension),
            "timeout": 30,
            "on_no_answer": "leave_voicemail" (optional fallback step)
        }

        Args:
            call_uuid: Call UUID
            config: Transfer configuration
            session: Call session data
        """
        short_uuid = call_uuid[:8]
        destination = config.get("destination")
        timeout = config.get("timeout", 30)

        if not destination:
            logger.error(f"❌ [{short_uuid}] Transfer failed: No destination specified")
            return False

        logger.info(f"📞 [{short_uuid}] Transferring call to: {destination}")
        logger.info(f"   Timeout: {timeout}s")

        try:
            # FreeSWITCH uuid_transfer command
            # Syntax: uuid_transfer <uuid> [-bleg|-both] <dest-exten> [<dialplan> <context>]
            transfer_cmd = f"uuid_transfer {call_uuid} {destination}"

            result = self._execute_esl_command(transfer_cmd)

            if result:
                logger.info(f"✅ [{short_uuid}] Call transferred successfully to {destination}")
                return True
            else:
                logger.error(f"❌ [{short_uuid}] Transfer command failed")

                # Fallback if configured
                fallback_step = config.get("on_no_answer")
                if fallback_step:
                    logger.info(f"   Fallback: {fallback_step}")
                    # TODO: Could execute fallback step here

                return False

        except Exception as e:
            logger.error(f"❌ [{short_uuid}] Transfer error: {e}")
            return False

    def _action_update_crm(self, call_uuid: str, config: Dict, session: Dict):
        """Update CRM via API (placeholder for future implementation)"""
        short_uuid = call_uuid[:8]
        logger.info(f"💼 [{short_uuid}] CRM UPDATE action triggered")
        logger.info(f"   Endpoint: {config.get('api_endpoint', 'N/A')}")
        # TODO: Implement CRM API call


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
    )

    print("=" * 80)
    print("ROBOT FREESWITCH - TEST MODE")
    print("=" * 80)

    try:
        # Initialize robot (PRELOAD all services)
        robot = RobotFreeSWITCH()

        print("\n" + "=" * 80)
        print("ROBOT INITIALIZED SUCCESSFULLY")
        print("=" * 80)
        print(f"Active calls: {len(robot.active_calls)}")
        print(f"STT service: {'OK' if robot.stt_service else 'FAIL'}")
        print(f"AMD service: {'OK' if robot.amd_service else 'FAIL'}")
        print(f"VAD service: {'OK' if robot.vad else 'FAIL'}")
        print(f"ScenarioManager: {'OK' if robot.scenario_manager else 'FAIL'}")
        print(f"ObjectionMatcher: {'OK' if robot.objection_matcher_default else 'NOT LOADED'}")

        print("\nSUCCESS - All services preloaded!")
        print("\nNOTE: To start robot, call robot.start()")
        print("This will connect to FreeSWITCH and start event loop")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
