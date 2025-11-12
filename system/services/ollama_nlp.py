# -*- coding: utf-8 -*-
"""
Ollama NLP Service - MiniBotPanel v3

Sentiment Analysis ONLY (NO intent detection)
Intent detection = keywords matching (faster)
"""

import logging
import time
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class OllamaNLP:
    """
    Ollama NLP Service for Sentiment Analysis ONLY

    NOTE: Intent detection is done via keywords matching (faster)
    Ollama is used ONLY for sentiment analysis (optional, non-blocking)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:7b",
        timeout: float = 5.0,
        enabled: bool = False
    ):
        """
        Initialize Ollama NLP

        Args:
            base_url: Ollama API URL
            model: Model name
            timeout: Request timeout (seconds)
            enabled: Enable/disable sentiment analysis
        """
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.enabled = enabled

        if not self.enabled:
            logger.info("Ollama NLP DISABLED (sentiment analysis optional)")
            return

        logger.info(
            f"Ollama NLP init: "
            f"model={model}, url={base_url}, timeout={timeout}s"
        )

        # Test connection
        self._test_connection()

    def _test_connection(self):
        """Test Ollama connection"""
        try:
            import requests

            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=2.0
            )

            if response.status_code == 200:
                logger.info("Ollama connection OK")
            else:
                logger.warning(f"Ollama connection issue: {response.status_code}")
                self.enabled = False

        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self.enabled = False

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text

        Args:
            text: Text to analyze

        Returns:
            {
                "sentiment": "positive" | "negative" | "neutral",
                "confidence": 0.0-1.0,
                "latency_ms": 200.0
            }
        """
        if not self.enabled:
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "latency_ms": 0.0,
                "disabled": True
            }

        if not text or not text.strip():
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "latency_ms": 0.0
            }

        try:
            import requests

            start_time = time.time()

            # Prompt for sentiment analysis
            prompt = f"""Analyse le sentiment de ce texte et reponds UNIQUEMENT par un mot: positive, negative, ou neutral.

Texte: "{text}"

Sentiment:"""

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                result = response.json()
                sentiment_text = result.get("response", "").strip().lower()

                # Parse sentiment
                if "positive" in sentiment_text or "positif" in sentiment_text:
                    sentiment = "positive"
                    confidence = 0.8
                elif "negative" in sentiment_text or "negatif" in sentiment_text:
                    sentiment = "negative"
                    confidence = 0.8
                else:
                    sentiment = "neutral"
                    confidence = 0.6

                logger.info(
                    f"Sentiment: {sentiment} "
                    f"(conf: {confidence:.2f}, latency: {latency_ms:.0f}ms)"
                )

                return {
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "latency_ms": latency_ms
                }
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {
                    "sentiment": "neutral",
                    "confidence": 0.0,
                    "latency_ms": latency_ms,
                    "error": f"api_error_{response.status_code}"
                }

        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "latency_ms": 0.0,
                "error": str(e)
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return Ollama service stats"""
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout
        }


# Unit tests
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("Ollama NLP - Unit Tests")
    print("=" * 80)

    # Test with disabled (default)
    ollama_disabled = OllamaNLP(enabled=False)
    print("\nTest 1: Disabled mode")
    result = ollama_disabled.analyze_sentiment("Je suis tres content!")
    print(f"  Sentiment: {result['sentiment']}")
    print(f"  Disabled: {result.get('disabled', False)}")
    print("  PASS" if result.get('disabled') else "  FAIL")

    # Test with enabled (requires Ollama running)
    print("\nTest 2: Enabled mode (requires Ollama)")
    ollama_enabled = OllamaNLP(enabled=True)
    
    if ollama_enabled.enabled:
        test_texts = [
            "Je suis tres content, c'est parfait!",
            "C'est nul, je deteste ca",
            "Ok d'accord"
        ]

        for text in test_texts:
            result = ollama_enabled.analyze_sentiment(text)
            print(f"  Text: '{text[:30]}...'")
            print(f"  Sentiment: {result['sentiment']} (latency: {result['latency_ms']:.0f}ms)")
    else:
        print("  SKIPPED - Ollama not available")

    print("\nNOTE: Ollama is OPTIONAL for this project")
    print("Intent detection uses keywords matching (faster)")
