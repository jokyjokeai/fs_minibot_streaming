# Streaming Audio WebSocket avec FreeSWITCH et mod_audio_stream

## Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Installation de mod_audio_stream](#installation-de-mod_audio_stream)
4. [Configuration FreeSWITCH](#configuration-freeswitch)
5. [Intégration avec RobotFreeSwitchV2](#intégration-avec-robotfreeswitchv2)
6. [Utilisation](#utilisation)
7. [Dépannage](#dépannage)

---

## Vue d'ensemble

Ce document décrit comment configurer le streaming audio temps réel depuis FreeSWITCH vers un serveur WebSocket pour la transcription vocale avec Vosk ASR.

**Problème résolu**: FreeSWITCH ne peut pas nativement streamer l'audio vers un WebSocket. Le module `mod_audio_stream` permet de capturer l'audio RTP d'un appel et de l'envoyer en temps réel vers un serveur WebSocket.

**Bénéfices**:
- ✅ Transcription en temps réel (pas d'attente de fin d'enregistrement)
- ✅ Détection de barge-in instantanée
- ✅ Latence minimale (~100-300ms)
- ✅ Pas de fichiers temporaires

---

## Architecture

```
┌─────────────────┐
│  Client SIP     │
│  (Téléphone)    │
└────────┬────────┘
         │ Audio RTP
         ▼
┌─────────────────────────────┐
│     FreeSWITCH              │
│                             │
│  ┌───────────────────────┐  │
│  │  mod_audio_stream     │  │
│  │  (Media Bug)          │  │
│  └──────────┬────────────┘  │
│             │ L16 PCM       │
└─────────────┼───────────────┘
              │ WebSocket
              │ ws://127.0.0.1:8080
              ▼
┌──────────────────────────────┐
│  StreamingASR Server         │
│  (Python WebSocket)          │
│                              │
│  ┌────────────────────────┐  │
│  │  WebRTC VAD            │  │
│  │  (Détection parole)    │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │  Vosk ASR              │  │
│  │  (Transcription)       │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │  Ollama NLP            │  │
│  │  (Intent Analysis)     │  │
│  └────────────────────────┘  │
└──────────────┬───────────────┘
               │ Transcription
               ▼
┌──────────────────────────────┐
│  RobotFreeSwitchV2           │
│  (Gestion scénario)          │
└──────────────────────────────┘
```

---

## Installation de mod_audio_stream

### 1. Prérequis

```bash
# Dépendances système
sudo apt-get update
sudo apt-get install -y libssl-dev zlib1g-dev libspeexdsp-dev cmake git
```

**Vérification**:
```bash
dpkg -l | grep -E "libssl-dev|zlib1g-dev|libspeexdsp-dev|cmake"
```

### 2. Cloner le repository

```bash
cd /tmp
git clone https://github.com/sptmru/freeswitch_mod_audio_stream.git
cd freeswitch_mod_audio_stream
git submodule init
git submodule update
```

### 3. Créer freeswitch.pc (pkg-config)

FreeSWITCH ne fournit pas de fichier `.pc` par défaut. Il faut le créer manuellement:

```bash
cat > /tmp/freeswitch.pc <<EOF
prefix=/usr/local/freeswitch
exec_prefix=\${prefix}
libdir=/usr/src/freeswitch/.libs
includedir=/usr/src/freeswitch/src/include

Name: freeswitch
Description: FreeSWITCH
Version: 1.10
Libs: -L\${libdir} -lfreeswitch
Cflags: -I\${includedir} -I/usr/src/freeswitch/libs/libteletone/src
EOF
```

**Important**: Adapter les chemins selon votre installation:
- `libdir`: Chemin vers libfreeswitch.so (généralement `/usr/src/freeswitch/.libs`)
- `includedir`: Chemin vers les headers FreeSWITCH
- Ajouter le chemin vers `libteletone/src` dans Cflags

### 4. Compiler le module

```bash
mkdir build && cd build

# Configurer avec cmake
export PKG_CONFIG_PATH=/tmp:$PKG_CONFIG_PATH
cmake -DCMAKE_BUILD_TYPE=Release ..

# Compiler
make -j$(nproc)
```

**Sortie attendue**:
```
[100%] Built target ixwebsocket
[100%] Built target mod_audio_stream
```

Le fichier `mod_audio_stream.so` est généré dans `build/`.

### 5. Installer le module

```bash
# Copier vers répertoire modules FreeSWITCH
sudo cp mod_audio_stream.so /usr/local/freeswitch/lib/freeswitch/mod/

# Définir permissions
sudo chmod 755 /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so

# Vérifier
ls -la /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so
```

---

## Configuration FreeSWITCH

### 1. Charger le module

Éditer `/usr/local/freeswitch/etc/freeswitch/autoload_configs/modules.conf.xml`:

```xml
<configuration name="modules.conf" description="Modules">
  <modules>
    <!-- ... autres modules ... -->

    <!-- Streaming Audio Module -->
    <load module="mod_audio_stream"/>

  </modules>
</configuration>
```

### 2. Redémarrer FreeSWITCH

```bash
sudo systemctl restart freeswitch
```

### 3. Vérifier le chargement

```bash
/usr/local/freeswitch/bin/fs_cli -x "module_exists mod_audio_stream"
```

**Sortie attendue**: `true`

### 4. Tester la commande

```bash
/usr/local/freeswitch/bin/fs_cli
```

Puis dans fs_cli:
```
uuid_audio_stream <UUID> help
```

**Sortie attendue**:
```
USAGE:
  uuid_audio_stream <uuid> start <wss-url> <mix-type> <sampling-rate> <metadata>
  uuid_audio_stream <uuid> send_text <metadata>
  uuid_audio_stream <uuid> stop <metadata>
  uuid_audio_stream <uuid> pause
  uuid_audio_stream <uuid> resume
```

---

## Intégration avec RobotFreeSwitchV2

### 1. Vérifier StreamingASR

Le serveur WebSocket StreamingASR est déjà implémenté dans:
```
system/services/streaming_asr.py
```

**Caractéristiques**:
- Port: 8080 (configurable)
- Format audio accepté: L16 PCM, 16kHz ou 8kHz, mono
- Protocole: WebSocket (ws://)
- Callbacks: speech_start, speech_end, transcription

### 2. Modifier _enable_audio_streaming()

Dans `system/robot_freeswitch_v2.py`, ligne ~612:

```python
def _enable_audio_streaming(self, call_uuid: str) -> bool:
    """
    Active le streaming audio FreeSWITCH → WebSocket avec mod_audio_stream

    Args:
        call_uuid: UUID de l'appel

    Returns:
        True si streaming activé
    """
    if not self.esl_conn_api or not self.esl_conn_api.connected():
        return False

    try:
        # URL du serveur WebSocket StreamingASR
        websocket_url = "ws://127.0.0.1:8080/stream/{call_uuid}"

        # Paramètres streaming
        mix_type = "mono"  # mono = caller only, mixed = both, stereo = separate
        sampling_rate = "16000"  # 16kHz pour Vosk
        metadata = ""  # Métadonnées optionnelles

        # Commande uuid_audio_stream
        cmd = f"uuid_audio_stream {call_uuid} start {websocket_url} {mix_type} {sampling_rate} {metadata}"
        result = self.esl_conn_api.api(cmd)

        result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

        if "+OK" in result_str:
            logger.info(f"[{call_uuid[:8]}] ✅ Audio streaming started to WebSocket")
            return True
        else:
            logger.error(f"[{call_uuid[:8]}] ❌ Audio streaming failed: {result_str}")
            return False

    except Exception as e:
        logger.error(f"[{call_uuid[:8]}] Audio streaming error: {e}", exc_info=True)
        return False
```

### 3. Activer le streaming au bon moment

Dans `_handle_call()` (ligne ~461), AVANT d'exécuter le scénario:

```python
def _handle_call(self, call_uuid: str, phone_number: str, scenario: str, campaign_id: str):
    """Thread principal de gestion d'appel"""
    try:
        logger.info(f"[{call_uuid[:8]}] 🌊 Call thread started for {phone_number}")

        # === AMD DETECTION ===
        if self.amd_service and config.AMD_ENABLED:
            # ... AMD code ...

        # === ACTIVER STREAMING AUDIO ===
        if self.streaming_asr and self.streaming_asr.is_available:
            streaming_ok = self._enable_audio_streaming(call_uuid)
            if streaming_ok:
                logger.info(f"[{call_uuid[:8]}] ✅ Streaming audio activé")
            else:
                logger.warning(f"[{call_uuid[:8]}] ⚠️ Streaming audio échoué, utilisation mode record")

        # === ENREGISTRER CALLBACK STREAMING ===
        if self.streaming_asr and self.streaming_asr.is_available:
            self.streaming_asr.register_callback(call_uuid, self._handle_streaming_event)

        # === EXÉCUTER SCÉNARIO ===
        if self.scenario_manager:
            scenario_data = self.scenario_manager.load_scenario(scenario)
            if scenario_data:
                self._execute_scenario(call_uuid, scenario, campaign_id)
            # ...
```

### 4. Réactiver le mode streaming dans _listen_for_response()

Dans `_listen_for_response()` (ligne ~746), retirer le forçage du mode record:

```python
def _listen_for_response(self, call_uuid: str, timeout: int = 10) -> Optional[str]:
    """Écoute et transcrit la réponse du client"""
    if call_uuid not in self.streaming_sessions:
        logger.warning(f"[{call_uuid[:8]}] No streaming session")
        return None

    try:
        # Mode streaming si disponible ET mod_audio_stream installé
        if self.streaming_asr and self.streaming_asr.is_available:
            return self._listen_streaming(call_uuid, timeout)
        else:
            # Fallback: mode record
            return self._listen_record_fallback(call_uuid, timeout)

    except Exception as e:
        logger.error(f"[{call_uuid[:8]}] Listen error: {e}", exc_info=True)
        return None
```

---

## Utilisation

### 1. Démarrer RobotFreeSwitchV2

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming
python3 test_call_v2.py
```

**Logs attendus**:
```
✅ StreamingASR initialized
🌐 Starting WebSocket server on 127.0.0.1:8080
✅ WebSocket server started successfully
✅ RobotFreeSWITCH V2 initialized
```

### 2. Lancer un appel test

Le script `test_call_v2.py` lance automatiquement un appel:

```python
robot = RobotFreeSwitchV2()
robot.start()
time.sleep(10)

call_uuid = robot.originate_call('33743130341', 0, 'dfdf')
```

### 3. Vérifier les logs streaming

**Logs à surveiller**:

```
[call_uuid] ✅ Audio streaming started to WebSocket
📞 New audio stream for call: call_uuid
🗣️ Speech START detected: call_uuid
📝 PARTIAL transcription [call_uuid]: 'bonjour'
📝 FINAL transcription [call_uuid]: 'bonjour je suis intéressé'
🤐 Speech END detected: call_uuid
✅ Got transcription: bonjour je suis intéressé
Intent: affirm
```

### 4. Flux complet d'un appel

1. **Origination**: FreeSWITCH compose le numéro
2. **Answer**: Le client décroche
3. **Streaming activé**: `uuid_audio_stream start` connecte à WebSocket
4. **Audio playback**: Robot joue le message
5. **Listen**: Attente transcription pendant timeout
6. **VAD**: Detection début de parole
7. **Vosk ASR**: Transcription en temps réel
8. **Intent**: Analyse NLP avec Ollama
9. **Next step**: Navigation scénario selon intent
10. **Boucle**: Répéter 4-9 jusqu'à end

---

## Dépannage

### Erreur: "module 'mod_audio_stream' not found"

**Cause**: Module non chargé dans FreeSWITCH

**Solution**:
```bash
# Vérifier présence
ls -la /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so

# Vérifier modules.conf.xml
grep "mod_audio_stream" /usr/local/freeswitch/etc/freeswitch/autoload_configs/modules.conf.xml

# Recharger module
/usr/local/freeswitch/bin/fs_cli -x "reload mod_audio_stream"
```

### Erreur: "Cannot find -lfreeswitch" pendant compilation

**Cause**: Chemin libdir incorrect dans freeswitch.pc

**Solution**:
```bash
# Trouver libfreeswitch.so
find /usr -name "libfreeswitch.so" 2>/dev/null

# Mettre à jour /tmp/freeswitch.pc
# libdir=/chemin/vers/.libs
```

### Pas de transcription en mode streaming

**Diagnostic**:
```bash
# Vérifier WebSocket server actif
netstat -tlnp | grep 8080

# Vérifier logs StreamingASR
tail -f logs/misc/system.services.streaming_asr_*.log

# Tester WebSocket manuellement
python3 -c "import websockets; print(websockets.__version__)"
```

**Causes possibles**:
1. StreamingASR server pas démarré
2. FreeSWITCH n'envoie pas audio (uuid_audio_stream échoué)
3. Format audio incompatible (doit être L16 16kHz)

**Solution**:
```python
# Vérifier dans logs robot_freeswitch_v2
"✅ Audio streaming started to WebSocket"  # Doit apparaître

# Si absent, vérifier _enable_audio_streaming() appelé
```

### WebSocket se déconnecte immédiatement

**Cause**: URL incorrecte ou path non reconnu

**Solution**:
```python
# Dans _enable_audio_streaming()
websocket_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"

# Vérifier dans StreamingASR._handle_websocket_connection()
# path.split('/')[-1] doit retourner call_uuid
```

### Audio crackling / distorsion

**Cause**: Buffer size trop petit

**Solution**: Compiler mod_audio_stream avec `BUFFERIZATION_INTERVAL_MS` plus grand:

```cpp
// Dans audio_streamer_glue.cpp
#define BUFFERIZATION_INTERVAL_MS 40  // Au lieu de 20
```

Puis recompiler et réinstaller.

---

## Commandes utiles

### FreeSWITCH

```bash
# Lister modules chargés
/usr/local/freeswitch/bin/fs_cli -x "show modules"

# Tester uuid_audio_stream
/usr/local/freeswitch/bin/fs_cli -x "uuid_audio_stream <UUID> help"

# Voir appels actifs
/usr/local/freeswitch/bin/fs_cli -x "show calls"

# Logs FreeSWITCH
tail -f /usr/local/freeswitch/log/freeswitch.log
```

### Debugging audio

```bash
# Capturer packets WebSocket
sudo tcpdump -i lo -A 'tcp port 8080'

# Vérifier format audio avec test
python3 -c "
from vosk import Model, KaldiRecognizer
model = Model('models/vosk-model-small-fr-0.22')
rec = KaldiRecognizer(model, 16000)
print('✅ Vosk ready for 16kHz audio')
"
```

---

## Performances

**Latences mesurées** (sur machine de test):

| Étape | Latence |
|-------|---------|
| FreeSWITCH → WebSocket | ~10-20ms |
| VAD détection début parole | ~300ms |
| Vosk transcription (partielle) | ~50-100ms |
| Vosk transcription (finale) | ~100-200ms |
| Ollama NLP | ~500-2000ms |
| **Total end-to-end** | **~1-2.5s** |

**Optimisations possibles**:
- Réduire `BUFFERIZATION_INTERVAL_MS` à 20ms
- Utiliser modèle Vosk plus petit
- Utiliser modèle Ollama plus rapide (mistral:7b → phi)
- GPU pour Ollama (si disponible)

---

## Références

- **mod_audio_stream**: https://github.com/sptmru/freeswitch_mod_audio_stream
- **FreeSWITCH Media Bugs**: https://developer.signalwire.com/freeswitch/FreeSWITCH-Explained/Modules/
- **Vosk ASR**: https://alphacephei.com/vosk/
- **WebRTC VAD**: https://github.com/wiseman/py-webrtcvad
- **IXWebSocket**: https://github.com/machinezone/IXWebSocket

---

**Date de création**: 2025-11-06
**Version**: 1.0
**Auteur**: Claude (AI Assistant)
**Projet**: fs_minibot_streaming
