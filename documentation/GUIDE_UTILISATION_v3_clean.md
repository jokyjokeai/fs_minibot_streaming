# GUIDE D'UTILISATION - MiniBotPanel v3

**Guide pratique basé sur le code réel - Sans TTS, uniquement audio pré-enregistré**

Version: 3.0  
Date: 2025-11-07

---

## 📋 TABLE DES MATIÈRES

1. [Vue d'ensemble](#1-vue-densemble)
2. [Configuration .env](#2-configuration-env)
3. [Gestion des fichiers audio](#3-gestion-des-fichiers-audio)
4. [Création de scénarios](#4-création-de-scénarios)
5. [Import contacts](#5-import-contacts)
6. [Lancement d'appels](#6-lancement-dappels)
7. [Monitoring](#7-monitoring)
8. [Export résultats](#8-export-résultats)
9. [Base d'objections](#9-base-dobjections)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. VUE D'ENSEMBLE

### Architecture réelle du système

```
┌─────────────────────────────────────────────────────┐
│                 MiniBotPanel v3                     │
│           (Audio pré-enregistré uniquement)         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  FreeSWITCH ←→ ESL ←→ RobotFreeSWITCH V2           │
│       ↓                        ↓                    │
│  mod_audio_stream      Streaming ASR (Vosk + VAD)  │
│       ↓                        ↓                    │
│  WebSocket 8080         Intent NLP (Ollama)        │
│                                ↓                    │
│                        Objection Matcher            │
│                         (Python modulaire)          │
└─────────────────────────────────────────────────────┘
```

### Fonctionnalités

✅ **Audio pré-enregistré** : Fichiers WAV/MP3 dans `audio/`  
✅ **Traitement automatique** : `setup_audio.py` (normalisation + 8kHz µ-law)  
✅ **Transcription Vosk** : `create_scenario.py` transcrit automatiquement  
✅ **Streaming temps réel** : WebSocket + VAD (barge-in)  
✅ **Intent NLP** : Ollama détecte affirm/deny/question/objection  
✅ **Objections** : Base Python modulaire (system/objections_db/)  

❌ **TTS retiré** : Pas de synthèse vocale (v3 cleanup)  
❌ **Clonage vocal retiré** : Dépendait du TTS

---

## 2. CONFIGURATION .ENV

Fichier: `/home/jokyjokeai/Desktop/fs_minibot_streaming/.env`

```ini
# ═══════════════════════════════════════════════════════════
# BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════
DATABASE_URL=postgresql://minibot:minibot@localhost:5432/minibot_freeswitch

# ═══════════════════════════════════════════════════════════
# FREESWITCH ESL
# ═══════════════════════════════════════════════════════════
FREESWITCH_ESL_HOST=localhost
FREESWITCH_ESL_PORT=8021
FREESWITCH_ESL_PASSWORD=ClueCon
FREESWITCH_GATEWAY=gateway1

# ═══════════════════════════════════════════════════════════
# AUDIO (pré-enregistré uniquement)
# ═══════════════════════════════════════════════════════════
DEFAULT_VOICE=julie
FREESWITCH_SOUNDS_DIR=/usr/share/freeswitch/sounds/minibot
AUDIO_VOLUME_ADJUST=2.0          # +2dB boost
AUDIO_BACKGROUND_REDUCTION=-10.0 # -10dB pour background audio

# ═══════════════════════════════════════════════════════════
# VOSK (Speech-to-Text)
# ═══════════════════════════════════════════════════════════
VOSK_MODEL_PATH=models/vosk-model-small-fr-0.22
VOSK_SAMPLE_RATE=16000

# ═══════════════════════════════════════════════════════════
# OLLAMA (Intent NLP uniquement - pas de TTS)
# ═══════════════════════════════════════════════════════════
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b
OLLAMA_TIMEOUT=10

# ═══════════════════════════════════════════════════════════
# AMD (Answering Machine Detection)
# ═══════════════════════════════════════════════════════════
AMD_ENABLED=true
AMD_DUAL_LAYER=true
AMD_FS_TIMEOUT=5000
AMD_PYTHON_ENABLED=true
AMD_MACHINE_SPEECH_DURATION_MIN=3.0

# ═══════════════════════════════════════════════════════════
# LIMITES SYSTÈME
# ═══════════════════════════════════════════════════════════
MAX_CONCURRENT_CALLS=10
CALL_TIMEOUT=300
DELAY_BETWEEN_CALLS=2.0

# ═══════════════════════════════════════════════════════════
# RETRY
# ═══════════════════════════════════════════════════════════
RETRY_ENABLED=true
MAX_RETRIES=2
RETRY_DELAY_MINUTES=30
RETRY_BUSY_DELAY_MINUTES=5

# ═══════════════════════════════════════════════════════════
# API REST
# ═══════════════════════════════════════════════════════════
API_HOST=0.0.0.0
API_PORT=8000
API_PASSWORD=change_me_in_production

# ═══════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════
LOG_LEVEL=INFO
```

---

## 3. GESTION DES FICHIERS AUDIO

### 3.1 Organisation (basé sur system/config.py)

```
audio/                              ← FICHIERS SOURCE
├── julie/                          
│   ├── base/                       ← Audio scénario
│   │   ├── hello.wav
│   │   ├── retry_hello.wav
│   │   ├── retry_silence.wav
│   │   ├── q1.wav
│   │   ├── q2.wav
│   │   ├── is_leads.wav
│   │   ├── retry_is_leads.wav
│   │   ├── confirm_time.wav
│   │   ├── bye.wav
│   │   ├── bye_failed.wav
│   │   └── not_understood.wav
│   │
│   └── objections/                 ← Réponses objections
│       ├── pas_le_temps.wav
│       ├── trop_cher.wav
│       ├── rappeler_plus_tard.wav
│       └── ...
│
└── marie/                          ← Autre voix
    ├── base/
    └── objections/

/usr/share/freeswitch/sounds/minibot/   ← FICHIERS TRAITÉS (FreeSWITCH)
└── julie/
    ├── base/                       ← 8kHz µ-law mono
    └── objections/
```

### 3.2 Formats supportés (source)

**Fichiers source** (dans `audio/`) :
- WAV, MP3, M4A, FLAC, OGG, AAC
- Tout sample rate (sera converti)
- Mono ou stéréo (sera converti)

**Fichiers FreeSWITCH** (après `setup_audio.py`) :
- Format: WAV PCM µ-law (G.711)
- Sample rate: 8000 Hz
- Channels: Mono
- Bits: 8-bit

### 3.3 Enregistrer des fichiers audio

**Méthode 1: Audacity (recommandé)**

```bash
# 1. Ouvrir Audacity
# 2. Paramètres projet:
#    - Sample rate: 44100 Hz ou 48000 Hz
#    - Channels: Mono
# 
# 3. Enregistrer votre texte
# 4. Export:
#    File → Export → Export as WAV
#    Format: WAV (Microsoft) signed 16-bit PCM
# 
# 5. Sauvegarder dans:
#    audio/julie/base/hello.wav
```

**Méthode 2: Via service externe**

Si vous utilisez un service de synthèse (ElevenLabs, etc.):

```bash
# 1. Générer l'audio via le service
# 2. Télécharger le fichier WAV
# 3. Placer dans audio/julie/base/
# 4. Lancer setup_audio.py
```

**Méthode 3: Enregistrement micro**

```bash
# Linux avec arecord
arecord -f cd -d 10 audio/julie/base/hello.wav

# Ou via script Python
python3 -c "
import sounddevice as sd
import scipy.io.wavfile as wav

fs = 44100
duration = 10  # secondes
print('Recording...')
recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
sd.wait()
wav.write('audio/julie/base/hello.wav', fs, recording)
print('Done!')
"
```

### 3.4 Traiter les fichiers (setup_audio.py)

**Usage basique:**

```bash
python3 setup_audio.py
```

**Ce que fait setup_audio.py (analysé ligne par ligne):**

1. **Scan** : Trouve tous les fichiers dans `audio/`
2. **Normalisation** : Peak à -3dB, RMS à -18dB
3. **Ajustement volume** : +2dB par défaut (configurable)
4. **Conversion** : 8kHz mono µ-law WAV
5. **Copie** : Vers `/usr/share/freeswitch/sounds/minibot/`
6. **Permissions** : `chmod 644`, `chown freeswitch:freeswitch`

**Options avancées:**

```bash
# Ajuster volume global
python3 setup_audio.py --volume-adjust +3.0

# Réduction background plus forte
python3 setup_audio.py --background-reduction -15.0

# Re-traiter tous les fichiers
python3 setup_audio.py --force

# Simulation (ne modifie rien)
python3 setup_audio.py --dry-run

# Combinaison
python3 setup_audio.py --volume-adjust +2.5 --force
```

**Résultat attendu:**

```
══════════════════════════════════════════════════════════════
📊 RAPPORT DE TRAITEMENT
══════════════════════════════════════════════════════════════

Fichiers traités :

Fichier                    Vol. Avant   Vol. Après   Status
────────────────────────────────────────────────────────────
hello.wav                  -12.3 dB     -1.0 dB      ✅ OK
retry_hello.wav            -15.1 dB     -1.0 dB      ✅ OK
q1.wav                     -10.5 dB     -1.0 dB      ✅ OK
...

────────────────────────────────────────────────────────────

Statistiques :
   ✅ Traités avec succès : 15
   ⚠️  Avertissements     : 0
   ❌ Erreurs            : 0
   ⏱️  Temps total        : 3.2s

Configuration :
   📁 Source             : audio
   📁 Target             : /usr/share/freeswitch/sounds/minibot
   🎚️  Volume adjust      : +2.0 dB
   🔉 Background reduce  : -10.0 dB
   📻 Format             : 8000Hz mono pcm_mulaw

✅ Fichiers copiés vers FreeSWITCH avec permissions appropriées
```

**Vérifier les fichiers:**

```bash
# Vérifier présence
ls -lh /usr/share/freeswitch/sounds/minibot/julie/base/

# Tester lecture FreeSWITCH
/usr/local/freeswitch/bin/fs_cli
> originate user/1000 &playback(/usr/share/freeswitch/sounds/minibot/julie/base/hello.wav)
```

---

## 4. CRÉATION DE SCÉNARIOS

### 4.1 Utiliser create_scenario.py

**Script interactif** (analysé 900 lignes) :

```bash
python3 create_scenario.py
```

**Workflow complet:**

1. **Informations de base**
   ```
   Nom du scénario: rdv_energie
   Description: Prise de RDV audit énergétique
   Objectif: Prise de rendez-vous
   Nom entreprise: EcoEnergie
   Nom agent: Julie
   ```

2. **Configuration voix**
   - Détection automatique dans `audio/`
   - Sélection: julie, marie, etc.

3. **Configuration questions**
   ```
   Combien de questions: 3
   
   → Le système créera:
   - hello, retry_hello, retry_silence
   - q1, q2, q3
   - is_leads, retry_is_leads
   - confirm_time
   - bye, bye_failed, not_understood
   ```

4. **Thème objections**
   ```
   Thématiques disponibles:
   1) general
   2) finance
   3) energie
   4) immobilier
   
   Choix: 3
   ```

5. **Barge-in**
   ```
   Activer barge-in ? [O/n]: O
   ✅ Barge-in activé (grace period 3s)
   ```

6. **Max autonomous turns**
   ```
   Nombre max_autonomous_turns [2]: 2
   
   Explication:
   - 0 = Pas de gestion objections
   - 1 = Répond 1 fois puis continue
   - 2 = Répond jusqu'à 2 fois (recommandé)
   - 3+ = Répond plusieurs fois
   ```

7. **Enregistrement audio avec transcription Vosk**

   **IMPORTANT:** Pour chaque étape, le système:
   
   a. Cherche `audio/{voice}/base/{step}.wav`
   b. **Transcrit automatiquement avec Vosk**
   c. Affiche la transcription
   d. Demande confirmation
   e. Utilise chemin FreeSWITCH dans le JSON

   ```
   Étape: hello - Introduction initiale
     Chemin FreeSWITCH: /usr/share/freeswitch/sounds/minibot/julie/base/hello.wav
     🎤 Transcription automatique avec Vosk...
     ✅ Transcription: "Bonjour Jean, je suis Julie de EcoEnergie..."
     
     Transcription correcte ? [O/n]: O
   
   Étape: q1 - Question 1
     Chemin FreeSWITCH: /usr/share/freeswitch/sounds/minibot/julie/base/q1.wav
     🎤 Transcription automatique avec Vosk...
     ✅ Transcription: "Êtes-vous propriétaire de votre logement ?"
     
     Transcription correcte ? [O/n]: O
   ```

8. **Configuration questions déterminantes**

   Pour chaque question:
   ```
   ────────────────────────────────────────────────
   Question Q1: Êtes-vous propriétaire ?
   ────────────────────────────────────────────────
   Cette question est-elle DÉTERMINANTE (refus = élimination) ? (oui/non): oui
   
   ✅ Déterminante : Un refus → bye_failed
   
   intent_mapping généré:
   {
     "affirm": "q2",
     "deny": "bye_failed",      ← Refus = éliminé
     "unsure": "q2",
     "silence": "retry_silence",
     "*": "bye_failed"
   }
   ```

9. **Sauvegarde**
   ```
   ✅ Scénario créé avec succès!
      Fichier: scenarios/rdv_energie.json
   ```

### 4.2 Structure scénario JSON généré

**Fichier: `scenarios/rdv_energie.json`**

```json
{
  "metadata": {
    "name": "rdv_energie",
    "description": "Prise de RDV audit énergétique",
    "version": "3.0",
    "theme_file": "objections_energie",
    "voice": "julie",
    "barge_in_default": true,
    "objective": "Prise de rendez-vous"
  },

  "variables": {
    "first_name": "{{first_name}}",
    "company_name": "EcoEnergie",
    "agent_name": "Julie"
  },

  "steps": {
    "hello": {
      "message_text": "Bonjour {{first_name}}, je suis Julie de EcoEnergie...",
      "audio_file": "/usr/share/freeswitch/sounds/minibot/julie/base/hello.wav",
      "audio_type": "audio",
      "voice": "julie",
      "barge_in": true,
      "timeout": 15,
      "max_autonomous_turns": 2,
      "intent_mapping": {
        "affirm": "q1",
        "deny": "retry_hello",
        "unsure": "q1",
        "silence": "retry_silence",
        "*": "retry_hello"
      }
    },

    "q1": {
      "message_text": "Êtes-vous propriétaire de votre logement ?",
      "audio_file": "/usr/share/freeswitch/sounds/minibot/julie/base/q1.wav",
      "audio_type": "audio",
      "voice": "julie",
      "barge_in": true,
      "timeout": 15,
      "max_autonomous_turns": 2,
      "intent_mapping": {
        "affirm": "q2",
        "deny": "bye_failed",
        "unsure": "q2",
        "silence": "retry_silence",
        "*": "bye_failed"
      }
    },

    "bye": {
      "message_text": "Excellent ! Un technicien vous appellera sous 24h...",
      "audio_file": "/usr/share/freeswitch/sounds/minibot/julie/base/bye.wav",
      "audio_type": "audio",
      "voice": "julie",
      "barge_in": false,
      "timeout": 5,
      "result": "completed",
      "intent_mapping": {
        "*": "end"
      }
    },

    "end": {
      "message_text": "",
      "audio_type": "none",
      "voice": "julie",
      "barge_in": false,
      "timeout": 0,
      "result": "ended",
      "intent_mapping": {}
    }
  }
}
```

### 4.3 Intent Mapping

**Intents détectés par Ollama NLP:**

| Intent | Description | Exemples |
|--------|-------------|----------|
| `affirm` | Oui, OK | "Oui", "D'accord", "OK" |
| `deny` | Non, refus | "Non", "Pas intéressé" |
| `unsure` | Hésitation | "Peut-être", "Je ne sais pas" |
| `silence` | Timeout | (aucune réponse pendant 4-15s) |
| `question` | Question | "C'est quoi ?", "Combien ça coûte ?" |
| `objection` | Objection | "Pas le temps", "Trop cher" |
| `*` | Wildcard | Tout le reste |

### 4.4 Configuration max_autonomous_turns

Contrôle combien de fois le robot peut gérer objections/questions:

```json
{
  "hello": {
    "max_autonomous_turns": 2,
    "intent_mapping": {
      "affirm": "q1",
      "question": "hello",     ← Reste sur "hello" pour répondre
      "objection": "hello"     ← Reste sur "hello" pour traiter
    }
  }
}
```

**Valeurs:**
- `0`: Pas de gestion objections (linéaire)
- `1`: Répond 1 fois puis continue
- `2`: Répond jusqu'à 2 fois (recommandé)
- `3+`: Répond plusieurs fois

---

## 5. IMPORT CONTACTS

### 5.1 Format CSV

**Fichier: `contacts.csv`**

```csv
phone,first_name,last_name,company,email,notes
33612345678,Jean,Dupont,Entreprise A,jean@ea.fr,Prospect salon
33687654321,Marie,Martin,Entreprise B,marie@eb.fr,Lead entrant
33698765432,Pierre,Durand,,pierre@gmail.com,
```

**Colonnes:**

| Colonne | Obligatoire | Description |
|---------|-------------|-------------|
| `phone` | ✅ Oui | Numéro (format international) |
| `first_name` | ❌ Non | Prénom |
| `last_name` | ❌ Non | Nom |
| `company` | ❌ Non | Entreprise |
| `email` | ❌ Non | Email |
| `notes` | ❌ Non | Notes |

### 5.2 Import

```bash
# Import simple
python3 import_contacts.py --source contacts.csv

# Import avec création campagne
python3 import_contacts.py \
  --source contacts.csv \
  --campaign "Test Novembre" \
  --scenario rdv_energie
```

**Résultat:**

```
📥 Importing contacts from contacts.csv...
✅ Read 3 contacts from contacts.csv
✅ Validated: 3 valid, 0 invalid
✅ Inserted 3 contacts into database
📊 Creating campaign: Test Novembre
✅ Campaign created with ID: 1
   Launch with: python launch_campaign.py --campaign-id 1

✅ Import complete: 3 contacts imported
```

---

## 6. LANCEMENT D'APPELS

### 6.1 Test simple

**Script: `test_call.py`**

```bash
python3 test_call.py
```

**Modifier le script:**

```python
# Ligne 25
call_uuid = robot.originate_call('33612345678', 0, 'rdv_energie')
#                                  ↑ numéro     ↑ campaign_id  ↑ scenario
```

### 6.2 Lancer une campagne

```bash
python3 launch_campaign.py --campaign-id 1
```

**Options:**

```bash
# Batch size personnalisé
python3 launch_campaign.py --campaign-id 1 --batch-size 3

# Délai entre appels
python3 launch_campaign.py --campaign-id 1 --delay 5

# Mode test (1 seul appel)
python3 launch_campaign.py --campaign-id 1 --test-mode
```

### 6.3 Démarrer le système complet

```bash
./start_system.sh
```

**Ce script démarre:**
- PostgreSQL (si pas déjà démarré)
- FreeSWITCH (affiche warning si pas démarré)
- Ollama (démarre automatiquement)
- API REST (uvicorn sur port 8000)

---

## 7. MONITORING

### 7.1 Monitor CLI

```bash
python3 monitor_campaign.py --campaign-id 1 --refresh 2
```

**Affichage:**

```
════════════════════════════════════════════════════════════
📊 CAMPAIGN MONITOR: Test Novembre (ID: 1)
════════════════════════════════════════════════════════════
Status: running         | Scenario: rdv_energie
Started: 2025-11-07 10:30:00
────────────────────────────────────────────────────────────

📈 PROGRESS:
  Total contacts:        100
  Completed:              45 ( 45.0%)
  In progress:             5
  Pending:                50

🎯 RESULTS:
  Leads:                  12 ( 26.7%)
  Not interested:         18
  Callbacks:               5
  No answer:               8
  Answering machines:      2
  Failed:                  0

⚡ PERFORMANCE:
  Avg duration:         38.5s
  Conversion rate:      26.7%
  Calls/min:             1.50
  Campaign duration:    0h 30m

💭 SENTIMENT:
  Positive:               15 ( 33.3%)
  Neutral:                20 ( 44.4%)
  Negative:               10 ( 22.2%)

════════════════════════════════════════════════════════════
Last update: 10:45:23
Press Ctrl+C to stop monitoring
════════════════════════════════════════════════════════════
```

### 7.2 Logs

```bash
# Log général
tail -f logs/misc/system.robot_freeswitch_20251107.log

# Erreurs uniquement
tail -f logs/errors/system.robot_freeswitch_errors.log

# Filtrer par UUID
tail -f logs/misc/system.robot_freeswitch_20251107.log | grep "a5d8f2c4"
```

---

## 8. EXPORT RÉSULTATS

### 8.1 Export CSV

```bash
python3 export_campaign.py --campaign-id 1
```

**Fichiers générés:**

```
campaign_1_export.csv          # Données complètes
campaign_1_export_summary.txt  # Résumé stats
```

**Colonnes CSV:**

| Colonne | Description |
|---------|-------------|
| `call_id` | ID appel |
| `call_uuid` | UUID FreeSWITCH |
| `phone` | Numéro |
| `first_name` | Prénom |
| `status` | COMPLETED, IN_PROGRESS, FAILED |
| `result` | lead, not_interested, callback, no_answer |
| `duration_seconds` | Durée |
| `started_at` | Date/heure début |
| `ended_at` | Date/heure fin |
| `amd_result` | HUMAN, MACHINE, UNKNOWN |
| `sentiment` | POSITIVE, NEUTRAL, NEGATIVE |
| `transcriptions` | Transcriptions (séparées par `|`) |
| `intents` | Intents détectés |
| `audio_file` | Fichier enregistrement |
| `notes` | Notes |
| `retry_count` | Nombre retry |

---

## 9. BASE D'OBJECTIONS

### 9.1 Système modulaire Python

**Structure:**

```
system/objections_db/
├── __init__.py
├── objections_general.py
├── objections_finance.py
├── objections_energie.py
└── objections_immobilier.py
```

### 9.2 Structure fichier objection

**Fichier: `system/objections_db/objections_energie.py`**

```python
"""
Base d'objections - Énergie et Rénovation
"""
from dataclasses import dataclass
from typing import List

@dataclass
class ObjectionEntry:
    keywords: List[str]
    category: str
    audio_file: str
    text_fallback: str

OBJECTIONS = [
    ObjectionEntry(
        keywords=[
            "pas le temps",
            "occupé",
            "très pris"
        ],
        category="timing",
        audio_file="objections/pas_le_temps.wav",
        text_fallback="Je comprends que vous soyez occupé..."
    ),

    ObjectionEntry(
        keywords=[
            "trop cher",
            "prix",
            "budget"
        ],
        category="price",
        audio_file="objections/prix.wav",
        text_fallback="L'audit est gratuit..."
    ),
]
```

### 9.3 Créer sa propre base

```bash
cd system/objections_db/
nano objections_votre_theme.py
```

**Template:**

```python
from dataclasses import dataclass
from typing import List

@dataclass
class ObjectionEntry:
    keywords: List[str]
    category: str
    audio_file: str
    text_fallback: str

OBJECTIONS = [
    ObjectionEntry(
        keywords=["mot clé 1", "mot clé 2"],
        category="votre_categorie",
        audio_file="objections/votre_fichier.wav",
        text_fallback="Texte si audio absent"
    ),
]
```

### 9.4 Enregistrer audios objections

```bash
# 1. Créer fichiers dans audio/julie/objections/
mkdir -p audio/julie/objections/

# 2. Enregistrer chaque réponse
#    - pas_le_temps.wav
#    - prix.wav
#    - etc.

# 3. Traiter
python3 setup_audio.py

# 4. Vérifier
ls -lh /usr/share/freeswitch/sounds/minibot/julie/objections/
```

### 9.5 Utiliser dans scénario

Dans `create_scenario.py`, sélectionner le thème:

```
Thématiques disponibles:
1) general
2) finance
3) energie
4) votre_theme

Choix: 4
```

Le JSON contiendra:

```json
{
  "metadata": {
    "theme_file": "objections_votre_theme"
  }
}
```

---

## 10. TROUBLESHOOTING

### 10.1 Aucun appel ne démarre

**Vérifier campagne:**

```bash
python3 -c "
from system.database import SessionLocal
from system.models import Campaign

db = SessionLocal()
campaign = db.query(Campaign).filter(Campaign.id == 1).first()
print(f'Status: {campaign.status.value}')
"
```

Si status = "completed", réinitialiser:

```bash
python3 -c "
from system.database import SessionLocal
from system.models import Campaign, CampaignStatus

db = SessionLocal()
campaign = db.query(Campaign).filter(Campaign.id == 1).first()
campaign.status = CampaignStatus.PENDING
db.commit()
print('✅ Réinitialisé')
"
```

### 10.2 FreeSWITCH ne répond pas

```bash
# Vérifier status
sudo systemctl status freeswitch

# Démarrer
sudo systemctl start freeswitch

# Tester ESL
/usr/local/freeswitch/bin/fs_cli
```

### 10.3 Audio ne joue pas

```bash
# Vérifier fichiers
ls -lh /usr/share/freeswitch/sounds/minibot/julie/base/

# Si vide, traiter
python3 setup_audio.py

# Vérifier permissions
sudo chown -R freeswitch:freeswitch /usr/share/freeswitch/sounds/minibot/
sudo chmod -R 644 /usr/share/freeswitch/sounds/minibot/**/*.wav
sudo chmod -R 755 /usr/share/freeswitch/sounds/minibot/**/

# Tester lecture
/usr/local/freeswitch/bin/fs_cli
> originate user/1000 &playback(/usr/share/freeswitch/sounds/minibot/julie/base/hello.wav)
```

### 10.4 Vosk ne transcrit pas

```bash
# Vérifier modèle
ls -lh models/vosk-model-small-fr-0.22/

# Si absent, télécharger
cd models/
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
unzip vosk-model-small-fr-0.22.zip

# Tester
python3 -c "
from vosk import Model
model = Model('models/vosk-model-small-fr-0.22')
print('✅ Modèle OK')
"
```

### 10.5 Ollama timeout

```bash
# Vérifier Ollama
curl http://localhost:11434/api/tags

# Si erreur, démarrer
ollama serve

# Vérifier modèle
ollama list

# Si absent
ollama pull mistral:7b
```

### 10.6 Port 8080 déjà utilisé

```bash
# Trouver processus
sudo lsof -i :8080

# Tuer processus
sudo kill -9 <PID>

# Ou tuer tous python3
pkill -f "python3.*robot_freeswitch"
```

### 10.7 Barge-in trop sensible

**Augmenter grace period:**

Fichier: `system/robot_freeswitch_v2.py` ligne 972

```python
# De 3s à 5s
if elapsed_since_audio_start < 5.0:
    return
```

**Réduire sensibilité VAD:**

Fichier: `system/services/streaming_asr.py` ligne 80

```python
# De mode 2 à mode 3 (plus strict)
self.vad = webrtcvad.Vad(3)
```

### 10.8 Timeout trop court

Fichier: `system/robot_freeswitch_v2.py`

```python
# Ligne 1169 + 1261
timeout = step_config.get("timeout", 10)  # 10s au lieu de 4s
```

Ou dans le scénario JSON:

```json
{
  "hello": {
    "timeout": 20
  }
}
```

---

## ANNEXES

### A. Commandes rapides

```bash
# Configuration
python3 setup_database.py
python3 setup_audio.py

# Scénarios
python3 create_scenario.py

# Contacts & Campagnes
python3 import_contacts.py --source contacts.csv --campaign "Test"
python3 launch_campaign.py --campaign-id 1
python3 monitor_campaign.py --campaign-id 1
python3 export_campaign.py --campaign-id 1

# Tests
python3 test_call.py

# Système
./start_system.sh
./stop_system.sh
```

### B. Structure fichiers

```
fs_minibot_streaming/
├── .env
├── requirements.txt
├── setup_database.py
├── setup_audio.py
├── create_scenario.py
├── import_contacts.py
├── launch_campaign.py
├── monitor_campaign.py
├── export_campaign.py
├── test_call.py
├── start_system.sh
├── stop_system.sh
│
├── audio/
│   └── julie/
│       ├── base/
│       └── objections/
│
├── scenarios/
│   └── rdv_energie.json
│
├── models/
│   └── vosk-model-small-fr-0.22/
│
├── system/
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── scenarios.py
│   ├── robot_freeswitch_v2.py
│   │
│   ├── services/
│   │   ├── vosk_stt.py
│   │   ├── ollama_nlp.py
│   │   ├── streaming_asr.py
│   │   └── amd_service.py
│   │
│   └── objections_db/
│       ├── objections_general.py
│       ├── objections_finance.py
│       └── objections_energie.py
│
└── logs/
    ├── misc/
    └── errors/
```

---

**Version:** 3.0  
**Date:** 2025-11-07  
**Auteur:** MiniBotPanel v3 Team  

**Système basé sur audio pré-enregistré uniquement (sans TTS)**
