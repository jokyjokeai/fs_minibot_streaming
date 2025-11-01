#!/bin/bash
#
# Stop System - MiniBotPanel v3
#
# Arrête tous les composants du système.
#
# Composants:
# - FastAPI
# - Ollama (optionnel)
# - FreeSWITCH (optionnel)
#
# Utilisation:
#   ./stop_system.sh
#   ./stop_system.sh --all (arrête aussi Ollama et FreeSWITCH)

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🛑 ARRÊT SYSTÈME - MiniBotPanel v3${NC}"
echo "=============================================="

STOP_ALL=false

# Parser arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            STOP_ALL=true
            shift
            ;;
        *)
            echo "Option inconnue: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "1️⃣ ARRÊT API REST"
echo "----------------------------------------------"

# Arrêter uvicorn/FastAPI
if pgrep -f "uvicorn system.api.main:app" > /dev/null; then
    echo "🛑 Arrêt de l'API FastAPI..."
    pkill -f "uvicorn system.api.main:app" || true
    echo -e "${GREEN}✅ API arrêtée${NC}"
else
    echo -e "${YELLOW}⚠️ API non démarrée${NC}"
fi

if [ "$STOP_ALL" = true ]; then
    echo ""
    echo "2️⃣ ARRÊT SERVICES OPTIONNELS"
    echo "----------------------------------------------"

    # Arrêter Ollama
    if pgrep -f "ollama" > /dev/null; then
        echo "🛑 Arrêt Ollama..."
        pkill -f "ollama" || true
        echo -e "${GREEN}✅ Ollama arrêté${NC}"
    else
        echo -e "${YELLOW}⚠️ Ollama non démarré${NC}"
    fi

    # FreeSWITCH (nécessite sudo)
    echo ""
    echo -e "${YELLOW}⚠️ FreeSWITCH doit être arrêté manuellement:${NC}"
    echo "   sudo systemctl stop freeswitch"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ Arrêt terminé!${NC}"

if [ "$STOP_ALL" = false ]; then
    echo ""
    echo "💡 Pour arrêter tous les services: ./stop_system.sh --all"
fi
