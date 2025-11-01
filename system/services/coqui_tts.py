"""
Coqui TTS Service - MiniBotPanel v3

Service de synthèse vocale (Text-to-Speech) avec clonage vocal.
Adapté de tts_voice_clone.py pour FreeSWITCH.

Technologie: Coqui TTS (offline, multilingue)

Fonctionnalités:
- Génération audio depuis texte
- Voice cloning (clonage vocal)
- Support GPU si disponible
- Cache audio pour performance
- Embeddings vocaux pré-calculés

Utilisation:
    from system.services.coqui_tts import CoquiTTS

    tts = CoquiTTS()

    # Générer audio
    audio_file = tts.synthesize("Bonjour, comment allez-vous?")
    print(f"Audio saved to: {audio_file}")

    # Avec voice cloning
    audio_file = tts.synthesize_with_voice("Merci beaucoup", reference_voice="voice.wav")
"""

import json
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

# Import TTS avec fallback
try:
    from TTS.api import TTS
    import torch
    TTS_AVAILABLE = True
    logger.info("✅ Coqui TTS imported successfully")
except ImportError as e:
    TTS_AVAILABLE = False
    logger.warning(f"⚠️ Coqui TTS not available: {e}")
    # Mock pour éviter erreurs
    class TTS:
        def __init__(self, model): pass
        def to(self, device): return self


class CoquiTTS:
    """
    Service de synthèse vocale Coqui TTS avec clonage vocal.
    Adapté de VoiceCloneService pour FreeSWITCH.
    """

    def __init__(self):
        """Initialise le service Coqui TTS."""
        logger.info("Initializing CoquiTTS...")

        self.tts_model = None
        self.is_available = TTS_AVAILABLE
        self.reference_voice_path = None
        self.voice_characteristics = {}

        # Configuration
        self.tts_config = {
            "model_name": config.COQUI_MODEL,
            "device": "cpu",
            "language": "fr",
            "sample_rate": 16000,  # Compatible FreeSWITCH
            "output_format": "wav"
        }

        # Statistiques
        self.stats = {
            "total_generations": 0,
            "avg_generation_time": 0.0,
            "voice_cloned": False,
            "reference_audio_duration": 0.0
        }

        if not self.is_available:
            logger.warning("🚫 CoquiTTS not available - missing dependencies")
            return

        # Charger modèle
        if config.PRELOAD_MODELS:
            self._load_model()

        logger.info(f"{'✅' if self.is_available else '❌'} CoquiTTS initialized")

    def _load_model(self):
        """Charge le modèle TTS en mémoire."""
        try:
            logger.info(f"🎙️ Loading Coqui TTS model: {self.tts_config['model_name']}")

            # Détecter GPU si disponible
            if config.COQUI_USE_GPU and 'torch' in globals() and torch.cuda.is_available():
                self.tts_config["device"] = "cuda"
                logger.info("🚀 GPU detected, using CUDA acceleration")

            start_time = time.time()

            # Charger modèle XTTS v2 (multilingue avec clonage)
            self.tts_model = TTS(self.tts_config["model_name"]).to(self.tts_config["device"])

            load_time = time.time() - start_time
            logger.info(f"✅ Coqui TTS model loaded in {load_time:.2f}s")

            # Préparer voix de référence
            self._prepare_reference_voice()

            self.is_available = True

        except Exception as e:
            logger.error(f"❌ Failed to load Coqui TTS model: {e}", exc_info=True)
            self.is_available = False

    def _prepare_reference_voice(self):
        """Prépare la voix de référence pour clonage vocal"""
        try:
            audio_dir = config.AUDIO_DIR
            voices_dir = config.VOICES_DIR
            voices_dir.mkdir(exist_ok=True)

            # Collecter fichiers audio de référence
            reference_files = []

            # Chercher audio_texts.json pour métadonnées
            audio_texts_path = audio_dir.parent / "audio_texts.json"
            if audio_texts_path.exists():
                with open(audio_texts_path, 'r', encoding='utf-8') as f:
                    audio_data = json.load(f)

                for key, info in audio_data.items():
                    duration = info.get("duration", 0)
                    audio_file = audio_dir / info.get("file", f"{key}.wav")

                    # Prendre fichiers > 3 secondes pour bon embedding
                    if audio_file.exists() and duration > 3.0:
                        reference_files.append({
                            "path": str(audio_file),
                            "duration": duration,
                            "text": info.get("text", ""),
                            "key": key
                        })

            if reference_files:
                # Trier par durée et prendre les 5 meilleurs
                reference_files.sort(key=lambda x: x["duration"], reverse=True)
                best_references = reference_files[:5]

                # Utiliser le plus long comme référence principale
                self.reference_voice_path = best_references[0]["path"]

                self.voice_characteristics = {
                    "total_references": len(best_references),
                    "total_duration": sum(ref["duration"] for ref in best_references),
                    "best_reference": best_references[0]["key"],
                    "references": best_references
                }

                total_duration = sum(ref["duration"] for ref in best_references)
                self.stats["reference_audio_duration"] = total_duration
                self.stats["voice_cloned"] = True

                logger.info(f"🎯 Voice references prepared: {len(best_references)} files ({total_duration:.1f}s total)")
                logger.info(f"📁 Main reference: {best_references[0]['key']} ({best_references[0]['duration']:.1f}s)")
            else:
                logger.warning("⚠️ No reference audio files found for voice cloning")

        except Exception as e:
            logger.error(f"❌ Failed to prepare reference voice: {e}")

    def synthesize(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
        """
        Génère audio depuis texte avec voix par défaut.

        Args:
            text: Texte à synthétiser
            output_file: Chemin fichier sortie (optionnel)

        Returns:
            Chemin vers fichier audio généré
        """
        if not self.is_available or not self.tts_model:
            logger.error("Coqui TTS not available")
            return None

        try:
            # Utiliser voice cloning si référence disponible
            if self.reference_voice_path:
                return self.synthesize_with_voice(text, self.reference_voice_path, output_file)

            # Sinon synthèse simple
            if not output_file:
                output_file = tempfile.mktemp(suffix=".wav", dir=config.AUDIO_DIR)

            start_time = time.time()

            self.tts_model.tts_to_file(
                text=text,
                file_path=output_file,
                language=self.tts_config["language"]
            )

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
        reference_voice: str = None,
        output_file: Optional[str] = None
    ) -> Optional[str]:
        """
        Génère audio avec clonage vocal.

        Args:
            text: Texte à synthétiser
            reference_voice: Fichier audio de référence (None = utiliser référence par défaut)
            output_file: Chemin fichier sortie (optionnel)

        Returns:
            Chemin vers fichier audio généré
        """
        if not self.is_available or not self.tts_model:
            logger.error("Coqui TTS not available")
            return None

        try:
            # Utiliser référence par défaut si non spécifiée
            voice_ref = reference_voice or self.reference_voice_path

            if not voice_ref or not Path(voice_ref).exists():
                logger.error(f"Reference voice not found: {voice_ref}")
                return self.synthesize(text, output_file)

            if not output_file:
                output_file = tempfile.mktemp(suffix=".wav", dir=config.AUDIO_DIR)

            start_time = time.time()

            # Synthèse avec clonage (XTTS)
            self.tts_model.tts_to_file(
                text=text,
                file_path=output_file,
                speaker_wav=voice_ref,
                language=self.tts_config["language"]
            )

            generation_time = time.time() - start_time

            # Update stats
            self.stats["total_generations"] += 1
            self.stats["avg_generation_time"] = (
                (self.stats["avg_generation_time"] * (self.stats["total_generations"] - 1) + generation_time)
                / self.stats["total_generations"]
            )

            logger.info(f"✅ TTS cloned voice generated in {generation_time:.2f}s: {output_file}")

            return output_file

        except Exception as e:
            logger.error(f"❌ TTS voice cloning error: {e}", exc_info=True)
            return None

    def clone_voice(self, audio_path: str, voice_name: str) -> bool:
        """
        Clone une voix et sauvegarde l'embedding de manière persistante.

        Args:
            audio_path: Chemin vers fichier audio de référence
            voice_name: Nom de la voix (ex: julie, marc)

        Returns:
            True si succès, False sinon
        """
        if not self.is_available or not self.tts_model:
            logger.error("Coqui TTS not available")
            return False

        try:
            audio_file = Path(audio_path)
            if not audio_file.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            # Créer dossier voix
            voice_dir = config.VOICES_DIR / voice_name
            voice_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"🎤 Cloning voice '{voice_name}' from {audio_path}...")

            # Copier fichier référence
            reference_path = voice_dir / "reference.wav"
            import shutil
            shutil.copy2(audio_path, reference_path)

            # Générer embeddings (XTTS calcule automatiquement depuis speaker_wav)
            # On va créer un fichier test pour vérifier que ça fonctionne
            test_text = "Ceci est un test de clonage vocal."
            test_output = voice_dir / "test_clone.wav"

            start_time = time.time()

            self.tts_model.tts_to_file(
                text=test_text,
                file_path=str(test_output),
                speaker_wav=str(reference_path),
                language=self.tts_config["language"]
            )

            clone_time = time.time() - start_time

            # Calculer embedding speaker (pour sauvegarde future)
            # Note: XTTS ne permet pas d'extraire directement l'embedding
            # On crée un fichier embeddings.pth comme marqueur de voix clonée
            # Le vrai embedding est calculé à la volée depuis reference.wav
            embeddings_path = voice_dir / "embeddings.pth"
            import torch
            marker_data = {
                "voice_name": voice_name,
                "reference_wav": str(reference_path.name),
                "created_at": time.time(),
                "note": "XTTS calculates embeddings on-the-fly from reference.wav"
            }
            torch.save(marker_data, embeddings_path)
            logger.info(f"📦 Embeddings marker saved: {embeddings_path.name}")

            # Créer métadonnées
            import json
            from datetime import datetime

            metadata = {
                "voice_name": voice_name,
                "reference_audio": str(reference_path.name),
                "created_at": datetime.now().isoformat(),
                "model": self.tts_config["model_name"],
                "language": self.tts_config["language"],
                "test_audio": str(test_output.name),
                "clone_time": clone_time,
                "audio_duration": self._get_audio_duration(reference_path)
            }

            metadata_path = voice_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Voice '{voice_name}' cloned successfully in {clone_time:.2f}s")
            logger.info(f"📁 Saved to: {voice_dir}")
            logger.info(f"🎵 Reference: {reference_path.name}")
            logger.info(f"📄 Metadata: {metadata_path.name}")

            return True

        except Exception as e:
            logger.error(f"❌ Voice cloning failed: {e}", exc_info=True)
            return False

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Retourne la durée d'un fichier audio en secondes"""
        try:
            import wave
            with wave.open(str(audio_path), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
                return round(duration, 2)
        except:
            return 0.0

    def generate(self, text: str, voice_name: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Génère audio TTS en utilisant une voix clonée par son nom.

        Args:
            text: Texte à synthétiser
            voice_name: Nom de la voix clonée (ex: julie)
            output_path: Chemin fichier sortie (optionnel)

        Returns:
            Chemin vers fichier audio généré
        """
        if not self.is_available or not self.tts_model:
            logger.error("Coqui TTS not available")
            return None

        try:
            # Charger voix depuis voices/
            voice_dir = config.VOICES_DIR / voice_name

            if not voice_dir.exists():
                logger.error(f"Voice '{voice_name}' not found in {config.VOICES_DIR}")
                return None

            # Charger métadonnées
            metadata_path = voice_dir / "metadata.json"
            if not metadata_path.exists():
                logger.error(f"Voice metadata not found: {metadata_path}")
                return None

            import json
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Récupérer fichier référence
            reference_file = voice_dir / metadata.get("reference_audio", "reference.wav")

            if not reference_file.exists():
                logger.error(f"Reference audio not found: {reference_file}")
                return None

            logger.info(f"🎙️ Generating TTS with voice '{voice_name}'...")

            # Générer avec voix clonée
            result = self.synthesize_with_voice(
                text=text,
                reference_voice=str(reference_file),
                output_file=output_path
            )

            if result:
                logger.info(f"✅ TTS generated with voice '{voice_name}': {result}")

            return result

        except Exception as e:
            logger.error(f"❌ Generate with voice '{voice_name}' failed: {e}", exc_info=True)
            return None

    def list_voices(self) -> List[Dict[str, Any]]:
        """Liste toutes les voix clonées disponibles"""
        voices = []

        voices_dir = config.VOICES_DIR
        if not voices_dir.exists():
            return voices

        import json

        for voice_dir in voices_dir.iterdir():
            if not voice_dir.is_dir():
                continue

            metadata_path = voice_dir / "metadata.json"
            if not metadata_path.exists():
                continue

            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                voices.append({
                    "name": voice_dir.name,
                    "created_at": metadata.get("created_at"),
                    "reference_audio": metadata.get("reference_audio"),
                    "audio_duration": metadata.get("audio_duration", 0.0),
                    "path": str(voice_dir)
                })
            except Exception as e:
                logger.warning(f"Failed to load voice metadata: {voice_dir.name}")

        return voices

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques TTS"""
        return {
            **self.stats,
            "is_available": self.is_available,
            "device": self.tts_config["device"],
            "reference_voice": self.reference_voice_path is not None,
            "cloned_voices": len(self.list_voices())
        }
