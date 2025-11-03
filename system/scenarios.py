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

        self.scenarios_dir = config.BASE_DIR / "documentation" / "scenarios"

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
        required_fields = ["name", "steps"]

        for field in required_fields:
            if field not in scenario:
                logger.error(f"Missing required field: {field}")
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
            # audio_type et intent_mapping toujours requis
            required_step_fields = ["audio_type", "intent_mapping"]

            for field in required_step_fields:
                if field not in step_config:
                    logger.error(f"Step '{step_name}' missing field: {field}")
                    return False

            # message_text toujours requis (freestyle removed in v3)
            if "message_text" not in step_config:
                logger.error(f"Step '{step_name}' missing required field: message_text")
                return False

            # Valider audio_type (freestyle removed in v3)
            valid_audio_types = ["audio", "tts", "tts_cloned"]
            if step_config["audio_type"] not in valid_audio_types:
                logger.error(f"Step '{step_name}' has invalid audio_type")
                return False

            # Si audio, vérifier audio_file
            if step_config["audio_type"] == "audio" and "audio_file" not in step_config:
                logger.error(f"Step '{step_name}' audio type but no audio_file")
                return False

            # Si TTS, vérifier voice
            if step_config["audio_type"] == "tts" and "voice" not in step_config:
                logger.error(f"Step '{step_name}' tts type but no voice")
                return False

            # Support pour tts_cloned (avec voice_config optionnel)
            if step_config["audio_type"] == "tts_cloned":
                if "voice" not in step_config:
                    logger.error(f"Step '{step_name}' tts_cloned type but no voice")
                    return False

            # Freestyle AI mode removed in v3 (using pre-recorded audio only)

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

    def evaluate_qualification(
        self,
        scenario: Dict,
        call_history: Dict[str, str],
        current_step: str = None
    ) -> Dict[str, Any]:
        """
        Évalue la qualification d'un lead selon les règles du scénario.

        Système BINAIRE : soit LEAD, soit NOT_INTERESTED.

        Args:
            scenario: Scénario chargé
            call_history: Dict {step_name: intent} de l'historique
            current_step: Étape actuelle (optionnel)

        Returns:
            Dict avec result et qualification_data
        """
        result = {
            "result": None,
            "qualification_data": {},
            "qualifying_answers": {}
        }

        # Si l'étape actuelle force un résultat
        if current_step:
            step_config = self.get_step_config(scenario, current_step)
            if step_config and "result" in step_config:
                result["result"] = step_config["result"]
                return result

        # Récupérer règles de qualification
        rules = scenario.get("qualification_rules", {})

        # Collecter les réponses aux questions qualifiantes
        qualifying_answers = {}

        for step_name, intent in call_history.items():
            step = scenario.get("steps", {}).get(step_name)
            if not step:
                continue

            # Si c'est une question qualifiante
            if step.get("qualifying_question"):
                # Enregistrer la réponse
                qualifying_answers[step_name] = {
                    "question": step.get("message_text", ""),
                    "answer": intent
                }

        result["qualifying_answers"] = qualifying_answers

        # Appliquer règles pour déterminer résultat
        if "lead" in rules:
            lead_rules = rules["lead"]

            # Vérifier si TOUTES les questions requises ont OUI
            if "required_steps" in lead_rules and "required_intents" in lead_rules:
                all_required_met = True

                for required_step in lead_rules["required_steps"]:
                    # Vérifier que la question a été posée
                    if required_step not in call_history:
                        all_required_met = False
                        break

                    # Vérifier que la réponse est OUI
                    required_intent = lead_rules["required_intents"].get(required_step)
                    if call_history.get(required_step) != required_intent:
                        all_required_met = False
                        break

                # Si TOUTES les conditions sont remplies → LEAD
                if all_required_met:
                    result["result"] = "lead"
                else:
                    result["result"] = "not_interested"

        # Si pas de règles définies, décision simple
        if not result["result"]:
            # Compter les "deny"
            deny_count = sum(1 for intent in call_history.values() if intent == "deny")

            # Si au moins un "deny" → NOT_INTERESTED
            if deny_count > 0:
                result["result"] = "not_interested"
            else:
                result["result"] = "lead"

        # Stocker les données de qualification
        result["qualification_data"]["qualifying_questions"] = list(qualifying_answers.keys())
        result["qualification_data"]["answers"] = qualifying_answers

        return result

    def get_qualifying_questions(self, scenario: Dict) -> List[str]:
        """
        Récupère la liste des questions qualifiantes d'un scénario.

        Args:
            scenario: Scénario chargé

        Returns:
            Liste des noms d'étapes qualifiantes
        """
        qualifying_questions = []

        for step_name, step_config in scenario.get("steps", {}).items():
            if step_config.get("qualifying_question"):
                qualifying_questions.append({
                    "step": step_name,
                    "question": step_config.get("message_text"),
                    "weight": step_config.get("qualification_weight", 1),
                    "type": step_config.get("qualification_type", "lead")
                })

        return qualifying_questions

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
        Récupère la thématique du scénario

        Args:
            scenario: Scénario chargé

        Returns:
            Theme (défaut: "general")
        """
        return scenario.get("theme", "general")

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
