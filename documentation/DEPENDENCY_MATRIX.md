# 📊 Matrice de Compatibilité des Dépendances

## Configuration Système

**Python:** 3.10 ou 3.11 (MAX - 3.13 incompatible)
**OS:** Linux, macOS
**Dernière vérification:** 2025-11-02

---

## 🔴 Dépendances CRITIQUES (Ordre d'Installation)

### Niveau 1: PyTorch Ecosystem (INSTALLER EN PREMIER)

```bash
torch==2.4.0 (CPU)
torchaudio==2.4.0
torchvision==0.19.0
numpy==1.25.2
```

**Contraintes:**
- torch 2.4.0 = MAX pour Python 3.11
- torch >2.4.0 nécessite Python 3.12+ (incompatible avec projet)
- numpy 1.25.2 = MAX pour compatibilité audio stack
- numpy >=2.0 casse audio-separator, librosa, scipy

**Dépendances de torch:**
- filelock
- fsspec
- jinja2
- sympy
- typing-extensions

---

### Niveau 2: Transformers

```bash
transformers==4.46.3
```

**Contraintes:**
- Requiert torch (déjà installé)
- Requiert numpy<2.0 (déjà installé)
- Compatible Python 3.10-3.11

**Dépendances:**
- huggingface-hub
- safetensors
- tokenizers
- regex
- tqdm

---

### Niveau 3: TTS Engine (Chatterbox)

```bash
Chatterbox TTS (git+https://github.com/resemble-ai/chatterbox.git)
```

**Installation:** `pip install --no-deps` (IMPORTANT)

**Contraintes:**
- Officiel: veut torch>=2.6.0 (mais fonctionne avec 2.4.0 ✅)
- Nécessite transformers
- Fonctionne avec numpy 1.25.2 ✅

**Pourquoi --no-deps:**
- Évite upgrade automatique torch 2.4.0 → 2.6.0+
- On utilise déjà les bonnes versions de dépendances

---

## 🎵 Audio Processing Stack

### Core Libraries

| Package | Version | Requiert Python | Requiert numpy | Compatible torch 2.4 |
|---------|---------|----------------|---------------|---------------------|
| soundfile | 0.12.1 | >=3.7 | <2.0 | ✅ |
| pydub | 0.25.1 | >=3.7 | N/A | ✅ |
| scipy | 1.11.4 | >=3.9,<3.13 | ==1.25.2 | ✅ |
| librosa | 0.10.1 | >=3.7,<3.12 | <2.0 | ✅ |
| webrtcvad | 2.0.10 | >=3.6 | N/A | ✅ |
| noisereduce | 3.0.2 | >=3.7 | <2.0 | ✅ |

### Matrice de Compatibilité

```
numpy 1.25.2 ✅
  ├── scipy 1.11.4 ✅
  ├── librosa 0.10.1 ✅
  ├── soundfile 0.12.1 ✅
  └── noisereduce 3.0.2 ✅

torch 2.4.0 ✅
  ├── torchaudio 2.4.0 (MUST MATCH) ✅
  ├── torchvision 0.19.0 ✅
  ├── audio-separator 0.12.0 ✅
  └── Chatterbox (accepte 2.4.0) ✅
```

### UVR (Ultimate Vocal Remover)

```bash
audio-separator==0.12.0
```

**Contraintes:**
- Requiert torch<=2.4.0 ✅
- Compatible numpy<2.0 ✅
- Python 3.10-3.11 ✅

**Dépendances:**
- onnxruntime (installé automatiquement)
- librosa (déjà installé)

---

## 🎤 Speaker Diarization (Système Maison)

```bash
scikit-learn>=1.3.2
```

**Contraintes:**
- Requiert numpy 1.25.2 ✅
- Requiert scipy 1.11.4 ✅
- Python 3.10-3.11 ✅

**Dépendances:**
- joblib
- threadpoolctl

**Utilise aussi:**
- librosa (déjà installé) - pour MFCC
- numpy (déjà installé) - pour clustering

---

## 📥 YouTube Extraction

```bash
yt-dlp>=2024.10.22
```

**Contraintes:**
- Aucune contrainte stricte
- Toujours garder à jour (YouTube change API)
- Requiert ffmpeg (système)

**Dépendances:**
- certifi
- mutagen
- pycryptodome
- websockets
- brotli

---

## 🗣️ Speech-to-Text (Vosk)

```bash
vosk==0.3.45
```

**Contraintes:**
- Requiert soundfile ✅
- Requiert scipy (indirect) ✅
- Python 3.7-3.11 ✅

**Dépendances:**
- cffi
- requests
- tqdm
- srt

---

## 🌐 Web Framework

### FastAPI Stack

| Package | Version | Compatible Python | Notes |
|---------|---------|------------------|-------|
| fastapi | 0.118.2 | >=3.8 | ✅ |
| uvicorn | 0.27.0 | >=3.8 | ✅ |
| pydantic | 2.12.0 | >=3.8 | ✅ |
| pydantic-settings | >=2.1.0 | >=3.8 | ✅ |
| python-multipart | 0.0.6 | >=3.7 | ✅ |

**Contraintes:**
- pydantic v2.x (pas v1.x)
- Tous compatibles Python 3.10-3.11 ✅

---

## 🗄️ Database

```bash
sqlalchemy==2.0.25
psycopg2-binary==2.9.11
alembic==1.13.1
```

**Contraintes:**
- SQLAlchemy 2.x (pas 1.x)
- psycopg2-binary (pas psycopg2 - compile nécessaire)
- Python 3.10-3.11 ✅

**System Dependencies:**
- PostgreSQL 14+ (apt/brew install)
- libpq-dev (headers PostgreSQL)

---

## 🤖 NLP & AI

```bash
ollama>=0.6.0
requests==2.31.0
```

**Contraintes:**
- Ollama (installation séparée via brew/curl)
- Aucun conflit avec stack

---

## 🔧 Utilities

```bash
python-dotenv==1.1.1
python-json-logger==2.0.7
colorama==0.4.6
click==8.3.0
tabulate==0.9.0
openpyxl==3.1.2
phonenumbers==8.13.27
invoke==2.2.1
tqdm>=4.66.0
prometheus-client==0.19.0
```

**Contraintes:**
- Tous compatibles Python 3.10-3.11 ✅
- Aucun conflit avec stack audio/ML

---

## ⚠️ Conflits Résolus

### 1. numpy Version Hell

**Problème:**
```
Chatterbox veut: torch>=2.6.0 → numpy>=2.0
audio-separator veut: torch<=2.4.0 → numpy<2.0
librosa veut: numpy<2.0
scipy 1.11.4 veut: numpy<2.0
```

**Solution:**
```bash
✅ numpy==1.25.2 (strict)
✅ torch==2.4.0 (strict)
✅ Installer Chatterbox avec --no-deps
```

### 2. PyTorch Version Conflict

**Problème:**
```
Chatterbox setup.py: requires torch>=2.6.0
UVR: compatible jusqu'à torch==2.4.0
```

**Solution:**
```bash
✅ torch==2.4.0 (testé et fonctionne)
✅ --no-deps pour Chatterbox
```

### 3. Python 3.13 Incompatibilité

**Problème:**
```
torch 2.4.0 max = Python 3.11
librosa 0.10.1 max = Python 3.12
```

**Solution:**
```bash
✅ Python 3.10 ou 3.11 UNIQUEMENT
❌ NE PAS upgrader vers 3.12+
```

### 4. Coqui TTS + networkx

**Problème:**
```
TTS==0.22.0 requiert networkx==2.8.8
Conflit avec autres packages
```

**Solution:**
```bash
✅ Coqui TTS RETIRÉ
✅ networkx RETIRÉ (inutilisé)
✅ Chatterbox seul (meilleure qualité)
```

---

## 📋 Ordre d'Installation STRICT

```bash
# 1. System dependencies
apt-get install -y ffmpeg postgresql-14 libpq-dev

# 2. Venv
python3.11 -m venv venv
source venv/bin/activate

# 3. Pip upgrade
pip install --upgrade pip setuptools wheel

# 4. PyTorch + numpy (CRITIQUE - EN PREMIER)
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.0 torchaudio==2.4.0 torchvision==0.19.0
pip install numpy==1.25.2

# 5. Transformers
pip install transformers==4.46.3

# 6. Chatterbox (--no-deps IMPORTANT)
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps

# 7. Audio stack
pip install soundfile==0.12.1 pydub==0.25.1 scipy==1.11.4 \
    librosa==0.10.1 webrtcvad==2.0.10 noisereduce==3.0.2

# 8. UVR
pip install audio-separator==0.12.0

# 9. Diarization
pip install scikit-learn>=1.3.2

# 10. YouTube
pip install yt-dlp>=2024.10.22

# 11. STT
pip install vosk==0.3.45

# 12. NLP
pip install ollama>=0.6.0 requests==2.31.0

# 13. Web framework
pip install fastapi==0.118.2 uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 pydantic==2.12.0 pydantic-settings>=2.1.0

# 14. Database
pip install sqlalchemy==2.0.25 psycopg2-binary==2.9.11 alembic==1.13.1

# 15. Utilities
pip install python-dotenv==1.1.1 python-json-logger==2.0.7 \
    colorama==0.4.6 click==8.3.0 tabulate==0.9.0 \
    openpyxl==3.1.2 phonenumbers==8.13.27 invoke==2.2.1 \
    tqdm>=4.66.0 prometheus-client==0.19.0
```

---

## ✅ Vérification Compatibilité

### Test Suite

```bash
# Python version
python3 --version  # 3.10.x ou 3.11.x

# Core ML stack
python3 -c "import torch; print(f'torch: {torch.__version__}')"  # 2.4.0+cpu
python3 -c "import numpy; print(f'numpy: {numpy.__version__}')"  # 1.25.2
python3 -c "import transformers; print(f'transformers: {transformers.__version__}')"  # 4.46.3

# Chatterbox
python3 -c "from chatterbox.model import ChatterboxMultilingualTTS; print('✅ Chatterbox OK')"

# Audio stack
python3 -c "import librosa, scipy, soundfile, noisereduce; print('✅ Audio stack OK')"

# UVR
python3 -c "from audio_separator.separator import Separator; print('✅ UVR OK')"

# Diarization
python3 -c "from system.services.simple_diarization import SimpleDiarization; print('✅ Diarization OK')"

# YouTube
python3 -c "import yt_dlp; print('✅ yt-dlp OK')"

# STT
python3 -c "import vosk; print('✅ Vosk OK')"

# Web
python3 -c "import fastapi, uvicorn; print('✅ FastAPI OK')"

# Database
python3 -c "import sqlalchemy, psycopg2; print('✅ Database OK')"
```

---

## 🚨 Problèmes Connus

### 1. Warnings Chatterbox

```
UserWarning: torch.load with weights_only=False
```

**Impact:** Aucun - juste un warning
**Solution:** Ignorer (sera corrigé dans Chatterbox upstream)

### 2. torchaudio Backend Deprecated

```
torchaudio._backend.set_audio_backend has been deprecated
```

**Impact:** Aucun - juste un warning
**Solution:** Ajouté `warnings.filterwarnings("ignore")` dans code

### 3. numpy Future Warnings

```
FutureWarning: casting complex to real discards imaginary part
```

**Impact:** Aucun - vient de librosa interne
**Solution:** Déjà filtré dans `simple_diarization.py`

---

## 📊 Tableau Récapitulatif

| Catégorie | Packages | Python | numpy | torch | Status |
|-----------|----------|--------|-------|-------|--------|
| ML Core | torch, numpy, transformers | 3.10-3.11 | 1.25.2 | 2.4.0 | ✅ |
| TTS | Chatterbox | 3.10-3.11 | 1.25.2 | 2.4.0 | ✅ |
| Audio Core | librosa, scipy, soundfile | 3.10-3.11 | 1.25.2 | N/A | ✅ |
| Audio Tools | noisereduce, webrtcvad, pydub | 3.10-3.11 | 1.25.2 | N/A | ✅ |
| UVR | audio-separator | 3.10-3.11 | 1.25.2 | 2.4.0 | ✅ |
| Diarization | scikit-learn | 3.10-3.11 | 1.25.2 | N/A | ✅ |
| YouTube | yt-dlp | 3.7+ | N/A | N/A | ✅ |
| STT | vosk | 3.7-3.11 | N/A | N/A | ✅ |
| Web | fastapi, uvicorn, pydantic | 3.8+ | N/A | N/A | ✅ |
| Database | sqlalchemy, psycopg2 | 3.7+ | N/A | N/A | ✅ |
| NLP | ollama | 3.8+ | N/A | N/A | ✅ |

---

## 🎯 Résumé

### ✅ Stack Validée

- **0 conflits** après suppression Coqui TTS + networkx
- **Toutes les dépendances** compatibles entre elles
- **Python 3.10 ou 3.11** requis (3.13 incompatible)
- **numpy 1.25.2** (pierre angulaire - ne jamais changer)
- **torch 2.4.0** (maximum compatible avec stack)

### 📦 Packages Retirés

- ❌ **TTS==0.22.0** (Coqui TTS - remplacé par Chatterbox)
- ❌ **networkx==2.8.8** (dépendance Coqui TTS uniquement)

### 🎉 Optimisations

- **Sample rate:** 22050 → 44100 Hz (qualité optimale)
- **Top fichiers:** 10 → 20 (meilleur scoring)
- **Paramètres Chatterbox:** Validés selon docs officielles
- **Diarization:** Maison (sans pyannote, sans HuggingFace token)

---

**Dernière mise à jour:** 2025-11-02
**Version:** 4.0 (Chatterbox Only + Custom Diarization)
