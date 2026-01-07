import argparse
import logging
import time
from typing import Dict

from cryptocosmo.config import AppConfig, load_config
from cryptocosmo.exchange import ExchangeConnector
from cryptocosmo.grid_trader import GridTrader
from cryptocosmo.health_monitor import HealthMonitor
from cryptocosmo.performance_analyst import PerformanceAnalyst
from cryptocosmo.profit_sweeper import ProfitSweeper
from cryptocosmo.risk_guard import RiskGuard
from cryptocosmo.sentiment_scout import SentimentScout
from cryptocosmo.simulator import Simulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CryptoCosmo grid bot")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--mode", choices=["simulation", "sandbox"], help="Override mode")
    return parser.parse_args()


def _extract_balances(raw_balances: Dict[str, Dict[str, float]], symbol: str) -> Dict[str, float]:
    base, quote = symbol.split("/")
    free = raw_balances.get("free", {})
    return {"base": float(free.get(base, 0.0)), "quote": float(free.get(quote, 0.0))}


def run(cfg: AppConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.info("Starting CryptoCosmo in %s mode", cfg.mode)

    grid_trader = GridTrader(cfg)
    risk_guard = RiskGuard(cfg)
    analyst = PerformanceAnalyst(cfg)
    sentiment = SentimentScout()
    health = HealthMonitor(cfg)
    sweeper = ProfitSweeper(cfg)
    sentiment_snapshot = sentiment.fetch()

    if cfg.mode == "simulation":
        simulator = Simulator(cfg)
        connector = simulator.exchange
    elif cfg.mode == "sandbox":
        connector = ExchangeConnector(cfg)
        simulator = None
    else:
        raise ValueError(f"Unsupported mode {cfg.mode}")

    try:
        tick = 0
        while tick < cfg.max_ticks:
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
                risk_state = risk_guard.evaluate(price, balances)
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

                if fills:
                    logging.info("Fills: %s", fills)

                logging.info(
                    "Tick %d price=%.2f equity=%.2f base=%.6f quote=%.2f open_orders=%d",
                    tick,
                    price,
                    risk_state.equity,
                    balances.get("base", 0.0),
                    balances.get("quote", 0.0),
                    len(open_orders),
                )

                if not health.healthy():
                    logging.warning("Health monitor paused trading loop")
                    break
            except Exception as exc:  # noqa: BLE001
                health.record_error()
                logging.error("Error on tick %d: %s", tick, exc)
            time.sleep(cfg.tick_seconds)
    except KeyboardInterrupt:
        logging.info("Shutting down")


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    if args.mode:
        config.mode = args.mode
    run(config)
