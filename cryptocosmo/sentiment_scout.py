import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

# Free public API — no key required, updates once daily
_FNG_URL = "https://api.alternative.me/fng/?limit=1"
_CACHE_TTL_SECONDS = 1800  # refresh every 30 minutes


@dataclass
class SentimentSnapshot:
    score: float        # -1.0 (extreme fear) to +1.0 (extreme greed)
    label: str          # human-readable classification from the API
    news_risk: str      # "low" | "elevated" | "high" — consumed by LLMRiskAgent
    raw_value: int      # 0–100 Fear & Greed Index value
    timestamp: float


def _map_score(value: int) -> float:
    """Map 0–100 Fear & Greed value to -1.0 to +1.0."""
    return round((value - 50) / 50.0, 4)


def _map_news_risk(value: int) -> str:
    """
    Map index value to a news_risk level consumed by LLMRiskAgent.
    Extreme fear  (0–20)  = high     — market panic, unstable
    Fear          (21–39) = elevated
    Neutral/Greed (40–79) = low
    Extreme greed (80–100) = elevated — overheated, correction risk
    """
    if value <= 20:
        return "high"
    if value <= 39:
        return "elevated"
    if value >= 80:
        return "elevated"
    return "low"


class SentimentScout:
    def __init__(self):
        self.last_snapshot: Optional[SentimentSnapshot] = None
        self._last_fetch_time: float = 0.0

    def fetch(self) -> SentimentSnapshot:
        """
        Return a SentimentSnapshot from the Alternative.me Fear & Greed Index.
        Caches for 30 minutes to avoid hammering the API on every tick refresh.
        Falls back to last known snapshot (or neutral) on network/parse errors.
        """
        now = time.time()
        if self.last_snapshot and (now - self._last_fetch_time) < _CACHE_TTL_SECONDS:
            return self.last_snapshot

        try:
            resp = requests.get(_FNG_URL, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            entry = data["data"][0]
            raw_value = int(entry["value"])
            label = str(entry.get("value_classification", "Unknown"))

            snapshot = SentimentSnapshot(
                score=_map_score(raw_value),
                label=label,
                news_risk=_map_news_risk(raw_value),
                raw_value=raw_value,
                timestamp=now,
            )
            self.last_snapshot = snapshot
            self._last_fetch_time = now
            logging.info(
                "SentimentScout: Fear & Greed = %d (%s) | score=%.3f | news_risk=%s",
                raw_value,
                label,
                snapshot.score,
                snapshot.news_risk,
                extra={"action": "sentiment_fetch"},
            )
            return snapshot

        except requests.exceptions.RequestException as exc:
            logging.warning(
                "SentimentScout: network error fetching Fear & Greed index: %s — using fallback",
                exc,
                extra={"action": "sentiment_fetch_error"},
            )
        except (KeyError, IndexError, ValueError) as exc:
            logging.warning(
                "SentimentScout: unexpected API response shape: %s — using fallback",
                exc,
                extra={"action": "sentiment_parse_error"},
            )

        if self.last_snapshot:
            logging.info(
                "SentimentScout: returning stale snapshot (age=%.0fs)",
                now - self.last_snapshot.timestamp,
                extra={"action": "sentiment_stale"},
            )
            return self.last_snapshot

        logging.warning(
            "SentimentScout: no cached snapshot — defaulting to neutral",
            extra={"action": "sentiment_default"},
        )
        return SentimentSnapshot(
            score=0.0, label="neutral", news_risk="low", raw_value=50, timestamp=now
        )
