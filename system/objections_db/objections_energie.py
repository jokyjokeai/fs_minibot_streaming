#!/usr/bin/env python3
"""
Objections ÉNERGIE (Panneaux solaires, pompes à chaleur, isolation) - MiniBotPanel v3

Objections et FAQ spécifiques au secteur Énergie/Rénovation énergétique.
Audio: audio/{voice}/objections/energie_*.wav
"""

from typing import List
from system.objections_database import ObjectionEntry

OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # OBJECTIONS
    ObjectionEntry(
        keywords=["trop cher", "investissement élevé", "prix", "coûte cher"],
        response="C'est vrai, l'investissement initial est significatif. Mais avec les aides de l'État (MaPrimeRénov, CEE) vous récupérez 40-60% immédiatement. Le reste se rentabilise en 7-10 ans. Après c'est 100% d'économies. Sur 25 ans vous gagnez 30-40k€. Ça change la donne non ?",
        audio_path="energie_prix.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["ça marche pas", "efficace", "rentable pas", "pas efficace"],
        response="Je comprends le doute. Nos clients économisent en moyenne 60-70% sur leur facture. Un couple avec maison 120m² : de 2500€/an à 800€/an. C'est 1700€ économisés chaque année. Sur 20 ans : 34 000€. C'est concret. Vous voulez qu'on calcule pour votre cas ?",
        audio_path="energie_efficacite.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["propriétaire pas", "location", "locataire", "pas propriétaire"],
        response="Vous êtes locataire ? Effectivement c'est pour les propriétaires. Mais vous connaissez des propriétaires autour de vous ? On a un programme de parrainage : vous touchez 500€ par parrainage. Intéressant non ?",
        audio_path="energie_locataire.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["arnaque", "démarchage", "fiable", "pas sérieux"],
        response="Prudence normale ! On est certifié RGE (Reconnu Garant Environnement), obligatoire pour les aides. On a +5000 installations en France, vérifiable sur Google. Paiement à la fin uniquement. Zéro acompte. Ça vous rassure ?",
        audio_path="energie_arnaque.wav",
        entry_type="objection"
    ),
    
    # FAQ
    ObjectionEntry(
        keywords=["aides état", "maprimerenov", "subventions", "aide financière"],
        response="MaPrimeRénov jusqu'à 10 000€, CEE jusqu'à 5000€, éco-PTZ sans intérêts. On s'occupe de TOUT : dossier, demande, versement. Vous n'avez rien à faire. On récupère 40-60% du coût total pour vous.",
        audio_path="energie_aides.wav",
        entry_type="faq"
    ),
    ObjectionEntry(
        keywords=["installation combien temps", "durée travaux", "chantier"],
        response="Installation 1-2 jours maximum. Pas de gros travaux ! Panneaux sur toit : 1 jour. Pompe à chaleur : 2 jours. Vous êtes dérangés au minimum. Propre, rapide, efficace.",
        audio_path="energie_duree.wav",
        entry_type="faq"
    ),
    ObjectionEntry(
        keywords=["garantie", "maintenance", "entretien", "SAV"],
        response="Garantie 20-25 ans constructeur. Maintenance annuelle offerte 5 ans. SAV français disponible 6j/7. Si panne, intervention sous 48h. Vous êtes tranquille !",
        audio_path="energie_garantie.wav",
        entry_type="faq"
    ),
]
