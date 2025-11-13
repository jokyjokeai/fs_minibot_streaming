# -*- coding: utf-8 -*-
"""
AMD Service - MiniBotPanel v3

Answering Machine Detection via Keywords Matching
Fast and reliable detection HUMAN vs MACHINE
Target latency: 10-30ms
"""

import logging
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher
from unidecode import unidecode
from system.config import config

logger = logging.getLogger(__name__)


class AMDService:
    """AMD Detection Service using keywords matching"""

    def __init__(
        self,
        keywords_human: Optional[List[str]] = None,
        keywords_machine: Optional[List[str]] = None,
        min_confidence: float = 0.5
    ):
        self.keywords_human = keywords_human or config.AMD_KEYWORDS_HUMAN
        self.keywords_machine = keywords_machine or config.AMD_KEYWORDS_MACHINE
        self.min_confidence = min_confidence

        # Normalize keywords (lowercase + remove accents with unidecode)
        self.keywords_human = [unidecode(k.lower()) for k in self.keywords_human]
        self.keywords_machine = [unidecode(k.lower()) for k in self.keywords_machine]

        logger.info(
            f"AMD Service init: "
            f"{len(self.keywords_human)} HUMAN keywords, "
            f"{len(self.keywords_machine)} MACHINE keywords"
        )

    def detect(self, transcription: str) -> Dict[str, Any]:
        """
        Detect if transcription is HUMAN or MACHINE

        Returns:
            {
                "result": "HUMAN" | "MACHINE" | "UNKNOWN",
                "confidence": 0.0-1.0,
                "keywords_matched": [...],
                "method": "keywords_matching"
            }
        """
        if not transcription or not transcription.strip():
            logger.warning("AMD: Empty transcription")
            return {
                "result": "UNKNOWN",
                "confidence": 0.0,
                "keywords_matched": [],
                "method": "keywords_matching"
            }

        # Normalize (lowercase + remove accents)
        text_normalized = unidecode(transcription.lower().strip())

        # Match keywords (exact match first)
        human_matches = self._match_keywords(text_normalized, self.keywords_human)
        machine_matches = self._match_keywords(text_normalized, self.keywords_machine)

        # If no matches, try fuzzy matching (fallback)
        if not human_matches and not machine_matches:
            logger.debug(f"AMD: No exact match, trying fuzzy matching...")
            human_matches = self._match_keywords_fuzzy(text_normalized, self.keywords_human, threshold=0.85)
            machine_matches = self._match_keywords_fuzzy(text_normalized, self.keywords_machine, threshold=0.85)

        # Calculate scores
        human_score = len(human_matches)
        machine_score = len(machine_matches)

        # Determine result - PRIORITIZE MACHINE DETECTION
        # Strategy: If any MACHINE keyword found → always return MACHINE
        # Reason: Answering machines often say "bonjour" (HUMAN keyword)
        #         but presence of "repondeur", "messagerie", etc. is definitive
        if machine_score > 0:
            # MACHINE has absolute priority (safer to hangup on machine than stay)
            result = "MACHINE"
            confidence = self._calculate_confidence(machine_score, len(self.keywords_machine))
            keywords_matched = machine_matches
        elif human_score > 0:
            # Only if NO machine keywords, check human keywords
            result = "HUMAN"
            confidence = self._calculate_confidence(human_score, len(self.keywords_human))
            keywords_matched = human_matches
        else:
            # No keywords matched at all
            result = "UNKNOWN"
            confidence = 0.0
            keywords_matched = []

        # Check min confidence
        if confidence < self.min_confidence:
            logger.warning(
                f"AMD: Low confidence ({confidence:.2f}) -> UNKNOWN"
            )
            result = "UNKNOWN"

        logger.info(
            f"AMD: {result} "
            f"(conf: {confidence:.2f}, "
            f"keywords: {keywords_matched[:3]})"
        )

        return {
            "result": result,
            "confidence": confidence,
            "keywords_matched": keywords_matched,
            "method": "keywords_matching",
            "human_score": human_score,
            "machine_score": machine_score
        }

    def _match_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """
        Find all keywords present in text (exact substring match)

        Args:
            text: Normalized text (already lowercase + unidecode)
            keywords: Normalized keywords (already lowercase + unidecode)

        Returns:
            List of matched keywords
        """
        matches = []
        for keyword in keywords:
            if keyword in text:
                matches.append(keyword)
        return matches

    def _match_keywords_fuzzy(
        self,
        text: str,
        keywords: List[str],
        threshold: float = 0.85
    ) -> List[str]:
        """
        Match keywords with fuzzy matching (fallback if exact match fails)

        Uses difflib SequenceMatcher to find similar words.
        Useful for typos, slight variations, phonetic errors.

        Args:
            text: Normalized text (already lowercase + unidecode)
            keywords: Normalized keywords (already lowercase + unidecode)
            threshold: Similarity threshold (0.0-1.0), default 0.85

        Returns:
            List of matched keywords

        Examples:
            - "alo" (typo) → matches "allo" (ratio ~0.88)
            - "mesagerie" (typo) → matches "messagerie" (ratio ~0.90)
        """
        matches = []
        words = text.split()

        for keyword in keywords:
            # For multi-word keywords, check if phrase exists
            if ' ' in keyword:
                if keyword in text:
                    matches.append(keyword)
                continue

            # For single-word keywords, check fuzzy similarity
            for word in words:
                ratio = SequenceMatcher(None, word, keyword).ratio()
                if ratio >= threshold:
                    matches.append(keyword)
                    logger.debug(f"AMD: Fuzzy match '{word}' → '{keyword}' (ratio: {ratio:.2f})")
                    break

        return matches

    def _calculate_confidence(self, matches_count: int, total_keywords: int) -> float:
        """
        Calculate confidence score

        Rules:
        - 1 keyword = 0.6
        - 2 keywords = 0.8
        - 3+ keywords = 0.95
        """
        if matches_count == 0:
            return 0.0
        elif matches_count == 1:
            return 0.6
        elif matches_count == 2:
            return 0.8
        else:  # 3+
            return 0.95

    def get_stats(self) -> Dict[str, Any]:
        """Return AMD service stats"""
        return {
            "keywords_human_count": len(self.keywords_human),
            "keywords_machine_count": len(self.keywords_machine),
            "min_confidence": self.min_confidence,
            "keywords_human_preview": self.keywords_human[:5],
            "keywords_machine_preview": self.keywords_machine[:5]
        }


# Global instance
amd_service = AMDService()


# Unit tests
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("AMD Service - Unit Tests")
    print("=" * 80)

    amd = AMDService()
    stats = amd.get_stats()
    
    print(f"\nStats:")
    print(f"  - Keywords HUMAN: {stats['keywords_human_count']}")
    print(f"  - Keywords MACHINE: {stats['keywords_machine_count']}")

    # Test cases
    test_cases = [
        ("Allo, oui bonjour", "HUMAN"),
        ("Oui j'ecoute", "HUMAN"),
        ("Vous etes sur le repondeur de Jean", "MACHINE"),
        ("Messagerie vocale, laissez un message", "MACHINE"),
        ("", "UNKNOWN"),
    ]

    print("\nTests:")
    passed = 0
    failed = 0

    for transcription, expected in test_cases:
        result = amd.detect(transcription)
        status = "PASS" if result["result"] == expected else "FAIL"
        
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"[{status}] '{transcription[:30]}' -> {result['result']} (conf: {result['confidence']:.2f})")

    print(f"\nResults: {passed} PASS, {failed} FAIL")
    
    if failed == 0:
        print("SUCCESS!")
