"""
Stats Collector - MiniBotPanel v3

Collecteur de statistiques temps réel pour monitoring.

Fonctionnalités:
- Agrégation stats campagne en temps réel
- Calcul moyennes (durée, sentiment, etc.)
- Cache stats pour performance
- Historique stats (pour graphiques)

Utilisation:
    from system.stats_collector import StatsCollector

    collector = StatsCollector()

    # Enregistrer événement
    collector.record_call_event(campaign_id, "lead", duration=120)

    # Récupérer stats
    stats = collector.get_campaign_stats(campaign_id)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from system.logger import get_logger

logger = get_logger(__name__)

class StatsCollector:
    """Collecteur de statistiques temps réel."""

    def __init__(self):
        """Initialise le collecteur de stats."""
        logger.info("Initializing StatsCollector...")

        # Cache stats en mémoire (pour performance)
        self._stats_cache: Dict[int, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()

        # Historique (pour graphiques)
        self._history: Dict[int, List[Dict]] = defaultdict(list)

        logger.info("✅ StatsCollector initialized")

    def record_call_event(
        self,
        campaign_id: int,
        event_type: str,
        data: Dict[str, Any] = None
    ):
        """
        Enregistre un événement d'appel.

        Args:
            campaign_id: ID campagne
            event_type: Type événement (lead, not_interested, callback, etc.)
            data: Données additionnelles (duration, sentiment, amd_result, etc.)
        """
        with self._cache_lock:
            if campaign_id not in self._stats_cache:
                self._stats_cache[campaign_id] = self._init_stats()
                self._stats_cache[campaign_id]["started_at"] = datetime.now()

            stats = self._stats_cache[campaign_id]
            data = data or {}

            # Update total
            stats["total"] += 1
            stats["last_update"] = datetime.now()

            # Update selon event_type
            if event_type == "lead":
                stats["leads"] += 1
                stats["completed"] += 1
            elif event_type == "not_interested":
                stats["not_interested"] += 1
                stats["completed"] += 1
            elif event_type == "callback":
                stats["callbacks"] += 1
                stats["completed"] += 1
            elif event_type == "answering_machine":
                stats["answering_machines"] += 1
                stats["completed"] += 1
            elif event_type == "no_answer":
                stats["no_answer"] += 1
                stats["completed"] += 1
            elif event_type == "failed":
                stats["failed"] += 1
                stats["completed"] += 1
            elif event_type == "in_progress":
                stats["in_progress"] += 1

            # Calculer moyenne durée
            if "duration" in data and data["duration"]:
                current_avg = stats["avg_duration"]
                completed = stats["completed"]
                if completed > 1:
                    new_avg = ((current_avg * (completed - 1)) + data["duration"]) / completed
                    stats["avg_duration"] = round(new_avg, 1)
                else:
                    stats["avg_duration"] = data["duration"]

            # Calculer moyenne durée AMD
            if "amd_duration" in data and data["amd_duration"]:
                current_avg = stats["avg_amd_duration"]
                count = stats["answering_machines"]
                if count > 1:
                    new_avg = ((current_avg * (count - 1)) + data["amd_duration"]) / count
                    stats["avg_amd_duration"] = round(new_avg, 1)
                else:
                    stats["avg_amd_duration"] = data["amd_duration"]

            # Sentiment
            if "sentiment" in data:
                sentiment = data["sentiment"]
                if sentiment == "positive":
                    stats["sentiment_positive"] += 1
                elif sentiment == "neutral":
                    stats["sentiment_neutral"] += 1
                elif sentiment == "negative":
                    stats["sentiment_negative"] += 1

            # Ajouter à historique (snapshots toutes les minutes)
            history_entry = {
                "timestamp": datetime.now(),
                "event_type": event_type,
                "stats_snapshot": stats.copy()
            }
            self._history[campaign_id].append(history_entry)

            # Limiter taille historique (garder dernières 1000 entrées)
            if len(self._history[campaign_id]) > 1000:
                self._history[campaign_id] = self._history[campaign_id][-1000:]

            logger.debug(f"Recorded event: campaign {campaign_id}, type {event_type}, "
                        f"total={stats['total']}, completed={stats['completed']}")

    def get_campaign_stats(self, campaign_id: int) -> Dict[str, Any]:
        """
        Récupère statistiques d'une campagne.

        Args:
            campaign_id: ID campagne

        Returns:
            Dict avec statistiques complètes
        """
        with self._cache_lock:
            if campaign_id not in self._stats_cache:
                return self._init_stats()

            return self._stats_cache[campaign_id].copy()

    def get_live_stats(self, campaign_id: int) -> Dict[str, Any]:
        """
        Récupère stats live pour monitoring CLI.

        Args:
            campaign_id: ID campagne

        Returns:
            Dict avec stats formatées pour affichage CLI avec pourcentages
        """
        stats = self.get_campaign_stats(campaign_id)

        # Calculer pourcentages
        total = stats.get("total", 0)
        completed = stats.get("completed", 0)

        live_stats = stats.copy()

        if total > 0:
            # Taux de complétion
            live_stats["completion_rate"] = round((completed / total) * 100, 1)

            # Taux de leads
            leads = stats.get("leads", 0)
            live_stats["lead_rate"] = round((leads / completed) * 100, 1) if completed > 0 else 0.0

            # Taux de conversion (leads / total appelés)
            live_stats["conversion_rate"] = round((leads / total) * 100, 1)

            # Taux AMD
            amd = stats.get("answering_machines", 0)
            live_stats["amd_rate"] = round((amd / total) * 100, 1)

            # Taux no answer
            no_answer = stats.get("no_answer", 0)
            live_stats["no_answer_rate"] = round((no_answer / total) * 100, 1)

            # Taux succès (completed - failed - no_answer)
            failed = stats.get("failed", 0)
            success = completed - failed - no_answer
            live_stats["success_rate"] = round((success / completed) * 100, 1) if completed > 0 else 0.0

        else:
            live_stats["completion_rate"] = 0.0
            live_stats["lead_rate"] = 0.0
            live_stats["conversion_rate"] = 0.0
            live_stats["amd_rate"] = 0.0
            live_stats["no_answer_rate"] = 0.0
            live_stats["success_rate"] = 0.0

        # Ajouter appels en cours
        in_progress = stats.get("in_progress", 0)
        live_stats["active_calls"] = in_progress

        # Durée campagne
        if stats.get("started_at"):
            duration = datetime.now() - stats["started_at"]
            live_stats["campaign_duration"] = str(duration).split('.')[0]  # Format HH:MM:SS
        else:
            live_stats["campaign_duration"] = "N/A"

        # Cadence (appels par minute)
        if stats.get("started_at") and completed > 0:
            duration_minutes = (datetime.now() - stats["started_at"]).total_seconds() / 60
            if duration_minutes > 0:
                live_stats["calls_per_minute"] = round(completed / duration_minutes, 2)
            else:
                live_stats["calls_per_minute"] = 0.0
        else:
            live_stats["calls_per_minute"] = 0.0

        return live_stats

    def _init_stats(self) -> Dict[str, Any]:
        """
        Initialise structure stats vide.

        Returns:
            Dict avec stats initialisées à 0
        """
        return {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "leads": 0,
            "not_interested": 0,
            "callbacks": 0,
            "answering_machines": 0,
            "no_answer": 0,
            "failed": 0,
            "avg_duration": 0.0,
            "avg_amd_duration": 0.0,
            "sentiment_positive": 0,
            "sentiment_neutral": 0,
            "sentiment_negative": 0,
            "started_at": None,
            "last_update": None
        }

    def clear_cache(self, campaign_id: Optional[int] = None):
        """
        Vide le cache stats.

        Args:
            campaign_id: ID campagne spécifique ou None pour tout vider
        """
        with self._cache_lock:
            if campaign_id:
                if campaign_id in self._stats_cache:
                    del self._stats_cache[campaign_id]
            else:
                self._stats_cache.clear()

        logger.info(f"Stats cache cleared{f' for campaign {campaign_id}' if campaign_id else ''}")
