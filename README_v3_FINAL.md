# 🤖 MiniBotPanel v3 - Agent Autonome IA pour Téléprospection

**Plateforme complète de prospection téléphonique intelligente avec Agent Autonome IA**

Système professionnel d'automatisation d'appels avec **Agent Autonome** (rail-based navigation, objection matching <50ms, freestyle AI fallback, scoring cumulatif 70%, background audio), voix clonées ultra-réalistes, et intelligence artificielle conversationnelle avancée.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FreeSWITCH](https://img.shields.io/badge/FreeSWITCH-1.10+-green.svg)](https://freeswitch.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791.svg)](https://www.postgresql.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Mistral_7B-orange.svg)](https://ollama.com/)
[![Coqui](https://img.shields.io/badge/Coqui-XTTS_v2-purple.svg)](https://github.com/coqui-ai/TTS)

---

## 📋 Table des Matières

- [🎯 Nouveautés v3 FINAL](#-nouveautés-v3-final)
- [✨ Fonctionnalités Complètes](#-fonctionnalités-complètes)
- [🏗️ Architecture Agent Autonome](#️-architecture-agent-autonome)
- [🛠️ Stack Technique](#️-stack-technique)
- [🚀 Installation](#-installation)
- [📖 Workflows](#-workflows)
- [🎓 Guides Utilisateur](#-guides-utilisateur)
- [📊 Performance](#-performance)
- [🛡️ Conformité](#️-conformité)

---

## 🎯 Nouveautés v3 FINAL (Phases 1-8)

### 🤖 **AGENT AUTONOME** (Phase 6-7)

Le système utilise désormais un **agent autonome intelligent** capable de gérer naturellement les conversations :

#### **Navigation Rail-Based**
```
Hello → Q1 → Q2 → Q3 → Is_Leads → Confirm_Time → Bye
```
- **Max 2 autonomous turns** par étape (configurable)
- Gestion **2 silences consécutifs** = hangup automatique NO_ANSWER
- **Rail flexible** : adapté au scénario (3-10 questions)

#### **Gestion Objections Ultra-Rapide**
```
Client: "C'est trop cher"
  ├─ Matcher objection (50ms) → Audio pré-enregistré si match
  └─ Sinon: Freestyle AI (2-3s) → Génération réponse dynamique
      └─ Question fermée variée pour retour au rail
```

**36 questions fermées variées** pour retour naturel au rail :
- "Ça vous parle ?"
- "Vous êtes d'accord ?"
- "C'est plus clair ?"
- ...

#### **Qualification Cumulative Scoring 70%**
```json
{
  "qualification_rules": {
    "lead_threshold": 70,
    "scoring_weights": {
      "Q1": 30,
      "Q2": 30,
      "Is_Leads": 40
    }
  }
}
```
- Scoring cumulatif 0-100%
- Seuil LEAD: 70% (configurable)
- Étapes **déterminantes** vs **informatives**

---

### 🎙️ **VOICE CLONING & AUDIO** (Phases 2-4)

#### **YouTube Extract + Speaker Diarization**
```bash
python youtube_extract.py
```
- **Téléchargement YouTube** avec yt-dlp (bestaudio WAV quality 0)
- **Speaker diarization** pyannote.audio 3.1 (HuggingFace)
- **Découpage intelligent** 4-10s (détection silence 500ms pour ne pas couper mots)
- Export WAV 22050Hz mono optimisé Coqui

#### **Multi-Voice Cloning**
```bash
python clone_voice.py
```
- Détection automatique dossiers `voices/`
- **3 modes Coqui** : quick (<30s), standard (30-120s), fine-tuning (>120s)
- **Génération TTS automatique** 100-150 fichiers objections/FAQ
- Nettoyage audio : noisereduce + audio-separator (extraction vocal)

#### **Background Audio Loop**
```bash
python setup_audio.py
```
- Conversion 22050Hz mono WAV
- Normalisation volume
- **Background -8dB automatique** (mixage FreeSWITCH mux)
- Loop infini avec `uuid_displace limit=0`

**Résultat** : Voix ultra-réalistes clonées en 30-60min avec background ambiant professionnel

---

### 🛡️ **OBJECTIONS DATABASE** (Phase 5)

**80 objections + FAQ** professionnelles :

| Thématique | Objections | FAQ | Total |
|------------|-----------|-----|-------|
| **GÉNÉRAL** | 10 | 10 | 20 |
| **Finance** | 10 | 10 | 20 |
| **Crypto** | 10 | 10 | 20 |
| **Énergie** | 10 | 10 | 20 |

Structure `ObjectionEntry` :
```python
ObjectionEntry(
    keywords=["trop cher", "hors de prix", "budget"],
    response="Je comprends. En fait, 70% de nos clients économisent...",
    audio_path="finance_1_trop_cher.wav",  # Optionnel
    type="objection"
)
```

**Matcher intelligent** :
- Fuzzy matching (difflib) + mots-clés
- Latence **<50ms** vs 2-3s (TTS temps réel)
- Retour `audio_path` avec fallback TTS si manquant

---

### ⚡ **CACHE INTELLIGENT** (Phase 8)

#### **CacheManager Singleton Thread-Safe**
```python
from system.cache_manager import CacheManager

cache = CacheManager.get_instance()
```

**3 types de cache** :

1. **Scénarios Cache** (TTL 1h, Max 50)
   - Hit rate: 90%+
   - Évite lecture disque répétée

2. **Objections Cache** (TTL 30min, Max 20)
   - Filtrées par thématique (finance, crypto, etc.)
   - Accès <1ms

3. **Models Cache** (TTL infini)
   - Ollama, TTS, ASR pré-chargés
   - Réutilisation instances

#### **Pré-warm Ollama**
```python
nlp_service.prewarm()  # Au démarrage campagne
# Réduit latence 1er appel: 2-5s → <100ms
# keep_alive="30m" maintient modèle chaud
```

**Statistiques temps réel** :
```
📊 CACHE MANAGER STATISTICS
🎬 SCENARIOS CACHE:
  • Hit rate: 93.8%
  • Cache size: 12/50

🛡️ OBJECTIONS CACHE:
  • Hit rate: 94.1%
  • Themes: finance, crypto, energie

🤖 MODELS CACHE:
  • Preloaded: ollama_mistral, coqui_tts
```

---

## ✨ Fonctionnalités Complètes

### 🎯 Agent Autonome IA

| Feature | Description | Latence |
|---------|-------------|---------|
| **Rail Navigation** | Hello → Q1-Qx → Is_Leads → Confirm → Bye | N/A |
| **Objection Matching** | Fuzzy match + keywords (80 objections) | <50ms |
| **Freestyle Fallback** | Génération IA dynamique si pas de match | 2-3s |
| **Rail Return** | 36 questions fermées variées | N/A |
| **Scoring Cumulatif** | Qualification 0-100%, seuil 70% | N/A |
| **Silence Detection** | 2 silences consécutifs = hangup NO_ANSWER | N/A |
| **Background Audio** | Loop infini -8dB (office, call center, etc.) | N/A |

### 🎙️ Voice & Audio

| Feature | Technologie | Performance |
|---------|-------------|-------------|
| **YouTube Extract** | yt-dlp + pyannote 3.1 | Diarization multi-locuteurs |
| **Voice Cloning** | Coqui XTTS v2 | 3 modes (quick/standard/fine-tuning) |
| **TTS Auto** | Génération 150 fichiers | 30-60min par voix |
| **Audio Cleanup** | noisereduce + audio-separator | Suppression bruit + extraction vocal |
| **Format Optimal** | 22050Hz mono WAV SLIN16 | FreeSWITCH + Coqui optimisé |

### 🧠 Intelligence Artificielle

| Service | Technologie | Rôle |
|---------|-------------|------|
| **STT** | Vosk 0.3.45 | Transcription temps réel français offline |
| **NLP** | Ollama Mistral 7B | Intent + Sentiment + Freestyle AI |
| **TTS** | Coqui XTTS v2 | Voix clonées ultra-réalistes |
| **Diarization** | pyannote.audio 3.1 | Séparation locuteurs YouTube |
| **Objection Matcher** | Fuzzy + Keywords | Matching <50ms |

### 📊 Qualification & Scoring

- **Scoring cumulatif** 0-100% (poids par étape)
- **Seuil LEAD** : 70% (configurable 50-100%)
- **Étapes déterminantes** : Q1, Q2, Is_Leads
- **Étapes informatives** : Pas de poids
- **Normalisation automatique** poids → 100%

---

## 🏗️ Architecture Agent Autonome

### Workflow d'un Appel Agent Autonome

```
┌──────────────────────────────────────────────────────────┐
│  DÉMARRAGE CAMPAGNE                                      │
├──────────────────────────────────────────────────────────┤
│  1. Pré-warm Ollama (keep_alive 30min)                  │
│  2. Chargement cache scénarios                           │
│  3. Chargement objections thématique (finance/crypto...) │
│  4. Pré-chargement modèles (TTS, ASR)                    │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  APPEL INDIVIDUEL                                        │
├──────────────────────────────────────────────────────────┤
│  1. Originate call (SIP/PSTN)                           │
│  2. AMD (Answering Machine Detection)                    │
│  3. Si humain détecté → Navigation Rail                  │
│  4. Start background audio loop (-8dB)                   │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  ÉTAPE AUTONOME (Q1, Q2, Is_Leads...)                   │
├──────────────────────────────────────────────────────────┤
│  ┌─ Turn 1/2 ────────────────────────────────────────┐  │
│  │  1. Play message audio/TTS                        │  │
│  │  2. Listen (avec barge-in)                        │  │
│  │  3. Transcription STT → NLP intent                │  │
│  │  4. Si objection/question:                        │  │
│  │     ├─ Matcher (50ms)                             │  │
│  │     │  └─ Match → Play audio pré-enregistré       │  │
│  │     └─ Pas match → Freestyle AI (2-3s)            │  │
│  │        └─ Génération + question fermée variée     │  │
│  │  5. Si affirm → Next rail step                    │  │
│  │  6. Si silence → Compteur +1                      │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌─ Turn 2/2 (si nécessaire) ───────────────────────┐  │
│  │  ... même logique ...                             │  │
│  └───────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  QUALIFICATION FINALE                                    │
├──────────────────────────────────────────────────────────┤
│  Score = Σ(poids_étape * réponse_positive)              │
│  Si score ≥ 70% → LEAD                                  │
│  Si score < 70% → NOT_INTERESTED                        │
│  Si 2 silences → NO_ANSWER                              │
└──────────────────────────────────────────────────────────┘
```

### Exemple Concret

```
[12:34:56] 📞 Appel vers +33612345678
[12:34:57] ✅ Humain détecté (AMD)
[12:34:57] 🔊 Background audio started: office.wav (-8dB)
[12:34:57] 📚 Objections loaded: finance (20 entries)

[12:34:58] 🤖 Rail step: Hello (turn 1/2)
[12:34:58]   🔊 "Allô, bonjour Monsieur Dupont. Je suis Julie de notre banque."
[12:35:01]   📝 "Oui je vous écoute"
[12:35:01]   ✅ Intent: affirm → Next: Q1

[12:35:02] 🤖 Rail step: Q1 (turn 1/2)
[12:35:02]   🔊 "Avez-vous actuellement un crédit immobilier ?"
[12:35:05]   📝 "Oui mais c'est trop cher vos taux"
[12:35:05]   🎯 Objection detected → Matching...
[12:35:05]   ✅ Match found (42ms): "trop cher | hors de prix"
[12:35:05]   🔊 Playing: finance_1_trop_cher.wav
[12:35:08]   🔊 "Ça vous rassure un peu ?" (rail return)
[12:35:10]   📝 "Oui effectivement"
[12:35:10]   ✅ Intent: affirm → Next: Q2

[12:35:11] 🤖 Rail step: Q2 (turn 1/2)
[12:35:11]   🔊 "Seriez-vous intéressé par une renégociation ?"
[12:35:14]   📝 "Oui pourquoi pas"
[12:35:14]   ✅ Intent: affirm → Next: Is_Leads

[12:35:15] 🤖 Rail step: Is_Leads (turn 1/2)
[12:35:15]   🔊 "Puis-je faire établir une simulation personnalisée ?"
[12:35:18]   📝 "Oui d'accord"
[12:35:18]   ✅ Intent: affirm → Next: Confirm_Time

[12:35:19] 🤖 Rail step: Confirm_Time
[12:35:19]   🔊 "Parfait ! Un conseiller vous rappelle sous 48h."
[12:35:22]   → Next: Bye

[12:35:23] 🤖 Rail step: Bye
[12:35:23]   🔊 "Merci Monsieur Dupont et excellente journée !"
[12:35:25]   🔊 Background audio stopped

[12:35:26] 📊 Qualification:
   Q1 (30%) = affirm ✅
   Q2 (30%) = affirm ✅
   Is_Leads (40%) = affirm ✅
   Score: 100% → LEAD ✅

[12:35:26] ✅ Call completed: LEAD
```

---

## 🛠️ Stack Technique

### Core
- **Python 3.10+** - Backend
- **FreeSWITCH 1.10.11** - Téléphonie VoIP (SIP/ESL)
- **PostgreSQL 14+** - Base de données
- **SQLAlchemy 2.0** - ORM

### Intelligence Artificielle
- **Vosk 0.3.45** - STT offline français
- **Ollama** - NLP (Mistral 7B / Llama 3.2)
- **Coqui XTTS v2** - TTS voix clonées
- **pyannote.audio 3.1** - Speaker diarization
- **noisereduce 3.0** - Nettoyage audio
- **audio-separator 0.19** - Extraction vocal (Demucs)

### Utilities
- **yt-dlp 2024.12** - YouTube download
- **pydub** - Manipulation audio
- **soundfile** - I/O audio

### APIs & Services
- **HuggingFace** - Pyannote models (token requis)
- **OpenCNAM** - Caller ID (optionnel)
- **Bloctel API** - Liste opposition (obligatoire France)

---

## 🚀 Installation

### Prérequis

```bash
# Système
Ubuntu 20.04+ / Debian 11+
Python 3.10+
PostgreSQL 14+
FreeSWITCH 1.10.11+

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral  # ou llama3.2
```

### Installation

```bash
# 1. Clone
git clone https://github.com/votre-repo/fs_minibot_streaming.git
cd fs_minibot_streaming

# 2. Python dependencies
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
nano .env
# Configurer: DATABASE_URL, OLLAMA_URL, HUGGINGFACE_TOKEN, etc.

# 4. Database
python -c "from system.database import init_db; init_db()"

# 5. Vosk model (français)
mkdir -p models/vosk
cd models/vosk
wget https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip
unzip vosk-model-fr-0.22.zip
mv vosk-model-fr-0.22 fr

# 6. Coqui XTTS v2 (auto-download au 1er lancement)
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

### Structure Dossiers

```
fs_minibot_streaming/
├── audio/
│   ├── background/         # Background audio (office.wav, etc.)
│   ├── tts/
│   │   ├── julie/         # TTS générés pour voix "julie"
│   │   └── ...
│   └── [voice_folders]/   # Audio organisé par voix
├── voices/
│   ├── julie/             # Samples voix Julie (30s-120s)
│   ├── marc/
│   └── ...
├── scenarios/             # Scénarios JSON
├── system/
│   ├── cache_manager.py   # Phase 8: Cache intelligent
│   ├── objections_database.py  # Phase 5: 80 objections
│   ├── objection_matcher.py    # Phase 6: Matcher
│   └── services/
│       ├── ollama_nlp.py       # NLP + prewarm
│       ├── freestyle_ai.py     # Phase 6: Rail return
│       └── coqui_tts.py
├── clone_voice.py         # Phase 4: Multi-voice cloning
├── youtube_extract.py     # Phase 3: YouTube → voices
├── setup_audio.py         # Phase 2: Audio setup
├── create_scenario.py     # Phase 7: Agent autonome workflow
└── main.py               # Lancement campagnes
```

---

## 📖 Workflows

### 1. Créer Voix Clonée depuis YouTube

```bash
# Étape 1: Extraire audio YouTube avec diarization
python youtube_extract.py

# Sélection interactive:
# - URL YouTube
# - Sélection locuteur (Speaker 0, 1, 2...)
# - Export voices/[nom]/ (4-10s chunks, 22050Hz mono)

# Étape 2: Cloner voix + générer TTS objections
python clone_voice.py

# Workflow:
# 1. Détection voix dans voices/
# 2. Sélection voix à cloner
# 3. Sélection thématique (finance/crypto/energie/general)
# 4. Mode auto-détecté (quick/standard/fine-tuning)
# 5. Génération 100-150 TTS objections/FAQ
# → audio/tts/[voix]/

# Étape 3: Setup audio (normalisation + background)
python setup_audio.py

# Workflow:
# 1. Sélection dossier audio
# 2. (Optionnel) Background audio
# 3. Volume adjustment (recommandé: -3 à -5dB)
# 4. Conversion 22050Hz mono + normalisation
# 5. Background automatique -8dB
```

**Temps total** : 30-60min pour voix complète + 150 TTS

### 2. Créer Scénario Agent Autonome

```bash
python create_scenario.py

# Workflow Phase 7:
# 1. Infos générales (nom, description)
# 2. Configuration agent autonome:
#    - Voix clonée (détection auto voices/)
#    - Nom téléprospecteur (Julie, Marc, etc.)
#    - Société
#    - Background audio (optionnel)
# 3. Objectif campagne (RDV/Lead/Transfer)
# 4. Thématique (finance/crypto/energie/...)
# 5. Personnalité agent (7 profils)
# 6. Questions Q1-Qx (3-10)
#    - Marquer questions déterminantes
# 7. Configuration qualification:
#    - Seuil (default 70%)
#    - Poids auto-normalisés → 100%
# 8. Sauvegarde scenarios/scenario_[nom].json
```

**Résultat** : Scénario JSON agent_mode=true prêt

### 3. Lancer Campagne

```bash
python main.py

# Workflow:
# 1. Sélection scénario (menu interactif)
# 2. Upload CSV contacts (first_name, last_name, phone, company)
# 3. Configuration campagne (max concurrent, throttle, etc.)
# 4. Lancement:
#    - Pré-warm Ollama ✅
#    - Chargement cache scénarios ✅
#    - Chargement objections thématique ✅
#    - Start calls...
# 5. Monitoring temps réel CLI
# 6. Export CSV résultats
```

---

## 🎓 Guides Utilisateur

### Guide Rapide : Premier Appel en 10min

**Objectif** : Lancer votre première campagne agent autonome

```bash
# 1. Utiliser voix par défaut (si existe)
ls voices/julie/  # Vérifier samples

# 2. Créer scénario simple
python create_scenario.py
# → Nom: "test_finance"
# → Voix: julie
# → Thématique: finance
# → 2 questions simples

# 3. Préparer CSV (test_contacts.csv)
first_name,last_name,phone,company
Jean,Dupont,0612345678,Entreprise A
Marie,Martin,0687654321,Société B

# 4. Lancer campagne
python main.py
# → Scénario: test_finance
# → CSV: test_contacts.csv
# → Max concurrent: 2

# 5. Observer logs temps réel
# → Objection matching
# → Freestyle fallback
# → Rail navigation
# → Scoring qualification

# 6. Résultats dans results/campaign_[id]_results.csv
```

### Guide Avancé : Voix Custom + Thématique

```bash
# 1. Extraire voix depuis YouTube (vidéo 10-30min)
python youtube_extract.py
# URL: https://youtube.com/watch?v=...
# Speaker: 0 (locuteur principal)
# Output: voices/sophie/

# 2. Cloner voix + générer TTS thématique crypto
python clone_voice.py
# Voix: sophie
# Thématique: crypto
# Mode: standard (30-120s détecté)
# → 150 TTS générés (30min)

# 3. Setup audio avec background
python setup_audio.py
# Folder: audio/sophie/
# Background: office.wav
# Volume: -3dB
# → Normalisation + background -8dB

# 4. Créer scénario crypto
python create_scenario.py
# Voix: sophie
# Téléprospecteur: Sophie
# Société: CryptoTrade Pro
# Background: office.wav
# Thématique: crypto
# Questions: 3
#   Q1: Vous tradez déjà ? (déterminante, 30%)
#   Q2: Volume mensuel ? (déterminante, 30%)
#   Is_Leads: Intéressé plateforme 0.1% frais ? (40%)
# Seuil: 70%

# 5. Campagne crypto 100 prospects
python main.py
# → Scénario: crypto_prospection
# → CSV: prospects_crypto_100.csv
# → Max concurrent: 5
# → Throttle: 10 calls/min
```

**Résultat** : Campagne professionnelle crypto avec voix Sophie, 150 TTS pré-générés, objection matching <50ms, background office

---

## 📊 Performance

### Latences Mesurées

| Opération | Avant Cache | Après Cache | Gain |
|-----------|-------------|-------------|------|
| **Load scenario** | 50-100ms | <1ms | 98% |
| **Load objections** | 30-50ms | <1ms | 98% |
| **Ollama 1st call** | 2-5s | <100ms | 95% |
| **Objection match** | N/A | <50ms | N/A |
| **TTS pré-généré** | 2-3s | Instantané | 100% |

### Hit Rates Cache (après 1h campagne)

```
Scénarios: 93.8% (150 hits / 160 requests)
Objections: 94.1% (80 hits / 85 requests)
```

### Capacité Système

- **Max concurrent calls** : 50 (recommandé: 10-20)
- **Throughput** : 600 calls/heure (10 calls/min throttle)
- **Latence moyenne** : 50-200ms (hors génération TTS/Freestyle)
- **RAM usage** : 2-4GB (avec cache + models)

---

## 🛡️ Conformité

### RGPD
- ✅ Consentement explicite (opt-in)
- ✅ Droit à l'oubli (suppression contacts/calls)
- ✅ Portabilité données (export CSV)
- ✅ Sécurité données (PostgreSQL encrypted)

### Bloctel (France)
- ✅ Vérification liste opposition avant appel
- ✅ API Bloctel intégrée
- ✅ Log vérifications (audit trail)

### Téléphonie
- ✅ Présentation numéro appelant (Caller ID)
- ✅ Respect horaires légaux (9h-20h lun-ven, 10h-18h sam)
- ✅ Opt-out instantané ("Ne plus me rappeler")

---

## 📝 Changelog v3 FINAL

### Phase 1 : Fondations Audio/IA
- ✅ Dependencies : pyannote.audio, yt-dlp, noisereduce, audio-separator
- ✅ HuggingFace token configuration

### Phase 2 : Background Audio + Clone Voice
- ✅ Background audio loop FreeSWITCH (uuid_displace limit=0 mux)
- ✅ Nettoyage audio avancé (noisereduce + vocal extraction)
- ✅ setup_audio.py : normalisation + volume -8dB auto

### Phase 3 : YouTube Extract + Diarization
- ✅ youtube_extract.py : download + pyannote speaker diarization
- ✅ Découpage intelligent 4-10s (détection silence 500ms)

### Phase 4 : Multi-Voice Cloning + TTS Auto
- ✅ clone_voice.py : détection multi-voix
- ✅ Modes Coqui auto (quick/standard/fine-tuning)
- ✅ Génération 150 TTS objections/FAQ

### Phase 5 : Objections Database
- ✅ objections_database.py : 80 objections (ObjectionEntry)
- ✅ 4 thématiques complètes (GENERAL, finance, crypto, energie)
- ✅ Structure keywords + response + audio_path

### Phase 6 : Agent Autonome
- ✅ scenarios.py : support agent_mode + rail
- ✅ objection_matcher.py : load_objections_for_theme() + audio_path
- ✅ robot_freeswitch.py : _execute_autonomous_step() max_turns=2
- ✅ Gestion barge-in : matcher 50ms → freestyle fallback 2-3s
- ✅ freestyle_ai.py : 36 questions fermées variées rail return
- ✅ Gestion 2 silences = hangup NO_ANSWER

### Phase 7 : Workflow Create Scenario
- ✅ create_scenario.py : workflow agent autonome
- ✅ Collecte : voix / téléprospecteur / société / thématique
- ✅ Configuration rail : Hello → Q1-Qx → Is_Leads → Confirm → Bye
- ✅ Qualification cumulative scoring 70%

### Phase 8 : Cache & Optimisations
- ✅ cache_manager.py : Singleton thread-safe (scénarios, objections, models)
- ✅ ollama_nlp.py : prewarm() avec keep_alive 30min
- ✅ Optimisations streaming (déjà intégrées)

---

## 📞 Support & Contact

### Documentation
- README_v3_FINAL.md (ce fichier)
- Guide utilisateur complet (voir ci-dessus)
- Code comments & docstrings

### Issues & Bugs
- GitHub Issues : [lien repo]

### Commercial
- Contact : [votre email]
- Demo : [lien calendly/demo]

---

**MiniBotPanel v3 FINAL** - Agent Autonome IA pour Téléprospection Professionnelle
© 2025 - All Rights Reserved
