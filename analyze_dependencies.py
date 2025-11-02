#!/usr/bin/env python3
"""
Analyse complète des dépendances pour trouver versions compatibles.
Chatterbox + Coqui-TTS + audio-separator + MiniBotPanel
"""

# Packages principaux qu'on DOIT installer
MAIN_PACKAGES = {
    "chatterbox-tts": "0.1.4",  # Principal TTS
    "TTS": "0.22.0",  # Coqui-TTS/XTTS backup
    "audio-separator": "0.12.0",  # UVR vocal extraction
}

# Dépendances CRITIQUES avec conflits connus
CRITICAL_DEPS = {
    # PyTorch ecosystem
    "torch": {
        "chatterbox-tts": "==2.6.0",
        "TTS": ">=2.1,<2.9",
        "audio-separator": ">=2.3",  # Version 0.12.0 accepte >=1.23
        "OPTIMAL": "2.6.0"  # Version qui satisfait tous
    },

    "torchaudio": {
        "chatterbox-tts": "==2.6.0",
        "TTS": ">=2.1.0,<2.9",
        "audio-separator": "N/A",
        "OPTIMAL": "2.6.0"
    },

    "torchvision": {
        "chatterbox-tts": "N/A",
        "TTS": "N/A",
        "audio-separator": ">=0.9.0 (via onnx2torch)",  # Problème ici!
        "OPTIMAL": "0.19.0"  # Compatible torch 2.4, mais pas 2.6!
        # NOTE: torchvision 0.21.0 (pour torch 2.6) cause error avec onnx2torch
    },

    "numpy": {
        "chatterbox-tts": ">=1.24.0,<1.26.0",
        "TTS": ">=1.26.0",  # Conflit!
        "audio-separator": ">=1.23 (v0.12.0)",
        "OPTIMAL": "1.25.2"  # Compromis
    },

    "transformers": {
        "chatterbox-tts": "==4.46.3",
        "TTS": ">=4.33.0 (v0.22.0)",
        "audio-separator": "N/A",
        "OPTIMAL": "4.46.3"
    },

    # ONNX ecosystem
    "onnx2torch": {
        "audio-separator": "required (v0.12.0)",
        "ISSUE": "torchvision 0.21.0 incompatible!",
        "FIX": "Utiliser torch 2.4.0 + torchvision 0.19.0 OU skip UVR"
    },
}

# Dépendances secondaires
SECONDARY_DEPS = {
    "gradio": {
        "chatterbox-tts": "==5.44.1",
        "MiniBotPanel": "compatible",
        "OPTIMAL": "5.44.1"
    },

    "librosa": {
        "chatterbox-tts": "==0.11.0",
        "TTS": ">=0.11.0",
        "audio-separator": ">=0.10",
        "OPTIMAL": "0.11.0"
    },

    "soundfile": ">=0.12.1",
    "pydub": "latest",
    "noisereduce": "==3.0.2",
}

# Analyse des conflits
CONFLICTS = """
╔══════════════════════════════════════════════════════════════════╗
║                     ANALYSE DES CONFLITS                          ║
╚══════════════════════════════════════════════════════════════════╝

❌ CONFLIT #1: numpy
   - Chatterbox: <1.26.0
   - Coqui-TTS: >=1.26.0
   → SOLUTION: numpy==1.25.2 (fonctionne en pratique pour les 2)

❌ CONFLIT #2: torchvision + onnx2torch
   - torch 2.6.0 → torchvision 0.21.0
   - onnx2torch incompatible avec torchvision 0.21.0
   - audio-separator dépend de onnx2torch
   → PROBLÈME MAJEUR!

╔══════════════════════════════════════════════════════════════════╗
║                      SOLUTIONS POSSIBLES                          ║
╚══════════════════════════════════════════════════════════════════╝

OPTION A: DOWNGRADE TORCH (2.6 → 2.4)
══════════════════════════════════════
✅ torch==2.4.0 + torchvision==0.19.0
✅ Compatible audio-separator + onnx2torch
❌ Chatterbox veut EXACTEMENT torch==2.6.0
❌ FAIL: Chatterbox ne marchera pas

OPTION B: SKIP UVR (garde Chatterbox + Coqui)
═════════════════════════════════════════════
✅ torch==2.6.0 + torchaudio==2.6.0
✅ numpy==1.25.2
✅ transformers==4.46.3
✅ Chatterbox OK
✅ Coqui-TTS OK
❌ Pas de UVR vocal extraction
✅ Scoring SNR fonctionne quand même!

OPTION C: FORCER CHATTERBOX AVEC --no-deps
═══════════════════════════════════════════
✅ Installer torch 2.4.0 (au lieu de 2.6.0)
✅ Installer Chatterbox avec --no-deps
✅ Espérer que Chatterbox fonctionne avec torch 2.4
⚠️  RISQUE: API changes entre torch 2.4 et 2.6
⚠️  Peut causer crashes

OPTION D: FORK audio-separator (enlever onnx2torch)
════════════════════════════════════════════════════
✅ Créer version sans onnx2torch
✅ Utiliser seulement onnxruntime
❌ Trop de travail
❌ Pas viable pour production

╔══════════════════════════════════════════════════════════════════╗
║                    RECOMMANDATION FINALE                          ║
╚══════════════════════════════════════════════════════════════════╝

✨ OPTION B: SKIP UVR (meilleur compromis)
═════════════════════════════════════════

Packages:
- torch==2.6.0, torchaudio==2.6.0 (CPU)
- numpy==1.25.2
- transformers==4.46.3
- chatterbox-tts==0.1.4
- TTS==0.22.0
- gradio==5.44.1
- noisereduce==3.0.2 (pour scoring SNR)

Features:
✅ Chatterbox TTS (principal, meilleure qualité)
✅ Coqui-TTS/XTTS (backup)
✅ Few-shot voice cloning (multiples fichiers)
✅ Audio scoring (SNR, durée, silence, stabilité)
✅ Normalisation volume -3dB
✅ Paramètres optimisés (exaggeration=0.35, cfg_weight=0.45)
❌ UVR vocal extraction (skip)

Workaround UVR:
1. Utiliser UVR desktop app en local
2. Nettoyer fichiers manuellement
3. Upload vocals nettoyés sur VPS
4. Cloner avec Chatterbox

OU:

✅ Tes fichiers audio/ sont déjà propres (hello, bye, q1, etc.)
→ Pas besoin de UVR!
→ Le scoring SNR va sélectionner les meilleurs

╔══════════════════════════════════════════════════════════════════╗
║                     VERSION FINALE OPTIMALE                       ║
╚══════════════════════════════════════════════════════════════════╝

numpy==1.25.2
torch==2.6.0
torchaudio==2.6.0
transformers==4.46.3
chatterbox-tts==0.1.4
TTS==0.22.0
gradio==5.44.1
librosa==0.11.0
soundfile==0.12.1
pydub (latest)
noisereduce==3.0.2

# Dépendances Chatterbox
encodec
einops
spandrel (sans torchvision!)
pykakasi
s3tokenizer
resemble-perth
pkuseg==0.0.25

# Dépendances Coqui-TTS
bangla
gruut==2.2.3
pypinyin
coqpit
flask
nltk
trainer

# SKIP:
# - audio-separator (cause problème torchvision)
# - torchvision (pas nécessaire si pas UVR)

"""

if __name__ == "__main__":
    print(CONFLICTS)

    print("\n" + "="*70)
    print("INSTALLATION SCRIPT:")
    print("="*70)
    print("""
# 1. Nettoyer
pip uninstall -y torch torchaudio torchvision numpy transformers audio-separator

# 2. Core deps
pip install "numpy==1.25.2"
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
pip install "transformers==4.46.3"

# 3. Chatterbox deps
pip install --upgrade cython setuptools wheel
pip install --no-build-isolation pkuseg==0.0.25 || echo "pkuseg optional"
pip install encodec einops pykakasi s3tokenizer resemble-perth
pip install gradio==5.44.1 librosa==0.11.0 soundfile pydub noisereduce==3.0.2

# 4. Chatterbox (no-deps)
pip install --no-deps chatterbox-tts

# 5. Coqui-TTS
pip install "TTS==0.22.0"
pip install bangla gruut==2.2.3 pypinyin

# 6. Test
python3 -c "from system.services.chatterbox_tts import ChatterboxTTSService; print('✅ Chatterbox OK')"
python3 -c "from TTS.api import TTS; print('✅ Coqui-TTS OK')"

# 7. Cloner voix (sans UVR)
mkdir -p voices/custom_voice
python3 clone_voice_chatterbox.py --voice custom_voice --score-only
python3 clone_voice_chatterbox.py --voice custom_voice --skip-tts
""")
