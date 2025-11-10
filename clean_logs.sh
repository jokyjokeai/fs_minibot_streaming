#!/bin/bash
# Script de nettoyage des logs - MiniBotPanel

echo "🧹 Nettoyage des logs en cours..."

# Nettoyer logs application
find logs -type f -name "*.log" -delete
echo "✅ Logs application supprimés"

# Nettoyer recordings temporaires
rm -f /tmp/minibot_recordings/* 2>/dev/null
echo "✅ Recordings temporaires supprimés"

# Afficher résumé
echo ""
echo "📊 RÉSUMÉ:"
echo "- Logs: $(find logs -type f | wc -l) fichiers ($(du -sh logs 2>/dev/null | cut -f1))"
echo "- Recordings: $(ls -1 /tmp/minibot_recordings/ 2>/dev/null | wc -l) fichiers"
echo ""
echo "✅ Nettoyage terminé ! Le système est prêt pour les tests. 🚀"
