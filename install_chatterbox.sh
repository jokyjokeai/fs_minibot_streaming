#!/bin/bash
#
# Installation Chatterbox TTS - MiniBotPanel v3
# Alternative à XTTS v2 avec qualité supérieure à ElevenLabs
#
# Usage:
#   ./install_chatterbox.sh          # CPU-only (par défaut)
#   ./install_chatterbox.sh --gpu    # Avec support GPU CUDA 11.8
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

echo "🔧 Installation Chatterbox TTS - MiniBotPanel v3"
echo "=============================================="
echo -e "${YELLOW}Python 3.11+ REQUIS${NC}"
if $GPU_MODE; then
    echo -e "${YELLOW}Mode: GPU (CUDA 11.8)${NC}"
else
    echo -e "${YELLOW}Mode: CPU-only${NC}"
fi
echo ""

# Vérification Python 3.11+
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 11 ]]; }; then
    echo -e "${RED}❌ Python 3.11+ requis, version détectée: $PYTHON_VERSION${NC}"
    echo -e "${YELLOW}Installer Python 3.11:${NC}"
    echo "  Ubuntu: sudo apt install python3.11 python3.11-venv"
    echo "  CentOS: sudo yum install python311"
    exit 1
fi

echo -e "${GREEN}✅ Python $PYTHON_VERSION détecté${NC}"
echo ""

# 1. NumPy (IMPORTANT: installer EN PREMIER pour éviter conflits)
echo -e "${GREEN}1️⃣ Installation numpy<2.0 (compatible)...${NC}"
pip install "numpy>=1.24.3,<2.0"

# 2. PyTorch (installer AVANT chatterbox-tts)
# IMPORTANT: Torch 2.6.0 requis par Chatterbox (compatible audio-separator aussi)
if $GPU_MODE; then
    echo -e "${GREEN}2️⃣ Installation PyTorch 2.6.0 (GPU CUDA 12.1)...${NC}"
    pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu121
else
    echo -e "${GREEN}2️⃣ Installation PyTorch 2.6.0 (CPU-only)...${NC}"
    pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
fi

# 3. Chatterbox TTS
echo -e "${GREEN}3️⃣ Installation Chatterbox TTS...${NC}"
pip install chatterbox-tts

# 4. Dépendances audio (si pas déjà installées)
echo -e "${GREEN}4️⃣ Installation dépendances audio...${NC}"
pip install noisereduce==3.0.2 pydub==0.25.1 soundfile==0.12.1

# 5. Autres dépendances MiniBotPanel (si nécessaire)
echo -e "${GREEN}5️⃣ Vérification dépendances MiniBotPanel...${NC}"
pip install \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 \
    pydantic>=2.9.0 \
    requests==2.31.0 \
    python-dotenv==1.0.0

echo ""
echo -e "${GREEN}✅ Installation terminée !${NC}"
echo ""
echo "Versions installées:"
pip list | grep -E "torch|chatterbox|torchaudio"

if $GPU_MODE; then
    echo ""
    echo -e "${YELLOW}🔍 Vérification GPU...${NC}"
    python3 -c "import torch; print(f'GPU disponible: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')" || echo -e "${RED}❌ Erreur vérification GPU${NC}"
fi

echo ""
echo -e "${GREEN}📝 Prochaines étapes:${NC}"
echo "  1. Ajouter fichiers audio dans voices/{nom_voix}/"
echo "  2. Lancer: python3 clone_voice_chatterbox.py --voice {nom_voix}"
echo "  3. Tester: voices/{nom_voix}/test_clone.wav"
echo ""
echo -e "${GREEN}🎯 Avantages Chatterbox vs XTTS:${NC}"
echo "  ✅ Bat ElevenLabs en blind tests (63.8%)"
echo "  ✅ Seulement 5-10s d'audio requis (vs 6s pour XTTS)"
echo "  ✅ Contrôle des émotions intégré"
echo "  ✅ MIT License (commercial OK)"
echo "  ✅ 23 langues supportées"
