"""
Recording Cleanup Service
=========================

Service de nettoyage automatique des recordings FreeSWITCH pour éviter
saturation disque en production.

Fonctionnalités:
1. Nettoyage automatique des recordings > N jours (configurable)
2. Monitoring espace disque
3. Logs détaillés pour audit

Usage:
    # Nettoyage manuel
    cleanup = RecordingCleanup(recordings_dir="/usr/local/freeswitch/recordings/")
    cleanup.cleanup_old_recordings(days=7)

    # Monitoring
    disk_info = cleanup.get_disk_usage()
    print(f"Espace utilisé: {disk_info['used_gb']:.2f} GB")
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class RecordingCleanup:
    """
    Service de nettoyage automatique des recordings FreeSWITCH.
    """

    def __init__(self, recordings_dir: str):
        """
        Initialise le service de cleanup.

        Args:
            recordings_dir: Répertoire des recordings FreeSWITCH
        """
        self.recordings_dir = Path(recordings_dir)
        if not self.recordings_dir.exists():
            logger.warning(f"Recordings directory does not exist: {recordings_dir}")

    def get_disk_usage(self) -> Dict[str, float]:
        """
        Obtenir l'utilisation disque du répertoire recordings.

        Returns:
            Dict avec: total_gb, used_gb, free_gb, percent_used
        """
        try:
            stats = shutil.disk_usage(str(self.recordings_dir))
            return {
                'total_gb': stats.total / (1024**3),
                'used_gb': stats.used / (1024**3),
                'free_gb': stats.free / (1024**3),
                'percent_used': (stats.used / stats.total) * 100
            }
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent_used': 0}

    def get_recordings_stats(self) -> Dict[str, any]:
        """
        Obtenir statistiques sur les recordings.

        Returns:
            Dict avec: count, total_size_gb, oldest_date, newest_date
        """
        try:
            recordings = list(self.recordings_dir.rglob("*.wav"))
            if not recordings:
                return {
                    'count': 0,
                    'total_size_gb': 0,
                    'oldest_date': None,
                    'newest_date': None
                }

            total_size = sum(f.stat().st_size for f in recordings)
            oldest = min(recordings, key=lambda f: f.stat().st_mtime)
            newest = max(recordings, key=lambda f: f.stat().st_mtime)

            return {
                'count': len(recordings),
                'total_size_gb': total_size / (1024**3),
                'oldest_date': datetime.fromtimestamp(oldest.stat().st_mtime),
                'newest_date': datetime.fromtimestamp(newest.stat().st_mtime)
            }
        except Exception as e:
            logger.error(f"Error getting recordings stats: {e}")
            return {'count': 0, 'total_size_gb': 0, 'oldest_date': None, 'newest_date': None}

    def cleanup_old_recordings(self, days: int = 7, dry_run: bool = False) -> Dict[str, any]:
        """
        Supprimer recordings plus vieux que N jours.

        Args:
            days: Nombre de jours de rétention (défaut: 7)
            dry_run: Si True, simule sans supprimer (défaut: False)

        Returns:
            Dict avec: deleted_count, freed_gb, errors
        """
        if not self.recordings_dir.exists():
            logger.warning(f"Recordings directory does not exist: {self.recordings_dir}")
            return {'deleted_count': 0, 'freed_gb': 0, 'errors': []}

        try:
            # Calculer date limite
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_timestamp = cutoff_date.timestamp()

            logger.info(f"🧹 Starting cleanup: delete recordings older than {days} days (before {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})")
            if dry_run:
                logger.info("🔍 DRY RUN mode - no files will be deleted")

            # Trouver tous les WAV
            recordings = list(self.recordings_dir.rglob("*.wav"))
            deleted_count = 0
            freed_bytes = 0
            errors = []

            for recording in recordings:
                try:
                    # Vérifier âge du fichier
                    file_mtime = recording.stat().st_mtime
                    if file_mtime < cutoff_timestamp:
                        file_size = recording.stat().st_size
                        file_date = datetime.fromtimestamp(file_mtime)

                        if dry_run:
                            logger.debug(f"[DRY RUN] Would delete: {recording.name} ({file_size / 1024**2:.2f} MB, created {file_date.strftime('%Y-%m-%d %H:%M:%S')})")
                        else:
                            logger.debug(f"Deleting: {recording.name} ({file_size / 1024**2:.2f} MB, created {file_date.strftime('%Y-%m-%d %H:%M:%S')})")
                            recording.unlink()

                        deleted_count += 1
                        freed_bytes += file_size

                except Exception as e:
                    error_msg = f"Error deleting {recording.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            freed_gb = freed_bytes / (1024**3)

            if dry_run:
                logger.info(f"🔍 DRY RUN complete: {deleted_count} files would be deleted, {freed_gb:.2f} GB would be freed")
            else:
                logger.info(f"✅ Cleanup complete: {deleted_count} files deleted, {freed_gb:.2f} GB freed")

            return {
                'deleted_count': deleted_count,
                'freed_gb': freed_gb,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            return {'deleted_count': 0, 'freed_gb': 0, 'errors': [str(e)]}

    def cleanup_by_disk_threshold(self, threshold_percent: float = 80.0, target_percent: float = 70.0, dry_run: bool = False) -> Dict[str, any]:
        """
        Supprimer vieux recordings jusqu'à atteindre target disk usage.

        Utile pour éviter saturation disque en production.

        Args:
            threshold_percent: Seuil déclenchement (défaut: 80%)
            target_percent: Objectif après nettoyage (défaut: 70%)
            dry_run: Si True, simule sans supprimer (défaut: False)

        Returns:
            Dict avec: deleted_count, freed_gb, errors, disk_usage_before, disk_usage_after
        """
        # Vérifier usage actuel
        disk_usage = self.get_disk_usage()
        current_percent = disk_usage['percent_used']

        logger.info(f"💾 Current disk usage: {current_percent:.1f}%")

        if current_percent < threshold_percent:
            logger.info(f"✅ Disk usage below threshold ({threshold_percent}%) - no cleanup needed")
            return {
                'deleted_count': 0,
                'freed_gb': 0,
                'errors': [],
                'disk_usage_before': current_percent,
                'disk_usage_after': current_percent
            }

        logger.warning(f"⚠️ Disk usage above threshold ({current_percent:.1f}% >= {threshold_percent}%)")
        logger.info(f"🧹 Starting cleanup to reach target: {target_percent}%")

        if dry_run:
            logger.info("🔍 DRY RUN mode - no files will be deleted")

        # Calculer espace à libérer
        total_bytes = disk_usage['total_gb'] * (1024**3)
        bytes_to_free = (current_percent - target_percent) / 100 * total_bytes

        logger.info(f"📊 Need to free: {bytes_to_free / (1024**3):.2f} GB")

        # Obtenir tous les recordings triés par date (plus vieux en premier)
        recordings = sorted(
            self.recordings_dir.rglob("*.wav"),
            key=lambda f: f.stat().st_mtime
        )

        deleted_count = 0
        freed_bytes = 0
        errors = []

        for recording in recordings:
            if freed_bytes >= bytes_to_free:
                break  # Objectif atteint

            try:
                file_size = recording.stat().st_size
                file_date = datetime.fromtimestamp(recording.stat().st_mtime)

                if dry_run:
                    logger.debug(f"[DRY RUN] Would delete: {recording.name} ({file_size / 1024**2:.2f} MB, created {file_date.strftime('%Y-%m-%d %H:%M:%S')})")
                else:
                    logger.debug(f"Deleting: {recording.name} ({file_size / 1024**2:.2f} MB, created {file_date.strftime('%Y-%m-%d %H:%M:%S')})")
                    recording.unlink()

                deleted_count += 1
                freed_bytes += file_size

            except Exception as e:
                error_msg = f"Error deleting {recording.name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        freed_gb = freed_bytes / (1024**3)

        # Vérifier usage final
        disk_usage_after = self.get_disk_usage()
        final_percent = disk_usage_after['percent_used']

        if dry_run:
            logger.info(f"🔍 DRY RUN complete: {deleted_count} files would be deleted, {freed_gb:.2f} GB would be freed")
            logger.info(f"💾 Estimated disk usage after: {final_percent:.1f}%")
        else:
            logger.info(f"✅ Cleanup complete: {deleted_count} files deleted, {freed_gb:.2f} GB freed")
            logger.info(f"💾 Disk usage after: {final_percent:.1f}%")

        return {
            'deleted_count': deleted_count,
            'freed_gb': freed_gb,
            'errors': errors,
            'disk_usage_before': current_percent,
            'disk_usage_after': final_percent
        }
