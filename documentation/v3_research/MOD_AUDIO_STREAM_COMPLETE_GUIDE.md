# mod_audio_stream - Complete Technical Guide

## Table of Contents
1. [Overview](#overview)
2. [Installation & Configuration](#installation--configuration)
3. [Command Reference](#command-reference)
4. [Audio Direction Deep Dive](#audio-direction-deep-dive)
5. [WebSocket Protocol](#websocket-protocol)
6. [Channel Variables](#channel-variables)
7. [Events System](#events-system)
8. [Integration Patterns](#integration-patterns)
9. [Performance & Optimization](#performance--optimization)
10. [Troubleshooting](#troubleshooting)
11. [Complete Examples](#complete-examples)

---

## Overview

### What is mod_audio_stream?

**mod_audio_stream** is a FreeSWITCH module that streams L16 (Linear 16-bit PCM) audio from a call channel to a WebSocket endpoint in real-time. It enables bidirectional audio streaming, allowing you to:
- Send live audio to external services (Speech-to-Text, AI engines, analytics)
- Receive audio responses from WebSocket servers for playback
- Implement real-time voice processing, transcription, and conversational AI

### Key Features

- **Full-duplex streaming**: Simultaneous audio capture and playback
- **Multiple audio formats**: Raw binary PCM or Base64-encoded audio
- **Flexible direction control**: Capture inbound, outbound, or both audio streams
- **Low-latency design**: Uses libevent-based libwsc, optimized for real-time streaming
- **Dynamic control**: Pause, resume, and gracefully shutdown streams mid-call
- **Automatic processing**: Handles resampling, transcoding, buffering, and queuing
- **Secure connections**: Full TLS/WSS support with certificate validation

### Primary Use Cases

1. **Real-time Speech-to-Text (STT)**: Stream caller audio to transcription services (Google, AWS, Azure, Vosk, Whisper)
2. **Barge-in Detection**: Monitor caller speech during TTS playback to interrupt when user speaks
3. **Conversational AI**: Integrate with AI engines (DialogFlow, IBM Watson, custom LLMs)
4. **Call Recording & Analytics**: Stream audio to analysis services for sentiment, compliance, quality monitoring
5. **Real-time Translation**: Send audio to translation services for multilingual support
6. **Voice Biometrics**: Stream for speaker verification and authentication

### Architecture Overview

```
┌─────────────────┐
│   SIP Call      │
│   (Caller)      │
└────────┬────────┘
         │ RTP Audio
         ↓
┌─────────────────────────────────┐
│      FreeSWITCH Server          │
│  ┌───────────────────────────┐  │
│  │   mod_audio_stream        │  │
│  │   (Media Bug Attached)    │  │
│  │                           │  │
│  │  • Captures audio         │  │
│  │  • Converts to L16 PCM    │  │
│  │  • Buffers & queues       │  │
│  │  • Resamples if needed    │  │
│  └───────────┬───────────────┘  │
└──────────────┼──────────────────┘
               │ WebSocket (L16 PCM)
               ↓
┌─────────────────────────────────┐
│   WebSocket Server              │
│   (Python/Node.js/etc)          │
│                                 │
│  • Receives L16 audio chunks    │
│  • Processes (STT/AI/etc)       │
│  • Sends responses (text/audio) │
└─────────────────────────────────┘
```

---

## Installation & Configuration

### Dependencies

#### Debian/Ubuntu
```bash
sudo apt-get update
sudo apt-get install -y \
    libfreeswitch-dev \
    libssl-dev \
    zlib1g-dev \
    libevent-dev \
    libspeexdsp-dev
```

#### CentOS/RHEL
```bash
sudo yum install -y \
    freeswitch-devel \
    openssl-devel \
    zlib-devel \
    libevent-devel \
    speexdsp-devel
```

### Building from Source

#### Method 1: Standard Build (amigniter/mod_audio_stream)

```bash
# Clone the repository
git clone https://github.com/amigniter/mod_audio_stream.git
cd mod_audio_stream

# Initialize submodules
git submodule init && git submodule update

# Build
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make

# Install
sudo make install
```

#### Method 2: Build with TLS/WSS Support

```bash
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DUSE_TLS=ON ..
make
sudo make install
```

#### Method 3: Generate DEB Package

```bash
cd build
cpack -G DEB
sudo dpkg -i mod_audio_stream-*.deb
```

#### Alternative Implementation (sptmru/freeswitch_mod_audio_stream)

```bash
git clone https://github.com/sptmru/freeswitch_mod_audio_stream.git
cd freeswitch_mod_audio_stream
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make
sudo make install
```

**Key Differences:**
- Uses ixwebsocket library instead of libwsc
- Static compilation of WebSocket dependencies
- Inspired by mod_audio_fork architecture

### Module Loading

#### Add to modules.conf.xml

Edit `/etc/freeswitch/autoload_configs/modules.conf.xml` (or `/usr/local/freeswitch/conf/autoload_configs/modules.conf.xml`):

```xml
<configuration name="modules.conf" description="Modules">
  <modules>
    <!-- ... other modules ... -->

    <!-- Load mod_audio_stream -->
    <load module="mod_audio_stream"/>

  </modules>
</configuration>
```

#### Verify Module Loaded

```bash
# From FreeSWITCH CLI (fs_cli)
freeswitch@internal> module_exists mod_audio_stream
true

# Or check loaded modules
freeswitch@internal> show modules | grep audio_stream
mod_audio_stream
```

#### Load Module Manually (without restart)

```bash
freeswitch@internal> load mod_audio_stream
+OK Reloading XML
+OK
```

---

## Command Reference

### uuid_audio_stream

The primary API command for controlling audio streaming.

#### Full Syntax

```
uuid_audio_stream <uuid> <action> [parameters...]
```

### Actions Overview

| Action | Description | Parameters |
|--------|-------------|------------|
| `start` | Begin audio streaming to WebSocket | `<url> <mix-type> <sample-rate> [metadata]` |
| `stop` | Stop streaming and close connection | `[metadata]` |
| `send_text` | Send text message to WebSocket | `<metadata>` |
| `pause` | Pause audio streaming (keep connection) | None |
| `resume` | Resume paused audio stream | None |
| `graceful-shutdown` | Gracefully close stream | None |

---

### START Command

Initiates audio streaming to a WebSocket endpoint.

#### Syntax
```
uuid_audio_stream <uuid> start <url> <mix-type> <sample-rate> [metadata]
```

#### Parameters

**`<uuid>`** (Required)
- The unique identifier of the FreeSWITCH channel/call
- Obtain via `${uuid}` in dialplan or from ESL events
- Example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`

**`<url>`** (Required)
- WebSocket endpoint URL
- Formats: `ws://host:port/path` or `wss://host:port/path`
- Examples:
  - `ws://localhost:8080/audio`
  - `wss://api.example.com/transcribe`
  - `ws://10.0.1.100:9000/stt?lang=en`

**`<mix-type>`** (Required)
- Controls which audio stream(s) to capture
- Options:
  - **`mono`**: Single-channel, inbound audio only (what the FreeSWITCH leg is receiving)
  - **`mixed`**: Both parties mixed into mono (bidirectional, single channel)
  - **`stereo`**: Two-channel output (left=inbound, right=outbound)

**`<sample-rate>`** (Required)
- Audio sampling rate for the stream
- Options:
  - **`8000`** or **`8k`**: 8 kHz narrowband (telephone quality)
  - **`16000`** or **`16k`**: 16 kHz wideband (higher quality)
  - Custom rates: Must be multiples of 8000 (e.g., 24000, 48000)
- Default FreeSWITCH rate: 8000 Hz
- Module automatically resamples if needed

**`[metadata]`** (Optional)
- JSON string or text metadata sent with initial connection
- Must be valid UTF-8
- Examples:
  - `{"call_id": "12345", "language": "en-US"}`
  - `caller_id=+15551234567`

#### Examples

**Basic STT streaming (mono, 8kHz):**
```bash
uuid_audio_stream a1b2c3d4-e5f6-7890-abcd-ef1234567890 start ws://localhost:8080/stt mono 8000
```

**High-quality bidirectional streaming:**
```bash
uuid_audio_stream ${uuid} start wss://api.transcribe.com/stream mixed 16000 '{"language":"en-US"}'
```

**Stereo recording to separate channels:**
```bash
uuid_audio_stream ${uuid} start ws://recorder.local:9000/record stereo 16k
```

**Via ESL (Python example):**
```python
import ESL

con = ESL.ESLconnection('localhost', '8021', 'ClueCon')
uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
url = "ws://localhost:8080/transcribe"
metadata = '{"caller_id": "+15551234567"}'

cmd = f"uuid_audio_stream {uuid} start {url} mono 8000 {metadata}"
con.api(cmd)
```

---

### STOP Command

Stops audio streaming and closes the WebSocket connection.

#### Syntax
```
uuid_audio_stream <uuid> stop [metadata]
```

#### Parameters

**`[metadata]`** (Optional)
- Final message sent to WebSocket before closing
- Example: `{"reason": "call_ended", "duration": 45}`

#### Examples

```bash
# Simple stop
uuid_audio_stream ${uuid} stop

# Stop with metadata
uuid_audio_stream ${uuid} stop '{"reason":"user_hangup"}'
```

**Via ESL (Python):**
```python
con.api(f"uuid_audio_stream {uuid} stop")
```

---

### SEND_TEXT Command

Sends a text message to the WebSocket server without affecting audio streaming.

#### Syntax
```
uuid_audio_stream <uuid> send_text <metadata>
```

#### Use Cases
- Send intermediate events (e.g., DTMF pressed, call transferred)
- Update context information (e.g., menu selection changed)
- Send control commands to the WebSocket server

#### Examples

```bash
# Send DTMF event
uuid_audio_stream ${uuid} send_text '{"event":"dtmf","digit":"1"}'

# Send context update
uuid_audio_stream ${uuid} send_text '{"context":"main_menu","intent":"billing"}'

# Send custom command
uuid_audio_stream ${uuid} send_text '{"command":"switch_language","lang":"es-ES"}'
```

---

### PAUSE Command

Pauses audio streaming while keeping the WebSocket connection alive.

#### Syntax
```
uuid_audio_stream <uuid> pause
```

#### Use Cases
- Temporarily stop sending audio during sensitive information entry (credit card, SSN)
- Pause during internal transfers or holds
- Reduce bandwidth during silence periods

#### Examples

```bash
# Pause streaming
uuid_audio_stream ${uuid} pause

# In dialplan - pause before collecting sensitive data
<action application="set" data="exec_after_answer=uuid_audio_stream ${uuid} pause"/>
<action application="read" data="1 16 ivr/ivr-enter_pin.wav pin 5000 #"/>
<action application="set" data="exec_after_answer=uuid_audio_stream ${uuid} resume"/>
```

---

### RESUME Command

Resumes a paused audio stream.

#### Syntax
```
uuid_audio_stream <uuid> resume
```

#### Examples

```bash
# Resume streaming
uuid_audio_stream ${uuid} resume
```

---

### GRACEFUL-SHUTDOWN Command

Gracefully closes the audio stream with proper cleanup.

#### Syntax
```
uuid_audio_stream <uuid> graceful-shutdown
```

#### Difference from STOP
- `graceful-shutdown`: Ensures all buffered audio is sent before closing
- `stop`: Immediate closure, may drop buffered audio

#### Examples

```bash
uuid_audio_stream ${uuid} graceful-shutdown
```

---

## Audio Direction Deep Dive

Understanding audio direction is critical for proper mod_audio_stream usage.

### FreeSWITCH Media Bug Flags

Internally, mod_audio_stream uses FreeSWITCH media bug flags to control audio capture:

| Flag | Description | Direction |
|------|-------------|-----------|
| `SMBF_READ_STREAM` | Captures inbound audio (what the call leg receives) | Read |
| `SMBF_WRITE_STREAM` | Captures outbound audio (what the call leg sends) | Write |
| `SMBF_READ_STREAM \| SMBF_WRITE_STREAM` | Captures both directions | Both |
| `SMBF_STEREO` | Two-channel output (requires WRITE_STREAM) | Stereo |

**Key Concept:**
- **READ buffer** = Audio coming TO the FreeSWITCH channel (inbound)
- **WRITE buffer** = Audio going FROM the FreeSWITCH channel (outbound)

---

### MONO Direction

**Mix-type:** `mono`

**Media Bug Flags:** `SMBF_READ_STREAM`

**What it captures:**
- **Inbound audio only** - what the FreeSWITCH call leg is receiving
- If FreeSWITCH is playing TTS, you capture the TTS audio
- If the remote party is speaking, you capture their speech

**Use Cases:**
1. **Barge-in Detection during TTS playback**
   - FreeSWITCH plays TTS to caller
   - Caller speech interrupts TTS
   - You want to detect when caller speaks (to stop TTS)
   - **Problem:** `mono` captures the TTS, NOT the caller!
   - **Solution:** Use dialplan to flip audio direction, or use `mixed`/`stereo`

2. **Monitoring IVR prompts**
   - Verify TTS/audio being played to callers
   - Quality assurance of prompts

**Example:**
```bash
# Playing TTS, want to monitor what caller hears
uuid_audio_stream ${uuid} start ws://localhost:8080/monitor mono 8000
```

**Important Caveat:**
For barge-in detection, `mono` alone won't work as expected because it captures the wrong direction. See "Barge-in Detection Implementation" below.

---

### MIXED Direction

**Mix-type:** `mixed`

**Media Bug Flags:** `SMBF_READ_STREAM | SMBF_WRITE_STREAM`

**What it captures:**
- **Both directions mixed into a single mono channel**
- Inbound + outbound audio combined
- Both parties' speech in one stream

**Audio Processing:**
- FreeSWITCH mixes the two streams by buffering both directions
- Output is synchronized mono audio
- Sample format: L16 PCM mono

**Use Cases:**
1. **Real-time transcription of full conversation**
   - Capture both caller and agent speech
   - STT engine receives mixed audio
   - Transcription shows both parties

2. **Call recording to single channel**
   - Simple mono recording of entire call
   - Lower bandwidth than stereo

3. **Sentiment analysis**
   - Analyze overall call sentiment
   - Both parties contribute to emotion detection

4. **Barge-in detection (alternative approach)**
   - Mixed audio includes both TTS and caller speech
   - Use Voice Activity Detection (VAD) to separate
   - More complex but captures everything

**Example:**
```bash
# Full conversation transcription
uuid_audio_stream ${uuid} start wss://stt.example.com/transcribe mixed 16000 '{"language":"en-US"}'
```

**Advantages:**
- Lower bandwidth (single channel)
- Simpler processing for full conversation capture
- Both parties captured reliably

**Disadvantages:**
- Cannot separate speakers without additional processing
- Overlapping speech can confuse STT engines
- Harder to implement barge-in detection

---

### STEREO Direction

**Mix-type:** `stereo`

**Media Bug Flags:** `SMBF_WRITE_STREAM | SMBF_STEREO`

**What it captures:**
- **Two-channel audio (left and right)**
- **Left channel:** Inbound audio (read stream)
- **Right channel:** Outbound audio (write stream)
- Completely separated speaker channels

**Audio Processing:**
- Two independent L16 PCM streams
- Left/right interleaved in audio frames
- Sample format: L16 PCM stereo

**Use Cases:**
1. **Barge-in detection (BEST approach)**
   - Left channel: TTS being played to caller
   - Right channel: Caller's speech
   - Detect speech on right channel = barge-in!
   - Clean separation, no mixing needed

2. **Speaker diarization**
   - Perfect for "who said what"
   - Each speaker on separate channel
   - High accuracy transcription with speaker labels

3. **Call recording with speaker separation**
   - Caller on one channel, agent on other
   - Post-call analysis per speaker
   - Quality monitoring for agents

4. **Advanced AI processing**
   - Separate emotion analysis per speaker
   - Different AI models for caller vs. agent
   - Independent voice biometrics

**Example:**
```bash
# Barge-in detection with clean separation
uuid_audio_stream ${uuid} start ws://localhost:8080/barge_detect stereo 16000

# Call recording with speaker separation
uuid_audio_stream ${uuid} start wss://recorder.com/calls stereo 8000 '{"call_id":"12345"}'
```

**WebSocket Receives:**
- Interleaved stereo L16 PCM
- Each frame: [L-sample1, R-sample1, L-sample2, R-sample2, ...]
- Separate channels in your server for processing

**Advantages:**
- Perfect speaker separation
- Best for barge-in detection
- Enables per-speaker analysis
- No crosstalk or mixing issues

**Disadvantages:**
- Double bandwidth (two channels)
- More complex processing required
- Must handle stereo deinterleaving

---

### Audio Direction Summary Table

| Mix-Type | Channels | Captures | Best For | Bandwidth |
|----------|----------|----------|----------|-----------|
| `mono` | 1 | Inbound only (READ) | TTS monitoring, IVR QA | Lowest |
| `mixed` | 1 | Both mixed (READ+WRITE) | Full conversation STT, recording | Low |
| `stereo` | 2 | Separated (L=READ, R=WRITE) | Barge-in, speaker diarization | High |

---

### Practical Direction Choice Guide

**Question: What do I need to capture?**

1. **Only what's being played to the caller (TTS, prompts)** → Use `mono`
2. **Full conversation, mixed together** → Use `mixed`
3. **Both parties, but separated** → Use `stereo`

**Question: What's my use case?**

1. **Barge-in detection** → Use `stereo` (best) or `mixed` (acceptable)
2. **Full conversation transcription** → Use `mixed` or `stereo`
3. **Call recording** → Use `stereo` (better) or `mixed` (simpler)
4. **IVR prompt monitoring** → Use `mono`
5. **Speaker diarization** → Use `stereo` (required)

---

## WebSocket Protocol

### Connection Flow

```
1. FreeSWITCH initiates WebSocket handshake
   ↓
2. WebSocket server accepts connection
   ↓
3. FreeSWITCH sends initial metadata (if provided)
   ↓
4. Audio streaming begins (L16 PCM chunks)
   ↓
5. Server can send responses (text or audio)
   ↓
6. Bidirectional communication continues
   ↓
7. Connection closed (via stop/hangup)
```

### Audio Data Format

#### L16 PCM Specification

**Format:** Linear 16-bit Pulse-Code Modulation (LPCM)
- **Encoding:** Signed 16-bit integers
- **Endianness:** Big-endian (network byte order)
- **Sample range:** -32768 to +32767
- **Bit depth:** 16 bits per sample
- **Uncompressed:** No codec applied

#### Sample Rates

| Rate | Description | Bandwidth (mono) | Bandwidth (stereo) |
|------|-------------|------------------|---------------------|
| 8000 Hz | Narrowband (telephone quality) | 128 kbps | 256 kbps |
| 16000 Hz | Wideband (HD voice) | 256 kbps | 512 kbps |

**Bandwidth Calculation:**
```
Bitrate = Sample_Rate × Bit_Depth × Channels
Example (8kHz mono): 8000 samples/sec × 16 bits × 1 channel = 128,000 bps = 128 kbps
Example (16kHz stereo): 16000 × 16 × 2 = 512 kbps
```

**Network Overhead:**
- Add 40 bytes per packet for IP+UDP+RTP headers
- WebSocket framing overhead varies
- Actual bandwidth ~10-15% higher than codec bitrate

### Frame Structure

#### Buffer Size (Chunk Duration)

Controlled by `STREAM_BUFFER_SIZE` channel variable (default: 20ms)

**20ms chunk at 8kHz mono:**
```
Samples per chunk = 8000 samples/sec × 0.020 sec = 160 samples
Bytes per chunk = 160 samples × 2 bytes/sample = 320 bytes
```

**20ms chunk at 16kHz stereo:**
```
Samples per chunk = 16000 × 0.020 × 2 channels = 640 samples
Bytes per chunk = 640 × 2 = 1280 bytes
```

**100ms chunk at 8kHz mono (custom buffer):**
```
Samples = 8000 × 0.100 = 800 samples
Bytes = 800 × 2 = 1600 bytes
```

#### WebSocket Message Format

**Binary Frame (Raw PCM):**
```
WebSocket Binary Frame
├── Header (WebSocket framing)
└── Payload: Raw L16 PCM bytes
    ├── [Sample 1 MSB][Sample 1 LSB]
    ├── [Sample 2 MSB][Sample 2 LSB]
    └── ... (continues for buffer duration)
```

**Stereo Interleaving:**
```
[L1_MSB][L1_LSB][R1_MSB][R1_LSB][L2_MSB][L2_LSB][R2_MSB][R2_LSB]...
 └─ Left Ch ─┘ └─ Right Ch ─┘ └─ Left Ch ─┘ └─ Right Ch ─┘
```

**Base64 Encoded (alternative):**
- WebSocket text frame
- Payload: Base64 encoded L16 PCM
- Use when binary WebSocket not supported
- ~33% larger than raw binary

### Server-Side Processing

#### Receiving Audio (Python Example)

```python
import websocket
import struct
import numpy as np

def on_message(ws, message):
    # message is raw binary L16 PCM

    # Convert bytes to 16-bit signed integers (big-endian)
    samples = struct.unpack(f'>{len(message)//2}h', message)

    # Convert to numpy array for processing
    audio_array = np.array(samples, dtype=np.int16)

    # For stereo, deinterleave channels
    if stereo:
        left_channel = audio_array[0::2]
        right_channel = audio_array[1::2]

    # Process audio (send to STT, analyze, etc.)
    process_audio(audio_array)

def on_open(ws):
    print("WebSocket connection opened")

ws = websocket.WebSocketApp("ws://localhost:8080/audio",
                           on_message=on_message,
                           on_open=on_open)
ws.run_forever()
```

#### Receiving Audio (Node.js Example)

```javascript
const WebSocket = require('ws');

const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws) => {
    console.log('Client connected');

    ws.on('message', (message) => {
        // message is Buffer containing raw L16 PCM

        // Convert to 16-bit signed integers (big-endian)
        const samples = [];
        for (let i = 0; i < message.length; i += 2) {
            samples.push(message.readInt16BE(i));
        }

        // For stereo, separate channels
        const leftChannel = samples.filter((_, i) => i % 2 === 0);
        const rightChannel = samples.filter((_, i) => i % 2 === 1);

        // Process audio
        processAudio(samples);
    });
});
```

### Sending Audio Responses

The module supports receiving audio from the WebSocket server for playback.

#### Audio Playback JSON Format

```json
{
  "type": "streamAudio",
  "data": {
    "audioDataType": "raw",
    "sampleRate": 8000,
    "audioData": "BASE64_ENCODED_AUDIO_DATA"
  }
}
```

#### Supported Audio Types

| Type | Description | Encoding |
|------|-------------|----------|
| `raw` | Raw L16 PCM | Base64 encoded PCM |
| `wav` | WAV file | Base64 encoded WAV |
| `mp3` | MP3 file | Base64 encoded MP3 |
| `ogg` | Ogg Vorbis | Base64 encoded OGG |

#### Sample Rate Matching

- If `sampleRate` matches channel codec (e.g., PCMU/PCMA at 8kHz), audio plays directly (fastest)
- If different, module resamples and transcodes (microsecond-level speed)
- For optimal performance, return audio in channel's native format

#### Codec Optimization

**Best Performance:**
- Channel using PCMU (G.711 μ-law)
- Return audio as PCMU at 8kHz
- Module skips resampling and transcoding, plays directly

**Good Performance:**
- Return raw L16 PCM
- Module handles transcoding efficiently

**Avoid:**
- Returning PCMU/PCMA when channel uses different codec
- Audio won't play back

#### Playback Example (Python Server)

```python
import base64
import json

def send_audio_response(ws, audio_bytes, sample_rate=8000):
    """Send audio to FreeSWITCH for playback"""

    # Base64 encode audio
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    # Create response JSON
    response = {
        "type": "streamAudio",
        "data": {
            "audioDataType": "raw",
            "sampleRate": sample_rate,
            "audioData": audio_b64
        }
    }

    # Send to FreeSWITCH
    ws.send(json.dumps(response))
```

#### Temporary File Management

- Audio files received from WebSocket are saved to `/tmp/`
- Files auto-deleted on session termination
- Module uses ESL internally: `uuid_broadcast <uuid> /tmp/<file> both`

---

## Channel Variables

Channel variables configure mod_audio_stream behavior. Set these in dialplan or via ESL.

### Configuration Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STREAM_MESSAGE_DEFLATE` | Boolean | `false` | Enable per-message deflate compression |
| `STREAM_HEART_BEAT` | Integer (seconds) | `0` (off) | WebSocket keep-alive ping interval |
| `STREAM_SUPPRESS_LOG` | Boolean | `false` | Suppress WebSocket response logging |
| `STREAM_BUFFER_SIZE` | Integer (ms) | `20` | Audio chunk duration (divisible by 20) |
| `STREAM_EXTRA_HEADERS` | JSON Object | `null` | Custom HTTP headers for WebSocket handshake |
| `STREAM_TLS_CA_FILE` | String (path) | `SYSTEM` | CA certificate file for WSS validation |
| `STREAM_TLS_CERT_FILE` | String (path) | `null` | Client certificate for mutual TLS |
| `STREAM_TLS_KEY_FILE` | String (path) | `null` | Client private key for mutual TLS |
| `STREAM_TLS_DISABLE_HOSTNAME_VALIDATION` | Boolean | `false` | Skip hostname verification (insecure) |
| `STREAM_PLAYBACK` | Boolean | `false` | Enable audio playback from WebSocket |
| `STREAM_SAMPLE_RATE` | Integer | (auto) | Required for raw binary playback |

---

### Detailed Variable Descriptions

#### STREAM_MESSAGE_DEFLATE

**Purpose:** Enable WebSocket per-message deflate compression (RFC 7692)

**Benefits:**
- Significant bandwidth savings (30-70% reduction)
- Lower data transfer costs
- Faster transmission on slow networks

**Tradeoffs:**
- Minimal CPU overhead for compression/decompression
- Slightly increased latency (negligible)

**Usage:**
```xml
<!-- In dialplan -->
<action application="set" data="STREAM_MESSAGE_DEFLATE=true"/>
```

```python
# Via ESL
con.execute("set", f"STREAM_MESSAGE_DEFLATE=true", uuid)
```

**Recommendation:** Enable for production deployments

---

#### STREAM_HEART_BEAT

**Purpose:** Send WebSocket ping frames at regular intervals to keep connection alive

**Why needed:**
- Load balancers may close idle connections (default timeout: 60-300s)
- Firewalls may drop silent connections
- Ensures connection liveness

**Usage:**
```xml
<!-- Send ping every 30 seconds -->
<action application="set" data="STREAM_HEART_BEAT=30"/>
```

**Recommendation:**
- Set to 30-60 seconds for production
- Lower if behind aggressive load balancers (e.g., 15 seconds)

---

#### STREAM_SUPPRESS_LOG

**Purpose:** Suppress logging of WebSocket responses to avoid log flooding

**When to use:**
- High-volume deployments
- Receiving many responses per second
- Log file size concerns

**Usage:**
```xml
<action application="set" data="STREAM_SUPPRESS_LOG=true"/>
```

**Recommendation:** Enable in production, disable for debugging

---

#### STREAM_BUFFER_SIZE

**Purpose:** Control audio chunk duration sent to WebSocket

**Constraints:**
- Must be divisible by 20
- Valid values: 20, 40, 60, 80, 100, 120, ... (ms)

**Impact:**

| Buffer Size | Chunks/sec | Latency | Use Case |
|-------------|------------|---------|----------|
| 20 ms | 50 | Lowest | Real-time STT, barge-in |
| 60 ms | ~17 | Low | Balanced performance |
| 100 ms | 10 | Medium | Batch processing |
| 200 ms | 5 | Higher | Non-real-time analysis |

**Latency vs. Efficiency:**
- Smaller buffers = lower latency, more WebSocket overhead
- Larger buffers = higher latency, fewer messages, more efficient

**Usage:**
```xml
<!-- 100ms chunks for balanced performance -->
<action application="set" data="STREAM_BUFFER_SIZE=100"/>
```

**Recommendation:**
- Barge-in detection: 20ms
- STT transcription: 60-100ms
- Call recording: 100-200ms

---

#### STREAM_EXTRA_HEADERS

**Purpose:** Add custom HTTP headers to WebSocket handshake

**Format:** JSON object with key-value pairs

**Use Cases:**
- Authentication tokens
- API keys
- Custom routing information
- Client identification

**Usage:**
```xml
<action application="set" data='STREAM_EXTRA_HEADERS={"Authorization":"Bearer TOKEN123","X-Client-ID":"freeswitch-prod"}'/>
```

```python
# Via ESL
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1...",
    "X-Call-ID": call_id,
    "X-Client": "freeswitch-v1.10"
}
con.execute("set", f"STREAM_EXTRA_HEADERS={json.dumps(headers)}", uuid)
```

**Server-Side Verification (Python):**
```python
from websocket_server import WebsocketServer

def on_connect(client, server):
    headers = server.request.headers
    auth_token = headers.get('Authorization')
    if not verify_token(auth_token):
        server.deny_new_connections(client)
```

---

#### TLS/WSS Configuration

**Purpose:** Secure WebSocket connections with TLS/SSL

**STREAM_TLS_CA_FILE**
- Path to CA certificate bundle for server validation
- Default: System CA bundle (`SYSTEM`)
- Example: `/etc/ssl/certs/ca-certificates.crt`

**STREAM_TLS_CERT_FILE** & **STREAM_TLS_KEY_FILE**
- Client certificate and key for mutual TLS (mTLS)
- Required when WebSocket server demands client authentication

**STREAM_TLS_DISABLE_HOSTNAME_VALIDATION**
- Skips hostname verification (useful for testing, NOT production)
- **Security risk:** Vulnerable to man-in-the-middle attacks

**Usage:**
```xml
<!-- Standard WSS with system CA -->
<action application="set" data="STREAM_TLS_CA_FILE=SYSTEM"/>

<!-- Custom CA certificate -->
<action application="set" data="STREAM_TLS_CA_FILE=/etc/ssl/custom-ca.crt"/>

<!-- Mutual TLS (client cert authentication) -->
<action application="set" data="STREAM_TLS_CERT_FILE=/etc/ssl/client.crt"/>
<action application="set" data="STREAM_TLS_KEY_FILE=/etc/ssl/client.key"/>

<!-- Disable validation (TESTING ONLY) -->
<action application="set" data="STREAM_TLS_DISABLE_HOSTNAME_VALIDATION=true"/>
```

---

#### STREAM_PLAYBACK

**Purpose:** Enable receiving audio from WebSocket for playback

**Requirement:** Must be set to receive audio responses

**Usage:**
```xml
<action application="set" data="STREAM_PLAYBACK=true"/>
```

**With raw binary audio:**
```xml
<action application="set" data="STREAM_PLAYBACK=true"/>
<action application="set" data="STREAM_SAMPLE_RATE=8000"/>
```

---

### Complete Configuration Example

```xml
<extension name="audio_stream_stt">
  <condition field="destination_number" expression="^9999$">

    <!-- Configure audio streaming -->
    <action application="set" data="STREAM_MESSAGE_DEFLATE=true"/>
    <action application="set" data="STREAM_HEART_BEAT=30"/>
    <action application="set" data="STREAM_BUFFER_SIZE=60"/>
    <action application="set" data="STREAM_SUPPRESS_LOG=false"/>
    <action application="set" data='STREAM_EXTRA_HEADERS={"Authorization":"Bearer SECRET_TOKEN"}'/>
    <action application="set" data="STREAM_PLAYBACK=true"/>

    <!-- Answer call -->
    <action application="answer"/>

    <!-- Start audio streaming via ESL or inline -->
    <action application="set" data="api_result=${uuid_audio_stream(${uuid} start ws://localhost:8080/stt stereo 16000)}"/>

    <!-- Continue dialplan... -->
    <action application="playback" data="ivr/ivr-welcome.wav"/>

  </condition>
</extension>
```

---

## Events System

mod_audio_stream generates custom events to notify FreeSWITCH applications of stream activity.

### Event Types

| Event Subclass | Trigger | Data Included |
|----------------|---------|---------------|
| `mod_audio_stream::json` | WebSocket server sends JSON response | Full JSON payload |
| `mod_audio_stream::connect` | WebSocket connection established | Connection metadata |
| `mod_audio_stream::disconnect` | Connection closed | Closure code, reason |
| `mod_audio_stream::error` | Connection error | Error code, description |
| `mod_audio_stream::play` | Audio playback instruction | Audio file path, format |

---

### Event: mod_audio_stream::json

**Trigger:** WebSocket server sends text message (typically JSON)

**Event Headers:**
```
Event-Name: CUSTOM
Event-Subclass: mod_audio_stream::json
Unique-ID: <uuid>
```

**Event Body:**
```json
{
  "transcript": "Hello, how can I help you?",
  "confidence": 0.95,
  "is_final": true
}
```

**Listening for Events (ESL Python):**
```python
import ESL

con = ESL.ESLconnection('localhost', '8021', 'ClueCon')
con.events('plain', 'CUSTOM mod_audio_stream::json')

while True:
    e = con.recvEvent()
    if e:
        body = e.getBody()
        uuid = e.getHeader('Unique-ID')
        print(f"Call {uuid}: {body}")
```

**Use Cases:**
- Receive real-time transcription results
- Get STT interim and final results
- Receive AI agent responses
- Handle custom events from WebSocket server

---

### Event: mod_audio_stream::connect

**Trigger:** WebSocket connection successfully established

**Event Headers:**
```
Event-Name: CUSTOM
Event-Subclass: mod_audio_stream::connect
Unique-ID: <uuid>
Connection-URL: ws://localhost:8080/stt
```

**Use Cases:**
- Verify connection before proceeding
- Log connection events
- Trigger dependent actions

---

### Event: mod_audio_stream::disconnect

**Trigger:** WebSocket connection closed

**Event Headers:**
```
Event-Name: CUSTOM
Event-Subclass: mod_audio_stream::disconnect
Unique-ID: <uuid>
Closure-Code: 1000
Closure-Reason: Normal closure
```

**WebSocket Closure Codes:**

| Code | Name | Description |
|------|------|-------------|
| 1000 | Normal Closure | Clean shutdown |
| 1001 | Going Away | Server shutting down |
| 1002 | Protocol Error | WebSocket protocol violation |
| 1003 | Unsupported Data | Invalid message type |
| 1006 | Abnormal Closure | No close frame (network issue) |
| 1011 | Internal Error | Server error |

**Use Cases:**
- Detect unexpected disconnections
- Trigger reconnection logic
- Log connection failures
- Alert monitoring systems

---

### Event: mod_audio_stream::error

**Trigger:** Connection error occurred

**Event Headers:**
```
Event-Name: CUSTOM
Event-Subclass: mod_audio_stream::error
Unique-ID: <uuid>
Error-Code: 6
Error-Description: DNS resolution failed
```

**Error Codes:**

| Code | Type | Description | Action |
|------|------|-------------|--------|
| 1 | IO | Socket read/write error | Check network connectivity |
| 6 | CONNECT_FAILED | DNS/TCP connection failure | Verify URL, DNS, firewall |
| 7 | TLS_INIT_FAILED | SSL/TLS initialization error | Check TLS configuration |
| 8 | SSL_HANDSHAKE_FAILED | TLS negotiation failure | Verify certificates |
| 9 | SSL_ERROR | OpenSSL error (cert/cipher) | Check certificate validity |

**Use Cases:**
- Debug connection issues
- Implement retry logic
- Alert on repeated failures
- Track error rates

---

### Event: mod_audio_stream::play

**Trigger:** Audio playback instruction received from WebSocket

**Event Headers:**
```
Event-Name: CUSTOM
Event-Subclass: mod_audio_stream::play
Unique-ID: <uuid>
Audio-File: /tmp/audio_stream_12345.raw
Audio-Format: raw
Sample-Rate: 8000
```

**Use Cases:**
- Track playback events
- Verify audio received
- Debug playback issues

---

### Event Handling Best Practices

1. **Always subscribe to error and disconnect events** for production reliability
2. **Use event-based architecture** instead of polling for responses
3. **Implement timeouts** - if no connect event within X seconds, assume failure
4. **Log all events** for troubleshooting and analytics
5. **Handle reconnections gracefully** on disconnect events

---

## Integration Patterns

### Pattern 1: ESL (Event Socket Library) Integration

The most common integration approach using FreeSWITCH ESL.

#### Python ESL Example - Complete Flow

```python
import ESL
import json
import time

class AudioStreamController:
    def __init__(self, host='localhost', port=8021, password='ClueCon'):
        self.con = ESL.ESLconnection(host, str(port), password)
        if not self.con.connected():
            raise Exception("Failed to connect to FreeSWITCH")

        # Subscribe to events
        self.con.events('plain', 'CUSTOM mod_audio_stream::json')
        self.con.events('plain', 'CUSTOM mod_audio_stream::error')
        self.con.events('plain', 'CUSTOM mod_audio_stream::disconnect')

    def start_streaming(self, uuid, ws_url, mix_type='stereo', sample_rate=16000, metadata=None):
        """Start audio streaming for a call"""
        metadata_str = json.dumps(metadata) if metadata else ''
        cmd = f"uuid_audio_stream {uuid} start {ws_url} {mix_type} {sample_rate} {metadata_str}"

        result = self.con.api(cmd)
        return result.getBody() == '+OK'

    def stop_streaming(self, uuid):
        """Stop audio streaming"""
        result = self.con.api(f"uuid_audio_stream {uuid} stop")
        return result.getBody() == '+OK'

    def send_text(self, uuid, text):
        """Send text to WebSocket"""
        result = self.con.api(f"uuid_audio_stream {uuid} send_text {json.dumps(text)}")
        return result.getBody() == '+OK'

    def handle_events(self):
        """Process events from FreeSWITCH"""
        while True:
            e = self.con.recvEvent()
            if not e:
                continue

            event_name = e.getHeader('Event-Subclass')
            uuid = e.getHeader('Unique-ID')

            if event_name == 'mod_audio_stream::json':
                # Transcription result
                body = json.loads(e.getBody())
                print(f"Transcript: {body.get('transcript')}")

            elif event_name == 'mod_audio_stream::error':
                error_code = e.getHeader('Error-Code')
                error_desc = e.getHeader('Error-Description')
                print(f"Error {error_code}: {error_desc}")

            elif event_name == 'mod_audio_stream::disconnect':
                reason = e.getHeader('Closure-Reason')
                print(f"Disconnected: {reason}")

# Usage
controller = AudioStreamController()

# Start streaming on a call
uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
ws_url = "ws://localhost:8080/transcribe"
metadata = {"caller_id": "+15551234567", "language": "en-US"}

controller.start_streaming(uuid, ws_url, 'stereo', 16000, metadata)

# Handle events
controller.handle_events()
```

---

### Pattern 2: Dialplan Integration

Execute audio streaming directly from FreeSWITCH dialplan.

#### Example: STT-Enabled IVR

```xml
<extension name="stt_ivr">
  <condition field="destination_number" expression="^8888$">

    <!-- Set channel variables -->
    <action application="set" data="STREAM_BUFFER_SIZE=60"/>
    <action application="set" data="STREAM_MESSAGE_DEFLATE=true"/>
    <action application="set" data="STREAM_HEART_BEAT=30"/>
    <action application="set" data='STREAM_EXTRA_HEADERS={"Authorization":"Bearer TOKEN"}'/>

    <!-- Answer call -->
    <action application="answer"/>

    <!-- Start audio streaming -->
    <action application="set" data="ws_url=ws://localhost:8080/stt"/>
    <action application="set" data="metadata={&quot;caller_id&quot;:&quot;${caller_id_number}&quot;}"/>
    <action application="set" data="stream_result=${uuid_audio_stream(${uuid} start ${ws_url} stereo 16000 ${metadata})}"/>

    <!-- Play IVR prompt -->
    <action application="playback" data="ivr/ivr-how_may_i_help_you.wav"/>

    <!-- Collect input (STT running in background) -->
    <action application="sleep" data="5000"/>

    <!-- Stop streaming -->
    <action application="set" data="stop_result=${uuid_audio_stream(${uuid} stop)}"/>

    <!-- Continue based on transcription results... -->
    <action application="hangup"/>

  </condition>
</extension>
```

#### Example: Barge-in Detection with Playback

```xml
<extension name="barge_in_demo">
  <condition field="destination_number" expression="^7777$">

    <action application="answer"/>

    <!-- Configure for barge-in -->
    <action application="set" data="STREAM_BUFFER_SIZE=20"/>
    <action application="set" data="STREAM_MESSAGE_DEFLATE=true"/>

    <!-- Start stereo streaming (right channel = caller speech) -->
    <action application="set" data="stream_result=${uuid_audio_stream(${uuid} start ws://localhost:8080/barge_detect stereo 16000)}"/>

    <!-- Play long TTS message -->
    <action application="playback" data="ivr/ivr-long_welcome_message.wav"/>

    <!-- WebSocket server detects barge-in and sends stop command -->
    <!-- (Application logic handles uuid_break via ESL) -->

    <!-- Stop streaming -->
    <action application="set" data="stop_result=${uuid_audio_stream(${uuid} stop)}"/>

    <action application="hangup"/>

  </condition>
</extension>
```

---

### Pattern 3: Node.js WebSocket Server

Complete WebSocket server implementation for receiving FreeSWITCH audio.

```javascript
const WebSocket = require('ws');
const fs = require('fs');

const wss = new WebSocket.Server({ port: 8080, path: '/stt' });

wss.on('connection', (ws, req) => {
    console.log('FreeSWITCH connected');

    // Extract custom headers
    const authHeader = req.headers['authorization'];
    console.log('Auth:', authHeader);

    let audioBuffer = [];
    let sampleRate = 16000;
    let channels = 2; // stereo

    ws.on('message', (message) => {
        if (typeof message === 'string') {
            // Text message (metadata or events)
            console.log('Metadata:', message);

            // Parse initial metadata
            try {
                const metadata = JSON.parse(message);
                console.log('Call metadata:', metadata);
            } catch (e) {
                // Not JSON
            }
        } else {
            // Binary audio data (L16 PCM)
            audioBuffer.push(message);

            // Process audio chunks
            processAudioChunk(message, sampleRate, channels);

            // Send response (example: transcription result)
            const response = {
                "transcript": "Hello world",
                "confidence": 0.95,
                "is_final": true
            };
            ws.send(JSON.stringify(response));
        }
    });

    ws.on('close', (code, reason) => {
        console.log(`Connection closed: ${code} - ${reason}`);

        // Save complete audio buffer to file
        const totalAudio = Buffer.concat(audioBuffer);
        fs.writeFileSync('call_recording.raw', totalAudio);
    });

    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
    });
});

function processAudioChunk(buffer, sampleRate, channels) {
    // Convert buffer to 16-bit samples (big-endian)
    const samples = [];
    for (let i = 0; i < buffer.length; i += 2) {
        samples.push(buffer.readInt16BE(i));
    }

    if (channels === 2) {
        // Separate stereo channels
        const leftChannel = samples.filter((_, i) => i % 2 === 0);
        const rightChannel = samples.filter((_, i) => i % 2 === 1);

        console.log(`Received ${leftChannel.length} samples per channel`);

        // Process each channel separately
        // Left = inbound (TTS playback)
        // Right = outbound (caller speech) - use this for barge-in detection

        detectSpeech(rightChannel, sampleRate);
    } else {
        // Mono processing
        detectSpeech(samples, sampleRate);
    }
}

function detectSpeech(samples, sampleRate) {
    // Implement VAD (Voice Activity Detection)
    // Calculate energy/RMS
    const energy = samples.reduce((sum, s) => sum + s*s, 0) / samples.length;
    const threshold = 1000000; // Adjust based on testing

    if (energy > threshold) {
        console.log('Speech detected!');
        // For barge-in: send signal to stop TTS playback
    }
}

console.log('WebSocket server listening on ws://localhost:8080/stt');
```

---

### Pattern 4: Python WebSocket Server with Vosk STT

Real-world example using Vosk for speech recognition.

```python
import asyncio
import websockets
import json
import struct
from vosk import Model, KaldiRecognizer

# Load Vosk model
model = Model("model")

async def handle_audio_stream(websocket, path):
    """Handle incoming audio stream from FreeSWITCH"""

    # Create recognizer (16kHz, mono - will use right channel only for stereo)
    recognizer = KaldiRecognizer(model, 16000)

    print(f"Client connected: {websocket.remote_address}")

    try:
        async for message in websocket:
            if isinstance(message, str):
                # Text message (metadata)
                print(f"Metadata: {message}")
                metadata = json.loads(message)
                print(f"Call from: {metadata.get('caller_id')}")

            else:
                # Binary audio (L16 PCM)
                # Assuming stereo: extract right channel (caller speech)
                samples = struct.unpack(f'>{len(message)//2}h', message)

                # Extract right channel (every odd index)
                right_channel_samples = samples[1::2]

                # Convert back to bytes (native endianness for Vosk)
                right_channel_bytes = struct.pack(
                    f'<{len(right_channel_samples)}h',
                    *right_channel_samples
                )

                # Feed to Vosk recognizer
                if recognizer.AcceptWaveform(right_channel_bytes):
                    # Final result
                    result = json.loads(recognizer.Result())
                    transcript = result.get('text', '')

                    if transcript:
                        print(f"Final: {transcript}")

                        # Send result to FreeSWITCH
                        response = {
                            "transcript": transcript,
                            "is_final": True,
                            "confidence": 0.9
                        }
                        await websocket.send(json.dumps(response))
                else:
                    # Partial result
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get('partial', '')

                    if partial_text:
                        print(f"Partial: {partial_text}")

                        # Send interim result
                        response = {
                            "transcript": partial_text,
                            "is_final": False
                        }
                        await websocket.send(json.dumps(response))

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

    finally:
        # Final result
        final_result = json.loads(recognizer.FinalResult())
        print(f"Final transcript: {final_result.get('text')}")

# Start WebSocket server
start_server = websockets.serve(handle_audio_stream, "localhost", 8080)

print("Vosk STT WebSocket server running on ws://localhost:8080")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
```

---

### Pattern 5: Barge-in Detection Implementation

Complete implementation for detecting caller speech during TTS playback.

#### Architecture
```
FreeSWITCH → WebSocket (stereo) → Barge-in Detector
             Left: TTS audio
             Right: Caller speech
                          ↓
                  VAD on right channel
                          ↓
                  Speech detected?
                          ↓
                  Send ESL uuid_break
                          ↓
                  FreeSWITCH stops TTS
```

#### Python Barge-in Server

```python
import asyncio
import websockets
import json
import struct
import ESL

# Simple VAD using energy threshold
def detect_voice_activity(samples, threshold=2000000):
    """Simple energy-based VAD"""
    energy = sum(s*s for s in samples) / len(samples)
    return energy > threshold

async def barge_in_handler(websocket, path):
    """Detect caller speech and interrupt TTS"""

    call_uuid = None
    speech_detected = False

    # ESL connection for uuid_break
    esl = ESL.ESLconnection('localhost', '8021', 'ClueCon')

    try:
        async for message in websocket:
            if isinstance(message, str):
                # Initial metadata
                metadata = json.loads(message)
                call_uuid = metadata.get('uuid')
                print(f"Monitoring call {call_uuid} for barge-in")

            else:
                # Stereo L16 PCM audio
                samples = struct.unpack(f'>{len(message)//2}h', message)

                # Right channel = caller speech
                caller_samples = samples[1::2]

                # Detect voice activity
                if detect_voice_activity(caller_samples):
                    if not speech_detected:
                        speech_detected = True
                        print(f"BARGE-IN DETECTED on call {call_uuid}")

                        # Stop TTS playback
                        if call_uuid:
                            esl.api(f"uuid_break {call_uuid} all")
                            print("TTS playback stopped")

                        # Notify FreeSWITCH
                        response = {
                            "event": "barge_in_detected",
                            "timestamp": time.time()
                        }
                        await websocket.send(json.dumps(response))
                else:
                    # Reset if silence returns
                    if speech_detected:
                        speech_detected = False

    except websockets.exceptions.ConnectionClosed:
        print(f"Call {call_uuid} disconnected")

# Start server
start_server = websockets.serve(barge_in_handler, "localhost", 8080)

print("Barge-in detection server running on ws://localhost:8080")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
```

#### FreeSWITCH Dialplan for Barge-in

```xml
<extension name="barge_in_ivr">
  <condition field="destination_number" expression="^6666$">

    <action application="answer"/>

    <!-- Configure for low-latency barge-in -->
    <action application="set" data="STREAM_BUFFER_SIZE=20"/>
    <action application="set" data="STREAM_MESSAGE_DEFLATE=true"/>

    <!-- Start stereo streaming -->
    <action application="set" data="ws_url=ws://localhost:8080/barge_detect"/>
    <action application="set" data="metadata={&quot;uuid&quot;:&quot;${uuid}&quot;}"/>
    <action application="set" data="stream_result=${uuid_audio_stream(${uuid} start ${ws_url} stereo 16000 ${metadata})}"/>

    <!-- Play long message (can be interrupted by barge-in) -->
    <action application="set" data="playback_terminators=none"/>
    <action application="playback" data="ivr/ivr-long_message.wav"/>

    <!-- If barge-in occurs, uuid_break is called, playback stops -->
    <!-- Dialplan continues here -->

    <!-- Stop streaming -->
    <action application="set" data="stop_result=${uuid_audio_stream(${uuid} stop)}"/>

    <!-- Handle barge-in (collect input, process STT, etc.) -->
    <action application="playback" data="ivr/ivr-you_said.wav"/>

    <action application="hangup"/>

  </condition>
</extension>
```

---

## Performance & Optimization

### Bandwidth Usage

#### Calculation by Configuration

**Mono 8kHz, 20ms chunks:**
```
Audio data: 8000 Hz × 16 bits × 1 channel = 128 kbps
Chunks/sec: 1000ms / 20ms = 50 chunks/sec
Chunk size: 160 samples × 2 bytes = 320 bytes
WebSocket overhead: ~10-20 bytes/frame
Total: ~135-140 kbps per stream
```

**Stereo 16kHz, 60ms chunks:**
```
Audio data: 16000 Hz × 16 bits × 2 channels = 512 kbps
Chunks/sec: 1000ms / 60ms = ~16.67 chunks/sec
Chunk size: 960 samples × 2 bytes × 2 channels = 3840 bytes
Total: ~520-530 kbps per stream
```

**With compression enabled (STREAM_MESSAGE_DEFLATE=true):**
- Typical reduction: 30-70%
- Mono 8kHz: ~90-100 kbps
- Stereo 16kHz: ~310-370 kbps

#### Bandwidth Planning

| Concurrent Streams | Mono 8kHz | Stereo 16kHz | With Compression |
|--------------------|-----------|--------------|------------------|
| 10 | 1.4 Mbps | 5.3 Mbps | 1.0 / 3.7 Mbps |
| 50 | 7 Mbps | 26 Mbps | 5 / 18.5 Mbps |
| 100 | 14 Mbps | 53 Mbps | 10 / 37 Mbps |

**Recommendation:** Always enable compression for production deployments.

---

### Latency Characteristics

#### End-to-End Latency Breakdown

```
Audio captured → FreeSWITCH buffer → WebSocket send → Network → Server receive → Processing
    0ms              20-200ms           1-5ms        10-50ms      0ms          10-500ms
                     (buffer size)                   (RTT/2)               (STT/AI)
```

**Total typical latency:**
- Best case (20ms buffer, local): 50-100ms
- Typical (60ms buffer, internet): 100-300ms
- High latency (200ms buffer, slow STT): 400-800ms

#### Optimization Strategies

1. **Reduce buffer size** (STREAM_BUFFER_SIZE)
   - 20ms for real-time barge-in
   - Trade-off: More WebSocket overhead

2. **Use compression** (STREAM_MESSAGE_DEFLATE)
   - Reduces network transfer time
   - Minimal CPU impact

3. **Optimize network path**
   - Place WebSocket server close to FreeSWITCH (same datacenter)
   - Use low-latency network links
   - Avoid VPNs/proxies if possible

4. **Server-side optimization**
   - Use fast STT engines (Vosk, Whisper.cpp)
   - Optimize AI model inference
   - Use streaming STT (partial results)

5. **Use appropriate sample rate**
   - 8kHz sufficient for speech recognition
   - 16kHz only if STT engine benefits
   - Higher rates = more bandwidth, no STT benefit

---

### CPU Usage

#### FreeSWITCH-Side

**Per Stream:**
- Media bug attachment: ~1-2% CPU
- L16 PCM conversion: ~1-3% CPU (if resampling needed)
- WebSocket encoding: ~1-2% CPU
- Compression (if enabled): ~2-5% CPU

**Total:** ~5-12% CPU per stream on modern servers

**Concurrent Capacity:**
- 8-core server: ~60-100 concurrent streams
- 16-core server: ~120-200 concurrent streams
- Scales linearly with cores

**Optimization:**
- Disable compression if CPU-bound (trade bandwidth for CPU)
- Use native sample rates (avoid resampling)
- Consider dedicated streaming servers

#### WebSocket Server-Side

Highly dependent on processing (STT, AI, etc.)

**Idle WebSocket handling:** ~0.1% CPU per stream
**Vosk STT:** ~10-30% CPU per stream
**Whisper STT:** ~50-200% CPU per stream (model-dependent)
**AI inference:** Varies greatly (GPU recommended)

**Recommendation:** Use GPU acceleration for STT/AI workloads.

---

### Concurrent Streams

#### Module Limitations

**Free tier (amigniter/mod_audio_stream):**
- Limited to 10 concurrent streaming channels
- Enforced by module
- Commercial license available for more

**sptmru fork:**
- No artificial limits
- Limited only by system resources

#### System Limits

**Network:**
- 100 concurrent stereo 16kHz streams = 53 Mbps
- Ensure adequate bandwidth
- Use compression to reduce

**Memory:**
- Per stream: ~2-5 MB (buffers, WebSocket state)
- 100 streams: ~200-500 MB

**CPU:**
- As discussed above, typically CPU-bound
- Plan for 5-12% CPU per stream

**File Descriptors:**
- Each WebSocket = 1 file descriptor
- Ensure system limits allow (ulimit -n)
- Recommended: 10,000+ for high-volume

---

## Troubleshooting

### Common Errors

#### Error: "Module not loaded"

**Symptom:**
```
-ERR mod_audio_stream not loaded
```

**Causes:**
1. Module not compiled/installed
2. Module not loaded in modules.conf.xml

**Solutions:**
```bash
# Check if module file exists
ls -la /usr/lib/freeswitch/mod/mod_audio_stream.so

# Load module manually
fs_cli -x "load mod_audio_stream"

# Verify loaded
fs_cli -x "module_exists mod_audio_stream"

# Add to modules.conf.xml
<load module="mod_audio_stream"/>
```

---

#### Error: Connection Failed (Error Code 6)

**Symptom:**
```
Event: mod_audio_stream::error
Error-Code: 6
Error-Description: DNS resolution failed / TCP connection failure
```

**Causes:**
1. WebSocket server not running
2. Incorrect URL
3. DNS resolution failure
4. Firewall blocking connection
5. Network unreachable

**Solutions:**
```bash
# Test WebSocket server manually
wscat -c ws://localhost:8080/stt

# Check DNS resolution
nslookup api.example.com

# Test TCP connectivity
telnet api.example.com 8080

# Check FreeSWITCH can resolve
fs_cli -x "eval ${dns(api.example.com)}"

# Verify firewall rules
iptables -L | grep 8080
```

---

#### Error: TLS Handshake Failed (Error Code 8)

**Symptom:**
```
Event: mod_audio_stream::error
Error-Code: 8
Error-Description: SSL handshake failed
```

**Causes:**
1. Self-signed certificate without CA
2. Certificate expired
3. Hostname mismatch
4. Unsupported TLS version/cipher

**Solutions:**
```xml
<!-- Accept self-signed certs (TESTING ONLY) -->
<action application="set" data="STREAM_TLS_DISABLE_HOSTNAME_VALIDATION=true"/>

<!-- Use custom CA -->
<action application="set" data="STREAM_TLS_CA_FILE=/path/to/ca-bundle.crt"/>

<!-- Check certificate validity -->
openssl s_client -connect api.example.com:443 -showcerts

<!-- Verify TLS version support -->
openssl s_client -connect api.example.com:443 -tls1_2
```

---

#### Error: No Audio Received on WebSocket

**Symptom:** WebSocket connects, but no audio data received

**Causes:**
1. Incorrect mix-type for use case
2. Media bug not attached
3. No audio on channel
4. Call not answered

**Debug Steps:**
```bash
# Check call is answered
fs_cli -x "uuid_getvar ${uuid} call_state"

# Check media bugs attached
fs_cli -x "uuid_buglist ${uuid}"

# Verify audio on channel
fs_cli -x "uuid_audio ${uuid}"

# Enable debug logging
fs_cli -x "fsctl loglevel DEBUG"

# Check channel variables
fs_cli -x "uuid_dump ${uuid}"
```

**Solutions:**
- Ensure call is answered before starting stream
- Verify correct mix-type (stereo for barge-in, not mono)
- Check WebSocket server is handling binary messages

---

#### Error: Audio Playback Not Working

**Symptom:** Send audio from WebSocket, but nothing plays

**Causes:**
1. STREAM_PLAYBACK not enabled
2. Incorrect audio format
3. Codec mismatch
4. Invalid Base64 encoding

**Solutions:**
```xml
<!-- Enable playback -->
<action application="set" data="STREAM_PLAYBACK=true"/>

<!-- For raw binary, set sample rate -->
<action application="set" data="STREAM_SAMPLE_RATE=8000"/>

<!-- Verify JSON format -->
{
  "type": "streamAudio",
  "data": {
    "audioDataType": "raw",
    "sampleRate": 8000,
    "audioData": "VALID_BASE64_HERE"
  }
}

<!-- Test Base64 encoding -->
echo "AUDIO_BASE64" | base64 -d > test.raw
# Should decode without errors
```

**Codec Optimization:**
- If channel uses PCMU, send PCMU audio (fastest)
- If unsure, use raw L16 PCM
- Avoid sending PCMU when channel uses other codecs

---

#### Error: Reconnection Fails

**Symptom:** After disconnect, restart fails with no media

**Cause:** Media bug not properly removed (fixed in recent versions)

**Solution:**
- Use latest version of mod_audio_stream (includes fix)
- Or, hangup and create new call
- Implement graceful shutdown before restart

---

### Debug Logging

#### Enable Module Debug Logs

```bash
# Set FreeSWITCH log level
fs_cli -x "fsctl loglevel DEBUG"

# Filter for mod_audio_stream logs
fs_cli -x "console loglevel DEBUG"

# Tail FreeSWITCH log
tail -f /var/log/freeswitch/freeswitch.log | grep audio_stream
```

#### Key Log Messages

**Successful start:**
```
[DEBUG] mod_audio_stream: Starting stream for UUID a1b2c3d4...
[INFO] mod_audio_stream: Connected to ws://localhost:8080/stt
[DEBUG] mod_audio_stream: Sending initial metadata: {...}
[DEBUG] mod_audio_stream: Media bug attached, flags: SMBF_READ_STREAM|SMBF_WRITE_STREAM
```

**Connection issues:**
```
[ERR] mod_audio_stream: Connection failed: DNS resolution failed
[ERR] mod_audio_stream: TLS handshake failed
[WARN] mod_audio_stream: WebSocket closed unexpectedly, code: 1006
```

**Audio processing:**
```
[DEBUG] mod_audio_stream: Sending audio chunk, size: 320 bytes
[DEBUG] mod_audio_stream: Resampling from 8000 to 16000 Hz
[DEBUG] mod_audio_stream: Received audio response, size: 1600 bytes
```

---

### Diagnostic Commands

```bash
# Check module status
fs_cli -x "module_exists mod_audio_stream"

# List all media bugs on a call
fs_cli -x "uuid_buglist ${uuid}"

# Dump all channel variables
fs_cli -x "uuid_dump ${uuid}" | grep STREAM_

# Kill specific media bug
fs_cli -x "uuid_media_bug_destroy ${uuid} <bug_id>"

# Check active calls
fs_cli -x "show channels"

# Check system resources
fs_cli -x "status"
```

---

## Complete Examples

### Example 1: Google Cloud STT Integration

Complete integration with Google Cloud Speech-to-Text API.

#### Python WebSocket Proxy Server

```python
import asyncio
import websockets
import json
from google.cloud import speech_v1p1beta1 as speech

# Google Cloud client
client = speech.SpeechClient()

streaming_config = speech.StreamingRecognitionConfig(
    config=speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    ),
    interim_results=True,
)

async def google_stt_handler(websocket, path):
    """Proxy audio from FreeSWITCH to Google STT"""

    print("FreeSWITCH connected")

    # Create streaming request generator
    async def audio_generator():
        async for message in websocket:
            if isinstance(message, bytes):
                # For stereo, extract right channel (caller speech)
                # ... (channel extraction code from previous examples) ...
                yield speech.StreamingRecognizeRequest(audio_content=message)

    # Start streaming recognition
    responses = client.streaming_recognize(streaming_config, audio_generator())

    # Process results
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        is_final = result.is_final
        confidence = result.alternatives[0].confidence if is_final else 0

        # Send result to FreeSWITCH
        response_json = {
            "transcript": transcript,
            "is_final": is_final,
            "confidence": confidence
        }
        await websocket.send(json.dumps(response_json))

        if is_final:
            print(f"Final: {transcript} ({confidence:.2f})")

# Start server
start_server = websockets.serve(google_stt_handler, "localhost", 8080)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
```

---

### Example 2: OpenAI Whisper Real-Time Transcription

Using faster-whisper for low-latency transcription.

#### Python WebSocket Server

```python
import asyncio
import websockets
import struct
import numpy as np
from faster_whisper import WhisperModel

# Load Whisper model (runs on GPU if available)
model = WhisperModel("base", device="cuda", compute_type="float16")

async def whisper_stt_handler(websocket, path):
    """Real-time transcription with Whisper"""

    print("Client connected")

    audio_buffer = []
    buffer_duration = 3.0  # Process every 3 seconds
    sample_rate = 16000
    samples_needed = int(sample_rate * buffer_duration)

    async for message in websocket:
        if isinstance(message, str):
            print(f"Metadata: {message}")
            continue

        # Convert bytes to samples (stereo - extract right channel)
        samples = struct.unpack(f'>{len(message)//2}h', message)
        right_channel = np.array(samples[1::2], dtype=np.float32)

        # Normalize to [-1, 1]
        right_channel = right_channel / 32768.0

        audio_buffer.extend(right_channel)

        # Process when buffer is full
        if len(audio_buffer) >= samples_needed:
            audio_segment = np.array(audio_buffer[:samples_needed])
            audio_buffer = audio_buffer[samples_needed:]

            # Transcribe
            segments, info = model.transcribe(audio_segment, beam_size=5)

            for segment in segments:
                transcript = segment.text.strip()
                if transcript:
                    print(f"Whisper: {transcript}")

                    response = {
                        "transcript": transcript,
                        "start": segment.start,
                        "end": segment.end,
                        "is_final": True
                    }
                    await websocket.send(json.dumps(response))

# Start server
start_server = websockets.serve(whisper_stt_handler, "localhost", 8080)
print("Whisper STT server running on ws://localhost:8080")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
```

---

### Example 3: Conversational AI with LLM Integration

Complete AI voice agent with STT → LLM → TTS pipeline.

#### Architecture
```
FreeSWITCH → mod_audio_stream (stereo) → WebSocket Server
                                              ↓
                                         STT (Whisper)
                                              ↓
                                         LLM (GPT-4)
                                              ↓
                                         TTS (ElevenLabs)
                                              ↓
                                    FreeSWITCH (playback)
```

#### Python AI Agent Server

```python
import asyncio
import websockets
import json
import struct
import numpy as np
from faster_whisper import WhisperModel
import openai
import requests
import base64
import ESL

# Initialize models
whisper = WhisperModel("base", device="cuda")
openai.api_key = "YOUR_OPENAI_KEY"
elevenlabs_api_key = "YOUR_ELEVENLABS_KEY"

# ESL for controlling FreeSWITCH
esl = ESL.ESLconnection('localhost', '8021', 'ClueCon')

class AIAgent:
    def __init__(self):
        self.conversation_history = []

    def process_speech(self, transcript):
        """Send to LLM and get response"""
        self.conversation_history.append({"role": "user", "content": transcript})

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant."},
                *self.conversation_history
            ]
        )

        ai_response = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": ai_response})

        return ai_response

    def synthesize_speech(self, text):
        """Convert text to speech using ElevenLabs"""
        url = "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID"
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        response = requests.post(url, headers=headers, json=data)
        return response.content  # MP3 audio

async def ai_agent_handler(websocket, path):
    """AI voice agent"""

    agent = AIAgent()
    call_uuid = None
    audio_buffer = []
    sample_rate = 16000
    buffer_duration = 2.0
    samples_needed = int(sample_rate * buffer_duration)

    async for message in websocket:
        if isinstance(message, str):
            # Extract UUID from metadata
            metadata = json.loads(message)
            call_uuid = metadata.get('uuid')
            print(f"AI Agent handling call {call_uuid}")
            continue

        # Process audio
        samples = struct.unpack(f'>{len(message)//2}h', message)
        right_channel = np.array(samples[1::2], dtype=np.float32) / 32768.0
        audio_buffer.extend(right_channel)

        if len(audio_buffer) >= samples_needed:
            audio_segment = np.array(audio_buffer[:samples_needed])
            audio_buffer = audio_buffer[samples_needed:]

            # STT
            segments, _ = whisper.transcribe(audio_segment)
            transcript = " ".join([seg.text.strip() for seg in segments])

            if transcript:
                print(f"User said: {transcript}")

                # Send transcript to FreeSWITCH
                await websocket.send(json.dumps({
                    "transcript": transcript,
                    "is_final": True
                }))

                # LLM processing
                ai_response = agent.process_speech(transcript)
                print(f"AI responds: {ai_response}")

                # TTS
                audio_bytes = agent.synthesize_speech(ai_response)
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

                # Send audio for playback
                playback_response = {
                    "type": "streamAudio",
                    "data": {
                        "audioDataType": "mp3",
                        "sampleRate": 24000,
                        "audioData": audio_b64
                    }
                }
                await websocket.send(json.dumps(playback_response))

                # Optionally, pause STT during AI speech
                # esl.api(f"uuid_audio_stream {call_uuid} pause")

# Start server
start_server = websockets.serve(ai_agent_handler, "localhost", 8080)
print("AI Agent server running on ws://localhost:8080")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
```

---

### Example 4: Call Recording with Speaker Separation

Save stereo call recording with separated channels.

#### Node.js Recording Server

```javascript
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const wss = new WebSocket.Server({ port: 8080, path: '/record' });

wss.on('connection', (ws, req) => {
    const recordingId = uuidv4();
    const filename = path.join('/recordings', `call_${recordingId}.raw`);
    const fileStream = fs.createWriteStream(filename);

    let metadata = {};

    console.log(`Recording started: ${recordingId}`);

    ws.on('message', (message) => {
        if (typeof message === 'string') {
            // Save metadata
            metadata = JSON.parse(message);
            console.log('Call metadata:', metadata);

            // Save metadata to JSON
            fs.writeFileSync(
                filename.replace('.raw', '.json'),
                JSON.stringify(metadata, null, 2)
            );
        } else {
            // Write binary audio to file
            fileStream.write(message);
        }
    });

    ws.on('close', () => {
        fileStream.end();
        console.log(`Recording saved: ${filename}`);

        // Post-process: convert to WAV with separated channels
        const wavFilename = filename.replace('.raw', '.wav');
        convertToWav(filename, wavFilename, 16000, 2);
    });
});

function convertToWav(inputFile, outputFile, sampleRate, channels) {
    const { execSync } = require('child_process');

    // Using sox to convert raw PCM to WAV
    const cmd = `sox -r ${sampleRate} -e signed-integer -b 16 -c ${channels} -B ${inputFile} ${outputFile}`;
    execSync(cmd);

    console.log(`Converted to WAV: ${outputFile}`);

    // Optionally split channels
    const leftFile = outputFile.replace('.wav', '_left.wav');
    const rightFile = outputFile.replace('.wav', '_right.wav');

    execSync(`sox ${outputFile} ${leftFile} remix 1`);
    execSync(`sox ${outputFile} ${rightFile} remix 2`);

    console.log(`Channels separated: ${leftFile}, ${rightFile}`);
}

console.log('Recording server running on ws://localhost:8080/record');
```

---

## Additional Resources

### Official Documentation
- **FreeSWITCH Docs**: https://developer.signalwire.com/freeswitch
- **mod_audio_stream GitHub**: https://github.com/amigniter/mod_audio_stream
- **Alternative fork**: https://github.com/sptmru/freeswitch_mod_audio_stream

### Related Modules
- **mod_audio_fork**: Alternative audio streaming module (multicast RTP)
- **mod_vg_tap_ws**: Voicegain's commercial STT module
- **mod_event_socket**: ESL for controlling FreeSWITCH

### Community Resources
- **FreeSWITCH Mailing List**: freeswitch-users@lists.freeswitch.org
- **FreeSWITCH Slack**: https://signalwire-community.slack.com
- **Stack Overflow**: Tag `freeswitch`

### WebSocket Libraries
- **Python**: websockets, websocket-client
- **Node.js**: ws, socket.io
- **Testing**: wscat, websocat

### STT/AI Services
- **Vosk**: Open-source, offline STT
- **Whisper**: OpenAI's open-source STT
- **Google Cloud STT**: Cloud-based, high accuracy
- **AWS Transcribe**: Amazon's STT service
- **Azure Speech**: Microsoft's STT service

---

## License & Support

**mod_audio_stream (amigniter):**
- **License**: Proprietary with free tier (10 concurrent streams)
- **Commercial**: Contact for higher limits
- **Support**: GitHub issues

**mod_audio_stream (sptmru fork):**
- **License**: MIT (open source)
- **Limitations**: None (resource-limited only)
- **Support**: Community-driven

---

## Changelog & Version Notes

**v1.0.3 (amigniter):**
- Added full-duplex streaming
- Raw binary stream support
- Base64 encoded audio support
- Audio playback from WebSocket
- Improved stability

**v1.0.2:**
- TLS/WSS support
- Channel variables for configuration
- Event system implementation

**v1.0.0:**
- Initial release
- Basic mono/stereo streaming
- WebSocket protocol support

---

## Conclusion

mod_audio_stream is a powerful, flexible module for real-time audio streaming in FreeSWITCH. Key takeaways:

1. **Use stereo mode for barge-in detection** - clean speaker separation
2. **Enable compression** - saves 30-70% bandwidth
3. **Optimize buffer size** - 20ms for real-time, 100ms for batch processing
4. **Handle events** - monitor for errors and disconnections
5. **Secure with TLS** - always use WSS in production
6. **Test thoroughly** - validate reconnection, error handling, and edge cases

With proper configuration and implementation, mod_audio_stream enables sophisticated voice AI applications, real-time transcription, and advanced call analytics.

---

**Document Version:** 1.0
**Last Updated:** 2025
**Author:** Research compiled from official documentation, GitHub repositories, and community resources
