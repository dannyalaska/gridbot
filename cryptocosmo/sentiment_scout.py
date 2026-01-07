import time
from dataclasses import dataclass


@dataclass
class SentimentSnapshot:
    score: float
    label: str
    news_risk: str
    timestamp: float


class SentimentScout:
    def __init__(self):
        self.last_snapshot: SentimentSnapshot | None = None

    def fetch(self) -> SentimentSnapshot:
        # Placeholder: hook up to a real sentiment feed or fear/greed index later.
        snapshot = SentimentSnapshot(score=0.0, label="neutral", news_risk="low", timestamp=time.time())
        self.last_snapshot = snapshot
        return snapshot

