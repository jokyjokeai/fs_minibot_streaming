#!/usr/bin/env python3
"""
Objections TRADING ROBOT IA - MiniBotPanel v3

Objections et FAQ spécifiques au secteur Trading Robot IA:
- Robots de trading avec intelligence artificielle
- Trading crypto, actions, devises, matières premières
- Société régulée
- Taux 4% par mois prouvé depuis 2 ans
- Accompagnement personnalisé (jusqu'à 5 RDV/semaine)

Audio:
- Fichiers dans: audio/{voice}/objections/
- Noms: finance_*.wav
"""

from typing import List
from system.objections_db import ObjectionEntry


OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # OBJECTIONS TRADING ROBOT IA
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "pas le budget", "budget serré", "budget limité",
            "manque budget", "budget restreint", "sans budget",
            "pas les moyens", "moyens limités", "pas 250",
            "250 c'est trop", "trop cher"
        ],
        response="Je comprends. Mais vous savez, l'argent appelle l'argent. La question c'est : combien êtes-vous prêt à offrir à votre patrimoine futur ? Notre expert peut vous aider à définir ça ensemble. Ça vous convient ?",
        audio_path="finance_pas_budget.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "quel robot", "c'est quoi le robot", "robot utilisé",
            "nom du robot", "quel logiciel", "quelle plateforme",
            "quel algorithme", "comment s'appelle"
        ],
        response="On utilise différentes technologies selon les marchés. Notre expert vous montrera les résultats concrets et répondra à toutes vos questions techniques. On part là-dessus ?",
        audio_path="finance_quel_robot.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "pourquoi 250", "minimum 250", "250 euros",
            "pourquoi ce montant", "pourquoi pas moins",
            "commencer avec moins", "capital minimum"
        ],
        response="Deux cent cinquante euros, c'est vraiment le minimum pour démarrer. On ne fera pas des milles et des cents avec ça, mais ça permet de faire un test raisonnable, d'apprendre à se connaître, et on pourra évoluer par la suite. Vous verrez tout ça avec notre expert. On fait comme ça ?",
        audio_path="finance_pourquoi_250.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "différence", "différenciez", "pourquoi vous",
            "qu'est-ce qui vous différencie", "par rapport aux autres",
            "mieux que les autres", "avantage", "plus-value"
        ],
        response="Ce qui nous différencie, simplement nos résultats. Aujourd'hui, on a plus de trois mille clients qui nous suivent avec des résultats prouvés. Mais ça, je vous laisse vous entretenir avec notre expert qui pourra vous donner des chiffres et des preuves concrètes. On y va ?",
        audio_path="finance_difference.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "accompagnement", "suivi", "aide", "support",
            "on est accompagné", "vous aidez", "assistance",
            "formation", "apprendre"
        ],
        response="Alors nous, ce qu'on vous propose à ce niveau-là, c'est jusqu'à cinq rendez-vous par semaine avec votre conseiller dédié. Formation, suivi des performances, ajustements. Vous n'êtes jamais seul. Notre expert vous expliquera tout ça en détail. Ça marche ?",
        audio_path="finance_accompagnement.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "mauvaise expérience", "déjà perdu", "arnaqué",
            "me suis fait avoir", "perdu de l'argent", "échaudé",
            "plus confiance", "traumatisé", "problème avant"
        ],
        response="Je comprends votre méfiance après une mauvaise expérience. C'est pour ça qu'en ce qui nous concerne, tout est vérifiable depuis le début de notre activité. Notre expert vous montrera les preuves et répondra à toutes vos questions. On y va ?",
        audio_path="finance_mauvaise_experience.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "déjà un robot", "déjà trading", "déjà investi",
            "autre robot", "autre plateforme", "déjà équipé",
            "j'en ai déjà un", "j'utilise déjà"
        ],
        response="C'est bien d'être déjà dans le trading. Mais vous diversifiez sûrement vos investissements. Nous, on affiche des performances de douze pourcent par mois depuis deux ans. Ça vaut le coup de comparer. Je vous prends rendez-vous avec l'expert ?",
        audio_path="finance_deja_robot.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "rencontrer", "voir en personne", "rendez-vous physique",
            "en face à face", "bureau", "agence",
            "je préfère me déplacer", "je viendrai en agence",
            "sur place", "en boutique", "en personne",
            "je passerai", "j'irai voir", "venir vous voir",
            "est-ce que vous recevez", "vous recevez", "avoir quelqu'un en face",
            "quelqu'un en face de moi", "pas au téléphone", "en physique"
        ],
        response="Avant toute chose, l'idée c'est bien sûr de vous entretenir avec notre expert pour qu'il puisse vous renseigner correctement. Et par la suite, si vous devenez client chez nous, je sais qu'il y a des séminaires une fois par an pour rencontrer l'ensemble de nos clients. Mais l'expert vous expliquera tout ça. Ça vous convient ?",
        audio_path="finance_rencontrer.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "hors france", "étranger", "autre pays",
            "pas en france", "à l'étranger", "international",
            "résident étranger", "expatrié"
        ],
        response="On travaille avec des clients partout dans le monde. Pas de problème pour les résidents hors France. Notre expert vous expliquera les modalités selon votre pays. Ça marche ?",
        audio_path="finance_hors_france.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "risque", "risqué", "perdre tout", "dangereux",
            "peur de perdre", "capital garanti", "sécurisé"
        ],
        response="Oui, le trading comporte des risques, c'est vrai. C'est pour ça que le robot diversifie et utilise des stop-loss automatiques. Douze pourcent par mois depuis deux ans, c'est la preuve que ça fonctionne. Et puis surtout, vous êtes accompagné par un expert qui vous expliquera la gestion du risque et qui sera là pour avoir un œil sur votre compte en permanence. On part là-dessus ?",
        audio_path="finance_risque.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "retirer argent", "récupérer", "retrait",
            "sortir l'argent", "liquider", "débloquer"
        ],
        response="Vous pouvez retirer votre argent quand vous voulez, pas de blocage. C'est votre capital, vous restez maître. Notre expert vous expliquera les modalités de retrait. On fait comme ça ?",
        audio_path="finance_retrait.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "régulé", "légal", "autorisé", "licence",
            "enregistré", "contrôlé", "supervision"
        ],
        response="Oui, on est une société régulée. Notre expert vous donnera tous les détails sur notre enregistrement et nos garanties. C'est important d'être en confiance. On y va ?",
        audio_path="finance_regule.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # FAQ TRADING ROBOT IA
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "c'est quoi", "c'est quoi exactement", "qu'est-ce que c'est",
            "de quoi il s'agit", "ça concerne quoi", "c'est à quel sujet",
            "vous voulez quoi", "vous proposez quoi", "objet appel",
            "sujet appel", "vous appelez pour quoi"
        ],
        response="En deux mots : on propose des robots de trading avec intelligence artificielle. Crypto, actions, forex. Douze pourcent par mois prouvé depuis deux ans. Notre expert vous expliquera tout en détail. On part là-dessus ?",
        audio_path="finance_cest_quoi.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "pourquoi m'appeler", "pourquoi vous m'appelez", "pourquoi cet appel",
            "pour quelle raison", "dans quel but", "à quel sujet vous m'appelez",
            "raison de votre appel", "motif de l'appel"
        ],
        response="Vous avez manifesté un intérêt pour le trading ou l'investissement. On vous propose de découvrir notre solution de robots IA avec des résultats prouvés. Notre expert vous donnera tous les détails. Ça marche ?",
        audio_path="finance_pourquoi.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "comment", "comment ça marche", "comment ça fonctionne",
            "ça marche comment", "expliquez-moi"
        ],
        response="C'est simple : vous déposez un capital minimum de deux cent cinquante euros, le robot trade automatiquement pour vous. Vous suivez vos gains en temps réel. Notre expert vous montrera une démo. On fait comme ça ?",
        audio_path="finance_comment.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "je comprends pas", "comprends pas", "j'ai pas compris",
            "vous pouvez répéter", "pardon répétez", "pardon j'ai pas compris",
            "hein", "quoi", "j'ai mal entendu", "répéter"
        ],
        response="Pas de souci, je reprends. On propose des robots de trading IA qui génèrent douze pourcent par mois. Capital minimum deux cent cinquante euros. Notre expert vous expliquera tout en détail. On part là-dessus ?",
        audio_path="finance_repeter.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "résultats", "performances", "gains", "rendement",
            "combien ça rapporte", "taux", "bénéfices"
        ],
        response="Douze pourcent par mois en moyenne, prouvé depuis deux ans. Notre expert vous montrera les résultats réels, pas des projections. On y va ?",
        audio_path="finance_resultats.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "crypto", "bitcoin", "ethereum", "cryptomonnaie",
            "monnaie virtuelle"
        ],
        response="Oui, on trade les cryptos : Bitcoin, Ethereum, et d'autres. Mais aussi les actions, le forex, les matières premières. Le robot diversifie automatiquement. Notre expert vous montrera les différents marchés. Ça marche ?",
        audio_path="finance_crypto.wav",
        entry_type="faq"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # IDENTIFICATION (spécifique trading IA)
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "qui êtes vous", "c'est qui", "vous êtes qui",
            "à qui j'ai affaire", "je parle à qui"
        ],
        response="On est spécialisés dans les robots de trading avec intelligence artificielle. Douze pourcent par mois prouvé depuis deux ans. Notre expert vous donnera tous les détails sur notre société. On part là-dessus ?",
        audio_path="finance_qui_etes_vous.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "quelle société", "quelle entreprise", "nom société",
            "vous êtes de quelle société", "nom de votre société",
            "pour quelle société", "société s'appelle comment"
        ],
        response="On est une société spécialisée dans le trading automatisé avec IA, régulée et avec des résultats prouvés depuis deux ans. Notre expert vous donnera tous les détails. Ça marche ?",
        audio_path="finance_quelle_societe.wav",
        entry_type="faq"
    ),
]
