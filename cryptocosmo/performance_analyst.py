import logging

from .config import AppConfig
from .grid_trader import GridTrader


class PerformanceAnalyst:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def maybe_adjust(self, tick: int, price: float, trader: GridTrader, sentiment_score: float = 0.0) -> None:
        if tick == 0 or tick % self.cfg.performance.adjust_interval_ticks != 0:
            return

        limit_pct = self.cfg.performance.center_shift_pct_limit / 100
        max_delta = trader.center * limit_pct
        desired_center = price * (1 + sentiment_score * self.cfg.sentiment.weight)
        bounded_center = min(trader.center + max_delta, max(trader.center - max_delta, desired_center))

        new_spacing = min(max(trader.spacing, self.cfg.performance.spacing_min), self.cfg.performance.spacing_max)
        trader.update_grid(center_price=bounded_center, spacing=new_spacing)
        logging.info(
            "PerformanceAnalyst adjusted grid center to %.2f (price %.2f, sentiment %.2f)",
            bounded_center,
            price,
            sentiment_score,
        )

