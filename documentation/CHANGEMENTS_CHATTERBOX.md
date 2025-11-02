# 🔄 Changements - Migration Coqui TTS → Chatterbox TTS

**Date:** 2025-11-02
**Version:** 4.0 (Chatterbox Only)

---

## 📋 Résumé

Migration complète de **Coqui TTS** vers **Chatterbox TTS** (0.5B, MIT license).
Chatterbox bat ElevenLabs en tests utilisateurs (63.8% de préférence) et est gratuit/open-source.

---

## ✅ Fichiers Modifiés

### 1. `requirements.txt` - Requirements Unifié
**Changements:**
- ❌ Supprimé: `coqui-tts==0.27.2`
- ❌ Supprimé: `networkx==2.8.8` (dépendance Coqui uniquement)
- ❌ Supprimé: `pyannote.audio==3.0.1` (remplacé par diarization custom)
- ✅ Ajouté: Instructions installation Chatterbox
- ✅ Ajouté: Dépendances Chatterbox (resemble-perth, s3tokenizer, onnxruntime, gradio, etc.)
- ✅ Ajouté: Support GPU/CPU (CUDA 11.8, CUDA 12.1)
- ✅ Upgradé: `torch 2.1.2` → `2.4.0`
- ✅ Upgradé: `numpy 1.24.3` → `1.25.2` (strict)
- ✅ Ajouté: `scikit-learn` (diarization custom)

**Installation stricte:**
```bash
# 1. PyTorch 2.4.0 (CPU ou GPU)
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.0 torchaudio==2.4.0 torchvision==0.19.0

# 2. numpy 1.25.2 (STRICT)
pip install numpy==1.25.2

# 3. Transformers
pip install transformers==4.46.3

# 4. Chatterbox dependencies
pip install resemble-perth s3tokenizer onnxruntime gradio==5.44.1
pip install pykakasi spacy-pkuseg diffusers==0.29.0
pip install git+https://github.com/Vuizur/add-stress-to-epub

# 5. Chatterbox (--no-deps IMPORTANT)
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps

# 6. Reste des requirements
pip install -r requirements.txt
```

---

### 2. `system/robot_freeswitch.py` - Robot Principal
**Ligne 148:**
```python
# AVANT:
from system.services.coqui_tts import CoquiTTS
self.tts_service = CoquiTTS()
logger.info("✅ Coqui TTS loaded")

# APRÈS:
from system.services.chatterbox_tts import ChatterboxTTSService
self.tts_service = ChatterboxTTSService()
logger.info("✅ Chatterbox TTS loaded")
```

---

### 3. `create_scenario.py` - Création Scénarios
**Ligne 972:**
```python
# AVANT:
from system.services.coqui_tts import CoquiTTS
tts = CoquiTTS()

# APRÈS:
from system.services.chatterbox_tts import ChatterboxTTSService
tts = ChatterboxTTSService()
```

**Utilisation:**
- Génération TTS pour objections fonctionne identique
- Compatible avec voix clonées (dossier `voices/`)

---

### 4. `system/api/main.py` - API FastAPI
**Ligne 66:**
```python
# AVANT:
from system.services.coqui_tts import CoquiTTS
if config.COQUI_USE_GPU:
    tts = CoquiTTS()
    logger.info("✅ Coqui TTS loaded (GPU mode)")

# APRÈS:
from system.services.chatterbox_tts import ChatterboxTTSService
tts = ChatterboxTTSService()
logger.info("✅ Chatterbox TTS loaded")
```

---

### 5. `test_services.py` - Tests Services
**Ligne 27 + 109:**
```python
# AVANT:
from system.services.coqui_tts import CoquiTTS
logger.info("\n🗣️ TEST COQUI TTS")
tts = CoquiTTS()
logger.info(f"✅ Coqui disponible")
logger.info(f"🤖 Modèle: {config.COQUI_MODEL}")
logger.info(f"🎮 GPU: {'Activé' if config.COQUI_USE_GPU else 'Désactivé'}")

# APRÈS:
from system.services.chatterbox_tts import ChatterboxTTSService
logger.info("\n🗣️ TEST CHATTERBOX TTS")
tts = ChatterboxTTSService()
logger.info(f"✅ Chatterbox TTS disponible")
logger.info(f"🤖 Modèle: Chatterbox 0.5B (MIT)")
logger.info(f"🎮 Device: {tts.tts_config.get('device', 'cpu')}")
```

---

## ✨ Nouveaux Fichiers

### 1. `clean_audio_uvr.py` - Nettoyage Audio UVR
**But:** Nettoyer des audios pré-enregistrés (enlever musique/bruits)

**Usage:**
```bash
# Nettoyer un fichier
python3 clean_audio_uvr.py audio/custom/message1.wav

# Nettoyer plusieurs fichiers
python3 clean_audio_uvr.py audio/objections/*.wav

# Nettoyer tous les WAV d'un dossier
python3 clean_audio_uvr.py --all audio/custom/

# Spécifier output
python3 clean_audio_uvr.py --output audio/clean/ audio/custom/message1.wav
```

**Fonctionnalités:**
- Extraction vocals avec UVR (Ultimate Vocal Remover)
- Modèle par défaut: `UVR-MDX-NET-Voc_FT`
- Fichiers générés avec suffix `_clean.wav`
- Batch processing supporté

---

### 2. `CHATTERBOX_BEST_PRACTICES.md` - Guide Complet
**Contenu:**
- Format audio optimal (44.1kHz WAV, mono)
- Durée recommandée (60-150s total pour few-shot)
- Paramètres Chatterbox (`exaggeration`, `cfg_weight`)
- Troubleshooting (gibberish, accent, pacing)
- Workflow optimal (YouTube → UVR → Normalisation → Clonage)

---

### 3. `DEPENDENCY_MATRIX.md` - Matrice Compatibilité
**Contenu:**
- Python 3.10-3.11 UNIQUEMENT (3.13 incompatible)
- torch 2.4.0 (strict - max pour Python 3.11)
- numpy 1.25.2 (strict - cornerstone audio stack)
- Résolution conflits (numpy version hell, PyTorch, etc.)
- Ordre installation STRICT
- Tableau récapitulatif toutes dépendances

---

## 🔄 Services Modifiés

### `system/services/chatterbox_tts.py`
**Améliorations:**
- Sample rate upgradé: `22050Hz` → `44100Hz` (qualité optimale)
- Paramètres validés: `exaggeration=0.4`, `cfg_weight=0.55`
- Suppression paramètres non supportés (temperature, top_p, etc.)
- Few-shot dynamique: sélection 60-150s automatique
- Max 30 fichiers (au lieu de 20)

### `system/services/simple_diarization.py`
**Nouveau:** Diarization custom (remplace pyannote.audio)
- MFCC + Clustering (scikit-learn)
- VAD (Voice Activity Detection)
- Pas de HuggingFace token requis
- Compatible numpy 1.25.2

### `clone_voice.py`
**Améliorations:**
- Sample rate: `22050Hz` → `44100Hz`
- Sélection dynamique: 60-150s total (au lieu de 20 fichiers fixes)
- Max 30 fichiers (sécurité)
- Option `--use-uvr` (déjà présente)
- **NOUVEAU:** Découpage automatique gros fichiers YouTube
  - Si 1 seul fichier > 60s: découpe auto en chunks 10s
  - Supprime fichier original après découpage
  - Permet few-shot même avec 1 seul gros fichier YouTube

### `youtube_extract.py`
**Améliorations:**
- Sample rate: `22050Hz` → `44100Hz`
- Utilise `SimpleDiarization` (au lieu de pyannote)
- Découpage intelligent 4-10s sans couper mots

---

## 📦 Dépendances Supprimées

### Packages Retirés
- ❌ `coqui-tts==0.27.2` (remplacé par Chatterbox)
- ❌ `networkx==2.8.8` (dépendance Coqui uniquement)
- ❌ `pyannote.audio==3.0.1` (remplacé par diarization custom)

### Raisons
- **Coqui TTS:** Projet abandonné, Chatterbox meilleure qualité
- **networkx:** Utilisé uniquement par Coqui TTS
- **pyannote.audio:** Requiert numpy>=2.0 (incompatible), token HuggingFace requis

---

## 🎯 Optimisations Techniques

### Audio Processing
| Paramètre | Avant | Après | Raison |
|-----------|-------|-------|--------|
| Sample Rate | 22050 Hz | 44100 Hz | Qualité optimale (docs officielles) |
| Top Files | 20 fixe | 30 max + dynamique | Adaptatif 60-150s total |
| UVR Cleaning | Manuel | Script `clean_audio_uvr.py` | Automatisation |

### Chatterbox Parameters
```python
# Paramètres validés (docs officielles Resemble AI)
exaggeration = 0.4     # 0.3-0.5 = naturel (0.5 = default)
cfg_weight = 0.55      # 0.5 = default, 0.55 = légèrement plus lent
language_id = "fr"     # DOIT matcher audio reference

# Paramètres NON supportés (supprimés)
# ❌ temperature
# ❌ top_p
# ❌ min_p
# ❌ repetition_penalty
```

### Diarization
```python
# Custom MFCC + Clustering (remplace pyannote)
SimpleDiarization(
    min_segment_duration=0.5,
    n_mfcc=20,
    min_speakers=1,
    max_speakers=5
)
```

---

## 📝 Fichiers Inchangés

Ces fichiers utilisent déjà `chatterbox_tts.py`:
- ✅ `system/services/chatterbox_tts.py` (service principal)
- ✅ `clone_voice.py` (déjà Chatterbox-only)
- ✅ Tous les fichiers dans `system/services/` (sauf coqui_tts.py)

---

## 🚀 Migration VPS

### Sur le VPS (déjà fait):
```bash
# 1. Venv propre
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate

# 2. Installation STRICTE
pip install --upgrade pip setuptools wheel

# 3. PyTorch + numpy
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.0 torchaudio==2.4.0 torchvision==0.19.0
pip install numpy==1.25.2

# 4. Transformers
pip install transformers==4.46.3

# 5. Chatterbox dependencies
pip install resemble-perth s3tokenizer onnxruntime gradio==5.44.1
pip install pykakasi spacy-pkuseg diffusers==0.29.0
pip install git+https://github.com/Vuizur/add-stress-to-epub

# 6. Chatterbox (--no-deps)
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps

# 7. Reste
pip install -r requirements.txt
```

### Vérification:
```bash
python3 -c "
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from system.services.chatterbox_tts import ChatterboxTTSService
from system.services.simple_diarization import SimpleDiarization
from audio_separator.separator import Separator
print('✅ Tout fonctionne!')
"
```

---

## 🎉 Résultats

### Avantages Chatterbox vs Coqui:
- ✅ **Qualité:** Bat ElevenLabs (63.8% préférence)
- ✅ **License:** MIT (Coqui = MPL-2.0 restrictif)
- ✅ **Maintenance:** Actif (Coqui = abandonné)
- ✅ **Taille:** 0.5B params (Coqui = 1.1B)
- ✅ **Multilingue:** Built-in (Coqui = fichiers séparés)

### Stack Final:
```
Python 3.10/3.11
├── torch 2.4.0 (CPU/GPU)
├── numpy 1.25.2 (strict)
├── Chatterbox TTS 0.5B (SEUL moteur)
├── UVR (Ultimate Vocal Remover)
├── SimpleDiarization (custom MFCC)
├── Vosk STT
├── Ollama NLP
└── FastAPI + PostgreSQL
```

### Fichiers à Tester:
```bash
# 1. YouTube extraction + diarization
python3 youtube_extract.py

# 2. Voice cloning
python3 clone_voice.py --voice test_voice --use-uvr

# 3. Nettoyage audio custom
python3 clean_audio_uvr.py audio/custom/message.wav

# 4. Création scénario
python3 create_scenario.py

# 5. Test TTS service
python3 test_services.py
```

---

## 📚 Documentation Mise à Jour

- ✅ `CHATTERBOX_BEST_PRACTICES.md` - Guide complet
- ✅ `DEPENDENCY_MATRIX.md` - Compatibilité totale
- ✅ `requirements.txt` - Unifié GPU/CPU
- ✅ `CHANGEMENTS_CHATTERBOX.md` - Ce fichier

---

**Migration complète terminée! 🎉**
Tous les fichiers utilisent maintenant Chatterbox TTS.
