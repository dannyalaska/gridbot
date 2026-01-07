import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict

from .config import AppConfig


@dataclass
class RiskState:
    equity: float
    drawdown_pct: float
    paused: bool
    allow_new_buys: bool
    reason: str | None = None


class RiskGuard:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.start_equity: float | None = None
        self.max_equity: float | None = None
        self.recent_prices: Deque[float] = deque(maxlen=cfg.risk.crash_window_ticks)
        self.paused = False

    def evaluate(self, price: float, balances: Dict[str, float]) -> RiskState:
        equity = balances.get("quote", 0.0) + balances.get("base", 0.0) * price
        if self.start_equity is None:
            self.start_equity = equity
            self.max_equity = equity
        if self.max_equity is None:
            self.max_equity = equity

        self.max_equity = max(self.max_equity, equity)
        drawdown_pct = 0.0
        if self.max_equity:
            drawdown_pct = (self.max_equity - equity) / self.max_equity * 100

        loss_pct = 0.0
        if self.start_equity:
            loss_pct = (self.start_equity - equity) / self.start_equity * 100

        self.recent_prices.append(price)
        crash_pct = self._crash_drop()

        reason = None
        if loss_pct >= self.cfg.risk.daily_loss_limit_pct:
            self.paused = True
            reason = f"daily loss {loss_pct:.2f}% >= limit {self.cfg.risk.daily_loss_limit_pct:.2f}%"
            logging.warning("Pausing: %s", reason)
        if drawdown_pct >= self.cfg.risk.max_drawdown_pct:
            self.paused = True
            reason = f"drawdown {drawdown_pct:.2f}% >= limit {self.cfg.risk.max_drawdown_pct:.2f}%"
            logging.warning("Pausing: %s", reason)
        if crash_pct >= self.cfg.risk.crash_drop_pct:
            self.paused = True
            reason = f"crash {crash_pct:.2f}% over {self.cfg.risk.crash_window_ticks} ticks"
            logging.warning("Pausing: %s", reason)

        return RiskState(equity=equity, drawdown_pct=drawdown_pct, paused=self.paused, allow_new_buys=not self.paused, reason=reason)

    def _crash_drop(self) -> float:
        if len(self.recent_prices) < self.recent_prices.maxlen:
            return 0.0
        first = self.recent_prices[0]
        last = self.recent_prices[-1]
        if first <= 0:
            return 0.0
        drop = (first - last) / first * 100
        return max(0.0, drop)
