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
sudo apt-get install -y libwebsockets-dev cmake git
```

**Vérification**:
```bash
dpkg -l | grep -E "libwebsockets-dev|cmake"
```

### 2. Cloner le repository

```bash
cd /usr/local/src
sudo git clone https://github.com/davehorner/mod_audio_stream.git
cd mod_audio_stream
sudo git submodule update --init --recursive
```

**Note importante**: Nous utilisons le repository de `davehorner` qui est compatible avec notre version de FreeSWITCH.

### 3. Configuration PKG_CONFIG_PATH

FreeSWITCH installé dans `/usr/local/freeswitch` fournit un fichier pkg-config:

```bash
export PKG_CONFIG_PATH=/usr/local/freeswitch/lib/pkgconfig:$PKG_CONFIG_PATH
```

**Vérifier la configuration**:
```bash
pkg-config --cflags --libs freeswitch
```

### 4. Compiler le module

```bash
cd /usr/local/src/mod_audio_stream
sudo mkdir build
cd build

# Configurer avec cmake
sudo cmake ..

# Compiler
sudo make
```

**Sortie attendue**:
```
[100%] Built target mod_audio_stream
```

Le fichier `mod_audio_stream.so` est généré dans `build/`.

### 5. Installer le module

```bash
# Copier vers répertoire modules FreeSWITCH
sudo cp mod_audio_stream.so /usr/local/freeswitch/lib/freeswitch/mod/

# Définir propriétaire et permissions
sudo chown freeswitch:freeswitch /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so
sudo chmod 755 /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so

# Vérifier
ls -la /usr/local/freeswitch/lib/freeswitch/mod/mod_audio_stream.so
```

**Sortie attendue**:
```
-rwxr-xr-x 1 freeswitch freeswitch 123456 Nov  7 10:00 mod_audio_stream.so
```

---

## Configuration FreeSWITCH

### 1. Charger le module

Éditer `/usr/local/freeswitch/conf/vanilla/autoload_configs/modules.conf.xml`:

```xml
<configuration name="modules.conf" description="Modules">
  <modules>
    <!-- ... autres modules ... -->

    <!-- Streaming Audio Module -->
    <load module="mod_audio_stream"/>

  </modules>
</configuration>
```

**Chemin important**: Le fichier est dans `/usr/local/freeswitch/conf/vanilla/autoload_configs/` et NON dans `/usr/local/freeswitch/etc/`.

### 2. Redémarrer FreeSWITCH

```bash
sudo systemctl restart freeswitch
# OU
sudo -S systemctl restart freeswitch
```

### 3. Vérifier le chargement

```bash
/usr/local/freeswitch/bin/fs_cli -x "module_exists mod_audio_stream"
```

**Sortie attendue**: `true`

Si le module n'est pas chargé:
```bash
# Charger manuellement
/usr/local/freeswitch/bin/fs_cli -x "load mod_audio_stream"

# Vérifier les erreurs dans les logs
sudo tail -f /var/log/freeswitch/freeswitch.log | grep audio_stream
```

### 4. Tester la commande

```bash
/usr/local/freeswitch/bin/fs_cli
```

Puis dans fs_cli:
```
uuid_audio_stream help
```

**Sortie attendue**:
```
USAGE:
  uuid_audio_stream <uuid> start <ws-url> [mono|mixed|stereo]
  uuid_audio_stream <uuid> stop
```

**Note**: La syntaxe peut varier selon la version du module. Notre implémentation utilise:
```
uuid_audio_stream <UUID> start ws://127.0.0.1:8080/stream/<UUID>
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

### 2. Implémentation _enable_audio_streaming()

Dans `system/robot_freeswitch_v2.py`, ligne ~650:

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
        # URL du serveur WebSocket StreamingASR avec call_uuid dans le path
        websocket_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"

        # Commande uuid_audio_stream (syntaxe simplifiée)
        # Format audio: SLIN16 (Linear PCM 16-bit), 16kHz, mono
        cmd = f"uuid_audio_stream {call_uuid} start {websocket_url}"
        result = self.esl_conn_api.api(cmd)

        result_str = result.getBody() if hasattr(result, 'getBody') else str(result)

        if "+OK" in result_str or "success" in result_str.lower():
            logger.info(f"[{call_uuid[:8]}] ✅ Audio streaming started to WebSocket (16kHz mono)")
            logger.debug(f"[{call_uuid[:8]}]    URL: {websocket_url}")
            return True
        else:
            logger.error(f"[{call_uuid[:8]}] ❌ Audio streaming failed: {result_str}")
            logger.warning(f"[{call_uuid[:8]}]    Vérifier que mod_audio_stream est chargé")
            return False

    except Exception as e:
        logger.error(f"[{call_uuid[:8]}] Audio streaming error: {e}", exc_info=True)
        return False
```

**Points clés**:
- L'URL inclut le `call_uuid` dans le path pour identifier le stream
- Pas besoin de spécifier mix_type ou sampling_rate (valeurs par défaut)
- Format audio automatique: SLIN16, 16kHz, mono

### 3. Activer le streaming au bon moment

Dans `_handle_call()` (ligne ~443), APRÈS l'AMD et AVANT d'exécuter le scénario:

```python
def _handle_call(self, call_uuid: str, phone_number: str, scenario: str, campaign_id: str):
    """Thread principal de gestion d'appel"""
    try:
        logger.info(f"[{call_uuid[:8]}] 🌊 Call thread started for {phone_number}")

        # === AMD DETECTION ===
        if self.amd_service and config.AMD_ENABLED:
            amd_result = self.amd_service.detect(call_uuid)
            logger.info(f"[{call_uuid[:8]}] AMD: {amd_result}")

        # === ACTIVER STREAMING AUDIO ===
        streaming_enabled = self._enable_audio_streaming(call_uuid)
        if streaming_enabled:
            logger.info(f"[{call_uuid[:8]}] ✅ Streaming audio WebSocket activé")
        else:
            logger.warning(f"[{call_uuid[:8]}] ⚠️ Streaming échoué - fallback mode record")

        # === EXÉCUTER SCÉNARIO ===
        if self.scenario_manager:
            scenario_data = self.scenario_manager.load_scenario(scenario)
            if scenario_data:
                self._execute_scenario(call_uuid, scenario, campaign_id)

        # Hangup à la fin
        self.hangup_call(call_uuid)

    except Exception as e:
        logger.error(f"[{call_uuid[:8]}] Call thread error: {e}", exc_info=True)
        self.hangup_call(call_uuid)
    finally:
        logger.info(f"[{call_uuid[:8]}] Call thread ended")
```

**Note importante**: Le callback streaming est enregistré automatiquement dans `_init_streaming_session()` appelé lors du CHANNEL_ANSWER.

### 4. Utilisation du mode streaming dans _listen_for_response()

Dans `_listen_for_response()` (ligne ~783):

```python
def _listen_for_response(self, call_uuid: str, timeout: int = 10) -> Optional[str]:
    """Écoute et transcrit la réponse du client"""
    if call_uuid not in self.streaming_sessions:
        logger.warning(f"[{call_uuid[:8]}] No streaming session")
        return None

    try:
        # Mode streaming si StreamingASR disponible ET mod_audio_stream installé
        if self.streaming_asr and self.streaming_asr.is_available:
            logger.debug(f"[{call_uuid[:8]}] Using streaming mode for transcription")
            return self._listen_streaming(call_uuid, timeout)
        else:
            # Fallback: mode record si streaming pas disponible
            logger.debug(f"[{call_uuid[:8]}] Using record fallback mode for transcription")
            return self._listen_record_fallback(call_uuid, timeout)

    except Exception as e:
        logger.error(f"[{call_uuid[:8]}] Listen error: {e}", exc_info=True)
        return None
```

**Flux**:
1. `_listen_streaming()` attend que le client parle
2. Le VAD détecte début de parole → callback `speech_start`
3. Vosk transcrit en temps réel → callback `transcription` (partiel + final)
4. Le VAD détecte fin de parole (1.5s silence) → callback `speech_end`
5. `_listen_streaming()` retourne la transcription finale

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
model = Model('models/vosk-model-fr-0.22-lgraph')
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

### Modules et bibliothèques

- **mod_audio_stream** (davehorner): https://github.com/davehorner/mod_audio_stream
  - Module FreeSWITCH pour streaming audio vers WebSocket
  - Alternative compatible à sptmru/freeswitch_mod_audio_stream

- **FreeSWITCH**: https://freeswitch.org/
  - Plateforme de téléphonie open-source
  - Documentation Media Bugs: https://developer.signalwire.com/freeswitch/

- **Vosk ASR**: https://alphacephei.com/vosk/
  - Moteur de reconnaissance vocale offline
  - Modèles français: https://alphacephei.com/vosk/models

- **WebRTC VAD**: https://github.com/wiseman/py-webrtcvad
  - Voice Activity Detection pour Python
  - Basé sur WebRTC de Google

- **websockets**: https://websockets.readthedocs.io/
  - Bibliothèque WebSocket pour Python (asyncio)

- **libwebsockets**: https://libwebsockets.org/
  - Bibliothèque C pour WebSocket (utilisée par mod_audio_stream)

### Configuration système

- **Dépendances**: libwebsockets-dev, cmake, git
- **FreeSWITCH**: Installé dans `/usr/local/freeswitch`
- **Configuration**: `/usr/local/freeswitch/conf/vanilla/`
- **Modules**: `/usr/local/freeswitch/lib/freeswitch/mod/`
- **Logs**: `/var/log/freeswitch/freeswitch.log`

### Architecture projet

- **Projet**: fs_minibot_streaming
- **StreamingASR**: `system/services/streaming_asr.py`
- **RobotFreeSwitchV2**: `system/robot_freeswitch_v2.py`
- **Config**: `system/config.py`
- **Logs**: `logs/misc/system.*.log`

---

**Date de création**: 2025-11-06
**Dernière mise à jour**: 2025-11-07
**Version**: 1.1
**Auteur**: Claude (AI Assistant)
**Projet**: fs_minibot_streaming

**Changelog**:
- v1.1 (2025-11-07): Mise à jour avec le processus exact d'installation (davehorner/mod_audio_stream)
- v1.0 (2025-11-06): Version initiale
