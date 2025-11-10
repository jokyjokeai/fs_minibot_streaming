#!/usr/bin/env python3
"""
Recording Cleanup Service - Daemon Mode
========================================

Service de nettoyage automatique des recordings FreeSWITCH.
Conçu pour être exécuté via systemd timer.

Usage:
    # Via systemd (recommandé)
    sudo systemctl start minibot-recording-cleanup

    # Manuel
    python system/services/recording_cleanup_service.py

    # Dry run
    python system/services/recording_cleanup_service.py --dry-run
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire parent au path pour imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from system.config import config
from system.services.recording_cleanup import RecordingCleanup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOGS_DIR / 'recording_cleanup.log')
    ]
)

logger = logging.getLogger(__name__)


def run_cleanup(dry_run: bool = False) -> int:
    """
    Exécute le nettoyage automatique des recordings.

    Args:
        dry_run: Si True, simulation sans suppression

    Returns:
        0 si succès, 1 si erreur
    """
    try:
        logger.info("=" * 70)
        logger.info("🧹 MiniBotPanel - Recording Cleanup Service")
        logger.info(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

        # Vérifier si cleanup activé
        if not config.RECORDING_CLEANUP_ENABLED:
            logger.warning("⚠️  Recording cleanup is DISABLED in config")
            logger.info("Set RECORDING_CLEANUP_ENABLED=true in .env to enable")
            return 0  # Pas une erreur, juste désactivé

        # Initialize cleanup service
        cleanup = RecordingCleanup(str(config.RECORDINGS_DIR))

        # Afficher statistiques initiales
        logger.info("\n📊 Status Before Cleanup:")
        logger.info("-" * 70)

        disk_usage = cleanup.get_disk_usage()
        logger.info(f"💾 Disk: {disk_usage['used_gb']:.2f} GB / {disk_usage['total_gb']:.2f} GB ({disk_usage['percent_used']:.1f}%)")

        recordings_stats = cleanup.get_recordings_stats()
        logger.info(f"📁 Recordings: {recordings_stats['count']} files ({recordings_stats['total_size_gb']:.2f} GB)")

        if recordings_stats['oldest_date']:
            logger.info(f"📅 Oldest: {recordings_stats['oldest_date'].strftime('%Y-%m-%d %H:%M:%S')}")

        # Exécuter cleanup time-based
        logger.info("\n🧹 Running Time-Based Cleanup:")
        logger.info("-" * 70)
        logger.info(f"Retention policy: Delete recordings older than {config.RECORDING_RETENTION_DAYS} days")

        if dry_run:
            logger.info("⚠️  DRY RUN MODE - No files will be deleted")

        result = cleanup.cleanup_old_recordings(
            days=config.RECORDING_RETENTION_DAYS,
            dry_run=dry_run
        )

        logger.info("\n📊 Time-Based Cleanup Results:")
        logger.info("-" * 70)
        logger.info(f"{'Would delete' if dry_run else 'Deleted'}: {result['deleted_count']} files")
        logger.info(f"{'Would free' if dry_run else 'Freed'}: {result['freed_gb']:.2f} GB")

        if result['errors']:
            logger.warning(f"⚠️  Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:
                logger.error(f"  - {error}")

        # Vérifier si cleanup par seuil disque nécessaire
        disk_usage_after_time = cleanup.get_disk_usage()
        current_percent = disk_usage_after_time['percent_used']

        if current_percent >= config.RECORDING_CLEANUP_DISK_THRESHOLD:
            logger.warning(f"\n⚠️  Disk usage still high: {current_percent:.1f}% >= {config.RECORDING_CLEANUP_DISK_THRESHOLD}%")
            logger.info("🧹 Running Disk-Based Cleanup:")
            logger.info("-" * 70)

            disk_result = cleanup.cleanup_by_disk_threshold(
                threshold_percent=config.RECORDING_CLEANUP_DISK_THRESHOLD,
                target_percent=config.RECORDING_CLEANUP_DISK_TARGET,
                dry_run=dry_run
            )

            logger.info("\n📊 Disk-Based Cleanup Results:")
            logger.info("-" * 70)
            logger.info(f"{'Would delete' if dry_run else 'Deleted'}: {disk_result['deleted_count']} additional files")
            logger.info(f"{'Would free' if dry_run else 'Freed'}: {disk_result['freed_gb']:.2f} GB")
            logger.info(f"Disk usage: {disk_result['disk_usage_before']:.1f}% → {disk_result['disk_usage_after']:.1f}%")

            if disk_result['errors']:
                logger.warning(f"⚠️  Errors: {len(disk_result['errors'])}")
        else:
            logger.info(f"\n✅ Disk usage OK: {current_percent:.1f}% < {config.RECORDING_CLEANUP_DISK_THRESHOLD}%")

        # Afficher statistiques finales
        logger.info("\n📊 Final Status:")
        logger.info("-" * 70)

        disk_usage_final = cleanup.get_disk_usage()
        logger.info(f"💾 Disk: {disk_usage_final['used_gb']:.2f} GB / {disk_usage_final['total_gb']:.2f} GB ({disk_usage_final['percent_used']:.1f}%)")

        recordings_stats_final = cleanup.get_recordings_stats()
        logger.info(f"📁 Recordings: {recordings_stats_final['count']} files ({recordings_stats_final['total_size_gb']:.2f} GB)")

        logger.info("\n✅ Cleanup completed successfully")
        logger.info(f"📅 Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

        return 0

    except Exception as e:
        logger.error(f"❌ Fatal error during cleanup: {e}", exc_info=True)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='MiniBotPanel - Recording Cleanup Service',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulation sans suppression réelle'
    )

    args = parser.parse_args()

    return run_cleanup(dry_run=args.dry_run)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
