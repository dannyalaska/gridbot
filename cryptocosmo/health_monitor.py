import logging
import time

from .config import AppConfig


class HealthMonitor:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.last_price_ts = time.time()
        self.error_streak = 0

    def record_price(self) -> None:
        self.last_price_ts = time.time()

    def record_error(self) -> None:
        self.error_streak += 1

    def reset_errors(self) -> None:
        self.error_streak = 0

    def healthy(self) -> bool:
        stale = time.time() - self.last_price_ts > self.cfg.health.max_stale_price_secs
        if stale:
            logging.warning("HealthMonitor: price feed stale")
        if self.error_streak >= self.cfg.health.max_error_streak:
            logging.warning("HealthMonitor: error streak %d exceeded", self.error_streak)
        return not stale and self.error_streak < self.cfg.health.max_error_streak

