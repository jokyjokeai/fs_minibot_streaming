#!/usr/bin/env python3
"""
Setup Audio Unifié - MiniBotPanel v3

Script complet pour normaliser, ajuster volume et copier les fichiers audio vers FreeSWITCH.

Fonctionnalités:
1. Normalisation audio (peak + RMS)
2. Ajustement volume configurable (-5dB à +5dB, défaut 0dB - pas de boost)
3. Réduction automatique background audio (-10dB sous autres fichiers)
4. Conversion format téléphonie (16kHz mono PCM 16-bit WAV - qualité wideband)
5. Copie vers FreeSWITCH avec permissions correctes

Utilisation:
    # Mode interactif
    python3 setup_audio.py

    # Mode automatique
    python3 setup_audio.py --source audio/ --target /usr/share/freeswitch/sounds/minibot

    # Avec ajustements
    python3 setup_audio.py --volume-adjust +2 --background-reduction -10

    # Simulation (dry-run)
    python3 setup_audio.py --dry-run
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import time

# Audio processing
try:
    from pydub import AudioSegment
    from pydub.effects import normalize as pydub_normalize
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("❌ Audio processing libraries not available")
    print("   Install: pip install pydub numpy")
    sys.exit(1)

# Couleurs terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AudioFileInfo:
    """Information sur un fichier audio traité"""
    source_path: Path
    target_path: Path
    volume_before: float  # dBFS
    volume_after: float   # dBFS
    duration: float       # secondes
    is_background: bool
    status: str           # "ok", "warning", "error"
    message: str = ""


class AudioProcessor:
    """
    Processeur audio principal pour normalisation, conversion et copie vers FreeSWITCH.
    """

    # Format cible téléphonie
    TARGET_SAMPLE_RATE = 16000  # 16kHz (wideband - meilleure qualité)
    TARGET_CHANNELS = 1         # Mono
    TARGET_FORMAT = "wav"
    TARGET_CODEC = "pcm_s16le"  # PCM 16-bit (meilleure qualité que µ-law)

    # Normalisation
    TARGET_PEAK_DB = -3.0      # Peak standard téléphonie
    TARGET_RMS_DB = -18.0      # RMS confort écoute

    def __init__(
        self,
        source_dir: Path,
        target_dir: Path,
        volume_adjust: float = 0.0,
        background_reduction: float = -10.0,
        dry_run: bool = False,
        force: bool = False
    ):
        """
        Initialise le processeur audio.

        Args:
            source_dir: Dossier source (audio/)
            target_dir: Dossier FreeSWITCH (/usr/share/freeswitch/sounds/minibot)
            volume_adjust: Ajustement volume global en dB (défaut 0dB - pas de boost)
            background_reduction: Réduction volume background en dB (défaut -10dB)
            dry_run: Mode simulation
            force: Re-traiter fichiers existants
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.volume_adjust = volume_adjust
        self.background_reduction = background_reduction
        self.dry_run = dry_run
        self.force = force

        # Statistiques
        self.processed_files: List[AudioFileInfo] = []
        self.warnings = 0
        self.errors = 0

        logger.info(f"{Colors.BOLD}🔊 AudioProcessor initialized{Colors.END}")

    def detect_volume(self, audio: AudioSegment) -> Tuple[float, float]:
        """
        Détecte le volume d'un audio (peak + RMS).

        Args:
            audio: AudioSegment

        Returns:
            (peak_dBFS, rms_dBFS)
        """
        peak_db = audio.max_dBFS
        rms_db = audio.dBFS

        return peak_db, rms_db

    def normalize_audio(
        self,
        audio: AudioSegment,
        target_peak: float = TARGET_PEAK_DB
    ) -> AudioSegment:
        """
        Normalise l'audio au peak cible.

        Args:
            audio: AudioSegment source
            target_peak: Peak cible en dBFS (défaut -3dB)

        Returns:
            AudioSegment normalisé
        """
        current_peak = audio.max_dBFS
        adjustment = target_peak - current_peak

        return audio + adjustment

    def adjust_volume(
        self,
        audio: AudioSegment,
        adjustment: float
    ) -> AudioSegment:
        """
        Ajuste le volume de l'audio.

        Args:
            audio: AudioSegment source
            adjustment: Ajustement en dB (+/-)

        Returns:
            AudioSegment ajusté
        """
        return audio + adjustment

    def convert_to_telephony_format(
        self,
        audio: AudioSegment
    ) -> AudioSegment:
        """
        Convertit audio au format téléphonie (8kHz mono).

        Args:
            audio: AudioSegment source

        Returns:
            AudioSegment converti
        """
        # Mono
        if audio.channels > 1:
            audio = audio.set_channels(self.TARGET_CHANNELS)

        # 8kHz
        if audio.frame_rate != self.TARGET_SAMPLE_RATE:
            audio = audio.set_frame_rate(self.TARGET_SAMPLE_RATE)

        return audio

    def process_file(
        self,
        source_path: Path,
        target_path: Path,
        is_background: bool = False
    ) -> AudioFileInfo:
        """
        Traite un fichier audio complet.

        Args:
            source_path: Fichier source
            target_path: Fichier destination
            is_background: Si True, applique réduction background

        Returns:
            AudioFileInfo avec résultats
        """
        try:
            # Charger audio
            audio = AudioSegment.from_file(str(source_path))
            duration = len(audio) / 1000.0  # secondes

            # Détecter volume avant
            peak_before, rms_before = self.detect_volume(audio)

            # 1. Normaliser au peak standard
            audio = self.normalize_audio(audio, self.TARGET_PEAK_DB)

            # 2. Appliquer ajustement global
            if is_background:
                # Background: ajustement global + réduction supplémentaire
                total_adjust = self.volume_adjust + self.background_reduction
                audio = self.adjust_volume(audio, total_adjust)
            else:
                # Fichiers normaux: juste ajustement global
                audio = self.adjust_volume(audio, self.volume_adjust)

            # 3. Convertir format téléphonie
            audio = self.convert_to_telephony_format(audio)

            # Détecter volume après
            peak_after, rms_after = self.detect_volume(audio)

            # 4. Exporter avec codec µ-law
            if not self.dry_run:
                # Créer dossier parent si nécessaire
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Export avec ffmpeg via pydub
                audio.export(
                    str(target_path),
                    format=self.TARGET_FORMAT,
                    codec=self.TARGET_CODEC,
                    parameters=[
                        "-ar", str(self.TARGET_SAMPLE_RATE),
                        "-ac", str(self.TARGET_CHANNELS)
                    ]
                )

            return AudioFileInfo(
                source_path=source_path,
                target_path=target_path,
                volume_before=peak_before,
                volume_after=peak_after,
                duration=duration,
                is_background=is_background,
                status="ok",
                message="✅ OK"
            )

        except Exception as e:
            logger.error(f"{Colors.RED}Error processing {source_path.name}: {e}{Colors.END}")
            self.errors += 1

            return AudioFileInfo(
                source_path=source_path,
                target_path=target_path,
                volume_before=0.0,
                volume_after=0.0,
                duration=0.0,
                is_background=is_background,
                status="error",
                message=f"❌ {str(e)[:50]}"
            )

    def scan_audio_files(self) -> List[Tuple[Path, Path, bool]]:
        """
        Scanne récursivement le dossier source pour trouver tous les fichiers audio.

        Returns:
            Liste de tuples (source_path, target_path, is_background)
        """
        audio_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac'}
        files = []

        for source_file in self.source_dir.rglob('*'):
            if source_file.is_file() and source_file.suffix.lower() in audio_extensions:
                # Calculer chemin relatif
                rel_path = source_file.relative_to(self.source_dir)
                target_file = self.target_dir / rel_path.with_suffix('.wav')

                # Détecter si c'est un fichier background
                is_background = 'background' in source_file.parts

                # Skip si déjà traité (sauf force)
                if not self.force and target_file.exists():
                    continue

                files.append((source_file, target_file, is_background))

        return files

    def copy_to_freeswitch_with_permissions(self) -> bool:
        """
        Copie les fichiers vers FreeSWITCH avec les bonnes permissions.

        Returns:
            True si succès
        """
        if self.dry_run:
            logger.info(f"{Colors.YELLOW}[DRY-RUN] Would copy to FreeSWITCH{Colors.END}")
            return True

        try:
            # Détecter utilisateur FreeSWITCH
            freeswitch_user = self._detect_freeswitch_user()

            # Créer dossier racine avec sudo si nécessaire
            if not self.target_dir.exists():
                logger.info(f"Creating target directory: {self.target_dir}")
                subprocess.run(
                    ['sudo', 'mkdir', '-p', str(self.target_dir)],
                    check=True,
                    capture_output=True
                )

            # Définir permissions sur tous les fichiers
            logger.info(f"Setting permissions...")

            # Dossiers: 755
            subprocess.run(
                ['sudo', 'find', str(self.target_dir), '-type', 'd', '-exec', 'chmod', '755', '{}', '+'],
                check=False,  # Peut échouer si dossiers n'existent pas encore
                capture_output=True
            )

            # Fichiers: 644
            subprocess.run(
                ['sudo', 'find', str(self.target_dir), '-type', 'f', '-exec', 'chmod', '644', '{}', '+'],
                check=False,
                capture_output=True
            )

            # Changer propriétaire si utilisateur FreeSWITCH détecté
            if freeswitch_user:
                logger.info(f"Setting owner to: {freeswitch_user}")
                subprocess.run(
                    ['sudo', 'chown', '-R', freeswitch_user, str(self.target_dir)],
                    check=False,  # Non critique si échoue
                    capture_output=True
                )

            return True

        except Exception as e:
            logger.error(f"{Colors.RED}Error setting permissions: {e}{Colors.END}")
            self.errors += 1
            return False

    def _detect_freeswitch_user(self) -> Optional[str]:
        """
        Détecte automatiquement l'utilisateur FreeSWITCH.

        Returns:
            "freeswitch:freeswitch" ou None
        """
        try:
            # Vérifier processus FreeSWITCH
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.split('\n'):
                if 'freeswitch' in line.lower() and 'grep' not in line:
                    # Extraire utilisateur (première colonne)
                    parts = line.split()
                    if parts:
                        user = parts[0]
                        logger.info(f"Detected FreeSWITCH user: {user}")
                        return f"{user}:{user}"

            # Fallback
            logger.warning("Could not detect FreeSWITCH user, using default: freeswitch:freeswitch")
            return "freeswitch:freeswitch"

        except Exception as e:
            logger.warning(f"Could not detect FreeSWITCH user: {e}")
            return None

    def process_all(self) -> bool:
        """
        Traite tous les fichiers audio.

        Returns:
            True si succès global
        """
        start_time = time.time()

        # Scanner fichiers
        logger.info(f"\n{Colors.BOLD}📂 Scanning audio files...{Colors.END}")
        files_to_process = self.scan_audio_files()

        if not files_to_process:
            logger.warning(f"{Colors.YELLOW}No audio files to process{Colors.END}")
            return False

        logger.info(f"Found {len(files_to_process)} files to process\n")

        # Traiter chaque fichier
        logger.info(f"{Colors.BOLD}🔄 Processing audio files...{Colors.END}\n")

        for source_path, target_path, is_background in files_to_process:
            file_type = "BACKGROUND" if is_background else "VOICE"
            logger.info(f"[{file_type}] {source_path.name}")

            file_info = self.process_file(source_path, target_path, is_background)
            self.processed_files.append(file_info)

        # Copier vers FreeSWITCH avec permissions
        logger.info(f"\n{Colors.BOLD}📦 Setting FreeSWITCH permissions...{Colors.END}")
        self.copy_to_freeswitch_with_permissions()

        # Rapport final
        elapsed_time = time.time() - start_time
        self._print_report(elapsed_time)

        return self.errors == 0

    def _print_report(self, elapsed_time: float):
        """
        Affiche le rapport final.

        Args:
            elapsed_time: Temps écoulé en secondes
        """
        print(f"\n{'═' * 80}")
        print(f"{Colors.BOLD}{Colors.CYAN}📊 RAPPORT DE TRAITEMENT{Colors.END}")
        print(f"{'═' * 80}\n")

        # Tableau résultats
        print(f"{Colors.BOLD}Fichiers traités :{Colors.END}\n")
        print(f"{'Fichier':<40} {'Vol. Avant':<12} {'Vol. Après':<12} {'Status':<10}")
        print(f"{'-' * 80}")

        for file_info in self.processed_files:
            filename = file_info.source_path.name[:38]
            vol_before = f"{file_info.volume_before:+.1f} dB"
            vol_after = f"{file_info.volume_after:+.1f} dB"

            # Couleur selon status
            if file_info.status == "ok":
                status_color = Colors.GREEN
            elif file_info.status == "warning":
                status_color = Colors.YELLOW
            else:
                status_color = Colors.RED

            print(f"{filename:<40} {vol_before:<12} {vol_after:<12} {status_color}{file_info.message}{Colors.END}")

        # Statistiques
        print(f"\n{'-' * 80}")
        print(f"\n{Colors.BOLD}Statistiques :{Colors.END}")
        print(f"   ✅ Traités avec succès : {len([f for f in self.processed_files if f.status == 'ok'])}")
        print(f"   ⚠️  Avertissements     : {self.warnings}")
        print(f"   ❌ Erreurs            : {self.errors}")
        print(f"   ⏱️  Temps total        : {elapsed_time:.1f}s")

        # Configuration
        print(f"\n{Colors.BOLD}Configuration :{Colors.END}")
        print(f"   📁 Source             : {self.source_dir}")
        print(f"   📁 Target             : {self.target_dir}")
        print(f"   🎚️  Volume adjust      : {self.volume_adjust:+.1f} dB")
        print(f"   🔉 Background reduce  : {self.background_reduction:.1f} dB")
        print(f"   📻 Format             : {self.TARGET_SAMPLE_RATE}Hz mono {self.TARGET_CODEC}")

        if self.dry_run:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  DRY-RUN MODE - No files were actually modified{Colors.END}")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Fichiers copiés vers FreeSWITCH avec permissions appropriées{Colors.END}")

        print(f"\n{'═' * 80}\n")


def main():
    """Point d'entrée principal"""

    parser = argparse.ArgumentParser(
        description="Setup Audio Unifié - MiniBotPanel v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Mode interactif (défaut)
  python3 setup_audio.py

  # Avec ajustements personnalisés
  python3 setup_audio.py --volume-adjust +3 --background-reduction -12

  # Simulation (ne modifie rien)
  python3 setup_audio.py --dry-run

  # Re-traiter tous les fichiers
  python3 setup_audio.py --force
        """
    )

    parser.add_argument(
        '--source',
        type=str,
        default='audio/',
        help='Dossier source audio (défaut: audio/)'
    )

    parser.add_argument(
        '--target',
        type=str,
        default='/usr/share/freeswitch/sounds/minibot',
        help='Dossier FreeSWITCH cible (défaut: /usr/share/freeswitch/sounds/minibot)'
    )

    parser.add_argument(
        '--volume-adjust',
        type=float,
        default=0.0,
        help='Ajustement volume global en dB (défaut: 0.0 = pas de boost, range: -5 à +5)'
    )

    parser.add_argument(
        '--background-reduction',
        type=float,
        default=-10.0,
        help='Réduction volume background en dB (défaut: -10.0)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mode simulation (ne modifie aucun fichier)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-traiter tous les fichiers même s\'ils existent déjà'
    )

    args = parser.parse_args()

    # Validation
    if args.volume_adjust < -5 or args.volume_adjust > 5:
        logger.error(f"{Colors.RED}Volume adjustment doit être entre -5 et +5 dB{Colors.END}")
        sys.exit(1)

    # Header
    print(f"\n{'═' * 80}")
    print(f"{Colors.BOLD}{Colors.CYAN}🔊 SETUP AUDIO UNIFIÉ - MiniBotPanel v3{Colors.END}")
    print(f"{'═' * 80}\n")

    # Créer processeur
    processor = AudioProcessor(
        source_dir=Path(args.source),
        target_dir=Path(args.target),
        volume_adjust=args.volume_adjust,
        background_reduction=args.background_reduction,
        dry_run=args.dry_run,
        force=args.force
    )

    # Traiter
    success = processor.process_all()

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
