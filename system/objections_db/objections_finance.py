#!/usr/bin/env python3
"""
Objections FINANCE / BANQUE - MiniBotPanel v3

Objections et FAQ spécifiques au secteur Finance/Banque:
- Crédit immobilier, crédit conso, rachat de crédit
- Épargne, placements, assurance-vie
- Banque en ligne, néobanques, courtiers
- Services bancaires

Audio:
- Fichiers dans: audio/{voice}/objections/
- Noms: finance_*.wav
"""

from typing import List
from system.objections_db.objections_database import ObjectionEntry


OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # OBJECTIONS FINANCE / BANQUE
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "déjà une banque", "banque actuelle", "ma banque",
            "j'ai déjà une banque", "déjà banque"
        ],
        response="Parfait ! La majorité de nos clients avaient déjà une banque. L'idée c'est pas de tout changer, mais d'optimiser. Sur un crédit nos taux sont 1 point plus bas. Sur 200k€ ça fait 20 000€ d'économie. Ça mérite 10 minutes non ?",
        audio_path="finance_deja_banque.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "fidèle banque", "fidélité", "depuis longtemps",
            "client depuis longtemps", "fidèle à ma banque"
        ],
        response="La fidélité c'est bien ! Mais votre banque, elle, n'est pas 'fidèle' sur les taux. Nous on propose mieux. C'est pas une question de fidélité, c'est du bon sens financier.",
        audio_path="finance_fidelite.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "frais bancaires", "frais élevés", "frais",
            "trop de frais", "frais de gestion"
        ],
        response="Chez nous : 0€ frais de tenue de compte, 0€ frais carte. Les banques traditionnelles prennent 15-45€/mois. Sur 10 ans ça fait 1800-5400€ perdus ! Vous voulez arrêter de jeter cet argent ?",
        audio_path="finance_frais.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "changer de banque", "pas changer", "trop compliqué",
            "compliqué changer", "changer banque compliqué"
        ],
        response="Qui parle de tout changer ? Gardez votre compte courant ! Nous on prend juste votre crédit ou épargne, là où on est meilleurs. Pas besoin de tout déménager.",
        audio_path="finance_changer_banque.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "démarches", "trop de démarches", "paperasse",
            "administratif", "trop de papiers"
        ],
        response="Loi mobilité bancaire 2017 : on fait TOUT pour vous. Transfert virements, prélèvements, clôture. Vous signez, nous on s'occupe du reste. 48h chrono. Vous faites RIEN.",
        audio_path="finance_demarches.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "pas intéressé crédit", "pas besoin crédit",
            "besoin pas crédit", "crédit m'intéresse pas"
        ],
        response="Ok pas de crédit. Et l'épargne ? Vous faites quoi de votre argent ? Livret A à 3% plafonné ? Nous on a 4-6% sans risque. Sur 50k€ ça fait 1500€/an de différence. Ça vous parle ?",
        audio_path="finance_pas_besoin_credit.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "conseiller connaît", "mon conseiller", "relation",
            "mon conseiller bancaire", "relation avec conseiller"
        ],
        response="C'est bien d'avoir un conseiller. Mais il vous a déjà appelé pour BAISSER vos frais ? Ou AUGMENTER votre rendement ? Non ? Nous si. On veut des clients satisfaits, pas des clients qu'on plume.",
        audio_path="finance_conseiller.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "comprends rien finance", "trop compliqué", "pas comprendre",
            "comprends pas finance", "trop complexe"
        ],
        response="Justement ! Notre job c'est d'expliquer simplement. 10 minutes, je vous explique comment économiser facilement. Si c'est pas clair, vous dites non. Deal ?",
        audio_path="finance_complique.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "taux vont baisser", "attendre", "pas le moment",
            "attendre baisse taux", "moment pas bon"
        ],
        response="Peut-être. Mais le meilleur moment c'était hier, le deuxième c'est aujourd'hui. Si les taux baissent, vous renégociez. En attendant vous perdez 6 mois à payer trop cher. Ça fait XXX€ perdus.",
        audio_path="finance_attendre.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "pas m'endetter", "endettement", "dettes",
            "veux pas m'endetter", "peur dettes"
        ],
        response="Un crédit c'est pas forcément s'endetter ! Emprunter à 2% pour investir à 5%, c'est GAGNER de l'argent. C'est de la gestion intelligente. Je peux vous expliquer ?",
        audio_path="finance_endettement.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # FAQ FINANCE / BANQUE
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "garantie dépôts", "sécurisé", "risque banque",
            "dépôts garantis", "sécurité dépôts"
        ],
        response="On est régulés par l'ACPR. Vos dépôts garantis 100k€ par l'État français. EXACTEMENT comme votre banque actuelle. Zéro différence de sécurité. Seule différence : on est moins chers.",
        audio_path="finance_garantie.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "agence physique", "bureau", "rendez-vous",
            "agence près de chez moi", "bureau physique"
        ],
        response="On a +150 agences en France ! Vous en avez une à 10min de chez vous. Plus le digital pour le rapide. Meilleur des deux mondes. Vous êtes où géographiquement ?",
        audio_path="finance_agence.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "rachat crédit", "regroupement", "plusieurs crédits",
            "regrouper crédits", "racheter crédit"
        ],
        response="Justement ! Si vous avez plusieurs crédits, on regroupe tout à un taux plus bas. Ça baisse vos mensualités de 30-40%. Vous avez des crédits en cours ?",
        audio_path="finance_rachat_credit.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "taux actuels", "quel taux", "conditions",
            "taux intérêt", "conditions crédit"
        ],
        response="Les taux dépendent de votre profil et montant. Pour vous donner un chiffre exact, j'ai besoin de 3 infos rapides : montant, durée, revenus. 2 minutes ?",
        audio_path="finance_taux.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "courtier", "meilleur courtier", "comparateur",
            "vous êtes courtier", "passer par courtier"
        ],
        response="On EST courtier ! On compare 50+ banques pour vous. On fait le travail de recherche. Résultat : meilleur taux du marché. Vous gagnez du temps ET de l'argent.",
        audio_path="finance_courtier.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "assurance emprunteur", "assurance crédit",
            "assurance prêt", "délégation assurance"
        ],
        response="L'assurance emprunteur c'est 30% du coût total ! On la négocie aussi. Nos clients économisent 15 000€ en moyenne sur l'assurance. Vous l'avez déléguée la vôtre ?",
        audio_path="finance_assurance.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "remboursement anticipé", "pénalités", "sortir",
            "rembourser avant", "pénalité sortie"
        ],
        response="Chez nous : pénalités remboursement anticipé très faibles (0,5%). Vous pouvez sortir quand vous voulez sans être piégé. C'est dans nos conditions.",
        audio_path="finance_remboursement_anticipe.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "simulateur", "simulation", "calculer",
            "faire simulation", "outil simulation"
        ],
        response="Oui on a un simulateur ! Mais pour un calcul PRÉCIS avec votre situation, je préfère le faire avec vous en direct. Ça prend 3 minutes. Je vous montre ?",
        audio_path="finance_simulateur.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "dossier refusé", "banque refuse", "pas accord",
            "refus crédit", "dossier rejeté"
        ],
        response="Nous on travaille avec 50+ banques. Si une refuse, on va voir les autres. On a 85% de taux d'acceptation. Vous avez été refusé où ? On peut sûrement faire mieux.",
        audio_path="finance_dossier_refuse.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "délai réponse", "combien temps", "rapidité",
            "délai accord", "temps réponse"
        ],
        response="Réponse de principe en 24-48h. Déblocage fonds sous 15 jours en moyenne. On est parmi les plus rapides du marché. Vous avez besoin pour quand ?",
        audio_path="finance_delai.wav",
        entry_type="faq"
    ),
]
