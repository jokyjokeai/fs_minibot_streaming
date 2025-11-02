#!/usr/bin/env python3
"""
Simple Speaker Diarization - MiniBotPanel v3

Système de diarization maison sans dépendances complexes (sans pyannote).
Utilise des techniques simples mais efficaces:
- Détection d'énergie vocale (VAD)
- Analyse spectrale (MFCC)
- Clustering simple des caractéristiques vocales

Dépendances: librosa, scikit-learn, numpy
"""

import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import warnings

# Supprimer warnings numpy
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    import numpy as np
    import librosa
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.preprocessing import StandardScaler
    DIARIZATION_AVAILABLE = True
except ImportError as e:
    DIARIZATION_AVAILABLE = False
    print(f"❌ Diarization dependencies not available: {e}")
    print("   Install: pip install librosa scikit-learn numpy")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpeakerSegment:
    """Représente un segment audio avec locuteur assigné"""

    def __init__(self, start: float, end: float, speaker: int):
        self.start = start  # secondes
        self.end = end      # secondes
        self.speaker = speaker  # ID locuteur (0, 1, 2...)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def __repr__(self):
        return f"SpeakerSegment(speaker={self.speaker}, {self.start:.2f}s-{self.end:.2f}s, {self.duration:.2f}s)"


class SimpleDiarization:
    """
    Diarization simple basée sur:
    1. VAD (Voice Activity Detection) - détection de parole
    2. MFCC (Mel-Frequency Cepstral Coefficients) - empreintes vocales
    3. Clustering - regroupement par similarité vocale
    """

    def __init__(
        self,
        min_segment_duration: float = 0.5,  # Segments minimum 500ms
        hop_length: int = 512,              # Résolution temporelle
        n_mfcc: int = 20,                   # Nombre de coefficients MFCC
        min_speakers: int = 1,              # Min locuteurs attendus
        max_speakers: int = 5,              # Max locuteurs possibles
    ):
        """
        Initialise le système de diarization

        Args:
            min_segment_duration: Durée minimum d'un segment (secondes)
            hop_length: Taille du hop pour analyse (échantillons)
            n_mfcc: Nombre de coefficients MFCC à extraire
            min_speakers: Nombre minimum de locuteurs
            max_speakers: Nombre maximum de locuteurs
        """
        self.min_segment_duration = min_segment_duration
        self.hop_length = hop_length
        self.n_mfcc = n_mfcc
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

        logger.info("🎤 SimpleDiarization initialized")
        logger.info(f"   Min segment: {min_segment_duration}s")
        logger.info(f"   MFCC coefficients: {n_mfcc}")
        logger.info(f"   Speaker range: {min_speakers}-{max_speakers}")

    def detect_voice_activity(
        self,
        audio_path: Path,
        threshold_db: float = -30,
        min_silence_duration: float = 0.3
    ) -> List[Tuple[float, float]]:
        """
        Détecte les segments de parole (VAD - Voice Activity Detection)

        Args:
            audio_path: Fichier audio
            threshold_db: Seuil énergie en dB (relatif au max)
            min_silence_duration: Durée minimum de silence (secondes)

        Returns:
            Liste de (start, end) en secondes pour chaque segment vocal
        """
        logger.info(f"🔊 Voice Activity Detection...")
        logger.info(f"   Threshold: {threshold_db}dB")

        # Charger audio
        y, sr = librosa.load(str(audio_path), sr=None)

        # Calculer énergie RMS (Root Mean Square)
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]

        # Convertir en dB
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)

        # Détecter segments au-dessus du seuil
        voice_frames = rms_db > threshold_db

        # Convertir frames en timestamps
        times = librosa.frames_to_time(
            np.arange(len(voice_frames)),
            sr=sr,
            hop_length=self.hop_length
        )

        # Regrouper frames consécutifs en segments
        segments = []
        in_segment = False
        segment_start = None

        min_silence_frames = int(min_silence_duration * sr / self.hop_length)
        silence_counter = 0

        for i, is_voice in enumerate(voice_frames):
            if is_voice:
                if not in_segment:
                    # Début nouveau segment
                    segment_start = times[i]
                    in_segment = True
                silence_counter = 0
            else:
                if in_segment:
                    silence_counter += 1
                    # Si silence assez long, terminer segment
                    if silence_counter >= min_silence_frames:
                        segment_end = times[i - silence_counter]
                        if segment_end - segment_start >= self.min_segment_duration:
                            segments.append((segment_start, segment_end))
                        in_segment = False
                        silence_counter = 0

        # Ajouter dernier segment si nécessaire
        if in_segment and segment_start is not None:
            segment_end = times[-1]
            if segment_end - segment_start >= self.min_segment_duration:
                segments.append((segment_start, segment_end))

        logger.info(f"✅ Detected {len(segments)} voice segments")
        total_duration = sum(end - start for start, end in segments)
        logger.info(f"   Total speech: {total_duration:.1f}s")

        return segments

    def extract_speaker_features(
        self,
        audio_path: Path,
        segments: List[Tuple[float, float]]
    ) -> np.ndarray:
        """
        Extrait caractéristiques vocales (MFCC) pour chaque segment

        Args:
            audio_path: Fichier audio
            segments: Liste de (start, end) en secondes

        Returns:
            Array numpy (n_segments, n_features) avec caractéristiques
        """
        logger.info(f"🎵 Extracting MFCC features...")

        # Charger audio
        y, sr = librosa.load(str(audio_path), sr=None)

        features_list = []

        for start, end in segments:
            # Extraire segment
            start_sample = int(start * sr)
            end_sample = int(end * sr)
            segment_audio = y[start_sample:end_sample]

            if len(segment_audio) == 0:
                continue

            # Extraire MFCC
            mfcc = librosa.feature.mfcc(
                y=segment_audio,
                sr=sr,
                n_mfcc=self.n_mfcc,
                hop_length=self.hop_length
            )

            # Statistiques temporelles (mean, std, min, max)
            mfcc_mean = np.mean(mfcc, axis=1)
            mfcc_std = np.std(mfcc, axis=1)
            mfcc_min = np.min(mfcc, axis=1)
            mfcc_max = np.max(mfcc, axis=1)

            # Concaténer features
            features = np.concatenate([mfcc_mean, mfcc_std, mfcc_min, mfcc_max])
            features_list.append(features)

        features_array = np.array(features_list)
        logger.info(f"✅ Extracted features: {features_array.shape}")

        return features_array

    def cluster_speakers(
        self,
        features: np.ndarray,
        n_speakers: Optional[int] = None
    ) -> np.ndarray:
        """
        Regroupe segments par locuteur via clustering

        Args:
            features: Array (n_segments, n_features)
            n_speakers: Nombre de locuteurs (None = auto-détection)

        Returns:
            Array (n_segments,) avec ID locuteur pour chaque segment
        """
        logger.info(f"👥 Clustering speakers...")

        # Normaliser features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        # Auto-détection nombre de locuteurs si non spécifié
        if n_speakers is None:
            # Essayer différents nombres et choisir via silhouette score
            from sklearn.metrics import silhouette_score

            best_score = -1
            best_n = self.min_speakers

            for n in range(self.min_speakers, min(self.max_speakers + 1, len(features))):
                clustering = AgglomerativeClustering(
                    n_clusters=n,
                    linkage='ward'
                )
                labels = clustering.fit_predict(features_scaled)

                # Score silhouette (qualité clustering)
                if n > 1:
                    score = silhouette_score(features_scaled, labels)
                    logger.info(f"   n={n} speakers: silhouette={score:.3f}")

                    if score > best_score:
                        best_score = score
                        best_n = n

            n_speakers = best_n
            logger.info(f"✅ Auto-detected {n_speakers} speakers (score={best_score:.3f})")

        # Clustering final
        clustering = AgglomerativeClustering(
            n_clusters=n_speakers,
            linkage='ward'
        )
        labels = clustering.fit_predict(features_scaled)

        logger.info(f"✅ Clustered into {n_speakers} speakers")

        return labels

    def merge_consecutive_segments(
        self,
        segments: List[SpeakerSegment],
        max_gap: float = 0.5
    ) -> List[SpeakerSegment]:
        """
        Fusionne segments consécutifs du même locuteur

        Args:
            segments: Liste de segments
            max_gap: Gap maximum pour fusion (secondes)

        Returns:
            Liste fusionnée
        """
        if not segments:
            return []

        # Trier par temps
        sorted_segments = sorted(segments, key=lambda s: s.start)

        merged = []
        current = sorted_segments[0]

        for next_seg in sorted_segments[1:]:
            # Même locuteur et gap acceptable ?
            if (next_seg.speaker == current.speaker and
                next_seg.start - current.end <= max_gap):
                # Fusionner
                current = SpeakerSegment(
                    start=current.start,
                    end=next_seg.end,
                    speaker=current.speaker
                )
            else:
                # Sauvegarder actuel et continuer
                merged.append(current)
                current = next_seg

        # Ajouter dernier
        merged.append(current)

        logger.info(f"🔗 Merged {len(segments)} → {len(merged)} segments")

        return merged

    def diarize(
        self,
        audio_path: Path,
        n_speakers: Optional[int] = None,
        vad_threshold_db: float = -30,
        min_silence_duration: float = 0.3
    ) -> List[SpeakerSegment]:
        """
        Effectue diarization complète

        Args:
            audio_path: Fichier audio
            n_speakers: Nombre de locuteurs (None = auto)
            vad_threshold_db: Seuil VAD en dB
            min_silence_duration: Durée min silence (secondes)

        Returns:
            Liste de SpeakerSegment avec locuteur assigné
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎤 Simple Speaker Diarization")
        logger.info(f"{'='*60}")
        logger.info(f"Audio: {audio_path.name}")

        # 1. VAD - Détecter segments vocaux
        vad_segments = self.detect_voice_activity(
            audio_path,
            threshold_db=vad_threshold_db,
            min_silence_duration=min_silence_duration
        )

        if not vad_segments:
            logger.warning("⚠️  No voice activity detected")
            return []

        # 2. Extraire features
        features = self.extract_speaker_features(audio_path, vad_segments)

        if len(features) == 0:
            logger.warning("⚠️  No features extracted")
            return []

        # 3. Clustering
        speaker_labels = self.cluster_speakers(features, n_speakers)

        # 4. Créer segments avec locuteurs
        segments = []
        for (start, end), speaker_id in zip(vad_segments, speaker_labels):
            segments.append(SpeakerSegment(start, end, int(speaker_id)))

        # 5. Fusionner segments consécutifs
        merged_segments = self.merge_consecutive_segments(segments, max_gap=0.5)

        # Stats
        logger.info(f"\n📊 Diarization Results:")
        speaker_stats = {}
        for seg in merged_segments:
            if seg.speaker not in speaker_stats:
                speaker_stats[seg.speaker] = 0.0
            speaker_stats[seg.speaker] += seg.duration

        for speaker_id in sorted(speaker_stats.keys()):
            duration = speaker_stats[speaker_id]
            logger.info(f"   SPEAKER_{speaker_id}: {duration:.1f}s ({duration/60:.1f}min)")

        logger.info(f"✅ Diarization completed: {len(merged_segments)} segments")
        logger.info(f"{'='*60}\n")

        return merged_segments

    def get_speaker_durations(self, segments: List[SpeakerSegment]) -> Dict[str, float]:
        """
        Calcule durée totale par locuteur

        Args:
            segments: Liste de segments

        Returns:
            Dict {speaker_name: duration_seconds}
        """
        durations = {}

        for seg in segments:
            speaker_name = f"SPEAKER_{seg.speaker}"
            if speaker_name not in durations:
                durations[speaker_name] = 0.0
            durations[speaker_name] += seg.duration

        return durations


# Test standalone
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python simple_diarization.py <audio_file.wav>")
        sys.exit(1)

    audio_file = Path(sys.argv[1])

    if not audio_file.exists():
        print(f"❌ File not found: {audio_file}")
        sys.exit(1)

    # Test diarization
    diarizer = SimpleDiarization(
        min_segment_duration=0.5,
        n_mfcc=20,
        min_speakers=1,
        max_speakers=5
    )

    segments = diarizer.diarize(audio_file)

    print(f"\n📋 Results:")
    for seg in segments[:10]:  # Premiers 10 segments
        print(f"   {seg}")

    if len(segments) > 10:
        print(f"   ... ({len(segments) - 10} more segments)")
