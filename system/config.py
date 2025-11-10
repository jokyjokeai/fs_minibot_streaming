"""
Configuration MiniBotPanel - ULTRA SIMPLIFIÉE
==============================================

Configuration épurée avec uniquement l'essentiel:
- Chemins et dossiers
- Database
- FreeSWITCH ESL
- Services IA (Vosk, Ollama)
- AMD (Answering Machine Detection)
- Barge-in (détection interruption client)
- Gestion appels et retry
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CHEMINS
# ============================================================================
BASE_DIR = Path(__file__).parent.parent
AUDIO_DIR = BASE_DIR / "audio"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"
RECORDINGS_DIR = BASE_DIR / "recordings"

# Audio FreeSWITCH
FREESWITCH_SOUNDS_DIR = Path(os.getenv(
    "FREESWITCH_SOUNDS_DIR",
    "/usr/share/freeswitch/sounds/minibot"
))
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "julie")

def get_freeswitch_audio_path(voice: str, audio_type: str, filename: str) -> Path:
    """
    Retourne chemin FreeSWITCH pour audio.

    Args:
        voice: julie, marie, etc.
        audio_type: base, objections
        filename: nom fichier avec .wav

    Returns:
        Path: /usr/share/freeswitch/sounds/minibot/{voice}/{audio_type}/{filename}
    """
    if not filename.endswith('.wav'):
        filename = f"{filename}.wav"
    return FREESWITCH_SOUNDS_DIR / voice / audio_type / filename

# ============================================================================
# DATABASE
# ============================================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://minibot:minibot@localhost:5432/minibot_freeswitch"
)

# ============================================================================
# FREESWITCH
# ============================================================================
FREESWITCH_HOST = os.getenv("FREESWITCH_HOST", "localhost")
FREESWITCH_ESL_HOST = os.getenv("FREESWITCH_ESL_HOST", "localhost")
FREESWITCH_ESL_PORT = int(os.getenv("FREESWITCH_ESL_PORT", "8021"))
FREESWITCH_ESL_PASSWORD = os.getenv("FREESWITCH_ESL_PASSWORD", "ClueCon")
FREESWITCH_GATEWAY = os.getenv("FREESWITCH_GATEWAY", "gateway1")

# ============================================================================
# IA SERVICES
# ============================================================================
# Vosk STT
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-fr-0.22-lgraph")
VOSK_SAMPLE_RATE = int(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# Ollama NLP
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# ============================================================================
# AMD (Answering Machine Detection)
# ============================================================================
AMD_ENABLED = os.getenv("AMD_ENABLED", "true").lower() == "true"
AMD_LISTEN_DURATION = float(os.getenv("AMD_LISTEN_DURATION", "2.5"))
AMD_WORD_THRESHOLD = int(os.getenv("AMD_WORD_THRESHOLD", "8"))
AMD_INITIAL_DELAY = float(os.getenv("AMD_INITIAL_DELAY", "2.5"))  # Délai avant de parler

# ============================================================================
# STREAMING ASR & VAD
# ============================================================================
# VAD (Voice Activity Detection)
VAD_SILENCE_THRESHOLD = float(os.getenv("VAD_SILENCE_THRESHOLD", "0.8"))  # secondes
VAD_SPEECH_START_THRESHOLD = float(os.getenv("VAD_SPEECH_START_THRESHOLD", "0.5"))

# WebSocket
WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "127.0.0.1")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "8080"))

# ============================================================================
# BARGE-IN (ULTRA SIMPLE)
# ============================================================================
BARGE_IN_ENABLED = True
BARGE_IN_DURATION_THRESHOLD = 2.5  # secondes - Parole >= 2.5s = barge-in
GRACE_PERIOD_SECONDS = 2.0  # Grace period au début audio
SMOOTH_DELAY_SECONDS = 1.0  # Délai avant stop audio (smooth pour finir phrase)
BARGE_IN_SMOOTH_DELAY = 1.0  # Alias pour compatibilité

# ============================================================================
# APPELS & RETRY
# ============================================================================
MAX_SIMULTANEOUS_CALLS = int(os.getenv("MAX_SIMULTANEOUS_CALLS", "10"))
CALL_TIMEOUT_SECONDS = int(os.getenv("CALL_TIMEOUT_SECONDS", "300"))

# Retry
RETRY_ENABLED = os.getenv("RETRY_ENABLED", "true").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
RETRY_DELAY_MINUTES = int(os.getenv("RETRY_DELAY_MINUTES", "30"))

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# ============================================================================
# CLASSE CONFIG (pour import facile)
# ============================================================================
class Config:
    """Config - Simplifié et propre"""

    # Chemins
    BASE_DIR = BASE_DIR
    AUDIO_DIR = AUDIO_DIR
    LOGS_DIR = LOGS_DIR
    EXPORTS_DIR = EXPORTS_DIR
    RECORDINGS_DIR = RECORDINGS_DIR
    FREESWITCH_SOUNDS_DIR = FREESWITCH_SOUNDS_DIR
    DEFAULT_VOICE = DEFAULT_VOICE

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

    # AMD
    AMD_ENABLED = AMD_ENABLED
    AMD_LISTEN_DURATION = AMD_LISTEN_DURATION
    AMD_WORD_THRESHOLD = AMD_WORD_THRESHOLD
    AMD_INITIAL_DELAY = AMD_INITIAL_DELAY

    # Streaming ASR & VAD
    VAD_SILENCE_THRESHOLD = VAD_SILENCE_THRESHOLD
    VAD_SPEECH_START_THRESHOLD = VAD_SPEECH_START_THRESHOLD
    WEBSOCKET_HOST = WEBSOCKET_HOST
    WEBSOCKET_PORT = WEBSOCKET_PORT

    # Barge-In (SIMPLE)
    BARGE_IN_ENABLED = BARGE_IN_ENABLED
    BARGE_IN_DURATION_THRESHOLD = BARGE_IN_DURATION_THRESHOLD
    GRACE_PERIOD_SECONDS = GRACE_PERIOD_SECONDS
    SMOOTH_DELAY_SECONDS = SMOOTH_DELAY_SECONDS
    BARGE_IN_SMOOTH_DELAY = BARGE_IN_SMOOTH_DELAY

    # Appels
    MAX_SIMULTANEOUS_CALLS = MAX_SIMULTANEOUS_CALLS
    CALL_TIMEOUT_SECONDS = CALL_TIMEOUT_SECONDS
    RETRY_ENABLED = RETRY_ENABLED
    MAX_RETRIES = MAX_RETRIES
    RETRY_DELAY_MINUTES = RETRY_DELAY_MINUTES

    # Logging
    LOG_LEVEL = LOG_LEVEL
    LOG_FORMAT = LOG_FORMAT

# Instance globale
config = Config()
