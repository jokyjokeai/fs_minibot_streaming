# -*- coding: utf-8 -*-
"""
Faster-Whisper STT Service - MiniBotPanel v3

GPU-optimized Speech-to-Text using Faster-Whisper
Target latency: 50-200ms (GPU batch processing)
"""

import logging
import time
import tempfile
from typing import Dict, Optional, Any
from pathlib import Path

# Noise reduction
try:
    import noisereduce as nr
    import numpy as np
    import soundfile as sf
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    nr = None
    np = None
    sf = None

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
        beam_size: int = 1,
        noise_reduce: bool = True,
        noise_reduce_strength: float = 1.0
    ):
        """
        Initialize Faster-Whisper STT

        Args:
            model_name: Model size (tiny/base/small/medium/large)
            device: "cuda" for GPU, "cpu" for CPU
            compute_type: "float16" (GPU fast) or "int8" (CPU fast)
            language: Language code (fr/en/etc)
            beam_size: Beam search size (1=fastest, 5=balanced)
            noise_reduce: Enable RNNoise-based noise reduction (default: True)
            noise_reduce_strength: Noise reduction strength 0.0-2.0 (default: 1.0)
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.noise_reduce = noise_reduce and NOISEREDUCE_AVAILABLE
        self.noise_reduce_strength = noise_reduce_strength
        self.model = None

        logger.info(
            f"FasterWhisperSTT init: "
            f"model={model_name}, device={device}, compute_type={compute_type}, "
            f"noise_reduce={self.noise_reduce}"
        )

        if noise_reduce and not NOISEREDUCE_AVAILABLE:
            logger.warning(
                "Noise reduction requested but noisereduce not installed! "
                "pip install noisereduce soundfile numpy"
            )

        # Load model
        self._load_model()

    def _apply_noise_reduction(self, audio_path: str) -> str:
        """
        Apply noise reduction to audio file using noisereduce library

        Args:
            audio_path: Path to input audio file

        Returns:
            Path to noise-reduced audio file (temp file)
        """
        if not NOISEREDUCE_AVAILABLE:
            return audio_path

        try:
            start_time = time.time()

            # Load audio
            audio_data, sample_rate = sf.read(audio_path)

            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)

            # Apply noise reduction
            # prop_decrease controls how much noise is reduced (0.0 to 1.0)
            reduced_audio = nr.reduce_noise(
                y=audio_data,
                sr=sample_rate,
                prop_decrease=min(1.0, self.noise_reduce_strength),
                stationary=False,  # Non-stationary noise (better for phone calls)
                n_fft=512,  # Smaller FFT for faster processing
                hop_length=128
            )

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                prefix="nr_"
            )
            temp_path = temp_file.name
            temp_file.close()

            sf.write(temp_path, reduced_audio, sample_rate)

            latency_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"Noise reduction applied: {audio_path} -> {temp_path} "
                f"(latency: {latency_ms:.0f}ms)"
            )

            return temp_path

        except Exception as e:
            logger.warning(f"Noise reduction failed, using original: {e}")
            return audio_path

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
        condition_on_previous_text: bool = True,
        beam_size: Optional[int] = None,
        apply_noise_reduction: Optional[bool] = None
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
            beam_size: Beam size for decoding (default: None = use model config)
                      Higher = more accurate but slower (1=fast, 3=balanced, 5=accurate)
                      Recommended: 5 for AMD to reduce hallucinations
            apply_noise_reduction: Override noise reduction setting for this call
                                  None = use default (self.noise_reduce)

        Returns:
            {
                "text": "transcription",
                "language": "fr",
                "duration": 1.5,
                "latency_ms": 150.0,
                "noise_reduced": True/False
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
            noise_reduced = False
            processed_audio_path = str(audio_file)
            temp_nr_file = None

            # Apply noise reduction if enabled
            use_noise_reduction = (
                apply_noise_reduction if apply_noise_reduction is not None
                else self.noise_reduce
            )

            if use_noise_reduction:
                temp_nr_file = self._apply_noise_reduction(str(audio_file))
                if temp_nr_file != str(audio_file):
                    processed_audio_path = temp_nr_file
                    noise_reduced = True

            # Build transcribe parameters
            transcribe_params = {
                "language": self.language,
                "beam_size": beam_size if beam_size is not None else self.beam_size,
                "vad_filter": vad_filter,
                "condition_on_previous_text": condition_on_previous_text
            }

            # Add no_speech_threshold if provided
            if no_speech_threshold is not None:
                transcribe_params["no_speech_threshold"] = no_speech_threshold

            # Transcribe with Faster-Whisper
            segments, info = self.model.transcribe(
                processed_audio_path,
                **transcribe_params
            )

            # Concatenate segments
            text = " ".join([segment.text for segment in segments])
            text = text.strip()

            latency_ms = (time.time() - start_time) * 1000

            # Cleanup temp noise-reduced file
            if temp_nr_file and temp_nr_file != str(audio_file):
                try:
                    Path(temp_nr_file).unlink()
                except:
                    pass

            logger.info(
                f"STT: '{text[:50]}...' "
                f"(duration: {info.duration:.1f}s, latency: {latency_ms:.0f}ms, "
                f"noise_reduced: {noise_reduced})"
            )

            return {
                "text": text,
                "language": info.language,
                "duration": info.duration,
                "latency_ms": latency_ms,
                "language_probability": info.language_probability,
                "noise_reduced": noise_reduced
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
            "model_loaded": self.model is not None,
            "noise_reduce": self.noise_reduce,
            "noise_reduce_strength": self.noise_reduce_strength
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
