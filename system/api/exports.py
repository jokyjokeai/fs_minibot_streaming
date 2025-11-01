"""
Exports API - MiniBotPanel v3

Endpoints pour exports CSV et téléchargements audio/transcriptions.
"""

import logging
import csv
import io
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_

from system.database import get_db
from system.models import Campaign, Call, Contact, CallStatus, CallResult
from system.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/campaign/{campaign_id}/csv")
def export_campaign_csv(
    campaign_id: int,
    include_links: bool = True,
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Exporte les résultats d'une campagne en CSV.

    Args:
        campaign_id: ID de la campagne
        include_links: Inclure liens audio/transcriptions

    Returns:
        StreamingResponse avec CSV
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Récupérer tous les appels de la campagne avec contacts
    calls = (
        db.query(Call, Contact)
        .join(Contact, Call.contact_id == Contact.id)
        .filter(Call.campaign_id == campaign_id)
        .order_by(Call.created_at)
        .all()
    )

    # Créer CSV en mémoire
    output = io.StringIO()

    # Colonnes CSV
    fieldnames = [
        "phone", "first_name", "last_name", "email", "company",
        "status", "result", "duration", "sentiment", "confidence",
        "amd_result", "created_at", "ended_at"
    ]

    if include_links:
        fieldnames.extend(["audio_link", "transcript_link"])

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    # Écrire les lignes
    base_url = f"http://{config.API_HOST}:{config.API_PORT}"

    for call, contact in calls:
        row = {
            "phone": contact.phone,
            "first_name": contact.first_name or "",
            "last_name": contact.last_name or "",
            "email": contact.email or "",
            "company": contact.company or "",
            "status": call.status.value if call.status else "",
            "result": call.result.value if call.result else "",
            "duration": call.duration or 0,
            "sentiment": call.sentiment.value if call.sentiment else "",
            "confidence": call.confidence or 0.0,
            "amd_result": call.amd_result or "",
            "created_at": call.created_at.isoformat() if call.created_at else "",
            "ended_at": call.ended_at.isoformat() if call.ended_at else ""
        }

        if include_links:
            # Ajouter liens vers audio et transcriptions
            if call.recording_path:
                row["audio_link"] = f"{base_url}/api/exports/audio/{call.uuid}"
            else:
                row["audio_link"] = ""

            if call.transcription_path:
                row["transcript_link"] = f"{base_url}/api/exports/transcript/{call.uuid}"
            else:
                row["transcript_link"] = ""

        writer.writerow(row)

    # Créer response
    output.seek(0)

    filename = f"campaign_{campaign_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        io.BytesIO(output.read().encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/campaign/{campaign_id}/json")
def export_campaign_json(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Exporte les résultats d'une campagne en JSON.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Dict avec toutes les données
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Récupérer tous les appels
    calls = (
        db.query(Call, Contact)
        .join(Contact, Call.contact_id == Contact.id)
        .filter(Call.campaign_id == campaign_id)
        .order_by(Call.created_at)
        .all()
    )

    # Construire réponse
    result = {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "scenario": campaign.scenario,
            "status": campaign.status.value if campaign.status else None,
            "stats": campaign.stats,
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
            "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
        },
        "calls": []
    }

    for call, contact in calls:
        call_data = {
            "uuid": call.uuid,
            "contact": {
                "phone": contact.phone,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "email": contact.email,
                "company": contact.company
            },
            "status": call.status.value if call.status else None,
            "result": call.result.value if call.result else None,
            "duration": call.duration,
            "sentiment": call.sentiment.value if call.sentiment else None,
            "confidence": call.confidence,
            "amd_result": call.amd_result,
            "metadata": call.metadata,
            "created_at": call.created_at.isoformat() if call.created_at else None,
            "answered_at": call.answered_at.isoformat() if call.answered_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None
        }
        result["calls"].append(call_data)

    return result


@router.get("/audio/{call_uuid}")
def download_audio(
    call_uuid: str,
    db: Session = Depends(get_db)
) -> FileResponse:
    """
    Télécharge l'enregistrement audio d'un appel.

    Args:
        call_uuid: UUID de l'appel

    Returns:
        FileResponse avec fichier audio
    """
    # Récupérer l'appel
    call = db.query(Call).filter(Call.uuid == call_uuid).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {call_uuid} not found")

    if not call.recording_path:
        raise HTTPException(status_code=404, detail="No recording available for this call")

    # Construire chemin complet
    audio_path = config.BASE_DIR / call.recording_path

    if not audio_path.exists():
        logger.error(f"Recording file not found: {audio_path}")
        raise HTTPException(status_code=404, detail="Recording file not found")

    # Retourner fichier
    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"call_{call_uuid}.wav",
        headers={
            "Content-Disposition": f"attachment; filename=call_{call_uuid}.wav"
        }
    )


@router.get("/transcript/{call_uuid}")
def download_transcript(
    call_uuid: str,
    format: str = "txt",
    db: Session = Depends(get_db)
) -> Response:
    """
    Télécharge la transcription d'un appel.

    Args:
        call_uuid: UUID de l'appel
        format: Format (txt ou json)

    Returns:
        Response avec transcription
    """
    # Récupérer l'appel
    call = db.query(Call).filter(Call.uuid == call_uuid).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {call_uuid} not found")

    if not call.transcription_path:
        raise HTTPException(status_code=404, detail="No transcription available for this call")

    # Construire chemin complet
    transcript_path = config.BASE_DIR / call.transcription_path

    if not transcript_path.exists():
        logger.error(f"Transcription file not found: {transcript_path}")
        raise HTTPException(status_code=404, detail="Transcription file not found")

    # Lire contenu
    with open(transcript_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if format == "json":
        # Retourner en JSON
        return {
            "call_uuid": call_uuid,
            "transcription": content,
            "duration": call.duration,
            "sentiment": call.sentiment.value if call.sentiment else None
        }
    else:
        # Retourner en texte brut
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=transcript_{call_uuid}.txt"
            }
        )


@router.get("/summary/{campaign_id}")
def export_summary(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Génère un résumé de campagne pour rapport.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Dict avec résumé détaillé
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Statistiques détaillées
    total_calls = db.query(Call).filter(Call.campaign_id == campaign_id).count()

    completed_calls = db.query(Call).filter(
        and_(
            Call.campaign_id == campaign_id,
            Call.status == CallStatus.COMPLETED
        )
    ).count()

    # Résultats par type
    results_count = {}
    for result in CallResult:
        count = db.query(Call).filter(
            and_(
                Call.campaign_id == campaign_id,
                Call.result == result
            )
        ).count()
        results_count[result.value] = count

    # Durée moyenne
    from sqlalchemy import func
    avg_duration = db.query(func.avg(Call.duration)).filter(
        and_(
            Call.campaign_id == campaign_id,
            Call.duration > 0
        )
    ).scalar() or 0

    # Taux de conversion
    leads_count = results_count.get("lead", 0)
    conversion_rate = (leads_count / completed_calls * 100) if completed_calls > 0 else 0

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "scenario": campaign.scenario,
            "status": campaign.status.value if campaign.status else None
        },
        "summary": {
            "total_calls": total_calls,
            "completed_calls": completed_calls,
            "completion_rate": f"{(completed_calls/total_calls*100):.1f}%" if total_calls > 0 else "0%",
            "results": results_count,
            "conversion_rate": f"{conversion_rate:.1f}%",
            "average_duration": f"{avg_duration:.1f}s",
            "date_range": {
                "started": campaign.started_at.isoformat() if campaign.started_at else None,
                "completed": campaign.completed_at.isoformat() if campaign.completed_at else None
            }
        }
    }
