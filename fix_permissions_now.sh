#!/bin/bash
###############################################################################
# Fix rapide des permissions pour test immédiat
###############################################################################

echo "🔧 Fix permissions recordings..."

# Rendre le répertoire accessible en lecture pour tout le monde
sudo chmod 755 /usr/local/freeswitch/recordings

# Rendre les fichiers WAV lisibles
sudo chmod 644 /usr/local/freeswitch/recordings/*.wav 2>/dev/null

echo "✅ Permissions fixées !"
echo ""
echo "Vérification :"
ls -la /usr/local/freeswitch/recordings/ | head -5
echo ""
echo "Test Python :"
python3 -c "import os; print('✅ Python peut lire' if os.access('/usr/local/freeswitch/recordings', os.R_OK) else '❌ Toujours bloqué')"
echo ""
echo "🚀 Vous pouvez maintenant lancer:"
echo "   python3 test_call.py"
