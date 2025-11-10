#!/usr/bin/env python3
"""
Setup Database - MiniBotPanel v3

Initialise la base de données PostgreSQL.

Fonctionnalités:
- Création tables (Contact, Campaign, Call, CallEvent)
- Test connexion
- Migration schema si nécessaire
- Données de test optionnelles
- Configuration permissions FreeSWITCH recordings (optionnel)

Utilisation:
    python setup_database.py
    python setup_database.py --test-data
    python setup_database.py --reset (⚠️ supprime toutes les données)
    python setup_database.py --setup-permissions (configure FreeSWITCH recordings)
"""

import argparse
import logging
import os
import subprocess
from pathlib import Path
from sqlalchemy import text

from system.database import engine, SessionLocal, init_database, test_connection
from system.models import Base, Contact, Campaign
from system.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_tables():
    """Crée toutes les tables dans la base de données."""
    logger.info("📊 Création des tables...")

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables créées avec succès")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur création tables: {e}")
        return False


def drop_tables():
    """Supprime toutes les tables (⚠️ DESTRUCTIF)."""
    logger.warning("⚠️ SUPPRESSION DE TOUTES LES TABLES...")

    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ Tables supprimées")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur suppression tables: {e}")
        return False


def create_test_data():
    """Crée des données de test."""
    logger.info("🧪 Création de données de test...")

    db = SessionLocal()
    try:
        # Contacts de test
        test_contacts = [
            Contact(
                phone="+33612345678",
                first_name="Jean",
                last_name="Dupont",
                email="jean.dupont@example.com",
                company="Entreprise A"
            ),
            Contact(
                phone="+33687654321",
                first_name="Marie",
                last_name="Martin",
                email="marie.martin@example.com",
                company="Entreprise B"
            ),
            Contact(
                phone="+33698765432",
                first_name="Pierre",
                last_name="Bernard",
                email="pierre.bernard@example.com",
                company="Entreprise C"
            )
        ]

        for contact in test_contacts:
            db.add(contact)

        db.commit()

        logger.info(f"✅ {len(test_contacts)} contacts de test créés")

        # Campagne de test
        test_campaign = Campaign(
            name="Campagne de Test",
            description="Campagne créée automatiquement pour les tests",
            scenario="production"
        )
        db.add(test_campaign)
        db.commit()

        logger.info("✅ 1 campagne de test créée")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur création données test: {e}")
    finally:
        db.close()


def show_stats():
    """Affiche les statistiques de la base de données."""
    db = SessionLocal()
    try:
        contact_count = db.query(Contact).count()
        campaign_count = db.query(Campaign).count()

        logger.info("\n📊 STATISTIQUES BASE DE DONNÉES")
        logger.info("=" * 40)
        logger.info(f"Contacts: {contact_count}")
        logger.info(f"Campagnes: {campaign_count}")
        logger.info("=" * 40)

    except Exception as e:
        logger.error(f"❌ Erreur récupération stats: {e}")
    finally:
        db.close()


def setup_freeswitch_permissions():
    """
    Configure les permissions pour le répertoire recordings FreeSWITCH.

    Actions:
    1. Crée /usr/local/freeswitch/recordings
    2. Configure ownership: freeswitch:daemon
    3. Permissions 775 (rwxrwxr-x)
    4. Ajoute user courant au groupe daemon
    5. Vérifie accès Python

    Requis: sudo
    """
    logger.info("\n🔧 CONFIGURATION PERMISSIONS FREESWITCH RECORDINGS")
    logger.info("=" * 60)

    # Vérifier si on tourne en root/sudo
    if os.geteuid() != 0:
        logger.error("❌ Cette configuration nécessite les droits sudo")
        logger.info("💡 Relancez avec: sudo python3 setup_database.py --setup-permissions")
        return False

    recordings_dir = Path("/usr/local/freeswitch/recordings")
    fs_user = "freeswitch"
    fs_group = "daemon"
    current_user = os.environ.get("SUDO_USER", os.environ.get("USER"))

    logger.info(f"Configuration:")
    logger.info(f"  Répertoire : {recordings_dir}")
    logger.info(f"  Propriétaire: {fs_user}:{fs_group}")
    logger.info(f"  Utilisateur : {current_user}")
    logger.info("")

    try:
        # 1. Créer le répertoire
        logger.info("[1/5] Création du répertoire recordings...")
        if recordings_dir.exists():
            logger.info("  ⚠️  Répertoire existe déjà")
        else:
            recordings_dir.mkdir(parents=True, exist_ok=True)
            logger.info("  ✅ Répertoire créé")

        # 2. Configurer propriétaire
        logger.info("[2/5] Configuration du propriétaire...")
        subprocess.run(
            ["chown", f"{fs_user}:{fs_group}", str(recordings_dir)],
            check=True,
            capture_output=True
        )
        logger.info(f"  ✅ Propriétaire: {fs_user}:{fs_group}")

        # 3. Configurer permissions
        logger.info("[3/5] Configuration des permissions...")
        subprocess.run(
            ["chmod", "775", str(recordings_dir)],
            check=True,
            capture_output=True
        )
        logger.info("  ✅ Permissions: 775 (rwxrwxr-x)")

        # 4. Ajouter user au groupe daemon
        logger.info("[4/5] Ajout de l'utilisateur au groupe daemon...")

        # Vérifier si déjà membre
        result = subprocess.run(
            ["groups", current_user],
            capture_output=True,
            text=True
        )
        if "daemon" in result.stdout:
            logger.info(f"  ⚠️  {current_user} déjà membre du groupe daemon")
        else:
            subprocess.run(
                ["usermod", "-a", "-G", "daemon", current_user],
                check=True,
                capture_output=True
            )
            logger.info(f"  ✅ {current_user} ajouté au groupe daemon")
            logger.warning("  ⚠️  IMPORTANT: Vous devez vous reconnecter pour que les permissions prennent effet")
            logger.warning(f"  💡 Exécutez: su - {current_user}")

        # 5. Fix permissions répertoire parent
        logger.info("[5/5] Configuration répertoire parent...")
        parent_dir = recordings_dir.parent
        subprocess.run(
            ["chmod", "o+rx", str(parent_dir)],
            check=True,
            capture_output=True
        )
        logger.info(f"  ✅ {parent_dir} accessible")

        # Vérification finale
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Configuration permissions terminée avec succès!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Vérification:")
        subprocess.run(["ls", "-la", str(recordings_dir)])
        logger.info("")

        # Test accès Python
        logger.info("Test accès Python:")
        if os.access(str(recordings_dir), os.R_OK | os.W_OK):
            logger.info("  ✅ Python peut lire/écrire dans recordings/")
        else:
            logger.warning("  ⚠️  Python ne peut pas encore accéder (reconnectez-vous)")

        logger.info("")
        logger.info("📝 Prochaines étapes:")
        logger.info(f"  1. Reconnectez-vous: su - {current_user}")
        logger.info("  2. Vérifiez accès: python3 -c \"import os; print(os.access('/usr/local/freeswitch/recordings', os.W_OK))\"")
        logger.info("  3. Lancez un test: python3 test_call.py <numero>")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erreur lors de l'exécution de la commande: {e}")
        logger.error(f"   Sortie: {e.stderr.decode() if e.stderr else 'N/A'}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur configuration permissions: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Initialiser la base de données")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="⚠️ Supprimer et recréer toutes les tables (DESTRUCTIF)"
    )
    parser.add_argument(
        "--test-data",
        action="store_true",
        help="Créer des données de test"
    )
    parser.add_argument(
        "--setup-permissions",
        action="store_true",
        help="Configurer permissions FreeSWITCH recordings (requiert sudo)"
    )

    args = parser.parse_args()

    # Si seulement setup-permissions, le faire et sortir
    if args.setup_permissions and not args.reset and not args.test_data:
        setup_freeswitch_permissions()
        return

    logger.info("🚀 SETUP BASE DE DONNÉES")
    logger.info("=" * 60)
    logger.info(f"Database URL: {config.DATABASE_URL}")
    logger.info("=" * 60)

    # Test connexion
    logger.info("\n1️⃣ Test de connexion...")
    if not test_connection():
        logger.error("❌ Impossible de se connecter à la base de données")
        logger.info("💡 Vérifiez que PostgreSQL est démarré et configuré")
        return

    # Reset si demandé
    if args.reset:
        logger.info("\n⚠️ MODE RESET ACTIVÉ")
        confirm = input("Êtes-vous sûr de vouloir SUPPRIMER toutes les données ? (tapez 'RESET'): ")
        if confirm != "RESET":
            logger.info("❌ Annulé")
            return

        logger.info("\n2️⃣ Suppression des tables...")
        drop_tables()

    # Créer tables
    logger.info("\n3️⃣ Création des tables...")
    if not create_tables():
        return

    # Données de test
    if args.test_data:
        logger.info("\n4️⃣ Création de données de test...")
        create_test_data()

    # Stats finales
    logger.info("\n5️⃣ Statistiques finales")
    show_stats()

    # Setup permissions si demandé
    if args.setup_permissions:
        logger.info("\n6️⃣ Configuration permissions FreeSWITCH")
        setup_freeswitch_permissions()

    logger.info("\n✅ Setup base de données terminé!")


if __name__ == "__main__":
    main()
