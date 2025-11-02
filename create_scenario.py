#!/usr/bin/env python3
"""
Create Scenario - MiniBotPanel v3

Script interactif ultra-complet pour créer des scénarios conversationnels.

Respecte la logique de base : HELLO → RETRY → Q1...Qn → IS_LEADS → CONFIRM → BYE

Fonctionnalités:
- Thématiques métier pré-configurées (finance, crypto, énergie, etc.)
- Structure de base flexible (hello/retry/bye + questions configurable

s)
- Objections pré-enregistrées + fallback Freestyle AI
- Qualification cumulative configurable
- Variables dynamiques ({{first_name}}, {{company}}, etc.)
- Génération TTS automatique des objections
- Mode Freestyle AI intelligent avec contexte thématique
- Barge-in configurable par étape

Usage:
    python3 create_scenario.py
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import objections database
try:
    from system.objections_database import get_objections_for_thematique
except ImportError:
    import warnings
    warnings.warn("objections_database not found, using embedded objections", UserWarning)
    def get_objections_for_thematique(key):
        return {}

# Couleurs terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str, char: str = "═"):
    """Affiche un header stylisé"""
    width = 70
    print(f"\n{Colors.CYAN}{char * width}")
    print(f"{title:^{width}}")
    print(f"{char * width}{Colors.END}\n")

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def ask_yes_no(question: str, default: bool = True) -> bool:
    """Pose une question oui/non"""
    suffix = "[O/n]" if default else "[o/N]"
    while True:
        response = input(f"{question} {suffix}: ").strip().lower()
        if not response:
            return default
        if response in ['o', 'oui', 'y', 'yes']:
            return True
        if response in ['n', 'non', 'no']:
            return False
        print_error("Réponse invalide. Utilisez O (oui) ou N (non)")

def ask_text(question: str, default: str = "", required: bool = True) -> str:
    """Pose une question texte"""
    while True:
        if default:
            response = input(f"{question} [{default}]: ").strip()
            result = response if response else default
        else:
            response = input(f"{question}: ").strip()
            result = response

        if result or not required:
            return result
        print_error("Ce champ est requis")

def ask_int(question: str, default: int = None, min_val: int = None, max_val: int = None) -> int:
    """Pose une question numérique"""
    while True:
        if default is not None:
            response = input(f"{question} [{default}]: ").strip()
            if not response:
                return default
        else:
            response = input(f"{question}: ").strip()

        try:
            value = int(response)
            if min_val is not None and value < min_val:
                print_error(f"Valeur minimale: {min_val}")
                continue
            if max_val is not None and value > max_val:
                print_error(f"Valeur maximale: {max_val}")
                continue
            return value
        except ValueError:
            print_error("Entrez un nombre valide")

def ask_choice(question: str, choices: List[str], default: int = 1) -> int:
    """Pose une question à choix multiples"""
    print(f"\n{question}")
    for i, choice in enumerate(choices, 1):
        prefix = "→" if i == default else " "
        print(f"  {prefix} {i}) {choice}")

    while True:
        response = input(f"\nChoix [{default}]: ").strip()
        if not response:
            return default
        try:
            choice = int(response)
            if 1 <= choice <= len(choices):
                return choice
        except ValueError:
            pass
        print_error(f"Choix invalide. Entrez un nombre entre 1 et {len(choices)}")

# Personnalités d'agent pour prompt system Freestyle
AGENT_PERSONALITIES = {
    "professionnel": {
        "name": "Professionnel",
        "description": "Ton neutre, courtois, expert sans être froid",
        "tone": "professionnel, courtois, posé, crédible",
        "style": "Phrases claires et structurées. Vouvoiement. Arguments factuels et chiffrés. Pas de familiarité.",
        "example": "Je comprends votre questionnement. Nos solutions ont fait leurs preuves auprès de 500+ clients."
    },
    "doux": {
        "name": "Doux / Empathique",
        "description": "Ton chaleureux, à l'écoute, rassurant",
        "tone": "doux, empathique, rassurant, bienveillant",
        "style": "Écoute active. Reformule les préoccupations. Rassure avant d'argumenter. Ton chaleureux.",
        "example": "Je comprends tout à fait votre hésitation, c'est normal. Prenons le temps d'en discuter ensemble."
    },
    "dynamique": {
        "name": "Dynamique / Énergique",
        "description": "Ton enjoué, rythmé, enthousiaste",
        "tone": "dynamique, énergique, enthousiaste, rythmé",
        "style": "Phrases courtes et percutantes. Enthousiasme communicatif. Rythme soutenu. Vocabulaire actif.",
        "example": "Excellente question ! Justement, on a LA solution qui va vous faire gagner un temps fou !"
    },
    "assertif": {
        "name": "Assertif / Directif",
        "description": "Ton franc, direct, factuel sans détour",
        "tone": "assertif, direct, factuel, confiant",
        "style": "Va droit au but. Affirmatif sans être agressif. Oriente la conversation. Factuel et pragmatique.",
        "example": "Soyons clairs : vous perdez de l'argent actuellement. On peut y remédier en 48h."
    },
    "expert": {
        "name": "Expert technique",
        "description": "Ton pédagogue, maîtrise sujet, vulgarise",
        "tone": "expert, pédagogue, technique mais accessible",
        "style": "Explications claires. Vulgarise concepts complexes. Références techniques dosées. Posture d'expertise.",
        "example": "Le principe est simple : cette technologie optimise votre ROI via l'automatisation des flux."
    },
    "commercial": {
        "name": "Commercial / Persuasif",
        "description": "Ton vendeur, orienté bénéfices, closing",
        "tone": "commercial, persuasif, orienté résultats",
        "style": "Focus sur bénéfices client. Urgence légère. Techniques de closing. Arguments ROI et gains concrets.",
        "example": "Et si je vous disais que vous pouviez économiser 3000€ par an ? Ça change la donne non ?"
    },
    "consultative": {
        "name": "Consultatif / Conseil",
        "description": "Ton conseiller, pose questions, co-construit",
        "tone": "consultatif, questionnement, co-construction",
        "style": "Pose des questions ouvertes. Découverte besoins. Position de conseiller. Approche partenariale.",
        "example": "Pour vous orienter au mieux, puis-je vous poser quelques questions sur vos besoins actuels ?"
    }
}

# Thématiques métier avec contexte + objections
THEMATIQUES = {
    "finance": {
        "name": "Finance / Banque",
        "context": {
            "agent_name": "Sophie",
            "company": "notre banque",
            "product": "solutions de crédit et d'épargne",
            "campaign_context": "Prospection clients particuliers pour produits bancaires",
            "key_benefits": "taux attractifs, conseiller dédié, gestion simplifiée",
            "target_audience": "particuliers 25-60 ans avec revenus stables",
            "tone": "professionnel, rassurant, expert financier"
        },
        "objections": {
            "J'ai déjà une banque": "Je comprends que vous ayez déjà une banque. Justement, beaucoup de nos clients gardent leur banque principale et profitent de nos taux avantageux en complément. Puis-je vous en dire plus ?",
            "Les frais sont trop élevés": "C'est une bonne question sur les frais. Chez nous, pas de frais cachés et des tarifs jusqu'à 30% moins chers que les banques traditionnelles. Souhaitez-vous une comparaison personnalisée ?",
            "Je ne veux pas changer": "Pas de souci, pas besoin de tout changer. On peut simplement optimiser certains produits pour vous faire économiser. Est-ce que 5 minutes pour voir les économies possibles vous intéressent ?",
            "Pas intéressé par un crédit": "Aucun problème. Au-delà du crédit, on a aussi des solutions d'épargne et d'investissement. Êtes-vous intéressé par faire travailler votre argent ?",
            "Je dois réfléchir": "Bien sûr, c'est normal de prendre le temps. Je vous envoie une brochure par email et on peut en rediscuter quand vous voulez. Ça vous va ?"
        }
    },
    "trading_crypto": {
        "name": "Trading / Crypto",
        "context": {
            "agent_name": "Marc",
            "company": "CryptoTrade Pro",
            "product": "plateforme de trading crypto régulée",
            "campaign_context": "Prospection traders pour nouvelle plateforme crypto",
            "key_benefits": "frais réduits 0.1%, sécurité maximale AMF, 200+ cryptos",
            "target_audience": "traders actifs 18-45 ans",
            "tone": "dynamique, tech-savvy, moderne"
        },
        "objections": {
            "C'est trop risqué": "Je comprends votre prudence. C'est pour ça qu'on est régulé AMF et que vos fonds sont sécurisés. On propose aussi un mode démo pour tester sans risque. Ça vous intéresse ?",
            "J'ai déjà Binance/Coinbase": "Super, vous connaissez déjà ! Notre avantage c'est des frais 10x moins chers et le support francophone 24/7. Vous faites beaucoup de trades ?",
            "Je ne connais pas la crypto": "Pas de problème, on a justement un accompagnement pour débutants avec formation gratuite. Vous êtes curieux d'en savoir plus ?",
            "Les frais sont élevés": "Justement, nos frais sont les plus bas du marché : 0.1% contre 0.5-1% ailleurs. Sur 10000€ de trades, ça fait 900€ d'économies par an. Intéressant non ?",
            "C'est une arnaque": "Je comprends la méfiance, il y a eu des abus. Nous on est régulé AMF, société française, et vos fonds sont garantis. Vous voulez voir nos certifications ?"
        }
    },
    "energie_renouvelable": {
        "name": "Énergie Renouvelable",
        "context": {
            "agent_name": "Julie",
            "company": "GreenEnergy Solutions",
            "product": "panneaux solaires et pompes à chaleur",
            "campaign_context": "Prospection propriétaires pour transition énergétique",
            "key_benefits": "économies jusqu'à 70%, aides d'État jusqu'à 10000€, ROI 8-10 ans",
            "target_audience": "propriétaires maison individuelle",
            "tone": "écologique, pédagogue, orienté économies"
        },
        "objections": {
            "C'est trop cher": "C'est vrai que c'est un investissement. Mais avec les aides de l'État jusqu'à 10000€ et les économies de 70% sur vos factures, le retour sur investissement est de 8 ans. On peut calculer ensemble ?",
            "Ma maison n'est pas adaptée": "C'est une bonne question. On fait justement une étude gratuite pour voir ce qui est possible chez vous. Même sans toit idéal, il y a souvent des solutions. Je peux envoyer un technicien ?",
            "Je suis locataire": "Ah effectivement, en tant que locataire c'est compliqué. Par contre, vous connaissez peut-être des propriétaires qui seraient intéressés ? On a un programme de parrainage.",
            "Les aides sont compliquées": "Je vous comprends, c'est un vrai labyrinthe. Justement on s'occupe de TOUT : dossier de subvention, installation, démarches. Vous n'avez rien à faire. Ça change la donne non ?",
            "J'ai déjà isolé": "Parfait, l'isolation c'est la base ! Maintenant l'étape suivante c'est de produire votre propre énergie. Avec vos combles isolés, vous allez économiser encore plus. On regarde ?"
        }
    },
    "immobilier": {
        "name": "Immobilier",
        "context": {
            "agent_name": "Pierre",
            "company": "ImmoExpert",
            "product": "estimation et vente de biens immobiliers",
            "campaign_context": "Prospection propriétaires pour vente ou estimation gratuite",
            "key_benefits": "estimation gratuite en 48h, vente en 45 jours moyenne, 0% frais si pas vendu",
            "target_audience": "propriétaires envisageant une vente dans 6-12 mois",
            "tone": "expert local, valorisation, rassurant"
        },
        "objections": {
            "Je ne vends pas actuellement": "Pas de souci, beaucoup de nos clients ne vendent pas tout de suite. Une estimation gratuite vous donne une idée de la valeur actuelle. C'est toujours bon à savoir, non ?",
            "J'ai déjà une agence": "Ok, vous avez mandaté quelqu'un. Est-ce que vous avez déjà eu des visites ? On a des techniques de vente rapide qui fonctionnent très bien en complément.",
            "Vos frais sont trop élevés": "Je comprends, les frais c'est important. On a une formule 0% si on ne vend pas, et nos frais sont parmi les plus bas du secteur. Je vous montre le comparatif ?",
            "Le marché est mauvais": "C'est une idée reçue. En réalité, le marché local est dynamique et on vend en moyenne en 45 jours. Le bon prix et la bonne stratégie font tout. On en discute ?",
            "Je veux vendre seul": "Je respecte ça. Mais saviez-vous que les biens vendus en agence se vendent 8% plus cher en moyenne ? Notre expertise vous fait gagner du temps ET de l'argent. On fait un point rapide ?"
        }
    },
    "assurance": {
        "name": "Assurance",
        "context": {
            "agent_name": "Caroline",
            "company": "AssurPlus",
            "product": "assurances habitation et auto",
            "campaign_context": "Prospection pour optimisation contrats d'assurance",
            "key_benefits": "économies jusqu'à 40%, même couverture, changement gratuit sans frais",
            "target_audience": "particuliers assurés cherchant à réduire leurs cotisations",
            "tone": "rassurant, économique, transparent"
        },
        "objections": {
            "Je suis déjà assuré": "Parfait, c'est justement pour ça que je vous appelle. On compare votre contrat actuel avec nos tarifs pour voir si vous payez trop cher. 2 minutes pour potentiellement économiser 40%, ça vaut le coup non ?",
            "Mon contrat est récent": "Pas de problème, même récent on peut optimiser. Et la loi Hamon vous permet de changer quand vous voulez après 1 an, sans frais. On regarde ensemble ?",
            "Pas le temps de comparer": "Je comprends, c'est chronophage. Justement on s'occupe de tout : comparaison, résiliation ancien contrat, souscription. Vous donnez juste votre numéro de contrat. 5 minutes max.",
            "Trop compliqué de changer": "C'est ce qu'on pense tous, mais depuis la loi Hamon c'est devenu ultra simple. On s'occupe de résilier votre ancien contrat, zéro démarche pour vous. Juste des économies. Tenté ?",
            "Pas intéressé": "Ok, juste une dernière question : vous payez combien par mois actuellement ? ... Vous savez que vous pourriez payer 200€ de moins par an pour la même couverture ? On fait une simulation gratuite ?"
        }
    },
    "saas_b2b": {
        "name": "SaaS B2B",
        "context": {
            "agent_name": "Thomas",
            "company": "notre entreprise",
            "product": "solution SaaS de gestion",
            "campaign_context": "Prospection B2B PME pour optimiser leurs processus",
            "key_benefits": "gain de temps 40%, automatisation complète, ROI sous 6 mois",
            "target_audience": "PME et ETI 10-500 employés, directeurs ops",
            "tone": "tech, orienté ROI, professionnel B2B"
        },
        "objections": {
            "On a déjà une solution": "Super, vous êtes déjà équipés. Est-ce qu'elle répond à 100% de vos besoins ? Beaucoup de nos clients utilisent notre solution en complément pour combler les gaps. Vous avez des points de friction actuels ?",
            "C'est trop cher": "Je comprends la question budget. Nos clients voient un ROI en 6 mois grâce aux gains de productivité. Pour une équipe de 10 personnes, ça représente 2 ETP économisés. Vous voulez voir le calcul ?",
            "Pas le temps de changer": "Excellente remarque. C'est pour ça qu'on a un processus de migration assisté : formation, import de données, support dédié. Déploiement complet en 2 semaines. Et si je vous montre en 15 minutes ?",
            "Pas le budget": "Ok, je comprends les contraintes budget. On a justement une offre Start pour les PME à partir de 99€/mois. Et vu que ça économise 40% du temps admin, ça se rentabilise vite. On regarde ?",
            "Pas le bon moment": "C'est vrai qu'il n'y a jamais de 'bon moment'. Par contre, chaque mois sans optimisation, c'est du temps et de l'argent perdus. Une démo de 15 min pour voir si ça vaut le coup de prioriser ?"
        }
    },
    "or": {
        "name": "Investissement Or (Gold)",
        "context": {
            "agent_name": "Alexandre",
            "company": "GoldInvest France",
            "product": "or physique d'investissement (lingots, pièces)",
            "campaign_context": "Prospection patrimoine pour diversification or physique",
            "key_benefits": "valeur refuge, +110% depuis 2020, protection inflation, liquidité 24-48h",
            "target_audience": "particuliers patrimoine >50k€, 35-70 ans, recherche sécurité",
            "tone": "expert patrimoine, rassurant, anti-crise, long-terme"
        },
        "objections": {
            "C'est trop cher": "Je comprends que 10 000€ en or ça paraît beaucoup. MAIS regardez : l'or a pris +110% depuis 2020. Sur 10k€, c'est +1500€ de gain potentiel. + c'est une ASSURANCE contre l'inflation. Vous avez combien en actifs tangibles actuellement ?",
            "C'est risqué": "Risqué ? L'or existe depuis 5000 ans et n'a JAMAIS valu zéro ! C'est l'actif le MOINS risqué au monde. Le vrai risque c'est de garder 100% en cash qui perd 5% par an avec l'inflation.",
            "Pas assez liquide": "Faux ! On vous rachète votre or sous 24-48h au cours du jour. Vous êtes plus liquide qu'avec un bien immobilier (6 mois) ou une assurance-vie (frais). L'or c'est liquide instantanément.",
            "Frais de stockage": "Nos frais sont de 0,5% par an dans des coffres ultra-sécurisés. Sur 10 000€ c'est 50€/an. Votre banque vous prend 150-300€/an pour un coffre ! Nous c'est 5x moins cher.",
            "Je préfère l'immobilier": "L'immobilier c'est excellent ! L'or c'est un COMPLÉMENT : 5-10% de votre patrimoine en or sécurise le reste. Les pros diversifient : immo 60%, actions 25%, or 10%, cash 5%."
        }
    },
    "vin_investissement": {
        "name": "Investissement Vin (Wine)",
        "context": {
            "agent_name": "Vincent",
            "company": "WineCapital Premium",
            "product": "grands crus classés Bordeaux et Bourgogne en primeur",
            "campaign_context": "Prospection investisseurs pour placement vin de garde",
            "key_benefits": "+8-15%/an historique, fiscalité avantageuse (6.5%), actif tangible décorrélé bourse",
            "target_audience": "investisseurs patrimoine >100k€, 40-70 ans, recherche diversification",
            "tone": "expert vin et finance, luxe accessible, patrimoine alternatif"
        },
        "objections": {
            "C'est trop cher": "Les Grands Crus Classés prennent 8-15% par an. Sur 10 000€ investis, c'est +1500€/an. En 8 ans votre investissement double ! + c'est tangible, pas du papier. Combien avez-vous en épargne à 3% ?",
            "Je ne connais rien au vin": "C'est justement notre métier ! On sélectionne pour vous : Château Margaux, Pétrus, Romanée-Conti. Vous n'avez pas besoin d'être œnologue. 70% de nos clients ne connaissaient rien au vin. On vous guide.",
            "Risque de contrefaçon": "On achète UNIQUEMENT en primeurs au château OU négociants agréés avec certificats. Chaque bouteille a sa traçabilité. + stockage sans sortie = garantie authenticité. Zéro contrefaçon possible.",
            "Frais de stockage": "Nos caves sont à 12°C constant, 70% humidité, assurance tous risques. Coût : 3-5% par an. Sur 10 000€ c'est 400€/an. Un vin mal stocké perd 50% de valeur. Bien stocké il prend +10%/an.",
            "Trop long pour vendre": "Horizon recommandé : 8-10 ans. MAIS vous pouvez revendre avant ! Réseau de collectionneurs et restaurants. Revente sous 2-3 mois via nos partenaires (iDealwine). Liquidité assurée."
        }
    },
    "custom": {
        "name": "Personnalisé (vous configurez tout)",
        "context": {},
        "objections": {}
    }
}

class ScenarioBuilder:
    """Constructeur de scénario interactif - Logique MiniBotPanel (Phase 7: Agent Autonome)"""

    def __init__(self):
        self.scenario = {
            "name": "",
            "description": "",
            "agent_mode": True,  # Phase 7: mode agent autonome par défaut
            "theme": "",  # Phase 7: thématique pour objection matcher
            "voice": "",  # Phase 7: voix clonée à utiliser
            "background_audio": "",  # Phase 7: fichier background audio
            "rail": [],  # Phase 7: navigation rail
            "steps": {},
            "qualification_rules": {}
        }
        self.thematique = None
        self.campaign_objective = None  # Type objectif campagne
        self.agent_personality = None  # Personnalité agent pour Freestyle
        self.freestyle_enabled = True  # Phase 7: activé par défaut pour agent autonome
        self.freestyle_context = {}
        self.objections_responses = {}  # {objection_text: response_text}
        self.variables = ["first_name", "last_name", "company"]
        self.qualifying_steps = []  # Étapes déterminantes
        self.num_questions = 3  # Nombre de questions Q1, Q2, Q3...
        self.barge_in_config = {}  # {step_name: bool}

        # Phase 7: Workflow agent autonome
        self.voice_name = ""  # Nom de la voix (dossier voices/)
        self.telemarketer_name = ""  # Nom du téléprospecteur
        self.company_name = ""  # Société
        self.use_audio_files = {}  # Phase 7: {step: bool} audio pré-enregistré vs TTS

    def run(self):
        """Lance le processus interactif complet"""
        print(f"{Colors.BOLD}")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║       🤖 MiniBotPanel v3 - Scenario Creator Pro                 ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(Colors.END)

        print_info("Création de scénario selon la logique HELLO → RETRY → Q1...Qn → IS_LEADS → CONFIRM → BYE\n")

        # 1. Informations de base
        self._ask_basic_info()

        # 2. Phase 7: Infos agent autonome (voix, téléprospecteur, société)
        self._ask_autonomous_agent_info()

        # 3. Objectif de campagne
        self._ask_campaign_objective()

        # 3. Choix thématique
        self._ask_thematique()

        # 4. Personnalité de l'agent
        self._ask_agent_personality()

        # 5. Variables dynamiques
        self._ask_variables()

        # 6. Mode Freestyle
        self._ask_freestyle_config()

        # 5. Configuration des questions
        self._ask_questions_config()

        # 6. Configuration objections
        self._ask_objections_config()

        # 7. Configuration barge-in
        self._ask_barge_in_config()

        # 8. Génération des étapes
        self._build_all_steps()

        # 9. Configuration qualification
        self._ask_qualification_rules()

        # 10. Nettoyage audios custom avec UVR (optionnel)
        if ask_yes_no("\nNettoyer des audios pré-enregistrés avec UVR ?", default=False):
            self._clean_custom_audios()

        # 11. Génération TTS objections
        if self.objections_responses and ask_yes_no("\nGénérer les audios TTS pour les objections ?", default=True):
            self._generate_objections_tts()

        # 12. Sauvegarde
        self._save_scenario()

    def _ask_basic_info(self):
        """Informations de base"""
        print_header("📋 Informations générales")
        self.scenario["name"] = ask_text("Nom du scénario")
        self.scenario["description"] = ask_text("Description courte", required=False)
        print_success(f"Scénario: {self.scenario['name']}")

    def _ask_autonomous_agent_info(self):
        """Phase 7: Collecte infos agent autonome (voix, téléprospecteur, société)"""
        print_header("🤖 Configuration Agent Autonome (Phase 7)")

        print_info("Le mode agent autonome nécessite:")
        print_info("  • Une voix clonée (dossier dans voices/)")
        print_info("  • Nom du téléprospecteur (personnalité)")
        print_info("  • Nom de la société\n")

        # 1. Choix voix clonée (vérifier embeddings.pth)
        print(f"{Colors.CYAN}Voix clonées disponibles:{Colors.END}")
        voices_dir = Path("voices")
        available_voices = []

        if voices_dir.exists():
            # Vérifier présence de embeddings.pth (voix réellement clonée)
            for d in voices_dir.iterdir():
                if d.is_dir() and not d.name.startswith('.'):
                    embeddings_file = d / "embeddings.pth"
                    if embeddings_file.exists():
                        available_voices.append(d.name)

        if available_voices:
            print_info(f"Détectées: {', '.join(available_voices)}")
            self.voice_name = ask_text("Nom de la voix à utiliser", default=available_voices[0])
        else:
            print_warning("Aucune voix clonée détectée (pas de embeddings.pth)")
            print_info("💡 Utilisez youtube_extract.py puis clone_voice.py pour créer des voix")
            self.voice_name = ask_text("Nom de la voix à utiliser", default="julie")

        self.scenario["voice"] = self.voice_name
        print_success(f"Voix: {self.voice_name}")

        # 2. Nom téléprospecteur
        self.telemarketer_name = ask_text("Nom du téléprospecteur (prénom)", default="Julie")
        print_success(f"Téléprospecteur: {self.telemarketer_name}")

        # 3. Nom société
        self.company_name = ask_text("Nom de la société", default="notre entreprise")
        print_success(f"Société: {self.company_name}")

        # 4. Background audio (optionnel)
        print(f"\n{Colors.CYAN}Background audio (optionnel):{Colors.END}")
        print_info("Fichier audio joué en boucle en fond d'appel (-8dB automatique)")

        backgrounds_dir = Path("audio/background")
        available_backgrounds = []

        if backgrounds_dir.exists():
            available_backgrounds = [f.name for f in backgrounds_dir.glob("*.wav")]

        if available_backgrounds:
            print_info(f"Disponibles: {', '.join(available_backgrounds)}")
            if ask_yes_no("Utiliser un background audio ?", default=False):
                bg_choice = ask_choice("Quel fichier ?", available_backgrounds, default=1)
                self.scenario["background_audio"] = available_backgrounds[bg_choice - 1]
                print_success(f"Background: {self.scenario['background_audio']}")
        else:
            print_warning("Aucun background disponible dans audio/background/")
            if ask_yes_no("Spécifier manuellement ?", default=False):
                self.scenario["background_audio"] = ask_text("Nom fichier background (ex: office.wav)")

    def _ask_campaign_objective(self):
        """Choix de l'objectif de campagne"""
        print_header("🎯 Objectif de campagne")

        print_info("L'objectif définit le but final de votre campagne:")
        print_info("  • Prise de RDV : Qualifier et fixer un rendez-vous avec un expert")
        print_info("  • Génération de lead : Collecter intérêt et coordonnées pour callback")
        print_info("  • Transfert d'appel : Transférer directement sur un conseiller disponible\n")

        objectives = [
            "Prise de RDV (rendez-vous avec expert/commercial)",
            "Génération de lead (être rappelé par conseiller)",
            "Transfert d'appel (transfert immédiat si intéressé)"
        ]

        choice = ask_choice("Quel est l'objectif principal ?", objectives, default=1)

        objective_keys = ["appointment", "lead_generation", "call_transfer"]
        self.campaign_objective = objective_keys[choice - 1]

        objective_names = {
            "appointment": "Prise de RDV",
            "lead_generation": "Génération de lead",
            "call_transfer": "Transfert d'appel"
        }

        self.scenario["campaign_objective"] = self.campaign_objective
        print_success(f"Objectif: {objective_names[self.campaign_objective]}")

        # Info pour contexte Freestyle
        if self.campaign_objective == "appointment":
            print_info("\n💡 Le système privilégiera les arguments pour obtenir un RDV")
        elif self.campaign_objective == "lead_generation":
            print_info("\n💡 Le système se concentrera sur la collecte d'intérêt et callback")
        else:
            print_info("\n💡 Le système préparera un transfert vers un conseiller disponible")

    def _ask_thematique(self):
        """Choix thématique"""
        print_header("🎯 Thématique métier")
        choices = [info["name"] for info in THEMATIQUES.values()]
        choice = ask_choice("Choisissez votre thématique:", choices, default=1)

        thematique_key = list(THEMATIQUES.keys())[choice - 1]
        self.thematique = THEMATIQUES[thematique_key]

        # Phase 7: Configurer theme pour objection matcher
        if thematique_key != "custom":
            self.scenario["theme"] = thematique_key  # finance, crypto, energie, etc.
            print_success(f"Thématique: {self.thematique['name']}")
            print_info(f"Theme code: {thematique_key} (pour objection matcher)")
        else:
            self.scenario["theme"] = "general"  # custom = general
            print_info("Theme: general (aucune thématique spécifique)")

    def _ask_agent_personality(self):
        """Choix de la personnalité de l'agent"""
        print_header("🎭 Personnalité de l'agent")

        print_info("Choisissez la personnalité qui guidera les réponses Freestyle AI:")
        print_info("(Cela influence le ton, le style et l'approche commerciale)\n")

        # Afficher exemples de personnalités
        for key, personality in AGENT_PERSONALITIES.items():
            print(f"{Colors.CYAN}• {personality['name']}{Colors.END}: {personality['description']}")
            print(f"  {Colors.YELLOW}Exemple :{Colors.END} \"{personality['example']}\"\n")

        choices = [info["name"] for info in AGENT_PERSONALITIES.values()]
        choice = ask_choice("Quelle personnalité pour votre agent ?", choices, default=1)

        personality_key = list(AGENT_PERSONALITIES.keys())[choice - 1]
        self.agent_personality = AGENT_PERSONALITIES[personality_key]

        print_success(f"Personnalité: {self.agent_personality['name']}")
        print_info(f"Ton: {self.agent_personality['tone']}")

    def _ask_variables(self):
        """Variables dynamiques"""
        print_header("🔤 Variables dynamiques")
        print_info("Variables par défaut: {{first_name}}, {{last_name}}, {{company}}\n")

        if ask_yes_no("Ajouter des variables personnalisées ?", default=False):
            while True:
                var_name = ask_text("Nom variable (vide pour terminer)", required=False)
                if not var_name:
                    break
                var_name = re.sub(r'[^a-z0-9_]', '_', var_name.lower())
                if var_name not in self.variables:
                    self.variables.append(var_name)
                    print_success(f"Variable ajoutée: {{{{" + var_name + "}}}}")

    def _ask_freestyle_config(self):
        """Configuration Freestyle"""
        print_header("✨ Mode Freestyle AI")
        print_info("Le Freestyle répond dynamiquement aux questions hors-script\n")

        self.freestyle_enabled = ask_yes_no("Activer Freestyle AI ?", default=True)

        if not self.freestyle_enabled:
            return

        # Context depuis thématique ou custom
        if self.thematique.get("context"):
            self.freestyle_context = self.thematique["context"].copy()
            print_info(f"Contexte thématique chargé ({self.thematique['name']})\n")
            if ask_yes_no("Personnaliser le contexte ?", default=False):
                for key in ["agent_name", "company", "product"]:
                    if key in self.freestyle_context:
                        self.freestyle_context[key] = ask_text(
                            key.replace('_', ' ').title(),
                            default=self.freestyle_context[key]
                        )
        else:
            self.freestyle_context = {
                "agent_name": ask_text("Nom agent", default="Julie"),
                "company": ask_text("Nom entreprise"),
                "product": ask_text("Produit/service"),
                "campaign_context": ask_text("Description campagne"),
                "key_benefits": ask_text("Bénéfices clés"),
            }

        price_info = ask_text("Indication prix (optionnel)", required=False)
        if price_info:
            self.freestyle_context["price_range"] = price_info

        # Ajouter l'objectif de campagne au contexte
        if self.campaign_objective:
            objective_context = {
                "appointment": "L'objectif est d'obtenir un rendez-vous avec un expert",
                "lead_generation": "L'objectif est de qualifier le lead pour un callback par un conseiller",
                "call_transfer": "L'objectif est de transférer le prospect vers un conseiller disponible"
            }
            self.freestyle_context["campaign_objective"] = objective_context[self.campaign_objective]

        # Ajouter la personnalité au contexte
        if self.agent_personality:
            self.freestyle_context["agent_tone"] = self.agent_personality["tone"]
            self.freestyle_context["agent_style"] = self.agent_personality["style"]
            print_info(f"\n💡 Personnalité intégrée: {self.agent_personality['name']}")

        self.freestyle_context["max_turns"] = ask_int("Max échanges freestyle par appel", default=3, min_val=1, max_val=10)
        print_success("Freestyle configuré")

    def _ask_questions_config(self):
        """Configuration questions Q1, Q2, Q3..."""
        print_header("❓ Questions qualifiantes")
        print_info("Logique: Q1 → Q2 → Q3 → ... → IS_LEADS\n")

        self.num_questions = ask_int("Nombre de questions (Q1, Q2, Q3...)", default=3, min_val=1, max_val=10)

        print_info(f"\n{self.num_questions} questions seront créées (Q1 à Q{self.num_questions})\n")

        # Demander quelles questions sont déterminantes
        print_info("Quelles questions sont déterminantes pour qualifier un lead ?")
        print_info("(Les questions non-déterminantes sont informatives seulement)\n")

        for i in range(1, self.num_questions + 1):
            is_qualifying = ask_yes_no(f"  Q{i} est déterminante ?", default=(i == self.num_questions))
            if is_qualifying:
                self.qualifying_steps.append(f"question{i}")

        print_success(f"Questions déterminantes: {', '.join(self.qualifying_steps) if self.qualifying_steps else 'Aucune'}")

    def _ask_objections_config(self):
        """Configuration objections pré-enregistrées"""
        print_header("🛡️ Objections pré-enregistrées + Fallback Freestyle")

        print_info("Système hybride intelligent:")
        print_info("  1. Objection détectée → Cherche audio pré-enregistré")
        print_info("  2. Si trouvé → Play immédiat (barge-in ultra-rapide)")
        print_info("  3. Sinon → Fallback Freestyle AI (génération dynamique)\n")

        if not self.thematique.get("objections"):
            print_warning("Pas d'objections pré-configurées pour cette thématique")
            return

        objections = self.thematique["objections"]
        print(f"Objections disponibles ({self.thematique['name']}):")
        for i, (obj, resp) in enumerate(objections.items(), 1):
            print(f"  {i}. {obj}")
            print(f"     → {resp[:60]}...")
        print()

        if ask_yes_no("Utiliser ces objections pré-enregistrées ?", default=True):
            self.objections_responses = objections.copy()
            print_success(f"{len(self.objections_responses)} objections chargées")

            if ask_yes_no("Ajouter des objections personnalisées ?", default=False):
                while True:
                    obj = ask_text("Objection (vide pour terminer)", required=False)
                    if not obj:
                        break
                    resp = ask_text(f"Réponse à '{obj}'")
                    self.objections_responses[obj] = resp
                    print_success("Objection ajoutée")

    def _ask_barge_in_config(self):
        """Configuration barge-in par étape"""
        print_header("🔊 Configuration Barge-In")

        print_info("Le barge-in permet au client d'interrompre le robot\n")

        mode = ask_choice(
            "Configuration barge-in:",
            [
                "Activé partout (recommandé)",
                "Désactivé partout",
                "Personnalisé par étape"
            ],
            default=1
        )

        if mode == 1:
            # Tout activé
            self.barge_in_default = True
            print_success("Barge-in activé sur toutes les étapes")
        elif mode == 2:
            # Tout désactivé
            self.barge_in_default = False
            print_warning("Barge-in désactivé (peut frustrer les clients)")
        else:
            # Custom
            self.barge_in_default = True
            print_info("Barge-in activé par défaut, vous pourrez personnaliser par étape")

    def _build_all_steps(self):
        """Génère toutes les étapes selon la logique MiniBotPanel (Phase 7: Agent Autonome)"""
        print_header("🔨 Génération des étapes (Rail Agent Autonome)")

        voice = self.voice_name  # Phase 7: utilise voice_name configuré
        agent_name = self.telemarketer_name  # Phase 7
        company = self.company_name  # Phase 7

        # Phase 7: Construire le rail
        rail = ["Hello"]
        for i in range(1, self.num_questions + 1):
            rail.append(f"Q{i}")
        rail.extend(["Is_Leads", "Confirm_Time", "Bye"])

        self.scenario["rail"] = rail
        print_info(f"Rail configuré: {' → '.join(rail)}\n")

        # Étape HELLO
        print_info("Création étape HELLO...")
        agent_name = self.freestyle_context.get("agent_name", "Julie")
        company = self.freestyle_context.get("company", "notre entreprise")

        hello_msg = ask_text(
            "Message HELLO",
            default=f"Allô, bonjour {{{{first_name}}}}. Je suis {agent_name} de {company}."
        )

        self.scenario["steps"]["hello"] = {
            "message_text": hello_msg,
            "audio_type": "tts_cloned",
            "voice": voice,
            "barge_in": self.barge_in_default,
            "timeout": 15,
            "intent_mapping": {
                "affirm": "question1",
                "interested": "question1",
                "question": "freestyle_answer" if self.freestyle_enabled else "retry",
                "deny": "retry",
                "not_interested": "retry",
                "unsure": "retry",
                "callback": "retry",
                "silence": "retry",
                "*": "retry"
            }
        }

        # Étape RETRY
        print_info("Création étape RETRY...")
        retry_msg = ask_text(
            "Message RETRY",
            default="Je comprends. C'est vraiment très rapide, juste 2 minutes. Puis-je vous poser quelques questions ?"
        )

        self.scenario["steps"]["retry"] = {
            "message_text": retry_msg,
            "audio_type": "tts_cloned",
            "voice": voice,
            "barge_in": self.barge_in_default,
            "timeout": 15,
            "intent_mapping": {
                "affirm": "question1",
                "interested": "question1",
                "question": "freestyle_answer" if self.freestyle_enabled else "bye_failed",
                "deny": "bye_failed",
                "not_interested": "bye_failed",
                "unsure": "bye_failed",
                "silence": "bye_failed",
                "*": "bye_failed"
            }
        }

        # Étapes Q1, Q2, Q3... (Phase 7: avec max_autonomous_turns et is_determinant)
        for i in range(1, self.num_questions + 1):
            print_info(f"Création Q{i}...")
            q_msg = ask_text(f"Question Q{i}")
            next_step = f"Q{i+1}" if i < self.num_questions else "Is_Leads"  # Phase 7: rail naming
            is_determinant = f"question{i}" in self.qualifying_steps

            self.scenario["steps"][f"Q{i}"] = {  # Phase 7: naming convention Q1, Q2, Q3
                "message_text": q_msg,
                "audio_type": "tts_cloned",  # Par défaut TTS, peut être changé
                "voice": voice,
                "barge_in": self.barge_in_default,
                "timeout": 12,
                "max_autonomous_turns": 2,  # Phase 7: configurable
                "is_determinant": is_determinant,  # Phase 7: pour qualification
                "qualification_weight": 30 if is_determinant else 10,  # Phase 7: poids cumulatif
                "intent_mapping": {
                    "question": "freestyle_answer" if self.freestyle_enabled else next_step,
                    "*": next_step,
                    "silence": next_step
                }
            }

        # Étape IS_LEADS (question qualifiante finale - Phase 7)
        print_info("Création IS_LEADS...")
        product = self.freestyle_context.get("product", "notre solution")
        is_leads_msg = ask_text(
            "Question IS_LEADS (déterminante)",
            default=f"Seriez-vous intéressé par {product} ?"
        )

        self.scenario["steps"]["Is_Leads"] = {  # Phase 7: naming convention
            "message_text": is_leads_msg,
            "audio_type": "tts_cloned",
            "voice": voice,
            "barge_in": self.barge_in_default,
            "timeout": 15,
            "max_autonomous_turns": 2,  # Phase 7
            "is_determinant": True,  # Phase 7: toujours déterminant
            "qualification_weight": 40,  # Phase 7: poids élevé (40% du score)
            "intent_mapping": {
                "affirm": "Confirm_Time",  # Phase 7: vers Confirm_Time
                "interested": "Confirm_Time",
                "question": "freestyle_answer" if self.freestyle_enabled else "Bye",
                "deny": "Bye",
                "not_interested": "Bye",
                "unsure": "Bye",
                "silence": "Bye",
                "*": "Bye"
            }
        }

        # Étape CONFIRM_TIME (Phase 7: confirmation RDV/callback)
        print_info("Création CONFIRM_TIME...")
        confirm_msg = ask_text(
            "Message CONFIRM_TIME (confirmation)",
            default="Parfait ! Un conseiller va vous rappeler pour fixer un rendez-vous. Merci {{first_name}} !"
        )

        self.scenario["steps"]["Confirm_Time"] = {  # Phase 7: naming
            "message_text": confirm_msg,
            "audio_type": "tts_cloned",
            "voice": voice,
            "barge_in": False,
            "timeout": 10,
            "max_autonomous_turns": 1,  # Phase 7
            "is_determinant": False,  # Phase 7: pas déterminant (déjà qualifié)
            "intent_mapping": {
                "*": "Bye",  # Phase 7: toujours vers Bye
                "silence": "Bye"
            }
        }

        # Étape FREESTYLE_ANSWER (si activé)
        if self.freestyle_enabled:
            print_info("Création FREESTYLE_ANSWER...")
            self.scenario["steps"]["freestyle_answer"] = {
                "audio_type": "freestyle",
                "voice": voice,
                "barge_in": True,
                "timeout": 10,
                "max_turns": self.freestyle_context.get("max_turns", 3),
                "context": self.freestyle_context,
                "intent_mapping": {
                    "affirm": "question1",
                    "interested": "question1",
                    "question": "freestyle_answer",
                    "deny": "retry",
                    "*": "question1"
                }
            }

        # Étape BYE (Phase 7: étape unique de fin)
        print_info("Création étape BYE...")
        bye_msg = ask_text(
            "Message BYE (fin d'appel)",
            default="Merci {{first_name}} et excellente journée !"
        )

        self.scenario["steps"]["Bye"] = {  # Phase 7: naming convention
            "message_text": bye_msg,
            "audio_type": "tts_cloned",
            "voice": voice,
            "barge_in": False,
            "timeout": 5,
            "result": "completed",  # Phase 7: qualification déterminée par scoring
            "intent_mapping": {"*": "end"}
        }

        total_steps = len(self.scenario["steps"])
        print_success(f"{total_steps} étapes créées avec succès")

    def _ask_qualification_rules(self):
        """Configuration qualification cumulative (Phase 7: scoring 70%)"""
        print_header("🎯 Règles de qualification (Phase 7: Cumulative Scoring)")

        print_info("Phase 7 utilise un système de scoring cumulatif:")
        print_info("  • Chaque étape déterminante a un poids (weight)")
        print_info("  • Score cumulatif calculé sur 100%")
        print_info("  • Seuil LEAD: 70% minimum\n")

        # Phase 7: Toujours mode scoring cumulatif
        print_info("Étapes déterminantes détectées:")
        total_weight = 0
        scoring_detail = {}

        for i in range(1, self.num_questions + 1):
            step_name = f"Q{i}"
            if f"question{i}" in self.qualifying_steps:
                weight = self.scenario["steps"][step_name]["qualification_weight"]
                total_weight += weight
                scoring_detail[step_name] = weight
                print(f"  • {step_name}: {weight}% (déterminante)")

        # Is_Leads toujours déterminante
        is_leads_weight = self.scenario["steps"]["Is_Leads"]["qualification_weight"]
        total_weight += is_leads_weight
        scoring_detail["Is_Leads"] = is_leads_weight
        print(f"  • Is_Leads: {is_leads_weight}% (toujours déterminante)")

        print(f"\n📊 Total poids: {total_weight}%")

        if total_weight != 100:
            print_warning(f"Attention: Le total devrait être 100% (actuellement {total_weight}%)")
            print_info("Ajustement automatique des poids...")

            # Normaliser les poids pour atteindre 100%
            factor = 100.0 / total_weight
            for step, weight in scoring_detail.items():
                scoring_detail[step] = round(weight * factor, 1)
                self.scenario["steps"][step]["qualification_weight"] = scoring_detail[step]

            print_success(f"Poids ajustés: {scoring_detail}")

        # Phase 7: Seuil 70% par défaut (configurable)
        threshold = ask_int("Seuil de qualification (%)", default=70, min_val=50, max_val=100)

        self.scenario["qualification_rules"] = {
            "lead_threshold": threshold,
            "scoring_weights": scoring_detail
        }

        print_success(f"Qualification: Seuil {threshold}% (scoring cumulatif)")
        print_info("Le système calculera automatiquement le score final")

    def _clean_custom_audios(self):
        """Nettoie les audios pré-enregistrés avec UVR (enlève musique/bruits)"""
        print_header("🎵 Nettoyage audios pré-enregistrés (UVR)")

        print_info("Cette fonction nettoie vos audios personnalisés (enlève musique, bruits de fond)")
        print_info("Utile pour préparer des messages pré-enregistrés de qualité\n")

        audio_custom_dir = Path("audio/custom")
        if not audio_custom_dir.exists():
            print_warning(f"Dossier {audio_custom_dir} inexistant")
            audio_custom_dir.mkdir(parents=True, exist_ok=True)
            print_info(f"Créé: {audio_custom_dir}/")
            return

        # Trouver fichiers WAV non-nettoyés
        audio_files = [f for f in audio_custom_dir.glob("*.wav") if "_clean" not in f.stem]

        if not audio_files:
            print_warning("Aucun fichier .wav à nettoyer dans audio/custom/")
            return

        print(f"📂 {len(audio_files)} fichier(s) trouvé(s):")
        for f in audio_files:
            print(f"   • {f.name}")
        print()

        if not ask_yes_no("Nettoyer ces fichiers avec UVR ?", default=False):
            return

        try:
            from audio_separator.separator import Separator

            print_info("🔧 Chargement modèle UVR...")
            separator = Separator(
                log_level=40,  # ERROR only
                model_file_dir=str(Path.home() / ".cache" / "audio-separator")
            )
            separator.load_model("UVR-MDX-NET-Voc_FT")
            print_success("Modèle chargé\n")

            for i, audio_file in enumerate(audio_files, 1):
                print(f"[{i}/{len(audio_files)}] 🎵 {audio_file.name}")

                # Séparer vocals
                output_files = separator.separate(str(audio_file))

                # Trouver fichier vocals
                vocals_file = None
                for f in output_files:
                    if "Vocals" in f or "vocals" in f:
                        vocals_file = Path(f)
                        break

                if vocals_file and vocals_file.exists():
                    # Renommer avec _clean
                    output_name = audio_file.stem + "_clean" + audio_file.suffix
                    output_path = audio_custom_dir / output_name
                    vocals_file.rename(output_path)

                    # Nettoyer instrumental
                    for f in output_files:
                        f_path = Path(f)
                        if f_path.exists() and f_path != output_path:
                            f_path.unlink()

                    print_success(f"   → {output_name} ({output_path.stat().st_size / 1024:.1f} KB)")
                else:
                    print_error("   → Échec extraction vocals")

                print()

            print_success(f"✅ {len(audio_files)} fichier(s) nettoyé(s)")

        except ImportError:
            print_error("audio-separator non disponible")
            print_info("Installation: pip install audio-separator==0.12.0")
        except Exception as e:
            print_error(f"Erreur UVR: {e}")

    def _generate_objections_tts(self):
        """Génère TTS pour objections"""
        print_header("🎙️ Génération TTS objections")

        try:
            from system.services.chatterbox_tts import ChatterboxTTSService
            tts = ChatterboxTTSService()

            if not tts.is_available:
                print_error("Service TTS non disponible")
                return

            audio_dir = Path("audio/objections")
            audio_dir.mkdir(parents=True, exist_ok=True)

            for i, (obj, resp) in enumerate(self.objections_responses.items(), 1):
                print(f"[{i}/{len(self.objections_responses)}] {obj[:40]}...")

                filename = re.sub(r'[^a-z0-9]', '_', obj.lower())[:40] + ".wav"
                output_path = audio_dir / filename

                result = tts.synthesize(resp, str(output_path))

                if result:
                    print_success(f"  → {filename}")
                else:
                    print_error(f"  → Échec")

            print_success(f"\n{len(self.objections_responses)} fichiers générés dans {audio_dir}/")

        except Exception as e:
            print_error(f"Erreur TTS: {e}")

    def _save_scenario(self):
        """Sauvegarde finale"""
        print_header("💾 Sauvegarde")

        print(f"{Colors.BOLD}Récapitulatif:{Colors.END}")
        print(f"  • Nom: {self.scenario['name']}")
        print(f"  • Thématique: {self.thematique['name']}")
        print(f"  • Étapes: {len(self.scenario['steps'])}")
        print(f"  • Questions: {self.num_questions}")
        print(f"  • Questions déterminantes: {len(self.qualifying_steps)}")
        print(f"  • Freestyle: {'✓' if self.freestyle_enabled else '✗'}")
        print(f"  • Objections pré-enregistrées: {len(self.objections_responses)}\n")

        if not ask_yes_no("Sauvegarder ?", default=True):
            print_warning("Non sauvegardé")
            return

        filename = re.sub(r'[^a-z0-9_]', '_', self.scenario['name'].lower())
        scenarios_dir = Path("scenarios")
        scenarios_dir.mkdir(parents=True, exist_ok=True)

        filepath = scenarios_dir / f"scenario_{filename}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.scenario, f, indent=2, ensure_ascii=False)

        print_success(f"Scénario sauvegardé: {filepath}")

        # Preview
        if ask_yes_no("\nPrévisualiser le JSON ?", default=False):
            with open(filepath, 'r', encoding='utf-8') as f:
                print(f"\n{Colors.CYAN}{'─' * 70}")
                print(f.read())
                print(f"{'─' * 70}{Colors.END}\n")

        print(f"\n{Colors.GREEN}✅ Terminé ! Votre scénario est prêt.{Colors.END}\n")

def main():
    """Point d'entrée"""
    try:
        builder = ScenarioBuilder()
        builder.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Annulé{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
