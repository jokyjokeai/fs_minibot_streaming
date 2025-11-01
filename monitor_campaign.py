#!/usr/bin/env python3
"""
Monitor Campaign - MiniBotPanel v3

Monitoring temps réel CLI d'une campagne.

Usage:
    python monitor_campaign.py --campaign-id 42
"""

import argparse
import logging
import time
import sys
import os
from datetime import datetime

from system.database import SessionLocal
from system.models import Campaign, Call, CallStatus
from system.stats_collector import StatsCollector

logging.basicConfig(level=logging.WARNING)  # Only warnings/errors
logger = logging.getLogger(__name__)

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_stats_table(campaign, stats):
    """Print formatted stats table"""
    print("\n" + "="*80)
    print(f"📊 CAMPAIGN MONITOR: {campaign.name} (ID: {campaign.id})")
    print("="*80)
    print(f"Status: {campaign.status.value:15} | Scenario: {campaign.scenario:20}")
    print(f"Started: {campaign.started_at.strftime('%Y-%m-%d %H:%M:%S') if campaign.started_at else 'N/A':30}")
    print("-"*80)

    # Progress
    total = stats.get("total", 0)
    completed = stats.get("completed", 0)
    in_progress = stats.get("in_progress", 0)
    pending = total - completed - in_progress

    print("\n📈 PROGRESS:")
    print(f"  Total contacts:     {total:6}")
    print(f"  Completed:          {completed:6} ({stats.get('completion_rate', 0):5.1f}%)")
    print(f"  In progress:        {in_progress:6}")
    print(f"  Pending:            {pending:6}")

    # Results
    print("\n🎯 RESULTS:")
    print(f"  Leads:              {stats.get('leads', 0):6} ({stats.get('lead_rate', 0):5.1f}%)")
    print(f"  Not interested:     {stats.get('not_interested', 0):6}")
    print(f"  Callbacks:          {stats.get('callbacks', 0):6}")
    print(f"  No answer:          {stats.get('no_answer', 0):6}")
    print(f"  Answering machines: {stats.get('answering_machines', 0):6}")
    print(f"  Failed:             {stats.get('failed', 0):6}")

    # Performance
    print("\n⚡ PERFORMANCE:")
    print(f"  Avg duration:       {stats.get('avg_duration', 0):6.1f}s")
    print(f"  Conversion rate:    {stats.get('conversion_rate', 0):6.1f}%")
    print(f"  Calls/min:          {stats.get('calls_per_minute', 0):6.2f}")
    print(f"  Campaign duration:  {stats.get('campaign_duration', 'N/A')}")

    # Sentiment
    sentiment_total = stats.get('sentiment_positive', 0) + stats.get('sentiment_neutral', 0) + stats.get('sentiment_negative', 0)
    if sentiment_total > 0:
        print("\n💭 SENTIMENT:")
        print(f"  Positive:           {stats.get('sentiment_positive', 0):6} ({stats.get('sentiment_positive', 0)/sentiment_total*100:5.1f}%)")
        print(f"  Neutral:            {stats.get('sentiment_neutral', 0):6} ({stats.get('sentiment_neutral', 0)/sentiment_total*100:5.1f}%)")
        print(f"  Negative:           {stats.get('sentiment_negative', 0):6} ({stats.get('sentiment_negative', 0)/sentiment_total*100:5.1f}%)")

    print("\n" + "="*80)
    print(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
    print("Press Ctrl+C to stop monitoring")
    print("="*80)

def main():
    parser = argparse.ArgumentParser(description="Monitoring temps réel campagne")
    parser.add_argument("--campaign-id", type=int, required=True, help="ID campagne")
    parser.add_argument("--refresh", type=int, default=2, help="Interval refresh (secondes)")
    parser.add_argument("--no-clear", action="store_true", help="Ne pas effacer l'écran à chaque refresh")

    args = parser.parse_args()

    # Initialize stats collector
    collector = StatsCollector()

    db = SessionLocal()

    # Verify campaign exists
    campaign = db.query(Campaign).filter(Campaign.id == args.campaign_id).first()
    if not campaign:
        logger.error(f"❌ Campaign {args.campaign_id} not found")
        sys.exit(1)

    print(f"\n📊 Starting monitor for campaign: {campaign.name}")
    print(f"   Refresh interval: {args.refresh} seconds")
    print(f"   Press Ctrl+C to stop\n")
    time.sleep(2)  # Give user time to read

    try:
        while True:
            # Récupérer stats from DB
            calls = db.query(Call).filter(Call.campaign_id == args.campaign_id).all()

            # Manually build stats (since collector may not have been used)
            for call in calls:
                # Record in collector if not already
                if call.status == CallStatus.COMPLETED:
                    if call.result:
                        collector.record_call_event(
                            campaign_id=args.campaign_id,
                            event_type=call.result.value,
                            data={
                                "duration": call.duration,
                                "sentiment": call.sentiment.value if call.sentiment else None
                            }
                        )

            # Get live stats
            stats = collector.get_live_stats(args.campaign_id)

            # Refresh campaign data
            db.refresh(campaign)

            # Clear screen and display
            if not args.no_clear:
                clear_screen()

            print_stats_table(campaign, stats)

            time.sleep(args.refresh)

    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")
        db.close()

    except Exception as e:
        logger.error(f"❌ Error during monitoring: {e}", exc_info=True)
        db.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
