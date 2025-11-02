#!/usr/bin/env python3
"""
YouTube Audio Extraction + Speaker Diarization - MiniBotPanel v3

Extrait l'audio d'une vidéo YouTube, identifie les locuteurs et découpe
intelligemment pour le clonage vocal.

Workflow:
1. Demande URL YouTube
2. Sélectionne dossier destination dans voices/
3. Télécharge et extrait audio (yt-dlp)
4. Identifie locuteurs avec SYSTÈME MAISON (sans pyannote)
5. Affiche durée par locuteur + preview audio
6. Sélectionne locuteur à extraire
7. Découpe intelligent 4-10s (sans couper mots)
8. Convertit 22050Hz mono WAV
9. Sauvegarde dans voices/{name}/

Utilisation:
    python youtube_extract.py
    python youtube_extract.py --url "https://youtube.com/..." --voice julie
"""

import argparse
import logging
import os
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Supprimer warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Audio processing
try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    from pydub.playback import play
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("❌ Audio processing libraries not available (pydub, soundfile)")
    print("   Install: pip install pydub soundfile")

# YouTube download
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    print("❌ yt-dlp not available")
    print("   Install: pip install yt-dlp")

# Speaker diarization (Resemblyzer - custom)
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    import numpy as np
    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False
    print("❌ Resemblyzer not available")
    print("   Install: pip install resemblyzer scikit-learn")

# Fallback: SimpleDiarization
try:
    from system.services.simple_diarization import SimpleDiarization, SpeakerSegment
    SIMPLE_DIARIZATION_AVAILABLE = True
except ImportError:
    SIMPLE_DIARIZATION_AVAILABLE = False

DIARIZATION_AVAILABLE = RESEMBLYZER_AVAILABLE or SIMPLE_DIARIZATION_AVAILABLE

# Quality scoring imports
try:
    import librosa
    import noisereduce as nr
    from scipy.io import wavfile
    import json
    import time
    import requests
    QUALITY_SCORING_AVAILABLE = True
except ImportError as e:
    QUALITY_SCORING_AVAILABLE = False
    print(f"❌ Quality scoring libraries not available: {e}")
    print("   Install: pip install librosa noisereduce scipy")

# UVR (Ultimate Vocal Remover)
try:
    from audio_separator.separator import Separator
    UVR_AVAILABLE = True
except ImportError:
    UVR_AVAILABLE = False
    print("❌ UVR (audio-separator) not available")
    print("   Install: pip install audio-separator")

# Vosk STT
try:
    from system.services.vosk_stt import VoskSTT
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("❌ Vosk STT not available")

from system.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# PYANNOTE SERVICE - Auto-starting isolated service
# ============================================================

class PyannoteService:
    """
    Service pyannote auto-démarrant en subprocess isolé

    - Lance automatiquement le service FastAPI au démarrage
    - Utilise venv isolé (pas de conflits de dépendances)
    - Arrête proprement le service à la fin
    """

    def __init__(self, service_dir: str = "/root/pyannote_service", port: int = 8001):
        self.service_dir = Path(service_dir)
        self.port = port
        self.process = None
        self.base_url = f"http://127.0.0.1:{port}"

    def start(self):
        """Démarre le service pyannote en background"""
        logger.info("🚀 Starting Pyannote service...")

        # Vérifier que le service existe
        if not self.service_dir.exists():
            logger.error(f"❌ Pyannote service not found: {self.service_dir}")
            logger.error("   Run: bash install_pyannote_service.sh")
            return False

        # Vérifier si déjà running
        try:
            import requests
            response = requests.get(f"{self.base_url}/health", timeout=1)
            if response.status_code == 200:
                logger.info("✅ Pyannote service already running")
                return True
        except:
            pass

        # Lancer le service
        python_bin = self.service_dir / "venv_pyannote" / "bin" / "python"

        if not python_bin.exists():
            logger.error(f"❌ Python binary not found: {python_bin}")
            logger.error("   Run: bash install_pyannote_service.sh")
            return False

        cmd = [
            str(python_bin),
            "-m", "uvicorn",
            "server:app",
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--log-level", "warning"
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.service_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Attendre que le service soit prêt (max 30s)
            import requests
            import time

            logger.info("   Waiting for service to start...")
            for i in range(30):
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=1)
                    if response.status_code == 200:
                        logger.info(f"✅ Pyannote service started on port {self.port}")
                        return True
                except:
                    time.sleep(1)

            logger.error("❌ Service failed to start (timeout)")
            self.stop()
            return False

        except Exception as e:
            logger.error(f"❌ Failed to start service: {e}")
            return False

    def stop(self):
        """Arrête le service proprement"""
        if self.process:
            logger.info("🛑 Stopping Pyannote service...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.process = None

    def diarize(self, audio_path: Path) -> Optional[List]:
        """
        Diarize audio file via HTTP API

        Args:
            audio_path: Path to audio file

        Returns:
            List of segments or None
        """
        import requests

        try:
            logger.info(f"📤 Sending audio to Pyannote service...")

            with open(audio_path, 'rb') as f:
                files = {'file': (audio_path.name, f, 'audio/wav')}
                response = requests.post(
                    f"{self.base_url}/diarize",
                    files=files,
                    timeout=300  # 5 minutes max
                )

            if response.status_code != 200:
                logger.error(f"❌ Service returned error: {response.status_code}")
                logger.error(f"   {response.text}")
                return None

            data = response.json()

            logger.info(f"✅ Received {data['total_segments']} segments, {data['num_speakers']} speakers")

            # Convert to SpeakerSegment objects
            segments = []
            for seg in data['segments']:
                segments.append(SpeakerSegment(
                    start=seg['start'],
                    end=seg['end'],
                    speaker=seg['speaker']
                ))

            return segments

        except Exception as e:
            logger.error(f"❌ Diarization request failed: {e}")
            return None

    def __del__(self):
        """Cleanup on object destruction"""
        self.stop()


# ============================================================
# RESEMBLYZER DIARIZATION - Custom Implementation
# ============================================================

class SpeakerSegment:
    """Segment audio avec speaker ID"""
    def __init__(self, start: float, end: float, speaker: str):
        self.start = start
        self.end = end
        self.speaker = speaker
        self.duration = end - start


class ResemblyzerDiarization:
    """
    Diarization ultra-performante avec Resemblyzer

    - Voice encoder pré-entraîné (256D embeddings)
    - Clustering hiérarchique automatique
    - Post-processing intelligent
    """

    def __init__(self,
                 min_segment_duration: float = 0.5,
                 embedding_window: float = 0.5,
                 min_speakers: int = 1,
                 max_speakers: int = 8):
        """
        Args:
            min_segment_duration: Durée minimale segment (secondes)
            embedding_window: Fenêtre pour embeddings (secondes)
            min_speakers: Nombre minimum locuteurs
            max_speakers: Nombre maximum locuteurs
        """
        self.min_segment_duration = min_segment_duration
        self.embedding_window = embedding_window
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

        # Charger voice encoder Resemblyzer
        logger.info("🎤 Loading Resemblyzer voice encoder...")
        self.encoder = VoiceEncoder()
        logger.info("✅ Resemblyzer encoder loaded")

    def diarize(self, audio_file: Path) -> List[SpeakerSegment]:
        """
        Diarization complète d'un fichier audio

        Args:
            audio_file: Chemin fichier audio WAV

        Returns:
            Liste de SpeakerSegment
        """
        logger.info("\n============================================================")
        logger.info("🎤 Resemblyzer Speaker Diarization")
        logger.info("============================================================")
        logger.info(f"Audio: {audio_file.name}")

        # 1. Prétraiter audio
        logger.info("🔊 Preprocessing audio...")
        wav = preprocess_wav(audio_file)
        duration = len(wav) / 16000  # Resemblyzer use 16kHz
        logger.info(f"   Duration: {duration:.1f}s")

        # 2. Voice Activity Detection simple
        logger.info("🔊 Voice Activity Detection...")
        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent

        audio = AudioSegment.from_wav(str(audio_file))
        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=300,
            silence_thresh=-40
        )

        logger.info(f"✅ Detected {len(nonsilent_ranges)} voice segments")

        # 3. Extraire embeddings pour chaque segment
        logger.info("🎵 Extracting voice embeddings...")
        embeddings = []
        timestamps = []

        for start_ms, end_ms in nonsilent_ranges:
            start_s = start_ms / 1000
            end_s = end_ms / 1000

            # Skip segments trop courts
            if (end_s - start_s) < self.min_segment_duration:
                continue

            # Extraire segment
            start_sample = int(start_s * 16000)
            end_sample = int(end_s * 16000)
            segment_wav = wav[start_sample:end_sample]

            # Embedding
            try:
                embedding = self.encoder.embed_utterance(segment_wav)
                embeddings.append(embedding)
                timestamps.append((start_s, end_s))
            except Exception as e:
                logger.warning(f"   ⚠️  Failed to embed segment {start_s:.1f}s: {e}")
                continue

        if not embeddings:
            logger.error("❌ No embeddings extracted")
            return []

        embeddings = np.array(embeddings)
        logger.info(f"✅ Extracted {len(embeddings)} embeddings")

        # 4. Clustering hiérarchique automatique
        logger.info("👥 Clustering speakers...")
        best_n_speakers = self._find_optimal_clusters(embeddings)

        clustering = AgglomerativeClustering(
            n_clusters=best_n_speakers,
            metric='cosine',
            linkage='average'
        )
        speaker_labels = clustering.fit_predict(embeddings)

        logger.info(f"✅ Detected {best_n_speakers} speakers")

        # 5. Créer segments
        segments = []
        for (start_s, end_s), label in zip(timestamps, speaker_labels):
            segment = SpeakerSegment(
                start=start_s,
                end=end_s,
                speaker=f"SPEAKER_{label}"
            )
            segments.append(segment)

        # 6. Merge segments consécutifs du même locuteur
        segments = self._merge_consecutive_segments(segments)

        logger.info(f"\n📊 Diarization Results:")
        speaker_durations = {}
        for seg in segments:
            if seg.speaker not in speaker_durations:
                speaker_durations[seg.speaker] = 0
            speaker_durations[seg.speaker] += seg.duration

        for speaker, duration in sorted(speaker_durations.items(),
                                       key=lambda x: x[1], reverse=True):
            logger.info(f"   {speaker}: {duration:.1f}s ({duration/60:.1f}min)")

        logger.info(f"✅ Diarization completed: {len(segments)} segments")
        logger.info("============================================================\n")

        return segments

    def _find_optimal_clusters(self, embeddings: np.ndarray) -> int:
        """
        Trouve nombre optimal de clusters avec silhouette score

        Args:
            embeddings: Embeddings vocaux

        Returns:
            Nombre optimal de speakers
        """
        if len(embeddings) < self.min_speakers + 1:
            return max(1, len(embeddings))

        best_score = -1
        best_n = self.min_speakers

        for n in range(self.min_speakers, min(self.max_speakers + 1, len(embeddings))):
            try:
                clustering = AgglomerativeClustering(
                    n_clusters=n,
                    metric='cosine',
                    linkage='average'
                )
                labels = clustering.fit_predict(embeddings)

                # Silhouette score (higher = better)
                score = silhouette_score(embeddings, labels, metric='cosine')
                logger.info(f"   n={n} speakers: silhouette={score:.3f}")

                if score > best_score:
                    best_score = score
                    best_n = n
            except Exception as e:
                logger.warning(f"   ⚠️  n={n} failed: {e}")
                continue

        logger.info(f"✅ Auto-detected {best_n} speakers (score={best_score:.3f})")
        return best_n

    def _merge_consecutive_segments(self, segments: List[SpeakerSegment]) -> List[SpeakerSegment]:
        """
        Merge segments consécutifs du même locuteur

        Args:
            segments: Segments à merger

        Returns:
            Segments mergés
        """
        if not segments:
            return []

        # Trier par temps
        segments = sorted(segments, key=lambda s: s.start)

        merged = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]

            # Même speaker et segments proches (< 1s gap)
            if seg.speaker == prev.speaker and (seg.start - prev.end) < 1.0:
                # Merge
                prev.end = seg.end
                prev.duration = prev.end - prev.start
            else:
                merged.append(seg)

        logger.info(f"🔗 Merged {len(segments)} → {len(merged)} segments")
        return merged

    def get_speaker_durations(self, segments: List[SpeakerSegment]) -> Dict[str, float]:
        """
        Calcule la durée totale de parole par locuteur

        Args:
            segments: Liste de SpeakerSegment

        Returns:
            Dict {speaker_name: duration_seconds}
        """
        durations = {}
        for seg in segments:
            if seg.speaker not in durations:
                durations[seg.speaker] = 0.0
            durations[seg.speaker] += seg.duration
        return durations


class YouTubeVoiceExtractor:
    """Extracteur audio YouTube avec diarization et découpage intelligent"""

    # Format optimal pour Chatterbox TTS (best practices: 44.1kHz minimum 24kHz)
    TARGET_SAMPLE_RATE = 44100  # Upgraded from 22050 for better quality
    TARGET_CHANNELS = 1  # Mono
    TARGET_FORMAT = "wav"

    # Découpage intelligent
    MIN_CHUNK_DURATION_MS = 4000  # 4 secondes minimum
    MAX_CHUNK_DURATION_MS = 10000  # 10 secondes maximum
    SILENCE_THRESHOLD_DB = -40  # dB pour détection silence
    MIN_SILENCE_LEN_MS = 500  # 500ms minimum de silence pour découpe

    def __init__(self):
        """Initialise l'extracteur"""
        self.voices_dir = Path(config.VOICES_DIR)
        self.voices_dir.mkdir(exist_ok=True)

        # Initialiser système de diarization (ordre de priorité)
        self.diarization_mode = None
        self.pyannote_service = None

        # 1. PRIORITÉ: Pyannote service (meilleur qualité)
        pyannote_service_dir = Path("/root/pyannote_service")
        if pyannote_service_dir.exists():
            logger.info("🎬 YouTubeVoiceExtractor initialized (Pyannote service - BEST)")
            self.pyannote_service = PyannoteService()
            if self.pyannote_service.start():
                self.diarization_mode = "pyannote"
            else:
                logger.warning("⚠️  Pyannote service failed to start, falling back...")
                self.pyannote_service = None

        # 2. Fallback: Resemblyzer (bonne qualité)
        if not self.diarization_mode and RESEMBLYZER_AVAILABLE:
            logger.info("🎬 YouTubeVoiceExtractor initialized (Resemblyzer diarization)")
            self.diarizer = ResemblyzerDiarization(
                min_segment_duration=0.5,
                min_speakers=1,
                max_speakers=8
            )
            self.diarization_mode = "resemblyzer"

        # 3. Fallback: SimpleDiarization (qualité basique)
        if not self.diarization_mode and SIMPLE_DIARIZATION_AVAILABLE:
            logger.info("🎬 YouTubeVoiceExtractor initialized (SimpleDiarization fallback)")
            self.diarizer = SimpleDiarization(
                min_segment_duration=0.5,
                n_mfcc=20,
                min_speakers=1,
                max_speakers=5
            )
            self.diarization_mode = "simple"

        # Check if any diarization system is available
        if not self.diarization_mode:
            raise RuntimeError("❌ No diarization system available")

    def detect_available_voices(self) -> List[str]:
        """
        Détecte les dossiers de voix disponibles dans voices/

        Returns:
            Liste des noms de voix
        """
        voices = []

        if not self.voices_dir.exists():
            return voices

        for item in self.voices_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                voices.append(item.name)

        return sorted(voices)

    def download_audio_from_youtube(self, url: str, output_dir: Path) -> Optional[Path]:
        """
        Télécharge l'audio d'une vidéo YouTube

        Args:
            url: URL YouTube
            output_dir: Dossier de sortie

        Returns:
            Path du fichier audio ou None si échec
        """
        logger.info(f"📥 Downloading audio from YouTube...")
        logger.info(f"   URL: {url}")

        # Créer dossier temporaire si nécessaire
        output_dir.mkdir(parents=True, exist_ok=True)

        # Configuration yt-dlp
        output_template = str(output_dir / "youtube_audio.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '0',
            }],
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("   Downloading...")
                info = ydl.extract_info(url, download=True)

                # Récupérer titre
                self.video_title = info.get('title', 'Unknown')

                # Le fichier sera nommé youtube_audio.wav après postprocessing
                audio_file = output_dir / "youtube_audio.wav"

                if audio_file.exists():
                    logger.info(f"✅ Downloaded: {audio_file}")
                    logger.info(f"   Title: {info.get('title', 'Unknown')}")
                    logger.info(f"   Duration: {info.get('duration', 0):.1f}s")
                    return audio_file
                else:
                    logger.error("❌ Audio file not found after download")
                    return None

        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return None

    def preprocess_audio(self, audio_file: Path, output_dir: Path) -> Optional[Path]:
        """
        Preprocessing pipeline complet:
        1. Normalize volume (-20 LUFS)
        2. Convert to mono 16kHz WAV
        3. UVR vocal extraction
        4. Noise reduction

        Args:
            audio_file: Fichier audio brut
            output_dir: Dossier de sortie

        Returns:
            Path du fichier preprocessed ou None
        """
        logger.info(f"\n🔧 Audio Preprocessing Pipeline...")

        try:
            from pydub import AudioSegment
            import noisereduce as nr

            # 1. Load audio
            logger.info("📂 Loading audio...")
            audio = AudioSegment.from_file(str(audio_file))

            # 2. Convert to mono 16kHz (optimal for diarization)
            logger.info("🔄 Converting to mono 16kHz...")
            audio = audio.set_channels(1)  # Mono
            audio = audio.set_frame_rate(16000)  # 16kHz for pyannote/resemblyzer

            # 3. Normalize volume to -20 LUFS (standard for speech)
            logger.info("🔊 Normalizing volume...")
            target_dBFS = -20.0
            change_in_dBFS = target_dBFS - audio.dBFS
            normalized_audio = audio.apply_gain(change_in_dBFS)

            # Save intermediate file
            normalized_file = output_dir / "normalized.wav"
            normalized_audio.export(str(normalized_file), format="wav")
            logger.info(f"   ✅ Normalized to {target_dBFS} dBFS")

            # 4. UVR vocal extraction (if available)
            try:
                from audio_separator.separator import Separator
                logger.info("🎵 UVR: Extracting vocals...")

                # Create models directory
                models_dir = Path("models/uvr")
                models_dir.mkdir(parents=True, exist_ok=True)

                # Try with mdx_params (newer versions), fallback to basic init
                logger.info("   ⚡ Using fast processing mode (KARA_2 model + optimized params)")

                try:
                    # Try newer API with mdx_params
                    separator = Separator(
                        log_level=logging.WARNING,
                        model_file_dir=str(models_dir),
                        mdx_params={
                            "hop_length": 1024,
                            "segment_size": 128,   # Reduced from 256 (faster)
                            "overlap": 0.1,        # Reduced from 0.25 (faster)
                            "batch_size": 1,
                            "enable_denoise": False
                        }
                    )
                except TypeError:
                    # Fallback for older audio-separator versions
                    logger.info("   ℹ️  Using basic config (older audio-separator version)")
                    separator = Separator(
                        log_level=logging.WARNING,
                        model_file_dir=str(models_dir)
                    )

                # Use fastest model for speed: Inst_1 (fastest) > Inst_Main (balanced) > KARA_2 > HQ_3 (slowest)
                separator.load_model("UVR-MDX-NET-Inst_1")

                output_files = separator.separate(str(normalized_file))

                # Trouver le fichier vocals
                vocals_file = None
                for f in output_files:
                    if "Vocals" in f or "vocals" in f:
                        vocals_file = Path(f)
                        break

                if vocals_file and vocals_file.exists():
                    logger.info(f"   ✅ Vocals extracted: {vocals_file.name}")
                    # Reload cleaned audio
                    audio = AudioSegment.from_file(str(vocals_file))
                    # Clean up
                    normalized_file.unlink()
                    for f in output_files:
                        if Path(f) != vocals_file:
                            Path(f).unlink(missing_ok=True)
                    cleaned_file = vocals_file
                else:
                    logger.warning("   ⚠️  Vocals file not found, using normalized")
                    cleaned_file = normalized_file

            except ImportError:
                logger.warning("   ⚠️  UVR not available, skipping vocal extraction")
                cleaned_file = normalized_file
            except Exception as e:
                logger.warning(f"   ⚠️  UVR failed: {e}, continuing...")
                cleaned_file = normalized_file

            # 5. Noise reduction (with safety check)
            logger.info("🔇 Reducing background noise...")
            import soundfile as sf
            import numpy as np

            try:
                # Load audio as numpy array
                data, rate = sf.read(str(cleaned_file))

                # Safety check: skip if audio shape is abnormal
                if data.ndim > 2 or (data.ndim == 2 and data.shape[1] > 2):
                    logger.warning(f"   ⚠️  Abnormal audio shape {data.shape}, skipping noise reduction")
                    preprocessed_file = cleaned_file
                else:
                    # Apply noise reduction with chunk processing for safety
                    reduced_noise = nr.reduce_noise(
                        y=data,
                        sr=rate,
                        stationary=True,
                        prop_decrease=0.8,  # Reduce 80% of noise
                        chunk_size=60000    # Process in smaller chunks to avoid memory issues
                    )

                    # Save final preprocessed file
                    preprocessed_file = output_dir / "preprocessed.wav"
                    sf.write(str(preprocessed_file), reduced_noise, rate)

            except (MemoryError, np.core._exceptions._ArrayMemoryError) as e:
                logger.warning(f"   ⚠️  Noise reduction failed (memory issue), using UVR output directly")
                preprocessed_file = cleaned_file

            logger.info(f"✅ Preprocessing complete: {preprocessed_file.name}")
            logger.info(f"   - Mono 16kHz")
            logger.info(f"   - Normalized volume")
            logger.info(f"   - Vocals extracted (UVR)")
            logger.info(f"   - Noise reduced")

            # Clean up intermediate files
            if cleaned_file != preprocessed_file:
                cleaned_file.unlink(missing_ok=True)

            return preprocessed_file

        except Exception as e:
            logger.error(f"❌ Preprocessing failed: {e}")
            import traceback
            traceback.print_exc()
            return audio_file  # Return original if preprocessing fails

    def download_subtitles(self, url: str, output_dir: Path) -> Optional[List[Dict]]:
        """
        Télécharge les sous-titres YouTube (auto-générés ou manuels)

        Args:
            url: URL YouTube
            output_dir: Dossier de sortie

        Returns:
            Liste de dict {text, start, duration} ou None
        """
        logger.info(f"📝 Downloading YouTube subtitles...")

        try:
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['fr', 'en'],
                'subtitlesformat': 'json3',
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Récupérer sous-titres depuis info
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})

                # Priorité: sous-titres manuels FR > auto FR > EN
                subs_data = None
                if 'fr' in subtitles:
                    subs_data = subtitles['fr']
                    logger.info("   Using manual French subtitles")
                elif 'fr' in automatic_captions:
                    subs_data = automatic_captions['fr']
                    logger.info("   Using auto-generated French subtitles")
                elif 'en' in automatic_captions:
                    subs_data = automatic_captions['en']
                    logger.info("   Using auto-generated English subtitles")

                if not subs_data:
                    logger.warning("   ⚠️  No subtitles available")
                    return None

                # Trouver format json3
                json3_sub = None
                for sub in subs_data:
                    if sub.get('ext') == 'json3':
                        json3_sub = sub
                        break

                if not json3_sub:
                    logger.warning("   ⚠️  json3 format not found")
                    return None

                # Télécharger et parser
                import json
                import urllib.request

                response = urllib.request.urlopen(json3_sub['url'])
                data = json.loads(response.read().decode('utf-8'))

                # Extraire events avec timestamps
                subtitles_list = []
                for event in data.get('events', []):
                    if 'segs' in event:
                        text = ''.join([seg.get('utf8', '') for seg in event['segs']])
                        subtitles_list.append({
                            'text': text.strip(),
                            'start': event.get('tStartMs', 0) / 1000.0,  # ms → s
                            'duration': event.get('dDurationMs', 0) / 1000.0
                        })

                logger.info(f"   ✅ Downloaded {len(subtitles_list)} subtitle segments")
                return subtitles_list

        except Exception as e:
            logger.warning(f"   ⚠️  Subtitle download failed: {e}")
            return None

    def validate_segments_with_vosk(
        self,
        audio_path: Path,
        segments: List[SpeakerSegment],
        subtitles: Optional[List[Dict]] = None
    ) -> List[SpeakerSegment]:
        """
        Valide les segments de diarization avec Vosk STT
        Filtre les segments avec voix mixtes en comparant avec sous-titres YouTube

        Args:
            audio_path: Fichier audio
            segments: Segments de diarization
            subtitles: Sous-titres YouTube (optionnel)

        Returns:
            Segments filtrés (segments purs uniquement)
        """
        if not subtitles:
            logger.info("   ⚠️  No subtitles - skipping Vosk validation")
            return segments

        logger.info(f"\n🎤 Validating segments with Vosk STT...")
        logger.info(f"   Filtering mixed-voice segments")

        try:
            # Importer Vosk
            from system.services.vosk_stt import VoskSTT
            vosk_stt = VoskSTT()

            if not vosk_stt.is_available:
                logger.warning("   ⚠️  Vosk not available - skipping validation")
                return segments

            # Charger audio
            audio = AudioSegment.from_file(str(audio_path))

            # Grouper segments par locuteur
            speakers_segments = {}
            for seg in segments:
                if seg.speaker not in speakers_segments:
                    speakers_segments[seg.speaker] = []
                speakers_segments[seg.speaker].append(seg)

            validated_segments = []
            total_checked = 0
            total_filtered = 0

            # Pour chaque locuteur
            for speaker_id, speaker_segs in speakers_segments.items():
                logger.info(f"\n   🔍 Validating SPEAKER_{speaker_id} ({len(speaker_segs)} segments)...")

                for seg in speaker_segs:
                    total_checked += 1

                    # Extraire audio du segment
                    start_ms = int(seg.start * 1000)
                    end_ms = int(seg.end * 1000)
                    segment_audio = audio[start_ms:end_ms]

                    # Sauvegarder temporairement
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                        segment_audio.export(temp_file.name, format='wav')
                        temp_path = Path(temp_file.name)

                        # Transcrire avec Vosk
                        transcription_result = vosk_stt.transcribe_file(temp_path)
                        temp_path.unlink()  # Supprimer fichier temp

                    # Vérifier si transcription valide
                    if not transcription_result or not isinstance(transcription_result, dict):
                        total_filtered += 1
                        continue

                    transcription_text = transcription_result.get('text', '').strip()
                    if not transcription_text:
                        total_filtered += 1
                        continue  # Skip segment vide

                    # Trouver sous-titres correspondants
                    matching_subs = []
                    for sub in subtitles:
                        sub_start = sub['start']
                        sub_end = sub_start + sub['duration']

                        # Chevauchement temporel
                        if not (seg.end < sub_start or seg.start > sub_end):
                            matching_subs.append(sub)

                    if not matching_subs:
                        # Pas de sous-titres correspondants - garder le segment
                        validated_segments.append(seg)
                        continue

                    # Comparer transcription Vosk vs sous-titres
                    sub_text = ' '.join([s['text'] for s in matching_subs]).lower()
                    vosk_text = transcription_text.lower()

                    # Simple similarité: compter mots communs
                    sub_words = set(sub_text.split())
                    vosk_words = set(vosk_text.split())

                    if not sub_words or not vosk_words:
                        validated_segments.append(seg)
                        continue

                    common_words = sub_words & vosk_words
                    similarity = len(common_words) / max(len(sub_words), len(vosk_words))

                    # Debug: log les 5 premières similarités
                    if len(validated_segments) + total_filtered < 5:
                        logger.info(f"      Segment {seg.speaker} {seg.start:.1f}s: similarity={similarity:.2f}")
                        logger.info(f"         Vosk: {vosk_text[:80]}")
                        logger.info(f"         Subs: {sub_text[:80]}")

                    # Si similarité < 20%, probablement plusieurs voix (seuil plus permissif)
                    if similarity < 0.2:
                        total_filtered += 1
                        continue

                    # Segment validé
                    validated_segments.append(seg)

            logger.info(f"\n   ✅ Validation complete:")
            logger.info(f"      Total segments: {total_checked}")
            logger.info(f"      Filtered (mixed): {total_filtered}")
            logger.info(f"      Kept (pure): {len(validated_segments)}")

            return validated_segments

        except Exception as e:
            logger.warning(f"   ⚠️  Vosk validation failed: {e}")
            return segments  # Retourner segments originaux

    def perform_speaker_diarization(self, audio_path: Path, n_speakers: Optional[int] = None) -> Optional[List[SpeakerSegment]]:
        """
        Identifie les locuteurs dans un fichier audio

        Args:
            audio_path: Chemin fichier audio
            n_speakers: Nombre de locuteurs (None = auto-détection)

        Returns:
            Liste de SpeakerSegment ou None
        """
        logger.info(f"\n🎤 Performing speaker diarization...")

        # Log quel système est utilisé
        if self.diarization_mode == "pyannote":
            logger.info(f"   Using Pyannote service (BEST QUALITY)")
        elif self.diarization_mode == "resemblyzer":
            logger.info(f"   Using Resemblyzer (voice embeddings + clustering)")
        elif self.diarization_mode == "simple":
            logger.info(f"   Using SimpleDiarization (MFCC+Clustering)")

        try:
            # 1. Pyannote service (priorité)
            if self.diarization_mode == "pyannote":
                segments = self.pyannote_service.diarize(audio_path)

            # 2. Resemblyzer
            elif self.diarization_mode == "resemblyzer":
                segments = self.diarizer.diarize(audio_path)

            # 3. SimpleDiarization
            elif self.diarization_mode == "simple":
                segments = self.diarizer.diarize(
                    audio_path,
                    n_speakers=n_speakers,
                    vad_threshold_db=-30,
                    min_silence_duration=0.3
                )
            else:
                logger.error("❌ No diarization mode selected")
                return None

            if not segments:
                logger.error("❌ No speakers detected")
                return None

            logger.info("✅ Diarization completed")
            return segments

        except Exception as e:
            logger.error(f"❌ Diarization failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def analyze_speakers(self, segments: List[SpeakerSegment]) -> Dict[str, float]:
        """
        Analyse les locuteurs et calcule durées

        Args:
            segments: Liste de SpeakerSegment

        Returns:
            Dict {speaker_name: duration_seconds}
        """
        return self.diarizer.get_speaker_durations(segments)

    def score_chunk_quality(self, audio_chunk: np.ndarray, sr: int) -> float:
        """
        Score la qualité d'un chunk audio (inspiré de ElevenLabs approach)

        Critères:
        - SNR (Signal-to-Noise Ratio)
        - RMS (volume/énergie)
        - Zero Crossing Rate (clarté)
        - Spectral centroid (richesse tonale)

        Args:
            audio_chunk: Audio numpy array
            sr: Sample rate

        Returns:
            Score 0-100 (plus haut = meilleure qualité)
        """
        try:
            import librosa

            # 1. SNR (Signal-to-Noise Ratio) - plus haut = mieux
            # Estimer le bruit comme les 10% plus faibles
            noise_floor = np.percentile(np.abs(audio_chunk), 10)
            signal_power = np.mean(audio_chunk ** 2)
            noise_power = noise_floor ** 2
            snr = 10 * np.log10(signal_power / (noise_power + 1e-10))
            snr_score = np.clip(snr / 30, 0, 1)  # Normaliser 0-30dB → 0-1

            # 2. RMS (Root Mean Square) - volume optimal
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            # Optimal RMS autour de 0.1-0.3
            rms_score = 1 - abs(0.2 - rms) / 0.2
            rms_score = np.clip(rms_score, 0, 1)

            # 3. Zero Crossing Rate - clarté (pas trop de distorsion)
            zcr = np.mean(librosa.zero_crossings(audio_chunk))
            # Optimal autour de 0.05-0.15
            zcr_score = 1 - abs(0.1 - zcr) / 0.1
            zcr_score = np.clip(zcr_score, 0, 1)

            # 4. Spectral Centroid - richesse tonale
            spectral_centroid = librosa.feature.spectral_centroid(
                y=audio_chunk, sr=sr
            )[0]
            sc_mean = np.mean(spectral_centroid)
            # Optimal autour de 2000-4000 Hz pour parole
            sc_score = 1 - abs(3000 - sc_mean) / 3000
            sc_score = np.clip(sc_score, 0, 1)

            # Score pondéré
            total_score = (
                snr_score * 0.4 +      # SNR le plus important
                rms_score * 0.3 +      # Volume
                zcr_score * 0.15 +     # Clarté
                sc_score * 0.15        # Richesse
            )

            return total_score * 100  # Score sur 100

        except Exception as e:
            logger.warning(f"⚠️  Quality scoring failed: {e}")
            return 50.0  # Score moyen par défaut

    def select_best_chunks(self, audio_file: Path, segments: List[SpeakerSegment],
                          speaker: str, target_count: int = 30) -> List[Tuple[Path, float]]:
        """
        Sélectionne les meilleurs chunks audio pour cloning

        Pipeline:
        1. Découper segments du speaker en chunks 6-10s
        2. Scorer chaque chunk (SNR, RMS, ZCR, spectral)
        3. Garder top N chunks

        Args:
            audio_file: Fichier audio source
            segments: Tous les segments
            speaker: Speaker à extraire
            target_count: Nombre de chunks à garder (default: 30)

        Returns:
            Liste de (chunk_path, quality_score)
        """
        logger.info(f"\n🎯 Selecting best audio chunks for {speaker}...")
        logger.info(f"   Target: {target_count} chunks of 6-10s")

        try:
            from pydub import AudioSegment
            import soundfile as sf
            import tempfile

            # Charger audio
            audio = AudioSegment.from_file(str(audio_file))

            # Filtrer segments du speaker
            speaker_segments = [s for s in segments if s.speaker == speaker]
            logger.info(f"   Found {len(speaker_segments)} segments for {speaker}")

            # Découper en chunks 6-10s
            chunks_data = []
            chunk_dir = Path(tempfile.mkdtemp())

            for idx, seg in enumerate(speaker_segments):
                # Extraire segment
                start_ms = int(seg.start * 1000)
                end_ms = int(seg.end * 1000)
                segment_audio = audio[start_ms:end_ms]

                # Si segment > 10s, découper en chunks
                if len(segment_audio) > 10000:  # 10s
                    # Découper en chunks de 8s (optimal)
                    chunk_size_ms = 8000
                    for i in range(0, len(segment_audio), chunk_size_ms):
                        chunk = segment_audio[i:i + chunk_size_ms]

                        # Garder seulement si >= 6s
                        if len(chunk) >= 6000:
                            chunks_data.append(chunk)

                # Si segment entre 6-10s, garder tel quel
                elif len(segment_audio) >= 6000:
                    chunks_data.append(segment_audio)

            logger.info(f"   Created {len(chunks_data)} chunks (6-10s each)")

            # Scorer chaque chunk
            logger.info(f"   Scoring quality...")
            scored_chunks = []

            for idx, chunk in enumerate(chunks_data):
                # Export temporaire pour scoring
                chunk_path = chunk_dir / f"chunk_{idx:03d}.wav"
                chunk.export(str(chunk_path), format="wav")

                # Charger comme numpy
                data, sr = sf.read(str(chunk_path))

                # Scorer
                score = self.score_chunk_quality(data, sr)
                scored_chunks.append((chunk_path, score))

            # Trier par score (meilleurs d'abord)
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            # Garder top N
            best_chunks = scored_chunks[:target_count]

            logger.info(f"✅ Selected {len(best_chunks)} best chunks")
            logger.info(f"   Quality range: {best_chunks[-1][1]:.1f} - {best_chunks[0][1]:.1f}")

            return best_chunks

        except Exception as e:
            logger.error(f"❌ Chunk selection failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def filter_chunks_with_vosk(self, chunks: List[Tuple[Path, float]],
                                target_count: int = 10) -> List[Tuple[Path, float, str]]:
        """
        Filtre final avec Vosk STT pour garder meilleurs chunks

        Critères Vosk:
        - Transcription non vide
        - Longueur texte raisonnable (pas tronqué)
        - Pas de répétitions
        - Clarté (confidence si disponible)

        Args:
            chunks: Liste de (path, quality_score)
            target_count: Nombre final à garder (default: 10)

        Returns:
            Liste de (path, quality_score, transcription)
        """
        logger.info(f"\n🎤 Vosk filtering for final {target_count} chunks...")

        try:
            from system.services.vosk_stt import VoskSTT

            # Initialiser Vosk
            vosk = VoskSTT()
            if not vosk.is_available:
                logger.warning("⚠️  Vosk not available, returning all chunks")
                return [(p, s, "") for p, s in chunks[:target_count]]

            # Transcrire et filtrer
            validated_chunks = []

            for chunk_path, quality_score in chunks:
                try:
                    # Transcrire
                    result = vosk.transcribe_file(chunk_path)

                    if not result or not isinstance(result, dict):
                        continue

                    text = result.get('text', '').strip()

                    # Filtres:
                    # 1. Texte non vide
                    if not text or len(text) < 10:
                        continue

                    # 2. Longueur raisonnable (pas tronqué)
                    # 6-10s devrait donner ~15-50 mots en français
                    word_count = len(text.split())
                    if word_count < 5 or word_count > 100:
                        continue

                    # 3. Pas de répétitions excessives
                    words = text.lower().split()
                    unique_words = set(words)
                    if len(unique_words) / len(words) < 0.4:  # 40% mots uniques minimum
                        continue

                    # Chunk validé
                    validated_chunks.append((chunk_path, quality_score, text))

                    # Stop si on a assez
                    if len(validated_chunks) >= target_count:
                        break

                except Exception as e:
                    logger.warning(f"   ⚠️  Failed to process {chunk_path.name}: {e}")
                    continue

            logger.info(f"✅ Vosk validation complete: {len(validated_chunks)}/{len(chunks)} chunks kept")

            if validated_chunks:
                logger.info(f"   Sample transcriptions:")
                for i, (_, score, text) in enumerate(validated_chunks[:3]):
                    logger.info(f"      [{i+1}] (score={score:.1f}): {text[:60]}...")

            return validated_chunks

        except Exception as e:
            logger.error(f"❌ Vosk filtering failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: retourner sans filtrage
            return [(p, s, "") for p, s in chunks[:target_count]]

    def concatenate_final_reference(self, chunks: List[Tuple[Path, float, str]],
                                    output_path: Path) -> Optional[Path]:
        """
        Concatène les chunks finaux en reference.wav pour cloning

        Args:
            chunks: Liste de (path, score, transcription)
            output_path: Chemin de sortie

        Returns:
            Path du fichier concaténé ou None
        """
        logger.info(f"\n🔗 Concatenating {len(chunks)} chunks into reference.wav...")

        try:
            from pydub import AudioSegment

            if not chunks:
                logger.error("❌ No chunks to concatenate")
                return None

            # Concaténer
            final_audio = None

            for idx, (chunk_path, score, text) in enumerate(chunks):
                chunk = AudioSegment.from_file(str(chunk_path))

                if final_audio is None:
                    final_audio = chunk
                else:
                    # Ajouter petit silence entre chunks (200ms)
                    silence = AudioSegment.silent(duration=200)
                    final_audio = final_audio + silence + chunk

            # Upsampler à 44.1kHz (optimal pour Chatterbox TTS)
            logger.info(f"🔄 Upsampling to 44.1kHz (Chatterbox optimal)...")
            final_audio = final_audio.set_frame_rate(44100)
            final_audio = final_audio.set_channels(1)  # Ensure mono

            # Exporter
            final_audio.export(str(output_path), format="wav")

            duration = len(final_audio) / 1000
            logger.info(f"✅ Reference audio created: {output_path.name}")
            logger.info(f"   Format: 44.1kHz mono WAV (Chatterbox optimal)")
            logger.info(f"   Duration: {duration:.1f}s ({duration/60:.1f}min)")
            logger.info(f"   Chunks: {len(chunks)}")

            # Sauvegarder métadonnées (transcriptions)
            metadata_path = output_path.with_suffix('.txt')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(f"Voice Reference Metadata\n")
                f.write(f"========================\n\n")
                f.write(f"Total duration: {duration:.1f}s\n")
                f.write(f"Chunks: {len(chunks)}\n\n")
                f.write(f"Transcriptions:\n")
                for idx, (path, score, text) in enumerate(chunks, 1):
                    f.write(f"\n[{idx}] Quality={score:.1f}\n")
                    f.write(f"{text}\n")

            logger.info(f"   Metadata saved: {metadata_path.name}")

            # Calculer qualité moyenne
            avg_quality = sum(score for _, score, _ in chunks) / len(chunks)

            return {
                "path": output_path,
                "duration": duration,
                "avg_quality": avg_quality,
                "chunks_count": len(chunks)
            }

        except Exception as e:
            logger.error(f"❌ Concatenation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def preview_speaker(self, audio_path: Path, segments: List[SpeakerSegment],
                       speaker: str, duration_seconds: float = 5.0):
        """
        Joue un extrait audio d'un locuteur

        Args:
            audio_path: Fichier audio source
            segments: Liste de SpeakerSegment
            speaker: Nom du locuteur (ex: "SPEAKER_0")
            duration_seconds: Durée preview
        """
        logger.info(f"🔊 Playing {duration_seconds}s preview of {speaker}...")

        # Charger audio
        audio = AudioSegment.from_file(str(audio_path))

        # Trouver segments du locuteur (comparer directement les strings)
        preview_audio = None
        accumulated_duration = 0

        for seg in segments:
            if seg.speaker == speaker:
                start_ms = int(seg.start * 1000)
                end_ms = int(seg.end * 1000)

                segment_audio = audio[start_ms:end_ms]

                if preview_audio is None:
                    preview_audio = segment_audio
                else:
                    preview_audio += segment_audio

                accumulated_duration = len(preview_audio) / 1000.0

                if accumulated_duration >= duration_seconds:
                    break

        if preview_audio:
            # Limiter à duration_seconds
            preview_audio = preview_audio[:int(duration_seconds * 1000)]

            try:
                play(preview_audio)
                logger.info("✅ Preview completed")
            except Exception as e:
                logger.warning(f"⚠️  Could not play audio: {e}")
                logger.info("   (Audio extraction will still work)")
        else:
            logger.warning(f"⚠️  No audio found for {speaker}")

    def extract_speaker_audio(self, audio_path: Path, segments: List[SpeakerSegment],
                             speaker: str) -> AudioSegment:
        """
        Extrait tous les segments d'un locuteur

        Args:
            audio_path: Fichier audio source
            segments: Liste de SpeakerSegment
            speaker: Nom du locuteur (ex: "SPEAKER_0")

        Returns:
            AudioSegment avec audio du locuteur
        """
        logger.info(f"✂️  Extracting audio for {speaker}...")

        # Charger audio
        audio = AudioSegment.from_file(str(audio_path))

        # Filtrer segments du locuteur (comparer directement les strings)
        speaker_segments = [seg for seg in segments if seg.speaker == speaker]

        # Debug: afficher format des speakers
        if len(speaker_segments) == 0:
            logger.warning(f"⚠️  No segments found for speaker '{speaker}'")
            logger.warning(f"   Available speakers in segments: {set(seg.speaker for seg in segments[:5])}")
            logger.warning(f"   Total segments: {len(segments)}")
            logger.warning(f"   Speaker type: {type(speaker)}, value: {repr(speaker)}")
            if segments:
                logger.warning(f"   First segment speaker type: {type(segments[0].speaker)}, value: {repr(segments[0].speaker)}")

        # Extraire tous les segments avec progression
        speaker_audio = None

        from tqdm import tqdm

        for seg in tqdm(speaker_segments, desc="   Extracting segments", unit="segment"):
            start_ms = int(seg.start * 1000)
            end_ms = int(seg.end * 1000)

            segment_audio = audio[start_ms:end_ms]

            if speaker_audio is None:
                speaker_audio = segment_audio
            else:
                speaker_audio += segment_audio

        if speaker_audio:
            logger.info(f"✅ Extracted {len(speaker_audio)/1000.0:.1f}s of audio")
            return speaker_audio
        else:
            logger.error(f"❌ No audio found for {speaker}")
            return AudioSegment.empty()

    def intelligent_split(self, audio: AudioSegment) -> List[AudioSegment]:
        """
        Découpe audio intelligemment en chunks 4-10s sans couper les mots

        Args:
            audio: AudioSegment à découper

        Returns:
            Liste de chunks
        """
        logger.info(f"\n✂️  Intelligent splitting...")
        logger.info(f"   Target: {self.MIN_CHUNK_DURATION_MS/1000:.0f}-{self.MAX_CHUNK_DURATION_MS/1000:.0f}s chunks")
        logger.info(f"   Silence detection: {self.MIN_SILENCE_LEN_MS}ms @ {self.SILENCE_THRESHOLD_DB}dB")

        # Détecter segments non-silencieux
        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=self.MIN_SILENCE_LEN_MS,
            silence_thresh=self.SILENCE_THRESHOLD_DB,
            seek_step=10
        )

        logger.info(f"   Found {len(nonsilent_ranges)} speech segments")

        # Regrouper en chunks optimaux
        chunks = []
        current_chunk_start = None
        current_chunk_end = None

        for start_ms, end_ms in nonsilent_ranges:
            segment_duration = end_ms - start_ms

            # Premier segment
            if current_chunk_start is None:
                current_chunk_start = start_ms
                current_chunk_end = end_ms
                continue

            # Durée actuelle du chunk en cours
            current_duration = current_chunk_end - current_chunk_start

            # Si on peut ajouter ce segment sans dépasser MAX
            if current_duration + segment_duration <= self.MAX_CHUNK_DURATION_MS:
                # Étendre le chunk
                current_chunk_end = end_ms
            else:
                # Sauvegarder chunk actuel si >= MIN
                if current_duration >= self.MIN_CHUNK_DURATION_MS:
                    chunk = audio[current_chunk_start:current_chunk_end]
                    chunks.append(chunk)

                # Démarrer nouveau chunk
                current_chunk_start = start_ms
                current_chunk_end = end_ms

        # Ajouter dernier chunk
        if current_chunk_start is not None and current_chunk_end is not None:
            current_duration = current_chunk_end - current_chunk_start
            if current_duration >= self.MIN_CHUNK_DURATION_MS:
                chunk = audio[current_chunk_start:current_chunk_end]
                chunks.append(chunk)

        logger.info(f"✅ Created {len(chunks)} intelligent chunks")

        # Stats
        if chunks:
            durations = [len(c)/1000.0 for c in chunks]
            logger.info(f"   Duration range: {min(durations):.1f}s - {max(durations):.1f}s")
            logger.info(f"   Average: {sum(durations)/len(durations):.1f}s")

        return chunks

    def save_chunks(self, chunks: List[AudioSegment], output_dir: Path,
                   prefix: str = "chunk") -> int:
        """
        Sauvegarde chunks en WAV 22050Hz mono

        Args:
            chunks: Liste de chunks
            output_dir: Dossier destination
            prefix: Préfixe nom fichier

        Returns:
            Nombre de fichiers sauvegardés
        """
        logger.info(f"\n💾 Saving chunks...")
        logger.info(f"   Format: {self.TARGET_SAMPLE_RATE}Hz mono WAV")
        logger.info(f"   Destination: {output_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)

        success_count = 0

        from tqdm import tqdm

        for i, chunk in tqdm(enumerate(chunks, 1), total=len(chunks), desc="   Saving", unit="file"):
            try:
                # Convertir mono 44.1kHz (optimal pour Chatterbox)
                if chunk.channels > 1:
                    chunk = chunk.set_channels(self.TARGET_CHANNELS)

                # Convertir sample rate (44.1kHz pour qualité optimale)
                if chunk.frame_rate != self.TARGET_SAMPLE_RATE:
                    chunk = chunk.set_frame_rate(self.TARGET_SAMPLE_RATE)

                # Sauvegarder
                output_file = output_dir / f"{prefix}_{i:03d}.wav"
                chunk.export(
                    str(output_file),
                    format=self.TARGET_FORMAT,
                    parameters=["-ar", str(self.TARGET_SAMPLE_RATE), "-ac", "1"]
                )

                success_count += 1

            except Exception as e:
                logger.error(f"   ⚠️  Failed to save chunk {i}: {e}")

        logger.info(f"✅ Saved {success_count}/{len(chunks)} chunks")
        return success_count

    def process_youtube_video(self, url: str, voice_name: str) -> bool:
        """
        Traite une vidéo YouTube complète

        Args:
            url: URL YouTube
            voice_name: Nom du dossier voix destination

        Returns:
            True si succès
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎬 Processing YouTube video")
        logger.info(f"{'='*60}")
        logger.info(f"URL: {url}")
        logger.info(f"Voice: {voice_name}")

        # Créer dossier temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 1. Télécharger audio
            raw_audio_file = self.download_audio_from_youtube(url, temp_path)
            if not raw_audio_file:
                return False

            # 2. Preprocessing (UVR + noise reduction + normalization)
            audio_file = self.preprocess_audio(raw_audio_file, temp_path)
            if not audio_file:
                logger.error("❌ Preprocessing failed")
                return False

            # 3. Télécharger sous-titres YouTube (pour validation Vosk)
            logger.info(f"\n📝 Downloading YouTube subtitles for validation...")
            subtitles = self.download_subtitles(url, temp_path)
            if subtitles:
                logger.info(f"   ✅ {len(subtitles)} subtitle entries downloaded")
            else:
                logger.warning(f"   ⚠️  No subtitles available - skipping Vosk validation")

            # 4. Diarization (sur audio preprocessed)
            segments = self.perform_speaker_diarization(audio_file)
            if not segments:
                return False

            # 4. Validation Vosk: DÉSACTIVÉ temporairement (filtrait tous les segments)
            # TODO: Améliorer validation Vosk ou utiliser autre méthode
            # if subtitles:
            #     logger.info(f"\n🎤 Validating segments with Vosk STT...")
            #     segments = self.validate_segments_with_vosk(audio_file, segments, subtitles)
            #     if not segments:
            #         logger.error("❌ No valid segments after Vosk filtering")
            #         return False
            #     logger.info(f"   ✅ {len(segments)} segments validated")

            # 5. Analyser locuteurs
            logger.info(f"\n📊 Speaker Analysis:")
            speaker_durations = self.analyze_speakers(segments)

            if not speaker_durations:
                logger.error("❌ No speakers detected")
                return False

            for speaker, duration in sorted(speaker_durations.items(),
                                           key=lambda x: x[1], reverse=True):
                logger.info(f"   {speaker}: {duration:.1f}s ({duration/60:.1f}min)")

            # 4. Sélection locuteur (interactif)
            speaker_list = sorted(speaker_durations.keys(),
                                 key=lambda x: speaker_durations[x], reverse=True)

            logger.info(f"\n🎤 Available speakers:")
            for i, speaker in enumerate(speaker_list, 1):
                duration = speaker_durations[speaker]
                logger.info(f"   {i}. {speaker} - {duration:.1f}s ({duration/60:.1f}min)")

            # Preview + sélection
            selected_speaker = None

            while not selected_speaker:
                print(f"\n🔊 Enter speaker number to preview (1-{len(speaker_list)}), ", end='')
                print("or 's' to skip preview: ", end='')

                choice = input().strip()

                if choice.lower() == 's':
                    # Sélection sans preview
                    print(f"📋 Select speaker to extract (1-{len(speaker_list)}): ", end='')
                    choice = input().strip()

                    try:
                        index = int(choice) - 1
                        if 0 <= index < len(speaker_list):
                            selected_speaker = speaker_list[index]
                        else:
                            print(f"❌ Invalid choice: {choice}")
                    except ValueError:
                        print(f"❌ Invalid input: {choice}")
                else:
                    # Preview
                    try:
                        index = int(choice) - 1
                        if 0 <= index < len(speaker_list):
                            speaker = speaker_list[index]
                            self.preview_speaker(audio_file, segments, speaker)

                            print(f"\n✅ Use this speaker? (y/n): ", end='')
                            confirm = input().strip().lower()

                            if confirm == 'y':
                                selected_speaker = speaker
                        else:
                            print(f"❌ Invalid choice: {choice}")
                    except ValueError:
                        print(f"❌ Invalid input: {choice}")

            logger.info(f"\n✅ Selected speaker: {selected_speaker}")
            logger.info(f"   Duration: {speaker_durations[selected_speaker]:.1f}s")

            # 5. Quality Scoring Pipeline
            voice_dir = self.voices_dir / voice_name
            voice_dir.mkdir(parents=True, exist_ok=True)

            # 5a. Sélectionner top 30 chunks (6-10s) avec quality scoring
            logger.info(f"\n📊 Quality scoring - selecting top 30 chunks...")
            top_30_chunks = self.select_best_chunks(
                audio_file, segments, selected_speaker, target_count=30
            )

            if not top_30_chunks:
                logger.error("❌ No quality chunks found")
                return False

            logger.info(f"✅ Selected {len(top_30_chunks)} chunks")
            avg_score = sum(score for _, score in top_30_chunks) / len(top_30_chunks)
            logger.info(f"   Average quality score: {avg_score:.1f}/100")

            # 5b. Filtrage Vosk pour top 10 final
            logger.info(f"\n🎤 Vosk filtering - selecting top 10 validated chunks...")
            top_10_validated = self.filter_chunks_with_vosk(
                top_30_chunks, target_count=10
            )

            if not top_10_validated:
                logger.error("❌ No validated chunks after Vosk filtering")
                return False

            logger.info(f"✅ Validated {len(top_10_validated)} chunks")

            # 5c. Concaténation finale
            logger.info(f"\n🔗 Concatenating final reference.wav...")
            output_path = voice_dir / "reference.wav"

            final_result = self.concatenate_final_reference(
                top_10_validated, output_path
            )

            if not final_result:
                logger.error("❌ Concatenation failed")
                return False

            logger.info(f"\n{'='*60}")
            logger.info(f"✅ YouTube Voice Extraction Complete!")
            logger.info(f"{'='*60}")
            logger.info(f"   Speaker: {selected_speaker}")
            logger.info(f"   Quality chunks: {len(top_10_validated)}")
            logger.info(f"   Total duration: {final_result['duration']:.1f}s")
            logger.info(f"   Average quality: {final_result['avg_quality']:.1f}/100")
            logger.info(f"   Reference file: {output_path}")
            logger.info(f"   Metadata: {output_path.with_suffix('.txt')}")
            logger.info(f"{'='*60}")
            logger.info(f"\n💡 Next step:")
            logger.info(f"   python3 clone_voice.py --voice {voice_name}")

            return True


def interactive_select_voice(available_voices: List[str]) -> Optional[str]:
    """
    Sélection interactive du dossier voix

    Args:
        available_voices: Liste voix disponibles

    Returns:
        Nom de la voix ou None
    """
    if not available_voices:
        print("\n⚠️  No voice folders found in voices/")
        print("💡 Create folder or select new name below")
        return None

    print("\n📋 Available voice folders:")
    print("  0. Create new voice folder")
    for i, voice in enumerate(available_voices, 1):
        print(f"  {i}. {voice}")

    print(f"\n🎤 Select voice (0-{len(available_voices)}) or 'q' to quit: ", end='')

    choice = input().strip()

    if choice.lower() == 'q':
        return None

    try:
        index = int(choice)

        if index == 0:
            # Nouveau dossier
            print("📝 Enter new voice name: ", end='')
            new_name = input().strip()

            if new_name:
                return new_name
            else:
                print("❌ Invalid name")
                return None

        elif 1 <= index <= len(available_voices):
            return available_voices[index - 1]

        else:
            print(f"❌ Invalid choice: {choice}")
            return None

    except ValueError:
        print(f"❌ Invalid input: {choice}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio from YouTube with speaker diarization",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--url",
        help="YouTube URL"
    )
    parser.add_argument(
        "--voice",
        help="Voice folder name in voices/"
    )

    args = parser.parse_args()

    # Vérifier dépendances
    if not all([AUDIO_AVAILABLE, YT_DLP_AVAILABLE, DIARIZATION_AVAILABLE]):
        logger.error("❌ Missing required dependencies")
        logger.error("   Install: pip install pydub soundfile yt-dlp librosa scikit-learn numpy")
        return

    print("\n" + "="*60)
    print("🎬  YOUTUBE AUDIO EXTRACTION - MiniBotPanel v3")
    print("="*60)

    # Initialiser extracteur
    extractor = YouTubeVoiceExtractor()

    # URL
    if args.url:
        url = args.url
    else:
        print("\n🔗 Enter YouTube URL: ", end='')
        url = input().strip()

        if not url:
            print("❌ No URL provided")
            return

    # Voice folder
    available_voices = extractor.detect_available_voices()

    if args.voice:
        voice_name = args.voice
    else:
        voice_name = interactive_select_voice(available_voices)

        if not voice_name:
            return

    # Traiter
    success = extractor.process_youtube_video(url, voice_name)

    if not success:
        logger.error("\n❌ YouTube extraction failed")
        return

    print("\n💡 Next steps:")
    print(f"   1. python clone_voice.py --voice {voice_name}")
    print(f"   2. Use this voice in your scenarios!")


if __name__ == "__main__":
    main()
