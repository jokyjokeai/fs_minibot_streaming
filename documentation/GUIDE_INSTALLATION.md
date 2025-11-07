# 📦 GUIDE D'INSTALLATION COMPLET - MiniBotPanel v3 Streaming

Guide d'installation complète du système de robot d'appels conversationnels avec FreeSWITCH, streaming audio temps réel, reconnaissance vocale Vosk et détection d'intentions Ollama.

---

## 📋 TABLE DES MATIÈRES

1. [Prérequis Système](#1-prérequis-système)
2. [Préparation du Système](#2-préparation-du-système)
3. [Installation PostgreSQL](#3-installation-postgresql)
4. [Installation Python & Environnement Virtuel](#4-installation-python--environnement-virtuel)
5. [Compilation FreeSWITCH depuis les Sources](#5-compilation-freeswitch-depuis-les-sources)
6. [Installation mod_audio_stream (Streaming Temps Réel)](#6-installation-mod_audio_stream-streaming-temps-réel)
7. [Configuration FreeSWITCH](#7-configuration-freeswitch)
8. [Installation des Modèles IA](#8-installation-des-modèles-ia)
9. [Configuration du Projet](#9-configuration-du-projet)
10. [Initialisation de la Base de Données](#10-initialisation-de-la-base-de-données)
11. [Tests de Validation](#11-tests-de-validation)
12. [Démarrage du Système](#12-démarrage-du-système)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. PRÉREQUIS SYSTÈME

### Matériel Minimum

| Composant | Minimum | Recommandé | Pour Production |
|-----------|---------|------------|-----------------|
| CPU | 2 cores | 4+ cores | 8+ cores |
| RAM | 4 GB | 8 GB | **12 GB** (Vosk + Ollama) |
| Disque | 20 GB | 50 GB SSD | 100 GB SSD |
| Réseau | 10 Mbps | 100 Mbps | 1 Gbps (streaming audio) |

**⚠️ Note Streaming Audio** : Le mode streaming temps réel nécessite une latence réseau faible (<50ms) et une bande passante stable.

### Système d'exploitation

**Linux (recommandé) :**
- Ubuntu 20.04 LTS / 22.04 LTS / 24.04 LTS ✅
- Debian 11 / 12
- Rocky Linux 8 / 9

**macOS :**
- macOS 12+ (Monterey ou supérieur)
- **Note :** python-ESL et mod_audio_stream nécessitent compilation manuelle

**Windows :**
- Non supporté officiellement (utiliser WSL2)

### Logiciels requis

```bash
# Ubuntu/Debian
- Python 3.11+
- PostgreSQL 14+
- FreeSWITCH 1.10+ (compilation sources)
- Git, Build essentials, CMake
- libwebsockets-dev (pour mod_audio_stream)
- ffmpeg
- Ollama (pour détection d'intentions NLP)
```

---

## 2. PRÉPARATION DU SYSTÈME

### 2.1 Mise à jour du système

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Installation des outils de base

```bash
sudo apt install -y \
  git curl wget vim nano \
  build-essential software-properties-common \
  cmake pkg-config
```

### 2.3 Vérifier version Ubuntu

```bash
lsb_release -a
# Devrait afficher: Ubuntu 22.04 LTS (ou 20.04/24.04)
```

### 2.4 Cloner le projet

```bash
cd /opt
sudo git clone https://github.com/votre-org/fs_minibot_streaming.git
cd fs_minibot_streaming
sudo chown -R $USER:$USER .
```

---

## 3. INSTALLATION POSTGRESQL

### 3.1 Installation

```bash
# Ubuntu/Debian
sudo apt install -y postgresql postgresql-contrib

# Ou installer version spécifique (14+)
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-14 postgresql-contrib-14
```

### 3.2 Démarrer le service

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo systemctl status postgresql
```

### 3.3 Créer utilisateur et base de données

```bash
# Méthode 1 : Via sudo -u postgres
sudo -u postgres psql <<EOF
CREATE USER minibot WITH PASSWORD 'minibot';
CREATE DATABASE minibot_freeswitch OWNER minibot;
GRANT ALL PRIVILEGES ON DATABASE minibot_freeswitch TO minibot;
EOF

# Méthode 2 : En une ligne
sudo -u postgres psql -c "CREATE USER minibot WITH PASSWORD 'minibot';"
sudo -u postgres psql -c "CREATE DATABASE minibot_freeswitch OWNER minibot;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE minibot_freeswitch TO minibot;"
```

### 3.4 Tester connexion

```bash
psql -U minibot -d minibot_freeswitch -h localhost -c "SELECT version();"
# Mot de passe: minibot
```

**⚠️ PRODUCTION** : Changez le mot de passe `minibot` pour un mot de passe fort !

---

## 4. INSTALLATION PYTHON & ENVIRONNEMENT VIRTUEL

### 4.1 Installer Python 3.11+

```bash
# Ubuntu 22.04 : Python 3.10 par défaut (compatible)
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Ubuntu 20.04 : Ajouter PPA pour Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Vérifier version
python3 --version
```

### 4.2 Créer environnement virtuel

```bash
cd /opt/fs_minibot_streaming
python3 -m venv venv
source venv/bin/activate

# Vérifier
python --version
pip --version
```

### 4.3 Installer dépendances Python

```bash
# Mettre à jour pip
pip install --upgrade pip setuptools wheel

# Installer dépendances
pip install -r requirements.txt
```

**⚠️ Note** : Si `python-esl` échoue à s'installer via pip, nous le compilerons manuellement plus tard (section 5.8).

### 4.4 Installer ffmpeg

```bash
sudo apt install -y ffmpeg

# Vérifier
ffmpeg -version
```

---

## 5. COMPILATION FREESWITCH DEPUIS LES SOURCES

### 5.1 Installer dépendances de compilation

```bash
sudo apt install -y \
  autoconf automake devscripts gawk g++ git-core \
  libjpeg-dev libncurses5-dev libtool libtool-bin make python3-dev \
  libtiff-dev libperl-dev libgdbm-dev libdb-dev gettext \
  libssl-dev libcurl4-openssl-dev libpcre3-dev \
  libspeex-dev libspeexdsp-dev libsqlite3-dev libedit-dev \
  libldns-dev libpq-dev yasm nasm libx264-dev \
  libavformat-dev libswscale-dev libopus-dev \
  libsndfile1-dev uuid-dev swig
```

### 5.2 Compiler sofia-sip (dépendance requise)

```bash
cd /usr/local/src
sudo git clone https://github.com/freeswitch/sofia-sip.git
cd sofia-sip
sudo ./bootstrap.sh
sudo ./configure
sudo make -j$(nproc)
sudo make install
sudo ldconfig

# Vérifier installation
ldconfig -p | grep sofia
# Devrait afficher: libsofia-sip-ua.so
```

### 5.3 Compiler spandsp (dépendance requise)

```bash
cd /usr/local/src
sudo git clone https://github.com/freeswitch/spandsp.git
cd spandsp
sudo ./bootstrap.sh
sudo ./configure
sudo make -j$(nproc)
sudo make install
sudo ldconfig
```

### 5.4 Cloner FreeSWITCH 1.10

```bash
cd /usr/src
sudo git clone https://github.com/signalwire/freeswitch.git -b v1.10 freeswitch
cd freeswitch
sudo ./bootstrap.sh -j
```

### 5.5 Configurer modules

Désactiver modules non nécessaires ou problématiques :

```bash
cd /usr/src/freeswitch

# Désactiver mod_verto et mod_signalwire (requièrent libks)
sudo sed -i 's/^endpoints\/mod_verto/#endpoints\/mod_verto/' modules.conf
sudo sed -i 's/^applications\/mod_signalwire/#applications\/mod_signalwire/' modules.conf

# Désactiver mod_lua (optionnel)
sudo sed -i 's/^languages\/mod_lua/#languages\/mod_lua/' modules.conf

# Vérifier
grep -E '^#(endpoints/mod_verto|applications/mod_signalwire)' modules.conf
```

### 5.6 Configuration et compilation

```bash
cd /usr/src/freeswitch

# Configuration
sudo ./configure --prefix=/usr/local/freeswitch

# Compilation (15-30 minutes)
sudo make -j$(nproc)

# Installation
sudo make install

# Installer fichiers audio
sudo make cd-sounds-install cd-moh-install
```

### 5.7 Configuration post-installation

```bash
# Créer utilisateur freeswitch
sudo adduser --disabled-password --quiet --system \
  --home /usr/local/freeswitch \
  --gecos "FreeSWITCH" \
  --ingroup daemon freeswitch

# Fixer permissions
sudo chown -R freeswitch:daemon /usr/local/freeswitch

# Créer service systemd
sudo tee /etc/systemd/system/freeswitch.service > /dev/null <<EOF
[Unit]
Description=FreeSWITCH
After=network.target

[Service]
Type=forking
PIDFile=/usr/local/freeswitch/var/run/freeswitch/freeswitch.pid
User=freeswitch
Group=daemon
ExecStart=/usr/local/freeswitch/bin/freeswitch -nc -nonat
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Activer et démarrer
sudo systemctl daemon-reload
sudo systemctl enable freeswitch
sudo systemctl start freeswitch
sudo systemctl status freeswitch
```

### 5.8 Compiler python-esl manuellement

```bash
# Aller dans le dossier ESL
cd /usr/src/freeswitch/libs/esl

# Retirer flag -classic obsolète (swig 4.x)
sudo sed -i 's/-classic //' python3/Makefile

# Compiler librairie ESL
sudo make

# Générer wrapper SWIG pour Python
sudo swig -module ESL -python -c++ -DMULTIPLICITY -threads \
  -I./src/include -o python3/esl_wrap.cpp ESL.i

# Compiler module Python
cd python3
sudo g++ -fPIC -shared \
  $(python3-config --includes) \
  $(python3-config --ldflags) \
  -I../src/include \
  esl_wrap.cpp ../.libs/libesl.a \
  -o _ESL.so

# Vérifier création
ls -la _ESL.so

# Copier dans venv
sudo cp _ESL.so ESL.py /opt/fs_minibot_streaming/venv/lib/python3.*/site-packages/

# Tester
cd /opt/fs_minibot_streaming
source venv/bin/activate
python -c "import ESL; print('✅ python-esl OK')"
```

---

## 6. INSTALLATION MOD_AUDIO_STREAM (STREAMING TEMPS RÉEL)

**⚠️ MODULE CRITIQUE** : mod_audio_stream permet le streaming audio temps réel vers WebSocket pour la transcription instantanée avec Vosk.

### 6.1 Prérequis

```bash
# Installer libwebsockets-dev
sudo apt install -y libwebsockets-dev cmake git

# Vérifier installation
dpkg -l | grep libwebsockets-dev
```

### 6.2 Cloner le repository

```bash
cd /usr/local/src
sudo git clone https://github.com/davehorner/mod_audio_stream.git
cd mod_audio_stream
sudo git submodule update --init --recursive
```

**Note** : Nous utilisons le repository `davehorner/mod_audio_stream` qui est compatible avec FreeSWITCH 1.10.

### 6.3 Configuration PKG_CONFIG_PATH

```bash
# Configurer path vers FreeSWITCH
export PKG_CONFIG_PATH=/usr/local/freeswitch/lib/pkgconfig:$PKG_CONFIG_PATH

# Vérifier
pkg-config --cflags --libs freeswitch
```

### 6.4 Compilation

```bash
cd /usr/local/src/mod_audio_stream
sudo mkdir build
cd build

# Configuration CMake
sudo cmake ..

# Compilation
sudo make

# Vérifier création
ls -la mod_audio_stream.so
```

### 6.5 Installation du module

```bash
# Copier vers répertoire modules FreeSWITCH
sudo cp mod_audio_stream.so /usr/local/freeswitch/lib/freeswitch/mod/

# Définir propriétaire et permissions
sudo chown freeswitch:daemon /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so
sudo chmod 755 /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so

# Vérifier
ls -la /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so
```

**Sortie attendue** :
```
-rwxr-xr-x 1 freeswitch daemon 123456 Nov  7 10:00 mod_audio_stream.so
```

### 6.6 Charger le module dans FreeSWITCH

```bash
# Éditer modules.conf.xml
sudo nano /usr/local/freeswitch/conf/vanilla/autoload_configs/modules.conf.xml
```

Ajouter **avant** `</modules>` :

```xml
    <!-- Streaming Audio Module -->
    <load module="mod_audio_stream"/>
  </modules>
</configuration>
```

**Ou automatiquement** :

```bash
sudo sed -i 's|</modules>|  <load module="mod_audio_stream"/>\n  </modules>|' \
  /usr/local/freeswitch/conf/vanilla/autoload_configs/modules.conf.xml
```

### 6.7 Redémarrer FreeSWITCH

```bash
sudo systemctl restart freeswitch

# Attendre 5 secondes
sleep 5

# Vérifier chargement
/usr/local/freeswitch/bin/fs_cli -x "module_exists mod_audio_stream"
```

**Sortie attendue** : `true`

### 6.8 Tester le module

```bash
/usr/local/freeswitch/bin/fs_cli -x "uuid_audio_stream help"
```

**Sortie attendue** :
```
USAGE:
  uuid_audio_stream <uuid> start <ws-url> [mono|mixed|stereo]
  uuid_audio_stream <uuid> stop
```

**✅ mod_audio_stream installé avec succès !**

---

## 7. CONFIGURATION FREESWITCH

### 7.1 Installer configuration vanilla de base

```bash
# Arrêter FreeSWITCH
sudo systemctl stop freeswitch

# Installer config vanilla
cd /usr/src/freeswitch
sudo make samples

# Vérifier installation
ls -la /usr/local/freeswitch/conf/vanilla/

# Fixer permissions
sudo chown -R freeswitch:daemon /usr/local/freeswitch/

# Redémarrer
sudo systemctl start freeswitch
```

### 7.2 Configuration Event Socket Layer (ESL)

Éditer `/usr/local/freeswitch/conf/vanilla/autoload_configs/event_socket.conf.xml` :

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

### 7.3 Configuration du dialplan

Créer `/usr/local/freeswitch/conf/vanilla/dialplan/minibot_outbound.xml` :

```xml
<?xml version="1.0" encoding="utf-8"?>
<include>
  <context name="minibot">
    <extension name="outbound_calls">
      <condition field="destination_number" expression="^(.+)$">
        <action application="set" data="continue_on_fail=true"/>
        <action application="set" data="hangup_after_bridge=false"/>
        <action application="answer"/>
        <action application="sleep" data="100"/>
        <action application="park"/>
      </condition>
    </extension>
  </context>
</include>
```

### 7.4 Configuration SIP Gateway

Créer `/usr/local/freeswitch/conf/vanilla/sip_profiles/external/gateway1.xml` :

```xml
<include>
  <gateway name="gateway1">
    <!-- Provider SIP -->
    <param name="proxy" value="188.34.143.144"/>
    <param name="realm" value="188.34.143.144"/>

    <!-- Authentification -->
    <param name="username" value="votre_username"/>
    <param name="password" value="votre_password"/>

    <!-- Registration -->
    <param name="register" value="true"/>
    <param name="retry-seconds" value="30"/>
    <param name="expire-seconds" value="3600"/>

    <!-- Caller ID -->
    <param name="caller-id-in-from" value="true"/>
    <param name="extension-in-contact" value="true"/>

    <!-- Context pour appels entrants -->
    <param name="context" value="public"/>

    <!-- Codec preferences -->
    <param name="codec-prefs" value="PCMU,PCMA"/>

    <!-- Variables -->
    <variables>
      <variable name="outbound_caller_id_number" value="votre_username"/>
      <variable name="outbound_caller_id_name" value="MiniBotPanel"/>
    </variables>
  </gateway>
</include>
```

**Remplacez** :
- `188.34.143.144` : IP/domaine de votre provider SIP
- `votre_username` : Votre username SIP
- `votre_password` : Votre mot de passe SIP

### 7.5 Redémarrer et vérifier

```bash
# Redémarrer FreeSWITCH
sudo systemctl restart freeswitch

# Vérifier ESL
/usr/local/freeswitch/bin/fs_cli -H localhost -P 8021 -p ClueCon -x "status"

# Vérifier gateway SIP
/usr/local/freeswitch/bin/fs_cli -x "sofia status gateway gateway1"
```

**Sortie attendue gateway** :
```
Name: gateway1
State: REGED
```

Si `NOREG` ou `FAIL_WAIT`, vérifier credentials SIP.

### 7.6 Test appel sortant

```bash
# Tester un appel (remplacer par un vrai numéro)
/usr/local/freeswitch/bin/fs_cli -x "originate sofia/gateway/gateway1/+33612345678 &park()"

# Raccrocher tous les appels
/usr/local/freeswitch/bin/fs_cli -x "hupall"
```

---

## 8. INSTALLATION DES MODÈLES IA

### 8.1 Vosk STT (Speech-to-Text) - Français

```bash
cd /opt/fs_minibot_streaming
mkdir -p models
cd models

# Télécharger modèle français léger
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip

# Décompresser
unzip vosk-model-small-fr-0.22.zip
rm vosk-model-small-fr-0.22.zip

# Vérifier
ls -lh vosk-model-small-fr-0.22/
# Doit contenir : am/, conf/, graph/, ivector/

cd ..
```

**Modèles alternatifs** :
- `vosk-model-fr-0.22` : Modèle complet (1.5 GB) - meilleure précision
- `vosk-model-small-fr-0.22` : Modèle léger (40 MB) - plus rapide ✅

### 8.2 Ollama NLP (Détection d'Intentions)

Ollama est utilisé pour la **détection d'intentions uniquement** (affirm/deny/question/objection), pas pour la génération de texte.

```bash
# Installer Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Vérifier installation
ollama --version

# Démarrer le service
sudo systemctl start ollama
sudo systemctl enable ollama

# Ou manuellement
ollama serve &
```

**Télécharger modèle** :

```bash
# Option 1 : Mistral 7B (recommandé - meilleure précision intent)
ollama pull mistral:7b
# Taille : ~4.1 GB
# RAM requise : 8 GB minimum

# Option 2 : Llama 3.2 3B (bon compromis)
ollama pull llama3.2:3b
# Taille : ~2 GB
# RAM requise : 4 GB minimum

# Option 3 : Llama 3.2 1B (rapide, moins de RAM)
ollama pull llama3.2:1b
# Taille : ~1.3 GB
# RAM requise : 2 GB minimum

# Vérifier
ollama list
```

**Tester Ollama** :

```bash
# Test API
curl http://localhost:11434/api/tags

# Test génération
ollama run mistral:7b "Bonjour, comment allez-vous ?"
```

**Note importante** : Ollama n'est utilisé que pour détecter les intentions (affirm, deny, question, objection) à partir des transcriptions Vosk. Il ne génère PAS de réponses textuelles.

---

## 9. CONFIGURATION DU PROJET

### 9.1 Créer fichier .env

```bash
cd /opt/fs_minibot_streaming
cp .env.example .env
nano .env
```

### 9.2 Configuration complète

**Éditer `.env` avec vos paramètres** :

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
FREESWITCH_CALLER_ID=+33123456789  # À MODIFIER
FREESWITCH_CONTEXT=minibot

# Répertoire des sons (fichiers audio traités)
FREESWITCH_SOUNDS_DIR=/usr/share/freeswitch/sounds/minibot

# ═══════════════════════════════════════════════════════════════
# AUDIO
# ═══════════════════════════════════════════════════════════════
# Répertoire source des audios (avant traitement)
AUDIO_DIR=audio

# Voix par défaut
DEFAULT_VOICE=julie

# Ajustement volume (dB) - Appliqué par setup_audio.py
AUDIO_VOLUME_ADJUST=2.0

# Réduction bruit de fond (dB)
AUDIO_BACKGROUND_REDUCTION=-10.0

# ═══════════════════════════════════════════════════════════════
# VOSK STT (Speech-to-Text)
# ═══════════════════════════════════════════════════════════════
VOSK_MODEL_PATH=models/vosk-model-small-fr-0.22
VOSK_SAMPLE_RATE=16000

# ═══════════════════════════════════════════════════════════════
# OLLAMA NLP (Intent Detection UNIQUEMENT)
# ═══════════════════════════════════════════════════════════════
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b
OLLAMA_TEMPERATURE=0.7
OLLAMA_MAX_TOKENS=150
OLLAMA_TIMEOUT=10

# ═══════════════════════════════════════════════════════════════
# STREAMING ASR (WebSocket Server)
# ═══════════════════════════════════════════════════════════════
STREAMING_ASR_PORT=8080

# Seuil silence pour fin de parole (secondes)
SILENCE_THRESHOLD=1.5

# Seuil début de parole (secondes)
SPEECH_START_THRESHOLD=0.5

# ═══════════════════════════════════════════════════════════════
# BARGE-IN (Interruption)
# ═══════════════════════════════════════════════════════════════
# Grace period anti-faux-positifs (secondes)
BARGE_IN_GRACE_PERIOD=3.0

# ═══════════════════════════════════════════════════════════════
# TIMEOUTS
# ═══════════════════════════════════════════════════════════════
# Timeout écoute réponse prospect (secondes)
LISTEN_TIMEOUT=4

# Timeout connexion (secondes)
CONNECTION_TIMEOUT=30

# ═══════════════════════════════════════════════════════════════
# OBJECTION MATCHING
# ═══════════════════════════════════════════════════════════════
OBJECTION_MIN_SCORE=0.5
OBJECTION_USE_PRERECORDED=true

# ═══════════════════════════════════════════════════════════════
# AMD (Answering Machine Detection)
# ═══════════════════════════════════════════════════════════════
AMD_ENABLED=true
AMD_METHOD=freeswitch
AMD_MAX_GREETING_MS=4000
AMD_SILENCE_THRESHOLD_MS=1000

# ═══════════════════════════════════════════════════════════════
# APPELS
# ═══════════════════════════════════════════════════════════════
# Nombre max d'appels simultanés
MAX_CONCURRENT_CALLS=10

# Délai entre appels (secondes)
CALL_DELAY=2

# Durée max d'un appel (secondes)
MAX_CALL_DURATION=300

# ═══════════════════════════════════════════════════════════════
# RETRY (Rappel automatique)
# ═══════════════════════════════════════════════════════════════
# Activer retry
RETRY_ENABLED=true

# Max tentatives
MAX_RETRY_ATTEMPTS=3

# Délai entre tentatives (secondes)
RETRY_DELAY=3600  # 1 heure

# Conditions de retry (séparées par virgule)
RETRY_CONDITIONS=no_answer,busy,timeout

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════
LOG_LEVEL=INFO
LOG_DIR=logs
```

**⚠️ Paramètres à modifier obligatoirement** :
1. `FREESWITCH_CALLER_ID` : Votre numéro de téléphone
2. `OLLAMA_MODEL` : Selon votre RAM disponible

### 9.3 Créer structure de dossiers

```bash
cd /opt/fs_minibot_streaming

mkdir -p logs
mkdir -p audio/julie/base
mkdir -p audio/julie/objections
mkdir -p recordings
mkdir -p transcriptions
mkdir -p exports
mkdir -p scenarios

# Fixer permissions
chmod -R 755 .
```

---

## 10. INITIALISATION DE LA BASE DE DONNÉES

### 10.1 Créer les tables

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

python setup_database.py
```

**Sortie attendue** :
```
✅ Database connection OK
✅ Tables créées avec succès
Contacts: 0
Campagnes: 0
✅ Setup base de données terminé!
```

### 10.2 (Optionnel) Charger données de test

```bash
python setup_database.py --test-data

# Vérifier
python -c "from system.database import SessionLocal; from system.models import Contact; db = SessionLocal(); print(f'Contacts: {db.query(Contact).count()}'); db.close()"
```

---

## 11. TESTS DE VALIDATION

### 11.1 Test services Python

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

python test_services.py
```

**Sortie attendue** :
```
✅ PostgreSQL : Connected
✅ Vosk STT   : Model loaded (vosk-model-small-fr-0.22)
✅ Ollama NLP : Connected (mistral:7b)
✅ FreeSWITCH : ESL connected (127.0.0.1:8021)
✅ StreamingASR : WebSocket server ready (port 8080)
```

### 11.2 Test appel complet

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

python test_call.py
```

Ceci lance un appel de test vers le numéro configuré.

**Surveiller les logs** :
```bash
# Terminal 2
tail -f logs/system/robot_freeswitch_v2.log
```

**Logs attendus** :
```
✅ Audio streaming started to WebSocket (16kHz mono)
📞 New audio stream for call: e5ce51fb
🗣️ Speech START detected
📝 FINAL transcription: 'bonjour'
Intent: affirm
```

---

## 12. DÉMARRAGE DU SYSTÈME

### 12.1 Lancer le robot FreeSWITCH

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Lancer le robot en background
nohup python system/robot_freeswitch_v2.py > logs/robot.log 2>&1 &

# Vérifier
ps aux | grep robot_freeswitch_v2
```

### 12.2 Vérifier démarrage

```bash
# Vérifier processus
ps aux | grep -E "(ollama|freeswitch|postgres)"

# Vérifier ports
sudo netstat -tulpn | grep -E "(8021|8080|11434|5432)"
```

**Ports attendus** :
- `8021` : FreeSWITCH ESL
- `8080` : StreamingASR WebSocket
- `11434` : Ollama
- `5432` : PostgreSQL

### 12.3 Monitorer les logs

```bash
# Logs robot
tail -f logs/system/robot_freeswitch_v2.log

# Logs streaming ASR
tail -f logs/streaming_asr.log

# Logs FreeSWITCH
tail -f /usr/local/freeswitch/var/log/freeswitch/freeswitch.log
```

---

## 13. TROUBLESHOOTING

### Problème : mod_audio_stream not found

```bash
# Vérifier présence
ls -la /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so

# Vérifier chargement
/usr/local/freeswitch/bin/fs_cli -x "module_exists mod_audio_stream"

# Recharger module
/usr/local/freeswitch/bin/fs_cli -x "reload mod_audio_stream"
```

### Problème : WebSocket connection refused (port 8080)

```bash
# Vérifier si WebSocket server actif
netstat -tlnp | grep 8080

# Vérifier logs StreamingASR
tail -f logs/streaming_asr.log

# Tester manuellement
python -c "import websockets; print(websockets.__version__)"
```

### Problème : Pas de transcription en mode streaming

**Causes possibles** :
1. StreamingASR server pas démarré
2. mod_audio_stream pas chargé
3. Format audio incompatible

**Diagnostic** :
```bash
# Vérifier dans logs robot_freeswitch
grep "Audio streaming started" logs/system/robot_freeswitch_v2.log

# Vérifier dans logs streaming_asr
grep "New audio stream" logs/streaming_asr.log

# Tester manuellement uuid_audio_stream
/usr/local/freeswitch/bin/fs_cli -x "uuid_audio_stream help"
```

### Problème : FreeSWITCH ESL connection refused

```bash
# Vérifier que FreeSWITCH écoute sur 8021
sudo netstat -tulpn | grep 8021

# Vérifier config ESL
sudo nano /usr/local/freeswitch/conf/vanilla/autoload_configs/event_socket.conf.xml

# Redémarrer FreeSWITCH
sudo systemctl restart freeswitch
```

### Problème : Ollama not available

```bash
# Vérifier service
curl http://localhost:11434/api/tags

# Redémarrer Ollama
sudo systemctl restart ollama

# Ou manuellement
pkill ollama
ollama serve &
sleep 5
ollama pull mistral:7b
```

### Problème : Out of memory

```bash
# Vérifier RAM
free -h

# Solutions :
# 1. Utiliser modèle plus léger
ollama pull llama3.2:1b
# Dans .env : OLLAMA_MODEL=llama3.2:1b

# 2. Limiter appels concurrents
# Dans .env : MAX_CONCURRENT_CALLS=5
```

### Problème : Gateway SIP NOREG

```bash
# Vérifier credentials
/usr/local/freeswitch/bin/fs_cli -x "sofia status gateway gateway1"

# Vérifier logs
tail -f /usr/local/freeswitch/var/log/freeswitch/freeswitch.log | grep gateway1

# Vérifier config
sudo nano /usr/local/freeswitch/conf/vanilla/sip_profiles/external/gateway1.xml

# Redémarrer profil SIP
/usr/local/freeswitch/bin/fs_cli -x "sofia profile external restart reloadxml"
```

---

## 🎉 INSTALLATION TERMINÉE !

Votre système MiniBotPanel v3 avec streaming audio temps réel est maintenant opérationnel !

### Prochaines étapes

1. **Préparer fichiers audio** :
   ```bash
   # Placer vos fichiers WAV/MP3 dans audio/julie/base/
   python setup_audio.py julie
   ```

2. **Créer un scénario** :
   ```bash
   python create_scenario.py
   ```

3. **Importer contacts** :
   ```bash
   python import_contacts.py contacts.csv
   ```

4. **Lancer une campagne** :
   ```bash
   python launch_campaign.py --scenario mon_scenario
   ```

5. **Monitorer en temps réel** :
   ```bash
   python monitor_campaign.py --campaign-id 1
   ```

### Documentation complémentaire

- **STREAMING_AUDIO_WEBSOCKET.md** : Architecture streaming temps réel
- **GUIDE_UTILISATION.md** : Utilisation quotidienne du système
- **BRIEF_PROJET.md** : Architecture globale

### Support

- **Logs système** : `logs/`
- **Logs FreeSWITCH** : `/usr/local/freeswitch/var/log/freeswitch/`

---

**Version du guide** : v3.0.0
**Dernière mise à jour** : 2025-11-07
**Basé sur** : Installation réelle sur Ubuntu 22.04 LTS
