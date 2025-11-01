"""
Campaigns API - MiniBotPanel v3

Endpoints pour gestion des campagnes.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from system.database import get_db
from system.models import Campaign, Call, Contact, CampaignStatus, CallStatus
from system.campaign_manager import CampaignManager
from system.config import config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["campaigns"])  # Prefix retiré (géré dans main.py)

# Instance du manager
campaign_manager = CampaignManager()


# Schemas Pydantic pour validation
class CreateCampaignRequest(BaseModel):
    """Requête de création de campagne."""
    name: str = Field(..., min_length=1, max_length=200, description="Nom de la campagne")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    contact_ids: List[int] = Field(..., min_items=1, description="IDs des contacts à appeler")
    scenario: str = Field(..., description="Nom du scénario à utiliser")
    max_concurrent_calls: Optional[int] = Field(
        None,
        ge=1,
        le=50,
        description="Nombre max d'appels simultanés"
    )
    batch_size: Optional[int] = Field(
        None,
        ge=1,
        le=20,
        description="Taille des batchs d'appels"
    )
    retry_enabled: Optional[bool] = Field(None, description="Activer le retry automatique")
    max_retries: Optional[int] = Field(
        None,
        ge=0,
        le=5,
        description="Nombre max de retry pour NO_ANSWER"
    )

    @validator('contact_ids')
    def validate_contact_ids(cls, v):
        if len(v) > 10000:
            raise ValueError("Maximum 10000 contacts par campagne")
        return v


class CampaignResponse(BaseModel):
    """Réponse avec détails campagne."""
    id: int
    name: str
    description: Optional[str]
    scenario: str
    status: str
    max_concurrent_calls: int
    batch_size: int
    retry_enabled: bool
    max_retries: int
    stats: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        orm_mode = True


class UpdateCampaignRequest(BaseModel):
    """Requête de mise à jour campagne."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    max_concurrent_calls: Optional[int] = Field(None, ge=1, le=50)


# Endpoints
@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    request: CreateCampaignRequest,
    db: Session = Depends(get_db)
):
    """
    Crée une nouvelle campagne.

    Args:
        request: Données de la campagne

    Returns:
        CampaignResponse avec détails de la campagne créée
    """
    logger.info(f"Creating campaign: {request.name}")

    # Vérifier que les contacts existent
    valid_contacts = db.query(Contact.id).filter(
        Contact.id.in_(request.contact_ids)
    ).count()

    if valid_contacts != len(request.contact_ids):
        raise HTTPException(
            status_code=400,
            detail=f"Some contact IDs are invalid. Found {valid_contacts} of {len(request.contact_ids)}"
        )

    # Créer campagne via manager
    try:
        campaign_id = campaign_manager.create_campaign(
            name=request.name,
            contact_ids=request.contact_ids,
            scenario=request.scenario,
            description=request.description
        )

        # Récupérer campagne créée
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

        # Mettre à jour les paramètres optionnels
        if request.max_concurrent_calls:
            campaign.max_concurrent_calls = request.max_concurrent_calls
        if request.batch_size:
            campaign.batch_size = request.batch_size
        if request.retry_enabled is not None:
            campaign.retry_enabled = request.retry_enabled
        if request.max_retries is not None:
            campaign.max_retries = request.max_retries

        db.commit()

        logger.info(f"✅ Campaign created: {campaign_id}")

        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            scenario=campaign.scenario,
            status=campaign.status.value if campaign.status else "pending",
            max_concurrent_calls=campaign.max_concurrent_calls,
            stats=campaign.stats,
            created_at=campaign.created_at,
            started_at=campaign.started_at,
            completed_at=campaign.completed_at
        )

    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
def list_campaigns(
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    limit: int = Query(50, ge=1, le=500, description="Limite de résultats"),
    offset: int = Query(0, ge=0, description="Offset pour pagination"),
    db: Session = Depends(get_db)
):
    """
    Liste les campagnes.

    Args:
        status: Filtrer par statut (pending, running, paused, completed, cancelled)
        limit: Nombre max de résultats
        offset: Offset pour pagination

    Returns:
        Liste des campagnes
    """
    query = db.query(Campaign)

    # Filtrer par statut si spécifié
    if status:
        try:
            campaign_status = CampaignStatus(status)
            query = query.filter(Campaign.status == campaign_status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in CampaignStatus]}"
            )

    # Total avant pagination
    total = query.count()

    # Appliquer pagination
    campaigns = query.order_by(Campaign.created_at.desc()).limit(limit).offset(offset).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "scenario": c.scenario,
                "status": c.status.value if c.status else None,
                "stats": c.stats,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in campaigns
        ]
    }


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Récupère les détails d'une campagne.

    Args:
        campaign_id: ID de la campagne

    Returns:
        CampaignResponse avec détails complets
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        scenario=campaign.scenario,
        status=campaign.status.value if campaign.status else "pending",
        max_concurrent_calls=campaign.max_concurrent_calls,
        stats=campaign.stats,
        created_at=campaign.created_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at
    )


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    request: UpdateCampaignRequest,
    db: Session = Depends(get_db)
):
    """
    Met à jour une campagne.

    Seules les campagnes non démarrées peuvent être modifiées complètement.

    Args:
        campaign_id: ID de la campagne
        request: Données à modifier

    Returns:
        CampaignResponse avec détails mis à jour
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Vérifier si modifications autorisées
    if campaign.status not in [CampaignStatus.PENDING, CampaignStatus.PAUSED]:
        # Seul max_concurrent_calls peut être modifié en cours
        if request.name or request.description:
            raise HTTPException(
                status_code=400,
                detail="Cannot modify campaign name/description while running"
            )

    # Appliquer modifications
    if request.name:
        campaign.name = request.name

    if request.description is not None:
        campaign.description = request.description

    if request.max_concurrent_calls:
        campaign.max_concurrent_calls = request.max_concurrent_calls

    campaign.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    logger.info(f"Campaign {campaign_id} updated")

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        scenario=campaign.scenario,
        status=campaign.status.value if campaign.status else "pending",
        max_concurrent_calls=campaign.max_concurrent_calls,
        stats=campaign.stats,
        created_at=campaign.created_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at
    )


@router.post("/{campaign_id}/start", status_code=status.HTTP_200_OK)
def start_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Démarre une campagne.

    Lance les appels de manière asynchrone.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Message de confirmation
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Vérifier statut
    if campaign.status == CampaignStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Campaign is already running"
        )

    if campaign.status in [CampaignStatus.COMPLETED, CampaignStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start a {campaign.status.value} campaign"
        )

    # Marquer comme démarrée
    campaign.status = CampaignStatus.RUNNING
    campaign.started_at = datetime.utcnow()
    db.commit()

    # Lancer en arrière-plan
    background_tasks.add_task(campaign_manager.start_campaign, campaign_id)

    logger.info(f"Campaign {campaign_id} started")

    return {
        "status": "success",
        "message": f"Campaign {campaign_id} started",
        "campaign_id": campaign_id
    }


@router.post("/{campaign_id}/pause", status_code=status.HTTP_200_OK)
def pause_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Met en pause une campagne.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Message de confirmation
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Vérifier statut
    if campaign.status != CampaignStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Can only pause a running campaign"
        )

    # Mettre en pause via manager
    campaign_manager.pause_campaign(campaign_id)

    # Mettre à jour DB
    campaign.status = CampaignStatus.PAUSED
    db.commit()

    logger.info(f"Campaign {campaign_id} paused")

    return {
        "status": "success",
        "message": f"Campaign {campaign_id} paused",
        "campaign_id": campaign_id
    }


@router.post("/{campaign_id}/resume", status_code=status.HTTP_200_OK)
def resume_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Reprend une campagne en pause.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Message de confirmation
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Vérifier statut
    if campaign.status != CampaignStatus.PAUSED:
        raise HTTPException(
            status_code=400,
            detail="Can only resume a paused campaign"
        )

    # Reprendre
    campaign.status = CampaignStatus.RUNNING
    db.commit()

    # Relancer en arrière-plan
    background_tasks.add_task(campaign_manager.resume_campaign, campaign_id)

    logger.info(f"Campaign {campaign_id} resumed")

    return {
        "status": "success",
        "message": f"Campaign {campaign_id} resumed",
        "campaign_id": campaign_id
    }


@router.post("/{campaign_id}/stop", status_code=status.HTTP_200_OK)
def stop_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Arrête définitivement une campagne.

    Args:
        campaign_id: ID de la campagne

    Returns:
        Message avec stats finales
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Vérifier statut
    if campaign.status in [CampaignStatus.COMPLETED, CampaignStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Campaign is already {campaign.status.value}"
        )

    # Arrêter via manager
    campaign_manager.stop_campaign(campaign_id)

    # Mettre à jour DB
    campaign.status = CampaignStatus.CANCELLED
    campaign.completed_at = datetime.utcnow()

    # Marquer appels PENDING comme CANCELLED
    db.query(Call).filter(
        and_(
            Call.campaign_id == campaign_id,
            Call.status == CallStatus.PENDING
        )
    ).update({"status": CallStatus.CANCELLED})

    db.commit()

    logger.info(f"Campaign {campaign_id} stopped")

    return {
        "status": "success",
        "message": f"Campaign {campaign_id} stopped",
        "campaign_id": campaign_id,
        "final_stats": campaign.stats
    }


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Supprime une campagne.

    Seules les campagnes non démarrées peuvent être supprimées.

    Args:
        campaign_id: ID de la campagne
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Vérifier qu'elle n'a pas été démarrée
    if campaign.status != CampaignStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a campaign that has been started"
        )

    # Supprimer appels associés
    db.query(Call).filter(Call.campaign_id == campaign_id).delete()

    # Supprimer campagne
    db.delete(campaign)
    db.commit()

    logger.info(f"Campaign {campaign_id} deleted")

    return None


@router.get("/{campaign_id}/calls", response_model=Dict[str, Any])
def get_campaign_calls(
    campaign_id: int,
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    result: Optional[str] = Query(None, description="Filtrer par résultat"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Liste les appels d'une campagne.

    Args:
        campaign_id: ID de la campagne
        status: Filtrer par statut d'appel
        result: Filtrer par résultat
        limit: Limite de résultats
        offset: Offset pour pagination

    Returns:
        Liste des appels avec détails
    """
    # Vérifier que campagne existe
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found"
        )

    # Construire query
    query = db.query(Call, Contact).join(
        Contact, Call.contact_id == Contact.id
    ).filter(Call.campaign_id == campaign_id)

    # Filtres
    if status:
        query = query.filter(Call.status == CallStatus(status))

    if result:
        query = query.filter(Call.result == result)

    # Total avant pagination
    total = query.count()

    # Pagination
    calls = query.order_by(Call.created_at.desc()).limit(limit).offset(offset).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "calls": [
            {
                "id": call.id,
                "uuid": call.uuid,
                "contact": {
                    "phone": contact.phone,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "company": contact.company
                },
                "status": call.status.value if call.status else None,
                "result": call.result.value if call.result else None,
                "duration": call.duration,
                "sentiment": call.sentiment.value if call.sentiment else None,
                "created_at": call.created_at.isoformat() if call.created_at else None
            }
            for call, contact in calls
        ]
    }
