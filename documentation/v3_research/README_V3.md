# V3 - STREAMING APPROACH pour Barge-In

## 🎯 Objectif

Tester l'approche **STREAMING** avec `mod_audio_stream` + **WebSocket** pour résoudre le problème de barge-in detection pendant concurrent playback.

## ❌ Problème Original (FILE-BASED)

```
uuid_record read + uuid_broadcast concurrent
= Media bug ordering conflict
= 0% audio capturé du client
```

**Preuve**: Tests `test_READ_LEG_FIX.log` et `test_CLIENT_ONLY.log` montrent SILENCE complete ou crash.

## ✅ Solution V3 (STREAMING)

```
uuid_audio_stream → WebSocket → Real-time STT → Barge-in detection
+ uuid_broadcast (playback concurrent)
= Full-duplex + Pas de media bug conflicts
```

---

## 🏗️ Architecture V3

### Flux de données

```
FreeSWITCH (mod_audio_stream)
    |
    |-- uuid_audio_stream start ws://127.0.0.1:8080/stream/<uuid>
    |      |
    |      v
    |   WebSocket Server (port 8080)
    |      |
    |      v
    |   AudioStreamSession
    |      |-- Buffer L16 PCM frames (16kHz mono)
    |      |-- Stream → Faster-Whisper STT
    |      |-- VAD detection (speech > 1.5s)
    |      |-- Barge-in callback → Robot
    |
    |-- uuid_broadcast <audio_file> (concurrent playback)
    |
Robot
    |-- Poll barge-in_events queue
    |-- If barge-in detected → uuid_break (stop playback)
```

### Composants Créés

1. **`system/services/websocket_audio_server.py`**
   - WebSocket server asyncio (port 8080)
   - Gère multiple sessions concurrentes (`AudioStreamSession`)
   - Buffering audio + real-time STT
   - Callback async pour notifier robot

2. **`system/robot_freeswitch_v3.py`**
   - Version SIMPLIFIÉE du robot actuel
   - Démarre WebSocket server en background thread
   - PHASE 2 avec `_execute_phase_playing_v3()`:
     - `uuid_audio_stream` pour streaming audio
     - `uuid_broadcast` pour playback
     - Poll `barge_in_events` queue
     - `uuid_break` pour stopper playback

3. **`test_real_call_v3.py`**
   - Script de test identique à `test_real_call.py`
   - Importe depuis `V3.system.robot_freeswitch_v3`
   - Logs dans console

---

## 🧪 Tests

### Test 1: Baseline (pas de parole)

```bash
./venv/bin/python3 V3/test_real_call_v3.py
```

**Attendu:**
- WebSocket connection établie
- Audio joué complètement
- Pas de barge-in détecté
- Clean hangup

### Test 2: Phrase courte (< 1.5s)

**Action:** Dire "oui" quand audio joue

**Attendu:**
- Speech détecté mais duration < 1.5s
- Pas de barge-in trigger
- Audio joué jusqu'au bout

### Test 3: Phrase longue (> 1.5s)

**Action:** Parler pendant 2-3 secondes ("Oui allô j'écoute, je suis intéressé...")

**Attendu:**
- Speech détecté, duration > 1.5s
- **BARGE-IN TRIGGERED!**
- Playback stoppé immédiatement (uuid_break)
- Transcription récupérée

---

## 📊 Comparaison FILE-BASED vs STREAMING

| Aspect | FILE-BASED (actuel) | STREAMING (V3) |
|--------|---------------------|----------------|
| **Commande FreeSWITCH** | `uuid_record read` | `uuid_audio_stream start` |
| **Transport** | File I/O (RAW) | WebSocket (L16 PCM) |
| **Latency** | ~500ms (snapshots toutes les 0.3s) | ~100-300ms (real-time frames) |
| **Concurrent playback** | ❌ Media bug conflict (0% audio) | ✅ Full-duplex supporté |
| **Complexité** | Moyenne (threads + file monitoring) | Élevée (asyncio + WebSocket) |
| **Dependencies** | Standard (ffmpeg, file I/O) | `websockets`, mod_audio_stream |
| **Production** | Jambonz, Retell, Deepgram | ✅ Standard industrie |

---

## 🔧 Prérequis

### mod_audio_stream (déjà installé ✅)

Vérifier:
```bash
/usr/local/bin/fs_cli -x "module_exists mod_audio_stream"
```

Si pas installé:
```bash
cd /usr/local/src
sudo git clone https://github.com/amigniter/mod_audio_stream.git
cd mod_audio_stream
sudo git submodule update --init --recursive
export PKG_CONFIG_PATH=/usr/local/freeswitch/lib/pkgconfig:$PKG_CONFIG_PATH
sudo mkdir build && cd build
sudo cmake -DCMAKE_BUILD_TYPE=Release -DUSE_TLS=ON ..
sudo make && sudo make install
```

Puis ajouter dans `/usr/local/freeswitch/conf/vanilla/autoload_configs/modules.conf.xml`:
```xml
<load module="mod_audio_stream"/>
```

Restart FreeSWITCH:
```bash
sudo systemctl restart freeswitch
```

### Python Dependencies

Déjà installées:
- `websockets==15.0.1` ✅
- `faster-whisper` ✅
- `numpy` ✅

---

## 🚀 Lancement Test

```bash
# Vérifier que FreeSWITCH est running
sudo systemctl status freeswitch

# Vérifier mod_audio_stream chargé
/usr/local/bin/fs_cli -x "module_exists mod_audio_stream"

# Lancer test V3
./venv/bin/python3 V3/test_real_call_v3.py
```

**Observer:**
1. Logs d'init robot V3
2. `WebSocket Audio Server running on ws://127.0.0.1:8080`
3. Appel vers 33743130341
4. Logs PHASE 2 STREAMING
5. Si tu parles > 1.5s → `⚡ BARGE-IN TRIGGERED!`

---

## 📝 Logs Attendus

### Success Case (Barge-In Détecté)

```
[abc12345] Starting audio stream: uuid_audio_stream abc12345 start ws://127.0.0.1:8080/stream/abc12345 mono 16k
[abc12345] WebSocket connection established from ('127.0.0.1', 54321)
[abc12345] AudioStreamSession created (16kHz mono, L16 PCM)
[abc12345] Starting playback: uuid_broadcast abc12345 /path/to/hello.wav aleg
🗣️ [abc12345] Speech START at 1.2s: 'oui allô'
🗣️ [abc12345] Speech continues: 'oui allô j'écoute'
⚡ [abc12345] BARGE-IN TRIGGERED at 2.1s! (speech_duration: 1.7s, text: 'oui allô j'écoute je suis')
[abc12345] BARGE-IN CALLBACK received: text='oui allô j'écoute je suis', duration=1.7s
⚡ [abc12345] BARGE-IN DETECTED at 2.1s! Stopping playback...
[abc12345] Playback stopped via uuid_break
[abc12345] PHASE 2 RESULT: Barge-in - 'oui allô j'écoute je suis'
```

### Failure Cases

**WebSocket connection failed:**
```
[abc12345] Starting audio stream: uuid_audio_stream ...
ERROR: WebSocket connection refused
```
→ Vérifier que WebSocket server est running (check logs init)

**mod_audio_stream not loaded:**
```
-ERR uuid_audio_stream Command not found!
```
→ Installer mod_audio_stream (voir Prérequis)

**No audio frames received:**
```
[abc12345] WebSocket connection established
[abc12345] AudioStreamSession created
[WARNING] No audio frames received after 5s
```
→ Vérifier format audio L16 PCM dans mod_audio_stream config

---

## 🎓 Lessons from Web Research

### Jambonz Implementation

```javascript
session.config({
  bargeIn: {
    enable: true,
    input: ['speech']
  }
})
```

- Event `tts:user_interrupt` quand client parle
- `clearTtsTokens()` stoppe TTS immédiatement
- **TRUE CONCURRENT**: TTS stream + STT listen en parallèle

### mod_audio_stream Documentation

```
uuid_audio_stream <uuid> start <ws-url> <mix-type> <sampling-rate>

mix-type: mono (client only), mixed (both), stereo (separate channels)
sampling-rate: 8k or 16k
format: L16 PCM (Linear 16-bit)
```

- **Full-duplex**: "playback runs independently while streaming continues"
- WebSocket protocol: RFC-6455 compliant
- Per-message deflate compression enabled

### Industry Standard (2024)

- Retell AI: Full-duplex avec barge-in detection, WebRTC audio
- Deepgram Voice Agent API: Sub-500ms latency, model-level barge-in optimization
- Voicegain: `mod_voicegain` avec barge-in support, WebSocket streaming

**Consensus:** STREAMING est la méthode standard pour concurrent playback + barge-in.

---

## 🔬 Next Steps

### Si ça marche ✅

1. Migrer PHASE 1 (AMD) vers V3
2. Migrer PHASE 3 (WAITING) vers V3
3. Ajouter DB integration
4. Performance testing (latency benchmarks)
5. Load testing (concurrent calls)
6. Production deployment

### Si ça ne marche pas ❌

1. **Debug WebSocket**: Vérifier connexion FreeSWITCH → WebSocket
2. **Debug audio frames**: Logger raw bytes received
3. **Debug STT**: Vérifier audio format (L16 PCM 16kHz mono)
4. **Fallback**: Essayer media bug ordering fix avec uuid_record (flag 'f')

---

## 📚 Sources

### Documentation Locale

- `/documentation/STREAMING_AUDIO_WEBSOCKET.md` - Implémentation streaming complète
- `/documentation/VAD_3_MODES_ARCHITECTURE.md` - Best practices barge-in
- `/documentation/IMPLEMENTATION_REPORT.md` - Performance metrics

### Web Research

- Jambonz TTS Streaming: https://docs.jambonz.org/guides/features/tts-streaming
- mod_audio_stream GitHub: https://github.com/amigniter/mod_audio_stream
- Deepgram FreeSWITCH integration
- Voicegain real-time transcription
- FreeSWITCH Media Bugs (ordering issues)

---

## 🎯 Success Criteria

- ✅ WebSocket server starts without errors
- ✅ FreeSWITCH connects to WebSocket (uuid_audio_stream)
- ✅ Audio frames received in WebSocket (L16 PCM)
- ✅ STT transcription works in real-time
- ✅ Speech detection works (> 1.5s trigger)
- ✅ Barge-in callback received by robot
- ✅ uuid_break stops playback immediately
- ✅ Final transcription récupérée

**Goal:** Détecter le CLIENT qui parle pendant que le ROBOT joue de l'audio.

---

**Version:** V3.0.0
**Date:** 2025-11-13
**Author:** MiniBotPanel Team
**Status:** 🧪 EXPERIMENTAL - Testing Phase
