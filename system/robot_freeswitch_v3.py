"""
RobotFreeSWITCH V3 - ARCHITECTURE SIMPLIFIÉE
=============================================

Version V3 avec barge-in ultra simplifié et sans bugs:

Changements V3:
- ✅ Barge-in SIMPLE: durée >= 2s = interruption (pas de keywords)
- ✅ Durée incluse dans événements streaming (pas de race condition)
- ❌ SUPPRIMÉ: backchannel keywords, background music
- ✅ Grace period 2.0s (réduit de 2.5s)
- ✅ Smooth delay 1.0s (conservé)
- ✅ Logs debug détaillés partout

Architecture conservée:
    1. ESL Connection Management (dual connections)
    2. Call Thread Management (one thread per call)
    3. Audio Playback System (uuid_broadcast)
    4. Audio Streaming System (FreeSWITCH → WebSocket)
    5. Speech Recognition (Vosk via StreamingASR V3)
    6. NLP Intent Analysis (Ollama)
    7. Scenario Execution Engine
    8. Autonomous Agent Mode (objections handler) ← CONSERVÉ

Author: MiniBotPanel Team
Version: 3.0.0
Date: 2025-11-09
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass

# FreeSWITCH ESL
try:
    from ESL import ESLconnection
    ESL_AVAILABLE = True
except ImportError:
    ESL_AVAILABLE = False

# Services V3
from system.services.vosk_stt import VoskSTT
from system.services.ollama_nlp import OllamaNLP
from system.services.amd_service import AMDService
from system.services.streaming_asr_v3 import StreamingASRV3  # ← V3

# Scenario & Config V3
from system.scenarios import ScenarioManager
from system.config_v3 import config  # ← V3

# Database
from system.database import SessionLocal
from system.models import Call

# Objections (conservé - essentiel au projet)
try:
    from system.objections_db import ObjectionMatcher
    OBJECTION_MATCHER_AVAILABLE = True
except ImportError:
    OBJECTION_MATCHER_AVAILABLE = False

# Logger
from system.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# V3: DATACLASSES & BARGE-IN DETECTOR
# ============================================================================

@dataclass
class CallState:
    """
    V3: État immutable d'un appel

    Permet tracking propre sans variables globales éparpillées.
    """
    call_uuid: str
    phone_number: str
    scenario_name: str
    audio_state: str  # "PLAYING_AUDIO" ou "WAITING_RESPONSE"
    speech_start_time: float = 0.0
    speech_duration: float = 0.0
    grace_period_active: bool = False
    last_transcription: str = ""
    barge_in_triggered: bool = False


class BargeInDetector:
    """
    V3: Détecteur de barge-in ULTRA SIMPLE

    Une seule règle:
    - PLAYING_AUDIO + durée >= 2s + pas grace period = BARGE-IN
    - WAITING_RESPONSE = Toujours capturer (pas de barge-in)
    """

    DURATION_THRESHOLD = 2.0  # secondes

    def should_trigger(
        self,
        audio_state: str,
        speech_duration: float,
        grace_period_active: bool
    ) -> bool:
        """
        Décision barge-in simple et claire.

        Args:
            audio_state: "PLAYING_AUDIO" ou "WAITING_RESPONSE"
            speech_duration: Durée de parole en secondes
            grace_period_active: Grace period actif ou non

        Returns:
            True si barge-in doit être déclenché
        """
        # Log détaillé V3
        logger.debug(
            f"🔍 V3 Barge-in check: audio_state={audio_state}, "
            f"duration={speech_duration:.2f}s, grace_period={grace_period_active}"
        )

        if audio_state != "PLAYING_AUDIO":
            logger.debug("   ➜ WAITING_RESPONSE mode - no barge-in, capture speech")
            return False

        if grace_period_active:
            logger.debug("   ➜ Grace period active - ignore speech")
            return False

        if speech_duration >= self.DURATION_THRESHOLD:
            logger.info(
                f"   ➜ ✅ BARGE-IN triggered (duration {speech_duration:.2f}s >= {self.DURATION_THRESHOLD}s)"
            )
            return True
        else:
            logger.info(
                f"   ➜ ❌ Backchannel ignored (duration {speech_duration:.2f}s < {self.DURATION_THRESHOLD}s)"
            )
            return False


class RobotFreeSwitchV3:
    """
    Robot FreeSWITCH V3 - Version simplifiée et optimisée

    Changements V3:
    - Barge-in ultra simple (durée >= 2s)
    - Pas de race conditions (durée incluse dans événements)
    - Pas de crash Vosk (reset_recognizer supprimé)
    - Logs debug détaillés

    Conserve:
    - Transcription temps réel (streaming V3)
    - Analyse NLP avec Ollama
    - Gestion objections/questions (mode autonome) ← ESSENTIEL
    - Intent mapping classique
    - AMD, barge-in, silences
    """

    def __init__(self):
        """Initialise le robot V3 et tous ses services"""
        logger.info("="*60)
        logger.info("🚀 RobotFreeSWITCH V3 - Initialization")
        logger.info("="*60)

        if not ESL_AVAILABLE:
            raise RuntimeError("❌ ESL module not available - install python-ESL")

        logger.info("✅ ESL module loaded (python-ESL)")

        # === CONFIGURATION ===
        self.esl_host = config.FREESWITCH_ESL_HOST
        self.esl_port = config.FREESWITCH_ESL_PORT
        self.esl_password = config.FREESWITCH_ESL_PASSWORD

        # === ESL CONNECTIONS (DUAL) ===
        self.esl_conn_events = None  # Pour recevoir événements (blocking)
        self.esl_conn_api = None     # Pour envoyer commandes API (non-blocking)

        # === EVENT LOOP ===
        self.running = False
        self.event_thread = None

        # === CALL MANAGEMENT ===
        self.active_calls = {}  # {call_uuid: call_info}
        self.call_threads = {}  # {call_uuid: thread}

        # === AUDIO TRACKING ===
        self.call_sequences = defaultdict(list)  # Historique audio par call
        self.barge_in_active = {}  # {call_uuid: bool}
        self.background_audio_active = {}  # {call_uuid: bool}

        # === STREAMING SESSIONS ===
        self.streaming_sessions = {}  # {call_uuid: session_data}

        # === V3: BARGE-IN DETECTOR ===
        self.barge_in_detector = BargeInDetector()
        logger.info("✅ V3 BargeInDetector initialized (threshold: 2.0s)")

        # === SERVICES INITIALIZATION ===
        logger.info("🤖 Loading AI services V3...")

        # 1. Vosk STT (legacy - pour tests sans streaming)
        try:
            self.stt_service = VoskSTT()
            logger.info("✅ Vosk STT loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load Vosk STT: {e}")
            self.stt_service = None

        # 2. Ollama NLP
        try:
            self.nlp_service = OllamaNLP()
            logger.info("✅ Ollama NLP loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load Ollama NLP: {e}")
            self.nlp_service = None

        # 3. AMD Service
        try:
            self.amd_service = AMDService(esl_conn=None)  # Will set after connection
            logger.info("✅ AMD Service loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load AMD Service: {e}")
            self.amd_service = None

        # 4. Streaming ASR V3 (WebSocket server)
        try:
            self.streaming_asr = StreamingASRV3()  # ← V3
            logger.info("✅ StreamingASR V3 loaded")

            # Démarrer serveur WebSocket en arrière-plan
            if self.streaming_asr.is_available:
                import asyncio
                loop = asyncio.new_event_loop()

                def start_asr_server():
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.streaming_asr.start_server())

                asr_thread = threading.Thread(target=start_asr_server, daemon=True)
                asr_thread.start()
                time.sleep(0.5)  # Laisser temps au serveur de démarrer
                logger.info(f"✅ StreamingASR V3 server started (port {config.WEBSOCKET_PORT})")
            else:
                logger.warning("⚠️ StreamingASR V3 not available - missing dependencies")
        except Exception as e:
            logger.error(f"❌ Streaming V3 server error: {e}")
            self.streaming_asr = None

        # 5. Scenario Manager
        try:
            logger.info("📋 Loading scenarios...")
            self.scenario_manager = ScenarioManager()
            logger.info("✅ ScenarioManager loaded successfully")
            logger.info("✅ ScenarioManager initialized")
        except Exception as e:
            logger.error(f"❌ Failed to load ScenarioManager: {e}")
            self.scenario_manager = None

        logger.info("✅ RobotFreeSWITCH V3 initialized")
        logger.info("="*60)

    def __repr__(self):
        return f"<RobotFreeSwitchV3 active_calls={len(self.active_calls)} running={self.running}>"

    # ========================================================================
    # SECTION 2: ESL CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self):
        """
        Établit les deux connexions ESL vers FreeSWITCH
        
        Connection 1 (events): Pour recevoir les événements (blocking recvEvent)
        Connection 2 (api): Pour envoyer les commandes API (non-blocking)
        """
        logger.info("📡 Connecting to FreeSWITCH ESL...")
        
        try:
            # Connexion #1: Pour événements (blocking)
            self.esl_conn_events = ESLconnection(self.esl_host, str(self.esl_port), self.esl_password)
            
            if not self.esl_conn_events.connected():
                raise ConnectionError("Failed to connect ESL events connection")
            
            # Subscribe aux événements nécessaires
            events = [
                "CHANNEL_CREATE",
                "CHANNEL_ANSWER", 
                "CHANNEL_HANGUP",
                "CHANNEL_HANGUP_COMPLETE",
                "DTMF",
                "CUSTOM"
            ]
            self.esl_conn_events.events("plain", " ".join(events))
            logger.info("✅ ESL events connection established")
            
            # Connexion #2: Pour commandes API (non-blocking)
            self.esl_conn_api = ESLconnection(self.esl_host, str(self.esl_port), self.esl_password)
            
            if not self.esl_conn_api.connected():
                raise ConnectionError("Failed to connect ESL API connection")
                
            logger.info("✅ ESL API connection established")
            logger.info(f"✅ Connected to FreeSWITCH ESL (2 connections)")

            # Pass ESL connection to AMD service
            if self.amd_service:
                self.amd_service.set_esl_connection(self.esl_conn_api)

            return True
            
        except Exception as e:
            logger.error(f"❌ ESL connection failed: {e}")
            return False

    def start(self):
        """Démarre le robot et la boucle d'événements"""
        logger.info("Starting RobotFreeSWITCH V3...")
        
        # Connexion ESL
        if not self.connect():
            logger.error("❌ Failed to connect to FreeSWITCH")
            return False
        
        # Démarrer event loop
        self.running = True
        self.event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self.event_thread.start()
        
        logger.info("✅ RobotFreeSWITCH V3 started and listening for events")
        logger.info("👂 Waiting for calls...")
        
        return True

    def stop(self):
        """Arrête le robot proprement"""
        logger.info("Stopping RobotFreeSWITCH V3...")
        
        self.running = False
        
        # Attendre fin event loop
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5)
        
        # Fermer connexions ESL
        if self.esl_conn_events:
            self.esl_conn_events.disconnect()
        if self.esl_conn_api:
            self.esl_conn_api.disconnect()
        
        logger.info("✅ RobotFreeSWITCH V3 stopped")

    def _event_loop(self):
        """
        Boucle principale d'écoute des événements FreeSWITCH
        Tourne dans un thread séparé
        """
        logger.debug("Event loop started")
        
        while self.running and self.esl_conn_events:
            try:
                # Recevoir événement (blocking)
                event = self.esl_conn_events.recvEvent()
                
                if not event:
                    continue
                
                event_name = event.getHeader("Event-Name")
                call_uuid = event.getHeader("Unique-ID")
                
                if not call_uuid:
                    continue
                
                # Dispatcher événements
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

    def _handle_channel_answer(self, call_uuid: str, event):
        """Gère l'événement CHANNEL_ANSWER"""
        logger.info(f"📞 Call answered: {call_uuid}")
        
        # Récupérer infos de l'appel
        phone_number = event.getHeader("Caller-Destination-Number")
        scenario = event.getHeader("variable_scenario_name")
        campaign_id = event.getHeader("variable_campaign_id") or "0"
        
        logger.info(f"📞 New call: {phone_number} | UUID: {call_uuid} | Scenario: {scenario}")
        
        # Créer session streaming
        self._init_streaming_session(call_uuid, phone_number, scenario)
        
        # Lancer thread de traitement appel
        call_thread = threading.Thread(
            target=self._handle_call,
            args=(call_uuid, phone_number, scenario, campaign_id),
            daemon=True
        )
        call_thread.start()
        self.call_threads[call_uuid] = call_thread

    def _handle_channel_hangup(self, call_uuid: str, event):
        """Gère l'événement CHANNEL_HANGUP_COMPLETE"""
        hangup_cause = event.getHeader("Hangup-Cause") or "UNKNOWN"
        logger.info(f"📞 Call ended: {call_uuid} - {hangup_cause}")

        # Marquer comme raccroché pour que les threads en cours s'arrêtent
        if call_uuid in self.streaming_sessions:
            self.streaming_sessions[call_uuid]["hangup_detected"] = True
            logger.debug(f"[{call_uuid[:8]}] Hangup flag set - threads will stop")

        # Cleanup
        self.active_calls.pop(call_uuid, None)
        self.call_threads.pop(call_uuid, None)
        self.streaming_sessions.pop(call_uuid, None)
        self.call_sequences.pop(call_uuid, None)
        self.barge_in_active.pop(call_uuid, None)
        self.background_audio_active.pop(call_uuid, None)

    def _handle_dtmf(self, call_uuid: str, event):
        """Gère les touches DTMF (optionnel)"""
        digit = event.getHeader("DTMF-Digit")
        logger.debug(f"[{call_uuid[:8]}] DTMF: {digit}")


    # ========================================================================
    # SECTION 3: CALL MANAGEMENT
    # ========================================================================

    def originate_call(self, phone_number: str, campaign_id: int, scenario: str, retry: int = 0) -> Optional[str]:
        """
        Lance un appel sortant vers un numéro
        
        Args:
            phone_number: Numéro à appeler (format international sans +)
            campaign_id: ID de la campagne
            scenario: Nom du scénario JSON à utiliser
            retry: Numéro de tentative (pour les rappels)
            
        Returns:
            UUID de l'appel ou None si échec
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            logger.error("❌ ESL not connected")
            return None
        
        logger.info(f"Originating call to {phone_number} (campaign {campaign_id}, scenario {scenario}, retry {retry})")
        
        try:
            # Construire commande originate
            gateway = config.FREESWITCH_GATEWAY

            # Variables de canal
            variables = {
                "scenario_name": scenario,
                "campaign_id": str(campaign_id),
                "retry_count": str(retry),
                "ignore_early_media": "true",
            }

            # Caller ID optionnel (si défini dans config)
            if hasattr(config, 'CALLER_ID_NUMBER'):
                variables["origination_caller_id_number"] = config.CALLER_ID_NUMBER
            
            var_string = ",".join([f"{k}='{v}'" for k, v in variables.items()])
            
            # Commande originate
            cmd = f"originate {{{var_string}}}sofia/gateway/{gateway}/{phone_number} &park()"
            
            result = self.esl_conn_api.api(cmd)
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            
            # Extraire UUID
            if result_str.startswith("+OK"):
                call_uuid = result_str.split("+OK ")[1].strip()
                logger.info(f"✅ Call originated: {call_uuid}")
                
                # Enregistrer appel
                self.active_calls[call_uuid] = {
                    "phone_number": phone_number,
                    "campaign_id": campaign_id,
                    "scenario": scenario,
                    "retry": retry,
                    "started_at": datetime.now()
                }
                
                return call_uuid
            else:
                logger.error(f"❌ Originate failed: {result_str}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Originate error: {e}")
            return None

    def _init_streaming_session(self, call_uuid: str, phone_number: str, scenario: str):
        """
        Initialise la session streaming pour un appel
        
        Args:
            call_uuid: UUID de l'appel
            phone_number: Numéro appelé
            scenario: Nom du scénario
        """
        self.streaming_sessions[call_uuid] = {
            "phone_number": phone_number,
            "scenario": scenario,
            "current_step": None,
            "transcriptions": [],
            "intents": [],
            "consecutive_silences": 0,
            "consecutive_no_match": 0,
            "autonomous_turns": 0,
            "last_transcription": None,
            "objection_matcher": None,
            "final_result": None,
            "started_at": datetime.now(),
            "speech_start_time": 0,  # Timestamp début parole (pour backchannel detection)
            "prev_speech_start_time": 0,  # Timestamp previous speech_start (pour calcul durée)
            "audio_start_time": 0,  # Timestamp début audio (pour grace period)
            "barge_in_detected_time": 0  # Phase 2: Timestamp détection barge-in (pour smooth delay)
        }
        
        logger.debug(f"[{call_uuid[:8]}] Streaming session initialized")

    def _handle_call(self, call_uuid: str, phone_number: str, scenario: str, campaign_id: str):
        """
        Thread principal de traitement d'un appel
        
        Gère:
        - AMD detection
        - Background audio (optionnel)
        - Exécution du scénario
        - Cleanup
        
        Args:
            call_uuid: UUID de l'appel
            phone_number: Numéro appelé
            scenario: Nom du scénario
            campaign_id: ID campagne
        """
        try:
            logger.info(f"[{call_uuid[:8]}] 🌊 Call thread started for {phone_number}")

            # === ACTIVER STREAMING AUDIO (AVANT AMD Phase 3) ===
            # Phase 3: Streaming DOIT être actif AVANT AMD pour collecter transcriptions
            logger.debug(f"[{call_uuid[:8]}] Checking streaming: streaming_asr={self.streaming_asr is not None}, is_available={self.streaming_asr.is_available if self.streaming_asr else 'N/A'}")
            if self.streaming_asr and self.streaming_asr.is_available:
                streaming_enabled = self._enable_audio_streaming(call_uuid)
                if streaming_enabled:
                    logger.info(f"[{call_uuid[:8]}] ✅ Streaming audio WebSocket activé")
                else:
                    logger.warning(f"[{call_uuid[:8]}] ⚠️ Streaming audio échoué, mode record fallback")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ Streaming NOT available - using fallback mode")

            # === ENREGISTRER CALLBACK STREAMING ===
            if self.streaming_asr and self.streaming_asr.is_available:
                self.streaming_asr.register_callback(call_uuid, self._handle_streaming_event)
                logger.debug(f"[{call_uuid[:8]}] Streaming callback registered")

            # === AMD DETECTION (Phase 3: après streaming activé) ===
            if config.AMD_ENABLED:
                try:
                    amd_result = self._detect_answering_machine(call_uuid)
                    logger.info(f"[{call_uuid[:8]}] AMD result: {amd_result}")

                    if amd_result == "MACHINE":
                        logger.info(f"[{call_uuid[:8]}] Machine detected - hanging up")
                        self.hangup_call(call_uuid)
                        return
                    # Si HUMAN ou UNKNOWN, continuer normalement

                except Exception as e:
                    logger.warning(f"[{call_uuid[:8]}] AMD error: {e} - continuing anyway")

            # === BACKGROUND AUDIO (OPTIONNEL) ===
            # Désactivé pour l'instant - peut causer des conflits avec playback principal
            # self._start_background_audio(call_uuid)

            # === EXÉCUTER SCÉNARIO ===
            if self.scenario_manager:
                scenario_data = self.scenario_manager.load_scenario(scenario)
                if scenario_data:
                    self._execute_scenario(call_uuid, scenario, campaign_id)
                else:
                    logger.error(f"[{call_uuid[:8]}] Scenario '{scenario}' not found")
                    self.hangup_call(call_uuid)
            else:
                logger.error(f"[{call_uuid[:8]}] ScenarioManager not available")
                self.hangup_call(call_uuid)
                
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Call thread error: {e}", exc_info=True)
        finally:
            # Cleanup
            self._stop_background_audio(call_uuid)
            logger.info(f"[{call_uuid[:8]}] Call thread ended")

    def _detect_answering_machine(self, call_uuid: str) -> str:
        """
        Phase 3: Détecte si l'appelé est un humain ou un répondeur

        Méthode: Écouter pendant 2.5 secondes AVANT de commencer à parler

        Détection basée sur ce qui se passe pendant le délai initial:
        - Silence total → Incertain (peut être retry_silence ou personne timide)
        - "Allô" court (< 2s, < 3 mots) → Humain ✅
        - Message long (> 5s) → Répondeur ❌
        - Mots-clés typiques répondeur → Répondeur ❌
        - BEEP détecté → Répondeur ❌

        Args:
            call_uuid: UUID de l'appel

        Returns:
            "HUMAN", "MACHINE", ou "UNKNOWN"
        """
        logger.info(f"[{call_uuid[:8]}] 🎧 AMD: Listening for {config.AMD_INITIAL_DELAY}s before speaking...")

        # Timestamp début écoute
        listen_start = time.time()

        # Collecter transcriptions pendant le délai
        collected_text = ""
        speech_detected = False
        total_speech_duration = 0.0
        last_seen_transcription = ""

        while time.time() - listen_start < config.AMD_INITIAL_DELAY:
            # Vérifier si hangup
            session = self.streaming_sessions.get(call_uuid, {})
            if session.get("hangup_detected", False):
                logger.info(f"[{call_uuid[:8]}] AMD: Call hung up during listening")
                return "UNKNOWN"

            # V3 FIX: Récupérer dernière transcription depuis "last_transcription" (pas "transcriptions")
            text = session.get("last_transcription") or ""
            text = text.strip() if text else ""

            if text and text != last_seen_transcription:
                collected_text += " " + text
                last_seen_transcription = text
                speech_detected = True
                logger.debug(f"[{call_uuid[:8]}] AMD: Collected: '{text}'")

            # Attendre un peu avant vérifier à nouveau
            time.sleep(0.1)

        # Analyser ce qui a été collecté
        collected_text = collected_text.strip().lower()
        word_count = len(collected_text.split()) if collected_text else 0

        logger.info(f"[{call_uuid[:8]}] AMD: Listening complete. Text: '{collected_text}' ({word_count} words)")

        # === ANALYSE ===

        # 1. Silence total → UNKNOWN (peut être humain timide ou retry_silence)
        if not speech_detected or not collected_text:
            logger.info(f"[{call_uuid[:8]}] AMD: Silence detected → UNKNOWN (continuing anyway)")
            return "UNKNOWN"

        # 2. Très court (< 3 mots, typiquement "allô" ou "oui") → HUMAN
        if word_count <= 3:
            logger.info(f"[{call_uuid[:8]}] AMD: Short greeting ({word_count} words) → HUMAN ✅")
            return "HUMAN"

        # 3. Mots-clés typiques répondeur
        machine_keywords = [
            "bonjour vous êtes bien",
            "laissez un message",
            "veuillez laisser",
            "après le bip",
            "après le signal",
            "notre bureau est fermé",
            "nous sommes absents",
            "bienvenue chez",
            "merci d'avoir appelé"
        ]

        for keyword in machine_keywords:
            if keyword in collected_text:
                logger.info(f"[{call_uuid[:8]}] AMD: Keyword '{keyword}' detected → MACHINE ❌")
                return "MACHINE"

        # 4. Message long (> 10 mots) → Probablement répondeur
        if word_count > 10:
            logger.info(f"[{call_uuid[:8]}] AMD: Long message ({word_count} words) → MACHINE ❌")
            return "MACHINE"

        # 5. Sinon, considérer comme humain
        logger.info(f"[{call_uuid[:8]}] AMD: Normal speech ({word_count} words) → HUMAN ✅")
        return "HUMAN"

    def hangup_call(self, call_uuid: str):
        """
        Raccroche un appel
        
        Args:
            call_uuid: UUID de l'appel
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            return
        
        try:
            cmd = f"uuid_kill {call_uuid}"
            self.esl_conn_api.api(cmd)
            logger.info(f"[{call_uuid[:8]}] Call hung up")
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Hangup error: {e}")


    # ========================================================================
    # SECTION 4: AUDIO SYSTEM
    # ========================================================================

    def _play_audio(self, call_uuid: str, audio_file: str) -> bool:
        """
        Joue un fichier audio sur l'appel avec support barge-in
        
        Utilise uuid_broadcast (pas uuid_playback qui n'existe pas)
        
        Args:
            call_uuid: UUID de l'appel
            audio_file: Chemin absolu vers fichier audio
            
        Returns:
            True si lecture complète, False si interrompu
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            return False
        
        try:
            # Réinitialiser flag barge-in
            self.barge_in_active[call_uuid] = False

            # Timestamp début audio (pour grace period anti-faux positifs)
            if call_uuid in self.streaming_sessions:
                self.streaming_sessions[call_uuid]["audio_start_time"] = time.time()
                # Reset robot_speech_end_time car robot commence à parler
                self.streaming_sessions[call_uuid]["robot_speech_end_time"] = 0

            logger.info(f"[{call_uuid[:8]}] 🎬 STATE: PLAYING_AUDIO (grace period: {config.GRACE_PERIOD_SECONDS:.1f}s, then backchannel filtering active)")

            # Commande uuid_broadcast pour playback
            # Syntaxe: uuid_broadcast <uuid> <path> [aleg|bleg|both]
            cmd = f"uuid_broadcast {call_uuid} {audio_file} aleg"
            result = self.esl_conn_api.api(cmd)
            
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            
            if "+OK" not in result_str:
                logger.error(f"[{call_uuid[:8]}] Playback failed: {result_str}")
                return False
            
            # Calculer durée audio (avec fallback si format inconnu)
            audio_duration = self._get_audio_duration(audio_file)
            logger.debug(f"[{call_uuid[:8]}] 🔊 Playing: {Path(audio_file).name} (duration: {audio_duration:.1f}s)")
            
            # Auto-tracking
            self.call_sequences[call_uuid].append({
                "type": "audio",
                "file": audio_file,
                "timestamp": datetime.now()
            })
            
            # Surveiller barge-in pendant playback
            max_duration = audio_duration + 1.0  # Durée + 1s marge
            check_interval = 0.1  # 100ms
            elapsed = 0.0

            while elapsed < max_duration:
                # Vérifier hangup
                if call_uuid not in self.streaming_sessions or self.streaming_sessions[call_uuid].get("hangup_detected", False):
                    logger.warning(f"[{call_uuid[:8]}] 📞 Hangup detected - stopping audio playback")
                    return False

                # Phase 2: Vérifier barge-in avec smooth delay
                session = self.streaming_sessions.get(call_uuid, {})
                barge_in_time = session.get("barge_in_detected_time", 0)

                if barge_in_time > 0:
                    # Barge-in détecté, vérifier si smooth delay écoulé
                    time_since_detection = time.time() - barge_in_time

                    if time_since_detection >= config.BARGE_IN_SMOOTH_DELAY:
                        # Smooth delay écoulé → Couper MAINTENANT
                        self.barge_in_active[call_uuid] = True
                        logger.info(f"[{call_uuid[:8]}] ⏹️ Audio interrupted by barge-in after {elapsed:.1f}s (smooth delay {config.BARGE_IN_SMOOTH_DELAY}s elapsed)")

                        # STOPPER l'audio en cours avec uuid_break
                        stop_cmd = f"uuid_break {call_uuid}"
                        self.esl_conn_api.api(stop_cmd)
                        logger.debug(f"[{call_uuid[:8]}] 🛑 Sent uuid_break to stop playback")

                        # CRITIQUE: Réinitialiser le flag barge-in pour le prochain audio
                        self.streaming_sessions[call_uuid]["barge_in_detected_time"] = 0
                        logger.debug(f"[{call_uuid[:8]}] 🔄 Barge-in flag reset for next audio")

                        # V3: reset_recognizer() supprimé (causait crash Vosk)
                        # Le buffer Vosk se vide automatiquement après speech_end

                        # Tracker quand robot finit de parler (interrompu par barge-in)
                        self.streaming_sessions[call_uuid]["robot_speech_end_time"] = time.time()

                        return False
                    else:
                        # Smooth delay en cours, robot continue de parler
                        remaining = config.BARGE_IN_SMOOTH_DELAY - time_since_detection
                        logger.debug(f"[{call_uuid[:8]}] 🔄 Barge-in smooth delay active (remaining: {remaining:.1f}s)")

                # Ancienne logique (fallback si pas de smooth delay)
                elif self.barge_in_active.get(call_uuid, False):
                    logger.info(f"[{call_uuid[:8]}] ⏹️ Audio interrupted by barge-in after {elapsed:.1f}s")

                    # STOPPER l'audio en cours avec uuid_break
                    stop_cmd = f"uuid_break {call_uuid}"
                    self.esl_conn_api.api(stop_cmd)
                    logger.debug(f"[{call_uuid[:8]}] 🛑 Sent uuid_break to stop playback")

                    return False

                time.sleep(check_interval)
                elapsed += check_interval

            logger.debug(f"[{call_uuid[:8]}] ✅ Audio playback completed ({elapsed:.1f}s)")

            # Tracker quand robot finit de parler (audio terminé normalement)
            if call_uuid in self.streaming_sessions:
                self.streaming_sessions[call_uuid]["robot_speech_end_time"] = time.time()

            logger.info(f"[{call_uuid[:8]}] 🎧 STATE: WAITING_RESPONSE (all speech will be captured, no backchannel filtering)")
            return True
            
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Playback error: {e}")
            return False

    def _get_audio_duration(self, audio_file: str) -> float:
        """
        Calcule la durée d'un fichier audio WAV
        
        Args:
            audio_file: Chemin vers fichier WAV
            
        Returns:
            Durée en secondes (60.0 si erreur/format inconnu)
        """
        try:
            import wave
            with wave.open(audio_file, 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                duration = frames / float(rate)
                return duration
        except Exception as e:
            # Format WAV non standard (mu-law, etc.) - utiliser durée par défaut
            logger.debug(f"Could not read audio duration from {Path(audio_file).name}: {e}")
            return 60.0  # Fallback

    def _enable_audio_streaming(self, call_uuid: str) -> bool:
        """
        Active le streaming audio FreeSWITCH → WebSocket avec mod_audio_stream

        Utilise uuid_audio_stream pour envoyer l'audio RTP en temps réel
        vers notre serveur WebSocket StreamingASR.

        Paramètres streaming:
        - Format: L16 PCM (Linear 16-bit)
        - Sample rate: 16kHz (optimal pour Vosk)
        - Mix: mono (caller only)
        - URL: ws://127.0.0.1:8080/stream/{UUID}

        Args:
            call_uuid: UUID de l'appel

        Returns:
            True si streaming activé avec succès
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            logger.error(f"[{call_uuid[:8]}] ESL API not connected")
            return False

        try:
            # URL WebSocket du serveur StreamingASR
            websocket_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"

            # Paramètres streaming
            # V3 FIX: Utiliser STEREO pour séparer complètement les canaux
            # Logs prouvent que "mono" capte AUSSI le robot (écho/loopback)
            # - "mono" = BUGGÉ - capte robot + client (transcriptions merdiques)
            # - "mixed" = Les deux parties mixées (pire)
            # - "stereo" = L=caller uniquement, R=callee uniquement ✅ SOLUTION
            mix_type = "stereo"
            sampling_rate = "16000" # 16kHz pour Vosk (meilleur qualité/performance)
            metadata = ""           # Métadonnées optionnelles JSON

            # Commande uuid_audio_stream (mod_audio_stream requis)
            # Format: uuid_audio_stream <uuid> start <wss-url> <mix-type> <sampling-rate> <metadata>
            cmd = f"uuid_audio_stream {call_uuid} start {websocket_url} {mix_type} {sampling_rate} {metadata}"

            logger.debug(f"[{call_uuid[:8]}] Executing: {cmd}")
            result = self.esl_conn_api.api(cmd)

            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            if "+OK" in result_str or "success" in result_str.lower():
                logger.info(f"[{call_uuid[:8]}] ✅ Audio streaming started to WebSocket (16kHz {mix_type})")
                logger.debug(f"[{call_uuid[:8]}]    URL: {websocket_url}")
                return True
            else:
                logger.error(f"[{call_uuid[:8]}] ❌ Audio streaming failed: {result_str}")
                logger.warning(f"[{call_uuid[:8]}]    Vérifier que mod_audio_stream est chargé")
                return False

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Audio streaming error: {e}", exc_info=True)
            return False

    def _start_background_audio(self, call_uuid: str, background_audio_path: Optional[str] = None):
        """
        Démarre audio de fond en boucle (ambiance)
        
        Utilise uuid_displace avec:
        - limit=0 pour boucle infinie
        - mux pour mixer avec audio principal
        
        Args:
            call_uuid: UUID de l'appel
            background_audio_path: Chemin fichier audio (optionnel)
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            return
        
        try:
            # Fichier par défaut
            if background_audio_path is None:
                background_audio_path = str(config.AUDIO_FILES_PATH / "background" / "default.wav")
            
            # Vérifier existence
            if not Path(background_audio_path).exists():
                logger.warning(f"[{call_uuid[:8]}] Background audio not found: {background_audio_path}")
                return
            
            # Attendre que le canal soit prêt (après answer)
            time.sleep(0.5)
            
            # Commande uuid_displace
            # Syntaxe: uuid_displace <uuid> start <file> <limit> [mux]
            cmd = f"uuid_displace {call_uuid} start {background_audio_path} 0 mux"
            result = self.esl_conn_api.api(cmd)
            
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            
            if "+OK" in result_str or "success" in result_str.lower():
                self.background_audio_active[call_uuid] = True
                logger.info(f"[{call_uuid[:8]}] ✅ Background audio started (loop): {Path(background_audio_path).name}")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ Background audio failed: {result_str}")
                
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Background audio error: {e}")

    def _stop_background_audio(self, call_uuid: str):
        """
        Arrête l'audio de fond
        
        Args:
            call_uuid: UUID de l'appel
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            return
        
        if not self.background_audio_active.get(call_uuid, False):
            return
        
        try:
            cmd = f"uuid_displace {call_uuid} stop"
            result = self.esl_conn_api.api(cmd)
            
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            
            if "+OK" in result_str:
                self.background_audio_active[call_uuid] = False
                logger.info(f"[{call_uuid[:8]}] ✅ Background audio stopped")
            else:
                logger.debug(f"[{call_uuid[:8]}] Background audio stop result: {result_str}")
                self.background_audio_active[call_uuid] = False
                
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Stop background audio error: {e}")
            self.background_audio_active.pop(call_uuid, None)


    # ========================================================================
    # SECTION 5: SPEECH RECOGNITION
    # ========================================================================

    def _listen_for_response(self, call_uuid: str, timeout: int = 10) -> Optional[str]:
        """
        Écoute et transcrit la réponse du client

        Modes:
        1. Streaming (WebSocket) - Si StreamingASR disponible ET mod_audio_stream installé
        2. Record fallback - Enregistre puis transcrit (mode par défaut)

        Args:
            call_uuid: UUID de l'appel
            timeout: Timeout en secondes

        Returns:
            Transcription texte ou None si silence/timeout
        """
        if call_uuid not in self.streaming_sessions:
            logger.warning(f"[{call_uuid[:8]}] No streaming session")
            return None

        try:
            # Mode streaming si StreamingASR disponible ET mod_audio_stream installé
            if self.streaming_asr and self.streaming_asr.is_available:
                logger.debug(f"[{call_uuid[:8]}] Using streaming mode for transcription")
                return self._listen_streaming(call_uuid, timeout)
            else:
                # Fallback: mode record si streaming pas disponible
                logger.debug(f"[{call_uuid[:8]}] Using record fallback mode for transcription")
                return self._listen_record_fallback(call_uuid, timeout)

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Listen error: {e}", exc_info=True)
            return None

    def _listen_streaming(self, call_uuid: str, timeout: int) -> Optional[str]:
        """
        Écoute en mode streaming (temps réel via WebSocket)

        Attend que le client finisse de parler avant de retourner la transcription.
        Le VAD détecte automatiquement la fin de parole (1.5s de silence).

        Args:
            call_uuid: UUID de l'appel
            timeout: Timeout en secondes

        Returns:
            Transcription ou None
        """
        logger.debug(f"[{call_uuid[:8]}] 👂 Listening (streaming mode)...")

        # TOUJOURS effacer l'ancienne transcription pour éviter réutilisation
        self.streaming_sessions[call_uuid]["last_transcription"] = None
        self.streaming_sessions[call_uuid]["last_speech_time"] = 0

        # Attendre nouvelle transcription (le client est en train de parler)
        start_time = time.time()
        check_interval = 0.1  # 100ms

        while time.time() - start_time < timeout:
            # Vérifier si hangup détecté
            if call_uuid not in self.streaming_sessions or self.streaming_sessions[call_uuid].get("hangup_detected", False):
                logger.warning(f"[{call_uuid[:8]}] 📞 Hangup detected - stopping listen")
                return None

            # Vérifier si transcription disponible
            transcription = self.streaming_sessions[call_uuid].get("last_transcription")

            if transcription:
                logger.info(f"[{call_uuid[:8]}] ✅ Got transcription: {transcription}")
                # Effacer pour éviter réutilisation
                self.streaming_sessions[call_uuid]["last_transcription"] = None
                return transcription

            time.sleep(check_interval)

        # Timeout sans transcription
        logger.warning(f"[{call_uuid[:8]}] ⏱️ Listen timeout ({timeout}s) - no response")
        return None

    def _listen_record_fallback(self, call_uuid: str, timeout: int) -> Optional[str]:
        """
        Fallback: Enregistre audio puis transcrit

        Utilisé si StreamingASR n'est pas disponible

        AMÉLIORATION: Enregistre PENDANT timeout, puis transcrit immédiatement

        Args:
            call_uuid: UUID de l'appel
            timeout: Timeout en secondes

        Returns:
            Transcription ou None
        """
        logger.debug(f"[{call_uuid[:8]}] 👂 Listening (record fallback mode, timeout: {timeout}s)...")

        try:
            # Créer fichier temporaire
            temp_dir = Path("/tmp/minibot_responses")
            temp_dir.mkdir(exist_ok=True)
            record_file = temp_dir / f"{call_uuid}_{int(time.time())}.wav"

            # Démarrer enregistrement avec limite de durée
            # uuid_record format: uuid_record <uuid> start <path> [<limit_secs>]
            cmd = f"uuid_record {call_uuid} start {record_file} {timeout}"
            result = self.esl_conn_api.api(cmd)

            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            logger.debug(f"[{call_uuid[:8]}] uuid_record start result: {result_str}")

            # Attendre fin enregistrement (timeout + petite marge)
            time.sleep(timeout + 0.5)

            # Arrêter enregistrement (au cas où)
            cmd = f"uuid_record {call_uuid} stop {record_file}"
            self.esl_conn_api.api(cmd)

            # Petite attente pour flush du fichier
            time.sleep(0.2)

            # Vérifier si fichier existe et a du contenu
            if not record_file.exists():
                logger.debug(f"[{call_uuid[:8]}] No recording file created (silence)")
                return None

            file_size = record_file.stat().st_size
            logger.debug(f"[{call_uuid[:8]}] Recording file size: {file_size} bytes")

            # Taille minimale: ~1KB pour avoir du contenu audio
            if file_size < 1000:
                logger.debug(f"[{call_uuid[:8]}] Recording too small (silence)")
                record_file.unlink()
                return None

            # Transcrire avec Vosk
            if not self.stt_service:
                logger.error(f"[{call_uuid[:8]}] STT service not available")
                record_file.unlink()
                return None

            logger.debug(f"[{call_uuid[:8]}] Transcribing recording...")
            transcription = self.stt_service.transcribe_file(str(record_file))

            # Cleanup
            try:
                record_file.unlink()
            except:
                pass

            if transcription:
                logger.info(f"[{call_uuid[:8]}] ✅ Transcription: '{transcription}'")
                return transcription
            else:
                logger.debug(f"[{call_uuid[:8]}] No speech detected in recording")
                return None

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Record fallback error: {e}", exc_info=True)
            return None

    # ============================================================================
    # V3: _is_backchannel() SUPPRIMÉ
    # ============================================================================
    # Cette méthode complexe a été remplacée par BargeInDetector.should_trigger()
    # Avantages V3:
    # - Logique simple et testable
    # - Pas de race conditions (durée fournie par événements)
    # - Pas de variables globales éparpillées
    # ============================================================================

    def _handle_streaming_event(self, event_data: Dict[str, Any]):
        """
        V3: Callback pour événements streaming audio - VERSION SIMPLIFIÉE

        Appelé par StreamingASR V3 quand:
        - speech_start: Début de parole (avec durée = 0)
        - speech_end: Fin de parole (avec durée incluse ← NOUVEAU V3)
        - transcription: Texte disponible (avec durée incluse ← NOUVEAU V3)

        Args:
            event_data: Dict contenant:
                - type: "speech_start" | "speech_end" | "transcription"
                - call_uuid: UUID de l'appel
                - duration: Durée de parole en secondes (speech_end, transcription)
                - text: Texte transcrit (transcription)
                - transcription_type: "final" | "partial" (transcription)
                - timestamp: Timestamp événement
        """
        # Extraire données (V3: "type" au lieu de "event")
        event_type = event_data.get("type")
        call_uuid = event_data.get("call_uuid")

        if not call_uuid or call_uuid not in self.streaming_sessions:
            logger.debug(f"[V3] Event ignored - call_uuid not in active sessions: {call_uuid}")
            return

        session = self.streaming_sessions[call_uuid]

        try:
            # ================================================================
            # SPEECH_START
            # ================================================================
            if event_type == "speech_start":
                logger.debug(f"[{call_uuid[:8]}] 🗣️ V3 Speech START detected")
                session["speech_start_time"] = time.time()

            # ================================================================
            # SPEECH_END - DÉCISION BARGE-IN ICI (PAS SUR TRANSCRIPTION)
            # ================================================================
            elif event_type == "speech_end":
                duration = event_data.get("duration", 0.0)  # ← NOUVEAU V3
                logger.info(f"[{call_uuid[:8]}] 🤐 V3 Speech END (durée: {duration:.2f}s)")

                # Sauvegarder durée pour debug
                session["last_speech_duration"] = duration

                # Déterminer audio_state
                is_playing_audio = not self.barge_in_active.get(call_uuid, True)
                audio_state = "PLAYING_AUDIO" if is_playing_audio else "WAITING_RESPONSE"

                # Vérifier grace period
                audio_start_time = session.get("audio_start_time", 0)
                current_time = time.time()
                elapsed_since_audio = current_time - audio_start_time if audio_start_time > 0 else 999
                grace_period_active = elapsed_since_audio < config.GRACE_PERIOD_SECONDS

                # V3: Utiliser BargeInDetector
                should_barge_in = self.barge_in_detector.should_trigger(
                    audio_state=audio_state,
                    speech_duration=duration,
                    grace_period_active=grace_period_active
                )

                if should_barge_in:
                    # BARGE-IN IMMÉDIAT
                    session["barge_in_detected_time"] = current_time
                    logger.info(f"[{call_uuid[:8]}] ✅ V3 BARGE-IN triggered on speech_end")

                    # V3: Smooth delay optionnel (1s)
                    if config.SMOOTH_DELAY_SECONDS > 0:
                        logger.debug(f"[{call_uuid[:8]}] ⏱️ V3 Smooth delay: {config.SMOOTH_DELAY_SECONDS}s")
                        time.sleep(config.SMOOTH_DELAY_SECONDS)

            # ================================================================
            # TRANSCRIPTION - LOGGING SEULEMENT (PAS DE DÉCISION BARGE-IN)
            # ================================================================
            elif event_type == "transcription":
                text = event_data.get("text", "").strip()
                transcription_type = event_data.get("transcription_type", "")  # V3: transcription_type
                duration = event_data.get("duration", 0.0)  # ← NOUVEAU V3

                # Ne traiter que finales
                if text and transcription_type == "final":
                    logger.info(
                        f"[{call_uuid[:8]}] 📝 V3 FINAL transcription: '{text}' "
                        f"(durée: {duration:.2f}s)"
                    )

                    # Sauvegarder pour NLP
                    session["last_transcription"] = text
                    session["last_speech_time"] = time.time()

                    # NOTE V3: Barge-in déjà décidé sur speech_end
                    # Cette transcription est juste pour NLP

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] V3 Streaming event error: {e}", exc_info=True)


    # ========================================================================
    # SECTION 6: SCENARIO EXECUTION ENGINE
    # ========================================================================

    def _execute_scenario(self, call_uuid: str, scenario_name: str, campaign_id: str):
        """
        Point d'entrée principal pour exécution d'un scénario
        
        Charge le scénario JSON et détermine le mode:
        - Mode classique (max_autonomous_turns = 0): Intent mapping simple
        - Mode agent autonome (max_autonomous_turns > 0): Gestion objections
        
        Args:
            call_uuid: UUID de l'appel
            scenario_name: Nom du scénario
            campaign_id: ID campagne
        """
        if not self.scenario_manager:
            logger.error(f"[{call_uuid[:8]}] ScenarioManager not available")
            self.hangup_call(call_uuid)
            return
        
        logger.info(f"[{call_uuid[:8]}] Executing scenario: {scenario_name}")
        
        # Charger scénario
        scenario = self.scenario_manager.load_scenario(scenario_name)
        if not scenario:
            logger.error(f"[{call_uuid[:8]}] Scenario '{scenario_name}' not found")
            self.hangup_call(call_uuid)
            return
        
        # Sauvegarder dans session
        if call_uuid in self.streaming_sessions:
            self.streaming_sessions[call_uuid]["scenario_data"] = scenario
        
        # Vérifier mode agent autonome
        is_agent_mode = self.scenario_manager.is_agent_mode(scenario)
        
        if is_agent_mode:
            logger.info(f"[{call_uuid[:8]}] 🤖 Agent Mode ENABLED")
            
            # Charger objection matcher
            theme_file = self.scenario_manager.get_theme_file(scenario) or "objections_general"
            
            if OBJECTION_MATCHER_AVAILABLE:
                try:
                    logger.info(f"[{call_uuid[:8]}] Loading objections from: {theme_file}")
                    matcher = ObjectionMatcher.load_objections_from_file(theme_file)
                    
                    if matcher:
                        self.streaming_sessions[call_uuid]["objection_matcher"] = matcher
                        logger.info(f"[{call_uuid[:8]}] ✅ Objection matcher loaded ({theme_file})")
                    else:
                        logger.warning(f"[{call_uuid[:8]}] ⚠️ Failed to load objection matcher")
                except Exception as e:
                    logger.error(f"[{call_uuid[:8]}] Objection matcher error: {e}")
        
        # Variables pour remplacement (first_name, etc.)
        variables = {}
        variables.setdefault("first_name", "")
        variables.setdefault("last_name", "")
        variables.setdefault("company", "")
        
        # Historique pour qualification
        call_history = {}
        
        # Déterminer step initial
        if is_agent_mode:
            # Mode agent: utiliser rail
            rail = self.scenario_manager.get_rail(scenario)
            if rail:
                current_step = rail[0]
                logger.info(f"[{call_uuid[:8]}] Rail: {' → '.join(rail)}")
            else:
                logger.error(f"[{call_uuid[:8]}] Agent mode but no rail defined")
                self.hangup_call(call_uuid)
                return
        else:
            # Mode classique: utiliser start_step ou "hello"
            metadata = scenario.get("metadata", {})
            current_step = metadata.get("start_step") or scenario.get("start_step", "hello")
        
        # === BOUCLE PRINCIPALE D'EXÉCUTION ===
        max_iterations = 50  # Sécurité anti-boucle infinie
        iteration = 0
        
        while current_step and iteration < max_iterations:
            iteration += 1
            
            # Récupérer config step
            step_config = self.scenario_manager.get_step_config(scenario, current_step)
            if not step_config:
                logger.error(f"[{call_uuid[:8]}] Step '{current_step}' not found")
                break
            
            # Sauvegarder step courant
            if call_uuid in self.streaming_sessions:
                self.streaming_sessions[call_uuid]["current_step"] = current_step

            # === EXÉCUTER STEP SELON MODE ===
            if is_agent_mode:
                # Mode agent autonome (avec objections)
                next_step = self._execute_step_autonomous(
                    call_uuid, scenario, current_step, variables, call_history
                )

                if next_step is None:
                    # 2 silences ou 3 no_match → terminé
                    logger.warning(f"[{call_uuid[:8]}] Autonomous step returned None → ending")
                    break

                current_step = next_step
            else:
                # Mode classique (intent mapping simple)
                next_step = self._execute_step_classic(
                    call_uuid, scenario, current_step, variables, call_history
                )

                if next_step == "end" or not next_step:
                    logger.info(f"[{call_uuid[:8]}] Scenario ended")
                    break

                current_step = next_step

            # Vérifier si step terminal (avec résultat) APRÈS l'avoir exécuté
            if "result" in step_config:
                result = step_config["result"]
                logger.info(f"[{call_uuid[:8]}] Scenario ended with result: {result}")

                # Sauvegarder résultat
                if call_uuid in self.streaming_sessions:
                    self.streaming_sessions[call_uuid]["final_result"] = result

                break
        
        # Fin scénario
        self.hangup_call(call_uuid)

    def _execute_step_classic(
        self,
        call_uuid: str,
        scenario: Dict[str, Any],
        step_name: str,
        variables: Dict[str, Any],
        call_history: Dict[str, str]
    ) -> Optional[str]:
        """
        Exécute une étape en mode classique (intent mapping simple)
        
        Flux:
        1. Jouer audio
        2. Écouter réponse
        3. Analyser intent
        4. Mapper vers next step
        
        Args:
            call_uuid: UUID appel
            scenario: Scénario complet
            step_name: Nom de l'étape
            variables: Variables pour remplacement
            call_history: Historique intents
            
        Returns:
            Nom du prochain step ou None
        """
        step_config = self.scenario_manager.get_step_config(scenario, step_name)
        if not step_config:
            return None
        
        logger.info(f"[{call_uuid[:8]}] Step: {step_name} (type: {step_config.get('audio_type')})")
        
        # 1. Jouer audio
        self._play_step_audio(call_uuid, step_config, variables, scenario)
        
        # 2. Écouter réponse
        timeout = step_config.get("timeout", 4)  # 4s par défaut (réduit de 10s)
        transcription = self._listen_for_response(call_uuid, timeout)
        
        # 3. Analyser intent
        intent = "silence"
        if transcription and self.nlp_service:
            intent_result = self.nlp_service.analyze_intent(transcription, context="telemarketing")
            intent = intent_result.get("intent", "unknown")
            logger.info(f"[{call_uuid[:8]}] Intent: {intent}")
            
            # Sauvegarder
            call_history[step_name] = intent
        else:
            logger.warning(f"[{call_uuid[:8]}] ⏱️ Listen timeout ({timeout}s) - no response")
        
        # 4. Déterminer next step
        next_step = self.scenario_manager.get_next_step(scenario, step_name, intent)
        
        return next_step


    # ========================================================================
    # SECTION 7: AUTONOMOUS AGENT MODE (Objections Handler)
    # ========================================================================

    def _execute_step_autonomous(
        self,
        call_uuid: str,
        scenario: Dict[str, Any],
        step_name: str,
        variables: Dict[str, Any],
        call_history: Dict[str, str]
    ) -> Optional[str]:
        """
        Exécute une étape en mode agent autonome (avec gestion objections)
        
        Logique:
        1. Jouer message principal (1ère fois seulement)
        2. BOUCLE (max_autonomous_turns):
           a. Écouter réponse client
           b. Si silence → retry ou hangup (2 silences = NO_ANSWER)
           c. Analyser intent
           d. Si objection/question:
              - Matcher dans DB (50ms)
              - Jouer audio pré-enregistré si match
              - Sinon jouer fallback "not_understood"
              - Continuer boucle
           e. Si affirm/deny → sortir et passer au next step
        3. Si max_turns atteint → next step selon dernier intent
        
        SÉCURITÉS:
        - 2 silences consécutifs → hangup NO_ANSWER
        - 3 no_match consécutifs → hangup silencieux
        - max_autonomous_turns par step (default 2)
        
        Args:
            call_uuid: UUID appel
            scenario: Scénario complet
            step_name: Nom étape
            variables: Variables
            call_history: Historique
            
        Returns:
            Nom next step ou None si terminé
        """
        if call_uuid not in self.streaming_sessions:
            return None
        
        session = self.streaming_sessions[call_uuid]
        step_config = self.scenario_manager.get_step_config(scenario, step_name)
        
        if not step_config:
            logger.error(f"[{call_uuid[:8]}] Step '{step_name}' not found")
            return None
        
        # Max autonomous turns pour cette étape
        max_turns = self.scenario_manager.get_max_autonomous_turns(scenario, step_name)
        logger.info(f"[{call_uuid[:8]}] 🤖 Autonomous step: {step_name} (max_turns={max_turns})")
        
        # Réinitialiser compteur
        session["autonomous_turns"] = 0
        
        # === BOUCLE AUTONOME ===
        while session["autonomous_turns"] < max_turns:
            turn_num = session["autonomous_turns"] + 1
            logger.info(f"[{call_uuid[:8]}]   └─ Turn {turn_num}/{max_turns}")
            
            # 1. Jouer message principal (première fois seulement)
            if session["autonomous_turns"] == 0:
                self._play_step_audio(call_uuid, step_config, variables, scenario)
            
            # 2. Écouter réponse
            timeout = step_config.get("timeout", 4)  # 4s par défaut (réduit de 10s)
            transcription = self._listen_for_response(call_uuid, timeout)
            
            # === GESTION SILENCE ===
            if not transcription or not transcription.strip():
                logger.warning(f"[{call_uuid[:8]}]   └─ Silence détecté ({session['consecutive_silences'] + 1}/2)")
                session["consecutive_silences"] += 1
                
                # 2 silences = hangup NO_ANSWER
                if session["consecutive_silences"] >= 2:
                    logger.warning(f"[{call_uuid[:8]}] ❌ 2 silences consécutifs → hangup NO_ANSWER")
                    self._update_call_status(call_uuid, "NO_ANSWER")
                    return None
                
                # 1er silence: jouer retry audio
                logger.info(f"[{call_uuid[:8]}] 🔁 Premier silence → retry audio")
                voice = scenario.get("metadata", {}).get("voice") or scenario.get("voice", config.DEFAULT_VOICE)
                retry_audio = step_config.get("retry_audio", "retry_silence.wav")
                retry_path = config.get_audio_path(voice, "base", retry_audio)
                
                if retry_path.exists():
                    self._play_audio(call_uuid, str(retry_path))
                else:
                    logger.error(f"[{call_uuid[:8]}]   ❌ Retry audio not found: {retry_path}")
                
                session["autonomous_turns"] += 1
                continue
            
            # Client a parlé - réinitialiser compteur silences
            session["consecutive_silences"] = 0
            
            # 3. Analyser intent
            if not self.nlp_service:
                logger.warning(f"[{call_uuid[:8]}] NLP service not available")
                break
            
            intent_result = self.nlp_service.analyze_intent(transcription, context="telemarketing")
            intent = intent_result.get("intent", "unknown")
            
            logger.info(f"[{call_uuid[:8]}]   └─ Intent: {intent}")
            
            # Sauvegarder
            session["transcriptions"].append(transcription)
            session["intents"].append(intent)
            
            # === OBJECTION / QUESTION ===
            if intent in ["objection", "question", "unsure"]:
                logger.info(f"[{call_uuid[:8]}] 🎯 Objection/Question détectée → Matching...")
                
                # Matcher objection
                matcher = session.get("objection_matcher")
                match = None
                
                if matcher and OBJECTION_MATCHER_AVAILABLE:
                    match_start = time.time()
                    match = matcher.find_best_match(transcription, min_score=0.6)
                    match_latency_ms = (time.time() - match_start) * 1000
                    
                    if match:
                        logger.info(f"[{call_uuid[:8]}]   ✅ Match trouvé ({match_latency_ms:.0f}ms): {match['objection'][:50]}...")
                        
                        # Réinitialiser compteur no_match
                        session["consecutive_no_match"] = 0
                        
                        # Jouer audio pré-enregistré
                        if match.get("audio_path"):
                            audio_path = self._resolve_audio_path(call_uuid, match["audio_path"], scenario)
                            if audio_path:
                                logger.info(f"[{call_uuid[:8]}]   🔊 Playing pre-recorded answer")
                                self._play_audio(call_uuid, audio_path)
                            else:
                                logger.warning(f"[{call_uuid[:8]}]   ⚠️ Audio file not found: {match['audio_path']}")
                        
                        # Sauvegarder réponse
                        session["transcriptions"].append(match.get("response", ""))
                    else:
                        logger.info(f"[{call_uuid[:8]}]   ❌ No match ({match_latency_ms:.0f}ms)")
                
                # Si pas de match → fallback
                if not match:
                    session["consecutive_no_match"] += 1
                    logger.warning(f"[{call_uuid[:8]}] ⚠️ No match found ({session['consecutive_no_match']}/3)")
                    
                    # 3 no match = hangup silencieux
                    if session["consecutive_no_match"] >= 3:
                        logger.warning(f"[{call_uuid[:8]}] ❌ 3 no match consécutifs → hangup silencieux")
                        self._update_call_status(call_uuid, "NO_ANSWER")
                        return None
                    
                    # Jouer fallback "not_understood"
                    logger.info(f"[{call_uuid[:8]}] Playing fallback audio not_understood.wav")
                    voice = scenario.get("metadata", {}).get("voice") or scenario.get("voice", config.DEFAULT_VOICE)
                    fallback_audio = step_config.get("fallback_audio", "not_understood.wav")
                    fallback_path = config.get_audio_path(voice, "base", fallback_audio)
                    
                    if fallback_path.exists():
                        self._play_audio(call_uuid, str(fallback_path))
                    else:
                        logger.error(f"[{call_uuid[:8]}]   ❌ Fallback audio not found: {fallback_path}")
                
                # Incrémenter compteur turns
                session["autonomous_turns"] += 1
            
            # === RÉPONSE POSITIVE ===
            elif intent in ["affirm", "positive", "interested"]:
                logger.info(f"[{call_uuid[:8]}] ✅ Positive response → next step")
                call_history[step_name] = intent
                break
            
            # === RÉPONSE NÉGATIVE ===
            elif intent in ["deny", "negative", "not_interested"]:
                logger.info(f"[{call_uuid[:8]}] ❌ Negative response")
                call_history[step_name] = intent
                break
            
            # === INTENT INCONNU ===
            else:
                logger.info(f"[{call_uuid[:8]}] ⚠️ Unknown/neutral intent → retry")
                session["autonomous_turns"] += 1
        
        # Fin boucle autonome - déterminer next step
        if session["intents"]:
            last_intent = session["intents"][-1]
        else:
            last_intent = "unknown"
        
        next_step = self.scenario_manager.get_next_step(scenario, step_name, last_intent)
        logger.info(f"[{call_uuid[:8]}] 🤖 Autonomous step completed → next: {next_step}")
        
        return next_step


    # ========================================================================
    # SECTION 8: UTILITY FUNCTIONS
    # ========================================================================

    def _play_step_audio(
        self,
        call_uuid: str,
        step_config: Dict[str, Any],
        variables: Dict[str, Any],
        scenario: Dict[str, Any]
    ):
        """
        Joue l'audio d'une étape (avec gestion chemins absolus/relatifs)
        
        Args:
            call_uuid: UUID appel
            step_config: Config de l'étape
            variables: Variables pour remplacement
            scenario: Scénario complet
        """
        audio_type = step_config.get("audio_type")
        
        if audio_type == "none":
            # Pas d'audio (step silencieux)
            return
        
        if audio_type != "audio":
            logger.error(f"[{call_uuid[:8]}] Unsupported audio_type: {audio_type} (only 'audio' supported)")
            return
        
        # Récupérer chemin audio
        audio_filename = step_config.get("audio_file")
        if not audio_filename:
            logger.warning(f"[{call_uuid[:8]}] No audio_file specified")
            return
        
        # Si chemin absolu → utiliser tel quel
        if audio_filename.startswith("/"):
            audio_file = audio_filename
        else:
            # Sinon construire chemin
            voice = scenario.get("metadata", {}).get("voice") or scenario.get("voice", config.DEFAULT_VOICE)
            audio_path = config.get_audio_path(voice, "base", audio_filename)
            audio_file = str(audio_path)
        
        # Jouer
        self._play_audio(call_uuid, audio_file)

    def _resolve_audio_path(self, call_uuid: str, audio_path: str, scenario: Dict[str, Any]) -> Optional[str]:
        """
        Résout le chemin audio complet (pour objections)
        
        Args:
            call_uuid: UUID appel
            audio_path: Chemin relatif
            scenario: Scénario
            
        Returns:
            Chemin absolu ou None
        """
        try:
            voice = scenario.get("metadata", {}).get("voice") or scenario.get("voice", config.DEFAULT_VOICE)
            full_path = config.get_audio_path(voice, "objections", audio_path)
            
            if full_path.exists():
                return str(full_path)
            else:
                logger.warning(f"[{call_uuid[:8]}] Audio file not found: {full_path}")
                return None
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Error resolving audio path: {e}")
            return None

    def _update_call_status(self, call_uuid: str, status: str):
        """
        Met à jour le statut de l'appel en DB
        
        Args:
            call_uuid: UUID appel
            status: Nouveau statut
        """
        try:
            db = SessionLocal()
            call = db.query(Call).filter(Call.uuid == call_uuid).first()
            
            if call:
                call.status = status
                call.ended_at = datetime.now()
                db.commit()
                logger.info(f"[{call_uuid[:8]}] Call status updated: {status}")
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Failed to update call status: {e}")
        finally:
            if db:
                db.close()

