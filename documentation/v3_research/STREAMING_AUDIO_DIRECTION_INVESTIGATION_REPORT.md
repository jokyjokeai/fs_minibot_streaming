# WebSocket Audio Streaming - Direction Investigation Report

**Date:** 2025-11-15
**Issue:** mono mode captures wrong audio (Whisper hallucinations instead of client speech)
**Status:** IN PROGRESS - BLOCKED by CUDA/cuDNN crash

---

## Executive Summary

✅ **WORKING**: WebSocket audio streaming via `uuid_audio_stream` + `mod_audio_stream`
✅ **WORKING**: FreeSWITCH connects to WebSocket and sends audio frames
✅ **WORKING**: Syntax corrected from invalid `read 16000` to valid `mono 16000`
❌ **PROBLEM**: `mono` mode transcribes Whisper hallucinations, not client speech
⚠️ **BLOCKER**: CUDA/cuDNN library crash prevents diagnostic data collection

---

## What We've Achieved

### 1. WebSocket Synchronization (FIXED)
**Problem:** Race condition - FreeSWITCH tried to connect before WebSocket server was listening
**Solution:** Implemented `threading.Event()` synchronization with `on_ready` callback
**Files Modified:**
- `/V3/system/robot_freeswitch_v3.py` lines 154-181, 255-282
- `/V3/system/services/websocket_audio_server.py` lines 375-399

**Result:** ✅ Server now confirms listening before calls proceed

---

### 2. uuid_audio_stream Syntax (FIXED)
**Problem:** Invalid parameter `read 16000` causing `-ERR no reply`
**Solution:** Changed to valid `mono 16000` syntax
**Files Modified:** `/V3/system/robot_freeswitch_v3.py` lines 740, 1928, 2131

**Command:**
```bash
uuid_audio_stream <uuid> start ws://127.0.0.1:8080/stream_mono/<uuid> mono 16000
```

**Result:** ✅ `+OK Success` - FreeSWITCH accepts command and connects

---

### 3. Audio Frame Reception (WORKING)
**Confirmed:**
- ✅ WebSocket receives connections from FreeSWITCH
- ✅ Binary audio frames arriving (1280 bytes = 64ms @ 16kHz mono)
- ✅ Frame count increments correctly

**Log Evidence:**
```
[9cf73834] ✅ MONO stream confirmed (1280 bytes/frame)
[9cf73834] WebSocket connection established from ('127.0.0.1', 53982)
[9cf73834] AudioStreamSession created (MONO forced, 16kHz, L16 PCM)
```

---

## The Core Problem

### Symptoms
User speaks "BONJOUR" during TTS playback, but Whisper transcribes:
- ❌ "Sous-titres réalisés par la communauté d'Amara.org"
- ❌ "vous remercie d'avoir regardé cette vidéo"
- ❌ "je vous remercie et je vous remercie"
- ❌ "donner une petite vidéo sur ce que vous avez fait"

These are **classic Whisper hallucinations on silence/noise**, NOT actual speech.

### Hypothesis
`mono` mode may be capturing:
1. **WRITE leg** (robot TTS) instead of READ leg (client speech) - MOST LIKELY
2. **Silence** - client audio not reaching FreeSWITCH
3. **Echo-canceled audio** - client speech removed during playback

### Research Findings

#### mod_audio_fork (Jambonz) vs mod_audio_stream
**Jambonz uses mod_audio_fork via drachtio:**
```javascript
await ep.forkAudioStart({
  wsUrl: 'ws://...',
  mixType: 'mono',  // defaults to mono!
  sampling: '16k',
  metadata,
  bidirectionalAudio: {}
});
```

**mod_audio_fork documentation states:**
> `mixType: "mono"` = **"Single channel containing caller's audio only"**

**But our mod_audio_stream `mono` behavior:**
- Captures audio successfully (frames received)
- But transcriptions suggest wrong direction or silence

**Critical difference:** mod_audio_stream and mod_audio_fork are DIFFERENT modules
- mod_audio_fork: Custom drachtio module (requires custom FreeSWITCH build)
- mod_audio_stream: FreeSWITCH built-in module

They may interpret "mono" differently for outbound calls!

---

### stereo/mixed Mode Tests (FAILED)
**Attempted:**
```bash
# Attempt 1: stereo mode
uuid_audio_stream <uuid> start ws://... stereo 16000
Result: 0 frames received ❌

# Attempt 2: mixed mode
uuid_audio_stream <uuid> start ws://... mixed 16000
Result: 0 frames received ❌
```

**Conclusion:** Only `mono` mode works via WebSocket with mod_audio_stream
stereo/mixed either not supported or has different requirements (dialplan configuration?)

---

## Diagnostic Approach

### RMS Audio Level Analysis (IMPLEMENTED)
Added diagnostic logging to determine what audio `mono` mode captures:

**Code Added** (`websocket_audio_server.py` lines 136-147):
```python
# Mono processing - calculate RMS to diagnose audio levels
audio_to_process = audio_array
rms_mono = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

# Log audio levels every 10 frames for diagnosis
if self.total_frames_received % 10 == 0:
    logger.info(
        f"[{self.short_uuid}] 🔍 MONO DIAGNOSTIC: Frame {self.total_frames_received}, "
        f"RMS={rms_mono:.0f}, "
        f"Min={audio_array.min()}, Max={audio_array.max()}, "
        f"Mean={np.mean(audio_array):.1f}"
    )
```

**Expected Results:**
- **If capturing robot TTS:** RMS 1000-5000+ during playback
- **If capturing client speech:** RMS 1000-5000+ only when user speaks
- **If silence:** RMS 50-300 (noise floor)

**Actual Result:** ❌ **CANNOT TEST** - CUDA/cuDNN crash on first frame

---

## Current Blocker: CUDA/cuDNN Crash

### Error
```
Unable to load any of {libcudnn_ops.so.9.1.0, libcudnn_ops.so.9.1, libcudnn_ops.so.9, libcudnn_ops.so}
Invalid handle. Cannot load symbol cudnnCreateTensorDescriptor
timeout: the monitored command dumped core
```

### Impact
Test crashes IMMEDIATELY when Faster-Whisper processes first audio chunk:
```
[4d72d935] ✅ MONO stream confirmed (1280 bytes/frame)   # Frame 1 received
[4d72d935] 🎯 Using STREAMING mode (process_chunk)      # Starting transcription
Processing audio with duration 00:00.040                 # Whisper starts
Unable to load libcudnn_ops.so.9.1.0                     # CRASH!
```

### Previous Git Commits Show This Was "Fixed"
```
89f644e FIX CRITICAL: Résolution conflit CUDA/cuDNN + PHASE 2 improvements
```
But the issue persists or is intermittent.

---

## Next Steps (Priority Order)

### Option 1: Fix CUDA/cuDNN First (RECOMMENDED)
**Rationale:** Cannot diagnose audio direction while Whisper crashes
**Actions:**
1. Verify cuDNN 9.x libraries are installed and accessible
2. Check `LD_LIBRARY_PATH` includes cuDNN path
3. Test with CPU-only Whisper temporarily to collect diagnostic data
4. Consider downgrading to cuDNN 8.x if compatible

### Option 2: CPU-only Diagnostic Mode
**Rationale:** Bypass CUDA issue temporarily for diagnosis
**Actions:**
1. Modify test to use `device='cpu'` for Whisper
2. Collect RMS diagnostic logs
3. Determine audio direction captured by `mono` mode
4. Fix direction issue, then return to GPU

### Option 3: Raw Audio File Capture
**Rationale:** Skip Whisper entirely, analyze raw PCM
**Actions:**
1. Save incoming WebSocket frames to `/tmp/captured_audio.raw`
2. Play back with: `sox -t raw -r 16000 -e signed -b 16 -c 1 captured_audio.raw output.wav`
3. Listen to determine if it's robot TTS or client speech
4. Analyze with `ffprobe` or audio editor

### Option 4: Install mod_audio_fork
**Rationale:** Match Jambonz's working implementation
**Actions:**
1. Clone `drachtio-freeswitch-modules`
2. Compile mod_audio_fork
3. Test if it handles `mono` direction correctly
4. Compare behavior with mod_audio_stream

---

## Files Modified (This Session)

### `/V3/system/robot_freeswitch_v3.py`
**Lines 154-181:** WebSocket server synchronization with `threading.Event()`
**Lines 255-282:** `_run_websocket_server()` with `on_ready` callback
**Lines 740, 1928, 2131:** Changed `read 16000` → `mono 16000`

### `/V3/system/services/websocket_audio_server.py`
**Lines 375-399:** Added `on_ready` callback parameter to `start()`
**Lines 136-147:** Added RMS diagnostic logging for mono mode

---

## Test Log References

### Successful Connection (Before Diagnostic Code)
`/home/jokyjokeai/Desktop/fs_minibot_streaming/test_streaming_final.log`
- Shows mono mode working, frames received
- Whisper hallucinations observed
- Test completed without crash (earlier run)

### Failed Test With Diagnostic (CUDA Crash)
`/tmp/diagnostic_test.log`
- Mono mode confirmed working (1 frame received)
- Crashed before reaching frame 10 (diagnostic trigger)
- cuDNN library loading failure

---

## Conclusion

**Status:** Audio streaming infrastructure is WORKING, but we cannot determine audio direction due to:
1. CUDA/cuDNN crash preventing diagnostic data collection
2. Whisper hallucinations suggest wrong direction OR silence
3. stereo/mixed modes not working (0 frames)

**Recommendation:** Fix CUDA/cuDNN issue FIRST, then collect RMS diagnostic data to determine if `mono` captures client speech or robot TTS. If `mono` captures wrong direction, consider installing mod_audio_fork or using dialplan-based approach.

**User Context:** User explicitly stated streaming is requirement (not file-based uuid_record), and Jambonz successfully uses mod_audio_fork with mono mode. Our mod_audio_stream may behave differently.
