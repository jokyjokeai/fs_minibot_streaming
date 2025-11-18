# Analyse Détaillée de SimulStreaming - Architecture & Intégration FreeSWITCH

## 1. ARCHITECTURE GÉNÉRALE DE SIMULSTREAMING

### 1.1 Origines et Composants

SimulStreaming est une fusion de deux projets majeurs:
- **Simul-Whisper**: Implémente AlignAtt (simultaneous policy) avec Whisper large-v2
- **Whisper-Streaming**: Interface UFAL pour streaming long-form

**Architecture Résultante:**
```
SimulStreaming = Simul-Whisper (large-v3) + Whisper-Streaming (TCP server)
                 + Machine Translation (EuroLLM optional)
```

### 1.2 Points d'Entrée

**Fichier Principal:** `/SimulStreaming/simulstreaming_whisper_server.py`
```python
#!/usr/bin/env python3
from simulstreaming_whisper import simulwhisper_args, simul_asr_factory
from whisper_streaming.whisper_server import main_server

if __name__ == "__main__":
    main_server(simul_asr_factory, add_args=simulwhisper_args)
```

**Ce qui se passe:**
1. Import de la factory `simul_asr_factory` (crée les objets ASR/processor)
2. Appel de `main_server` qui lance le serveur TCP

---

## 2. SERVEUR TCP - ARCHITECTURE COMPLÈTE

### 2.1 Serveur TCP (TCP Socket Streaming)

**Location:** `whisper_streaming/whisper_server.py`

#### Configuration TCP
```python
SAMPLING_RATE = 16000  # 16kHz
PACKET_SIZE = 32000*5*60  # 5 minutes (~320KB)
```

**Port par défaut:** 43007 (configurable)
**Serveur:** Socket TCP STREAM (mode bloquant)

#### Architecture Serveur

```python
# main_server() -> TCP loop
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((host, port))  # Default: localhost:43007
    s.listen(1)
    while True:
        conn, addr = s.accept()
        # Créer une instance ServerProcessor pour ce client
        proc = ServerProcessor(connection, online, min_chunk)
        proc.process()  # Traitement du client
        conn.close()
```

### 2.2 Flux Audio - Format Exact

**Format attendu:**
- **Codec:** Raw PCM (NO container, NO WAV header)
- **Bit depth:** 16-bit signed (S16_LE = little-endian)
- **Sample rate:** 16000 Hz (16kHz)
- **Channels:** Mono (1 channel)
- **Byte order:** Little-endian (LITTLE)

**Exemple d'envoi audio Linux:**
```bash
# Depuis microphone vers serveur SimulStreaming
arecord -f S16_LE -c1 -r 16000 -t raw -D default | nc localhost 43001
```

**Format dans le code Python:**
```python
# whisper_server.py - ligne 73
sf = soundfile.SoundFile(
    io.BytesIO(raw_bytes),
    channels=1,
    endian="LITTLE",
    samplerate=SAMPLING_RATE,
    subtype="PCM_16",  # Signed 16-bit PCM
    format="RAW"       # Format RAW (pas WAV)
)
audio, _ = librosa.load(sf, sr=SAMPLING_RATE, dtype=np.float32)
```

### 2.3 Réception Audio - Algorithme Buffering

```python
def receive_audio_chunk(self):
    """Reçoit chunks audio avec buffering minlimit"""
    out = []
    minlimit = self.min_chunk * SAMPLING_RATE  # min 1s par défaut
    
    while sum(len(x) for x in out) < minlimit:
        raw_bytes = self.connection.non_blocking_receive_audio()
        if not raw_bytes:
            break
        
        # Convertir bytes → numpy float32
        audio = librosa.load(sf, sr=SAMPLING_RATE, dtype=np.float32)
        out.append(audio)
    
    return np.concatenate(out)  # Combiner tous les chunks
```

**Comportement:**
- Attend au minimum `min_chunk_size` secondes d'audio (default: 1.0s)
- Si moins reçu avant timeout → retour immédiat
- Rassemble tous les chunks reçus en un seul array numpy

### 2.4 Format de Réponse (Output)

**Format serveur:** `"start_time end_time text"`

Exemple:
```
0 1200 Bonjour
1200 2400 comment
2400 3600 allez-vous
```

**Parsing dans le code:**
```python
# freeswitch_simulstreaming_bridge.py - ligne 260
message = "%1.0f %1.0f %s" % (
    iteration_output['start'] * 1000,  # ms
    iteration_output['end'] * 1000,    # ms
    iteration_output['text']
)
# Retour: "0 1200 Bonjour\n"
```

**Format simulstreaming_whisper.py (simulation from file):**
```
timestamp_ms start_ms end_ms text
1200.0000 0 1200 Bonjour
```

---

## 3. PIPELINE DE TRAITEMENT

### 3.1 Architecture Classe SimulWhisperASR

**File:** `simulstreaming_whisper.py` (ligne 84)

```python
class SimulWhisperASR(ASRBase):
    def __init__(self, language, model_path, cif_ckpt_path, ...):
        cfg = AlignAttConfig(...)
        self.model = PaddedAlignAttWhisper(cfg)  # Modèle principal
    
    def warmup(self, audio):
        self.model.insert_audio(audio)
        self.model.infer(True)
        self.model.refresh_segment(complete=True)
```

### 3.2 Architecture Classe SimulWhisperOnline (Streaming)

**File:** `simulstreaming_whisper.py` (ligne 128)

```python
class SimulWhisperOnline(OnlineProcessorInterface):
    def __init__(self, asr):
        self.model = asr.model
        self.audio_chunks = []
        self.offset = 0
        self.beg, self.end = 0, 0
    
    def insert_audio_chunk(self, audio):
        # Accumule audio en chunks
        self.audio_chunks.append(torch.from_numpy(audio))
    
    def process_iter(self):
        # 1. Concatène tous les chunks accumulés
        audio = torch.cat(self.audio_chunks, dim=0)
        self.audio_chunks = []
        
        # 2. Insert audio dans le modèle
        self.audio_bufer_offset += self.model.insert_audio(audio)
        
        # 3. Inférence
        tokens, generation_progress = self.model.infer(is_last=self.is_last)
        
        # 4. Obtenir timestamps au niveau mot
        ts_words = self.timestamped_text(tokens, generation_progress)
        
        # 5. Retourner avec timing
        return {
            'start': self.beg,
            'end': e,
            'text': text,
            'tokens': tokens,
            'words': ts_words
        }
```

### 3.3 Timing des Frames

**Information importante:**
- 1 frame Whisper = 0.02 secondes
- Pour large-v3: 1 frame = 20ms

```python
# simulstreaming_whisper.py - ligne 181
'start': b * 0.02 + self.audio_bufer_offset  # b = frame number
'end': e * 0.02 + self.audio_bufer_offset
```

---

## 4. INTÉGRATION FREESWITCH - BRIDGE DÉTAILLÉ

### 4.1 Vue d'Ensemble du Bridge

**File:** `freeswitch_simulstreaming_bridge.py`

```
FreeSWITCH
    ↓ (uuid_record → RAW PCM)
    ↓
FreeSwitchAudioCapture
    ↓ (tail -f → read)
    ↓
SimulStreamingClient
    ↓ (TCP socket)
    ↓
SimulStreaming Server (port 43001)
    ↓ (processing)
    ↓
SimulStreamingClient (receive)
    ↓ (parse "start end text")
    ↓
Transcriptions → Callback
```

### 4.2 Configuration FreeSWITCH ESL

```python
# freeswitch_simulstreaming_bridge.py - ligne 44-46
FREESWITCH_HOST = "127.0.0.1"
FREESWITCH_PORT = 8021  # ESL port (Event Socket Layer)
FREESWITCH_PASSWORD = "ClueCon"
```

### 4.3 Capture Audio via uuid_record

**Classe:** `FreeSwitchAudioCapture` (ligne 115)

```python
def start_capture(self) -> bool:
    """Démarre capture via ESL uuid_record"""
    import ESL
    
    con = ESL.ESLconnection(
        FREESWITCH_HOST,
        str(FREESWITCH_PORT),
        FREESWITCH_PASSWORD
    )
    
    # Démarrer enregistrement RAW
    cmd = f"uuid_record {call_uuid} start {recording_path} 3600"
    result = con.api("uuid_record", f"{call_uuid} start {recording_path} 3600")
    response = result.getBody().strip()
    
    if "+OK" in response or "Success" in response:
        return True
```

**Important:**
- Format: RAW (pas WAV)
- Sample rate: 16kHz (FreeSWITCH default)
- Bit depth: 16-bit signed
- Durée max: 3600 secondes (1 heure)

### 4.4 Streaming Audio depuis Fichier

**Problème:** `uuid_record` écrit dans un fichier, pas en stream direct

**Solution:**
```python
def read_audio_stream(self) -> bytes:
    """Lit depuis fichier en cours d'écriture avec tail -f"""
    # Utiliser tail -f pour suivre le fichier en temps réel
    if not self.capture_process:
        cmd = ["tail", "-f", "-c", "+0", self.recording_path]
        self.capture_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
    
    # Lire chunk depuis tail
    data = self.capture_process.stdout.read(CHUNK_SIZE * 2)  # 3200 bytes
    return data
```

**Paramètres:**
- CHUNK_SIZE = 1600 samples = 100ms @ 16kHz
- 3200 bytes = 1600 samples * 2 bytes/sample

### 4.5 Client TCP - Envoi Audio

```python
class SimulStreamingClient:
    def __init__(self, host="localhost", port=43001):
        self.host = host
        self.port = port
        self.socket = None
    
    def connect(self) -> bool:
        """Connexion TCP"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5.0)
        self.socket.connect((self.host, self.port))
        self.connected = True
        return True
    
    def send_audio(self, audio_data: bytes) -> bool:
        """Envoie audio PCM brut"""
        self.socket.sendall(audio_data)
        return True
    
    def receive_transcription(self, timeout=0.1) -> Optional[str]:
        """Reçoit transcription"""
        self.socket.settimeout(timeout)
        data = self.socket.recv(4096)
        if data:
            text = data.decode('utf-8').strip()
            return text  # Format: "start end text\n"
        return None
```

### 4.6 Parsing Transcription

```python
# freeswitch_simulstreaming_bridge.py - ligne 259-273
text = self.client.receive_transcription(timeout=0.1)

if text:
    # Parser: "start_time end_time text"
    parts = text.split(' ', 2)
    if len(parts) >= 3:
        start_time = float(parts[0])  # En millisecondes
        end_time = float(parts[1])
        transcription = parts[2]
        
        self.transcriptions.append({
            'start': start_time,
            'end': end_time,
            'text': transcription,
            'timestamp': datetime.now()
        })
```

---

## 5. PARAMÈTRES CRITIQUES POUR FRENCH

### 5.1 Configuration Langue

```python
# simulstreaming_whisper.py - ligne 13-16
group.add_argument('--language', '--lan', default='fr',
                   help='Source language code: en, de, cs, fr, etc.')

# Utilisation pour SimulStreaming
asr = SimulWhisperASR(
    language="fr",  # CRITICAL pour français
    model_path="./large-v3.pt",
    ...
)
```

### 5.2 Modèles Disponibles

```
- tiny.pt         (39M)  - Rapide, moins précis
- base.pt        (74M)  - Bon rapport qualité/vitesse
- small.pt       (244M) - Recommandé pour français
- medium.pt      (769M) - Très bon mais lent
- large-v3.pt    (2.9G) - Meilleur, GPU requis

Pour français RECOMMANDÉ: small.pt ou large-v3.pt
```

### 5.3 Paramètres AlignAtt (Streaming)

```python
# simulstreaming_whisper.py - ligne 28-31
parser.add_argument('--frame_threshold', type=int, default=25,
                    help='Threshold for AlignAtt policy')
```

**Explication:**
- `frame_threshold=25`: Décoder seulement jusqu'à 25 frames (500ms) avant la fin
- Cela rend la transcription simultanée en gardant de la latence faible
- Value: nombre de frames Whisper (1 frame = 20ms)

### 5.4 Paramètres Beam Search

```python
parser.add_argument('--beams', '-b', type=int, default=1,
                    help='Number of beams for beam search')
```

- `--beams 1`: Greedy decoding (rapide, moins précis)
- `--beams 5`: Beam search (plus lent, plus précis)
- **Recommandé pour français:** beams=3 (compromis)

---

## 6. DIFFÉRENCES: SIMULSTREAMING vs WHISPER_STREAMING

### 6.1 Whisper-Streaming (UFAL)

```
TCP Server → receive audio RAW PCM
          → FasterWhisperASR (batch processing)
          → Output: "start_ms end_ms text\n"
```

**Avantages:**
- Plus simple, communauté active
- Supporte plusieurs languages
- Output format clair

**Inconvénients:**
- Pas de simultaneous streaming (AlignAtt)
- Latence plus haute
- Moins d'options de fine-tuning

### 6.2 SimulStreaming

```
TCP Server → receive audio RAW PCM
          → PaddedAlignAttWhisper (simultaneous policy)
          → Output: "start_ms end_ms text\n"
```

**Avantages:**
- AlignAtt: simultaneous/streaming policy
- Latence beaucoup plus basse
- Support large-v3 (meilleure précision)
- Beam search, prompts, context

**Inconvénients:**
- Plus complexe
- Plus lourd en GPU
- Moins de documentation

---

## 7. CHECKLIST INTÉGRATION FREESWITCH

### 7.1 Vérifications Audio Format

```python
# VÉRIFIER dans le code:
1. ✓ Format PCM brut (pas WAV)
2. ✓ 16-bit signed little-endian (S16_LE)
3. ✓ 16000 Hz mono (SAMPLING_RATE = 16000)
4. ✓ Pas de compression (raw bytes)
5. ✓ FreeSWITCH uuid_record output → raw PCM
```

### 7.2 Tests à Faire

```bash
# Test 1: Vérifier le serveur démarre
python3 SimulStreaming/simulstreaming_whisper_server.py \
    --language fr \
    --model_path ./SimulStreaming/large-v3.pt \
    --host localhost \
    --port 43001

# Test 2: Envoyer audio via netcat (Linux)
arecord -f S16_LE -c1 -r 16000 -t raw -D default | nc localhost 43001

# Test 3: Vérifier format audio FreeSWITCH
# Dans FreeSWITCH CLI:
# uuid_record <call_uuid> start /tmp/test.raw 10
# (enregistrer 10 secondes, vérifier avec hexdump)

# Test 4: Bridge complet
python3 freeswitch_simulstreaming_bridge.py --test
```

---

## 8. FICHIERS IMPORTANTS - STRUCTURE

```
SimulStreaming/
├── simulstreaming_whisper_server.py  ← Entry point serveur TCP
├── simulstreaming_whisper.py          ← Factory ASR + Online processor
├── whisper_streaming/
│   ├── whisper_server.py              ← TCP server implementation
│   ├── base.py                        ← OnlineProcessorInterface
│   └── line_packet.py                 ← Protocol TCP
├── simul_whisper/
│   ├── simul_whisper.py               ← PaddedAlignAttWhisper
│   ├── config.py                      ← AlignAttConfig
│   └── whisper/                       ← Whisper model files
├── large-v3.pt                        ← Modèle large-v3 (2.9G)
└── small.pt                           ← Modèle small (244M)

Project Root/
├── freeswitch_simulstreaming_bridge.py ← FreeSWITCH integration
├── system/
│   ├── robot_freeswitch.py            ← Main robot
│   ├── config.py                      ← Configuration centrale
│   └── services/                      ← AI services
└── test_simulstreaming_simple.py      ← Tests simples
```

---

## 9. POINTS CRITIQUES - PIÈGES COURANTS

### 9.1 Format Audio

❌ **ERREUR:** Envoyer WAV avec header
✅ **CORRECT:** Raw PCM bytes directement

❌ **ERREUR:** 44.1kHz ou autre sample rate
✅ **CORRECT:** Exactement 16000 Hz

### 9.2 Port TCP

❌ **ERREUR:** Port 43007 (défaut du code)
⚠️ **À VÉRIFIER:** Port 43001 utilisé par bridge

### 9.3 Timing

❌ **ERREUR:** Attendre réponse immédiate
✅ **CORRECT:** Timeout 0.1-0.5s entre messages

### 9.4 Langue

❌ **ERREUR:** Pas spécifier langue
✅ **CORRECT:** `--language fr` pour français

---

## 10. COMMANDES LANCEMENT

### 10.1 Lancer Serveur SimulStreaming

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

# Avec large-v3 (meilleur)
python3 SimulStreaming/simulstreaming_whisper_server.py \
    --host 127.0.0.1 \
    --port 43001 \
    --language fr \
    --model_path ./SimulStreaming/large-v3.pt \
    --min-chunk-size 0.5 \
    --frame_threshold 25

# Ou avec small (plus rapide)
python3 SimulStreaming/simulstreaming_whisper_server.py \
    --host 127.0.0.1 \
    --port 43001 \
    --language fr \
    --model_path ./SimulStreaming/small.pt \
    --min-chunk-size 0.3
```

### 10.2 Test Bridge FreeSWITCH

```bash
# Test connexion directe
python3 freeswitch_simulstreaming_bridge.py --test-connection

# Test avec appel réel
python3 freeswitch_simulstreaming_bridge.py --test
```

---

## RÉSUMÉ TECHNIQUE

**SimulStreaming = Streaming Whisper avec AlignAtt**

1. **TCP Server** écoute port 43001
2. **Accepte audio** en format PCM 16kHz 16-bit mono
3. **Process** chunks via SimulWhisper (AlignAtt policy)
4. **Retourne** transcriptions en format: `"start_ms end_ms text\n"`
5. **FreeSWITCH Bridge** capture uuid_record → envoie TCP → parse résultats

**Clé du succès:** 
- Format audio PCM brut (exact)
- Port TCP correct (43001)
- Langue spécifiée (fr)
- Paramètres AlignAtt adaptés (frame_threshold, min_chunk_size)

