#!/usr/bin/env python3
"""
Batch Caller - MiniBotPanel v3

Worker qui gère la file d'attente et lance les appels par batch.

Équivalent du badge_caller de l'ancien système Asterisk.

Fonctionnalités:
- Lecture de la file d'attente DB
- Lancement par batch configurable
- Gestion des retry NO_ANSWER
- Respect des limites de concurrence
- Logs détaillés

Utilisation:
    python -m system.batch_caller

    Ou depuis code:
    from system.batch_caller import BatchCaller

    caller = BatchCaller()
    caller.start()
"""

import time
import threading
from datetime import datetime, timedelta
from typing import List, Optional
import signal
import sys

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from system.database import SessionLocal, engine
from system.models import Call, Campaign, Contact, CallStatus, CallResult, CampaignStatus
from system.config import config
from system.logger import get_logger
from system.robot_freeswitch import RobotFreeSWITCH

# Logger
logger = get_logger("system", name="batch_caller")


class BatchCaller:
    """
    Worker qui gère la file d'attente des appels.

    Cycle:
    1. Récupère les appels à lancer (PENDING/RETRY)
    2. Vérifie les limites (concurrent calls, batch size)
    3. Lance les appels via robot_freeswitch
    4. Gère les retry pour NO_ANSWER
    5. Met à jour les stats
    """

    def __init__(self):
        """Initialise le batch caller."""
        logger.info("🚀 Initializing BatchCaller...")

        self.running = False
        self.thread = None

        # Configuration
        self.batch_size = config.DEFAULT_BATCH_SIZE
        self.max_concurrent = config.MAX_CONCURRENT_CALLS
        self.delay_between_calls = config.DELAY_BETWEEN_CALLS
        self.queue_check_interval = config.QUEUE_CHECK_INTERVAL

        # Robot FreeSWITCH
        self.robot = RobotFreeSWITCH()

        # Stats
        self.total_launched = 0
        self.total_retry = 0
        self.active_calls = {}

        logger.info(f"✅ BatchCaller initialized (batch_size={self.batch_size}, max_concurrent={self.max_concurrent})")

    def start(self):
        """Démarre le worker."""
        if self.running:
            logger.warning("BatchCaller already running")
            return

        logger.info("▶️ Starting BatchCaller worker...")

        # Connecter robot FreeSWITCH
        if not self.robot.connect():
            logger.error("❌ Failed to connect to FreeSWITCH")
            return False

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        logger.info("✅ BatchCaller started")
        return True

    def stop(self):
        """Arrête le worker."""
        logger.info("⏹️ Stopping BatchCaller...")
        self.running = False

        if self.thread:
            self.thread.join(timeout=5)

        # Arrêter robot
        self.robot.stop()

        logger.info("✅ BatchCaller stopped")

    def _run_loop(self):
        """Boucle principale du worker."""
        logger.info("🔄 BatchCaller loop started")

        while self.running:
            try:
                # Process queue
                launched = self._process_queue()

                if launched > 0:
                    logger.info(f"📞 Launched {launched} calls")
                    self.total_launched += launched

                # Check retry
                retried = self._process_retry()
                if retried > 0:
                    logger.info(f"🔁 Scheduled {retried} retry")
                    self.total_retry += retried

                # Update active calls
                self._update_active_calls()

                # Sleep
                time.sleep(self.queue_check_interval)

            except Exception as e:
                logger.error(f"❌ Error in batch caller loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retry

        logger.info("🔄 BatchCaller loop ended")

    def _process_queue(self) -> int:
        """
        Process la file d'attente.

        Returns:
            Nombre d'appels lancés
        """
        db = SessionLocal()
        launched = 0

        try:
            # Récupérer campagnes actives
            campaigns = db.query(Campaign).filter(
                Campaign.status == CampaignStatus.RUNNING
            ).all()

            for campaign in campaigns:
                # Vérifier limites campagne
                active_campaign_calls = db.query(Call).filter(
                    Call.campaign_id == campaign.id,
                    Call.status.in_([CallStatus.IN_PROGRESS, CallStatus.CALLING])
                ).count()

                if active_campaign_calls >= campaign.max_concurrent_calls:
                    logger.debug(f"Campaign {campaign.id} at limit ({active_campaign_calls}/{campaign.max_concurrent_calls})")
                    continue

                # Calculer nombre à lancer
                available_slots = min(
                    campaign.max_concurrent_calls - active_campaign_calls,
                    self.max_concurrent - len(self.active_calls),
                    campaign.batch_size
                )

                if available_slots <= 0:
                    continue

                # Récupérer appels à lancer
                now = datetime.utcnow()
                calls = db.query(Call).filter(
                    Call.campaign_id == campaign.id,
                    Call.status.in_([CallStatus.PENDING, CallStatus.RETRY]),
                    or_(
                        Call.scheduled_at == None,
                        Call.scheduled_at <= now
                    )
                ).order_by(
                    Call.queue_priority.desc(),
                    Call.scheduled_at.asc()
                ).limit(available_slots).all()

                # Lancer les appels
                for call in calls:
                    success = self._launch_call(call, campaign, db)
                    if success:
                        launched += 1
                        time.sleep(self.delay_between_calls)

                db.commit()

        except Exception as e:
            logger.error(f"Error processing queue: {e}", exc_info=True)
            db.rollback()

        finally:
            db.close()

        return launched

    def _launch_call(self, call: Call, campaign: Campaign, db: Session) -> bool:
        """
        Lance un appel individuel.

        Args:
            call: Appel à lancer
            campaign: Campagne
            db: Session DB

        Returns:
            True si succès
        """
        try:
            # Récupérer contact
            contact = db.query(Contact).filter(Contact.id == call.contact_id).first()
            if not contact:
                logger.error(f"Contact {call.contact_id} not found for call {call.id}")
                call.status = CallStatus.FAILED
                return False

            # Logger
            call_logger = get_logger("calls", call_uuid=call.uuid)
            call_logger.info(f"Launching call to {contact.phone}", extra={
                "campaign_id": campaign.id,
                "contact_id": contact.id,
                "retry_count": call.retry_count,
                "scenario": campaign.scenario
            })

            # Lancer via FreeSWITCH
            result = self.robot.originate_call(
                uuid=call.uuid,
                phone_number=contact.phone,
                campaign_id=campaign.id,
                contact_id=contact.id,
                scenario=campaign.scenario,
                caller_id="+33123456789",  # TODO: From config
                retry_count=call.retry_count,
                variables={
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "company": contact.company,
                    "email": contact.email
                }
            )

            if result:
                # Mettre à jour statut
                call.status = CallStatus.CALLING
                call.started_at = datetime.utcnow()
                call.retry_count += 1
                call.last_attempt_at = datetime.utcnow()

                # Ajouter aux appels actifs
                self.active_calls[call.uuid] = {
                    "call_id": call.id,
                    "campaign_id": campaign.id,
                    "started_at": time.time()
                }

                call_logger.info("Call launched successfully")
                return True
            else:
                call_logger.error("Failed to launch call")
                call.status = CallStatus.FAILED
                return False

        except Exception as e:
            logger.error(f"Error launching call {call.id}: {e}", exc_info=True)
            call.status = CallStatus.FAILED
            return False

    def _process_retry(self) -> int:
        """
        Process les retry pour NO_ANSWER et BUSY.

        Returns:
            Nombre de retry planifiés
        """
        db = SessionLocal()
        retried = 0

        try:
            # Récupérer appels NO_ANSWER ou BUSY
            calls = db.query(Call).filter(
                Call.status.in_([CallStatus.NO_ANSWER, CallStatus.BUSY]),
                Call.retry_count < Call.max_retries
            ).all()

            for call in calls:
                campaign = db.query(Campaign).filter(Campaign.id == call.campaign_id).first()
                if not campaign or not campaign.retry_enabled:
                    continue

                # Calculer prochaine tentative
                if call.status == CallStatus.NO_ANSWER:
                    delay_minutes = campaign.retry_delay_minutes
                elif call.status == CallStatus.BUSY:
                    delay_minutes = config.RETRY_BUSY_DELAY_MINUTES
                else:
                    continue

                next_attempt = datetime.utcnow() + timedelta(minutes=delay_minutes)

                # Planifier retry
                call.status = CallStatus.RETRY
                call.scheduled_at = next_attempt
                call.queue_priority = 1  # Priorité plus haute

                logger.info(f"Scheduled retry for call {call.id} at {next_attempt}")
                retried += 1

            db.commit()

        except Exception as e:
            logger.error(f"Error processing retry: {e}", exc_info=True)
            db.rollback()

        finally:
            db.close()

        return retried

    def _update_active_calls(self):
        """Met à jour la liste des appels actifs."""
        # Récupérer statut depuis FreeSWITCH
        active_uuids = self.robot.get_active_calls()

        # Nettoyer les appels terminés
        for uuid in list(self.active_calls.keys()):
            if uuid not in active_uuids:
                call_info = self.active_calls.pop(uuid)
                duration = time.time() - call_info["started_at"]

                logger.info(f"Call {uuid} ended (duration: {duration:.1f}s)")

                # Mettre à jour DB
                self._handle_call_end(call_info["call_id"], uuid)

    def _handle_call_end(self, call_id: int, uuid: str):
        """
        Gère la fin d'un appel.

        Args:
            call_id: ID de l'appel
            uuid: UUID FreeSWITCH
        """
        db = SessionLocal()

        try:
            call = db.query(Call).filter(Call.id == call_id).first()
            if not call:
                return

            # Récupérer infos depuis FreeSWITCH
            call_info = self.robot.get_call_info(uuid)

            if call_info:
                # Mettre à jour statut
                hangup_cause = call_info.get("hangup_cause", "NORMAL_CLEARING")

                if hangup_cause == "NO_ANSWER":
                    call.status = CallStatus.NO_ANSWER
                elif hangup_cause == "BUSY":
                    call.status = CallStatus.BUSY
                elif hangup_cause == "NORMAL_CLEARING":
                    call.status = CallStatus.COMPLETED
                else:
                    call.status = CallStatus.FAILED

                # Durée
                call.ended_at = datetime.utcnow()
                if call.started_at:
                    call.duration = int((call.ended_at - call.started_at).total_seconds())

                # AMD result
                if "amd_result" in call_info:
                    call.amd_result = call_info["amd_result"]

                # Qualification result
                if "qualification_result" in call_info:
                    if call_info["qualification_result"] == "LEADS":
                        call.result = CallResult.LEADS
                    else:
                        call.result = CallResult.NOT_INTERESTED
            else:
                call.status = CallStatus.FAILED
                call.ended_at = datetime.utcnow()

            db.commit()

            # Logger
            call_logger = get_logger("calls", call_uuid=uuid)
            call_logger.info(f"Call ended: {call.status}", extra={
                "duration": call.duration,
                "result": call.result,
                "amd_result": call.amd_result
            })

        except Exception as e:
            logger.error(f"Error handling call end: {e}", exc_info=True)
            db.rollback()

        finally:
            db.close()

    def get_stats(self) -> dict:
        """Retourne les statistiques du batch caller."""
        return {
            "running": self.running,
            "active_calls": len(self.active_calls),
            "total_launched": self.total_launched,
            "total_retry": self.total_retry,
            "batch_size": self.batch_size,
            "max_concurrent": self.max_concurrent
        }


# Instance globale
batch_caller = None


def start_batch_caller():
    """Démarre le batch caller."""
    global batch_caller

    if batch_caller and batch_caller.running:
        logger.warning("BatchCaller already running")
        return

    batch_caller = BatchCaller()
    batch_caller.start()


def stop_batch_caller():
    """Arrête le batch caller."""
    global batch_caller

    if batch_caller:
        batch_caller.stop()
        batch_caller = None


def signal_handler(sig, frame):
    """Gère l'arrêt propre sur Ctrl+C."""
    logger.info("\n📛 Received interrupt signal, stopping...")
    stop_batch_caller()
    sys.exit(0)


if __name__ == "__main__":
    """Lance le batch caller en standalone."""

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("🤖 BATCH CALLER - MiniBotPanel v3")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Configuration:")
    logger.info(f"  Batch size: {config.DEFAULT_BATCH_SIZE}")
    logger.info(f"  Max concurrent: {config.MAX_CONCURRENT_CALLS}")
    logger.info(f"  Check interval: {config.QUEUE_CHECK_INTERVAL}s")
    logger.info(f"  Delay between calls: {config.DELAY_BETWEEN_CALLS}s")
    logger.info("")

    # Start
    start_batch_caller()

    # Keep alive
    logger.info("✅ BatchCaller running. Press Ctrl+C to stop...")

    try:
        while True:
            if batch_caller:
                stats = batch_caller.get_stats()
                logger.info(f"📊 Stats: Active={stats['active_calls']}, Total={stats['total_launched']}, Retry={stats['total_retry']}")
            time.sleep(30)
    except KeyboardInterrupt:
        pass

    # Clean stop
    stop_batch_caller()
    logger.info("👋 Bye!")