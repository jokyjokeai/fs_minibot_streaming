#!/usr/bin/env python3
"""
Simple Voice Cloning with Chatterbox - MiniBotPanel v3

Utilise reference.wav (généré par youtube_extract.py) pour cloner une voix
et générer les TTS d'objections/FAQ.

Usage:
    python clone_voice_simple.py --voice ss
    python clone_voice_simple.py --voice ss --skip-tts
"""

import argparse
import logging
import time
from pathlib import Path
from typing import List
import json

from system.config import config
from system.services.chatterbox_tts import ChatterboxTTSService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleVoiceCloner:
    """Cloner de voix simplifié - utilise reference.wav directement"""

    def __init__(self):
        """Initialise le cloner"""
        self.voices_dir = Path(config.VOICES_DIR)
        self.audio_dir = Path(config.AUDIO_DIR)
        self.tts = None

        self.voices_dir.mkdir(exist_ok=True)
        self.audio_dir.mkdir(exist_ok=True)

        logger.info("🎤 SimpleVoiceCloner initialized")

    def detect_available_voices(self) -> List[str]:
        """
        Détecte les voix avec reference.wav disponible.

        Returns:
            Liste des noms de voix
        """
        voices = []

        if not self.voices_dir.exists():
            return voices

        for voice_dir in self.voices_dir.iterdir():
            if voice_dir.is_dir():
                reference_file = voice_dir / "reference.wav"
                if reference_file.exists():
                    voices.append(voice_dir.name)

        return sorted(voices)

    def init_tts(self):
        """Initialise le service TTS"""
        if not self.tts:
            logger.info("🎙️ Initializing Chatterbox TTS service...")
            self.tts = ChatterboxTTSService()

            if not self.tts.is_available:
                logger.error("❌ Chatterbox TTS not available")
                logger.error("   Install with: pip install git+https://github.com/resemble-ai/chatterbox.git")
                return False

        return True

    def clone_voice(self, voice_name: str, force: bool = False) -> bool:
        """
        Clone une voix depuis reference.wav.

        Args:
            voice_name: Nom de la voix
            force: Force le re-clonage

        Returns:
            True si succès
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎤  CLONING VOICE: {voice_name}")
        logger.info(f"{'='*60}")

        voice_folder = self.voices_dir / voice_name
        reference_file = voice_folder / "reference.wav"

        if not reference_file.exists():
            logger.error(f"❌ reference.wav not found in voices/{voice_name}/")
            logger.error(f"   Run: python youtube_extract.py")
            return False

        # Vérifier si déjà cloné
        test_file = voice_folder / "test_clone.wav"
        metadata_file = voice_folder / "metadata.json"

        if not force and test_file.exists():
            logger.info(f"✅ Voice '{voice_name}' already cloned")
            logger.info(f"   Use --force to re-clone")

            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    logger.info(f"📄 Cloned on: {metadata.get('created_at', 'Unknown')}")

            return True

        # Initialiser TTS
        if not self.init_tts():
            return False

        # Cloner avec Chatterbox
        logger.info(f"\n🔬 Cloning voice with Chatterbox TTS...")
        logger.info(f"📁 Source: reference.wav")

        success = self.tts.clone_voice(
            str(reference_file),
            voice_name,
            use_few_shot=False  # Zero-shot depuis reference.wav
        )

        if success:
            logger.info(f"\n✅ Voice '{voice_name}' cloned successfully!")
            logger.info(f"📁 Saved to: {voice_folder}")
            logger.info(f"📄 Files created:")
            logger.info(f"   - test_clone.wav (quality test)")
            logger.info(f"   - metadata.json (voice info)")
        else:
            logger.error(f"❌ Failed to clone voice '{voice_name}'")

        return success

    def generate_tts_objections(self, voice_name: str, themes: List[str] = None):
        """
        Génère les fichiers TTS pour objections/FAQ.

        Args:
            voice_name: Nom de la voix
            themes: Liste des thèmes (None = tous)
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔊 Generating TTS for objections/FAQ...")
        logger.info(f"{'='*60}")

        # Initialiser TTS
        if not self.init_tts():
            return False

        # Charger la voix
        logger.info(f"📥 Loading voice '{voice_name}'...")
        if not self.tts.load_voice(voice_name):
            logger.error(f"❌ Failed to load voice '{voice_name}'")
            return False

        # Importer objections database
        try:
            from system import objections_database
        except ImportError:
            logger.error("❌ Could not import objections_database")
            return False

        # Collecter objections
        all_objections = {}

        if themes:
            for theme in themes:
                objections_list = objections_database.get_objections_by_theme(theme)
                if objections_list:
                    all_objections[theme] = objections_list
            logger.info(f"📋 Themes: {', '.join(themes)}")
        else:
            all_themes = objections_database.get_all_themes()
            for theme_name in all_themes:
                objections_list = objections_database.get_objections_by_theme(theme_name)
                if objections_list:
                    all_objections[theme_name] = objections_list
            logger.info(f"📋 Themes: {', '.join(all_objections.keys())}")

        total_count = sum(len(obj_list) for obj_list in all_objections.values())
        logger.info(f"📊 Total objections: {total_count}")

        if total_count == 0:
            logger.warning("⚠️  No objections found")
            return False

        # Créer dossier de sortie
        output_dir = self.audio_dir / "tts" / voice_name
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📁 Output directory: {output_dir}")

        # Estimer temps
        estimated_time_minutes = (total_count * 10) / 60
        logger.info(f"⏱️  Estimated time: {estimated_time_minutes:.1f} minutes\n")

        success_count = 0
        failed_count = 0
        total_time = 0

        for theme_name, objections_list in all_objections.items():
            logger.info(f"\n📂 Processing theme: {theme_name.upper()}")
            logger.info(f"   {len(objections_list)} objections")

            for i, objection_entry in enumerate(objections_list, 1):
                # Extraire la réponse
                if hasattr(objection_entry, 'response'):
                    response_text = objection_entry.response
                elif isinstance(objection_entry, str):
                    response_text = objection_entry
                else:
                    logger.warning(f"   ⚠️  Skipping invalid entry")
                    continue

                # Créer nom de fichier
                response_preview = response_text[:30]
                safe_name = self._sanitize_filename(response_preview)
                filename = f"{theme_name}_{i:03d}_{safe_name}.wav"
                output_file = output_dir / filename

                # Skip si existe
                if output_file.exists():
                    logger.info(f"   [{i}/{len(objections_list)}] ⏭️  Skip (exists): {filename}")
                    success_count += 1
                    continue

                start_time = time.time()

                # Générer TTS
                result = self.tts.synthesize_with_voice(
                    response_text,
                    voice_name=voice_name,
                    output_file=str(output_file)
                )

                gen_time = time.time() - start_time
                total_time += gen_time

                if result:
                    logger.info(f"   [{i}/{len(objections_list)}] ✅ Generated in {gen_time:.1f}s: {filename}")
                    success_count += 1
                else:
                    logger.error(f"   [{i}/{len(objections_list)}] ❌ Failed: {filename}")
                    failed_count += 1

        # Statistiques
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ TTS Generation complete!")
        logger.info(f"{'='*60}")
        logger.info(f"📊 Success: {success_count}/{total_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info(f"⏱️  Total time: {total_time / 60:.1f} minutes")
        logger.info(f"⚡ Avg time per file: {total_time / max(success_count, 1):.1f}s")

        return failed_count == 0

    def _sanitize_filename(self, text: str) -> str:
        """Crée un nom de fichier safe"""
        import re
        safe = re.sub(r'[^\w\s-]', '', text)
        safe = re.sub(r'\s+', '_', safe)
        return safe[:40].lower()


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Simple voice cloning with Chatterbox")
    parser.add_argument("--voice", type=str, help="Nom de la voix à cloner")
    parser.add_argument("--skip-tts", action="store_true", help="Ne pas générer les fichiers TTS")
    parser.add_argument("--force", action="store_true", help="Force le re-clonage")
    parser.add_argument("--theme", type=str, help="Thème spécifique pour TTS")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🎤  SIMPLE VOICE CLONER - Chatterbox TTS")
    print("="*60)

    cloner = SimpleVoiceCloner()

    # Détecter voix disponibles
    available_voices = cloner.detect_available_voices()

    if not available_voices:
        logger.error("❌ No voices with reference.wav found in voices/")
        logger.info("💡 Run: python youtube_extract.py")
        return 1

    logger.info(f"📁 Available voices: {', '.join(available_voices)}")

    # Sélectionner voix
    if args.voice:
        voice_name = args.voice
        if voice_name not in available_voices:
            logger.error(f"❌ Voice '{voice_name}' not found")
            logger.info(f"💡 Available: {', '.join(available_voices)}")
            return 1
    else:
        if len(available_voices) == 1:
            voice_name = available_voices[0]
            logger.info(f"\n🎯 Using voice: {voice_name}")
        else:
            logger.info("\n🎤 Select a voice:")
            for i, v in enumerate(available_voices, 1):
                logger.info(f"   {i}. {v}")

            try:
                choice = input("\nEnter number: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(available_voices):
                    voice_name = available_voices[idx]
                else:
                    logger.error("❌ Invalid choice")
                    return 1
            except (ValueError, KeyboardInterrupt):
                logger.error("\n❌ Cancelled")
                return 1

    # Cloner voix
    if not cloner.clone_voice(voice_name, force=args.force):
        return 1

    # Demander si générer TTS
    if not args.skip_tts:
        try:
            logger.info("\n" + "="*60)
            response = input("🔊 Generate TTS for objections/FAQ? (y/N): ").strip().lower()
            if response in ['y', 'yes', 'o', 'oui']:
                themes = [args.theme] if args.theme else None
                cloner.generate_tts_objections(voice_name, themes)
            else:
                logger.info("⏭️  Skipped TTS generation")
        except KeyboardInterrupt:
            logger.info("\n⏭️  Skipped TTS generation")

    logger.info("\n✅ Done!")
    return 0


if __name__ == "__main__":
    exit(main())
