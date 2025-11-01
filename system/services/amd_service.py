"""
AMD Service - MiniBotPanel v3

Service de détection de répondeur (Answering Machine Detection).

Architecture Dual Layer:
- Niveau 1: AMD FreeSWITCH (rapide, filtrage grossier)
- Niveau 2: AMD Python Vosk (précis, analyse fine)

Fonctionnalités:
- Détection répondeur en <6 secondes
- Analyse mots-clés typiques répondeur
- Analyse durée parole
- Score de confiance

Utilisation:
    from system.services.amd_service import AMDService

    amd = AMDService()
    result = amd.analyze_audio(audio_file)
    # result = {"is_machine": True, "confidence": 0.95, "reason": "keywords"}
"""

import logging
import re
from typing import Dict, Any
from system.config import config
from system.logger import get_logger

logger = get_logger(__name__)

class AMDService:
    """
    Service AMD dual layer pour détection répondeur.

    Combine détection FreeSWITCH (rapide) et analyse Python (précise).
    """

    def __init__(self):
        logger.info("Initializing AMDService...")
        self.is_available = config.AMD_ENABLED

        # Mots-clés typiques de répondeurs (français)
        self.machine_keywords = [
            r"\bbonjour\s+(vous\s+êtes\s+bien\s+)?au\s+",  # "bonjour vous êtes bien au..."
            r"\bvous\s+êtes\s+bien\s+au\b",
            r"\bmerci\s+d'avoir\s+appelé\b",
            r"\blaissez\s+un\s+message\b",
            r"\blaissez\s+votre\s+message\b",
            r"\bveuillez\s+laisser\b",
            r"\blaissez\s+vos\s+coordonnées\b",
            r"\baprès\s+le\s+bip\b",
            r"\baprès\s+le\s+signal\s+sonore\b",
            r"\brappelez\s+nous\s+au\b",
            r"\bne\s+quittez\s+pas\b.*\bmise\s+en\s+attente\b",
            r"\bbienvenue\s+chez\b",
            r"\bvous\s+pouvez\s+laisser\b",
            r"\bnotre\s+bureau\s+est\s+fermé\b",
            r"\bnotre\s+société\s+est\s+fermée\b",
            r"\bnous\s+sommes\s+absents\b",
        ]

        # Durée typique messages répondeur (> 10 secondes de parole continue)
        self.machine_min_duration = 10.0  # secondes

        logger.info(f"{'✅' if self.is_available else '❌'} AMDService initialized")

    def analyze_freeswitch_result(self, amd_result: str) -> Dict[str, Any]:
        """
        Analyse résultat AMD FreeSWITCH.

        Args:
            amd_result: Résultat AMD FS ("MACHINE", "HUMAN", "UNKNOWN")

        Returns:
            Dict avec is_machine, confidence, method
        """
        if amd_result == "MACHINE":
            return {"is_machine": True, "confidence": 0.8, "method": "freeswitch"}
        elif amd_result == "HUMAN":
            return {"is_machine": False, "confidence": 0.7, "method": "freeswitch"}
        else:
            return {"is_machine": None, "confidence": 0.0, "method": "freeswitch"}

    def analyze_audio_python(self, transcription: str, duration: float) -> Dict[str, Any]:
        """
        Analyse Python (niveau 2) basée sur transcription et durée.

        Détecte répondeur via:
        1. Mots-clés typiques ("laissez un message", "après le bip", etc.)
        2. Durée parole continue (> 10 sec = suspect)
        3. Combinaison des deux pour score confiance

        Args:
            transcription: Texte transcrit des premières secondes
            duration: Durée parole en secondes

        Returns:
            Dict avec is_machine, confidence, reason, method
        """
        if not transcription:
            return {
                "is_machine": None,
                "confidence": 0.0,
                "reason": "no_transcription",
                "method": "python"
            }

        transcription_lower = transcription.lower()

        # 1. Analyser mots-clés
        keyword_matches = []
        for pattern in self.machine_keywords:
            if re.search(pattern, transcription_lower, re.IGNORECASE):
                keyword_matches.append(pattern)

        keyword_score = len(keyword_matches) / len(self.machine_keywords)

        # 2. Analyser durée parole
        # Répondeur typique: parole continue > 10 secondes
        duration_score = 0.0
        if duration > self.machine_min_duration:
            # Plus c'est long, plus c'est suspect
            duration_score = min((duration - self.machine_min_duration) / 10.0, 1.0)

        # 3. Calculer score confiance global
        # Pondération: keywords (70%), duration (30%)
        confidence = (keyword_score * 0.7) + (duration_score * 0.3)

        # Déterminer is_machine avec seuil 0.5
        is_machine = confidence >= 0.5

        # Raison principale
        if keyword_matches:
            reason = f"keywords_matched ({len(keyword_matches)})"
        elif duration > self.machine_min_duration:
            reason = f"long_duration ({duration:.1f}s)"
        else:
            reason = "human_like"

        result = {
            "is_machine": is_machine,
            "confidence": round(confidence, 2),
            "reason": reason,
            "method": "python",
            "details": {
                "keyword_score": round(keyword_score, 2),
                "duration_score": round(duration_score, 2),
                "keyword_matches": len(keyword_matches),
                "duration": duration
            }
        }

        logger.debug(f"AMD Python analysis: is_machine={is_machine}, "
                    f"confidence={confidence:.2f}, reason={reason}")

        return result

    def analyze_combined(
        self,
        freeswitch_result: str,
        transcription: str = None,
        duration: float = 0.0
    ) -> Dict[str, Any]:
        """
        Analyse combinée FreeSWITCH + Python pour décision finale.

        Args:
            freeswitch_result: Résultat AMD FreeSWITCH
            transcription: Transcription audio (optionnel)
            duration: Durée parole (optionnel)

        Returns:
            Dict avec décision finale is_machine, confidence, method
        """
        # Analyse niveau 1 (FreeSWITCH)
        fs_result = self.analyze_freeswitch_result(freeswitch_result)

        # Si FreeSWITCH est confiant (> 0.9) et dit MACHINE, on valide
        if fs_result["is_machine"] and fs_result["confidence"] >= 0.9:
            return fs_result

        # Sinon, analyse niveau 2 (Python) si transcription disponible
        if transcription and duration > 0:
            py_result = self.analyze_audio_python(transcription, duration)

            # Combinaison: moyenne pondérée FS (40%) + Python (60%)
            combined_confidence = (fs_result.get("confidence", 0) * 0.4) + (py_result["confidence"] * 0.6)

            is_machine = combined_confidence >= 0.5

            return {
                "is_machine": is_machine,
                "confidence": round(combined_confidence, 2),
                "method": "combined",
                "freeswitch": fs_result,
                "python": py_result
            }

        # Fallback: utiliser uniquement résultat FreeSWITCH
        return fs_result
