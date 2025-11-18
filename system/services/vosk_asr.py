# -*- coding: utf-8 -*-
"""
Vosk ASR Service - mod_vosk Integration for FreeSWITCH

Ce service gère l'intégration avec mod_vosk pour la reconnaissance vocale
en temps réel via FreeSWITCH.

Utilisé pour PHASE 2 (barge-in streaming) comme alternative à WebRTC VAD + Faster-Whisper.

Architecture:
- Crée des grammars XML dynamiques pour barge-in
- Lance/arrête mod_vosk via ESL commands
- Parse les événements DETECTED_SPEECH de FreeSWITCH
- Retourne transcriptions en temps réel (<200ms latency)

Avantages mod_vosk vs WebRTC VAD actuel:
- Latence réduite (150ms vs 600ms)
- Transcription native (pas de snapshot périodique)
- Intégration FreeSWITCH native (pas de bridges)
- Fallback CPU-only robuste
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VoskDetectionResult:
    """Résultat d'une détection Vosk"""
    text: str
    confidence: float
    is_final: bool
    timestamp_ms: int


class VoskASR:
    """
    Service ASR basé sur mod_vosk pour FreeSWITCH

    Permet la reconnaissance vocale streaming native via mod_vosk.
    """

    def __init__(
        self,
        model_path: str,
        sample_rate: int = 8000,
        confidence_threshold: float = 0.3,
        bargein_keywords: Optional[List[str]] = None
    ):
        """
        Initialise le service Vosk ASR

        Args:
            model_path: Chemin vers le modèle Vosk (ex: /usr/share/vosk/model-fr)
            sample_rate: Taux d'échantillonnage audio (8000 Hz pour téléphonie)
            confidence_threshold: Seuil de confiance minimum (0.0-1.0)
            bargein_keywords: Liste de mots-clés pour grammars barge-in
        """
        self.model_path = Path(model_path)
        self.sample_rate = sample_rate
        self.confidence_threshold = confidence_threshold
        self.bargein_keywords = bargein_keywords or []

        # Vérifier que le modèle existe
        if not self.model_path.exists():
            logger.warning(
                f"⚠️  Vosk model not found at {self.model_path}. "
                f"mod_vosk may not work correctly."
            )
        else:
            logger.info(f"✅ Vosk model loaded from {self.model_path}")

    def create_bargein_grammar(
        self,
        grammar_id: str = "bargein",
        keywords: Optional[List[str]] = None
    ) -> str:
        """
        Crée une grammar XML pour barge-in detection

        Grammar permet de contraindre la reconnaissance vocale à des mots-clés
        spécifiques, améliorant la précision et réduisant la latence.

        Args:
            grammar_id: Identifiant de la grammar (utilisé par mod_vosk)
            keywords: Liste de mots-clés (utilise self.bargein_keywords si None)

        Returns:
            Chaîne XML de la grammar

        Example:
            >>> vosk = VoskASR("/usr/share/vosk/model-fr")
            >>> grammar_xml = vosk.create_bargein_grammar()
            >>> print(grammar_xml)
            <grammar>
              <rule id="bargein">
                <one-of>
                  <item>oui</item>
                  <item>non</item>
                  ...
                </one-of>
              </rule>
            </grammar>
        """
        keywords = keywords or self.bargein_keywords

        if not keywords:
            # Grammar vide (accepte tout)
            return """<?xml version="1.0" encoding="UTF-8"?>
<grammar version="1.0" xmlns="http://www.w3.org/2001/06/grammar"
         xml:lang="fr-FR" mode="voice" root="root">
  <rule id="root">
    <item repeat="0-">
      <ruleref special="GARBAGE"/>
    </item>
  </rule>
</grammar>
"""

        # Construire les items de keywords
        items_xml = "\n".join(
            f"      <item>{keyword}</item>"
            for keyword in keywords
        )

        grammar_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<grammar version="1.0" xmlns="http://www.w3.org/2001/06/grammar"
         xml:lang="fr-FR" mode="voice" root="{grammar_id}">
  <rule id="{grammar_id}">
    <one-of>
{items_xml}
      <item repeat="1-">
        <ruleref special="GARBAGE"/>
      </item>
    </one-of>
  </rule>
</grammar>
"""

        return grammar_xml

    def save_grammar_file(
        self,
        grammar_xml: str,
        filename: str = "bargein_grammar.xml"
    ) -> Path:
        """
        Sauvegarde une grammar XML dans un fichier temporaire

        Args:
            grammar_xml: Contenu XML de la grammar
            filename: Nom du fichier (sera créé dans /tmp)

        Returns:
            Path vers le fichier créé
        """
        grammar_path = Path("/tmp") / filename

        with open(grammar_path, 'w', encoding='utf-8') as f:
            f.write(grammar_xml)

        logger.debug(f"📝 Grammar saved to {grammar_path}")

        return grammar_path

    def parse_detected_speech_event(
        self,
        event: Any
    ) -> Optional[VoskDetectionResult]:
        """
        Parse un événement DETECTED_SPEECH de FreeSWITCH

        Args:
            event: Événement ESL (ESLEvent object)

        Returns:
            VoskDetectionResult si événement valide, sinon None

        Event headers attendus:
        - Event-Name: DETECTED_SPEECH
        - Speech-Type: detected-speech ou detected-partial (Vosk)
        - Speech-Text: Texte transcrit
        - Confidence: Score de confiance (0-100)
        """
        if not event:
            return None

        # Vérifier type événement
        event_name = event.getHeader("Event-Name")
        if event_name != "DETECTED_SPEECH":
            return None

        # Extraire texte
        text = event.getHeader("Speech-Text") or ""
        if not text.strip():
            return None

        # Extraire confiance (0-100 en entier, convertir en 0.0-1.0)
        confidence_str = event.getHeader("Confidence") or "0"
        try:
            confidence = float(confidence_str) / 100.0
        except ValueError:
            confidence = 0.0

        # Détecter si transcription finale ou partielle
        speech_type = event.getHeader("Speech-Type") or ""
        is_final = "detected-speech" in speech_type.lower()

        # Timestamp (si disponible)
        timestamp_str = event.getHeader("Event-Date-Timestamp") or "0"
        try:
            timestamp_ms = int(timestamp_str) // 1000  # microsecondes -> millisecondes
        except ValueError:
            timestamp_ms = 0

        result = VoskDetectionResult(
            text=text.strip(),
            confidence=confidence,
            is_final=is_final,
            timestamp_ms=timestamp_ms
        )

        logger.debug(
            f"🎙️  Vosk detected: '{result.text}' "
            f"(confidence: {result.confidence:.2f}, final: {result.is_final})"
        )

        return result

    def check_module_loaded(self, esl_connection: Any) -> bool:
        """
        Vérifie si mod_vosk est chargé dans FreeSWITCH

        Args:
            esl_connection: Connexion ESL active

        Returns:
            True si mod_vosk chargé, sinon False
        """
        # Commande: module_exists mod_vosk
        result = esl_connection.api("module_exists", "mod_vosk")

        if not result:
            logger.warning("⚠️  Unable to check mod_vosk (ESL error)")
            return False

        response = result.getBody()

        if response and "true" in response.lower():
            logger.info("✅ mod_vosk is loaded in FreeSWITCH")
            return True
        else:
            logger.warning(
                "⚠️  mod_vosk not loaded in FreeSWITCH. "
                "Load it with: fs_cli> load mod_vosk"
            )
            return False

    def get_esl_commands_for_detection(
        self,
        call_uuid: str,
        audio_file: str,
        grammar_path: Optional[Path] = None
    ) -> Dict[str, str]:
        """
        Génère les commandes ESL pour démarrer la détection Vosk

        Args:
            call_uuid: UUID de l'appel FreeSWITCH
            audio_file: Chemin vers le fichier audio à jouer
            grammar_path: Chemin vers la grammar XML (optionnel)

        Returns:
            Dictionnaire avec les commandes ESL à exécuter:
            {
                "play_and_detect": "...",  # Commande principale
                "stop": "..."              # Commande pour arrêter
            }

        Example:
            >>> cmds = vosk.get_esl_commands_for_detection(
            ...     "abc123",
            ...     "/tmp/prompt.wav",
            ...     "/tmp/bargein_grammar.xml"
            ... )
            >>> print(cmds["play_and_detect"])
            play_and_detect_speech /tmp/prompt.wav detect:vosk {grammars=/tmp/bargein_grammar.xml}
        """
        # Construire la commande play_and_detect_speech
        detect_params = f"detect:vosk"

        if grammar_path and grammar_path.exists():
            detect_params += f" {{grammars={grammar_path}}}"

        # IMPORTANT: Pour ESL recevoir événements DETECTED_SPEECH, il FAUT :
        # 1. Configurer fire_asr_events=true (sinon pas d'événements envoyés à ESL)
        # 2. Utiliser sendmsg execute (play_and_detect_speech est application dialplan)

        # Commande 1: Activer fire_asr_events
        fire_asr_cmd = f"uuid_setvar {call_uuid} fire_asr_events true"

        # Commande 2: play_and_detect_speech via sendmsg (format dict pour traitement spécial)
        play_and_detect_cmd = {
            "type": "sendmsg",
            "uuid": call_uuid,
            "app": "play_and_detect_speech",
            "args": f"{audio_file} {detect_params}"
        }

        # Commande pour arrêter
        stop_cmd = f"uuid_break {call_uuid}"

        return {
            "fire_asr": fire_asr_cmd,
            "play_and_detect": play_and_detect_cmd,
            "stop": stop_cmd
        }


def create_vosk_service(config: Any) -> Optional[VoskASR]:
    """
    Factory function pour créer le service Vosk ASR

    Vérifie la configuration et crée le service uniquement si activé.

    Args:
        config: Objet configuration (system.config.Config)

    Returns:
        Instance VoskASR si activé, sinon None
    """
    if not config.VOSK_ENABLED:
        logger.info("ℹ️  Vosk ASR disabled in config (VOSK_ENABLED=False)")
        return None

    try:
        vosk_service = VoskASR(
            model_path=config.VOSK_MODEL_PATH,
            sample_rate=config.VOSK_SAMPLE_RATE,
            confidence_threshold=config.VOSK_CONFIDENCE_THRESHOLD,
            bargein_keywords=config.VOSK_BARGEIN_GRAMMAR_KEYWORDS
        )

        logger.info(
            f"✅ Vosk ASR service created "
            f"(model: {config.VOSK_MODEL_PATH}, sr: {config.VOSK_SAMPLE_RATE}Hz)"
        )

        return vosk_service

    except Exception as e:
        logger.error(f"❌ Failed to create Vosk ASR service: {e}")
        return None
