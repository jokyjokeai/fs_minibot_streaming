"""
RobotFreeSWITCH V3 - MODE FICHIER + BARGE-IN VAD
=================================================

Version V3 avec mode fichier fiable et barge-in VAD:

Changements V3 (refonte complète):
- ✅ MODE FICHIER: Enregistrement + transcription (comme Asterisk)
- ✅ BARGE-IN VAD: Détection parole >= 2.5s SANS transcription
- ✅ Transcription avec GROS modèle Vosk (meilleure qualité)
- ❌ SUPPRIMÉ: Streaming temps réel (trop instable)
- ✅ Workflow simple: Enregistrer → Détecter VAD → Transcrire si besoin
- ✅ Fiable et rapide

Architecture simplifiée:
    1. ESL Connection Management (dual connections)
    2. Call Thread Management (one thread per call)
    3. Audio Playback System (uuid_broadcast)
    4. Audio Recording System (uuid_record) + VAD barge-in
    5. Speech Recognition (Vosk fichier - gros modèle)
    6. NLP Intent Analysis (Ollama)
    7. Scenario Execution Engine
    8. Autonomous Agent Mode (objections handler) ← CONSERVÉ

Author: MiniBotPanel Team
Version: 3.0.0
Date: 2025-11-10
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
# StreamingASR V3 SUPPRIMÉ - Mode fichier uniquement

# VAD pour barge-in (détection parole sans transcription)
try:
    import webrtcvad
    import wave
    import struct
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False

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
    - PLAYING_AUDIO + durée >= 2.5s + pas grace period = BARGE-IN
    - WAITING_RESPONSE = Toujours capturer (pas de barge-in)
    """

    DURATION_THRESHOLD = 2.5  # secondes (augmenté de 2.0s pour plus de naturel)

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

        # === CALL SESSIONS (ex-call_sessions) ===
        self.call_sessions = {}  # {call_uuid: session_data}

        # === V3: BARGE-IN DETECTOR ===
        self.barge_in_detector = BargeInDetector()
        logger.info(f"✅ V3 BargeInDetector initialized (threshold: {BargeInDetector.DURATION_THRESHOLD}s)")

        # === SERVICES INITIALIZATION ===
        logger.info("🤖 Loading AI services V3...")

        # 1. Vosk STT (mode fichier - gros modèle)
        try:
            self.stt_service = VoskSTT()
            logger.info("✅ Vosk STT loaded (file mode with large model)")
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

        # 4. VAD pour barge-in (détection parole sans transcription)
        if VAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad(2)  # Mode 2 (compromis réactivité/précision)
                logger.info("✅ WebRTC VAD loaded for barge-in detection")
            except Exception as e:
                logger.error(f"❌ Failed to initialize VAD: {e}")
                self.vad = None
        else:
            logger.warning("⚠️ WebRTC VAD not available - barge-in disabled")
            self.vad = None

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
        
        # Créer session d'appel
        self._init_call_session(call_uuid, phone_number, scenario)
        
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
        if call_uuid in self.call_sessions:
            self.call_sessions[call_uuid]["hangup_detected"] = True
            logger.debug(f"[{call_uuid[:8]}] Hangup flag set - threads will stop")

        # Cleanup
        self.active_calls.pop(call_uuid, None)
        self.call_threads.pop(call_uuid, None)
        self.call_sessions.pop(call_uuid, None)
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

    def _init_call_session(self, call_uuid: str, phone_number: str, scenario: str):
        """
        Initialise la session d'appel (mode fichier)

        Args:
            call_uuid: UUID de l'appel
            phone_number: Numéro appelé
            scenario: Nom du scénario
        """
        self.call_sessions[call_uuid] = {
            "phone_number": phone_number,
            "scenario": scenario,
            "current_step": None,
            "transcriptions": [],
            "intents": [],
            "consecutive_silences": 0,
            "consecutive_no_match": 0,
            "autonomous_turns": 0,
            "objection_matcher": None,
            "final_result": None,
            "started_at": datetime.now(),
            "barge_in_detected_time": 0,  # Timestamp détection barge-in (pour smooth delay)
            "recording_file": None,  # Fichier d'enregistrement en cours
            "hangup_detected": False  # Flag pour détecter hangup
        }

        logger.debug(f"[{call_uuid[:8]}] Call session initialized (file mode)")

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

            # === MODE FICHIER (pas de streaming) ===
            logger.info(f"[{call_uuid[:8]}] 📁 File mode enabled (record + transcribe)")

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
            session = self.call_sessions.get(call_uuid, {})
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
        Joue un fichier audio avec barge-in VAD

        NOUVEAU WORKFLOW (mode fichier + VAD):
        1. Lancer uuid_broadcast (robot parle)
        2. EN PARALLÈLE: uuid_record (enregistrer client)
        3. EN PARALLÈLE: Thread VAD (détecter parole >= 2.5s)
        4. Si barge-in détecté → uuid_break après smooth delay 1s
        5. Stopper recording, retourner False (interrupted)

        Args:
            call_uuid: UUID de l'appel
            audio_file: Chemin absolu vers fichier audio

        Returns:
            True si lecture complète, False si interrompu par barge-in
        """
        if not self.esl_conn_api or not self.esl_conn_api.connected():
            return False

        try:
            # Réinitialiser flag barge-in
            self.barge_in_active[call_uuid] = False

            # Calculer durée audio
            audio_duration = self._get_audio_duration(audio_file)

            # Marquer session
            if call_uuid in self.call_sessions:
                self.call_sessions[call_uuid]["barge_in_detected_time"] = 0

            logger.info(f"[{call_uuid[:8]}] 🎬 PLAYING_AUDIO (duration: {audio_duration:.1f}s, barge-in VAD if >= 2.5s)")

            # 1. Lancer uuid_broadcast (robot parle)
            cmd = f"uuid_broadcast {call_uuid} {audio_file} aleg"
            result = self.esl_conn_api.api(cmd)
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            if "+OK" not in result_str:
                logger.error(f"[{call_uuid[:8]}] Playback failed: {result_str}")
                return False

            logger.debug(f"[{call_uuid[:8]}] 🔊 Playing: {Path(audio_file).name} (duration: {audio_duration:.1f}s)")

            # Auto-tracking
            self.call_sequences[call_uuid].append({
                "type": "audio",
                "file": audio_file,
                "timestamp": datetime.now()
            })

            # 2. Lancer uuid_record EN PARALLÈLE (enregistrer client)
            record_file = config.RECORDINGS_DIR / f"bargein_{call_uuid}_{int(time.time())}.wav"
            record_cmd = f"uuid_record {call_uuid} start {record_file}"
            self.esl_conn_api.api(record_cmd)
            logger.debug(f"[{call_uuid[:8]}] 📝 Recording started for barge-in detection: {record_file.name}")

            # Sauvegarder dans session
            if call_uuid in self.call_sessions:
                self.call_sessions[call_uuid]["recording_file"] = str(record_file)

            # 3. Lancer thread VAD barge-in detection
            vad_thread = threading.Thread(
                target=self._monitor_barge_in_vad,
                args=(call_uuid, str(record_file), audio_duration),
                daemon=True
            )
            vad_thread.start()

            # 4. Surveiller si barge-in détecté
            max_duration = audio_duration + 1.0
            check_interval = 0.1
            elapsed = 0.0

            while elapsed < max_duration:
                # Vérifier hangup
                if call_uuid not in self.call_sessions or self.call_sessions[call_uuid].get("hangup_detected", False):
                    logger.warning(f"[{call_uuid[:8]}] 📞 Hangup - stopping playback & recording")
                    self.esl_conn_api.api(f"uuid_break {call_uuid}")
                    self.esl_conn_api.api(f"uuid_record {call_uuid} stop {record_file}")
                    return False

                # Vérifier si barge-in détecté par VAD
                session = self.call_sessions.get(call_uuid, {})
                barge_in_time = session.get("barge_in_detected_time", 0)

                if barge_in_time > 0:
                    # Barge-in détecté ! Vérifier smooth delay
                    time_since_detection = time.time() - barge_in_time

                    if time_since_detection >= config.BARGE_IN_SMOOTH_DELAY:
                        # Smooth delay écoulé → Couper audio
                        logger.info(f"[{call_uuid[:8]}] ⏹️ BARGE-IN! Interrupting audio (smooth delay {config.BARGE_IN_SMOOTH_DELAY}s)")

                        # Stopper audio
                        self.esl_conn_api.api(f"uuid_break {call_uuid}")

                        # Stopper recording
                        self.esl_conn_api.api(f"uuid_record {call_uuid} stop {record_file}")

                        # Reset flag
                        self.call_sessions[call_uuid]["barge_in_detected_time"] = 0
                        self.barge_in_active[call_uuid] = True

                        logger.info(f"[{call_uuid[:8]}] 🎧 Barge-in completed - recording saved")
                        return False

                time.sleep(check_interval)
                elapsed += check_interval

            # Audio terminé normalement - stopper recording
            logger.debug(f"[{call_uuid[:8]}] ✅ Audio completed - stopping recording")
            self.esl_conn_api.api(f"uuid_record {call_uuid} stop {record_file}")

            # Supprimer fichier (pas de barge-in)
            try:
                if record_file.exists():
                    record_file.unlink()
            except:
                pass

            return True
            
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Playback error: {e}")
            return False

        def _monitor_barge_in_vad(self, call_uuid: str, record_file: str, max_duration: float):
            """
            Thread VAD: Surveille fichier enregistrement et détecte parole >= 2.5s
    
            Workflow:
            1. Attendre que fichier existe et commence à s'écrire
            2. Lire fichier frame par frame (30ms) avec VAD
            3. Si parole détectée >= 2.5s → Marquer barge_in_detected_time
            4. Thread principal détectera le flag et coupera audio
    
            Args:
                call_uuid: UUID appel
                record_file: Chemin fichier .wav en cours d'écriture
                max_duration: Durée max à surveiller
            """
            if not self.vad:
                logger.warning(f"[{call_uuid[:8]}] VAD not available - barge-in disabled")
                return
    
            try:
                import wave
                import struct
    
                # Attendre que fichier existe (max 2s)
                wait_start = time.time()
                while not Path(record_file).exists():
                    if time.time() - wait_start > 2.0:
                        logger.warning(f"[{call_uuid[:8]}] Recording file not created - VAD aborted")
                        return
                    time.sleep(0.1)
    
                logger.debug(f"[{call_uuid[:8]}] VAD monitoring started on {Path(record_file).name}")
    
                # Config VAD
                sample_rate = 16000  # uuid_record en 16kHz
                frame_duration_ms = 30  # 30ms frames
                frame_size = int(sample_rate * frame_duration_ms / 1000)  # 480 samples
                bytes_per_frame = frame_size * 2  # 16-bit = 2 bytes
    
                # État VAD
                speech_frames = 0
                silence_frames = 0
                speech_start_time = None
                total_speech_duration = 0.0
    
                start_time = time.time()
    
                while time.time() - start_time < max_duration:
                    # Vérifier si hangup ou audio terminé
                    session = self.call_sessions.get(call_uuid)
                    if not session or session.get("hangup_detected", False):
                        logger.debug(f"[{call_uuid[:8]}] VAD: Hangup detected - stopping")
                        break
    
                    # Lire fichier WAV
                    try:
                        with wave.open(record_file, 'rb') as wav:
                            # Vérifier format
                            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                                logger.error(f"[{call_uuid[:8]}] VAD: Invalid WAV format")
                                break
    
                            # Lire toutes les frames disponibles
                            audio_data = wav.readframes(wav.getnframes())
    
                            # Traiter par frames de 30ms
                            offset = 0
                            while offset + bytes_per_frame <= len(audio_data):
                                frame = audio_data[offset:offset + bytes_per_frame]
                                offset += bytes_per_frame
    
                                # VAD sur cette frame
                                is_speech = self.vad.is_speech(frame, sample_rate)
    
                                if is_speech:
                                    speech_frames += 1
                                    silence_frames = 0
    
                                    if speech_start_time is None:
                                        speech_start_time = time.time()
    
                                    # Calculer durée parole
                                    if speech_start_time:
                                        total_speech_duration = time.time() - speech_start_time
    
                                        # BARGE-IN si >= 2.5s !
                                        if total_speech_duration >= config.BARGE_IN_DURATION_THRESHOLD:
                                            logger.info(f"[{call_uuid[:8]}] 🎙️ VAD: Speech detected >= {config.BARGE_IN_DURATION_THRESHOLD}s → BARGE-IN!")
    
                                            # Marquer timestamp barge-in
                                            if call_uuid in self.call_sessions:
                                                self.call_sessions[call_uuid]["barge_in_detected_time"] = time.time()
    
                                            return  # Thread terminé
    
                                else:
                                    # Silence
                                    silence_frames += 1
    
                                    # Reset si silence > 0.8s (800ms)
                                    if silence_frames > int(800 / frame_duration_ms):
                                        if speech_start_time and total_speech_duration > 0:
                                            logger.debug(f"[{call_uuid[:8]}] VAD: Speech ended ({total_speech_duration:.2f}s < threshold)")
    
                                        speech_frames = 0
                                        speech_start_time = None
                                        total_speech_duration = 0.0
    
                    except Exception as e:
                        # Fichier pas encore prêt ou en cours d'écriture
                        pass
    
                    time.sleep(0.05)  # Check toutes les 50ms
    
                logger.debug(f"[{call_uuid[:8]}] VAD monitoring ended (no barge-in)")
    
            except Exception as e:
                logger.error(f"[{call_uuid[:8]}] VAD error: {e}", exc_info=True)
    
    

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
        Écoute et transcrit la réponse du client (MODE FICHIER)

        Workflow:
        1. Enregistre audio client avec uuid_record
        2. Transcrit le fichier avec Vosk (gros modèle)
        3. Retourne la transcription

        Args:
            call_uuid: UUID de l'appel
            timeout: Timeout en secondes

        Returns:
            Transcription texte ou None si silence/timeout
        """
        if call_uuid not in self.call_sessions:
            logger.warning(f"[{call_uuid[:8]}] No call session")
            return None

        try:
            # Mode fichier uniquement
            logger.debug(f"[{call_uuid[:8]}] Using file mode for transcription")
            return self._listen_record_fallback(call_uuid, timeout)

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Listen error: {e}", exc_info=True)
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
        if call_uuid in self.call_sessions:
            self.call_sessions[call_uuid]["scenario_data"] = scenario
        
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
                        self.call_sessions[call_uuid]["objection_matcher"] = matcher
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
            if call_uuid in self.call_sessions:
                self.call_sessions[call_uuid]["current_step"] = current_step

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
                if call_uuid in self.call_sessions:
                    self.call_sessions[call_uuid]["final_result"] = result

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
        if call_uuid not in self.call_sessions:
            return None
        
        session = self.call_sessions[call_uuid]
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

