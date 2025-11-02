#!/bin/bash
#
# Installation FINALE - Chatterbox + Coqui-TTS + UVR
# FORCE torch 2.4.0 (au lieu de 2.6.0) pour compatibilité UVR
# Chatterbox installé avec --no-deps et prière qu'il marche!
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🎯 Installation FINALE - AVEC UVR (EXPERIMENTAL)"
echo "================================================"
echo ""
echo -e "${YELLOW}⚠️  WARNING: Chatterbox veut torch 2.6.0${NC}"
echo -e "${YELLOW}⚠️  On installe torch 2.4.0 pour UVR${NC}"
echo -e "${YELLOW}⚠️  Chatterbox peut crasher!${NC}"
echo ""
read -p "Continuer? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# 1. Nettoyer TOUT
echo -e "${YELLOW}1️⃣ Nettoyage complet...${NC}"
pip uninstall -y torch torchaudio torchvision numpy transformers audio-separator chatterbox-tts TTS 2>/dev/null || true

# 2. NUMPY
echo -e "${GREEN}2️⃣ numpy==1.25.2${NC}"
pip install "numpy==1.25.2"

# 3. TORCH 2.4.0 (pour UVR, pas 2.6!)
echo -e "${GREEN}3️⃣ torch==2.4.0 + torchaudio==2.4.0 + torchvision==0.19.0${NC}"
pip install torch==2.4.0 torchaudio==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cpu

# 4. Transformers
echo -e "${GREEN}4️⃣ transformers==4.46.3${NC}"
pip install "transformers==4.46.3"

# 5. Dépendances Chatterbox
echo -e "${GREEN}5️⃣ Dépendances Chatterbox...${NC}"
pip install --upgrade cython setuptools wheel
pip install --no-build-isolation pkuseg==0.0.25 || echo "⚠️ pkuseg skipped"

pip install \
    encodec \
    einops \
    pykakasi \
    s3tokenizer \
    resemble-perth \
    gradio==5.44.1 \
    librosa==0.11.0 \
    soundfile \
    pydub \
    noisereduce==3.0.2

# 6. Chatterbox TTS (FORCE avec --no-deps malgré torch 2.4)
echo -e "${YELLOW}6️⃣ chatterbox-tts (FORCE no-deps avec torch 2.4)${NC}"
pip install --no-deps chatterbox-tts

# 7. Coqui-TTS
echo -e "${GREEN}7️⃣ TTS==0.22.0${NC}"
pip install "TTS==0.22.0"
pip install bangla pypinyin gruut==2.2.3 2>/dev/null || true

# 8. audio-separator (ENFIN!)
echo -e "${GREEN}8️⃣ audio-separator==0.12.0${NC}"
pip install "audio-separator==0.12.0"

echo ""
echo -e "${GREEN}✅ Installation terminée!${NC}"
echo ""
echo "Packages installés:"
pip list | grep -E "numpy|torch|chatterbox|TTS|audio-separator|transformers" | sort

echo ""
echo -e "${YELLOW}🧪 Tests CRITIQUES:${NC}"

# Test Chatterbox (peut fail avec torch 2.4)
python3 -c "from system.services.chatterbox_tts import ChatterboxTTSService; tts = ChatterboxTTSService(); print('✅ Chatterbox OK')" && CHATTERBOX_OK=true || CHATTERBOX_OK=false

if [ "$CHATTERBOX_OK" = true ]; then
    echo -e "${GREEN}✅ Chatterbox marche avec torch 2.4!${NC}"
else
    echo -e "${RED}❌ Chatterbox FAIL avec torch 2.4${NC}"
    echo -e "${YELLOW}   Solution: utiliser install_final_no_uvr.sh${NC}"
fi

python3 -c "from TTS.api import TTS; print('✅ Coqui-TTS OK')" || echo "❌ Coqui-TTS failed"
python3 -c "from audio_separator.separator import Separator; print('✅ UVR OK')" || echo "❌ UVR failed"

echo ""
echo -e "${GREEN}📝 Features:${NC}"
echo "  ✅ Coqui-TTS/XTTS"
echo "  ✅ UVR vocal extraction"
echo "  ✅ Audio scoring"
if [ "$CHATTERBOX_OK" = true ]; then
    echo "  ✅ Chatterbox TTS (miracle!)"
else
    echo "  ❌ Chatterbox TTS (torch 2.4 incompatible)"
fi

echo ""
echo -e "${YELLOW}💡 Usage:${NC}"
echo "  # Avec UVR"
echo "  python3 clone_voice_chatterbox.py --voice custom_voice --uvr --score-only"
echo "  python3 clone_voice_chatterbox.py --voice custom_voice --uvr --skip-tts"
