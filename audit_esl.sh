#!/bin/bash
#
# Audit ESL & FreeSWITCH - MiniBotPanel v3
# Script de diagnostic complet pour identifier les problèmes ESL
#
# Usage:
#   chmod +x audit_esl.sh
#   ./audit_esl.sh
#

set +e  # Ne pas arrêter sur erreurs

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  AUDIT ESL & FreeSWITCH${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# ============================================
# 1. SYSTÈME
# ============================================
echo -e "${BLUE}[1/10] Informations système${NC}"
echo "----------------------------------------"
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"')"
echo "Kernel: $(uname -r)"
echo "Python: $(python3 --version 2>&1)"
echo "Hostname: $(hostname)"
echo "IP: $(hostname -I | awk '{print $1}')"
echo ""

# ============================================
# 2. FREESWITCH INSTALLATION
# ============================================
echo -e "${BLUE}[2/10] FreeSWITCH Installation${NC}"
echo "----------------------------------------"

# Version FreeSWITCH
if command -v freeswitch &> /dev/null; then
    echo -e "${GREEN}✅ FreeSWITCH binary found${NC}"
    echo "Binary: $(which freeswitch)"
    FS_VERSION=$(freeswitch -version 2>&1 | head -1)
    echo "Version: $FS_VERSION"
else
    echo -e "${RED}❌ FreeSWITCH binary not found${NC}"
fi
echo ""

# Packages installés
echo "Packages FreeSWITCH installés:"
if command -v dpkg &> /dev/null; then
    dpkg -l | grep freeswitch | awk '{print "  - " $2 " (" $3 ")"}'
elif command -v rpm &> /dev/null; then
    rpm -qa | grep freeswitch | awk '{print "  - " $1}'
fi
echo ""

# ============================================
# 3. FREESWITCH PROCESSUS
# ============================================
echo -e "${BLUE}[3/10] FreeSWITCH Processus${NC}"
echo "----------------------------------------"

FS_PID=$(pgrep -f freeswitch)
if [ -n "$FS_PID" ]; then
    echo -e "${GREEN}✅ FreeSWITCH running (PID: $FS_PID)${NC}"
    ps aux | grep freeswitch | grep -v grep | head -3
else
    echo -e "${RED}❌ FreeSWITCH not running${NC}"
fi
echo ""

# ============================================
# 4. PORTS & NETWORK
# ============================================
echo -e "${BLUE}[4/10] Ports réseau${NC}"
echo "----------------------------------------"

# Port ESL (8021)
if netstat -tlnp 2>/dev/null | grep -q ":8021"; then
    echo -e "${GREEN}✅ Port ESL 8021 listening${NC}"
    netstat -tlnp 2>/dev/null | grep ":8021"
else
    echo -e "${RED}❌ Port ESL 8021 not listening${NC}"
fi
echo ""

# Port SIP (5060/5080)
if netstat -tlnp 2>/dev/null | grep -q ":5060\|:5080"; then
    echo -e "${GREEN}✅ Port SIP listening${NC}"
    netstat -tlnp 2>/dev/null | grep ":5060\|:5080"
else
    echo -e "${YELLOW}⚠️  Port SIP not listening${NC}"
fi
echo ""

# ============================================
# 5. ESL.py RECHERCHE
# ============================================
echo -e "${BLUE}[5/10] Recherche ESL.py${NC}"
echo "----------------------------------------"

ESL_FOUND=false

# Localisation 1: /usr/lib/freeswitch/mod/
if [ -f "/usr/lib/freeswitch/mod/ESL.py" ]; then
    echo -e "${GREEN}✅ ESL.py trouvé: /usr/lib/freeswitch/mod/ESL.py${NC}"
    ls -lh /usr/lib/freeswitch/mod/ESL.py
    ESL_FOUND=true
fi

# Localisation 2: /usr/share/freeswitch/scripts/
if [ -f "/usr/share/freeswitch/scripts/ESL.py" ]; then
    echo -e "${GREEN}✅ ESL.py trouvé: /usr/share/freeswitch/scripts/ESL.py${NC}"
    ls -lh /usr/share/freeswitch/scripts/ESL.py
    ESL_FOUND=true
fi

# Localisation 3: /usr/local/freeswitch/
if [ -f "/usr/local/freeswitch/lib/python3/ESL.py" ]; then
    echo -e "${GREEN}✅ ESL.py trouvé: /usr/local/freeswitch/lib/python3/ESL.py${NC}"
    ls -lh /usr/local/freeswitch/lib/python3/ESL.py
    ESL_FOUND=true
fi

# Recherche exhaustive
echo "Recherche exhaustive (peut prendre 10-20s)..."
FIND_RESULTS=$(find /usr -name "ESL.py" 2>/dev/null)
if [ -n "$FIND_RESULTS" ]; then
    echo -e "${GREEN}ESL.py trouvés:${NC}"
    echo "$FIND_RESULTS" | while read line; do
        echo "  - $line ($(stat -c%s "$line" 2>/dev/null || stat -f%z "$line" 2>/dev/null) bytes)"
    done
    ESL_FOUND=true
else
    echo -e "${YELLOW}⚠️  Aucun ESL.py trouvé via find${NC}"
fi
echo ""

# ============================================
# 6. _ESL.so RECHERCHE (module natif)
# ============================================
echo -e "${BLUE}[6/10] Recherche _ESL.so (module natif)${NC}"
echo "----------------------------------------"

FIND_SO=$(find /usr -name "_ESL.so" 2>/dev/null)
if [ -n "$FIND_SO" ]; then
    echo -e "${GREEN}_ESL.so trouvés:${NC}"
    echo "$FIND_SO" | while read line; do
        echo "  - $line"
        file "$line"
    done
else
    echo -e "${YELLOW}⚠️  Aucun _ESL.so trouvé${NC}"
fi
echo ""

# ============================================
# 7. SOURCES FREESWITCH
# ============================================
echo -e "${BLUE}[7/10] Sources FreeSWITCH${NC}"
echo "----------------------------------------"

if [ -d "/usr/src/freeswitch" ]; then
    echo -e "${GREEN}✅ Sources FreeSWITCH: /usr/src/freeswitch${NC}"

    if [ -d "/usr/src/freeswitch/libs/esl" ]; then
        echo -e "${GREEN}✅ Dossier ESL: /usr/src/freeswitch/libs/esl${NC}"

        # Vérifier si Makefile existe
        if [ -f "/usr/src/freeswitch/libs/esl/Makefile" ]; then
            echo -e "${GREEN}✅ Makefile ESL trouvé${NC}"
        else
            echo -e "${YELLOW}⚠️  Makefile ESL manquant${NC}"
        fi
    else
        echo -e "${RED}❌ Dossier ESL manquant: /usr/src/freeswitch/libs/esl${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Sources FreeSWITCH non trouvées: /usr/src/freeswitch${NC}"
fi
echo ""

# ============================================
# 8. PYTHON VENV & DÉPENDANCES
# ============================================
echo -e "${BLUE}[8/10] Environnement Python${NC}"
echo "----------------------------------------"

PROJECT_DIR="/root/fs_minibot_streaming"
if [ -d "$PROJECT_DIR" ]; then
    echo -e "${GREEN}✅ Projet: $PROJECT_DIR${NC}"

    if [ -d "$PROJECT_DIR/venv" ]; then
        echo -e "${GREEN}✅ Venv: $PROJECT_DIR/venv${NC}"

        # Vérifier si ESL.py dans venv
        if [ -f "$PROJECT_DIR/venv/lib/python3.11/site-packages/ESL.py" ]; then
            echo -e "${GREEN}✅ ESL.py dans venv${NC}"
            ls -lh "$PROJECT_DIR/venv/lib/python3.11/site-packages/ESL.py"
        else
            echo -e "${YELLOW}⚠️  ESL.py absent du venv${NC}"
        fi

        # Vérifier _ESL.so dans venv
        if [ -f "$PROJECT_DIR/venv/lib/python3.11/site-packages/_ESL.so" ]; then
            echo -e "${GREEN}✅ _ESL.so dans venv${NC}"
        else
            echo -e "${YELLOW}⚠️  _ESL.so absent du venv${NC}"
        fi
    else
        echo -e "${RED}❌ Venv manquant: $PROJECT_DIR/venv${NC}"
    fi
else
    echo -e "${RED}❌ Projet non trouvé: $PROJECT_DIR${NC}"
fi
echo ""

# ============================================
# 9. TEST IMPORT ESL PYTHON
# ============================================
echo -e "${BLUE}[9/10] Test import ESL Python${NC}"
echo "----------------------------------------"

if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate" 2>/dev/null

    # Test import ESL
    python3 << 'EOF'
import sys
import os

print("Python version:", sys.version)
print("Python executable:", sys.executable)
print("")

# Test 1: Import depuis venv
print("Test 1: Import ESL depuis venv")
try:
    from ESL import ESLconnection
    print("✅ ESL importé depuis venv")
except ImportError as e:
    print(f"❌ Import venv échoué: {e}")

# Test 2: Import depuis /usr/share/freeswitch/scripts
print("\nTest 2: Import ESL depuis /usr/share/freeswitch/scripts")
try:
    sys.path.insert(0, '/usr/share/freeswitch/scripts')
    from ESL import ESLconnection
    print("✅ ESL importé depuis FreeSWITCH scripts")
except ImportError as e:
    print(f"❌ Import scripts échoué: {e}")

# Test 3: Import depuis /usr/lib/freeswitch/mod
print("\nTest 3: Import ESL depuis /usr/lib/freeswitch/mod")
try:
    if '/usr/lib/freeswitch/mod' not in sys.path:
        sys.path.insert(0, '/usr/lib/freeswitch/mod')
    from ESL import ESLconnection
    print("✅ ESL importé depuis FreeSWITCH mod")
except ImportError as e:
    print(f"❌ Import mod échoué: {e}")

# Test 4: Import depuis system/
print("\nTest 4: Import ESL depuis system/")
try:
    sys.path.insert(0, '/root/fs_minibot_streaming/system')
    from ESL import ESLconnection
    print("✅ ESL importé depuis system/")
except ImportError as e:
    print(f"❌ Import system/ échoué: {e}")
EOF

    deactivate 2>/dev/null
else
    echo -e "${RED}❌ Impossible de tester (venv manquant)${NC}"
fi
echo ""

# ============================================
# 10. TEST CONNEXION ESL
# ============================================
echo -e "${BLUE}[10/10] Test connexion ESL${NC}"
echo "----------------------------------------"

# Lire config .env
if [ -f "$PROJECT_DIR/.env" ]; then
    ESL_HOST=$(grep "^FREESWITCH_HOST=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"' | tr -d "'")
    ESL_PORT=$(grep "^FREESWITCH_PORT=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"' | tr -d "'")
    ESL_PASSWORD=$(grep "^FREESWITCH_PASSWORD=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"' | tr -d "'")

    ESL_HOST=${ESL_HOST:-127.0.0.1}
    ESL_PORT=${ESL_PORT:-8021}
    ESL_PASSWORD=${ESL_PASSWORD:-ClueCon}

    echo "Configuration ESL (.env):"
    echo "  Host: $ESL_HOST"
    echo "  Port: $ESL_PORT"
    echo "  Password: ${ESL_PASSWORD:0:3}***"
    echo ""
fi

# Test telnet
echo "Test connexion telnet..."
timeout 3 bash -c "echo -e 'auth $ESL_PASSWORD\nexit\n' | telnet $ESL_HOST $ESL_PORT 2>/dev/null" | head -5
echo ""

# Test avec Python si ESL disponible
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate" 2>/dev/null

    python3 << EOF
import sys
sys.path.insert(0, '/usr/share/freeswitch/scripts')

try:
    from ESL import ESLconnection

    esl = ESLconnection("$ESL_HOST", "$ESL_PORT", "$ESL_PASSWORD")

    if esl.connected():
        print("✅ ESL connexion réussie")

        # Test API
        result = esl.api("status")
        if result:
            status = result.getBody()
            print(f"\nFreeSWITCH status:\n{status[:200]}...")
    else:
        print("❌ ESL connexion échouée")

except Exception as e:
    print(f"⚠️  Test ESL impossible: {e}")
EOF

    deactivate 2>/dev/null
fi
echo ""

# ============================================
# RÉSUMÉ
# ============================================
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  RÉSUMÉ AUDIT${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

ISSUES=0

# FreeSWITCH running?
if [ -n "$FS_PID" ]; then
    echo -e "${GREEN}✅ FreeSWITCH running${NC}"
else
    echo -e "${RED}❌ FreeSWITCH NOT running${NC}"
    ((ISSUES++))
fi

# Port ESL listening?
if netstat -tlnp 2>/dev/null | grep -q ":8021"; then
    echo -e "${GREEN}✅ Port ESL 8021 listening${NC}"
else
    echo -e "${RED}❌ Port ESL 8021 NOT listening${NC}"
    ((ISSUES++))
fi

# ESL.py found?
if [ "$ESL_FOUND" = true ]; then
    echo -e "${GREEN}✅ ESL.py trouvé sur le système${NC}"
else
    echo -e "${RED}❌ ESL.py NOT found${NC}"
    ((ISSUES++))
fi

# Venv exists?
if [ -d "$PROJECT_DIR/venv" ]; then
    echo -e "${GREEN}✅ Venv configuré${NC}"
else
    echo -e "${RED}❌ Venv NOT configured${NC}"
    ((ISSUES++))
fi

echo ""
echo -e "${CYAN}Problèmes détectés: $ISSUES${NC}"
echo ""

# ============================================
# RECOMMANDATIONS
# ============================================
if [ $ISSUES -gt 0 ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  RECOMMANDATIONS${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""

    if [ -z "$FS_PID" ]; then
        echo -e "${YELLOW}1. Démarrer FreeSWITCH:${NC}"
        echo "   systemctl start freeswitch"
        echo ""
    fi

    if ! netstat -tlnp 2>/dev/null | grep -q ":8021"; then
        echo -e "${YELLOW}2. Vérifier config ESL dans FreeSWITCH:${NC}"
        echo "   /etc/freeswitch/autoload_configs/event_socket.conf.xml"
        echo ""
    fi

    if [ "$ESL_FOUND" = false ]; then
        echo -e "${YELLOW}3. Compiler ESL Python:${NC}"
        echo "   cd /usr/src/freeswitch/libs/esl"
        echo "   make pymod"
        echo "   cp python/ESL.py python/_ESL.so $PROJECT_DIR/venv/lib/python3.11/site-packages/"
        echo ""
    fi
fi

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Audit terminé !${NC}"
echo -e "${CYAN}========================================${NC}"
