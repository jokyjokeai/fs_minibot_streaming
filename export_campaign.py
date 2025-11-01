#!/usr/bin/env python3
"""
Export Campaign - MiniBotPanel v3

Export résultats campagne en CSV complet.

Usage:
    python export_campaign.py --campaign-id 42
    python export_campaign.py --campaign-id 42 --output results.csv

CSV output includes:
    - Contact info (phone, name, company, email)
    - Call results (status, result, duration, started_at, ended_at)
    - Sentiment & transcriptions
    - Audio/transcription file links
"""

import argparse
import logging
import csv
import sys
import json
from datetime import datetime
from pathlib import Path

from system.database import SessionLocal
from system.models import Campaign, Call, Contact

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_campaign_to_csv(campaign_id: int, output_file: str):
    """
    Export campaign results to CSV.

    Includes all call details, transcriptions, and metadata.
    """
    db = SessionLocal()

    try:
        # 1. Récupérer campagne
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            logger.error(f"❌ Campaign {campaign_id} not found")
            return False

        logger.info(f"📊 Exporting campaign: {campaign.name}")

        # 2. Récupérer tous les appels avec contacts
        calls = db.query(Call).join(Contact).filter(
            Call.campaign_id == campaign_id
        ).all()

        if not calls:
            logger.warning("⚠️ No calls found for this campaign")
            return False

        logger.info(f"   Found {len(calls)} calls")

        # 3. Générer CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'call_id',
                'call_uuid',
                'phone',
                'first_name',
                'last_name',
                'company',
                'email',
                'status',
                'result',
                'duration_seconds',
                'started_at',
                'ended_at',
                'amd_result',
                'sentiment',
                'transcriptions',
                'intents',
                'audio_file',
                'notes',
                'retry_count'
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for call in calls:
                contact = call.contact

                # Parse metadata for transcriptions and intents
                metadata = call.metadata or {}
                transcriptions = metadata.get('transcriptions', [])
                intents = metadata.get('intents', [])

                # Format transcriptions as single string
                transcriptions_str = ' | '.join(transcriptions) if transcriptions else ''
                intents_str = ', '.join(intents) if intents else ''

                # Audio file path (if exists)
                audio_file = ''
                if call.recording_path:
                    audio_file = call.recording_path

                row = {
                    'call_id': call.id,
                    'call_uuid': call.uuid,
                    'phone': contact.phone if contact else '',
                    'first_name': contact.first_name if contact else '',
                    'last_name': contact.last_name if contact else '',
                    'company': contact.company if contact else '',
                    'email': contact.email if contact else '',
                    'status': call.status.value if call.status else '',
                    'result': call.result.value if call.result else '',
                    'duration_seconds': call.duration or 0,
                    'started_at': call.started_at.isoformat() if call.started_at else '',
                    'ended_at': call.ended_at.isoformat() if call.ended_at else '',
                    'amd_result': call.amd_result or '',
                    'sentiment': call.sentiment.value if call.sentiment else '',
                    'transcriptions': transcriptions_str,
                    'intents': intents_str,
                    'audio_file': audio_file,
                    'notes': call.notes or '',
                    'retry_count': call.retry_count or 0
                }

                writer.writerow(row)

        logger.info(f"✅ Exported {len(calls)} calls to {output_file}")

        # 4. Generate summary
        summary_file = output_file.replace('.csv', '_summary.txt')
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"CAMPAIGN EXPORT SUMMARY\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Campaign: {campaign.name} (ID: {campaign.id})\n")
            f.write(f"Scenario: {campaign.scenario}\n")
            f.write(f"Status: {campaign.status.value}\n")
            f.write(f"Started: {campaign.started_at.strftime('%Y-%m-%d %H:%M:%S') if campaign.started_at else 'N/A'}\n")
            f.write(f"Completed: {campaign.completed_at.strftime('%Y-%m-%d %H:%M:%S') if campaign.completed_at else 'N/A'}\n\n")

            # Stats
            stats = campaign.stats or {}
            f.write(f"STATISTICS\n")
            f.write(f"{'-'*60}\n")
            f.write(f"Total calls: {len(calls)}\n")
            f.write(f"Leads: {stats.get('leads', 0)}\n")
            f.write(f"Not interested: {stats.get('not_interested', 0)}\n")
            f.write(f"Callbacks: {stats.get('callbacks', 0)}\n")
            f.write(f"No answer: {stats.get('no_answer', 0)}\n")
            f.write(f"Answering machines: {stats.get('answering_machines', 0)}\n")
            f.write(f"Failed: {stats.get('failed', 0)}\n\n")
            f.write(f"Average duration: {stats.get('avg_duration', 0):.1f}s\n")
            f.write(f"Conversion rate: {stats.get('leads', 0) / len(calls) * 100 if len(calls) > 0 else 0:.1f}%\n")

        logger.info(f"✅ Summary saved to {summary_file}")

        return True

    except Exception as e:
        logger.error(f"❌ Error exporting campaign: {e}", exc_info=True)
        return False

    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Export campagne en CSV")
    parser.add_argument("--campaign-id", type=int, required=True, help="ID campagne")
    parser.add_argument("--output", help="Fichier sortie CSV (default: campaign_<id>_export.csv)")

    args = parser.parse_args()

    # Default output filename
    if not args.output:
        args.output = f"campaign_{args.campaign_id}_export.csv"

    logger.info(f"📤 Exporting campaign {args.campaign_id}...")

    success = export_campaign_to_csv(args.campaign_id, args.output)

    if success:
        logger.info(f"\n✅ Export complete!")
        logger.info(f"   CSV file: {args.output}")
        logger.info(f"   Summary: {args.output.replace('.csv', '_summary.txt')}")
    else:
        logger.error("❌ Export failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
