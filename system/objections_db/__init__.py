#!/usr/bin/env python3
"""
Objections Database - MiniBotPanel v3

Structure modulaire par thématique:
- objections_general.py : Objections communes à toutes thématiques
- objections_finance.py : Finance/Banque
- objections_crypto.py : Crypto/Trading
- objections_energie.py : Énergie/Panneaux solaires

Usage:
    from system.objections_db import load_objections

    objections = load_objections("objections_finance")
    # → Charge uniquement les objections finance (pas de GENERAL auto)
"""

import importlib
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Import config pour chemins FreeSWITCH
try:
    from system.config import get_freeswitch_audio_path
    FREESWITCH_CONFIG_AVAILABLE = True
except ImportError:
    FREESWITCH_CONFIG_AVAILABLE = False
    logger.warning("Could not import FreeSWITCH config, audio paths may not work correctly")
    def get_freeswitch_audio_path(voice, audio_type, filename):
        return Path(f"/usr/share/freeswitch/sounds/minibot/{voice}/{audio_type}/{filename}")

# Définition de la classe ObjectionEntry
from dataclasses import dataclass

@dataclass
class ObjectionEntry:
    """Entrée d'objection ou FAQ"""
    keywords: List[str]
    response: str
    audio_path: Optional[str] = None
    entry_type: str = "objection"

    def to_dict(self) -> dict:
        return {
            "keywords": self.keywords,
            "response": self.response,
            "audio_path": self.audio_path,
            "type": self.entry_type
        }


def _convert_audio_paths_to_freeswitch(objections: List[ObjectionEntry], voice: str = "julie") -> List[ObjectionEntry]:
    """
    Convertit les chemins audio des objections vers chemins FreeSWITCH.

    Args:
        objections: Liste d'ObjectionEntry avec chemins relatifs
        voice: Nom de la voix (défaut: julie)

    Returns:
        Liste d'ObjectionEntry avec chemins FreeSWITCH
    """
    for objection in objections:
        if objection.audio_path:
            # Si chemin relatif (audio/julie/objections/...)
            if objection.audio_path.startswith("audio/"):
                # Extraire juste le nom de fichier
                filename = Path(objection.audio_path).name
                # Convertir vers chemin FreeSWITCH
                objection.audio_path = str(get_freeswitch_audio_path(voice, "objections", filename))
            # Si déjà un chemin absolu FreeSWITCH, ne rien faire
            elif objection.audio_path.startswith("/usr/share/freeswitch"):
                pass
            # Sinon, assumer que c'est juste un nom de fichier
            else:
                objection.audio_path = str(get_freeswitch_audio_path(voice, "objections", objection.audio_path))

    return objections


def load_objections(theme_file: str, voice: str = "julie", use_freeswitch_paths: bool = True) -> List[ObjectionEntry]:
    """
    Charge les objections depuis un fichier de thématique spécifique.

    IMPORTANT: Charge AUTOMATIQUEMENT objections_general.py + thématique choisie.

    Si theme_file = "objections_general" → Charge SEULEMENT general
    Si theme_file = "objections_finance" → Charge general + finance
    Si theme_file = "objections_crypto" → Charge general + crypto

    Args:
        theme_file: Nom du fichier (sans .py)
                   Ex: "objections_finance", "objections_crypto"
        voice: Nom de la voix pour chemins audio (défaut: "julie")
        use_freeswitch_paths: Si True, convertit chemins vers FreeSWITCH (défaut: True)

    Returns:
        Liste d'ObjectionEntry (GENERAL + thématique)

    Raises:
        ImportError: Si le fichier n'existe pas
        AttributeError: Si OBJECTIONS_DATABASE n'existe pas dans le module

    Example:
        >>> objections = load_objections("objections_finance")
        >>> print(f"Loaded {len(objections)} objections")
        Loaded 40 objections (20 general + 20 finance)
    """
    try:
        objections = []

        # 1. TOUJOURS charger objections_general (sauf si c'est déjà general)
        if theme_file != "objections_general":
            try:
                general_module = importlib.import_module("system.objections_db.objections_general")
                if hasattr(general_module, "OBJECTIONS_DATABASE"):
                    general_objections = general_module.OBJECTIONS_DATABASE
                    objections.extend(general_objections)
                    logger.info(f"✅ Loaded {len(general_objections)} objections from 'objections_general'")
            except ImportError:
                logger.warning("⚠️ objections_general.py not found, skipping general objections")

        # 2. Charger la thématique spécifique
        module = importlib.import_module(f"system.objections_db.{theme_file}")

        # Récupérer OBJECTIONS_DATABASE
        if not hasattr(module, "OBJECTIONS_DATABASE"):
            raise AttributeError(
                f"Module '{theme_file}' n'a pas d'attribut OBJECTIONS_DATABASE"
            )

        theme_objections = module.OBJECTIONS_DATABASE
        objections.extend(theme_objections)

        logger.info(f"✅ Loaded {len(theme_objections)} objections from '{theme_file}'")
        logger.info(f"📚 Total: {len(objections)} objections (general + {theme_file})")

        # 3. Convertir chemins audio vers FreeSWITCH si demandé
        if use_freeswitch_paths:
            objections = _convert_audio_paths_to_freeswitch(objections, voice)
            logger.debug(f"✅ Audio paths converted to FreeSWITCH format")

        return objections

    except ImportError as e:
        logger.error(f"❌ Cannot import '{theme_file}': {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error loading objections from '{theme_file}': {e}")
        raise


def list_available_themes() -> List[str]:
    """
    Liste tous les fichiers de thématiques disponibles.

    Returns:
        Liste des noms de fichiers (sans .py)

    Example:
        >>> themes = list_available_themes()
        >>> print(themes)
        ['objections_finance', 'objections_crypto', 'objections_energie', 'objections_general']
    """
    objections_dir = Path(__file__).parent
    theme_files = []

    for file in objections_dir.glob("objections_*.py"):
        # Exclure __init__.py et objections_database.py (ancien système)
        if file.name != "__init__.py" and file.stem != "objections_database":
            theme_files.append(file.stem)  # stem = nom sans extension

    return sorted(theme_files)


# Export des symboles publics
__all__ = [
    "ObjectionEntry",
    "load_objections",
    "list_available_themes"
]
