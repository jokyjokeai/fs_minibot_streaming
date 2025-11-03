"""
Configuration Centrale - MiniBotPanel v3

Ce module centralise TOUTE la configuration du système:
- Paramètres base de données (PostgreSQL)
- Configuration FreeSWITCH (ESL host, port, password)
- Paramètres services IA (Vosk, Ollama)
- Chemins fichiers (audio, logs, exports)
- Limites système (appels simultanés, timeouts)
- Conformité légale (horaires légaux)

Utilisation:
    from system.config import config
    db_url = config.DATABASE_URL
    freeswitch_host = config.FREESWITCH_ESL_HOST
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger variables d'environnement depuis .env
load_dotenv()

# Chemins de base
BASE_DIR = Path(__file__).parent.parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_FILES_PATH = AUDIO_DIR  # Alias pour compatibilité

# Structure audio par voix
# audio/{voice_name}/base/        - Fichiers scénario de base
# audio/{voice_name}/objections/  - Objections/questions de la DB
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "julie")

def get_audio_path(voice: str, audio_type: str, filename: str) -> Path:
    """
    Retourne le chemin complet d'un fichier audio.

    Args:
        voice: Nom de la voix (julie, marie, etc.)
        audio_type: Type audio ("base" ou "objections")
        filename: Nom du fichier (avec .wav)

    Returns:
        Path complet vers le fichier audio
    """
    return AUDIO_DIR / voice / audio_type / filename

LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"
RECORDINGS_DIR = BASE_DIR / "recordings"
TRANSCRIPTIONS_DIR = BASE_DIR / "transcriptions"

# ============================================================================
# BASE DE DONNÉES
# ============================================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://minibot:minibot@localhost:5432/minibot_freeswitch"
)

# ============================================================================
# FREESWITCH ESL
# ============================================================================
FREESWITCH_ESL_HOST = os.getenv("FREESWITCH_ESL_HOST", "localhost")
FREESWITCH_ESL_PORT = int(os.getenv("FREESWITCH_ESL_PORT", "8021"))
FREESWITCH_ESL_PASSWORD = os.getenv("FREESWITCH_ESL_PASSWORD", "ClueCon")
FREESWITCH_GATEWAY = os.getenv("FREESWITCH_GATEWAY", "gateway1")  # Gateway SIP configuré
FREESWITCH_HOST = FREESWITCH_ESL_HOST  # Alias pour robot

# ============================================================================
# SERVICES IA
# ============================================================================

# Vosk (Speech-to-Text)
VOSK_MODEL_PATH = os.getenv(
    "VOSK_MODEL_PATH",
    str(BASE_DIR / "models" / "vosk-model-small-fr-0.22")
)
VOSK_SAMPLE_RATE = int(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# Ollama (NLP - Intent + Sentiment)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "10"))

# TTS removed - using pre-recorded audio only

# HuggingFace (requis pour pyannote.audio speaker diarization)
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")

# ============================================================================
# AMD (Answering Machine Detection)
# ============================================================================
AMD_ENABLED = os.getenv("AMD_ENABLED", "true").lower() == "true"
AMD_DUAL_LAYER = os.getenv("AMD_DUAL_LAYER", "true").lower() == "true"

# AMD FreeSWITCH (niveau 1 - rapide)
AMD_FS_TIMEOUT = int(os.getenv("AMD_FS_TIMEOUT", "5000"))  # ms

# AMD Python Vosk (niveau 2 - précis)
AMD_PYTHON_ENABLED = os.getenv("AMD_PYTHON_ENABLED", "true").lower() == "true"
AMD_MACHINE_KEYWORDS = ["bonjour vous êtes bien", "laissez un message", "veuillez laisser"]
AMD_MACHINE_SPEECH_DURATION_MIN = float(os.getenv("AMD_MACHINE_SPEECH_DURATION_MIN", "3.0"))

# ============================================================================
# LIMITES SYSTÈME
# ============================================================================
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "10"))
CALL_TIMEOUT = int(os.getenv("CALL_TIMEOUT", "300"))  # secondes
DELAY_BETWEEN_CALLS = float(os.getenv("DELAY_BETWEEN_CALLS", "2.0"))  # secondes

# ============================================================================
# GESTION FILE D'ATTENTE & BATCH
# ============================================================================
DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", "5"))  # Appels par batch
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "20"))  # Batch size maximum
QUEUE_CHECK_INTERVAL = int(os.getenv("QUEUE_CHECK_INTERVAL", "5"))  # secondes

# ============================================================================
# GESTION RETRY (NO_ANSWER / BUSY)
# ============================================================================
RETRY_ENABLED = os.getenv("RETRY_ENABLED", "true").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))  # Nombre max de retry
RETRY_DELAY_MINUTES = int(os.getenv("RETRY_DELAY_MINUTES", "30"))  # Délai entre retry NO_ANSWER
RETRY_BUSY_DELAY_MINUTES = int(os.getenv("RETRY_BUSY_DELAY_MINUTES", "5"))  # Délai retry BUSY

# ============================================================================
# CONFORMITÉ LÉGALE (FRANCE)
# ============================================================================
# Horaires légaux (France) : Lun-Ven 10h-13h et 14h-20h, Sam 10h-13h
LEGAL_HOURS = {
    "weekdays": [(10, 13), (14, 20)],  # Lundi à Vendredi
    "saturday": [(10, 13)],             # Samedi
    "sunday": []                        # Dimanche interdit
}

# ============================================================================
# CACHE AU DÉMARRAGE
# ============================================================================
PRELOAD_MODELS = os.getenv("PRELOAD_MODELS", "true").lower() == "true"
PRELOAD_TTS_AUDIO = os.getenv("PRELOAD_TTS_AUDIO", "true").lower() == "true"
PRELOAD_SCENARIOS = os.getenv("PRELOAD_SCENARIOS", "true").lower() == "true"

# ============================================================================
# API REST
# ============================================================================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_BASE_URL = os.getenv("API_BASE_URL", f"http://localhost:{API_PORT}")
API_PASSWORD = os.getenv("API_PASSWORD", "change_me_in_production")  # Simple password protection

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============================================================================
# CLASSE CONFIG (pour import facile)
# ============================================================================
class Config:
    """Classe config pour accès attributs"""

    # Chemins
    BASE_DIR = BASE_DIR
    AUDIO_DIR = AUDIO_DIR
    AUDIO_FILES_PATH = AUDIO_FILES_PATH
    VOICES_DIR = VOICES_DIR
    LOGS_DIR = LOGS_DIR
    EXPORTS_DIR = EXPORTS_DIR
    RECORDINGS_DIR = RECORDINGS_DIR
    TRANSCRIPTIONS_DIR = TRANSCRIPTIONS_DIR

    # Database
    DATABASE_URL = DATABASE_URL

    # FreeSWITCH
    FREESWITCH_HOST = FREESWITCH_HOST
    FREESWITCH_ESL_HOST = FREESWITCH_ESL_HOST
    FREESWITCH_ESL_PORT = FREESWITCH_ESL_PORT
    FREESWITCH_ESL_PASSWORD = FREESWITCH_ESL_PASSWORD
    FREESWITCH_GATEWAY = FREESWITCH_GATEWAY

    # IA Services
    VOSK_MODEL_PATH = VOSK_MODEL_PATH
    VOSK_SAMPLE_RATE = VOSK_SAMPLE_RATE
    OLLAMA_URL = OLLAMA_URL
    OLLAMA_MODEL = OLLAMA_MODEL
    OLLAMA_TIMEOUT = OLLAMA_TIMEOUT
    COQUI_MODEL = COQUI_MODEL
    COQUI_USE_GPU = COQUI_USE_GPU
    COQUI_CACHE_ENABLED = COQUI_CACHE_ENABLED
    HUGGINGFACE_TOKEN = HUGGINGFACE_TOKEN

    # AMD
    AMD_ENABLED = AMD_ENABLED
    AMD_DUAL_LAYER = AMD_DUAL_LAYER
    AMD_FS_TIMEOUT = AMD_FS_TIMEOUT
    AMD_PYTHON_ENABLED = AMD_PYTHON_ENABLED
    AMD_MACHINE_KEYWORDS = AMD_MACHINE_KEYWORDS
    AMD_MACHINE_SPEECH_DURATION_MIN = AMD_MACHINE_SPEECH_DURATION_MIN

    # Limites
    MAX_CONCURRENT_CALLS = MAX_CONCURRENT_CALLS
    CALL_TIMEOUT = CALL_TIMEOUT
    DELAY_BETWEEN_CALLS = DELAY_BETWEEN_CALLS

    # Queue & Batch
    DEFAULT_BATCH_SIZE = DEFAULT_BATCH_SIZE
    MAX_BATCH_SIZE = MAX_BATCH_SIZE
    QUEUE_CHECK_INTERVAL = QUEUE_CHECK_INTERVAL

    # Retry
    RETRY_ENABLED = RETRY_ENABLED
    MAX_RETRIES = MAX_RETRIES
    RETRY_DELAY_MINUTES = RETRY_DELAY_MINUTES
    RETRY_BUSY_DELAY_MINUTES = RETRY_BUSY_DELAY_MINUTES

    # Conformité
    LEGAL_HOURS = LEGAL_HOURS

    # Cache
    PRELOAD_MODELS = PRELOAD_MODELS
    PRELOAD_TTS_AUDIO = PRELOAD_TTS_AUDIO
    PRELOAD_SCENARIOS = PRELOAD_SCENARIOS

    # API
    API_HOST = API_HOST
    API_PORT = API_PORT
    API_BASE_URL = API_BASE_URL
    API_PASSWORD = API_PASSWORD

    # Logging
    LOG_LEVEL = LOG_LEVEL
    LOG_FORMAT = LOG_FORMAT

# Instance globale
config = Config()
