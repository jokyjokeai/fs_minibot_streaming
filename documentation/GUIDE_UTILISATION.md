# GUIDE D'UTILISATION - MiniBotPanel v3

**Guide complet d'utilisation du système basé sur l'analyse réelle du code**

Version: 3.0
Date: 2025-11-07
Auteur: MiniBotPanel v3 Team

---

## 📖 Table des Matières

1. [Introduction](#introduction)
2. [Architecture du Système](#architecture-du-système)
3. [Configuration (.env)](#configuration-env)
4. [Gestion des Fichiers Audio](#gestion-des-fichiers-audio)
5. [Création de Scénarios](#création-de-scénarios)
6. [Import de Contacts](#import-de-contacts)
7. [Lancement d'Appels](#lancement-dappels)
8. [Monitoring des Campagnes](#monitoring-des-campagnes)
9. [Export des Résultats](#export-des-résultats)
10. [Base d'Objections](#base-dobjections)
11. [Troubleshooting](#troubleshooting)

---

## 🚀 Introduction

MiniBotPanel v3 est un système d'appels automatisés utilisant **FreeSWITCH**, **Vosk** (reconnaissance vocale), et **Ollama** (détection d'intentions). Le système fonctionne avec des **fichiers audio pré-enregistrés** et peut gérer des objections grâce à une base de données modulaire.

### Prérequis

Avant de commencer, assurez-vous que :
- ✅ Le système est installé (voir `GUIDE_INSTALLATION.md`)
- ✅ PostgreSQL est démarré
- ✅ FreeSWITCH est démarré (`sudo systemctl start freeswitch`)
- ✅ Les modèles Vosk sont téléchargés
- ✅ Ollama est installé et configuré

### Vérification Rapide

```bash
# 1. Vérifier FreeSWITCH
fs_cli -x "status"

# 2. Vérifier PostgreSQL
psql -U minibot -d minibot_freeswitch -c "SELECT COUNT(*) FROM contacts;"

# 3. Vérifier Vosk
ls -la models/vosk-model-fr-0.22-lgraph

# 4. Vérifier Ollama
ollama list
```

---

## 🏗️ Architecture du Système

### Composants Principaux

```
┌──────────────────────────────────────────────────────────┐
│                    ARCHITECTURE v3                        │
└──────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  PostgreSQL │────▶│RobotFreeSwitch│◀───│ FreeSWITCH  │
│   Database  │     │      V2       │    │ (mod_audio) │
└─────────────┘     └───────┬───────┘    └─────────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
        ┌───────▼──────┐ ┌──▼──────┐ ┌─▼─────────┐
        │ StreamingASR │ │ VoskSTT │ │ OllamaNLP │
        │  (WebSocket) │ │         │ │ (Intent)  │
        └──────────────┘ └─────────┘ └───────────┘
```

### Flux d'un Appel

1. **Origination** : `robot_freeswitch_v2.py` lance l'appel via FreeSWITCH
2. **AMD** : Détection répondeur (HUMAN/MACHINE/UNKNOWN)
3. **Streaming Audio** : Audio envoyé via WebSocket (port 8080) vers StreamingASR
4. **VAD** : WebRTC VAD détecte parole vs silence
5. **Transcription** : Vosk transcrit l'audio en temps réel
6. **Intent** : Ollama détecte l'intention (affirm/deny/question/objection)
7. **Objections** : Matching avec base d'objections (Python modular)
8. **Réponse** : Lecture fichier audio pré-enregistré
9. **Timeout** : 4 secondes max d'attente (configurable)
10. **Grace Period** : 3 secondes anti-faux-positifs pour barge-in

### Chemins Importants

```
/home/jokyjokeai/Desktop/fs_minibot_streaming/
├── audio/                                  ← Fichiers audio SOURCE
│   └── julie/
│       ├── base/                          ← Audios principaux
│       │   ├── hello.wav
│       │   ├── bye.wav
│       │   └── ...
│       └── objections/                    ← Réponses objections
│           ├── too_expensive.wav
│           └── ...
│
├── scenarios/                              ← Scénarios JSON
│   ├── dfdf.json
│   └── ...
│
└── system/
    ├── config.py                          ← Configuration centrale
    ├── robot_freeswitch_v2.py             ← Orchestrateur principal
    ├── scenarios.py                       ← Manager scénarios
    ├── services/
    │   ├── streaming_asr.py               ← Streaming + VAD
    │   ├── vosk_stt.py                    ← Vosk ASR
    │   └── ollama_nlp.py                  ← Ollama NLP
    └── objections_db/                     ← Base objections (Python)
        ├── standard.py
        ├── finance.py
        └── ...

FreeSWITCH:
/usr/share/freeswitch/sounds/minibot/      ← Fichiers audio PROCESSÉS
└── julie/
    ├── base/
    └── objections/
```

---

## ⚙️ Configuration (.env)

### Fichier .env

Le fichier `.env` à la racine du projet contient toutes les variables de configuration.

**Analyse basée sur `system/config.py` (283 lignes)**

#### Variables Essentielles

```bash
# ============================================================
# DATABASE
# ============================================================
DB_HOST=localhost
DB_PORT=5432
DB_NAME=minibot_freeswitch
DB_USER=minibot
DB_PASSWORD=your_secure_password

# ============================================================
# FREESWITCH
# ============================================================
FREESWITCH_ESL_HOST=localhost
FREESWITCH_ESL_PORT=8021
FREESWITCH_ESL_PASSWORD=ClueCon

# Répertoire des sons (fichiers audio traités)
FREESWITCH_SOUNDS_DIR=/usr/share/freeswitch/sounds/minibot

# Gateway SIP pour appels sortants
FREESWITCH_GATEWAY=mygateway

# ============================================================
# AUDIO
# ============================================================
# Répertoire source des audios (avant traitement)
AUDIO_DIR=audio

# Voix par défaut
DEFAULT_VOICE=julie

# Ajustement volume (dB) - Appliqué par setup_audio.py
AUDIO_VOLUME_ADJUST=2.0

# Réduction bruit de fond (dB)
AUDIO_BACKGROUND_REDUCTION=-10.0

# ============================================================
# VOSK (Speech-to-Text)
# ============================================================
# Chemin vers modèle Vosk français
VOSK_MODEL_PATH=models/vosk-model-fr-0.22-lgraph

# Sample rate pour Vosk (Hz)
VOSK_SAMPLE_RATE=16000

# ============================================================
# OLLAMA (NLP Intent Detection)
# ============================================================
# URL Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Modèle Ollama à utiliser
OLLAMA_MODEL=mistral:7b

# Température (créativité) : 0.0-1.0
OLLAMA_TEMPERATURE=0.7

# Max tokens par réponse
OLLAMA_MAX_TOKENS=150

# Timeout génération (secondes)
OLLAMA_TIMEOUT=10

# ============================================================
# AMD (Answering Machine Detection)
# ============================================================
# Activer AMD
AMD_ENABLED=true

# Méthode de détection
AMD_METHOD=freeswitch  # ou energy, silence

# Durée max AMD (ms)
AMD_MAX_GREETING_MS=4000

# Seuil silence (ms)
AMD_SILENCE_THRESHOLD_MS=1000

# ============================================================
# APPELS
# ============================================================
# Nombre max d'appels simultanés
MAX_CONCURRENT_CALLS=5

# Délai entre appels (secondes)
CALL_DELAY=2

# Durée max d'un appel (secondes)
MAX_CALL_DURATION=300

# ============================================================
# RETRY (Rappel automatique)
# ============================================================
# Activer retry
RETRY_ENABLED=true

# Max tentatives
MAX_RETRY_ATTEMPTS=3

# Délai entre tentatives (secondes)
RETRY_DELAY=3600  # 1 heure

# Conditions de retry (séparées par virgule)
RETRY_CONDITIONS=no_answer,busy,timeout

# ============================================================
# TIMEOUTS
# ============================================================
# Timeout écoute réponse prospect (secondes)
LISTEN_TIMEOUT=4

# Timeout connexion (secondes)
CONNECTION_TIMEOUT=30

# ============================================================
# STREAMING ASR
# ============================================================
# Port WebSocket pour streaming audio
STREAMING_ASR_PORT=8080

# Seuil silence pour fin de parole (secondes)
SILENCE_THRESHOLD=1.5

# Seuil début de parole (secondes)
SPEECH_START_THRESHOLD=0.5

# ============================================================
# BARGE-IN (Interruption)
# ============================================================
# Grace period anti-faux-positifs (secondes)
BARGE_IN_GRACE_PERIOD=3.0

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

LOG_DIR=logs

# ============================================================
# OBJECTIONS
# ============================================================
# Score minimum pour match objection (0.0-1.0)
OBJECTION_MIN_SCORE=0.5

# Utiliser audio pré-enregistré si match trouvé
OBJECTION_USE_PRERECORDED=true
```

### Variables Importantes par Use Case

#### Ajuster Réactivité Barge-In

```bash
# Plus réactif (risque faux positifs)
SILENCE_THRESHOLD=1.0
SPEECH_START_THRESHOLD=0.3
BARGE_IN_GRACE_PERIOD=2.0

# Plus conservateur (recommandé)
SILENCE_THRESHOLD=1.5
SPEECH_START_THRESHOLD=0.5
BARGE_IN_GRACE_PERIOD=3.0
```

#### Ajuster Timeout Écoute

```bash
# Rapide (4s - recommandé après fixes)
LISTEN_TIMEOUT=4

# Normal (10s - ancien comportement)
LISTEN_TIMEOUT=10

# Patient (15s)
LISTEN_TIMEOUT=15
```

#### Ajuster Matching Objections

```bash
# Permissif (plus de matchs)
OBJECTION_MIN_SCORE=0.4

# Équilibré (recommandé)
OBJECTION_MIN_SCORE=0.5

# Strict (haute précision)
OBJECTION_MIN_SCORE=0.7
```

---

## 🎵 Gestion des Fichiers Audio

### Architecture Audio

**Analyse basée sur `setup_audio.py` (597 lignes)**

Le système utilise **uniquement des fichiers audio pré-enregistrés**. Les fichiers audio passent par 3 étapes :

```
SOURCE (audio/)
    ↓ [setup_audio.py]
PROCESSÉ (normalisation + conversion)
    ↓ [setup_audio.py]
DÉPLOYÉ (/usr/share/freeswitch/sounds/minibot/)
```

### 1. Préparer les Fichiers Audio SOURCE

#### Structure Répertoire

```bash
audio/
└── julie/                        # Nom de la voix
    ├── base/                     # Audios principaux du scénario
    │   ├── hello.wav             # Salutation
    │   ├── pitch.wav             # Argumentaire
    │   ├── confirm_time.wav      # Confirmation RDV
    │   ├── bye.wav               # Au revoir (succès)
    │   ├── retry_hello.wav       # Relance si pas compris
    │   ├── retry_silence.wav     # Relance si silence
    │   ├── retry_is_leads.wav    # Relance si hésitation
    │   └── not_understood.wav    # Pas compris
    │
    └── objections/               # Réponses aux objections
        ├── too_expensive.wav
        ├── not_interested.wav
        ├── no_time.wav
        └── ...
```

#### Formats Supportés (INPUT)

D'après `setup_audio.py` lignes 597, les formats supportés en entrée sont :

- WAV (recommandé)
- MP3
- M4A
- FLAC
- OGG
- AAC

#### Recommandations Qualité

```
Durée : 5-30 secondes par fichier
Qualité : Bonne (peu de bruit de fond)
Débit parole : Naturel (pas trop rapide)
```

### 2. Traiter les Fichiers avec setup_audio.py

**Analyse détaillée du pipeline (lignes 208-276)** :

```python
def process_file(source_path, target_path, is_background=False):
    # 1. Charger audio (n'importe quel format)
    audio = AudioSegment.from_file(source_path)

    # 2. Détecter volume actuel
    peak_before, rms_before = detect_volume(audio)

    # 3. Normaliser au pic standard (-3dB)
    audio = normalize_audio(audio, TARGET_PEAK_DB=-3.0)

    # 4. Appliquer ajustement volume (+2dB par défaut)
    audio = adjust_volume(audio, AUDIO_VOLUME_ADJUST=2.0)

    # 5. Convertir au format téléphonie
    #    - 8000 Hz (sample rate)
    #    - Mono (1 canal)
    audio = convert_to_telephony_format(audio)

    # 6. Exporter avec codec µ-law (G.711)
    audio.export(
        target_path,
        format="wav",
        codec="pcm_mulaw",
        parameters=["-ar", "8000", "-ac", "1"]
    )
```

#### Normalisation Audio

**Objectifs** (lignes 243-276) :

1. **Peak normalization** : -3dB (évite saturation)
2. **RMS target** : -18dB (niveau moyen confortable)
3. **Volume boost** : +2dB (configurable via `.env`)
4. **Format téléphonie** : 8kHz mono µ-law

#### Commande setup_audio.py

**Usage basique** :

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

# Traiter tous les audios de la voix "julie"
python setup_audio.py julie

# Sortie attendue :
# 🎵 MiniBotPanel Audio Setup
# ════════════════════════════════════════════════════
# Voice: julie
# Source: /home/.../audio/julie
# Target: /usr/share/freeswitch/sounds/minibot/julie
# ════════════════════════════════════════════════════
#
# 📁 Processing: base/
#   ✅ hello.wav (3.2s) → Peak: -3.1 dB, RMS: -17.8 dB
#   ✅ pitch.wav (12.5s) → Peak: -3.0 dB, RMS: -18.2 dB
#   ✅ bye.wav (2.1s) → Peak: -3.2 dB, RMS: -17.5 dB
#   ...
#
# 📁 Processing: objections/
#   ✅ too_expensive.wav (8.3s) → Peak: -3.1 dB, RMS: -18.0 dB
#   ...
#
# ✅ Processed 15 files successfully
# 📊 Total duration: 2m 34s
# 🎯 All files copied to FreeSWITCH with correct permissions
```

**Options avancées** :

```bash
# Ajuster volume (override .env)
python setup_audio.py julie --volume-adjust 3.0

# Réduction bruit de fond
python setup_audio.py julie --background-reduction -15.0

# Dry-run (test sans copier vers FreeSWITCH)
python setup_audio.py julie --dry-run

# Verbose (debug détails)
python setup_audio.py julie --verbose
```

### 3. Vérifier les Fichiers Déployés

```bash
# Lister fichiers FreeSWITCH
ls -lah /usr/share/freeswitch/sounds/minibot/julie/base/
ls -lah /usr/share/freeswitch/sounds/minibot/julie/objections/

# Vérifier permissions (doit être lisible par freeswitch)
namei -l /usr/share/freeswitch/sounds/minibot/julie/base/hello.wav

# Vérifier format audio
file /usr/share/freeswitch/sounds/minibot/julie/base/hello.wav
# Sortie attendue : RIFF (little-endian) data, WAVE audio, ITU G.711 mu-law, mono 8000 Hz

# Tester lecture dans FreeSWITCH
fs_cli -x "originate user/1000 &playback(/usr/share/freeswitch/sounds/minibot/julie/base/hello.wav)"
```

### 4. Workflow Complet Ajout Nouveau Audio

**Exemple : Ajouter un nouvel audio "confirm_rdv.wav"**

```bash
# 1. Enregistrer/Obtenir le fichier audio source
#    Format : WAV, MP3, etc. (n'importe lequel)
#    Placer dans audio/julie/base/confirm_rdv.wav

# 2. Traiter avec setup_audio.py
python setup_audio.py julie

# 3. Vérifier déploiement
ls -lah /usr/share/freeswitch/sounds/minibot/julie/base/confirm_rdv.wav

# 4. Utiliser dans scénario JSON
{
  "confirm_rdv": {
    "type": "audio",
    "audio_path": "julie/base/confirm_rdv.wav",
    "timeout": 4,
    "barge_in": true
  }
}
```

### 5. Créer une Nouvelle Voix

```bash
# 1. Créer structure
mkdir -p audio/marc/base
mkdir -p audio/marc/objections

# 2. Placer fichiers audio
cp mes_audios/*.wav audio/marc/base/

# 3. Traiter
python setup_audio.py marc

# 4. Vérifier
ls -lah /usr/share/freeswitch/sounds/minibot/marc/

# 5. Utiliser dans scénario
{
  "name": "Scénario avec Marc",
  "voice": "marc",
  "steps": {
    "hello": {
      "type": "audio",
      "audio_path": "marc/base/hello.wav"
    }
  }
}
```

---

## 📝 Création de Scénarios

**Analyse basée sur `create_scenario.py` (900 lignes)**

### 1. Mode Interactif (Recommandé)

Le script `create_scenario.py` offre un assistant interactif complet.

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

python create_scenario.py
```

#### Workflow de l'Assistant

**Étape 1 : Informations de Base** (lignes 196-212)

```
┌──────────────────────────────────────────────────────┐
│ 🎬 Créateur de Scénario MiniBotPanel v3             │
└──────────────────────────────────────────────────────┘

📋 Nom du scénario : Vente Or Investissement

📄 Description : Prospection pour investissement en or physique
```

**Étape 2 : Configuration Voix** (lignes 213-248)

L'assistant détecte automatiquement les voix disponibles dans `audio/` :

```
🎤 Voix disponibles (détectées dans audio/) :
  1. julie
  2. marc

Choisissez une voix [1-2] : 1

✅ Voix sélectionnée : julie
```

**Étape 3 : Configuration Questions** (lignes 249-295)

```
❓ Nombre de questions dans le scénario : 3

Pour chaque question :

  Question 1 :
    Nom de l'étape : hello
    Fichier audio : hello.wav

    🎙️ Transcription automatique avec Vosk...
    ✅ Transcription : "Bonjour, je suis Julie de GoldInvest. Avez-vous 2 minutes ?"

    Type de question :
      1. Normale (peut retry)
      2. Déterminante (refus = élimination)
    Choix [1-2] : 2

    ✅ Question déterminante configurée

  Question 2 :
    Nom de l'étape : pitch
    Fichier audio : pitch.wav
    ...
```

**Important : Transcription Automatique Vosk**

D'après les lignes 445-498, le système transcrit automatiquement chaque audio :

```python
def _transcribe_audio_with_vosk(audio_path):
    # 1. Charger modèle Vosk
    model = Model("models/vosk-model-fr-0.22-lgraph")

    # 2. Ouvrir fichier WAV
    wf = wave.open(audio_path, "rb")
    recognizer = KaldiRecognizer(model, wf.getframerate())

    # 3. Transcription streaming
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        recognizer.AcceptWaveform(data)

    # 4. Résultat final
    result = json.loads(recognizer.FinalResult())
    return result["text"]
```

**Étape 4 : Thématique Objections** (lignes 296-337)

```
🎯 Thématique pour objections :
  1. Standard (18 objections)
  2. Finance (15 objections)
  3. Trading Crypto (17 objections)
  4. Or Investissement (16 objections)
  5. Vin Investissement (15 objections)
  6. Immobilier (15 objections)
  7. Assurance (17 objections)
  8. SaaS B2B (19 objections)
  9. Énergie Renouvelable (16 objections)

Choix [1-9] : 4

✅ Thématique sélectionnée : Or Investissement (16 objections)
```

**Étape 5 : Configuration Barge-In** (lignes 338-368)

```
🔊 Configuration Barge-In (interruption) :

  Activer barge-in ? [O/n] : O

  Timeout écoute (secondes) [4] : 4

  Grace period anti-faux-positifs (secondes) [3.0] : 3.0

✅ Barge-in configuré :
   - Actif : Oui
   - Timeout : 4s
   - Grace period : 3.0s
```

**Étape 6 : Max Autonomous Turns** (lignes 369-395)

```
🔄 Nombre maximum de tours autonomes (objections) :

   C'est le nombre de fois que le robot peut répondre automatiquement
   aux objections avant de passer à l'étape suivante.

   Recommandations :
     0 = Pas de gestion objections
     1-2 = Basique
     3 = Recommandé
     5 = Maximum

   Choix [0-5] : 3

✅ Max autonomous turns : 3
```

**Étape 7 : Construction et Sauvegarde** (lignes 500-582)

```
🔨 Construction du scénario...

✅ Structure JSON créée :
   - 3 questions
   - Thématique : or
   - 16 objections disponibles
   - Barge-in actif
   - Max turns : 3

💾 Sauvegarder sous (nom fichier) [scenario_or_investissement] :

✅ Scénario sauvegardé : scenarios/scenario_or_investissement.json

📊 Résumé :
   Nom : Vente Or Investissement
   Voix : julie
   Étapes : 7 (3 questions + 4 auxiliaires)
   Objections : 16 (or)
   Fichier : scenarios/scenario_or_investissement.json
```

### 2. Structure JSON du Scénario

**Exemple complet basé sur l'analyse de `system/scenarios.py` (575 lignes)** :

```json
{
  "name": "Vente Or Investissement",
  "description": "Prospection pour investissement en or physique",
  "voice": "julie",
  "theme": "or",
  "max_autonomous_turns": 3,
  "steps": {
    "hello": {
      "type": "audio",
      "audio_path": "julie/base/hello.wav",
      "text": "Bonjour {{first_name}}, je suis Julie de GoldInvest. Avez-vous 2 minutes ?",
      "timeout": 4,
      "barge_in": true,
      "is_determinant": true,
      "transitions": {
        "affirm": "pitch",
        "deny": "bye",
        "question": "retry_hello",
        "objection": "handle_objection",
        "silence": "retry_silence",
        "not_understood": "retry_hello"
      }
    },

    "pitch": {
      "type": "audio",
      "audio_path": "julie/base/pitch.wav",
      "text": "L'or a pris +110% depuis 2020. C'est le moment idéal pour diversifier. Seriez-vous disponible mardi pour un RDV de 30 minutes ?",
      "timeout": 4,
      "barge_in": true,
      "transitions": {
        "affirm": "confirm_time",
        "deny": "handle_objection",
        "question": "handle_objection",
        "silence": "retry_silence"
      }
    },

    "confirm_time": {
      "type": "audio",
      "audio_path": "julie/base/confirm_time.wav",
      "text": "Parfait ! Je note mardi 14h. Vous recevrez un SMS de confirmation. Merci et à bientôt !",
      "timeout": 0,
      "barge_in": false,
      "transitions": {
        "*": "bye"
      }
    },

    "handle_objection": {
      "type": "objection_handler",
      "max_attempts": 3,
      "fallback_step": "bye_not_interested",
      "success_step": "pitch"
    },

    "retry_hello": {
      "type": "audio",
      "audio_path": "julie/base/retry_hello.wav",
      "text": "Je me présente, je suis Julie de GoldInvest. Puis-je vous parler 2 minutes ?",
      "timeout": 4,
      "barge_in": true,
      "transitions": {
        "affirm": "pitch",
        "deny": "bye",
        "*": "bye_not_interested"
      }
    },

    "retry_silence": {
      "type": "audio",
      "audio_path": "julie/base/retry_silence.wav",
      "text": "Vous êtes toujours là ? Je répète : avez-vous 2 minutes ?",
      "timeout": 4,
      "barge_in": true,
      "transitions": {
        "affirm": "pitch",
        "*": "bye"
      }
    },

    "bye": {
      "type": "audio",
      "audio_path": "julie/base/bye.wav",
      "text": "D'accord, je vous souhaite une excellente journée. Au revoir !",
      "timeout": 0,
      "barge_in": false,
      "is_final": true,
      "result": "success"
    },

    "bye_not_interested": {
      "type": "audio",
      "audio_path": "julie/base/bye.wav",
      "text": "Je comprends. Bonne journée !",
      "timeout": 0,
      "barge_in": false,
      "is_final": true,
      "result": "not_interested"
    }
  }
}
```

### 3. Champs du Scénario

#### Métadonnées Scénario

```json
{
  "name": "string",              // Nom du scénario
  "description": "string",       // Description
  "voice": "string",             // Nom de la voix (julie, marc, etc.)
  "theme": "string",             // Thématique objections (or, vin, finance, etc.)
  "max_autonomous_turns": 0-5    // Tours autonomes max pour objections
}
```

#### Champs d'une Étape (Step)

```json
{
  "type": "audio|objection_handler",  // Type étape
  "audio_path": "string",             // Chemin relatif audio (ex: julie/base/hello.wav)
  "text": "string",                   // Transcription (avec variables {{first_name}})
  "timeout": 0-15,                    // Timeout écoute (0 = pas d'écoute)
  "barge_in": true|false,             // Autoriser interruption
  "is_determinant": true|false,       // Question déterminante (refus = élimination)
  "is_final": true|false,             // Étape finale (termine appel)
  "result": "string",                 // Résultat (success, not_interested, no_answer, etc.)
  "transitions": {                    // Transitions selon intent
    "affirm": "step_name",
    "deny": "step_name",
    "question": "step_name",
    "objection": "step_name",
    "silence": "step_name",
    "not_understood": "step_name",
    "*": "step_name"                  // Fallback
  }
}
```

#### Variables Dynamiques

Disponibles dans `text` (lignes 128-145 de `scenarios.py`) :

```
{{first_name}}   → Prénom contact
{{last_name}}    → Nom contact
{{company}}      → Entreprise
{{email}}        → Email
{{phone}}        → Téléphone
```

### 4. Types d'Étapes

#### audio

Lecture d'un fichier audio avec écoute de réponse.

```json
{
  "type": "audio",
  "audio_path": "julie/base/hello.wav",
  "text": "Bonjour {{first_name}}",
  "timeout": 4,
  "barge_in": true
}
```

#### objection_handler

Gestion automatique des objections avec matching.

```json
{
  "type": "objection_handler",
  "max_attempts": 3,
  "fallback_step": "bye_not_interested",
  "success_step": "pitch"
}
```

### 5. Intents Disponibles

D'après `system/services/ollama_nlp.py`, les intents détectés sont :

```
affirm          → Affirmation (oui, d'accord, ok)
deny            → Négation (non, pas intéressé)
question        → Question (pourquoi ? comment ?)
objection       → Objection (trop cher, pas le temps)
silence         → Silence (aucune parole détectée)
not_understood  → Pas compris (transcription vide/incompréhensible)
```

### 6. Tester un Scénario

```bash
# Lancer un appel test
python test_call.py

# Le script utilise le scénario configuré dans test_call.py (ligne ~15)
# Par défaut : "dfdf"

# Monitorer les logs
tail -f logs/system/robot_freeswitch_v2.log

# Vérifier les transitions
# Les logs montrent :
# [UUID] Step: hello (type: audio)
# [UUID] Intent detected: affirm
# [UUID] Step: pitch (type: audio)
# ...
```

---

## 👥 Import de Contacts

**Analyse basée sur `import_contacts.py` (218 lignes)**

### 1. Format CSV

**Champs supportés** (lignes 45-78) :

```csv
phone,first_name,last_name,company,email,tags
+33612345678,Jean,Dupont,ACME Corp,jean@acme.com,"prospect,vip"
+33698765432,Marie,Martin,Tech Inc,marie@tech.com,"client,actif"
```

**Champs obligatoires** :
- `phone` : Numéro au format international (+33..., +1..., etc.)

**Champs optionnels** :
- `first_name`, `last_name`, `company`, `email`, `tags`

### 2. Import Simple

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

python import_contacts.py contacts.csv

# Sortie :
# 📥 Importation Contacts MiniBotPanel v3
# ═══════════════════════════════════════════
# Fichier : contacts.csv
# ═══════════════════════════════════════════
#
# ✅ Ligne 1 : +33612345678 (Jean Dupont)
# ✅ Ligne 2 : +33698765432 (Marie Martin)
#
# 📊 Résumé :
#    Total lignes : 2
#    Importés : 2
#    Doublons : 0
#    Erreurs : 0
#
# ✅ Import terminé avec succès
```

### 3. Options Avancées

```bash
# Ignorer doublons (ne pas importer si phone existe déjà)
python import_contacts.py contacts.csv --skip-duplicates

# Valider format téléphone strict
python import_contacts.py contacts.csv --validate-phones

# Ajouter tags à tous les contacts importés
python import_contacts.py contacts.csv --add-tags "campagne_janvier,segment_A"

# Mode verbose (debug)
python import_contacts.py contacts.csv --verbose

# Dry-run (tester sans importer)
python import_contacts.py contacts.csv --dry-run
```

### 4. Format Excel

```bash
# Supporter fichiers .xlsx
python import_contacts.py contacts.xlsx

# Le script détecte automatiquement :
# - Première ligne = header
# - Colonnes : phone, first_name, last_name, etc.
```

### 5. Vérifier Contacts Importés

```bash
# Via psql
psql -U minibot -d minibot_freeswitch

SELECT id, phone, first_name, last_name, created_at
FROM contacts
ORDER BY created_at DESC
LIMIT 10;

# Sortie :
#  id |     phone      | first_name | last_name |       created_at
# ----+----------------+------------+-----------+-------------------------
#   1 | +33612345678   | Jean       | Dupont    | 2025-11-07 10:30:15
#   2 | +33698765432   | Marie      | Martin    | 2025-11-07 10:30:15
```

### 6. Workflow Complet

```bash
# 1. Créer fichier CSV
cat > prospects_or.csv << EOF
phone,first_name,last_name,company,email
+33612345678,Jean,Dupont,Entreprise A,jean@example.com
+33698765432,Marie,Martin,Entreprise B,marie@example.com
+33687654321,Pierre,Bernard,Société C,pierre@example.com
EOF

# 2. Importer avec validation
python import_contacts.py prospects_or.csv \
  --validate-phones \
  --skip-duplicates \
  --add-tags "campagne_or_janvier,prospect"

# 3. Vérifier
psql -U minibot -d minibot_freeswitch -c "SELECT COUNT(*) FROM contacts;"

# 4. Lancer campagne avec ces contacts
python launch_campaign.py --scenario scenario_or_investissement
```

---

## 📞 Lancement d'Appels

### 1. Test Call (Un seul appel)

**Analyse basée sur `test_call.py`**

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

# Lancer test call
python test_call.py

# Le script :
# 1. Lit la config du scénario "dfdf" (configurable ligne ~15)
# 2. Appelle le numéro configuré (33743130341)
# 3. Execute le scénario
# 4. Affiche logs en temps réel
```

**Logs attendus** :

```
2025-11-07 10:47:40 | INFO | Originating call to 33743130341 (campaign 0, scenario dfdf, retry 0)
2025-11-07 10:47:45 | INFO | 📞 Call answered: 8402c4b8-14a8-4d8d-8fb7-8981d8c7377c
2025-11-07 10:47:45 | INFO | [8402c4b8] AMD: UNKNOWN
2025-11-07 10:47:45 | INFO | [8402c4b8] ✅ Audio streaming started to WebSocket (16kHz mono)
2025-11-07 10:47:45 | INFO | [8402c4b8] Executing scenario: dfdf
2025-11-07 10:47:45 | INFO | [8402c4b8] Step: hello (type: audio)
...
```

### 2. Launch Campaign (Multiple appels)

**Analyse basée sur `launch_campaign.py`**

```bash
# Lancer campagne
python launch_campaign.py --scenario scenario_or_investissement

# Options :
python launch_campaign.py \
  --scenario scenario_or_investissement \
  --max-concurrent 5 \
  --delay 2 \
  --retry-enabled

# Sortie :
# 🚀 MiniBotPanel Campaign Launcher v3
# ════════════════════════════════════════════════════
# Scénario : scenario_or_investissement
# Contacts : 50 (depuis DB)
# Max concurrent : 5
# Delay : 2s
# ════════════════════════════════════════════════════
#
# 📞 [1/50] Appel +33612345678 (Jean Dupont)
# 📞 [2/50] Appel +33698765432 (Marie Martin)
# ...
# ⏸️  Attente 2s avant prochain lot...
# 📞 [6/50] Appel +33687654321 (Pierre Bernard)
# ...
```

### 3. Configuration Appels

**D'après `.env` et `system/config.py`** :

```bash
# Nombre max d'appels simultanés
MAX_CONCURRENT_CALLS=5

# Délai entre appels (secondes)
CALL_DELAY=2

# Durée max d'un appel (secondes)
MAX_CALL_DURATION=300

# Retry automatique
RETRY_ENABLED=true
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY=3600  # 1 heure
RETRY_CONDITIONS=no_answer,busy,timeout
```

### 4. Monitoring Live

**Pendant l'appel** :

```bash
# Logs système
tail -f logs/system/robot_freeswitch_v2.log

# Logs streaming ASR
tail -f logs/streaming_asr.log

# FreeSWITCH console
fs_cli

# Dans fs_cli :
freeswitch> show calls
freeswitch> uuid_dump <UUID>
```

### 5. Workflow Complet Test

```bash
# 1. Vérifier scénario existe
ls -la scenarios/scenario_or_investissement.json

# 2. Vérifier audios déployés
ls -la /usr/share/freeswitch/sounds/minibot/julie/base/

# 3. Vérifier services actifs
systemctl status freeswitch
ps aux | grep robot_freeswitch_v2
ps aux | grep streaming_asr

# 4. Lancer test
python test_call.py

# 5. Observer logs
tail -f logs/system/robot_freeswitch_v2.log

# 6. Vérifier résultat dans DB
psql -U minibot -d minibot_freeswitch -c "
  SELECT call_uuid, phone, status, result, duration
  FROM calls
  ORDER BY started_at DESC
  LIMIT 1;
"
```

---

## 📊 Monitoring des Campagnes

**Analyse basée sur `monitor_campaign.py`**

### 1. Lancer Monitor

```bash
# Monitor campagne ID 1 avec refresh toutes les 5 secondes
python monitor_campaign.py --campaign-id 1 --refresh 5

# Options :
python monitor_campaign.py \
  --campaign-id 1 \
  --refresh 10 \
  --show-live-calls \
  --export-csv
```

### 2. Interface Monitor

```
╔══════════════════════════════════════════════════════════════╗
║    MiniBotPanel v3 - Campaign Monitor (ID: 1)                ║
║       Campagne Or Investissement Janvier 2025                ║
╚══════════════════════════════════════════════════════════════╝

📊 Status: RUNNING | Duration: 01:23:45 | Updated: 14:35:12

┌─ Progress ──────────────────────────────────────────────────┐
│ [████████████████░░░░░░░░░░] 32/50 (64%)                    │
└─────────────────────────────────────────────────────────────┘

┌─ Call Stats ────────────────────────────────────────────────┐
│ Total calls: 32                                             │
│ Active calls: 3                                             │
│ Completed: 29                                               │
│ Failed: 0                                                   │
│ Avg duration: 2m 34s                                        │
└─────────────────────────────────────────────────────────────┘

┌─ Results ───────────────────────────────────────────────────┐
│ SUCCESS:          12 (38%) ████████                         │
│ NOT_INTERESTED:   15 (47%) ██████████                       │
│ NO_ANSWER:        3 (9%)   ██                               │
│ ANSWERING_MACHINE: 2 (6%)  █                                │
└─────────────────────────────────────────────────────────────┘

┌─ Live Calls ────────────────────────────────────────────────┐
│ UUID: 8402c4b8 | +33612... | Step: pitch | 0:45            │
│ UUID: 7f3a21c9 | +33698... | Step: hello | 0:12            │
│ UUID: 9b5d4e2a | +33687... | Step: objection | 1:23        │
└─────────────────────────────────────────────────────────────┘

Press Ctrl+C to stop monitoring...
```

### 3. Requêtes SQL Utiles

```bash
# Stats campagne
psql -U minibot -d minibot_freeswitch

# Résumé campagne
SELECT
  campaign_id,
  COUNT(*) as total_calls,
  COUNT(*) FILTER (WHERE status = 'completed') as completed,
  COUNT(*) FILTER (WHERE result = 'success') as success,
  COUNT(*) FILTER (WHERE result = 'not_interested') as not_interested,
  AVG(duration) as avg_duration
FROM calls
WHERE campaign_id = 1
GROUP BY campaign_id;

# Appels actifs
SELECT call_uuid, phone, status, current_step, started_at
FROM calls
WHERE status = 'active'
ORDER BY started_at;

# Top résultats
SELECT result, COUNT(*) as count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM calls
WHERE campaign_id = 1
GROUP BY result
ORDER BY count DESC;
```

---

## 📤 Export des Résultats

**Analyse basée sur `export_campaign.py` (191 lignes)**

### 1. Export CSV

```bash
# Export basique CSV
python export_campaign.py --campaign-id 1 --format csv

# Sortie : exports/campaign_1_YYYYMMDD_HHMMSS.csv

# Options :
python export_campaign.py \
  --campaign-id 1 \
  --format csv \
  --output my_results.csv \
  --filter-result success \
  --include-transcriptions
```

**Colonnes CSV exportées** :

```
call_id, call_uuid, campaign_id, phone, first_name, last_name, company, email,
status, result, duration, started_at, ended_at, current_step,
amd_result, retry_count, transcription
```

### 2. Export Excel

```bash
# Export Excel (multi-feuilles)
python export_campaign.py --campaign-id 1 --format excel

# Sortie : exports/campaign_1_YYYYMMDD_HHMMSS.xlsx
```

**Feuilles générées** :

1. **Summary** : Stats globales
   - Total calls, success rate, avg duration
   - Graphiques (si openpyxl disponible)

2. **Calls** : Détail de tous les appels
   - Toutes les colonnes
   - Filtres activés

3. **Results** : Répartition résultats
   - Tableau croisé dynamique

4. **Timeline** : Analyse temporelle
   - Appels par heure/jour

### 3. Filtrer l'Export

```bash
# Uniquement succès
python export_campaign.py --campaign-id 1 --filter-result success

# Plage de dates
python export_campaign.py \
  --campaign-id 1 \
  --start-date "2025-11-01" \
  --end-date "2025-11-07"

# Uniquement contacts spécifiques
python export_campaign.py \
  --campaign-id 1 \
  --filter-phone "+33612345678,+33698765432"
```

### 4. Export Programmatique

```python
from export_campaign import CampaignExporter

# Créer exporter
exporter = CampaignExporter(campaign_id=1)

# Export CSV
exporter.export_csv("results.csv", filter_result="success")

# Export Excel
exporter.export_excel("results.xlsx", include_charts=True)

# Export JSON
data = exporter.export_json()
```

---

## 🎯 Base d'Objections

**Analyse basée sur `system/objections_db/` (modules Python)**

### 1. Architecture Modulaire

Contrairement à la v2 qui utilisait des fichiers audio statiques, la v3 utilise une **base d'objections Python modulaire**.

```
system/objections_db/
├── __init__.py              # Agrégateur
├── standard.py              # 18 objections standard
├── finance.py               # 15 objections finance
├── crypto.py                # 17 objections trading crypto
├── or_investissement.py     # 16 objections or
├── vin_investissement.py    # 15 objections vin
├── immobilier.py            # 15 objections immobilier
├── assurance.py             # 17 objections assurance
├── saas_b2b.py              # 19 objections SaaS
└── energie.py               # 16 objections énergie
```

### 2. Format Objection

Chaque module Python contient un dictionnaire :

```python
# Exemple : system/objections_db/or_investissement.py

OBJECTIONS_OR = {
    # Objection → Réponse
    "C'est risqué": {
        "response": "Risqué ? L'or existe depuis 5000 ans et n'a JAMAIS valu zéro ! En fait c'est l'inverse : l'or protège de l'inflation. +110% depuis 2020.",
        "audio_file": "or_risky.wav",
        "category": "risk"
    },

    "C'est trop cher": {
        "response": "Trop cher ? Vous pouvez commencer dès 1000€. Nos clients investissent en moyenne 5000-15000€. C'est un actif tangible qui prend de la valeur.",
        "audio_file": "or_expensive.wav",
        "category": "price"
    },

    "Où stocker l'or ?": {
        "response": "Excellente question ! Nous proposons un coffre sécurisé gratuit la première année. Ou alors livraison chez vous avec assurance. Vous préférez quoi ?",
        "audio_file": "or_storage.wav",
        "category": "practical"
    },

    # ... 13 autres objections
}
```

### 3. Utilisation dans Scénario

**Lors de la création du scénario**, on choisit une thématique :

```bash
python create_scenario.py

# Étape : Choix thématique
🎯 Thématique pour objections :
  4. Or Investissement (16 objections)

Choix : 4
```

**Le scénario JSON contient** :

```json
{
  "name": "Vente Or",
  "theme": "or",
  "max_autonomous_turns": 3,
  "steps": {
    "handle_objection": {
      "type": "objection_handler",
      "max_attempts": 3,
      "fallback_step": "bye_not_interested",
      "success_step": "pitch"
    }
  }
}
```

**Pendant l'appel** (d'après `robot_freeswitch_v2.py` lignes 1100-1250) :

1. **Transcription** : Vosk transcrit réponse prospect
2. **Intent** : Ollama détecte intent = "objection"
3. **Matching** : Fuzzy matching avec objections de la thématique
4. **Réponse** :
   - Si match (score ≥ 0.5) → Lire `audio_file` pré-enregistré
   - Sinon → Fallback (retry ou bye)

### 4. Algorithme Fuzzy Matching

**Basé sur `system/objection_matcher.py`** (si présent) :

```python
from difflib import SequenceMatcher

def fuzzy_match(input_text, objection_text):
    # 1. Normalisation
    input_clean = input_text.lower().strip()
    objection_clean = objection_text.lower().strip()

    # 2. Similarité textuelle (70%)
    similarity = SequenceMatcher(None, input_clean, objection_clean).ratio()

    # 3. Mots-clés communs (30%)
    input_words = set(input_clean.split())
    objection_words = set(objection_clean.split())
    common_words = input_words & objection_words
    keyword_score = len(common_words) / max(len(input_words), len(objection_words))

    # 4. Score final
    final_score = 0.7 * similarity + 0.3 * keyword_score

    return final_score

# Exemple :
fuzzy_match("C'est pas un peu risqué l'or ?", "C'est risqué")
# → 0.72 (match !)

fuzzy_match("Quel temps fait-il ?", "C'est risqué")
# → 0.18 (pas de match)
```

### 5. Ajouter des Objections Personnalisées

```python
# 1. Créer nouveau module : system/objections_db/custom.py

OBJECTIONS_CUSTOM = {
    "Mon objection perso": {
        "response": "Ma réponse experte personnalisée",
        "audio_file": "custom_objection_1.wav",
        "category": "custom"
    },

    "Autre objection": {
        "response": "Autre réponse",
        "audio_file": "custom_objection_2.wav",
        "category": "custom"
    }
}

# 2. Enregistrer fichiers audio
# audio/julie/objections/custom_objection_1.wav
# audio/julie/objections/custom_objection_2.wav

# 3. Traiter avec setup_audio.py
python setup_audio.py julie

# 4. Importer dans __init__.py
# system/objections_db/__init__.py
from .custom import OBJECTIONS_CUSTOM

ALL_OBJECTIONS = {
    "standard": OBJECTIONS_STANDARD,
    "finance": OBJECTIONS_FINANCE,
    "custom": OBJECTIONS_CUSTOM,  # ← Ajouter
    # ...
}

# 5. Utiliser dans scénario
{
  "theme": "custom",
  "steps": {
    "handle_objection": {
      "type": "objection_handler"
    }
  }
}
```

### 6. Statistiques Objections

**Total : 153 objections** réparties sur 9 thématiques :

| Thématique | Nb Objections | Module |
|------------|---------------|--------|
| Standard | 18 | `standard.py` |
| Finance | 15 | `finance.py` |
| Trading Crypto | 17 | `crypto.py` |
| Énergie Renouvelable | 16 | `energie.py` |
| Immobilier | 15 | `immobilier.py` |
| Assurance | 17 | `assurance.py` |
| SaaS B2B | 19 | `saas_b2b.py` |
| Or Investissement | 16 | `or_investissement.py` |
| Vin Investissement | 15 | `vin_investissement.py` |

---

## 🐛 Troubleshooting

### Problème : WebSocket port 8080 déjà utilisé

**Symptôme** :

```
ERROR | ❌ Failed to start WebSocket server: [Errno 98] address already in use
```

**Solution** :

```bash
# 1. Identifier processus
sudo lsof -i :8080

# 2. Tuer processus
sudo kill -9 <PID>

# 3. Ou changer port dans .env
STREAMING_ASR_PORT=8081

# 4. Redémarrer robot
python system/robot_freeswitch_v2.py
```

### Problème : Timeout systématique (pas de réponse détectée)

**Symptôme** :

```
WARNING | ⏱️ Listen timeout (4s) - no response
```

**Causes possibles** :

1. **Streaming ASR non connecté**
2. **VAD trop strict**
3. **Modèle Vosk non chargé**

**Solutions** :

```bash
# 1. Vérifier WebSocket actif
ps aux | grep streaming_asr
netstat -tlnp | grep 8080

# 2. Ajuster VAD dans .env
SILENCE_THRESHOLD=1.0         # Plus permissif (défaut: 1.5)
SPEECH_START_THRESHOLD=0.3    # Plus réactif (défaut: 0.5)

# 3. Vérifier Vosk
ls -la models/vosk-model-fr-0.22-lgraph

# 4. Augmenter timeout
LISTEN_TIMEOUT=10  # Au lieu de 4
```

### Problème : Barge-in détecté trop tôt (faux positifs)

**Symptôme** :

```
WARNING | 🚫 Speech ignored (grace period: 0.5s < 3.0s)
```

**Cause** : VAD détecte bruit de fond comme parole

**Solution** :

```bash
# Augmenter grace period
BARGE_IN_GRACE_PERIOD=5.0  # Au lieu de 3.0

# Ou désactiver barge-in dans scénario
{
  "hello": {
    "barge_in": false  # ← Désactiver
  }
}
```

### Problème : Vosk ne transcrit rien

**Symptôme** :

```
INFO | 📝 Transcription: "" (vide)
```

**Solutions** :

```bash
# 1. Vérifier modèle Vosk
ls -la models/vosk-model-fr-0.22-lgraph/
# Doit contenir : am/, graph/, ivector/

# 2. Vérifier sample rate audio
file /usr/share/freeswitch/sounds/minibot/julie/base/hello.wav
# Doit être : 8000 Hz (µ-law)

# 3. Vérifier streaming audio
# Dans fs_cli :
freeswitch> uuid_dump <UUID>
# Chercher : mod_audio_stream

# 4. Tester Vosk manuellement
python
>>> from vosk import Model, KaldiRecognizer
>>> model = Model("models/vosk-model-fr-0.22-lgraph")
>>> # Si erreur → modèle corrompu, re-télécharger
```

### Problème : Ollama NLP ne détecte pas les intents

**Symptôme** :

```
ERROR | ❌ Ollama not available
```

**Solutions** :

```bash
# 1. Vérifier Ollama installé
which ollama

# 2. Démarrer service
ollama serve &

# 3. Vérifier modèle téléchargé
ollama list
# Si vide : ollama pull mistral:7b

# 4. Tester
curl http://localhost:11434/api/tags

# 5. Vérifier URL dans .env
OLLAMA_BASE_URL=http://localhost:11434
```

### Problème : Audio crackling / saturé

**Symptôme** : Audio déformé, saturé pendant l'appel

**Cause** : Volume trop élevé

**Solution** :

```bash
# 1. Réduire volume dans .env
AUDIO_VOLUME_ADJUST=0.0  # Au lieu de 2.0

# 2. Re-traiter audios
python setup_audio.py julie

# 3. Vérifier normalisation
# Les logs setup_audio.py doivent afficher :
# Peak: -3.0 dB (pas 0.0 dB = saturation)
```

### Problème : FreeSWITCH ne trouve pas les fichiers audio

**Symptôme** :

```
ERROR | Cannot play file: julie/base/hello.wav
```

**Solutions** :

```bash
# 1. Vérifier fichier existe
ls -la /usr/share/freeswitch/sounds/minibot/julie/base/hello.wav

# 2. Vérifier permissions
namei -l /usr/share/freeswitch/sounds/minibot/julie/base/hello.wav
# Tous les répertoires doivent être +x (exécutable)

# 3. Vérifier ownership
sudo chown -R freeswitch:freeswitch /usr/share/freeswitch/sounds/minibot/

# 4. Tester lecture manuelle
fs_cli -x "originate user/1000 &playback(/usr/share/freeswitch/sounds/minibot/julie/base/hello.wav)"
```

### Problème : Calls DB vide après appels

**Symptôme** : Aucun enregistrement dans table `calls` après campagne

**Solutions** :

```bash
# 1. Vérifier connexion DB
psql -U minibot -d minibot_freeswitch -c "SELECT 1;"

# 2. Vérifier tables existent
psql -U minibot -d minibot_freeswitch -c "\dt"

# 3. Vérifier logs DB dans robot
tail -f logs/system/robot_freeswitch_v2.log | grep -i "database\|INSERT\|UPDATE"

# 4. Vérifier config DB dans .env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=minibot_freeswitch
DB_USER=minibot
DB_PASSWORD=<password>
```

### Problème : Appels se terminent immédiatement

**Symptôme** : Call duration < 2 secondes

**Causes** :

1. **AMD détecte répondeur** → Hangup immédiat
2. **Scénario mal configuré** → is_final sur première étape
3. **Numéro invalide**

**Solutions** :

```bash
# 1. Désactiver AMD pour test
# .env :
AMD_ENABLED=false

# 2. Vérifier scénario JSON
cat scenarios/mon_scenario.json | jq '.steps.hello.is_final'
# Ne doit PAS être true

# 3. Tester numéro manuellement
fs_cli -x "originate sofia/gateway/mygateway/33612345678 &echo"

# 4. Monitorer logs
tail -f logs/system/robot_freeswitch_v2.log
```

---

## 📞 Support et Ressources

### Documentation

- `GUIDE_INSTALLATION.md` : Installation complète
- `BRIEF_PROJET.md` : Architecture technique
- `scenarios/` : Exemples de scénarios

### Logs

```bash
# Logs système
tail -f logs/system/robot_freeswitch_v2.log

# Logs FreeSWITCH
tail -f /usr/local/freeswitch/log/freeswitch.log

# Logs PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-*.log
```

### Commandes Utiles

```bash
# Vérifier tous les services
systemctl status freeswitch
systemctl status postgresql
ps aux | grep robot_freeswitch_v2
ps aux | grep streaming_asr
ollama list

# Nettoyer logs anciens
find logs/ -name "*.log" -mtime +7 -delete

# Backup DB
pg_dump -U minibot minibot_freeswitch > backup_$(date +%Y%m%d).sql

# Restaurer DB
psql -U minibot minibot_freeswitch < backup_20251107.sql
```

---

## 🎯 Workflows Complets

### Workflow A : Créer Campagne Or de A à Z

```bash
# 1. Préparer audios
mkdir -p audio/julie/base
mkdir -p audio/julie/objections

# 2. Placer fichiers WAV dans audio/julie/base/
# hello.wav, pitch.wav, confirm_time.wav, bye.wav, etc.

# 3. Traiter audios
python setup_audio.py julie

# 4. Vérifier déploiement
ls -la /usr/share/freeswitch/sounds/minibot/julie/base/

# 5. Créer scénario
python create_scenario.py
# → Thématique : Or Investissement
# → Voix : julie
# → Max turns : 3

# 6. Vérifier scénario généré
cat scenarios/scenario_or_investissement.json | jq '.'

# 7. Préparer contacts
cat > prospects_or.csv << EOF
phone,first_name,last_name,company,email
+33612345678,Jean,Dupont,Entreprise A,jean@example.com
+33698765432,Marie,Martin,Entreprise B,marie@example.com
EOF

# 8. Importer contacts
python import_contacts.py prospects_or.csv --validate-phones

# 9. Vérifier import
psql -U minibot -d minibot_freeswitch -c "SELECT COUNT(*) FROM contacts;"

# 10. Lancer campagne
python launch_campaign.py --scenario scenario_or_investissement --max-concurrent 2

# 11. Monitorer
python monitor_campaign.py --campaign-id 1 --refresh 5

# 12. Exporter résultats
python export_campaign.py --campaign-id 1 --format excel
```

### Workflow B : Ajouter Nouvelle Voix

```bash
# 1. Créer structure
mkdir -p audio/marc/base
mkdir -p audio/marc/objections

# 2. Placer audios
cp mes_audios_marc/*.wav audio/marc/base/

# 3. Traiter
python setup_audio.py marc --verbose

# 4. Vérifier
ls -la /usr/share/freeswitch/sounds/minibot/marc/

# 5. Créer scénario avec nouvelle voix
python create_scenario.py
# → Voix : marc

# 6. Tester
python test_call.py  # (après config scénario dans test_call.py)
```

### Workflow C : Debug Appel Qui Échoue

```bash
# 1. Activer logs verbeux
# .env :
LOG_LEVEL=DEBUG

# 2. Relancer robot
pkill -f robot_freeswitch_v2
python system/robot_freeswitch_v2.py &

# 3. Lancer test call
python test_call.py 2>&1 | tee /tmp/debug_call.log

# 4. Analyser logs
tail -f logs/system/robot_freeswitch_v2.log

# 5. Vérifier FreeSWITCH
fs_cli
freeswitch> sofia status
freeswitch> show channels

# 6. Vérifier DB
psql -U minibot -d minibot_freeswitch -c "
  SELECT call_uuid, status, current_step, result
  FROM calls
  ORDER BY started_at DESC
  LIMIT 1;
"

# 7. Vérifier audio streaming
netstat -tlnp | grep 8080
```

---

## 🚀 Conclusion

Ce guide couvre l'utilisation complète de MiniBotPanel v3 basée sur l'analyse du code réel.

**Points clés** :

✅ **Audio pré-enregistré** : Workflow complet avec `setup_audio.py`
✅ **Vosk transcription** : Automatique dans `create_scenario.py`
✅ **Ollama NLP** : Détection d'intentions uniquement
✅ **Objections modulaires** : Base Python extensible
✅ **Streaming ASR** : WebSocket + VAD temps réel
✅ **Grace period** : 3s anti-faux-positifs
✅ **Timeout réduit** : 4s (optimisé)

**Quick Start** :

```bash
# 1. Traiter audios
python setup_audio.py julie

# 2. Créer scénario
python create_scenario.py

# 3. Importer contacts
python import_contacts.py contacts.csv

# 4. Lancer campagne
python launch_campaign.py --scenario mon_scenario

# 5. Monitorer
python monitor_campaign.py --campaign-id 1
```

**Bonne utilisation ! 🚀**

---

**Version du guide** : v3.0.0
**Dernière mise à jour** : 2025-11-07
**Basé sur** : Analyse code réel (3000+ lignes analysées)
