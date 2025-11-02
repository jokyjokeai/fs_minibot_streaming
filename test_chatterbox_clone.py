#!/usr/bin/env python3
"""
Test Chatterbox Voice Cloning

Usage:
    python test_chatterbox_clone.py <reference.wav> <text>

Example:
    python test_chatterbox_clone.py voices/ss/reference.wav "Bonjour, ceci est un test"
"""

import sys
import os
from pathlib import Path

# Import Chatterbox
try:
    from chatterbox import ChatterboxTTS
    print("✅ Chatterbox imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Chatterbox: {e}")
    print("   Install with: pip install git+https://github.com/resemble-ai/chatterbox.git")
    sys.exit(1)


def test_voice_cloning(reference_audio: str, text: str, output_file: str = "test_clone.wav"):
    """
    Test voice cloning with Chatterbox.

    Args:
        reference_audio: Path to reference.wav (voice to clone)
        text: Text to synthesize with cloned voice
        output_file: Output audio file
    """
    print("\n" + "="*70)
    print("🎤 Chatterbox Voice Cloning Test")
    print("="*70)
    print()

    # Check reference file
    ref_path = Path(reference_audio)
    if not ref_path.exists():
        print(f"❌ Reference audio not found: {reference_audio}")
        return False

    print(f"📁 Reference audio: {ref_path}")
    print(f"📝 Text to synthesize: {text}")
    print(f"💾 Output file: {output_file}")
    print()

    try:
        # Initialize Chatterbox TTS
        print("🔧 Initializing Chatterbox TTS...")
        tts = ChatterboxTTS()
        print("✅ Chatterbox initialized")
        print()

        # Clone voice from reference
        print(f"🎵 Loading speaker voice from {ref_path.name}...")
        tts.load_speaker_embedding(str(ref_path))
        print("✅ Speaker voice loaded")
        print()

        # Generate audio
        print(f"🎙️  Synthesizing: '{text}'...")
        audio = tts.tts(text, speaker_embedding=str(ref_path))

        # Save to file
        print(f"💾 Saving to {output_file}...")
        tts.save_wav(audio, output_file)
        print(f"✅ Audio saved successfully!")
        print()

        # File info
        output_path = Path(output_file)
        if output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"📊 Output file size: {size_kb:.2f} KB")
            print(f"📍 Full path: {output_path.absolute()}")

        print()
        print("="*70)
        print("✅ Voice cloning test completed successfully!")
        print("="*70)
        print()
        print("🔊 Play the audio:")
        print(f"   ffplay {output_file}")
        print()

        return True

    except Exception as e:
        print(f"❌ Voice cloning failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python test_chatterbox_clone.py <reference.wav> <text>")
        print()
        print("Example:")
        print("  python test_chatterbox_clone.py voices/ss/reference.wav 'Bonjour, ceci est un test'")
        sys.exit(1)

    reference_audio = sys.argv[1]
    text = " ".join(sys.argv[2:])

    success = test_voice_cloning(reference_audio, text)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
