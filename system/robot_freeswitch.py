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
import time
import threading
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
from system.services.ollama_nlp import OllamaNLP

# Scenarios & Objections
from system.scenarios import ScenarioManager
from system.objection_matcher import ObjectionMatcher

# Database
from system.database import SessionLocal
from system.models import Call, CallStatus

# Config
from system.config import config

logger = logging.getLogger(__name__)


class RobotFreeSWITCH:
    """
    Main Robot for automated marketing calls

    Architecture:
    - Dual ESL connections (events + API)
    - Thread per call
    - 3 phases: AMD -> PLAYING -> WAITING
    - PRELOADED AI services (no cold starts)
    """

    def __init__(self):
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

        # === EVENT LOOP ===
        self.running = False
        self.event_thread = None

        # === CALL MANAGEMENT ===
        self.active_calls = {}  # {call_uuid: call_info}
        self.call_threads = {}  # {call_uuid: thread}
        self.call_sessions = {}  # {call_uuid: session_data}

        # === AUDIO TRACKING ===
        self.barge_in_active = {}  # {call_uuid: bool}

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
                beam_size=config.FASTER_WHISPER_BEAM_SIZE
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

        # 2. Ollama NLP (OPTIONAL - sentiment analysis only)
        if config.OLLAMA_ENABLED:
            try:
                logger.info("Loading Ollama NLP (sentiment analysis)...")
                self.nlp_service = OllamaNLP(
                    base_url=config.OLLAMA_BASE_URL,
                    model=config.OLLAMA_MODEL,
                    timeout=config.OLLAMA_TIMEOUT,
                    enabled=True
                )
                logger.info("Ollama NLP loaded")
            except Exception as e:
                logger.warning(f"Ollama NLP not available: {e}")
                self.nlp_service = None
        else:
            logger.info("Ollama NLP disabled (sentiment analysis optional)")
            self.nlp_service = None

        # 3. AMD Service (keywords matching)
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

        # 4. WebRTC VAD (barge-in detection)
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

        # 5. ScenarioManager
        try:
            logger.info("Loading ScenarioManager...")
            self.scenario_manager = ScenarioManager()
            logger.info("ScenarioManager loaded")
        except Exception as e:
            logger.error(f"Failed to load ScenarioManager: {e}")
            self.scenario_manager = None
            raise

        # 6. ObjectionMatcher (PRELOAD with default theme)
        try:
            logger.info("Loading ObjectionMatcher (default theme)...")
            # Preload general objections (will be theme-specific per campaign)
            self.objection_matcher_default = ObjectionMatcher.load_objections_for_theme("general")
            if self.objection_matcher_default:
                logger.info("ObjectionMatcher loaded (general theme)")
            else:
                logger.warning("ObjectionMatcher not loaded (no objections found)")
        except Exception as e:
            logger.warning(f"ObjectionMatcher not available: {e}")
            self.objection_matcher_default = None

        # ===================================================================
        # WARMUP TESTS (CRITICAL - Avoid first-call latency spikes)
        # ===================================================================

        # 1. GPU WARMUP (Faster-Whisper)
        if self.stt_service and config.FASTER_WHISPER_DEVICE == "cuda":
            logger.info("WARMUP 1/3: GPU Faster-Whisper test transcription...")
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

                logger.info(f"GPU WARMUP 1/3: Completed in {warmup_time:.0f}ms - GPU is HOT!")

                # Cleanup
                Path(warmup_path).unlink()

            except Exception as e:
                logger.warning(f"GPU warmup failed (non-critical): {e}")

        # 2. VAD WARMUP
        if self.vad:
            logger.info("WARMUP 2/3: VAD test detection...")
            try:
                # Test VAD on dummy audio frame
                import struct

                # 30ms frame @ 8kHz = 240 samples
                frame_samples = 240
                test_frame = struct.pack('<' + ('h' * frame_samples), *([100] * frame_samples))

                warmup_start = time.time()
                is_speech = self.vad.is_speech(test_frame, 8000)
                warmup_time = (time.time() - warmup_start) * 1000

                logger.info(f"VAD WARMUP 2/3: Completed in {warmup_time:.2f}ms - VAD is READY!")

            except Exception as e:
                logger.warning(f"VAD warmup failed (non-critical): {e}")

        # 3. OBJECTION MATCHER WARMUP
        if self.objection_matcher_default:
            logger.info("WARMUP 3/3: ObjectionMatcher test match...")
            try:
                warmup_start = time.time()
                test_match = self.objection_matcher_default.find_best_match(
                    "C'est trop cher pour moi",
                    min_score=0.5
                )
                warmup_time = (time.time() - warmup_start) * 1000

                logger.info(
                    f"ObjectionMatcher WARMUP 3/3: Completed in {warmup_time:.2f}ms - "
                    f"Matcher is READY!"
                )

            except Exception as e:
                logger.warning(f"ObjectionMatcher warmup failed (non-critical): {e}")

        logger.info("=" * 80)
        logger.info("ROBOT INITIALIZED - ALL SERVICES PRELOADED")
        logger.info("=" * 80)

    def __repr__(self):
        return f"<RobotFreeSWITCH active_calls={len(self.active_calls)} running={self.running}>"

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
            scenario = self.scenario_manager.get_scenario(scenario_name)
            if not scenario:
                logger.error(f"Scenario '{scenario_name}' not found")
                return None

            logger.info(f"Scenario loaded: {scenario.get('name', scenario_name)}")

            # Build originate command
            # Format: originate {variables}sofia/gateway/gateway_name/number &park()

            # Variables to pass to the call
            variables = [
                f"scenario_name={scenario_name}",
                f"lead_id={lead_id}",
                "origination_caller_id_name=MiniBotPanel",
                "origination_caller_id_number=0000000000",
                "ignore_early_media=true"
            ]

            # Join variables
            vars_str = ",".join(variables)

            # Originate command (appel sortant)
            cmd = f"originate {{{vars_str}}}sofia/internal/{phone_number}@localhost &park()"

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
        short_uuid = call_uuid[:8]

        logger.info(f"[{short_uuid}] CHANNEL_HANGUP_COMPLETE")

        # Get hangup cause from event
        hangup_cause = event.getHeader("Hangup-Cause")
        caller_hangup = event.getHeader("variable_sip_hangup_disposition")

        logger.info(
            f"[{short_uuid}] Hangup details: "
            f"cause={hangup_cause}, disposition={caller_hangup}"
        )

        # ===================================================================
        # CRITICAL: Determine if client hung up (NOT robot)
        # ===================================================================

        # Check if robot already set a final status
        session = self.call_sessions.get(call_uuid, {})
        robot_initiated_hangup = session.get("robot_hangup", False)
        existing_status = session.get("final_status")

        if robot_initiated_hangup:
            # Robot initiated hangup → use robot's status
            final_status = existing_status or CallStatus.COMPLETED
            logger.info(
                f"[{short_uuid}] Robot-initiated hangup "
                f"-> Status: {final_status.value}"
            )

        else:
            # Client hung up → NOT_INTERESTED
            # This is the REACTIVE detection that was difficult before!

            # Additional checks for hangup cause
            client_hangup_causes = [
                "NORMAL_CLEARING",           # Client hung up normally
                "ORIGINATOR_CANCEL",         # Client cancelled call
                "USER_BUSY",                 # Client rejected
                "NO_USER_RESPONSE",          # Client didn't respond
                "NO_ANSWER"                  # Client didn't answer
            ]

            if hangup_cause in client_hangup_causes or caller_hangup == "recv_bye":
                final_status = CallStatus.NOT_INTERESTED

                logger.warning(
                    f"[{short_uuid}] CLIENT HANGUP DETECTED! "
                    f"(cause: {hangup_cause}) "
                    f"-> Status: NOT_INTERESTED"
                )

            else:
                # Other causes (network error, etc.) → use existing or default
                final_status = existing_status or CallStatus.COMPLETED

                logger.info(
                    f"[{short_uuid}] Hangup (cause: {hangup_cause}) "
                    f"-> Status: {final_status.value}"
                )

        # ===================================================================
        # Update database with final status
        # ===================================================================
        try:
            # TODO: Database update implementation
            # For now, log the status that SHOULD be saved

            logger.info(
                f"[{short_uuid}] FINAL STATUS: {final_status.value} "
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
        if call_uuid in self.active_calls:
            del self.active_calls[call_uuid]

        if call_uuid in self.call_threads:
            del self.call_threads[call_uuid]

        if call_uuid in self.call_sessions:
            del self.call_sessions[call_uuid]

        if call_uuid in self.barge_in_active:
            del self.barge_in_active[call_uuid]

        logger.info(f"[{short_uuid}] Call cleanup completed")

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
            # PHASE 2: PLAYING AUDIO (with barge-in detection)
            # ================================================================
            # TODO PART 5: Load scenario and get first audio to play
            # For now, we'll use a placeholder flow
            # Example: playing_result = self._execute_phase_playing(call_uuid, audio_path)

            # STUB for PART 5 integration
            logger.info(
                f"[{short_uuid}] PHASE 2 STUB: Would play first audio with barge-in "
                f"(implementation ready, waiting for scenario integration)"
            )

            # ================================================================
            # PHASE 3: WAITING RESPONSE (listen to client)
            # ================================================================
            # TODO PART 5: After playing audio, listen for client response
            # Example: waiting_result = self._execute_phase_waiting(call_uuid)

            # STUB for PART 5 integration
            logger.info(
                f"[{short_uuid}] PHASE 3 STUB: Would listen for client response "
                f"(implementation ready, waiting for scenario integration)"
            )

            # ================================================================
            # INTEGRATION SCENARIO FLOW (PART 5)
            # ================================================================
            # TODO PART 5: Load scenario, execute conversation loop
            # This will be implemented with:
            # - Load scenario from call metadata
            # - Loop through rail/steps
            # - Intent analysis + objection handling
            # - MaxTurn autonomous objection handling
            # - Lead qualification
            #
            # Example flow:
            # scenario = self._load_scenario_for_call(call_uuid)
            # session = self._init_session(call_uuid, scenario)
            # while not finished:
            #     playing_result = self._execute_phase_playing(...)
            #     waiting_result = self._execute_phase_waiting(...)
            #     intent = self._analyze_intent(waiting_result["transcription"])
            #     next_step = self._get_next_step(intent, session)
            #
            # For now, stub message
            logger.info(
                f"[{short_uuid}] SCENARIO FLOW STUB: Would execute conversation loop "
                f"(implementation ready, waiting for call metadata integration)"
            )

            # Temporary hangup for testing
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

    def _execute_phase_amd(self, call_uuid: str) -> Dict[str, Any]:
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

        logger.info(f"[{short_uuid}] === PHASE 1: AMD START ===")

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

        logger.info(
            f"[{short_uuid}] === PHASE 1: AMD END === "
            f"Result: {result}, Total latency: {total_latency_ms:.0f}ms"
        )

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

        logger.info(f"[{short_uuid}] === PHASE 2: PLAYING START ===")
        logger.info(
            f"[{short_uuid}] Audio: {Path(audio_path).name}, "
            f"Barge-in: {'ENABLED' if enable_barge_in else 'DISABLED'}"
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

        if result.get("interrupted"):
            logger.info(
                f"[{short_uuid}] === PHASE 2: PLAYING END === "
                f"INTERRUPTED at {result.get('barge_in_at', 0):.1f}s "
                f"(speech: {result.get('speech_duration', 0):.1f}s)"
            )
        else:
            logger.info(
                f"[{short_uuid}] === PHASE 2: PLAYING END === "
                f"COMPLETED (duration: {total_latency_ms/1000:.1f}s)"
            )

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

        logger.info(f"[{short_uuid}] === PHASE 3: WAITING START ===")
        logger.info(
            f"[{short_uuid}] Listening for client response "
            f"(silence threshold: {config.SILENCE_THRESHOLD}s, "
            f"max duration: {max_duration}s)"
        )

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

        logger.info(
            f"[{short_uuid}] === PHASE 3: WAITING END === "
            f"Transcription: '{transcription[:30]}...', "
            f"Total latency: {total_latency_ms:.0f}ms"
        )

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
        retry_count: int = 0
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

        playing_result = self._execute_phase_playing(
            call_uuid,
            audio_path,
            enable_barge_in=enable_barge_in
        )

        # ===================================================================
        # STEP 2: Wait for response (PHASE 3)
        # ===================================================================
        waiting_result = self._execute_phase_waiting(call_uuid)

        transcription = waiting_result.get("transcription", "").strip()

        # ===================================================================
        # STEP 3: Analyze intent
        # ===================================================================
        intent_result = self._analyze_intent(transcription, scenario)
        intent = intent_result["intent"]

        logger.info(
            f"[{short_uuid}] Step result: intent={intent}, "
            f"transcription='{transcription[:40]}...'"
        )

        # ===================================================================
        # STEP 4: Handle based on intent
        # ===================================================================
        intent_mapping = step_config.get("intent_mapping", {})

        # --- OBJECTION HANDLING with MaxTurn ---
        if intent == "objection":
            max_turns = self.scenario_manager.get_max_autonomous_turns(
                scenario,
                step_name
            )

            if max_turns > 0:
                # Autonomous objection handling
                logger.info(
                    f"[{short_uuid}] Objection detected with MaxTurn={max_turns} "
                    f"-> Starting autonomous loop"
                )

                objection_result = self._handle_objection_autonomous(
                    call_uuid,
                    scenario,
                    step_name,
                    transcription,
                    max_turns=max_turns
                )

                # After objection loop, check result
                if objection_result.get("resolved"):
                    # Objection resolved -> continue to affirm path
                    logger.info(f"[{short_uuid}] Objection resolved -> Continue")
                    next_step = intent_mapping.get("affirm")

                else:
                    # Objection not resolved -> deny path
                    logger.info(f"[{short_uuid}] Objection NOT resolved -> Deny path")
                    next_step = intent_mapping.get("deny", "Bye_Failed")

            else:
                # No MaxTurn -> direct objection mapping or deny
                next_step = intent_mapping.get("objection", intent_mapping.get("deny"))

        # --- SILENCE HANDLING ---
        elif intent == "silence":
            # Check max consecutive silences
            session["consecutive_silences"] = session.get("consecutive_silences", 0) + 1

            if session["consecutive_silences"] >= config.MAX_CONSECUTIVE_SILENCES:
                logger.warning(
                    f"[{short_uuid}] Max consecutive silences reached "
                    f"({config.MAX_CONSECUTIVE_SILENCES})"
                )
                next_step = intent_mapping.get("silence", "Bye_Failed")
            else:
                # Retry step
                logger.info(f"[{short_uuid}] Silence -> Retry step")
                return {
                    "success": True,
                    "retry": True,
                    "intent": intent,
                    "transcription": transcription,
                    "latencies": {"total_ms": (time.time() - step_start) * 1000}
                }

        # --- AFFIRM / DENY / OTHER ---
        else:
            # Reset silence counter on valid response
            session["consecutive_silences"] = 0

            # Get next step from intent_mapping
            next_step = intent_mapping.get(intent)

            if not next_step:
                # No mapping -> try "unknown" fallback or deny
                logger.warning(f"[{short_uuid}] No mapping for intent: {intent}")
                next_step = intent_mapping.get("unknown", intent_mapping.get("deny"))

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
        # Summary
        # ===================================================================
        total_latency_ms = (time.time() - step_start) * 1000

        logger.info(
            f"[{short_uuid}] === STEP END: {step_name} === "
            f"Next: {next_step}, Latency: {total_latency_ms:.0f}ms"
        )

        return {
            "success": True,
            "next_step": next_step,
            "intent": intent,
            "transcription": transcription,
            "retry": False,
            "qualification_delta": qualification_delta,
            "latencies": {
                "playing_ms": playing_result["latencies"]["total_ms"],
                "waiting_ms": waiting_result["latencies"]["total_ms"],
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
        max_turns: int = 2
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

        theme = self.scenario_manager.get_theme(scenario)
        current_objection = objection_text
        turns_used = 0

        for turn in range(max_turns):
            turns_used += 1

            logger.info(
                f"[{short_uuid}] Objection turn {turn + 1}/{max_turns}: "
                f"'{current_objection[:40]}...'"
            )

            # Find objection response
            objection_result = self._find_objection_response(
                current_objection,
                theme=theme,
                min_score=config.OBJECTION_MIN_SCORE
            )

            if not objection_result.get("found"):
                logger.warning(
                    f"[{short_uuid}] No objection response found -> Exit loop"
                )
                break

            # Play objection response
            audio_file = objection_result.get("audio_file")

            if not audio_file:
                logger.error(f"[{short_uuid}] Objection response has no audio file")
                break

            # Build full audio path for objection
            audio_path = config.BASE_DIR / "sounds" / theme / "objections" / audio_file

            if not audio_path.exists():
                logger.error(f"[{short_uuid}] Objection audio not found: {audio_path}")
                break

            # Play objection response (with barge-in)
            playing_result = self._execute_phase_playing(
                call_uuid,
                str(audio_path),
                enable_barge_in=True
            )

            # Wait for client reaction
            waiting_result = self._execute_phase_waiting(call_uuid)

            reaction = waiting_result.get("transcription", "").strip()

            # Analyze reaction intent
            intent_result = self._analyze_intent(reaction, scenario)
            intent = intent_result["intent"]

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

            elif intent == "silence" or intent == "unknown":
                # Continue loop
                logger.info(f"[{short_uuid}] Silence/Unknown -> Continue loop")
                current_objection = reaction  # Use for next iteration
                continue

            else:
                # New objection or deny
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
    ) -> CallStatus:
        """
        Calculate final call status based on session data

        Args:
            session: Call session data
            scenario: Scenario dict

        Returns:
            CallStatus enum (LEAD, NOT_INTERESTED, NO_ANSWER)
        """
        qualification_score = session.get("qualification_score", 0.0)

        # Define qualification threshold
        # For a typical scenario with 3-4 determinant questions:
        # - Each question has weight 30-40
        # - LEAD threshold: >= 70% of questions answered positively
        # - Example: 3 questions * 30 = 90 max -> threshold ~60

        lead_threshold = 60.0  # Configurable per scenario

        if qualification_score >= lead_threshold:
            return CallStatus.LEAD
        else:
            return CallStatus.NOT_INTERESTED

    # ========================================================================
    # INTENT ANALYSIS & OBJECTION HANDLING
    # ========================================================================

    def _negation_near_word(self, text: str, word: str, window: int = 4) -> bool:
        """
        Check if negation word is near a positive word (within ±window words)

        Used to detect phrases like:
        - "ca m'interesse pas" (interesse + pas nearby) → deny
        - "ca marche pas" (marche + pas nearby) → deny

        Args:
            text: Lowercase text to analyze
            word: Positive word to check
            window: Distance window (default 4 words)

        Returns:
            True if negation found near word, False otherwise
        """
        words = text.split()

        # Find position of positive word
        word_pos = -1
        for i, w in enumerate(words):
            if word in w:
                word_pos = i
                break

        if word_pos == -1:
            return False

        # Check negations in window [-window, +window]
        window_start = max(0, word_pos - window)
        window_end = min(len(words), word_pos + window + 1)

        for i in range(window_start, window_end):
            if words[i] in config.NEGATION_WORDS:
                return True

        return False

    def _analyze_intent(self, transcription: str, scenario: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze client intent using BETON ARME keywords matching

        Architecture 3 niveaux (basee sur research NLP + best practices):
        NIVEAU 1: Pre-traitement (negations, MWEs, interrogatifs)
        NIVEAU 2: Keywords matching (keywords simples)
        NIVEAU 3: Resolution prioritaire (deny > question > objection > affirm)

        This replaces Ollama NLP for intent detection (200-500ms saved!)

        5 intents de base:
        - affirm: Acceptation positive
        - deny: Refus/rejet
        - unsure: Hesitation
        - question: Demande info
        - objection: Objection (pour ObjectionMatcher)

        Args:
            transcription: Client transcription
            scenario: Optional scenario context (for custom intent keywords)

        Returns:
            {
                "intent": "affirm" | "deny" | "unsure" | "question" | "objection" | "silence",
                "confidence": 0.0-1.0,
                "keywords_matched": [...],
                "reason": "fixed_expression" | "negation_override" | "interrogative_start" | "keywords",
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

        # ===== NIVEAU 1: PRE-TRAITEMENT =====
        # Ordre FINAL: negations explicites > fixed expressions > interrogatifs > negation generale

        # 1.A - Check negations explicites (phrases completes) - PRIORITE ABSOLUE
        for neg_phrase in config.NEGATION_PHRASES:
            if neg_phrase in text_lower:
                latency_ms = (time.time() - analyze_start) * 1000
                logger.info(
                    f"Intent analysis: '{transcription[:30]}...' -> deny "
                    f"(conf: 0.90, reason: negation_phrase '{neg_phrase}', latency: {latency_ms:.1f}ms)"
                )
                return {
                    "intent": "deny",
                    "confidence": 0.90,
                    "keywords_matched": [neg_phrase],
                    "reason": "negation_phrase",
                    "latency_ms": latency_ms
                }

        # 1.B - Check expressions figees (MWEs) - AVANT interrogatifs et negation generale
        # Important: traite "pourquoi pas" (affirm) AVANT de detecter "pourquoi" (question)
        # Important: traite "pas mal" (affirm) AVANT de detecter "pas" (negation)
        # CRITIQUE: Verifie la PLUS LONGUE expression qui matche (evite "ca m'interesse" avant "ca m'interesse pas")
        best_match = None
        best_intent = None
        best_length = 0

        for intent_name, expressions in config.FIXED_EXPRESSIONS.items():
            for expr in expressions:
                if expr in text_lower and len(expr) > best_length:
                    best_match = expr
                    best_intent = intent_name
                    best_length = len(expr)

        if best_match:
            latency_ms = (time.time() - analyze_start) * 1000
            logger.info(
                f"Intent analysis: '{transcription[:30]}...' -> {best_intent} "
                f"(conf: 0.95, reason: fixed_expression '{best_match}', latency: {latency_ms:.1f}ms)"
            )
            return {
                "intent": best_intent,
                "confidence": 0.95,
                "keywords_matched": [best_match],
                "reason": "fixed_expression",
                "latency_ms": latency_ms
            }

        # 1.C - Check interrogatifs en debut de phrase (position 0-2)
        words = text_lower.split()
        for i in range(min(3, len(words))):
            if words[i] in config.INTERROGATIVE_WORDS:
                latency_ms = (time.time() - analyze_start) * 1000
                logger.info(
                    f"Intent analysis: '{transcription[:30]}...' -> question "
                    f"(conf: 0.85, reason: interrogative_start '{words[i]}', latency: {latency_ms:.1f}ms)"
                )
                return {
                    "intent": "question",
                    "confidence": 0.85,
                    "keywords_matched": [words[i]],
                    "reason": "interrogative_start",
                    "latency_ms": latency_ms
                }

        # 1.D - Check negation generale dans phrase (si pas deja traite par fixed expressions)
        # Ex: "ca marche pas", "ca m'interesse pas" -> deny
        has_negation = any(neg in text_lower for neg in config.NEGATION_WORDS)
        if has_negation:
            latency_ms = (time.time() - analyze_start) * 1000
            logger.info(
                f"Intent analysis: '{transcription[:30]}...' -> deny "
                f"(conf: 0.80, reason: negation_present, latency: {latency_ms:.1f}ms)"
            )
            return {
                "intent": "deny",
                "confidence": 0.80,
                "keywords_matched": ["negation"],
                "reason": "negation_present",
                "latency_ms": latency_ms
            }

        # ===== NIVEAU 2: KEYWORDS MATCHING =====

        intent_matches = {}

        for intent_name, keywords in config.INTENT_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in text_lower]
            if matches:
                intent_matches[intent_name] = matches

        # ===== NIVEAU 3: RESOLUTION PRIORITAIRE =====
        # NOUVELLE priorite (basee sur research): deny > question > objection > affirm > unsure

        if "deny" in intent_matches:
            intent = "deny"
            keywords = intent_matches["deny"]
            confidence = min(0.95, 0.6 + 0.15 * len(keywords))

        elif "question" in intent_matches:
            intent = "question"
            keywords = intent_matches["question"]
            confidence = min(0.90, 0.6 + 0.15 * len(keywords))

        elif "objection" in intent_matches:
            intent = "objection"
            keywords = intent_matches["objection"]
            confidence = min(0.90, 0.5 + 0.15 * len(keywords))

        elif "affirm" in intent_matches:
            intent = "affirm"
            keywords = intent_matches["affirm"]
            confidence = min(0.95, 0.6 + 0.15 * len(keywords))

        elif "unsure" in intent_matches:
            intent = "unsure"
            keywords = intent_matches["unsure"]
            confidence = min(0.80, 0.5 + 0.15 * len(keywords))

        else:
            # Aucun keyword match -> unsure par defaut
            intent = "unsure"
            keywords = []
            confidence = 0.0

        latency_ms = (time.time() - analyze_start) * 1000

        logger.info(
            f"Intent analysis: '{transcription[:30]}...' -> {intent} "
            f"(conf: {confidence:.2f}, keywords: {keywords[:3]}, "
            f"latency: {latency_ms:.1f}ms)"
        )

        return {
            "intent": intent,
            "confidence": confidence,
            "keywords_matched": keywords,
            "reason": "keywords",
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

        # Build full path
        # Audios are in: BASE_DIR/sounds/{theme}/{voice}/{filename}
        theme = scenario.get("theme", "general")
        voice = scenario.get("voice", step_config.get("voice", "julie"))

        audio_path = config.BASE_DIR / "sounds" / theme / voice / filename

        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        return str(audio_path)

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
        Execute ESL API command

        Args:
            cmd: ESL command (e.g. "uuid_record <uuid> start ...")

        Returns:
            Command result body or None if error
        """
        try:
            if not self.esl_conn_api:
                logger.error("ESL API connection not available")
                return None

            result = self.esl_conn_api.api(cmd)

            if not result:
                return None

            return result.getBody()

        except Exception as e:
            logger.error(f"ESL command error: {e}")
            return None

    def _hangup_call(self, call_uuid: str, status: CallStatus = CallStatus.COMPLETED):
        """
        Hangup call and update database

        CRITICAL: Mark robot_hangup flag BEFORE executing hangup
        so that CHANNEL_HANGUP_COMPLETE handler knows robot initiated it

        Args:
            call_uuid: Call UUID
            status: Call status (NO_ANSWER, COMPLETED, NOT_INTERESTED, LEAD, etc.)
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
        print(f"Ollama NLP: {'OK' if robot.nlp_service else 'DISABLED'}")
        print(f"ObjectionMatcher: {'OK' if robot.objection_matcher_default else 'NOT LOADED'}")

        print("\nSUCCESS - All services preloaded!")
        print("\nNOTE: To start robot, call robot.start()")
        print("This will connect to FreeSWITCH and start event loop")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
