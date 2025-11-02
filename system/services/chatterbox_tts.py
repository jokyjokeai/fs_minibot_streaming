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
            "language": "fr",  # Langue par défaut (en=English, fr=French)
            "sample_rate": 24000,  # Chatterbox génère en 24kHz natif
            "output_format": "wav",

            # Paramètres VALIDÉS selon docs officielles Resemble AI
            # SEULEMENT exaggeration et cfg_weight sont supportés
            "exaggeration": 0.4,      # 0.3-0.5 = naturel (0.5 = default)
            "cfg_weight": 0.5,        # 0.5 = default équilibré, 0.3 = faster speaker, 0.7 = slower
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

            # IMPORTANT: Forcer CPU si pas de GPU disponible
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"

            # Charger modèle anglais (base)
            self.tts_model = ChatterboxTTS.from_pretrained(
                device=device
            )

            # Charger modèle multilingue pour français
            # Fix: Chatterbox a un bug où il charge en CUDA même sur CPU
            # On doit patcher torch.load temporairement
            original_load = torch.load
            def patched_load(*args, **kwargs):
                kwargs['map_location'] = device
                return original_load(*args, **kwargs)

            torch.load = patched_load
            try:
                self.mtl_model = ChatterboxMultilingualTTS.from_pretrained(
                    device=device
                )
            finally:
                torch.load = original_load

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

            # Paramètres VALIDÉS selon best practices Resemble AI
            # exaggeration: 0.3-0.5 = naturel, 0.5 = default
            # cfg_weight: 0.5 = default, 0.3 = faster speaker, 0.7 = slower
            exag = exaggeration if exaggeration is not None else self.tts_config["exaggeration"]
            cfg = cfg_weight if cfg_weight is not None else self.tts_config["cfg_weight"]

            # Générer avec voice cloning
            # Note: Chatterbox supporte seulement exaggeration et cfg_weight
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

    def clone_voice(self, audio_path, voice_name: str, use_few_shot: bool = True, max_files: int = 30) -> bool:
        """
        Clone une voix avec few-shot learning (meilleure qualité).

        Chatterbox supporte few-shot: on peut passer plusieurs fichiers
        et il va moyenner les caractéristiques vocales (comme ElevenLabs).

        Args:
            audio_path: Chemin fichier audio OU liste de fichiers
            voice_name: Nom de la voix (ex: julie, marc)
            use_few_shot: Si True, utilise plusieurs fichiers (recommandé)
            max_files: Nombre max de fichiers à utiliser (défaut: 10)

        Returns:
            True si succès
        """
        try:
            import shutil
            import torchaudio

            voices_dir = config.VOICES_DIR
            voice_folder = voices_dir / voice_name
            voice_folder.mkdir(parents=True, exist_ok=True)

            # Convertir en liste
            if isinstance(audio_path, (list, tuple)):
                audio_files = list(audio_path)
            else:
                audio_files = [audio_path]

            logger.info(f"🎤 Cloning voice '{voice_name}' from {len(audio_files)} file(s)...")

            # Few-shot: utiliser plusieurs fichiers
            if use_few_shot and len(audio_files) > 1:
                logger.info(f"🎯 Few-shot mode: Using {min(len(audio_files), max_files)} best files")

                # Limiter au nombre max
                selected_files = audio_files[:max_files]

                # Convertir et normaliser tous les fichiers
                # Best practice: 44.1kHz selon docs officielles (24kHz minimum)
                logger.info(f"📊 Converting to 44100Hz mono + normalizing to -3dB...")
                normalized_files = []
                TARGET_SR = 44100  # Optimal quality (was 22050)

                for i, audio_file in enumerate(selected_files, 1):
                    # Charger audio
                    waveform, sr = torchaudio.load(str(audio_file))

                    # 1. Convertir en mono si nécessaire
                    if waveform.shape[0] > 1:
                        waveform = torch.mean(waveform, dim=0, keepdim=True)

                    # 2. Resample vers 22050Hz si nécessaire
                    if sr != TARGET_SR:
                        resampler = torchaudio.transforms.Resample(sr, TARGET_SR)
                        waveform = resampler(waveform)
                        sr = TARGET_SR

                    # 3. Normaliser au pic à -3dB
                    peak = waveform.abs().max()
                    if peak > 0:
                        target_peak = 10 ** (-3.0 / 20.0)  # -3dB en linéaire
                        waveform = waveform * (target_peak / peak)

                    # Sauvegarder temporairement
                    import tempfile
                    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(voice_folder))
                    torchaudio.save(temp_file.name, waveform, sr)
                    normalized_files.append(temp_file.name)

                    logger.info(f"   [{i}/{len(selected_files)}] Converted & normalized: {Path(audio_file).name}")

                logger.info(f"✅ {len(normalized_files)} files normalized and ready")

                # Few-shot: CONCATÉNER tous les fichiers en un seul
                logger.info(f"🔗 Concatenating {len(normalized_files)} files for few-shot...")

                combined_audio = []
                combined_sr = None

                for i, temp_file in enumerate(normalized_files, 1):
                    waveform, sr = torchaudio.load(temp_file)
                    if combined_sr is None:
                        combined_sr = sr
                    elif sr != combined_sr:
                        # Resample si nécessaire
                        resampler = torchaudio.transforms.Resample(sr, combined_sr)
                        waveform = resampler(waveform)

                    combined_audio.append(waveform)
                    logger.info(f"   [{i}/{len(normalized_files)}] Added: {Path(temp_file).name}")

                # Concaténer tous les audios
                concatenated = torch.cat(combined_audio, dim=1)

                # Sauvegarder comme reference.wav
                reference_path = voice_folder / "reference.wav"
                torchaudio.save(str(reference_path), concatenated, combined_sr)

                logger.info(f"✅ Combined audio: {concatenated.shape[1] / combined_sr:.1f}s total")

                # Utiliser le fichier combiné
                audio_prompt_path = str(reference_path)

            else:
                # Zero-shot: un seul fichier
                logger.info(f"⚡ Zero-shot mode: Using single file")
                source_file = audio_files[0]

                # Copier fichier de référence (seulement si différent)
                reference_path = voice_folder / "reference.wav"
                if Path(source_file).resolve() != reference_path.resolve():
                    shutil.copy2(source_file, reference_path)
                    logger.info(f"   Copied reference.wav from {Path(source_file).name}")
                else:
                    logger.info(f"   Using existing reference.wav")

                audio_prompt_path = str(reference_path)

            # Générer test audio
            logger.info(f"🎵 Generating test audio with cloned voice...")

            # Charger modèle si nécessaire
            if not self.mtl_model:
                self._load_model()

            # Paramètres optimisés pour voix naturelle (appels téléphoniques)
            test_text = "Bonjour, ceci est un test de clonage vocal avec Chatterbox. La qualité devrait être excellente."
            test_output = voice_folder / "test_clone.wav"

            wav = self.mtl_model.generate(
                test_text,
                language_id="fr",
                audio_prompt_path=audio_prompt_path,  # Peut être str ou list!
                exaggeration=0.35,      # Voix naturelle et professionnelle
                cfg_weight=0.45,        # Bon équilibre vitesse/qualité
            )

            ta.save(str(test_output), wav, self.mtl_model.sr)

            # Nettoyer fichiers temporaires si few-shot
            if use_few_shot and len(audio_files) > 1:
                for temp_file in normalized_files:
                    if temp_file != str(reference_path):
                        try:
                            Path(temp_file).unlink()
                        except:
                            pass

            # Sauvegarder metadata
            metadata = {
                "voice_name": voice_name,
                "model": "Chatterbox TTS (few-shot)" if use_few_shot and len(audio_files) > 1 else "Chatterbox TTS (zero-shot)",
                "num_files": len(audio_files) if use_few_shot else 1,
                "reference_file": str(reference_path.name),
                "sample_rate": self.mtl_model.sr,
                "parameters": {
                    "exaggeration": 0.35,
                    "cfg_weight": 0.45,
                },
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            metadata_path = voice_folder / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"✅ Voice '{voice_name}' cloned successfully!")
            logger.info(f"📁 Saved to: {voice_folder}")
            logger.info(f"📄 Metadata: metadata.json")
            if use_few_shot and len(audio_files) > 1:
                logger.info(f"🎯 Few-shot: {len(audio_files)} files averaged")

            return True

        except Exception as e:
            logger.error(f"❌ Voice cloning failed: {e}", exc_info=True)
            return False
