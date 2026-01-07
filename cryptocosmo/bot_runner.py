import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import AppConfig
from .exchange import ExchangeConnector
from .grid_trader import GridTrader
from .health_monitor import HealthMonitor
from .logging_utils import InMemoryLogHandler
from .performance_analyst import PerformanceAnalyst
from .persistence import Persistence
from .profit_sweeper import ProfitSweeper
from .risk_guard import RiskGuard
from .sentiment_scout import SentimentScout
from .simulator import Simulator


@dataclass
class BotStatus:
    running: bool = False
    mode: str = "simulation"
    symbol: str = "BTC/USDT"
    tick: int = 0
    price: float = 0.0
    equity: float = 0.0
    balances: Dict[str, float] = field(default_factory=dict)
    open_orders: List[dict] = field(default_factory=list)
    risk: Dict[str, object] = field(default_factory=dict)
    health: Dict[str, object] = field(default_factory=dict)
    grid: Dict[str, object] = field(default_factory=dict)
    sentiment: Dict[str, object] = field(default_factory=dict)
    sweeper: Dict[str, object] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    last_updated: float = 0.0


class BotRunner:
    """
    Background runner with shared state for the dashboard.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.log_handler = InMemoryLogHandler(capacity=200)
        self._attach_log_handler()

        self.grid_trader: Optional[GridTrader] = None
        self.risk_guard: Optional[RiskGuard] = None
        self.analyst: Optional[PerformanceAnalyst] = None
        self.sentiment: Optional[SentimentScout] = None
        self.health: Optional[HealthMonitor] = None
        self.sweeper: Optional[ProfitSweeper] = None
        self.simulator: Optional[Simulator] = None
        self.connector = None
        self.persistence: Optional[Persistence] = None
        self.run_id: Optional[int] = None
        self._seeded_from_live = False

        self.status = BotStatus(mode=cfg.mode, symbol=cfg.symbol)

    def _attach_log_handler(self) -> None:
        logger = logging.getLogger()
        if not logger.handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
        if not any(isinstance(h, InMemoryLogHandler) for h in logger.handlers):
            self.log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(self.log_handler)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self._seeded_from_live = False
        self.stop_event.clear()
        self._build_components()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        with self.lock:
            self.status.running = False

    def _build_components(self) -> None:
        self.grid_trader = GridTrader(self.cfg)
        self.risk_guard = RiskGuard(self.cfg)
        self.analyst = PerformanceAnalyst(self.cfg)
        self.sentiment = SentimentScout()
        self.health = HealthMonitor(self.cfg)
        self.sweeper = ProfitSweeper(self.cfg)

        if self.cfg.mode == "simulation":
            self.simulator = Simulator(self.cfg)
            self.connector = self.simulator.exchange
        elif self.cfg.mode == "sandbox":
            self.simulator = None
            self.connector = ExchangeConnector(self.cfg)
        else:
            raise ValueError(f"Unsupported mode {self.cfg.mode}")

        if self.cfg.persistence.enabled:
            self.persistence = Persistence(self.cfg.persistence.db_path)
        else:
            self.persistence = None

        # Restore last grid if configured
        if self.persistence and self.cfg.persistence.restore_last_grid:
            restored = self.persistence.last_run(self.cfg.mode, self.cfg.symbol)
            if restored:
                _, grid = restored
                self.cfg.grid.center_price = grid.get("center", self.cfg.grid.center_price)
                self.cfg.grid.spacing = grid.get("spacing", self.cfg.grid.spacing)
                self.cfg.grid.lower_bound = grid.get("lower", self.cfg.grid.lower_bound)
                self.cfg.grid.upper_bound = grid.get("upper", self.cfg.grid.upper_bound)
                self.cfg.grid.max_exposure_quote = grid.get("max_exposure", self.cfg.grid.max_exposure_quote)
                self.grid_trader.update_grid(self.cfg.grid.center_price, self.cfg.grid.spacing)

    def _extract_balances(self, raw_balances: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        base, quote = self.cfg.symbol.split("/")
        free = raw_balances.get("free", {})
        return {"base": float(free.get(base, 0.0)), "quote": float(free.get(quote, 0.0))}

    def _run_loop(self) -> None:
        tick = 0
        sentiment_snapshot = self.sentiment.fetch()
        max_ticks = self.cfg.max_ticks if self.cfg.max_ticks > 0 else float("inf")
        with self.lock:
            self.status.running = True
            if self.persistence:
                self.run_id = self.persistence.start_run(
                    self.cfg.mode,
                    self.cfg.symbol,
                    grid={
                        "center": self.cfg.grid.center_price,
                        "spacing": self.cfg.grid.spacing,
                        "lower": self.cfg.grid.lower_bound,
                        "upper": self.cfg.grid.upper_bound,
                        "max_exposure": self.cfg.grid.max_exposure_quote,
                    },
                )
        while not self.stop_event.is_set() and tick < max_ticks:
            tick += 1
            try:
                if self.cfg.mode == "simulation":
                    sim_result = self.simulator.step()
                    price = sim_result.price
                    balances = sim_result.balances
                    fills = sim_result.fills
                    open_orders = self.connector.get_open_orders(symbol=self.cfg.symbol)
                else:
                    price = self.connector.get_current_price(self.cfg.symbol)
                    raw_balances = self.connector.get_balances()
                    balances = self._extract_balances(raw_balances)
                    fills = []
                    open_orders = self.connector.get_open_orders(symbol=self.cfg.symbol)

                if not self._seeded_from_live:
                    self._seed_grid(price, balances)
                    self._seeded_from_live = True

                self.health.record_price()
                risk_state = self.risk_guard.evaluate(price, balances)
                if tick % 12 == 0:
                    sentiment_snapshot = self.sentiment.fetch()
                self.analyst.maybe_adjust(tick, price, self.grid_trader, sentiment_score=sentiment_snapshot.score)
                self.grid_trader.sync(
                    connector=self.connector,
                    price=price,
                    balances=balances,
                    open_orders=open_orders,
                    allow_new_buys=risk_state.allow_new_buys,
                )
                self.sweeper.maybe_sweep(tick, risk_state.equity)
                self.health.reset_errors()

                if risk_state.paused and self.cfg.risk.cancel_open_orders_on_pause:
                    self.grid_trader.cancel_all(self.connector)
                    open_orders = []

                if fills:
                    logging.info("Fills: %s", fills)

                self._update_status(
                    tick=tick,
                    price=price,
                    balances=balances,
                    open_orders=open_orders,
                    risk_state=risk_state,
                    sentiment_snapshot=sentiment_snapshot,
                )

                if self.persistence and self.run_id:
                    self.persistence.record_snapshot(
                        run_id=self.run_id,
                        tick=tick,
                        price=price,
                        equity=risk_state.equity,
                        base=balances.get("base", 0.0),
                        quote=balances.get("quote", 0.0),
                        paused=risk_state.paused,
                        drawdown=risk_state.drawdown_pct,
                        healthy=self.health.healthy(),
                    )

                if not self.health.healthy():
                    logging.warning("Health monitor paused trading loop")
                    break
            except Exception as exc:  # noqa: BLE001
                self.health.record_error()
                logging.error("Error on tick %d: %s", tick, exc)

            if self.stop_event.wait(self.cfg.tick_seconds):
                break
        with self.lock:
            self.status.running = False

    def _update_status(
        self,
        tick: int,
        price: float,
        balances: Dict[str, float],
        open_orders: List[dict],
        risk_state,
        sentiment_snapshot,
    ) -> None:
        with self.lock:
            self.status.tick = tick
            self.status.price = price
            self.status.equity = risk_state.equity
            self.status.balances = balances
            self.status.open_orders = open_orders
            self.status.risk = {
                "paused": risk_state.paused,
                "drawdown_pct": risk_state.drawdown_pct,
                "allow_new_buys": risk_state.allow_new_buys,
                "reason": risk_state.reason,
            }
            self.status.health = {
                "healthy": self.health.healthy(),
                "error_streak": self.health.error_streak,
            }
            self.status.grid = {
                "center": self.grid_trader.center,
                "spacing": self.grid_trader.spacing,
                "lower": self.cfg.grid.lower_bound,
                "upper": self.cfg.grid.upper_bound,
                "max_exposure": self.cfg.grid.max_exposure_quote,
                "levels": self.cfg.grid.levels,
            }
            self.status.sentiment = {
                "score": sentiment_snapshot.score,
                "label": sentiment_snapshot.label,
                "news_risk": sentiment_snapshot.news_risk,
            }
            self.status.sweeper = {"fund_balance": self.sweeper.fund_balance}
            self.status.logs = self.log_handler.get_logs()
            self.status.mode = self.cfg.mode
            self.status.symbol = self.cfg.symbol
            self.status.last_updated = time.time()
            if self.persistence and self.run_id:
                self.persistence.update_grid(
                    self.run_id,
                    {
                        "center": self.grid_trader.center,
                        "spacing": self.grid_trader.spacing,
                        "lower": self.cfg.grid.lower_bound,
                        "upper": self.cfg.grid.upper_bound,
                        "max_exposure": self.cfg.grid.max_exposure_quote,
                    },
                )

    def get_status(self) -> BotStatus:
        with self.lock:
            return self.status

    def _seed_grid(self, price: float, balances: Dict[str, float]) -> None:
        """
        Center grid on live price and place sell ladder from existing holdings.
        """
        # Center the grid on current price
        self.cfg.grid.center_price = price
        self.grid_trader.update_grid(center_price=price, spacing=self.cfg.grid.spacing)
        # Place sells for existing holdings
        base_available = balances.get("base", 0.0)
        self.grid_trader.seed_sell_ladder(self.connector, price, base_available)

    def update_grid(
        self,
        center: Optional[float] = None,
        spacing: Optional[float] = None,
        lower: Optional[float] = None,
        upper: Optional[float] = None,
        max_exposure: Optional[float] = None,
    ) -> None:
        with self.lock:
            if center is not None:
                self.cfg.grid.center_price = center
            if spacing is not None:
                self.cfg.grid.spacing = spacing
            if lower is not None:
                self.cfg.grid.lower_bound = lower
            if upper is not None:
                self.cfg.grid.upper_bound = upper
            if max_exposure is not None:
                self.cfg.grid.max_exposure_quote = max_exposure

        if self.grid_trader:
            self.grid_trader.update_grid(
                center_price=self.cfg.grid.center_price,
                spacing=self.cfg.grid.spacing,
            )
        if self.persistence and self.run_id:
            self.persistence.update_grid(
                self.run_id,
                {
                    "center": self.cfg.grid.center_price,
                    "spacing": self.cfg.grid.spacing,
                    "lower": self.cfg.grid.lower_bound,
                    "upper": self.cfg.grid.upper_bound,
                    "max_exposure": self.cfg.grid.max_exposure_quote,
                },
            )

    def configure_and_start(
        self,
        mode: Optional[str] = None,
        symbol: Optional[str] = None,
        center: Optional[float] = None,
        spacing: Optional[float] = None,
        lower: Optional[float] = None,
        upper: Optional[float] = None,
        max_exposure: Optional[float] = None,
    ) -> None:
        was_running = self.thread is not None and self.thread.is_alive()
        self.stop()
        with self.lock:
            if mode:
                self.cfg.mode = mode
            if symbol:
                self.cfg.symbol = symbol
            if center is not None:
                self.cfg.grid.center_price = center
            if spacing is not None:
                self.cfg.grid.spacing = spacing
            if lower is not None:
                self.cfg.grid.lower_bound = lower
            if upper is not None:
                self.cfg.grid.upper_bound = upper
            if max_exposure is not None:
                self.cfg.grid.max_exposure_quote = max_exposure
        if was_running or True:
            self.start()
