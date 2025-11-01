# Installation fs_minibot_streaming sur Ubuntu 22.04 LTS

Guide d'installation complet étape par étape.

---

## 1. Préparation du système

### 1.1 Mise à jour du système
```bash
apt update && apt upgrade -y
```

### 1.2 Installation des outils de base
```bash
apt install -y git curl wget vim nano build-essential software-properties-common
```

### 1.3 Vérifier version Ubuntu
```bash
lsb_release -a
# Devrait afficher: Ubuntu 22.04 LTS
```

---

## 2. Cloner le projet

### 2.1 Créer dossier et cloner
```bash
mkdir -p /opt
cd /opt
git clone https://github.com/jokyjokeai/fs_minibot_streaming.git
cd fs_minibot_streaming
ls -la
```

---

## 3. Installer PostgreSQL

### 3.1 Installation
```bash
apt install -y postgresql postgresql-contrib
```

### 3.2 Démarrer le service
```bash
systemctl start postgresql
systemctl enable postgresql
systemctl status postgresql
```

### 3.3 Créer utilisateur et base de données
```bash
sudo -u postgres psql -c "CREATE USER minibot WITH PASSWORD 'minibot';"
sudo -u postgres psql -c "CREATE DATABASE minibot_freeswitch OWNER minibot;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE minibot_freeswitch TO minibot;"
```

### 3.4 Tester connexion
```bash
psql -U minibot -d minibot_freeswitch -h localhost -c "SELECT version();"
# Mot de passe: minibot
```

---

## 4. Détection GPU et installation drivers (OPTIONNEL)

### 4.1 Détecter GPU NVIDIA

```bash
# Vérifier si GPU NVIDIA présent
lspci | grep -i nvidia
```

**Si vous voyez une sortie** (ex: `NVIDIA Corporation GP102 [GeForce GTX 1080 Ti]`), vous avez un GPU NVIDIA. **Continuez avec 4.2**.

**Si aucune sortie**, vous n'avez pas de GPU → **Passez directement à la section 5**.

---

### 4.2 Installer drivers NVIDIA (si GPU détecté)

```bash
# Ajouter repository NVIDIA
add-apt-repository ppa:graphics-drivers/ppa -y
apt update

# Détecter version driver recommandée
ubuntu-drivers devices

# Installer driver recommandé (exemple: 535)
apt install -y nvidia-driver-535

# Redémarrer pour activer le driver
reboot
```

**Après redémarrage**, vérifier :
```bash
nvidia-smi
```

Devrait afficher infos GPU (température, mémoire, etc.)

---

### 4.3 Installer CUDA Toolkit (si GPU détecté)

```bash
# CUDA 11.8 (compatible PyTorch 2.1.2)
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run
chmod +x cuda_11.8.0_520.61.05_linux.run
./cuda_11.8.0_520.61.05_linux.run --silent --toolkit

# Ajouter CUDA au PATH
echo 'export PATH=/usr/local/cuda-11.8/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# Vérifier installation
nvcc --version
```

---

## 5. Installer Python 3.11 et dépendances

### 5.1 Installer Python
```bash
apt install -y python3 python3-pip python3-venv python3-dev
python3 --version
pip3 --version
```

### 5.2 Créer environnement virtuel
```bash
cd /opt/fs_minibot_streaming
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 5.3 Installer dépendances Python (BASE)

**IMPORTANT** : On installe d'abord les dépendances de base, PyTorch sera installé après selon GPU/CPU.

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Utiliser le script d'installation automatique (RECOMMANDÉ)
./install_dependencies.sh

# OU installer manuellement
pip install -r requirements.txt
```

**Notes importantes**:
- PyTorch sera installé à l'étape 5.4 selon votre configuration GPU/CPU
- python-esl est commenté dans requirements.txt (compilation manuelle à l'étape 10.5)
- L'installation peut prendre 5-10 minutes

---

### 5.4 Installer PyTorch (GPU ou CPU)

#### **Option A : Si GPU NVIDIA détecté (étape 4)**

```bash
# PyTorch avec CUDA 11.8 (GPU)
pip install torch==2.1.2+cu118 torchaudio==2.1.2+cu118 --index-url https://download.pytorch.org/whl/cu118

# Vérifier détection GPU
python -c "import torch; print(f'CUDA disponible: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"Aucun\"}')"
```

**Résultat attendu** :
```
CUDA disponible: True
GPU: NVIDIA GeForce RTX 4090
```

#### **Option B : Pas de GPU (VPS CPU-only)**

```bash
# PyTorch CPU (léger ~200 MB)
pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu

# Vérifier
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print('Mode: CPU only')"
```

---

### 5.5 Vérifier installation complète
```bash
pip list | grep -E "fastapi|vosk|coqui-tts|psycopg2|ollama|torch|numpy|transformers|demucs"
```

Vous devriez voir:
- `torch` 2.1.2 (ou 2.1.2+cu118 si GPU)
- `numpy` >= 1.24.3
- `transformers` 4.35.0
- `coqui-tts` 0.27.2
- `demucs` >= 4.0.0
- `pydantic` >= 2.9.0
- `ollama` >= 0.6.0

---

## 6. Compiler FreeSWITCH 1.10 depuis les sources

### 6.1 Installer dépendances de compilation
```bash
apt install -y \
  autoconf automake devscripts gawk g++ git-core \
  libjpeg-dev libncurses5-dev libtool libtool-bin make python3-dev pkg-config \
  libtiff-dev libperl-dev libgdbm-dev libdb-dev gettext libssl-dev \
  libcurl4-openssl-dev libpcre3-dev libspeex-dev libspeexdsp-dev \
  libsqlite3-dev libedit-dev libldns-dev libpq-dev \
  yasm nasm libx264-dev libavformat-dev libswscale-dev \
  libopus-dev libsndfile1-dev uuid-dev swig
```

### 6.2 Cloner FreeSWITCH 1.10
```bash
cd /usr/src
git clone https://github.com/signalwire/freeswitch.git -b v1.10 freeswitch
cd freeswitch
```

### 6.3 Bootstrap
```bash
./bootstrap.sh -j
```

---

## 6. Compiler sofia-sip (dépendance requise)

**Important**: Depuis FreeSWITCH 1.10.4, sofia-sip n'est plus dans l'arbre FreeSWITCH.

```bash
cd /usr/local/src
git clone https://github.com/freeswitch/sofia-sip.git
cd sofia-sip
./bootstrap.sh
./configure
make
make install
ldconfig
```

### Vérifier installation
```bash
ldconfig -p | grep sofia
# Devrait afficher: libsofia-sip-ua.so
```

---

## 7. Compiler spandsp (dépendance requise)

```bash
cd /usr/local/src
git clone https://github.com/freeswitch/spandsp.git
cd spandsp
./bootstrap.sh
./configure
make
make install
ldconfig
```

---

## 8. Configurer modules FreeSWITCH

**Désactiver modules non nécessaires**:

```bash
cd /usr/src/freeswitch

# mod_verto et mod_signalwire (requièrent libks)
sed -i 's/^endpoints\/mod_verto/#endpoints\/mod_verto/' modules.conf
sed -i 's/^applications\/mod_signalwire/#applications\/mod_signalwire/' modules.conf

# mod_lua (requiert headers Lua non installés)
sed -i 's/^languages\/mod_lua/#languages\/mod_lua/' modules.conf
```

**Optionnel**: Désactiver modules FAX et voicemail (non utilisés):
```bash
sed -i 's/^applications\/mod_spandsp/#applications\/mod_spandsp/' modules.conf
sed -i 's/^applications\/mod_fax/#applications\/mod_fax/' modules.conf
sed -i 's/^applications\/mod_voicemail/#applications\/mod_voicemail/' modules.conf
```

### Vérifier modules désactivés
```bash
grep -E '^#(endpoints/mod_verto|applications/mod_signalwire|languages/mod_lua)' modules.conf
```

---

## 9. Configurer et compiler FreeSWITCH

### 9.1 Configuration
```bash
cd /usr/src/freeswitch
./configure --prefix=/usr/local/freeswitch
```

**Attendre la fin** (quelques minutes). Devrait se terminer par:
```
-------------------------- FreeSWITCH configuration --------------------------
  prefix:          /usr/local/freeswitch
  ...
------------------------------------------------------------------------------
```

### 9.2 Compilation
```bash
# Compilation (utilise tous les CPU disponibles)
make -j$(nproc)
```

**⏱ Durée**: 15-30 minutes selon le VPS.

**Note**: Si la compilation échoue avec une erreur "fatal error: xxx.h: No such file or directory" pour un module, désactivez ce module dans modules.conf et relancez make:
```bash
# Exemple: si mod_xyz échoue
sed -i 's/^categorie\/mod_xyz/#categorie\/mod_xyz/' modules.conf
make -j$(nproc)
```

### 9.3 Installation
```bash
make install
```

### 9.4 Installer fichiers de configuration
```bash
make cd-sounds-install cd-moh-install
```

---

## 10. Configuration post-installation FreeSWITCH

### 10.1 Créer utilisateur freeswitch
```bash
adduser --disabled-password --quiet --system --home /usr/local/freeswitch --gecos "FreeSWITCH" --ingroup daemon freeswitch
chown -R freeswitch:daemon /usr/local/freeswitch
```

### 10.2 Créer service systemd
```bash
cat > /etc/systemd/system/freeswitch.service << 'EOF'
[Unit]
Description=FreeSWITCH
After=network.target

[Service]
Type=forking
PIDFile=/usr/local/freeswitch/var/run/freeswitch/freeswitch.pid
User=freeswitch
Group=daemon
ExecStart=/usr/local/freeswitch/bin/freeswitch -nc -nonat
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 10.3 Activer et démarrer FreeSWITCH
```bash
systemctl daemon-reload
systemctl enable freeswitch
systemctl start freeswitch
systemctl status freeswitch
```

### 10.4 Tester ESL (Event Socket Library)
```bash
/usr/local/freeswitch/bin/fs_cli -H localhost -P 8021 -p ClueCon -x "status"
```

### 10.5 Compiler python-esl manuellement

**Important** : Le package python-esl via pip ne compile pas avec swig 4.x (flag `-classic` déprécié). On doit le compiler depuis les sources FreeSWITCH.

```bash
# Aller dans le dossier ESL de FreeSWITCH
cd /usr/src/freeswitch/libs/esl

# Retirer le flag -classic obsolète du Makefile python3
sed -i 's/-classic //' python3/Makefile

# Compiler la librairie ESL
make

# Générer le wrapper SWIG pour Python
swig -module ESL -python -c++ -DMULTIPLICITY -threads -I./src/include -o python3/esl_wrap.cpp ESL.i

# Compiler le module Python
cd python3
g++ -fPIC -shared \
  $(python3-config --includes) \
  $(python3-config --ldflags) \
  -I../src/include \
  esl_wrap.cpp ../.libs/libesl.a \
  -o _ESL.so

# Vérifier que le module a été créé
ls -la _ESL.so

# Activer le venv du projet
source /opt/fs_minibot_streaming/venv/bin/activate

# Copier le module dans le venv
cp _ESL.so ESL.py /opt/fs_minibot_streaming/venv/lib/python3.11/site-packages/
```

### Vérifier installation python-esl
```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate
python -c "import ESL; print('python-esl OK')"
```

Devrait afficher : `python-esl OK`

---

## 11. Installer modèles IA

### 11.1 Vosk STT (Speech-to-Text) - Français
```bash
cd /opt/fs_minibot_streaming
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
unzip vosk-model-small-fr-0.22.zip
rm vosk-model-small-fr-0.22.zip
```

### 11.2 Ollama NLP
```bash
# Installer Ollama (service)
curl -fsSL https://ollama.com/install.sh | sh

# Démarrer le service Ollama (si pas déjà lancé)
ollama serve &

# Télécharger modèle Mistral 7B
ollama pull mistral:7b

# Vérifier
ollama list
```

**Note**: Le package Python `ollama` est déjà inclus dans requirements.txt et a été installé à la section 5.3.

### 11.3 Coqui TTS (Text-to-Speech)
```bash
# Les modèles seront téléchargés automatiquement au premier lancement
# Créer le dossier cache
mkdir -p /opt/fs_minibot_streaming/models/coqui_cache
```

---

## 12. Configuration du projet

### 12.1 Créer fichier .env
```bash
cd /opt/fs_minibot_streaming
cp .env.example .env

# Éditer avec nano (recommandé pour débutants)
nano .env

# Ou avec vim si vous préférez
# vim .env
```

**Modifier les valeurs** (au minimum):
```bash
# Database
DATABASE_URL=postgresql://minibot:minibot@localhost:5432/minibot_freeswitch

# FreeSWITCH
FREESWITCH_ESL_HOST=localhost
FREESWITCH_ESL_PORT=8021
FREESWITCH_ESL_PASSWORD=ClueCon
FREESWITCH_CALLER_ID=+33123456789  # À MODIFIER

# Vosk
VOSK_MODEL_PATH=models/vosk-model-small-fr-0.22

# Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b

# API
API_PASSWORD=VotreMotDePasseSecurise  # À MODIFIER
```

### 12.2 Initialiser la base de données
```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate
python setup_database.py
```

Devrait afficher :
```
✅ Database connection OK
✅ Tables créées avec succès
Contacts: 0
Campagnes: 0
✅ Setup base de données terminé!
```

---

## 13. Tester le système

### 13.1 Vérifier installation PyTorch

⚠️ **Si vous avez sauté les sections 4 et 5.4**, assurez-vous que PyTorch 2.1.2 est bien installé :

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate
pip list | grep -E "torch|numpy|transformers"
```

**Versions attendues** :
- torch: 2.1.2 (ou 2.1.2+cu118 si GPU)
- numpy: 1.22.0
- transformers: 4.33.0

Si les versions ne correspondent pas, retournez à la **section 5.4** pour installer PyTorch correctement.

---

### 13.2 Démarrer l'API
```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate
uvicorn system.api.main:app --host 0.0.0.0 --port 8000
```

**Logs attendus au démarrage** :
```
✅ Vosk STT loaded
✅ Coqui TTS loaded        ← Doit afficher "loaded", pas "error"
✅ Ollama NLP loaded
✅ AMD Service loaded
✅ StreamingASR loaded
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 13.3 Tester l'API
Dans un **nouveau terminal SSH** :

```bash
# Test 1 : Health check
curl http://localhost:8000/health

# Test 2 : Info API
curl http://localhost:8000/

# Test 3 : Campaigns (avec authentification)
curl -H "X-API-Key: VotreMotDePasseSecurise" http://localhost:8000/api/campaigns
```

**Résultats attendus** :
- `/health` → JSON avec status "healthy" ou "degraded"
- `/` → Infos API + uptime
- `/api/campaigns` → `[]` (liste vide, normal pour début)

---

## 14. Créer service systemd pour l'API

```bash
cat > /etc/systemd/system/minibot-api.service << 'EOF'
[Unit]
Description=MiniBotPanel v3 API
After=network.target postgresql.service freeswitch.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fs_minibot_streaming
Environment="PATH=/opt/fs_minibot_streaming/venv/bin"
ExecStart=/opt/fs_minibot_streaming/venv/bin/uvicorn system.api.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable minibot-api
systemctl start minibot-api
systemctl status minibot-api
```

---

## 15. Configuration FreeSWITCH pour MiniBotPanel

### 15.1 Installer configuration vanilla (base)

```bash
# Arrêter FreeSWITCH
sudo systemctl stop freeswitch

# Installer config vanilla de base
cd /usr/src/freeswitch
sudo make samples

# Vérifier installation (config dans /etc/freeswitch/)
ls -la /usr/local/freeswitch/etc/freeswitch/
ls -la /usr/local/freeswitch/etc/freeswitch/autoload_configs/ | head -10
ls -la /usr/local/freeswitch/etc/freeswitch/dialplan/

# Fixer permissions
sudo chown -R freeswitch:daemon /usr/local/freeswitch/

# Redémarrer FreeSWITCH
sudo systemctl start freeswitch
sudo systemctl status freeswitch

# Tester
fs_cli -x "sofia status"
fs_cli -x "reloadxml"
```

---

### 15.2 Copier fichiers config custom

Les fichiers de configuration personnalisés sont dans `documentation/config_freeswitch/`.

```bash
cd /opt/fs_minibot_streaming

# Event Socket Layer (ESL) - OBLIGATOIRE
sudo cp documentation/config_freeswitch/event_socket.conf.xml /usr/local/freeswitch/etc/freeswitch/autoload_configs/

# Modules minimaux
sudo cp documentation/config_freeswitch/modules.conf.xml /usr/local/freeswitch/etc/freeswitch/autoload_configs/

# Dialplan appels sortants
sudo cp documentation/config_freeswitch/dialplan_outbound.xml /usr/local/freeswitch/etc/freeswitch/dialplan/

# Gateway SIP (template à éditer)
sudo cp documentation/config_freeswitch/gateway_example.xml /usr/local/freeswitch/etc/freeswitch/sip_profiles/external/gateway1.xml

# Fixer permissions
sudo chown -R freeswitch:daemon /usr/local/freeswitch/etc/freeswitch/

# Recharger config
fs_cli -x "reloadxml"
fs_cli -x "sofia status"
```

---

### 15.3 Configurer gateway SIP provider

⚠️ **IMPORTANT** : Modifier `/usr/local/freeswitch/etc/freeswitch/sip_profiles/external/gateway1.xml` avec les infos de **votre provider SIP**.

**Méthode 1 : Édition manuelle**

```bash
sudo nano /usr/local/freeswitch/etc/freeswitch/sip_profiles/external/gateway1.xml
```

Modifier ces valeurs :
```xml
<param name="proxy" value="188.34.143.144"/>        <!-- IP serveur SIP -->
<param name="realm" value="188.34.143.144"/>        <!-- Même IP -->
<param name="username" value="votre_username"/>     <!-- Username -->
<param name="password" value="votre_password"/>     <!-- Password -->
<variable name="outbound_caller_id_number" value="votre_username"/>  <!-- Caller ID -->
```

**Méthode 2 : Script direct (plus rapide)**

```bash
sudo bash -c 'cat > /usr/local/freeswitch/etc/freeswitch/sip_profiles/external/gateway1.xml << "EOF"
<gateway name="gateway1">
  <!-- Provider SIP configuré -->

  <!-- Serveur SIP -->
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
EOF'
```

**Exemples de providers** :
- OVH Telecom : `sip.ovh.fr`
- Bandwidth : `sip.bandwidth.com`
- Twilio : `YOUR_ACCOUNT.pstn.twilio.com`
- IP directe : `188.34.143.144` (comme dans l'exemple)

Après modification :
```bash
# Recharger profil SIP
fs_cli -x "sofia profile external restart reloadxml"

# Attendre 10 secondes
sleep 10

# Vérifier gateway
fs_cli -x "sofia status gateway gateway1"
```

---

### 15.4 Test registration SIP

Vérifier que le gateway s'enregistre correctement :

```bash
# Vérifier status gateway
fs_cli -x "sofia status gateway gateway1"
```

**Résultat attendu** :
```
Name: gateway1
State: REGED (enregistré avec succès)
```

**Si NOREG ou FAIL_WAIT** :
- Vérifier username/password
- Vérifier que le serveur SIP est accessible : `ping sip.votreprovider.com`
- Vérifier logs : `tail -f /usr/local/freeswitch/var/log/freeswitch/freeswitch.log`

---

### 15.5 Test appel sortant

Tester un appel manuel depuis FreeSWITCH :

```bash
# Remplacer +33612345678 par un vrai numéro
fs_cli -x "originate sofia/gateway/gateway1/+33612345678 &park()"
```

**Résultat attendu** :
- L'appel se lance
- Le numéro appelé sonne
- Logs FreeSWITCH montrent `CHANNEL_CREATE` et `CHANNEL_ANSWER`

**Raccrocher l'appel** :
```bash
fs_cli -x "hupall"
```

---

## 16. Tests services IA

### 16.1 Test Vosk STT (Speech-to-Text)

Tester la transcription audio → texte avec le fichier `audio/test_audio.wav` :

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Tester transcription Vosk STT
python3 << 'EOF'
from vosk import Model, KaldiRecognizer
import wave
import json

print("📥 Chargement modèle Vosk...")
model = Model("models/vosk-model-small-fr-0.22")

# Ouvrir fichier audio test
print("🎵 Lecture audio/test_audio.wav...")
wf = wave.open("audio/test_audio.wav", "rb")

print(f"   Channels: {wf.getnchannels()}")
print(f"   Sample rate: {wf.getframerate()} Hz")
print(f"   Duration: {wf.getnframes() / wf.getframerate():.2f}s")

# Créer recognizer
rec = KaldiRecognizer(model, wf.getframerate())

# Transcrire
print("\n🎤 Transcription en cours...")
while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    rec.AcceptWaveform(data)

# Résultat final
result = json.loads(rec.FinalResult())

print("\n✅ Transcription terminée !")
print(f"📝 Texte reconnu : \"{result.get('text', '')}\"")

wf.close()
EOF
```

**Résultat attendu** : Le texte contenu dans `audio/test_audio.wav` est transcrit avec succès.

---

### 16.2 Test clonage de voix Coqui (préparation)

**IMPORTANT** : XTTS v2 est un modèle **uniquement avec clonage de voix**. Il faut d'abord créer un embedding vocal avant de générer du TTS.

Cloner la voix depuis `audio/test_audio.wav` :

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Tester clonage de voix
python3 << 'EOF'
from TTS.api import TTS
import torch

print("📥 Chargement Coqui TTS XTTS v2...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🖥️  Device : {device}")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Clonage avec audio/test_audio.wav comme référence
print("🎭 Clonage de la voix depuis audio/test_audio.wav...")
print("🔊 Génération avec la voix clonée...")

tts.tts_to_file(
    text="Ceci est un test de clonage de voix avec Coqui TTS. Ma voix a été clonée à partir d'un échantillon audio.",
    speaker_wav="audio/test_audio.wav",  # Fichier référence pour clonage
    language="fr",
    file_path="audio/test_voice_cloned.wav"
)

print("✅ Voix clonée : audio/test_voice_cloned.wav")
print("💡 Comparez avec audio/test_audio.wav pour entendre la similarité")
EOF
```

**Résultat attendu** :
- Modèle XTTS v2 téléchargé (~2 GB, première fois uniquement)
- Le fichier `audio/test_voice_cloned.wav` est créé
- La voix synthétisée ressemble à celle de `audio/test_audio.wav`

**Notes** :
- Meilleure qualité avec un fichier référence de **6-10 secondes**
- Voix claire, sans bruit de fond
- Format optimal : **mono, 16-22kHz, WAV**

---

### 16.3 Test Coqui TTS (Text-to-Speech)

Maintenant qu'on a créé l'embedding vocal, générer un fichier audio à partir de texte avec la voix clonée :

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Tester génération TTS avec voix clonée
python3 << 'EOF'
from TTS.api import TTS
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🖥️  Device : {device}")

print("📥 Chargement Coqui TTS XTTS v2...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Générer audio avec voix clonée depuis test_audio.wav
print("🔊 Génération TTS avec voix clonée...")
tts.tts_to_file(
    text="Ceci est un test de création texte vers parole avec Coqui TTS.",
    speaker_wav="audio/test_audio.wav",  # Utiliser la voix de référence
    language="fr",
    file_path="audio/test_tts_output.wav"
)

print("✅ Audio généré : audio/test_tts_output.wav")
EOF
```

**Résultat attendu** :
- Le fichier `audio/test_tts_output.wav` est créé
- La voix utilisée est celle clonée depuis `audio/test_audio.wav`
- Le texte est différent de l'audio source

---

### 16.4 Test Ollama NLP (Intent + Sentiment)

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Tester Ollama
python3 << 'EOF'
import ollama

# Test intent detection
response = ollama.chat(model='mistral:7b', messages=[
  {
    'role': 'system',
    'content': 'Tu es un assistant qui détecte l\'intention de l\'utilisateur. Réponds uniquement par : INTERESTED, NOT_INTERESTED, ou QUESTION.'
  },
  {
    'role': 'user',
    'content': 'Oui ça m\'intéresse, envoyez-moi plus d\'informations.'
  },
])

print("🤖 Intent détecté :", response['message']['content'])

# Test sentiment analysis
response = ollama.chat(model='mistral:7b', messages=[
  {
    'role': 'system',
    'content': 'Analyse le sentiment de cette phrase. Réponds uniquement par : POSITIVE, NEGATIVE, ou NEUTRAL.'
  },
  {
    'role': 'user',
    'content': 'Je suis très satisfait de votre service !'
  },
])

print("😊 Sentiment :", response['message']['content'])
print("✅ Ollama NLP fonctionne")
EOF
```

---

## 17. Vérification finale

### 17.1 Vérifier tous les services
```bash
systemctl status postgresql
systemctl status freeswitch
systemctl status minibot-api
```

### 17.2 Tester connexion complète
```bash
curl http://localhost:8000/health
```

Devrait retourner:
```json
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy"},
    "freeswitch": {"status": "healthy"},
    "vosk": {"status": "healthy"},
    "ollama": {"status": "healthy"}
  }
}
```

---

## Troubleshooting

### FreeSWITCH ne démarre pas
```bash
# Vérifier logs
journalctl -u freeswitch -n 50

# Tester manuellement
/usr/local/freeswitch/bin/freeswitch -nc -nonat
```

### API ne démarre pas
```bash
# Vérifier logs
journalctl -u minibot-api -n 50

# Tester manuellement
cd /opt/fs_minibot_streaming
source venv/bin/activate
python system/api/main.py
```

### Problèmes de permissions
```bash
chown -R freeswitch:daemon /usr/local/freeswitch
chmod -R 755 /opt/fs_minibot_streaming
```

---

## Commandes utiles

```bash
# FreeSWITCH CLI
/usr/local/freeswitch/bin/fs_cli

# Logs FreeSWITCH
tail -f /usr/local/freeswitch/var/log/freeswitch/freeswitch.log

# Logs API
journalctl -u minibot-api -f

# Restart services
systemctl restart freeswitch
systemctl restart minibot-api
```

---

## 16.5 Clonage de Voix Persistante

Le système supporte maintenant les **voix clonées persistantes** pour optimiser les performances en production.

### Créer une voix clonée

```bash
cd /opt/fs_minibot_streaming
source venv/bin/activate

# Cloner voix depuis test_audio.wav
python clone_voice.py --audio audio/test_audio.wav --name julie --test "Ceci est un test de génération vocale."
```

**Résultat attendu :**
```
🎤 Cloning voice 'julie' from audio/test_audio.wav...
✅ Voice 'julie' cloned successfully in X.XXs
📁 Saved to: voices/julie/
🎵 Reference: reference.wav
📄 Metadata: metadata.json
🔊 Test de la voix 'julie'...
📝 Texte: Ceci est un test de génération vocale.
✅ Audio de test généré: voices/test_julie.wav
💡 Écoutez le fichier pour valider la qualité de la voix
✅ Clonage terminé avec succès!
📁 Voix sauvegardée: voices/julie/
```

### Structure créée

```
voices/julie/
├── reference.wav        # Audio de référence (copie de test_audio.wav)
├── test_clone.wav       # Test de clonage vocal
└── metadata.json        # Métadonnées (durée, date création, etc.)
```

### Utiliser une voix clonée

**En Python :**
```python
from system.services.coqui_tts import CoquiTTS

tts = CoquiTTS()

# Générer avec voix clonée "julie"
audio_file = tts.generate(
    text="Bonjour, comment allez-vous aujourd'hui ?",
    voice_name="julie",
    output_path="audio/test_generation_julie.wav"
)

print(f"Audio généré: {audio_file}")
```

**Résultat attendu :**
```
🎙️ Generating TTS with voice 'julie'...
✅ TTS cloned voice generated in X.XXs
✅ TTS generated with voice 'julie': audio/test_generation_julie.wav
```

### Lister les voix disponibles

**En Python :**
```python
from system.services.coqui_tts import CoquiTTS

tts = CoquiTTS()
voices = tts.list_voices()

for voice in voices:
    print(f"Voix: {voice['name']}")
    print(f"  - Créée le: {voice['created_at']}")
    print(f"  - Durée référence: {voice['audio_duration']}s")
    print(f"  - Chemin: {voice['path']}")
```

### Utiliser dans les scénarios

**Nouveau type audio : `tts_cloned`**

```json
{
  "intro": {
    "message_text": "Bonjour {{first_name}}, je suis Julie...",
    "audio_type": "tts_cloned",
    "voice": "julie",
    "voice_config": {
      "reference_wav": "voices/julie/reference.wav"
    },
    "barge_in": true,
    "timeout": 15,
    "intent_mapping": {
      "affirm": "question1",
      "deny": "fin"
    }
  }
}
```

**Voir exemple complet :** `documentation/scenarios/exemple_voix_clonee.json`

### Avantages production

✅ **Performance** : La voix clonée est sauvegardée, pas besoin de recalculer l'embedding à chaque fois
✅ **Cohérence** : Même voix pour toute la campagne (pré-enregistré + freestyle)
✅ **Qualité** : Référence audio optimale choisie manuellement
✅ **Gestion** : Liste des voix disponibles, métadonnées, tests automatiques

---

**✅ Installation terminée !**

Documentation complète dans `/opt/fs_minibot_streaming/documentation/`
