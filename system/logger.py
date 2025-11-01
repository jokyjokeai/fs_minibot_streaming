"""
Logger System - MiniBotPanel v3

Système de logs automatique et structuré.

Fonctionnalités:
- Logs séparés par module (campaigns, calls, system, services)
- Rotation automatique des fichiers
- Format structuré avec timestamps
- Niveaux de log configurables
- Support JSON pour analyse

Utilisation:
    from system.logger import get_logger

    logger = get_logger("campaigns", campaign_id=42)
    logger.info("Campaign started", extra={"contacts": 150})

    logger = get_logger("calls", call_uuid="abc-123")
    logger.info("Call connected", extra={"duration": 45})
"""

import logging
import logging.handlers
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import os

from system.config import config

# Créer dossier logs
LOGS_DIR = config.BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Sous-dossiers par catégorie
LOG_DIRS = {
    "system": LOGS_DIR / "system",
    "campaigns": LOGS_DIR / "campaigns",
    "calls": LOGS_DIR / "calls",
    "services": LOGS_DIR / "services",
    "api": LOGS_DIR / "api",
    "errors": LOGS_DIR / "errors",
    "debug": LOGS_DIR / "debug",
    "freestyle": LOGS_DIR / "freestyle",  # NOUVEAU v3
    "objections": LOGS_DIR / "objections",  # NOUVEAU v3
    "ollama": LOGS_DIR / "ollama",  # NOUVEAU v3
    "amd": LOGS_DIR / "amd",  # Détection répondeur
    "tts": LOGS_DIR / "tts",  # Text-to-Speech
    "stt": LOGS_DIR / "stt"  # Speech-to-Text
}

# Créer tous les sous-dossiers
for dir_path in LOG_DIRS.values():
    dir_path.mkdir(parents=True, exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """Formatter pour logs structurés JSON."""

    def format(self, record):
        """Format le log en JSON structuré."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno
        }

        # Ajouter données extra si présentes
        if hasattr(record, 'campaign_id'):
            log_data['campaign_id'] = record.campaign_id
        if hasattr(record, 'call_uuid'):
            log_data['call_uuid'] = record.call_uuid
        if hasattr(record, 'contact_id'):
            log_data['contact_id'] = record.contact_id

        # Ajouter extra data custom
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename',
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName',
                          'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """Formatter pour logs lisibles humainement."""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logger(
    name: str,
    category: str = "system",
    level: int = logging.INFO,
    campaign_id: Optional[int] = None,
    call_uuid: Optional[str] = None,
    json_format: bool = True
) -> logging.Logger:
    """
    Configure un logger avec handlers appropriés.

    Args:
        name: Nom du logger
        category: Catégorie (system, campaigns, calls, etc.)
        level: Niveau de log
        campaign_id: ID campagne pour logs campagne
        call_uuid: UUID appel pour logs appel
        json_format: Utiliser format JSON ou texte

    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)

    # Si déjà configuré, retourner
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Déterminer fichiers de sortie
    log_dir = LOG_DIRS.get(category, LOGS_DIR / "misc")
    log_dir.mkdir(exist_ok=True)

    # Fichier spécifique si campaign_id ou call_uuid
    if campaign_id:
        log_file = log_dir / f"campaign_{campaign_id}.log"
    elif call_uuid:
        log_file = log_dir / f"call_{call_uuid}.log"
    else:
        # Fichier par jour
        date_str = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"{category}_{date_str}.log"

    # Handler fichier avec rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )

    # Formatter
    if json_format:
        file_handler.setFormatter(StructuredFormatter())
    else:
        file_handler.setFormatter(PlainFormatter())

    logger.addHandler(file_handler)

    # Handler console pour INFO et plus
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(PlainFormatter())
    logger.addHandler(console_handler)

    # Handler erreurs dans fichier séparé
    if category != "errors":
        error_file = LOG_DIRS["errors"] / f"{category}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter() if json_format else PlainFormatter())
        logger.addHandler(error_handler)

    return logger


def get_logger(
    category: str = "system",
    campaign_id: Optional[int] = None,
    call_uuid: Optional[str] = None,
    name: Optional[str] = None
) -> logging.Logger:
    """
    Obtenir un logger pour une catégorie donnée.

    Args:
        category: Type de log (system, campaigns, calls, services, api, errors)
        campaign_id: ID campagne pour contextualiser
        call_uuid: UUID appel pour contextualiser
        name: Nom custom du logger

    Returns:
        Logger configuré

    Examples:
        >>> # Log système
        >>> logger = get_logger("system")
        >>> logger.info("System started")

        >>> # Log campagne
        >>> logger = get_logger("campaigns", campaign_id=42)
        >>> logger.info("Campaign started", extra={"contacts": 150})

        >>> # Log appel
        >>> logger = get_logger("calls", call_uuid="abc-123")
        >>> logger.info("Call connected", extra={"phone": "+33612345678"})

        >>> # Log service
        >>> logger = get_logger("services", name="vosk_stt")
        >>> logger.debug("Transcription result", extra={"text": "Bonjour", "confidence": 0.95})
    """
    if not name:
        name = f"minibot.{category}"
        if campaign_id:
            name = f"{name}.campaign_{campaign_id}"
        elif call_uuid:
            name = f"{name}.call_{call_uuid}"

    logger = setup_logger(
        name=name,
        category=category,
        campaign_id=campaign_id,
        call_uuid=call_uuid
    )

    # Ajouter context au logger
    class ContextLogger:
        def __init__(self, logger, campaign_id=None, call_uuid=None):
            self.logger = logger
            self.campaign_id = campaign_id
            self.call_uuid = call_uuid

        def _log(self, level, msg, *args, **kwargs):
            extra = kwargs.get('extra', {})
            if self.campaign_id:
                extra['campaign_id'] = self.campaign_id
            if self.call_uuid:
                extra['call_uuid'] = self.call_uuid
            kwargs['extra'] = extra
            getattr(self.logger, level)(msg, *args, **kwargs)

        def debug(self, msg, *args, **kwargs):
            self._log('debug', msg, *args, **kwargs)

        def info(self, msg, *args, **kwargs):
            self._log('info', msg, *args, **kwargs)

        def warning(self, msg, *args, **kwargs):
            self._log('warning', msg, *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            self._log('error', msg, *args, **kwargs)

        def critical(self, msg, *args, **kwargs):
            self._log('critical', msg, *args, **kwargs)

    return ContextLogger(logger, campaign_id, call_uuid)


# Loggers globaux pré-configurés
system_logger = get_logger("system")
api_logger = get_logger("api")
error_logger = get_logger("errors")


def log_campaign_event(campaign_id: int, event: str, data: Dict[str, Any] = None):
    """Log un événement de campagne."""
    logger = get_logger("campaigns", campaign_id=campaign_id)
    logger.info(event, extra=data or {})


def log_call_event(call_uuid: str, event: str, data: Dict[str, Any] = None):
    """Log un événement d'appel."""
    logger = get_logger("calls", call_uuid=call_uuid)
    logger.info(event, extra=data or {})


def log_service_event(service: str, event: str, data: Dict[str, Any] = None):
    """Log un événement de service."""
    logger = get_logger("services", name=f"service.{service}")
    logger.info(event, extra=data or {})


def log_error(module: str, error: Exception, context: Dict[str, Any] = None):
    """Log une erreur avec contexte."""
    logger = get_logger("errors", name=f"error.{module}")
    logger.error(
        f"{error.__class__.__name__}: {str(error)}",
        exc_info=True,
        extra=context or {}
    )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers spécialisés pour v3
# ═══════════════════════════════════════════════════════════════════════════

def log_freestyle_turn(call_uuid: str, turn_number: int, user_input: str, ai_response: str,
                      generation_time: float, context: Dict[str, Any] = None):
    """Log un tour de conversation Freestyle AI."""
    logger = get_logger("freestyle", call_uuid=call_uuid)
    logger.info(
        f"Freestyle turn {turn_number}",
        extra={
            "turn_number": turn_number,
            "user_input": user_input,
            "ai_response": ai_response,
            "generation_time": generation_time,
            "response_length": len(ai_response),
            **(context or {})
        }
    )


def log_objection_match(call_uuid: str, user_input: str, matched_objection: str,
                       score: float, response_used: str, method: str = "hybrid"):
    """Log un matching d'objection réussi."""
    logger = get_logger("objections", call_uuid=call_uuid)
    logger.info(
        f"Objection matched: '{matched_objection}' (score: {score:.2f})",
        extra={
            "user_input": user_input,
            "matched_objection": matched_objection,
            "match_score": score,
            "response_used": response_used,
            "match_method": method,
            "confidence": "high" if score >= 0.8 else "medium" if score >= 0.7 else "low"
        }
    )


def log_objection_no_match(call_uuid: str, user_input: str, best_score: float,
                          fallback_method: str = "freestyle"):
    """Log une absence de matching d'objection."""
    logger = get_logger("objections", call_uuid=call_uuid)
    logger.info(
        f"No objection match (best score: {best_score:.2f})",
        extra={
            "user_input": user_input,
            "best_score": best_score,
            "threshold": 0.5,
            "fallback_method": fallback_method
        }
    )


def log_ollama_request(call_uuid: str, prompt: str, model: str, temperature: float,
                      max_tokens: int, response_time: float, response: str = None):
    """Log une requête Ollama (LLM)."""
    logger = get_logger("ollama", call_uuid=call_uuid)
    logger.info(
        f"Ollama request ({model})",
        extra={
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "response_time": response_time,
            "response_length": len(response) if response else 0,
            "response_preview": response[:200] + "..." if response and len(response) > 200 else response
        }
    )


def log_amd_detection(call_uuid: str, method: str, result: str, confidence: float,
                     speech_duration: float = None, keywords_matched: list = None):
    """Log un événement de détection AMD (Answering Machine Detection)."""
    logger = get_logger("amd", call_uuid=call_uuid)
    logger.info(
        f"AMD detection: {result} (confidence: {confidence:.2f})",
        extra={
            "detection_method": method,  # "freeswitch" ou "python"
            "result": result,  # "HUMAN" ou "MACHINE"
            "confidence": confidence,
            "speech_duration": speech_duration,
            "keywords_matched": keywords_matched or [],
            "num_keywords": len(keywords_matched) if keywords_matched else 0
        }
    )


def log_tts_generation(call_uuid: str, text: str, voice_id: int, method: str,
                      generation_time: float, audio_duration: float, cached: bool = False):
    """Log une génération TTS (Text-to-Speech)."""
    logger = get_logger("tts", call_uuid=call_uuid)
    logger.info(
        f"TTS generated ({method})",
        extra={
            "text": text,
            "text_length": len(text),
            "voice_id": voice_id,
            "method": method,  # "coqui", "prerecorded", "cache"
            "generation_time": generation_time,
            "audio_duration": audio_duration,
            "cached": cached,
            "efficiency_ratio": audio_duration / generation_time if generation_time > 0 else 0
        }
    )


def log_stt_transcription(call_uuid: str, audio_duration: float, transcription: str,
                         confidence: float, processing_time: float, language: str = "fr"):
    """Log une transcription STT (Speech-to-Text)."""
    logger = get_logger("stt", call_uuid=call_uuid)
    logger.info(
        f"STT transcription: '{transcription}'",
        extra={
            "audio_duration": audio_duration,
            "transcription": transcription,
            "transcription_length": len(transcription),
            "confidence": confidence,
            "processing_time": processing_time,
            "language": language,
            "words_per_second": len(transcription.split()) / audio_duration if audio_duration > 0 else 0
        }
    )


def log_scenario_transition(call_uuid: str, from_step: str, to_step: str, intent: str,
                           reason: str = None):
    """Log une transition de scénario."""
    logger = get_logger("calls", call_uuid=call_uuid)
    logger.info(
        f"Scenario transition: {from_step} → {to_step}",
        extra={
            "from_step": from_step,
            "to_step": to_step,
            "intent": intent,
            "reason": reason
        }
    )


def log_performance_metric(category: str, metric_name: str, value: float,
                          unit: str = "", context: Dict[str, Any] = None):
    """Log une métrique de performance."""
    logger = get_logger("system", name=f"metrics.{category}")
    logger.info(
        f"{metric_name}: {value}{unit}",
        extra={
            "category": category,
            "metric": metric_name,
            "value": value,
            "unit": unit,
            **(context or {})
        }
    )


# Test au démarrage
if __name__ == "__main__":
    # Test logs
    system_logger.info("Logger system initialized")

    # Test campaign log
    log_campaign_event(1, "Campaign started", {"contacts": 100, "scenario": "test"})

    # Test call log
    log_call_event("uuid-123", "Call connected", {"phone": "+33612345678"})

    # Test service log
    log_service_event("vosk_stt", "Model loaded", {"model": "fr-small"})

    # Test error log
    try:
        raise ValueError("Test error")
    except Exception as e:
        log_error("test_module", e, {"action": "testing"})

    print(f"✅ Logs créés dans: {LOGS_DIR}")