#!/usr/bin/env python3
"""
Objections CRYPTO / TRADING - MiniBotPanel v3

Objections et FAQ spécifiques au secteur Crypto/Trading.
Audio: audio/{voice}/objections/crypto_*.wav
"""

from typing import List
from system.objections_db.objections_database import ObjectionEntry

OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # OBJECTIONS
    ObjectionEntry(
        keywords=["trop risqué", "risque", "dangereux", "peur perdre", "risque crypto"],
        response="Je comprends. Les médias parlent des risques. Mais garder 100% en euros avec l'inflation, c'est aussi un risque ! On propose 5-10% de diversification. Plus un mode DÉMO gratuit pour tester sans risque.",
        audio_path="crypto_risque.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["déjà binance", "déjà coinbase", "déjà plateforme", "j'ai déjà"],
        response="Super ! Alors vous savez que Binance c'est 0,1% de frais. Nous 0,05%, soit 2x moins cher. Sur 100k€ de trades annuels, ça fait 500€ d'économie. Plus support 24/7 français. Vous tradez combien ?",
        audio_path="crypto_deja_plateforme.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["connais rien crypto", "débutant", "jamais fait", "comprends pas crypto"],
        response="Justement notre force ! 60% de clients débutants. Formation gratuite 2h visio, simulateur sans risque, accompagnement perso 3 mois. Vous apprenez tranquille. Curieux de découvrir ?",
        audio_path="crypto_debutant.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["arnaque", "bulle", "pyramide", "ponzi", "crypto arnaque"],
        response="On est régulé AMF (Autorité Marchés Financiers), société française vérifiable. Fonds ségrégués et sécurisés. 50k+ clients depuis 2019. Pas un site offshore ! Vous voulez vérifier sur le site AMF ?",
        audio_path="crypto_arnaque.wav",
        entry_type="objection"
    ),
    ObjectionEntry(
        keywords=["volatilité", "ça monte descend", "instable", "trop volatile"],
        response="La volatilité c'est justement l'opportunité ! +200% en 6 mois possible. Mais on vous forme à gérer : ordres limites, stop-loss, prise profits automatique. On transforme la volatilité en GAIN.",
        audio_path="crypto_volatilite.wav",
        entry_type="objection"
    ),
    
    # FAQ
    ObjectionEntry(
        keywords=["comment ça marche", "c'est quoi", "expliquer", "comment crypto"],
        response="Simple : vous créez un compte, vous déposez des euros, vous achetez crypto. Vous revendez quand vous voulez, vous récupérez vos euros. On a une démo vidéo 5min qui explique tout. Je vous l'envoie ?",
        audio_path="crypto_comment_marche.wav",
        entry_type="faq"
    ),
    ObjectionEntry(
        keywords=["retirer argent", "récupérer", "virement", "retrait"],
        response="Virement bancaire sous 24-48h max. Vous revendez crypto → euros sur compte → virement SEPA. Simple, rapide, sécurisé. Pas de blocage, pas de minimum.",
        audio_path="crypto_retirer.wav",
        entry_type="faq"
    ),
    ObjectionEntry(
        keywords=["montant minimum", "mise départ", "combien investir", "minimum"],
        response="Dès 50€ pour tester ! Mais pour une vraie diversification, on recommande 500-1000€ minimum. Vous pensez à quel montant pour débuter ?",
        audio_path="crypto_minimum.wav",
        entry_type="faq"
    ),
    ObjectionEntry(
        keywords=["sécurité", "piratage", "vol", "hacké", "sécurisé"],
        response="Fonds sécurisés cold wallet (hors ligne) + hot wallet (en ligne) minimal. Assurance jusqu'à 100k€. Authentification 2FA obligatoire. Jamais piraté en 5 ans. Vous voulez les détails sécurité ?",
        audio_path="crypto_securite.wav",
        entry_type="faq"
    ),
    ObjectionEntry(
        keywords=["impôts", "fiscalité", "déclarer", "taxes"],
        response="Oui à déclarer ! On génère automatiquement votre IFU fiscal pour les impôts. Plus-values taxées flat tax 30%. On vous aide pour la déclaration. Tout est transparent et légal.",
        audio_path="crypto_impots.wav",
        entry_type="faq"
    ),
]
