"""
Campaign Manager - MiniBotPanel v3

Gestionnaire de campagnes d'appels.

Fonctionnalités:
- Création campagnes depuis contacts
- Gestion file d'attente (throttling intelligent)
- Lancement appels avec respect limites système
- Mise à jour stats temps réel
- Gestion pause/reprise/arrêt

Utilisation:
    from system.campaign_manager import CampaignManager

    manager = CampaignManager()
    campaign_id = manager.create_campaign(
        name="Vente Produit X",
        contact_ids=[1, 2, 3, 4, 5],
        scenario="production"
    )

    manager.start_campaign(campaign_id)
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_

from system.database import SessionLocal
from system.models import Campaign, Call, Contact, CampaignStatus, CallStatus, CallResult
from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

class CampaignManager:
    """Gestionnaire de campagnes d'appels."""

    def __init__(self, robot=None):
        """
        Initialise le gestionnaire de campagnes.

        Args:
            robot: Instance RobotFreeSWITCH (optionnel, peut être injecté plus tard)
        """
        logger.info("Initializing CampaignManager...")

        # Référence vers robot FreeSWITCH
        self.robot = robot

        if not self.robot:
            # Import lazy pour éviter circular imports
            try:
                from system.robot_freeswitch import RobotFreeSWITCH
                self.robot = RobotFreeSWITCH()
                logger.info("✅ Robot FreeSWITCH initialized internally")
            except Exception as e:
                logger.warning(f"⚠️ Robot not available: {e}")
                self.robot = None

        logger.info("✅ CampaignManager initialized")

    def get_eligible_contacts(self, limit: Optional[int] = None, include_no_answer: bool = False) -> List[int]:
        """
        Récupère les contacts éligibles pour être appelés.

        Critères:
        - last_result = NEW (par défaut, ou NEW + NO_ANSWER si include_no_answer=True)
        - NOT blacklist
        - NOT opt_out

        Args:
            limit: Nombre max de contacts (None = tous)
            include_no_answer: Inclure les NO_ANSWER dans les éligibles (défaut: False)

        Returns:
            Liste des IDs contacts éligibles
        """
        db = SessionLocal()
        try:
            # Par défaut: seulement NEW (pas de rappel automatique)
            if include_no_answer:
                eligible_results = [CallResult.NEW, CallResult.NO_ANSWER]
                logger.info("Mode rappel activé: NEW + NO_ANSWER")
            else:
                eligible_results = [CallResult.NEW]
                logger.info("Mode normal: NEW uniquement (pas de rappel automatique)")

            query = db.query(Contact.id).filter(
                Contact.last_result.in_(eligible_results),
                Contact.blacklist == False,
                Contact.opt_out == False
            )

            if limit:
                query = query.limit(limit)

            contact_ids = [c.id for c in query.all()]

            logger.info(f"Found {len(contact_ids)} eligible contacts")
            return contact_ids

        finally:
            db.close()

    def create_campaign(
        self,
        name: str,
        contact_ids: List[int],
        scenario: str = "production",
        description: Optional[str] = None
    ) -> int:
        """
        Crée une nouvelle campagne.

        Args:
            name: Nom de la campagne
            contact_ids: Liste des IDs contacts à appeler
            scenario: Scénario à utiliser
            description: Description optionnelle

        Returns:
            ID de la campagne créée
        """
        logger.info(f"Creating campaign: {name} ({len(contact_ids)} contacts, scenario: {scenario})")

        db = SessionLocal()
        try:
            # Créer campagne
            campaign = Campaign(
                name=name,
                description=description,
                scenario=scenario,
                status=CampaignStatus.PENDING
            )
            db.add(campaign)
            db.flush()

            # Créer calls pour chaque contact
            for contact_id in contact_ids:
                call = Call(
                    uuid=f"pending_{contact_id}_{datetime.utcnow().timestamp()}",
                    contact_id=contact_id,
                    campaign_id=campaign.id,
                    status=CallStatus.PENDING
                )
                db.add(call)

            db.commit()

            # Update stats
            campaign.stats["total"] = len(contact_ids)
            db.commit()

            logger.info(f"✅ Campaign created: ID {campaign.id}")
            return campaign.id

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to create campaign: {e}")
            raise
        finally:
            db.close()

    def start_campaign(self, campaign_id: int):
        """
        Démarre une campagne (lance les appels).

        Gère la file d'attente, les batchs et les retry automatiques.

        Args:
            campaign_id: ID de la campagne
        """
        logger.info(f"Starting campaign {campaign_id}")

        db = SessionLocal()
        try:
            # Récupérer campagne
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return

            # Mettre à jour statut
            campaign.status = CampaignStatus.RUNNING
            campaign.started_at = datetime.now()
            db.commit()

            # Boucle de traitement de la file d'attente
            while campaign.status == CampaignStatus.RUNNING:
                # Compter appels en cours
                active_calls = db.query(Call).filter(
                    Call.campaign_id == campaign_id,
                    Call.status.in_([CallStatus.CALLING, CallStatus.RINGING,
                                     CallStatus.ANSWERED, CallStatus.IN_PROGRESS])
                ).count()

                # Si on peut lancer plus d'appels
                available_slots = campaign.max_concurrent_calls - active_calls

                if available_slots > 0:
                    # Prendre un batch depuis la file
                    batch_size = min(campaign.batch_size, available_slots)

                    # Récupérer appels à lancer (PENDING ou RETRY, triés par priorité et scheduled_at)
                    now = datetime.now()
                    calls_to_make = db.query(Call).filter(
                        Call.campaign_id == campaign_id,
                        Call.status.in_([CallStatus.PENDING, CallStatus.RETRY]),
                        or_(Call.scheduled_at == None, Call.scheduled_at <= now)
                    ).order_by(
                        Call.queue_priority.desc(),  # Priorité d'abord
                        Call.scheduled_at.asc()       # Puis par date planifiée
                    ).limit(batch_size).all()

                    # Lancer les appels du batch
                    for call in calls_to_make:
                        # Vérifier contact pas en blocklist
                        contact = db.query(Contact).filter(Contact.id == call.contact_id).first()

                        if contact.blacklist or contact.opt_out:
                            call.status = CallStatus.CANCELLED
                            call.result = CallResult.NOT_INTERESTED
                            call.notes = "Contact in blocklist"
                            db.commit()
                            continue

                        # Marquer comme en cours
                        call.status = CallStatus.QUEUED
                        call.last_attempt_at = datetime.now()
                        call.retry_count += 1
                        db.commit()

                        # Lancer appel via robot
                        if self.robot:
                            try:
                                # Générer UUID unique
                                import uuid as uuid_lib
                                call_uuid = str(uuid_lib.uuid4())
                                call.uuid = call_uuid
                                call.status = CallStatus.CALLING
                                call.started_at = datetime.now()
                                db.commit()

                                # Originate via FreeSWITCH
                                result_uuid = self.robot.originate_call(
                                    phone_number=contact.phone,
                                    campaign_id=campaign_id,
                                    scenario=campaign.scenario,
                                    uuid=call_uuid,
                                    contact_id=contact.id,
                                    caller_id=campaign.caller_id or config.DEFAULT_CALLER_ID,
                                    retry_count=call.retry_count,
                                    variables={
                                        "first_name": contact.first_name or "",
                                        "last_name": contact.last_name or "",
                                        "company": contact.company or "",
                                        "email": contact.email or ""
                                    }
                                )

                                if result_uuid:
                                    logger.info(f"✅ Call initiated: {result_uuid} to {contact.phone}")
                                else:
                                    logger.error(f"Failed to originate call to {contact.phone}")
                                    call.status = CallStatus.FAILED
                                    db.commit()

                            except Exception as e:
                                logger.error(f"Failed to originate call: {e}")
                                call.status = CallStatus.FAILED
                                db.commit()

                        # Délai entre appels
                        import time
                        time.sleep(campaign.delay_between_calls)

                # Vérifier si campagne terminée
                pending_count = db.query(Call).filter(
                    Call.campaign_id == campaign_id,
                    Call.status.in_([CallStatus.PENDING, CallStatus.RETRY, CallStatus.QUEUED])
                ).count()

                if pending_count == 0 and active_calls == 0:
                    # Plus rien à faire
                    campaign.status = CampaignStatus.COMPLETED
                    campaign.completed_at = datetime.now()
                    db.commit()
                    logger.info(f"✅ Campaign {campaign_id} completed")
                    break

                # Pause entre checks
                import time
                time.sleep(5)  # Check toutes les 5 secondes

        except Exception as e:
            logger.error(f"Error in campaign {campaign_id}: {e}")
            campaign.status = CampaignStatus.FAILED
            db.commit()
        finally:
            db.close()

    def pause_campaign(self, campaign_id: int):
        """
        Met en pause une campagne.
        Arrête le lancement de nouveaux appels mais laisse les appels en cours terminer.

        Args:
            campaign_id: ID de la campagne
        """
        logger.info(f"Pausing campaign {campaign_id}")

        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False

            if campaign.status != CampaignStatus.RUNNING:
                logger.warning(f"Campaign {campaign_id} is not running (status: {campaign.status})")
                return False

            # Mettre à jour statut
            campaign.status = CampaignStatus.PAUSED
            campaign.paused_at = datetime.now()
            db.commit()

            logger.info(f"✅ Campaign {campaign_id} paused")
            return True

        except Exception as e:
            logger.error(f"Error pausing campaign {campaign_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def resume_campaign(self, campaign_id: int):
        """
        Reprend une campagne en pause.

        Args:
            campaign_id: ID de la campagne
        """
        logger.info(f"Resuming campaign {campaign_id}")

        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False

            if campaign.status != CampaignStatus.PAUSED:
                logger.warning(f"Campaign {campaign_id} is not paused (status: {campaign.status})")
                return False

            # Mettre à jour statut
            campaign.status = CampaignStatus.RUNNING
            campaign.resumed_at = datetime.now()
            db.commit()

            logger.info(f"✅ Campaign {campaign_id} resumed")
            return True

        except Exception as e:
            logger.error(f"Error resuming campaign {campaign_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def stop_campaign(self, campaign_id: int):
        """
        Arrête une campagne définitivement.
        Marque tous les appels PENDING comme CANCELLED.

        Args:
            campaign_id: ID de la campagne
        """
        logger.info(f"Stopping campaign {campaign_id}")

        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False

            if campaign.status in [CampaignStatus.COMPLETED, CampaignStatus.CANCELLED]:
                logger.warning(f"Campaign {campaign_id} already stopped (status: {campaign.status})")
                return False

            # Mettre à jour statut campagne
            campaign.status = CampaignStatus.CANCELLED
            campaign.stopped_at = datetime.now()

            # Annuler tous les appels PENDING/RETRY
            cancelled_count = db.query(Call).filter(
                Call.campaign_id == campaign_id,
                Call.status.in_([CallStatus.PENDING, CallStatus.RETRY, CallStatus.QUEUED])
            ).update({
                "status": CallStatus.CANCELLED,
                "ended_at": datetime.now(),
                "notes": "Campaign stopped by user"
            }, synchronize_session=False)

            db.commit()

            logger.info(f"✅ Campaign {campaign_id} stopped ({cancelled_count} calls cancelled)")
            return True

        except Exception as e:
            logger.error(f"Error stopping campaign {campaign_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def get_campaign_stats(self, campaign_id: int) -> dict:
        """
        Récupère les statistiques d'une campagne.

        Args:
            campaign_id: ID de la campagne

        Returns:
            Dict avec statistiques
        """
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {}

            return campaign.stats

        finally:
            db.close()

    def update_campaign_stats(self, campaign_id: int, call_result: dict):
        """
        Met à jour les statistiques d'une campagne après un appel.

        Args:
            campaign_id: ID de la campagne
            call_result: Résultat de l'appel (dict avec status, result, sentiment, etc.)
        """
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return

            # Récupérer stats actuelles
            stats = campaign.stats or {}

            # Incrémenter completed
            stats["completed"] = stats.get("completed", 0) + 1

            # Incrémenter selon résultat
            if call_result.get("result") == "lead":
                stats["leads"] = stats.get("leads", 0) + 1
            elif call_result.get("result") == "not_interested":
                stats["not_interested"] = stats.get("not_interested", 0) + 1
            elif call_result.get("result") == "answering_machine":
                stats["answering_machines"] = stats.get("answering_machines", 0) + 1
            elif call_result.get("result") == "no_answer":
                stats["no_answer"] = stats.get("no_answer", 0) + 1

            # Mettre à jour moyenne durée
            if call_result.get("duration"):
                current_avg = stats.get("avg_duration", 0)
                completed = stats.get("completed", 1)
                new_avg = ((current_avg * (completed - 1)) + call_result["duration"]) / completed
                stats["avg_duration"] = round(new_avg, 1)

            # Sentiment
            sentiment = call_result.get("sentiment")
            if sentiment == "positive":
                stats["sentiment_positive"] = stats.get("sentiment_positive", 0) + 1
            elif sentiment == "neutral":
                stats["sentiment_neutral"] = stats.get("sentiment_neutral", 0) + 1
            elif sentiment == "negative":
                stats["sentiment_negative"] = stats.get("sentiment_negative", 0) + 1

            # Sauvegarder
            campaign.stats = stats
            db.commit()

        finally:
            db.close()

    def handle_call_result(self, call_id: int, status: CallStatus, result: CallResult = None):
        """
        Traite le résultat d'un appel et gère les retry si nécessaire.

        Si NO_ANSWER et retry_count < max_retries, replanifie l'appel.

        Args:
            call_id: ID de l'appel
            status: Statut final de l'appel
            result: Résultat métier (optionnel)
        """
        db = SessionLocal()
        try:
            # Récupérer appel et campagne
            call = db.query(Call).filter(Call.id == call_id).first()
            if not call:
                return

            campaign = db.query(Campaign).filter(Campaign.id == call.campaign_id).first()
            if not campaign:
                return

            # Mettre à jour appel
            call.status = status
            if result:
                call.result = result
            call.ended_at = datetime.now()

            # Calculer durée
            if call.started_at:
                call.duration = int((call.ended_at - call.started_at).total_seconds())

            # Si NO_ANSWER et retry activé, planifier retry
            if (status == CallStatus.NO_ANSWER and
                campaign.retry_enabled and
                call.retry_count < campaign.max_retries):

                # Calculer prochaine tentative
                delay_minutes = campaign.retry_delay_minutes
                next_attempt = datetime.now() + timedelta(minutes=delay_minutes)

                # Créer nouvelle entrée pour retry
                call.status = CallStatus.RETRY
                call.scheduled_at = next_attempt
                call.queue_priority = 1  # Priorité plus haute pour retry

                logger.info(f"📞 Call {call_id} scheduled for retry at {next_attempt} "
                            f"(attempt {call.retry_count + 1}/{campaign.max_retries})")

            # Si BUSY, retry immédiat avec priorité haute
            elif status == CallStatus.BUSY and call.retry_count < campaign.max_retries:
                call.status = CallStatus.RETRY
                call.scheduled_at = datetime.now() + timedelta(minutes=5)  # Dans 5 minutes
                call.queue_priority = 2  # Priorité haute

                logger.info(f"📞 Call {call_id} BUSY, retry in 5 minutes")

            db.commit()

            # Mettre à jour stats campagne
            self.update_campaign_stats(
                campaign_id=campaign.id,
                call_result={
                    "status": status.value,
                    "result": result.value if result else None,
                    "duration": call.duration,
                    "sentiment": call.sentiment.value if call.sentiment else None
                }
            )

        except Exception as e:
            logger.error(f"Error handling call result: {e}")
        finally:
            db.close()
