from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class GridConfig:
    center_price: float
    spacing: float
    levels: int
    order_size: float
    max_exposure_quote: float
    lower_bound: float
    upper_bound: float


@dataclass
class RiskConfig:
    daily_loss_limit_pct: float
    max_drawdown_pct: float
    crash_drop_pct: float
    crash_window_ticks: int
    cancel_open_orders_on_pause: bool
    restore_state: bool


@dataclass
class PerformanceConfig:
    adjust_interval_ticks: int
    center_shift_pct_limit: float
    spacing_min: float
    spacing_max: float
    order_size_min: float
    order_size_max: float


@dataclass
class SimulationConfig:
    starting_base: float
    starting_quote: float
    drift: float
    volatility: float
    fee_rate: float
    seed: int


@dataclass
class SentimentConfig:
    weight: float


@dataclass
class LLMRiskConfig:
    enabled: bool
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_crash_pct: float
    block_on_news_risk: bool


@dataclass
class HealthConfig:
    max_stale_price_secs: int
    max_error_streak: int


@dataclass
class ProfitSweeperConfig:
    cosmetics_goal: float
    sweep_interval_ticks: int


@dataclass
class ExchangeConfig:
    name: str
    sandbox: bool
    dry_run: bool
    api_key_env: str
    api_secret_env: str


@dataclass
class PersistenceConfig:
    enabled: bool
    db_path: str
    restore_last_grid: bool


@dataclass
class AppConfig:
    mode: str
    symbol: str
    tick_seconds: int
    max_ticks: int
    log_level: str
    grid: GridConfig
    risk: RiskConfig
    performance: PerformanceConfig
    simulation: SimulationConfig
    sentiment: SentimentConfig
    llm_risk: LLMRiskConfig
    health: HealthConfig
    profit_sweeper: ProfitSweeperConfig
    exchange: ExchangeConfig
    persistence: PersistenceConfig


def _require(data: Dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required config key: {key}")
    return data[key]


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _optional(data: Optional[Dict[str, Any]], key: str, default: Any) -> Any:
    if not data:
        return default
    return data.get(key, default)


def load_config(path: str) -> AppConfig:
    cfg_raw = _load_yaml(Path(path))
    grid_raw = _require(cfg_raw, "grid")
    risk_raw = _require(cfg_raw, "risk")
    perf_raw = _require(cfg_raw, "performance")
    sim_raw = _require(cfg_raw, "simulation")
    sentiment_raw = _require(cfg_raw, "sentiment")
    llm_raw = cfg_raw.get("llm_risk", {})
    health_raw = _require(cfg_raw, "health")
    sweeper_raw = _require(cfg_raw, "profit_sweeper")
    exch_raw = _require(cfg_raw, "exchange")

    grid = GridConfig(
        center_price=float(_require(grid_raw, "center_price")),
        spacing=float(_require(grid_raw, "spacing")),
        levels=int(_require(grid_raw, "levels")),
        order_size=float(_require(grid_raw, "order_size")),
        max_exposure_quote=float(_require(grid_raw, "max_exposure_quote")),
        lower_bound=float(_require(grid_raw, "lower_bound")),
        upper_bound=float(_require(grid_raw, "upper_bound")),
    )

    risk = RiskConfig(
        daily_loss_limit_pct=float(_require(risk_raw, "daily_loss_limit_pct")),
        max_drawdown_pct=float(_require(risk_raw, "max_drawdown_pct")),
        crash_drop_pct=float(_require(risk_raw, "crash_drop_pct")),
        crash_window_ticks=int(_require(risk_raw, "crash_window_ticks")),
        cancel_open_orders_on_pause=bool(_require(risk_raw, "cancel_open_orders_on_pause")),
        restore_state=bool(_optional(risk_raw, "restore_state", True)),
    )

    performance = PerformanceConfig(
        adjust_interval_ticks=int(_require(perf_raw, "adjust_interval_ticks")),
        center_shift_pct_limit=float(_require(perf_raw, "center_shift_pct_limit")),
        spacing_min=float(_require(perf_raw, "spacing_min")),
        spacing_max=float(_require(perf_raw, "spacing_max")),
        order_size_min=float(_require(perf_raw, "order_size_min")),
        order_size_max=float(_require(perf_raw, "order_size_max")),
    )

    simulation = SimulationConfig(
        starting_base=float(_require(sim_raw, "starting_base")),
        starting_quote=float(_require(sim_raw, "starting_quote")),
        drift=float(_require(sim_raw, "drift")),
        volatility=float(_require(sim_raw, "volatility")),
        fee_rate=float(_require(sim_raw, "fee_rate")),
        seed=int(_require(sim_raw, "seed")),
    )

    sentiment = SentimentConfig(weight=float(_require(sentiment_raw, "weight")))

    llm_risk = LLMRiskConfig(
        enabled=bool(_optional(llm_raw, "enabled", False)),
        max_daily_loss_pct=float(_optional(llm_raw, "max_daily_loss_pct", 0.0)),
        max_drawdown_pct=float(_optional(llm_raw, "max_drawdown_pct", 0.0)),
        max_crash_pct=float(_optional(llm_raw, "max_crash_pct", 0.0)),
        block_on_news_risk=bool(_optional(llm_raw, "block_on_news_risk", True)),
    )

    health = HealthConfig(
        max_stale_price_secs=int(_require(health_raw, "max_stale_price_secs")),
        max_error_streak=int(_require(health_raw, "max_error_streak")),
    )

    profit_sweeper = ProfitSweeperConfig(
        cosmetics_goal=float(_require(sweeper_raw, "cosmetics_goal")),
        sweep_interval_ticks=int(_require(sweeper_raw, "sweep_interval_ticks")),
    )

    exchange = ExchangeConfig(
        name=str(_require(exch_raw, "name")),
        sandbox=bool(_require(exch_raw, "sandbox")),
        dry_run=bool(_require(exch_raw, "dry_run")),
        api_key_env=str(_require(exch_raw, "api_key_env")),
        api_secret_env=str(_require(exch_raw, "api_secret_env")),
    )

    persistence_raw = _require(cfg_raw, "persistence")
    persistence = PersistenceConfig(
        enabled=bool(_require(persistence_raw, "enabled")),
        db_path=str(_require(persistence_raw, "db_path")),
        restore_last_grid=bool(_require(persistence_raw, "restore_last_grid")),
    )

    return AppConfig(
        mode=str(_require(cfg_raw, "mode")),
        symbol=str(_require(cfg_raw, "symbol")),
        tick_seconds=int(_require(cfg_raw, "tick_seconds")),
        max_ticks=int(_require(cfg_raw, "max_ticks")),
        log_level=str(_require(cfg_raw, "log_level")),
        grid=grid,
        risk=risk,
        performance=performance,
        simulation=simulation,
        sentiment=sentiment,
        llm_risk=llm_risk,
        health=health,
        profit_sweeper=profit_sweeper,
        exchange=exchange,
        persistence=persistence,
    )
