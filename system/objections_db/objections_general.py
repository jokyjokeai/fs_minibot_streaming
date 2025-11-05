#!/usr/bin/env python3
"""
Objections GÉNÉRALES - MiniBotPanel v3

Objections et FAQ communes à TOUTES les thématiques.
Ces objections peuvent être utilisées seules ou combinées avec une thématique spécifique.

Structure:
- Objections TEMPS (pas le temps, rappeler plus tard, etc.)
- Objections INTÉRÊT (pas intéressé, aucun intérêt, etc.)
- Objections PRIX/BUDGET (trop cher, pas le budget, etc.)
- Objections RÉFLEXION (besoin de réfléchir, parler au conjoint, etc.)
- Objections CONCURRENCE (déjà un fournisseur, déjà équipé, etc.)
- FAQ GÉNÉRALES (qui êtes-vous, Bloctel, tarif, documentation, etc.)

Audio:
- Fichiers dans: audio/{voice}/objections/
- Noms: general_*.wav
"""

from typing import List
from system.objections_database import ObjectionEntry


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIONS GÉNÉRALES
# ═══════════════════════════════════════════════════════════════════════════

OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # TEMPS
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "pas le temps", "pas de temps", "pas le temps là",
            "occupé", "débordé", "surchargé", "submergé",
            "pas maintenant", "moment pas bon", "pas disponible",
            "j'ai pas le temps", "vraiment pas le temps"
        ],
        response="Je comprends parfaitement. C'est justement pour ça que je vous appelle maintenant - 2 minutes chrono pour voir si ça peut vous intéresser. Vous avez 2 petites minutes là ?",
        audio_path="general_pas_temps.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "rappelez", "rappeler plus tard", "rappeler", "plus tard",
            "pas maintenant", "autre moment", "rappeler demain"
        ],
        response="Pas de souci. Quel serait le meilleur moment ? Demain matin à 10h ou plutôt en fin d'après-midi vers 17h ?",
        audio_path="general_rappeler.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "réunion", "en cours", "là je peux pas",
            "en rendez-vous", "en meeting", "occupé là"
        ],
        response="Je vous laisse tout de suite. Je vous rappelle dans combien de temps ? Une heure, deux heures ?",
        audio_path="general_reunion.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # INTÉRÊT
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "pas intéressé", "intéresse pas", "m'intéresse pas",
            "ça m'intéresse pas", "non merci", "merci non",
            "pas pour moi", "ça me dit rien", "pas convaincu",
            "aucun intérêt", "je suis pas intéressé", "pas vraiment"
        ],
        response="D'accord. Est-ce que je peux quand même vous poser UNE question rapide pour voir si ça pourrait vous concerner ? Ça prend 10 secondes.",
        audio_path="general_pas_interesse.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "ça m'intéresse vraiment pas", "aucun intérêt du tout",
            "pas du tout intéressé", "vraiment pas"
        ],
        response="Pas de souci. Puis-je savoir ce qui ne vous intéresse pas précisément ? Comme ça je note et on ne vous recontacte pas pour rien.",
        audio_path="general_aucun_interet.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # PRIX / BUDGET
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "trop cher", "c'est cher", "trop élevé", "prix élevé",
            "hors budget", "hors de prix", "pas les moyens",
            "je peux pas me permettre", "trop onéreux",
            "coûte trop", "tarif élevé", "prix excessif", "inabordable"
        ],
        response="Je comprends la question budget. Vous payez combien actuellement ? Nos clients économisent 30 à 40% en moyenne. Ça vaut le coup de comparer non ?",
        audio_path="general_trop_cher.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "pas le budget", "budget serré", "budget limité",
            "manque budget", "budget restreint", "sans budget"
        ],
        response="Le budget c'est une contrainte, je comprends. On a des formules dès XX€/mois. Avec les économies générées, ça se rentabilise vite. On regarde ensemble ?",
        audio_path="general_pas_budget.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # RÉFLEXION
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "réfléchir", "besoin de temps", "hésiter", "hésitation",
            "dois réfléchir", "je vais réfléchir", "laisser réfléchir",
            "temps de réflexion", "besoin réfléchir"
        ],
        response="C'est normal de réfléchir. Qu'est-ce qui vous fait hésiter précisément ? Le prix ? Les modalités ? Je peux vous apporter des réponses claires.",
        audio_path="general_reflechir.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "parler conjoint", "parler femme", "parler mari",
            "en parler", "parler ma femme", "parler mon mari",
            "décision à deux", "consulter conjoint"
        ],
        response="C'est une décision qui se prend à deux, je comprends. Je vous envoie une doc claire par email pour que vous puissiez en discuter ?",
        audio_path="general_parler_conjoint.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # CONCURRENCE
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "déjà un fournisseur", "déjà équipé", "déjà chez",
            "j'ai déjà", "déjà souscrit", "déjà un contrat"
        ],
        response="Parfait, vous êtes équipé ! Vous en êtes satisfait ? Beaucoup de clients gardent leur fournisseur et nous utilisent en complément. Curieux de comparer ?",
        audio_path="general_deja_fournisseur.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # FAQ GÉNÉRALES
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "qui êtes vous", "c'est qui", "quelle société",
            "quelle entreprise", "vous êtes de quelle société"
        ],
        response="Je suis [Prénom] de [Société]. On est basés à [Ville], on fait [Activité] depuis [X années]. Vous voulez notre site web pour vérifier ?",
        audio_path="general_qui_etes_vous.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "comment vous avez mon numéro", "d'où numéro",
            "qui vous a donné", "comment vous m'avez eu"
        ],
        response="On fait de la prospection commerciale légale. Votre numéro est dans une base opt-in. Si vous voulez être retiré, je le fais immédiatement. Vous voulez ?",
        audio_path="general_comment_numero.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "bloctel", "je suis sur bloctel", "liste opposition",
            "liste rouge", "opposé démarchage"
        ],
        response="Je vérifie... Effectivement vous êtes sur Bloctel. On ne devrait pas vous appeler. Toutes mes excuses, je vous retire tout de suite. Bonne journée.",
        audio_path="general_bloctel.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "c'est gratuit", "ça coûte quoi", "tarif", "combien",
            "quel prix", "coût"
        ],
        response="Le tarif dépend de votre situation. Pour un chiffre exact, j'ai besoin de 2-3 infos rapides. Vous me donnez 2 minutes ?",
        audio_path="general_tarif.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "envoyez documentation", "envoyez email", "envoyez brochure",
            "envoyez doc", "envoyer documentation", "envoyer brochure"
        ],
        response="Pas de problème. Pour que ce soit adapté à votre situation, j'ai besoin de 2-3 infos rapides avant. Comme ça je vous envoie exactement ce qu'il vous faut. D'accord ?",
        audio_path="general_documentation.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "c'est sérieux", "arnaque", "fiable", "confiance",
            "vous êtes sérieux", "c'est une arnaque"
        ],
        response="Excellente question ! On est enregistrés avec SIRET, régulés, XX clients en France. Vous pouvez tout vérifier. On ne demande RIEN par téléphone. Ça vous rassure ?",
        audio_path="general_serieux.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "engagement", "durée", "contrat", "résiliation",
            "durée engagement", "sans engagement"
        ],
        response="Aucun engagement ! Vous testez, si ça vous plaît pas vous résiliez quand vous voulez. Simple comme bonjour. Ça vous va ?",
        audio_path="general_engagement.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "déjà client", "je suis client", "déjà chez vous",
            "suis déjà client"
        ],
        response="Ah super ! Vous êtes client depuis quand ? Vous êtes satisfait ? Je vous appelle justement pour voir si on peut améliorer votre offre actuelle.",
        audio_path="general_deja_client.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "pas décideur", "pas le bon", "c'est pas moi",
            "je suis pas décideur", "pas la bonne personne"
        ],
        response="D'accord. Qui serait la bonne personne à contacter pour ce sujet ? Vous auriez son contact ? Comme ça je ne vous dérange plus.",
        audio_path="general_pas_decideur.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "dérangez", "embêtez", "arrêtez", "laissez-moi",
            "vous me dérangez", "arrêtez de m'appeler"
        ],
        response="Désolé de vous déranger. Vous préférez qu'on ne vous rappelle plus du tout, ou juste pas maintenant ? Comme ça je note.",
        audio_path="general_derangez.wav",
        entry_type="faq"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # RATTRAPAGE ABANDON
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "laissez tomber", "laisser tomber", "laisse tomber",
            "arrêtez", "arrêter", "stop", "j'arrête",
            "j'ai pas le temps", "plus le temps", "ça va pas le faire",
            "plus intéressé", "je suis plus intéressé", "ça m'intéresse plus",
            "je veux arrêter", "on arrête là", "terminé", "fini"
        ],
        response="C'est dommage, on avait bien avancé ! Si vous êtes éligible, vous pourrez bénéficier des conseils de notre expert, c'est sans engagement. On continue juste 2 minutes ?",
        audio_path="retry_global.wav",
        entry_type="objection"
    ),
]
