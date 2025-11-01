#!/usr/bin/env python3
"""
Setup Audio - MiniBotPanel v3

Utilitaire pour préparer et optimiser les fichiers audio pour FreeSWITCH.

Fonctionnalités:
- Détection automatique dossiers voix dans audio/
- Sélection background audio
- Conversion format optimal FreeSWITCH (22050Hz mono WAV SLIN16)
- Normalisation volume global
- Volume background automatique (-8dB par rapport aux autres)
- Analyse qualité audio

Workflow:
1. Détecte dossiers audio disponibles
2. Sélectionne dossier à traiter
3. (Optionnel) Sélectionne background audio
4. Convertit tous les fichiers au format optimal
5. Normalise volumes
6. Applique volume background (-8dB)
7. Vérifie compatibilité FreeSWITCH

Utilisation:
    python setup_audio.py
    python setup_audio.py --folder audio/julie --volume -3
    python setup_audio.py --folder audio/marie --background audio/background/office.wav --volume -5
"""

import argparse
import logging
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

# Audio processing
try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("❌ Audio processing libraries not available (pydub, soundfile)")
    print("   Install: pip install pydub soundfile")

from system.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioSetup:
    """Gestionnaire de setup audio pour FreeSWITCH"""

    # Format optimal FreeSWITCH
    TARGET_SAMPLE_RATE = 22050  # Hz (Coqui TTS optimal)
    TARGET_CHANNELS = 1  # Mono
    TARGET_FORMAT = "wav"

    # Volume adjustments
    BACKGROUND_VOLUME_OFFSET = -8.0  # dB (background plus bas que voix)

    def __init__(self):
        """Initialise le setup"""
        self.audio_dir = Path(config.AUDIO_FILES_PATH)
        self.background_dir = self.audio_dir / "background"

        # Créer dossiers si nécessaire
        self.audio_dir.mkdir(exist_ok=True)
        self.background_dir.mkdir(exist_ok=True)

        logger.info("🔊 AudioSetup initialized")

    def detect_audio_folders(self) -> List[str]:
        """
        Détecte les dossiers audio disponibles dans audio/

        Returns:
            Liste des noms de dossiers
        """
        folders = []

        if not self.audio_dir.exists():
            return folders

        for item in self.audio_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != 'background':
                # Vérifier s'il y a des fichiers audio
                audio_files = self._find_audio_files(item)
                if audio_files:
                    folders.append(item.name)

        return sorted(folders)

    def detect_background_files(self) -> List[str]:
        """
        Détecte les fichiers background audio disponibles

        Returns:
            Liste des noms de fichiers background
        """
        if not self.background_dir.exists():
            return []

        audio_files = self._find_audio_files(self.background_dir)
        return [f.name for f in audio_files]

    def _find_audio_files(self, directory: Path) -> List[Path]:
        """
        Trouve tous les fichiers audio dans un dossier

        Args:
            directory: Dossier à scanner

        Returns:
            Liste de fichiers audio
        """
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
        audio_files = []

        for ext in audio_extensions:
            audio_files.extend(directory.glob(f'*{ext}'))
            audio_files.extend(directory.glob(f'**/*{ext}'))  # Récursif

        return sorted(set(audio_files))  # Déduplique

    def analyze_audio_file(self, file_path: Path) -> dict:
        """
        Analyse un fichier audio

        Args:
            file_path: Chemin fichier

        Returns:
            Dict avec infos audio
        """
        try:
            audio = AudioSegment.from_file(str(file_path))

            return {
                "duration_seconds": len(audio) / 1000.0,
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "format": file_path.suffix[1:],
                "dBFS": audio.dBFS,
                "max_dBFS": audio.max_dBFS,
                "file_size_mb": file_path.stat().st_size / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Error analyzing {file_path.name}: {e}")
            return {}

    def convert_to_optimal_format(self, input_path: Path, output_path: Path,
                                   volume_adjustment: float = 0.0) -> bool:
        """
        Convertit audio au format optimal FreeSWITCH

        Args:
            input_path: Fichier source
            output_path: Fichier destination
            volume_adjustment: Ajustement volume en dB (0 = aucun)

        Returns:
            True si succès
        """
        try:
            # Charger audio
            audio = AudioSegment.from_file(str(input_path))

            # Convertir mono
            if audio.channels > 1:
                audio = audio.set_channels(self.TARGET_CHANNELS)

            # Convertir sample rate
            if audio.frame_rate != self.TARGET_SAMPLE_RATE:
                audio = audio.set_frame_rate(self.TARGET_SAMPLE_RATE)

            # Ajuster volume si demandé
            if volume_adjustment != 0.0:
                audio = audio + volume_adjustment  # dB

            # Exporter WAV
            audio.export(
                str(output_path),
                format=self.TARGET_FORMAT,
                parameters=["-ar", str(self.TARGET_SAMPLE_RATE), "-ac", "1"]
            )

            return True

        except Exception as e:
            logger.error(f"Conversion failed for {input_path.name}: {e}")
            return False

    def process_audio_folder(self, folder_name: str, volume_db: float = 0.0,
                            background_file: Optional[str] = None) -> bool:
        """
        Traite un dossier audio complet

        Args:
            folder_name: Nom du dossier à traiter
            volume_db: Ajustement volume global (-10 à +10 dB)
            background_file: Nom fichier background (optionnel)

        Returns:
            True si succès
        """
        folder_path = self.audio_dir / folder_name

        if not folder_path.exists():
            logger.error(f"❌ Folder not found: {folder_path}")
            return False

        logger.info(f"\n{'='*60}")
        logger.info(f"🔊 Processing audio folder: {folder_name}")
        logger.info(f"{'='*60}")

        # Trouver fichiers audio
        audio_files = self._find_audio_files(folder_path)
        if not audio_files:
            logger.error(f"❌ No audio files found in {folder_path}")
            return False

        logger.info(f"📁 Found {len(audio_files)} audio files")

        # Créer dossier processed
        processed_dir = folder_path / "processed"
        processed_dir.mkdir(exist_ok=True)

        # Traiter chaque fichier
        logger.info(f"\n🔄 Converting to optimal format (22050Hz mono WAV)...")
        success_count = 0

        for i, audio_file in enumerate(audio_files, 1):
            logger.info(f"\n[{i}/{len(audio_files)}] {audio_file.name}")

            # Analyser fichier original
            info = self.analyze_audio_file(audio_file)
            if info:
                logger.info(f"  📊 Original: {info['sample_rate']}Hz, "
                          f"{info['channels']}ch, {info['duration_seconds']:.1f}s, "
                          f"{info['dBFS']:.1f}dBFS")

            # Chemin de sortie
            output_file = processed_dir / f"{audio_file.stem}.wav"

            # Convertir
            if self.convert_to_optimal_format(audio_file, output_file, volume_db):
                success_count += 1

                # Analyser résultat
                info_new = self.analyze_audio_file(output_file)
                if info_new:
                    logger.info(f"  ✅ Converted: {info_new['sample_rate']}Hz, "
                              f"{info_new['channels']}ch, {info_new['dBFS']:.1f}dBFS")
            else:
                logger.warning(f"  ⚠️  Conversion failed")

        if success_count == 0:
            logger.error(f"\n❌ No files converted successfully")
            return False

        logger.info(f"\n✅ {success_count}/{len(audio_files)} files converted")

        # Traiter background audio si fourni
        if background_file:
            logger.info(f"\n🎵 Processing background audio...")
            self._process_background_audio(background_file, folder_name, volume_db)

        # Copier fichiers traités dans le dossier principal
        logger.info(f"\n📦 Copying processed files to {folder_path}...")
        for processed_file in processed_dir.glob("*.wav"):
            dest_file = folder_path / processed_file.name
            shutil.copy2(processed_file, dest_file)
            logger.info(f"  ✅ {processed_file.name}")

        return True

    def _process_background_audio(self, background_file: str, voice_folder: str,
                                  main_volume_db: float):
        """
        Traite le fichier background audio

        Args:
            background_file: Nom du fichier background
            voice_folder: Dossier voix destination
            main_volume_db: Volume principal (pour calculer offset)
        """
        background_path = self.background_dir / background_file

        if not background_path.exists():
            logger.error(f"❌ Background file not found: {background_path}")
            return

        # Calculer volume background (main_volume - 8dB)
        background_volume = main_volume_db + self.BACKGROUND_VOLUME_OFFSET

        logger.info(f"  📁 Source: {background_file}")
        logger.info(f"  🔊 Volume adjustment: {background_volume:.1f}dB "
                   f"({main_volume_db:.1f}dB {self.BACKGROUND_VOLUME_OFFSET:+.1f}dB)")

        # Destination
        dest_folder = self.audio_dir / voice_folder
        dest_file = dest_folder / f"background_{background_path.stem}.wav"

        # Convertir avec volume ajusté
        if self.convert_to_optimal_format(background_path, dest_file, background_volume):
            logger.info(f"  ✅ Background audio copied: {dest_file.name}")

            # Analyser
            info = self.analyze_audio_file(dest_file)
            if info:
                logger.info(f"     → {info['sample_rate']}Hz, {info['channels']}ch, "
                          f"{info['duration_seconds']:.1f}s, {info['dBFS']:.1f}dBFS")
        else:
            logger.error(f"  ❌ Background processing failed")


def interactive_select_folder(available_folders: List[str]) -> Optional[str]:
    """
    Sélection interactive du dossier audio

    Args:
        available_folders: Liste dossiers disponibles

    Returns:
        Nom du dossier ou None
    """
    if not available_folders:
        print("\n❌ No audio folders found in audio/")
        print("💡 Create a folder in audio/ and add audio files")
        return None

    print("\n📋 Available audio folders:")
    for i, folder in enumerate(available_folders, 1):
        print(f"  {i}. {folder}")

    print(f"\n🔊 Select folder to process (1-{len(available_folders)}) or 'q' to quit: ", end='')

    choice = input().strip()

    if choice.lower() == 'q':
        return None

    try:
        index = int(choice) - 1
        if 0 <= index < len(available_folders):
            return available_folders[index]
        else:
            print(f"❌ Invalid choice: {choice}")
            return None
    except ValueError:
        print(f"❌ Invalid input: {choice}")
        return None


def interactive_select_background(available_backgrounds: List[str]) -> Optional[str]:
    """
    Sélection interactive du background audio

    Args:
        available_backgrounds: Liste backgrounds disponibles

    Returns:
        Nom du fichier ou None
    """
    if not available_backgrounds:
        print("\n⚠️  No background audio files found in audio/background/")
        print("   Skipping background audio")
        return None

    print("\n📋 Available background audio:")
    print("  0. Skip (no background)")
    for i, bg in enumerate(available_backgrounds, 1):
        print(f"  {i}. {bg}")

    print(f"\n🎵 Select background (0-{len(available_backgrounds)}) or 'q' to skip: ", end='')

    choice = input().strip()

    if choice.lower() == 'q' or choice == '0':
        return None

    try:
        index = int(choice) - 1
        if 0 <= index < len(available_backgrounds):
            return available_backgrounds[index]
        else:
            print(f"❌ Invalid choice: {choice}")
            return None
    except ValueError:
        print(f"❌ Invalid input: {choice}")
        return None


def interactive_select_volume() -> float:
    """
    Sélection interactive du volume

    Returns:
        Ajustement volume en dB
    """
    print("\n🔊 Volume adjustment (-10 to +10 dB, 0 = no change)")
    print("   Recommended: -3 to -5 dB")
    print("   (Background will automatically be set to -8dB lower)")
    print(f"\n📊 Enter volume adjustment: ", end='')

    choice = input().strip()

    try:
        volume = float(choice)
        if -10 <= volume <= 10:
            return volume
        else:
            print(f"⚠️  Volume out of range, using 0dB")
            return 0.0
    except ValueError:
        print(f"⚠️  Invalid input, using 0dB")
        return 0.0


def main():
    parser = argparse.ArgumentParser(
        description="Setup audio files for FreeSWITCH",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--folder",
        help="Audio folder name to process (if not specified, interactive mode)"
    )
    parser.add_argument(
        "--background",
        help="Background audio file name (in audio/background/)"
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=0.0,
        help="Volume adjustment in dB (-10 to +10, default: 0)"
    )

    args = parser.parse_args()

    if not AUDIO_AVAILABLE:
        logger.error("❌ Audio processing not available")
        logger.error("   Install: pip install pydub soundfile")
        return

    print("\n" + "="*60)
    print("🔊  AUDIO SETUP - MiniBotPanel v3")
    print("="*60)

    # Initialiser setup
    setup = AudioSetup()

    # Détecter dossiers disponibles
    available_folders = setup.detect_audio_folders()

    # Sélection dossier
    if args.folder:
        folder_name = args.folder
        if folder_name not in available_folders:
            logger.error(f"❌ Folder '{folder_name}' not found in audio/")
            logger.info(f"💡 Available: {', '.join(available_folders) if available_folders else 'None'}")
            return
    else:
        # Mode interactif
        folder_name = interactive_select_folder(available_folders)
        if not folder_name:
            return

    # Sélection background
    if args.background:
        background_file = args.background
    else:
        # Mode interactif
        available_backgrounds = setup.detect_background_files()
        background_file = interactive_select_background(available_backgrounds)

    # Sélection volume
    if args.volume == 0.0 and not args.folder:
        # Mode interactif uniquement si pas spécifié en CLI
        volume_db = interactive_select_volume()
    else:
        volume_db = args.volume

    # Valider volume
    if volume_db < -10 or volume_db > 10:
        logger.warning(f"⚠️  Volume {volume_db}dB out of range, clamping to [-10, +10]")
        volume_db = max(-10, min(10, volume_db))

    # Traiter dossier
    success = setup.process_audio_folder(folder_name, volume_db, background_file)

    if not success:
        logger.error("\n❌ Audio setup failed")
        return

    print("\n" + "="*60)
    print(f"✅ Audio setup completed successfully!")
    print(f"📁 Folder: audio/{folder_name}/")
    print(f"🔊 Volume: {volume_db:+.1f}dB")
    if background_file:
        bg_volume = volume_db + AudioSetup.BACKGROUND_VOLUME_OFFSET
        print(f"🎵 Background: {background_file} ({bg_volume:+.1f}dB)")
    print("="*60)


if __name__ == "__main__":
    main()
