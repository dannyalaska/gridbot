import random
from dataclasses import dataclass
from typing import List, Tuple

from .config import AppConfig
from .exchange import SimulationExchange


@dataclass
class SimulationTickResult:
    tick: int
    price: float
    fills: List[dict]
    balances: dict


class Simulator:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.tick = 0
        self.price = cfg.grid.center_price
        self.exchange = SimulationExchange(
            starting_base=cfg.simulation.starting_base,
            starting_quote=cfg.simulation.starting_quote,
            fee_rate=cfg.simulation.fee_rate,
        )
        random.seed(cfg.simulation.seed)

    def step(self) -> SimulationTickResult:
        self.tick += 1
        self.price = self._next_price(self.price)
        self.exchange.set_price(self.price)
        fills = self.exchange.consume_fills()
        balances = self.exchange.get_balances()
        return SimulationTickResult(
            tick=self.tick,
            price=self.price,
            fills=fills,
            balances=balances,
        )

    def _next_price(self, current: float) -> float:
        move = self.cfg.simulation.drift + self.cfg.simulation.volatility * random.gauss(0, 1)
        next_price = max(0.0001, current * (1 + move))
        return next_price

    def equity(self) -> float:
        balances = self.exchange.get_balances()
        return balances["quote"] + balances["base"] * self.price

    def get_price_history(self) -> List[Tuple[int, float]]:
        # This can be expanded to feed historical data instead of random walk.
        return [(self.tick, self.price)]

