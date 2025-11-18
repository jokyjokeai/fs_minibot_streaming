# FreeSWITCH Audio Direction - Complete Technical Guide

**Version:** 1.0
**Date:** 2025-11-14
**Author:** Technical Research & Analysis

---

## Table of Contents

1. [Audio Flow Fundamentals](#audio-flow-fundamentals)
2. [Channel Architecture](#channel-architecture)
3. [Audio Direction Concepts](#audio-direction-concepts)
4. [Direction Types Deep Dive](#direction-types-deep-dive)
5. [Media Bug Internals](#media-bug-internals)
6. [Common Patterns & Use Cases](#common-patterns--use-cases)
7. [Stereo Recording Architecture](#stereo-recording-architecture)
8. [Troubleshooting Direction Issues](#troubleshooting-direction-issues)
9. [Testing and Validation](#testing-and-validation)
10. [Real-World Examples](#real-world-examples)

---

## Audio Flow Fundamentals

### The FreeSWITCH Perspective

**CRITICAL CONCEPT:** All audio directions in FreeSWITCH are defined from **FreeSWITCH's perspective**, not the caller's perspective.

```
┌─────────────────────────────────────────────────────────────────┐
│                     FreeSWITCH as Reference Point               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  READ Direction  ←─────  Audio FROM endpoint TO FreeSWITCH     │
│                                                                 │
│  WRITE Direction ─────→  Audio FROM FreeSWITCH TO endpoint     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Audio Path Visualization

```
┌──────────────┐         RTP Stream          ┌──────────────┐
│              │  ───────────────────────→    │              │
│   Caller     │  ←───────────────────────    │  FreeSWITCH  │
│  (Endpoint)  │                              │   (Server)   │
│              │                              │              │
└──────────────┘                              └──────────────┘
       ↓                                             ↓
   Microphone                                   READ STREAM
    Speaker                                     WRITE STREAM
```

**READ STREAM:** Audio traveling FROM the caller's microphone TO FreeSWITCH (inbound audio)
**WRITE STREAM:** Audio traveling FROM FreeSWITCH TO the caller's speaker (outbound audio)

---

## Channel Architecture

### A-Leg vs B-Leg

FreeSWITCH uses the concept of "call legs" to represent different sides of a call:

```
┌─────────────┐         A-Leg          ┌──────────────┐         B-Leg          ┌─────────────┐
│   Caller    │ ─────────────────────→ │  FreeSWITCH  │ ─────────────────────→ │   Callee    │
│  (Ingress)  │ ←───────────────────── │              │ ←───────────────────── │  (Egress)   │
└─────────────┘                        └──────────────┘                        └─────────────┘
```

**A-leg (Ingress):** The incoming call leg from the originator (caller)
**B-leg (Egress):** The outgoing call leg to the recipient (callee)

### Key Characteristics

- Each leg is a **separate FreeSWITCH channel** with its own UUID
- Legs can use **different protocols** (e.g., SIP incoming, TDM outgoing)
- When bridged, both legs form a single "call"
- Each leg has its own READ and WRITE streams

### Bridged Call Architecture

```
A-Leg Channel (UUID: abc123)              B-Leg Channel (UUID: def456)
┌─────────────────────────┐              ┌─────────────────────────┐
│  READ:  Caller speech   │              │  READ:  Callee speech   │
│  WRITE: Bot TTS/audio   │  ◄─bridge─►  │  WRITE: Caller audio    │
└─────────────────────────┘              └─────────────────────────┘
```

---

## Audio Direction Concepts

### What "READ" Means

**READ = Audio being READ FROM the channel**

- Audio **coming FROM** the remote endpoint
- Audio **going INTO** FreeSWITCH
- Audio **being RECEIVED** by FreeSWITCH
- The **inbound RTP stream**

**Mental Model:** FreeSWITCH is "reading" audio data from the network interface.

### What "WRITE" Means

**WRITE = Audio being WRITTEN TO the channel**

- Audio **going TO** the remote endpoint
- Audio **coming FROM** FreeSWITCH
- Audio **being SENT** by FreeSWITCH
- The **outbound RTP stream**

**Mental Model:** FreeSWITCH is "writing" audio data to the network interface.

### What "BOTH" Means

**BOTH = Bidirectional audio capture**

- Captures **both READ and WRITE** streams simultaneously
- Provides **complete conversation** recording
- Can be mixed (mono) or separated (stereo)

### Common Misconceptions

❌ **WRONG:** "READ captures what the caller hears"
✅ **CORRECT:** "READ captures what the caller speaks"

❌ **WRONG:** "WRITE is what FreeSWITCH receives"
✅ **CORRECT:** "WRITE is what FreeSWITCH sends"

❌ **WRONG:** "Direction depends on who initiated the call"
✅ **CORRECT:** "Direction is always from FreeSWITCH's perspective"

---

## Direction Types Deep Dive

### READ Direction (Inbound Audio)

#### What It Captures

```
Caller Microphone → SIP/RTP → FreeSWITCH READ Stream → Media Bug
                                         ↓
                                   WebSocket/STT
```

Audio flow: **FROM caller TO FreeSWITCH**

#### Primary Use Cases

1. **Speech-to-Text (STT/ASR)**
   - Listen to caller's voice
   - Convert speech to text
   - Natural language processing

2. **Barge-In Detection**
   - Detect when caller starts speaking
   - Interrupt robot playback
   - Improve conversation flow

3. **Voice Commands**
   - DTMF detection alternatives
   - "Press 1 or say 'sales'"
   - Voice-driven IVR

4. **Answering Machine Detection (AMD)**
   - Analyze greeting patterns
   - Detect beep tones
   - Human vs machine classification

5. **Voice Biometrics**
   - Speaker verification
   - Voice authentication
   - Fraud detection

#### Command Examples

```bash
# Basic READ stream for STT
uuid_audio_stream <uuid> start ws://server:8080/stt read

# AMD using READ stream (detect caller voice)
uuid_audio_stream <uuid> start ws://server:8080/amd read 8000

# Barge-in detection during playback
uuid_audio_stream <uuid> start ws://server:8080/bargein read 16000
uuid_broadcast <uuid> prompt.wav aleg
```

#### Media Bug Flags

```c
// Source code perspective
flags = SMBF_READ_STREAM;  // Capture incoming audio only
flags = SMBF_READ_REPLACE; // Capture + allow modification
```

### WRITE Direction (Outbound Audio)

#### What It Captures

```
FreeSWITCH WRITE Stream → SIP/RTP → Caller Speaker
         ↓
   Media Bug Tap
         ↓
   WebSocket/Monitor
```

Audio flow: **FROM FreeSWITCH TO caller**

#### Primary Use Cases

1. **TTS Quality Monitoring**
   - Verify text-to-speech output
   - Quality assurance
   - Debug TTS issues

2. **Playback Verification**
   - Confirm audio file played correctly
   - Detect silence or corruption
   - Compliance recording

3. **Echo Cancellation Testing**
   - Monitor outbound audio quality
   - Detect audio artifacts
   - Network quality analysis

4. **Outbound Call Monitoring**
   - Track what customer hears
   - Verify prompt delivery
   - Customer experience auditing

5. **Legal Compliance**
   - Record disclaimers played
   - Verify regulatory messages
   - Audit trail for outbound content

#### Command Examples

```bash
# Monitor TTS output
uuid_audio_stream <uuid> start ws://server:8080/monitor write

# Quality check playback
uuid_audio_stream <uuid> start ws://server:8080/qa write 8000

# Record outbound audio only
uuid_audio_stream <uuid> start ws://server:8080/outbound write 16000
```

#### Media Bug Flags

```c
// Source code perspective
flags = SMBF_WRITE_STREAM;  // Capture outgoing audio only
flags = SMBF_WRITE_REPLACE; // Capture + allow modification
```

### BOTH/MIXED/STEREO Direction

#### What It Captures

```
Caller ←──────────────────────→ FreeSWITCH
         READ + WRITE Streams
                ↓
         Media Bug (Both)
                ↓
        WebSocket/Recording
```

Audio flow: **Bidirectional (READ + WRITE)**

#### Mix Type Variants

1. **mono** - Single channel, READ only (caller speech)
2. **mixed** - Single channel, READ + WRITE mixed together
3. **stereo** - Dual channels, READ on one, WRITE on other

#### Command Examples

```bash
# Full call recording (mono mix)
uuid_audio_stream <uuid> start ws://server:8080/record mixed 16000

# Stereo recording (separate channels)
uuid_audio_stream <uuid> start ws://server:8080/record stereo 16000

# Basic mono (READ only despite name)
uuid_audio_stream <uuid> start ws://server:8080/stream mono 8000
```

#### Media Bug Flags

```c
// Source code (mod_audio_stream.c)
switch_media_bug_flag_t flags = SMBF_READ_STREAM;

if (mix_type == "mixed") {
    flags |= SMBF_WRITE_STREAM;  // Add WRITE to READ
}

if (mix_type == "stereo") {
    flags |= SMBF_WRITE_STREAM;
    flags |= SMBF_STEREO;  // Enable dual-channel
}
```

---

## Media Bug Internals

### Media Bug Architecture

A **media bug** is FreeSWITCH's built-in mechanism to "tap into" live RTP streams.

```
┌─────────────────────────────────────────────────────────────┐
│                    FreeSWITCH Core                          │
│                                                             │
│  RTP Packet → Decoder → ┌─────────────┐ → Encoder → RTP   │
│                          │ Media Frame │                    │
│                          └─────────────┘                    │
│                                ↓                            │
│                          ┌─────────────┐                    │
│                          │ Media Bug   │ (Tap Point)        │
│                          │ Callback    │                    │
│                          └─────────────┘                    │
│                                ↓                            │
│                       raw_read_buffer  (READ)               │
│                       raw_write_buffer (WRITE)              │
└─────────────────────────────────────────────────────────────┘
```

### Media Bug Flags Reference

| Flag | Description | Use Case |
|------|-------------|----------|
| `SMBF_READ_STREAM` | Tap READ stream (buffered) | STT, AMD, recording |
| `SMBF_WRITE_STREAM` | Tap WRITE stream (buffered) | TTS monitor, QA |
| `SMBF_READ_REPLACE` | Tap + modify READ (real-time) | Audio filters, effects |
| `SMBF_WRITE_REPLACE` | Tap + modify WRITE (real-time) | Dynamic audio injection |
| `SMBF_STEREO` | Enable stereo recording | Separate caller/callee |
| `SMBF_STEREO_SWAP` | Swap stereo channels | Reverse L/R mapping |

### Buffer Management

**STREAM Flags (READ_STREAM, WRITE_STREAM):**
- Audio is **buffered** by FreeSWITCH
- Provides **muxed stream** of both directions
- Best for **recording and streaming**
- No real-time modification capability

**REPLACE Flags (READ_REPLACE, WRITE_REPLACE):**
- Audio is **passed through** in real-time
- Allows **modifying audio frames**
- Best for **filters and effects**
- Can write new data to replace original

### Audio Format

**CRITICAL:** Media bug audio is **always** raw signed linear PCM (L16), regardless of the negotiated codec.

```
Codec Negotiation (SIP):   G.711 μ-law
      ↓
RTP Packets:                G.711 encoded
      ↓
FreeSWITCH Decoder:         Converts to L16
      ↓
Media Bug Receives:         L16 (raw PCM)
      ↓
Your Application:           L16 16-bit signed
```

Common formats from media bug:
- Sample rate: 8000 Hz or 16000 Hz (configurable)
- Encoding: L16 (16-bit signed PCM)
- Channels: 1 (mono) or 2 (stereo)
- Byte order: System native (usually little-endian)

---

## Common Patterns & Use Cases

### Pattern 1: Speech-to-Text During Playback (READ)

**Scenario:** Play prompt while listening for caller's speech (barge-in enabled)

```python
# Python implementation
call_uuid = "abc-123-def-456"
ws_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"

# Step 1: Start READ stream (capture caller speech)
fs.api(f"uuid_audio_stream {call_uuid} start {ws_url} read 16000")

# Step 2: Play prompt (non-blocking)
fs.api(f"uuid_broadcast {call_uuid} /path/to/prompt.wav aleg")

# Step 3: WebSocket receives READ stream (caller speaking)
# Your STT service detects speech and triggers barge-in

# Step 4: Stop streaming when done
fs.api(f"uuid_audio_stream {call_uuid} stop")
```

**Audio Flow:**
```
Caller speaks → READ stream → uuid_audio_stream → WebSocket → STT
FreeSWITCH plays prompt.wav → WRITE stream → Caller hears (not captured)
```

**Why READ?** You want to detect when the **caller starts speaking**, not what the **bot is saying**.

### Pattern 2: Answering Machine Detection (READ)

**Scenario:** Detect if call was answered by human or voicemail

```python
# AMD implementation
call_uuid = "abc-123-def-456"
ws_url = f"ws://127.0.0.1:8080/amd/{call_uuid}"

# Start READ stream immediately after answer
fs.api(f"uuid_audio_stream {call_uuid} start {ws_url} read 8000")

# Wait 3-5 seconds to analyze greeting
time.sleep(config.AMD_MAX_DURATION)

# Stop stream
fs.api(f"uuid_audio_stream {call_uuid} stop")

# Analyze audio received via WebSocket:
# - Voicemail: Long greeting (>2s), beep detection, silence patterns
# - Human: Short greeting (<2s), conversational tone, irregular pauses
```

**Audio Flow:**
```
Called party answers → speaks greeting
    ↓
READ stream captures greeting audio
    ↓
WebSocket sends to AMD engine
    ↓
AMD analyzes patterns:
  - Duration
  - Energy levels
  - Beep detection
  - Silence patterns
    ↓
Result: HUMAN or MACHINE
```

**Why READ?** You're analyzing what the **called party says** after answering.

### Pattern 3: Full Call Recording (BOTH - Stereo)

**Scenario:** Record entire conversation with caller on left, bot on right

```python
# Stereo recording
call_uuid = "abc-123-def-456"
ws_url = f"ws://127.0.0.1:8080/record/{call_uuid}"

# Enable stereo recording
fs.api(f"uuid_audio_stream {call_uuid} start {ws_url} stereo 16000")

# Call proceeds normally - both directions captured
# ...

# Stop recording at end
fs.api(f"uuid_audio_stream {call_uuid} stop")
```

**Channel Mapping (Default):**
- **Left channel:** Callee audio (WRITE stream - what caller hears)
- **Right channel:** Caller audio (READ stream - what caller says)

**Channel Mapping (with RECORD_STEREO_SWAP=true):**
- **Left channel:** Caller audio (READ stream)
- **Right channel:** Callee audio (WRITE stream)

**Why STEREO?** Compliance, quality monitoring, separate speaker analysis.

### Pattern 4: TTS Quality Monitoring (WRITE)

**Scenario:** Verify TTS output quality before customer hears it

```bash
# Monitor TTS playback
uuid_audio_stream <uuid> start ws://server:8080/tts-qa write 16000

# Play TTS
uuid_broadcast <uuid> say:Hello, how can I help you today? aleg

# WebSocket receives WRITE stream (TTS audio)
# QA system checks for:
# - Clarity
# - Volume levels
# - Silence/gaps
# - Pronunciation errors
```

**Why WRITE?** You're monitoring what FreeSWITCH is **sending to the caller** (TTS output).

### Pattern 5: Conversation Analysis (BOTH - Mixed)

**Scenario:** Analyze full conversation (sentiment, compliance, quality)

```python
# Mixed mono recording
call_uuid = "abc-123-def-456"
ws_url = f"ws://127.0.0.1:8080/analyze/{call_uuid}"

# Start mixed stream (READ + WRITE in single channel)
fs.api(f"uuid_audio_stream {call_uuid} start {ws_url} mixed 16000")

# Conversation happens - all audio captured
# Analysis engine receives mixed audio:
# - Sentiment analysis
# - Keyword spotting
# - Compliance monitoring
# - Quality scoring

# Stop at end
fs.api(f"uuid_audio_stream {call_uuid} stop")
```

**Why MIXED?** Some analysis tools work better with mono audio, and you don't need to separate speakers.

---

## Stereo Recording Architecture

### Understanding Stereo Channel Mapping

FreeSWITCH stereo recording uses **separate channels** for caller and callee audio:

```
┌─────────────────────────────────────────────────────────────┐
│                   Stereo Recording                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Left Channel  ← WRITE Stream (FreeSWITCH → Caller)        │
│                  (What caller HEARS)                        │
│                                                             │
│  Right Channel ← READ Stream  (Caller → FreeSWITCH)        │
│                  (What caller SAYS)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Default Channel Assignment

**Without RECORD_STEREO_SWAP:**
- **Left (0):** WRITE stream (callee audio - what caller hears)
- **Right (1):** READ stream (caller audio - what caller says)

**With RECORD_STEREO_SWAP=true:**
- **Left (0):** READ stream (caller audio - what caller says)
- **Right (1):** WRITE stream (callee audio - what caller hears)

### Practical Example

```xml
<!-- Dialplan stereo recording -->
<action application="set" data="RECORD_STEREO=true"/>
<action application="record_session" data="/tmp/call_${uuid}.wav"/>
```

**Result:** WAV file with 2 channels
- Channel 0 (L): Bot/IVR audio
- Channel 1 (R): Caller audio

**Use cases:**
- Separate transcription per speaker
- Individual speaker sentiment analysis
- Quality scoring per participant
- Training data for ML models

### WebSocket Stereo Streaming

```python
# Receive stereo WebSocket stream
async def handle_stereo_audio(websocket, path):
    while True:
        # Receive interleaved stereo PCM
        # Format: L16 stereo, 16000 Hz, 2 channels
        # Data: [L0, R0, L1, R1, L2, R2, ...]

        audio_data = await websocket.recv()

        # De-interleave channels
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        left_channel = audio_array[0::2]   # Bot audio
        right_channel = audio_array[1::2]  # Caller audio

        # Process separately
        caller_transcription = stt_engine.transcribe(right_channel)
        bot_qa_check = qa_engine.analyze(left_channel)
```

---

## Troubleshooting Direction Issues

### Symptom: No Audio Received via WebSocket

**Possible Causes:**

1. **Wrong direction specified**
   ```bash
   # Wrong: Using WRITE when you need caller speech
   uuid_audio_stream <uuid> start ws://... write

   # Correct: Use READ for caller speech
   uuid_audio_stream <uuid> start ws://... read
   ```

2. **WebSocket not connected**
   - Check WebSocket server is running
   - Verify URL is accessible
   - Check FreeSWITCH can reach WebSocket server
   - Review firewall rules

3. **Media bug not attached**
   ```bash
   # Check if stream started successfully
   uuid_audio_stream <uuid> start ws://... read
   # Should return: "+OK"
   # Error return: "-ERR ..." indicates problem
   ```

4. **Channel doesn't exist**
   ```bash
   # Verify channel exists
   uuid_exists <uuid>
   # Returns: true/false
   ```

**Debug Steps:**

```bash
# 1. Enable media bug debugging
uuid_debug_media <uuid> read on

# 2. Check WebSocket connection
netstat -an | grep 8080

# 3. Verify audio stream status
show channels like <uuid>

# 4. Test with different direction
uuid_audio_stream <uuid> start ws://... both
```

### Symptom: Wrong Audio Captured

**Problem:** Receiving bot audio instead of caller audio (or vice versa)

**Diagnosis:**

```python
# Current implementation
uuid_audio_stream <uuid> start ws://... write  # WRONG for STT

# You're getting:
# - FreeSWITCH TTS output
# - Playback audio
# - What caller HEARS

# What you need:
uuid_audio_stream <uuid> start ws://... read   # CORRECT for STT

# You'll get:
# - Caller speech
# - What caller SAYS
```

**Solution Matrix:**

| Want to Capture | Use Direction | Typical Use Case |
|-----------------|---------------|------------------|
| Caller speech | `read` | STT, barge-in, AMD |
| Bot/TTS output | `write` | Quality monitoring |
| Full conversation (mono) | `mixed` | Recording, analysis |
| Caller + bot (separate) | `stereo` | Compliance, training |

### Symptom: Garbled or Incorrect Audio Format

**Problem:** Audio sounds like static or noise

**Causes:**

1. **Sample rate mismatch**
   ```bash
   # FreeSWITCH sends 16000 Hz
   uuid_audio_stream <uuid> start ws://... read 16000

   # But your decoder expects 8000 Hz
   # Result: Audio plays at wrong speed/pitch
   ```

2. **Incorrect encoding assumption**
   ```python
   # WRONG: Assuming G.711
   audio = decode_g711(websocket_data)

   # CORRECT: Media bug always sends L16
   audio = np.frombuffer(websocket_data, dtype=np.int16)
   ```

3. **Endianness issues**
   ```python
   # System native endianness
   audio = np.frombuffer(data, dtype=np.int16)

   # If needed, swap byte order
   audio = audio.byteswap()
   ```

**Solution:**

```python
# Proper audio handling
def process_media_bug_audio(data, sample_rate=16000):
    """
    Process audio from FreeSWITCH media bug

    Args:
        data: Raw bytes from WebSocket
        sample_rate: 8000 or 16000 (must match uuid_audio_stream)

    Returns:
        numpy array of audio samples
    """
    # Media bug always sends L16 (16-bit signed PCM)
    audio = np.frombuffer(data, dtype=np.int16)

    # Verify sample rate matches expectation
    # (no automatic detection, must know from command)

    return audio
```

### Symptom: Intermittent Audio Gaps

**Problem:** Audio stream has silence periods or drops

**Causes:**

1. **Network latency/packet loss**
   - Check network quality
   - Monitor WebSocket connection stability
   - Review FreeSWITCH RTP statistics

2. **Processing lag in WebSocket handler**
   ```python
   # BAD: Slow processing blocks receiving
   async def handle_audio(websocket):
       while True:
           data = await websocket.recv()
           result = slow_stt_engine.process(data)  # Blocks!

   # GOOD: Async processing
   async def handle_audio(websocket):
       while True:
           data = await websocket.recv()
           asyncio.create_task(process_async(data))  # Non-blocking
   ```

3. **Buffer overflow/underflow**
   - Increase WebSocket buffer size
   - Implement proper backpressure handling
   - Monitor queue depths

**Debug Commands:**

```bash
# Check media stats
uuid_dump <uuid> | grep -i media

# Monitor RTP quality
sofia status profile internal

# Show active media bugs
show channels like <uuid>
```

---

## Testing and Validation

### Verify Correct Direction

**Test 1: READ Direction Validation**

```bash
# Setup
uuid_audio_stream <uuid> start ws://localhost:8080/test read 16000

# Test: Caller speaks into phone
# Expected: WebSocket receives audio data
# Validation: STT transcribes caller's speech

# Test: FreeSWITCH plays audio (uuid_broadcast)
# Expected: WebSocket should NOT receive playback audio
# Validation: No TTS transcription appears
```

**Test 2: WRITE Direction Validation**

```bash
# Setup
uuid_audio_stream <uuid> start ws://localhost:8080/test write 16000

# Test: FreeSWITCH plays audio (uuid_broadcast)
# Expected: WebSocket receives playback audio
# Validation: Can verify audio file content

# Test: Caller speaks into phone
# Expected: WebSocket should NOT receive caller speech
# Validation: No speech transcription from caller
```

**Test 3: STEREO Direction Validation**

```bash
# Setup
uuid_audio_stream <uuid> start ws://localhost:8080/test stereo 16000

# Test: Simultaneous caller speech + bot playback
# Expected: WebSocket receives interleaved stereo
# Validation:
#   - Left channel: Bot audio
#   - Right channel: Caller audio
```

### Audio Quality Verification

**Test Signal Generator:**

```bash
# Play test tone to caller (WRITE direction)
uuid_broadcast <uuid> tone_stream://%(400,200,400,450) aleg

# Monitor with WRITE stream
uuid_audio_stream <uuid> start ws://localhost:8080/test write 16000

# Validate: Should see 400 Hz tone in left speaker, 450 Hz in right
```

**Record and Compare:**

```python
# Record via uuid_audio_stream
ws_recording = []

async def websocket_handler(websocket):
    while True:
        data = await websocket.recv()
        ws_recording.append(data)

# Also record via record_session
fs.api(f"record_session /tmp/test_{uuid}.wav")

# Compare outputs
ws_audio = b''.join(ws_recording)
file_audio = load_wav('/tmp/test_{uuid}.wav')

# Should be identical (accounting for timing differences)
```

### Debug Logging

**Enable comprehensive logging:**

```bash
# FreeSWITCH console
console loglevel 7

# Enable media bug debugging
uuid_debug_media <uuid> read on
uuid_debug_media <uuid> write on

# Monitor logs
tail -f /var/log/freeswitch/freeswitch.log | grep -i "audio_stream\|media.*bug"
```

**Python WebSocket Debugging:**

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('audio_stream')

async def debug_websocket(websocket, path):
    logger.info(f"WebSocket connected: {path}")

    chunk_count = 0
    total_bytes = 0

    while True:
        try:
            data = await websocket.recv()
            chunk_count += 1
            total_bytes += len(data)

            if chunk_count % 100 == 0:
                logger.debug(
                    f"Received {chunk_count} chunks, "
                    f"{total_bytes} bytes total, "
                    f"{total_bytes / chunk_count:.1f} bytes/chunk avg"
                )

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            break

    logger.info(f"WebSocket closed. Total: {chunk_count} chunks, {total_bytes} bytes")
```

---

## Real-World Examples

### Example 1: Voice Bot with Barge-In

**Your Current Implementation (V3/system/robot_freeswitch_v3.py):**

```python
# Line 700: Start streaming for barge-in detection
ws_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"
cmd = f"uuid_audio_stream {call_uuid} start {ws_url} mono 16k"

# Line 711: Start playback (non-blocking)
playback_cmd = f"uuid_broadcast {call_uuid} {abs_audio_path} aleg"
```

**Analysis:**

- **Direction:** `mono` (which defaults to READ stream only)
- **Purpose:** Capture caller speech during playback
- **Why READ:** Barge-in requires detecting when **caller speaks**
- **Correct:** Yes - READ is the right choice for barge-in

**Audio Flow:**
```
Bot plays prompt.wav → WRITE stream → Caller hears
Caller speaks        → READ stream  → uuid_audio_stream → WebSocket → STT
                                                                        ↓
                                                              Barge-in detected!
```

### Example 2: AMD (Answering Machine Detection)

**Your Current Implementation (V3/system/robot_freeswitch_v3.py):**

```python
# Line 1886: Start streaming for AMD
ws_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"
stream_cmd = f"uuid_audio_stream {call_uuid} start {ws_url} read"

# Wait 3-5 seconds to capture greeting
time.sleep(config.AMD_MAX_DURATION)

# Analyze greeting patterns
```

**Analysis:**

- **Direction:** `read`
- **Purpose:** Analyze called party's greeting
- **Why READ:** AMD needs to hear what the **answering party says**
- **Correct:** Yes - READ captures the greeting

**Audio Flow:**
```
Called party answers → Speaks greeting
           ↓
   "Hello?"  (Human, 1.2s)
   OR
   "Hi, you've reached John's voicemail..." (Machine, 4.8s + beep)
           ↓
   READ stream → uuid_audio_stream → WebSocket → AMD Engine
                                                      ↓
                                              HUMAN vs MACHINE
```

### Example 3: Customer Service Call Recording

**Implementation:**

```python
def start_compliance_recording(call_uuid):
    """
    Record full customer service call with separate channels
    for quality monitoring and compliance
    """
    # Use stereo to separate agent (bot) and customer
    ws_url = f"ws://recordings.company.com/calls/{call_uuid}"

    # Stereo: Left=Bot, Right=Customer
    cmd = f"uuid_audio_stream {call_uuid} start {ws_url} stereo 16000"
    result = fs.api(cmd)

    if "+OK" in result:
        logger.info(f"Recording started: {call_uuid}")
        # Recording continues for entire call
        # Backend processes:
        # - Left channel: Bot QA (clarity, professionalism)
        # - Right channel: Customer sentiment, keywords
        # - Both: Compliance checks, hold time, resolution
```

**Why STEREO:**
- **Compliance:** Separate customer consent from agent disclosure
- **Quality:** Evaluate bot performance independently
- **Analytics:** Speaker diarization already done
- **Training:** Clean data for ML model training

### Example 4: Dynamic IVR with Real-Time Transcription

**Implementation:**

```python
async def ivr_with_live_stt(call_uuid):
    """
    IVR that listens to caller in real-time for natural language input
    """
    # Start READ stream for STT
    ws_url = f"ws://127.0.0.1:8080/stt/{call_uuid}"
    fs.api(f"uuid_audio_stream {call_uuid} start {ws_url} read 16000")

    # Play menu
    fs.api(f"uuid_broadcast {call_uuid} /prompts/main_menu.wav aleg")

    # WebSocket handler receives READ stream (caller speech only)
    # STT transcribes: "I need to check my account balance"
    # NLU extracts intent: BALANCE_INQUIRY
    # Route accordingly

    # No need to capture playback (WRITE) - only listen to caller
```

**Why READ:**
- Only care about **caller's response**, not menu prompt
- STT would waste resources transcribing known prompts
- Cleaner audio without playback interference

### Example 5: TTS Quality Assurance Pipeline

**Implementation:**

```python
async def tts_qa_pipeline(call_uuid, text_to_speak):
    """
    Generate TTS, monitor output quality before customer hears it
    """
    # Start WRITE stream monitoring
    ws_url = f"ws://qa-service.company.com/tts/{call_uuid}"
    fs.api(f"uuid_audio_stream {call_uuid} start {ws_url} write 16000")

    # Generate and play TTS
    fs.api(f"uuid_broadcast {call_uuid} say:{text_to_speak} aleg")

    # QA service receives WRITE stream (TTS audio)
    # Checks:
    # - Pronunciation accuracy
    # - Volume levels (-16 dBFS target)
    # - No clipping or distortion
    # - Pause placement
    # - Speaking rate (150-160 WPM)

    # If issues detected, log for TTS engine tuning
```

**Why WRITE:**
- Monitor **what customer hears** (FreeSWITCH output)
- Verify TTS before it reaches customer
- Quality metrics on outbound audio

---

## Quick Reference

### Direction Decision Tree

```
What do you want to capture?
├─ Caller speech / voice input
│  └─ Use: read
│     └─ Examples: STT, barge-in, AMD, voice commands
│
├─ Bot playback / TTS output
│  └─ Use: write
│     └─ Examples: QA monitoring, playback verification
│
├─ Full conversation (mixed together)
│  └─ Use: mixed
│     └─ Examples: Simple recording, conversation analysis
│
└─ Full conversation (separate speakers)
   └─ Use: stereo
      └─ Examples: Compliance, speaker-specific analysis
```

### Command Quick Reference

```bash
# READ: Capture caller speech
uuid_audio_stream <uuid> start ws://server/path read 16000

# WRITE: Capture bot output
uuid_audio_stream <uuid> start ws://server/path write 16000

# MIXED: Capture both (mono)
uuid_audio_stream <uuid> start ws://server/path mixed 16000

# STEREO: Capture both (separate channels)
uuid_audio_stream <uuid> start ws://server/path stereo 16000

# MONO: Capture READ only (despite name)
uuid_audio_stream <uuid> start ws://server/path mono 16000

# STOP: Stop any active stream
uuid_audio_stream <uuid> stop

# DEBUG: Enable media bug debugging
uuid_debug_media <uuid> read on
uuid_debug_media <uuid> write on
uuid_debug_media <uuid> both on
```

### Media Bug Flags Quick Reference

| Scenario | Flag Combination | Buffer Type |
|----------|------------------|-------------|
| STT from caller | `SMBF_READ_STREAM` | Buffered |
| TTS monitoring | `SMBF_WRITE_STREAM` | Buffered |
| Full recording (mono) | `SMBF_READ_STREAM \| SMBF_WRITE_STREAM` | Buffered |
| Full recording (stereo) | `SMBF_READ_STREAM \| SMBF_WRITE_STREAM \| SMBF_STEREO` | Buffered |
| Real-time filter (inbound) | `SMBF_READ_REPLACE` | Pass-through |
| Real-time filter (outbound) | `SMBF_WRITE_REPLACE` | Pass-through |

---

## Conclusion

Understanding FreeSWITCH audio direction is critical for implementing:

- ✅ Speech-to-Text (STT) systems
- ✅ Barge-in / interruption detection
- ✅ Answering Machine Detection (AMD)
- ✅ Call recording and compliance
- ✅ Quality monitoring and analytics
- ✅ Voice biometrics and authentication

**Key Takeaways:**

1. **Always think from FreeSWITCH's perspective:**
   - READ = Audio coming TO FreeSWITCH (caller speech)
   - WRITE = Audio going FROM FreeSWITCH (bot output)

2. **Match direction to use case:**
   - Want caller speech? → Use READ
   - Want bot output? → Use WRITE
   - Want both? → Use MIXED or STEREO

3. **Media bugs always provide L16 PCM:**
   - No codec conversion needed in application
   - Sample rate matches uuid_audio_stream parameter
   - Handle as raw 16-bit signed integers

4. **Test your implementation:**
   - Verify correct direction with known inputs
   - Monitor WebSocket data flow
   - Enable debug logging during development

---

## Additional Resources

- **FreeSWITCH Official Documentation:** https://developer.signalwire.com/freeswitch/
- **Media Bug API Reference:** https://docs.freeswitch.org/group__mb1.html
- **mod_audio_stream Source:** https://github.com/amigniter/mod_audio_stream
- **Call Legs Explanation:** https://developer.signalwire.com/freeswitch/FreeSWITCH-Explained/Introduction/Call-Legs/

---

**Document Version:** 1.0
**Last Updated:** 2025-11-14
**Maintained By:** AI Technical Documentation Team
