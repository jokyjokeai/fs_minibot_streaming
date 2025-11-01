"""
Freestyle AI Service - MiniBotPanel v3

Service de génération de réponses dynamiques (freestyle) pour conversations hors-script.

Fonctionnalités:
- Génération réponses contextuelles via Ollama
- Cache questions fréquentes (mémoire + optionnel Redis)
- Historique conversationnel (5 derniers échanges)
- Limites intelligentes (max words, max turns)
- Prompts engineering pour commercial naturel
- Détection objectifs conversationnels

Utilisation:
    from system.services.freestyle_ai import FreestyleAI

    freestyle = FreestyleAI(ollama_service, tts_service)

    response_text = freestyle.generate_response(
        call_uuid="abc-123",
        user_input="C'est pour quoi exactement ?",
        context={
            "campaign": "Prospection B2B",
            "product": "Solution CRM",
            "agent_name": "Julie"
        }
    )
"""

import json
import time
import hashlib
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from datetime import datetime

from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

# Import Ollama avec fallback
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("⚠️ Ollama not available for freestyle")


class FreestyleAI:
    """
    Service de génération de réponses freestyle (hors-script).
    Utilise Ollama pour générer des réponses naturelles et contextuelles.
    """

    def __init__(self, ollama_service=None, tts_service=None):
        """
        Initialise le service Freestyle AI.

        Args:
            ollama_service: Service Ollama NLP (optionnel, créé auto si None)
            tts_service: Service Coqui TTS (optionnel)
        """
        logger.info("Initializing FreestyleAI...")

        self.ollama = ollama_service
        self.tts = tts_service
        self.is_available = OLLAMA_AVAILABLE

        # Configuration
        self.config = {
            "model": config.OLLAMA_MODEL,
            "url": config.OLLAMA_URL,
            "timeout": config.OLLAMA_TIMEOUT,
            "max_response_words": 150,  # Max mots par réponse
            "max_context_messages": 5,  # Historique conversationnel
            "temperature": 0.7,          # Créativité modérée
            "cache_size": 100            # Nombre questions en cache
        }

        # Cache questions fréquentes (LRU)
        self._cache = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0

        # Historique conversationnel par call_uuid
        self._conversations = {}  # {call_uuid: [messages]}

        # Statistiques
        self.stats = {
            "total_requests": 0,
            "successful_generations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_generation_time_ms": 0.0,
            "avg_response_length_words": 0.0
        }

        # Prompts système par type d'interaction
        self._system_prompts = {
            "default": """Tu es un assistant commercial au téléphone nommé {agent_name}.
Tu travailles pour {company} et tu proposes {product}.

RÈGLES STRICTES:
1. Réponds en FRANÇAIS naturel et professionnel
2. Maximum 2-3 phrases (≤150 mots)
3. Réponds DIRECTEMENT à la question posée
4. Ton amical mais pas trop familier
5. Ramène subtilement vers l'offre/rendez-vous
6. Ne mentionne JAMAIS que tu es une IA
7. Si tu ne sais pas, dis "Je vais vérifier et revenir vers vous"

INTERDICTIONS:
- Pas de markdown, pas de formatage
- Pas de "En tant qu'IA..."
- Pas de réponses vagues
- Pas de questions multiples

Contexte campagne: {campaign_context}""",

            "objection": """Tu es un commercial expérimenté nommé {agent_name}.
Le prospect vient de faire une objection.

Ta réponse doit:
1. Reconnaître l'objection ("Je comprends...")
2. Apporter un élément rassurant
3. Proposer une solution concrète
4. Garder la porte ouverte

Maximum 2 phrases, ton empathique.

Contexte: {campaign_context}""",

            "question_price": """Tu es commercial pour {company}.
Le prospect demande des informations sur le prix.

Ta réponse doit:
1. Ne PAS donner de prix précis par téléphone
2. Expliquer que ça dépend des besoins
3. Proposer une démo/RDV pour personnaliser

Maximum 2 phrases, professionnel mais pas évasif.

Contexte: {campaign_context}""",

            "question_info": """Tu es {agent_name}, expert de {product}.
Le prospect demande des infos techniques/pratiques.

Ta réponse doit:
1. Donner une réponse claire et précise
2. Rester simple (pas de jargon)
3. Mentionner un bénéfice concret
4. Proposer d'en parler en détail lors d'un RDV

Maximum 3 phrases.

Contexte: {campaign_context}"""
        }

        # Questions fermées pour retour au rail (Phase 6+)
        # Variées pour éviter répétition robotique
        self._rail_return_questions = {
            "general": [
                "Ça vous parle ?",
                "C'est clair pour vous ?",
                "Vous me suivez ?",
                "Ça répond à votre question ?",
                "C'est bon pour vous ?",
                "Vous voyez l'idée ?",
                "Ça fait sens ?",
                "D'accord ?"
            ],
            "after_objection": [
                "Vous êtes d'accord avec moi ?",
                "Ça vous rassure un peu ?",
                "Vous comprenez mieux maintenant ?",
                "Ça vous semble plus clair ?",
                "C'est mieux comme ça ?",
                "Ça change votre vision ?",
                "Ça vous parle davantage ?"
            ],
            "after_info": [
                "C'est plus clair pour vous ?",
                "Vous avez toutes les infos qu'il vous faut ?",
                "Ça répond à votre question ?",
                "Vous voulez que je précise un point ?",
                "C'est bon de votre côté ?",
                "Vous y voyez plus clair ?"
            ],
            "after_price": [
                "Vous voyez que c'est personnalisable ?",
                "Ça mérite qu'on en parle, non ?",
                "Vous êtes partant pour en discuter ?",
                "On peut creuser ensemble ?",
                "Ça vous intéresse d'en savoir plus ?"
            ]
        }

        # Index pour rotation des questions (éviter répétition)
        self._rail_question_indices = {
            category: 0 for category in self._rail_return_questions.keys()
        }

        if not self.is_available:
            logger.warning("🚫 FreestyleAI not available - Ollama missing")
            return

        logger.info("✅ FreestyleAI initialized")

    def generate_response(
        self,
        call_uuid: str,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        prompt_type: str = "default"
    ) -> str:
        """
        Génère une réponse freestyle contextuelle.

        Args:
            call_uuid: UUID de l'appel
            user_input: Question/remarque du prospect
            context: Contexte campagne (agent_name, company, product, etc.)
            prompt_type: Type de prompt (default, objection, question_price, etc.)

        Returns:
            Texte de la réponse générée
        """
        self.stats["total_requests"] += 1

        if not self.is_available or not OLLAMA_AVAILABLE:
            logger.error("FreestyleAI not available")
            return "Je vous remercie pour votre question. Un conseiller va vous rappeler."

        # Nettoyer input
        user_input = user_input.strip()
        if not user_input:
            return "Je vous écoute."

        # Context par défaut
        if context is None:
            context = {}

        context.setdefault("agent_name", "Julie")
        context.setdefault("company", "notre entreprise")
        context.setdefault("product", "nos solutions")
        context.setdefault("campaign_context", "Appel de prospection commercial")

        # 1. Vérifier cache
        cache_key = self._get_cache_key(user_input, context)
        cached_response = self._get_from_cache(cache_key)

        if cached_response:
            self.stats["cache_hits"] += 1
            logger.debug(f"Cache HIT for: {user_input[:50]}...")
            return cached_response

        self.stats["cache_misses"] += 1

        # 2. Construire historique conversation
        conversation_history = self._get_conversation_history(call_uuid)

        # 3. Générer réponse avec Ollama
        start_time = time.time()

        try:
            response = self._generate_with_ollama(
                user_input=user_input,
                context=context,
                conversation_history=conversation_history,
                prompt_type=prompt_type
            )

            generation_time = (time.time() - start_time) * 1000

            # Valider réponse
            response = self._validate_response(response)

            # Sauvegarder dans historique
            self._add_to_conversation(call_uuid, user_input, response)

            # Sauvegarder dans cache
            self._add_to_cache(cache_key, response)

            # Stats
            self.stats["successful_generations"] += 1
            self._update_avg_generation_time(generation_time)
            self._update_avg_response_length(response)

            logger.info(
                f"Freestyle generated ({generation_time:.0f}ms): "
                f"{user_input[:30]}... → {response[:50]}..."
            )

            return response

        except Exception as e:
            logger.error(f"Freestyle generation failed: {e}", exc_info=True)
            return "Merci pour votre question. Puis-je vous proposer un rendez-vous pour en discuter ?"

    def _generate_with_ollama(
        self,
        user_input: str,
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        prompt_type: str
    ) -> str:
        """Génère réponse avec Ollama"""

        # Sélectionner prompt système
        system_prompt_template = self._system_prompts.get(
            prompt_type,
            self._system_prompts["default"]
        )

        # Formater prompt avec contexte
        system_prompt = system_prompt_template.format(**context)

        # Construire messages
        messages = [{"role": "system", "content": system_prompt}]

        # Ajouter historique
        for msg in conversation_history[-self.config["max_context_messages"]:]:
            messages.append({"role": "user", "content": msg["user"]})
            messages.append({"role": "assistant", "content": msg["assistant"]})

        # Ajouter question actuelle
        messages.append({"role": "user", "content": user_input})

        # Appel Ollama
        response = ollama.chat(
            model=self.config["model"],
            messages=messages,
            options={
                "temperature": self.config["temperature"],
                "num_predict": 200,  # Max tokens
                "top_p": 0.9,
                "top_k": 40
            }
        )

        # Extraire texte
        response_text = response.get("message", {}).get("content", "").strip()

        return response_text

    def _validate_response(self, response: str) -> str:
        """Valide et nettoie la réponse générée"""

        # Supprimer markdown
        response = response.replace("**", "").replace("*", "")
        response = response.replace("#", "").replace("`", "")

        # Supprimer mentions IA
        ai_mentions = [
            "en tant qu'ia",
            "en tant qu'intelligence artificielle",
            "je suis une ia",
            "je suis un modèle",
            "en tant que modèle"
        ]
        response_lower = response.lower()
        for mention in ai_mentions:
            if mention in response_lower:
                logger.warning(f"IA mention detected in response: {mention}")
                response = "Merci pour votre question. Laissez-moi vous expliquer notre offre en détail."

        # Limiter longueur
        words = response.split()
        if len(words) > self.config["max_response_words"]:
            logger.warning(f"Response too long ({len(words)} words), truncating")
            response = " ".join(words[:self.config["max_response_words"]]) + "."

        # Nettoyer espaces multiples
        response = " ".join(response.split())

        return response

    def _get_cache_key(self, user_input: str, context: Dict[str, Any]) -> str:
        """Génère clé de cache"""
        # Hash basé sur input + contexte principal
        cache_string = f"{user_input.lower()}_{context.get('product', '')}_{context.get('company', '')}"
        return hashlib.md5(cache_string.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[str]:
        """Récupère réponse du cache"""
        if key in self._cache:
            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._cache_hits += 1
            return self._cache[key]
        return None

    def _add_to_cache(self, key: str, response: str):
        """Ajoute réponse au cache"""
        self._cache[key] = response
        self._cache.move_to_end(key)

        # Limite cache size (LRU eviction)
        if len(self._cache) > self.config["cache_size"]:
            self._cache.popitem(last=False)

    def _get_conversation_history(self, call_uuid: str) -> List[Dict[str, str]]:
        """Récupère historique conversation"""
        return self._conversations.get(call_uuid, [])

    def _add_to_conversation(self, call_uuid: str, user_input: str, response: str):
        """Ajoute échange à l'historique"""
        if call_uuid not in self._conversations:
            self._conversations[call_uuid] = []

        self._conversations[call_uuid].append({
            "user": user_input,
            "assistant": response,
            "timestamp": datetime.now().isoformat()
        })

        # Limite historique
        max_history = self.config["max_context_messages"] * 2
        if len(self._conversations[call_uuid]) > max_history:
            self._conversations[call_uuid] = self._conversations[call_uuid][-max_history:]

    def clear_conversation(self, call_uuid: str):
        """Nettoie historique d'un appel"""
        if call_uuid in self._conversations:
            del self._conversations[call_uuid]
            logger.debug(f"Conversation history cleared for {call_uuid}")

    def _update_avg_generation_time(self, time_ms: float):
        """Met à jour temps de génération moyen"""
        total = self.stats["successful_generations"]
        current_avg = self.stats["avg_generation_time_ms"]

        self.stats["avg_generation_time_ms"] = (
            (current_avg * (total - 1) + time_ms) / total
        )

    def _update_avg_response_length(self, response: str):
        """Met à jour longueur réponse moyenne"""
        word_count = len(response.split())
        total = self.stats["successful_generations"]
        current_avg = self.stats["avg_response_length_words"]

        self.stats["avg_response_length_words"] = (
            (current_avg * (total - 1) + word_count) / total
        )

    def detect_prompt_type(self, user_input: str) -> str:
        """
        Détecte automatiquement le type de prompt selon l'input.

        Args:
            user_input: Texte du prospect

        Returns:
            Type de prompt (default, objection, question_price, question_info)
        """
        user_input_lower = user_input.lower()

        # Détection objection
        objection_keywords = [
            "pas le temps", "pas intéressé", "trop cher", "déjà",
            "pas besoin", "ça va", "je réfléchis", "rappeler", "pas maintenant"
        ]
        if any(kw in user_input_lower for kw in objection_keywords):
            return "objection"

        # Détection question prix
        price_keywords = ["prix", "coût", "combien", "tarif", "budget", "cher"]
        if any(kw in user_input_lower for kw in price_keywords):
            return "question_price"

        # Détection question info
        question_keywords = ["comment", "pourquoi", "quoi", "c'est quoi", "qu'est-ce"]
        if any(kw in user_input_lower for kw in question_keywords):
            return "question_info"

        return "default"

    def generate_rail_return_question(
        self,
        prompt_type: str = "general",
        include_in_response: bool = True
    ) -> str:
        """
        Génère une question fermée variée pour retour au rail (Phase 6+).

        Après avoir répondu à une objection/question en mode freestyle,
        cette méthode génère une question fermée (oui/non) pour reprendre
        le contrôle de la conversation et ramener vers le rail.

        Les questions sont variées et tournent pour éviter la répétition robotique.

        Args:
            prompt_type: Type de contexte (objection, question_price, question_info, default)
            include_in_response: Si True, retourne question complète. Si False, juste la question

        Returns:
            Question fermée variée

        Example:
            >>> freestyle.generate_rail_return_question("objection")
            "Ça vous rassure un peu ?"

            >>> freestyle.generate_rail_return_question("question_price")
            "Ça mérite qu'on en parle, non ?"
        """
        # Mapper prompt_type vers catégorie de questions
        category_map = {
            "objection": "after_objection",
            "question_price": "after_price",
            "question_info": "after_info",
            "default": "general"
        }

        category = category_map.get(prompt_type, "general")

        # Récupérer liste des questions pour cette catégorie
        questions = self._rail_return_questions.get(category, self._rail_return_questions["general"])

        # Rotation des questions (éviter répétition)
        index = self._rail_question_indices[category]
        question = questions[index]

        # Incrémenter index (avec wrap-around)
        self._rail_question_indices[category] = (index + 1) % len(questions)

        logger.debug(f"Rail return question ({category}): {question}")

        return question

    def generate_response_with_rail_return(
        self,
        call_uuid: str,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        prompt_type: str = "default"
    ) -> str:
        """
        Génère une réponse freestyle AVEC question de retour au rail (Phase 6+).

        Cette méthode combine:
        1. Réponse freestyle à l'objection/question
        2. Question fermée variée pour retour au rail

        Args:
            call_uuid: UUID de l'appel
            user_input: Question/remarque du prospect
            context: Contexte campagne
            prompt_type: Type de prompt

        Returns:
            Réponse complète avec question de retour

        Example:
            Input: "C'est trop cher pour moi"
            Output: "Je comprends votre préoccupation. En réalité, nos clients
                     économisent en moyenne 30% sur leurs coûts actuels.
                     Ça vous rassure un peu ?"
        """
        # 1. Générer réponse principale
        main_response = self.generate_response(
            call_uuid=call_uuid,
            user_input=user_input,
            context=context,
            prompt_type=prompt_type
        )

        # 2. Ajouter question de retour au rail
        rail_question = self.generate_rail_return_question(prompt_type)

        # 3. Combiner (avec espace si besoin)
        if main_response.endswith((".", "!", "?")):
            combined = f"{main_response} {rail_question}"
        else:
            combined = f"{main_response}. {rail_question}"

        logger.info(f"Freestyle with rail return: {combined[:80]}...")

        return combined

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques freestyle"""
        cache_hit_rate = (
            (self.stats["cache_hits"] / self.stats["total_requests"] * 100)
            if self.stats["total_requests"] > 0 else 0
        )

        success_rate = (
            (self.stats["successful_generations"] / self.stats["total_requests"] * 100)
            if self.stats["total_requests"] > 0 else 0
        )

        return {
            **self.stats,
            "is_available": self.is_available,
            "cache_hit_rate_pct": round(cache_hit_rate, 1),
            "success_rate_pct": round(success_rate, 1),
            "cache_size": len(self._cache),
            "active_conversations": len(self._conversations),
            "model": self.config["model"]
        }

    def clear_all_cache(self):
        """Nettoie tout le cache"""
        self._cache.clear()
        logger.info("Freestyle cache cleared")

    def clear_all_conversations(self):
        """Nettoie tous les historiques"""
        self._conversations.clear()
        logger.info("All conversation histories cleared")
