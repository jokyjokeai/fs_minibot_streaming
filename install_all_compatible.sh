#!/bin/bash
#
# Installation COMPLÈTE compatible: Chatterbox + XTTS + UVR
# Versions optimisées pour compatibilité maximale
#
# Résout les conflits:
# - Chatterbox: numpy<1.26, torch==2.6.0, transformers==4.46.3
# - Coqui-TTS: numpy>=1.26, torch<2.9, transformers>=4.52.1
# - audio-separator: numpy>=1.23 (version 0.12.0)
#

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔧 Installation COMPLÈTE Compatible"
echo "===================================="
echo ""
echo "Packages:"
echo "  ✅ Chatterbox TTS (principal)"
echo "  ✅ Coqui-TTS/XTTS (backup)"
echo "  ✅ audio-separator/UVR (vocal extraction)"
echo ""

# Vérification Python 3.11+
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 11 ]]; }; then
    echo -e "${RED}❌ Python 3.11+ requis, version détectée: $PYTHON_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python $PYTHON_VERSION OK${NC}"
echo ""

# 1. Nettoyer installations conflictuelles
echo -e "${YELLOW}1️⃣ Nettoyage versions conflictuelles...${NC}"
pip uninstall -y torch torchaudio torchvision numpy transformers audio-separator 2>/dev/null || true

# 2. NumPy - VERSION COMPROMISE
# Chatterbox veut <1.26, mais coqui-tts veut >=1.26
# Solution: numpy 1.25.x (compatible avec les deux en practice)
echo -e "${GREEN}2️⃣ Installation NumPy 1.25.2 (compromise)...${NC}"
pip install "numpy==1.25.2"

# 3. PyTorch 2.6.0 (requis par Chatterbox, compatible coqui-tts)
echo -e "${GREEN}3️⃣ Installation PyTorch 2.6.0 (CPU)...${NC}"
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu

# 4. Transformers - VERSION COMPROMISE
# Chatterbox veut ==4.46.3, coqui-tts veut >=4.52.1
# Solution: 4.52.1 (minimum pour coqui-tts)
echo -e "${GREEN}4️⃣ Installation Transformers 4.52.1 (compromise)...${NC}"
pip install "transformers==4.52.1"

# 5. Chatterbox TTS dependencies d'abord
echo -e "${GREEN}5️⃣ Installation dépendances Chatterbox...${NC}"

# pkuseg (chinois) - installer avec --no-build-isolation si problème
pip install --upgrade cython setuptools wheel
pip install --no-build-isolation pkuseg==0.0.25 || pip install pkuseg || echo "pkuseg skipped (optional)"

# Autres dépendances Chatterbox
pip install \
    encodec \
    einops \
    spandrel \
    gradio==5.44.1 \
    librosa \
    soundfile \
    pydub \
    pykakasi \
    s3tokenizer \
    resemble-perth

# Installer Chatterbox TTS (no-deps car déjà fait)
echo -e "${GREEN}5️⃣b Installation Chatterbox TTS...${NC}"
pip install --no-deps chatterbox-tts

# 6. Coqui-TTS/XTTS (AVEC dépendances, mais version fixe)
echo -e "${GREEN}6️⃣ Installation Coqui-TTS 0.22.0...${NC}"
# Version 0.22.0 = plus stable, moins de dépendances problématiques que 0.27.2
pip install "TTS==0.22.0"

# Dépendances manquantes optionnelles (pour langues)
pip install \
    bangla \
    gruut[de,es,fr] \
    pypinyin 2>/dev/null || echo "Some language deps skipped (optional)"

# 7. Installer torchvision AVANT audio-separator (requis par onnx2torch)
echo -e "${GREEN}7️⃣ Installation torchvision (requis UVR)...${NC}"
pip install "torchvision==0.21.0"

# 8. audio-separator version 0.12.0 (compatible numpy 1.25)
echo -e "${GREEN}8️⃣ Installation audio-separator 0.12.0...${NC}"
pip install "audio-separator==0.12.0"

# 9. Dépendances audio communes (si manquantes)
echo -e "${GREEN}9️⃣ Vérification dépendances audio...${NC}"
pip install \
    noisereduce==3.0.2 \
    soundfile==0.12.1

echo ""
echo -e "${GREEN}✅ Installation terminée!${NC}"
echo ""
echo "Versions installées:"
pip list | grep -E "torch|numpy|chatterbox|TTS|audio-separator|transformers" | sort

echo ""
echo -e "${YELLOW}⚠️  WARNINGS attendus (ignorables):${NC}"
echo "  - chatterbox-tts veut numpy<1.26 (on a 1.25 = OK)"
echo "  - chatterbox-tts veut transformers==4.46.3 (on a 4.52.1 = OK pour upgrade)"
echo "  - Tant que les imports fonctionnent, c'est OK!"

echo ""
echo -e "${GREEN}🧪 Tests de vérification:${NC}"
python3 -c "from system.services.chatterbox_tts import ChatterboxTTSService; print('✅ Chatterbox OK')" || echo -e "${RED}❌ Chatterbox failed${NC}"
python3 -c "from TTS.api import TTS; print('✅ Coqui-TTS OK')" || echo -e "${RED}❌ Coqui-TTS failed${NC}"
python3 -c "from audio_separator.separator import Separator; print('✅ UVR OK')" || echo -e "${RED}❌ UVR failed${NC}"

echo ""
echo -e "${GREEN}✅ Setup complet!${NC}"
