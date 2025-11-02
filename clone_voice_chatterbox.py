#!/usr/bin/env python3
"""
Clone Voice with Chatterbox - MiniBotPanel v3

Utilitaire pour cloner des voix avec Chatterbox TTS (meilleure qualité qu'XTTS).

Avantages Chatterbox vs XTTS:
- Bat ElevenLabs en blind tests (63.8% préfèrent Chatterbox)
- Zero-shot voice cloning (pas besoin d'embeddings)
- Seulement 5-10 secondes d'audio requis
- Contrôle des émotions intégré
- MIT License (commercial OK)

Utilisation:
    python clone_voice_chatterbox.py --voice tt
    python clone_voice_chatterbox.py --voice julie --skip-tts
"""

import argparse
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple
import json
import numpy as np

from system.config import config
from system.services.chatterbox_tts import ChatterboxTTSService

# Import audio processing
try:
    import torchaudio
    import noisereduce as nr
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False

# Import UVR (Ultimate Vocal Remover) - optionnel
try:
    from audio_separator.separator import Separator
    UVR_AVAILABLE = True
except ImportError:
    UVR_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChatterboxVoiceCloner:
    """Gestionnaire de clonage de voix avec Chatterbox TTS"""

    def __init__(self):
        """Initialise le cloner"""
        self.voices_dir = Path(config.VOICES_DIR)
        self.audio_dir = Path(config.AUDIO_DIR)
        self.tts = None

        # Créer dossiers si n'existent pas
        self.voices_dir.mkdir(exist_ok=True)
        self.audio_dir.mkdir(exist_ok=True)

        logger.info("🎤 ChatterboxVoiceCloner initialized")

    def detect_available_voices(self) -> List[str]:
        """
        Détecte les dossiers de voix disponibles dans voices/

        Returns:
            Liste des noms de voix disponibles
        """
        voices = []

        if not self.voices_dir.exists():
            return voices

        for voice_dir in self.voices_dir.iterdir():
            if voice_dir.is_dir():
                # Vérifier si des fichiers audio existent
                cleaned_dir = voice_dir / "cleaned"
                has_audio = False

                # Chercher reference.wav ou fichiers cleaned
                if (voice_dir / "reference.wav").exists():
                    has_audio = True
                elif cleaned_dir.exists() and list(cleaned_dir.glob("*.wav")):
                    has_audio = True

                if has_audio:
                    voices.append(voice_dir.name)

        return sorted(voices)

    def init_tts(self):
        """Initialise le service TTS si pas déjà fait"""
        if not self.tts:
            logger.info("🎙️ Initializing Chatterbox TTS service...")
            self.tts = ChatterboxTTSService()

            if not self.tts.is_available:
                logger.error("❌ Chatterbox TTS not available")
                logger.error("   Install with: pip install chatterbox-tts")
                return False

        return True

    def clone_voice(
        self,
        voice_name: str,
        force: bool = False,
        use_scoring: bool = True,
        max_files: int = 10,
        use_uvr: bool = False
    ) -> bool:
        """
        Clone une voix depuis les fichiers audio disponibles.

        Args:
            voice_name: Nom de la voix
            force: Force le re-clonage même si déjà fait
            use_scoring: Utilise scoring pour sélectionner meilleurs fichiers
            max_files: Nombre max de fichiers pour few-shot
            use_uvr: Utiliser UVR pour extraire vocals avant scoring

        Returns:
            True si succès
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎤  CLONING VOICE: {voice_name}")
        logger.info(f"{'='*60}")

        voice_folder = self.voices_dir / voice_name

        if not voice_folder.exists():
            logger.error(f"❌ Voice folder not found: {voice_name}")
            return False

        # Vérifier si déjà cloné
        reference_file = voice_folder / "reference.wav"
        test_file = voice_folder / "test_clone.wav"
        metadata_file = voice_folder / "metadata.json"

        if not force and reference_file.exists() and test_file.exists():
            logger.info(f"✅ Voice '{voice_name}' already cloned")
            logger.info(f"   Use --force to re-clone")

            # Charger metadata
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    logger.info(f"📄 Cloned on: {metadata.get('created_at', 'Unknown')}")
                    logger.info(f"📄 Mode: {metadata.get('mode', 'unknown')}")
                    if 'files_used' in metadata:
                        logger.info(f"📄 Files used: {metadata['files_used']}")

            return True

        # Initialiser TTS
        if not self.init_tts():
            return False

        # Déterminer source audio
        audio_source = None
        use_few_shot = False

        # Stratégie 1: Si use_scoring ET fichiers disponibles → few-shot
        if use_scoring and AUDIO_PROCESSING_AVAILABLE:
            # Chercher dans audio/ OU cleaned/
            cleaned_dir = voice_folder / "cleaned"

            # Priorité 1: Chercher dans audio/ si voice_name correspond
            source_candidates = []
            if self.audio_dir.exists():
                source_candidates = list(self.audio_dir.glob("*.wav"))
                source_candidates.extend(self.audio_dir.glob("*.mp3"))

            # Priorité 2: Sinon chercher dans cleaned/
            if not source_candidates and cleaned_dir.exists():
                source_candidates = list(cleaned_dir.glob("*.wav"))

            if len(source_candidates) >= 2:
                logger.info(f"🎯 Few-shot mode: {len(source_candidates)} candidates found")

                # Scorer et sélectionner meilleurs
                selected_files = self.process_and_score_audio_files(
                    voice_name,
                    source_dir=self.audio_dir if (self.audio_dir / source_candidates[0].name).exists() else cleaned_dir,
                    top_n=min(max_files, len(source_candidates)),
                    use_uvr=use_uvr
                )

                if selected_files:
                    # Passer liste pour few-shot
                    audio_source = [str(f) for f in selected_files]
                    use_few_shot = True
                    logger.info(f"\n✅ Using {len(selected_files)} files for few-shot cloning")

        # Stratégie 2: Fallback sur reference.wav ou meilleur fichier
        if not audio_source:
            if reference_file.exists() and not force:
                audio_source = str(reference_file)
                logger.info(f"📁 Using existing reference.wav (zero-shot)")
            else:
                # Chercher dans cleaned/
                cleaned_dir = voice_folder / "cleaned"
                if cleaned_dir.exists():
                    cleaned_files = sorted(cleaned_dir.glob("*_cleaned.wav"))

                    if cleaned_files:
                        # Utiliser le fichier le plus gros (généralement meilleure qualité)
                        best_file = max(cleaned_files, key=lambda f: f.stat().st_size)
                        audio_source = str(best_file)
                        logger.info(f"📁 Using best cleaned file: {best_file.name} (zero-shot)")

        if not audio_source:
            logger.error(f"❌ No audio files found for voice '{voice_name}'")
            logger.error(f"   Add files to: {voice_folder}/ or {voice_folder}/cleaned/")
            return False

        # Cloner avec Chatterbox
        logger.info(f"\n🔬 Cloning voice with Chatterbox TTS...")
        if use_few_shot:
            logger.info(f"   Mode: Few-shot ({len(audio_source)} files)")
            logger.info(f"   Files: {', '.join([Path(f).name for f in audio_source[:3]])}{'...' if len(audio_source) > 3 else ''}")
        else:
            logger.info(f"   Mode: Zero-shot")
            logger.info(f"   Source: {Path(audio_source).name}")

        success = self.tts.clone_voice(
            audio_source,
            voice_name,
            use_few_shot=use_few_shot,
            max_files=max_files
        )

        if success:
            logger.info(f"\n✅ Voice '{voice_name}' cloned successfully!")
            logger.info(f"📁 Saved to: {voice_folder}")
            logger.info(f"📄 Files created:")
            logger.info(f"   - reference.wav (source audio)")
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

        # Importer objections database (comme clone_voice.py)
        try:
            from system import objections_database
        except ImportError:
            logger.error("❌ Could not import objections_database")
            return False

        # Collecter toutes les objections selon thématique
        all_objections = {}

        if themes:
            # Thématiques spécifiques
            for theme in themes:
                objections_list = objections_database.get_objections_by_theme(theme)
                if objections_list:
                    all_objections[theme] = objections_list
            logger.info(f"📋 Themes: {', '.join(themes)}")
        else:
            # Toutes les thématiques
            all_themes = objections_database.get_all_themes()
            for theme_name in all_themes:
                objections_list = objections_database.get_objections_by_theme(theme_name)
                if objections_list:
                    all_objections[theme_name] = objections_list

            logger.info(f"📋 Themes: {', '.join(all_objections.keys())}")

        # Compter total
        total_count = sum(len(obj_list) for obj_list in all_objections.values())
        logger.info(f"📊 Total objections: {total_count}")

        if total_count == 0:
            logger.warning("⚠️  No objections found")
            return False

        # Créer dossier de sortie
        output_dir = self.audio_dir / "tts" / voice_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Générer TTS
        logger.info(f"📁 Output directory: {output_dir}")

        # Estimer temps (10s par objection avec Chatterbox)
        estimated_time_minutes = (total_count * 10) / 60
        logger.info(f"⏱️  Estimated time: {estimated_time_minutes:.1f} minutes\n")

        success_count = 0
        failed_count = 0
        total_time = 0

        for theme_name, objections_list in all_objections.items():
            logger.info(f"\n📂 Processing theme: {theme_name.upper()}")
            logger.info(f"   {len(objections_list)} objections")

            for i, objection_entry in enumerate(objections_list, 1):
                # Extraire la réponse (ObjectionEntry ou str)
                if hasattr(objection_entry, 'response'):
                    response_text = objection_entry.response
                elif isinstance(objection_entry, str):
                    response_text = objection_entry
                else:
                    logger.warning(f"   ⚠️  Skipping invalid entry type: {type(objection_entry)}")
                    continue

                # Créer nom de fichier safe à partir des premiers mots de la réponse
                response_preview = response_text[:30]
                safe_name = self._sanitize_filename(response_preview)
                filename = f"{theme_name}_{i:03d}_{safe_name}.wav"
                output_file = output_dir / filename

                # Skip si existe déjà
                if output_file.exists():
                    logger.info(f"   [{i}/{len(objections_list)}] ⏭️  Skip (exists): {filename}")
                    success_count += 1
                    continue

                start_time = time.time()

                # Générer TTS avec Chatterbox
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

    def _clean_audio_with_uvr(self, audio_path: Path, output_dir: Path) -> Optional[Path]:
        """
        Nettoie un fichier audio avec UVR (Ultimate Vocal Remover).
        Extrait uniquement les vocals, enlève musique/bruit de fond.

        Args:
            audio_path: Fichier audio source
            output_dir: Dossier de sortie

        Returns:
            Path vers fichier nettoyé, ou None si échec
        """
        if not UVR_AVAILABLE:
            logger.warning("⚠️  UVR not available, skipping vocal extraction")
            return None

        try:
            logger.info(f"   🎵 UVR: Extracting vocals from {audio_path.name}...")

            # Créer dossier temporaire pour UVR
            temp_output = output_dir / "uvr_temp"
            temp_output.mkdir(exist_ok=True)

            # Initialiser UVR Separator
            separator = Separator(
                log_level=logging.WARNING,  # Réduire verbosité
                output_dir=str(temp_output),
                output_format="wav"
            )

            # Charger modèle vocal (version 0.12.0 API différente)
            # Pas de load_model(), utiliser directement separate()
            # Le modèle sera téléchargé automatiquement

            # Séparer vocals
            output_files = separator.separate(str(audio_path))

            # UVR génère 2 fichiers: vocals et instrumental
            # On garde juste les vocals
            vocals_file = None
            for f in output_files:
                if "Vocals" in f or "vocals" in f:
                    vocals_file = Path(f)
                    break

            if vocals_file and vocals_file.exists():
                # Déplacer vers output_dir avec nom propre
                clean_name = f"{audio_path.stem}_vocals.wav"
                final_path = output_dir / clean_name

                import shutil
                shutil.move(str(vocals_file), str(final_path))

                # Nettoyer temp
                shutil.rmtree(temp_output, ignore_errors=True)

                logger.info(f"      ✅ Vocals extracted: {clean_name}")
                return final_path
            else:
                logger.warning(f"      ⚠️  No vocals file generated")
                return None

        except Exception as e:
            logger.warning(f"      ⚠️  UVR failed: {e}")
            return None

    def _sanitize_filename(self, text: str) -> str:
        """Crée un nom de fichier safe depuis du texte"""
        import re
        # Garder seulement lettres, chiffres, espaces
        safe = re.sub(r'[^\w\s-]', '', text)
        # Remplacer espaces par underscores
        safe = re.sub(r'\s+', '_', safe)
        # Limiter longueur
        return safe[:40].lower()

    def _calculate_snr(self, waveform: np.ndarray, sample_rate: int) -> float:
        """
        Calcule le Signal-to-Noise Ratio (SNR) d'un audio.

        Args:
            waveform: Audio waveform (numpy array)
            sample_rate: Sample rate

        Returns:
            SNR en dB (plus élevé = meilleur)
        """
        try:
            # Convertir en mono si stéréo
            if len(waveform.shape) > 1:
                waveform = np.mean(waveform, axis=0)

            # Réduction de bruit pour estimer le signal propre
            reduced_noise = nr.reduce_noise(
                y=waveform,
                sr=sample_rate,
                stationary=True,
                prop_decrease=0.8
            )

            # Signal = variance du signal nettoyé
            signal_power = np.var(reduced_noise)

            # Bruit = variance de la différence
            noise = waveform - reduced_noise
            noise_power = np.var(noise)

            if noise_power == 0:
                return 100.0  # Très bon SNR

            snr = 10 * np.log10(signal_power / noise_power)
            return float(snr)

        except Exception as e:
            logger.warning(f"   ⚠️  SNR calculation failed: {e}")
            return 0.0

    def _calculate_silence_ratio(self, waveform: np.ndarray, threshold: float = 0.01) -> float:
        """
        Calcule le ratio de silence dans l'audio.

        Args:
            waveform: Audio waveform
            threshold: Seuil pour considérer comme silence

        Returns:
            Ratio de silence (0.0 = pas de silence, 1.0 = tout silence)
        """
        # Convertir en mono si stéréo
        if len(waveform.shape) > 1:
            waveform = np.mean(waveform, axis=0)

        # Normaliser
        if np.max(np.abs(waveform)) > 0:
            waveform = waveform / np.max(np.abs(waveform))

        # Compter samples sous le seuil
        silent_samples = np.sum(np.abs(waveform) < threshold)
        total_samples = len(waveform)

        return silent_samples / total_samples

    def _score_audio_file(self, audio_path: Path) -> Tuple[float, dict]:
        """
        Score un fichier audio basé sur qualité pour clonage.

        Args:
            audio_path: Chemin vers le fichier audio

        Returns:
            (score, metrics_dict)
            score: Score total (0-100, plus élevé = meilleur)
            metrics: Détails des métriques
        """
        if not AUDIO_PROCESSING_AVAILABLE:
            logger.warning("⚠️  Audio processing not available, using file size")
            size_mb = audio_path.stat().st_size / (1024 * 1024)
            return size_mb * 10, {"size_mb": size_mb}

        try:
            # Charger audio
            waveform, sample_rate = torchaudio.load(str(audio_path))
            waveform_np = waveform.numpy()

            # Durée
            duration = waveform.shape[1] / sample_rate

            # Métriques
            metrics = {
                "duration": duration,
                "sample_rate": sample_rate,
                "channels": waveform.shape[0]
            }

            # 1. Score durée (optimal: 3-15 secondes)
            if duration < 2:
                duration_score = 0
            elif duration < 3:
                duration_score = 50
            elif duration <= 15:
                duration_score = 100
            elif duration <= 30:
                duration_score = 80
            else:
                duration_score = 60

            metrics["duration_score"] = duration_score

            # 2. SNR (Signal-to-Noise Ratio)
            snr = self._calculate_snr(waveform_np, sample_rate)
            # SNR typique: 10-40 dB
            snr_score = min(100, max(0, (snr - 10) * 3.33))  # 10dB=0, 40dB=100
            metrics["snr"] = snr
            metrics["snr_score"] = snr_score

            # 3. Ratio de silence (moins = mieux)
            silence_ratio = self._calculate_silence_ratio(waveform_np)
            silence_score = max(0, 100 - (silence_ratio * 200))  # 0%=100, 50%=0
            metrics["silence_ratio"] = silence_ratio
            metrics["silence_score"] = silence_score

            # 4. Stabilité du volume (variance normalisée)
            if len(waveform_np.shape) > 1:
                waveform_mono = np.mean(waveform_np, axis=0)
            else:
                waveform_mono = waveform_np

            # Calculer RMS par fenêtres
            window_size = sample_rate // 10  # 100ms windows
            rms_values = []
            for i in range(0, len(waveform_mono), window_size):
                window = waveform_mono[i:i+window_size]
                if len(window) > 0:
                    rms = np.sqrt(np.mean(window**2))
                    rms_values.append(rms)

            if len(rms_values) > 0:
                rms_std = np.std(rms_values)
                rms_mean = np.mean(rms_values)
                stability = 1 - min(1, rms_std / (rms_mean + 1e-8))
                stability_score = stability * 100
            else:
                stability_score = 50

            metrics["stability"] = stability_score / 100
            metrics["stability_score"] = stability_score

            # Score total pondéré
            total_score = (
                duration_score * 0.25 +    # 25% durée
                snr_score * 0.35 +          # 35% qualité audio
                silence_score * 0.20 +      # 20% pas trop de silence
                stability_score * 0.20      # 20% stabilité
            )

            metrics["total_score"] = total_score

            return total_score, metrics

        except Exception as e:
            logger.error(f"   ❌ Error scoring {audio_path.name}: {e}")
            return 0.0, {"error": str(e)}

    def process_and_score_audio_files(
        self,
        voice_name: str,
        source_dir: Optional[Path] = None,
        top_n: int = 10,
        use_uvr: bool = False
    ) -> List[Path]:
        """
        Process, score et sélectionne les meilleurs fichiers audio.

        Args:
            voice_name: Nom de la voix
            source_dir: Dossier source (None = audio/ dir)
            top_n: Nombre de meilleurs fichiers à garder
            use_uvr: Utiliser UVR pour extraire vocals (enlève musique)

        Returns:
            Liste des meilleurs fichiers triés par score
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 AUDIO PROCESSING & SCORING")
        logger.info(f"{'='*60}")

        if not AUDIO_PROCESSING_AVAILABLE:
            logger.error("❌ Audio processing not available")
            logger.error("   Install: pip install torchaudio noisereduce")
            return []

        # Déterminer dossier source
        if source_dir is None:
            source_dir = self.audio_dir

        if not source_dir.exists():
            logger.error(f"❌ Source directory not found: {source_dir}")
            return []

        # Trouver tous les fichiers audio
        audio_files = list(source_dir.glob("*.wav"))
        audio_files.extend(source_dir.glob("*.mp3"))

        if not audio_files:
            logger.error(f"❌ No audio files found in {source_dir}")
            return []

        logger.info(f"📁 Source: {source_dir}")
        logger.info(f"📊 Found {len(audio_files)} audio files")
        logger.info(f"🎯 Selecting top {top_n} files")
        if use_uvr and UVR_AVAILABLE:
            logger.info(f"🎵 UVR: Vocal extraction enabled")
        logger.info("")

        # Créer dossier pour fichiers nettoyés
        cleaned_dir = self.voices_dir / voice_name / "cleaned"
        cleaned_dir.mkdir(parents=True, exist_ok=True)

        # Phase 1: UVR si demandé
        files_to_score = []

        if use_uvr and UVR_AVAILABLE:
            logger.info("🎵 Phase 1: UVR Vocal Extraction")
            logger.info("="*60)

            for i, audio_file in enumerate(audio_files, 1):
                logger.info(f"[{i}/{len(audio_files)}] Processing: {audio_file.name}")

                cleaned_file = self._clean_audio_with_uvr(audio_file, cleaned_dir)

                if cleaned_file:
                    files_to_score.append(cleaned_file)
                else:
                    # Fallback sur fichier original si UVR échoue
                    logger.info(f"      ⚠️  Using original file as fallback")
                    files_to_score.append(audio_file)

            logger.info(f"\n✅ UVR processed {len(files_to_score)} files\n")
        else:
            if use_uvr:
                logger.warning("⚠️  UVR requested but not available")
                logger.warning("   Install: pip install audio-separator\n")
            files_to_score = audio_files

        # Phase 2: Scoring
        logger.info("📊 Phase 2: Audio Quality Scoring")
        logger.info("="*60)

        scored_files = []

        for i, audio_file in enumerate(files_to_score, 1):
            logger.info(f"[{i}/{len(files_to_score)}] Scoring: {audio_file.name}")

            score, metrics = self._score_audio_file(audio_file)

            # Log métriques importantes
            if "total_score" in metrics:
                logger.info(f"   📊 Score: {score:.1f}/100")
                logger.info(f"      Duration: {metrics.get('duration', 0):.1f}s (score: {metrics.get('duration_score', 0):.1f})")
                logger.info(f"      SNR: {metrics.get('snr', 0):.1f}dB (score: {metrics.get('snr_score', 0):.1f})")
                logger.info(f"      Silence: {metrics.get('silence_ratio', 0)*100:.1f}% (score: {metrics.get('silence_score', 0):.1f})")
                logger.info(f"      Stability: {metrics.get('stability', 0)*100:.1f}% (score: {metrics.get('stability_score', 0):.1f})")
            else:
                logger.info(f"   📊 Score: {score:.1f}")

            scored_files.append((audio_file, score, metrics))

        # Trier par score (meilleur en premier)
        scored_files.sort(key=lambda x: x[1], reverse=True)

        # Sélectionner top N
        selected_files = [f[0] for f in scored_files[:top_n]]

        # Afficher résumé
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ TOP {len(selected_files)} FILES SELECTED:")
        logger.info(f"{'='*60}")

        for i, (audio_file, score, metrics) in enumerate(scored_files[:top_n], 1):
            duration = metrics.get('duration', 0)
            snr = metrics.get('snr', 0)
            logger.info(f"{i:2d}. {audio_file.name:30s} | Score: {score:5.1f} | {duration:.1f}s | SNR: {snr:.1f}dB")

        if len(scored_files) > top_n:
            logger.info(f"\n⏭️  Skipped {len(scored_files) - top_n} lower-scored files")

        return selected_files


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Voice cloning with Chatterbox TTS")
    parser.add_argument("--voice", type=str, help="Nom de la voix à cloner")
    parser.add_argument("--skip-tts", action="store_true", help="Ne pas générer les fichiers TTS")
    parser.add_argument("--theme", type=str, help="Thème spécifique pour TTS (crypto, energie, etc.)")
    parser.add_argument("--force", action="store_true", help="Force le re-clonage même si déjà fait")
    parser.add_argument("--no-scoring", action="store_true", help="Désactiver le scoring (utiliser un seul fichier)")
    parser.add_argument("--max-files", type=int, default=10, help="Nombre max de fichiers pour few-shot (défaut: 10)")
    parser.add_argument("--score-only", action="store_true", help="Juste scorer les fichiers sans cloner")
    parser.add_argument("--uvr", action="store_true", help="Utiliser UVR pour extraire vocals (enlève musique/bruit)")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🎤  VOICE CLONER - Chatterbox TTS (MiniBotPanel v3)")
    print("="*60)

    cloner = ChatterboxVoiceCloner()

    # Détecter voix disponibles
    available_voices = cloner.detect_available_voices()

    if not available_voices:
        logger.error("❌ No voices found in voices/")
        logger.info("💡 Create a folder in voices/ and add audio files")
        return 1

    logger.info(f"📁 Available voices: {', '.join(available_voices)}")

    # Sélectionner voix
    if args.voice:
        voice_name = args.voice
        # Si --score-only, pas besoin que la voix existe
        if not args.score_only and voice_name not in available_voices:
            logger.error(f"❌ Voice '{voice_name}' not found in voices/")
            logger.info(f"💡 Available voices: {', '.join(available_voices)}")
            return 1
    else:
        if args.score_only:
            logger.error("❌ --score-only requires --voice parameter")
            return 1
        # Utiliser première voix disponible
        voice_name = available_voices[0]
        logger.info(f"🎯 Using voice: {voice_name}")

    # Mode score-only
    if args.score_only:
        logger.info(f"🎯 Score-only mode for voice: {voice_name}")
        cloner.process_and_score_audio_files(
            voice_name,
            source_dir=cloner.audio_dir,
            top_n=args.max_files,
            use_uvr=args.uvr
        )
        logger.info("\n✅ Scoring complete!")
        return 0

    # Cloner voix
    if not cloner.clone_voice(
        voice_name,
        force=args.force,
        use_scoring=not args.no_scoring,
        max_files=args.max_files,
        use_uvr=args.uvr
    ):
        return 1

    # Générer TTS
    if not args.skip_tts:
        themes = [args.theme] if args.theme else None
        cloner.generate_tts_objections(voice_name, themes)

    logger.info("\n✅ Done!")
    return 0


if __name__ == "__main__":
    exit(main())
