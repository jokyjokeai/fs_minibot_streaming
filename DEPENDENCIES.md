# 📦 Dépendances Compatibles - MiniBotPanel v3

## ✅ Configuration Testée et Validée

### Python Version
- **Python 3.10** ✅ (recommandé)
- **Python 3.11** ✅ (recommandé)
- **Python 3.12** ⚠️ (peut fonctionner mais non testé)
- **Python 3.13** ❌ (INCOMPATIBLE - PyTorch 2.4.0 max = Python 3.11)

---

## 🎯 Stack Principal

### PyTorch Ecosystem (FONDATION)
```
torch==2.4.0 (CPU)
torchaudio==2.4.0
torchvision==0.19.0
numpy==1.25.2
```

**CRITIQUE:** Installer EN PREMIER, avant tout autre package.

---

## 🎙️ TTS Engines (Text-to-Speech)

### 1. Chatterbox TTS (PRIMARY)
```bash
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps
```

- **Modèle:** 0.5B Llama-based
- **License:** MIT
- **Langues:** Multilingue (français excellent)
- **Note:** Installer avec `--no-deps`, fonctionne avec torch 2.4.0
- **Dépendances:** transformers==4.46.3

### 2. Coqui TTS (BACKUP)
```
TTS==0.22.0
```

- **Modèle:** XTTS v2
- **License:** MPL 2.0
- **Langues:** Multilingue
- **Note:** Backup si Chatterbox échoue
- **Max version:** 0.22.0 (dernière compatible numpy<2.0)

---

## 🎵 Audio Processing

### Extraction Vocale (UVR)
```
audio-separator==0.12.0
```

- **Fonction:** Ultimate Vocal Remover
- **Usage:** Nettoie audio pour clonage vocal
- **Modèles:** Téléchargés automatiquement

### Bibliothèques Audio Core
```
soundfile==0.12.1
pydub==0.25.1
scipy==1.11.4
librosa==0.10.1
webrtcvad==2.0.10
noisereduce==3.0.2
```

---

## 🎤 Speaker Diarization - SYSTÈME MAISON

### IMPORTANT: pyannote.audio RETIRÉ

**Ancien système (ABANDONNÉ):**
```
❌ pyannote.audio (incompatible avec numpy<2.0)
❌ HuggingFace token requis
❌ Dépendances complexes
```

**Nouveau système (MAISON):**
```python
system/services/simple_diarization.py
```

**Dépendances:**
```
scikit-learn>=1.3.2
librosa (déjà installé)
numpy (déjà installé)
```

**Avantages:**
- ✅ Pas de HuggingFace token
- ✅ Compatible numpy 1.25.2
- ✅ Basé sur MFCC + Clustering
- ✅ Performance suffisante pour voice cloning
- ✅ Simple à maintenir

**Technique:**
1. VAD (Voice Activity Detection) - détection parole
2. MFCC (Mel-Frequency Cepstral Coefficients) - empreintes vocales
3. Agglomerative Clustering - regroupement par similarité

---

## 📥 YouTube Extraction

```
yt-dlp>=2024.10.22
```

**Note:** Toujours garder à jour (YouTube change son API fréquemment)

```bash
pip install --upgrade yt-dlp
```

---

## 🗣️ Speech-to-Text

```
vosk==0.3.45
```

**Modèle requis (français):**
```bash
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
unzip vosk-model-small-fr-0.22.zip -d models/
```

---

## 🤖 NLP & AI

```
ollama>=0.6.0
requests==2.31.0
transformers==4.46.3
```

**Installation Ollama (séparée):**
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Télécharger modèle
ollama pull mistral:7b
```

---

## 🌐 Web Framework

```
fastapi==0.118.2
uvicorn[standard]==0.27.0
python-multipart==0.0.6
pydantic==2.12.0
pydantic-settings>=2.1.0
```

---

## 🗄️ Database

```
sqlalchemy==2.0.25
psycopg2-binary==2.9.11
alembic==1.13.1
```

**System dependencies:**
```bash
# Ubuntu/Debian
apt-get install -y postgresql-14 libpq-dev

# macOS
brew install postgresql
```

---

## 🛠️ Utilities

```
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

---

## 📋 Installation Ordre STRICT

### Option 1: Script Automatisé (RECOMMANDÉ)

```bash
bash install_complete_system.sh
```

### Option 2: Installation Manuelle

```bash
# 1. Créer venv
python3.11 -m venv venv
source venv/bin/activate

# 2. Upgrade pip
pip install --upgrade pip setuptools wheel

# 3. PyTorch + numpy (EN PREMIER)
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.0 \
    torchaudio==2.4.0 \
    torchvision==0.19.0

pip install numpy==1.25.2

# 4. Transformers
pip install transformers==4.46.3

# 5. TTS Engines
pip install TTS==0.22.0
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps

# 6. Reste des dépendances
pip install -r requirements-unified.txt
```

---

## ⚠️ Conflits de Dépendances Résolus

### 1. numpy Version Conflict

**Problème:**
- Coqui TTS veut `numpy<2.0`
- pyannote.audio 3.1+ veut `numpy>=2.0`

**Solution:**
- ✅ Utiliser numpy==1.25.2
- ✅ Retirer pyannote.audio
- ✅ Utiliser simple_diarization.py (système maison)

### 2. PyTorch Version Conflict

**Problème:**
- Chatterbox veut `torch>=2.6.0`
- UVR compatible jusqu'à `torch==2.4.0`

**Solution:**
- ✅ Installer Chatterbox avec `--no-deps`
- ✅ Chatterbox fonctionne avec torch 2.4.0 (testé)

### 3. Python 3.13 Incompatibilité

**Problème:**
- PyTorch 2.4.0 max = Python 3.11
- TTS 0.22.0 max = Python 3.11

**Solution:**
- ✅ Utiliser Python 3.10 ou 3.11
- ❌ NE PAS upgrader vers Python 3.13

### 4. pyannote.audio Abandonné

**Problème:**
- Dépendances complexes
- HuggingFace token requis
- Incompatible numpy<2.0
- 404 errors sur modèles

**Solution:**
- ✅ Système maison (MFCC + Clustering)
- ✅ Pas de token externe
- ✅ Compatible toute la stack

---

## 🧪 Vérification Installation

```bash
# Version Python
python3 --version  # 3.10.x ou 3.11.x

# PyTorch
python3 -c "import torch; print(f'PyTorch: {torch.__version__}')"
# Attendu: 2.4.0+cpu

# numpy
python3 -c "import numpy; print(f'numpy: {numpy.__version__}')"
# Attendu: 1.25.2

# Coqui TTS
python3 -c "from TTS.api import TTS; print('✅ Coqui TTS OK')"

# Chatterbox
python3 -c "from chatterbox.model import ChatterboxMultilingualTTS; print('✅ Chatterbox OK')"

# UVR
python3 -c "from audio_separator.separator import Separator; print('✅ UVR OK')"

# Diarization maison
python3 -c "from system.services.simple_diarization import SimpleDiarization; print('✅ Diarization OK')"

# YouTube
python3 -c "import yt_dlp; print('✅ yt-dlp OK')"
```

---

## 📊 Comparaison Versions

| Package | Version Actuelle | Max Compatible | Notes |
|---------|-----------------|----------------|-------|
| Python | 3.10/3.11 | 3.11 | 3.13 incompatible |
| torch | 2.4.0 | 2.4.0 | UVR max |
| numpy | 1.25.2 | 1.26.x | TTS max <2.0 |
| TTS | 0.22.0 | 0.22.0 | Dernière numpy<2.0 |
| transformers | 4.46.3 | 4.55.x | Compatible stack |
| librosa | 0.10.1 | 0.11.x | Stable |
| scikit-learn | 1.3.2+ | latest | Diarization |

---

## 🚀 Quick Start

```bash
# 1. Clone repo
git clone https://github.com/your-repo/fs_minibot_streaming
cd fs_minibot_streaming

# 2. Installer tout
bash install_complete_system.sh

# 3. Télécharger modèle Vosk
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
unzip vosk-model-small-fr-0.22.zip -d models/

# 4. Installer Ollama
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.ai/install.sh | sh
ollama pull mistral:7b

# 5. Configurer
cp .env.example .env
# Éditer .env (plus besoin de HUGGINGFACE_TOKEN!)

# 6. Tester
python3 youtube_extract.py  # Extraction + diarization maison
python3 clone_voice_chatterbox.py  # Clonage vocal
```

---

## 📝 Changelog Dépendances

### v3.2 (Current) - Système Maison
- ✅ Retiré pyannote.audio
- ✅ Ajouté simple_diarization.py (MFCC + Clustering)
- ✅ Ajouté Chatterbox TTS (primary)
- ✅ Ajouté audio-separator (UVR)
- ✅ Upgradé torch 2.1.2 → 2.4.0
- ✅ Plus besoin HuggingFace token

### v3.1 (Previous) - pyannote
- ❌ pyannote.audio 3.0.1 (problèmes)
- ❌ torch 2.1.2 (ancien)
- ❌ HuggingFace token requis

---

## 🆘 Troubleshooting

### Erreur: "numpy 2.x installed"
```bash
pip uninstall numpy -y
pip install numpy==1.25.2
```

### Erreur: "torch version mismatch"
```bash
pip uninstall torch torchaudio torchvision -y
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.0 torchaudio==2.4.0 torchvision==0.19.0
```

### Erreur: "Chatterbox not found"
```bash
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps
```

### Erreur: "simple_diarization import error"
```bash
pip install scikit-learn librosa numpy
```

---

## 📞 Support

- Issues: https://github.com/your-repo/issues
- Documentation: ./docs/
- Logs: ./logs/

---

**Dernière mise à jour:** 2025-11-02
**Version:** 3.2 (Système Diarization Maison)
