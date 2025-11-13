# -*- coding: utf-8 -*-
"""
Faster-Whisper STT Service - MiniBotPanel v3

GPU-optimized Speech-to-Text using Faster-Whisper
Target latency: 50-200ms (GPU batch processing)
"""

import logging
import time
from typing import Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FasterWhisperSTT:
    """
    Faster-Whisper STT Service with GPU optimization

    Uses CTranslate2-optimized Whisper for fast transcription
    Batch processing mode for .wav files
    """

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "fr",
        beam_size: int = 1
    ):
        """
        Initialize Faster-Whisper STT

        Args:
            model_name: Model size (tiny/base/small/medium/large)
            device: "cuda" for GPU, "cpu" for CPU
            compute_type: "float16" (GPU fast) or "int8" (CPU fast)
            language: Language code (fr/en/etc)
            beam_size: Beam search size (1=fastest, 5=balanced)
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.model = None

        logger.info(
            f"FasterWhisperSTT init: "
            f"model={model_name}, device={device}, compute_type={compute_type}"
        )

        # Load model
        self._load_model()

    def _load_model(self):
        """Load Faster-Whisper model"""
        try:
            from faster_whisper import WhisperModel

            start_time = time.time()

            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type
            )

            load_time = (time.time() - start_time) * 1000

            logger.info(
                f"Faster-Whisper model loaded in {load_time:.0f}ms "
                f"({self.model_name}/{self.device})"
            )

        except ImportError:
            logger.error("faster-whisper not installed! pip install faster-whisper")
            raise
        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper model: {e}")
            raise

    def transcribe_file(
        self,
        audio_path: str,
        vad_filter: bool = True,
        no_speech_threshold: Optional[float] = None,
        condition_on_previous_text: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe audio file

        Args:
            audio_path: Path to .wav file
            vad_filter: Enable VAD filter to remove silences (default: True)
                       Set to False for AMD to keep all audio
            no_speech_threshold: Probability threshold to detect silence (0.0-1.0)
                               Higher = more likely to return empty (e.g., 0.8 for AMD)
                               None = use Faster-Whisper default (0.6)
            condition_on_previous_text: Use previous text as context (default: True)
                                       Set to False for AMD to avoid hallucinations

        Returns:
            {
                "text": "transcription",
                "language": "fr",
                "duration": 1.5,
                "latency_ms": 150.0
            }
        """
        if not self.model:
            logger.error("Model not loaded!")
            return {
                "text": "",
                "language": self.language,
                "duration": 0.0,
                "latency_ms": 0.0,
                "error": "model_not_loaded"
            }

        audio_file = Path(audio_path)
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return {
                "text": "",
                "language": self.language,
                "duration": 0.0,
                "latency_ms": 0.0,
                "error": "file_not_found"
            }

        try:
            start_time = time.time()

            # Build transcribe parameters
            transcribe_params = {
                "language": self.language,
                "beam_size": self.beam_size,
                "vad_filter": vad_filter,
                "condition_on_previous_text": condition_on_previous_text
            }

            # Add no_speech_threshold if provided
            if no_speech_threshold is not None:
                transcribe_params["no_speech_threshold"] = no_speech_threshold

            # Transcribe with Faster-Whisper
            segments, info = self.model.transcribe(
                str(audio_file),
                **transcribe_params
            )

            # Concatenate segments
            text = " ".join([segment.text for segment in segments])
            text = text.strip()

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"STT: '{text[:50]}...' "
                f"(duration: {info.duration:.1f}s, latency: {latency_ms:.0f}ms)"
            )

            return {
                "text": text,
                "language": info.language,
                "duration": info.duration,
                "latency_ms": latency_ms,
                "language_probability": info.language_probability
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {
                "text": "",
                "language": self.language,
                "duration": 0.0,
                "latency_ms": 0.0,
                "error": str(e)
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return STT service stats"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": self.language,
            "beam_size": self.beam_size,
            "model_loaded": self.model is not None
        }


# Unit tests
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("Faster-Whisper STT - Unit Tests")
    print("=" * 80)

    # Init service
    try:
        stt = FasterWhisperSTT(
            model_name="base",
            device="cuda",  # Auto-fallback to CPU if no GPU
            compute_type="float16",
            language="fr",
            beam_size=1
        )

        stats = stt.get_stats()
        print(f"\nStats:")
        print(f"  - Model: {stats['model_name']}")
        print(f"  - Device: {stats['device']}")
        print(f"  - Loaded: {stats['model_loaded']}")

        print("\nSUCCESS - Model loaded!")
        print("\nNOTE: To test transcription, provide a .wav file path:")
        print("  result = stt.transcribe_file('/path/to/audio.wav')")

    except Exception as e:
        print(f"\nERROR: {e}")
        print("Make sure faster-whisper is installed:")
        print("  pip install faster-whisper")
