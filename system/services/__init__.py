"""
Services IA Package - MiniBotPanel v3

Ce package contient tous les services d'intelligence artificielle:
- faster_whisper_stt.py : Speech-to-Text GPU (Faster-Whisper)
- vosk_asr.py : ASR streaming (mod_vosk FreeSWITCH integration)
- vosk_stt.py : Speech-to-Text fallback (Vosk standalone)
- amd_service.py : Answering Machine Detection (keywords matching)

Note: Intent detection est intégré dans robot_freeswitch.py (via INTENT_KEYWORDS du config)
"""

__version__ = "3.0.0"

# Exports
from system.services.faster_whisper_stt import FasterWhisperSTT
from system.services.amd_service import AMDService
from system.services.vosk_asr import VoskASR, create_vosk_service

__all__ = [
    "FasterWhisperSTT",
    "AMDService",
    "VoskASR",
    "create_vosk_service"
]
