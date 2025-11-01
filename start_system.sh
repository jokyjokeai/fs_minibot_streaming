#!/bin/bash
#
# Start System - MiniBotPanel v3
#
# Démarre tous les composants du système.
#
# Composants:
# - PostgreSQL
# - FreeSWITCH
# - Ollama
# - FastAPI (REST API)
#
# Utilisation:
#   ./start_system.sh
#   ./start_system.sh --api-only

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 DÉMARRAGE SYSTÈME - MiniBotPanel v3${NC}"
echo "=============================================="

API_ONLY=false

# Parser arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-only)
            API_ONLY=true
            shift
            ;;
        *)
            echo "Option inconnue: $1"
            exit 1
            ;;
    esac
done

# Fonction de vérification de service
check_service() {
    local service_name="$1"
    local check_command="$2"

    echo -n "🔍 Vérification $service_name... "

    if eval "$check_command" &> /dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ NON DISPONIBLE${NC}"
        return 1
    fi
}

if [ "$API_ONLY" = false ]; then
    echo ""
    echo "1️⃣ VÉRIFICATION SERVICES SYSTÈME"
    echo "----------------------------------------------"

    # PostgreSQL
    if check_service "PostgreSQL" "pg_isready"; then
        :
    else
        echo "💡 Démarrage PostgreSQL..."
        # macOS
        if command -v brew &> /dev/null; then
            brew services start postgresql@14 || true
        # Linux
        else
            sudo systemctl start postgresql || true
        fi
    fi

    # FreeSWITCH
    if check_service "FreeSWITCH" "fs_cli -x 'status' 2>/dev/null"; then
        :
    else
        echo -e "${YELLOW}⚠️ FreeSWITCH non démarré${NC}"
        echo "💡 Démarrez manuellement: sudo systemctl start freeswitch"
    fi

    # Ollama
    if check_service "Ollama" "curl -s http://localhost:11434/api/tags"; then
        :
    else
        echo "💡 Démarrage Ollama..."
        ollama serve &> /dev/null &
        sleep 2
    fi
fi

echo ""
echo "2️⃣ DÉMARRAGE API REST"
echo "----------------------------------------------"

# Vérifier environnement virtuel
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️ Environnement virtuel non activé${NC}"

    if [ -d "venv" ]; then
        echo "💡 Activation de l'environnement virtuel..."
        source venv/bin/activate
    else
        echo -e "${RED}❌ venv/ introuvable${NC}"
        echo "💡 Créez-le avec: python3 -m venv venv"
        exit 1
    fi
fi

# Démarrer FastAPI
echo "🚀 Lancement FastAPI..."

# Vérifier si uvicorn est installé
if ! command -v uvicorn &> /dev/null; then
    echo -e "${RED}❌ uvicorn non installé${NC}"
    echo "💡 Installez avec: pip install -r requirements.txt"
    exit 1
fi

# Lancer en mode développement
echo ""
echo -e "${GREEN}✅ Démarrage de l'API REST...${NC}"
echo ""
echo "🌐 API disponible sur: http://localhost:8000"
echo "📖 Documentation: http://localhost:8000/docs"
echo ""
echo "💡 Utilisez Ctrl+C pour arrêter"
echo "=============================================="
echo ""

# Lancer uvicorn
uvicorn system.api.main:app --reload --host 0.0.0.0 --port 8000
