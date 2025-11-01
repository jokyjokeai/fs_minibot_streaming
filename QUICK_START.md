# 🚀 MiniBotPanel v3 FINAL - Quick Start Guide

**Temps estimé**: 10 minutes | **Niveau**: Débutant

Ce guide vous permet de lancer votre premier appel autonome en 10 minutes avec les fonctionnalités par défaut.

---

## 📋 Prérequis (5 min)

### 1. Installation des dépendances

```bash
# Installation complète
pip install -r requirements.txt

# Vérification Ollama (NLP)
ollama --version
ollama pull mistral:7b-instruct-q4_0
```

### 2. Configuration de base

```bash
# Copier template environnement
cp .env.example .env

# Éditer .env avec vos paramètres
nano .env
```

**Paramètres obligatoires** dans `.env`:

```bash
# FreeSWITCH
FREESWITCH_HOST=127.0.0.1
FREESWITCH_PORT=8021
FREESWITCH_PASSWORD=ClueCon

# PostgreSQL
DATABASE_URL=postgresql://minibot:password@localhost:5432/minibot_db

# SIP Provider
SIP_USER=votre_user
SIP_PASSWORD=votre_password
SIP_PROXY=votre_proxy.com

# HuggingFace (pour speaker diarization)
HUGGINGFACE_TOKEN=hf_VOTRE_TOKEN_ICI
```

### 3. Base de données

```bash
# Création des tables
python init_db.py
```

---

## 🎯 Scénario de Test Rapide (3 min)

### Option 1: Utiliser le scénario démo fourni

```bash
# Le scénario demo_finance_b2c est déjà prêt
# Fichier: scenarios/demo_finance_b2c.json
```

**Ce scénario contient**:
- Agent autonome activé
- 3 questions de qualification (30s)
- Objections finance pré-enregistrées
- Background audio musical
- Voix "default" (Coqui TTS par défaut)

### Option 2: Créer votre propre scénario

```bash
python create_scenario.py
```

Suivez les étapes:

1. **Nom du scénario**: `test_demo`
2. **Agent autonome**: `Oui` (recommandé)
3. **Voix**: Sélectionnez `default` ou votre voix clonée
4. **Thématique**: `finance` (ou `general`, `crypto`, `energie`)
5. **Téléprospecteur**: `Sophie Martin`
6. **Société**: `FinanceConseil`
7. **Questions**: 2-3 questions simples
8. **Qualification**: Gardez les poids par défaut

**Temps total**: ~2 min

---

## 📞 Premier Appel (2 min)

### 1. Lancer le robot

```bash
python run_minibot.py
```

**Logs attendus**:
```
✅ CacheManager initialized
✅ Ollama prewarmed successfully (1200ms)
✅ Robot FreeSWITCH démarré
🔊 Background audio ready: 12 files detected
```

### 2. Lancer une campagne de test

Via l'API REST (Panel Web ou curl):

```bash
curl -X POST http://localhost:5000/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "scenario_name": "demo_finance_b2c",
    "phone_list": [
      {"phone": "+33612345678", "first_name": "Jean", "last_name": "Dupont"}
    ]
  }'
```

Ou via le Panel Web:
1. Ouvrir `http://localhost:5000`
2. Onglet **Campagnes** → **Nouvelle Campagne**
3. Sélectionner scénario `demo_finance_b2c`
4. Importer CSV avec 1-2 numéros de test
5. Cliquer **Lancer**

### 3. Monitoring en temps réel

**Panel Web**: `http://localhost:5000/dashboard`

**Logs temps réel**:
```bash
tail -f logs/minibot.log
```

**Exemple de log d'appel autonome**:
```
[INFO] Call 550e8400-e29b OUTBOUND → +33612345678
[INFO] Background audio started: corporate_ambient.wav (-8dB)
[INFO] Step: Hello → Playing audio
[INFO] ASR detected: "oui bonjour"
[INFO] NLP Intent: affirm (confidence: 0.92)
[INFO] Step: Q1 → Playing audio
[INFO] ASR detected: "pas vraiment intéressé"
[INFO] Objection matched: "pas_interesse" (42ms)
[INFO] Playing objection audio: objection_pas_interesse.wav
[INFO] Rail return question: "Ça vous parle ?"
[INFO] ASR detected: "oui pourquoi pas"
[INFO] Intent: affirm → Next step: Q2
```

---

## ✅ Vérifications Post-Appel

### 1. Statut de l'appel

**Base de données**:
```sql
SELECT call_uuid, phone_number, call_status, lead_score
FROM calls
ORDER BY created_at DESC
LIMIT 5;
```

**Statuts possibles**:
- `COMPLETED`: Appel terminé normalement
- `NO_ANSWER`: 2 silences consécutifs
- `HANGUP`: Prospect a raccroché
- `LEAD`: Qualifié (score ≥70%)

### 2. Enregistrement audio

```bash
# Fichier audio sauvegardé dans:
ls -lh audio/recordings/
# Exemple: call_550e8400-e29b_20250101_143022.wav
```

### 3. Statistiques cache

```python
from system.cache_manager import get_cache

cache = get_cache()
cache.print_stats()
```

**Résultat attendu**:
```
📊 CACHE MANAGER STATISTICS
🎬 SCENARIOS CACHE:
  • Hit rate: 85.7%
  • Cache size: 1/50
  • Cached: demo_finance_b2c

🛡️ OBJECTIONS CACHE:
  • Hit rate: 92.3%
  • Cache size: 1/20
  • Themes: finance

🤖 MODELS CACHE:
  • Preloaded: 1 models
  • Models: ollama_mistral
```

---

## 🎓 Prochaines Étapes

Maintenant que votre premier appel fonctionne, explorez:

### 1. Voice Cloning (15 min)

Cloner une voix depuis YouTube pour des appels ultra-personnalisés:

```bash
python youtube_extract.py
```

**Guide détaillé**: Voir `README_v3_FINAL.md` → Section "Voice Cloning from YouTube"

### 2. Thématiques Personnalisées (10 min)

Ajouter vos propres objections dans `system/objections_database.py`:

```python
OBJECTIONS_VOTRE_THEME = [
    ObjectionEntry(
        keywords=["pas le temps", "trop occupé"],
        response="Je comprends que vous soyez occupé. Justement...",
        audio_path="objections/votre_theme/pas_le_temps.wav"
    ),
    # ... vos objections
]
```

### 3. Campagnes Multi-Numéros (5 min)

Importer CSV avec 100+ prospects:

```csv
phone,first_name,last_name,company,custom_field
+33612345678,Jean,Dupont,ACME,VIP
+33623456789,Marie,Martin,TechCorp,Standard
```

```bash
# Panel Web → Campagnes → Importer CSV
```

### 4. Monitoring Avancé (Optionnel)

Activer Grafana + Prometheus pour dashboards temps réel:

```bash
docker-compose up -d grafana prometheus
```

Dashboard: `http://localhost:3000`

---

## 🆘 Dépannage Rapide

### Problème 1: "Ollama connection failed"

```bash
# Vérifier Ollama tourne
ollama list

# Redémarrer si nécessaire
ollama serve

# Tester connexion
curl http://localhost:11434/api/version
```

### Problème 2: "FreeSWITCH ESL connection refused"

```bash
# Vérifier FreeSWITCH
fs_cli -x "status"

# Vérifier event_socket.conf.xml
fs_cli -x "event_socket status"
```

### Problème 3: "HuggingFace token invalid"

```bash
# Vérifier token dans .env
grep HUGGINGFACE_TOKEN .env

# Générer nouveau token:
# https://huggingface.co/settings/tokens

# Accepter conditions pyannote:
# https://huggingface.co/pyannote/speaker-diarization-3.1
```

### Problème 4: "Audio not playing"

```bash
# Vérifier format audio (doit être 22050Hz mono WAV)
python setup_audio.py

# Convertir automatiquement tous les audios:
python setup_audio.py --convert-all
```

### Problème 5: "No objection matched"

**Causes**:
- Thématique incorrecte dans scénario
- Keywords trop spécifiques

**Solution**:
```python
# Vérifier thématique scenario
with open("scenarios/votre_scenario.json") as f:
    scenario = json.load(f)
    print(scenario.get("theme"))  # Doit correspondre à objections_database.py

# Ajouter keywords plus génériques
ObjectionEntry(
    keywords=["pas intéressé", "intéresse pas", "pas interet"],  # Variantes
    response="...",
)
```

---

## 📊 Benchmarks de Référence

**Latences attendues** (après prewarm):

| Composant | Latence |
|-----------|---------|
| Ollama NLP | <100ms |
| Objection Matcher | <50ms |
| Freestyle AI | 2-3s |
| TTS Coqui | 200-500ms |
| ASR Vosk | 50-200ms |
| Cache Hit | <5ms |

**Capacités**:
- **Appels simultanés**: 50-100 (selon CPU/RAM)
- **Objections/FAQ**: 80 pré-enregistrées + illimité freestyle
- **Questions rail retour**: 36 variantes automatiques

---

## 📚 Documentation Complète

Pour aller plus loin:

- **README complet**: `README_v3_FINAL.md`
- **Changelog Phases 1-8**: `README_v3_FINAL.md` → Section "Changelog Complet"
- **API Reference**: `http://localhost:5000/api/docs`
- **Architecture Agent**: `README_v3_FINAL.md` → Section "Architecture Agent Autonome"

---

## 🎉 Félicitations !

Vous avez lancé votre premier appel autonome avec MiniBotPanel v3 FINAL !

**Prochains challenges**:
- [ ] Cloner votre propre voix depuis YouTube
- [ ] Créer une campagne 100+ numéros
- [ ] Ajouter vos objections personnalisées
- [ ] Atteindre 70%+ taux de qualification

**Support**:
- Issues GitHub: `https://github.com/votre-repo/issues`
- Documentation: `README_v3_FINAL.md`

---

*Guide créé pour MiniBotPanel v3 FINAL - Phase 9 Documentation*
