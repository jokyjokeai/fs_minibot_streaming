"""
Echo Filter - Détection anti-echo pour barge-in
================================================

Filtre simple pour détecter si un barge-in est probablement un echo/feedback
du haut-parleur au lieu d'une vraie interruption client.

Méthodes de détection:
1. Volume trop élevé (>80% max = probable haut-parleur)
2. RMS similaire au robot (±20% = probable echo)
3. Zero-crossing rate similaire (±30% = probable echo)

Usage:
    filter = SimpleEchoFilter()

    # Avant de jouer audio robot
    filter.set_robot_audio("path/to/robot/audio.wav")

    # Après détection barge-in
    if filter.is_probable_echo("path/to/bargein/audio.wav"):
        # Ignorer ce barge-in
        pass
"""

import logging
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SimpleEchoFilter:
    """
    Filtre anti-echo basique pour barge-in.

    Détecte si audio barge-in est probablement un echo du robot
    plutôt qu'une vraie parole client.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialise le filtre anti-echo.

        Args:
            enabled: Activer/désactiver le filtre (default: True)
        """
        self.enabled = enabled
        self.last_robot_audio: Optional[dict] = None
        logger.info(f"SimpleEchoFilter initialized (enabled={enabled})")

    def set_robot_audio(self, audio_path: str):
        """
        Sauvegarder features de l'audio robot pour comparaison ultérieure.

        Extrait:
        - RMS (Root Mean Square) = Volume moyen
        - ZCR (Zero-Crossing Rate) = Fréquence changements de signe

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

            # Lire audio robot
            audio, sr = sf.read(str(audio_path))

            # Si stereo, prendre RIGHT channel (robot)
            if audio.ndim == 2:
                audio = audio[:, 1]  # RIGHT channel = robot

            # Calculer features
            rms = float(np.sqrt(np.mean(audio**2)))
            zcr = float(np.mean(np.abs(np.diff(np.sign(audio)))))

            self.last_robot_audio = {
                'rms': rms,
                'zcr': zcr,
                'path': str(audio_path)
            }

            logger.debug(f"🔇 Echo filter: Robot audio cached (RMS={rms:.3f}, ZCR={zcr:.3f})")

        except Exception as e:
            logger.error(f"🔇 Echo filter: Error loading robot audio: {e}")
            self.last_robot_audio = None

    def is_probable_echo(self, barge_in_audio_path: str, threshold_rms: float = 0.8) -> bool:
        """
        Détecte si audio barge-in est probablement un echo.

        Checks effectués:
        1. Volume trop élevé (>threshold_rms = probable haut-parleur)
        2. RMS similaire au robot (±20%)
        3. Zero-crossing rate similaire (±30%)

        Args:
            barge_in_audio_path: Chemin vers fichier audio barge-in (.wav)
            threshold_rms: Seuil volume max (default: 0.8)

        Returns:
            True si probable echo, False sinon
        """
        if not self.enabled:
            return False

        if not self.last_robot_audio:
            logger.debug("🔇 Echo filter: No robot audio cached, skipping check")
            return False

        try:
            barge_in_path = Path(barge_in_audio_path)
            if not barge_in_path.exists():
                logger.warning(f"🔇 Echo filter: Barge-in file not found: {barge_in_path}")
                return False

            # Lire audio barge-in
            audio, sr = sf.read(str(barge_in_path))

            # Si stereo, prendre LEFT channel (client)
            if audio.ndim == 2:
                audio = audio[:, 0]  # LEFT channel = client

            # Calculer features
            rms = float(np.sqrt(np.mean(audio**2)))
            zcr = float(np.mean(np.abs(np.diff(np.sign(audio)))))

            # Check 1: Volume trop élevé (probable haut-parleur)
            if rms > threshold_rms:
                logger.info(f"🔇 Echo filter: ECHO DETECTED (high volume: {rms:.3f} > {threshold_rms})")
                return True

            # Check 2: RMS similaire au robot (±20%)
            robot_rms = self.last_robot_audio['rms']
            if robot_rms > 0:  # Éviter division par zéro
                rms_diff = abs(rms - robot_rms) / robot_rms
                if rms_diff < 0.20:
                    logger.info(f"🔇 Echo filter: ECHO DETECTED (similar RMS: diff={rms_diff:.1%})")
                    return True

            # Check 3: Zero-crossing similaire (±30%)
            robot_zcr = self.last_robot_audio['zcr']
            if robot_zcr > 0:  # Éviter division par zéro
                zcr_diff = abs(zcr - robot_zcr) / robot_zcr
                if zcr_diff < 0.30:
                    logger.info(f"🔇 Echo filter: ECHO DETECTED (similar ZCR: diff={zcr_diff:.1%})")
                    return True

            # Pas d'echo détecté
            logger.debug(f"🔇 Echo filter: No echo (RMS={rms:.3f}, ZCR={zcr:.3f})")
            return False

        except Exception as e:
            logger.error(f"🔇 Echo filter: Error checking echo: {e}")
            return False  # En cas d'erreur, ne pas bloquer barge-in

    def clear(self):
        """Vider le cache audio robot."""
        self.last_robot_audio = None
        logger.debug("🔇 Echo filter: Cache cleared")
