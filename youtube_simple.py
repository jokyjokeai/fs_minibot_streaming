#!/usr/bin/env python3
"""
Simple YouTube audio extractor - NO diarization required
Just downloads audio and chunks it into 5-10s segments
"""

import argparse
import subprocess
import tempfile
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_youtube_audio(url: str) -> Path:
    """Download YouTube audio using yt-dlp"""
    temp_dir = Path(tempfile.mkdtemp())
    output_path = temp_dir / "audio.wav"

    logger.info(f"📥 Downloading: {url}")

    cmd = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", "wav",
        "--audio-quality", "0",  # Best quality
        "-o", str(output_path),
        url
    ]

    subprocess.run(cmd, check=True)
    logger.info(f"✅ Downloaded to: {output_path}")

    return output_path

def chunk_audio(audio_path: Path, output_dir: Path, min_duration: int = 5000, max_duration: int = 10000):
    """
    Chunk audio into segments using silence detection

    Args:
        audio_path: Path to audio file
        output_dir: Output directory
        min_duration: Min chunk duration in ms (default 5s)
        max_duration: Max chunk duration in ms (default 10s)
    """
    logger.info(f"🔪 Chunking audio into {min_duration/1000}s-{max_duration/1000}s segments...")

    # Load audio
    audio = AudioSegment.from_wav(str(audio_path))

    # Detect non-silent chunks
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=500,  # 500ms of silence = split point
        silence_thresh=-40,   # -40dB threshold
        seek_step=10
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_saved = 0

    for i, (start, end) in enumerate(nonsilent_ranges, 1):
        duration = end - start

        # Skip too short segments
        if duration < min_duration:
            continue

        # Split long segments
        if duration > max_duration:
            # Split into multiple chunks
            num_chunks = int(duration / max_duration) + 1
            chunk_duration = duration / num_chunks

            for j in range(num_chunks):
                chunk_start = start + int(j * chunk_duration)
                chunk_end = start + int((j + 1) * chunk_duration)

                chunk = audio[chunk_start:chunk_end]

                # Convert to mono 22050Hz
                chunk = chunk.set_channels(1)
                chunk = chunk.set_frame_rate(22050)

                output_file = output_dir / f"youtube_{chunks_saved+1:03d}.wav"
                chunk.export(str(output_file), format="wav")

                chunks_saved += 1
                logger.info(f"   ✅ Saved: {output_file.name} ({len(chunk)/1000:.1f}s)")
        else:
            # Save chunk as-is
            chunk = audio[start:end]

            # Convert to mono 22050Hz
            chunk = chunk.set_channels(1)
            chunk = chunk.set_frame_rate(22050)

            output_file = output_dir / f"youtube_{chunks_saved+1:03d}.wav"
            chunk.export(str(output_file), format="wav")

            chunks_saved += 1
            logger.info(f"   ✅ Saved: {output_file.name} ({len(chunk)/1000:.1f}s)")

    logger.info(f"\n✅ Total chunks saved: {chunks_saved}")
    return chunks_saved

def main():
    parser = argparse.ArgumentParser(description="Simple YouTube audio extractor (no diarization)")
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--voice", required=True, help="Voice name (output to voices/{name}/)")
    parser.add_argument("--min-duration", type=int, default=5, help="Min chunk duration in seconds (default: 5)")
    parser.add_argument("--max-duration", type=int, default=10, help="Max chunk duration in seconds (default: 10)")

    args = parser.parse_args()

    # Output directory
    output_dir = Path("voices") / args.voice

    try:
        # Download
        audio_path = download_youtube_audio(args.url)

        # Chunk
        chunk_audio(
            audio_path,
            output_dir,
            min_duration=args.min_duration * 1000,
            max_duration=args.max_duration * 1000
        )

        logger.info(f"\n✅ Done! Files saved to: {output_dir}/")
        logger.info(f"\n💡 Next step:")
        logger.info(f"   python3 clone_voice_chatterbox.py --voice {args.voice} --skip-tts")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
