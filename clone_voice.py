#!/usr/bin/env python3
"""
Clone Voice - MiniBotPanel v3 (Multi-Voice)

Utilitaire pour cloner des voix depuis des échantillons audio.

Fonctionnalités:
- Détection automatique des dossiers de voix dans voices/
- Nettoyage audio (noisereduce + audio-separator pour extraction voix)
- Conversion format optimal pour Coqui XTTS (22050Hz mono WAV)
- Détection automatique mode clonage (quick/standard/fine-tuning)
- Clone voix avec Coqui XTTS
- Génération automatique TTS pour objections/FAQ

Workflow:
1. Créer dossier voices/{nom_voix}/
2. Ajouter fichiers audio (10+ fichiers de 6-10 secondes recommandés)
3. Lancer script: python clone_voice.py
4. Sélectionner voix à cloner
5. Script nettoie, convertit, clone et génère TTS

Utilisation:
    python clone_voice.py
    python clone_voice.py --voice julie
    python clone_voice.py --voice marie --theme finance
    python clone_voice.py --voice julie --skip-tts
    python clone_voice.py --voice marie --force
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional
import json

# Audio processing
try:
    import noisereduce as nr
    import soundfile as sf
    from pydub import AudioSegment
    from pydub.effects import normalize
    from pydub.silence import detect_silence
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    print("⚠️  Audio processing libraries not available (noisereduce, soundfile, pydub)")

# Audio separator (vocal extraction)
try:
    from audio_separator.separator import Separator
    AUDIO_SEPARATOR_AVAILABLE = True
except ImportError:
    AUDIO_SEPARATOR_AVAILABLE = False
    print("⚠️  audio-separator not available (vocal extraction disabled)")

from system.config import config
from system.services.coqui_tts import CoquiTTS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VoiceCloner:
    """Gestionnaire de clonage de voix multi-voix avec nettoyage audio"""

    def __init__(self):
        """Initialise le cloner"""
        self.voices_dir = Path(config.VOICES_DIR)
        self.audio_dir = Path(config.AUDIO_DIR)
        self.tts = None

        # Créer dossiers si n'existent pas
        self.voices_dir.mkdir(exist_ok=True)
        self.audio_dir.mkdir(exist_ok=True)

        logger.info("🎤 VoiceCloner initialized")

    def detect_available_voices(self) -> List[str]:
        """
        Détecte les dossiers de voix disponibles dans voices/

        Returns:
            Liste des noms de voix disponibles
        """
        voices = []

        if not self.voices_dir.exists():
            return voices

        for item in self.voices_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Vérifier s'il y a des fichiers audio dedans
                audio_files = self._find_audio_files(item)
                if audio_files:
                    voices.append(item.name)

        return sorted(voices)

    def _find_audio_files(self, directory: Path) -> List[Path]:
        """
        Trouve tous les fichiers audio dans un dossier

        Args:
            directory: Dossier à scanner

        Returns:
            Liste de chemins vers fichiers audio
        """
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
        audio_files = []

        for ext in audio_extensions:
            audio_files.extend(directory.glob(f'*{ext}'))

        return sorted(audio_files)

    def clean_audio_file(self, input_path: Path, output_path: Path) -> bool:
        """
        Nettoie un fichier audio:
        1. Extraction voix (séparation musique avec audio-separator)
        2. Réduction bruit de fond (noisereduce)
        3. Trim silence (début/fin)
        4. Normalisation volume

        Args:
            input_path: Fichier audio source
            output_path: Fichier audio nettoyé

        Returns:
            True si succès
        """
        if not AUDIO_PROCESSING_AVAILABLE:
            logger.warning(f"⚠️  Audio processing not available, copying file as-is")
            # Copie simple
            import shutil
            shutil.copy2(input_path, output_path)
            return True

        try:
            logger.info(f"  🧹 Cleaning: {input_path.name}...")

            # Étape 1: Extraction voix si musique détectée (audio-separator)
            temp_path = input_path
            if AUDIO_SEPARATOR_AVAILABLE:
                try:
                    logger.info(f"    → Extracting vocals (audio-separator)...")
                    separator = Separator(output_dir=str(input_path.parent))
                    separator.load_model()
                    output_files = separator.separate(str(input_path))

                    # Chercher le fichier "vocals"
                    vocals_file = None
                    for f in output_files:
                        if 'vocals' in f.lower():
                            vocals_file = Path(f)
                            break

                    if vocals_file and vocals_file.exists():
                        temp_path = vocals_file
                        logger.info(f"    ✅ Vocals extracted")
                    else:
                        logger.info(f"    ℹ️  No vocals file, using original")

                except Exception as e:
                    logger.warning(f"    ⚠️  Vocal extraction failed: {e}, using original")

            # Étape 2: Charger audio
            audio_data, sample_rate = sf.read(str(temp_path))

            # Étape 3: Réduction bruit (stationary mode - bon pour bruit constant)
            logger.info(f"    → Noise reduction...")
            reduced_noise = nr.reduce_noise(
                y=audio_data,
                sr=sample_rate,
                stationary=True,  # Bon pour bruits constants (ventilation, etc.)
                prop_decrease=0.8  # Agressivité réduction (0-1)
            )

            # Sauvegarder temporairement pour pydub
            temp_reduced = output_path.parent / f"temp_{output_path.name}"
            sf.write(str(temp_reduced), reduced_noise, sample_rate)

            # Étape 4: Trim silence et normalisation avec pydub
            logger.info(f"    → Trim silence & normalize...")
            audio = AudioSegment.from_file(str(temp_reduced))

            # Trim silence (début et fin)
            silence_thresh = audio.dBFS - 14  # Seuil adaptatif
            nonsilent_ranges = detect_silence(
                audio,
                min_silence_len=500,  # 500ms de silence
                silence_thresh=silence_thresh,
                seek_step=10
            )

            # Inverser pour obtenir les parties non-silencieuses
            if nonsilent_ranges:
                # Prendre du début du premier son à la fin du dernier
                start_trim = nonsilent_ranges[0][1] if nonsilent_ranges else 0
                end_trim = nonsilent_ranges[-1][0] if nonsilent_ranges else len(audio)
                audio = audio[start_trim:end_trim]

            # Normalisation
            audio = normalize(audio)

            # Sauvegarder
            audio.export(str(output_path), format='wav')

            # Cleanup temp
            if temp_reduced.exists():
                temp_reduced.unlink()
            if temp_path != input_path and temp_path.exists():
                temp_path.unlink()  # Supprimer fichier vocals temporaire

            logger.info(f"    ✅ Cleaned: {output_path.name}")
            return True

        except Exception as e:
            logger.error(f"    ❌ Cleaning failed: {e}")
            return False

    def convert_to_optimal_format(self, input_path: Path, output_path: Path) -> bool:
        """
        Convertit audio au format optimal pour Coqui XTTS:
        - 22050 Hz (sample rate Coqui)
        - Mono
        - WAV format

        Args:
            input_path: Fichier source
            output_path: Fichier converti

        Returns:
            True si succès
        """
        try:
            # Charger avec pydub
            audio = AudioSegment.from_file(str(input_path))

            # Convertir mono
            if audio.channels > 1:
                audio = audio.set_channels(1)

            # Convertir 22050 Hz
            if audio.frame_rate != 22050:
                audio = audio.set_frame_rate(22050)

            # Exporter WAV
            audio.export(str(output_path), format='wav')

            logger.info(f"    ✅ Converted to 22050Hz mono WAV: {output_path.name}")
            return True

        except Exception as e:
            logger.error(f"    ❌ Conversion failed: {e}")
            return False

    def calculate_total_duration(self, audio_files: List[Path]) -> float:
        """
        Calcule la durée totale des fichiers audio

        Args:
            audio_files: Liste de fichiers

        Returns:
            Durée totale en secondes
        """
        total_duration = 0.0

        for audio_file in audio_files:
            try:
                audio = AudioSegment.from_file(str(audio_file))
                total_duration += len(audio) / 1000.0  # ms -> secondes
            except Exception as e:
                logger.warning(f"⚠️  Could not read {audio_file.name}: {e}")

        return total_duration

    def detect_cloning_mode(self, total_duration: float) -> Tuple[str, str]:
        """
        Détecte le mode de clonage optimal selon durée totale

        Args:
            total_duration: Durée totale en secondes

        Returns:
            Tuple (mode, description)
        """
        if total_duration < 30:
            return "quick", "⚠️  Quick mode (<30s) - Qualité limitée"
        elif total_duration < 120:
            return "standard", "✅ Standard mode (30s-120s) - Qualité recommandée"
        else:
            return "fine_tuning", "🌟 Fine-tuning mode (>120s) - Meilleure qualité"

    def process_voice_folder(self, voice_name: str, force: bool = False) -> bool:
        """
        Traite un dossier de voix complet:
        1. Scan fichiers audio
        2. Nettoyage + conversion
        3. Détection mode clonage
        4. Clonage voix

        Args:
            voice_name: Nom de la voix
            force: Forcer écrasement si existe

        Returns:
            True si succès
        """
        voice_dir = self.voices_dir / voice_name
        if not voice_dir.exists():
            logger.error(f"❌ Voice folder not found: {voice_dir}")
            return False

        logger.info(f"\n{'='*60}")
        logger.info(f"🎤 Processing voice: {voice_name}")
        logger.info(f"{'='*60}")

        # Trouver fichiers audio
        raw_audio_files = self._find_audio_files(voice_dir)
        if not raw_audio_files:
            logger.error(f"❌ No audio files found in {voice_dir}")
            return False

        logger.info(f"📁 Found {len(raw_audio_files)} audio files")

        # Créer dossier cleaned
        cleaned_dir = voice_dir / "cleaned"
        cleaned_dir.mkdir(exist_ok=True)

        # Nettoyer et convertir chaque fichier
        logger.info(f"\n🧹 Cleaning and converting audio files...")
        cleaned_files = []

        for i, raw_file in enumerate(raw_audio_files, 1):
            logger.info(f"\n[{i}/{len(raw_audio_files)}] {raw_file.name}")

            # Chemin cleaned
            cleaned_file = cleaned_dir / f"{raw_file.stem}_cleaned.wav"

            # Nettoyer
            if not self.clean_audio_file(raw_file, cleaned_file):
                logger.warning(f"⚠️  Skipping {raw_file.name}")
                continue

            # Convertir au format optimal
            optimal_file = cleaned_dir / f"{raw_file.stem}_optimal.wav"
            if not self.convert_to_optimal_format(cleaned_file, optimal_file):
                logger.warning(f"⚠️  Skipping {raw_file.name}")
                continue

            cleaned_files.append(optimal_file)

        if not cleaned_files:
            logger.error(f"❌ No files successfully processed")
            return False

        logger.info(f"\n✅ {len(cleaned_files)} files processed successfully")

        # Calculer durée totale
        total_duration = self.calculate_total_duration(cleaned_files)
        logger.info(f"⏱️  Total duration: {total_duration:.1f}s")

        # Détection mode clonage
        mode, mode_desc = self.detect_cloning_mode(total_duration)
        logger.info(f"🎯 Cloning mode: {mode_desc}")

        # Initialiser Coqui TTS
        if self.tts is None:
            logger.info(f"\n🤖 Initializing Coqui TTS...")
            self.tts = CoquiTTS()

            if not self.tts.is_available:
                logger.error("❌ Coqui TTS not available")
                return False

        # Cloner voix (utilise le premier fichier comme référence principale)
        # Note: Coqui XTTS v2 peut utiliser plusieurs fichiers pour améliorer qualité
        logger.info(f"\n🎤 Cloning voice '{voice_name}'...")

        # Pour l'instant, on utilise le premier fichier
        # TODO: Améliorer pour utiliser tous les fichiers (fine-tuning)
        reference_audio = str(cleaned_files[0])

        success = self.tts.clone_voice(reference_audio, voice_name)

        if not success:
            logger.error(f"❌ Voice cloning failed")
            return False

        logger.info(f"✅ Voice '{voice_name}' cloned successfully!")

        # Sauvegarder métadonnées
        metadata = {
            "voice_name": voice_name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_files": len(cleaned_files),
            "total_duration_seconds": total_duration,
            "cloning_mode": mode,
            "sample_rate": 22050,
            "format": "WAV mono"
        }

        metadata_path = voice_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"📄 Metadata saved: {metadata_path}")

        return True

    def generate_tts_for_objections(self, voice_name: str, theme: Optional[str] = None) -> bool:
        """
        Génère TTS pour toutes les objections/FAQ de la base de données

        Args:
            voice_name: Nom de la voix à utiliser
            theme: Thématique spécifique (None = toutes)

        Returns:
            True si succès
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔊 Generating TTS for objections/FAQ...")
        logger.info(f"{'='*60}")

        # Vérifier que la voix est clonée
        voice_dir = self.voices_dir / voice_name
        if not voice_dir.exists():
            logger.error(f"❌ Voice '{voice_name}' not found. Clone voice first.")
            return False

        # Initialiser Coqui TTS si nécessaire
        if self.tts is None:
            logger.info(f"🤖 Initializing Coqui TTS...")
            self.tts = CoquiTTS()

            if not self.tts.is_available:
                logger.error("❌ Coqui TTS not available")
                return False

        # Importer objections database
        try:
            from system import objections_database
        except ImportError:
            logger.error("❌ Could not import objections_database")
            return False

        # Créer dossier de sortie audio/tts/{voice_name}/
        output_dir = self.audio_dir / "tts" / voice_name
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📁 Output directory: {output_dir}")

        # Collecter toutes les objections selon thématique
        all_objections = {}

        if theme:
            # Thématique spécifique
            theme_upper = theme.upper()
            objection_dict_name = f"OBJECTIONS_{theme_upper}"

            if hasattr(objections_database, objection_dict_name):
                all_objections[theme] = getattr(objections_database, objection_dict_name)
                logger.info(f"📋 Theme: {theme}")
            else:
                logger.error(f"❌ Theme '{theme}' not found in objections_database")
                return False
        else:
            # Toutes les thématiques
            # Collecter tous les dicts OBJECTIONS_*
            for attr_name in dir(objections_database):
                if attr_name.startswith("OBJECTIONS_"):
                    theme_name = attr_name.replace("OBJECTIONS_", "").lower()
                    all_objections[theme_name] = getattr(objections_database, attr_name)

            logger.info(f"📋 Themes: {', '.join(all_objections.keys())}")

        # Compter total
        total_count = sum(len(obj_dict) for obj_dict in all_objections.values())
        logger.info(f"📊 Total objections: {total_count}")

        if total_count == 0:
            logger.warning("⚠️  No objections found")
            return False

        # Estimer temps (2s par objection environ)
        estimated_time_minutes = (total_count * 2) / 60
        logger.info(f"⏱️  Estimated time: {estimated_time_minutes:.1f} minutes")

        print(f"\n⚠️  This will generate {total_count} TTS files (~{estimated_time_minutes:.0f} minutes)")
        print(f"   Continue? (y/n): ", end='')

        confirm = input().strip().lower()
        if confirm != 'y':
            logger.info("❌ Generation cancelled by user")
            return False

        # Générer TTS
        logger.info(f"\n🎤 Generating TTS with voice '{voice_name}'...")

        import time
        start_time = time.time()
        success_count = 0
        failed_count = 0

        for theme_name, objections_dict in all_objections.items():
            logger.info(f"\n📂 Processing theme: {theme_name.upper()}")
            logger.info(f"   {len(objections_dict)} objections")

            for i, (objection, response) in enumerate(objections_dict.items(), 1):
                # Créer nom de fichier safe
                # Format: theme_objection_number.wav
                safe_name = self._sanitize_filename(objection)
                filename = f"{theme_name}_{i:03d}_{safe_name}.wav"
                output_file = output_dir / filename

                # Skip si existe déjà
                if output_file.exists():
                    logger.debug(f"   ⏭️  Skip (exists): {filename}")
                    success_count += 1
                    continue

                # Générer TTS
                try:
                    success = self.tts.generate_speech(
                        text=response,
                        output_path=str(output_file),
                        voice_name=voice_name
                    )

                    if success:
                        success_count += 1

                        # Log tous les 10 fichiers
                        if success_count % 10 == 0:
                            elapsed = time.time() - start_time
                            rate = success_count / elapsed
                            remaining = (total_count - success_count) / rate if rate > 0 else 0

                            logger.info(f"   ✅ Progress: {success_count}/{total_count} "
                                      f"({success_count*100//total_count}%) - "
                                      f"ETA: {remaining/60:.1f}min")
                    else:
                        failed_count += 1
                        logger.warning(f"   ⚠️  Failed: {filename}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"   ❌ Error generating {filename}: {e}")

        # Statistiques finales
        elapsed_time = time.time() - start_time

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ TTS Generation completed!")
        logger.info(f"{'='*60}")
        logger.info(f"📊 Statistics:")
        logger.info(f"   Total: {total_count} objections")
        logger.info(f"   Success: {success_count}")
        logger.info(f"   Failed: {failed_count}")
        logger.info(f"   Time: {elapsed_time/60:.1f} minutes")
        logger.info(f"   Rate: {success_count/elapsed_time:.1f} files/sec")
        logger.info(f"📁 Output: {output_dir}")

        return success_count > 0

    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """
        Nettoie un texte pour en faire un nom de fichier valide

        Args:
            text: Texte à nettoyer
            max_length: Longueur max

        Returns:
            Nom de fichier safe
        """
        import re

        # Convertir en minuscules
        safe = text.lower()

        # Remplacer espaces et caractères spéciaux par _
        safe = re.sub(r'[^a-z0-9]+', '_', safe)

        # Retirer _ en début/fin
        safe = safe.strip('_')

        # Limiter longueur
        if len(safe) > max_length:
            safe = safe[:max_length]

        return safe


def interactive_select_voice(available_voices: List[str]) -> Optional[str]:
    """
    Sélection interactive de la voix à cloner

    Args:
        available_voices: Liste des voix disponibles

    Returns:
        Nom de la voix sélectionnée ou None
    """
    if not available_voices:
        print("\n❌ No voices found in voices/ directory")
        print("💡 Create a folder in voices/ and add audio files (10+ files of 6-10 seconds recommended)")
        return None

    print("\n📋 Available voices:")
    for i, voice in enumerate(available_voices, 1):
        print(f"  {i}. {voice}")

    print(f"\n🎤 Select voice to clone (1-{len(available_voices)}) or 'q' to quit: ", end='')

    choice = input().strip()

    if choice.lower() == 'q':
        return None

    try:
        index = int(choice) - 1
        if 0 <= index < len(available_voices):
            return available_voices[index]
        else:
            print(f"❌ Invalid choice: {choice}")
            return None
    except ValueError:
        print(f"❌ Invalid input: {choice}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Clone voice for TTS (Multi-Voice)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--voice",
        help="Voice name to clone (if not specified, interactive mode)"
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Skip TTS generation for objections/FAQ"
    )
    parser.add_argument(
        "--theme",
        help="Theme for TTS generation (finance, crypto, energie, etc.) - default: all themes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing voice"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🎤  VOICE CLONER - MiniBotPanel v3")
    print("="*60)

    # Initialiser cloner
    cloner = VoiceCloner()

    # Détecter voix disponibles
    available_voices = cloner.detect_available_voices()

    # Sélection voix
    if args.voice:
        voice_name = args.voice
        if voice_name not in available_voices:
            logger.error(f"❌ Voice '{voice_name}' not found in voices/")
            logger.info(f"💡 Available voices: {', '.join(available_voices) if available_voices else 'None'}")
            return
    else:
        # Mode interactif
        voice_name = interactive_select_voice(available_voices)
        if not voice_name:
            return

    # Traiter voix
    success = cloner.process_voice_folder(voice_name, force=args.force)

    if not success:
        logger.error("\n❌ Voice cloning failed")
        return

    # Générer TTS pour objections/FAQ (sauf si skip)
    if not args.skip_tts:
        theme = args.theme if args.theme else None
        tts_success = cloner.generate_tts_for_objections(voice_name, theme=theme)

        if tts_success:
            print("\n" + "="*60)
            print(f"✅ Voice cloning + TTS generation completed!")
            print(f"📁 Voice: voices/{voice_name}/")
            print(f"📁 TTS files: audio/tts/{voice_name}/")
            print("="*60)
        else:
            print("\n" + "="*60)
            print(f"✅ Voice cloning completed!")
            print(f"⚠️  TTS generation failed or skipped")
            print(f"📁 Voice saved: voices/{voice_name}/")
            print("="*60)
    else:
        print("\n" + "="*60)
        print(f"✅ Voice cloning completed successfully!")
        print(f"📁 Voice saved: voices/{voice_name}/")
        print("="*60)


if __name__ == "__main__":
    main()
