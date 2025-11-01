#!/usr/bin/env python3
"""
Cache Manager - MiniBotPanel v3 (Phase 8)

Système de cache intelligent centralisé pour optimiser les performances.

Fonctionnalités:
- Cache scénarios en RAM (évite lecture disque répétée)
- Cache objections filtrées par thématique
- Pré-chargement modèles AI (Ollama, TTS, ASR)
- Cache TTL configurable
- Statistiques temps réel
- Invalidation sélective

Architecture:
- Singleton pattern pour instance unique
- Thread-safe (locks)
- LRU eviction policy
- Monitoring intégré

Usage:
    from system.cache_manager import CacheManager

    cache = CacheManager.get_instance()

    # Cache scénario
    scenario = cache.get_scenario("finance_b2c")
    if not scenario:
        scenario = load_scenario_from_disk("finance_b2c")
        cache.set_scenario("finance_b2c", scenario)

    # Cache objections
    objections = cache.get_objections("finance")
    if not objections:
        objections = load_objections_for_theme("finance")
        cache.set_objections("finance", objections)
"""

import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Gestionnaire de cache centralisé (Singleton).

    Thread-safe, avec TTL configurable et statistiques.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialise le cache manager (appelé une seule fois via get_instance)"""
        if CacheManager._instance is not None:
            raise RuntimeError("Use CacheManager.get_instance() instead")

        # Configuration
        self.config = {
            "scenario_ttl": 3600,  # 1h (scénarios changent peu)
            "objections_ttl": 1800,  # 30min
            "models_ttl": 0,  # Infini (modèles restent en mémoire)
            "max_scenarios": 50,  # Max scénarios en cache
            "max_objections": 20,  # Max thématiques objections
            "enable_stats": True
        }

        # Caches (OrderedDict pour LRU)
        self._scenarios_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._objections_cache: OrderedDict[str, List[Any]] = OrderedDict()
        self._models_cache: Dict[str, Any] = {}  # Models pré-chargés

        # Metadata (timestamps, hits, etc.)
        self._scenarios_meta: Dict[str, Dict[str, Any]] = {}
        self._objections_meta: Dict[str, Dict[str, Any]] = {}

        # Statistics
        self.stats = {
            "scenarios": {
                "hits": 0,
                "misses": 0,
                "total_requests": 0,
                "cache_size": 0
            },
            "objections": {
                "hits": 0,
                "misses": 0,
                "total_requests": 0,
                "cache_size": 0
            },
            "models": {
                "preloaded": [],
                "cache_size": 0
            }
        }

        # Thread locks pour thread-safety
        self._scenarios_lock = threading.Lock()
        self._objections_lock = threading.Lock()
        self._models_lock = threading.Lock()

        logger.info("✅ CacheManager initialized (Singleton)")

    @classmethod
    def get_instance(cls) -> 'CacheManager':
        """
        Retourne l'instance unique du CacheManager (Singleton).

        Thread-safe.

        Returns:
            Instance unique du CacheManager
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls.__new__(cls)
                    cls._instance.__init__()
        return cls._instance

    # ========== SCENARIOS CACHE ==========

    def get_scenario(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un scénario du cache.

        Args:
            scenario_name: Nom du scénario

        Returns:
            Scénario dict ou None si pas en cache/expiré
        """
        with self._scenarios_lock:
            self.stats["scenarios"]["total_requests"] += 1

            if scenario_name not in self._scenarios_cache:
                self.stats["scenarios"]["misses"] += 1
                logger.debug(f"Cache MISS: scenario '{scenario_name}'")
                return None

            # Vérifier TTL
            meta = self._scenarios_meta.get(scenario_name, {})
            cached_at = meta.get("cached_at", 0)
            ttl = self.config["scenario_ttl"]

            if ttl > 0 and (time.time() - cached_at) > ttl:
                # Expiré
                logger.debug(f"Cache EXPIRED: scenario '{scenario_name}'")
                del self._scenarios_cache[scenario_name]
                del self._scenarios_meta[scenario_name]
                self.stats["scenarios"]["misses"] += 1
                return None

            # Hit
            self.stats["scenarios"]["hits"] += 1
            meta["last_accessed"] = time.time()
            meta["access_count"] = meta.get("access_count", 0) + 1

            # LRU: move to end
            self._scenarios_cache.move_to_end(scenario_name)

            logger.debug(f"Cache HIT: scenario '{scenario_name}' (accessed {meta['access_count']} times)")
            return self._scenarios_cache[scenario_name]

    def set_scenario(self, scenario_name: str, scenario_data: Dict[str, Any]):
        """
        Met en cache un scénario.

        Args:
            scenario_name: Nom du scénario
            scenario_data: Données du scénario (dict)
        """
        with self._scenarios_lock:
            # LRU eviction si nécessaire
            max_size = self.config["max_scenarios"]
            if len(self._scenarios_cache) >= max_size:
                # Supprimer le plus ancien (FIFO car OrderedDict)
                oldest_key = next(iter(self._scenarios_cache))
                logger.debug(f"Cache EVICT: scenario '{oldest_key}' (LRU)")
                del self._scenarios_cache[oldest_key]
                del self._scenarios_meta[oldest_key]

            # Ajouter au cache
            self._scenarios_cache[scenario_name] = scenario_data
            self._scenarios_meta[scenario_name] = {
                "cached_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 0,
                "size_bytes": len(str(scenario_data))
            }

            self.stats["scenarios"]["cache_size"] = len(self._scenarios_cache)
            logger.info(f"Cache SET: scenario '{scenario_name}' (size: {len(self._scenarios_cache)}/{max_size})")

    def invalidate_scenario(self, scenario_name: str):
        """Invalide un scénario du cache"""
        with self._scenarios_lock:
            if scenario_name in self._scenarios_cache:
                del self._scenarios_cache[scenario_name]
                del self._scenarios_meta[scenario_name]
                self.stats["scenarios"]["cache_size"] = len(self._scenarios_cache)
                logger.info(f"Cache INVALIDATE: scenario '{scenario_name}'")

    def clear_scenarios(self):
        """Vide tout le cache scénarios"""
        with self._scenarios_lock:
            count = len(self._scenarios_cache)
            self._scenarios_cache.clear()
            self._scenarios_meta.clear()
            self.stats["scenarios"]["cache_size"] = 0
            logger.info(f"Cache CLEAR: {count} scenarios removed")

    # ========== OBJECTIONS CACHE ==========

    def get_objections(self, theme: str) -> Optional[List[Any]]:
        """
        Récupère les objections d'une thématique du cache.

        Args:
            theme: Thématique (finance, crypto, energie, general, etc.)

        Returns:
            Liste ObjectionEntry ou None si pas en cache
        """
        with self._objections_lock:
            self.stats["objections"]["total_requests"] += 1

            if theme not in self._objections_cache:
                self.stats["objections"]["misses"] += 1
                logger.debug(f"Cache MISS: objections '{theme}'")
                return None

            # Vérifier TTL
            meta = self._objections_meta.get(theme, {})
            cached_at = meta.get("cached_at", 0)
            ttl = self.config["objections_ttl"]

            if ttl > 0 and (time.time() - cached_at) > ttl:
                # Expiré
                logger.debug(f"Cache EXPIRED: objections '{theme}'")
                del self._objections_cache[theme]
                del self._objections_meta[theme]
                self.stats["objections"]["misses"] += 1
                return None

            # Hit
            self.stats["objections"]["hits"] += 1
            meta["last_accessed"] = time.time()
            meta["access_count"] = meta.get("access_count", 0) + 1

            # LRU
            self._objections_cache.move_to_end(theme)

            logger.debug(f"Cache HIT: objections '{theme}' ({len(self._objections_cache[theme])} entries)")
            return self._objections_cache[theme]

    def set_objections(self, theme: str, objections_list: List[Any]):
        """
        Met en cache les objections d'une thématique.

        Args:
            theme: Thématique
            objections_list: Liste ObjectionEntry
        """
        with self._objections_lock:
            # LRU eviction
            max_size = self.config["max_objections"]
            if len(self._objections_cache) >= max_size:
                oldest_key = next(iter(self._objections_cache))
                logger.debug(f"Cache EVICT: objections '{oldest_key}'")
                del self._objections_cache[oldest_key]
                del self._objections_meta[oldest_key]

            # Ajouter
            self._objections_cache[theme] = objections_list
            self._objections_meta[theme] = {
                "cached_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 0,
                "count": len(objections_list)
            }

            self.stats["objections"]["cache_size"] = len(self._objections_cache)
            logger.info(f"Cache SET: objections '{theme}' ({len(objections_list)} entries)")

    def invalidate_objections(self, theme: str):
        """Invalide les objections d'une thématique"""
        with self._objections_lock:
            if theme in self._objections_cache:
                del self._objections_cache[theme]
                del self._objections_meta[theme]
                self.stats["objections"]["cache_size"] = len(self._objections_cache)
                logger.info(f"Cache INVALIDATE: objections '{theme}'")

    def clear_objections(self):
        """Vide tout le cache objections"""
        with self._objections_lock:
            count = len(self._objections_cache)
            self._objections_cache.clear()
            self._objections_meta.clear()
            self.stats["objections"]["cache_size"] = 0
            logger.info(f"Cache CLEAR: {count} objection themes removed")

    # ========== MODELS CACHE ==========

    def register_model(self, model_name: str, model_instance: Any):
        """
        Enregistre un modèle pré-chargé (Ollama, TTS, ASR, etc.).

        Args:
            model_name: Nom du modèle (ex: "ollama_mistral", "coqui_tts", "vosk_asr")
            model_instance: Instance du modèle
        """
        with self._models_lock:
            self._models_cache[model_name] = {
                "instance": model_instance,
                "loaded_at": time.time()
            }
            self.stats["models"]["preloaded"] = list(self._models_cache.keys())
            self.stats["models"]["cache_size"] = len(self._models_cache)
            logger.info(f"Model REGISTERED: '{model_name}' (total: {len(self._models_cache)})")

    def get_model(self, model_name: str) -> Optional[Any]:
        """
        Récupère un modèle pré-chargé.

        Args:
            model_name: Nom du modèle

        Returns:
            Instance du modèle ou None
        """
        with self._models_lock:
            if model_name in self._models_cache:
                return self._models_cache[model_name]["instance"]
            return None

    def unregister_model(self, model_name: str):
        """Désenregistre un modèle"""
        with self._models_lock:
            if model_name in self._models_cache:
                del self._models_cache[model_name]
                self.stats["models"]["preloaded"] = list(self._models_cache.keys())
                self.stats["models"]["cache_size"] = len(self._models_cache)
                logger.info(f"Model UNREGISTERED: '{model_name}'")

    # ========== STATISTICS & MONITORING ==========

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne statistiques complètes du cache.

        Returns:
            Dict avec stats détaillées
        """
        with self._scenarios_lock, self._objections_lock, self._models_lock:
            # Calcul hit rates
            scenarios_total = self.stats["scenarios"]["total_requests"]
            scenarios_hit_rate = (
                (self.stats["scenarios"]["hits"] / scenarios_total * 100)
                if scenarios_total > 0 else 0
            )

            objections_total = self.stats["objections"]["total_requests"]
            objections_hit_rate = (
                (self.stats["objections"]["hits"] / objections_total * 100)
                if objections_total > 0 else 0
            )

            return {
                "scenarios": {
                    **self.stats["scenarios"],
                    "hit_rate_pct": round(scenarios_hit_rate, 1),
                    "cached_names": list(self._scenarios_cache.keys())
                },
                "objections": {
                    **self.stats["objections"],
                    "hit_rate_pct": round(objections_hit_rate, 1),
                    "cached_themes": list(self._objections_cache.keys())
                },
                "models": {
                    **self.stats["models"]
                },
                "config": self.config
            }

    def print_stats(self):
        """Affiche statistiques formatées"""
        stats = self.get_stats()

        print("\n" + "="*70)
        print("📊 CACHE MANAGER STATISTICS")
        print("="*70)

        print(f"\n🎬 SCENARIOS CACHE:")
        print(f"  • Hit rate: {stats['scenarios']['hit_rate_pct']}%")
        print(f"  • Hits: {stats['scenarios']['hits']} / Misses: {stats['scenarios']['misses']}")
        print(f"  • Cache size: {stats['scenarios']['cache_size']}/{self.config['max_scenarios']}")
        print(f"  • Cached: {', '.join(stats['scenarios']['cached_names'][:5])}{'...' if len(stats['scenarios']['cached_names']) > 5 else ''}")

        print(f"\n🛡️ OBJECTIONS CACHE:")
        print(f"  • Hit rate: {stats['objections']['hit_rate_pct']}%")
        print(f"  • Hits: {stats['objections']['hits']} / Misses: {stats['objections']['misses']}")
        print(f"  • Cache size: {stats['objections']['cache_size']}/{self.config['max_objections']}")
        print(f"  • Themes: {', '.join(stats['objections']['cached_themes'])}")

        print(f"\n🤖 MODELS CACHE:")
        print(f"  • Preloaded: {stats['models']['cache_size']} models")
        print(f"  • Models: {', '.join(stats['models']['preloaded'])}")

        print("="*70 + "\n")

    def clear_all(self):
        """Vide tous les caches (sauf models)"""
        self.clear_scenarios()
        self.clear_objections()
        logger.info("Cache ALL CLEARED (scenarios + objections)")


# Raccourci pour accès rapide
def get_cache() -> CacheManager:
    """Raccourci pour obtenir l'instance du cache"""
    return CacheManager.get_instance()
