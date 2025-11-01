"""
Robot FreeSWITCH - MiniBotPanel v3

Cœur du système: Connexion ESL à FreeSWITCH et gestion des appels.
Adapté de robot_ari_hybrid.py pour FreeSWITCH.

Architecture:
- 1 thread principal pour connexion ESL
- 1 thread par appel actif (simple et efficace)
- Callbacks vers services IA (STT, NLP, TTS, AMD)
- Update stats temps réel en DB

Fonctionnalités:
- Originate calls (lancement appels sortants)
- Event handling (CHANNEL_ANSWER, CHANNEL_HANGUP, etc.)
- Call flow execution (scénarios)
- AMD integration (dual layer FreeSWITCH + Python)
- Recording management
- Streaming audio temps réel
- Barge-in (interruption)
- IA Freestyle

Utilisation:
    from system.robot_freeswitch import RobotFreeSWITCH

    robot = RobotFreeSWITCH()
    robot.start()  # Démarre connexion ESL

    # Lancer un appel
    call_uuid = robot.originate_call(
        phone_number="+33612345678",
        campaign_id=42,
        scenario="production"
    )
"""

import json
import logging
import threading
import time
import uuid as uuid_lib
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session
from system.models import Base, Call, Contact, Campaign
from system.database import SessionLocal, engine
from system.config import config
from system.logger import get_logger
from system.cache_manager import get_cache  # Phase 8

logger = get_logger(__name__)

# Import ObjectionMatcher pour Phase 6
try:
    from system.objection_matcher import ObjectionMatcher
    OBJECTION_MATCHER_AVAILABLE = True
except ImportError:
    OBJECTION_MATCHER_AVAILABLE = False
    logger.warning("⚠️ ObjectionMatcher not available")

# Import ESL - plusieurs méthodes possibles
try:
    # Méthode 1: Package python-ESL
    from ESL import ESLconnection
    ESL_AVAILABLE = True
    logger.info("✅ ESL module loaded (python-ESL)")
except ImportError:
    try:
        # Méthode 2: ESL.py de FreeSWITCH
        import sys
        sys.path.insert(0, '/usr/share/freeswitch/scripts')
        from ESL import ESLconnection
        ESL_AVAILABLE = True
        logger.info("✅ ESL module loaded (FreeSWITCH ESL.py)")
    except ImportError:
        ESL_AVAILABLE = False
        logger.error("❌ ESL module not available - install python-ESL or copy ESL.py from FreeSWITCH")
        # Mode dégradé pour tests
        class ESLconnection:
            def __init__(self, *args): pass
            def connected(self): return False
            def api(self, cmd): return "NOT_CONNECTED"
            def events(self, *args): pass
            def recvEvent(self): return None

class RobotFreeSWITCH:
    """
    Robot principal gérant les appels via FreeSWITCH ESL.

    Pattern: 1 thread par appel (simple, debuggable, scalable jusqu'à 50 calls)
    Adapté de RobotARIStreaming pour FreeSWITCH
    """

    def __init__(self):
        """Initialise le robot FreeSWITCH."""
        logger.info("Initializing RobotFreeSWITCH...")

        # Connexion ESL
        self.esl_conn = None
        self.running = False

        # État des appels (architecture identique à robot_ari_hybrid)
        self.active_calls: Dict[str, threading.Thread] = {}  # {uuid: thread}
        self.call_sequences: Dict[str, list] = {}  # {uuid: [audio_items]} - AUTO-TRACKING
        self.call_lock = threading.Lock()

        # État streaming
        self.streaming_sessions: Dict[str, dict] = {}  # {uuid: streaming_session_info}
        self.barge_in_active: Dict[str, bool] = {}  # {uuid: bool}

        # Background audio tracking
        self.background_audio_active: Dict[str, bool] = {}  # {uuid: bool}

        # Charger services IA
        logger.info("🤖 Loading AI services...")
        self._load_services()

        # Charger scénarios
        logger.info("📋 Loading scenarios...")
        self._load_scenarios()

        # Initialiser ScenarioManager pour scénarios JSON
        try:
            from system.scenarios import ScenarioManager
            self.scenario_manager = ScenarioManager()
            logger.info("✅ ScenarioManager initialized")
        except Exception as e:
            logger.warning(f"⚠️ ScenarioManager not available: {e}")
            self.scenario_manager = None

        logger.info("✅ RobotFreeSWITCH initialized")

    def _load_services(self):
        """Charge les services IA (STT, TTS, NLP, AMD)"""
        try:
            # Import conditionnel pour éviter erreurs si pas installés
            try:
                from system.services.vosk_stt import VoskSTT
                self.stt_service = VoskSTT()
                logger.info("✅ Vosk STT loaded")
            except Exception as e:
                logger.warning(f"⚠️ Vosk STT not available: {e}")
                self.stt_service = None

            try:
                from system.services.coqui_tts import CoquiTTS
                self.tts_service = CoquiTTS()
                logger.info("✅ Coqui TTS loaded")
            except Exception as e:
                logger.warning(f"⚠️ Coqui TTS not available: {e}")
                self.tts_service = None

            try:
                from system.services.ollama_nlp import OllamaNLP
                self.nlp_service = OllamaNLP()
                logger.info("✅ Ollama NLP loaded")
            except Exception as e:
                logger.warning(f"⚠️ Ollama NLP not available: {e}")
                self.nlp_service = None

            try:
                from system.services.amd_service import AMDService
                self.amd_service = AMDService()
                logger.info("✅ AMD Service loaded")
            except Exception as e:
                logger.warning(f"⚠️ AMD Service not available: {e}")
                self.amd_service = None

            # FreestyleAI pour génération réponses hors-script
            try:
                from system.services.freestyle_ai import FreestyleAI
                self.freestyle_service = FreestyleAI(
                    ollama_service=self.nlp_service,
                    tts_service=self.tts_service
                )
                logger.info("✅ FreestyleAI loaded")
            except Exception as e:
                logger.warning(f"⚠️ FreestyleAI not available: {e}")
                self.freestyle_service = None

            # StreamingASR pour transcription temps réel + barge-in
            try:
                from system.services.streaming_asr import streaming_asr
                self.streaming_asr = streaming_asr
                logger.info("✅ StreamingASR loaded")

                # Démarrer serveur streaming en background
                self._start_streaming_server()
            except Exception as e:
                logger.warning(f"⚠️ StreamingASR not available: {e}")
                self.streaming_asr = None

        except Exception as e:
            logger.error(f"❌ Failed to load services: {e}")

    def _start_streaming_server(self):
        """Démarre le serveur ASR streaming en background"""
        if not self.streaming_asr or not self.streaming_asr.is_available:
            logger.warning("⚠️ StreamingASR not available - skipping server start")
            return

        try:
            import asyncio

            def run_server():
                """Thread function pour serveur async"""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.streaming_asr.start_server())
                    loop.run_forever()
                except Exception as e:
                    logger.error(f"❌ Streaming server error: {e}")
                finally:
                    loop.close()

            # Lancer dans thread daemon
            streaming_thread = threading.Thread(
                target=run_server,
                daemon=True,
                name="StreamingASR-Server"
            )
            streaming_thread.start()

            # Attendre un peu pour que le serveur démarre
            time.sleep(0.5)

            logger.info("✅ StreamingASR server started in background (port 8080)")

        except Exception as e:
            logger.error(f"❌ Failed to start streaming server: {e}")

    def _load_scenarios(self):
        """Charge les scénarios depuis scenarios.py"""
        try:
            from system.scenarios import ScenarioManager
            self.scenario_manager = ScenarioManager()
            logger.info(f"✅ ScenarioManager loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load scenarios: {e}")
            self.scenario_manager = None

    def connect(self):
        """Établit la connexion ESL avec FreeSWITCH"""
        logger.info("📡 Connecting to FreeSWITCH ESL...")

        if not ESL_AVAILABLE:
            logger.error("❌ ESL module not available - cannot connect")
            return False

        try:
            # Connexion ESL (équivalent de WebSocket ARI)
            self.esl_conn = ESLconnection(
                config.FREESWITCH_HOST,
                str(config.FREESWITCH_ESL_PORT),
                config.FREESWITCH_ESL_PASSWORD
            )

            if self.esl_conn.connected():
                logger.info("✅ Connected to FreeSWITCH ESL")

                # S'abonner aux événements (équivalent de ws.on_message)
                self.esl_conn.events("plain", "CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP CHANNEL_DESTROY")

                return True
            else:
                logger.error("❌ Failed to connect to FreeSWITCH ESL")
                return False

        except Exception as e:
            logger.error(f"❌ ESL connection error: {e}", exc_info=True)
            return False

    def start(self):
        """
        Démarre le robot (connexion ESL et écoute événements).

        Bloquant: ne retourne que si arrêt ou erreur.
        """
        logger.info("Starting RobotFreeSWITCH...")

        # Connexion ESL
        if not self.connect():
            logger.error("❌ Cannot start without ESL connection")
            return

        self.running = True
        logger.info("✅ RobotFreeSWITCH started and listening for events")
        logger.info("👂 Waiting for calls...")

        # Boucle événements (équivalent de ws.run_forever)
        try:
            while self.running:
                # Recevoir événement (bloquant avec timeout)
                event = self.esl_conn.recvEvent()

                if event:
                    self.handle_event(event)

        except KeyboardInterrupt:
            logger.info("⚠️ Interrupted by user")
        except Exception as e:
            logger.error(f"❌ Event loop error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Arrête le robot proprement."""
        logger.info("Stopping RobotFreeSWITCH...")

        self.running = False

        # Attendre fin threads actifs
        with self.call_lock:
            active_count = len(self.active_calls)
            if active_count > 0:
                logger.info(f"⏳ Waiting for {active_count} active calls to finish...")

        # Fermer connexion ESL
        if self.esl_conn and self.esl_conn.connected():
            # Note: ESL n'a pas de méthode disconnect() explicite
            self.esl_conn = None

        logger.info("✅ RobotFreeSWITCH stopped")

    def handle_event(self, event):
        """
        Traite les événements ESL (équivalent de on_message pour ARI)

        Args:
            event: ESL Event object
        """
        try:
            event_name = event.getHeader("Event-Name")
            call_uuid = event.getHeader("Unique-ID")

            if event_name == "CHANNEL_CREATE":
                logger.debug(f"📨 CHANNEL_CREATE: {call_uuid}")
                # Pas d'action, on attend CHANNEL_ANSWER

            elif event_name == "CHANNEL_ANSWER":
                logger.info(f"📞 Call answered: {call_uuid}")
                self.handle_channel_answer(event)

            elif event_name == "CHANNEL_HANGUP":
                hangup_cause = event.getHeader("Hangup-Cause")
                logger.info(f"📞 Call ended: {call_uuid} - {hangup_cause}")
                self.handle_channel_hangup(event)

            elif event_name == "CHANNEL_DESTROY":
                logger.debug(f"📨 CHANNEL_DESTROY: {call_uuid}")
                # Cleanup final

        except Exception as e:
            logger.error(f"❌ Error handling event: {e}", exc_info=True)

    def handle_channel_answer(self, event):
        """Traite l'événement CHANNEL_ANSWER (équivalent StasisStart)"""
        try:
            call_uuid = event.getHeader("Unique-ID")
            destination = event.getHeader("Caller-Destination-Number")

            # Extraire les variables custom (campaign_id, scenario, etc.)
            campaign_id = event.getHeader("variable_campaign_id") or "default"
            scenario = event.getHeader("variable_scenario") or "production"

            logger.info(f"📞 New call: {destination} | UUID: {call_uuid} | Scenario: {scenario}")

            # Lancer thread de traitement (architecture identique à robot_ari_hybrid)
            call_thread = threading.Thread(
                target=self._handle_call,
                args=(call_uuid, destination, scenario, campaign_id),
                daemon=True,
                name=f"Call-{call_uuid[:8]}"
            )

            with self.call_lock:
                self.active_calls[call_uuid] = call_thread
                self.call_sequences[call_uuid] = []  # AUTO-TRACKING

            call_thread.start()

        except Exception as e:
            logger.error(f"❌ Error in CHANNEL_ANSWER: {e}", exc_info=True)

    def handle_channel_hangup(self, event):
        """Traite l'événement CHANNEL_HANGUP (équivalent StasisEnd)"""
        try:
            call_uuid = event.getHeader("Unique-ID")

            with self.call_lock:
                # Nettoyer ressources
                if call_uuid in self.active_calls:
                    del self.active_calls[call_uuid]

                # Post-process
                if call_uuid in self.call_sequences:
                    self._post_process_call(call_uuid)
                    del self.call_sequences[call_uuid]

                # Nettoyer streaming callbacks
                if self.streaming_asr and call_uuid in self.streaming_sessions:
                    self.streaming_asr.unregister_callback(call_uuid)
                    logger.debug(f"[{call_uuid[:8]}] Streaming callback unregistered")

                # Nettoyer streaming sessions
                if call_uuid in self.streaming_sessions:
                    del self.streaming_sessions[call_uuid]
                if call_uuid in self.barge_in_active:
                    del self.barge_in_active[call_uuid]

        except Exception as e:
            logger.error(f"❌ Error in CHANNEL_HANGUP: {e}", exc_info=True)

    def originate_call(
        self,
        phone_number: str,
        campaign_id: int,
        scenario: str = "production",
        uuid: Optional[str] = None,
        contact_id: Optional[int] = None,
        caller_id: Optional[str] = None,
        retry_count: int = 0,
        variables: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Lance un appel sortant (équivalent de POST /channels en ARI)

        Args:
            phone_number: Numéro à appeler (format E.164)
            campaign_id: ID campagne
            scenario: Nom du scénario à exécuter
            uuid: UUID personnalisé pour l'appel (optionnel)
            contact_id: ID du contact (optionnel)
            caller_id: Numéro appelant (optionnel)
            retry_count: Compteur de retry (optionnel)
            variables: Variables supplémentaires pour le dialplan

        Returns:
            UUID de l'appel FreeSWITCH ou None si échec
        """
        logger.info(f"Originating call to {phone_number} (campaign {campaign_id}, scenario {scenario}, retry {retry_count})")

        if not self.esl_conn or not self.esl_conn.connected():
            logger.error("❌ ESL not connected")
            return None

        try:
            # Construire variables pour le dialplan
            vars_dict = {
                "campaign_id": campaign_id,
                "scenario": scenario,
                "retry_count": retry_count
            }

            if contact_id:
                vars_dict["contact_id"] = contact_id

            if variables:
                vars_dict.update(variables)

            # Construire string de variables
            vars_str = ",".join([f"{k}={v}" for k, v in vars_dict.items()])

            # Caller ID
            if caller_id:
                vars_str += f",origination_caller_id_number={caller_id}"

            # UUID personnalisé
            if uuid:
                vars_str += f",origination_uuid={uuid}"

            # Construire dial string avec variables
            # Format: {var1=val1,var2=val2}sofia/gateway/gateway1/+33123456789
            dial_string = (
                f"{{{vars_str}}}"
                f"sofia/gateway/{config.FREESWITCH_GATEWAY}/{phone_number}"
            )

            # Commande originate (équivalent POST /channels)
            # originate <dial_string> &park() - park() pour garder le canal ouvert
            cmd = f"originate {dial_string} &park()"

            result = self.esl_conn.api(cmd)
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            # Extraire UUID de la réponse (+OK uuid)
            if "+OK" in result_str:
                call_uuid = uuid or (result_str.split()[1] if len(result_str.split()) > 1 else None)

                if call_uuid:
                    logger.info(f"✅ Call originated: {call_uuid}")

                    # Créer enregistrement Call en DB si pas déjà fait
                    if not uuid:
                        self._create_call_record(call_uuid, phone_number, campaign_id, scenario)

                    return call_uuid

            logger.error(f"❌ Originate failed: {result_str}")
            return None

        except Exception as e:
            logger.error(f"❌ Error originating call: {e}", exc_info=True)
            return None

    def _handle_call(self, call_uuid: str, phone_number: str, scenario: str, campaign_id: str):
        """
        Thread principal d'un appel (exécute le scénario).
        Adapté de _handle_call_streaming de robot_ari_hybrid

        Args:
            call_uuid: UUID FreeSWITCH
            phone_number: Numéro appelé
            scenario: Scénario à exécuter
            campaign_id: ID campagne
        """
        logger.info(f"[{call_uuid[:8]}] 🌊 Call thread started for {phone_number}")

        try:
            # Initialiser session streaming
            self._init_streaming_session(call_uuid, phone_number)

            # AMD (Answering Machine Detection) si activé
            if config.AMD_ENABLED and self.amd_service:
                try:
                    # FreeSWITCH peut faire AMD en premier
                    # Pour l'instant on assume HUMAN
                    amd_result = "HUMAN"
                    logger.info(f"[{call_uuid[:8]}] AMD: {amd_result}")

                    if amd_result == "MACHINE":
                        logger.info(f"[{call_uuid[:8]}] Machine detected - hanging up")
                        self.hangup_call(call_uuid)
                        return

                except Exception as e:
                    logger.warning(f"[{call_uuid[:8]}] AMD error: {e}")

            # Démarrer background audio loop (bruit de fond)
            # Note: Le fichier peut être configuré par scénario ou via audio/background/default.wav
            self._start_background_audio(call_uuid)

            # Exécuter scénario
            if scenario in self.scenarios:
                self._execute_scenario(call_uuid, scenario, campaign_id)
            else:
                logger.error(f"[{call_uuid[:8]}] Scenario '{scenario}' not found")
                self.hangup_call(call_uuid)

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Call thread error: {e}", exc_info=True)
        finally:
            # Arrêter background audio avant hangup
            self._stop_background_audio(call_uuid)

            logger.info(f"[{call_uuid[:8]}] Call thread ended")
            # Cleanup fait dans handle_channel_hangup

    def _init_streaming_session(self, call_uuid: str, phone_number: str):
        """Initialise session streaming pour un appel"""
        self.streaming_sessions[call_uuid] = {
            "phone_number": phone_number,
            "started_at": datetime.now(),
            "current_step": "INIT",
            "transcriptions": [],
            "intents": [],
            "last_transcription": None,  # Pour _listen_for_response
            "is_speaking": False,  # Pour barge-in
            "consecutive_silences": 0,  # Phase 6: tracking 2 silences consécutifs
            "autonomous_turns": 0,  # Phase 6: compteur turns dans step
            "objection_matcher": None  # Phase 6: matcher chargé par thématique
        }
        self.barge_in_active[call_uuid] = False

        # Enregistrer callback streaming si disponible
        if self.streaming_asr and self.streaming_asr.is_available:
            self.streaming_asr.register_callback(call_uuid, self._handle_streaming_event)
            logger.debug(f"[{call_uuid[:8]}] Streaming callback registered")

            # Activer audio fork vers WebSocket
            self._enable_audio_fork(call_uuid)

    def _start_background_audio(self, call_uuid: str, background_audio_path: Optional[str] = None):
        """
        Démarre la lecture en boucle d'un fichier audio de fond pendant l'appel.

        Utilise uuid_displace avec:
        - limit=0 pour boucle infinie
        - mux pour mixer avec l'audio principal

        Args:
            call_uuid: UUID de l'appel
            background_audio_path: Chemin vers le fichier audio de fond (optionnel)
                                   Si None, cherche dans audio/background/default.wav
        """
        if not self.esl_conn or not self.esl_conn.connected():
            logger.warning(f"[{call_uuid[:8]}] Cannot start background audio: ESL not connected")
            return

        try:
            # Déterminer le fichier background
            if background_audio_path is None:
                # Par défaut: audio/background/default.wav
                background_audio_path = str(config.AUDIO_FILES_PATH / "background" / "default.wav")

            # Vérifier que le fichier existe
            from pathlib import Path
            if not Path(background_audio_path).exists():
                logger.warning(f"[{call_uuid[:8]}] Background audio file not found: {background_audio_path}")
                return

            # Commande uuid_displace avec loop infini (limit=0) et mixage (mux)
            # Syntaxe: uuid_displace <uuid> start <file> <limit> [mux]
            cmd = f"uuid_displace {call_uuid} start {background_audio_path} 0 mux"
            result = self.esl_conn.api(cmd)

            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            if "+OK" in result_str or "success" in result_str.lower():
                self.background_audio_active[call_uuid] = True
                logger.info(f"[{call_uuid[:8]}] ✅ Background audio started (loop): {Path(background_audio_path).name}")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ Background audio failed: {result_str}")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Error starting background audio: {e}", exc_info=True)

    def _stop_background_audio(self, call_uuid: str):
        """
        Arrête la lecture du fichier audio de fond.

        Args:
            call_uuid: UUID de l'appel
        """
        if not self.esl_conn or not self.esl_conn.connected():
            return

        # Vérifier si background audio était actif
        if not self.background_audio_active.get(call_uuid, False):
            return

        try:
            # Commande uuid_displace stop
            cmd = f"uuid_displace {call_uuid} stop"
            result = self.esl_conn.api(cmd)

            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            if "+OK" in result_str or "success" in result_str.lower():
                self.background_audio_active[call_uuid] = False
                logger.info(f"[{call_uuid[:8]}] ✅ Background audio stopped")
            else:
                logger.debug(f"[{call_uuid[:8]}] Background audio stop result: {result_str}")
                # Nettoyer quand même le flag
                self.background_audio_active[call_uuid] = False

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Error stopping background audio: {e}")
            # Cleanup flag
            self.background_audio_active.pop(call_uuid, None)

    def _enable_audio_fork(self, call_uuid: str):
        """Active le streaming audio vers le serveur WebSocket"""
        if not self.esl_conn:
            return

        try:
            # Forker l'audio vers WebSocket (mod_audio_fork ou uuid_audio_fork)
            websocket_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"

            # Commande FreeSWITCH pour forker audio
            # Note: Nécessite mod_audio_fork compilé dans FreeSWITCH
            cmd = f"uuid_audio_fork {call_uuid} start {websocket_url}"
            result = self.esl_conn.api(cmd)

            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            if "+OK" in result_str or "success" in result_str.lower():
                logger.info(f"[{call_uuid[:8]}] ✅ Audio fork enabled → WebSocket")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ Audio fork failed: {result_str}")
                logger.warning(f"[{call_uuid[:8]}] Falling back to non-streaming mode")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Audio fork error: {e}")

    def _handle_streaming_event(self, event_data: Dict[str, Any]):
        """
        Callback pour événements du streaming ASR.
        Appelé par StreamingASR pour speech_start, speech_end, transcription.
        """
        try:
            event_type = event_data.get("event")
            call_uuid = event_data.get("call_uuid")

            if not call_uuid or call_uuid not in self.streaming_sessions:
                return

            if event_type == "speech_start":
                # BARGE-IN: Client commence à parler
                logger.info(f"[{call_uuid[:8]}] 🗣️ BARGE-IN detected!")

                self.barge_in_active[call_uuid] = True
                self.streaming_sessions[call_uuid]["is_speaking"] = True

                # Arrêter l'audio en cours
                self._stop_audio(call_uuid)

            elif event_type == "speech_end":
                # Fin de parole (silence détecté)
                silence_duration = event_data.get("silence_duration", 0)
                logger.info(f"[{call_uuid[:8]}] 🤐 Speech ended (silence: {silence_duration:.1f}s)")

                self.streaming_sessions[call_uuid]["is_speaking"] = False

            elif event_type == "transcription":
                # Transcription disponible
                text = event_data.get("text", "")
                trans_type = event_data.get("type", "partial")  # "final" ou "partial"
                latency_ms = event_data.get("latency_ms", 0)

                if trans_type == "final":
                    logger.info(f"[{call_uuid[:8]}] 📝 Transcription: '{text}' ({latency_ms:.0f}ms)")

                    # Sauvegarder pour _listen_for_response
                    self.streaming_sessions[call_uuid]["last_transcription"] = text
                    self.streaming_sessions[call_uuid]["transcriptions"].append(text)

                    # Détecter questions pour IA Freestyle
                    if self.nlp_service:
                        intent_result = self.nlp_service.analyze_intent(text, context="general")
                        intent = intent_result.get("intent", "unknown")

                        if intent == "question":
                            logger.info(f"[{call_uuid[:8]}] ❓ Question detected → IA Freestyle mode")
                            # Générer réponse IA Freestyle
                            self._handle_freestyle_question(call_uuid, text)

                else:
                    # Partial transcription (debug seulement)
                    logger.debug(f"[{call_uuid[:8]}] 📝 PARTIAL: '{text}'")

        except Exception as e:
            logger.error(f"Streaming event handler error: {e}", exc_info=True)

    def _stop_audio(self, call_uuid: str):
        """Arrête l'audio en cours (pour barge-in)"""
        if not self.esl_conn:
            return

        try:
            # uuid_break arrête le playback en cours
            cmd = f"uuid_break {call_uuid}"
            self.esl_conn.api(cmd)

            logger.debug(f"[{call_uuid[:8]}] ⏹️ Audio stopped (barge-in)")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Stop audio error: {e}")

    def _handle_freestyle_question(self, call_uuid: str, question: str):
        """
        Gère une question hors-script avec IA Freestyle (Ollama).

        Utilise le service FreestyleAI centralisé pour:
        - Historique conversationnel (5 derniers échanges)
        - Prompt engineering pour réponses courtes (~150 mots max)
        - Cache des réponses fréquentes (LRU)
        - Détection automatique du type de question (objection, prix, info)
        - Génération TTS + playback

        Args:
            call_uuid: UUID de l'appel
            question: Question du client
        """
        if not self.freestyle_service or not self.freestyle_service.is_available:
            logger.warning(f"[{call_uuid[:8]}] IA Freestyle not available")
            # Fallback simple
            self._play_fallback_freestyle(call_uuid)
            return

        try:
            logger.info(f"[{call_uuid[:8]}] 🤖 IA Freestyle: '{question}'")

            # 1. Construire contexte campagne depuis session
            context = self._build_freestyle_context(call_uuid)

            # 2. Détecter automatiquement le type de prompt optimal
            prompt_type = self.freestyle_service.detect_prompt_type(question)
            logger.debug(f"[{call_uuid[:8]}] Prompt type detected: {prompt_type}")

            # 3. Générer réponse avec FreestyleAI (gère cache, historique, validation)
            ai_response = self.freestyle_service.generate_response(
                call_uuid=call_uuid,
                user_input=question,
                context=context,
                prompt_type=prompt_type
            )

            if not ai_response:
                logger.warning(f"[{call_uuid[:8]}] Empty AI response")
                self._play_fallback_freestyle(call_uuid)
                return

            logger.info(f"[{call_uuid[:8]}] 🤖 AI Response: '{ai_response[:80]}...'")

            # 4. Générer audio TTS
            audio_file = self.tts_service.synthesize(ai_response)

            if not audio_file:
                logger.error(f"[{call_uuid[:8]}] TTS generation failed")
                return

            # 5. Jouer réponse au client
            success = self._play_audio(call_uuid, audio_file)

            if success:
                logger.info(f"[{call_uuid[:8]}] ✅ IA Freestyle response played successfully")

                # Sauvegarder dans transcriptions pour contexte futur
                if call_uuid in self.streaming_sessions:
                    self.streaming_sessions[call_uuid]["transcriptions"].append(ai_response)
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ IA Freestyle playback interrupted")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] ❌ IA Freestyle error: {e}", exc_info=True)
            self._play_fallback_freestyle(call_uuid)

    def _handle_freestyle_with_rail_return(self, call_uuid: str, question: str, intent: str):
        """
        Gère une question hors-script avec IA Freestyle + question de retour au rail (Phase 6+).

        Cette méthode génère une réponse en 2 parties:
        1. Réponse à l'objection/question (2-3s generation)
        2. Question fermée variée pour retour au rail (oui/non)

        Args:
            call_uuid: UUID de l'appel
            question: Question du client
            intent: Intent détecté (objection, question, concern, etc.)
        """
        if not self.freestyle_service or not self.freestyle_service.is_available:
            logger.warning(f"[{call_uuid[:8]}] IA Freestyle not available")
            self._play_fallback_freestyle(call_uuid)
            return

        try:
            logger.info(f"[{call_uuid[:8]}] 🤖 IA Freestyle with rail return: '{question}'")

            # 1. Construire contexte campagne
            context = self._build_freestyle_context(call_uuid)

            # 2. Détecter type de prompt optimal
            prompt_type = self.freestyle_service.detect_prompt_type(question)
            logger.debug(f"[{call_uuid[:8]}] Prompt type: {prompt_type}")

            # 3. Générer réponse AVEC question de retour au rail
            ai_response = self.freestyle_service.generate_response_with_rail_return(
                call_uuid=call_uuid,
                user_input=question,
                context=context,
                prompt_type=prompt_type
            )

            if not ai_response:
                logger.warning(f"[{call_uuid[:8]}] Empty AI response")
                self._play_fallback_freestyle(call_uuid)
                return

            logger.info(f"[{call_uuid[:8]}] 🤖 AI Response (with rail return): '{ai_response[:80]}...'")

            # 4. Générer audio TTS
            audio_file = self.tts_service.synthesize(ai_response) if self.tts_service else None

            if not audio_file:
                logger.error(f"[{call_uuid[:8]}] TTS generation failed")
                return

            # 5. Jouer réponse au client
            success = self._play_audio(call_uuid, audio_file)

            if success:
                logger.info(f"[{call_uuid[:8]}] ✅ IA Freestyle + rail return played successfully")

                # Sauvegarder dans transcriptions pour contexte futur
                if call_uuid in self.streaming_sessions:
                    self.streaming_sessions[call_uuid]["transcriptions"].append(ai_response)
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ IA Freestyle playback interrupted")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] ❌ IA Freestyle with rail return error: {e}", exc_info=True)
            self._play_fallback_freestyle(call_uuid)

    def _build_freestyle_context(self, call_uuid: str) -> Dict[str, Any]:
        """
        Construit le contexte campagne pour génération freestyle.

        Args:
            call_uuid: UUID de l'appel

        Returns:
            Dict avec contexte (agent_name, company, product, etc.)
        """
        context = {
            "agent_name": "Julie",
            "company": "notre entreprise",
            "product": "nos solutions",
            "campaign_context": "Appel de prospection commercial"
        }

        # Enrichir avec infos session si disponibles
        if call_uuid in self.streaming_sessions:
            session = self.streaming_sessions[call_uuid]
            # TODO: Récupérer infos campagne depuis DB si campaign_id disponible
            # Pour l'instant contexte générique

        return context

    def _play_fallback_freestyle(self, call_uuid: str):
        """
        Joue une réponse fallback générique en cas d'erreur freestyle.

        Args:
            call_uuid: UUID de l'appel
        """
        fallback_response = "Je n'ai pas toutes les informations pour répondre précisément. Puis-je vous proposer un rendez-vous avec un expert qui pourra vous renseigner en détail?"

        try:
            audio_file = self.tts_service.synthesize(fallback_response)
            if audio_file:
                self._play_audio(call_uuid, audio_file)
        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Fallback response failed: {e}")

    def _execute_scenario(self, call_uuid: str, scenario_name: str, campaign_id: str):
        """
        Exécute un scénario conversationnel.

        Args:
            call_uuid: UUID de l'appel
            scenario_name: Nom du scénario
            campaign_id: ID campagne
        """
        logger.info(f"[{call_uuid[:8]}] Executing scenario: {scenario_name}")

        scenario = self.scenarios.get(scenario_name)
        if not scenario:
            logger.error(f"[{call_uuid[:8]}] Scenario not found")
            return

        # Commencer à la première étape
        current_step = scenario.get("start_step", "HELLO")

        # Loop sur les étapes
        max_iterations = 50  # Sécurité contre boucles infinies
        iteration = 0

        while current_step and iteration < max_iterations:
            iteration += 1

            # Récupérer config étape
            step_config = scenario.get("steps", {}).get(current_step)
            if not step_config:
                logger.error(f"[{call_uuid[:8]}] Step '{current_step}' not found")
                break

            logger.info(f"[{call_uuid[:8]}] Step: {current_step}")
            self.streaming_sessions[call_uuid]["current_step"] = current_step

            # 1. Jouer audio
            audio_file = step_config.get("audio")
            if audio_file:
                audio_path = Path(config.AUDIO_FILES_PATH) / audio_file
                if not self._play_audio(call_uuid, str(audio_path)):
                    logger.error(f"[{call_uuid[:8]}] Failed to play audio")
                    break

            # 2. Écouter réponse si attendue
            if step_config.get("expect_response", True):
                timeout = step_config.get("timeout", 10)
                transcription = self._listen_for_response(call_uuid, timeout)

                # 3. Analyser intent
                if transcription and self.nlp_service:
                    intent = self._analyze_intent(transcription, step_config)
                    logger.info(f"[{call_uuid[:8]}] Intent: {intent}")

                    # Sauvegarder
                    self.streaming_sessions[call_uuid]["transcriptions"].append(transcription)
                    self.streaming_sessions[call_uuid]["intents"].append(intent)

                    # 4. Brancher vers étape suivante
                    next_step = step_config.get("next", {}).get(intent)
                    if not next_step:
                        next_step = step_config.get("next", {}).get("default")

                    current_step = next_step
                else:
                    # Pas de réponse ou pas de NLP
                    current_step = step_config.get("next", {}).get("silence")
            else:
                # Pas de réponse attendue, next direct
                current_step = step_config.get("next")

            # Si étape terminale, sortir
            if current_step in ["BYE_SUCCESS", "BYE_FAILED", None]:
                logger.info(f"[{call_uuid[:8]}] Scenario ended at: {current_step}")
                break

        # Fin du scénario
        self.hangup_call(call_uuid)

    def _execute_autonomous_step(
        self,
        call_uuid: str,
        scenario: Dict[str, Any],
        step_name: str,
        variables: Dict[str, Any]
    ) -> Optional[str]:
        """
        Exécute une étape en mode agent autonome (Phase 6+).

        Logique:
        1. Jouer message principal (audio/TTS)
        2. Écouter réponse (avec barge-in support)
        3. Si objection/question détectée:
           a. Matcher objection (50ms) → jouer audio pré-enregistré si match
           b. Sinon freestyle fallback (2-3s) → générer réponse IA
           c. Retour au rail avec question fermée variée
        4. Max autonomous_turns=2 par étape (configurable)
        5. Gestion 2 silences consécutifs → hangup + NO_ANSWER

        Args:
            call_uuid: UUID de l'appel
            scenario: Scénario complet (dict)
            step_name: Nom de l'étape courante
            variables: Variables pour remplacement

        Returns:
            Nom de la prochaine étape ou None si terminé
        """
        if call_uuid not in self.streaming_sessions:
            logger.error(f"[{call_uuid[:8]}] No streaming session for autonomous step")
            return None

        session = self.streaming_sessions[call_uuid]

        # Récupérer config étape
        step_config = self.scenario_manager.get_step_config(scenario, step_name) if self.scenario_manager else {}
        if not step_config:
            logger.error(f"[{call_uuid[:8]}] Step '{step_name}' not found")
            return None

        # Max autonomous turns pour cette étape
        max_turns = self.scenario_manager.get_max_autonomous_turns(scenario, step_name) if self.scenario_manager else 2

        logger.info(f"[{call_uuid[:8]}] 🤖 Autonomous step: {step_name} (max_turns={max_turns})")

        # Réinitialiser compteur turns pour cette étape
        session["autonomous_turns"] = 0

        # Boucle autonome (max_turns)
        while session["autonomous_turns"] < max_turns:
            turn_num = session["autonomous_turns"] + 1
            logger.info(f"[{call_uuid[:8]}]   └─ Turn {turn_num}/{max_turns}")

            # 1. Jouer message principal (première fois seulement)
            if session["autonomous_turns"] == 0:
                self._handle_normal_step(call_uuid, step_config, variables)

            # 2. Écouter réponse client
            timeout = step_config.get("timeout", 10)
            transcription = self._listen_for_response(call_uuid, timeout)

            # Gestion silence
            if not transcription or not transcription.strip():
                logger.warning(f"[{call_uuid[:8]}]   └─ Silence détecté ({session['consecutive_silences'] + 1}/2)")
                session["consecutive_silences"] += 1

                # 2 silences consécutifs = hangup
                if session["consecutive_silences"] >= 2:
                    logger.warning(f"[{call_uuid[:8]}] ❌ 2 silences consécutifs → hangup NO_ANSWER")
                    # Mettre à jour DB avec status NO_ANSWER
                    self._update_call_status(call_uuid, "NO_ANSWER")
                    return None  # Terminera le scénario

                # Premier silence: retry message
                session["autonomous_turns"] += 1
                continue

            # Réinitialiser compteur silences (client a parlé)
            session["consecutive_silences"] = 0

            # 3. Analyser intent avec NLP
            if not self.nlp_service:
                logger.warning(f"[{call_uuid[:8]}] NLP service not available")
                break

            intent_result = self.nlp_service.analyze_intent(transcription, context="telemarketing")
            intent = intent_result.get("intent", "unknown")

            logger.info(f"[{call_uuid[:8]}]   └─ Intent: {intent}")

            # Sauvegarder transcription
            session["transcriptions"].append(transcription)
            session["intents"].append(intent)

            # 4. Vérifier si c'est une objection/question
            if intent in ["objection", "question", "concern", "unsure"]:
                logger.info(f"[{call_uuid[:8]}] 🎯 Objection/Question détectée → Matching...")

                # a. Matcher objection (50ms rapide)
                matcher = session.get("objection_matcher")
                match = None

                if matcher and OBJECTION_MATCHER_AVAILABLE:
                    import time
                    match_start = time.time()
                    match = matcher.find_best_match(transcription, min_score=0.6)
                    match_latency_ms = (time.time() - match_start) * 1000

                    if match:
                        logger.info(f"[{call_uuid[:8]}]   ✅ Match trouvé ({match_latency_ms:.0f}ms): {match['objection'][:50]}...")

                        # Jouer audio pré-enregistré si disponible
                        if match.get("audio_path"):
                            audio_path = self._resolve_audio_path(call_uuid, match["audio_path"], scenario)
                            if audio_path:
                                logger.info(f"[{call_uuid[:8]}]   🔊 Playing pre-recorded answer (50ms path)")
                                self._play_audio(call_uuid, audio_path)
                            else:
                                # Fallback TTS avec réponse texte
                                logger.info(f"[{call_uuid[:8]}]   🔊 Audio not found, TTS fallback")
                                audio_file = self.tts_service.synthesize(match["response"]) if self.tts_service else None
                                if audio_file:
                                    self._play_audio(call_uuid, audio_file)
                        else:
                            # TTS avec réponse texte
                            logger.info(f"[{call_uuid[:8]}]   🔊 TTS answer (no pre-recorded audio)")
                            audio_file = self.tts_service.synthesize(match["response"]) if self.tts_service else None
                            if audio_file:
                                self._play_audio(call_uuid, audio_file)

                        # Sauvegarder réponse dans historique
                        session["transcriptions"].append(match["response"])

                    else:
                        logger.info(f"[{call_uuid[:8]}]   ❌ No match ({match_latency_ms:.0f}ms) → Freestyle fallback")

                # b. Si pas de match: Freestyle fallback (2-3s)
                if not match:
                    logger.info(f"[{call_uuid[:8]}] 🤖 Generating freestyle answer...")
                    self._handle_freestyle_with_rail_return(call_uuid, transcription, intent)

                # c. Retour au rail avec question fermée (intégré dans freestyle)
                logger.info(f"[{call_uuid[:8]}]   └─ Rail return question asked")

                # Incrémenter compteur turns
                session["autonomous_turns"] += 1

            elif intent in ["affirm", "positive", "interested"]:
                # Réponse positive → continuer au rail suivant
                logger.info(f"[{call_uuid[:8]}] ✅ Positive response → next rail step")
                break

            elif intent in ["deny", "negative", "not_interested"]:
                # Réponse négative → gérer selon scénario
                logger.info(f"[{call_uuid[:8]}] ❌ Negative response")
                break

            else:
                # Intent inconnu ou neutre
                logger.info(f"[{call_uuid[:8]}] ⚠️ Unknown/neutral intent → retry")
                session["autonomous_turns"] += 1

        # Fin de la boucle autonome
        # Déterminer prochaine étape selon dernier intent
        if session["intents"]:
            last_intent = session["intents"][-1]
        else:
            last_intent = "unknown"

        next_step = self.scenario_manager.get_next_step(scenario, step_name, last_intent) if self.scenario_manager else None

        logger.info(f"[{call_uuid[:8]}] 🤖 Autonomous step completed → next: {next_step}")

        return next_step

    def _resolve_audio_path(self, call_uuid: str, audio_path: str, scenario: Dict[str, Any]) -> Optional[str]:
        """
        Résout le chemin audio complet depuis audio_path relatif.

        Args:
            call_uuid: UUID de l'appel
            audio_path: Chemin relatif (ex: "finance_1_trop_cher.wav")
            scenario: Scénario (pour récupérer voice)

        Returns:
            Chemin absolu ou None si pas trouvé
        """
        try:
            # Récupérer voice depuis scénario
            voice = scenario.get("voice", "default")

            # Construire chemin complet: audio/tts/{voice}/{audio_path}
            full_path = config.AUDIO_FILES_PATH / "tts" / voice / audio_path

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
        Met à jour le status de l'appel en DB.

        Args:
            call_uuid: UUID de l'appel
            status: Nouveau status (NO_ANSWER, COMPLETED, etc.)
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
            db.close()

    def _execute_scenario_json(self, call_uuid: str, scenario_name: str, campaign_id: str, contact_data: Dict[str, Any] = None):
        """
        Exécute un scénario JSON (nouveau format avec ScenarioManager).

        Support complet pour:
        - audio_type: audio, tts, tts_cloned, freestyle
        - intent_mapping dynamique
        - Variables dans message_text ({{first_name}}, etc.)
        - Qualification lead/not_interested

        Args:
            call_uuid: UUID de l'appel
            scenario_name: Nom du scénario JSON (sans .json)
            campaign_id: ID campagne
            contact_data: Données contact pour variables (optionnel)
        """
        if not self.scenario_manager:
            logger.error(f"[{call_uuid[:8]}] ScenarioManager not available")
            self.hangup_call(call_uuid)
            return

        logger.info(f"[{call_uuid[:8]}] Executing JSON scenario: {scenario_name}")

        # Charger scénario
        scenario = self.scenario_manager.load_scenario(scenario_name)
        if not scenario:
            logger.error(f"[{call_uuid[:8]}] Scenario '{scenario_name}' not found")
            self.hangup_call(call_uuid)
            return

        # Charger voix en cache pour performance TTS (CRITIQUE pour appels temps réel)
        # Chercher voix au niveau global ou dans le premier step
        voice_name = scenario.get("voice")
        if not voice_name and "steps" in scenario:
            # Trouver la première voix définie dans un step
            for step_name, step_config in scenario.get("steps", {}).items():
                if "voice" in step_config:
                    voice_name = step_config["voice"]
                    break

        voice_name = voice_name or "julie"  # Fallback par défaut

        if self.tts_service and hasattr(self.tts_service, 'load_voice'):
            logger.info(f"[{call_uuid[:8]}] 🎙️ Loading voice '{voice_name}' in cache...")
            if self.tts_service.load_voice(voice_name):
                logger.info(f"[{call_uuid[:8]}] ✅ Voice '{voice_name}' loaded (embeddings cached)")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ Voice '{voice_name}' not loaded (will use on-the-fly)")

        # Stocker voix du scénario dans session pour accès rapide
        if call_uuid in self.streaming_sessions:
            self.streaming_sessions[call_uuid]["scenario_voice"] = voice_name

        # Vérifier mode agent autonome (Phase 6+)
        is_agent_mode = self.scenario_manager.is_agent_mode(scenario) if self.scenario_manager else False

        if is_agent_mode:
            logger.info(f"[{call_uuid[:8]}] 🤖 Agent Mode ENABLED")

            # Charger objection matcher pour la thématique
            theme = self.scenario_manager.get_theme(scenario) if self.scenario_manager else "general"
            if OBJECTION_MATCHER_AVAILABLE:
                logger.info(f"[{call_uuid[:8]}] Loading objections for theme: {theme}")
                matcher = ObjectionMatcher.load_objections_for_theme(theme)
                if matcher:
                    self.streaming_sessions[call_uuid]["objection_matcher"] = matcher
                    logger.info(f"[{call_uuid[:8]}] ✅ Objection matcher loaded ({theme})")
                else:
                    logger.warning(f"[{call_uuid[:8]}] ⚠️ Failed to load objection matcher")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ ObjectionMatcher not available")

            # Démarrer background audio si configuré
            background_audio = scenario.get("background_audio")
            if background_audio:
                bg_path = config.AUDIO_FILES_PATH / "background" / background_audio
                self._start_background_audio(call_uuid, str(bg_path))

        # Variables pour remplacement
        variables = contact_data or {}
        variables.setdefault("first_name", "")
        variables.setdefault("last_name", "")
        variables.setdefault("company", "")

        # Historique pour qualification
        call_history = {}

        # Première étape (rail ou intro classique)
        if is_agent_mode:
            rail = self.scenario_manager.get_rail(scenario) if self.scenario_manager else []
            if rail:
                current_step = rail[0]  # Première étape du rail
                logger.info(f"[{call_uuid[:8]}] Rail: {' → '.join(rail)}")
            else:
                logger.error(f"[{call_uuid[:8]}] Agent mode but no rail defined")
                self.hangup_call(call_uuid)
                return
        else:
            current_step = "intro"  # Convention: toujours commencer par "intro"

        # Loop sur les étapes
        max_iterations = 50
        iteration = 0

        while current_step and iteration < max_iterations:
            iteration += 1

            # Récupérer config étape
            step_config = self.scenario_manager.get_step_config(scenario, current_step)
            if not step_config:
                logger.error(f"[{call_uuid[:8]}] Step '{current_step}' not found")
                break

            self.streaming_sessions[call_uuid]["current_step"] = current_step

            # Vérifier si étape terminale (avec résultat)
            if "result" in step_config:
                result = step_config["result"]
                logger.info(f"[{call_uuid[:8]}] Scenario ended with result: {result}")
                # Sauvegarder résultat en DB ici
                break

            # MODE AGENT AUTONOME (Phase 6+)
            if is_agent_mode:
                # Exécuter étape autonome avec gestion objections/questions
                next_step = self._execute_autonomous_step(call_uuid, scenario, current_step, variables)

                # Si None retourné → 2 silences consécutifs ou erreur
                if next_step is None:
                    logger.warning(f"[{call_uuid[:8]}] Autonomous step returned None → ending scenario")
                    break

                # Sauvegarder dans historique pour qualification
                if self.streaming_sessions[call_uuid]["intents"]:
                    last_intent = self.streaming_sessions[call_uuid]["intents"][-1]
                    call_history[current_step] = last_intent

                current_step = next_step

            # MODE CLASSIQUE (ancien)
            else:
                logger.info(f"[{call_uuid[:8]}] Step: {current_step} (type: {step_config.get('audio_type')})")

                audio_type = step_config.get("audio_type")

                # 1. Traiter selon le type d'audio
                if audio_type == "freestyle":
                    # Mode Freestyle AI - pas de message_text prédéfini
                    self._handle_freestyle_step(call_uuid, step_config, variables)
                else:
                    # Modes normaux: audio, tts, tts_cloned
                    self._handle_normal_step(call_uuid, step_config, variables)

                # 2. Écouter réponse si nécessaire
                timeout = step_config.get("timeout", 10)
                barge_in = step_config.get("barge_in", True)

                transcription = self._listen_for_response(call_uuid, timeout)

                # 3. Analyser intent
                intent = "unknown"
                if transcription and self.nlp_service:
                    intent_result = self.nlp_service.analyze_intent(transcription)
                    intent = intent_result.get("intent", "unknown")
                    logger.info(f"[{call_uuid[:8]}] Intent: {intent}")

                    # Sauvegarder dans historique
                    call_history[current_step] = intent

                # 4. Déterminer prochaine étape via intent_mapping
                next_step = self.scenario_manager.get_next_step(scenario, current_step, intent)

                if next_step == "end" or not next_step:
                    logger.info(f"[{call_uuid[:8]}] Scenario ended")
                    break

                current_step = next_step

        # Évaluer qualification finale
        qualification = self.scenario_manager.evaluate_qualification(scenario, call_history)
        logger.info(f"[{call_uuid[:8]}] Qualification: {qualification['result']}")

        # Fin du scénario
        self.hangup_call(call_uuid)

    def _handle_normal_step(self, call_uuid: str, step_config: Dict[str, Any], variables: Dict[str, Any]):
        """
        Traite une étape normale (audio, tts, tts_cloned).

        Args:
            call_uuid: UUID de l'appel
            step_config: Configuration de l'étape
            variables: Variables pour remplacement
        """
        audio_type = step_config.get("audio_type")
        message_text = step_config.get("message_text", "")

        # Remplacer variables
        if self.scenario_manager:
            message_text = self.scenario_manager.replace_variables(message_text, variables)

        audio_file = None

        if audio_type == "audio":
            # Audio pré-enregistré
            audio_filename = step_config.get("audio_file")
            if audio_filename:
                audio_file = str(config.AUDIO_DIR / audio_filename)

        elif audio_type == "tts":
            # TTS simple
            if self.tts_service and message_text:
                audio_file = self.tts_service.synthesize(message_text)

        elif audio_type == "tts_cloned":
            # TTS avec voix clonée
            if self.tts_service and message_text:
                # Utiliser voix du step, sinon voix du scénario, sinon julie par défaut
                voice_name = step_config.get("voice")
                if not voice_name and call_uuid in self.streaming_sessions:
                    voice_name = self.streaming_sessions[call_uuid].get("scenario_voice", "julie")
                voice_name = voice_name or "julie"
                audio_file = self.tts_service.generate(message_text, voice_name)

        # Jouer audio
        if audio_file:
            self._play_audio(call_uuid, audio_file)
        else:
            logger.warning(f"[{call_uuid[:8]}] No audio generated for step")

    def _handle_freestyle_step(self, call_uuid: str, step_config: Dict[str, Any], variables: Dict[str, Any]):
        """
        Traite une étape freestyle (génération IA dynamique).

        Args:
            call_uuid: UUID de l'appel
            step_config: Configuration de l'étape
            variables: Variables pour contexte
        """
        # Le client a déjà parlé (transcription dans session)
        # On récupère sa dernière question
        if call_uuid not in self.streaming_sessions:
            logger.warning(f"[{call_uuid[:8]}] No streaming session for freestyle")
            return

        transcriptions = self.streaming_sessions[call_uuid].get("transcriptions", [])
        if not transcriptions:
            # Pas encore de question, on attend
            logger.debug(f"[{call_uuid[:8]}] Waiting for user input in freestyle mode...")
            return

        # Dernière transcription = question du client
        last_question = transcriptions[-1]

        # Construire contexte depuis step_config
        context = step_config.get("context", {})
        context.update(variables)  # Ajouter variables contact

        # Générer et jouer réponse freestyle
        if self.freestyle_service and self.freestyle_service.is_available:
            prompt_type = self.freestyle_service.detect_prompt_type(last_question)
            ai_response = self.freestyle_service.generate_response(
                call_uuid=call_uuid,
                user_input=last_question,
                context=context,
                prompt_type=prompt_type
            )

            if ai_response and self.tts_service:
                # Générer audio - utiliser voix du step, sinon voix du scénario
                voice_name = step_config.get("voice")
                if not voice_name and call_uuid in self.streaming_sessions:
                    voice_name = self.streaming_sessions[call_uuid].get("scenario_voice", "julie")
                voice_name = voice_name or "julie"
                audio_file = self.tts_service.generate(ai_response, voice_name)

                if audio_file:
                    self._play_audio(call_uuid, audio_file)
                    # Sauvegarder réponse
                    self.streaming_sessions[call_uuid]["transcriptions"].append(ai_response)

    def _play_audio(self, call_uuid: str, audio_file: str) -> bool:
        """
        Joue un fichier audio sur l'appel avec support barge-in.

        Args:
            call_uuid: UUID de l'appel
            audio_file: Chemin vers fichier audio

        Returns:
            True si lecture complète OK, False si interrompu par barge-in ou erreur
        """
        if not self.esl_conn:
            return False

        try:
            # Réinitialiser flag barge-in
            self.barge_in_active[call_uuid] = False

            # Commande ESL uuid_playback (non-bloquante)
            cmd = f"uuid_playback {call_uuid} {audio_file}"
            result = self.esl_conn.api(cmd)

            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

            if "+OK" not in result_str:
                logger.error(f"[{call_uuid[:8]}] Playback failed: {result_str}")
                return False

            logger.debug(f"[{call_uuid[:8]}] 🔊 Playing: {Path(audio_file).name}")

            # Auto-tracking
            self.call_sequences[call_uuid].append({
                "type": "audio",
                "file": audio_file,
                "timestamp": datetime.now()
            })

            # Surveiller barge-in pendant playback
            # Estimer durée audio (ou interroger FreeSWITCH)
            max_duration = 60  # secondes (sécurité)
            check_interval = 0.1  # 100ms
            elapsed = 0.0

            while elapsed < max_duration:
                # Vérifier si barge-in détecté
                if self.barge_in_active.get(call_uuid, False):
                    logger.info(f"[{call_uuid[:8]}] ⏹️ Audio interrupted by barge-in")
                    return False  # Playback interrompu

                # Vérifier si playback terminé
                # TODO: Vérifier status via uuid_getvar playback_terminators ou events
                # Pour l'instant, on assume terminé après durée max ou barge-in

                time.sleep(check_interval)
                elapsed += check_interval

            # Playback terminé normalement (ou timeout)
            return True

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Playback error: {e}")
            return False

    def _listen_for_response(self, call_uuid: str, timeout: int = 10) -> Optional[str]:
        """
        Écoute et transcrit la réponse du client via streaming temps réel.

        Args:
            call_uuid: UUID de l'appel
            timeout: Timeout en secondes

        Returns:
            Transcription texte ou None
        """
        if call_uuid not in self.streaming_sessions:
            logger.warning(f"[{call_uuid[:8]}] No streaming session")
            return None

        try:
            # Si streaming disponible, attendre transcription via callback
            if self.streaming_asr and self.streaming_asr.is_available:
                logger.debug(f"[{call_uuid[:8]}] 👂 Listening (streaming mode)...")

                # Réinitialiser transcription
                self.streaming_sessions[call_uuid]["last_transcription"] = None

                # Attendre transcription ou timeout
                start_time = time.time()
                check_interval = 0.1  # 100ms

                while time.time() - start_time < timeout:
                    # Vérifier si transcription disponible
                    transcription = self.streaming_sessions[call_uuid].get("last_transcription")

                    if transcription:
                        logger.info(f"[{call_uuid[:8]}] ✅ Got transcription: {transcription}")
                        return transcription

                    # Attendre un peu
                    time.sleep(check_interval)

                # Timeout
                logger.warning(f"[{call_uuid[:8]}] ⏱️ Listen timeout ({timeout}s) - no response")
                return None

            else:
                # Fallback: mode recording si streaming pas disponible
                logger.debug(f"[{call_uuid[:8]}] 👂 Listening (recording fallback)...")

                if not self.stt_service:
                    logger.warning(f"[{call_uuid[:8]}] STT service not available")
                    return None

                # Enregistrer réponse temporairement
                temp_file = f"/tmp/response_{call_uuid}.wav"

                # uuid_record pour capturer audio
                cmd = f"uuid_record {call_uuid} start {temp_file}"
                self.esl_conn.api(cmd)

                # Attendre
                time.sleep(timeout)

                # Arrêter enregistrement
                cmd = f"uuid_record {call_uuid} stop {temp_file}"
                self.esl_conn.api(cmd)

                # Transcrire avec Vosk
                result = self.stt_service.transcribe_file(temp_file)
                transcription = result.get("text", "")

                if transcription:
                    logger.info(f"[{call_uuid[:8]}] Transcription: {transcription}")

                # Cleanup
                Path(temp_file).unlink(missing_ok=True)

                return transcription if transcription else None

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Listen error: {e}")
            return None

    def _analyze_intent(self, transcription: str, step_config: dict) -> str:
        """
        Analyse l'intention depuis la transcription.

        Args:
            transcription: Texte transcrit
            step_config: Config de l'étape

        Returns:
            Intent détecté (affirm, deny, unsure, etc.)
        """
        if not self.nlp_service:
            return "unknown"

        try:
            # Demander à Ollama d'analyser l'intent
            result = self.nlp_service.analyze_intent(transcription)
            intent = result.get("intent", "unknown")
            return intent

        except Exception as e:
            logger.error(f"Intent analysis error: {e}")
            return "unknown"

    def hangup_call(self, call_uuid: str):
        """Raccroche un appel (équivalent DELETE /channels en ARI)"""
        if not self.esl_conn:
            return

        try:
            # Arrêter background audio avant de raccrocher
            self._stop_background_audio(call_uuid)

            cmd = f"uuid_kill {call_uuid}"
            self.esl_conn.api(cmd)
            logger.info(f"[{call_uuid[:8]}] Call hung up")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Hangup error: {e}")

    def _create_call_record(self, call_uuid: str, phone_number: str, campaign_id: str, scenario: str):
        """Crée un enregistrement Call en DB"""
        try:
            db = SessionLocal()

            call = Call(
                uuid=call_uuid,
                phone_number=phone_number,
                campaign_id=int(campaign_id) if campaign_id != "default" else None,
                status="in_progress",
                started_at=datetime.now(),
                scenario=scenario
            )

            db.add(call)
            db.commit()
            logger.debug(f"[{call_uuid[:8]}] Call record created")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Failed to create call record: {e}")
        finally:
            db.close()

    def _post_process_call(self, call_uuid: str):
        """Post-traitement après fin d'appel"""
        try:
            # Sauvegarder transcriptions, intents, etc. en DB
            session_data = self.streaming_sessions.get(call_uuid, {})

            db = SessionLocal()
            call = db.query(Call).filter(Call.uuid == call_uuid).first()

            if call:
                call.ended_at = datetime.now()
                call.status = "completed"
                # Sauvegarder données
                call.metadata = {
                    "transcriptions": session_data.get("transcriptions", []),
                    "intents": session_data.get("intents", []),
                    "sequence": self.call_sequences.get(call_uuid, [])
                }
                db.commit()

            logger.debug(f"[{call_uuid[:8]}] Post-process completed")

        except Exception as e:
            logger.error(f"[{call_uuid[:8]}] Post-process error: {e}")
        finally:
            db.close()

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne statistiques temps réel du robot.

        Returns:
            Dict avec stats (active_calls, total_calls, etc.)
        """
        with self.call_lock:
            return {
                "running": self.running,
                "esl_connected": self.esl_conn and self.esl_conn.connected() if self.esl_conn else False,
                "active_calls": len(self.active_calls),
                "active_calls_list": list(self.active_calls.keys()),
                "streaming_sessions": len(self.streaming_sessions),
                "services": {
                    "stt": self.stt_service is not None and getattr(self.stt_service, 'is_available', False),
                    "tts": self.tts_service is not None and getattr(self.tts_service, 'is_available', False),
                    "nlp": self.nlp_service is not None,
                    "amd": self.amd_service is not None
                }
            }

    def get_active_calls(self) -> List[str]:
        """
        Retourne la liste des UUIDs des appels actifs.

        Returns:
            Liste des UUIDs actifs
        """
        with self.call_lock:
            return list(self.active_calls.keys())

    def get_call_info(self, call_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un appel depuis FreeSWITCH.

        Args:
            call_uuid: UUID de l'appel

        Returns:
            Dict avec infos de l'appel ou None
        """
        if not self.esl_conn or not self.esl_conn.connected():
            return None

        try:
            # Récupérer variables via uuid_getvar
            info = {}

            # Hangup cause
            cmd = f"uuid_getvar {call_uuid} hangup_cause"
            result = self.esl_conn.api(cmd)
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            if result_str and not result_str.startswith("-ERR"):
                info["hangup_cause"] = result_str.strip()

            # AMD result
            cmd = f"uuid_getvar {call_uuid} amd_result"
            result = self.esl_conn.api(cmd)
            result_str = result.getBody() if hasattr(result, 'getBody') else str(result)
            if result_str and not result_str.startswith("-ERR"):
                info["amd_result"] = result_str.strip()

            # Qualification result (depuis metadata session)
            if call_uuid in self.streaming_sessions:
                session = self.streaming_sessions[call_uuid]

                # Déterminer qualification basée sur intents
                intents = session.get("intents", [])
                if intents:
                    # Logique simple: si majorité de "affirm", c'est un LEAD
                    affirm_count = sum(1 for i in intents if i == "affirm")
                    if affirm_count >= len(intents) / 2:
                        info["qualification_result"] = "LEAD"
                    else:
                        info["qualification_result"] = "NOT_INTERESTED"

            return info if info else None

        except Exception as e:
            logger.error(f"Error getting call info for {call_uuid[:8]}: {e}")
            return None


# Point d'entrée pour test
if __name__ == "__main__":
    import sys

    logger.info("🤖 Starting RobotFreeSWITCH test")

    robot = RobotFreeSWITCH()

    if len(sys.argv) > 1 and sys.argv[1] == "--test-call":
        # Mode test: lancer un appel
        phone = sys.argv[2] if len(sys.argv) > 2 else "+33612345678"
        logger.info(f"📞 Test call to {phone}")

        robot.connect()
        if robot.esl_conn and robot.esl_conn.connected():
            call_uuid = robot.originate_call(phone, campaign_id=999, scenario="production")
            logger.info(f"✅ Call UUID: {call_uuid}")
        else:
            logger.error("❌ ESL not connected")
    else:
        # Mode normal: écouter les événements
        try:
            robot.start()
        except KeyboardInterrupt:
            logger.info("⚠️ Stopped by user")
            robot.stop()
