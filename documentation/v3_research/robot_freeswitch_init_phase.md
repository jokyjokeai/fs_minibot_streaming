# Robot FreeSWITCH V3 - Phase d'Initialisation

## Vue d'ensemble

La phase d'initialisation du Robot V3 prépare tous les services AI, le serveur WebSocket streaming, et effectue des tests de warmup pour éliminer les latences du premier appel.

**Durée typique**: 600-800ms (GPU CUDA) | 1500-2500ms (CPU)

**Architecture V3**: Streaming WebSocket + Real-time STT barge-in (remplace file-based uuid_record)

---

## Étapes d'Initialisation

### 0. Configuration & Connexion Base de Données

```python
from V3.system.config import config
from V3.system.database import SessionLocal
```

- Charge configuration depuis `.env` + defaults
- Test connexion PostgreSQL
- Vérifie que toutes les tables existent

**Logs attendus**:
```
✅ Database connection OK
```

---

### 1. Chargement Scenario & Theme Détection

```python
scenario_manager = ScenarioManager()
scenario = scenario_manager.load_scenario(scenario_name)
theme_file = scenario_manager.get_theme_file(scenario)
```

**Objectif**: Charger le scénario avant init robot pour détecter le theme_file (ex: `objections_finance`) et précharger les bonnes objections.

**Logs attendus**:
```
✅ Scenario charge: theme_file = 'objections_finance'
```

---

### 2. Initialisation Services AI

#### 2.1 Faster-Whisper STT (GPU/CPU Auto-détection)

```python
from V3.system.services.faster_whisper_stt import FasterWhisperSTT

self.stt_service = FasterWhisperSTT(
    model_name=config.FASTER_WHISPER_MODEL,
    device=config.FASTER_WHISPER_DEVICE,  # Auto-détecté: "cuda" ou "cpu"
    compute_type=config.FASTER_WHISPER_COMPUTE_TYPE
)
```

**Auto-détection GPU** (config.py:76):
```python
def _detect_gpu_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"  # ✅ GPU détecté
    except ImportError:
        pass
    return "cpu"  # Fallback CPU
```

**Logs attendus**:
```
INFO: Faster-Whisper initialized (model: base, device: cuda, compute: float16)
```

#### 2.2 AMD Service (Answering Machine Detection)

```python
from V3.system.services.amd_service import AMDService

self.amd_service = AMDService()
```

**Méthode**: Keywords matching pour détecter HUMAN vs MACHINE.

**Logs attendus**:
```
INFO: AMD Service initialized (keywords: bonjour, allô, oui, etc.)
```

#### 2.3 ObjectionMatcher (Theme-Based)

```python
from V3.system.objection_matcher import ObjectionMatcher

self.objection_matcher_default = ObjectionMatcher.load_objections_from_file(default_theme)
```

**Charge automatiquement**: `objections_general.py` + theme spécifique (ex: `objections_finance.py`)

**Logs attendus**:
```
INFO: Loaded 45 objections from 'objections_finance'
INFO: ObjectionMatcher ready with 45 objections
```

---

### 3. WebSocket Audio Server (NEW V3)

```python
from V3.system.services.websocket_audio_server import WebSocketAudioServer

self.ws_server = WebSocketAudioServer(
    stt_service=self.stt_service,
    barge_in_callback=self._on_barge_in_detected
)
```

**Démarrage en background thread**:
```python
self.ws_thread = threading.Thread(
    target=self._run_websocket_server,
    daemon=True,
    name="WebSocketServer"
)
self.ws_thread.start()
```

**Logs attendus**:
```
================================================================================
INITIALIZING WEBSOCKET AUDIO SERVER (STREAMING V3)
================================================================================
INFO: WebSocket Audio Server created (host: 127.0.0.1, port: 8080)
✅ WebSocket server running at ws://127.0.0.1:8080
   - Real-time audio streaming: ENABLED
   - Barge-in detection: ACTIVE
   - STT transcription: GPU-accelerated
```

**Pourquoi WebSocket en V3 ?**
- Remplace `uuid_record` (file-based) par `uuid_audio_stream` (streaming)
- Permet barge-in **en temps réel** (<100ms) via STT callbacks
- Pas besoin de WebRTC VAD (obsolète en V3)

---

### 4. WARMUP Tests (3/3)

#### WARMUP 1/3: Faster-Whisper GPU/CPU

**Objectif**: Éviter latence première transcription (GPU cold start ~2000ms → ~150ms après warmup)

```python
# Créer audio silence 1s (8000 frames @ 8kHz)
warmup_path = tempfile.mktemp(suffix='.wav')
with wave.open(warmup_path, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(8000)
    silence = struct.pack('<' + ('h' * 8000), *([0] * 8000))
    wf.writeframes(silence)

# Test transcription
result = self.stt_service.transcribe_file(warmup_path)
```

**Logs attendus**:
```
INFO: WARMUP 1/3: Faster-Whisper test transcription (device: CUDA)...
✅ WARMUP 1/3: GPU CUDA ready (147ms) - GPU is HOT!
```

**Si CPU**:
```
INFO: WARMUP 1/3: Faster-Whisper test transcription (device: CPU)...
✅ WARMUP 1/3: CPU ready (523ms) - CPU mode active
```

---

#### WARMUP 2/3: AMD Service

**Objectif**: Chauffer le système de détection AMD (keywords matching)

```python
test_text = "bonjour comment allez vous"
result = self.amd_service.analyze_response(test_text)
# Retourne: "human" (car keywords HUMAN détectés)
```

**Logs attendus**:
```
INFO: WARMUP 2/3: AMD Service test detection...
INFO: AMD WARMUP 2/3: Completed in 2.34ms - AMD is READY!
```

---

#### WARMUP 3/3: ObjectionMatcher

**Objectif**: Chauffer le fuzzy matching + keyword overlap

```python
# Test avec texte bidon (pas une vraie objection)
_ = self.objection_matcher_default.find_best_match(
    "test test test",
    silent=True  # ← Évite log "❌ Pas de match suffisant"
)
```

**Logs attendus**:
```
INFO: WARMUP 3/3: ObjectionMatcher test...
INFO: WARMUP 3/3: ObjectionMatcher ready (15ms)
```

**Pourquoi `silent=True` ?**
- Le texte "test test test" est bidon → pas de match trouvé
- Sans `silent=True`, affiche "❌ Pas de match suffisant" (confusing)
- Avec `silent=True`, le log est masqué (warmup silencieux)

---

### 5. Finalisation

```python
logger.info("=" * 80)
logger.info("ROBOT V3 INITIALIZED - ALL SERVICES PRELOADED + WEBSOCKET READY")
logger.info("=" * 80)
```

**État final**:
- ✅ Faster-Whisper GPU/CPU prêt (chauffé)
- ✅ AMD Service prêt
- ✅ ObjectionMatcher chargé (theme spécifique)
- ✅ WebSocket server running (ws://127.0.0.1:8080)
- ✅ Connexion ESL FreeSWITCH établie

**Robot prêt pour appels sortants avec barge-in temps réel !**

---

## Différences V3 vs V2

| Feature | V2 (File-based) | V3 (Streaming) |
|---------|----------------|----------------|
| **Audio capture** | `uuid_record` → fichier WAV | `uuid_audio_stream` → WebSocket |
| **Barge-in detection** | WebRTC VAD périodique | STT real-time callbacks |
| **Latence barge-in** | ~500-1000ms (VAD polling) | <100ms (streaming) |
| **Warmups** | GPU (1/3), VAD (2/3), ObjectionMatcher (3/3) | GPU (1/3), AMD (2/3), ObjectionMatcher (3/3) |
| **VAD usage** | ✅ Utilisé (Phase WAITING) | ❌ Obsolète (remplacé par STT streaming) |
| **WebSocket server** | ❌ Pas de WebSocket | ✅ ws://127.0.0.1:8080 (streaming) |

---

## Troubleshooting

### Erreur: "CUDA not available"

**Cause**: PyTorch ne détecte pas le GPU

**Solution**:
```bash
# Vérifier CUDA
nvidia-smi
python3 -c "import torch; print(torch.cuda.is_available())"

# Si False, réinstaller PyTorch avec CUDA:
pip install torch==2.0.1+cu118 --index-url https://download.pytorch.org/whl/cu118
```

---

### Erreur: "Could not import FreeSWITCH config"

**Cause**: Import path incorrect dans `objections_db/__init__.py`

**Solution**: Vérifier ligne 27:
```python
# CORRECT (V3)
from V3.system.config import get_freeswitch_audio_path

# INCORRECT (ancien)
from system.config import get_freeswitch_audio_path
```

---

### Warning: "GPU warmup failed"

**Cause**: Faster-Whisper service non disponible

**Impact**: Non-bloquant, premier appel aura +2s latence

**Solution**: Vérifier installation Faster-Whisper:
```bash
pip install faster-whisper==0.9.0
```

---

### Erreur: "WebSocket server port 8080 already in use"

**Cause**: Une instance V3 précédente tourne encore

**Solution**:
```bash
# Trouver processus
lsof -i :8080

# Killer processus
kill -9 <PID>
```

---

## Logs Complets Attendus

```
================================================================================
INITIALIZING WEBSOCKET AUDIO SERVER (STREAMING V3)
================================================================================
INFO: WebSocket Audio Server created (host: 127.0.0.1, port: 8080)
✅ WebSocket server running at ws://127.0.0.1:8080
   - Real-time audio streaming: ENABLED
   - Barge-in detection: ACTIVE
   - STT transcription: GPU-accelerated

================================================================================
WARMUP TESTS (CRITICAL - Avoid first-call latency spikes)
================================================================================

INFO: WARMUP 1/3: Faster-Whisper test transcription (device: CUDA)...
✅ WARMUP 1/3: GPU CUDA ready (147ms) - GPU is HOT!

INFO: WARMUP 2/3: AMD Service test detection...
INFO: AMD WARMUP 2/3: Completed in 2.34ms - AMD is READY!

INFO: WARMUP 3/3: ObjectionMatcher test...
INFO: WARMUP 3/3: ObjectionMatcher ready (15ms)

================================================================================
ROBOT V3 INITIALIZED - ALL SERVICES PRELOADED + WEBSOCKET READY
================================================================================
```

**Durée totale**: ~680ms (GPU) | ~2100ms (CPU)

---

## Prochaine Étape

**Phase 1: AMD (Answering Machine Detection)** → Voir `robot_freeswitch_phase1_amd.md`
