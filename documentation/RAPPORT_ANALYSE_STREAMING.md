# Rapport d'Analyse - Streaming Audio FreeSWITCH + Whisper
**Date:** 2025-11-16
**Objectif:** Implémenter streaming audio temps réel pour barge-in et transcription

---

## 📋 RÉSUMÉ EXÉCUTIF

### ✅ CE QUI FONCTIONNE:
- **mod_audio_fork** compilé et installé sur FreeSWITCH ✅
- **WebSocket** serveur Python opérationnel ✅
- **Faster-Whisper GPU** s'initialise correctement ✅
- **Frames audio** reçus en continu (640 bytes @ 50fps) ✅

### ❌ PROBLÈMES BLOQUANTS:
1. **Direction audio INCORRECTE** - Capture silence au lieu de voix client
2. **Crash cuDNN** - Faster-Whisper crash pendant transcription finale
3. **Version novembre NON FONCTIONNELLE** - Code désactivé car mod_audio_fork manquait

---

## 🔍 DÉCOUVERTES RECHERCHE WEB

### 1. mod_audio_fork vs mod_audio_stream

**mod_audio_fork** (Drachtio/Jambonz):
- Module **CUSTOM** nécessitant compilation FreeSWITCH avec libwebsockets
- Utilisé en production par Jambonz
- Format: **L16 PCM** (Linear 16-bit)
- **Mix types supportés:**
  - `read` - Inbound audio channel (caller)
  - `write` - Outbound audio channel (robot TTS)
  - `mixed` ou `stereo` - Both channels

**mod_audio_stream** (Alternative):
- Module **similaire** à mod_audio_fork
- Commande: `uuid_audio_stream <uuid> start <wss-url> <mix-type> <sampling-rate>`
- Exemple: `uuid_audio_stream UUID start ws://... stereo 8k`

**Syntaxe drachtio/Jambonz:**
```javascript
await ep.forkAudioStart({
  wsUrl: 'ws://stt-service:8080/transcribe',
  mixType: 'mono',        // Caller audio only
  sampling: '16k',
  metadata: { callId, language }
});
```

### 2. Configuration Audio Direction

**Recherche web findings:**
- **Jambonz**: Utilise `mixType: "mono"` pour audio caller uniquement
- **WebSocket subprotocol**: `audio.drachtio.org`
- **Format audio**: 16-bit PCM, sample rates: 8k, 16k, 24k, 48k, 64k
- **Frames:** Binaires, pas de header, stream continu

### 3. Whisper Streaming Solutions

#### **UFAL whisper_streaming** (GitHub: ufal/whisper_streaming)
- Implémentation streaming **officiellement reconnue**
- Backend recommandé: **faster-whisper**
- **Local agreement policy** avec self-adaptive latency
- ✅ Production-ready

#### **WhisperLive** (GitHub: collabora/WhisperLive)
- Backends: faster_whisper, tensorrt, openvino
- WebSocket server intégré
- Latence: ~100-300ms

#### **VoiceStreamAI** (GitHub: alesaccoia/VoiceStreamAI)
- WebSocket + VAD + Whisper
- Near real-time transcription
- Architecture similaire à notre test

**CONCLUSION RECHERCHE:** Faster-Whisper est le backend **recommandé** pour streaming, mais nécessite gestion VAD externe

---

## 📦 ANALYSE CODE NOVEMBRE (streaming_asr.py)

### Architecture Trouvée

**Fichier:** `documentation/code_archive_novembre/streaming_asr.py`
**Date:** 8 novembre 2025

**Stack technique:**
```python
# Services utilisés
- WebRTC VAD (mode 2) - Détection parole/silence
- Vosk ASR - Transcription streaming (PAS Whisper!)
- WebSocket server (port 8080)
- Callbacks async pour barge-in
```

**Configuration VAD:**
```python
self.vad = webrtcvad.Vad(2)              # Mode 2 = balance qualité/réactivité
self.sample_rate = 16000                  # 16kHz
self.frame_duration_ms = 30               # 30ms frames
self.silence_threshold = 0.8              # 800ms silence = fin parole
self.speech_start_threshold = 0.5         # 500ms parole = début détecté
```

**Modèle:** Vosk (CPU-only, léger, pas de GPU requis)

### État de l'Implémentation Novembre

**Fichier:** `documentation/code_archive_novembre/robot_freeswitch_nov6.py`

**Fonction `_enable_audio_fork()` - LIGNE 680-690:**
```python
def _enable_audio_fork(self, call_uuid: str):
    """Active le streaming audio vers le serveur WebSocket"""
    # TODO: uuid_audio_fork n'existe pas dans FreeSWITCH standard
    # Options pour streaming audio:
    # 1. mod_audio_fork (nécessite compilation custom)
    # 2. mod_avmd + mod_event_socket
    # 3. uuid_record + transcription post-call
    #
    # Pour l'instant: mode non-streaming (record + transcribe après)
    logger.debug(f"[{call_uuid[:8]}] Audio fork disabled (not supported yet)")
    return
```

**Code commenté (ligne 698):**
```python
# cmd = f"uuid_audio_fork {call_uuid} start {websocket_url}"
#                                          ^^^^^
#                                          AUCUN paramètre mono/read/stereo!
```

**⚠️ CONCLUSION CRITIQUE:**
- Leur version **NE MARCHAIT PAS** en novembre
- mod_audio_fork **n'était PAS installé** à l'époque
- Fonction **désactivée** → mode file-based utilisé
- Pas de paramètre direction audio dans leur code

---

## 🧪 RÉSULTATS TEST 2025-11-16

### Test Effectué

**Fichier:** `test_whisper_streaming_call.py`
**Commande:** `uuid_audio_fork {uuid} start ws://127.0.0.1:8765/stream/{uuid} mono 16k`

### Résultats

#### ✅ Succès:
1. **mod_audio_fork activé:** `+OK Success`
2. **WebSocket connecté:** Handshake réussi, connection OPEN
3. **Faster-Whisper GPU init:** Modèle chargé sans erreur
4. **Frames reçus:** ~450 frames en 10 secondes (correct pour 50fps)

#### ❌ Échecs:
1. **Direction audio:**
   - Tous frames: `ff ff ff ff` (silence/bruit)
   - RMS: 0.95 (quasi-silence)
   - **ALORS QUE** client a parlé ("c'est moi Richard")
   - **DIAGNOSTIC:** Mode `mono` capture mauvais leg ou silence

2. **Crash cuDNN:**
   ```
   Unable to load libcudnn_ops.so.9.1.0
   Invalid handle. Cannot load symbol cudnnCreateTensorDescriptor
   [Exit code: 134 - SIGABRT]
   ```
   - Crash pendant transcription finale
   - Whisper init OK, mais crash sur transcription avec VAD

3. **VAD Whisper filtre tout:**
   - VAD détecte 100% silence
   - 0 transcription générée
   - Buffer vidé systématiquement

---

## 🔧 SOLUTIONS POSSIBLES

### Option A: Tester Différents Mix Types mod_audio_fork

**Hypothèse:** `mono` capture mauvais leg

**Tests à faire:**
```bash
# Test 1: read (inbound uniquement)
uuid_audio_fork {uuid} start ws://... read 16k

# Test 2: mixed (les 2 legs)
uuid_audio_fork {uuid} start ws://... mixed 16k

# Test 3: stereo (2 channels séparés)
uuid_audio_fork {uuid} start ws://... stereo 16k
```

**Attentes:**
- `read` devrait capturer **UNIQUEMENT** voix client
- `mixed` capturera robot + client (à filtrer côté serveur)
- `stereo` donnera 2 channels séparés

### Option B: Utiliser Vosk au lieu de Whisper

**Avantages:**
- ✅ Comme version novembre (éprouvé)
- ✅ Pas de GPU → pas de cuDNN crash
- ✅ Latence plus faible (~50-100ms vs 200-500ms)
- ✅ Pas d'hallucinations
- ✅ Modèle léger (CPU suffisant)

**Inconvénients:**
- ❌ Précision inférieure à Whisper
- ❌ Moins de langues supportées
- ❌ Pas de ponctuation automatique

**Implémentation:**
```python
from vosk import Model, KaldiRecognizer

model = Model("models/vosk-model-fr-0.22")
recognizer = KaldiRecognizer(model, 16000)

# Streaming
for audio_chunk in stream:
    if recognizer.AcceptWaveform(audio_chunk):
        result = json.loads(recognizer.Result())
        text = result["text"]  # Transcription finale
    else:
        partial = json.loads(recognizer.PartialResult())
        text = partial["partial"]  # Transcription partielle
```

### Option C: Fixer cuDNN pour Whisper

**Problème identifié:**
- cuDNN 9.x incompatible avec certaines opérations Faster-Whisper
- Crash spécifique sur `cudnnCreateTensorDescriptor`

**Solutions:**
1. **Downgrade cuDNN 9.x → 8.x**
   ```bash
   pip uninstall nvidia-cudnn-cu12
   pip install nvidia-cudnn-cu12==8.9.7.29
   ```

2. **Désactiver VAD Whisper** (cause probable du crash)
   ```python
   segments, info = self.model.transcribe(
       audio,
       language="fr",
       vad_filter=False,  # ← Désactiver VAD
       beam_size=1
   )
   ```

3. **Utiliser CPU pour transcription** (lent mais stable)
   ```python
   model = WhisperModel("small", device="cpu", compute_type="int8")
   ```

### Option D: Hybrid - Vosk streaming + Whisper final

**Concept:**
- **Vosk** pour détections temps réel (barge-in, VAD)
- **Whisper** pour transcription finale précise (post-call)

**Avantages:**
- ✅ Réactivité Vosk (<100ms)
- ✅ Précision Whisper (offline)
- ✅ Pas de cuDNN crash en live
- ✅ Best of both worlds

---

## 📊 COMPARAISON SOLUTIONS

| Critère | A: Fix mod_audio_fork | B: Vosk streaming | C: Fix cuDNN Whisper | D: Hybrid |
|---------|----------------------|-------------------|---------------------|-----------|
| **Complexité** | Faible (test params) | Moyenne | Élevée | Élevée |
| **Temps impl.** | 1-2h | 4-6h | 2-4h | 6-10h |
| **Latence** | 200-500ms | 50-100ms | 200-500ms | 50-100ms (live) |
| **Précision** | Élevée (Whisper) | Moyenne (Vosk) | Élevée (Whisper) | Élevée (Whisper offline) |
| **Stabilité** | ? (à tester) | ✅ Éprouvé | ❌ Crash cuDNN | ✅ Stable |
| **GPU requis** | ✅ Oui | ❌ Non | ✅ Oui | ✅ Oui (offline seulement) |
| **Production ready** | 🟡 Inconnu | ✅ Oui | ❌ Non (instable) | ✅ Oui |

---

## 🎯 RECOMMANDATION FINALE

### Plan d'Action Recommandé

#### **PHASE 1: Tests Direction Audio (1-2h)** ⭐ PRIORITÉ

**Objectif:** Identifier le bon mix type

**Actions:**
1. Modifier `test_whisper_streaming_call.py`
2. Tester séquentiellement: `read`, `mixed`, `stereo`
3. Pour chaque test:
   - Appeler, parler "c'est moi Richard"
   - Vérifier RMS audio (>500 = parole détectée)
   - Vérifier transcriptions

**Critère succès:** RMS >500 ET transcriptions correctes

#### **PHASE 2: Migration Vosk (4-6h)** 🔄

**SI Phase 1 échoue OU instabilité Whisper:**

**Actions:**
1. Installer Vosk: `pip install vosk`
2. Télécharger modèle français: `vosk-model-fr-0.22`
3. Adapter `test_whisper_streaming_call.py` pour Vosk
4. Tester streaming complet

**Avantages:**
- Architecture éprouvée (novembre)
- Pas de cuDNN crash
- Latence optimale

#### **PHASE 3: Intégration Production (2-4h)** ✅

**Après succès Phase 1 OU 2:**

**Actions:**
1. Créer `system/services/live_streaming_stt.py`
2. Intégrer dans `robot_freeswitch.py`:
   - Démarrer serveur WebSocket au boot
   - Activer mod_audio_fork par call
   - Callbacks barge-in
3. Tests charge (multiple calls)
4. Documentation

---

## 💡 DÉCISION ARCHITECTURE

### Si mod_audio_fork `read` mode FONCTIONNE:

**→ GARDER Whisper** (précision maximale)
- Fixer cuDNN (downgrade 8.x ou désactiver VAD)
- Production avec Faster-Whisper GPU
- Latence acceptable (~200-300ms)

### Si mod_audio_fork direction PROBLÉMATIQUE:

**→ MIGRER vers Vosk** (stabilité maximale)
- Comme novembre (architecture éprouvée)
- CPU-only (pas de cuDNN)
- Latence optimale (~50-100ms)
- Sacrifice précision pour réactivité

### Si TOUT échoue:

**→ REVENIR file-based optimisé**
- Version production actuelle marche
- Optimiser barge-in (VAD + snapshots 100ms)
- Abandonner streaming pour v4

---

## 📝 PROCHAINES ÉTAPES IMMÉDIATES

1. **Tester `read` mode** - 15 min
2. **Si OK:** Fixer cuDNN - 1h
3. **Si KO:** Tester `mixed` et `stereo` - 30 min
4. **Si tous KO:** Basculer Vosk - 4h

**Décision:** À prendre après tests Phase 1

---

## 📚 RÉFÉRENCES

### Documentation
- mod_audio_fork README: https://github.com/drachtio/drachtio-freeswitch-modules
- Jambonz listen verb: https://www.jambonz.org/docs/webhooks/listen/
- UFAL whisper_streaming: https://github.com/ufal/whisper_streaming
- Faster-Whisper: https://github.com/SYSTRAN/faster-whisper
- Vosk: https://alphacephei.com/vosk/

### Fichiers Code
- `documentation/code_archive_novembre/streaming_asr.py` - Architecture Vosk
- `documentation/code_archive_novembre/robot_freeswitch_nov6.py` - Intégration (désactivée)
- `test_whisper_streaming_call.py` - Test actuel

---

**Rapport créé:** 2025-11-16 12:45
**Auteur:** Analyse approfondie streaming audio
**Statut:** En attente décision tests Phase 1
