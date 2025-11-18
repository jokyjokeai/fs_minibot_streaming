# Barge-in Detection & Audio Streaming - Master Guide

**Comprehensive technical guide for real-time voice interruption and streaming architectures in telephony/VoIP systems**

---

## Table of Contents

1. [Part 1: Barge-in Detection](#part-1-barge-in-detection)
2. [Part 2: Audio Streaming Patterns](#part-2-audio-streaming-patterns)
3. [Part 3: Industry Implementations](#part-3-industry-implementations)
4. [Part 4: Production Best Practices](#part-4-production-best-practices)
5. [Part 5: Code Examples](#part-5-code-examples)

---

## Part 1: Barge-in Detection

### 1.1 What is Barge-in?

**Definition**: Barge-in is a telephony feature that allows callers to interrupt automated voice prompts during playback, enabling more natural conversations between users and automated systems.

**Importance**:
- Reduces average call duration by 20-40% for experienced users
- Improves user satisfaction scores significantly
- Enables natural, human-like conversation flow
- Critical for modern conversational AI and IVR systems

**Two Types of Barge-in**:

1. **Voice IVR Barge-in** (Focus of this guide)
   - User interrupts AI/IVR prompts with speech
   - Enables natural dialogue flow
   - Requires real-time speech detection

2. **Supervisor Barge-in** (Call center feature)
   - Supervisor joins agent-customer call
   - Turns into three-way conference
   - Different technical requirements

**User Experience Benefits**:
- **Speed**: Experienced users can skip to responses immediately
- **Natural Flow**: Mimics human conversation patterns
- **Reduced Frustration**: No forced listening to complete prompts
- **Accessibility**: Better for users who know exactly what they want

**Technical Challenges**:
- Sub-500ms latency requirement for natural conversation
- Avoiding false positives (background noise, cross-talk)
- Graceful audio fade-out without clicks/pops
- State management during interruption
- Resource optimization for concurrent calls

**Latency Requirements**:
- **Ideal**: < 300ms (feels natural)
- **Acceptable**: 300-600ms (usable)
- **Poor**: > 1000ms (feels robotic)
- **Target**: 800ms total voice-to-voice latency (including STT + LLM + TTS)

---

### 1.2 Detection Methods

#### 1.2.1 Voice Activity Detection (VAD)

**How It Works**:
Voice Activity Detection uses signal processing and machine learning to identify the presence or absence of human speech in audio signals.

**Technical Approach**:
1. **Feature Extraction**: Analyzes acoustic features like:
   - Energy levels
   - Zero-crossing rate
   - Spectral characteristics (spectrograms)

2. **Classification**: Binary decision - speech detected or not

3. **Noise Reduction**: Often includes spectral subtraction stage

4. **Threshold-based Decision**: Compares calculated features against configurable thresholds

**Pros**:
- **Ultra-low latency**: Detection in < 50ms possible
- **Lightweight**: Minimal CPU/memory overhead
- **Customizable sensitivity**: Easy to tune for different environments
- **Works offline**: No cloud dependency
- **Cost-effective**: Free open-source implementations available

**Cons**:
- **No semantic understanding**: Cannot distinguish words vs noise
- **False positives**: May trigger on coughs, background speech, phone noise
- **Misinterprets pauses**: Short thinking pauses may be seen as turn completion
- **Language-agnostic**: Cannot filter by intent/keywords

**Popular Implementations**:

1. **Silero VAD** (Recommended)
   - Enterprise-grade pre-trained model
   - Processing: < 1ms per chunk on single CPU thread
   - Supports batching and GPU acceleration
   - ONNX runtime: 4-5x faster than PyTorch
   - MIT license (no restrictions)
   - GitHub: github.com/snakers4/silero-vad

2. **WebRTC VAD**
   - Browser-compatible implementation
   - Lightweight (< 100KB)
   - Three aggressiveness modes (0-3)
   - Frame sizes: 10ms, 20ms, 30ms
   - C library with Python/JS bindings

3. **OpenAI Realtime VAD**
   - Built into GPT-4o Realtime API
   - Optimized for conversational AI
   - Adaptive algorithms based on environment
   - Real-time threshold adjustment

**Performance Metrics**:
- **Front End Clipping (FEC)**: Speech clipped at start
- **Mid Speech Clipping (MSC)**: Speech cut during utterance
- **Noise Detected as Speech (NDS)**: False positive rate

#### 1.2.2 STT-based Detection

**How It Works**:
Uses Speech-to-Text transcription to detect actual speech content, then triggers interruption based on transcribed text.

**Technical Approach**:
1. Stream audio to STT engine in real-time
2. Receive partial/streaming transcripts
3. Analyze transcript content (word count, keywords, confidence)
4. Trigger barge-in when threshold met

**Pros**:
- **Semantic awareness**: Knows what user actually said
- **Keyword filtering**: Can require specific words/phrases
- **Confidence scoring**: Only trigger on high-confidence detections
- **Reduces false positives**: Ignores non-speech noise
- **Context-aware**: Can integrate with conversation state

**Cons**:
- **Higher latency**: 200-500ms typical (STT processing time)
- **Resource intensive**: GPU recommended for real-time
- **Cost**: Cloud STT APIs charge per second/minute
- **Network dependency**: Cloud APIs require stable connection
- **Accuracy variations**: Performance depends on accent, noise, vocabulary

**Latency Characteristics**:

| STT Service | Streaming Latency (P50) | Accuracy (WER) | Cost |
|-------------|-------------------------|----------------|------|
| AssemblyAI Universal-Streaming | ~300ms | 9.3% | $0.65/hr |
| Deepgram Nova-2 | ~250ms | 8.7% | $0.59/hr |
| Google Cloud Speech (Streaming) | ~350ms | 10.2% | $1.44/hr |
| Azure Speech Services | ~400ms | 11.1% | $1.00/hr |
| Whisper (local GPU) | ~500ms | 9.5% | GPU cost |

**Key Consideration**: Streaming STT typically has 10-15% higher WER (Word Error Rate) than batch processing due to processing audio with less context.

#### 1.2.3 Hybrid Approaches (Recommended)

**Architecture**:
Combine VAD for instant detection + STT for validation.

```
Audio Stream → VAD → Quick Detection (< 50ms)
                ↓
          STT Streaming → Validation (200-300ms)
                ↓
          Confidence Check → Final Barge-in Decision
```

**Implementation Flow**:
1. **VAD triggers**: Detects voice activity immediately
2. **STT validates**: Confirms actual speech content
3. **Threshold check**: Requires minimum word count or confidence
4. **Barge-in executes**: Stop playback, process user input

**Best Practices**:
- Use VAD for initial "wake up" signal
- Stream to STT in parallel during VAD detection
- Set minimum word count threshold (1-3 words)
- Require STT confidence > 0.7 for final trigger
- Implement debounce logic (avoid trigger on single phonemes)

**Example Configuration** (Jambonz-style):
```javascript
{
  bargeIn: {
    enable: true,
    sticky: true,  // Keep listening after first interrupt
    minBargeinWordCount: 1,  // Minimum words to trigger
    actionHook: '/speech-detected',
    input: ['speech']  // Can also include 'dtmf'
  }
}
```

**Performance Optimization**:
- VAD aggressiveness: Medium (level 2/3)
- STT chunk size: 100-200ms
- Confidence threshold: 0.65-0.75
- Minimum speech duration: 300-500ms

---

### 1.3 Implementation Patterns

#### 1.3.1 Concurrent Read/Write Streams

**Challenge**: Must simultaneously playback audio AND listen for interruptions.

**Traditional Approach** (Sequential):
```
Play audio → Wait → Listen → Process → Respond
```
**Problem**: No barge-in capability during playback.

**Streaming Approach** (Concurrent):
```
┌─────────────────┐     ┌──────────────────┐
│  Audio Playback │ ←── │  TTS Generator   │
│  (Write Stream) │     └──────────────────┘
└─────────────────┘
        ║
        ║ CONCURRENT EXECUTION
        ║
┌─────────────────┐     ┌──────────────────┐
│  Audio Capture  │ ──→ │  STT Processor   │
│  (Read Stream)  │     │  (Barge-in VAD)  │
└─────────────────┘     └──────────────────┘
```

**FreeSWITCH Implementation**:

Option 1: **uuid_audio_stream** (Modern, recommended)
```bash
# Start streaming audio to WebSocket while playing
uuid_audio_stream <call_uuid> start ws://127.0.0.1:8080/stream/<call_uuid>
uuid_broadcast <call_uuid> /path/to/prompt.wav
```

Option 2: **Background gather + say** (Jambonz pattern)
```javascript
// Background say with barge-in config
session.config({
  ttsStream: { enable: true },
  bargeIn: {
    enable: true,
    sticky: true,
    minBargeinWordCount: 1,
    actionHook: '/speech-detected',
    input: ['speech']
  }
})
.say({text: 'Hi there, how can I help you today?'})
.send();
```

**Key Architectural Components**:
1. **Duplex audio channel**: Simultaneous read/write capability
2. **WebSocket connection**: Low-latency bidirectional streaming
3. **STT processor**: Real-time transcription engine
4. **Event dispatcher**: Routes barge-in signals to call handler
5. **State manager**: Coordinates playback/listening states

#### 1.3.2 Background Transcription

**Pattern**: Continuous STT running in background during all call phases.

**Architecture**:
```python
# Pseudo-code
class CallSession:
    def __init__(self):
        self.transcription_active = True
        self.background_thread = Thread(target=self.continuous_transcribe)
        self.background_thread.start()

    def continuous_transcribe(self):
        while self.transcription_active:
            audio_chunk = self.get_audio_chunk()  # 100-200ms
            transcript = self.stt.transcribe_stream(audio_chunk)

            if self.state == "PLAYING" and transcript:
                self.trigger_barge_in(transcript)
            elif self.state == "WAITING":
                self.process_response(transcript)
```

**Benefits**:
- Zero cold-start latency when user speaks
- Continuous monitoring for interruptions
- Simplifies state machine logic

**Challenges**:
- Higher resource usage (continuous STT)
- Must filter out bot's own speech (echo cancellation)
- Requires proper audio routing (don't transcribe outbound audio)

**Optimization Techniques**:
- Use VAD to pause STT during silence
- Batch small chunks before sending to STT
- Implement audio ducking (reduce monitoring during playback)
- Use GPU streaming for parallel processing

#### 1.3.3 Interrupt Signal Handling

**Event-driven Architecture**:

```python
class BargeInHandler:
    def __init__(self):
        self.barge_in_events = {}  # {call_uuid: event_data}
        self.lock = threading.Lock()

    def on_speech_detected(self, call_uuid, transcript, confidence):
        """Called by STT service when speech detected"""
        with self.lock:
            if self.should_trigger_barge_in(transcript, confidence):
                self.barge_in_events[call_uuid] = {
                    'text': transcript,
                    'confidence': confidence,
                    'timestamp': time.time()
                }
                self.emit_event('barge_in', call_uuid)

    def should_trigger_barge_in(self, transcript, confidence):
        """Validation logic"""
        word_count = len(transcript.split())
        return (
            word_count >= self.min_words and
            confidence >= self.min_confidence and
            len(transcript.strip()) > 0
        )

    def emit_event(self, event_type, call_uuid):
        """Notify call handler"""
        # Stop audio playback
        self.stop_playback(call_uuid)
        # Clear TTS buffer
        self.clear_tts_queue(call_uuid)
        # Transition state
        self.set_call_state(call_uuid, "PROCESSING_RESPONSE")
```

**Signal Types**:
1. **Immediate stop**: Hard interrupt (click-free implementation needed)
2. **Fade out**: Gradual volume reduction (200-500ms)
3. **Natural breakpoint**: Wait for phrase completion

#### 1.3.4 Smooth Audio Fade-out

**Problem**: Abrupt audio cutoff creates jarring user experience.

**Solution**: Implement audio ramping.

**Fade-out Implementation**:
```python
def fade_out_audio(audio_buffer, fade_duration_ms=200, sample_rate=8000):
    """
    Apply linear fade-out to prevent audio clicks.

    Args:
        audio_buffer: numpy array of audio samples
        fade_duration_ms: Fade duration in milliseconds
        sample_rate: Audio sample rate (8000 for telephony)

    Returns:
        Audio with fade-out applied
    """
    fade_samples = int((fade_duration_ms / 1000.0) * sample_rate)
    fade_samples = min(fade_samples, len(audio_buffer))

    # Create linear fade curve (1.0 → 0.0)
    fade_curve = np.linspace(1.0, 0.0, fade_samples)

    # Apply to last N samples
    audio_buffer[-fade_samples:] *= fade_curve

    return audio_buffer
```

**FreeSWITCH Break Command**:
```bash
# Stop playback gracefully
uuid_break <call_uuid> all
```

**Best Practices**:
- Fade duration: 100-300ms (longer feels sluggish)
- Use cosine curve for more natural sound
- Implement cross-fade when switching audio
- Avoid fade on DTMF tones (instant stop preferred)

#### 1.3.5 State Machine Design

**Call States for Barge-in-enabled System**:

```
┌──────────────┐
│  INITIATED   │ ── AMD Detection ──→ [HUMAN/MACHINE/VOICEMAIL]
└──────────────┘
       ↓
┌──────────────┐
│   PLAYING    │ ─── Barge-in ───→ [INTERRUPTED]
│  (bot talks) │                         ↓
└──────────────┘                   ┌──────────────┐
       ↓                           │ PROCESSING   │
┌──────────────┐                   │  RESPONSE    │
│   WAITING    │ ←───────────────  └──────────────┘
│ (bot listens)│
└──────────────┘
       ↓
┌──────────────┐
│  ANALYZING   │ ── Objection Match ──→ [MATCHED/CONTINUE]
└──────────────┘
       ↓
┌──────────────┐
│  COMPLETED   │
└──────────────┘
```

**State Transition Rules**:
```python
class CallStateMachine:
    VALID_TRANSITIONS = {
        'INITIATED': ['PLAYING', 'TERMINATED'],
        'PLAYING': ['WAITING', 'INTERRUPTED', 'TERMINATED'],
        'INTERRUPTED': ['PROCESSING_RESPONSE', 'WAITING'],
        'PROCESSING_RESPONSE': ['PLAYING', 'TERMINATED'],
        'WAITING': ['ANALYZING', 'TIMEOUT', 'TERMINATED'],
        'ANALYZING': ['PLAYING', 'COMPLETED', 'TERMINATED'],
        'COMPLETED': ['TERMINATED'],
    }

    def transition(self, call_uuid, new_state):
        current_state = self.get_state(call_uuid)

        if new_state not in self.VALID_TRANSITIONS.get(current_state, []):
            raise InvalidStateTransition(
                f"Cannot transition from {current_state} to {new_state}"
            )

        # Execute state-specific cleanup
        self.exit_state(call_uuid, current_state)

        # Update state
        self.set_state(call_uuid, new_state)

        # Execute state-specific initialization
        self.enter_state(call_uuid, new_state)
```

---

### 1.4 Latency Optimization

#### 1.4.1 Chunk-by-Chunk Processing

**Streaming STT Optimization**:

Instead of waiting for complete utterance, process audio in small chunks.

**Chunk Size Trade-offs**:

| Chunk Size | Latency | Accuracy | CPU Usage | Use Case |
|------------|---------|----------|-----------|----------|
| 50ms | Lowest | Poor | High | VAD only |
| 100-200ms | Low | Good | Medium | **Recommended for barge-in** |
| 500ms | Medium | Better | Low | Background transcription |
| 1000ms+ | High | Best | Lowest | Batch processing |

**Implementation**:
```python
class StreamingSTT:
    def __init__(self, chunk_size_ms=100):
        self.chunk_size_ms = chunk_size_ms
        self.sample_rate = 8000  # Telephony standard
        self.chunk_samples = int(self.sample_rate * chunk_size_ms / 1000)
        self.buffer = bytearray()

    def process_audio_stream(self, audio_bytes):
        """Process incoming audio in chunks"""
        self.buffer.extend(audio_bytes)

        transcripts = []
        while len(self.buffer) >= self.chunk_samples * 2:  # 2 bytes per sample
            # Extract chunk
            chunk = self.buffer[:self.chunk_samples * 2]
            self.buffer = self.buffer[self.chunk_samples * 2:]

            # Process with STT
            result = self.stt_engine.transcribe_chunk(chunk)
            if result:
                transcripts.append(result)

        return transcripts
```

**Whisper Streaming** (whisper_streaming library):
- Uses local agreement policy with self-adaptive latency
- Achieves 3.3 seconds latency on unsegmented long-form speech
- Processes consecutively, emits transcripts confirmed by 2 iterations
- Avoids naive 30-second segmentation that splits words mid-way

#### 1.4.2 Streaming vs Batch STT

**Performance Comparison**:

| Metric | Streaming STT | Batch STT |
|--------|---------------|-----------|
| Latency | 200-500ms (real-time) | 2-10s (waits for complete audio) |
| WER (Word Error Rate) | 10.9% | 9.37% |
| Use Case | Conversational AI | Post-call transcription |
| Cost Efficiency | Per-minute | Per-minute (same) |
| Context Window | Limited (1-5s) | Full utterance |

**When to Use Streaming**:
- Voice agents (latency critical)
- Live captioning
- Real-time translation
- Barge-in detection

**When to Use Batch**:
- Meeting transcription
- Voicemail transcription
- Quality assurance reviews
- Analytics/insights extraction

#### 1.4.3 GPU Acceleration

**Why GPU Matters**:
- Whisper models: 5-10x faster on GPU vs CPU
- Enables real-time processing for multiple concurrent calls
- Lower latency variance (more predictable)

**GPU Optimization Techniques**:

1. **Model Selection**:
   - `tiny`: 39M params, 32x real-time on GPU, ~5% WER increase
   - `base`: 74M params, 16x real-time, ~3% WER increase
   - `small`: 244M params, 6x real-time, baseline accuracy
   - **Recommended for production**: `small` with GPU

2. **Batching** (Kyutai STT approach):
   - Process hundreds of concurrent conversations on single GPU
   - Group audio chunks from multiple calls
   - Trade slight latency increase for massive throughput

3. **Quantization**:
   - FP16: 2x faster, minimal accuracy loss
   - INT8: 4x faster, ~1-2% WER increase
   - **Recommended**: FP16 for production

**Faster-Whisper Configuration**:
```python
from faster_whisper import WhisperModel

model = WhisperModel(
    "small",
    device="cuda",
    compute_type="float16",  # GPU optimization
    num_workers=4,  # Parallel processing
)

# For streaming (low latency)
segments, info = model.transcribe(
    audio,
    beam_size=1,  # Greedy decode (fast)
    best_of=1,
    language="en",
    vad_filter=True,  # Built-in VAD
    vad_parameters=dict(
        min_speech_duration_ms=100,
        max_speech_duration_s=float('inf'),
    )
)
```

#### 1.4.4 Network Optimization

**WebSocket Configuration**:
```python
# Low-latency WebSocket settings
import websockets

async def audio_stream_handler(websocket, path):
    # Disable buffering for minimum latency
    websocket.max_size = 2**20  # 1MB max message
    websocket.read_limit = 2**16  # 64KB read buffer
    websocket.write_limit = 2**16

    # Set TCP_NODELAY (disable Nagle's algorithm)
    websocket.transport.set_tcp_nodelay(True)
```

**Twilio Media Streams Optimization**:
- Messages in JSON format (< 1KB per audio packet)
- ~20ms of audio per media message
- Base64 encoding (overhead: 33%)
- Port 443 (TCP, no additional firewall config)

**RTP Optimization** (for direct FreeSWITCH integration):
- Use UDP for lower latency vs TCP
- Enable jitter buffer (40-80ms)
- OPUS codec for better compression
- Packet loss concealment (PLC)

#### 1.4.5 Buffer Management

**Audio Buffer Sizing**:

```python
class AudioBufferManager:
    def __init__(self):
        # Input buffer (from network)
        self.input_buffer_size = 320  # 20ms @ 8kHz, 16-bit

        # Processing buffer (for STT)
        self.processing_buffer_size = 1600  # 100ms chunks

        # Output buffer (for playback)
        self.output_buffer_size = 960  # 60ms @ 8kHz

        # Jitter buffer (network variation)
        self.jitter_buffer_size = 640  # 40ms

    def adaptive_buffering(self, network_latency_ms):
        """Adjust buffer based on network conditions"""
        if network_latency_ms > 100:
            self.jitter_buffer_size = 960  # 60ms
        elif network_latency_ms > 50:
            self.jitter_buffer_size = 640  # 40ms
        else:
            self.jitter_buffer_size = 320  # 20ms
```

**Backpressure Handling**:

Jambonz example - when TTS buffer full:
```javascript
// Buffer capacity: ~5000 characters
session.on('tts:streaming-event', (event) => {
  if (event.event === 'stream_paused') {
    // Buffer full - stop sending
    llmStream.pause();
  }
  else if (event.event === 'stream_resumed') {
    // Buffer has space - resume
    llmStream.resume();
  }
});
```

---

### 1.5 Threshold Tuning

#### 1.5.1 Speech Duration Thresholds

**Minimum Speech Duration** (avoid false triggers):

```python
class BargeInConfig:
    # Minimum duration before considering as speech
    MIN_SPEECH_DURATION_MS = 300  # 300ms

    # Maximum silence before ending utterance
    MAX_SILENCE_DURATION_MS = 1500  # 1.5s

    # Minimum word count to trigger
    MIN_WORD_COUNT = 1

    def is_valid_barge_in(self, audio_duration_ms, word_count):
        return (
            audio_duration_ms >= self.MIN_SPEECH_DURATION_MS and
            word_count >= self.MIN_WORD_COUNT
        )
```

**Tuning Guidelines**:
- **Too short** (< 200ms): Triggers on vocal fillers ("uh", "um")
- **Too long** (> 500ms): User perceives delay
- **Sweet spot**: 250-350ms for conversational AI

#### 1.5.2 Confidence Scoring

**STT Confidence Thresholds**:

```python
def process_stt_result(transcript, confidence):
    """
    Confidence-based decision making

    Confidence Ranges:
    - 0.9-1.0: Very high (accept immediately)
    - 0.7-0.9: High (accept for barge-in)
    - 0.5-0.7: Medium (verify with context)
    - < 0.5: Low (ignore or request repeat)
    """
    if confidence >= 0.9:
        return {'action': 'accept', 'verify': False}
    elif confidence >= 0.7:
        return {'action': 'accept', 'verify': True}
    elif confidence >= 0.5:
        return {'action': 'clarify', 'verify': True}
    else:
        return {'action': 'ignore', 'verify': False}
```

**Multi-factor Scoring**:
```python
def calculate_barge_in_score(stt_result, vad_result, context):
    """Hybrid scoring combining multiple signals"""
    weights = {
        'stt_confidence': 0.4,
        'vad_confidence': 0.2,
        'word_count': 0.2,
        'context_match': 0.2
    }

    score = (
        stt_result.confidence * weights['stt_confidence'] +
        vad_result.confidence * weights['vad_confidence'] +
        min(len(stt_result.words) / 3, 1.0) * weights['word_count'] +
        context.relevance_score * weights['context_match']
    )

    return score
```

#### 1.5.3 False Positive Prevention

**Common False Positive Triggers**:
1. Background conversations
2. TV/radio in background
3. Phone hold music
4. Coughing, sneezing
5. Echo/feedback loops

**Mitigation Strategies**:

```python
class FalsePositiveFilter:
    def __init__(self):
        # Blacklist phrases (noise patterns)
        self.noise_patterns = [
            r'^\s*uh+\s*$',  # "uh", "uhh"
            r'^\s*um+\s*$',  # "um", "umm"
            r'^\s*mm+\s*$',  # "mm", "mmm"
            r'^\s*\[NOISE\]\s*$',
        ]

        # Require semantic content
        self.min_unique_words = 1

    def is_likely_false_positive(self, transcript):
        """Check if transcript is likely noise"""
        import re

        # Check noise patterns
        for pattern in self.noise_patterns:
            if re.match(pattern, transcript.lower()):
                return True

        # Check for repeated single phoneme
        words = transcript.split()
        if len(set(words)) < self.min_unique_words:
            return True

        # Check transcript length
        if len(transcript.strip()) < 3:
            return True

        return False
```

**Echo Cancellation**:
```python
def prevent_echo_detection(call_session):
    """
    Prevent bot from detecting its own speech

    Strategy: Track what bot is saying, ignore matching transcripts
    """
    # Track outbound audio timestamps
    bot_speech_windows = []

    def on_bot_starts_speaking(start_time, duration):
        bot_speech_windows.append({
            'start': start_time,
            'end': start_time + duration + 0.5  # 500ms grace period
        })

    def should_ignore_transcript(transcript, timestamp):
        # Check if transcript overlaps with bot speech
        for window in bot_speech_windows:
            if window['start'] <= timestamp <= window['end']:
                return True  # Likely echo
        return False
```

#### 1.5.4 Silence Detection

**Silence Parameters**:

```python
class SilenceDetector:
    def __init__(self):
        # Silence threshold (amplitude)
        self.silence_threshold_db = -40  # dB

        # Minimum silence for end-of-speech
        self.min_silence_duration_ms = 700  # 700ms

        # Maximum silence before timeout
        self.max_silence_timeout_ms = 10000  # 10s

    def detect_silence(self, audio_chunk, sample_rate=8000):
        """Detect silence in audio chunk"""
        import numpy as np

        # Calculate RMS energy
        audio_float = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(audio_float ** 2))

        # Convert to dB
        db = 20 * np.log10(rms + 1e-10)

        return db < self.silence_threshold_db
```

**Adaptive Thresholds**:
```python
def calculate_adaptive_silence_threshold(noise_floor_db):
    """
    Adjust silence threshold based on background noise

    Quieter environment → stricter threshold
    Noisier environment → looser threshold
    """
    base_threshold = -40  # dB
    adaptation = noise_floor_db * 0.3  # 30% of noise floor

    return max(base_threshold, noise_floor_db + 5)  # At least 5dB above noise
```

---

## Part 2: Audio Streaming Patterns

### 2.1 Streaming Architectures

#### 2.1.1 Push vs Pull Models

**Push Model** (Producer-driven):
```
Audio Source ──→ [PUSH] ──→ WebSocket Server ──→ Consumer (STT)
                                ↓
                        (Consumer processes at own pace)
```

**Characteristics**:
- Source controls data rate
- Requires backpressure mechanism
- Common in live streaming (Twilio, WebRTC)
- Risk of buffer overflow if consumer too slow

**Pull Model** (Consumer-driven):
```
Audio Source ←── [REQUEST] ←── WebSocket Server ←── Consumer (STT)
      ↓
  [RESPONSE] ──→ WebSocket Server ──→ Consumer
```

**Characteristics**:
- Consumer controls data rate
- Natural backpressure (no request = no data)
- Common in HTTP streaming
- May underutilize network if consumer too slow

**Hybrid Model** (Recommended for telephony):
```
Audio Source ──→ Jitter Buffer ──→ WebSocket ──→ Processor
                      ↓
              (Smooths variations)
                      ↓
              Backpressure Signal ←── (If buffer > 80%)
```

#### 2.1.2 Buffer Management

**Multi-stage Buffering**:

```python
class AudioStreamBuffer:
    def __init__(self):
        # Network buffer (handles packet jitter)
        self.network_buffer = collections.deque(maxlen=50)  # 1s @ 20ms chunks

        # Processing buffer (for STT input)
        self.processing_buffer = bytearray()

        # Output buffer (for playback)
        self.output_buffer = collections.deque(maxlen=100)  # 2s @ 20ms chunks

        # Statistics
        self.stats = {
            'underruns': 0,  # Buffer empty when needed
            'overruns': 0,   # Buffer full, data dropped
            'avg_fill_rate': 0.0
        }

    def add_network_packet(self, audio_chunk):
        """Add incoming network audio"""
        try:
            self.network_buffer.append(audio_chunk)
        except IndexError:
            # Buffer full
            self.stats['overruns'] += 1
            logger.warning("Network buffer overrun, dropping packet")

    def get_processing_chunk(self, size_bytes):
        """Get chunk for STT processing"""
        if len(self.processing_buffer) < size_bytes:
            # Drain network buffer into processing buffer
            while self.network_buffer and len(self.processing_buffer) < size_bytes:
                self.processing_buffer.extend(self.network_buffer.popleft())

        if len(self.processing_buffer) >= size_bytes:
            chunk = bytes(self.processing_buffer[:size_bytes])
            self.processing_buffer = self.processing_buffer[size_bytes:]
            return chunk
        else:
            # Buffer underrun
            self.stats['underruns'] += 1
            return None

    def get_buffer_health(self):
        """Monitor buffer status"""
        network_fill = len(self.network_buffer) / self.network_buffer.maxlen
        output_fill = len(self.output_buffer) / self.output_buffer.maxlen

        return {
            'network_buffer_pct': network_fill * 100,
            'output_buffer_pct': output_fill * 100,
            'status': 'healthy' if 0.2 < network_fill < 0.8 else 'warning'
        }
```

#### 2.1.3 Backpressure Handling

**Detection**:
```python
def detect_backpressure(buffer_stats):
    """
    Detect when downstream consumer cannot keep up

    Indicators:
    - Buffer fill rate > 80%
    - Increasing buffer size over time
    - Dropped frames
    """
    return (
        buffer_stats['network_buffer_pct'] > 80 or
        buffer_stats['output_buffer_pct'] > 80 or
        buffer_stats.get('dropped_frames', 0) > 10
    )
```

**Mitigation Strategies**:

1. **Throttling** (slow down source):
```python
async def adaptive_rate_control(websocket):
    """Adjust send rate based on buffer status"""
    base_chunk_interval = 0.020  # 20ms

    while True:
        buffer_health = get_buffer_health()

        if buffer_health['network_buffer_pct'] > 80:
            # Slow down
            chunk_interval = base_chunk_interval * 1.5
        elif buffer_health['network_buffer_pct'] < 20:
            # Speed up
            chunk_interval = base_chunk_interval * 0.8
        else:
            chunk_interval = base_chunk_interval

        await asyncio.sleep(chunk_interval)
        chunk = get_next_audio_chunk()
        await websocket.send(chunk)
```

2. **Buffering** (queue data):
```python
# Jambonz TTS streaming example
if buffer_full:
    # Stop sending until buffer drains
    return {'status': 'failed', 'reason': 'full'}

# Wait for resume event
on('stream_resumed', () => {
    # Resume sending
    continue_streaming()
})
```

3. **Dropping** (discard old data):
```python
def intelligent_frame_dropping(buffer):
    """Drop least important frames when buffer full"""
    if buffer.is_full():
        # Keep most recent data (more relevant)
        # Drop older data
        buffer.pop(0)  # Remove oldest
```

#### 2.1.4 Frame Synchronization

**Challenge**: Maintain timing alignment between audio streams.

**Timestamp-based Sync**:
```python
class AudioFrameSync:
    def __init__(self):
        self.reference_timestamp = None
        self.sample_rate = 8000
        self.samples_per_frame = 160  # 20ms @ 8kHz

    def sync_frame(self, audio_frame, timestamp_ms):
        """Ensure frame plays at correct time"""
        if self.reference_timestamp is None:
            self.reference_timestamp = timestamp_ms
            return audio_frame

        # Calculate expected position
        elapsed_ms = timestamp_ms - self.reference_timestamp
        expected_samples = int((elapsed_ms / 1000.0) * self.sample_rate)

        # Calculate current position
        current_samples = self.get_total_played_samples()

        # Drift detection
        drift_samples = expected_samples - current_samples
        drift_ms = (drift_samples / self.sample_rate) * 1000

        if abs(drift_ms) > 100:
            # Significant drift - resync
            logger.warning(f"Audio drift detected: {drift_ms:.1f}ms")
            self.resync(timestamp_ms)

        return audio_frame
```

**RTP Timestamp Synchronization**:
```python
def process_rtp_packet(rtp_packet):
    """Handle RTP packet with timing info"""
    sequence_number = rtp_packet.sequence
    timestamp = rtp_packet.timestamp
    payload = rtp_packet.payload

    # Detect packet loss
    if sequence_number != last_sequence + 1:
        lost_packets = sequence_number - last_sequence - 1
        logger.warning(f"Lost {lost_packets} RTP packets")
        # Packet loss concealment (PLC)
        interpolate_missing_audio(lost_packets)

    # Reorder if needed (out-of-order delivery)
    insert_at_correct_position(payload, timestamp)
```

---

### 2.2 Protocol Choices

#### 2.2.1 WebSocket

**Advantages**:
- **Full-duplex**: Bidirectional communication over single connection
- **Low latency**: < 50ms typical (vs 200ms+ for HTTP polling)
- **Efficient**: No HTTP header overhead per message
- **Stateful**: Maintains persistent connection
- **Firewall-friendly**: Uses standard ports (80/443)

**Latency Characteristics**:
- Connection establishment: 50-100ms
- Message latency: 10-50ms (depends on network)
- Overhead per message: ~10 bytes (vs 500+ for HTTP)

**Implementation Example** (Python WebSocket server):
```python
import asyncio
import websockets
import json

async def audio_stream_handler(websocket, path):
    """Handle WebSocket audio streaming"""
    call_uuid = path.split('/')[-1]

    logger.info(f"WebSocket connected: {call_uuid}")

    try:
        async for message in websocket:
            # Parse message
            if isinstance(message, bytes):
                # Binary audio data
                await process_audio_chunk(call_uuid, message)
            else:
                # JSON control message
                data = json.loads(message)
                await handle_control_message(call_uuid, data)

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"WebSocket disconnected: {call_uuid}")
    finally:
        cleanup_call_session(call_uuid)

async def process_audio_chunk(call_uuid, audio_bytes):
    """Process incoming audio for STT"""
    # Run STT in thread pool (blocking operation)
    loop = asyncio.get_event_loop()
    transcript = await loop.run_in_executor(
        None,
        stt_engine.transcribe_chunk,
        audio_bytes
    )

    if transcript:
        # Check for barge-in
        await check_barge_in(call_uuid, transcript)

# Start server
start_server = websockets.serve(
    audio_stream_handler,
    "127.0.0.1",
    8080,
    max_size=2**20,  # 1MB max message
    compression=None  # Disable compression for latency
)

asyncio.get_event_loop().run_until_complete(start_server)
```

**Message Format** (Twilio Media Streams example):
```json
{
  "event": "media",
  "streamSid": "MZ1234567890abcdef",
  "media": {
    "track": "inbound",
    "chunk": "2",
    "timestamp": "1234567",
    "payload": "base64_encoded_audio_data..."
  }
}
```

**Best Practices**:
- Use binary frames for audio (lower overhead)
- Disable compression for real-time streams
- Set TCP_NODELAY (disable Nagle's algorithm)
- Implement ping/pong for keepalive
- Handle reconnection gracefully

#### 2.2.2 RTP/RTCP

**Use Cases**:
- Direct VoIP integration (SIP trunks)
- Low-level telephony applications
- Custom media servers
- FreeSWITCH/Asterisk integration

**RTP Characteristics**:
- **Protocol**: UDP (connectionless)
- **Port range**: 10000-20000 (configurable)
- **Payload**: Raw audio (no encoding overhead)
- **Timestamp**: 90kHz clock for synchronization
- **Sequence**: Packet ordering and loss detection

**RTCP (Control Protocol)**:
- Statistics (packet loss, jitter, RTT)
- Sender/receiver reports
- Quality of Service (QoS) monitoring

**Integration Example** (FreeSWITCH unicast):
```bash
# Stream RTP audio to external processor
uuid_media <call_uuid> <ip>:<port>
```

**Advantages over WebSocket**:
- Lower latency (UDP, no TCP handshake)
- More efficient for pure audio
- Standard telephony protocol

**Disadvantages**:
- No built-in reliability (UDP)
- Firewall/NAT traversal challenges
- More complex implementation

#### 2.2.3 HTTP Streaming

**When to Use**:
- Batch processing scenarios
- Recording/archival
- Non-real-time applications
- Simple integration (no WebSocket support)

**Protocols**:
1. **HTTP Long Polling**: Client repeatedly requests updates
2. **Server-Sent Events (SSE)**: Server pushes updates to client
3. **Chunked Transfer Encoding**: Stream data in chunks

**Limitations**:
- **Higher latency**: 200-500ms typical
- **Inefficient**: New connection per request (long polling)
- **Unidirectional**: SSE is server→client only
- **Overhead**: Full HTTP headers per request

**Not Recommended** for barge-in detection due to latency.

---

### 2.3 STT Service Integration

#### 2.3.1 Whisper Streaming (whisper-online)

**Implementation**: whisper_streaming (UFAL)

**How It Works**:
- Processes audio in overlapping chunks
- Uses local agreement policy for low latency
- Emits transcripts confirmed by 2 iterations
- Adaptive latency based on speech patterns

**Latency**: ~3.3 seconds on unsegmented speech (research paper)

**Setup**:
```bash
# Install
pip install whisper-streaming

# Run server
python whisper_online_server.py \
    --model small \
    --language en \
    --backend faster-whisper \
    --host 0.0.0.0 \
    --port 43001
```

**Client Usage**:
```python
import asyncio
import websockets

async def stream_audio():
    uri = "ws://localhost:43001"
    async with websockets.connect(uri) as websocket:
        # Stream audio chunks
        with open("audio.wav", "rb") as f:
            while chunk := f.read(1600):  # 100ms chunks
                await websocket.send(chunk)

                # Receive partial transcripts
                response = await websocket.recv()
                print(f"Transcript: {response}")
```

**Optimization**:
```python
# Configuration for lowest latency
config = {
    "model": "tiny",  # Fastest model
    "backend": "faster-whisper",
    "device": "cuda",
    "compute_type": "float16",
    "beam_size": 1,  # Greedy decode
    "buffer_trimming": "segment",  # Trim aggressively
}
```

**GPU Requirements**:
- tiny: 1GB VRAM
- base: 1GB VRAM
- small: 2GB VRAM (recommended)
- medium: 5GB VRAM
- large: 10GB VRAM

#### 2.3.2 Deepgram Live API

**Features**:
- Sub-300ms latency (Nova-2 model)
- Built-in punctuation and formatting
- Multi-language support (30+ languages)
- Word-level timestamps
- Confidence scores

**Setup**:
```python
from deepgram import Deepgram

dg_client = Deepgram(DEEPGRAM_API_KEY)

# Configure streaming
options = {
    "model": "nova-2",
    "language": "en",
    "punctuate": True,
    "interim_results": True,  # Partial transcripts
    "endpointing": 300,  # ms silence before finalizing
    "utterance_end_ms": 1000,
}

# WebSocket connection
source = {"url": "wss://api.deepgram.com/v1/listen"}
response = await dg_client.transcription.live(options)

# Stream audio
async for chunk in audio_stream:
    response.send(chunk)

# Receive transcripts
@response.on("transcript")
def on_transcript(transcript):
    if transcript["is_final"]:
        print(transcript["channel"]["alternatives"][0]["transcript"])
```

**Pricing** (as of 2024):
- Nova-2: $0.0043/min ($0.59/hour)
- Enhanced: $0.0145/min ($0.87/hour)
- Base: $0.0125/min ($0.75/hour)

**Latency Optimization**:
- Use `nova-2` model (fastest)
- Set `interim_results: true` for progressive updates
- Tune `endpointing` parameter (lower = faster, but may cut off speech)

#### 2.3.3 Google Cloud Speech (Streaming)

**Configuration**:
```python
from google.cloud import speech

client = speech.SpeechClient()

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    language_code="en-US",
    enable_automatic_punctuation=True,
    model="phone_call",  # Optimized for telephony
    use_enhanced=True,
)

streaming_config = speech.StreamingRecognitionConfig(
    config=config,
    interim_results=True,
    single_utterance=False,
)

# Stream audio
def request_generator(audio_stream):
    for chunk in audio_stream:
        yield speech.StreamingRecognizeRequest(audio_content=chunk)

responses = client.streaming_recognize(streaming_config, request_generator(audio_stream))

# Process results
for response in responses:
    for result in response.results:
        if result.is_final:
            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence
            print(f"{transcript} ({confidence:.2f})")
```

**Pricing**: $1.44/hour (phone_call model)

**Latency**: ~350ms (P50)

#### 2.3.4 Azure Speech Services

**Setup**:
```python
import azure.cognitiveservices.speech as speechsdk

speech_config = speechsdk.SpeechConfig(
    subscription=AZURE_SPEECH_KEY,
    region=AZURE_REGION
)

speech_config.speech_recognition_language = "en-US"

# Audio stream config
audio_stream_format = speechsdk.audio.AudioStreamFormat(
    samples_per_second=8000,
    bits_per_sample=16,
    channels=1
)

audio_stream = speechsdk.audio.PushAudioInputStream(audio_stream_format)
audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)

# Create recognizer
recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config,
    audio_config=audio_config
)

# Event handlers
def recognized_cb(evt):
    print(f"RECOGNIZED: {evt.result.text}")

def recognizing_cb(evt):
    print(f"RECOGNIZING: {evt.result.text}")

recognizer.recognized.connect(recognized_cb)
recognizer.recognizing.connect(recognizing_cb)

# Start recognition
recognizer.start_continuous_recognition()

# Stream audio
for chunk in audio_stream_chunks:
    audio_stream.write(chunk)
```

**Pricing**: ~$1.00/hour

**Latency**: ~400ms

#### 2.3.5 Vosk Streaming (Offline)

**Advantages**:
- Fully offline (no internet required)
- Zero cost after model download
- Privacy-friendly (data stays local)
- Lightweight models (50MB-1.8GB)

**Performance**:
- Latency: 100-300ms (depends on model size)
- Accuracy: Lower than cloud services (~15-20% WER)
- CPU usage: Moderate (1 core per stream)

**Setup**:
```python
from vosk import Model, KaldiRecognizer
import json

# Load model (one-time, keep in memory)
model = Model("model/vosk-model-small-en-us-0.15")

# Create recognizer (per call)
recognizer = KaldiRecognizer(model, 8000)
recognizer.SetWords(True)  # Get word timestamps

# Stream audio
for chunk in audio_chunks:
    if recognizer.AcceptWaveform(chunk):
        # Final result
        result = json.loads(recognizer.Result())
        print(result['text'])
    else:
        # Partial result
        partial = json.loads(recognizer.PartialResult())
        print(partial['partial'])
```

**Model Selection**:
- Small (50MB): Fast, lower accuracy
- Large (1.8GB): Slower, better accuracy
- Recommend: Medium models for production

---

## Part 3: Industry Implementations

### 3.1 Jambonz Architecture

**Overview**: Open-source CPaaS (Communications Platform as a Service) optimized for building conversational AI voice applications.

#### How They Handle Barge-in

**Architecture**:
```
SIP Trunk ──→ FreeSWITCH ──→ Feature Server ──→ WebSocket ──→ STT/TTS
                   │                                  │
                   └──────── Media Streams ───────────┘
```

**Barge-in Configuration**:
```javascript
// Background streaming say with barge-in
session.config({
  ttsStream: { enable: true },
  bargeIn: {
    enable: true,
    sticky: true,  // Keep listening after first interrupt
    minBargeinWordCount: 1,
    actionHook: '/speech-detected',
    input: ['speech']
  }
})
.say({text: 'Hi there, how can I help you today?'})
.send();
```

**Event System**:
- `stream_open`: TTS vendor connected, streaming active
- `stream_closed`: TTS disconnected
- `stream_paused`: Buffer full (backpressure)
- `stream_resumed`: Buffer available
- `user_interruption`: Barge-in detected

**Flow Control**:
- Buffer capacity: ~5,000 characters
- Automatic backpressure via `tts:tokens-result` status
- Node.js SDK handles buffering transparently

**Key Innovation**: Combines real-time STT listening with streaming TTS playback in single session.

#### Streaming Implementation

**WebSocket Protocol**:
```javascript
// Send TTS tokens
{
  "type": "command",
  "command": "tts:tokens",
  "data": {
    "id": 101,
    "tokens": "It was the best of times, it was the "
  }
}

// Receive acknowledgment
{
  "type": "tts:tokens-result",
  "data": {
    "id": 101,
    "status": "ok"  // or "failed" with reason
  }
}
```

**Flushing Pattern**:
```javascript
// Periodically flush to generate audio
session.flushTtsTokens();

// Example: On LLM completion
if (messageStreamEvent.type === 'message_stop') {
  session.flushTtsTokens();
}
```

**Barge-in Handling**:
```javascript
session.on('tts:user_interrupt', () => {
  // User spoke during playback
  session.clearTtsTokens();  // Stop playback
  cancelLLMRequest();  // Stop generating
  // Wait for user input to complete...
});
```

#### Lessons Learned

1. **Sticky barge-in**: Keeps listening after first interruption (critical for multi-turn)
2. **Buffering transparency**: SDK abstracts flow control
3. **Event-driven**: Decouples detection from action
4. **Vendor-agnostic**: Works with Deepgram, ElevenLabs, Cartesia, etc.

---

### 3.2 Retell AI Approach

**Overview**: Production voice AI platform focused on ultra-low latency (< 800ms).

#### Streaming Strategy

**Architecture Stack**:
```
Phone Network ──→ WebRTC ──→ Deepgram STT ──→ LLM (Nova Pro) ──→ Deepgram TTS ──→ WebRTC ──→ Phone
                     ↓             ↓                 ↓                    ↓
                   50ms         250ms             200ms                200ms

                   Total: ~700-800ms
```

**Protocol Choice**: WebRTC for bidirectional audio
- Minimizes network-level delays
- Built-in jitter buffering
- Adaptive bitrate
- Packet loss concealment

**Component Selection**:
- **STT**: Deepgram Nova-2 (250ms latency, 8.7% WER)
- **LLM**: Amazon Nova Pro with prompt caching
- **TTS**: Deepgram Aura (streaming output)

#### Latency Optimization

**Techniques**:
1. **Prompt caching**: Pre-cache system prompts (70% tokens cached)
2. **Streaming responses**: LLM streams tokens as generated
3. **TTS streaming**: Begin speaking before LLM finishes
4. **Predictive caching**: Anticipate common responses

**Natural Fillers**:
```javascript
// Keep user engaged during processing
if (processingTime > 500ms) {
  playFiller("Let me look that up for you");
}
```

**Barge-in Implementation**:
- VAD for initial detection (< 50ms)
- STT validation (200-300ms)
- Immediate playback stop
- LLM request cancellation

#### Production Patterns

**Concurrent Call Handling**:
```python
# Scale STT across multiple calls
class MultiCallSTTProcessor:
    def __init__(self, max_concurrent=100):
        self.gpu_batch_size = 8
        self.processing_queue = asyncio.Queue()

    async def batch_process_calls(self):
        """Process multiple calls on single GPU"""
        while True:
            batch = []
            for _ in range(self.gpu_batch_size):
                call_audio = await self.processing_queue.get()
                batch.append(call_audio)

            # Batch inference
            transcripts = await self.stt_model.transcribe_batch(batch)

            # Dispatch results
            for call_id, transcript in zip(batch, transcripts):
                self.send_result(call_id, transcript)
```

**Monitoring**:
- P50/P95/P99 latency tracking
- Real-time quality scoring
- Automatic fallback to simpler models if latency spikes

---

### 3.3 Deepgram Patterns

**Overview**: Leading STT/TTS provider focused on real-time performance.

#### Best Practices

**1. Model Selection**:
- Use `nova-2` for lowest latency
- Enable `interim_results` for progressive transcription
- Set `utterance_end_ms` based on use case

**2. WebSocket Configuration**:
```python
# Optimal settings for conversational AI
options = {
    "model": "nova-2",
    "language": "en",
    "punctuate": True,
    "interim_results": True,
    "endpointing": 300,  # 300ms silence = end
    "utterance_end_ms": 1000,
    "smart_format": True,
}
```

**3. Connection Management**:
```python
async def resilient_deepgram_connection():
    """Auto-reconnect on failures"""
    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            dg = Deepgram(API_KEY)
            return await dg.transcription.live(options)
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
            else:
                raise
```

#### SDK Usage

**Python SDK**:
```python
from deepgram import Deepgram

dg = Deepgram(API_KEY)

# Event handlers
async def on_message(result):
    if result["is_final"]:
        transcript = result["channel"]["alternatives"][0]["transcript"]
        confidence = result["channel"]["alternatives"][0]["confidence"]

        # Check for barge-in
        if state == "PLAYING" and confidence > 0.7:
            trigger_barge_in(transcript)

# Start streaming
connection = await dg.transcription.live(options)
connection.on("transcript", on_message)

# Stream audio
for chunk in audio_stream:
    connection.send(chunk)
```

**Node.js SDK**:
```javascript
const { Deepgram } = require('@deepgram/sdk');

const deepgram = new Deepgram(API_KEY);

const deepgramLive = deepgram.transcription.live({
  model: 'nova-2',
  interim_results: true,
});

deepgramLive.addListener('transcriptReceived', (transcript) => {
  if (transcript.is_final) {
    console.log(transcript.channel.alternatives[0].transcript);
  }
});

// Stream audio
audioStream.on('data', (chunk) => {
  deepgramLive.send(chunk);
});
```

#### Integration Examples

**Twilio + Deepgram**:
```python
from twilio.twiml.voice_response import VoiceResponse, Start

response = VoiceResponse()
start = Start()
start.stream(url='wss://your-server.com/media')
response.append(start)

# In WebSocket handler
async def handle_twilio_stream(websocket):
    async for message in websocket:
        data = json.loads(message)

        if data['event'] == 'media':
            # Forward to Deepgram
            audio = base64.b64decode(data['media']['payload'])
            deepgram_connection.send(audio)
```

---

### 3.4 Twilio Media Streams

**Overview**: Real-time audio streaming for Programmable Voice calls.

#### Architecture Overview

**Unidirectional** (receive only):
```xml
<Response>
  <Start>
    <Stream url="wss://your-server.com/media" track="inbound_track" />
  </Start>
  <Say>Please leave a message</Say>
</Response>
```

**Bidirectional** (send and receive):
```xml
<Response>
  <Connect>
    <Stream url="wss://your-server.com/media" />
  </Connect>
</Response>
```

#### WebSocket Protocol

**Message Types**:

1. **Connected**:
```json
{
  "event": "connected",
  "protocol": "Call",
  "version": "1.0.0"
}
```

2. **Start**:
```json
{
  "event": "start",
  "streamSid": "MZ1234567890",
  "start": {
    "streamSid": "MZ1234567890",
    "accountSid": "AC1234567890",
    "callSid": "CA1234567890",
    "tracks": ["inbound"],
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1
    }
  }
}
```

3. **Media** (audio packets):
```json
{
  "event": "media",
  "streamSid": "MZ1234567890",
  "media": {
    "track": "inbound",
    "chunk": "2",
    "timestamp": "5",
    "payload": "base64_encoded_audio..."
  }
}
```

4. **Mark** (timing events):
```json
{
  "event": "mark",
  "streamSid": "MZ1234567890",
  "mark": {
    "name": "audio_complete"
  }
}
```

#### Barge-in with Mark/Clear

**Mark Command** (set timing marker):
```json
{
  "event": "mark",
  "streamSid": "MZ1234567890",
  "mark": {
    "name": "prompt_start"
  }
}
```

**Clear Command** (stop pending audio):
```json
{
  "event": "clear",
  "streamSid": "MZ1234567890"
}
```

**Barge-in Flow**:
1. Bot starts playing audio
2. Send `mark` event (e.g., "prompt_1_start")
3. Monitor incoming media stream for speech (VAD/STT)
4. When barge-in detected:
   - Send `clear` to flush audio queue
   - Stop sending new audio
5. Wait for user input
6. Resume conversation

**Example**:
```python
async def twilio_barge_in_handler(websocket):
    """Handle Twilio Media Stream with barge-in"""

    async for message in websocket:
        data = json.loads(message)

        if data['event'] == 'media':
            # Process incoming audio
            audio = base64.b64decode(data['media']['payload'])

            # Check for speech
            if vad.is_speech(audio) and state == 'PLAYING':
                # Barge-in detected
                await websocket.send(json.dumps({
                    'event': 'clear',
                    'streamSid': data['streamSid']
                }))

                # Stop playing
                stop_audio_playback()

                # Update state
                state = 'LISTENING'
```

#### Operational Constraints

- **Max 4 unidirectional streams** per call
- **Max 1 bidirectional stream** per call
- Each stream = 1 WebSocket connection
- Regional availability: US1, IE1, AU1

---

## Part 4: Production Best Practices

### 4.1 When to Enable Barge-in

**Enable barge-in for**:
- Conversational AI / voice assistants
- IVR systems with experienced users
- Long prompts (> 10 seconds)
- Multi-turn dialogues
- Customer service bots

**Disable barge-in for**:
- Critical legal/compliance messages
- Error messages (user must hear)
- Important instructions
- Security warnings
- Advertisement playback (regulatory)

**Conditional barge-in**:
```python
def should_enable_barge_in(prompt_type):
    """Decide barge-in per prompt"""
    no_barge_in = [
        'legal_disclaimer',
        'error_critical',
        'security_warning',
        'required_notice'
    ]

    return prompt_type not in no_barge_in
```

---

### 4.2 Performance Monitoring

**Key Metrics**:

1. **Latency**:
   - STT latency (target: < 300ms P50)
   - TTS latency (target: < 200ms P50)
   - Total voice-to-voice (target: < 800ms P50)
   - Barge-in reaction time (target: < 500ms)

2. **Accuracy**:
   - STT Word Error Rate (WER) (target: < 10%)
   - Barge-in false positive rate (target: < 2%)
   - Barge-in false negative rate (target: < 5%)

3. **Resource Usage**:
   - CPU utilization per call
   - GPU memory usage
   - Network bandwidth
   - Concurrent call capacity

**Monitoring Implementation**:
```python
import time
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class BargeInMetrics:
    """Track barge-in performance"""
    detection_latency_ms: float
    stt_confidence: float
    false_positive: bool
    user_satisfied: bool

class MetricsCollector:
    def __init__(self):
        self.metrics = defaultdict(list)

    def record_barge_in(self, call_uuid, metrics: BargeInMetrics):
        """Record barge-in event"""
        self.metrics['latency'].append(metrics.detection_latency_ms)
        self.metrics['confidence'].append(metrics.stt_confidence)
        self.metrics['false_positives'].append(1 if metrics.false_positive else 0)

    def get_statistics(self):
        """Calculate aggregate metrics"""
        import numpy as np

        return {
            'latency_p50': np.percentile(self.metrics['latency'], 50),
            'latency_p95': np.percentile(self.metrics['latency'], 95),
            'latency_p99': np.percentile(self.metrics['latency'], 99),
            'avg_confidence': np.mean(self.metrics['confidence']),
            'false_positive_rate': np.mean(self.metrics['false_positives']) * 100,
        }
```

**Alerting Thresholds**:
```python
def check_health(stats):
    """Alert on degraded performance"""
    alerts = []

    if stats['latency_p95'] > 1000:
        alerts.append('HIGH_LATENCY')

    if stats['false_positive_rate'] > 5.0:
        alerts.append('HIGH_FP_RATE')

    if stats['avg_confidence'] < 0.65:
        alerts.append('LOW_CONFIDENCE')

    return alerts
```

---

### 4.3 Quality Assurance

**Testing Checklist**:

1. **Functional Tests**:
   - [ ] Barge-in triggers on valid speech
   - [ ] No trigger on background noise
   - [ ] Graceful audio fade-out
   - [ ] State transitions correct
   - [ ] Multi-turn conversation works
   - [ ] Handles rapid interruptions

2. **Performance Tests**:
   - [ ] Latency < 800ms (P95)
   - [ ] Handles 100+ concurrent calls
   - [ ] GPU memory stable under load
   - [ ] No memory leaks
   - [ ] WebSocket reconnection works

3. **Edge Cases**:
   - [ ] User interrupts mid-word
   - [ ] Rapid fire interruptions
   - [ ] Very long pauses
   - [ ] Network disconnection
   - [ ] STT API failure
   - [ ] GPU out of memory

**Automated Testing**:
```python
import pytest

def test_barge_in_detection():
    """Test barge-in triggers correctly"""
    robot = RobotFreeSWITCH()
    call_uuid = robot.start_call("1234567890")

    # Start playing prompt
    robot.play_audio(call_uuid, "welcome.wav")
    assert robot.get_state(call_uuid) == "PLAYING"

    # Simulate user speech
    robot.inject_audio(call_uuid, "test_speech.wav")

    # Wait for barge-in
    time.sleep(0.5)

    # Verify barge-in triggered
    assert robot.get_state(call_uuid) == "PROCESSING_RESPONSE"
    assert robot.playback_stopped(call_uuid)

def test_no_false_positive():
    """Test barge-in doesn't trigger on noise"""
    robot = RobotFreeSWITCH()
    call_uuid = robot.start_call("1234567890")

    robot.play_audio(call_uuid, "prompt.wav")

    # Inject background noise
    robot.inject_audio(call_uuid, "background_noise.wav")

    time.sleep(1.0)

    # Verify still playing
    assert robot.get_state(call_uuid) == "PLAYING"
```

---

### 4.4 Failover Strategies

**STT Service Failover**:
```python
class STTWithFailover:
    def __init__(self):
        self.primary = DeepgramSTT()
        self.secondary = GoogleSTT()
        self.tertiary = VoskSTT()  # Offline fallback

    async def transcribe(self, audio):
        """Try services in order"""
        try:
            return await self.primary.transcribe(audio)
        except Exception as e:
            logger.warning(f"Primary STT failed: {e}")
            try:
                return await self.secondary.transcribe(audio)
            except Exception as e:
                logger.error(f"Secondary STT failed: {e}")
                # Offline fallback
                return await self.tertiary.transcribe(audio)
```

**Circuit Breaker Pattern**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0

    async def call(self, func, *args, **kwargs):
        """Execute with circuit breaker"""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'

            raise
```

---

### 4.5 Load Balancing

**Horizontal Scaling**:
```
                    ┌─────────────┐
  Phone Calls ──────┤ Load Balance├────┐
                    └─────────────┘    │
                            │          │
         ┌──────────────────┼──────────┼──────────┐
         │                  │          │          │
    ┌────▼────┐      ┌─────▼───┐  ┌───▼────┐  ┌──▼─────┐
    │ Robot 1 │      │ Robot 2 │  │ Robot 3│  │ Robot 4│
    │ GPU 0   │      │ GPU 1   │  │ GPU 2  │  │ GPU 3  │
    └─────────┘      └─────────┘  └────────┘  └────────┘
```

**Call Distribution**:
```python
class CallLoadBalancer:
    def __init__(self, robot_instances):
        self.robots = robot_instances
        self.call_counts = {r.id: 0 for r in robot_instances}

    def assign_call(self, call_uuid):
        """Assign to least loaded robot"""
        # Simple round-robin
        min_load_robot = min(
            self.robots,
            key=lambda r: self.call_counts[r.id]
        )

        self.call_counts[min_load_robot.id] += 1
        return min_load_robot

    def release_call(self, robot_id):
        """Decrement call count"""
        self.call_counts[robot_id] -= 1
```

**GPU Affinity**:
```python
import os

def set_gpu_affinity(gpu_id):
    """Assign process to specific GPU"""
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)

# Per-worker GPU assignment
workers = [
    {'id': 0, 'gpu': 0, 'max_calls': 50},
    {'id': 1, 'gpu': 1, 'max_calls': 50},
    {'id': 2, 'gpu': 2, 'max_calls': 50},
    {'id': 3, 'gpu': 3, 'max_calls': 50},
]
```

---

### 4.6 Cost Optimization

**Cloud STT Costs** (monthly, 1000 hours):

| Service | Model | Cost/hr | Monthly |
|---------|-------|---------|---------|
| Deepgram | Nova-2 | $0.59 | $590 |
| AssemblyAI | Universal | $0.65 | $650 |
| Google Cloud | Enhanced | $0.87 | $870 |
| Azure | Standard | $1.00 | $1,000 |
| AWS Transcribe | Standard | $1.44 | $1,440 |

**Optimization Strategies**:

1. **Selective STT**:
```python
def should_transcribe(audio_chunk):
    """Only transcribe if VAD detects speech"""
    if vad.is_silence(audio_chunk):
        return False  # Save STT API call
    return True
```

2. **Caching**:
```python
class STTCache:
    """Cache common phrases"""
    def __init__(self):
        self.cache = {}
        self.common_phrases = {
            audio_hash("yes.wav"): "yes",
            audio_hash("no.wav"): "no",
            audio_hash("hello.wav"): "hello",
        }

    def transcribe_with_cache(self, audio):
        """Check cache before API call"""
        audio_sig = audio_hash(audio)

        if audio_sig in self.cache:
            return self.cache[audio_sig]

        # API call
        transcript = stt_api.transcribe(audio)
        self.cache[audio_sig] = transcript
        return transcript
```

3. **Local STT for Simple Cases**:
```python
# Use Vosk for simple commands, Deepgram for complex
if is_simple_command(context):
    transcript = vosk_stt.transcribe(audio)  # Free, local
else:
    transcript = deepgram_stt.transcribe(audio)  # Paid, accurate
```

4. **Batch Processing**:
```python
# Process multiple calls on single GPU
batch_size = 8
batch = collect_audio_chunks(batch_size)
transcripts = stt_model.transcribe_batch(batch)  # 8x efficiency
```

**Cost Monitoring**:
```python
class CostTracker:
    def __init__(self):
        self.stt_seconds = 0
        self.tts_characters = 0

    def record_stt_usage(self, duration_seconds):
        self.stt_seconds += duration_seconds

    def record_tts_usage(self, character_count):
        self.tts_characters += character_count

    def get_estimated_cost(self):
        """Calculate monthly cost projection"""
        stt_cost_per_second = 0.59 / 3600  # Deepgram Nova-2
        tts_cost_per_char = 0.016 / 1000  # Deepgram Aura

        return {
            'stt_cost': self.stt_seconds * stt_cost_per_second,
            'tts_cost': self.tts_characters * tts_cost_per_char,
            'total': (
                self.stt_seconds * stt_cost_per_second +
                self.tts_characters * tts_cost_per_char
            )
        }
```

---

## Part 5: Code Examples

### 5.1 FreeSWITCH + WebSocket + STT

**Complete Barge-in Implementation**:

```python
#!/usr/bin/env python3
"""
FreeSWITCH Barge-in with WebSocket Streaming
Combines ESL, WebSocket audio server, and real-time STT
"""

import asyncio
import websockets
import json
import logging
from ESL import ESLconnection
import threading
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class WebSocketAudioServer:
    """WebSocket server for audio streaming"""

    def __init__(self, host='127.0.0.1', port=8080):
        self.host = host
        self.port = port
        self.stt_model = WhisperModel("small", device="cuda", compute_type="float16")
        self.active_streams = {}  # {call_uuid: audio_buffer}
        self.barge_in_callback = None

    def set_barge_in_callback(self, callback):
        """Set callback for barge-in events"""
        self.barge_in_callback = callback

    async def handle_stream(self, websocket, path):
        """Handle incoming WebSocket audio stream"""
        # Extract call UUID from path: /stream/{call_uuid}
        call_uuid = path.split('/')[-1]
        logger.info(f"WebSocket stream started: {call_uuid}")

        self.active_streams[call_uuid] = {
            'buffer': bytearray(),
            'websocket': websocket
        }

        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Audio data
                    await self.process_audio(call_uuid, message)
                else:
                    # Control message
                    await self.handle_control(call_uuid, json.loads(message))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket stream closed: {call_uuid}")
        finally:
            if call_uuid in self.active_streams:
                del self.active_streams[call_uuid]

    async def process_audio(self, call_uuid, audio_bytes):
        """Process incoming audio chunk"""
        stream = self.active_streams[call_uuid]
        stream['buffer'].extend(audio_bytes)

        # Process in 100ms chunks (800 bytes @ 8kHz, 16-bit)
        chunk_size = 1600

        if len(stream['buffer']) >= chunk_size:
            chunk = bytes(stream['buffer'][:chunk_size])
            stream['buffer'] = stream['buffer'][chunk_size:]

            # Run STT in thread pool (blocking)
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None,
                self.transcribe_chunk,
                chunk
            )

            if transcript and self.barge_in_callback:
                # Trigger barge-in
                await self.barge_in_callback(call_uuid, transcript)

    def transcribe_chunk(self, audio_bytes):
        """Transcribe audio chunk with Whisper"""
        import numpy as np

        # Convert bytes to numpy array
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        segments, info = self.stt_model.transcribe(
            audio,
            beam_size=1,  # Fast greedy decode
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=250)
        )

        # Extract text
        text = " ".join([seg.text for seg in segments]).strip()
        return text if text else None

    async def handle_control(self, call_uuid, message):
        """Handle control messages"""
        logger.debug(f"Control message for {call_uuid}: {message}")

    async def start(self):
        """Start WebSocket server"""
        logger.info(f"Starting WebSocket server at ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_stream, self.host, self.port):
            await asyncio.Future()  # Run forever


class FreeSWITCHBargeInRobot:
    """FreeSWITCH robot with barge-in support"""

    def __init__(self):
        # ESL connection
        self.esl_conn = ESLconnection('127.0.0.1', '8021', 'ClueCon')

        # WebSocket server
        self.ws_server = WebSocketAudioServer()
        self.ws_server.set_barge_in_callback(self.on_barge_in_detected)

        # State
        self.call_states = {}  # {call_uuid: state}
        self.barge_in_events = {}  # {call_uuid: transcript}

    async def on_barge_in_detected(self, call_uuid, transcript):
        """Callback when barge-in detected"""
        logger.info(f"🎤 Barge-in detected on {call_uuid}: '{transcript}'")

        # Store event
        self.barge_in_events[call_uuid] = transcript

        # Stop playback
        self.stop_playback(call_uuid)

        # Update state
        self.call_states[call_uuid] = 'INTERRUPTED'

    def stop_playback(self, call_uuid):
        """Stop audio playback gracefully"""
        # FreeSWITCH break command
        self.esl_conn.api(f"uuid_break {call_uuid} all")
        logger.info(f"Playback stopped for {call_uuid}")

    def start_streaming(self, call_uuid):
        """Start audio streaming to WebSocket"""
        ws_url = f"ws://127.0.0.1:8080/stream/{call_uuid}"

        # Start uuid_audio_stream
        self.esl_conn.api(f"uuid_audio_stream {call_uuid} start {ws_url}")
        logger.info(f"Audio streaming started: {call_uuid} → {ws_url}")

    def stop_streaming(self, call_uuid):
        """Stop audio streaming"""
        self.esl_conn.api(f"uuid_audio_stream {call_uuid} stop")

    def play_with_barge_in(self, call_uuid, audio_file):
        """Play audio file with barge-in detection"""
        # Update state
        self.call_states[call_uuid] = 'PLAYING'

        # Start streaming (for barge-in detection)
        self.start_streaming(call_uuid)

        # Play audio
        self.esl_conn.api(f"uuid_broadcast {call_uuid} {audio_file}")

        # Wait for completion or barge-in
        while self.call_states[call_uuid] == 'PLAYING':
            asyncio.sleep(0.1)

            # Check for barge-in
            if call_uuid in self.barge_in_events:
                logger.info(f"Barge-in occurred: {self.barge_in_events[call_uuid]}")
                return 'INTERRUPTED'

        # Stop streaming
        self.stop_streaming(call_uuid)

        return 'COMPLETED'

    async def run_websocket_server(self):
        """Run WebSocket server in background"""
        await self.ws_server.start()

    def start(self):
        """Start robot"""
        # Start WebSocket server in background
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        threading.Thread(
            target=lambda: loop.run_until_complete(self.run_websocket_server()),
            daemon=True
        ).start()

        logger.info("FreeSWITCH Barge-in Robot started")


# Usage example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    robot = FreeSWITCHBargeInRobot()
    robot.start()

    # Example: Play audio with barge-in
    call_uuid = "12345678-1234-1234-1234-123456789012"
    result = robot.play_with_barge_in(call_uuid, "/tmp/welcome.wav")

    if result == 'INTERRUPTED':
        transcript = robot.barge_in_events[call_uuid]
        print(f"User said: {transcript}")
```

---

### 5.2 Barge-in State Machine

**Production-ready State Machine**:

```python
#!/usr/bin/env python3
"""
Barge-in State Machine
Handles complex state transitions for voice calls with interruption support
"""

from enum import Enum
from typing import Dict, Optional, Callable
import logging
import time

logger = logging.getLogger(__name__)


class CallState(Enum):
    """Call states"""
    INITIATED = "INITIATED"
    AMD_DETECTING = "AMD_DETECTING"
    PLAYING = "PLAYING"
    WAITING = "WAITING"
    INTERRUPTED = "INTERRUPTED"
    PROCESSING_RESPONSE = "PROCESSING_RESPONSE"
    ANALYZING_OBJECTION = "ANALYZING_OBJECTION"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class BargeInStateMachine:
    """
    State machine for managing call flow with barge-in support

    Ensures valid state transitions and handles events correctly.
    """

    # Valid state transitions
    TRANSITIONS = {
        CallState.INITIATED: [CallState.AMD_DETECTING, CallState.TERMINATED],
        CallState.AMD_DETECTING: [CallState.PLAYING, CallState.TERMINATED],
        CallState.PLAYING: [CallState.WAITING, CallState.INTERRUPTED, CallState.TERMINATED],
        CallState.INTERRUPTED: [CallState.PROCESSING_RESPONSE, CallState.WAITING, CallState.TERMINATED],
        CallState.PROCESSING_RESPONSE: [CallState.PLAYING, CallState.ANALYZING_OBJECTION, CallState.TERMINATED],
        CallState.WAITING: [CallState.ANALYZING_OBJECTION, CallState.PLAYING, CallState.TERMINATED],
        CallState.ANALYZING_OBJECTION: [CallState.PLAYING, CallState.COMPLETED, CallState.TERMINATED],
        CallState.COMPLETED: [CallState.TERMINATED],
        CallState.TERMINATED: [],
    }

    def __init__(self, call_uuid: str):
        self.call_uuid = call_uuid
        self.current_state = CallState.INITIATED
        self.state_history = [(CallState.INITIATED, time.time())]

        # State-specific data
        self.state_data = {}

        # Event handlers
        self.on_state_enter = {}  # {CallState: Callable}
        self.on_state_exit = {}  # {CallState: Callable}

    def transition(self, new_state: CallState, reason: str = ""):
        """
        Transition to new state

        Args:
            new_state: Target state
            reason: Reason for transition (for logging)

        Raises:
            ValueError: If transition is invalid
        """
        if new_state not in self.TRANSITIONS.get(self.current_state, []):
            raise ValueError(
                f"Invalid transition: {self.current_state.value} → {new_state.value}"
            )

        old_state = self.current_state

        logger.info(
            f"[{self.call_uuid}] State transition: {old_state.value} → {new_state.value} "
            f"({reason})" if reason else ""
        )

        # Exit current state
        self._exit_state(old_state)

        # Update state
        self.current_state = new_state
        self.state_history.append((new_state, time.time()))

        # Enter new state
        self._enter_state(new_state)

    def _exit_state(self, state: CallState):
        """Execute exit handler for state"""
        if state in self.on_state_exit:
            try:
                self.on_state_exit[state](self.call_uuid, state)
            except Exception as e:
                logger.error(f"Error in exit handler for {state.value}: {e}")

    def _enter_state(self, state: CallState):
        """Execute enter handler for state"""
        if state in self.on_state_enter:
            try:
                self.on_state_enter[state](self.call_uuid, state)
            except Exception as e:
                logger.error(f"Error in enter handler for {state.value}: {e}")

    def register_enter_handler(self, state: CallState, handler: Callable):
        """Register handler called when entering state"""
        self.on_state_enter[state] = handler

    def register_exit_handler(self, state: CallState, handler: Callable):
        """Register handler called when exiting state"""
        self.on_state_exit[state] = handler

    def handle_barge_in(self):
        """Handle barge-in event"""
        if self.current_state == CallState.PLAYING:
            self.transition(CallState.INTERRUPTED, "User barge-in detected")
        else:
            logger.warning(
                f"Barge-in event in non-PLAYING state: {self.current_state.value}"
            )

    def handle_speech_completed(self, transcript: str):
        """Handle completed user speech"""
        if self.current_state == CallState.WAITING:
            self.state_data['last_transcript'] = transcript
            self.transition(CallState.ANALYZING_OBJECTION, "User finished speaking")
        elif self.current_state == CallState.INTERRUPTED:
            self.state_data['interrupt_transcript'] = transcript
            self.transition(CallState.PROCESSING_RESPONSE, "Interrupt speech completed")

    def handle_playback_completed(self):
        """Handle audio playback completion"""
        if self.current_state == CallState.PLAYING:
            self.transition(CallState.WAITING, "Playback finished")

    def handle_timeout(self):
        """Handle user input timeout"""
        if self.current_state == CallState.WAITING:
            self.transition(CallState.COMPLETED, "User timeout")

    def get_state_duration(self) -> float:
        """Get duration in current state (seconds)"""
        if not self.state_history:
            return 0.0
        return time.time() - self.state_history[-1][1]

    def get_total_duration(self) -> float:
        """Get total call duration (seconds)"""
        if not self.state_history:
            return 0.0
        return time.time() - self.state_history[0][1]

    def is_terminal(self) -> bool:
        """Check if in terminal state"""
        return self.current_state == CallState.TERMINATED

    def get_history(self) -> list:
        """Get state transition history"""
        return [
            {
                'state': state.value,
                'timestamp': ts,
                'duration': self.state_history[i+1][1] - ts if i < len(self.state_history) - 1 else time.time() - ts
            }
            for i, (state, ts) in enumerate(self.state_history)
        ]


# Example usage with handlers
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create state machine
    sm = BargeInStateMachine("test-call-123")

    # Register handlers
    def on_enter_playing(call_uuid, state):
        print(f"[{call_uuid}] Starting audio playback")
        # Start streaming audio
        # Start barge-in detection

    def on_exit_playing(call_uuid, state):
        print(f"[{call_uuid}] Stopping audio playback")
        # Stop audio
        # Continue barge-in detection

    def on_enter_interrupted(call_uuid, state):
        print(f"[{call_uuid}] User interrupted - processing")
        # Clear audio queue
        # Focus on user input

    sm.register_enter_handler(CallState.PLAYING, on_enter_playing)
    sm.register_exit_handler(CallState.PLAYING, on_exit_playing)
    sm.register_enter_handler(CallState.INTERRUPTED, on_enter_interrupted)

    # Simulate call flow
    sm.transition(CallState.AMD_DETECTING, "AMD started")
    time.sleep(1)

    sm.transition(CallState.PLAYING, "Human detected, start conversation")
    time.sleep(0.5)

    # User interrupts
    sm.handle_barge_in()

    # User finishes speaking
    sm.handle_speech_completed("I'm not interested")

    # Print history
    print("\nCall history:")
    for entry in sm.get_history():
        print(f"  {entry['state']}: {entry['duration']:.2f}s")
```

---

### 5.3 Production-ready Implementation

**Complete System** (simplified for clarity):

```python
#!/usr/bin/env python3
"""
Production Voice AI System with Barge-in
Integrates all components for real-world deployment
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict
import time

# Import components (assume these exist)
from websocket_server import WebSocketAudioServer
from stt_service import STTService
from tts_service import TTSService
from scenario_manager import ScenarioManager
from objection_matcher import ObjectionMatcher
from state_machine import BargeInStateMachine, CallState

logger = logging.getLogger(__name__)


@dataclass
class CallSession:
    """Represents active call session"""
    call_uuid: str
    phone_number: str
    state_machine: BargeInStateMachine
    scenario: Dict
    objection_matcher: ObjectionMatcher
    audio_buffer: bytearray
    metadata: Dict


class ProductionVoiceAI:
    """
    Production-ready voice AI system

    Features:
    - Real-time barge-in detection
    - State machine management
    - Objection handling
    - Performance monitoring
    - Error recovery
    """

    def __init__(self):
        # Services
        self.stt_service = STTService(model="small", device="cuda")
        self.tts_service = TTSService(provider="deepgram")
        self.scenario_manager = ScenarioManager()

        # WebSocket server
        self.ws_server = WebSocketAudioServer(port=8080)
        self.ws_server.on_audio_received = self.on_audio_received

        # Sessions
        self.active_sessions: Dict[str, CallSession] = {}

        # Metrics
        self.metrics = {
            'total_calls': 0,
            'barge_ins': 0,
            'avg_latency_ms': 0,
        }

    async def start_call(self, call_uuid: str, phone_number: str, scenario_name: str):
        """Initialize new call session"""
        logger.info(f"Starting call: {call_uuid} ({phone_number})")

        # Load scenario
        scenario = self.scenario_manager.get_scenario(scenario_name)

        # Load objections
        theme = scenario.get('theme', 'general')
        objection_matcher = ObjectionMatcher.load_objections_for_theme(theme)

        # Create state machine
        state_machine = BargeInStateMachine(call_uuid)

        # Register state handlers
        state_machine.register_enter_handler(
            CallState.PLAYING,
            self.on_enter_playing
        )
        state_machine.register_enter_handler(
            CallState.INTERRUPTED,
            self.on_enter_interrupted
        )

        # Create session
        session = CallSession(
            call_uuid=call_uuid,
            phone_number=phone_number,
            state_machine=state_machine,
            scenario=scenario,
            objection_matcher=objection_matcher,
            audio_buffer=bytearray(),
            metadata={}
        )

        self.active_sessions[call_uuid] = session
        self.metrics['total_calls'] += 1

        # Start call flow
        await self.run_call_flow(call_uuid)

    async def run_call_flow(self, call_uuid: str):
        """Execute call conversation flow"""
        session = self.active_sessions[call_uuid]
        sm = session.state_machine

        try:
            # 1. AMD Detection
            sm.transition(CallState.AMD_DETECTING, "Starting AMD")
            amd_result = await self.detect_answering_machine(call_uuid)

            if amd_result != 'HUMAN':
                logger.info(f"AMD detected {amd_result}, ending call")
                sm.transition(CallState.TERMINATED, f"AMD: {amd_result}")
                return

            # 2. Play greeting
            sm.transition(CallState.PLAYING, "Starting conversation")
            greeting = session.scenario['phases'][0]['text']
            await self.play_with_barge_in(call_uuid, greeting)

            # 3. Conversation loop
            while not sm.is_terminal():
                if sm.current_state == CallState.WAITING:
                    # Wait for user response
                    transcript = await self.wait_for_speech(call_uuid, timeout=10)

                    if transcript:
                        sm.handle_speech_completed(transcript)
                    else:
                        sm.handle_timeout()

                elif sm.current_state == CallState.ANALYZING_OBJECTION:
                    # Check for objection
                    transcript = sm.state_data.get('last_transcript', '')
                    match = session.objection_matcher.find_best_match(transcript)

                    if match:
                        # Play objection response
                        response = match['response']
                        sm.transition(CallState.PLAYING, "Objection response")
                        await self.play_with_barge_in(call_uuid, response)
                    else:
                        # Continue scenario
                        sm.transition(CallState.COMPLETED, "Scenario complete")

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in call flow: {e}")
            sm.transition(CallState.TERMINATED, f"Error: {e}")

        finally:
            # Cleanup
            await self.end_call(call_uuid)

    async def play_with_barge_in(self, call_uuid: str, text: str):
        """Play audio with barge-in detection"""
        session = self.active_sessions[call_uuid]

        # Generate audio
        audio_data = await self.tts_service.synthesize(text)

        # Start playback
        await self.start_playback(call_uuid, audio_data)

        # Wait for playback completion or barge-in
        while session.state_machine.current_state == CallState.PLAYING:
            await asyncio.sleep(0.1)

        if session.state_machine.current_state == CallState.INTERRUPTED:
            logger.info(f"Playback interrupted by user")

    async def on_audio_received(self, call_uuid: str, audio_bytes: bytes):
        """Handle incoming audio from WebSocket"""
        if call_uuid not in self.active_sessions:
            return

        session = self.active_sessions[call_uuid]
        session.audio_buffer.extend(audio_bytes)

        # Process in chunks
        chunk_size = 1600  # 100ms @ 8kHz

        if len(session.audio_buffer) >= chunk_size:
            chunk = bytes(session.audio_buffer[:chunk_size])
            session.audio_buffer = session.audio_buffer[chunk_size:]

            # Transcribe
            start_time = time.time()
            transcript = await self.stt_service.transcribe_chunk(chunk)
            latency_ms = (time.time() - start_time) * 1000

            # Update metrics
            self.metrics['avg_latency_ms'] = (
                (self.metrics['avg_latency_ms'] * 0.9) + (latency_ms * 0.1)
            )

            if transcript:
                await self.on_speech_detected(call_uuid, transcript)

    async def on_speech_detected(self, call_uuid: str, transcript: str):
        """Handle detected speech"""
        session = self.active_sessions[call_uuid]
        sm = session.state_machine

        logger.info(f"[{call_uuid}] Speech detected: '{transcript}'")

        if sm.current_state == CallState.PLAYING:
            # Barge-in detected
            self.metrics['barge_ins'] += 1
            sm.handle_barge_in()
            sm.state_data['interrupt_transcript'] = transcript

        elif sm.current_state == CallState.WAITING:
            # Expected user response
            sm.state_data['last_transcript'] = transcript

    def on_enter_playing(self, call_uuid: str, state: CallState):
        """Handler when entering PLAYING state"""
        logger.info(f"[{call_uuid}] Starting audio playback")
        # Start WebSocket streaming for barge-in detection

    def on_enter_interrupted(self, call_uuid: str, state: CallState):
        """Handler when entering INTERRUPTED state"""
        logger.info(f"[{call_uuid}] User interrupted - stopping playback")
        # Stop audio playback
        # Clear TTS queue

    async def detect_answering_machine(self, call_uuid: str) -> str:
        """Detect if call answered by machine"""
        # Simplified - use actual AMD service
        await asyncio.sleep(1)
        return 'HUMAN'

    async def start_playback(self, call_uuid: str, audio_data: bytes):
        """Start audio playback"""
        # Send to FreeSWITCH/telephony system
        pass

    async def wait_for_speech(self, call_uuid: str, timeout: float) -> Optional[str]:
        """Wait for user to speak"""
        session = self.active_sessions[call_uuid]
        sm = session.state_machine

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if 'last_transcript' in sm.state_data:
                transcript = sm.state_data['last_transcript']
                del sm.state_data['last_transcript']
                return transcript

            await asyncio.sleep(0.1)

        return None  # Timeout

    async def end_call(self, call_uuid: str):
        """Cleanup call session"""
        logger.info(f"Ending call: {call_uuid}")

        if call_uuid in self.active_sessions:
            session = self.active_sessions[call_uuid]

            # Log statistics
            history = session.state_machine.get_history()
            logger.info(f"Call duration: {session.state_machine.get_total_duration():.1f}s")
            logger.info(f"State transitions: {len(history)}")

            # Remove session
            del self.active_sessions[call_uuid]

    def get_metrics(self) -> Dict:
        """Get system metrics"""
        return {
            **self.metrics,
            'active_calls': len(self.active_sessions),
        }


# Main
async def main():
    logging.basicConfig(level=logging.INFO)

    # Create system
    system = ProductionVoiceAI()

    # Start WebSocket server
    await system.ws_server.start()

    # Handle calls
    await system.start_call(
        call_uuid="test-123",
        phone_number="+1234567890",
        scenario_name="sales_script_v1"
    )

    # Keep running
    while True:
        await asyncio.sleep(1)
        metrics = system.get_metrics()
        logger.info(f"Metrics: {metrics}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Conclusion

This guide covers the essential aspects of implementing barge-in detection and audio streaming in production voice AI systems:

**Key Takeaways**:

1. **Hybrid Detection**: Combine VAD (fast, 50ms) with STT (accurate, 300ms) for optimal barge-in
2. **Streaming Architecture**: Use WebSocket for low-latency bidirectional audio
3. **State Management**: Implement robust state machine for call flow
4. **Latency Budget**: Target < 800ms total (STT 300ms + LLM 200ms + TTS 200ms + network 100ms)
5. **Production Readiness**: Monitor metrics, handle failures, optimize costs

**Recommended Stack**:
- **STT**: Deepgram Nova-2 or Whisper (local GPU)
- **TTS**: Deepgram Aura or ElevenLabs
- **VAD**: Silero VAD
- **Protocol**: WebSocket (Twilio Media Streams or custom)
- **Platform**: Jambonz (open-source) or Retell AI (managed)

**Resources**:
- Jambonz Documentation: https://docs.jambonz.org
- Deepgram Live Streaming: https://developers.deepgram.com/docs/getting-started-with-live-streaming-audio
- Whisper Streaming: https://github.com/ufal/whisper_streaming
- Silero VAD: https://github.com/snakers4/silero-vad
- Twilio Media Streams: https://www.twilio.com/docs/voice/media-streams

---

**Document Version**: 1.0
**Last Updated**: 2025-01-14
**Author**: Generated from extensive industry research and production implementations
