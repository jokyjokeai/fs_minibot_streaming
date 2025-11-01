"""
Ollama NLP Service - MiniBotPanel v3

Service d'analyse NLP (Intent + Sentiment) via Ollama.
Adapté de nlp_intent.py pour FreeSWITCH.

Fonctionnalités:
- Détection intent (Positif, Négatif, Neutre, Unsure)
- Analyse sentiment
- Score de confiance
- Fallback mots-clés si Ollama indisponible
- Prompts contextuels pour différentes étapes du scénario

Utilisation:
    from system.services.ollama_nlp import OllamaNLP

    nlp = OllamaNLP()
    result = nlp.analyze_intent("Oui d'accord ça m'intéresse")
    # result = {"intent": "affirm", "sentiment": "positive", "confidence": 0.92}
"""

import json
import time
import re
from typing import Dict, Any, Optional

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

# Import Ollama avec fallback
try:
    import ollama
    OLLAMA_AVAILABLE = True
    logger.info("✅ Ollama imported successfully")
except ImportError as e:
    OLLAMA_AVAILABLE = False
    logger.warning(f"⚠️ Ollama not available: {e}")


class OllamaNLP:
    """
    Service NLP Ollama pour analyse d'intention et sentiment.
    Adapté de IntentEngine pour FreeSWITCH.
    """

    def __init__(self):
        """Initialise le service Ollama NLP."""
        logger.info("Initializing OllamaNLP...")

        self.is_available = OLLAMA_AVAILABLE
        self.ollama_client = None

        # Configuration
        self.ollama_config = {
            "url": config.OLLAMA_URL,
            "model": config.OLLAMA_MODEL,
            "timeout": config.OLLAMA_TIMEOUT
        }

        # Statistiques
        self.stats = {
            "total_requests": 0,
            "ollama_success": 0,
            "fallback_used": 0,
            "avg_latency_ms": 0.0
        }

        # Mapping intents vers statuts standard
        self.intent_to_status = {
            "Positif": "affirm",
            "Négatif": "deny",
            "Neutre": "unsure",
            "Unsure": "unsure"
        }

        # Prompts système pour différents contextes
        self.system_prompts = {
            "general": """Tu es un module NLP pour un robot d'appel de prospection.

Tu analyses les réponses des prospects français.
Réponds UNIQUEMENT en JSON au format {"intent": "...", "confidence": 0.9}.

Intents possibles (4 seulement) :
- "Positif" : oui, d'accord, ok, intéressé, absolument, évidemment, j'aimerais en savoir plus
- "Négatif" : non, pas intéressé, pas le temps, ça ne m'intéresse pas, arrêtez
- "Neutre" : peut-être, je ne sais pas, il faut que je réfléchisse, ça dépend
- "Unsure" : je n'ai pas compris, pouvez-vous répéter, pardon, comment

Réponds TOUJOURS en JSON valide.""",

            "greeting": """Tu analyses la réponse à l'introduction.
Réponds UNIQUEMENT en JSON : {"intent": "...", "confidence": 0.9}

Le prospect répond à l'introduction.

Intents :
- "Positif" : oui, ok, d'accord, allez-y, je vous écoute, pourquoi pas
- "Négatif" : non, pas le temps, pas intéressé, raccrochez, ça ne m'intéresse pas
- "Neutre" : peut-être, ça dépend, voyons, je ne sais pas
- "Unsure" : je n'ai pas compris, pardon, comment""",

            "qualification": """Tu analyses la réponse aux questions de qualification.
Réponds UNIQUEMENT en JSON : {"intent": "...", "confidence": 0.9}

Intents :
- "Positif" : oui, j'ai, effectivement, bien sûr, tout à fait
- "Négatif" : non, je n'ai pas, pas du tout, jamais
- "Neutre" : je ne sais pas, peut-être, il faut voir, ça dépend
- "Unsure" : je n'ai pas compris, pardon, comment""",

            "final_offer": """Tu analyses la réponse à l'offre finale.
Réponds UNIQUEMENT en JSON : {"intent": "...", "confidence": 0.9}

Le prospect répond à la proposition finale.

Intents :
- "Positif" : oui, d'accord, ok, parfait, allez-y, très bien
- "Négatif" : non, pas intéressé, ça ne m'intéresse pas, merci mais non
- "Neutre" : oui mais plus tard, pas cette semaine, dans un mois, je réfléchis
- "Unsure" : je n'ai pas compris, pardon, comment"""
        }

        # Mots-clés pour fallback
        self.keyword_patterns = {
            "affirm": [
                r"\b(oui|ok|d'accord|bien sur|absolument|evidemment|parfait|allez-y|je veux bien)\b",
                r"\b(intéress|pourquoi pas|volontiers)\b"
            ],
            "deny": [
                r"\b(non|pas intéress|pas le temps|rappel|pas maintenant|jamais)\b",
                r"\b(arrêt|stop|fiche|tranquille)\b"
            ],
            "unsure": [
                r"\b(peut-être|je sais pas|réfléchir|voir|dépend)\b",
                r"\b(hésit|incertain)\b"
            ],
            "question": [
                r"\b(qui|quoi|comment|pourquoi|combien|quand|où)\b",
                r"\?(.*)\?"
            ]
        }

        if not self.is_available:
            logger.warning("🚫 OllamaNLP not available - using keyword fallback")
            return

        # Tester connexion Ollama
        self._test_ollama_connection()

        logger.info(f"{'✅' if self.is_available else '❌'} OllamaNLP initialized")

    def prewarm(self) -> bool:
        """
        Pré-charge le modèle Ollama (Phase 8).

        Cette méthode force Ollama à charger le modèle en mémoire avant
        la première vraie requête, réduisant la latence du premier appel.

        Utilise l'API generate avec keep_alive pour maintenir le modèle chaud.

        Returns:
            True si succès, False sinon
        """
        if not self.is_available or not OLLAMA_AVAILABLE:
            logger.warning("Ollama not available, cannot prewarm")
            return False

        try:
            logger.info(f"🔥 Prewarming Ollama model: {self.ollama_config['model']}...")
            start_time = time.time()

            # Requête minimale pour charger le modèle
            response = ollama.generate(
                model=self.ollama_config['model'],
                prompt="Hello",  # Prompt minimal
                options={
                    "num_predict": 1,  # Générer juste 1 token
                    "temperature": 0
                },
                keep_alive="30m"  # Phase 8: Garder modèle chaud 30min
            )

            latency = (time.time() - start_time) * 1000

            if response:
                logger.info(f"✅ Ollama prewarmed successfully ({latency:.0f}ms)")
                logger.info(f"   Model will stay loaded for 30 minutes")
                return True
            else:
                logger.warning("⚠️ Ollama prewarm returned empty response")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to prewarm Ollama: {e}")
            return False

    def _test_ollama_connection(self):
        """Teste la connexion à Ollama"""
        try:
            if not OLLAMA_AVAILABLE:
                return False

            # Test simple
            response = ollama.list()
            logger.info(f"✅ Ollama connection OK - {len(response.get('models', []))} models available")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Ollama connection failed: {e}")
            self.is_available = False
            return False

    def analyze_intent(self, text: str, context: str = "general") -> Dict[str, Any]:
        """
        Analyse texte pour détecter intention.

        Args:
            text: Texte à analyser
            context: Contexte (general, greeting, qualification, final_offer)

        Returns:
            Dict avec intent, confidence
        """
        self.stats["total_requests"] += 1

        # Nettoyer texte
        text = text.strip().lower()

        if not text:
            return {"intent": "silence", "confidence": 0.0}

        # Essayer Ollama si disponible
        if self.is_available and OLLAMA_AVAILABLE:
            start_time = time.time()
            result = self._analyze_with_ollama(text, context)

            if result:
                latency = (time.time() - start_time) * 1000
                self.stats["ollama_success"] += 1
                self.stats["avg_latency_ms"] = (
                    (self.stats["avg_latency_ms"] * (self.stats["ollama_success"] - 1) + latency)
                    / self.stats["ollama_success"]
                )
                return result

        # Fallback mots-clés
        self.stats["fallback_used"] += 1
        return self._analyze_with_keywords(text)

    def _analyze_with_ollama(self, text: str, context: str) -> Optional[Dict[str, Any]]:
        """Analyse avec Ollama"""
        try:
            # Sélectionner prompt selon contexte
            system_prompt = self.system_prompts.get(context, self.system_prompts["general"])

            # Appel Ollama
            response = ollama.chat(
                model=self.ollama_config["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Réponse du prospect: {text}"}
                ],
                options={
                    "temperature": 0.1,  # Peu de créativité, cohérence maximale
                    "num_predict": 50     # Réponse courte (JSON)
                }
            )

            # Parser réponse
            content = response.get("message", {}).get("content", "")

            # Extraire JSON
            try:
                # Chercher JSON dans la réponse
                json_match = re.search(r'\{[^}]+\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                    intent = result.get("intent", "Unsure")
                    confidence = result.get("confidence", 0.5)

                    # Convertir intent Ollama vers format standard
                    standard_intent = self.intent_to_status.get(intent, "unsure")

                    logger.debug(f"Ollama: '{text}' → {standard_intent} ({confidence:.2f})")

                    return {
                        "intent": standard_intent,
                        "confidence": confidence,
                        "raw_intent": intent
                    }

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse Ollama JSON: {content}")

            return None

        except Exception as e:
            logger.error(f"Ollama analysis error: {e}")
            return None

    def _analyze_with_keywords(self, text: str) -> Dict[str, Any]:
        """Analyse avec mots-clés (fallback)"""
        # Chercher patterns
        for intent, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.debug(f"Keyword fallback: '{text}' → {intent}")
                    return {
                        "intent": intent,
                        "confidence": 0.7,  # Confiance plus basse pour fallback
                        "method": "keywords"
                    }

        # Par défaut : unsure
        return {
            "intent": "unsure",
            "confidence": 0.3,
            "method": "default"
        }

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques NLP"""
        success_rate = (
            (self.stats["ollama_success"] / self.stats["total_requests"] * 100)
            if self.stats["total_requests"] > 0 else 0
        )

        return {
            **self.stats,
            "is_available": self.is_available,
            "success_rate_pct": round(success_rate, 1),
            "model": self.ollama_config["model"]
        }
