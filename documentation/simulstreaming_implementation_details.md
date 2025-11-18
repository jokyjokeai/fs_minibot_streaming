# DÉTAILS D'IMPLÉMENTATION - SimulStreaming & FreeSWITCH Bridge

## 1. DÉMARRAGE SERVEUR TCP - ANALYSE COMPLÈTE

### 1.1 Entry Point: simulstreaming_whisper_server.py

```python
#!/usr/bin/env python3
from simulstreaming_whisper import simulwhisper_args, simul_asr_factory
from whisper_streaming.whisper_server import main_server

if __name__ == "__main__":
    main_server(simul_asr_factory, add_args=simulwhisper_args)
```

**Flow:**
1. Import `simulwhisper_args` = fonction qui ajoute arguments CLI spécifiques
2. Import `simul_asr_factory` = factory function créant ASR + Online processor
3. Appel `main_server()` qui:
   - Parse arguments (incluant ceux de simulwhisper_args)
   - Crée ASR via factory
   - Lance boucle TCP

### 1.2 Factory Function - simul_asr_factory

**File:** `simulstreaming_whisper.py` ligne 52

```python
def simul_asr_factory(args):
    logger.setLevel(args.log_level)
    
    # Sélectionner decoder (greedy ou beam)
    decoder = args.decoder
    if args.beams > 1:
        decoder = "beam"
    else:
        decoder = "greedy"
    
    # Construire dict des paramètres
    a = {
        'model_path': args.model_path,
        'cif_ckpt_path': args.cif_ckpt_path,
        'frame_threshold': args.frame_threshold,
        'audio_min_len': args.audio_min_len,
        'audio_max_len': args.audio_max_len,
        'beams': args.beams,
        'task': args.task,
        'never_fire': args.never_fire,
        'init_prompt': args.init_prompt,
        'static_init_prompt': args.static_init_prompt,
        'max_context_tokens': args.max_context_tokens,
        'logdir': args.logdir
    }
    a["language"] = args.lan
    a["segment_length"] = args.min_chunk_size
    a["decoder_type"] = decoder
    
    # Vérifications
    if args.min_chunk_size >= args.audio_max_len:
        raise ValueError("min_chunk_size must be smaller than audio_max_len")
    
    # Créer ASR et Online processor
    asr = SimulWhisperASR(**a)
    return asr, SimulWhisperOnline(asr)
```

**Important:** La factory retourne TUPLE (ASR, OnlineProcessor)

### 1.3 main_server() - Boucle TCP

**File:** `whisper_streaming/whisper_server.py` ligne 115

```python
def main_server(factory, add_args):
    """
    factory: function(args) -> (asr, online_processor)
    add_args: function(parser) to add specific arguments
    """
    
    # 1. Parse arguments
    parser = argparse.ArgumentParser()
    processor_args(parser)      # Arguments whisper_streaming
    add_args(parser)            # Arguments SimulStreaming
    args = parser.parse_args()
    
    # 2. Create ASR via factory
    asr, online = asr_factory(args, factory)
    
    # 3. Warmup ASR
    if args.warmup_file:
        a = load_audio_chunk(args.warmup_file, 0, 1)
        asr.warmup(a)
        logger.info("Whisper is warmed up.")
    
    # 4. Boucle TCP principale
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((args.host, args.port))
        s.listen(1)
        logger.info(f'Listening on {args.host}:{args.port}')
        
        while True:
            conn, addr = s.accept()
            logger.info(f'Connected to {addr}')
            
            connection = Connection(conn)
            proc = ServerProcessor(connection, online, min_chunk)
            proc.process()  # Traiter ce client
            
            conn.close()
            logger.info('Connection closed')
```

---

## 2. PROCESSING UN CLIENT - SERVERPROCESSOR

### 2.1 Classe ServerProcessor

**File:** `whisper_streaming/whisper_server.py` ligne 53

```python
class ServerProcessor:
    def __init__(self, c, online_asr_proc, min_chunk):
        self.connection = c
        self.online_asr_proc = online_asr_proc
        self.min_chunk = min_chunk
        self.is_first = True
    
    def process(self):
        """Main processing loop for one client"""
        self.online_asr_proc.init()  # Reset state
        
        while True:
            # 1. Recevoir audio chunk
            a = self.receive_audio_chunk()
            if a is None:
                break
            
            # 2. Insert dans processor
            self.online_asr_proc.insert_audio_chunk(a)
            
            # 3. Process itérativement
            o = self.online_asr_proc.process_iter()
            
            # 4. Envoyer résultats
            try:
                self.send_result(o)
            except BrokenPipeError:
                logger.info("broken pipe -- connection closed?")
                break
```

### 2.2 Receive Audio Chunk - Buffering Algorithm

**File:** `whisper_streaming/whisper_server.py` ligne 62

```python
def receive_audio_chunk(self):
    """
    Reçoit chunks jusqu'à atteindre minlimit (en samples).
    Combine tous les chunks en un seul array.
    Retourne None si connexion fermée.
    """
    out = []
    minlimit = self.min_chunk * SAMPLING_RATE  # Par défaut: 1.0 * 16000 = 16000 samples
    
    while sum(len(x) for x in out) < minlimit:
        # Recevoir bytes bruts
        raw_bytes = self.connection.non_blocking_receive_audio()
        
        if not raw_bytes:
            break
        
        # Convertir bytes PCM → numpy float32
        sf = soundfile.SoundFile(
            io.BytesIO(raw_bytes),
            channels=1,
            endian="LITTLE",
            samplerate=SAMPLING_RATE,
            subtype="PCM_16",
            format="RAW"
        )
        audio, _ = librosa.load(sf, sr=SAMPLING_RATE, dtype=np.float32)
        out.append(audio)
    
    if not out:
        return None
    
    # Première chunk: vérifier minlimit atteint
    conc = np.concatenate(out)
    if self.is_first and len(conc) < minlimit:
        return None
    
    self.is_first = False
    return conc
```

**Comportement clé:**
- Attend au minimum `min_chunk` secondes de données
- Si moins de données avant timeout → retourne None (fin connexion)
- Premier chunk: vérification stricte de minlimit
- Chunks suivants: retour dès que minlimit atteint

### 2.3 Send Result - Format Output

**File:** `whisper_streaming/whisper_server.py` ligne 84

```python
def send_result(self, iteration_output):
    """
    Envoie résultats au client
    Format: "start_ms end_ms text"
    """
    if iteration_output:
        message = "%1.0f %1.0f %s" % (
            iteration_output['start'] * 1000,   # Convertir secondes → ms
            iteration_output['end'] * 1000,
            iteration_output['text']
        )
        # Format de message: "0.0 1200.0 Bonjour\n"
        print(message, flush=True, file=sys.stderr)
        self.connection.send(message)
    else:
        logger.debug("No text in this segment")
```

---

## 3. SIMULWHISPER ONLINE PROCESSOR - DÉTAILS

### 3.1 Structure SimulWhisperOnline

**File:** `simulstreaming_whisper.py` ligne 128

```python
class SimulWhisperOnline(OnlineProcessorInterface):
    SAMPLING_RATE = 16000
    
    def __init__(self, asr):
        self.model = asr.model  # PaddedAlignAttWhisper
        self.file = None
        self.init()
    
    def init(self, offset=None):
        """Reset pour nouveau client"""
        self.audio_chunks = []
        self.offset = offset if offset else 0
        self.is_last = False
        self.beg = self.offset
        self.end = self.offset
        
        self.audio_bufer_offset = self.offset
        self.last_ts = -1
        self.model.refresh_segment(complete=True)
        
        self.unicode_buffer = []
```

### 3.2 Process Iterator - Core Processing

**File:** `simulstreaming_whisper.py` ligne 207

```python
def process_iter(self):
    """
    Main processing step:
    1. Combiner chunks accumulés
    2. Insert audio dans modèle
    3. Inférence
    4. Extraire timestamps
    5. Retourner résultats
    """
    
    # 1. Concatène chunks (ou None si aucun)
    if len(self.audio_chunks) == 0:
        audio = None
    else:
        audio = torch.cat(self.audio_chunks, dim=0)
        if audio.shape[0] == 0:
            audio = None
        else:
            self.end += audio.shape[0] / self.SAMPLING_RATE
    
    self.audio_chunks = []
    
    # 2. Insert audio dans modèle
    self.audio_bufer_offset += self.model.insert_audio(audio)
    
    # 3. Inférence (avec AlignAtt policy)
    tokens, generation_progress = self.model.infer(is_last=self.is_last)
    
    # 4. Gérer caractères unicode incomplets
    tokens = self.hide_incomplete_unicode(tokens)
    
    # 5. Décoder tokens → texte
    text = self.model.tokenizer.decode(tokens)
    
    if len(text) == 0:
        return {}
    
    # 6. Extraire timestamps au niveau mot
    ts_words = self.timestamped_text(tokens, generation_progress)
    
    # 7. Calculer timing segment
    self.beg = min(word['start'] for word in ts_words)
    self.beg = max(self.beg, self.last_ts + 0.001)
    
    if self.is_last:
        e = self.end
    else:
        e = max(word['end'] for word in ts_words)
    
    e = max(e, self.beg + 0.001)
    self.last_ts = e
    
    # 8. Retourner résultats
    return {
        'start': self.beg,
        'end': e,
        'text': text,
        'tokens': tokens,
        'words': ts_words
    }
```

### 3.3 Timestamped Text - Frame-to-Time Conversion

**File:** `simulstreaming_whisper.py` ligne 154

```python
def timestamped_text(self, tokens, generation):
    """
    Convertit tokens et frames → mots avec timestamps
    
    1 frame Whisper = 0.02 secondes (20ms)
    
    Retourne: list of {start, end, text, tokens}
    """
    if not generation:
        return []
    
    pr = generation["progress"]
    split_words, split_tokens = self.model.tokenizer.split_to_word_tokens(tokens)
    
    # Extraire frame le plus attendu pour chaque token
    frames = [p["most_attended_frames"][0] for p in pr]
    
    # Construire resultats mot-par-mot
    ret = []
    for sw, st in zip(split_words, split_tokens):
        b = None
        for stt in st:
            t, f = tokens.pop(0), frames.pop(0)
            if t != stt:
                raise ValueError(f"Token mismatch")
            if b is None:
                b = f
        e = f
        
        out = {
            'start': b * 0.02 + self.audio_bufer_offset,  # Frame → secondes
            'end': e * 0.02 + self.audio_bufer_offset,
            'text': sw,
            'tokens': st
        }
        ret.append(out)
    
    return ret
```

---

## 4. FREESWITCH BRIDGE - DÉTAILS IMPLÉMENTATION

### 4.1 FreeSwitchAudioCapture - Capture par uuid_record

**File:** `freeswitch_simulstreaming_bridge.py` ligne 115

```python
class FreeSwitchAudioCapture:
    def __init__(self, call_uuid: str):
        self.call_uuid = call_uuid
        self.recording_path = f"/tmp/fs_simulstreaming_{call_uuid}.raw"
        self.capture_process = None
    
    def start_capture(self) -> bool:
        """Démarre enregistrement via ESL"""
        try:
            import ESL
            
            con = ESL.ESLconnection(
                FREESWITCH_HOST,
                str(FREESWITCH_PORT),
                FREESWITCH_PASSWORD
            )
            
            if not con.connected():
                logger.error("Cannot connect to FreeSWITCH ESL")
                return False
            
            # Format RAW PCM 16-bit 16kHz mono
            cmd = f"uuid_record {self.call_uuid} start {self.recording_path} 3600"
            result = con.api("uuid_record", f"{self.call_uuid} start {self.recording_path} 3600")
            response = result.getBody().strip()
            
            if "+OK" in response or "Success" in response:
                logger.info(f"Recording started: {self.recording_path}")
                return True
            else:
                logger.error(f"Recording failed: {response}")
                return False
        
        except Exception as e:
            logger.error(f"Capture error: {e}")
            return False
```

**Important:**
- ESL connection sur port 8021
- uuid_record crée fichier RAW (pas WAV)
- Durée: 3600s (1 heure)
- Path: `/tmp/fs_simulstreaming_{uuid}.raw`

### 4.2 read_audio_stream - Tail-based Streaming

**File:** `freeswitch_simulstreaming_bridge.py` ligne 151

```python
def read_audio_stream(self) -> bytes:
    """
    Lit depuis fichier en cours d'écriture via tail -f
    
    Problem: uuid_record écrit dans fichier (pas stream direct)
    Solution: tail -f pour suivre le fichier en temps réel
    """
    if not self.capture_process:
        # -c +0: commencer à 0 bytes
        # -f: follow (mode tail -f)
        cmd = ["tail", "-f", "-c", "+0", self.recording_path]
        self.capture_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.5)  # Attendre que tail démarre
    
    try:
        # Lire 1600 samples = 3200 bytes (100ms @ 16kHz)
        data = self.capture_process.stdout.read(CHUNK_SIZE * 2)
        return data
    except:
        return b""
```

**Calculations:**
- CHUNK_SIZE = 1600 samples
- 1600 samples * 2 bytes/sample = 3200 bytes
- Duration = 1600 samples / 16000 Hz = 100ms

### 4.3 Boucle Envoi Audio

**File:** `freeswitch_simulstreaming_bridge.py` ligne 217

```python
def _audio_streaming_loop(self):
    """Thread qui envoie audio à SimulStreaming"""
    logger.info("Audio streaming started")
    chunks_sent = 0
    
    while self.running:
        try:
            # Lire audio depuis FreeSWITCH
            audio_data = self.capture.read_audio_stream()
            
            if audio_data and len(audio_data) > 0:
                # Envoyer au serveur SimulStreaming
                if self.client.send_audio(audio_data):
                    chunks_sent += 1
                    
                    if chunks_sent % 50 == 0:
                        logger.info(f"Sent {chunks_sent} chunks")
                        
                        # Log energy
                        audio_np = np.frombuffer(audio_data, dtype=np.int16)
                        energy = np.sqrt(np.mean(audio_np**2))
                        logger.info(f"   Energy: {energy:.0f}")
            else:
                time.sleep(0.01)
        
        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
            time.sleep(0.1)
    
    logger.info("Audio streaming stopped")
```

**Flow:**
1. Lire 100ms d'audio depuis tail
2. Envoyer au serveur TCP
3. Répéter avec ~10-50ms d'overhead
4. Calculer energy (RMS) pour monitoring

### 4.4 Boucle Réception Transcriptions

**File:** `freeswitch_simulstreaming_bridge.py` ligne 249

```python
def _transcription_receive_loop(self):
    """Thread qui reçoit transcriptions"""
    logger.info("Transcription receiver started")
    
    while self.running:
        try:
            # Recevoir avec timeout court (non-blocking)
            text = self.client.receive_transcription(timeout=0.1)
            
            if text:
                # Parser: "start_ms end_ms text"
                parts = text.split(' ', 2)
                if len(parts) >= 3:
                    start_time = float(parts[0])
                    end_time = float(parts[1])
                    transcription = parts[2]
                    
                    logger.info(f"[{start_time:.2f}-{end_time:.2f}s] {transcription}")
                    
                    self.transcriptions.append({
                        'start': start_time,
                        'end': end_time,
                        'text': transcription,
                        'timestamp': datetime.now()
                    })
        
        except Exception as e:
            if "timeout" not in str(e).lower():
                logger.error(f"Receive error: {e}")
            time.sleep(0.01)
    
    logger.info("Transcription receiver stopped")
```

---

## 5. TIMING & LATENCY ANALYSIS

### 5.1 Latency Budget (audio 16kHz = 62.5us per sample)

```
Total latency = Buffering + Inference + Network

1. BUFFERING DELAY (min_chunk_size)
   - Default: 1.0 second
   - Minimum: 0.3 second
   - Each chunk waits for minlimit samples

2. INFERENCE DELAY (AlignAtt)
   - Whisper large-v3: ~50-100ms per second of audio
   - AlignAtt with frame_threshold=25: ~20-30ms extra
   - Total: ~70-130ms latency

3. NETWORK DELAY
   - Local TCP: ~1-2ms
   - Added by tail -f: ~10-50ms

4. TOTAL LATENCY
   - Best case: 300ms (min_chunk_size=0.3s + inference 70ms + network 20ms)
   - Typical: 500ms (min_chunk_size=0.5s)
   - Worst case: 1s+ (large buffering + slow inference)
```

### 5.2 Frame Timeline

```
t=0ms:     Audio chunk arrives at server
t=0-50ms:  Buffering (waiting for min_chunk_size)
t=50ms:    Start inference
t=50-120ms: Inference (AlignAtt processing)
t=120ms:   Generate output
t=120-122ms: Network send
t=122ms:   Output received by client
           TOTAL LATENCY: 122ms
```

---

## 6. ARGUMENTS CLI IMPORTANTS

### 6.1 Arguments SimulStreaming

```python
# simulstreaming_whisper.py - les plus importants:

--language fr              # Language code (required)
--model_path ./small.pt    # Modèle Whisper
--beams 1                  # 1=greedy, 5=beam search
--frame_threshold 25       # AlignAtt threshold (frames)
--min-chunk-size 0.5       # Min audio buffering (seconds)
--audio_max_len 30.0       # Max audio buffer (seconds)
--audio_min_len 0.0        # Min audio before processing

# Pour optimisation latency:
--min-chunk-size 0.3       # Moins de buffering = plus rapide
--frame_threshold 20       # Moins de latence AlignAtt
--beams 1                  # Greedy = plus rapide
```

### 6.2 Arguments Server

```python
# whisper_server.py:

--host localhost           # Interface d'écoute
--port 43001              # Port TCP
--warmup-file /path/audio # Warmup before first call
```

---

## 7. DEBUG & TROUBLESHOOTING

### 7.1 Vérifier Connection TCP

```bash
# Test connection au serveur
python3 -c "
import socket
import time

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)

try:
    sock.connect(('127.0.0.1', 43001))
    print('✅ Server is running on port 43001')
    sock.close()
except:
    print('❌ Server not responding on port 43001')
"
```

### 7.2 Vérifier Audio Format

```bash
# Vérifier format du fichier uuid_record
file /tmp/fs_simulstreaming_*.raw
# Output: data  (raw audio file)

# Vérifier bytes audio
hexdump -C /tmp/fs_simulstreaming_*.raw | head -20
# Doit montrer 16-bit samples en little-endian

# Convertir en WAV pour écouter
ffmpeg -f s16le -ar 16000 -ac 1 -i /tmp/fs_simulstreaming_*.raw \
       /tmp/test.wav
```

### 7.3 Monitor Logs

```bash
# SimulStreaming server
tail -f /tmp/simulstreaming.log | grep -E "Processing|output|error"

# FreeSWITCH logs
tail -f /var/log/freeswitch/freeswitch.log | grep uuid_record

# Bridge logs
python3 freeswitch_simulstreaming_bridge.py --uuid <uuid> 2>&1 | tee bridge.log
```

---

## 8. OPTIMIZATIONS POSSIBLES

### 8.1 Reduce Buffering

```python
# Current: min_chunk_size=1.0s
# Change to: min_chunk_size=0.3s

# In bridge:
server_cmd = [
    "python3", "SimulStreaming/simulstreaming_whisper_server.py",
    "--min-chunk-size", "0.3",  # 300ms buffer
    "--language", "fr"
]
```

### 8.2 Use Smaller Model

```python
# Current: large-v3.pt (2.9G, meilleur mais lent)
# Change to: small.pt (244M, bon compromis)

# In bridge:
server_cmd = [
    "python3", "SimulStreaming/simulstreaming_whisper_server.py",
    "--model_path", "./SimulStreaming/small.pt",
    "--language", "fr"
]
```

### 8.3 Adjust AlignAtt Threshold

```python
# Current: frame_threshold=25 (500ms latency)
# Change to: frame_threshold=15 (300ms latency)

# Tradeoff: lower threshold = less context = potentially less accurate
```

