"""
Chatterbox TTS Service - MiniBotPanel v3

Service de synthèse vocale (Text-to-Speech) avec clonage vocal.
Alternative à Coqui TTS avec qualité supérieure à ElevenLabs.

Technologie: Chatterbox TTS (MIT License, multilingue, emotion control)

Fonctionnalités:
- Génération audio depuis texte
- Voice cloning zero-shot (5 secondes d'audio)
- Support GPU/CPU
- Contrôle des émotions (exaggeration)
- 23 langues supportées
- Watermarking audio intégré

Utilisation:
    from system.services.chatterbox_tts import ChatterboxTTSService

    tts = ChatterboxTTSService()

    # Générer audio
    audio_file = tts.synthesize("Bonjour, comment allez-vous?")
    print(f"Audio saved to: {audio_file}")

    # Avec voice cloning
    audio_file = tts.synthesize_with_voice("Merci beaucoup", voice_name="julie")
"""

import json
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

# Import Chatterbox TTS avec fallback
try:
    import torchaudio as ta
    from chatterbox.tts import ChatterboxTTS
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    import torch
    CHATTERBOX_AVAILABLE = True
    logger.info("✅ Chatterbox TTS imported successfully")
except ImportError as e:
    CHATTERBOX_AVAILABLE = False
    logger.warning(f"⚠️ Chatterbox TTS not available: {e}")
    logger.warning(f"   Install with: pip install chatterbox-tts")


class ChatterboxTTSService:
    """
    Service de synthèse vocale Chatterbox TTS avec clonage vocal.
    Qualité supérieure à XTTS v2 et comparable à ElevenLabs (bat ElevenLabs en blind tests).
    """

    def __init__(self):
        """Initialise le service Chatterbox TTS."""
        logger.info("Initializing ChatterboxTTS...")

        self.tts_model = None
        self.mtl_model = None  # Modèle multilingue
        self.is_available = CHATTERBOX_AVAILABLE

        # Cache des voix clonées (audio_prompt_path pour chaque voix)
        self.cached_voices = {}

        # Configuration
        self.tts_config = {
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "language": "fr",  # Langue par défaut
            "sample_rate": 24000,  # Chatterbox génère en 24kHz
            "output_format": "wav",

            # Paramètres de qualité optimaux
            "exaggeration": 0.5,      # Emotion control (0.25-2.0, défaut 0.5)
            "cfg_weight": 0.5,        # CFG scale pour pacing (0.3-0.7, défaut 0.5)
            "temperature": 0.9,       # Randomness (défaut 0.9)
            "top_p": 0.95,           # Nucleus sampling (défaut 0.95)
            "min_p": 0.1,            # Min probability (défaut 0.1)
            "repetition_penalty": 1.3,  # Anti-répétition (défaut 1.3)
            "n_timesteps": 32,       # Diffusion steps (plus = meilleure qualité)
            "max_new_tokens": 4096,  # Max ~163 secondes
        }

        # Statistiques
        self.stats = {
            "total_generations": 0,
            "avg_generation_time": 0.0,
            "voice_cloned": False,
        }

        if not self.is_available:
            logger.warning("🚫 ChatterboxTTS not available - missing dependencies")
            return

        # Charger modèle
        if config.PRELOAD_MODELS:
            self._load_model()

        logger.info(f"{'✅' if self.is_available else '❌'} ChatterboxTTS initialized")

    def _load_model(self):
        """Charge le modèle Chatterbox TTS en mémoire."""
        if not self.is_available:
            logger.error("Cannot load model - Chatterbox TTS not available")
            return False

        try:
            logger.info(f"🎙️ Loading Chatterbox TTS model...")
            logger.info(f"   Device: {self.tts_config['device']}")

            start_time = time.time()

            # Charger modèle anglais (base)
            self.tts_model = ChatterboxTTS.from_pretrained(
                device=self.tts_config["device"]
            )

            # Charger modèle multilingue pour français
            self.mtl_model = ChatterboxMultilingualTTS.from_pretrained(
                device=self.tts_config["device"]
            )

            load_time = time.time() - start_time
            logger.info(f"✅ Chatterbox TTS models loaded in {load_time:.2f}s")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to load Chatterbox TTS: {e}", exc_info=True)
            self.is_available = False
            return False

    def load_voice(self, voice_name: str) -> bool:
        """
        Charge une voix clonée depuis le dossier voices/.

        Args:
            voice_name: Nom de la voix (ex: 'julie', 'tt')

        Returns:
            True si succès, False sinon
        """
        if not self.is_available:
            logger.error("Chatterbox TTS not available")
            return False

        # Charger modèle si pas déjà fait
        if not self.tts_model or not self.mtl_model:
            if not self._load_model():
                return False

        try:
            voices_dir = config.VOICES_DIR
            voice_folder = voices_dir / voice_name

            if not voice_folder.exists():
                logger.error(f"❌ Voice folder not found: {voice_name}")
                return False

            # Chercher fichier audio de référence
            # Priorité: reference.wav > test_clone.wav > premier fichier cleaned
            reference_files = [
                voice_folder / "reference.wav",
                voice_folder / "test_clone.wav",
            ]

            # Ajouter cleaned files
            cleaned_dir = voice_folder / "cleaned"
            if cleaned_dir.exists():
                cleaned_files = sorted(cleaned_dir.glob("*_cleaned.wav"))
                reference_files.extend(cleaned_files[:1])  # Premier fichier cleaned

            # Trouver premier fichier existant
            audio_prompt_path = None
            for ref_file in reference_files:
                if ref_file.exists():
                    audio_prompt_path = str(ref_file)
                    break

            if not audio_prompt_path:
                logger.error(f"❌ No reference audio found for voice '{voice_name}'")
                logger.error(f"   Looked for: reference.wav, test_clone.wav, or cleaned/*.wav")
                return False

            # Charger en cache
            self.cached_voices[voice_name] = {
                "audio_prompt_path": audio_prompt_path,
                "language": "fr",  # Par défaut français
            }

            logger.info(f"🚀 Voice '{voice_name}' loaded in cache")
            logger.info(f"   Reference: {Path(audio_prompt_path).name}")

            return True

        except Exception as e:
            logger.error(f"❌ Error loading voice '{voice_name}': {e}", exc_info=True)
            return False

    def synthesize(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
        """
        Génère audio depuis texte avec voix par défaut (sans clonage).

        Args:
            text: Texte à synthétiser
            output_file: Chemin fichier sortie (optionnel)

        Returns:
            Chemin vers fichier audio généré
        """
        if not self.is_available or not self.mtl_model:
            logger.error("Chatterbox TTS not available")
            return None

        try:
            if not output_file:
                output_file = tempfile.mktemp(suffix=".wav", dir=config.AUDIO_DIR)

            start_time = time.time()

            # Générer avec modèle multilingue (meilleure qualité pour français)
            wav = self.mtl_model.generate(
                text,
                language_id=self.tts_config["language"],
                exaggeration=self.tts_config["exaggeration"],
                cfg_weight=self.tts_config["cfg_weight"],
            )

            # Sauvegarder
            ta.save(output_file, wav, self.mtl_model.sr)

            generation_time = time.time() - start_time

            # Update stats
            self.stats["total_generations"] += 1
            self.stats["avg_generation_time"] = (
                (self.stats["avg_generation_time"] * (self.stats["total_generations"] - 1) + generation_time)
                / self.stats["total_generations"]
            )

            logger.info(f"✅ TTS generated in {generation_time:.2f}s: {output_file}")

            return output_file

        except Exception as e:
            logger.error(f"❌ TTS synthesis error: {e}", exc_info=True)
            return None

    def synthesize_with_voice(
        self,
        text: str,
        voice_name: str = None,
        output_file: Optional[str] = None,
        exaggeration: Optional[float] = None,
        cfg_weight: Optional[float] = None,
    ) -> Optional[str]:
        """
        Génère audio avec clonage vocal.

        Args:
            text: Texte à synthétiser
            voice_name: Nom de la voix (ex: 'tt') - doit être préchargé avec load_voice()
            output_file: Chemin fichier sortie (optionnel)
            exaggeration: Override emotion control (0.25-2.0, défaut=0.5)
            cfg_weight: Override pacing control (0.3-0.7, défaut=0.5)

        Returns:
            Chemin vers fichier audio généré
        """
        if not self.is_available or not self.mtl_model:
            logger.error("Chatterbox TTS not available")
            return None

        try:
            # Vérifier que voice_name est fourni et chargé
            if not voice_name or voice_name not in self.cached_voices:
                logger.error(f"❌ Voice '{voice_name}' not loaded in cache")
                logger.error(f"   Call load_voice('{voice_name}') first")
                return None

            if not output_file:
                output_file = tempfile.mktemp(suffix=".wav", dir=config.AUDIO_DIR)

            start_time = time.time()

            # Récupérer voice cache
            voice_data = self.cached_voices[voice_name]
            audio_prompt_path = voice_data["audio_prompt_path"]
            language = voice_data.get("language", self.tts_config["language"])

            # Paramètres (avec overrides)
            exag = exaggeration if exaggeration is not None else self.tts_config["exaggeration"]
            cfg = cfg_weight if cfg_weight is not None else self.tts_config["cfg_weight"]

            # Générer avec voice cloning
            wav = self.mtl_model.generate(
                text,
                language_id=language,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exag,
                cfg_weight=cfg,
            )

            # Sauvegarder
            ta.save(output_file, wav, self.mtl_model.sr)

            generation_time = time.time() - start_time

            # Update stats
            self.stats["total_generations"] += 1
            self.stats["avg_generation_time"] = (
                (self.stats["avg_generation_time"] * (self.stats["total_generations"] - 1) + generation_time)
                / self.stats["total_generations"]
            )

            logger.info(f"✅ Voice cloned TTS generated in {generation_time:.2f}s")
            logger.info(f"   Voice: {voice_name}, Exaggeration: {exag}, CFG: {cfg}")

            return output_file

        except Exception as e:
            logger.error(f"❌ Voice cloning synthesis error: {e}", exc_info=True)
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du service."""
        return {
            **self.stats,
            "model": "Chatterbox TTS (MIT)",
            "device": self.tts_config["device"],
            "is_available": self.is_available,
            "cached_voices": list(self.cached_voices.keys()),
        }

    def clone_voice(self, audio_path, voice_name: str) -> bool:
        """
        Clone une voix et sauvegarde le fichier de référence.

        Chatterbox utilise zero-shot voice cloning, donc pas besoin d'embeddings.
        On copie juste le fichier audio de référence.

        Args:
            audio_path: Chemin fichier audio OU liste de fichiers
            voice_name: Nom de la voix (ex: julie, marc)

        Returns:
            True si succès
        """
        try:
            import shutil

            voices_dir = config.VOICES_DIR
            voice_folder = voices_dir / voice_name
            voice_folder.mkdir(parents=True, exist_ok=True)

            # Si liste de fichiers, utiliser le premier (ou faire une moyenne?)
            if isinstance(audio_path, (list, tuple)):
                logger.info(f"🎤 Cloning voice '{voice_name}' from {len(audio_path)} files...")
                logger.info(f"   Using first file as reference: {audio_path[0]}")
                source_file = audio_path[0]
            else:
                logger.info(f"🎤 Cloning voice '{voice_name}' from single file...")
                source_file = audio_path

            # Copier fichier de référence
            reference_path = voice_folder / "reference.wav"
            shutil.copy2(source_file, reference_path)

            # Générer test audio
            logger.info(f"🎵 Generating test audio with cloned voice...")

            # Charger modèle si nécessaire
            if not self.mtl_model:
                self._load_model()

            # Générer test
            test_text = "Bonjour, ceci est un test de clonage vocal avec Chatterbox."
            test_output = voice_folder / "test_clone.wav"

            wav = self.mtl_model.generate(
                test_text,
                language_id="fr",
                audio_prompt_path=str(reference_path),
                exaggeration=0.5,
                cfg_weight=0.5,
            )

            ta.save(str(test_output), wav, self.mtl_model.sr)

            # Sauvegarder metadata
            metadata = {
                "voice_name": voice_name,
                "model": "Chatterbox TTS",
                "reference_file": str(reference_path.name),
                "sample_rate": self.mtl_model.sr,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            metadata_path = voice_folder / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"✅ Voice '{voice_name}' cloned successfully!")
            logger.info(f"📁 Saved to: {voice_folder}")
            logger.info(f"📄 Metadata: metadata.json")

            return True

        except Exception as e:
            logger.error(f"❌ Voice cloning failed: {e}", exc_info=True)
            return False
