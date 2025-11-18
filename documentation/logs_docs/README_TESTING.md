# Guide de Logging pour Tests

## 📋 Convention de Logging

Pour éviter la pollution de la racine du projet, **TOUS les logs de tests** doivent être générés dans ce dossier `logs/tests/`.

## ✅ Bonne Pratique

```bash
# Depuis la racine du projet
./venv/bin/python3 test_real_call.py > logs/tests/test_$(date +%Y%m%d_%H%M%S).log 2>&1

# Ou avec le wrapper fourni
./scripts/run_test.sh test_real_call.py
```

## ❌ À Éviter

```bash
# NE PAS FAIRE: log à la racine
./venv/bin/python3 test_real_call.py > test_output.log  # ❌
```

## 📁 Organisation

- **logs/tests/** → Logs de tests manuels et scripts de test
- **logs/calls/** → Logs des appels réels en production
- **logs/debug/** → Logs de debugging niveau système
- **logs/errors/** → Logs d'erreurs critiques

## 🧹 Nettoyage

Les logs de tests sont automatiquement supprimés après 30 jours (voir `.gitignore`).

```bash
# Nettoyer manuellement les logs > 7 jours
find logs/tests/ -name "*.log" -mtime +7 -delete
```

## 📝 Nommage Recommandé

Format: `test_<description>_<date>.log`

Exemples:
- `test_streaming_phase2_20251116.log`
- `test_cuda_fix_20251116_143022.log`
- `test_barge_in_diagnostics_20251116.log`

---

**Dernière mise à jour:** 2025-11-16
