#!/usr/bin/env python3
"""
Objection Matcher - MiniBotPanel v3

Système de matching rapide et intelligent pour détecter les objections
dans les réponses du prospect et les associer aux objections pré-enregistrées.

Utilise plusieurs techniques :
- Fuzzy matching (difflib) pour similarité textuelle
- Mots-clés extraits pour matching rapide
- Score de confiance pour décider entre pré-enregistré vs Freestyle

Phase 6+ : Support ObjectionEntry avec audio_path
- Charge automatiquement objections GENERAL + thématique
- Retourne audio_path si disponible (fallback TTS si manquant)
- Cache intelligent par thématique

Usage (ancien format dict):
    matcher = ObjectionMatcher({"Pas intéressé": "Je comprends..."})
    match = matcher.find_best_match("Pas intéressé franchement")

Usage Phase 6+ (avec thématique):
    matcher = ObjectionMatcher.load_objections_for_theme("finance")
    match = matcher.find_best_match("C'est trop cher", min_score=0.7)

    if match:
        print(f"Objection: {match['objection']}")
        print(f"Réponse: {match['response']}")
        print(f"Audio: {match['audio_path']}")  # Nouveau Phase 6+
        print(f"Score: {match['score']:.2f}")
"""

import re
from typing import Dict, Optional, List, Tuple, Union
from difflib import SequenceMatcher
import logging

# Import ObjectionEntry pour support Phase 6
try:
    from system.objections_database import ObjectionEntry, get_objections_by_theme, get_all_themes
    OBJECTIONS_DB_AVAILABLE = True
except ImportError:
    OBJECTIONS_DB_AVAILABLE = False
    ObjectionEntry = None

# Phase 8: CacheManager pour cache objections par thématique
from system.cache_manager import get_cache

logger = logging.getLogger(__name__)


class ObjectionMatcher:
    """
    Matcher intelligent pour détecter rapidement les objections

    Supporte deux formats:
    1. Dict classique: {objection_text: response_text}
    2. Liste ObjectionEntry (Phase 6+): avec keywords, response, audio_path
    """

    def __init__(self, objections_input: Union[Dict[str, str], List['ObjectionEntry']]):
        """
        Initialize matcher avec dictionnaire d'objections OU liste ObjectionEntry.

        Args:
            objections_input:
                - Dict {objection_text: response_text} (ancien format)
                - List[ObjectionEntry] (nouveau format Phase 6+)
        """
        # Convertir ObjectionEntry en format interne unifié
        self.objections = {}  # {keywords_joined: response}
        self.audio_paths = {}  # {keywords_joined: audio_path}
        self.objection_keys = []

        if isinstance(objections_input, dict):
            # Ancien format dict
            self.objections = objections_input
            self.objection_keys = list(objections_input.keys())
            self.audio_paths = {k: None for k in self.objection_keys}
            logger.info(f"ObjectionMatcher initialized with dict (legacy format)")

        elif isinstance(objections_input, list) and OBJECTIONS_DB_AVAILABLE:
            # Nouveau format ObjectionEntry
            for entry in objections_input:
                if isinstance(entry, ObjectionEntry):
                    # Utiliser keywords comme clé (joinés)
                    key = " | ".join(entry.keywords)
                    self.objections[key] = entry.response
                    self.audio_paths[key] = entry.audio_path
                    self.objection_keys.append(key)
            logger.info(f"ObjectionMatcher initialized with {len(self.objections)} ObjectionEntry")
        else:
            logger.warning("Invalid objections_input format, initializing empty matcher")
            self.objection_keys = []

        # Pré-calculer les mots-clés pour chaque objection (optimisation)
        self.keywords_map = {}
        for objection in self.objection_keys:
            self.keywords_map[objection] = self._extract_keywords(objection)

        logger.info(f"ObjectionMatcher ready with {len(self.objections)} objections")

    @staticmethod
    def load_objections_for_theme(theme: str = "general") -> Optional['ObjectionMatcher']:
        """
        Charge les objections pour une thématique spécifique (GENERAL + thématique).

        Phase 8: Utilise CacheManager pour cache intelligent avec TTL + LRU.

        Cette méthode facilite l'initialisation du matcher avec les objections
        de la database filtrées par thématique. Elle charge automatiquement:
        - Les objections GENERAL (toujours incluses)
        - Les objections spécifiques à la thématique (si fournie)

        Args:
            theme: Thématique à charger ("general", "finance", "crypto", "energie", etc.)
                   Si "general", charge uniquement les objections générales.

        Returns:
            ObjectionMatcher initialisé ou None si erreur

        Example:
            >>> matcher = ObjectionMatcher.load_objections_for_theme("finance")
            >>> match = matcher.find_best_match("C'est trop cher")
            >>> if match:
            ...     print(match['response'])
            ...     if match['audio_path']:
            ...         play_audio(match['audio_path'])
        """
        if not OBJECTIONS_DB_AVAILABLE:
            logger.error("❌ objections_database.py not available, cannot load objections")
            return None

        # Phase 8: Check CacheManager global
        cache = get_cache()
        cached_objections = cache.get_objections(theme)

        if cached_objections:
            logger.debug(f"Objections '{theme}' loaded from CacheManager (hit)")
            return ObjectionMatcher(cached_objections)

        try:
            # Charger objections pour la thématique (inclut GENERAL automatiquement)
            objections_list = get_objections_by_theme(theme)

            if not objections_list:
                logger.warning(f"⚠️  No objections found for theme '{theme}'")
                return None

            logger.info(f"📚 Loaded {len(objections_list)} objections for theme '{theme}'")

            # Phase 8: Mettre en cache via CacheManager
            cache.set_objections(theme, objections_list)

            # Créer et retourner le matcher
            return ObjectionMatcher(objections_list)

        except Exception as e:
            logger.error(f"❌ Error loading objections for theme '{theme}': {e}")
            return None

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extrait les mots-clés significatifs d'un texte.

        Retire les mots vides (le, la, de, etc.) et garde les mots importants.
        """
        # Normaliser
        text = text.lower().strip()

        # Mots vides français courants
        stopwords = {
            'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'ce', 'cette', 'ces',
            'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa', 'ses',
            'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
            'suis', 'es', 'est', 'sommes', 'êtes', 'sont',
            'ai', 'as', 'a', 'avons', 'avez', 'ont',
            'pour', 'dans', 'sur', 'avec', 'sans', 'par',
            'que', 'qui', 'quoi', 'dont', 'où',
            'et', 'ou', 'mais', 'donc', 'car', 'ni'
        }

        # Extraire mots alphanumérique
        words = re.findall(r'\b[a-zàâäéèêëïîôùûüÿçæœ]{3,}\b', text)

        # Filtrer stopwords
        keywords = [w for w in words if w not in stopwords]

        return keywords

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule similarité entre deux textes (0.0 à 1.0).

        Utilise SequenceMatcher de difflib (algorithme Ratcliff-Obershelp).
        """
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        return SequenceMatcher(None, text1, text2).ratio()

    def _calculate_keyword_overlap(self, input_keywords: List[str], objection_keywords: List[str]) -> float:
        """
        Calcule le score de chevauchement de mots-clés (0.0 à 1.0).

        Plus il y a de mots-clés communs, plus le score est élevé.
        """
        if not input_keywords or not objection_keywords:
            return 0.0

        # Intersection des mots-clés
        common = set(input_keywords) & set(objection_keywords)

        # Score = nombre communs / max(len1, len2)
        max_len = max(len(input_keywords), len(objection_keywords))

        return len(common) / max_len if max_len > 0 else 0.0

    def _hybrid_score(self, input_text: str, objection_text: str) -> float:
        """
        Score hybride combinant similarité textuelle et chevauchement mots-clés.

        70% similarité textuelle + 30% chevauchement mots-clés.
        """
        # Similarité textuelle globale
        text_similarity = self._calculate_similarity(input_text, objection_text)

        # Chevauchement mots-clés
        input_keywords = self._extract_keywords(input_text)
        objection_keywords = self.keywords_map[objection_text]
        keyword_overlap = self._calculate_keyword_overlap(input_keywords, objection_keywords)

        # Pondération : 70% texte, 30% mots-clés
        hybrid_score = (0.7 * text_similarity) + (0.3 * keyword_overlap)

        return hybrid_score

    def find_best_match(
        self,
        user_input: str,
        min_score: float = 0.5,
        top_n: int = 3
    ) -> Optional[Dict]:
        """
        Trouve la meilleure objection correspondant à l'input utilisateur.

        Args:
            user_input: Ce que le prospect a dit
            min_score: Score minimum pour considérer un match (0.0-1.0)
            top_n: Nombre de candidats à évaluer en détail

        Returns:
            Dict avec {objection, response, score, method} ou None si pas de match
        """
        if not user_input or not user_input.strip():
            return None

        user_input = user_input.strip()

        # Étape 1: Calcul rapide des scores pour toutes les objections
        scores = []
        for objection in self.objection_keys:
            score = self._hybrid_score(user_input, objection)
            scores.append((objection, score))

        # Trier par score décroissant
        scores.sort(key=lambda x: x[1], reverse=True)

        # Prendre les top_n meilleurs
        top_matches = scores[:top_n]

        # Log des top matches pour debug
        logger.debug(f"Input: '{user_input}'")
        for obj, score in top_matches:
            logger.debug(f"  → '{obj}': {score:.2f}")

        # Vérifier si le meilleur match dépasse le seuil
        best_objection, best_score = top_matches[0]

        if best_score >= min_score:
            logger.info(f"✅ Match trouvé: '{best_objection}' (score: {best_score:.2f})")
            return {
                "objection": best_objection,
                "response": self.objections[best_objection],
                "audio_path": self.audio_paths.get(best_objection),  # Phase 6: support audio_path
                "score": best_score,
                "method": "hybrid",
                "confidence": "high" if best_score >= 0.8 else "medium"
            }
        else:
            logger.info(f"❌ Pas de match suffisant (meilleur: {best_score:.2f} < {min_score})")
            return None

    def find_all_matches(
        self,
        user_input: str,
        min_score: float = 0.6,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Trouve toutes les objections correspondant au-dessus du seuil.

        Utile pour afficher plusieurs options ou logs.

        Args:
            user_input: Input prospect
            min_score: Score minimum
            max_results: Nombre max de résultats

        Returns:
            Liste de dicts [{objection, response, score}, ...]
        """
        if not user_input or not user_input.strip():
            return []

        user_input = user_input.strip()

        # Calculer scores pour toutes
        results = []
        for objection in self.objection_keys:
            score = self._hybrid_score(user_input, objection)

            if score >= min_score:
                results.append({
                    "objection": objection,
                    "response": self.objections[objection],
                    "audio_path": self.audio_paths.get(objection),  # Phase 6: support audio_path
                    "score": score,
                    "confidence": "high" if score >= 0.8 else "medium" if score >= 0.7 else "low"
                })

        # Trier par score décroissant
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:max_results]

    def get_stats(self) -> Dict:
        """Retourne statistiques du matcher."""
        return {
            "total_objections": len(self.objections),
            "objections_list": list(self.objection_keys)[:10],  # 10 premières pour preview
            "avg_keywords_per_objection": sum(len(kw) for kw in self.keywords_map.values()) / len(self.keywords_map) if self.keywords_map else 0
        }


# ═══════════════════════════════════════════════════════════════════════════
# Tests unitaires
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Test ObjectionMatcher - MiniBotPanel v3\n")

    # Objections de test
    test_objections = {
        "Je n'ai pas le temps": "Je comprends parfaitement, vous êtes occupé. C'est justement pour ça que je vous appelle maintenant - on peut faire ça en 2 minutes chrono.",
        "Pas intéressé": "Je comprends que dit comme ça, ça ne vous parle pas. Mais justement, est-ce que je peux vous poser UNE question rapide ?",
        "C'est trop cher": "Je comprends la question du budget. Mais justement, vous payez combien actuellement ? Parce que nos clients économisent en moyenne 30 à 40%.",
        "J'ai déjà une banque": "C'est parfait, la majorité de nos clients avaient déjà une banque ! L'idée c'est pas de tout changer.",
        "Je dois réfléchir": "Tout à fait, c'est normal de prendre le temps de réfléchir. Qu'est-ce qui vous fait hésiter précisément ?"
    }

    matcher = ObjectionMatcher(test_objections)

    # Test 1: Match exact
    print("Test 1: Match exact")
    result = matcher.find_best_match("Je n'ai pas le temps")
    print(f"  Input: 'Je n'ai pas le temps'")
    print(f"  Match: {result['objection'] if result else 'Aucun'}")
    print(f"  Score: {result['score']:.2f}" if result else "  Score: N/A")
    print(f"  ✅ PASS\n" if result and result['score'] > 0.9 else "  ❌ FAIL\n")

    # Test 2: Variante proche
    print("Test 2: Variante proche")
    result = matcher.find_best_match("Désolé mais j'ai vraiment pas le temps là")
    print(f"  Input: 'Désolé mais j'ai vraiment pas le temps là'")
    print(f"  Match: {result['objection'] if result else 'Aucun'}")
    print(f"  Score: {result['score']:.2f}" if result else "  Score: N/A")
    print(f"  ✅ PASS\n" if result and "temps" in result['objection'].lower() else "  ❌ FAIL\n")

    # Test 3: Reformulation
    print("Test 3: Reformulation")
    result = matcher.find_best_match("Ça m'intéresse pas du tout")
    print(f"  Input: 'Ça m'intéresse pas du tout'")
    print(f"  Match: {result['objection'] if result else 'Aucun'}")
    print(f"  Score: {result['score']:.2f}" if result else "  Score: N/A")
    print(f"  ✅ PASS\n" if result and "intéressé" in result['objection'].lower() else "  ❌ FAIL\n")

    # Test 4: Prix
    print("Test 4: Mots-clés prix")
    result = matcher.find_best_match("C'est hors de prix votre truc")
    print(f"  Input: 'C'est hors de prix votre truc'")
    print(f"  Match: {result['objection'] if result else 'Aucun'}")
    print(f"  Score: {result['score']:.2f}" if result else "  Score: N/A")
    print(f"  ✅ PASS\n" if result and "cher" in result['objection'].lower() else "  ❌ FAIL\n")

    # Test 5: Aucun match
    print("Test 5: Aucun match (input hors sujet)")
    result = matcher.find_best_match("Quel temps fait-il aujourd'hui ?")
    print(f"  Input: 'Quel temps fait-il aujourd'hui ?'")
    print(f"  Match: {result['objection'] if result else 'Aucun'}")
    print(f"  ✅ PASS\n" if not result else "  ❌ FAIL (ne devrait pas matcher)\n")

    # Test 6: Top 3 matches
    print("Test 6: Trouver top 3 matches")
    results = matcher.find_all_matches("Je suis déjà client ailleurs", min_score=0.3, max_results=3)
    print(f"  Input: 'Je suis déjà client ailleurs'")
    print(f"  Résultats trouvés: {len(results)}")
    for i, res in enumerate(results, 1):
        print(f"    {i}. {res['objection']} (score: {res['score']:.2f})")
    print(f"  ✅ PASS\n" if results else "  ⚠️  Aucun résultat\n")

    # Stats
    print("Stats du matcher:")
    stats = matcher.get_stats()
    print(f"  • Total objections: {stats['total_objections']}")
    print(f"  • Mots-clés moyens: {stats['avg_keywords_per_objection']:.1f} par objection")

    print("\n✅ Tests terminés")
