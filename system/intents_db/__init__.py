#!/usr/bin/env python3
"""
Intents Database - MiniBotPanel v3

Système de détection d'intents avec fuzzy matching (comme objections_db).

Structure modulaire par thématique:
- intents_basic.py : Intents de base (affirm, deny, silence, unsure) - TOUJOURS chargé
- intents_general.py : Intents généraux (question, objection) - TOUJOURS chargé
- intents_{theme}.py : Intents spécifiques par thématique (optionnel)

Usage:
    from system.intents_db import load_intents_database, match_intent

    intents = load_intents_database("finance")  # Charge basic + general + finance
    result = match_intent("oui d'accord", intents)  # {"intent": "affirm", "confidence": 0.95}
"""

import importlib
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


@dataclass
class IntentEntry:
    """Entrée d'intent avec keywords pour fuzzy matching"""
    intent: str  # "affirm", "deny", "silence", "question", etc.
    keywords: List[str]  # Liste de variations
    confidence_base: float = 0.6  # Confiance de base

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "keywords": self.keywords,
            "confidence_base": self.confidence_base
        }


def load_intents_database(theme: str = "general") -> List[IntentEntry]:
    """
    Charge les intents depuis les modules.

    TOUJOURS charge: basic + general + theme (si fourni)

    Args:
        theme: Nom de la thématique (ex: "finance", "immobilier")
               Valeur spéciale "general" = charge seulement basic + general

    Returns:
        Liste de IntentEntry (combinaison basic + general + theme)
    """
    all_intents = []

    # 1. TOUJOURS charger intents_basic
    try:
        basic_module = importlib.import_module("system.intents_db.intents_basic")
        basic_intents = basic_module.INTENTS_DATABASE
        all_intents.extend(basic_intents)
        logger.info(f"✅ Loaded {len(basic_intents)} basic intents")
    except Exception as e:
        logger.error(f"❌ Failed to load intents_basic: {e}")

    # 2. TOUJOURS charger intents_general
    try:
        general_module = importlib.import_module("system.intents_db.intents_general")
        general_intents = general_module.INTENTS_DATABASE
        all_intents.extend(general_intents)
        logger.info(f"✅ Loaded {len(general_intents)} general intents")
    except Exception as e:
        logger.error(f"❌ Failed to load intents_general: {e}")

    # 3. Charger thématique si spécifié (et différent de "general")
    if theme and theme != "general":
        try:
            theme_module = importlib.import_module(f"system.intents_db.intents_{theme}")
            theme_intents = theme_module.INTENTS_DATABASE
            all_intents.extend(theme_intents)
            logger.info(f"✅ Loaded {len(theme_intents)} intents from theme '{theme}'")
        except ModuleNotFoundError:
            logger.warning(f"⚠️ No intents file for theme '{theme}', using basic + general only")
        except Exception as e:
            logger.error(f"❌ Failed to load intents_{theme}: {e}")

    logger.info(f"📊 Total intents loaded: {len(all_intents)}")
    return all_intents


def match_intent(transcription: str, intents_db: List[IntentEntry], min_confidence: float = 0.6) -> Optional[Dict]:
    """
    Match transcription contre intents database avec fuzzy matching.

    Args:
        transcription: Texte à analyser
        intents_db: Database d'intents chargée
        min_confidence: Confiance minimale pour retourner un match

    Returns:
        {"intent": "affirm", "confidence": 0.95, "matched_keyword": "oui"} ou None
    """
    if not transcription or not intents_db:
        return None

    transcription_lower = transcription.lower().strip()
    best_match = None
    best_confidence = 0.0
    best_keyword = ""

    for intent_entry in intents_db:
        for keyword in intent_entry.keywords:
            # Fuzzy matching (comme objections_db)
            similarity = fuzz.partial_ratio(keyword.lower(), transcription_lower) / 100.0

            # Bonus si mot exact trouvé
            if keyword.lower() in transcription_lower:
                similarity = min(1.0, similarity + 0.1)

            # Calcul confiance finale
            confidence = min(0.95, intent_entry.confidence_base + (similarity * 0.3))

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = intent_entry.intent
                best_keyword = keyword

    if best_confidence >= min_confidence:
        return {
            "intent": best_match,
            "confidence": best_confidence,
            "matched_keyword": best_keyword
        }

    return None


def get_available_themes() -> List[str]:
    """Liste les thématiques disponibles"""
    import pkgutil
    import sys

    themes = []
    package = sys.modules['system.intents_db']

    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("intents_") and modname not in ["intents_basic", "intents_general"]:
            theme = modname.replace("intents_", "")
            themes.append(theme)

    return sorted(themes)
