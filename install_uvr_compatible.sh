#!/bin/bash
#
# Installation UVR (audio-separator) compatible avec Chatterbox
# Utilise Torch 2.6.0 (compatible avec Chatterbox ET audio-separator)
#

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔧 Installation UVR compatible avec Chatterbox"
echo "=============================================="
echo ""

# 1. Désinstaller versions incompatibles
echo -e "${YELLOW}1️⃣ Cleaning incompatible versions...${NC}"
pip uninstall -y torch torchaudio torchvision numpy audio-separator 2>/dev/null || true

# 2. Installer NumPy compatible (1.24.x < 1.26)
echo -e "${GREEN}2️⃣ Installing compatible NumPy...${NC}"
pip install "numpy>=1.24.3,<1.26.0"

# 3. Installer PyTorch 2.6.0 (compatible Chatterbox + audio-separator)
echo -e "${GREEN}3️⃣ Installing PyTorch 2.6.0 (CPU)...${NC}"
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu

# 4. Installer audio-separator SANS dépendances (pour éviter upgrade)
echo -e "${GREEN}4️⃣ Installing audio-separator (no-deps)...${NC}"
pip install --no-deps audio-separator

# 5. Installer dépendances manquantes de audio-separator (sauf torch/numpy)
echo -e "${GREEN}5️⃣ Installing audio-separator dependencies...${NC}"
pip install \
    onnx \
    onnxruntime \
    librosa \
    soundfile \
    resampy \
    pydub \
    requests \
    tqdm

# 6. Vérifier installations
echo ""
echo -e "${GREEN}✅ Vérification des installations:${NC}"
echo ""
pip list | grep -E "torch|numpy|audio-separator|chatterbox"

echo ""
echo -e "${GREEN}✅ Installation terminée!${NC}"
echo ""
echo "Test rapide:"
echo "  python3 -c \"from audio_separator.separator import Separator; print('✅ UVR OK')\""
echo "  python3 -c \"from system.services.chatterbox_tts import ChatterboxTTSService; print('✅ Chatterbox OK')\""
