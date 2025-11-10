#!/bin/bash
###############################################################################
# Fix permissions répertoires parents
###############################################################################

echo "🔧 Fix permissions répertoires parents..."
echo ""

# Le problème : /usr/local/freeswitch/ n'a pas +x pour les autres
# Solution : Ajouter r-x sur les répertoires parents

echo "[1/3] Fix /usr/local/freeswitch..."
sudo chmod o+rx /usr/local/freeswitch

echo "[2/3] Fix /usr/local/freeswitch/recordings..."
sudo chmod 755 /usr/local/freeswitch/recordings

echo "[3/3] Fix fichiers WAV..."
sudo chmod 644 /usr/local/freeswitch/recordings/*.wav 2>/dev/null || echo "  (aucun fichier WAV pour l'instant)"

echo ""
echo "✅ Permissions fixées !"
echo ""
echo "Vérification :"
ls -la /usr/local/freeswitch/recordings/ | head -5
echo ""
echo "Test Python :"
python3 -c "import os; print('✅ Python peut lire' if os.access('/usr/local/freeswitch/recordings', os.R_OK) else '❌ Toujours bloqué')"
echo ""
echo "🚀 Lancez maintenant:"
echo "   python3 test_call.py"
