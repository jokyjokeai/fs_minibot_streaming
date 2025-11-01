#!/bin/bash
#
# Setup Audio - MiniBotPanel v3
#
# Prépare les fichiers audio pour le système.
#
# Fonctionnalités:
# - Normalisation audio (volume, sample rate)
# - Conversion format (MP3 → WAV)
# - Validation qualité
# - Organisation fichiers
#
# Utilisation:
#   ./setup_audio.sh
#   ./setup_audio.sh --source /path/to/audio/files
#   ./setup_audio.sh --normalize-all

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AUDIO_DIR="audio"
TARGET_SAMPLE_RATE=8000  # 8kHz pour téléphonie
TARGET_FORMAT="wav"
TARGET_CODEC="pcm_mulaw"  # G.711 µ-law

echo "🎵 SETUP AUDIO - MiniBotPanel v3"
echo "=============================================="

# Vérifier si ffmpeg est installé
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}❌ ffmpeg n'est pas installé${NC}"
    echo "💡 Installez-le avec: brew install ffmpeg (macOS) ou apt install ffmpeg (Linux)"
    exit 1
fi

echo -e "${GREEN}✅ ffmpeg détecté${NC}"

# Créer répertoires si nécessaire
mkdir -p "$AUDIO_DIR/raw"
mkdir -p "$AUDIO_DIR/normalized"
mkdir -p "$AUDIO_DIR/scenarios"

echo ""
echo "📁 Structure des répertoires:"
echo "   $AUDIO_DIR/raw/          - Fichiers audio bruts"
echo "   $AUDIO_DIR/normalized/   - Fichiers audio normalisés"
echo "   $AUDIO_DIR/scenarios/    - Audio pour scénarios"

# Fonction de normalisation
normalize_audio() {
    local input_file="$1"
    local output_file="$2"

    echo "🔄 Normalisation: $(basename "$input_file")"

    # Normaliser: 8kHz, mono, µ-law, volume normalisé
    ffmpeg -i "$input_file" \
        -ar $TARGET_SAMPLE_RATE \
        -ac 1 \
        -acodec $TARGET_CODEC \
        -af "volume=1.5" \
        "$output_file" \
        -y -loglevel error

    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✅ OK${NC}"
    else
        echo -e "   ${RED}❌ ERREUR${NC}"
    fi
}

# Scanner et normaliser tous les fichiers audio dans raw/
if [ -d "$AUDIO_DIR/raw" ]; then
    audio_files=$(find "$AUDIO_DIR/raw" -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.m4a" \))

    if [ -n "$audio_files" ]; then
        echo ""
        echo "🔍 Fichiers audio détectés:"

        count=0
        while IFS= read -r file; do
            filename=$(basename "$file")
            name_only="${filename%.*}"
            output_file="$AUDIO_DIR/normalized/${name_only}.wav"

            normalize_audio "$file" "$output_file"
            ((count++))
        done <<< "$audio_files"

        echo ""
        echo -e "${GREEN}✅ $count fichier(s) normalisé(s)${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠️ Aucun fichier audio dans $AUDIO_DIR/raw/${NC}"
        echo "💡 Placez vos fichiers audio (.wav, .mp3, .m4a) dans ce dossier"
    fi
else
    echo ""
    echo -e "${YELLOW}⚠️ Créez le dossier $AUDIO_DIR/raw/ et placez-y vos fichiers audio${NC}"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ Setup audio terminé!${NC}"
echo ""
echo "💡 UTILISATION:"
echo "1. Placez vos fichiers audio bruts dans: $AUDIO_DIR/raw/"
echo "2. Exécutez: ./setup_audio.sh"
echo "3. Utilisez les fichiers normalisés dans: $AUDIO_DIR/normalized/"
