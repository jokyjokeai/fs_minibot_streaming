# -*- coding: utf-8 -*-
"""
Configuration Manager - MiniBotPanel v3 FILE-BASED Optimized

Configuration centralis�e pour le robot d'appel marketing automatis�.

Architecture 3 PHASES :
- Phase 1 : AMD (Answering Machine Detection)
- Phase 2 : PLAYING AUDIO (avec barge-in VAD)
- Phase 3 : WAITING RESPONSE (�coute client)

Optimisations latence :
- Intent detection via KEYWORDS (NO Ollama) � -200 � -400ms
- Barge-in VAD sans transcription � -100ms
- Faster-Whisper GPU batch processing � -50 � -100ms
- FILE-BASED mode (fiable, pas de WebSocket drops)

Objectif : Conversation INSTANTAN�E, FLUIDE, NATURELLE (<1s par cycle)
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 1. ENVIRONNEMENT & CHEMINS
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Base directory (racine du projet)
BASE_DIR = Path(__file__).parent.parent.resolve()

# Dossiers principaux
LOGS_DIR = BASE_DIR / "logs"
AUDIO_DIR = BASE_DIR / "audio"
RECORDINGS_DIR = BASE_DIR / "audio_recordings"
SCENARIOS_DIR = BASE_DIR / "scenarios"
MODELS_DIR = BASE_DIR / "models"

# Cr�er dossiers si inexistants
for directory in [LOGS_DIR, AUDIO_DIR, RECORDINGS_DIR, SCENARIOS_DIR, MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 2. FREESWITCH ESL (Event Socket Layer)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

FREESWITCH_ESL_HOST = os.getenv("FREESWITCH_ESL_HOST", "127.0.0.1")
FREESWITCH_ESL_PORT = int(os.getenv("FREESWITCH_ESL_PORT", 8021))
FREESWITCH_ESL_PASSWORD = os.getenv("FREESWITCH_ESL_PASSWORD", "ClueCon")

# FreeSWITCH sounds directory (for processed audio files)
# Path where setup_audio.py copies normalized 8kHz µ-law audio files
FREESWITCH_SOUNDS_DIR = os.getenv(
    "FREESWITCH_SOUNDS_DIR",
    "/usr/share/freeswitch/sounds/minibot"
)

# Timeouts ESL
ESL_CONNECT_TIMEOUT = 5  # secondes
ESL_RECONNECT_DELAY = 3  # secondes
ESL_MAX_RECONNECT_ATTEMPTS = 5


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 3. POSTGRESQL DATABASE
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://minibot:minibot@localhost:5432/minibot"
)


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 4. GPU AUTO-DETECTION (Faster-Whisper)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

def _detect_gpu_device() -> str:
    """
    D�tecte automatiquement si GPU CUDA disponible pour Faster-Whisper.

    Returns:
        "cuda" si GPU disponible, sinon "cpu"
    """
    try:
        import torch
        if not torch.cuda.is_available():
            logger.warning("�  CUDA not available, using CPU (slower)")
            return "cpu"

        # V�rifier CTranslate2 (requis pour Faster-Whisper)
        try:
            from ctranslate2 import __version__
            logger.info(f" GPU CUDA detected, CTranslate2 {__version__}")
            return "cuda"
        except ImportError:
            logger.warning("�  CTranslate2 not found, using CPU")
            return "cpu"
    except ImportError:
        logger.warning("�  PyTorch not found, using CPU")
        return "cpu"


DEVICE = _detect_gpu_device()


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 5. PHASE 1 - AMD (Answering Machine Detection)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Dur�e max d'�coute pour AMD (en secondes)
AMD_MAX_DURATION = 2.5  # Extended timing (comfortable margin for late speakers + speech_end detection)

# Keywords pour d�tecter HUMAIN
AMD_KEYWORDS_HUMAN = [
    # Salutations basiques
    "all�", "allo", "oui", "ouais", "bonjour", "bonsoir",

    # Variations apostrophes (Unicode ' vs ASCII ')
    "j'�coute", "j ecoute", "je vous �coute", "je vous ecoute",

    # Questions identificatoires
    "qui", "quoi", "c'est qui", "c est qui"
]

# Keywords pour d�tecter R�PONDEUR/MACHINE
AMD_KEYWORDS_MACHINE = [
    # Messages répondeur classiques
    "messagerie", "repondeur", "message", "bip", "signal sonore",
    "laissez", "apres le bip", "absent", "indisponible",
    "rappeler", "vous etes bien", "bonjour vous etes",

    # Opérateurs télécom français
    "sfr", "orange", "free", "bouygues",

    # Variations phonétiques opérateurs (transcription Whisper)
    "c'est fer", "c est fer", "ses fers",  # SFR mal transcrit
    "au range", "hors range",  # Orange
    "fri", "fry",  # Free

    # Messages vocaux
    "vocal", "vocale", "boite vocale", "boîte vocale",

    # Indisponibilité
    "ne peut pas repondre", "ne peux pas repondre", "pas disponible",
    "ne suis pas disponible", "joignable", "injoignable",
    "momentanement absent",

    # === PHONE NUMBERS (CRITICAL FIX) ===
    # Préfixes numériques français (mobiles + fixes)
    "06", "07",  # Mobiles
    "01", "02", "03", "04", "05", "08", "09",  # Fixes + autres

    # Formes parlées des préfixes
    "zero six", "zero six", "zero sept", "zero sept",
    "zero un", "zero un", "zero deux", "zero deux",
    "zero trois", "zero trois", "zero quatre", "zero quatre",
    "zero cinq", "zero cinq", "zero huit", "zero huit",
    "zero neuf", "zero neuf",

    # Contexte téléphone (phrases indicatrices)
    "repondeur du", "numero", "numero de",
    "joindre au", "rappeler au", "contacter au", "appeler au",

    # === BEEP VARIATIONS ===
    "beep", "biiip", "biip", "bep",
    "top sonore", "apres le signal", "apres la tonalite",
    "tonalite", "apres le top",

    # === ADDITIONAL MACHINE PHRASES ===
    "je ne suis pas la", "actuellement", "pour le moment",
    "en ce moment", "veuillez laisser", "merci de laisser",
    "laissez votre", "un message apres", "votre message"
]

# Timeout silence AMD (si aucun son d�tect�)
AMD_SILENCE_TIMEOUT = 2.0  # secondes

# Confidence minimum pour consid�rer d�tection valide
AMD_MIN_CONFIDENCE = 0.5


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 6. PHASE 2 - PLAYING AUDIO (Barge-in)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Barge-in activ� par d�faut
BARGE_IN_ENABLED = True

# Seuil de parole pour d�clencher barge-in (en secondes)
# Parole <1.5s (respirations, "oui", "non") � ignor�e
# Parole e1.5s � barge-in d�clench�
BARGE_IN_THRESHOLD = 1.5

# Smooth delay apr�s d�tection barge-in (pour naturel)
# Robot coupe pas direct, attend 0.5s pour effet naturel
# NOTE: Fade-out progressif appliqu� pendant ce d�lai (0 dB -> -40 dB en 10 steps)
BARGE_IN_SMOOTH_DELAY = 0.5

# Breathing room apr�s speech_end (pause naturelle)
# Petit d�lai avant Phase 3 pour effet humain (100ms)
BARGE_IN_BREATHING_ROOM = 0.1

# Minimum words for barge-in detection
# Client doit dire au moins 5 mots pour d�clencher barge-in
# (�vite faux positifs sur "oui", "ok", "all�", etc.)
MIN_WORDS_FOR_BARGE_IN = 5

# Dur�e minimale de parole pour d�tecter "start speech" (en secondes)
# Evite faux positifs (bruits, respirations courtes)
PLAYING_START_SPEECH_DURATION = 0.3

# D�clencheur background transcription (en secondes)
# Apr�s 0.5s de parole client � lance thread transcription snapshot
PLAYING_BG_TRANSCRIBE_TRIGGER = 0.5

# VAD aggressiveness (0-3, 3 = plus agressif)
VAD_AGGRESSIVENESS = 3

# Phase 2 → Phase 3 transition optimization
# Arrêter monitoring Phase 2 X secondes AVANT fin audio
# Permet de démarrer Phase 3 plus tôt (écoute pendant dernière seconde audio)
# Gain de réactivité sans threading complexe
PHASE2_EARLY_EXIT = 1.0  # Stop Phase 2 monitoring 1s before audio ends


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 7. PHASE 3 - WAITING RESPONSE (�coute client)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Seuil de silence pour d�tecter fin de parole client (en secondes)
# Client parle � silence 0.6s � consid�r� comme "fini de parler"
SILENCE_THRESHOLD = 1.5  # Changed from 0.6s to 1.5s for better silence detection

# Timeout max d'attente pour r�ponse client (en secondes)
WAITING_TIMEOUT = 10.0

# Timeout silence client (pour retry_silence après robot parle)
# Si client ne dit rien pendant 3.7s → retry_silence
WAITING_SILENCE_TIMEOUT = 3.7

# Dur�e minimale de parole pour d�tecter "start speech" (en secondes)
WAITING_START_SPEECH_DURATION = 0.3

# D�clencheur background transcription (en secondes)
# Apr�s 0.5s de parole client � lance thread transcription snapshot
WAITING_BG_TRANSCRIBE_TRIGGER = 0.5

# Nombre max de silences cons�cutifs avant hangup NO_ANSWER
MAX_CONSECUTIVE_SILENCES = 2

# Nombre max de "no match" objections cons�cutifs avant hangup
MAX_CONSECUTIVE_NO_MATCH = 3


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 8. STT - FASTER-WHISPER (Speech-to-Text)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Mod�le Faster-Whisper
# Options : "tiny", "base", "small", "medium", "large-v2", "large-v3"
# Recommandation : "small" (meilleur sur audio dégradé)
FASTER_WHISPER_MODEL = os.getenv("FASTER_WHISPER_MODEL", "small")

# Device (auto-d�tect�)
FASTER_WHISPER_DEVICE = os.getenv("FASTER_WHISPER_DEVICE", "cpu")  # Forcé CPU pour éviter crash cuDNN

# Compute type (GPU optimis�)
# Options : "float16" (GPU rapide), "int8" (CPU rapide), "float32" (pr�cis mais lent)
FASTER_WHISPER_COMPUTE_TYPE = "float16" if FASTER_WHISPER_DEVICE == "cuda" else "int8"

# Langue
FASTER_WHISPER_LANGUAGE = "fr"

# Beam size (pr�cision transcription, 1-10)
# Plus �lev� = plus pr�cis mais plus lent
# Recommandation : 3 pour bon compromis pr�cision/vitesse (r�duit hallucinations)
FASTER_WHISPER_BEAM_SIZE = 3

# VAD filter (supprime silences avant/apr�s)
FASTER_WHISPER_VAD_FILTER = True

# Noise Reduction (noisereduce library)
# Active la réduction de bruit avant transcription STT
# Améliore significativement la qualité sur audio téléphonique bruité
NOISE_REDUCE_ENABLED = os.getenv("NOISE_REDUCE_ENABLED", "true").lower() == "true"

# Force de la réduction de bruit (0.0 à 2.0)
# 0.0 = pas de réduction, 1.0 = normal, 2.0 = agressif
# Recommandation: 0.8-1.2 pour audio téléphonique
NOISE_REDUCE_STRENGTH = float(os.getenv("NOISE_REDUCE_STRENGTH", "1.0"))


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 9. VAD - WEBRTC (Voice Activity Detection)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Aggressiveness VAD (0-3)
# 0 = moins agressif (d�tecte + de parole, risque faux positifs)
# 3 = plus agressif (d�tecte uniquement parole claire)
# Recommandation : 3 pour barge-in r�actif sans faux positifs
WEBRTC_VAD_AGGRESSIVENESS = 3

# Frame duration pour VAD (millisecondes)
# Options : 10, 20, 30
# Recommandation : 30 (balance r�activit�/fiabilit�)
WEBRTC_VAD_FRAME_DURATION_MS = 30

# Sample rate pour VAD (Hz)
# Doit �tre 8000, 16000, 32000, ou 48000
WEBRTC_VAD_SAMPLE_RATE = 8000

# Noise Gate Dynamique (réduction bruit de fond pour Vosk streaming)
# Active/désactive le noise gate
NOISE_GATE_ENABLED = os.getenv("NOISE_GATE_ENABLED", "true").lower() == "true"

# Seuil en dB pour ouvrir le gate (plus bas = plus sensible)
# -35dB = bon pour téléphonie, -30dB = moins sensible, -40dB = très sensible
NOISE_GATE_THRESHOLD_DB = float(os.getenv("NOISE_GATE_THRESHOLD_DB", "-35"))

# Atténuation en dB quand gate fermé (plus négatif = plus d'atténuation)
# -40dB = quasi silence, -20dB = atténuation légère
NOISE_GATE_ATTENUATION_DB = float(os.getenv("NOISE_GATE_ATTENUATION_DB", "-40"))

# Attack en ms (temps pour ouvrir le gate - rapide pour ne pas couper début de parole)
NOISE_GATE_ATTACK_MS = float(os.getenv("NOISE_GATE_ATTACK_MS", "5"))

# Release en ms (temps pour fermer le gate - plus lent pour éviter coupures)
NOISE_GATE_RELEASE_MS = float(os.getenv("NOISE_GATE_RELEASE_MS", "50"))


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 10. INTENT DETECTION - KEYWORDS MATCHING (NO Ollama)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# FIXED EXPRESSIONS (Multi-Word Expressions) - PRIORITE ABSOLUE
# Ces expressions doivent etre detectees AVANT les keywords simples
# Basees sur best practices NLP: MWEs representent 30-50% du vocabulaire
FIXED_EXPRESSIONS: Dict[str, List[str]] = {
    # Affirm: Expressions positives multi-mots
    "affirm": [
        "pourquoi pas",      # vs "pourquoi" (question)
        "pas mal",           # vs "mal" (negatif)
        "pas bete",          # vs "bete" (negatif)
        "ca m'interesse",    # vs "ca m'interesse pas" (deny)
        "bien sur",          # expression complete
        "tout a fait",       # expression complete
        "avec plaisir",      # expression complete
        "bien entendu",      # expression complete
        "d'accord",          # expression complete
        "allons-y",          # expression complete
    ],

    # Deny: Negations d'expressions positives
    "deny": [
        "ca marche pas",        # vs "ca marche" (affirm)
        "ca m'interesse pas",   # vs "ca m'interesse" (affirm)
        "ca va pas",            # vs "ca va" (affirm)
        "pas vraiment",         # negation de "vraiment"
        "peut-etre pas",        # negation de "peut-etre"
        "pas pour moi",         # vs "pour moi" (affirm)
        "pas question",         # vs "question" (question)
        "hors de question",     # vs "question" (question)
        "pas du tout",          # negation forte
        "pas interesse",        # negation
        "non merci",            # refus poli
        "jamais de la vie",     # refus fort
        "absolument pas",       # negation forte
        "en aucun cas",         # negation forte
        "surtout pas",          # negation forte
    ],

    # Question: Questions avec mots affirm
    "question": [
        "comment ca marche",    # vs "ca marche" (affirm)
        "ca marche comment",    # vs "ca marche" (affirm)
        "pourquoi ca",          # question avec "ca"
        "c'est quoi",           # question complete
        "qu'est-ce que",        # question complete
        "combien ca coute",     # question complete
        "comment ca",           # question avec "ca"
    ],

    # Unsure: Expressions d'hesitation
    "unsure": [
        "je sais pas",          # vs "je sais" (affirm potentiel)
        "sais pas trop",        # hesitation
        "faut voir",            # hesitation
        "on verra",             # hesitation
    ]
}

# NEGATION WORDS - Detection negations francais parle (sans "ne")
# Basees sur research NLP francais: "ne" souvent omis en parle
NEGATION_WORDS: List[str] = [
    "non", "pas", "jamais", "aucun", "aucune", "rien"
]

# NEGATION PHRASES - Negations explicites (override tout)
NEGATION_PHRASES: List[str] = [
    "non merci",
    "pas du tout",
    "absolument pas",
    "hors de question",
    "jamais de la vie",
    "en aucun cas",
    "surtout pas"
]

# INTERROGATIVE WORDS - Mots interrogatifs en debut de phrase
# Si detectes en position 0-2, override intent = "question"
# Exception: "pourquoi pas" (expression figee affirm)
# Note: "ou" retire (trop ambigu - match dans "pour", "beaucoup", etc.)
INTERROGATIVE_WORDS: List[str] = [
    "comment", "pourquoi", "combien", "quoi",
    "quel", "quelle", "qui", "quand"
]

# Mapping keywords � intent
# Optimisation : keywords matching au lieu d'Ollama (gain -200 � -400ms)
INTENT_KEYWORDS: Dict[str, List[str]] = {
    # Intent 1: AFFIRM (acceptation positive)
    # Mots ambigus retires: "interesse", "ca m'interesse", "ca marche"
    # (maintenant dans FIXED_EXPRESSIONS uniquement)
    "affirm": [
        "oui", "ok", "daccord", "parfait", "volontiers",
        "tres bien", "entendu", "certainement",
        "curieux", "je veux bien", "attentif",
        # Nouveaux mots surs
        "go", "allez-y", "banco", "carrementx",
        "nickel", "super", "genial", "top",
        "evidemment", "absolument"
    ],

    # Intent 2: DENY (refus/rejet)
    # Renforce avec +10 keywords pour detecter refus/negations
    "deny": [
        "non", "jamais", "arretez", "stop",
        # Nouveaux keywords negations
        "aucune", "refuse", "je refuse", "hors sujet",
        "ca va aller", "c'est bon", "laissez",
        "pas trop", "pas tellement", "vraiment pas"
    ],

    # Intent 3: UNSURE (hesitation)
    # Ajoute +6 keywords pour mieux detecter hesitations
    "unsure": [
        "peut-etre", "hesite", "voir", "reflechir",
        "penser", "hesiter", "doute",
        # Nouveaux keywords hesitation
        "bof", "mouais", "euh",
        "je vois", "je sais plus", "chais pas",
        "sais pas vraiment", "pas sur"
    ],

    # Intent 4: QUESTION (demande information)
    # Ajoute +7 keywords pour mieux detecter questions
    "question": [
        "comment", "pourquoi", "combien", "quoi", "quelle", "quel",
        "expliquer", "details", "fonctionnement", "preciser",
        # Nouveaux keywords questions ("ou" retire - trop ambigu)
        "qui", "quand",
        "dites-moi", "expliquez-moi", "je comprends pas",
        "exemple", "par exemple", "ca veut dire quoi"
    ],

    # Intent 5: OBJECTION (objection specifique - pour ObjectionMatcher)
    "objection": [
        # Prix / Budget
        "cher", "prix", "cout", "budget", "argent",
        "trop cher", "hors de prix", "pas les moyens",

        # Temps
        "temps", "occupe", "pas le temps", "plus tard", "rappeler",
        "derangez", "moment", "disponible", "rappel", "recontacter",

        # Confiance
        "arnaque", "serieux", "fiable", "confiance", "mefiance",

        # Deja equipe
        "deja", "ai deja", "possede deja", "equipe",

        # Autres objections
        "pas maintenant", "autre moment"
    ]
}

# Intent par d�faut si aucun keyword match�
DEFAULT_INTENT = "unsure"

# Poids minimum de matching pour consid�rer intent valide
# Ex: si 2 keywords "affirm" et 1 keyword "deny" � affirm (2 > 1)
INTENT_MIN_WEIGHT = 1


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 11. OBJECTION MATCHER
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Score minimum pour consid�rer match valide (0.0-1.0)
# 0.6 = 60% similarit� minimum
OBJECTION_MIN_SCORE = 0.6

# Score "high confidence" (e0.8) vs "medium confidence" (0.6-0.8)
OBJECTION_HIGH_CONFIDENCE_THRESHOLD = 0.8

# Top N candidats � �valuer (optimisation)
OBJECTION_TOP_N = 3


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 12. AUDIO SETTINGS (FreeSWITCH)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Sample rate t�l�phonie standard
AUDIO_SAMPLE_RATE = 8000  # Hz

# Channels (MONO = �vite echo, robot n'entend pas sa propre voix)
AUDIO_CHANNELS = 1  # Mono

# Format audio
AUDIO_FORMAT = "wav"

# Codec FreeSWITCH (G.711 �-law pour t�l�phonie)
AUDIO_CODEC = "PCMU"

# R�pertoire audios pr�-enregistr�s
PRERECORDED_AUDIO_DIR = AUDIO_DIR / "prerecorded"
PRERECORDED_AUDIO_DIR.mkdir(exist_ok=True)


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 13. LOGGING
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Niveau de log (DEBUG pour d�veloppement, INFO pour production)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Format logs (JSON structur� pour parsing)
LOG_FORMAT_JSON = True

# Logs d�taill�s avec latences
LOG_LATENCIES = True

# R�pertoires logs
LOG_CALLS_DIR = LOGS_DIR / "calls"
LOG_SYSTEM_DIR = LOGS_DIR / "system"
LOG_PERFORMANCE_DIR = LOGS_DIR / "performance"

for log_dir in [LOG_CALLS_DIR, LOG_SYSTEM_DIR, LOG_PERFORMANCE_DIR]:
    log_dir.mkdir(exist_ok=True)

# R�tention logs (jours)
LOG_RETENTION_DAYS = 30

# R�tention fichiers audio enregistr�s (jours)
AUDIO_RETENTION_DAYS = 7


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 14. QUALIFICATIONS LEADS
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Statuts possibles pour qualification leads
LEAD_STATUS_NEW = "NEW"  # Initial
LEAD_STATUS_NO_ANSWER = "NO_ANSWER"  # Pas de r�ponse, rappeler
LEAD_STATUS_NOT_INTERESTED = "NOT_INTERESTED"  # Pas int�ress�
LEAD_STATUS_LEAD = "LEAD"  # Qualifi� comme lead



# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 15. VOSK / STREAMING ASR (WebSocket)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Vosk model path (French model)
VOSK_MODEL_PATH = os.getenv(
    "VOSK_MODEL_PATH",
    "/usr/share/vosk/model-fr"  # Default: vosk-model-small-fr-0.22
)

# Vosk sample rate (streaming ASR uses 16kHz for better quality)
VOSK_SAMPLE_RATE = 16000  # 16kHz for streaming ASR

# Streaming ASR WebSocket server configuration
STREAMING_ASR_ENABLED = os.getenv("STREAMING_ASR_ENABLED", "True").lower() in ("true", "1", "yes")
STREAMING_ASR_HOST = os.getenv("STREAMING_ASR_HOST", "127.0.0.1")
STREAMING_ASR_PORT = int(os.getenv("STREAMING_ASR_PORT", "8080"))

# VAD configuration for streaming ASR
VAD_AGGRESSIVENESS = 2  # 0-3, 2 = balanced quality/reactivity
VAD_SILENCE_THRESHOLD_MS = 500  # 500ms silence = end of speech (réactivité optimisée)
VAD_SPEECH_START_THRESHOLD_MS = 500  # 500ms speech = start detected

# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# 16. CONFIGURATION OBJECT (pour compatibilit�)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

class Config:
    """Configuration object pour acc�s via config.PARAM_NAME"""

    # Chemins
    BASE_DIR = BASE_DIR
    LOGS_DIR = LOGS_DIR
    AUDIO_DIR = AUDIO_DIR
    RECORDINGS_DIR = RECORDINGS_DIR
    SCENARIOS_DIR = SCENARIOS_DIR
    MODELS_DIR = MODELS_DIR

    # FreeSWITCH
    FREESWITCH_ESL_HOST = FREESWITCH_ESL_HOST
    FREESWITCH_ESL_PORT = FREESWITCH_ESL_PORT
    FREESWITCH_ESL_PASSWORD = FREESWITCH_ESL_PASSWORD
    FREESWITCH_SOUNDS_DIR = FREESWITCH_SOUNDS_DIR
    ESL_CONNECT_TIMEOUT = ESL_CONNECT_TIMEOUT
    ESL_RECONNECT_DELAY = ESL_RECONNECT_DELAY
    ESL_MAX_RECONNECT_ATTEMPTS = ESL_MAX_RECONNECT_ATTEMPTS

    # Database
    DATABASE_URL = DATABASE_URL

    # GPU
    DEVICE = DEVICE

    # Phase 1 - AMD
    AMD_MAX_DURATION = AMD_MAX_DURATION
    AMD_KEYWORDS_HUMAN = AMD_KEYWORDS_HUMAN
    AMD_KEYWORDS_MACHINE = AMD_KEYWORDS_MACHINE
    AMD_SILENCE_TIMEOUT = AMD_SILENCE_TIMEOUT
    AMD_MIN_CONFIDENCE = AMD_MIN_CONFIDENCE

    # Phase 2 - Playing (Barge-in)
    BARGE_IN_ENABLED = BARGE_IN_ENABLED
    BARGE_IN_THRESHOLD = BARGE_IN_THRESHOLD
    BARGE_IN_SMOOTH_DELAY = BARGE_IN_SMOOTH_DELAY
    BARGE_IN_BREATHING_ROOM = BARGE_IN_BREATHING_ROOM
    MIN_WORDS_FOR_BARGE_IN = MIN_WORDS_FOR_BARGE_IN
    PLAYING_START_SPEECH_DURATION = PLAYING_START_SPEECH_DURATION
    PLAYING_BG_TRANSCRIBE_TRIGGER = PLAYING_BG_TRANSCRIBE_TRIGGER
    VAD_AGGRESSIVENESS = VAD_AGGRESSIVENESS
    PHASE2_EARLY_EXIT = PHASE2_EARLY_EXIT

    # Phase 3 - Waiting
    SILENCE_THRESHOLD = SILENCE_THRESHOLD
    WAITING_TIMEOUT = WAITING_TIMEOUT
    WAITING_SILENCE_TIMEOUT = WAITING_SILENCE_TIMEOUT
    WAITING_START_SPEECH_DURATION = WAITING_START_SPEECH_DURATION
    WAITING_BG_TRANSCRIBE_TRIGGER = WAITING_BG_TRANSCRIBE_TRIGGER
    MAX_CONSECUTIVE_SILENCES = MAX_CONSECUTIVE_SILENCES
    MAX_CONSECUTIVE_NO_MATCH = MAX_CONSECUTIVE_NO_MATCH

    # STT
    FASTER_WHISPER_MODEL = FASTER_WHISPER_MODEL
    FASTER_WHISPER_DEVICE = FASTER_WHISPER_DEVICE
    FASTER_WHISPER_COMPUTE_TYPE = FASTER_WHISPER_COMPUTE_TYPE
    FASTER_WHISPER_LANGUAGE = FASTER_WHISPER_LANGUAGE
    FASTER_WHISPER_BEAM_SIZE = FASTER_WHISPER_BEAM_SIZE
    FASTER_WHISPER_VAD_FILTER = FASTER_WHISPER_VAD_FILTER
    NOISE_REDUCE_ENABLED = NOISE_REDUCE_ENABLED
    NOISE_REDUCE_STRENGTH = NOISE_REDUCE_STRENGTH

    # VAD
    WEBRTC_VAD_AGGRESSIVENESS = WEBRTC_VAD_AGGRESSIVENESS
    WEBRTC_VAD_FRAME_DURATION_MS = WEBRTC_VAD_FRAME_DURATION_MS
    WEBRTC_VAD_SAMPLE_RATE = WEBRTC_VAD_SAMPLE_RATE

    # Noise Gate
    NOISE_GATE_ENABLED = NOISE_GATE_ENABLED
    NOISE_GATE_THRESHOLD_DB = NOISE_GATE_THRESHOLD_DB
    NOISE_GATE_ATTENUATION_DB = NOISE_GATE_ATTENUATION_DB
    NOISE_GATE_ATTACK_MS = NOISE_GATE_ATTACK_MS
    NOISE_GATE_RELEASE_MS = NOISE_GATE_RELEASE_MS

    # Intent Keywords
    INTENT_KEYWORDS = INTENT_KEYWORDS
    DEFAULT_INTENT = DEFAULT_INTENT
    INTENT_MIN_WEIGHT = INTENT_MIN_WEIGHT

    # Intent Detection BETON ARME (nouvelles constantes)
    FIXED_EXPRESSIONS = FIXED_EXPRESSIONS
    NEGATION_WORDS = NEGATION_WORDS
    NEGATION_PHRASES = NEGATION_PHRASES
    INTERROGATIVE_WORDS = INTERROGATIVE_WORDS

    # Objection Matcher
    OBJECTION_MIN_SCORE = OBJECTION_MIN_SCORE
    OBJECTION_HIGH_CONFIDENCE_THRESHOLD = OBJECTION_HIGH_CONFIDENCE_THRESHOLD
    OBJECTION_TOP_N = OBJECTION_TOP_N

    # Audio
    AUDIO_SAMPLE_RATE = AUDIO_SAMPLE_RATE
    AUDIO_CHANNELS = AUDIO_CHANNELS
    AUDIO_FORMAT = AUDIO_FORMAT
    AUDIO_CODEC = AUDIO_CODEC
    PRERECORDED_AUDIO_DIR = PRERECORDED_AUDIO_DIR

    # Logging
    LOG_LEVEL = LOG_LEVEL
    LOG_FORMAT_JSON = LOG_FORMAT_JSON
    LOG_LATENCIES = LOG_LATENCIES
    LOG_CALLS_DIR = LOG_CALLS_DIR
    LOG_SYSTEM_DIR = LOG_SYSTEM_DIR
    LOG_PERFORMANCE_DIR = LOG_PERFORMANCE_DIR
    LOG_RETENTION_DAYS = LOG_RETENTION_DAYS
    AUDIO_RETENTION_DAYS = AUDIO_RETENTION_DAYS

    # Leads
    LEAD_STATUS_NEW = LEAD_STATUS_NEW
    LEAD_STATUS_NO_ANSWER = LEAD_STATUS_NO_ANSWER
    LEAD_STATUS_NOT_INTERESTED = LEAD_STATUS_NOT_INTERESTED
    LEAD_STATUS_LEAD = LEAD_STATUS_LEAD

    # Vosk / Streaming ASR
    VOSK_MODEL_PATH = VOSK_MODEL_PATH
    VOSK_SAMPLE_RATE = VOSK_SAMPLE_RATE
    STREAMING_ASR_ENABLED = STREAMING_ASR_ENABLED
    STREAMING_ASR_HOST = STREAMING_ASR_HOST
    STREAMING_ASR_PORT = STREAMING_ASR_PORT
    VAD_AGGRESSIVENESS = VAD_AGGRESSIVENESS
    VAD_SILENCE_THRESHOLD_MS = VAD_SILENCE_THRESHOLD_MS
    VAD_SPEECH_START_THRESHOLD_MS = VAD_SPEECH_START_THRESHOLD_MS


# Instance globale
config = Config()
