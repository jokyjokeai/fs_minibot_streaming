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
import re
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

    OPTION B: Charge SEULEMENT intents_basic (affirm, deny, unsure, silence)
    Les intents question/objection sont détectés via objections_db (élimine duplication)

    Args:
        theme: Nom de la thématique (ex: "finance", "immobilier")
               Non utilisé actuellement (legacy parameter)

    Returns:
        Liste de IntentEntry (basic intents only)
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

    # 2. intents_general SUPPRIMÉ (OPTION B simplification)
    # Les intents "question" et "objection" sont maintenant détectés via objections_db
    # dans _analyze_intent() NIVEAU 0.5 (fallback après fuzzy matching basic)

    # 3. Charger thématique si spécifié (optionnel, pour extensions futures)
    if theme and theme != "general":
        try:
            theme_module = importlib.import_module(f"system.intents_db.intents_{theme}")
            theme_intents = theme_module.INTENTS_DATABASE
            all_intents.extend(theme_intents)
            logger.info(f"✅ Loaded {len(theme_intents)} intents from theme '{theme}'")
        except ModuleNotFoundError:
            logger.debug(f"No intents file for theme '{theme}' (expected)")
        except Exception as e:
            logger.error(f"❌ Failed to load intents_{theme}: {e}")

    logger.info(f"📊 Total intents loaded: {len(all_intents)} (basic only)")
    return all_intents


def match_intent(transcription: str, intents_db: List[IntentEntry], min_confidence: float = 0.7) -> Optional[Dict]:
    """
    Match transcription contre intents database avec fuzzy matching.

    AMÉLIORATION v3.1: Vérification de mots entiers pour éviter faux positifs
    Exemple: "oui" ne matche PAS "suis" (évite match partiel "ui")

    Args:
        transcription: Texte à analyser
        intents_db: Database d'intents chargée
        min_confidence: Confiance minimale pour retourner un match (défaut: 0.7)

    Returns:
        {"intent": "affirm", "confidence": 0.95, "matched_keyword": "oui"} ou None
    """
    if not transcription or not intents_db:
        return None

    transcription_lower = transcription.lower().strip()
    best_match = None
    best_confidence = 0.0
    best_keyword = ""
    best_reason = ""

    for intent_entry in intents_db:
        for keyword in intent_entry.keywords:
            keyword_lower = keyword.lower()

            # ============================================================
            # PRIORITÉ 1: MOT ENTIER (word boundary check)
            # ============================================================
            # Utilise regex pour vérifier que keyword est un mot complet
            # Exemple: "oui" match "oui d'accord" mais PAS "suis" (évite "ui" substring)
            word_pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            if re.search(word_pattern, transcription_lower):
                # Mot entier trouvé → Confiance très haute
                confidence = 0.90
                reason = "word_exact"

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = intent_entry.intent
                    best_keyword = keyword
                    best_reason = reason
                continue  # Passe au keyword suivant

            # ============================================================
            # PRIORITÉ 2: FUZZY MATCHING (fallback)
            # ============================================================
            # Seulement si mot entier PAS trouvé
            # Utilise partial_ratio mais avec seuil plus strict
            similarity = fuzz.partial_ratio(keyword_lower, transcription_lower) / 100.0

            # Seuil: Au moins 80% de similarité pour fuzzy
            if similarity >= 0.8:
                # Calcul confiance (moins élevée que word exact)
                confidence = min(0.85, intent_entry.confidence_base + (similarity * 0.2))
                reason = "fuzzy"

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = intent_entry.intent
                    best_keyword = keyword
                    best_reason = reason

    if best_confidence >= min_confidence:
        return {
            "intent": best_match,
            "confidence": best_confidence,
            "matched_keyword": best_keyword,
            "reason": best_reason
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
