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
# FreeSWITCH recordings - Utiliser répertoire natif FreeSWITCH
# Avantages: permissions correctes, pas de header WAV corrompu, standard FreeSWITCH
RECORDINGS_DIR = Path(os.getenv(
    "FREESWITCH_RECORDINGS_DIR",
    "/usr/local/freeswitch/recordings"
))

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
FREESWITCH_CALLER_ID = os.getenv("FREESWITCH_CALLER_ID", "33609907845")

# ============================================================================
# IA SERVICES
# ============================================================================
# Vosk STT
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-fr-0.6-linto-2.2.0")
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
# VAD MODES - 3 comportements distincts (Best Practices 2025)
# ============================================================================

# MODE 1: AMD (Answering Machine Detection)
# Objectif: Détecter HUMAN vs MACHINE rapidement
# Comportement: Transcrire TOUT (même "allô", bip, silence), pas de seuil minimum
AMD_TIMEOUT = 1.3  # secondes (ultra agressive! test limite minimal)
AMD_MIN_SPEECH_DURATION = 0.3  # secondes - Détecter dès 300ms de parole
AMD_TRANSCRIBE_ALL = True  # Tout transcrire pour NLP

# MODE 2: PLAYING_AUDIO (Barge-in intelligent)
# Objectif: Détecter vraies interruptions vs. backchannels ("oui", "ok", "hum")
# Comportement: Transcrire TOUT en continu, barge-in si parole >= 2.5s
PLAYING_BARGE_IN_THRESHOLD = 2.5  # secondes - Parole continue >= 2.5s = barge-in
PLAYING_BACKCHANNEL_MAX = 0.8  # secondes - Parole < 0.8s = backchannel (logger seulement)
PLAYING_SILENCE_RESET = 2.0  # secondes - Reset compteur si silence >= 2.0s (filtre backchannels multiples)
PLAYING_TRANSCRIBE_ALL = True  # Transcrire tous les segments (même backchannels)
PLAYING_SMOOTH_DELAY = 1.0  # secondes - Délai avant interruption (finir phrase naturellement)

# MODE 3: WAITING_RESPONSE (End-of-speech detection)
# Objectif: Détecter début/fin de parole, transcrire réponse complète
# Comportement: Détecter début parole dès 300ms, fin si silence >= 1.0s
WAITING_TIMEOUT = 10.0  # secondes - Timeout total avant retry_silence
WAITING_MIN_SPEECH_DURATION = 0.3  # secondes - Détecter début parole
WAITING_END_OF_SPEECH_SILENCE = 1.0  # secondes - Silence pour fin de parole (optimisé: réactif mais safe)
WAITING_TRANSCRIBE_CONTINUOUS = True  # Transcrire pendant que client parle (latence minimale)

# Compatibilité ancienne config (DEPRECATED - utiliser configs spécifiques ci-dessus)
BARGE_IN_ENABLED = True
BARGE_IN_DURATION_THRESHOLD = PLAYING_BARGE_IN_THRESHOLD
BARGE_IN_SILENCE_RESET = PLAYING_SILENCE_RESET
GRACE_PERIOD_SECONDS = 2.0  # Grace period au début audio (à retirer si non utilisé)
SMOOTH_DELAY_SECONDS = PLAYING_SMOOTH_DELAY
BARGE_IN_SMOOTH_DELAY = PLAYING_SMOOTH_DELAY

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
    FREESWITCH_CALLER_ID = FREESWITCH_CALLER_ID

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

    # VAD Modes (3 comportements distincts)
    # Mode 1: AMD (1.3s ultra agressive!)
    AMD_TIMEOUT = AMD_TIMEOUT
    AMD_MIN_SPEECH_DURATION = AMD_MIN_SPEECH_DURATION
    AMD_TRANSCRIBE_ALL = AMD_TRANSCRIBE_ALL

    # Mode 2: PLAYING_AUDIO
    PLAYING_BARGE_IN_THRESHOLD = PLAYING_BARGE_IN_THRESHOLD
    PLAYING_BACKCHANNEL_MAX = PLAYING_BACKCHANNEL_MAX
    PLAYING_SILENCE_RESET = PLAYING_SILENCE_RESET
    PLAYING_TRANSCRIBE_ALL = PLAYING_TRANSCRIBE_ALL
    PLAYING_SMOOTH_DELAY = PLAYING_SMOOTH_DELAY

    # Mode 3: WAITING_RESPONSE
    WAITING_TIMEOUT = WAITING_TIMEOUT
    WAITING_MIN_SPEECH_DURATION = WAITING_MIN_SPEECH_DURATION
    WAITING_END_OF_SPEECH_SILENCE = WAITING_END_OF_SPEECH_SILENCE
    WAITING_TRANSCRIBE_CONTINUOUS = WAITING_TRANSCRIBE_CONTINUOUS

    # Compatibilité ancienne config (DEPRECATED)
    BARGE_IN_ENABLED = BARGE_IN_ENABLED
    BARGE_IN_DURATION_THRESHOLD = BARGE_IN_DURATION_THRESHOLD
    BARGE_IN_SILENCE_RESET = BARGE_IN_SILENCE_RESET
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
