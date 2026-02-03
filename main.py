import argparse
import logging
import time
from typing import Dict

from cryptocosmo.config import AppConfig, load_config
from cryptocosmo.exchange import ExchangeConnector
from cryptocosmo.grid_trader import GridTrader
from cryptocosmo.health_monitor import HealthMonitor
from cryptocosmo.logging_utils import configure_logging
from cryptocosmo.performance_analyst import PerformanceAnalyst
from cryptocosmo.persistence import Persistence
from cryptocosmo.profit_sweeper import ProfitSweeper
from cryptocosmo.risk_council import RiskCouncil
from cryptocosmo.sentiment_scout import SentimentScout
from cryptocosmo.simulator import Simulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CryptoCosmo grid bot")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--mode", choices=["simulation", "sandbox", "live"], help="Override mode")
    return parser.parse_args()


def _extract_balances(raw_balances: Dict[str, Dict[str, float]], symbol: str) -> Dict[str, float]:
    base, quote = symbol.split("/")
    free = raw_balances.get("free", {})
    return {"base": float(free.get(base, 0.0)), "quote": float(free.get(quote, 0.0))}


def run(cfg: AppConfig) -> None:
    configure_logging(log_level=cfg.log_level, mode=cfg.mode, symbol=cfg.symbol)
    logging.info("Starting CryptoCosmo in %s mode", cfg.mode, extra={"action": "startup"})

    grid_trader = GridTrader(cfg)
    risk_council = RiskCouncil(cfg)
    analyst = PerformanceAnalyst(cfg)
    sentiment = SentimentScout()
    health = HealthMonitor(cfg)
    sweeper = ProfitSweeper(cfg)
    sentiment_snapshot = sentiment.fetch()

    if cfg.mode == "simulation":
        simulator = Simulator(cfg)
        connector = simulator.exchange
    elif cfg.mode in ("sandbox", "live"):
        connector = ExchangeConnector(cfg)
        simulator = None
    else:
        raise ValueError(f"Unsupported mode {cfg.mode}")

    persistence = Persistence(cfg.persistence.db_path) if cfg.persistence.enabled else None
    run_id = None
    if persistence and cfg.persistence.restore_last_grid:
        restored = persistence.last_run(cfg.mode, cfg.symbol)
        if restored:
            _, grid = restored
            cfg.grid.center_price = grid.get("center", cfg.grid.center_price)
            cfg.grid.spacing = grid.get("spacing", cfg.grid.spacing)
            cfg.grid.lower_bound = grid.get("lower", cfg.grid.lower_bound)
            cfg.grid.upper_bound = grid.get("upper", cfg.grid.upper_bound)
            cfg.grid.max_exposure_quote = grid.get("max_exposure", cfg.grid.max_exposure_quote)
            grid_trader.update_grid(cfg.grid.center_price, cfg.grid.spacing)
    if persistence and cfg.risk.restore_state:
        restored_risk = persistence.last_run_risk(cfg.mode, cfg.symbol)
        if restored_risk:
            risk_council.restore_state(
                start_equity=restored_risk.get("start_equity"),
                max_equity=restored_risk.get("max_equity"),
            )
    if persistence:
        run_id = persistence.start_run(
            cfg.mode,
            cfg.symbol,
            grid={
                "center": cfg.grid.center_price,
                "spacing": cfg.grid.spacing,
                "lower": cfg.grid.lower_bound,
                "upper": cfg.grid.upper_bound,
                "max_exposure": cfg.grid.max_exposure_quote,
            },
        )

    try:
        tick = 0
        max_ticks = cfg.max_ticks if cfg.max_ticks > 0 else float("inf")
        while tick < max_ticks:
            tick += 1
            try:
                if cfg.mode == "simulation":
                    sim_result = simulator.step()
                    price = sim_result.price
                    balances = sim_result.balances
                    fills = sim_result.fills
                    open_orders = connector.get_open_orders(symbol=cfg.symbol)
                else:
                    price = connector.get_current_price(cfg.symbol)
                    raw_balances = connector.get_balances()
                    balances = _extract_balances(raw_balances, cfg.symbol)
                    fills = []
                    open_orders = connector.get_open_orders(symbol=cfg.symbol)

                health.record_price()
                health_ok = health.healthy()
                risk_state = risk_council.evaluate(
                    price=price,
                    balances=balances,
                    sentiment=sentiment_snapshot,
                    health_ok=health_ok,
                )
                if tick % 12 == 0:
                    sentiment_snapshot = sentiment.fetch()
                analyst.maybe_adjust(tick, price, grid_trader, sentiment_score=sentiment_snapshot.score)
                grid_trader.sync(
                    connector=connector,
                    price=price,
                    balances=balances,
                    open_orders=open_orders,
                    allow_new_buys=risk_state.allow_new_buys,
                )
                sweeper.maybe_sweep(tick, risk_state.equity)
                health.reset_errors()

                if risk_state.paused and cfg.risk.cancel_open_orders_on_pause:
                    grid_trader.cancel_all(connector)
                    open_orders = []

                if fills:
                    logging.info("Fills: %s", fills, extra={"tick": tick, "action": "fills"})

                logging.info(
                    "Tick %d price=%.2f equity=%.2f base=%.6f quote=%.2f open_orders=%d",
                    tick,
                    price,
                    risk_state.equity,
                    balances.get("base", 0.0),
                    balances.get("quote", 0.0),
                    len(open_orders),
                    extra={"tick": tick, "action": "tick"},
                )

                if persistence and run_id:
                    persistence.update_risk(
                        run_id=run_id,
                        start_equity=risk_state.start_equity,
                        max_equity=risk_state.max_equity,
                    )
                    persistence.record_snapshot(
                        run_id=run_id,
                        tick=tick,
                        price=price,
                        equity=risk_state.equity,
                        base=balances.get("base", 0.0),
                        quote=balances.get("quote", 0.0),
                        paused=risk_state.paused,
                        drawdown=risk_state.drawdown_pct,
                        healthy=health_ok,
                    )
                    persistence.update_grid(
                        run_id,
                        {
                            "center": grid_trader.center,
                            "spacing": grid_trader.spacing,
                            "lower": cfg.grid.lower_bound,
                            "upper": cfg.grid.upper_bound,
                            "max_exposure": cfg.grid.max_exposure_quote,
                        },
                    )

                if not health_ok:
                    logging.warning(
                        "Health monitor paused trading loop",
                        extra={"tick": tick, "action": "health_pause"},
                    )
                    break
            except Exception as exc:  # noqa: BLE001
                health.record_error()
                logging.error("Error on tick %d: %s", tick, exc, extra={"tick": tick, "action": "tick_error"})
            time.sleep(cfg.tick_seconds)
    except KeyboardInterrupt:
        logging.info("Shutting down")


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    if args.mode:
        config.mode = args.mode
    run(config)
