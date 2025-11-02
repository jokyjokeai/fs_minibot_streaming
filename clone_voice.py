#!/usr/bin/env python3
"""
Clone Voice - MiniBotPanel v3 (Multi-Voice)

Utilitaire pour cloner des voix depuis des échantillons audio.

Fonctionnalités:
- Détection automatique des dossiers de voix dans voices/
- Nettoyage audio (noisereduce + Demucs pour extraction voix)
- Conversion format optimal pour Coqui XTTS (22050Hz mono WAV)
- Traitement parallèle multi-core (4-8× plus rapide que séquentiel)
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
    python clone_voice.py --voice julie --workers 4  # Utilise 4 workers parallèles
    python clone_voice.py --voice marie --sequential  # Mode séquentiel (debug)
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional
import json
import multiprocessing as mp
from functools import partial

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

# Demucs et pyrnnoise désactivés (non nécessaires, noisereduce suffit)
PYRNNOISE_AVAILABLE = False
DEMUCS_AVAILABLE = False

# Progress bar
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️  tqdm not available (no progress bars)")

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
        Ignore les fichiers de séparation vocale (Vocals/Instrumental)

        Args:
            directory: Dossier à scanner

        Returns:
            Liste de chemins vers fichiers audio (originaux seulement)
        """
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
        audio_files = []

        # Patterns à ignorer (fichiers générés par audio-separator, spleeter, demucs)
        ignore_patterns = [
            '(Vocals)',
            '(Instrumental)',
            '(vocals)',
            '(instrumental)',
            '_vocals.',
            '_instrumental.',
            'demucs_',
            'spleeter_output',
            'htdemucs',
            'model_mel_band_roformer'
        ]

        for ext in audio_extensions:
            for file_path in directory.glob(f'*{ext}'):
                # Ignorer si le nom contient un des patterns
                if any(pattern in file_path.name for pattern in ignore_patterns):
                    continue
                audio_files.append(file_path)

        return sorted(audio_files)

    def clean_audio_file(self, input_path: Path, output_path: Path) -> bool:
        """
        Nettoie un fichier audio:
        1. Extraction voix (séparation musique avec Demucs)
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

            # Étape 1: Extraction voix avec Demucs (state-of-the-art qualité)
            temp_path = input_path
            if DEMUCS_AVAILABLE:
                try:
                    logger.info(f"    → Extracting vocals (Demucs)...")

                    # Charger modèle Demucs (htdemucs ou htdemucs_ft)
                    model = get_model('htdemucs')
                    model.eval()

                    # Charger audio
                    import torchaudio
                    wav, sr = torchaudio.load(str(input_path))

                    # Demucs requiert stereo (2 channels) - convertir mono → stereo si nécessaire
                    if wav.shape[0] == 1:
                        # Mono → Stereo (dupliquer le canal)
                        wav = wav.repeat(2, 1)
                    elif wav.shape[0] > 2:
                        # Plus de 2 canaux → prendre les 2 premiers
                        wav = wav[:2, :]

                    # Appliquer séparation
                    with torch.no_grad():
                        sources = apply_model(model, wav[None], device='cpu', shifts=1, split=True, overlap=0.25)[0]

                    # Sources: [drums, bass, other, vocals]
                    vocals = sources[3]  # Index 3 = vocals

                    # Sauvegarder vocals
                    temp_vocals = input_path.parent / f"demucs_{input_path.name}"
                    torchaudio.save(str(temp_vocals), vocals.cpu(), sr)

                    temp_path = temp_vocals
                    logger.info(f"    ✅ Vocals extracted")

                except Exception as e:
                    logger.warning(f"    ⚠️  Vocal extraction failed: {e}, using original")

            # Étape 2: Charger audio
            audio_data, sample_rate = sf.read(str(temp_path))

            # Étape 3: Réduction bruit avec noisereduce
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

            # Sauvegarder avec codec PCM explicite
            audio.export(
                str(output_path),
                format='wav',
                codec='pcm_s16le'
            )

            # Cleanup temp files
            if temp_reduced.exists():
                temp_reduced.unlink()

            # Cleanup Demucs temp file
            if DEMUCS_AVAILABLE:
                temp_vocals = input_path.parent / f"demucs_{input_path.name}"
                if temp_vocals.exists() and temp_vocals != input_path:
                    temp_vocals.unlink()

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

            # Exporter WAV avec codec PCM explicite (compatible torchaudio)
            audio.export(
                str(output_path),
                format='wav',
                codec='pcm_s16le',  # PCM 16-bit little-endian
                parameters=["-ar", "22050", "-ac", "1"]
            )

            logger.info(f"    ✅ Converted to 22050Hz mono WAV: {output_path.name}")
            return True

        except Exception as e:
            logger.error(f"    ❌ Conversion failed: {e}")
            return False

    def _calculate_audio_quality_score(self, audio_data, sample_rate: int, file_size: int) -> float:
        """
        Calcule un score de qualité audio basé sur plusieurs critères.
        Score plus élevé = meilleure qualité pour le clonage vocal.

        Critères (inspirés d'ElevenLabs):
        1. SNR (Signal-to-Noise Ratio) - > 40 dB optimal
        2. Durée optimale (3-15 secondes)
        3. Volume stable (peu de variations)
        4. Pas de silence prolongé
        5. Taille fichier (corrélation avec qualité)

        Returns:
            Score de 0 à 100
        """
        import numpy as np

        try:
            # Convertir en mono si stéréo
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)

            duration = len(audio_data) / sample_rate
            score = 0.0

            # Critère 1: Durée optimale (3-15 secondes = meilleur)
            if 3 <= duration <= 15:
                score += 30  # Durée parfaite
            elif 1 <= duration < 3:
                score += 20  # Un peu court mais OK
            elif 15 < duration <= 30:
                score += 25  # Un peu long mais OK
            elif duration > 30:
                score += 10  # Trop long
            else:
                score += 5  # Trop court

            # Critère 2: SNR (Signal-to-Noise Ratio)
            # Estimer le bruit via les 10% les plus faibles en amplitude
            sorted_abs = np.sort(np.abs(audio_data))
            noise_floor = np.mean(sorted_abs[:int(len(sorted_abs) * 0.1)])
            signal_level = np.mean(np.abs(audio_data))

            if noise_floor > 0:
                snr_estimate = 20 * np.log10(signal_level / noise_floor)
                if snr_estimate > 40:
                    score += 30  # SNR excellent (comme ElevenLabs)
                elif snr_estimate > 30:
                    score += 20  # SNR bon
                elif snr_estimate > 20:
                    score += 10  # SNR acceptable
            else:
                score += 15  # Pas de bruit détectable

            # Critère 3: Stabilité du volume (faible écart-type = stable)
            # Calculer l'enveloppe RMS par segments de 100ms
            frame_length = int(0.1 * sample_rate)  # 100ms
            rms_values = []
            for i in range(0, len(audio_data) - frame_length, frame_length):
                frame = audio_data[i:i+frame_length]
                rms = np.sqrt(np.mean(frame**2))
                rms_values.append(rms)

            if len(rms_values) > 0:
                rms_std = np.std(rms_values)
                rms_mean = np.mean(rms_values)
                if rms_mean > 0:
                    variation_coef = rms_std / rms_mean
                    if variation_coef < 0.3:
                        score += 25  # Très stable
                    elif variation_coef < 0.5:
                        score += 15  # Stable
                    else:
                        score += 5  # Instable

            # Critère 4: Pas de silence prolongé
            silence_threshold = np.max(np.abs(audio_data)) * 0.01  # 1% du max
            silence_frames = np.sum(np.abs(audio_data) < silence_threshold)
            silence_ratio = silence_frames / len(audio_data)

            if silence_ratio < 0.1:
                score += 15  # Très peu de silence
            elif silence_ratio < 0.3:
                score += 10  # Silence acceptable
            else:
                score += 0  # Trop de silence

            return min(score, 100.0)  # Cap à 100

        except Exception as e:
            logger.warning(f"    ⚠️  Error calculating quality score: {e}")
            return 0.0

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

    def _process_single_file_worker(self, args: Tuple[Path, Path]) -> Optional[Path]:
        """
        Worker function pour traitement parallèle d'un fichier audio

        Args:
            args: Tuple (raw_file, cleaned_dir)

        Returns:
            Path du fichier optimal si succès, None sinon
        """
        raw_file, cleaned_dir = args

        try:
            # Chemin de sortie (plus de fichier _optimal, c'était un doublon inutile)
            cleaned_file = cleaned_dir / f"{raw_file.stem}_cleaned.wav"

            # Nettoyer ET convertir au format optimal (22050Hz mono)
            if not self.clean_audio_file(raw_file, cleaned_file):
                return None

            # Convertir directement le fichier cleaned au format optimal
            if not self.convert_to_optimal_format(cleaned_file, cleaned_file):
                return None

            return cleaned_file

        except Exception as e:
            logger.error(f"    ❌ Error processing {raw_file.name}: {e}")
            return None

    def process_audio_batch_parallel(
        self,
        raw_audio_files: List[Path],
        cleaned_dir: Path,
        num_workers: Optional[int] = None,
        sequential: bool = False
    ) -> List[Path]:
        """
        Traite plusieurs fichiers audio en parallèle ou séquentiel

        Args:
            raw_audio_files: Liste de fichiers à traiter
            cleaned_dir: Dossier de sortie
            num_workers: Nombre de workers (None = auto-détect CPU cores)
            sequential: Si True, traite en séquentiel (pour debug)

        Returns:
            Liste des fichiers nettoyés avec succès
        """
        # Auto-détection nombre de cores
        if num_workers is None:
            num_workers = max(1, mp.cpu_count() - 1)  # Garde 1 core libre

        # Mode séquentiel (backward compatibility / debug)
        if sequential:
            logger.info(f"🔄 Processing {len(raw_audio_files)} files sequentially...")
            cleaned_files = []

            iterator = enumerate(raw_audio_files, 1)
            if TQDM_AVAILABLE:
                iterator = tqdm(iterator, total=len(raw_audio_files), desc="Processing files", unit="file")

            for i, raw_file in iterator:
                if not TQDM_AVAILABLE:
                    logger.info(f"\n[{i}/{len(raw_audio_files)}] {raw_file.name}")

                result = self._process_single_file_worker((raw_file, cleaned_dir))
                if result:
                    cleaned_files.append(result)

            return cleaned_files

        # Mode parallèle (optimisé)
        logger.info(f"🚀 Processing {len(raw_audio_files)} files with {num_workers} parallel workers...")

        # Préparer arguments pour workers
        args_list = [(raw_file, cleaned_dir) for raw_file in raw_audio_files]

        # Traitement parallèle avec progress bar
        cleaned_files = []

        with mp.Pool(processes=num_workers) as pool:
            if TQDM_AVAILABLE:
                # Avec barre de progression
                results = list(tqdm(
                    pool.imap(self._process_single_file_worker, args_list),
                    total=len(args_list),
                    desc="Processing files",
                    unit="file"
                ))
            else:
                # Sans barre de progression
                results = pool.map(self._process_single_file_worker, args_list)

        # Filtrer résultats valides
        cleaned_files = [f for f in results if f is not None]

        logger.info(f"✅ {len(cleaned_files)}/{len(raw_audio_files)} files processed successfully")
        return cleaned_files

    def process_voice_folder(self, voice_name: str, force: bool = False, sequential: bool = False, num_workers: Optional[int] = None) -> bool:
        """
        Traite un dossier de voix complet:
        1. Nettoyage fichiers inutiles (vocals/instrumental générés)
        2. Scan fichiers audio originaux
        3. Nettoyage + conversion (parallèle ou séquentiel)
        4. Détection mode clonage
        5. Clonage voix

        Args:
            voice_name: Nom de la voix
            force: Forcer écrasement si existe
            sequential: Si True, traite fichiers en séquentiel (debug)
            num_workers: Nombre de workers parallèles (None = auto)

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

        # Nettoyer les fichiers inutiles AVANT traitement (vocals/instrumental générés)
        self._cleanup_generated_files(voice_dir)

        # Trouver fichiers audio
        raw_audio_files = self._find_audio_files(voice_dir)
        if not raw_audio_files:
            logger.error(f"❌ No audio files found in {voice_dir}")
            return False

        logger.info(f"📁 Found {len(raw_audio_files)} audio files")

        # Créer dossier cleaned
        cleaned_dir = voice_dir / "cleaned"
        cleaned_dir.mkdir(exist_ok=True)

        # Nettoyer et convertir avec traitement parallèle
        logger.info(f"\n🧹 Cleaning and converting audio files...")
        cleaned_files = self.process_audio_batch_parallel(
            raw_audio_files=raw_audio_files,
            cleaned_dir=cleaned_dir,
            num_workers=num_workers,
            sequential=sequential
        )

        if not cleaned_files:
            logger.error(f"❌ No files successfully processed")
            return False

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

        # Cloner voix avec TOUS les fichiers valides pour embeddings moyennés
        # XTTS va extraire les embeddings de chaque fichier et les moyenner
        logger.info(f"\n🎤 Cloning voice '{voice_name}' with averaged embeddings...")

        # Analyser et scorer TOUS les fichiers pour sélectionner les meilleurs
        logger.info(f"\n🔍 Analyzing audio quality to select best files...")

        scored_files = []
        MIN_FILE_SIZE = 10 * 1024  # 10KB minimum

        for cleaned_file in cleaned_files:
            try:
                file_size = cleaned_file.stat().st_size
                if file_size < MIN_FILE_SIZE:
                    continue

                # Lire le fichier audio
                import soundfile as sf
                import numpy as np

                data, sr = sf.read(str(cleaned_file))

                if len(data) == 0 or sr == 0:
                    continue

                # Calculer le score de qualité
                score = self._calculate_audio_quality_score(data, sr, file_size)

                if score > 0:
                    scored_files.append({
                        'path': str(cleaned_file),
                        'name': cleaned_file.name,
                        'score': score,
                        'size': file_size,
                        'duration': len(data) / sr
                    })
                    logger.info(f"    📊 {cleaned_file.name}: score={score:.2f}, duration={len(data)/sr:.1f}s")

            except Exception as e:
                logger.warning(f"    ⚠️  Error analyzing {cleaned_file.name}: {e}")
                continue

        if not scored_files:
            logger.error(f"❌ No valid audio files found")
            return False

        # Trier par score décroissant et sélectionner les 10 meilleurs
        scored_files.sort(key=lambda x: x['score'], reverse=True)

        # Sélectionner les N meilleurs (max 10 ou tous si moins de 10)
        MAX_BEST_FILES = 10
        best_files = scored_files[:min(MAX_BEST_FILES, len(scored_files))]

        logger.info(f"\n🎯 Selected {len(best_files)} BEST files (out of {len(scored_files)} analyzed):")
        for i, f in enumerate(best_files, 1):
            logger.info(f"    {i}. {f['name']} - score: {f['score']:.2f}, duration: {f['duration']:.1f}s")

        best_file_paths = [f['path'] for f in best_files]

        # Passer les meilleurs fichiers à clone_voice() pour moyenne des embeddings
        success = self.tts.clone_voice(best_file_paths, voice_name)

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

    def _cleanup_generated_files(self, voice_dir: Path):
        """
        Nettoie les fichiers générés par audio-separator/spleeter/demucs
        Garde seulement les originaux (youtube_XXX.wav) et le dossier cleaned/

        Args:
            voice_dir: Dossier de la voix
        """
        logger.info(f"\n🧹 Cleaning up generated files...")

        # Patterns de fichiers à supprimer
        cleanup_patterns = [
            '*_(Vocals)*.wav',
            '*_(Instrumental)*.wav',
            '*_(vocals)*.wav',
            '*_(instrumental)*.wav',
            '*_vocals.wav',
            '*_instrumental.wav',
            'demucs_*.wav',
            '*model_mel_band_roformer*.wav'
        ]

        deleted_count = 0
        for pattern in cleanup_patterns:
            for file_path in voice_dir.glob(pattern):
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"    Deleted: {file_path.name}")
                except Exception as e:
                    logger.warning(f"    Failed to delete {file_path.name}: {e}")

        # Supprimer dossiers temporaires
        temp_dirs = ['spleeter_output', 'separated']
        for temp_dir_name in temp_dirs:
            temp_dir = voice_dir / temp_dir_name
            if temp_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    deleted_count += 1
                    logger.debug(f"    Deleted directory: {temp_dir_name}/")
                except Exception as e:
                    logger.warning(f"    Failed to delete {temp_dir_name}/: {e}")

        if deleted_count > 0:
            logger.info(f"    ✅ Cleaned {deleted_count} generated files/folders")
        else:
            logger.info(f"    ✅ No cleanup needed")

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
            objections_list = objections_database.get_objections_by_theme(theme)
            all_objections[theme] = objections_list
            logger.info(f"📋 Theme: {theme}")
        else:
            # Toutes les thématiques
            themes = objections_database.get_all_themes()
            for theme_name in themes:
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
                # Format: theme_number_debut_reponse.wav
                response_preview = response_text[:30]
                safe_name = self._sanitize_filename(response_preview)
                filename = f"{theme_name}_{i:03d}_{safe_name}.wav"
                output_file = output_dir / filename

                # Skip si existe déjà
                if output_file.exists():
                    logger.debug(f"   ⏭️  Skip (exists): {filename}")
                    success_count += 1
                    continue

                # Générer TTS avec synthesize_with_voice
                try:
                    # Trouver le fichier reference.wav de la voix
                    voice_dir = self.voices_dir / voice_name
                    reference_wav = voice_dir / "reference.wav"

                    if not reference_wav.exists():
                        logger.error(f"   ❌ Reference file not found: {reference_wav}")
                        failed_count += 1
                        continue

                    # Utiliser voice_name pour profiter des embeddings cachés
                    result_path = self.tts.synthesize_with_voice(
                        text=response_text,
                        reference_voice=str(reference_wav),
                        voice_name=voice_name,  # Utiliser embeddings cachés si disponibles
                        output_file=str(output_file)
                    )
                    success = result_path is not None

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
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process files sequentially (slower, for debugging)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: auto-detect CPU cores - 1)"
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
    success = cloner.process_voice_folder(
        voice_name,
        force=args.force,
        sequential=args.sequential,
        num_workers=args.workers
    )

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
