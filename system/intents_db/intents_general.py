#!/usr/bin/env python3
"""
Intents GENERAL - MiniBotPanel v3

Intents généraux TOUJOURS chargés (questions/objections).
Ces intents déclenchent le système MaxTurns + objection_matcher.

Intents:
- question: Questions générales (qui, quoi, comment, pourquoi, etc.)
- objection: Objections classiques (cher, pas le temps, rappeler, etc.)

Note: Les keywords ici sont juste pour DÉTECTER qu'il y a une question/objection.
      La RÉPONSE est cherchée dans objections_db (système séparé).
"""

from typing import List
from system.intents_db import IntentEntry


INTENTS_DATABASE: List[IntentEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # QUESTION (Questions générales)
    # ─────────────────────────────────────────────────────────────────────
    IntentEntry(
        intent="question",
        keywords=[
            # Mots interrogatifs
            "qui", "quoi", "quand", "comment", "pourquoi", "où", "combien",
            "quel", "quelle", "quels", "quelles",

            # Questions directes
            "c'est qui", "c'est quoi", "qui êtes-vous", "quelle société",
            "comment ça marche", "pourquoi moi",

            # Demandes d'information
            "vous pouvez m'expliquer", "expliquer", "préciser",
            "c'est gratuit", "ça coûte quoi", "tarif", "prix",

            # Questions procédurales
            "comment vous avez mon numéro", "d'où vous avez",
            "qui vous a donné", "comment faire", "c'est comment",

            # Demandes de documentation
            "envoyez documentation", "envoyez email", "envoyez brochure",
            "envoyer doc", "plus d'infos",

            # Questions de confiance
            "c'est sérieux", "fiable", "arnaque", "vous êtes sérieux",

            # Questions engagement
            "engagement", "durée", "contrat", "résiliation"
        ],
        confidence_base=0.65
    ),

    # ─────────────────────────────────────────────────────────────────────
    # OBJECTION (Objections classiques)
    # ─────────────────────────────────────────────────────────────────────
    IntentEntry(
        intent="objection",
        keywords=[
            # Objections TEMPS
            "pas le temps", "pas de temps", "occupé", "débordé",
            "pas maintenant", "rappelez", "rappeler plus tard",

            # Objections INTÉRÊT
            # (Note: "pas intéressé" déjà dans deny, mais peut être objection selon contexte)
            "pas vraiment intéressé", "ça m'intéresse pas vraiment",

            # Objections PRIX
            "trop cher", "c'est cher", "prix élevé", "hors budget",
            "pas le budget", "pas les moyens", "trop onéreux",

            # Objections RÉFLEXION
            "réfléchir", "besoin de temps", "parler conjoint", "parler femme",
            "parler mari", "décision à deux",

            # Objections CONCURRENCE
            "déjà un fournisseur", "déjà équipé", "j'ai déjà",

            # Objections PROCESSUS
            "pas décideur", "pas le bon", "c'est pas moi",
            "pas la bonne personne",

            # Objections DÉRANGEMENT
            "dérangez", "embêtez", "arrêtez de m'appeler",
            "laissez-moi tranquille",

            # BLOCTEL / Liste opposition
            "bloctel", "liste opposition", "liste rouge",

            # Objections ABANDON
            "laissez tomber", "laisser tomber", "j'arrête",
            "plus intéressé", "ça va pas le faire"
        ],
        confidence_base=0.65
    ),
]
