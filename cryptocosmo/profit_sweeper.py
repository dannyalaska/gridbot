import logging

from .config import AppConfig


class ProfitSweeper:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.fund_balance = 0.0
        self.last_equity = None

    def maybe_sweep(self, tick: int, equity: float) -> None:
        if self.last_equity is None:
            self.last_equity = equity
            return
        if tick % self.cfg.profit_sweeper.sweep_interval_ticks != 0:
            return

        profit = equity - self.last_equity
        if profit > 0:
            self.fund_balance += profit
            logging.info(
                "ProfitSweeper moved %.2f to cosmetics fund (balance %.2f)",
                profit,
                self.fund_balance,
            )
        self.last_equity = equity

