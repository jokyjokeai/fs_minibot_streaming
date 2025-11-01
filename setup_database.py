#!/usr/bin/env python3
"""
Setup Database - MiniBotPanel v3

Initialise la base de données PostgreSQL.

Fonctionnalités:
- Création tables (Contact, Campaign, Call, CallEvent)
- Test connexion
- Migration schema si nécessaire
- Données de test optionnelles

Utilisation:
    python setup_database.py
    python setup_database.py --test-data
    python setup_database.py --reset (⚠️ supprime toutes les données)
"""

import argparse
import logging
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

    args = parser.parse_args()

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

    logger.info("\n✅ Setup base de données terminé!")


if __name__ == "__main__":
    main()
