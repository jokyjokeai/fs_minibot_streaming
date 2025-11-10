"""
Advanced Echo Filter - Détection anti-echo avec Librosa
========================================================

Filtre avancé pour détecter echo/feedback avec analyse audio professionnelle.

Méthodes de détection:
1. MFCC Similarity (Mel-frequency cepstral coefficients) - Empreinte vocale
2. Spectral features (centroid, bandwidth, rolloff)
3. Cross-correlation - Similitude temporelle
4. Energy/RMS comparison

Usage:
    filter = AdvancedEchoFilter()
    filter.set_robot_audio("path/to/robot.wav")

    if filter.is_probable_echo("path/to/bargein.wav"):
        # Ignorer ce barge-in
        pass
"""

import logging
import numpy as np
import librosa
from pathlib import Path
from typing import Optional, Dict
from scipy import signal

logger = logging.getLogger(__name__)


class AdvancedEchoFilter:
    """
    Filtre anti-echo avancé utilisant librosa pour analyse audio.

    Plus précis que SimpleEchoFilter mais légèrement plus lent (~20-30ms vs <10ms).
    """

    def __init__(self, enabled: bool = True):
        """
        Initialise le filtre anti-echo avancé.

        Args:
            enabled: Activer/désactiver le filtre (default: True)
        """
        self.enabled = enabled
        self.last_robot_features: Optional[Dict] = None

        # Seuils de détection (ajustables)
        self.mfcc_similarity_threshold = 0.85  # Similarité MFCC > 85% = probable echo
        self.spectral_similarity_threshold = 0.80  # Similarité spectrale > 80%
        self.correlation_threshold = 0.70  # Corrélation > 70%
        self.energy_ratio_threshold = (0.6, 1.4)  # Ratio énergie entre 0.6-1.4

        logger.info(f"AdvancedEchoFilter initialized (enabled={enabled}, using librosa)")

    def _extract_features(self, audio_path: str, channel: int = None) -> Optional[Dict]:
        """
        Extrait features audio avancées avec librosa.

        Args:
            audio_path: Chemin vers fichier audio
            channel: 0=left (client), 1=right (robot), None=mono

        Returns:
            Dict avec features ou None si erreur
        """
        try:
            # Charger audio
            y, sr = librosa.load(audio_path, sr=None, mono=False)

            # Si stereo, sélectionner canal
            if y.ndim == 2:
                if channel is not None:
                    y = y[channel, :]
                else:
                    y = librosa.to_mono(y)

            # 1. MFCC (empreinte vocale)
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_mean = np.mean(mfcc, axis=1)
            mfcc_std = np.std(mfcc, axis=1)

            # 2. Spectral features
            spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
            spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))
            spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr))

            # 3. Energy
            rms = np.sqrt(np.mean(y**2))

            # 4. Zero-crossing rate
            zcr = np.mean(librosa.feature.zero_crossing_rate(y))

            # 5. Chroma features (contenu harmonique)
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)

            return {
                'mfcc_mean': mfcc_mean,
                'mfcc_std': mfcc_std,
                'spectral_centroid': spectral_centroid,
                'spectral_bandwidth': spectral_bandwidth,
                'spectral_rolloff': spectral_rolloff,
                'rms': rms,
                'zcr': zcr,
                'chroma_mean': chroma_mean,
                'audio': y,
                'sr': sr
            }

        except Exception as e:
            logger.error(f"🔇 Echo filter: Error extracting features: {e}")
            return None

    def set_robot_audio(self, audio_path: str):
        """
        Sauvegarder features de l'audio robot pour comparaison ultérieure.

        Args:
            audio_path: Chemin vers fichier audio robot (.wav)
        """
        if not self.enabled:
            return

        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                logger.warning(f"🔇 Echo filter: Audio file not found: {audio_path}")
                return

            # Extraire features (RIGHT channel = robot)
            features = self._extract_features(str(audio_path), channel=1)

            if features:
                self.last_robot_features = features
                logger.debug(f"🔇 Echo filter: Robot features cached (RMS={features['rms']:.3f})")
            else:
                self.last_robot_features = None

        except Exception as e:
            logger.error(f"🔇 Echo filter: Error loading robot audio: {e}")
            self.last_robot_features = None

    def _compute_mfcc_similarity(self, mfcc1: np.ndarray, mfcc2: np.ndarray) -> float:
        """
        Calcule similarité MFCC (cosine similarity).

        Returns:
            Score 0-1 (1 = identique)
        """
        # Normaliser
        mfcc1_norm = mfcc1 / (np.linalg.norm(mfcc1) + 1e-8)
        mfcc2_norm = mfcc2 / (np.linalg.norm(mfcc2) + 1e-8)

        # Cosine similarity
        similarity = np.dot(mfcc1_norm, mfcc2_norm)
        return float(np.clip(similarity, 0, 1))

    def _compute_spectral_similarity(self, features1: Dict, features2: Dict) -> float:
        """
        Calcule similarité spectrale globale.

        Returns:
            Score 0-1 (1 = très similaire)
        """
        # Comparer centroid, bandwidth, rolloff
        centroid_ratio = min(features1['spectral_centroid'], features2['spectral_centroid']) / \
                        (max(features1['spectral_centroid'], features2['spectral_centroid']) + 1e-8)

        bandwidth_ratio = min(features1['spectral_bandwidth'], features2['spectral_bandwidth']) / \
                         (max(features1['spectral_bandwidth'], features2['spectral_bandwidth']) + 1e-8)

        rolloff_ratio = min(features1['spectral_rolloff'], features2['spectral_rolloff']) / \
                       (max(features1['spectral_rolloff'], features2['spectral_rolloff']) + 1e-8)

        # Moyenne
        similarity = (centroid_ratio + bandwidth_ratio + rolloff_ratio) / 3.0
        return float(similarity)

    def _compute_cross_correlation(self, audio1: np.ndarray, audio2: np.ndarray) -> float:
        """
        Calcule cross-correlation entre deux signaux audio.

        Returns:
            Score 0-1 (1 = très corrélés)
        """
        # Normaliser signaux
        audio1_norm = (audio1 - np.mean(audio1)) / (np.std(audio1) + 1e-8)
        audio2_norm = (audio2 - np.mean(audio2)) / (np.std(audio2) + 1e-8)

        # Tronquer au plus court
        min_len = min(len(audio1_norm), len(audio2_norm))
        audio1_norm = audio1_norm[:min_len]
        audio2_norm = audio2_norm[:min_len]

        # Cross-correlation
        correlation = signal.correlate(audio1_norm, audio2_norm, mode='valid')
        max_corr = np.max(np.abs(correlation)) / min_len

        return float(np.clip(max_corr, 0, 1))

    def is_probable_echo(self, barge_in_audio_path: str) -> bool:
        """
        Détecte si audio barge-in est probablement un echo (version avancée).

        Utilise plusieurs méthodes:
        1. MFCC similarity (empreinte vocale)
        2. Spectral similarity (caractéristiques fréquentielles)
        3. Cross-correlation (similitude temporelle)
        4. Energy ratio (volume comparable)

        Args:
            barge_in_audio_path: Chemin vers fichier audio barge-in (.wav)

        Returns:
            True si probable echo, False sinon
        """
        if not self.enabled:
            return False

        if not self.last_robot_features:
            logger.debug("🔇 Echo filter: No robot features cached, skipping check")
            return False

        try:
            barge_in_path = Path(barge_in_audio_path)
            if not barge_in_path.exists():
                logger.warning(f"🔇 Echo filter: Barge-in file not found: {barge_in_path}")
                return False

            # Extraire features barge-in (LEFT channel = client)
            bargein_features = self._extract_features(str(barge_in_path), channel=0)

            if not bargein_features:
                logger.warning("🔇 Echo filter: Could not extract barge-in features")
                return False

            robot_features = self.last_robot_features

            # --- Test 1: MFCC Similarity ---
            mfcc_similarity = self._compute_mfcc_similarity(
                robot_features['mfcc_mean'],
                bargein_features['mfcc_mean']
            )

            if mfcc_similarity >= self.mfcc_similarity_threshold:
                logger.warning(f"🔇 Echo detected: MFCC {mfcc_similarity:.0%} (threshold {self.mfcc_similarity_threshold:.0%})")
                return True

            # --- Test 2: Spectral Similarity ---
            spectral_similarity = self._compute_spectral_similarity(
                robot_features,
                bargein_features
            )

            if spectral_similarity >= self.spectral_similarity_threshold:
                logger.warning(f"🔇 Echo detected: Spectral {spectral_similarity:.0%} (threshold {self.spectral_similarity_threshold:.0%})")
                return True

            # --- Test 3: Cross-Correlation ---
            correlation = self._compute_cross_correlation(
                robot_features['audio'],
                bargein_features['audio']
            )

            if correlation >= self.correlation_threshold:
                logger.warning(f"🔇 Echo detected: Correlation {correlation:.0%} (threshold {self.correlation_threshold:.0%})")
                return True

            # --- Test 4: Energy Ratio (doit être dans range acceptable) ---
            energy_ratio = bargein_features['rms'] / (robot_features['rms'] + 1e-8)

            if self.energy_ratio_threshold[0] <= energy_ratio <= self.energy_ratio_threshold[1]:
                # Energy ratio OK, mais vérifier si combinaison de plusieurs facteurs
                combined_score = (mfcc_similarity + spectral_similarity + correlation) / 3.0

                if combined_score >= 0.65:  # Score combiné > 65%
                    logger.warning(f"🔇 Echo detected: Combined {combined_score:.0%} (energy ratio {energy_ratio:.1f})")
                    return True

            # Pas d'echo détecté - pas de log (silent)
            return False

        except Exception as e:
            logger.error(f"🔇 Echo filter: Error checking echo: {e}", exc_info=True)
            return False  # En cas d'erreur, ne pas bloquer barge-in

    def clear(self):
        """Vider le cache features robot."""
        self.last_robot_features = None
        logger.debug("🔇 Echo filter: Cache cleared")
