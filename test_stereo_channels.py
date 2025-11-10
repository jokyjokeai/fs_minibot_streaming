#!/usr/bin/env python3
"""
Test Stereo Channel Mapping - Verify LEFT vs RIGHT
===================================================

Tests which channel (::2 vs 1::2) contains CLIENT vs ROBOT audio.

Test scenarios:
1. AMD recording (should contain client "allô" + robot start)
2. Barge-in recording (should contain client interrupt + robot audio)
3. Waiting response recording (should contain client full response)

Expected:
- LEFT channel (index 0) = CLIENT audio
- RIGHT channel (index 1) = ROBOT audio

Bug hypothesis:
- Current code uses stereo_samples[::2] thinking it's LEFT
- But [::2] extracts indices 0,2,4... which may be RIGHT channel
- Should use [1::2] for LEFT channel (indices 1,3,5...)
"""

import logging
from pathlib import Path
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_channel(stereo_wav_path: str, channel: int, output_path: str):
    """
    Extract single channel from stereo WAV using soundfile.

    Args:
        stereo_wav_path: Input stereo WAV file
        channel: 0=first channel, 1=second channel
        output_path: Output mono WAV file
    """
    # Read stereo audio
    audio, samplerate = sf.read(stereo_wav_path, always_2d=True)

    # Verify stereo
    if audio.shape[1] != 2:
        raise ValueError(f"File is not stereo: {audio.shape[1]} channels")

    # Extract channel
    mono_audio = audio[:, channel]

    # Write mono WAV
    sf.write(output_path, mono_audio, samplerate)

    logger.info(f"✅ Extracted channel {channel} → {output_path}")


def transcribe_audio(audio_path: str, model: WhisperModel) -> str:
    """Transcribe audio file."""
    segments, info = model.transcribe(audio_path, language="fr", beam_size=5)
    transcription = " ".join([seg.text for seg in segments]).strip()
    return transcription


def test_stereo_mapping(stereo_wav_path: str, expected_client: str = None, expected_robot: str = None):
    """
    Test stereo channel mapping for a recording.

    Args:
        stereo_wav_path: Path to stereo WAV file
        expected_client: Expected text in client audio (optional)
        expected_robot: Expected text in robot audio (optional)
    """
    stereo_path = Path(stereo_wav_path)
    if not stereo_path.exists():
        logger.error(f"❌ File not found: {stereo_path}")
        return

    logger.info(f"\n{'='*80}")
    logger.info(f"🧪 Testing: {stereo_path.name}")
    logger.info(f"{'='*80}")

    # Extract channels
    temp_dir = Path("/tmp")
    channel0_path = temp_dir / f"test_channel0_{stereo_path.stem}.wav"
    channel1_path = temp_dir / f"test_channel1_{stereo_path.stem}.wav"

    extract_channel(str(stereo_path), 0, str(channel0_path))
    extract_channel(str(stereo_path), 1, str(channel1_path))

    # Transcribe both channels
    logger.info("\n📝 Transcribing channels...")
    model = WhisperModel("small", device="cpu", compute_type="int8")

    transcription_ch0 = transcribe_audio(str(channel0_path), model)
    transcription_ch1 = transcribe_audio(str(channel1_path), model)

    # Results
    logger.info(f"\n📊 RESULTS:")
    logger.info(f"─" * 80)
    logger.info(f"Channel 0 (::2 - even indices 0,2,4...):")
    logger.info(f"  Text: {transcription_ch0}")
    logger.info(f"")
    logger.info(f"Channel 1 (1::2 - odd indices 1,3,5...):")
    logger.info(f"  Text: {transcription_ch1}")
    logger.info(f"─" * 80)

    # Analysis
    logger.info(f"\n🔍 ANALYSIS:")

    # Check if expected texts match
    if expected_client:
        if expected_client.lower() in transcription_ch0.lower():
            logger.info(f"  ✅ Channel 0 contains CLIENT text: '{expected_client}'")
            logger.warning(f"  ⚠️  BUG CONFIRMED: Code uses [::2] thinking it's LEFT (client), but it's correct!")
        elif expected_client.lower() in transcription_ch1.lower():
            logger.warning(f"  ❌ Channel 1 contains CLIENT text: '{expected_client}'")
            logger.error(f"  🐛 BUG CONFIRMED: Code uses [::2] for LEFT but it's actually RIGHT (robot)!")
            logger.error(f"  🔧 FIX: Change stereo_samples[::2] → stereo_samples[1::2]")

    if expected_robot:
        if expected_robot.lower() in transcription_ch0.lower():
            logger.warning(f"  ❌ Channel 0 contains ROBOT text: '{expected_robot}'")
            logger.error(f"  🐛 BUG CONFIRMED: Code uses [::2] for LEFT but it's actually RIGHT (robot)!")
            logger.error(f"  🔧 FIX: Change stereo_samples[::2] → stereo_samples[1::2]")
        elif expected_robot.lower() in transcription_ch1.lower():
            logger.info(f"  ✅ Channel 1 contains ROBOT text: '{expected_robot}'")

    # Cleanup
    channel0_path.unlink(missing_ok=True)
    channel1_path.unlink(missing_ok=True)


def main():
    """Test all recording types."""
    recordings_dir = Path("/usr/local/freeswitch/recordings")

    # Find latest recordings
    logger.info("🔍 Searching for test recordings...")

    # 1. Test barge-in (critical bug)
    bargein_files = sorted(recordings_dir.glob("bargein_*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    if bargein_files:
        logger.info(f"\n{'='*80}")
        logger.info("🧪 TEST 1: BARGE-IN (Critical Bug)")
        logger.info(f"{'='*80}")
        test_stereo_mapping(
            str(bargein_files[0]),
            expected_robot="Bonjour, je suis Thierry"  # Robot hello.wav text
        )

    # 2. Test AMD
    amd_files = sorted(recordings_dir.glob("amd_*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    if amd_files:
        logger.info(f"\n{'='*80}")
        logger.info("🧪 TEST 2: AMD (Potential Bug)")
        logger.info(f"{'='*80}")
        test_stereo_mapping(
            str(amd_files[0]),
            expected_client="allô"  # Common AMD response
        )

    # 3. Test waiting response
    waiting_files = sorted(recordings_dir.glob("recording_*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    if waiting_files:
        logger.info(f"\n{'='*80}")
        logger.info("🧪 TEST 3: WAITING RESPONSE (Should work)")
        logger.info(f"{'='*80}")
        test_stereo_mapping(str(waiting_files[0]))

    logger.info(f"\n{'='*80}")
    logger.info("✅ Stereo channel mapping tests completed")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()
