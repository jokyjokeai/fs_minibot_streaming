"""
Database Models - MiniBotPanel v3

Ce module définit tous les modèles ORM SQLAlchemy pour PostgreSQL.

Modèles:
- Contact : Contacts à appeler
- Campaign : Campagnes d'appels
- Call : Appels individuels avec résultats
- CallEvent : Événements durant l'appel (pour debugging)

Relations:
- Campaign 1→N Call
- Contact 1→N Call
- Call 1→N CallEvent

Utilisation:
    from system.models import Contact, Campaign, Call
    from system.database import SessionLocal

    db = SessionLocal()
    contact = Contact(phone="+33612345678", first_name="Jean")
    db.add(contact)
    db.commit()
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime,
    ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from system.database import Base

# ============================================================================
# ENUMS
# ============================================================================
class CallStatus(str, enum.Enum):
    """Statut technique de l'appel"""
    PENDING = "pending"           # En attente lancement
    QUEUED = "queued"             # Dans la file d'attente
    CALLING = "calling"           # Appel en cours
    RINGING = "ringing"           # Sonnerie en cours
    ANSWERED = "answered"         # Décrochage confirmé
    IN_PROGRESS = "in_progress"   # Conversation en cours
    COMPLETED = "completed"       # Terminé avec succès
    FAILED = "failed"             # Échec technique
    NO_ANSWER = "no_answer"       # Pas de réponse
    BUSY = "busy"                 # Occupé
    CANCELLED = "cancelled"       # Annulé
    RETRY = "retry"               # À réessayer

class CallResult(str, enum.Enum):
    """Résultat métier de l'appel"""
    NEW = "new"                               # Nouveau contact (jamais appelé)
    LEAD = "lead"                             # Lead qualifié (intéressé)
    NOT_INTERESTED = "not_interested"         # Pas intéressé
    CALLBACK = "callback"                     # Demande rappel
    ANSWERING_MACHINE = "answering_machine"   # Répondeur détecté
    NO_ANSWER = "no_answer"                   # Pas de réponse
    WRONG_NUMBER = "wrong_number"             # Mauvais numéro
    NOT_QUALIFIED = "not_qualified"           # Non qualifié
    OTHER = "other"                           # Autre

class Sentiment(str, enum.Enum):
    """Sentiment détecté"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    NONE = "none"

class CampaignStatus(str, enum.Enum):
    """Statut campagne"""
    PENDING = "pending"       # En attente démarrage
    RUNNING = "running"       # En cours
    PAUSED = "paused"         # En pause
    COMPLETED = "completed"   # Terminée
    CANCELLED = "cancelled"   # Annulée
    FAILED = "failed"         # Échec technique

# ============================================================================
# MODÈLE: Contact
# ============================================================================
class Contact(Base):
    """
    Modèle Contact - Contacts à appeler

    Colonnes principales:
    - phone : Numéro de téléphone (unique)
    - first_name, last_name : Nom/Prénom
    - email : Email
    - company : Entreprise
    - custom_data : Données custom (JSON)
    - blacklist : Dans blacklist interne (bloquer)
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)

    # Informations de base
    phone = Column(String(20), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)

    # Données custom (stockage flexible JSON)
    custom_data = Column(JSON, nullable=True)

    # Conformité légale
    blacklist = Column(Boolean, default=False, index=True)  # Blacklist interne
    opt_out = Column(Boolean, default=False)  # Désinscription volontaire

    # Statistiques
    total_calls = Column(Integer, default=0)
    last_call_at = Column(DateTime, nullable=True)
    last_result = Column(SQLEnum(CallResult), default=CallResult.NEW, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    calls = relationship("Call", back_populates="contact")

# ============================================================================
# MODÈLE: Campaign
# ============================================================================
class Campaign(Base):
    """
    Modèle Campaign - Campagnes d'appels

    Colonnes principales:
    - name : Nom campagne
    - scenario : Scénario à utiliser
    - status : État campagne (running, paused, completed)
    - stats : Statistiques temps réel (JSON)
    """
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)

    # Informations de base
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scenario = Column(String(100), nullable=False)  # Nom du scénario

    # Statut
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.PENDING, index=True)

    # Configuration
    max_concurrent_calls = Column(Integer, default=10)
    delay_between_calls = Column(Float, default=2.0)
    batch_size = Column(Integer, default=5)  # Nombre d'appels à lancer par batch
    retry_enabled = Column(Boolean, default=False)  # Activer retry automatique (DÉSACTIVÉ par défaut)
    max_retries = Column(Integer, default=1)  # Nombre max de retry pour NO_ANSWER (1 = pas de retry)
    retry_delay_minutes = Column(Integer, default=30)  # Délai entre retry (minutes)

    # Statistiques (JSON pour flexibilité)
    stats = Column(JSON, default={
        "total": 0,
        "completed": 0,
        "leads": 0,
        "not_interested": 0,
        "answering_machines": 0,
        "no_answer": 0,
        "failed": 0,
        "avg_duration": 0.0,
        "sentiment_positive": 0,
        "sentiment_neutral": 0,
        "sentiment_negative": 0
    })

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    calls = relationship("Call", back_populates="campaign")

# ============================================================================
# MODÈLE: Call
# ============================================================================
class Call(Base):
    """
    Modèle Call - Appels individuels

    Colonnes principales:
    - uuid : UUID FreeSWITCH unique
    - contact_id : Lien vers Contact
    - campaign_id : Lien vers Campaign
    - status : Statut technique (completed, failed, etc.)
    - result : Résultat métier (lead, not_interested, etc.)
    - sentiment : Sentiment détecté (positive, neutral, negative)
    - duration : Durée appel en secondes
    - recording_path : Chemin enregistrement audio
    - transcription_path : Chemin transcription texte
    """
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)

    # UUID FreeSWITCH (identifiant unique appel)
    uuid = Column(String(100), unique=True, index=True, nullable=False)

    # Relations
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    # Statut technique
    status = Column(SQLEnum(CallStatus), default=CallStatus.PENDING, index=True)

    # Résultat métier
    result = Column(SQLEnum(CallResult), nullable=True, index=True)

    # AMD (Answering Machine Detection)
    amd_result = Column(String(20), nullable=True)  # human, machine, unknown
    amd_duration = Column(Float, nullable=True)     # Temps AMD en secondes

    # Sentiment analysis
    sentiment = Column(SQLEnum(Sentiment), default=Sentiment.NONE, index=True)
    sentiment_score = Column(Float, nullable=True)  # Score 0.0-1.0

    # Lead Qualification
    qualification_data = Column(JSON, nullable=True, default={})  # Réponses aux questions qualifiantes

    # Durées
    duration = Column(Integer, nullable=True)  # Durée totale en secondes
    talk_duration = Column(Integer, nullable=True)  # Durée conversation uniquement

    # Fichiers
    recording_path = Column(String(500), nullable=True)
    transcription_path = Column(String(500), nullable=True)

    # Gestion File d'Attente et Retry
    retry_count = Column(Integer, default=0)  # Nombre de tentatives effectuées
    max_retries = Column(Integer, default=2)  # Nombre max de retry (hérité de campaign)
    last_attempt_at = Column(DateTime, nullable=True)  # Dernière tentative
    scheduled_at = Column(DateTime, nullable=True, index=True)  # Planifié pour (file attente)
    queue_priority = Column(Integer, default=0)  # Priorité dans file (0=normal, 1+=urgent)

    # Métadonnées (JSON flexible)
    call_metadata = Column(JSON, default={})

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    # Relations
    contact = relationship("Contact", back_populates="calls")
    campaign = relationship("Campaign", back_populates="calls")
    events = relationship("CallEvent", back_populates="call", cascade="all, delete-orphan")

# ============================================================================
# MODÈLE: CallEvent
# ============================================================================
class CallEvent(Base):
    """
    Modèle CallEvent - Événements durant l'appel

    Pour debugging et analyse détaillée.

    Événements typiques:
    - dial : Début composition
    - answer : Décrochage
    - amd_start : Début AMD
    - amd_result : Résultat AMD
    - play_audio : Lecture audio
    - stt_transcription : Transcription reçue
    - nlp_intent : Intent détecté
    - tts_start : Début génération TTS
    - hangup : Raccrochage
    """
    __tablename__ = "call_events"

    id = Column(Integer, primary_key=True, index=True)

    # Relation
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)

    # Type d'événement
    event_type = Column(String(50), index=True, nullable=False)

    # Données événement (JSON flexible)
    data = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relation
    call = relationship("Call", back_populates="events")
