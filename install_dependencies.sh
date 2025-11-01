#!/bin/bash
#
# Installation des dépendances MiniBotPanel v3 FINAL
# Contourne les conflits numpy entre TTS et audio-separator
#
# Usage:
#   ./install_dependencies.sh          # CPU-only (par défaut)
#   ./install_dependencies.sh --gpu    # Avec support GPU CUDA 11.8
#

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Détection GPU
GPU_MODE=false
if [[ "$1" == "--gpu" ]]; then
    GPU_MODE=true
fi

echo "🔧 Installation MiniBotPanel v3 - Dépendances"
echo "=============================================="
if $GPU_MODE; then
    echo -e "${YELLOW}Mode: GPU (CUDA 11.8)${NC}"
else
    echo -e "${YELLOW}Mode: CPU-only${NC}"
fi
echo ""

# 1. PyTorch
if $GPU_MODE; then
    echo -e "${GREEN}1️⃣ Installation PyTorch (GPU CUDA 11.8 - 1.3GB)...${NC}"
    pip install torch==2.1.2 torchaudio==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118
else
    echo -e "${GREEN}1️⃣ Installation PyTorch (CPU-only - 200MB)...${NC}"
    pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
fi

# 2. TTS avec numpy 1.22.0
echo -e "${GREEN}2️⃣ Installation TTS + numpy 1.22.0...${NC}"
pip install TTS==0.22.0

# 3. Upgrade numpy pour Spleeter
echo -e "${GREEN}3️⃣ Upgrade numpy à 1.24.3...${NC}"
pip install --upgrade "numpy==1.24.3"

# 4. Audio packages
echo -e "${GREEN}4️⃣ Installation audio packages...${NC}"
pip install spleeter==2.4.0 noisereduce==3.0.2

# 5. Pyannote (diarization)
echo -e "${GREEN}5️⃣ Installation pyannote.audio...${NC}"
pip install pyannote.audio==3.1.1

# 6. Autres dépendances (sans conflits)
echo -e "${GREEN}6️⃣ Installation autres dépendances...${NC}"
pip install \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 \
    pydantic>=2.9.0 \
    pydantic-settings>=2.1.0 \
    sqlalchemy==2.0.25 \
    psycopg2-binary==2.9.9 \
    alembic==1.13.1 \
    vosk==0.3.45 \
    soundfile==0.12.1 \
    scipy>=1.11.2 \
    ollama>=0.6.0 \
    requests==2.31.0 \
    transformers==4.35.0 \
    pydub==0.25.1 \
    webrtcvad==2.0.10 \
    librosa==0.10.1 \
    networkx==2.8.8 \
    "yt-dlp>=2024.10.22" \
    python-dotenv==1.0.0 \
    python-json-logger==2.0.7 \
    colorama==0.4.6 \
    click==8.1.7 \
    tabulate==0.9.0 \
    openpyxl==3.1.2 \
    phonenumbers==8.13.27 \
    prometheus-client==0.19.0

echo ""
echo -e "${GREEN}✅ Installation terminée !${NC}"
echo ""
echo "Versions installées:"
pip list | grep -E "torch|TTS|numpy|spleeter|pyannote"

if $GPU_MODE; then
    echo ""
    echo -e "${YELLOW}🔍 Vérification GPU...${NC}"
    python -c "import torch; print(f'GPU disponible: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')" || echo -e "${RED}❌ Erreur vérification GPU${NC}"
fi

echo ""
echo -e "${GREEN}📝 Prochaines étapes:${NC}"
echo "  1. Télécharger modèle Vosk: wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
echo "  2. Configurer .env avec DATABASE_URL, HUGGINGFACE_TOKEN, etc."
echo "  3. Lancer: ./start_system.sh"
