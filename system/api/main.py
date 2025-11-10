"""
API REST Main - MiniBotPanel v3

Point d'entrée de l'API REST FastAPI.
"""

import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from system.config import config
from system.database import engine, init_database, test_connection
from system.models import Base

# Import routers
from system.api import campaigns, stats, exports

logger = logging.getLogger(__name__)

# Variables globales pour stats
app_start_time = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion du cycle de vie de l'application.

    Actions au démarrage et à l'arrêt.
    """
    # Startup
    global app_start_time
    app_start_time = datetime.utcnow()

    logger.info("🚀 Starting MiniBotPanel v3 API...")

    # Initialiser base de données
    logger.info("📊 Initializing database...")
    if not test_connection():
        logger.error("❌ Database connection failed!")
        # On continue quand même pour le développement
    else:
        init_database()
        logger.info("✅ Database initialized")

    # Phase 8: Initialiser Cache Manager (singleton)
    logger.info("💾 Initializing Cache Manager...")
    try:
        from system.cache_manager import get_cache
        cache = get_cache()
        logger.info("✅ Cache Manager initialized")
    except Exception as e:
        logger.warning(f"⚠️ Could not initialize Cache Manager: {e}")

    # Précharger modèles IA si configuré
    if config.PRELOAD_MODELS:
        logger.info("🧠 Preloading AI models...")
        try:
            from system.services.faster_whisper_stt import FasterWhisperSTT
            from system.services.ollama_nlp import OllamaNLP

            # Initialiser services pour préchargement
            fw_stt = FasterWhisperSTT(
                model_name=config.FASTER_WHISPER_MODEL,
                device=config.FASTER_WHISPER_DEVICE,
                compute_type=config.FASTER_WHISPER_COMPUTE_TYPE
            )

            # Phase 8: Prewarm Ollama (keep_alive 30min)
            logger.info("🔥 Prewarming Ollama model...")
            nlp = OllamaNLP()
            if nlp.prewarm():
                logger.info("✅ Ollama prewarmed (latency optimized)")
            else:
                logger.warning("⚠️ Ollama prewarm failed (will use on-demand)")

            # TTS removed - using pre-recorded audio only

            logger.info("✅ AI models preloaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not preload AI models: {e}")

    logger.info("✅ API started successfully!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down MiniBotPanel v3 API...")

    # Cleanup resources
    try:
        # Stop batch caller if running
        try:
            from system.batch_caller import batch_caller
            if batch_caller and batch_caller.running:
                logger.info("Stopping batch caller...")
                batch_caller.stop()
        except Exception as e:
            logger.warning(f"Could not stop batch caller: {e}")

        # Close database connections
        try:
            engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.warning(f"Could not close database: {e}")

        logger.info("✅ Cleanup complete")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info("✅ API shutdown complete")


# Créer application FastAPI
app = FastAPI(
    title="MiniBotPanel v3 API",
    description="API REST pour robot d'appels conversationnels avec FreeSWITCH",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configuration CORS
origins = config.API_CORS_ORIGINS.split(",") if hasattr(config, 'API_CORS_ORIGINS') else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type"]
)


# Middleware de logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log toutes les requêtes HTTP.
    """
    start_time = datetime.utcnow()

    # Log requête
    logger.info(f"📥 {request.method} {request.url.path}")

    # Traiter requête
    response = await call_next(request)

    # Calculer durée
    duration = (datetime.utcnow() - start_time).total_seconds()

    # Log réponse
    logger.info(f"📤 {request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")

    return response


# Middleware de protection simple par mot de passe
@app.middleware("http")
async def simple_password_auth(request: Request, call_next):
    """
    Protection simple de l'API par mot de passe unique.

    Le mot de passe peut être passé :
    - Header: X-API-Key: votre_mot_de_passe
    - Query param: ?password=votre_mot_de_passe

    Chemins publics (pas de vérification) :
    - /, /health, /metrics
    - /docs, /redoc, /openapi.json
    """
    # Chemins publics (pas de protection)
    public_paths = [
        "/",
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json"
    ]

    # Vérifier si le chemin est public
    if request.url.path in public_paths:
        return await call_next(request)

    # Récupérer mot de passe configuré
    expected_password = config.API_PASSWORD

    # Récupérer mot de passe de la requête
    # Méthode 1: Header X-API-Key
    api_key_header = request.headers.get("X-API-Key")

    # Méthode 2: Query parameter password
    password_param = request.query_params.get("password")

    provided_password = api_key_header or password_param

    # Vérifier mot de passe
    if not provided_password or provided_password != expected_password:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API password. Provide it via X-API-Key header or ?password= query param."
                }
            },
            headers={"WWW-Authenticate": "API-Key"}
        )

    # Mot de passe valide, continuer
    response = await call_next(request)
    return response


# Gestion des erreurs globales
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Gestion des erreurs de validation Pydantic.
    """
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Gestion des HTTPExceptions.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Gestion des erreurs non prévues.
    """
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal error occurred"
            }
        }
    )


# Inclure routers
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(stats.router, prefix="/api", tags=["statistics"])
app.include_router(exports.router, prefix="/api", tags=["exports"])


# Endpoints racine
@app.get("/", tags=["root"])
def root():
    """
    Endpoint racine avec informations système.
    """
    uptime = None
    if app_start_time:
        uptime_seconds = (datetime.utcnow() - app_start_time).total_seconds()
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime = f"{hours}h {minutes}m"

    return {
        "name": "MiniBotPanel v3 API",
        "version": "3.0.0",
        "status": "running",
        "uptime": uptime,
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "endpoints": {
            "campaigns": "/api/campaigns",
            "statistics": "/api/stats",
            "exports": "/api/exports"
        }
    }


@app.get("/health", tags=["health"])
def health():
    """
    Health check endpoint pour monitoring.

    Vérifie l'état de tous les composants.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    # Check database
    try:
        if test_connection():
            health_status["components"]["database"] = {"status": "healthy"}
        else:
            health_status["components"]["database"] = {"status": "unhealthy"}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    # Check FreeSWITCH via ESL connection test
    try:
        from system.robot_freeswitch import RobotFreeSWITCH
        robot = RobotFreeSWITCH()
        if robot.connect():
            health_status["components"]["freeswitch"] = {"status": "healthy", "esl_port": config.FREESWITCH_ESL_PORT}
            robot.stop()  # Close connection immediately
        else:
            health_status["components"]["freeswitch"] = {"status": "unhealthy", "error": "Cannot connect to ESL"}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["freeswitch"] = {"status": "unknown", "error": str(e)}

    # Check services IA
    try:
        from system.services.faster_whisper_stt import FasterWhisperSTT
        stt = FasterWhisperSTT(
            model_name=config.FASTER_WHISPER_MODEL,
            device=config.FASTER_WHISPER_DEVICE,
            compute_type=config.FASTER_WHISPER_COMPUTE_TYPE
        )
        if stt.is_available:
            health_status["components"]["faster_whisper"] = {
                "status": "healthy",
                "model": config.FASTER_WHISPER_MODEL,
                "device": stt.device
            }
        else:
            health_status["components"]["faster_whisper"] = {"status": "unhealthy"}
    except Exception as e:
        health_status["components"]["faster_whisper"] = {"status": "unknown", "error": str(e)}

    try:
        from system.services.ollama_nlp import OllamaNLP
        nlp = OllamaNLP()
        if nlp.is_available:
            health_status["components"]["ollama"] = {"status": "healthy"}
        else:
            health_status["components"]["ollama"] = {"status": "unhealthy"}
    except:
        health_status["components"]["ollama"] = {"status": "unknown"}

    # Déterminer code HTTP
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@app.get("/metrics", tags=["monitoring"])
def metrics():
    """
    Endpoint pour métriques Prometheus.

    Retourne métriques au format compatible Prometheus.
    Pour une intégration complète Prometheus, installer prometheus_client.
    """
    try:
        from system.database import SessionLocal
        from system.models import Campaign, Call, CallStatus, CampaignStatus

        db = SessionLocal()

        # Compter campagnes actives
        active_campaigns = db.query(Campaign).filter(
            Campaign.status == CampaignStatus.RUNNING
        ).count()

        # Compter appels actifs
        active_calls = db.query(Call).filter(
            Call.status.in_([CallStatus.IN_PROGRESS, CallStatus.CALLING, CallStatus.RINGING])
        ).count()

        # Total appels complétés
        completed_calls = db.query(Call).filter(
            Call.status == CallStatus.COMPLETED
        ).count()

        db.close()

        # Format Prometheus-like (text plain)
        metrics_text = f"""# HELP minibot_campaigns_active Number of active campaigns
# TYPE minibot_campaigns_active gauge
minibot_campaigns_active {active_campaigns}

# HELP minibot_calls_active Number of active calls
# TYPE minibot_calls_active gauge
minibot_calls_active {active_calls}

# HELP minibot_calls_completed_total Total completed calls
# TYPE minibot_calls_completed_total counter
minibot_calls_completed_total {completed_calls}

# HELP minibot_uptime_seconds Uptime in seconds
# TYPE minibot_uptime_seconds gauge
minibot_uptime_seconds {int((datetime.utcnow() - app_start_time).total_seconds()) if app_start_time else 0}
"""

        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=metrics_text, media_type="text/plain")

    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return {
            "error": "Failed to generate metrics",
            "hint": "Use /api/stats/system for JSON metrics"
        }
