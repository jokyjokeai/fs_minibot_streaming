"""
Database Manager - MiniBotPanel v3

Ce module gère la connexion à PostgreSQL et les sessions SQLAlchemy.

Fonctionnalités:
- Création engine PostgreSQL avec pool de connexions
- Session factory pour dependency injection
- Base declarative pour modèles ORM
- Helper get_db() pour FastAPI

Utilisation:
    from system.database import SessionLocal, get_db

    # Usage direct
    db = SessionLocal()
    try:
        # ... requêtes DB
    finally:
        db.close()

    # Usage FastAPI (dependency injection)
    @app.get("/items")
    def get_items(db: Session = Depends(get_db)):
        return db.query(Item).all()
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from system.config import config

logger = logging.getLogger(__name__)

# ============================================================================
# ENGINE PostgreSQL
# ============================================================================
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,          # Test connexion avant usage
    pool_size=10,                # 10 connexions permanentes
    max_overflow=20,             # +20 connexions temporaires max
    pool_timeout=30,             # Timeout si pool saturé
    pool_recycle=1800,           # Recycle connexions après 30min
    echo=False                   # Mettre True pour debug SQL
)

# ============================================================================
# SESSION FACTORY
# ============================================================================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ============================================================================
# BASE DECLARATIVE
# ============================================================================
Base = declarative_base()

# ============================================================================
# DEPENDENCY INJECTION (FastAPI)
# ============================================================================
def get_db() -> Generator[Session, None, None]:
    """
    Générateur de session DB pour dependency injection FastAPI.

    Garantit la fermeture de la session même en cas d'exception.

    Yields:
        Session: Session SQLAlchemy active

    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# INITIALISATION DATABASE
# ============================================================================
def init_database():
    """
    Initialise la base de données (crée toutes les tables).

    À appeler au démarrage ou via setup_database.py
    """
    logger.info("Initializing database...")

    try:
        # Import models pour qu'ils soient enregistrés
        from system import models

        # Créer toutes les tables
        Base.metadata.create_all(bind=engine)

        logger.info("✅ Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

# ============================================================================
# TEST CONNEXION
# ============================================================================
def test_connection():
    """
    Test la connexion à la base de données.

    Returns:
        bool: True si connexion OK, False sinon
    """
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("✅ Database connection OK")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
