#!/usr/bin/env python3
"""
Launch Campaign - MiniBotPanel v3

Lance une campagne d'appels.

Usage:
    python launch_campaign.py --campaign-id 42
    python launch_campaign.py --name "Vente Produit X" --contacts contacts.csv --scenario production
"""

import argparse
import logging
import sys
import csv
import json
from pathlib import Path
from typing import List, Dict, Optional

from system.database import SessionLocal
from system.models import Campaign, Contact, CampaignStatus
from system.campaign_manager import CampaignManager
from system.batch_caller import start_batch_caller

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Couleurs pour terminal
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def list_available_scenarios() -> List[Dict]:
    """
    Liste tous les scénarios disponibles dans le dossier scenarios/.

    Returns:
        List de dicts avec {filename, name, description, thematique, objective}
    """
    scenarios_dir = Path("scenarios")

    if not scenarios_dir.exists():
        logger.warning(f"{Colors.YELLOW}⚠️  Dossier scenarios/ introuvable{Colors.END}")
        return []

    scenarios = []

    # Parcourir tous les fichiers scenario_*.json
    for scenario_file in scenarios_dir.glob("scenario_*.json"):
        try:
            with open(scenario_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                scenarios.append({
                    "filename": scenario_file.stem,  # sans .json
                    "filepath": str(scenario_file),
                    "name": data.get("name", scenario_file.stem),
                    "description": data.get("description", "Pas de description"),
                    "campaign_objective": data.get("campaign_objective", "N/A"),
                    "num_steps": len(data.get("steps", {}))
                })
        except Exception as e:
            logger.warning(f"⚠️  Erreur lecture {scenario_file.name}: {e}")
            continue

    # Trier par nom
    scenarios.sort(key=lambda s: s["name"])

    return scenarios

def display_scenarios_menu(scenarios: List[Dict]) -> Optional[str]:
    """
    Affiche un menu interactif pour choisir un scénario.

    Returns:
        Nom du fichier scénario choisi (sans .json), ou None si annulé
    """
    if not scenarios:
        print(f"{Colors.RED}❌ Aucun scénario disponible{Colors.END}")
        print(f"{Colors.YELLOW}💡 Créez-en un avec: python3 create_scenario.py{Colors.END}")
        return None

    print(f"\n{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗")
    print(f"║  📋 Scénarios disponibles ({len(scenarios)} trouvés)              ║")
    print(f"╚════════════════════════════════════════════════════════════════╝{Colors.END}\n")

    for i, scenario in enumerate(scenarios, 1):
        print(f"{Colors.CYAN}{i}.{Colors.END} {Colors.BOLD}{scenario['name']}{Colors.END}")
        if scenario['description'] and scenario['description'] != "Pas de description":
            print(f"   {scenario['description']}")

        objective_emoji = {
            "appointment": "📅",
            "lead_generation": "📞",
            "call_transfer": "☎️"
        }
        obj_emoji = objective_emoji.get(scenario['campaign_objective'], "🎯")

        print(f"   {obj_emoji} Objectif: {scenario['campaign_objective']} | {scenario['num_steps']} étapes")
        print()

    while True:
        try:
            choice = input(f"{Colors.BOLD}Choisissez un scénario [1-{len(scenarios)}] (ou 'q' pour annuler): {Colors.END}").strip()

            if choice.lower() == 'q':
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(scenarios):
                selected = scenarios[idx]
                print(f"{Colors.GREEN}✅ Scénario sélectionné: {selected['name']}{Colors.END}\n")
                return selected['filename']
            else:
                print(f"{Colors.RED}❌ Choix invalide. Entrez un nombre entre 1 et {len(scenarios)}{Colors.END}")
        except ValueError:
            print(f"{Colors.RED}❌ Entrée invalide. Entrez un nombre ou 'q'{Colors.END}")
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠️  Annulé{Colors.END}")
            return None

def load_contacts_from_csv(csv_file: str) -> list:
    """
    Charge les contacts depuis un fichier CSV.

    Expected CSV format: phone,first_name,last_name,company,email
    """
    contacts = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Créer contact
                contact = Contact(
                    phone=row.get('phone'),
                    first_name=row.get('first_name', ''),
                    last_name=row.get('last_name', ''),
                    company=row.get('company', ''),
                    email=row.get('email', '')
                )
                contacts.append(contact)

        logger.info(f"✅ Loaded {len(contacts)} contacts from {csv_file}")
        return contacts

    except FileNotFoundError:
        logger.error(f"❌ File not found: {csv_file}")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading contacts: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Lancer une campagne d'appels")
    parser.add_argument("--campaign-id", type=int, help="ID campagne existante")
    parser.add_argument("--name", help="Nom nouvelle campagne")
    parser.add_argument("--contacts", help="Fichier contacts CSV")
    parser.add_argument("--scenario", help="Scénario à utiliser (nom fichier sans .json)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Mode interactif pour choisir scénario")

    args = parser.parse_args()

    # Mode interactif si aucun argument fourni
    if len(sys.argv) == 1:
        args.interactive = True

    # Validation
    if not args.campaign_id and not args.name and not args.interactive:
        logger.error("❌ Must provide either --campaign-id, --name, or use --interactive mode")
        parser.print_help()
        sys.exit(1)

    if args.name and not args.contacts:
        logger.error("❌ Must provide --contacts when creating new campaign with --name")
        parser.print_help()
        sys.exit(1)

    # Choix interactif du scénario si mode interactif ou pas de scénario spécifié
    scenario_name = args.scenario
    if args.interactive or (args.name and not args.scenario):
        scenarios = list_available_scenarios()
        scenario_name = display_scenarios_menu(scenarios)

        if not scenario_name:
            logger.info("❌ Opération annulée")
            sys.exit(0)
    elif not scenario_name:
        # Fallback sur "production" si vraiment rien spécifié
        scenario_name = "production"
        logger.warning(f"{Colors.YELLOW}⚠️  Aucun scénario spécifié, utilisation par défaut: {scenario_name}{Colors.END}")

    logger.info("🚀 Launching campaign...")

    db = SessionLocal()
    campaign_id = args.campaign_id

    try:
        # Créer nouvelle campagne si --name fourni
        if args.name:
            logger.info(f"Creating new campaign: {args.name}")

            # Charger contacts depuis CSV
            contacts = load_contacts_from_csv(args.contacts)
            if not contacts:
                logger.error("❌ No contacts loaded, aborting")
                sys.exit(1)

            # Sauvegarder contacts en DB
            db.add_all(contacts)
            db.commit()

            # Récupérer IDs
            contact_ids = [c.id for c in contacts]

            # Créer campagne via CampaignManager
            manager = CampaignManager()
            campaign_id = manager.create_campaign(
                name=args.name,
                contact_ids=contact_ids,
                scenario=scenario_name
            )

            logger.info(f"✅ Campaign created with ID: {campaign_id}")

        # Vérifier que campagne existe
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            logger.error(f"❌ Campaign {campaign_id} not found")
            sys.exit(1)

        logger.info(f"📊 Campaign: {campaign.name} (ID: {campaign.id})")
        logger.info(f"   Scenario: {campaign.scenario}")
        logger.info(f"   Status: {campaign.status}")

        # Mettre à jour statut à RUNNING
        if campaign.status == CampaignStatus.PENDING:
            campaign.status = CampaignStatus.RUNNING
            db.commit()
            logger.info("✅ Campaign status updated to RUNNING")

        # Démarrer batch caller
        logger.info("🚀 Starting batch caller...")
        start_batch_caller()

        logger.info("✅ Campaign launched successfully!")
        logger.info("   Monitor progress with: python monitor_campaign.py --campaign-id {campaign_id}")

    except Exception as e:
        logger.error(f"❌ Error launching campaign: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)

    finally:
        db.close()

if __name__ == "__main__":
    main()
