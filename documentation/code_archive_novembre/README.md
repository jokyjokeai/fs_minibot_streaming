# Code Archive - Version Streaming Novembre 2024

## Source
Fichiers extraits de `~/Desktop/fs_minibot_streaming_2.zip` (archive du 9 novembre 2025)

## Fichiers

### 1. streaming_asr.py
- **Date:** 8 novembre 2025, 22:07
- **Taille:** 17,768 octets
- **Description:** Service streaming ASR avec WebSocket + VAD + Vosk
- **Version:** V2 (stable)
- **Caractéristiques:**
  - Serveur WebSocket port 8080
  - WebRTC VAD mode 2
  - Vosk KaldiRecognizer pour transcription streaming
  - Callbacks: speech_start, speech_end, transcription (partial/final)
  - Support barge-in
  - Méthode `reset_recognizer()` présente

### 2. streaming_asr_v3.py
- **Date:** 9 novembre 2025, 11:39
- **Taille:** 19,912 octets
- **Description:** Version améliorée de streaming_asr.py
- **Version:** V3 (expérimental)
- **Améliorations:**
  - ❌ SUPPRIMÉ `reset_recognizer()` (causait crash Vosk)
  - ✅ Calcul durée de parole précis
  - ✅ Format événements modernisé (`type` au lieu de `event`)
  - ✅ Mode MONO optimisé (SMBF_READ_STREAM)
  - ✅ Durée incluse dans événements speech_end et transcription

**Différences format événements:**
```python
# V2:
{"event": "speech_start"}
{"event": "transcription", "type": "final", "text": "..."}

# V3:
{"type": "speech_start"}
{"type": "transcription", "transcription_type": "final", "text": "...", "duration": 2.5}
```

### 3. vosk_stt.py
- **Date:** 30 octobre 2025, 10:37
- **Taille:** 8,529 octets
- **Description:** Service STT Vosk (batch + streaming)
- **Fonctionnalités:**
  - `create_recognizer(sample_rate)` - Créer KaldiRecognizer
  - `accept_waveform(recognizer, audio_data)` - Feed audio chunk
  - `get_result(recognizer)` - Transcription finale
  - `get_partial_result(recognizer)` - Transcription partielle
  - `transcribe_file(audio_file)` - Transcription fichier WAV complet
  - Support 8kHz et 16kHz

### 4. robot_freeswitch_nov6.py
- **Date:** 6 novembre 2025, 13:43
- **Taille:** 65,639 octets (1,625 lignes)
- **Description:** Robot FreeSWITCH compatible avec streaming_asr.py V2
- **Intégration streaming:**
  - Import: `from system.services.streaming_asr import streaming_asr`
  - Démarrage serveur WebSocket dans thread daemon
  - Callbacks: `_handle_streaming_event()` pour speech_start/end/transcription
  - Barge-in: `uuid_break` sur speech_start

**⚠️ PROBLÈME CRITIQUE IDENTIFIÉ:**
La fonction `_enable_audio_fork()` (ligne 680-711) est **DÉSACTIVÉE** avec ce commentaire:
```python
# TODO: uuid_audio_fork n'existe pas dans FreeSWITCH standard
# Options pour streaming audio:
# 1. mod_audio_fork (nécessite compilation custom)
# 2. mod_avmd + mod_event_socket
# 3. uuid_record + transcription post-call
#
# Pour l'instant: mode non-streaming (record + transcribe après)
```

**NOTE:** mod_audio_fork est maintenant INSTALLÉ ET COMPILÉ sur le système actuel.

## Architecture Système

```
FreeSWITCH (mod_audio_fork)
    │
    ├─ Appel entrant/sortant
    │
    └─> robot_freeswitch.py
        │
        ├─> _init_streaming_session()
        │   ├─ streaming_asr.register_callback()
        │   └─ _enable_audio_fork() [À ACTIVER]
        │
        └─> _handle_streaming_event()
            ├─ speech_start → uuid_break (barge-in)
            ├─ speech_end → fin parole
            └─ transcription → analyse intent

streaming_asr.py (WebSocket Server)
    │
    ├─ WebSocket: ws://127.0.0.1:8080/stream/{UUID}
    │
    ├─> WebRTC VAD (30ms frames)
    │   ├─ Silence threshold: 0.8s
    │   └─ Speech start: 0.5s
    │
    ├─> Vosk ASR (KaldiRecognizer)
    │   ├─ Sample rate: 16000 Hz
    │   ├─ Model: vosk-model-fr
    │   └─ Transcription streaming (partial + final)
    │
    └─> Callbacks async
        ├─ speech_start
        ├─ speech_end
        └─ transcription (final/partial)
```

## Utilisation

### Choix de version

**Utiliser streaming_asr.py (V2) si:**
- Stabilité prioritaire
- Format événements standard souhaité
- Besoin de `reset_recognizer()`

**Utiliser streaming_asr_v3.py si:**
- Performance/robustesse prioritaire
- Crash Vosk avec reset_recognizer
- Besoin calcul durée parole précis
- Mode MONO optimisé requis

### Intégration

1. Copier fichier choisi dans `system/services/`
2. Copier `vosk_stt.py` dans `system/services/`
3. Adapter `robot_freeswitch.py`:
   - Activer `_enable_audio_fork()` (mod_audio_fork disponible maintenant)
   - Vérifier callbacks compatibles avec format événements
4. Installer modèle Vosk français
5. Configurer FreeSWITCH pour mod_audio_fork

## Prochaines étapes

1. ✅ Fichiers extraits et documentés
2. ⏳ Régler CUDA/cuDNN
3. ⏳ Tester streaming isolément (appel vide + transcription)
4. ⏳ Décider architecture finale selon résultats

---

**Archive créée:** 2025-11-16
**Source:** fs_minibot_streaming_2.zip (9 nov 2025)
