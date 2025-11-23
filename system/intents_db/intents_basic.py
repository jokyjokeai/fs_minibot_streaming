#!/usr/bin/env python3
"""
Intents BASIC - MiniBotPanel v3

Intents de base TOUJOURS chargés pour tous les scénarios.

Intents:
- affirm: Réponses affirmatives (oui, d'accord, ok, etc.)
- deny: Réponses négatives (non, pas intéressé, ça va, etc.)
- silence: Pas de réponse (géré automatiquement par VAD, pas de keywords)

Note: unsure/hésitations sont gérés par objections_db pour des réponses plus spécifiques
"""

from typing import List
from system.intents_db import IntentEntry


INTENTS_DATABASE: List[IntentEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # AFFIRM (Réponses positives)
    # ─────────────────────────────────────────────────────────────────────
    IntentEntry(
        intent="affirm",
        keywords=[
            # Oui variations
            "oui", "ouais", "oui oui", "ouais ouais", "ui", "si",

            # D'accord variations
            "d'accord", "dac", "daccord", "ok", "okay", "oki",

            # Absolument / Exactement
            "absolument", "exactement", "tout à fait", "bien sûr", "évidemment",
            "carrément", "clairement", "sans problème", "avec plaisir",

            # Affirmations directes
            "je suis intéressé", "ça m'intéresse", "pourquoi pas", "je veux bien",
            "volontiers", "je suis d'accord", "allons-y", "parfait",
            "ça peut se passer", "ça peut se faire", "ça peut le faire",

            # Validation
            "c'est bon", "c'est parfait", "ça marche", "ça me va", "entendu",
            "compris", "validé", "je valide", "go", "banco"
        ],
        confidence_base=0.7
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DENY (Réponses négatives)
    # ─────────────────────────────────────────────────────────────────────
    IntentEntry(
        intent="deny",
        keywords=[
            # Non variations
            "non", "nan", "non non", "nan nan", "nope", "négatif",

            # Pas intéressé
            "pas intéressé", "intéresse pas", "m'intéresse pas", "ça m'intéresse pas",
            "aucun intérêt", "je suis pas intéressé",

            # Refus poli
            "ça va", "merci non", "non merci", "c'est gentil mais non",
            "pas pour moi", "ça ira", "je passe", "je décline",

            # Refus direct
            "arrêtez", "stop", "laissez tomber", "laisser tomber",
            "j'arrête", "on arrête", "terminé", "fini",

            # Désintérêt
            "ça me dit rien", "pas convaincu", "pas vraiment",
            "je préfère pas", "c'est pas pour moi"
        ],
        confidence_base=0.7
    ),

    # ─────────────────────────────────────────────────────────────────────
    # SILENCE
    # ─────────────────────────────────────────────────────────────────────
    # Note: Silence n'a pas de keywords (détecté par VAD)
    # Inclus ici pour documentation uniquement
    IntentEntry(
        intent="silence",
        keywords=[],  # Détecté par SPEECH_END, pas par keywords
        confidence_base=1.0
    ),
]
