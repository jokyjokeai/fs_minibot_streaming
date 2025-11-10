#!/bin/bash
###############################################################################
# Script de configuration du répertoire recordings FreeSWITCH
#
# Ce script :
# 1. Crée le répertoire /usr/local/freeswitch/recordings
# 2. Configure les permissions correctes (freeswitch:daemon)
# 3. Ajoute l'utilisateur actuel au groupe daemon
# 4. Nettoie l'ancien répertoire /tmp/minibot_recordings
#
# Usage: sudo ./setup_freeswitch_recordings.sh
###############################################################################

set -e  # Exit on error

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Configuration FreeSWITCH Recordings${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Vérifier si exécuté en root/sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Ce script doit être exécuté avec sudo${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Variables
RECORDINGS_DIR="/usr/local/freeswitch/recordings"
FS_USER="freeswitch"
FS_GROUP="daemon"
CURRENT_USER="${SUDO_USER:-$USER}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Répertoire : $RECORDINGS_DIR"
echo "  Propriétaire: $FS_USER:$FS_GROUP"
echo "  Utilisateur : $CURRENT_USER"
echo ""

# 1. Créer le répertoire s'il n'existe pas
echo -e "${BLUE}[1/5]${NC} Création du répertoire recordings..."
if [ -d "$RECORDINGS_DIR" ]; then
    echo -e "${YELLOW}  ⚠️  Répertoire existe déjà${NC}"
else
    mkdir -p "$RECORDINGS_DIR"
    echo -e "${GREEN}  ✅ Répertoire créé${NC}"
fi

# 2. Configurer le propriétaire
echo -e "${BLUE}[2/5]${NC} Configuration du propriétaire..."
chown $FS_USER:$FS_GROUP "$RECORDINGS_DIR"
echo -e "${GREEN}  ✅ Propriétaire: $FS_USER:$FS_GROUP${NC}"

# 3. Configurer les permissions (775 = rwxrwxr-x)
echo -e "${BLUE}[3/5]${NC} Configuration des permissions..."
chmod 775 "$RECORDINGS_DIR"
echo -e "${GREEN}  ✅ Permissions: 775 (rwxrwxr-x)${NC}"

# 4. Ajouter l'utilisateur au groupe daemon
echo -e "${BLUE}[4/5]${NC} Ajout de l'utilisateur au groupe daemon..."
if groups "$CURRENT_USER" | grep -q "\bdaemon\b"; then
    echo -e "${YELLOW}  ⚠️  $CURRENT_USER déjà membre du groupe daemon${NC}"
else
    usermod -a -G daemon "$CURRENT_USER"
    echo -e "${GREEN}  ✅ $CURRENT_USER ajouté au groupe daemon${NC}"
    echo -e "${YELLOW}  ⚠️  Vous devez vous reconnecter pour que les permissions prennent effet${NC}"
fi

# 5. Nettoyer ancien répertoire /tmp (optionnel)
echo -e "${BLUE}[5/5]${NC} Nettoyage ancien répertoire /tmp..."
if [ -d "/tmp/minibot_recordings" ]; then
    echo -e "${YELLOW}  Voulez-vous supprimer /tmp/minibot_recordings ? [y/N]${NC}"
    read -p "  > " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf /tmp/minibot_recordings
        echo -e "${GREEN}  ✅ Ancien répertoire supprimé${NC}"
    else
        echo -e "${YELLOW}  ⏭️  Ancien répertoire conservé${NC}"
    fi
else
    echo -e "${YELLOW}  ⏭️  Aucun ancien répertoire trouvé${NC}"
fi

# Vérification finale
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Configuration terminée avec succès !${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Vérification :"
ls -la "$RECORDINGS_DIR"
echo ""
echo -e "${YELLOW}📝 Prochaines étapes :${NC}"
echo "  1. Relancer votre session (pour groupe daemon) :"
echo "     ${BLUE}su - $CURRENT_USER${NC}"
echo ""
echo "  2. Vérifier que Python peut lire le répertoire :"
echo "     ${BLUE}python3 -c 'import os; print(os.access(\"$RECORDINGS_DIR\", os.W_OK))'${NC}"
echo ""
echo "  3. Tester un appel avec le nouveau robot_freeswitch.py"
echo ""
