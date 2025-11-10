#!/usr/bin/env python3
"""
Script de nettoyage automatique des recordings FreeSWITCH
==========================================================

Ce script peut être lancé:
1. Manuellement: python scripts/cleanup_recordings.py
2. Via cron (quotidien recommandé): 0 2 * * * /path/to/venv/bin/python /path/to/scripts/cleanup_recordings.py
3. Via systemd timer

Options:
  --dry-run         Simulation sans suppression
  --days N          Rétention en jours (défaut: 7)
  --disk-mode       Mode nettoyage par seuil disque
  --threshold N     Seuil déclenchement (défaut: 80%)
  --target N        Objectif après nettoyage (défaut: 70%)

Exemples:
  # Simulation (voir ce qui serait supprimé)
  python scripts/cleanup_recordings.py --dry-run

  # Supprimer recordings > 7 jours
  python scripts/cleanup_recordings.py

  # Supprimer recordings > 14 jours
  python scripts/cleanup_recordings.py --days 14

  # Mode seuil disque (supprimer jusqu'à 70% si > 80%)
  python scripts/cleanup_recordings.py --disk-mode

  # Mode seuil disque avec valeurs custom
  python scripts/cleanup_recordings.py --disk-mode --threshold 85 --target 75
"""

import sys
import argparse
import logging
from pathlib import Path

# Ajouter le répertoire parent au path pour imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from system.config import config
from system.services.recording_cleanup import RecordingCleanup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Nettoyage automatique des recordings FreeSWITCH',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulation sans suppression réelle'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=config.RECORDING_RETENTION_DAYS,
        help=f'Rétention en jours (défaut: {config.RECORDING_RETENTION_DAYS})'
    )
    parser.add_argument(
        '--disk-mode',
        action='store_true',
        help='Mode nettoyage par seuil disque'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=config.RECORDING_CLEANUP_DISK_THRESHOLD,
        help=f'Seuil déclenchement en %% (défaut: {config.RECORDING_CLEANUP_DISK_THRESHOLD})'
    )
    parser.add_argument(
        '--target',
        type=float,
        default=config.RECORDING_CLEANUP_DISK_TARGET,
        help=f'Objectif après nettoyage en %% (défaut: {config.RECORDING_CLEANUP_DISK_TARGET})'
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Afficher statistiques seulement, pas de nettoyage'
    )

    args = parser.parse_args()

    # Vérifier si cleanup activé
    if not config.RECORDING_CLEANUP_ENABLED and not args.dry_run:
        logger.warning("⚠️  Recording cleanup is DISABLED in config")
        logger.info("Set RECORDING_CLEANUP_ENABLED=true in .env to enable")
        return 1

    logger.info("=" * 70)
    logger.info("🧹 FreeSWITCH Recordings Cleanup")
    logger.info("=" * 70)

    # Initialize cleanup service
    cleanup = RecordingCleanup(str(config.RECORDINGS_DIR))

    # Afficher statistiques initiales
    logger.info("\n📊 Current Status:")
    logger.info("-" * 70)

    disk_usage = cleanup.get_disk_usage()
    logger.info(f"💾 Disk Usage: {disk_usage['used_gb']:.2f} GB / {disk_usage['total_gb']:.2f} GB ({disk_usage['percent_used']:.1f}%)")
    logger.info(f"💾 Free Space: {disk_usage['free_gb']:.2f} GB")

    recordings_stats = cleanup.get_recordings_stats()
    logger.info(f"📁 Total Recordings: {recordings_stats['count']} files")
    logger.info(f"📁 Total Size: {recordings_stats['total_size_gb']:.2f} GB")

    if recordings_stats['oldest_date']:
        logger.info(f"📅 Oldest Recording: {recordings_stats['oldest_date'].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📅 Newest Recording: {recordings_stats['newest_date'].strftime('%Y-%m-%d %H:%M:%S')}")

    # Mode stats seulement
    if args.no_cleanup:
        logger.info("\n✅ Statistics only mode - no cleanup performed")
        return 0

    # Exécuter cleanup
    logger.info("\n🧹 Cleanup Operation:")
    logger.info("-" * 70)

    if args.disk_mode:
        logger.info(f"Mode: Disk threshold cleanup")
        logger.info(f"Threshold: {args.threshold}%")
        logger.info(f"Target: {args.target}%")
        if args.dry_run:
            logger.info("⚠️  DRY RUN - No files will be deleted")

        result = cleanup.cleanup_by_disk_threshold(
            threshold_percent=args.threshold,
            target_percent=args.target,
            dry_run=args.dry_run
        )

        logger.info("\n📊 Results:")
        logger.info("-" * 70)
        logger.info(f"{'Would delete' if args.dry_run else 'Deleted'}: {result['deleted_count']} files")
        logger.info(f"{'Would free' if args.dry_run else 'Freed'}: {result['freed_gb']:.2f} GB")
        logger.info(f"Disk usage before: {result['disk_usage_before']:.1f}%")
        logger.info(f"Disk usage after: {result['disk_usage_after']:.1f}%")

        if result['errors']:
            logger.warning(f"\n⚠️  Errors encountered: {len(result['errors'])}")
            for error in result['errors'][:5]:  # Show first 5 errors
                logger.error(f"  - {error}")

    else:
        logger.info(f"Mode: Time-based cleanup")
        logger.info(f"Retention: {args.days} days")
        if args.dry_run:
            logger.info("⚠️  DRY RUN - No files will be deleted")

        result = cleanup.cleanup_old_recordings(
            days=args.days,
            dry_run=args.dry_run
        )

        logger.info("\n📊 Results:")
        logger.info("-" * 70)
        logger.info(f"{'Would delete' if args.dry_run else 'Deleted'}: {result['deleted_count']} files")
        logger.info(f"{'Would free' if args.dry_run else 'Freed'}: {result['freed_gb']:.2f} GB")

        if result['errors']:
            logger.warning(f"\n⚠️  Errors encountered: {len(result['errors'])}")
            for error in result['errors'][:5]:  # Show first 5 errors
                logger.error(f"  - {error}")

    # Afficher statistiques finales
    if not args.dry_run:
        logger.info("\n📊 Final Status:")
        logger.info("-" * 70)

        disk_usage_final = cleanup.get_disk_usage()
        logger.info(f"💾 Disk Usage: {disk_usage_final['used_gb']:.2f} GB / {disk_usage_final['total_gb']:.2f} GB ({disk_usage_final['percent_used']:.1f}%)")
        logger.info(f"💾 Free Space: {disk_usage_final['free_gb']:.2f} GB")

        recordings_stats_final = cleanup.get_recordings_stats()
        logger.info(f"📁 Total Recordings: {recordings_stats_final['count']} files")
        logger.info(f"📁 Total Size: {recordings_stats_final['total_size_gb']:.2f} GB")

    logger.info("\n✅ Cleanup completed successfully")
    logger.info("=" * 70)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
