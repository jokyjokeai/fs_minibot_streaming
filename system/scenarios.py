"""
Scenarios Manager - MiniBotPanel v3

Gestion des scénarios conversationnels.

Fonctionnalités:
- Chargement scénarios depuis JSON
- Exécution flow conversationnel
- Intent mapping (OUI → étape X, NON → étape Y)
- Support audio pré-enregistré ET TTS par étape
- Variables dynamiques ({{first_name}}, {{company}}, etc.)

Format JSON d'un scénario:

MODE CLASSIQUE (ancien):
{
    "name": "Production V1",
    "description": "Scénario production principal",
    "agent_mode": false,
    "steps": {
        "intro": {
            "message_text": "Bonjour {{first_name}}, je suis Julie...",
            "audio_type": "tts",
            "voice": "julie",
            "barge_in": true,
            "timeout": 15,
            "intent_mapping": {
                "affirm": "question1",
                "deny": "retry"
            }
        }
    }
}

MODE AGENT AUTONOME (nouveau):
{
    "name": "Agent Finance V1",
    "description": "Agent autonome finance",
    "agent_mode": true,
    "theme": "finance",
    "voice": "julie",
    "background_audio": "office.wav",
    "rail": [
        "Hello",
        "Retry_Hello",
        "Q1_Proprietaire",
        "Q2_Surface",
        "Q3_Chauffage",
        "Is_Leads",
        "Retry_Is_Leads",
        "Confirm_Time",
        "Bye_Success",
        "Bye_Failed"
    ],
    "steps": {
        "Hello": {
            "message_text": "Bonjour {{first_name}}, je suis Julie de {{company}}. On aide les propriétaires à économiser sur leur crédit. Vous avez 2 minutes ?",
            "audio_type": "audio",
            "audio_file": "hello.wav",
            "max_autonomous_turns": 2,
            "is_determinant": false,
            "intent_mapping": {
                "affirm": "Q1_Proprietaire",
                "deny": "Bye_Failed",
                "silence": "Retry_Hello"
            }
        },
        "Q1_Proprietaire": {
            "message_text": "Vous êtes propriétaire de votre logement ?",
            "audio_type": "tts_cloned",
            "voice": "julie",
            "max_autonomous_turns": 2,
            "is_determinant": true,
            "qualification_weight": 30,
            "intent_mapping": {
                "affirm": "Q2_Surface",
                "deny": "Bye_Failed",
                "silence": "Bye_Failed"
            }
        }
    }
}

Utilisation:
    from system.scenarios import ScenarioManager

    manager = ScenarioManager()
    scenario = manager.load_scenario("production")

    # Exécuter scénario
    result = manager.execute_scenario(scenario, call_uuid, contact_data)
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from system.config import config
from system.cache_manager import get_cache  # Phase 8

logger = logging.getLogger(__name__)

class ScenarioManager:
    """Gestionnaire de scénarios conversationnels."""

    def __init__(self):
        """Initialise le gestionnaire de scénarios."""
        logger.info("Initializing ScenarioManager...")

        self.scenarios_dir = config.BASE_DIR / "scenarios"

        # Phase 8: Utiliser CacheManager global au lieu de cache local
        self.cache = get_cache()

        logger.info("✅ ScenarioManager initialized (using CacheManager)")

    def load_scenario(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """
        Charge un scénario depuis JSON.

        Phase 8: Utilise CacheManager pour cache intelligent avec TTL + LRU.

        Args:
            scenario_name: Nom du scénario (sans .json)

        Returns:
            Dict avec définition scénario ou None si erreur
        """
        # Phase 8: Check CacheManager global
        cached_scenario = self.cache.get_scenario(scenario_name)
        if cached_scenario:
            logger.debug(f"Scenario '{scenario_name}' loaded from CacheManager (hit)")
            return cached_scenario

        # Charger depuis fichier
        scenario_path = self.scenarios_dir / f"{scenario_name}.json"

        if not scenario_path.exists():
            logger.error(f"Scenario file not found: {scenario_path}")
            return None

        try:
            with open(scenario_path, 'r', encoding='utf-8') as f:
                scenario = json.load(f)

            # Valider structure
            if not self._validate_scenario(scenario):
                logger.error(f"Invalid scenario structure: {scenario_name}")
                return None

            # Phase 8: Mettre en cache via CacheManager
            self.cache.set_scenario(scenario_name, scenario)

            logger.info(f"✅ Scenario '{scenario_name}' loaded successfully")
            return scenario

        except Exception as e:
            logger.error(f"❌ Failed to load scenario '{scenario_name}': {e}")
            return None

    def _validate_scenario(self, scenario: Dict) -> bool:
        """
        Valide la structure d'un scénario.

        Args:
            scenario: Dict scénario à valider

        Returns:
            True si valide, False sinon
        """
        # Support 2 formats:
        # - Ancien: {"name": "...", "steps": {...}}
        # - Nouveau: {"metadata": {"name": "..."}, "steps": {...}}

        # Vérifier "name" - soit à la racine, soit dans metadata
        has_name = "name" in scenario or ("metadata" in scenario and "name" in scenario.get("metadata", {}))
        if not has_name:
            logger.error(f"Missing required field: name (either at root or in metadata)")
            return False

        # Vérifier "steps"
        if "steps" not in scenario:
            logger.error(f"Missing required field: steps")
            return False

        # Valider steps
        if not isinstance(scenario["steps"], dict) or len(scenario["steps"]) == 0:
            logger.error("Steps must be a non-empty dict")
            return False

        # Mode agent autonome : validation spécifique
        agent_mode = scenario.get("agent_mode", False)

        if agent_mode:
            # Rail requis en mode agent
            if "rail" not in scenario:
                logger.error("agent_mode=true requires 'rail' field")
                return False

            if not isinstance(scenario["rail"], list) or len(scenario["rail"]) == 0:
                logger.error("'rail' must be a non-empty list")
                return False

            # Vérifier que toutes les étapes du rail existent dans steps
            for rail_step in scenario["rail"]:
                if rail_step not in scenario["steps"]:
                    logger.error(f"Rail step '{rail_step}' not found in steps")
                    return False

            # Theme optionnel mais recommandé
            if "theme" not in scenario:
                logger.warning("agent_mode=true without 'theme' - objections générales uniquement")

            # Voice optionnelle (défaut: première step avec voice)
            if "voice" not in scenario:
                logger.debug("No global voice specified, will use step-level voice")

        # Valider chaque step
        for step_name, step_config in scenario["steps"].items():
            # Skip validation pour step "end" (juste pour raccrocher)
            if step_name == "end":
                continue

            # audio_type et intent_mapping toujours requis
            required_step_fields = ["audio_type", "intent_mapping"]

            for field in required_step_fields:
                if field not in step_config:
                    logger.error(f"Step '{step_name}' missing field: {field}")
                    return False

            # message_text toujours requis
            if "message_text" not in step_config:
                logger.error(f"Step '{step_name}' missing required field: message_text")
                return False

            # Valider audio_type (v3: TTS removed, only pre-recorded audio)
            # "audio" = pre-recorded audio file
            # "none" = no audio (for end steps)
            valid_audio_types = ["audio", "none"]
            if step_config["audio_type"] not in valid_audio_types:
                logger.error(f"Step '{step_name}' has invalid audio_type")
                return False

            # Si audio, vérifier audio_file
            if step_config["audio_type"] == "audio" and "audio_file" not in step_config:
                logger.error(f"Step '{step_name}' audio type but no audio_file")
                return False

            # TTS removed in v3 - only pre-recorded audio supported

            # Validation champs agent autonome
            if agent_mode:
                # max_autonomous_turns optionnel (défaut: 2)
                if "max_autonomous_turns" in step_config:
                    if not isinstance(step_config["max_autonomous_turns"], int):
                        logger.error(f"Step '{step_name}' max_autonomous_turns must be integer")
                        return False
                    if step_config["max_autonomous_turns"] < 0 or step_config["max_autonomous_turns"] > 10:
                        logger.error(f"Step '{step_name}' max_autonomous_turns must be 0-10")
                        return False

                # is_determinant optionnel (défaut: false)
                if "is_determinant" in step_config:
                    if not isinstance(step_config["is_determinant"], bool):
                        logger.error(f"Step '{step_name}' is_determinant must be boolean")
                        return False

                # qualification_weight optionnel (si is_determinant=true)
                if "qualification_weight" in step_config:
                    if not isinstance(step_config["qualification_weight"], (int, float)):
                        logger.error(f"Step '{step_name}' qualification_weight must be number")
                        return False
                    if step_config["qualification_weight"] < 0 or step_config["qualification_weight"] > 100:
                        logger.error(f"Step '{step_name}' qualification_weight must be 0-100")
                        return False

        return True

    def get_step_config(self, scenario: Dict, step_name: str) -> Optional[Dict]:
        """
        Récupère la configuration d'une étape.

        Args:
            scenario: Scénario chargé
            step_name: Nom de l'étape

        Returns:
            Dict config de l'étape ou None
        """
        if "steps" not in scenario or step_name not in scenario["steps"]:
            return None

        return scenario["steps"][step_name]

    def get_next_step(
        self,
        scenario: Dict,
        current_step: str,
        intent: str
    ) -> Optional[str]:
        """
        Détermine la prochaine étape selon l'intent détecté.

        Args:
            scenario: Scénario chargé
            current_step: Nom étape actuelle
            intent: Intent détecté (affirm, deny, question, etc.)

        Returns:
            Nom de la prochaine étape ou None si fin
        """
        step_config = self.get_step_config(scenario, current_step)

        if not step_config or "intent_mapping" not in step_config:
            return None

        intent_mapping = step_config["intent_mapping"]

        # Chercher intent exact
        if intent in intent_mapping:
            return intent_mapping[intent]

        # Chercher wildcard "*"
        if "*" in intent_mapping:
            return intent_mapping["*"]

        # Pas de mapping trouvé
        logger.warning(f"No intent mapping found for '{intent}' in step '{current_step}'")
        return None

    def replace_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """
        Remplace les variables dans un texte.

        Args:
            text: Texte avec variables (ex: "Bonjour {{first_name}}")
            variables: Dict avec valeurs (ex: {"first_name": "Jean"})

        Returns:
            Texte avec variables remplacées
        """
        result = text

        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))

        return result

    def list_scenarios(self) -> list:
        """
        Liste tous les scénarios disponibles.

        Returns:
            Liste des noms de scénarios
        """
        if not self.scenarios_dir.exists():
            return []

        scenarios = []
        for file in self.scenarios_dir.glob("*.json"):
            scenarios.append(file.stem)

        return scenarios

    # ═══════════════════════════════════════════════════════════════════════
    # AGENT AUTONOME - Nouvelles méthodes
    # ═══════════════════════════════════════════════════════════════════════

    def is_agent_mode(self, scenario: Dict) -> bool:
        """
        Vérifie si le scénario est en mode agent autonome

        Args:
            scenario: Scénario chargé

        Returns:
            True si agent_mode activé
        """
        return scenario.get("agent_mode", False)

    def get_rail(self, scenario: Dict) -> List[str]:
        """
        Récupère le rail du scénario

        Args:
            scenario: Scénario chargé

        Returns:
            Liste des étapes du rail (vide si mode classique)
        """
        return scenario.get("rail", [])

    def get_next_rail_step(self, scenario: Dict, current_step: str) -> Optional[str]:
        """
        Récupère la prochaine étape du rail

        Args:
            scenario: Scénario chargé
            current_step: Étape actuelle

        Returns:
            Nom de la prochaine étape du rail ou None si fin
        """
        rail = self.get_rail(scenario)

        if not rail or current_step not in rail:
            return None

        current_index = rail.index(current_step)

        # Prochaine étape
        if current_index + 1 < len(rail):
            return rail[current_index + 1]

        # Fin du rail
        return None

    def get_theme(self, scenario: Dict) -> str:
        """
        Récupère la thématique du scénario (ANCIEN SYSTÈME).

        DEPRECATED: Utiliser get_theme_file() à la place.

        Args:
            scenario: Scénario chargé

        Returns:
            Theme (défaut: "general")
        """
        return scenario.get("theme", "general")

    def get_theme_file(self, scenario: Dict) -> str:
        """
        Récupère le fichier d'objections du scénario (NOUVEAU SYSTÈME).

        Le nouveau système utilise "theme_file" pour charger depuis
        system/objections_db/{theme_file}.py

        Args:
            scenario: Scénario chargé

        Returns:
            Nom du fichier (ex: "objections_finance", "objections_crypto")
            Défaut: "objections_general"

        Example:
            >>> theme_file = manager.get_theme_file(scenario)
            >>> print(theme_file)
            objections_finance
        """
        # Essayer d'abord "theme_file" (nouveau système)
        if "theme_file" in scenario:
            return scenario["theme_file"]

        # Fallback: "theme" (ancien système) → conversion automatique
        if "theme" in scenario:
            theme = scenario["theme"]
            # Conversion: "finance" → "objections_finance"
            if not theme.startswith("objections_"):
                return f"objections_{theme}"
            return theme

        # Défaut
        return "objections_general"

    def get_max_autonomous_turns(self, scenario: Dict, step_name: str) -> int:
        """
        Récupère le nombre max de tours autonomes pour une étape

        Args:
            scenario: Scénario chargé
            step_name: Nom de l'étape

        Returns:
            Max turns (défaut: 2)
        """
        step_config = self.get_step_config(scenario, step_name)

        if not step_config:
            return 2

        return step_config.get("max_autonomous_turns", 2)

    def is_determinant_step(self, scenario: Dict, step_name: str) -> bool:
        """
        Vérifie si une étape est déterminante pour la qualification

        Args:
            scenario: Scénario chargé
            step_name: Nom de l'étape

        Returns:
            True si étape déterminante
        """
        step_config = self.get_step_config(scenario, step_name)

        if not step_config:
            return False

        return step_config.get("is_determinant", False)

    def get_qualification_weight(self, scenario: Dict, step_name: str) -> float:
        """
        Récupère le poids de qualification d'une étape

        Args:
            scenario: Scénario chargé
            step_name: Nom de l'étape

        Returns:
            Poids (défaut: 0)
        """
        step_config = self.get_step_config(scenario, step_name)

        if not step_config:
            return 0.0

        return float(step_config.get("qualification_weight", 0))

    def calculate_lead_score(
        self,
        scenario: Dict,
        call_history: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Calcule le score de qualification cumulatif

        Args:
            scenario: Scénario chargé
            call_history: Dict {step_name: intent}

        Returns:
            Dict avec score, is_lead, details
        """
        total_weight = 0.0
        obtained_weight = 0.0
        determinant_steps = []

        for step_name, intent in call_history.items():
            if self.is_determinant_step(scenario, step_name):
                weight = self.get_qualification_weight(scenario, step_name)
                total_weight += weight

                # Si réponse positive (affirm), on compte le poids
                if intent == "affirm":
                    obtained_weight += weight
                    determinant_steps.append({
                        "step": step_name,
                        "weight": weight,
                        "qualified": True
                    })
                else:
                    determinant_steps.append({
                        "step": step_name,
                        "weight": weight,
                        "qualified": False
                    })

        # Calculer score en %
        score = (obtained_weight / total_weight * 100) if total_weight > 0 else 0

        # Déterminer si c'est un lead (seuil: 70%)
        is_lead = score >= 70

        return {
            "score": round(score, 2),
            "is_lead": is_lead,
            "total_weight": total_weight,
            "obtained_weight": obtained_weight,
            "determinant_steps": determinant_steps
        }
