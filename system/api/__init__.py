"""
API REST Package - MiniBotPanel v3

API REST FastAPI pour contrôle et monitoring du système.

Endpoints:
- /campaigns : Gestion campagnes (create, start, pause, stop)
- /stats : Statistiques temps réel
- /exports : Exports CSV et téléchargements audio/transcriptions
"""

from .exports import router as exports_router
from .stats import router as stats_router
from .campaigns import router as campaigns_router

__all__ = ['exports_router', 'stats_router', 'campaigns_router']
