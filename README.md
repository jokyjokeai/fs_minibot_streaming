# 🤖 MiniBotPanel v3 - Robot d'Appels Automatisés avec IA

**Plateforme complète de prospection téléphonique intelligente avec IA conversationnelle**

Système professionnel d'automatisation d'appels téléphoniques avec intelligence artificielle (STT, NLP, TTS), mode Freestyle AI, détection de répondeur, gestion de scénarios conversationnels, et matching intelligent d'objections.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FreeSWITCH](https://img.shields.io/badge/FreeSWITCH-1.10+-green.svg)](https://freeswitch.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## 📋 Table des Matières

- [🎯 Nouveautés v3](#-nouveautés-v3)
- [✨ Fonctionnalités](#-fonctionnalités)
- [🏗️ Architecture](#️-architecture)
- [🛠️ Stack Technique](#️-stack-technique)
- [🚀 Installation Rapide](#-installation-rapide)
- [📖 Utilisation](#-utilisation)
- [🌐 API REST](#-api-rest)
- [📚 Documentation](#-documentation)
- [🛡️ Conformité](#️-conformité)
- [🤝 Support](#-support)

---

## 🎯 Nouveautés v3

### 🚀 Fonctionnalités Majeures

#### 1. **Mode Freestyle AI** 🧠
Réponses dynamiques et contextuelles aux questions hors-script :
- ✅ Génération temps réel via Ollama (Mistral 7B)
- ✅ Cache intelligent LRU (100 entrées)
- ✅ Historique conversationnel (5 derniers échanges)
- ✅ 4 types de prompts adaptés (default, objection, price, info)
- ✅ Validation stricte (150 mots max, anti-markdown)
- ✅ **Personnalités d'agent** : 7 profils (Professionnel, Empathique, Dynamique, Assertif, Expert, Commercial, Consultatif)

#### 2. **Base d'Objections Professionnelles** 🛡️
**153 objections** pré-écrites avec réponses expertes :
- 30 objections standard (toutes industries)
- 15 Finance/Banque | 15 Trading/Crypto | 16 Énergie renouvelable
- 15 Immobilier | 16 Assurance | 15 SaaS B2B
- **16 Or (Gold Investment)** 🆕
- **15 Vin d'investissement (Wine)** 🆕

#### 3. **Matching Intelligent d'Objections** ⚡
Détection rapide et fuzzy matching :
- Algorithme hybride (70% similarité textuelle + 30% mots-clés)
- Latence : ~50ms vs 2-3s (génération Freestyle)
- 3 niveaux de confiance (high/medium/low)
- **Audio pré-enregistré instantané** si match trouvé

#### 4. **Thématiques Métier Complètes** 🎯
**8 thématiques** préconfigurées avec contexte + objections :
- Finance/Banque
- Trading/Crypto
- Énergie Renouvelable (panneaux solaires, pompes à chaleur)
- Immobilier
- Assurance
- SaaS B2B
- **Investissement Or** 🆕 (contexte marché 2025, réglementation AMF)
- **Investissement Vin** 🆕 (Grands Crus Bordeaux/Bourgogne)

#### 5. **Objectifs de Campagne** 🎪
3 objectifs configurables influençant le comportement AI :
- 📅 **Prise de RDV** : Obtenir rendez-vous avec expert
- 📞 **Lead generation** : Qualifier pour callback
- ☎️ **Call transfer** : Transfert direct vers conseiller

#### 6. **Sélection Interactive de Scénarios** 🎬
- Liste dynamique du dossier `scenarios/`
- Menu coloré avec emojis selon objectif
- Mode interactif par défaut (zéro argument)
- Metadata affichées (nom, description, objectif, nb étapes)

---

## ✨ Fonctionnalités

### 🎯 Core Features

- **Appels Automatisés** - Campagnes avec throttling intelligent (max concurrent calls)
- **Scénarios Conversationnels** - Flow dynamique JSON avec intent mapping
- **IA Multi-Services** - STT (Vosk 8kHz), NLP (Ollama), TTS (Coqui XTTS v2)
- **AMD Dual Layer** - Détection répondeur (FreeSWITCH + Python)
- **Monitoring Live** - CLI temps réel avec statistiques détaillées
- **Exports CSV** - Résultats + liens audio/transcriptions
- **Conformité Bloctel** - Vérification liste opposition avant appel
- **Barge-In** - Interruption client avec détection VAD

### 🧠 Intelligence Artificielle

| Service | Technologie | Rôle |
|---------|-------------|------|
| **STT** | Vosk 0.3.45 | Transcription temps réel (français, offline) |
| **NLP** | Ollama (Mistral 7B / Llama 3.2) | Intent detection + Sentiment analysis + Freestyle |
| **TTS** | Coqui XTTS v2 | Synthèse vocale + clonage voix réaliste |
| **VAD** | WebRTC VAD | Détection parole pour barge-in |

### 📊 Système Hybride Objections

```
┌─────────────────────────────────────────────┐
│   Client dit une objection                 │
└───────────────┬─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│   ObjectionMatcher (fuzzy matching)        │
│   Score de confiance : 0.0 - 1.0           │
└────────┬────────────────────┬────────────────┘
         │                    │
    Score ≥ 0.8           Score < 0.5
    (high confidence)     (low confidence)
         │                    │
         ▼                    ▼
┌────────────────┐   ┌──────────────────────┐
│ Audio Pré-     │   │  Freestyle AI        │
│ Enregistré     │   │  Génération          │
│ ~50ms          │   │  ~2-3s               │
└────────────────┘   └──────────────────────┘
```

**Avantages** :
- ⚡ Latence réduite : 50ms vs 2-3s
- 🎯 Réponses validées par experts
- 💰 Coût réduit (pas d'appel Ollama si match)
- 🔄 Fallback automatique si échec

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    CAMPAIGN MANAGER                            │
│     (Gestion campagnes, throttling, stats temps réel)         │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│                   ROBOT FREESWITCH                             │
│   (ESL, Originate, Event handling, 1 thread/call)             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│   │ Scenarios    │  │ AMD Service  │  │ Objection    │       │
│   │ Manager      │  │ (Dual Layer) │  │ Matcher      │       │
│   └──────────────┘  └──────────────┘  └──────────────┘       │
└────┬───────────────────────────┬───────────────────────────────┘
     │                           │
     ▼                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      AI SERVICES                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Vosk STT │  │ Ollama   │  │ Coqui TTS│  │ Freestyle   │ │
│  │ (8kHz FR)│  │ (Intent) │  │ (Clone)  │  │ AI Service  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Flux d'un Appel avec Freestyle

```
1. Campaign Manager → Lance appel (throttling)
2. Robot FreeSWITCH → Originate via ESL
3. AMD Service → Détection répondeur (dual layer)
4. Si humain détecté:
   a. Scenario Manager → Charge étape courante
   b. TTS/Audio → Joue message (barge-in ON)
   c. Vosk STT → Transcription réponse client
   d. Si question hors-script:
      → ObjectionMatcher vérifie match (score)
      → Si match high (≥0.8): Audio pré-enregistré ~50ms
      → Sinon: FreestyleAI génère réponse ~2-3s
   e. Ollama NLP → Intent + Sentiment
   f. Scenario → Étape suivante selon intent_mapping
   g. Répéter jusqu'à fin (bye_lead / bye_not_interested)
5. Robot → Enregistrement résultat + stats + audio
6. Campaign Manager → Prochain appel
```

---

## 🛠️ Stack Technique

| Composant | Technologie | Version | Rôle |
|-----------|-------------|---------|------|
| **PBX** | FreeSWITCH | 1.10+ | Gestion appels (ESL) |
| **STT** | Vosk | 0.3.45 | Speech-to-Text français offline |
| **NLP** | Ollama | Latest | Intent + Sentiment + Freestyle AI |
| **TTS** | Coqui XTTS | 0.22.0 | Synthèse vocale + clonage |
| **Database** | PostgreSQL | 14+ | Contacts, appels, résultats |
| **API** | FastAPI | 0.109+ | REST API async |
| **ORM** | SQLAlchemy | 2.0+ | Models & queries |
| **Audio** | PyDub, WebRTC VAD | - | Traitement audio |
| **Matching** | difflib + custom | - | Fuzzy matching objections |

### Modèles IA

- **Vosk** : `vosk-model-small-fr-0.22` (français, 40 MB, offline)
- **Ollama** : `mistral:7b` (recommandé) ou `llama3.2:1b` (plus rapide)
- **Coqui** : `xtts_v2` (multilingual, clonage vocal)

### Base de Données Objections

- **153 objections professionnelles** dans `system/objections_database.py`
- Recherche approfondie (Cegos, Uptoo, HubSpot, Modjo.ai)
- Réglementations françaises (AMF, Loi Hamon, RGPD, Bloctel)
- Méthodes CRAC et Rebond intégrées

---

## 🚀 Installation Rapide

### Prérequis

- **OS** : Linux (Ubuntu 20.04+) ou macOS
- **Python** : 3.11+ (3.11 ou 3.12 recommandé)
- **PostgreSQL** : 14+
- **FreeSWITCH** : 1.10+
- **Ollama** : Latest
- **GPU** : Optionnel (Coqui TTS, ~4GB VRAM recommandé)

### Installation Automatique

```bash
# 1. Cloner le projet
git clone https://github.com/jokyjokeai/fs_minibot_streaming.git
cd fs_minibot_streaming

# 2. Lancer l'installateur interactif
python3 install.py

# Suivez les instructions :
# - Installation dépendances Python
# - Configuration PostgreSQL
# - Téléchargement modèles IA
# - Configuration FreeSWITCH
# - Génération .env
```

**L'installateur configure automatiquement** :
- ✅ Environnement virtuel Python
- ✅ Dépendances (requirements.txt)
- ✅ Base de données PostgreSQL
- ✅ Modèle Vosk français
- ✅ Ollama + modèle Mistral
- ✅ Fichier .env
- ✅ Configs FreeSWITCH

### Installation Manuelle

Voir **[GUIDE_INSTALLATION.md](documentation/GUIDE_INSTALLATION.md)** pour l'installation détaillée pas à pas.

---

## 📖 Utilisation

### 1. Créer un Scénario Conversationnel

```bash
# Mode interactif (recommandé)
python3 create_scenario.py
```

**Le script vous guidera à travers** :
1. ✏️ Informations générales (nom, description)
2. 🎯 **Objectif campagne** (RDV / Lead / Transfer)
3. 📂 Choix thématique (Finance, Crypto, Or, Vin, etc.)
4. 🎭 **Personnalité agent** (Professionnel, Empathique, Commercial, etc.)
5. 🔤 Variables dynamiques ({{first_name}}, etc.)
6. ✨ Configuration Freestyle AI (contexte, max_turns)
7. ❓ Configuration questions (nombre, déterminantes)
8. 🛡️ Objections pré-enregistrées (auto-chargées selon thématique)
9. 🔊 Barge-in (ON/OFF/Custom)
10. 💾 Sauvegarde dans `scenarios/scenario_<nom>.json`

**Exemple de sortie** :
```
Scénario sauvegardé: scenarios/scenario_finance_prospect_2025.json
✅ 153 objections disponibles (standard + Finance)
✅ Personnalité: Professionnel
✅ Objectif: Prise de RDV
✅ Freestyle: Activé (max 3 tours)
```

### 2. Importer des Contacts

```bash
# Depuis CSV
python3 import_contacts.py --source contacts.csv --campaign "Prospection Or Q1"

# Depuis Excel
python3 import_contacts.py --source contacts.xlsx --campaign "Lead Crypto"
```

**Format CSV attendu** :
```csv
phone,first_name,last_name,email,company
+33612345678,Jean,Dupont,jean@example.com,Entreprise A
+33687654321,Marie,Martin,marie@example.com,Entreprise B
```

### 3. Lancer une Campagne

```bash
# Mode interactif (liste les scénarios disponibles)
python3 launch_campaign.py

# OU spécifier directement
python3 launch_campaign.py \
  --name "Prospection Or Janvier 2025" \
  --contacts contacts.csv \
  --scenario scenario_or_investissement
```

**Menu interactif** :
```
╔════════════════════════════════════════════════════════════════╗
║  📋 Scénarios disponibles (3 trouvés)                          ║
╚════════════════════════════════════════════════════════════════╝

1. Finance Prospect 2025
   Prospection bancaire B2C avec freestyle
   📅 Objectif: appointment | 12 étapes

2. Or Investissement
   Placement or physique patrimoine
   📞 Objectif: lead_generation | 10 étapes

3. Vin Grands Crus
   Investissement vin Bordeaux/Bourgogne
   📅 Objectif: appointment | 11 étapes

Choisissez un scénario [1-3] (ou 'q' pour annuler):
```

### 4. Monitoring Temps Réel

```bash
# Monitoring auto-refresh
python3 monitor_campaign.py --campaign-id 1 --refresh 2
```

**Affichage live** :
```
╔══════════════════════════════════════════════════════════════╗
║           MONITORING CAMPAGNE #1                             ║
║           Prospection Or Janvier 2025                        ║
╠══════════════════════════════════════════════════════════════╣
║  Total       : 150 appels                                    ║
║  Complétés   : 87  (58%)                                     ║
║  En cours    : 3   [=====>    ]                              ║
╠══════════════════════════════════════════════════════════════╣
║  ✅ Leads            : 23  (26%)                             ║
║  ❌ Pas intéressé    : 45  (52%)                             ║
║  📞 Rappel           : 12  (14%)                             ║
║  🤖 Répondeur        : 5   (6%)                              ║
║  ⏰ Pas de réponse   : 2   (2%)                              ║
╠══════════════════════════════════════════════════════════════╣
║  Durée moyenne       : 98s                                   ║
║  Sentiment positif   : 65%                                   ║
║  Objections matchées : 18/23 (78%)                           ║
║  Freestyle utilisé   : 5 fois (avg 2.3s)                     ║
╚══════════════════════════════════════════════════════════════╝
```

### 5. Cloner une Voix (Optionnel)

```bash
# Cloner voix depuis échantillon (min 6 secondes)
python3 clone_voice.py \
  --audio julie_sample.wav \
  --name julie \
  --test "Bonjour, ceci est un test de clonage vocal"

# Audio test généré: voices/test_julie.wav
```

### 6. Export Résultats

```bash
# Export CSV complet
python3 export_campaign.py --campaign-id 1 --output resultats.csv
```

**Contenu CSV** :
```csv
phone,first_name,last_name,result,duration,sentiment,objections_matched,audio_link,transcript_link
+33612345678,Jean,Dupont,lead,120,positive,2,http://localhost:8000/api/exports/audio/abc123,http://localhost:8000/api/exports/transcript/abc123
```

---

## 🌐 API REST

### Démarrer l'API

```bash
# Démarrer tous les services
./start_system.sh

# OU manuellement
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Documentation interactive: http://localhost:8000/docs
```

### Endpoints Principaux

**Campagnes** :
```bash
# Créer campagne
POST /api/campaigns/
{
  "name": "Ma Campagne Or",
  "contact_ids": [1, 2, 3],
  "scenario": "scenario_or_investissement"
}

# Lancer
POST /api/campaigns/{id}/start

# Stats live
GET /api/campaigns/{id}/stats
```

**Scénarios** :
```bash
# Lister scénarios disponibles
GET /api/scenarios/

# Détails scénario
GET /api/scenarios/{name}
```

**Exports** :
```bash
# Export CSV
GET /api/exports/campaign/{id}/csv

# Télécharger audio
GET /api/exports/audio/{call_uuid}

# Télécharger transcription JSON
GET /api/exports/transcript/{call_uuid}
```

**Objections** :
```bash
# Lister objections par thématique
GET /api/objections/{thematique}

# Tester matching
POST /api/objections/match
{
  "user_input": "Pas le temps",
  "thematique": "standard",
  "min_score": 0.5
}
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[GUIDE_INSTALLATION.md](documentation/GUIDE_INSTALLATION.md)** | Installation détaillée pas à pas |
| **[GUIDE_UTILISATION.md](documentation/GUIDE_UTILISATION.md)** | Guide complet utilisation |
| **[BRIEF_PROJET.md](documentation/BRIEF_PROJET.md)** | Architecture technique complète |
| **[FREESTYLE_MODE.md](documentation/FREESTYLE_MODE.md)** | Documentation mode Freestyle AI |
| **[scenarios/README.md](scenarios/README.md)** | Guide création scénarios |

### Exemples

- `scenarios/scenario_test_demo.json` - Scénario de test complet
- `documentation/scenarios/exemple_freestyle.json` - Exemple Freestyle
- `system/objections_database.py` - 153 objections professionnelles

---

## 🛡️ Conformité

### Bloctel (France)

Vérification automatique liste opposition avant appel :

```bash
# Dans .env
BLOCTEL_ENABLED=true
BLOCTEL_API_KEY=votre_cle_api
BLOCTEL_CHECK_BEFORE_CALL=true
```

### RGPD

- ✅ Stockage local des enregistrements et transcriptions
- ✅ Export/suppression données via API
- ✅ Consentement à intégrer dans scénarios
- ✅ Logs d'accès et modifications

### Réglementations Intégrées

- **AMF** : Autorité des Marchés Financiers (Crypto, Or)
- **Loi Hamon** : Changement assurance (objections Assurance)
- **MaPrimeRénov** : Aides énergie (objections Énergie)
- **Loi Lagarde** : Assurance crédit (objections Finance)

---

## 🧪 Tests

```bash
# Tester tous les services IA
python3 test_services.py

# Tester service spécifique
python3 test_services.py --service vosk
python3 test_services.py --service ollama
python3 test_services.py --service coqui

# Tester matcher d'objections
python3 system/objection_matcher.py

# Tester base objections
python3 system/objections_database.py
```

---

## 🔧 Dépannage

### Vosk ne démarre pas

```bash
# Vérifier modèle
ls -la models/vosk-model-small-fr-0.22/

# Retélécharger
cd models/
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
unzip vosk-model-small-fr-0.22.zip
```

### Ollama timeout

```bash
# Vérifier service
curl http://localhost:11434/api/tags

# Redémarrer
ollama serve

# Pull modèle
ollama pull mistral:7b
```

### FreeSWITCH connexion refusée

```bash
# Vérifier ESL
fs_cli -x "event_socket status"

# Vérifier config
cat /etc/freeswitch/autoload_configs/event_socket.conf.xml

# Redémarrer
sudo systemctl restart freeswitch
```

### Freestyle génère réponses vides

```bash
# Vérifier logs
tail -f logs/minibot.log | grep Freestyle

# Tester Ollama directement
curl http://localhost:11434/api/generate -d '{
  "model": "mistral:7b",
  "prompt": "Test"
}'
```

---

## 🤝 Support

- **Issues GitHub** : [https://github.com/jokyjokeai/fs_minibot_streaming/issues](https://github.com/jokyjokeai/fs_minibot_streaming/issues)
- **Documentation** : Dossier `documentation/`
- **Email** : support@minibotpanel.com

---

## 📝 Changelog

### v3.0.0 (2025-01-29)
- ✨ Mode Freestyle AI avec Ollama
- ✨ 7 Personnalités d'agent configurable
- ✨ Système matching intelligent objections (fuzzy + keywords)
- ✨ 153 objections professionnelles (8 thématiques)
- ✨ Thématiques Or et Vin investissement
- ✨ Objectifs de campagne (RDV/Lead/Transfer)
- ✨ Sélection interactive scénarios
- ✨ Dossier scenarios/ dédié
- 🐛 Corrections diverses et optimisations

### v2.0.0 (2024-10)
- ✨ Intégration Coqui TTS avec clonage vocal
- ✨ AMD dual layer
- ✨ Barge-in avec VAD
- ✨ API REST FastAPI

### v1.0.0 (2024-06)
- 🎉 Version initiale
- ✨ Robot FreeSWITCH basique
- ✨ Vosk STT + Ollama NLP

---

## 👥 Auteurs

- **Équipe MiniBotPanel** - Développement initial
- **Claude Code (Anthropic)** - Co-développement v3

---

## 🙏 Remerciements

- **Vosk** (Alpha Cephei) - STT offline français
- **Ollama** (Ollama.ai) - NLP et Freestyle AI
- **Coqui TTS** (Coqui.ai) - Clonage vocal
- **FreeSWITCH** (FreeSWITCH Community) - PBX open source
- **Anthropic Claude** - Assistance développement IA

---

## 📄 Licence

Copyright © 2025 MiniBotPanel

Ce projet est sous licence propriétaire. Voir le fichier `LICENSE` pour plus de détails.

---

<div align="center">

**MiniBotPanel v3** - Robot d'Appels Conversationnels avec IA 🤖

[Installation](documentation/GUIDE_INSTALLATION.md) • [Utilisation](documentation/GUIDE_UTILISATION.md) • [API](documentation/API_REFERENCE.md) • [Support](https://github.com/jokyjokeai/fs_minibot_streaming/issues)

</div>
