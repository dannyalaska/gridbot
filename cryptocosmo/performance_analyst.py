import logging
from collections import deque
from typing import List, Optional

from .config import AppConfig
from .grid_trader import GridTrader
from .indicators import calc_atr, calc_bollinger, calc_rsi

# Number of recent prices to buffer for indicator computation.
_PRICE_BUFFER_SIZE = 200


class PerformanceAnalyst:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._prices: deque = deque(maxlen=_PRICE_BUFFER_SIZE)

    def maybe_adjust(
        self,
        tick: int,
        price: float,
        trader: GridTrader,
        sentiment_score: float = 0.0,
    ) -> None:
        # Always update the price buffer — current_rsi() depends on this being current.
        self._prices.append(price)

        if tick == 0 or tick % self.cfg.performance.adjust_interval_ticks != 0:
            return

        closes: List[float] = list(self._prices)
        ind = self.cfg.indicators

        # ── 1. ATR-based spacing ──────────────────────────────────────────────
        new_spacing = trader.spacing  # fallback: keep current spacing
        candles = self._synthetic_candles(closes)
        if len(candles) >= ind.atr_period + 1:
            try:
                atr = calc_atr(candles, ind.atr_period)
                atr_spacing = atr * ind.atr_spacing_multiplier
                new_spacing = min(
                    max(atr_spacing, self.cfg.performance.spacing_min),
                    self.cfg.performance.spacing_max,
                )
                logging.info(
                    "ATR(%.0f) = %.2f -> spacing = %.2f",
                    ind.atr_period,
                    atr,
                    new_spacing,
                    extra={"action": "atr_spacing"},
                )
            except ValueError:
                pass  # not enough data yet; use current spacing

        # ── 2. Volatility-adjusted order size ─────────────────────────────────
        new_order_size = trader.cfg.grid.order_size  # fallback
        max_exp = self.cfg.grid.max_exposure_quote
        if price > 0 and max_exp > 0 and len(candles) >= ind.atr_period + 1:
            try:
                atr = calc_atr(candles, ind.atr_period)
                atr_pct = atr / price  # ATR as fraction of price
                # Scale order size: smaller when volatile (large ATR), bigger when calm
                vol_factor = ind.typical_atr_pct / atr_pct if atr_pct > 0 else 1.0
                vol_factor = min(max(vol_factor, 0.5), 1.5)
                base_order_quote = max_exp * ind.order_fraction * vol_factor
                new_order_size = base_order_quote / price
                new_order_size = min(
                    max(new_order_size, self.cfg.performance.order_size_min),
                    self.cfg.performance.order_size_max,
                )
                trader.cfg.grid.order_size = new_order_size
                logging.info(
                    "Vol-adj order size: atr_pct=%.4f vol_factor=%.2f -> %.6f BTC",
                    atr_pct,
                    vol_factor,
                    new_order_size,
                    extra={"action": "vol_order_size"},
                )
            except ValueError:
                pass

        # ── 3. Bollinger Band bounds ───────────────────────────────────────────
        if ind.use_bollinger_bounds and len(closes) >= ind.bb_period:
            try:
                bb_lower, _mid, bb_upper = calc_bollinger(closes, ind.bb_period, ind.bb_std)
                trader.cfg.grid.lower_bound = bb_lower
                trader.cfg.grid.upper_bound = bb_upper
                logging.info(
                    "BB(%d, %.1fσ) bounds: lower=%.2f upper=%.2f",
                    ind.bb_period,
                    ind.bb_std,
                    bb_lower,
                    bb_upper,
                    extra={"action": "bb_bounds"},
                )
            except ValueError:
                pass

        # ── 4. Sentiment-adjusted center ──────────────────────────────────────
        limit_pct = self.cfg.performance.center_shift_pct_limit / 100
        max_delta = trader.center * limit_pct
        desired_center = price * (1 + sentiment_score * self.cfg.sentiment.weight)
        bounded_center = min(
            trader.center + max_delta,
            max(trader.center - max_delta, desired_center),
        )

        trader.update_grid(center_price=bounded_center, spacing=new_spacing)
        logging.info(
            "Grid adjusted: center=%.2f spacing=%.2f order_size=%.6f (price=%.2f sentiment=%.2f)",
            bounded_center,
            new_spacing,
            trader.cfg.grid.order_size,
            price,
            sentiment_score,
            extra={"action": "adjust_grid"},
        )

    def current_rsi(self) -> Optional[float]:
        """Latest RSI from the internal price buffer. Returns None until enough data."""
        closes = list(self._prices)
        period = self.cfg.indicators.rsi_period
        if len(closes) < period + 1:
            return None
        try:
            return calc_rsi(closes, period)
        except ValueError:
            return None

    @staticmethod
    def _synthetic_candles(closes: List[float]) -> List[List[float]]:
        """Build synthetic OHLCV candles from consecutive close prices."""
        candles = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            candles.append([float(i), prev, max(prev, curr), min(prev, curr), curr, 1.0])
        return candles
