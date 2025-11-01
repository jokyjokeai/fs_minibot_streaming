# 📦 GUIDE D'INSTALLATION COMPLET - MiniBotPanel v3

Installation complète du système de robot d'appels conversationnels avec FreeSWITCH, IA Freestyle et matching intelligent d'objections.

---

## 📋 TABLE DES MATIÈRES

1. [Prérequis Système](#1-prérequis-système)
2. [Installation PostgreSQL](#2-installation-postgresql)
3. [Installation FreeSWITCH](#3-installation-freeswitch)
4. [Installation Python & Dépendances](#4-installation-python--dépendances)
5. [Configuration FreeSWITCH](#5-configuration-freeswitch)
6. [Installation des Modèles IA](#6-installation-des-modèles-ia)
7. [Configuration du Projet](#7-configuration-du-projet)
8. [Initialisation de la Base de Données](#8-initialisation-de-la-base-de-données)
9. [Tests de Validation](#9-tests-de-validation)
10. [Démarrage du Système](#10-démarrage-du-système)
11. [Configuration Freestyle AI](#11-configuration-freestyle-ai)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. PRÉREQUIS SYSTÈME

### Matériel Minimum

| Composant | Minimum | Recommandé | Pour Freestyle AI |
|-----------|---------|------------|-------------------|
| CPU | 2 cores | 4+ cores | 8+ cores |
| RAM | 4 GB | 8 GB | **12 GB** (Mistral 7B) |
| Disque | 20 GB | 50 GB SSD | 100 GB SSD |
| GPU | — | NVIDIA (optionnel) | RTX 3060+ (accélération TTS) |
| Réseau | 10 Mbps | 100 Mbps | 1 Gbps (streaming) |

**⚠️ Note Freestyle AI** : Le mode Freestyle nécessite au minimum **8 GB RAM** pour Mistral 7B ou **4 GB RAM** pour Llama 3.2 1B.

### Système d'exploitation

**Linux (recommandé) :**
- Ubuntu 20.04 LTS / 22.04 LTS / 24.04 LTS
- Debian 11 / 12
- Rocky Linux 8 / 9

**macOS :**
- macOS 12+ (Monterey ou supérieur)
- **Note :** python-ESL nécessite compilation manuelle

**Windows :**
- Non supporté officiellement (utiliser WSL2)

### Logiciels requis

```bash
# Ubuntu/Debian
- Python 3.11+ (3.11 recommandé)
- PostgreSQL 14+
- FreeSWITCH 1.10+
- Git
- Build essentials
- ffmpeg
- Ollama (pour Freestyle AI)

# macOS
- Homebrew
- Python 3.11+ (via brew)
- PostgreSQL 14+ (via brew)
- FreeSWITCH (via brew ou compilation)
- Ollama (via official installer)
```

---

## 2. INSTALLATION POSTGRESQL

### Ubuntu/Debian

```bash
# 1. Ajouter repository PostgreSQL
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# 2. Installer PostgreSQL
sudo apt update
sudo apt install -y postgresql-14 postgresql-contrib-14

# 3. Démarrer le service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 4. Vérifier le statut
sudo systemctl status postgresql
```

### macOS

```bash
# Via Homebrew
brew install postgresql@14
brew services start postgresql@14

# Vérifier
psql --version
# Sortie attendue : psql (PostgreSQL) 14.x
```

### Créer la base de données

```bash
# 1. Se connecter comme postgres
sudo -u postgres psql

# 2. Dans le shell PostgreSQL :
CREATE DATABASE minibot_freeswitch;
CREATE USER minibot WITH PASSWORD 'minibot';
GRANT ALL PRIVILEGES ON DATABASE minibot_freeswitch TO minibot;
\q

# 3. Tester la connexion
psql -h localhost -U minibot -d minibot_freeswitch
# Entrer le mot de passe : minibot
```

**⚠️ PRODUCTION** : Changez le mot de passe `minibot` pour un mot de passe fort !

---

## 3. INSTALLATION FREESWITCH

### Ubuntu/Debian (via packages)

```bash
# 1. Ajouter la clé GPG FreeSWITCH
wget -O - https://files.freeswitch.org/repo/deb/debian-release/fsstretch-archive-keyring.asc | sudo apt-key add -

# 2. Ajouter le repository
echo "deb http://files.freeswitch.org/repo/deb/debian-release/ $(lsb_release -sc) main" | sudo tee /etc/apt/sources.list.d/freeswitch.list

# 3. Installer FreeSWITCH
sudo apt update
sudo apt install -y freeswitch-meta-all

# 4. Démarrer FreeSWITCH
sudo systemctl start freeswitch
sudo systemctl enable freeswitch

# 5. Vérifier
sudo systemctl status freeswitch
fs_cli -x "status"
```

### macOS (via Homebrew)

```bash
# Installer FreeSWITCH
brew install freeswitch

# Démarrer FreeSWITCH
brew services start freeswitch

# Vérifier
fs_cli -x "status"
```

### Compilation depuis les sources (optionnel)

```bash
# 1. Cloner le repository
cd /usr/src
sudo git clone https://github.com/signalwire/freeswitch.git
cd freeswitch

# 2. Bootstrap
sudo ./bootstrap.sh -j

# 3. Configuration
sudo ./configure --prefix=/usr/local/freeswitch

# 4. Compiler
sudo make -j$(nproc)
sudo make install

# 5. Créer le service systemd
sudo nano /etc/systemd/system/freeswitch.service
```

**Contenu du fichier freeswitch.service :**

```ini
[Unit]
Description=FreeSWITCH
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/freeswitch/bin/freeswitch -nc -nonat
ExecReload=/usr/local/freeswitch/bin/fs_cli -x "reloadxml"
ExecStop=/usr/local/freeswitch/bin/fs_cli -x "shutdown"
Restart=on-failure
RestartSec=10
User=freeswitch
Group=freeswitch

[Install]
WantedBy=multi-user.target
```

```bash
# Activer et démarrer
sudo systemctl daemon-reload
sudo systemctl enable freeswitch
sudo systemctl start freeswitch
```

---

## 4. INSTALLATION PYTHON & DÉPENDANCES

### 1. Installer Python 3.11+ ou 3.11

**Ubuntu/Debian :**

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y build-essential libffi-dev libssl-dev libsndfile1-dev
```

**macOS :**

```bash
brew install python@3.11
```

### 2. Cloner le projet

```bash
cd /opt  # Ou tout autre répertoire
sudo git clone <url_du_repository> minibot_streaming
cd minibot_streaming
sudo chown -R $USER:$USER .
```

### 3. Créer l'environnement virtuel

```bash
python3.11 -m venv venv
source venv/bin/activate

# Vérifier
python --version
# Sortie : Python 3.11.x
```

### 4. Installer les dépendances Python

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Note :** L'installation peut prendre 10-20 minutes (téléchargement de PyTorch, Coqui TTS, transformers, etc.)

**Nouveautés v3** installées via requirements.txt :
- `ollama` : Client Python pour Freestyle AI
- `difflib` : Matching fuzzy d'objections (intégré à Python)
- `python-dotenv` : Gestion variables d'environnement

### 5. Installer python-ESL

**Linux :**

```bash
# Si disponible via apt
sudo apt install freeswitch-python-esl

# Ou via pip (version compatible)
pip install python-esl
```

**macOS :** (Compilation manuelle requise)

```bash
# Copier ESL.py depuis FreeSWITCH sources
cp /usr/local/freeswitch/share/freeswitch/scripts/ESL.py venv/lib/python3.11/site-packages/

# Ou compiler depuis les sources FreeSWITCH
cd /usr/local/freeswitch/libs/esl
make pymod
cp ESL.py $VIRTUAL_ENV/lib/python3.11/site-packages/
```

### 6. Installer ffmpeg

**Ubuntu/Debian :**

```bash
sudo apt install -y ffmpeg
```

**macOS :**

```bash
brew install ffmpeg
```

**Vérifier :**

```bash
ffmpeg -version
# Sortie : ffmpeg version 4.x ou 5.x
```

---

## 5. CONFIGURATION FREESWITCH

### 1. Configuration Event Socket Layer (ESL)

Éditer `/etc/freeswitch/autoload_configs/event_socket.conf.xml` :

```xml
<configuration name="event_socket.conf" description="Socket Protocol">
  <settings>
    <param name="listen-ip" value="127.0.0.1"/>
    <param name="listen-port" value="8021"/>
    <param name="password" value="ClueCon"/>
    <param name="apply-inbound-acl" value="loopback.auto"/>
  </settings>
</configuration>
```

**⚠️ PRODUCTION :** Changez le mot de passe `ClueCon` !

### 2. Configuration du dialplan

Créer `/etc/freeswitch/dialplan/minibot_outbound.xml` :

```xml
<?xml version="1.0" encoding="utf-8"?>
<include>
  <context name="minibot">
    <extension name="outbound_calls">
      <condition field="destination_number" expression="^(.+)$">
        <action application="set" data="continue_on_fail=true"/>
        <action application="set" data="hangup_after_bridge=true"/>
        <action application="answer"/>
        <action application="sleep" data="100"/>
        <action application="park"/>
      </condition>
    </extension>
  </context>
</include>
```

### 3. Configuration SIP Gateway

Éditer `/etc/freeswitch/sip_profiles/external/gateway1.xml` :

```xml
<include>
  <gateway name="gateway1">
    <param name="realm" value="sip.votre-provider.com"/>
    <param name="username" value="votre_username"/>
    <param name="password" value="votre_password"/>
    <param name="proxy" value="sip.votre-provider.com"/>
    <param name="register" value="true"/>
    <param name="caller-id-in-from" value="true"/>
  </gateway>
</include>
```

**Remplacez** `sip.votre-provider.com`, `username`, et `password` par vos identifiants SIP.

### 4. Redémarrer FreeSWITCH

```bash
sudo systemctl restart freeswitch

# Vérifier les logs
sudo tail -f /var/log/freeswitch/freeswitch.log

# Tester ESL
fs_cli
> status
> sofia status gateway gateway1
```

---

## 6. INSTALLATION DES MODÈLES IA

### 1. Vosk (Speech-to-Text)

```bash
# Créer le dossier models
mkdir -p models
cd models

# Télécharger le modèle français
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip

# Décompresser
unzip vosk-model-small-fr-0.22.zip
mv vosk-model-small-fr-0.22 vosk-model-fr

# Vérifier
ls -lh vosk-model-fr/
# Doit contenir : am/, conf/, graph/, ivector/

cd ..
```

**Modèles alternatifs :**
- `vosk-model-fr-0.22` : Modèle complet (1.5 GB) - meilleure précision
- `vosk-model-small-fr-0.22` : Modèle léger (40 MB) - plus rapide

### 2. Ollama (NLP - **NOUVEAU v3**)

**Installation Ollama :**

```bash
# Linux : Installation automatique
curl -fsSL https://ollama.com/install.sh | sh

# macOS : Télécharger depuis https://ollama.com/download
# Ou via Homebrew
brew install ollama

# Vérifier l'installation
ollama --version
```

**Démarrer le service Ollama :**

```bash
# Linux (systemd)
sudo systemctl start ollama
sudo systemctl enable ollama

# macOS / Linux (manual)
ollama serve &
```

**Télécharger les modèles pour Freestyle AI :**

```bash
# Option 1 : Mistral 7B (recommandé - meilleure qualité)
ollama pull mistral:7b
# Taille : ~4.1 GB
# RAM requise : 8 GB minimum

# Option 2 : Llama 3.2 1B (plus rapide, moins de RAM)
ollama pull llama3.2:1b
# Taille : ~1.3 GB
# RAM requise : 2 GB minimum

# Option 3 : Llama 3.2 3B (bon compromis)
ollama pull llama3.2:3b
# Taille : ~2 GB
# RAM requise : 4 GB minimum

# Vérifier les modèles installés
ollama list
```

**Tableau comparatif des modèles :**

| Modèle | Taille | RAM min | Qualité | Latence | Recommandation |
|--------|--------|---------|---------|---------|----------------|
| **mistral:7b** | 4.1 GB | 8 GB | ⭐⭐⭐⭐⭐ | ~1-2s | Production |
| llama3.2:3b | 2 GB | 4 GB | ⭐⭐⭐⭐ | ~0.5-1s | Équilibré |
| llama3.2:1b | 1.3 GB | 2 GB | ⭐⭐⭐ | ~0.3-0.5s | Dev/Test |

**Tester Ollama :**

```bash
# Test API
curl http://localhost:11434/api/tags

# Test de génération
ollama run mistral:7b "Bonjour, comment allez-vous ?"
```

### 3. Coqui TTS (Text-to-Speech)

```bash
# Créer le dossier cache
mkdir -p models/coqui_cache

# Les modèles se téléchargent automatiquement au premier lancement
# Taille : ~2 GB (XTTS v2 multilingual)
```

**Activation GPU (optionnel) :**

```bash
# Installer PyTorch avec CUDA
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Vérifier GPU
python -c "import torch; print(torch.cuda.is_available())"
# Sortie : True (si GPU détecté)
```

**Modèles TTS disponibles :**

```bash
# Modèle par défaut : XTTS v2 (multilingual, clonage de voix)
# Téléchargement automatique au premier usage

# Test manuel du TTS
python -c "
from TTS.api import TTS
tts = TTS('tts_models/multilingual/multi-dataset/xtts_v2')
tts.tts_to_file(text='Bonjour, je suis Julie de TechCorp.', file_path='test_tts.wav', language='fr')
print('✅ TTS test OK : test_tts.wav généré')
"
```

### 4. Vérifier toutes les installations

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Lancer le script de test
python test_services.py
```

**Sortie attendue :**

```
✅ PostgreSQL : Connected
✅ Vosk STT   : Model loaded (vosk-model-fr)
✅ Coqui TTS  : Model loaded (xtts_v2)
✅ Ollama NLP : Connected (mistral:7b)
✅ FreeSWITCH : ESL connected (127.0.0.1:8021)
✅ Objection Matcher : Loaded 153 objections
```

---

## 7. CONFIGURATION DU PROJET

### 1. Copier le fichier d'exemple

```bash
cp .env.example .env
```

### 2. Éditer le fichier `.env`

```bash
nano .env
```

**Configuration complète v3 :**

```bash
# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
DATABASE_URL=postgresql://minibot:minibot@localhost:5432/minibot_freeswitch

# ═══════════════════════════════════════════════════════════════
# FREESWITCH ESL
# ═══════════════════════════════════════════════════════════════
FREESWITCH_ESL_HOST=localhost
FREESWITCH_ESL_PORT=8021
FREESWITCH_ESL_PASSWORD=ClueCon
FREESWITCH_GATEWAY=gateway1
FREESWITCH_CALLER_ID=+33123456789  # VOTRE numéro
FREESWITCH_CONTEXT=minibot

# ═══════════════════════════════════════════════════════════════
# VOSK STT (Speech-to-Text)
# ═══════════════════════════════════════════════════════════════
VOSK_MODEL_PATH=models/vosk-model-fr
VOSK_SAMPLE_RATE=16000

# ═══════════════════════════════════════════════════════════════
# OLLAMA NLP (Freestyle AI - NOUVEAU v3)
# ═══════════════════════════════════════════════════════════════
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b
OLLAMA_TEMPERATURE=0.7
OLLAMA_MAX_TOKENS=150

# ═══════════════════════════════════════════════════════════════
# COQUI TTS (Text-to-Speech)
# ═══════════════════════════════════════════════════════════════
COQUI_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
COQUI_USE_GPU=false  # Mettre true si GPU disponible
COQUI_CACHE_DIR=models/coqui_cache

# ═══════════════════════════════════════════════════════════════
# OBJECTION MATCHING (NOUVEAU v3)
# ═══════════════════════════════════════════════════════════════
OBJECTION_MIN_SCORE=0.5
OBJECTION_USE_PRERECORDED=true
OBJECTION_FALLBACK_TO_FREESTYLE=true

# ═══════════════════════════════════════════════════════════════
# FREESTYLE AI SETTINGS (NOUVEAU v3)
# ═══════════════════════════════════════════════════════════════
FREESTYLE_MAX_TURNS=3
FREESTYLE_TIMEOUT=10
FREESTYLE_DEFAULT_PERSONALITY=professionnel

# ═══════════════════════════════════════════════════════════════
# AMD (Answering Machine Detection)
# ═══════════════════════════════════════════════════════════════
AMD_ENABLED=true
AMD_INITIAL_SILENCE=2500
AMD_GREETING_DURATION=1500
AMD_AFTER_GREETING_SILENCE=800
AMD_TOTAL_ANALYSIS_TIME=5000
AMD_MIN_WORD_LENGTH=100
AMD_BETWEEN_WORDS_SILENCE=50
AMD_MAXIMUM_NUMBER_OF_WORDS=3
AMD_MAXIMUM_WORD_LENGTH=5000

# ═══════════════════════════════════════════════════════════════
# API SECURITY
# ═══════════════════════════════════════════════════════════════
API_PASSWORD=changez_moi_en_production_12345
API_HOST=0.0.0.0
API_PORT=8000

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_ROTATION=daily
LOG_MAX_BYTES=10485760

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE
# ═══════════════════════════════════════════════════════════════
MAX_CONCURRENT_CALLS=10
CALL_QUEUE_SIZE=100
PRELOAD_MODELS=true
```

**⚠️ IMPORTANT - Paramètres à modifier :**

1. `FREESWITCH_CALLER_ID` : Remplacez par VOTRE numéro de téléphone
2. `API_PASSWORD` : Changez pour un mot de passe fort
3. `OLLAMA_MODEL` : Choisissez selon votre RAM disponible
4. `COQUI_USE_GPU` : Mettez `true` si GPU NVIDIA disponible
5. `OBJECTION_MIN_SCORE` : Seuil de confiance pour matching (0.5 = 50%)

### 3. Créer les dossiers nécessaires

```bash
mkdir -p logs/{system,campaigns,calls,services,api,errors,debug}
mkdir -p audio/generated
mkdir -p voices
mkdir -p recordings
mkdir -p transcriptions
mkdir -p exports
mkdir -p models/coqui_cache
mkdir -p scenarios  # NOUVEAU v3
```

**Structure finale :**

```
minibot_streaming/
├── audio/
│   └── generated/
├── logs/
│   ├── system/
│   ├── campaigns/
│   ├── calls/
│   ├── services/
│   ├── api/
│   ├── errors/
│   └── debug/
├── models/
│   ├── vosk-model-fr/
│   └── coqui_cache/
├── scenarios/          # ← NOUVEAU v3
├── voices/
├── recordings/
├── transcriptions/
└── exports/
```

---

## 8. INITIALISATION DE LA BASE DE DONNÉES

### 1. Créer les tables

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Lancer le script d'initialisation
python setup_database.py

# Vérifier les tables créées
python setup_database.py --check
```

**Sortie attendue :**

```
✅ Tables créées :
   - contacts (9 colonnes)
   - campaigns (15 colonnes)
   - calls (23 colonnes)
   - call_events (4 colonnes)

✅ Index créés : 12
✅ Relations : 3
```

### 2. (Optionnel) Charger des données de test

```bash
# Créer 100 contacts de test
python setup_database.py --test-data

# Vérifier
python -c "from system.database import SessionLocal; from system.models import Contact; db = SessionLocal(); print(f'Contacts: {db.query(Contact).count()}'); db.close()"
# Sortie : Contacts: 100
```

---

## 9. TESTS DE VALIDATION

### 1. Test de la base de données

```bash
python -c "
from system.database import test_connection
if test_connection():
    print('✅ PostgreSQL OK')
else:
    print('❌ PostgreSQL ERREUR')
"
```

### 2. Test ESL FreeSWITCH

```bash
python -c "
from system.robot_freeswitch import RobotFreeSWITCH
robot = RobotFreeSWITCH()
if robot.connect():
    print('✅ FreeSWITCH ESL OK')
    robot.stop()
else:
    print('❌ FreeSWITCH ESL ERREUR')
"
```

### 3. Test Ollama (Freestyle AI)

```bash
# Test connexion
curl http://localhost:11434/api/tags

# Test génération Python
python -c "
import ollama
response = ollama.chat(model='mistral:7b', messages=[
    {'role': 'user', 'content': 'Bonjour, qui êtes-vous ?'}
])
print('✅ Ollama OK')
print(f'Réponse : {response[\"message\"][\"content\"]}')
"
```

### 4. Test Objection Matcher (**NOUVEAU v3**)

```bash
python system/objection_matcher.py
```

**Sortie attendue :**

```
🧪 Test ObjectionMatcher - MiniBotPanel v3

Test 1: Match exact
  Input: 'Je n'ai pas le temps'
  Match: Je n'ai pas le temps
  Score: 1.00
  ✅ PASS

Test 2: Variante proche
  Input: 'Désolé mais j'ai vraiment pas le temps là'
  Match: Je n'ai pas le temps
  Score: 0.54
  ✅ PASS

...

✅ Tests terminés
```

### 5. Test des services IA

```bash
python test_services.py
```

### 6. Test de l'API

```bash
# Démarrer l'API
uvicorn system.api.main:app --host 0.0.0.0 --port 8000 &

# Attendre 5 secondes
sleep 5

# Tester health check
curl http://localhost:8000/health

# Sortie attendue : {"status": "healthy", "components": {...}}

# Arrêter l'API
pkill -f uvicorn
```

---

## 10. DÉMARRAGE DU SYSTÈME

### Méthode 1 : Script automatique

```bash
# Rendre le script exécutable
chmod +x start_system.sh

# Démarrer tous les services
./start_system.sh
```

**Le script démarre :**
1. PostgreSQL (si non démarré)
2. FreeSWITCH (si non démarré)
3. Ollama (si non démarré) **← NOUVEAU v3**
4. API REST (FastAPI/Uvicorn)
5. Serveur WebSocket StreamingASR
6. Batch Caller (worker de queue)

### Méthode 2 : Démarrage manuel

```bash
# 1. Activer l'environnement virtuel
source venv/bin/activate

# 2. Démarrer Ollama (si pas déjà en service)
ollama serve &
sleep 5

# 3. Démarrer l'API
uvicorn system.api.main:app --host 0.0.0.0 --port 8000 --reload &

# 4. Vérifier que l'API est lancée
curl http://localhost:8000/
# Sortie : {"name": "MiniBotPanel v3 API", "status": "running", ...}

# 5. Lancer un premier appel de test (optionnel)
python launch_campaign.py --interactive
```

### Vérification du démarrage

```bash
# Vérifier les processus
ps aux | grep -E "(uvicorn|python|freeswitch|ollama)"

# Vérifier les ports
sudo netstat -tulpn | grep -E "(8000|8021|8080|11434|5432)"

# Sortie attendue :
# 8000 : API FastAPI
# 8021 : FreeSWITCH ESL
# 8080 : StreamingASR WebSocket
# 11434 : Ollama (NOUVEAU v3)
# 5432 : PostgreSQL
```

### Arrêter le système

```bash
./stop_system.sh
```

---

## 11. CONFIGURATION FREESTYLE AI

### 1. Créer un scénario avec Freestyle

```bash
# Mode interactif
python create_scenario.py --interactive
```

**Workflow de création :**

1. **Choisir la thématique** (Finance, Crypto, Immobilier, Or, Vin, etc.)
2. **Choisir l'objectif de campagne** :
   - Prise de RDV
   - Génération de lead
   - Transfert d'appel
3. **Choisir la personnalité de l'agent** :
   - Professionnel
   - Doux
   - Dynamique
   - Assertif
   - Expert
   - Commercial
   - Consultative
4. **Configurer les étapes** avec option `audio_type: "freestyle"`

**Exemple de step Freestyle :**

```json
{
  "freestyle_answer": {
    "audio_type": "freestyle",
    "voice": "julie",
    "barge_in": true,
    "timeout": 10,
    "max_turns": 3,
    "context": {
      "agent_name": "Julie",
      "company": "TechCorp",
      "product": "solution d'automatisation",
      "campaign_context": "Prospection B2B",
      "campaign_objective": "L'objectif est d'obtenir un rendez-vous",
      "agent_tone": "professionnel, courtois, posé, crédible",
      "agent_style": "Phrases claires et structurées. Vouvoiement. Arguments factuels."
    },
    "intent_mapping": {
      "affirm": "question1",
      "question": "freestyle_answer",
      "deny": "objection",
      "*": "question1"
    }
  }
}
```

### 2. Tester le Freestyle AI

```bash
# Test unitaire du prompt system
python -c "
from system.robot_freeswitch import RobotFreeSWITCH
robot = RobotFreeSWITCH()

context = {
    'agent_name': 'Julie',
    'company': 'TechCorp',
    'product': 'solution IA',
    'campaign_objective': 'Prise de RDV',
    'agent_tone': 'professionnel, courtois',
    'agent_style': 'Phrases courtes. Vouvoiement.'
}

response = robot._generate_freestyle_response(
    user_input='Je ne suis pas sûr...',
    context=context
)

print(f'✅ Freestyle response: {response}')
"
```

### 3. Charger un scénario existant

```bash
# Lister les scénarios disponibles
ls -lh scenarios/scenario_*.json

# Utiliser un scénario dans une campagne
python launch_campaign.py --interactive
# Sélectionnez le scénario dans le menu
```

### 4. Ajuster les paramètres Freestyle

**Dans `.env` :**

```bash
# Température (créativité) : 0.0 = strict, 1.0 = créatif
OLLAMA_TEMPERATURE=0.7

# Nombre max de tokens par réponse
OLLAMA_MAX_TOKENS=150

# Nombre max de tours Freestyle avant fallback
FREESTYLE_MAX_TURNS=3

# Timeout pour génération (secondes)
FREESTYLE_TIMEOUT=10
```

**Recommandations :**

| Cas d'usage | TEMPERATURE | MAX_TOKENS | MAX_TURNS |
|-------------|-------------|------------|-----------|
| Strict (script) | 0.3 | 100 | 2 |
| Équilibré | 0.7 | 150 | 3 |
| Créatif | 0.9 | 200 | 5 |

---

## 12. TROUBLESHOOTING

### Problème : PostgreSQL ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u postgresql -n 50

# Réinitialiser le cluster
sudo pg_dropcluster 14 main --stop
sudo pg_createcluster 14 main --start
```

### Problème : FreeSWITCH ESL connection refused

```bash
# Vérifier que FreeSWITCH écoute sur 8021
sudo netstat -tulpn | grep 8021

# Si vide, vérifier la config ESL
sudo nano /etc/freeswitch/autoload_configs/event_socket.conf.xml

# Redémarrer FreeSWITCH
sudo systemctl restart freeswitch
```

### Problème : Vosk model not found

```bash
# Vérifier le chemin
ls -la models/vosk-model-fr/

# Si vide, re-télécharger
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
unzip vosk-model-small-fr-0.22.zip
mv vosk-model-small-fr-0.22 vosk-model-fr
cd ..
```

### Problème : Ollama not available (**NOUVEAU v3**)

```bash
# Vérifier le service
curl http://localhost:11434/api/tags

# Si erreur, redémarrer Ollama
pkill ollama
ollama serve &
sleep 5
ollama pull mistral:7b

# Vérifier les logs Ollama
journalctl -u ollama -f
```

### Problème : Ollama out of memory

```bash
# Vérifier la RAM disponible
free -h

# Utiliser un modèle plus léger
ollama pull llama3.2:1b

# Dans .env :
OLLAMA_MODEL=llama3.2:1b

# Ou limiter le contexte
OLLAMA_MAX_TOKENS=100
```

### Problème : Coqui TTS fails to load

```bash
# Vérifier la RAM disponible
free -h

# Si < 4GB, utiliser CPU uniquement
# Dans .env :
COQUI_USE_GPU=false

# Réinstaller TTS
pip uninstall TTS
pip install coqui-tts==0.27.2

# Vider le cache
rm -rf models/coqui_cache/*
```

### Problème : Objection Matcher ne trouve aucun match (**NOUVEAU v3**)

```bash
# Vérifier le score minimum
# Dans .env :
OBJECTION_MIN_SCORE=0.4  # Baisser de 0.5 à 0.4

# Tester manuellement
python -c "
from system.objections_database import ALL_OBJECTIONS
from system.objection_matcher import ObjectionMatcher

matcher = ObjectionMatcher(ALL_OBJECTIONS['standard'])
result = matcher.find_best_match('Ça coûte trop cher', min_score=0.4)
print(result)
"
```

### Problème : Freestyle répond lentement

```bash
# 1. Vérifier le modèle utilisé
ollama list

# 2. Utiliser un modèle plus rapide
ollama pull llama3.2:1b
# Dans .env : OLLAMA_MODEL=llama3.2:1b

# 3. Réduire le nombre de tokens
# Dans .env : OLLAMA_MAX_TOKENS=80

# 4. Vérifier CPU/RAM
top
htop
```

### Problème : API 401 Unauthorized

```bash
# Vérifier que vous passez le mot de passe
curl http://localhost:8000/api/campaigns \
  -H "X-API-Key: changez_moi_en_production_12345"

# Ou via query param
curl http://localhost:8000/api/campaigns?password=changez_moi_en_production_12345
```

### Problème : Calls not originating

```bash
# Vérifier les logs FreeSWITCH
sudo tail -f /var/log/freeswitch/freeswitch.log | grep -i originate

# Vérifier la gateway SIP
fs_cli -x "sofia status gateway gateway1"

# Si DOWN, vérifier les credentials SIP
sudo nano /etc/freeswitch/sip_profiles/external/gateway1.xml
```

### Problème : Out of memory

```bash
# Vérifier l'utilisation mémoire
free -h
top

# Solutions :
# 1. Utiliser Llama 3.2 1B au lieu de Mistral 7B
ollama pull llama3.2:1b
# Dans .env : OLLAMA_MODEL=llama3.2:1b

# 2. Désactiver le preloading des modèles
# Dans .env :
PRELOAD_MODELS=false
COQUI_USE_GPU=false

# 3. Réduire le nombre d'appels simultanés
# Dans .env :
MAX_CONCURRENT_CALLS=5

# 4. Limiter Ollama
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
```

### Problème : Scénarios not found (**NOUVEAU v3**)

```bash
# Vérifier le dossier scenarios
ls -lh scenarios/

# Créer un scénario de test
python create_scenario.py --interactive

# Vérifier la création
ls -lh scenarios/scenario_*.json

# Lister via launch_campaign
python launch_campaign.py --interactive
```

### Problème : python-ESL import error (macOS)

```bash
# Vérifier si ESL.py est présent
ls $VIRTUAL_ENV/lib/python3.11/site-packages/ESL.py

# Si absent, copier depuis FreeSWITCH
cp /usr/local/freeswitch/share/freeswitch/scripts/ESL.py \
   $VIRTUAL_ENV/lib/python3.11/site-packages/

# Ou compiler depuis sources
cd /usr/local/src/freeswitch/libs/esl
make pymod
cp ESL.py $VIRTUAL_ENV/lib/python3.11/site-packages/
```

---

## 🎉 INSTALLATION TERMINÉE !

Vous pouvez maintenant :

1. **Importer des contacts** :
   ```bash
   python import_contacts.py --source contacts.csv
   ```

2. **Créer un scénario** (avec Freestyle AI) :
   ```bash
   python create_scenario.py --interactive
   ```

3. **Lancer une campagne** :
   ```bash
   python launch_campaign.py --interactive
   ```

4. **Monitorer en temps réel** :
   ```bash
   python monitor_campaign.py --campaign-id 1
   ```

5. **Exporter les résultats** :
   ```bash
   python export_campaign.py --campaign-id 1
   ```

---

## 📚 PROCHAINES ÉTAPES

- Consulter le **GUIDE_UTILISATION.md** pour apprendre à utiliser le système
- Consulter le **BRIEF_PROJET.md** pour comprendre l'architecture
- Consulter le **README.md** pour une vue d'ensemble des nouveautés v3

### Nouveautés v3 à explorer :

✅ **Freestyle AI** : Réponses générées dynamiquement par Ollama
✅ **Objection Matching** : Détection rapide avec fuzzy matching
✅ **7 Personnalités d'agent** : Professionnel, Doux, Dynamique, etc.
✅ **9 Thématiques métier** : Finance, Crypto, Immobilier, Or, Vin, etc.
✅ **3 Objectifs de campagne** : RDV, Lead, Transfert d'appel
✅ **Scenarios Manager** : Gestion centralisée dans `scenarios/`

**Support :** Consultez les logs dans `logs/` pour diagnostiquer les problèmes.

---

**Version du guide** : v3.0.0
**Dernière mise à jour** : 2025-01-29
