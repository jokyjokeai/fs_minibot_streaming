#!/usr/bin/env python3
"""
Objection Matcher - MiniBotPanel v3

Système de matching rapide et intelligent pour détecter les objections
dans les réponses du prospect et les associer aux objections pré-enregistrées.

Utilise plusieurs techniques :
- Fuzzy matching (difflib) pour similarité textuelle
- Mots-clés extraits pour matching rapide
- Score de confiance pour sélection de la meilleure réponse

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

# RapidFuzz pour matching ultra-rapide (5-10x plus rapide que difflib)
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

# Import ObjectionEntry pour support Phase 6 (nouveau système modulaire)
try:
    from system.objections_db import ObjectionEntry, load_objections, list_available_themes
    OBJECTIONS_DB_AVAILABLE = True
except ImportError:
    OBJECTIONS_DB_AVAILABLE = False
    ObjectionEntry = None
    logger.warning("objections_db module not available, objection matching will be disabled")

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
        self.entry_types = {}  # {keywords_joined: entry_type} (NEW: faq vs objection)
        self.objection_keys = []

        if isinstance(objections_input, dict):
            # Ancien format dict
            self.objections = objections_input
            self.objection_keys = list(objections_input.keys())
            self.audio_paths = {k: None for k in self.objection_keys}
            self.entry_types = {k: "objection" for k in self.objection_keys}  # Default to objection
            logger.info(f"ObjectionMatcher initialized with dict (legacy format)")

        elif isinstance(objections_input, list) and OBJECTIONS_DB_AVAILABLE:
            # Nouveau format ObjectionEntry
            for entry in objections_input:
                if isinstance(entry, ObjectionEntry):
                    # Utiliser keywords comme clé (joinés)
                    key = " | ".join(entry.keywords)
                    self.objections[key] = entry.response
                    self.audio_paths[key] = entry.audio_path
                    self.entry_types[key] = entry.entry_type  # NEW: Stocker entry_type (faq/objection)
                    self.objection_keys.append(key)
            logger.info(f"ObjectionMatcher initialized with {len(self.objections)} ObjectionEntry")
        else:
            logger.warning("Invalid objections_input format, initializing empty matcher")
            self.objection_keys = []

        # Pré-calculer les mots-clés pour chaque objection (optimisation)
        self.keywords_map = {}
        for objection in self.objection_keys:
            self.keywords_map[objection] = self._extract_keywords(objection)

        # LOOKUP DIRECT O(1) - Hashmap keyword -> objection_key
        # Pour matching instantané comme intents_db
        self.keyword_lookup = {}
        for objection_key in self.objection_keys:
            keywords = objection_key.split(" | ")
            for kw in keywords:
                kw_lower = kw.lower().strip()
                # Premier keyword gagne (priorité)
                if kw_lower not in self.keyword_lookup:
                    self.keyword_lookup[kw_lower] = objection_key

        logger.info(f"ObjectionMatcher ready with {len(self.objections)} objections, {len(self.keyword_lookup)} keywords indexed")

    @staticmethod
    def load_objections_from_file(theme_file: str) -> Optional['ObjectionMatcher']:
        """
        Charge les objections depuis un fichier de la nouvelle structure modulaire.

        Utilise le nouveau système: system/objections_db/{theme_file}.py
        Charge AUTOMATIQUEMENT objections_general.py + thématique choisie.

        Phase 8: Utilise CacheManager pour cache intelligent avec TTL + LRU.

        Args:
            theme_file: Nom du fichier (sans .py)
                       Ex: "objections_finance", "objections_crypto", "objections_energie"

        Returns:
            ObjectionMatcher initialisé ou None si erreur

        Example:
            >>> matcher = ObjectionMatcher.load_objections_from_file("objections_finance")
            >>> match = matcher.find_best_match("C'est trop cher")
            >>> if match:
            ...     print(match['response'])
            ...     play_audio(match['audio_path'])
        """
        try:
            # Import du nouveau système
            from system.objections_db import load_objections

            # Phase 8: Check CacheManager global
            cache = get_cache()
            cached_objections = cache.get_objections(theme_file)

            if cached_objections:
                logger.debug(f"Objections '{theme_file}' loaded from CacheManager (hit)")
                return ObjectionMatcher(cached_objections)

            # Charger depuis nouveau système (inclut GENERAL automatiquement)
            objections_list = load_objections(theme_file)

            if not objections_list:
                logger.warning(f"⚠️  No objections found in '{theme_file}'")
                return None

            logger.info(f"📚 Loaded {len(objections_list)} objections from '{theme_file}'")

            # Phase 8: Mettre en cache via CacheManager
            cache.set_objections(theme_file, objections_list)

            # Créer et retourner le matcher
            return ObjectionMatcher(objections_list)

        except ImportError as e:
            logger.error(f"❌ Cannot load objections from '{theme_file}': {e}")
            logger.error("💡 Make sure the file exists in system/objections_db/")
            return None
        except Exception as e:
            logger.error(f"❌ Error loading objections from '{theme_file}': {e}")
            return None

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
            # Note: load_objections attend "objections_finance" pas juste "finance"
            theme_file = theme if theme.startswith("objections_") else f"objections_{theme}"
            objections_list = load_objections(theme_file)

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
        top_n: int = 3,
        silent: bool = False
    ) -> Optional[Dict]:
        """
        Trouve la meilleure objection correspondant à l'input utilisateur.

        ALGORITHME AMÉLIORÉ: Teste chaque keyword individuellement au lieu
        de comparer avec la chaîne jointe. Cela permet de matcher "oui" avec
        le keyword "oui" directement, plutôt qu'avec "oui | ouais | ok | ..."

        Args:
            user_input: Ce que le prospect a dit
            min_score: Score minimum pour considérer un match (0.0-1.0)
            top_n: Nombre de candidats à évaluer en détail
            silent: Si True, désactive les logs INFO (utile pour warmup)

        Returns:
            Dict avec {objection, response, score, method, matched_keyword} ou None si pas de match
        """
        if not user_input or not user_input.strip():
            return None

        user_input = user_input.strip().lower()

        if not silent:
            logger.info(f"")
            logger.info(f"{'═'*60}")
            logger.info(f"🔍 OBJECTION MATCHER - ANALYSE DÉTAILLÉE")
            logger.info(f"{'═'*60}")
            logger.info(f"📝 Input: '{user_input}'")
            logger.info(f"⚙️  Config: min_score={min_score}, total_entries={len(self.objection_keys)}")
            logger.info(f"{'─'*60}")

        # ===== ÉTAPE 0: LOOKUP DIRECT O(1) - INSTANTANÉ =====
        # Comme intents_db - match exact immédiat
        if not silent:
            logger.info(f"🔎 ÉTAPE 1: Lookup direct (O(1))...")

        if user_input in self.keyword_lookup:
            objection_key = self.keyword_lookup[user_input]
            entry_type = self.entry_types.get(objection_key, "objection")
            if not silent:
                logger.info(f"   ✅ TROUVÉ! Keyword exact dans lookup table")
                logger.info(f"   → Entry: [{entry_type}] '{user_input}'")
                logger.info(f"{'─'*60}")
                logger.info(f"🏆 RÉSULTAT FINAL: [{entry_type}] '{user_input}'")
                logger.info(f"   Score: 1.00 | Méthode: direct_lookup | Len: {len(user_input)}")
                logger.info(f"{'═'*60}")
                logger.info(f"")
            return {
                "objection": objection_key,
                "response": self.objections[objection_key],
                "audio_path": self.audio_paths.get(objection_key),
                "entry_type": entry_type,
                "score": 1.0,
                "method": "direct_lookup",
                "matched_keyword": user_input,
                "confidence": "high"
            }

        # Étape 2: Fuzzy matching sur tous les keywords
        if not silent:
            logger.info(f"   ❌ Pas de match direct")
            logger.info(f"{'─'*60}")
            logger.info(f"🔎 ÉTAPE 2: Fuzzy matching (word boundary + RapidFuzz)...")

        scores = []
        word_boundary_matches = []  # Pour logger les matches word boundary

        for objection_key in self.objection_keys:
            # Séparer les keywords de cette objection
            keywords = objection_key.split(" | ")

            # Trouver le meilleur score parmi tous les keywords
            best_keyword_score = 0.0
            best_keyword = ""

            for keyword in keywords:
                keyword_lower = keyword.lower().strip()

                # Score 1: Match exact ou mot entier (word boundary)
                # Utilise regex pour éviter les faux positifs (ex: "ui" dans "suis")
                if keyword_lower == user_input:
                    score = 1.0
                else:
                    # Check if keyword appears as a whole word in input
                    pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                    if re.search(pattern, user_input):
                        score = 1.0
                        entry_type = self.entry_types.get(objection_key, "objection")
                        word_boundary_matches.append((keyword_lower, entry_type, len(keyword_lower)))
                    elif user_input in keyword_lower:
                        score = len(user_input) / len(keyword_lower)
                    else:
                        # Score 2: Similarité textuelle (fuzzy) - RapidFuzz pour performance
                        if RAPIDFUZZ_AVAILABLE:
                            score = fuzz.ratio(user_input, keyword_lower) / 100.0
                        else:
                            score = self._calculate_similarity(user_input, keyword_lower)

                if score > best_keyword_score:
                    best_keyword_score = score
                    best_keyword = keyword

            scores.append((objection_key, best_keyword_score, best_keyword))

        # Log word boundary matches found
        if not silent and word_boundary_matches:
            logger.info(f"   📍 Word boundary matches trouvés ({len(word_boundary_matches)}):")
            for kw, et, ln in sorted(word_boundary_matches, key=lambda x: -x[2])[:5]:
                logger.info(f"      • '{kw}' [{et}] (len={ln})")

        if not silent:
            logger.info(f"{'─'*60}")
            logger.info(f"🔎 ÉTAPE 3: Tri par score DESC, puis longueur DESC...")

        # Trier par: score DESC, puis longueur du keyword DESC
        # Le match le plus spécifique (plus long) gagne quand scores égaux
        def sort_key(x):
            obj_key, score, kw = x
            return (-score, -len(kw))  # Score DESC, longueur DESC

        scores.sort(key=sort_key)

        # Prendre les top_n meilleurs
        top_matches = scores[:top_n]

        # Vérifier si le meilleur match dépasse le seuil
        best_objection, best_score, matched_keyword = top_matches[0]

        # === LOGS DÉTAILLÉS TOP 5 ===
        if not silent:
            logger.info(f"   📊 TOP {min(5, len(top_matches))} après tri:")
            for i, (obj, score, kw) in enumerate(top_matches[:5], 1):
                entry_type = self.entry_types.get(obj, "objection")
                status = "✓" if score >= min_score else "✗"
                marker = "→" if i == 1 else " "
                logger.info(f"   {marker} {i}. [{entry_type}] '{kw}' (len={len(kw)}) = {score:.2f} {status}")

            # Expliquer pourquoi le gagnant a gagné
            if len(top_matches) >= 2:
                second_score = top_matches[1][1]
                second_kw = top_matches[1][2]
                if best_score == second_score:
                    logger.info(f"   💡 Raison: scores égaux ({best_score:.2f}), '{matched_keyword}' (len={len(matched_keyword)}) > '{second_kw}' (len={len(second_kw)})")
                else:
                    logger.info(f"   💡 Raison: score supérieur ({best_score:.2f} > {second_score:.2f})")

        if best_score >= min_score:
            # === FILTRE OVERLAP SÉMANTIQUE ===
            # Évite les faux positifs où le keyword n'a rien à voir avec l'input
            # Ex: "vacances" → "confiance", "allo" → "salope"
            if best_score < 1.0:  # Ne pas filtrer les matches exacts
                input_chars = set(user_input.lower().replace(" ", "").replace("'", ""))
                kw_chars = set(matched_keyword.lower().replace(" ", "").replace("'", ""))
                if len(input_chars) > 0 and len(kw_chars) > 0:
                    overlap = len(input_chars & kw_chars) / max(len(input_chars), len(kw_chars))
                    if overlap < 0.25 and best_score < 0.8:
                        if not silent:
                            logger.info(f"{'─'*60}")
                            logger.info(f"❌ REJETÉ: overlap sémantique trop faible")
                            logger.info(f"   Input chars: {len(input_chars)}, Keyword chars: {len(kw_chars)}")
                            logger.info(f"   Overlap: {overlap:.2f} < 0.25 (seuil)")
                            logger.info(f"{'═'*60}")
                            logger.info(f"")
                        return None

            entry_type = self.entry_types.get(best_objection, "objection")
            if not silent:
                logger.info(f"{'─'*60}")
                logger.info(f"🏆 RÉSULTAT FINAL: [{entry_type}] '{matched_keyword}'")
                logger.info(f"   Score: {best_score:.2f} | Méthode: fuzzy | Len: {len(matched_keyword)}")
                audio = self.audio_paths.get(best_objection)
                if audio:
                    logger.info(f"   Audio: {audio.split('/')[-1] if '/' in str(audio) else audio}")
                else:
                    logger.info(f"   Audio: (aucun - intent de navigation)")
                logger.info(f"{'═'*60}")
                logger.info(f"")
            return {
                "objection": best_objection,
                "response": self.objections[best_objection],
                "audio_path": self.audio_paths.get(best_objection),  # Phase 6: support audio_path
                "entry_type": entry_type,  # NEW: faq vs objection
                "score": best_score,
                "method": "keyword_match",
                "matched_keyword": matched_keyword,
                "confidence": "high" if best_score >= 0.8 else "medium",
                "top_alternatives": [(kw, score, self.entry_types.get(obj, "objection")) for obj, score, kw in top_matches[1:3]]
            }
        else:
            if not silent:
                logger.info(f"Result: ❌ NO MATCH (best: {best_score:.2f} < {min_score})")
                logger.info(f"═════════════════════════")
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
