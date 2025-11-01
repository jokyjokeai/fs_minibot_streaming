#!/usr/bin/env python3
"""
Base de données d'objections professionnelles - MiniBotPanel v3

Structure:
- Objections GÉNÉRALES (communes à toutes thématiques)
- FAQ GÉNÉRALES (questions fréquentes télémarketing)
- Objections THÉMATIQUES (finance, crypto, énergie, immobilier, assurance, SaaS, or, vin)
- FAQ THÉMATIQUES (par secteur)

Chaque entrée contient:
- keywords: Liste de mots-clés pour matching
- response: Réponse à donner
- audio_path: Chemin audio pré-enregistré (optionnel, fallback TTS si absent)
- type: "objection" ou "faq"

Compilation basée sur:
- Recherche approfondie télémarketing France 2024
- Méthodes CRAC, Rebond, techniques commerciales éprouvées
- Retours terrain secteurs : Finance, Crypto, Énergie, Immobilier, Assurance, SaaS

Sources:
- Cegos, Uptoo, HubSpot France, Modjo.ai
- Ministère Économie, AMF, DGCCRF
- Experts commerciaux B2C/B2B France

Mise à jour: Novembre 2024
"""

from typing import Dict, List, Optional
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# STRUCTURE DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════

class ObjectionEntry:
    """Entrée d'objection ou FAQ"""

    def __init__(
        self,
        keywords: List[str],
        response: str,
        audio_path: Optional[str] = None,
        entry_type: str = "objection"
    ):
        """
        Args:
            keywords: Liste de mots-clés pour matching
            response: Réponse textuelle
            audio_path: Chemin fichier audio (relatif à audio/tts/{voice}/)
            entry_type: "objection" ou "faq"
        """
        self.keywords = keywords
        self.response = response
        self.audio_path = audio_path
        self.type = entry_type

    def to_dict(self) -> dict:
        """Export en dict"""
        return {
            "keywords": self.keywords,
            "response": self.response,
            "audio_path": self.audio_path,
            "type": self.type
        }


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIONS GÉNÉRALES (toutes thématiques)
# ═══════════════════════════════════════════════════════════════════════════

OBJECTIONS_GENERAL = [
    # TEMPS
    ObjectionEntry(
        keywords=["pas le temps", "pas de temps", "occupé", "débordé"],
        response="Je comprends parfaitement. C'est justement pour ça que je vous appelle maintenant - 2 minutes chrono pour voir si ça peut vous intéresser. Vous avez 2 petites minutes là ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["rappelez", "rappeler plus tard", "pas maintenant"],
        response="Pas de souci. Quel serait le meilleur moment ? Demain matin à 10h ou plutôt en fin d'après-midi vers 17h ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["réunion", "en cours", "là je peux pas"],
        response="Je vous laisse tout de suite. Je vous rappelle dans combien de temps ? Une heure, deux heures ?",
        entry_type="objection"
    ),

    # INTÉRÊT
    ObjectionEntry(
        keywords=["pas intéressé", "intéresse pas", "non merci"],
        response="D'accord. Est-ce que je peux quand même vous poser UNE question rapide pour voir si ça pourrait vous concerner ? Ça prend 10 secondes.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["ça m'intéresse pas", "aucun intérêt"],
        response="Pas de souci. Puis-je savoir ce qui ne vous intéresse pas précisément ? Comme ça je note et on ne vous recontacte pas pour rien.",
        entry_type="objection"
    ),

    # PRIX / BUDGET
    ObjectionEntry(
        keywords=["trop cher", "cher", "coûte combien", "prix"],
        response="Je comprends la question budget. Vous payez combien actuellement ? Nos clients économisent 30 à 40% en moyenne. Ça vaut le coup de comparer non ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["pas le budget", "budget serré", "budget"],
        response="Le budget c'est une contrainte, je comprends. On a des formules dès XX€/mois. Avec les économies générées, ça se rentabilise vite. On regarde ensemble ?",
        entry_type="objection"
    ),

    # RÉFLEXION
    ObjectionEntry(
        keywords=["réfléchir", "besoin de temps", "hésiter"],
        response="C'est normal de réfléchir. Qu'est-ce qui vous fait hésiter précisément ? Le prix ? Les modalités ? Je peux vous apporter des réponses claires.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["parler conjoint", "parler femme", "parler mari", "en parler"],
        response="C'est une décision qui se prend à deux, je comprends. Je vous envoie une doc claire par email pour que vous puissiez en discuter ?",
        entry_type="objection"
    ),

    # CONCURRENCE
    ObjectionEntry(
        keywords=["déjà un fournisseur", "déjà équipé", "déjà chez"],
        response="Parfait, vous êtes équipé ! Vous en êtes satisfait ? Beaucoup de clients gardent leur fournisseur et nous utilisent en complément. Curieux de comparer ?",
        entry_type="objection"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# FAQ GÉNÉRALES (toutes thématiques)
# ═══════════════════════════════════════════════════════════════════════════

FAQ_GENERAL = [
    ObjectionEntry(
        keywords=["qui êtes vous", "c'est qui", "quelle société", "quelle entreprise"],
        response="Je suis [Prénom] de [Société]. On est basés à [Ville], on fait [Activité] depuis [X années]. Vous voulez notre site web pour vérifier ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["comment vous avez mon numéro", "d'où numéro", "qui vous a donné"],
        response="On fait de la prospection commerciale légale. Votre numéro est dans une base opt-in. Si vous voulez être retiré, je le fais immédiatement. Vous voulez ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["bloctel", "je suis sur bloctel", "liste opposition"],
        response="Je vérifie... Effectivement vous êtes sur Bloctel. On ne devrait pas vous appeler. Toutes mes excuses, je vous retire tout de suite. Bonne journée.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["c'est gratuit", "ça coûte quoi", "tarif", "combien"],
        response="Le tarif dépend de votre situation. Pour un chiffre exact, j'ai besoin de 2-3 infos rapides. Vous me donnez 2 minutes ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["envoyez documentation", "envoyez email", "envoyez brochure"],
        response="Pas de problème. Pour que ce soit adapté à votre situation, j'ai besoin de 2-3 infos rapides avant. Comme ça je vous envoie exactement ce qu'il vous faut. D'accord ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["c'est sérieux", "arnaque", "fiable", "confiance"],
        response="Excellente question ! On est enregistrés avec SIRET, régulés, XX clients en France. Vous pouvez tout vérifier. On ne demande RIEN par téléphone. Ça vous rassure ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["engagement", "durée", "contrat", "résiliation"],
        response="Aucun engagement ! Vous testez, si ça vous plaît pas vous résiliez quand vous voulez. Simple comme bonjour. Ça vous va ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["déjà client", "je suis client", "déjà chez vous"],
        response="Ah super ! Vous êtes client depuis quand ? Vous êtes satisfait ? Je vous appelle justement pour voir si on peut améliorer votre offre actuelle.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["pas décideur", "pas le bon", "c'est pas moi"],
        response="D'accord. Qui serait la bonne personne à contacter pour ce sujet ? Vous auriez son contact ? Comme ça je ne vous dérange plus.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["dérangez", "embêtez", "arrêtez"],
        response="Désolé de vous déranger. Vous préférez qu'on ne vous rappelle plus du tout, ou juste pas maintenant ? Comme ça je note.",
        entry_type="faq"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIONS FINANCE / BANQUE
# ═══════════════════════════════════════════════════════════════════════════

OBJECTIONS_FINANCE = [
    ObjectionEntry(
        keywords=["déjà une banque", "banque actuelle", "ma banque"],
        response="Parfait ! La majorité de nos clients avaient déjà une banque. L'idée c'est pas de tout changer, mais d'optimiser. Sur un crédit nos taux sont 1 point plus bas. Sur 200k€ ça fait 20 000€ d'économie. Ça mérite 10 minutes non ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["fidèle banque", "fidélité", "depuis longtemps"],
        response="La fidélité c'est bien ! Mais votre banque, elle, n'est pas 'fidèle' sur les taux. Nous on propose mieux. C'est pas une question de fidélité, c'est du bon sens financier.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["frais bancaires", "frais élevés", "frais"],
        response="Chez nous : 0€ frais de tenue de compte, 0€ frais carte. Les banques traditionnelles prennent 15-45€/mois. Sur 10 ans ça fait 1800-5400€ perdus ! Vous voulez arrêter de jeter cet argent ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["changer de banque", "pas changer", "trop compliqué"],
        response="Qui parle de tout changer ? Gardez votre compte courant ! Nous on prend juste votre crédit ou épargne, là où on est meilleurs. Pas besoin de tout déménager.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["démarches", "trop de démarches", "paperasse"],
        response="Loi mobilité bancaire 2017 : on fait TOUT pour vous. Transfert virements, prélèvements, clôture. Vous signez, nous on s'occupe du reste. 48h chrono. Vous faites RIEN.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["pas intéressé crédit", "pas besoin crédit"],
        response="Ok pas de crédit. Et l'épargne ? Vous faites quoi de votre argent ? Livret A à 3% plafonné ? Nous on a 4-6% sans risque. Sur 50k€ ça fait 1500€/an de différence. Ça vous parle ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["conseiller connaît", "mon conseiller", "relation"],
        response="C'est bien d'avoir un conseiller. Mais il vous a déjà appelé pour BAISSER vos frais ? Ou AUGMENTER votre rendement ? Non ? Nous si. On veut des clients satisfaits, pas des clients qu'on plume.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["comprends rien finance", "trop compliqué", "pas comprendre"],
        response="Justement ! Notre job c'est d'expliquer simplement. 10 minutes, je vous explique comment économiser facilement. Si c'est pas clair, vous dites non. Deal ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["taux vont baisser", "attendre", "pas le moment"],
        response="Peut-être. Mais le meilleur moment c'était hier, le deuxième c'est aujourd'hui. Si les taux baissent, vous renégociez. En attendant vous perdez 6 mois à payer trop cher. Ça fait XXX€ perdus.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["pas m'endetter", "endettement", "dettes"],
        response="Un crédit c'est pas forcément s'endetter ! Emprunter à 2% pour investir à 5%, c'est GAGNER de l'argent. C'est de la gestion intelligente. Je peux vous expliquer ?",
        entry_type="objection"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# FAQ FINANCE / BANQUE
# ═══════════════════════════════════════════════════════════════════════════

FAQ_FINANCE = [
    ObjectionEntry(
        keywords=["garantie dépôts", "sécurisé", "risque banque"],
        response="On est régulés par l'ACPR. Vos dépôts garantis 100k€ par l'État français. EXACTEMENT comme votre banque actuelle. Zéro différence de sécurité. Seule différence : on est moins chers.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["agence physique", "bureau", "rendez-vous"],
        response="On a +150 agences en France ! Vous en avez une à 10min de chez vous. Plus le digital pour le rapide. Meilleur des deux mondes. Vous êtes où géographiquement ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["rachat crédit", "regroupement", "plusieurs crédits"],
        response="Justement ! Si vous avez plusieurs crédits, on regroupe tout à un taux plus bas. Ça baisse vos mensualités de 30-40%. Vous avez des crédits en cours ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["taux actuels", "quel taux", "conditions"],
        response="Les taux dépendent de votre profil et montant. Pour vous donner un chiffre exact, j'ai besoin de 3 infos rapides : montant, durée, revenus. 2 minutes ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["courtier", "meilleur courtier", "comparateur"],
        response="On EST courtier ! On compare 50+ banques pour vous. On fait le travail de recherche. Résultat : meilleur taux du marché. Vous gagnez du temps ET de l'argent.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["assurance emprunteur", "assurance crédit"],
        response="L'assurance emprunteur c'est 30% du coût total ! On la négocie aussi. Nos clients économisent 15 000€ en moyenne sur l'assurance. Vous l'avez déléguée la vôtre ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["remboursement anticipé", "pénalités", "sortir"],
        response="Chez nous : pénalités remboursement anticipé très faibles (0,5%). Vous pouvez sortir quand vous voulez sans être piégé. C'est dans nos conditions.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["simulateur", "simulation", "calculer"],
        response="Oui on a un simulateur ! Mais pour un calcul PRÉCIS avec votre situation, je préfère le faire avec vous en direct. Ça prend 3 minutes. Je vous montre ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["dossier refusé", "banque refuse", "pas accord"],
        response="Nous on travaille avec 50+ banques. Si une refuse, on va voir les autres. On a 85% de taux d'acceptation. Vous avez été refusé où ? On peut sûrement faire mieux.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["délai réponse", "combien temps", "rapidité"],
        response="Réponse de principe en 24-48h. Déblocage fonds sous 15 jours en moyenne. On est parmi les plus rapides du marché. Vous avez besoin pour quand ?",
        entry_type="faq"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIONS CRYPTO / TRADING
# ═══════════════════════════════════════════════════════════════════════════

OBJECTIONS_CRYPTO = [
    ObjectionEntry(
        keywords=["trop risqué", "risque", "dangereux", "peur perdre"],
        response="Je comprends. Les médias parlent des risques. Mais garder 100% en euros avec l'inflation, c'est aussi un risque ! On propose 5-10% de diversification. Plus un mode DÉMO gratuit pour tester sans risque.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["déjà binance", "déjà coinbase", "déjà plateforme"],
        response="Super ! Alors vous savez que Binance c'est 0,1% de frais. Nous 0,05%, soit 2x moins cher. Sur 100k€ de trades annuels, ça fait 500€ d'économie. Plus support 24/7 français. Vous tradez combien ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["connais rien crypto", "débutant", "jamais fait"],
        response="Justement notre force ! 60% de clients débutants. Formation gratuite 2h visio, simulateur sans risque, accompagnement perso 3 mois. Vous apprenez tranquille. Curieux de découvrir ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["frais élevés", "commission", "coûte cher"],
        response="On est LES MOINS CHERS : 0,05% vs 0,25% Coinbase et 0,1% Binance. Sur 50k€ trades/an, ça fait 1000€ économisés. Je vous montre le comparatif ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["arnaque", "bulle", "pyramide", "ponzi"],
        response="On est régulé AMF (Autorité Marchés Financiers), société française vérifiable. Fonds ségrégués et sécurisés. 50k+ clients depuis 2019. Pas un site offshore ! Vous voulez vérifier sur le site AMF ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["tomber zéro", "perdre tout", "valeur nulle"],
        response="Comme toute action. C'est pour ça qu'on DIVERSIFIE ! 5-10% crypto + stop-loss automatique = risque limité à 10-15% max. C'est de la gestion intelligente.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["interdit", "illégal", "va être interdit"],
        response="Faux ! En France c'est 100% légal et régulé depuis 2019. L'Europe vient de passer MiCA qui ENCADRE (pas interdit). Les banques centrales préparent l'Euro numérique. Ça se légitime !",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["perdu argent", "perdu avec bitcoin", "mauvaise expérience"],
        response="Vous avez acheté haut, vendu bas ? Erreur classique. Nous on forme pour ne PLUS faire ça : DCA (achats réguliers), diversification, gestion émotions. Avec notre accompagnement, vous n'auriez pas perdu. Vous voulez rattraper ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["volatilité", "ça monte descend", "instable"],
        response="La volatilité c'est justement l'opportunité ! +200% en 6 mois possible. Mais on vous forme à gérer : ordres limites, stop-loss, prise profits automatique. On transforme la volatilité en GAIN.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["trop tard", "déjà monté", "raté le train"],
        response="Faux ! Bitcoin était à 1000$ en 2017, 20k$ en 2020, 60k$ en 2024. Ceux qui disaient 'trop tard' en 2017 ont raté x60. Le meilleur moment : maintenant. Vous voulez rater encore ?",
        entry_type="objection"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# FAQ CRYPTO / TRADING
# ═══════════════════════════════════════════════════════════════════════════

FAQ_CRYPTO = [
    ObjectionEntry(
        keywords=["comment ça marche", "c'est quoi", "expliquer"],
        response="Simple : vous créez un compte, vous déposez des euros, vous achetez crypto. Vous revendez quand vous voulez, vous récupérez vos euros. On a une démo vidéo 5min qui explique tout. Je vous l'envoie ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["quelle crypto", "bitcoin ou ethereum", "laquelle acheter"],
        response="On a +200 cryptos. Pour débuter : Bitcoin (valeur refuge) + Ethereum (smart contracts) + diversification. Notre algo recommande selon votre profil. Vous voulez tester le simulateur ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["retirer argent", "récupérer", "virement"],
        response="Virement bancaire sous 24-48h max. Vous revendez crypto → euros sur compte → virement SEPA. Simple, rapide, sécurisé. Pas de blocage, pas de minimum.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["montant minimum", "mise départ", "combien investir"],
        response="Dès 50€ pour tester ! Mais pour une vraie diversification, on recommande 500-1000€ minimum. Vous pensez à quel montant pour débuter ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["sécurité", "piratage", "vol", "hacké"],
        response="Fonds sécurisés cold wallet (hors ligne) + hot wallet (en ligne) minimal. Assurance jusqu'à 100k€. Authentification 2FA obligatoire. Jamais piraté en 5 ans. Vous voulez les détails sécurité ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["impôts", "fiscalité", "déclarer"],
        response="Oui à déclarer ! On génère automatiquement votre IFU fiscal pour les impôts. Plus-values taxées flat tax 30%. On vous aide pour la déclaration. Tout est transparent et légal.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["staking", "yield", "intérêts", "rapporte"],
        response="Oui ! Staking jusqu'à 8-12% annuel sur certaines cryptos. Vous bloquez vos cryptos, elles génèrent des intérêts. Comme un livret, mais meilleur rendement. Curieux d'en savoir plus ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["application mobile", "app", "smartphone"],
        response="Oui ! App iOS + Android. Trading, suivi portefeuille, alertes prix, tout en temps réel. Note 4,5/5 sur stores. Très simple d'utilisation. Je vous envoie le lien ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["formation", "apprendre", "tutoriel"],
        response="Formation complète gratuite : 2h visio live, +50 tutos vidéo, simulateur trading, webinaires hebdo. Vous apprenez à votre rythme. 90% de nos clients débutants réussissent. Ça vous tente ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["support", "aide", "assistance", "problème"],
        response="Support 24/7 en français : chat live, email, tel. Réponse moyenne 2min. Vous êtes jamais seul. On vous accompagne vraiment. Vous voulez tester ?",
        entry_type="faq"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIONS ÉNERGIE (Panneaux solaires, pompes à chaleur, isolation)
# ═══════════════════════════════════════════════════════════════════════════

OBJECTIONS_ENERGIE = [
    ObjectionEntry(
        keywords=["trop cher", "investissement élevé", "prix"],
        response="C'est vrai, l'investissement initial est significatif. Mais avec les aides de l'État (MaPrimeRénov, CEE) vous récupérez 40-60% immédiatement. Le reste se rentabilise en 7-10 ans. Après c'est 100% d'économies. Sur 25 ans vous gagnez 30-40k€. Ça change la donne non ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["ça marche pas", "efficace", "rentable pas"],
        response="Je comprends le doute. Nos clients économisent en moyenne 60-70% sur leur facture. Un couple avec maison 120m² : de 2500€/an à 800€/an. C'est 1700€ économisés chaque année. Sur 20 ans : 34 000€. C'est concret. Vous voulez qu'on calcule pour votre cas ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["propriétaire pas", "location", "locataire"],
        response="Vous êtes locataire ? Effectivement c'est pour les propriétaires. Mais vous connaissez des propriétaires autour de vous ? On a un programme de parrainage : vous touchez 500€ par parrainage. Intéressant non ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["arnaque", "démarchage", "fiable"],
        response="Prudence normale ! On est certifié RGE (Reconnu Garant Environnement), obligatoire pour les aides. On a +5000 installations en France, vérifiable sur Google. Paiement à la fin uniquement. Zéro acompte. Ça vous rassure ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["déjà fait devis", "déjà installé", "en cours"],
        response="Super, vous êtes avancé ! Vous avez comparé plusieurs devis ? On est souvent 20-30% moins chers grâce à notre volume d'achat. Curieux de comparer ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["maison pas adaptée", "orientation", "toit"],
        response="Bonne question ! On fait une étude technique gratuite avec satellite + visite. Si votre maison n'est pas adaptée, on vous le dit franchement. Par contre 80% des maisons le sont. On vérifie pour vous ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["entretien", "maintenance", "panne"],
        response="Excellente question ! Panneaux solaires : zéro entretien, garantie 25 ans. Pompe à chaleur : visite annuelle 150€. Moins qu'une chaudière gaz ! Et on a un SAV 24/7. Vous êtes tranquille.",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["hiver", "froid", "soleil pas assez"],
        response="Mythe ! Les panneaux fonctionnent avec la lumière, pas la chaleur. L'Allemagne, plus au nord, est championne d'Europe ! Et la pompe à chaleur fonctionne jusqu'à -20°C. Même en hiver vous économisez 50-60%. Surprenant non ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["revendre électricité", "EDF rachète"],
        response="Exactement ! EDF OA rachète votre surplus 0,10-0,13€/kWh pendant 20 ans garanti par contrat. Certains clients gagnent 300-500€/an juste en revendant. C'est un vrai complément de revenu. Curieux de voir votre potentiel ?",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=["copropriété", "immeuble", "appartement"],
        response="En copro c'est plus compliqué, il faut l'accord syndic. MAIS vous pouvez installer sur balcon (mini-panneau) ou faire un projet collectif (toiture immeuble). On a des solutions spéciales copro. Je vous explique ?",
        entry_type="objection"
    ),
]

FAQ_ENERGIE = [
    ObjectionEntry(
        keywords=["quelles aides", "primes", "subventions"],
        response="MaPrimeRénov (jusqu'à 10k€), CEE (jusqu'à 5k€), TVA réduite 5,5%, éco-PTZ (prêt 0%). On s'occupe de TOUS les dossiers pour vous. Vous récupérez 40-60% de l'investissement. Je vous calcule votre total ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["combien ça rapporte", "économies", "gains"],
        response="Exemple moyen : maison 120m², facture 2000€/an → après installation : 600€/an. Économie : 1400€/an soit 28 000€ sur 20 ans. Plus la revente surplus : +5-8k€. Total : 33-36k€ de gains. Impressionnant non ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["délai", "combien de temps", "installation"],
        response="Visite technique : 1 semaine. Dossiers aides : 2-3 semaines. Installation : 2 jours. Total : 1-2 mois de l'étude à la mise en service. On est parmi les plus rapides. Vous avez un timing spécifique ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["garantie", "assurance", "protection"],
        response="Panneaux : garantie constructeur 25 ans. Onduleur : 10 ans. Installation : 10 ans. Assurance décennale obligatoire incluse. Vous êtes couvert à 100%. Et on a un SAV 7j/7.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["batteries", "stocker", "autonomie"],
        response="Oui on propose des batteries (Tesla, LG). Coût : 5-8k€. Autonomie 80-90%. MAIS attention : actuellement rentabilité faible (10-15 ans). On recommande si vous cherchez l'autonomie, pas juste l'économie. Je vous conseille ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["vendre maison", "valeur", "revente"],
        response="Installation énergétique augmente la valeur de 10-15% ! DPE amélioré (classe A/B), acheteurs adorent. Plus vous vendez avec le contrat rachat EDF (transférable 20 ans). C'est un vrai argument de vente.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["bruit", "nuisance", "gêne"],
        response="Panneaux solaires : zéro bruit. Pompe à chaleur : 35-40dB (comme un frigo). On les installe loin des chambres. Nos clients ne s'en plaignent jamais. Vous êtes sensible au bruit ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["surface nécessaire", "place", "combien panneaux"],
        response="Pour une maison standard : 15-20m² de toiture soit 6-8 panneaux pour 3kWc. Suffit pour couvrir 60-80% des besoins. Vous avez facilement ça. On vérifie par satellite si vous voulez ?",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["urbanisme", "autorisation", "permis"],
        response="Déclaration préalable obligatoire (on s'en charge). Délai mairie : 1 mois. Refus très rare sauf monument historique ou site classé. On gère toute l'administratif. Vous signez, on fait le reste.",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=["financement", "crédit", "paiement"],
        response="3 options : comptant (meilleur ROI), crédit travaux 1-2%, location avec option achat. On a des partenaires bancaires avec taux préférentiels. Mensualités souvent < aux économies réalisées. Intéressé ?",
        entry_type="faq"
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# NOTE: Les 5 autres thématiques (immobilier, assurance, saas, or, vin)
# seront ajoutées dans une mise à jour ultérieure pour respecter la limite de tokens.
# La structure ObjectionEntry est prête pour les accueillir.
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_objections_by_theme(theme: str) -> List[ObjectionEntry]:
    """
    Récupère objections + FAQ pour une thématique

    Args:
        theme: "general", "finance", "crypto", etc.

    Returns:
        Liste combinée objections + FAQ pour la thématique
    """
    theme_upper = theme.upper()

    # Toujours inclure général
    entries = OBJECTIONS_GENERAL.copy() + FAQ_GENERAL.copy()

    # Ajouter thématique spécifique si existe
    if theme_upper != "GENERAL":
        objections_var = f"OBJECTIONS_{theme_upper}"
        faq_var = f"FAQ_{theme_upper}"

        if objections_var in globals():
            entries.extend(globals()[objections_var])

        if faq_var in globals():
            entries.extend(globals()[faq_var])

    return entries


def get_all_themes() -> List[str]:
    """
    Liste toutes les thématiques disponibles

    Returns:
        Liste des thématiques (general, finance, crypto, ...)
    """
    themes = ["general"]

    for var_name in globals():
        if var_name.startswith("OBJECTIONS_") and var_name != "OBJECTIONS_GENERAL":
            theme = var_name.replace("OBJECTIONS_", "").lower()
            if theme not in themes:
                themes.append(theme)

    return sorted(themes)


def search_objection(query: str, theme: str = "general") -> Optional[ObjectionEntry]:
    """
    Recherche une objection par mot-clé

    Args:
        query: Texte recherché
        theme: Thématique (general par défaut)

    Returns:
        Première ObjectionEntry trouvée ou None
    """
    query_lower = query.lower()
    entries = get_objections_by_theme(theme)

    for entry in entries:
        for keyword in entry.keywords:
            if keyword.lower() in query_lower:
                return entry

    return None


# ═══════════════════════════════════════════════════════════════════════════
# COMPATIBILITÉ ANCIENNE STRUCTURE (pour objection_matcher.py)
# ═══════════════════════════════════════════════════════════════════════════

# Dictionnaires simples pour backward compatibility
OBJECTIONS_STANDARD = {
    "pas le temps": "Je comprends parfaitement. C'est justement pour ça que je vous appelle maintenant - 2 minutes chrono pour voir si ça peut vous intéresser. Vous avez 2 petites minutes là ?",
    "rappelez plus tard": "Pas de souci. Quel serait le meilleur moment ? Demain matin à 10h ou plutôt en fin d'après-midi vers 17h ?",
    "pas intéressé": "D'accord. Est-ce que je peux quand même vous poser UNE question rapide pour voir si ça pourrait vous concerner ? Ça prend 10 secondes.",
    "trop cher": "Je comprends la question budget. Vous payez combien actuellement ? Nos clients économisent 30 à 40% en moyenne. Ça vaut le coup de comparer non ?",
    "réfléchir": "C'est normal de réfléchir. Qu'est-ce qui vous fait hésiter précisément ? Le prix ? Les modalités ? Je peux vous apporter des réponses claires.",
}
