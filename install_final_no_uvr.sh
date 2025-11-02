#!/bin/bash
#
# Installation FINALE - Chatterbox + Coqui-TTS (SANS UVR)
# torch==2.6.0 et numpy==1.25.2 non négociables
# Les autres s'adaptent!
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🎯 Installation FINALE - Chatterbox + Coqui-TTS"
echo "=============================================="
echo ""
echo "Règle: torch==2.6.0 et numpy==1.25.2 FIXES"
echo "Les autres packages s'adaptent!"
echo ""

# 1. Nettoyer TOUT
echo -e "${YELLOW}1️⃣ Nettoyage complet...${NC}"
pip uninstall -y torch torchaudio torchvision numpy transformers audio-separator chatterbox-tts TTS 2>/dev/null || true

# 2. NUMPY (FIXE)
echo -e "${GREEN}2️⃣ numpy==1.25.2 (FIXE)${NC}"
pip install "numpy==1.25.2"

# 3. TORCH (FIXE)
echo -e "${GREEN}3️⃣ torch==2.6.0 + torchaudio==2.6.0 (FIXE)${NC}"
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu

# 4. Transformers
echo -e "${GREEN}4️⃣ transformers==4.46.3${NC}"
pip install "transformers==4.46.3"

# 5. Dépendances Chatterbox
echo -e "${GREEN}5️⃣ Dépendances Chatterbox...${NC}"
pip install --upgrade cython setuptools wheel
pip install --no-build-isolation pkuseg==0.0.25 || echo "⚠️ pkuseg skipped (optional Chinese)"

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

# 6. Chatterbox TTS (no-deps pour éviter downgrades)
echo -e "${GREEN}6️⃣ chatterbox-tts==0.1.4 (no-deps)${NC}"
pip install --no-deps chatterbox-tts

# 7. Coqui-TTS
echo -e "${GREEN}7️⃣ TTS==0.22.0${NC}"
pip install "TTS==0.22.0"

# Dépendances Coqui optionnelles
pip install bangla pypinyin 2>/dev/null || echo "⚠️ Some language deps skipped (optional)"

# 8. Downgrade gruut si conflit
pip install "gruut==2.2.3" 2>/dev/null || echo "⚠️ gruut kept at current version"

echo ""
echo -e "${GREEN}✅ Installation terminée!${NC}"
echo ""
echo "Packages installés:"
pip list | grep -E "numpy|torch|chatterbox|TTS|transformers|noisereduce" | sort

echo ""
echo -e "${GREEN}🧪 Tests:${NC}"
python3 -c "from system.services.chatterbox_tts import ChatterboxTTSService; print('✅ Chatterbox OK')" || echo "❌ Chatterbox failed"
python3 -c "from TTS.api import TTS; print('✅ Coqui-TTS OK')" || echo "❌ Coqui-TTS failed"

echo ""
echo -e "${GREEN}📝 Features disponibles:${NC}"
echo "  ✅ Chatterbox TTS (meilleure qualité)"
echo "  ✅ Coqui-TTS/XTTS (backup)"
echo "  ✅ Few-shot voice cloning (9 fichiers)"
echo "  ✅ Audio scoring (SNR, durée, silence, stabilité)"
echo "  ✅ Normalisation volume -3dB"
echo "  ✅ Paramètres optimisés (exaggeration=0.35)"
echo "  ❌ UVR vocal extraction (skipped - incompatible)"

echo ""
echo -e "${YELLOW}💡 Prochaines étapes:${NC}"
echo "  mkdir -p voices/custom_voice"
echo "  python3 clone_voice_chatterbox.py --voice custom_voice --score-only"
echo "  python3 clone_voice_chatterbox.py --voice custom_voice --skip-tts"
echo ""
echo -e "${GREEN}✅ Ready to clone!${NC}"
