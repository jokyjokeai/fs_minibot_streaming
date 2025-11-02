#!/bin/bash
# Installation complète - MiniBotPanel v3
# Chatterbox + Coqui TTS + UVR + Custom Diarization (sans pyannote)
# Python 3.10 ou 3.11 requis

set -e  # Exit on error

echo "============================================"
echo "🚀 MiniBotPanel v3 - Installation Complète"
echo "============================================"
echo ""

# Vérifier version Python
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "Python version: $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -ne 3 ]; then
    echo "❌ Python 3 requis"
    exit 1
fi

if [ "$PYTHON_MINOR" -gt 11 ]; then
    echo "⚠️  Python 3.$PYTHON_MINOR détecté"
    echo "   RECOMMANDÉ: Python 3.10 ou 3.11"
    echo "   Python 3.12+ peut causer des problèmes de compatibilité"
    read -p "   Continuer quand même? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
elif [ "$PYTHON_MINOR" -lt 10 ]; then
    echo "❌ Python 3.10+ requis (vous avez 3.$PYTHON_MINOR)"
    exit 1
else
    echo "✅ Version Python compatible"
fi

echo ""
echo "============================================"
echo "📦 Installation des dépendances"
echo "============================================"
echo ""

# Upgrade pip
echo "1️⃣ Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel
echo ""

# PyTorch + numpy (CRITICAL: EN PREMIER)
echo "2️⃣ Installing PyTorch 2.4.0 (CPU) + numpy 1.25.2..."
echo "   IMPORTANT: Installé EN PREMIER pour éviter upgrades"
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.0 \
    torchaudio==2.4.0 \
    torchvision==0.19.0

pip install numpy==1.25.2
echo ""

# Transformers
echo "3️⃣ Installing transformers 4.46.3..."
pip install transformers==4.46.3
echo ""

# Chatterbox TTS (SEUL ENGINE - bat ElevenLabs en blind tests)
echo "4️⃣ Installing Chatterbox TTS (MIT license, meilleure qualité)..."
echo "   NOTE: Warnings normaux sur torch version (accepte 2.4.0)"
pip install git+https://github.com/resemble-ai/chatterbox.git --no-deps
echo "   ✅ Coqui TTS RETIRÉ - Chatterbox seul suffit"
echo ""

# Audio processing core
echo "5️⃣ Installing audio processing libraries..."
pip install \
    soundfile==0.12.1 \
    pydub==0.25.1 \
    scipy==1.11.4 \
    librosa==0.10.1 \
    webrtcvad==2.0.10 \
    noisereduce==3.0.2
echo ""

# UVR (vocal extraction)
echo "6️⃣ Installing audio-separator (UVR)..."
pip install audio-separator==0.12.0
echo ""

# Diarization maison (scikit-learn pour clustering)
echo "7️⃣ Installing custom diarization dependencies..."
pip install scikit-learn>=1.3.2
echo "   ✅ Custom diarization (system/services/simple_diarization.py)"
echo "   ✅ PLUS besoin de pyannote.audio ni HuggingFace token"
echo ""

# YouTube extraction
echo "8️⃣ Installing YouTube extraction..."
pip install yt-dlp>=2024.10.22
echo ""

# STT
echo "9️⃣ Installing Vosk STT..."
pip install vosk==0.3.45
echo ""

# NLP
echo "🔟 Installing Ollama client..."
pip install ollama>=0.6.0 requests==2.31.0
echo ""

# Web framework
echo "1️⃣1️⃣ Installing FastAPI + Uvicorn..."
pip install \
    fastapi==0.118.2 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 \
    pydantic==2.12.0 \
    pydantic-settings>=2.1.0
echo ""

# Database
echo "1️⃣2️⃣ Installing database libraries..."
pip install \
    sqlalchemy==2.0.25 \
    psycopg2-binary==2.9.11 \
    alembic==1.13.1
echo ""

# Utilities
echo "1️⃣3️⃣ Installing utilities..."
pip install \
    python-dotenv==1.1.1 \
    python-json-logger==2.0.7 \
    colorama==0.4.6 \
    click==8.3.0 \
    tabulate==0.9.0 \
    openpyxl==3.1.2 \
    phonenumbers==8.13.27 \
    invoke==2.2.1 \
    tqdm>=4.66.0 \
    prometheus-client==0.19.0
echo ""

echo "============================================"
echo "✅ Installation terminée!"
echo "============================================"
echo ""

# Vérifications
echo "🔍 Vérification des installations..."
echo ""

# Vérifier PyTorch
TORCH_VERSION=$(python3 -c "import torch; print(torch.__version__)" 2>&1)
if [[ $TORCH_VERSION == 2.4.0* ]]; then
    echo "✅ PyTorch: $TORCH_VERSION"
else
    echo "⚠️  PyTorch: $TORCH_VERSION (attendu: 2.4.0)"
fi

# Vérifier numpy
NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>&1)
if [[ $NUMPY_VERSION == 1.25.2* ]]; then
    echo "✅ numpy: $NUMPY_VERSION"
else
    echo "⚠️  numpy: $NUMPY_VERSION (attendu: 1.25.2)"
fi

# Vérifier Chatterbox TTS (seul engine)
python3 -c "from chatterbox.model import ChatterboxMultilingualTTS; print('✅ Chatterbox TTS OK')" 2>&1 | grep -E "(✅|Error)"

# Vérifier UVR
python3 -c "from audio_separator.separator import Separator; print('✅ UVR (audio-separator) OK')" 2>&1 | grep -E "(✅|Error)"

# Vérifier diarization maison
python3 -c "from system.services.simple_diarization import SimpleDiarization; print('✅ Custom Diarization OK')" 2>&1 | grep -E "(✅|Error)"

# Vérifier YouTube
python3 -c "import yt_dlp; print('✅ yt-dlp OK')" 2>&1 | grep -E "(✅|Error)"

echo ""
echo "============================================"
echo "📋 Prochaines étapes"
echo "============================================"
echo ""
echo "1. Télécharger modèle Vosk (français):"
echo "   wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
echo "   unzip vosk-model-small-fr-0.22.zip -d models/"
echo ""
echo "2. Installer Ollama:"
echo "   https://ollama.ai/download"
echo "   ollama pull mistral:7b"
echo ""
echo "3. Configurer .env (copier .env.example)"
echo ""
echo "4. Tester le système:"
echo "   python3 youtube_extract.py  # Extraction YouTube avec diarization maison"
echo "   python3 clone_voice.py  # Clonage vocal avec Chatterbox+UVR (top 20 fichiers)"
echo ""
echo "============================================"
echo "🎉 Installation réussie!"
echo "============================================"
echo ""
echo "NOTES:"
echo "- Système de diarization MAISON (plus besoin de pyannote)"
echo "- Pas de HuggingFace token requis"
echo "- Chatterbox TTS SEUL (Coqui retiré - qualité supérieure)"
echo "- UVR pour extraction vocale"
echo "- Sample rate 44.1kHz (qualité optimale)"
echo "- Top 20 meilleurs fichiers audio (scoring automatique)"
echo "- Compatible Python 3.10 et 3.11"
echo ""
