#!/usr/bin/env python3
"""
YouTube Audio Extraction + Speaker Diarization - MiniBotPanel v3

Extrait l'audio d'une vidéo YouTube, identifie les locuteurs et découpe
intelligemment pour le clonage vocal.

Workflow:
1. Demande URL YouTube
2. Sélectionne dossier destination dans voices/
3. Télécharge et extrait audio (yt-dlp)
4. Identifie locuteurs avec pyannote.audio 3.1
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

# Supprimer warning pyannote.audio (torchaudio backend déprécié)
warnings.filterwarnings("ignore", message="torchaudio._backend.set_audio_backend has been deprecated")

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

# Speaker diarization
try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    print("❌ pyannote.audio not available")
    print("   Install: pip install pyannote.audio")

from system.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YouTubeVoiceExtractor:
    """Extracteur audio YouTube avec diarization et découpage intelligent"""

    # Format optimal pour Coqui TTS
    TARGET_SAMPLE_RATE = 22050
    TARGET_CHANNELS = 1
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

        # HuggingFace token
        self.hf_token = config.HUGGINGFACE_TOKEN
        if not self.hf_token:
            logger.warning("⚠️  HUGGINGFACE_TOKEN not configured in .env")
            logger.warning("   Speaker diarization will not work")

        logger.info("🎬 YouTubeVoiceExtractor initialized")

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

    def perform_speaker_diarization(self, audio_path: Path) -> Optional[object]:
        """
        Identifie les locuteurs dans un fichier audio

        Args:
            audio_path: Chemin fichier audio

        Returns:
            Objet diarization pyannote ou None
        """
        if not self.hf_token:
            logger.error("❌ HUGGINGFACE_TOKEN required for speaker diarization")
            logger.error("   Configure in .env file")
            return None

        logger.info(f"\n🎤 Performing speaker diarization...")
        logger.info(f"   Using pyannote.audio 3.1")

        try:
            # Charger pipeline (télécharge automatiquement si nécessaire)
            logger.info("   Loading pipeline...")
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                use_auth_token=self.hf_token
            )

            # Exécuter diarization avec progression
            logger.info(f"   Analyzing audio: {audio_path.name}")

            # Callback pour progression
            from tqdm import tqdm

            class ProgressHook:
                def __init__(self):
                    self.pbar = None

                def __call__(self, step_name, step_artefact, file=None, total=None, completed=None):
                    if completed == 0 and total is not None:
                        if self.pbar is not None:
                            self.pbar.close()
                        self.pbar = tqdm(total=total, desc=f"   {step_name}", unit="chunk")
                    elif self.pbar is not None and completed is not None:
                        self.pbar.update(completed - self.pbar.n)
                        if completed >= total:
                            self.pbar.close()
                            self.pbar = None

            hook = ProgressHook()
            diarization = pipeline(str(audio_path), hook=hook)

            logger.info("✅ Diarization completed")
            return diarization

        except Exception as e:
            logger.error(f"❌ Diarization failed: {e}")
            logger.error("   Make sure you accepted terms at:")
            logger.error("   https://huggingface.co/pyannote/speaker-diarization-community-1")
            return None

    def analyze_speakers(self, diarization: object) -> Dict[str, float]:
        """
        Analyse les locuteurs et calcule durées

        Args:
            diarization: Objet pyannote diarization

        Returns:
            Dict {speaker: duration_seconds}
        """
        speaker_durations = {}

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            duration = turn.end - turn.start

            if speaker not in speaker_durations:
                speaker_durations[speaker] = 0.0

            speaker_durations[speaker] += duration

        return speaker_durations

    def preview_speaker(self, audio_path: Path, diarization: object,
                       speaker: str, duration_seconds: float = 5.0):
        """
        Joue un extrait audio d'un locuteur

        Args:
            audio_path: Fichier audio source
            diarization: Objet diarization
            speaker: ID du locuteur
            duration_seconds: Durée preview
        """
        logger.info(f"🔊 Playing {duration_seconds}s preview of {speaker}...")

        # Charger audio
        audio = AudioSegment.from_file(str(audio_path))

        # Trouver premier segment du locuteur
        preview_audio = None
        accumulated_duration = 0

        for turn, _, spk in diarization.itertracks(yield_label=True):
            if spk == speaker:
                start_ms = int(turn.start * 1000)
                end_ms = int(turn.end * 1000)

                segment = audio[start_ms:end_ms]

                if preview_audio is None:
                    preview_audio = segment
                else:
                    preview_audio += segment

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

    def extract_speaker_audio(self, audio_path: Path, diarization: object,
                             speaker: str) -> AudioSegment:
        """
        Extrait tous les segments d'un locuteur

        Args:
            audio_path: Fichier audio source
            diarization: Objet diarization
            speaker: ID du locuteur

        Returns:
            AudioSegment avec audio du locuteur
        """
        logger.info(f"✂️  Extracting audio for {speaker}...")

        # Charger audio
        audio = AudioSegment.from_file(str(audio_path))

        # Compter segments
        segments_list = [(turn, spk) for turn, _, spk in diarization.itertracks(yield_label=True) if spk == speaker]

        # Extraire tous les segments du locuteur avec progression
        speaker_audio = None

        from tqdm import tqdm

        for turn, spk in tqdm(segments_list, desc="   Extracting segments", unit="segment"):
            start_ms = int(turn.start * 1000)
            end_ms = int(turn.end * 1000)

            segment = audio[start_ms:end_ms]

            if speaker_audio is None:
                speaker_audio = segment
            else:
                speaker_audio += segment

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
                # Convertir mono
                if chunk.channels > 1:
                    chunk = chunk.set_channels(self.TARGET_CHANNELS)

                # Convertir sample rate
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
            audio_file = self.download_audio_from_youtube(url, temp_path)
            if not audio_file:
                return False

            # 2. Diarization
            diarization = self.perform_speaker_diarization(audio_file)
            if not diarization:
                return False

            # 3. Analyser locuteurs
            logger.info(f"\n📊 Speaker Analysis:")
            speaker_durations = self.analyze_speakers(diarization)

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
                            self.preview_speaker(audio_file, diarization, speaker)

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

            # 5. Extraire audio du locuteur
            speaker_audio = self.extract_speaker_audio(audio_file, diarization, selected_speaker)
            if len(speaker_audio) == 0:
                return False

            # 6. Découpe intelligent
            chunks = self.intelligent_split(speaker_audio)
            if not chunks:
                logger.error("❌ No chunks created")
                return False

            # 7. Sauvegarder
            voice_dir = self.voices_dir / voice_name
            saved_count = self.save_chunks(chunks, voice_dir, prefix="youtube")

            if saved_count == 0:
                logger.error("❌ No files saved")
                return False

            logger.info(f"\n{'='*60}")
            logger.info(f"✅ YouTube extraction completed!")
            logger.info(f"   Speaker: {selected_speaker}")
            logger.info(f"   Duration: {speaker_durations[selected_speaker]:.1f}s")
            logger.info(f"   Chunks: {saved_count} files")
            logger.info(f"   Location: {voice_dir}")
            logger.info(f"{'='*60}")

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
    if not all([AUDIO_AVAILABLE, YT_DLP_AVAILABLE, PYANNOTE_AVAILABLE]):
        logger.error("❌ Missing required dependencies")
        logger.error("   Install: pip install pydub soundfile yt-dlp pyannote.audio")
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
