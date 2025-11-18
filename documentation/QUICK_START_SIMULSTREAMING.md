# QUICK START - SimulStreaming TCP Server

## 1. Démarrer le Serveur SimulStreaming

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

# Option A: Avec large-v3 (meilleur, mais lent - requis GPU)
python3 SimulStreaming/simulstreaming_whisper_server.py \
    --host 127.0.0.1 \
    --port 43001 \
    --language fr \
    --model_path ./SimulStreaming/large-v3.pt \
    --min-chunk-size 0.5 \
    --frame_threshold 25

# Option B: Avec small (plus rapide, bon compromis)
python3 SimulStreaming/simulstreaming_whisper_server.py \
    --host 127.0.0.1 \
    --port 43001 \
    --language fr \
    --model_path ./SimulStreaming/small.pt \
    --min-chunk-size 0.3 \
    --frame_threshold 15
```

**Sortie attendue:**
```
2024-11-16 15:12:34 | whisper_server | INFO | Listening on 127.0.0.1:43001
2024-11-16 15:12:34 | whisper_server | INFO | Whisper is warmed up.
```

---

## 2. Tester le Serveur

### Test 1: Connexion TCP simple

```bash
# Ouvrir nouveau terminal
python3 -c "
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 43001))
print('✅ Server is running')
sock.close()
"
```

### Test 2: Envoyer audio via netcat

```bash
# Depuis microphone
arecord -f S16_LE -c1 -r 16000 -t raw -D default | nc localhost 43001

# Depuis fichier
dd if=audio_file.raw 2>/dev/null | nc localhost 43001
```

### Test 3: Test complet FreeSWITCH

```bash
python3 freeswitch_simulstreaming_bridge.py --test-connection
```

---

## 3. Format Audio Attendu

SimulStreaming accepte UNIQUEMENT:

| Paramètre | Valeur |
|-----------|--------|
| Format | RAW PCM (sans header WAV) |
| Codec | PCM 16-bit signed |
| Sample Rate | 16000 Hz (16kHz) |
| Channels | 1 (mono) |
| Byte Order | Little-endian (S16_LE) |

**Hexdump exemple:**
```
# Correct (S16_LE)
00000000: 0000 0100 02ff 0300 04ff 0500 06ff 0700
          ^^^^ ^^^^ ^^^^ ^^^^  (16-bit samples en little-endian)

# Incorrect (WAV header)
RIFF....WAVE....data.... (non-acceptable!)
```

---

## 4. Format Réponse Serveur

**Format:** `"start_ms end_ms text\n"`

Exemple:
```
0 500 Bonjour
500 1200 comment
1200 1800 allez
1800 2400 vous
```

**Parsing en Python:**
```python
# Recevoir
data = socket.recv(4096)
text = data.decode('utf-8').strip()  # "0 500 Bonjour"

# Parser
parts = text.split(' ', 2)
start_ms = float(parts[0])  # 0
end_ms = float(parts[1])    # 500
transcription = parts[2]    # "Bonjour"
```

---

## 5. Paramètres Clés

### Port TCP
- Default: 43007
- **Pour FreeSWITCH Bridge:** 43001 (à vérifier)

### Langue
```bash
--language fr    # Français (obligatoire pour transcription correcte)
--language en    # English
--language auto  # Auto-detect
```

### Buffering Latency
```bash
--min-chunk-size 0.3    # 300ms   (rapide, moins de contexte)
--min-chunk-size 0.5    # 500ms   (recommandé)
--min-chunk-size 1.0    # 1000ms  (default, latence haute)
```

### AlignAtt Threshold
```bash
--frame_threshold 15    # 300ms latency (moins de contexte)
--frame_threshold 25    # 500ms latency (recommandé)
--frame_threshold 50    # 1000ms latency (plus de contexte)

# Explication: 1 frame = 20ms, donc 25 frames = 500ms
```

### Modèles Disponibles
```bash
--model_path ./SimulStreaming/tiny.pt        # 39M   (rapide, moins précis)
--model_path ./SimulStreaming/base.pt        # 74M
--model_path ./SimulStreaming/small.pt       # 244M  (recommandé)
--model_path ./SimulStreaming/medium.pt      # 769M
--model_path ./SimulStreaming/large-v3.pt    # 2.9G  (meilleur, GPU requis)
```

---

## 6. Intégration FreeSWITCH Bridge

### Lancer le Bridge

```bash
# Test connexion simple
python3 freeswitch_simulstreaming_bridge.py --test-connection

# Test avec appel réel
python3 freeswitch_simulstreaming_bridge.py --test

# Bridge pour UUID spécifique
python3 freeswitch_simulstreaming_bridge.py --uuid <call_uuid>
```

### Architecture Bridge

```
FreeSWITCH (uuid_record)
    ↓ (RAW PCM 16kHz)
    ↓
tail -f (streaming depuis fichier)
    ↓
TCP socket (SimulStreamingClient)
    ↓
SimulStreaming server (port 43001)
    ↓
TCP receive
    ↓
Parse & log transcriptions
```

---

## 7. Architecture Technique Simplifiée

```
CLIENT                          SERVEUR SIMULSTREAMING
(FreeSWITCH Bridge)             (port 43001)

[ESL uuid_record]
    ↓
[tail -f /tmp/fs_*.raw]
    ↓
[TCP send PCM bytes]  ─────────→ [ServerProcessor]
                                      ↓
                                  [receive_audio_chunk()]
                                      ↓
                                  [bytes → numpy PCM]
                                      ↓
                                  [SimulWhisperOnline]
                                      ↓
                                  [PaddedAlignAttWhisper]
                                  (AlignAtt policy)
                                      ↓
                                  [tokens + timestamps]
                                      ↓
[TCP receive]  ←────────────────── [send_result()]
    ↓
[Parse "start end text"]
    ↓
[Store transcription]
```

---

## 8. Checklist Avant Lancement

- [ ] Serveur SimulStreaming démarre sans erreur
- [ ] Port 43001 est libre (ou configurer un autre)
- [ ] Modèle Whisper téléchargé (`large-v3.pt` ou `small.pt`)
- [ ] Langue spécifiée: `--language fr`
- [ ] Audio format vérifié: RAW PCM S16_LE 16kHz mono
- [ ] FreeSWITCH ESL accessible (127.0.0.1:8021)
- [ ] Dossier `/tmp` accessible pour uuid_record

---

## 9. Troubleshooting Courant

### "Connection refused" (port 43001)
```bash
# Vérifier que le serveur est lancé
netstat -tuln | grep 43001

# Vérifier firewall
sudo ufw allow 43001
```

### "No transcription received"
- Vérifier format audio: doit être RAW PCM, pas WAV
- Vérifier sample rate: doit être 16000 Hz exact
- Ajouter logs: voir stderr du serveur

### "Timeout waiting for min_chunk_size"
- Réduire `--min-chunk-size` (default: 1.0 → essayer 0.3)
- Vérifier que audio est envoyé continuellement

### "Unicode error: replacement character"
- Normal, géré automatiquement par le code
- Les caractères incomplets sont bufferisés pour le prochain chunk

---

## 10. Performance Baseline

### Avec large-v3 (GPU CUDA)
- Latency: ~500-800ms
- Throughput: 1-2 appels simultanés
- Accuracy: Meilleure
- GPU memory: ~4-6GB

### Avec small (CPU ou GPU)
- Latency: ~200-400ms
- Throughput: 5-10 appels simultanés
- Accuracy: Bonne
- Memory: ~1-2GB

---

## 11. Fichiers Importants

| Fichier | Rôle |
|---------|------|
| `SimulStreaming/simulstreaming_whisper_server.py` | Entry point serveur TCP |
| `SimulStreaming/simulstreaming_whisper.py` | Factory + Online processor |
| `SimulStreaming/whisper_streaming/whisper_server.py` | Boucle TCP + buffering |
| `freeswitch_simulstreaming_bridge.py` | FreeSWITCH integration |
| `SimulStreaming/large-v3.pt` | Modèle Whisper (2.9G) |

---

## 12. Différence avec Whisper-Streaming

| Aspect | SimulStreaming | Whisper-Streaming |
|--------|---|---|
| Policy | AlignAtt (simultaneous) | Batch processing |
| Latency | Bas (300-800ms) | Moyen (1-2s) |
| Modèle | large-v3 support | Modèles OpenAI standards |
| Beam search | Oui | Oui |
| Complexité | Haute | Basse |

SimulStreaming = Plus rapide, mais plus complexe

---

## LOGS DE DÉMARRAGE

**Succès:**
```
2024-11-16 15:12:34 | ... | INFO | Listening on 127.0.0.1:43001
2024-11-16 15:12:35 | ... | INFO | Whisper is warmed up.
2024-11-16 15:12:36 | ... | INFO | Connected to client on ('127.0.0.1', 54321)
2024-11-16 15:12:37 | ... | INFO | 0.0 500.0 Bonjour
```

**Erreur:**
```
ERROR: Address already in use (port 43001 occupe)
→ Changer port avec --port 43002
```

