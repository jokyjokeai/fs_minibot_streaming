"""
Stats API - MiniBotPanel v3

Endpoints pour statistiques temps réel.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from system.database import get_db
from system.models import Campaign, Call, Contact, CallStatus, CallResult, Sentiment, CampaignStatus
from system.config import config
from system.stats_collector import StatsCollector

logger = logging.getLogger(__name__)

# Import app_start_time from main to calculate uptime
# Using delayed import to avoid circular dependency
_app_start_time = None

def get_app_start_time():
    """Get app start time with lazy loading to avoid circular import."""
    global _app_start_time
    if _app_start_time is None:
        try:
            from system.api.main import app_start_time
            _app_start_time = app_start_time
        except (ImportError, AttributeError):
            _app_start_time = datetime.utcnow()  # Fallback
    return _app_start_time

router = APIRouter(prefix="/stats", tags=["statistics"])

# Instance globale du collector pour cache en mémoire
stats_collector = StatsCollector()


@router.get("/campaign/{campaign_id}")
def get_campaign_stats(
    campaign_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Récupère les statistiques complètes d'une campagne.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Dict avec toutes les statistiques
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Stats de base
    total_calls = db.query(Call).filter(Call.campaign_id == campaign_id).count()

    # Stats par statut
    status_counts = {}
    for status in CallStatus:
        count = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.status == status
            )
        ).count()
        status_counts[status.value] = count

    # Stats par résultat
    result_counts = {}
    for result in CallResult:
        count = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.result == result
            )
        ).count()
        result_counts[result.value] = count

    # Stats sentiment
    sentiment_counts = {}
    for sentiment in Sentiment:
        count = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.sentiment == sentiment
            )
        ).count()
        sentiment_counts[sentiment.value] = count

    # Durées moyennes
    avg_duration = db.query(func.avg(Call.duration)).filter(
        and_(
            Call.campaign_id == campaign_id,
            Call.duration > 0
        )
    ).scalar() or 0

    # AMD stats
    amd_human = db.query(Call).filter(
        and_(
            Call.campaign_id == campaign_id,
            Call.amd_result == "human"
        )
    ).count()

    amd_machine = db.query(Call).filter(
        and_(
            Call.campaign_id == campaign_id,
            Call.amd_result == "machine"
        )
    ).count()

    # Taux de conversion
    completed = status_counts.get("completed", 0)
    leads = result_counts.get("lead", 0)
    conversion_rate = (leads / completed * 100) if completed > 0 else 0

    # Temps écoulé
    elapsed_time = None
    if campaign.started_at:
        if campaign.completed_at:
            elapsed_time = (campaign.completed_at - campaign.started_at).total_seconds()
        else:
            elapsed_time = (datetime.utcnow() - campaign.started_at).total_seconds()

    # Construire réponse
    stats = {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "campaign_status": campaign.status.value if campaign.status else None,
        "total": total_calls,
        "status": status_counts,
        "results": result_counts,
        "sentiment": sentiment_counts,
        "amd": {
            "human": amd_human,
            "machine": amd_machine,
            "detection_rate": f"{(amd_human/(amd_human+amd_machine)*100):.1f}%" if (amd_human+amd_machine) > 0 else "N/A"
        },
        "averages": {
            "duration": f"{avg_duration:.1f}s",
            "calls_per_hour": f"{(completed/elapsed_time*3600):.1f}" if elapsed_time and elapsed_time > 0 else "0"
        },
        "conversion": {
            "leads": leads,
            "rate": f"{conversion_rate:.1f}%"
        },
        "timestamps": {
            "created": campaign.created_at.isoformat() if campaign.created_at else None,
            "started": campaign.started_at.isoformat() if campaign.started_at else None,
            "completed": campaign.completed_at.isoformat() if campaign.completed_at else None,
            "elapsed_seconds": elapsed_time
        }
    }

    return stats


@router.get("/campaign/{campaign_id}/live")
def get_live_stats(
    campaign_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Récupère les statistiques live pour monitoring temps réel.

    Utilise le cache en mémoire pour performance.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Dict avec stats formatées pour CLI
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Récupérer depuis cache si disponible
    cached_stats = stats_collector.get_live_stats(campaign_id)

    # Si pas de cache ou trop vieux, recalculer
    if not cached_stats or not cached_stats.get("last_update"):
        # Calculer stats fraîches
        total = db.query(Call).filter(Call.campaign_id == campaign_id).count()

        completed = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.status == CallStatus.COMPLETED
            )
        ).count()

        in_progress = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.status == CallStatus.IN_PROGRESS
            )
        ).count()

        # Résultats principaux (3 status seulement)
        leads = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.result == CallResult.LEADS
            )
        ).count()

        not_interested = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.result == CallResult.NOT_INTERESTED
            )
        ).count()

        no_answer = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.result == CallResult.NO_ANSWER
            )
        ).count()

        # AMD stats (detection répondeur)
        answering_machines = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.amd_result == "machine"
            )
        ).count()

        # Durée moyenne
        avg_duration = db.query(func.avg(Call.duration)).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.duration > 0
            )
        ).scalar() or 0

        # Sentiment global
        positive = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.sentiment == Sentiment.POSITIVE
            )
        ).count()

        neutral = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.sentiment == Sentiment.NEUTRAL
            )
        ).count()

        negative = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.sentiment == Sentiment.NEGATIVE
            )
        ).count()

        # Calculer ETA
        eta_completion = None
        if campaign.status == CampaignStatus.RUNNING and completed > 0 and in_progress > 0:
            pending = total - completed
            if campaign.started_at:
                elapsed = (datetime.utcnow() - campaign.started_at).total_seconds()
                rate = completed / elapsed if elapsed > 0 else 0
                if rate > 0:
                    eta_seconds = pending / rate
                    eta_completion = datetime.utcnow() + timedelta(seconds=eta_seconds)

        # Stats live
        live_stats = {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "status": campaign.status.value if campaign.status else None,
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": total - completed - in_progress,
            "results": {
                "leads": leads,
                "not_interested": not_interested,
                "answering_machines": answering_machines,
                "no_answer": no_answer
            },
            "percentages": {
                "completion": f"{(completed/total*100):.1f}%" if total > 0 else "0%",
                "leads": f"{(leads/completed*100):.1f}%" if completed > 0 else "0%",
                "not_interested": f"{(not_interested/completed*100):.1f}%" if completed > 0 else "0%"
            },
            "duration": {
                "average": f"{avg_duration:.1f}s",
                "total": f"{(avg_duration * completed / 60):.1f}min"
            },
            "sentiment": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "positive_rate": f"{(positive/completed*100):.1f}%" if completed > 0 else "0%"
            },
            "eta": eta_completion.isoformat() if eta_completion else None,
            "last_update": datetime.utcnow().isoformat()
        }

        # Mettre en cache
        stats_collector.record_call_event(
            campaign_id=campaign_id,
            event_type="stats_update",
            data=live_stats
        )

        return live_stats

    return cached_stats


@router.get("/campaign/{campaign_id}/timeline")
def get_campaign_timeline(
    campaign_id: int,
    interval: int = 60,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Récupère timeline d'activité de la campagne.

    Args:
        campaign_id: ID de la campagne
        interval: Intervalle en minutes (défaut: 60)

    Returns:
        Timeline avec points de données
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    if not campaign.started_at:
        return {"timeline": [], "message": "Campaign not started yet"}

    # Calculer intervalles
    start_time = campaign.started_at
    end_time = campaign.completed_at or datetime.utcnow()

    timeline = []
    current_time = start_time

    while current_time < end_time:
        next_time = current_time + timedelta(minutes=interval)

        # Compter appels dans cet intervalle
        calls_count = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.created_at >= current_time,
                Call.created_at < next_time
            )
        ).count()

        leads_count = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.created_at >= current_time,
                Call.created_at < next_time,
                Call.result == CallResult.LEADS
            )
        ).count()

        timeline.append({
            "timestamp": current_time.isoformat(),
            "calls": calls_count,
            "leads": leads_count
        })

        current_time = next_time

    return {
        "campaign_id": campaign_id,
        "interval_minutes": interval,
        "timeline": timeline
    }


@router.get("/system")
def get_system_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Récupère les statistiques globales du système.

    Returns:
        Dict avec stats système
    """
    # Total campagnes
    total_campaigns = db.query(Campaign).count()
    active_campaigns = db.query(Campaign).filter(
        Campaign.status == CampaignStatus.RUNNING
    ).count()

    # Total appels
    total_calls = db.query(Call).count()
    calls_today = db.query(Call).filter(
        Call.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
    ).count()

    # Total contacts
    total_contacts = db.query(Contact).count()

    # Appels en cours (toutes campagnes)
    active_calls = db.query(Call).filter(
        Call.status == CallStatus.IN_PROGRESS
    ).count()

    # Performance moyenne
    avg_duration = db.query(func.avg(Call.duration)).scalar() or 0
    avg_conversion = 0

    # Taux conversion global
    total_completed = db.query(Call).filter(
        Call.status == CallStatus.COMPLETED
    ).count()

    total_leads = db.query(Call).filter(
        Call.result == CallResult.LEADS
    ).count()

    if total_completed > 0:
        avg_conversion = (total_leads / total_completed) * 100

    # Calculate uptime
    start_time = get_app_start_time()
    if start_time:
        uptime_delta = datetime.utcnow() - start_time
        uptime_seconds = int(uptime_delta.total_seconds())
        uptime_hours = uptime_seconds // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60
        uptime_str = f"{uptime_hours}h {uptime_minutes}m"
    else:
        uptime_str = "N/A"

    return {
        "system": {
            "version": "3.0.0",
            "status": "operational",
            "uptime": uptime_str
        },
        "campaigns": {
            "total": total_campaigns,
            "active": active_campaigns,
            "completed": total_campaigns - active_campaigns
        },
        "calls": {
            "total": total_calls,
            "today": calls_today,
            "active_now": active_calls,
            "average_duration": f"{avg_duration:.1f}s"
        },
        "contacts": {
            "total": total_contacts
        },
        "performance": {
            "conversion_rate": f"{avg_conversion:.1f}%",
            "total_leads": total_leads
        },
        "limits": {
            "max_concurrent_calls": config.MAX_CONCURRENT_CALLS,
            "current_usage": f"{(active_calls/config.MAX_CONCURRENT_CALLS*100):.1f}%"
        }
    }
