import logging
import os
import time
import uuid
from typing import Dict, List, Optional

import ccxt

from .config import AppConfig


Order = Dict[str, object]


class ExchangeConnector:
    """
    Thin wrapper around ccxt for sandbox/live trading.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.dry_run = cfg.exchange.dry_run
        self.exchange = None
        self.paper_orders: List[Order] = []
        if cfg.mode in ("sandbox", "live"):
            self._init_exchange()

    def _init_exchange(self) -> None:
        name = self.cfg.exchange.name
        if not hasattr(ccxt, name):
            raise ValueError(f"Exchange {name} is not supported by ccxt")
        api_key = os.getenv(self.cfg.exchange.api_key_env, "")
        api_secret = os.getenv(self.cfg.exchange.api_secret_env, "")
        if not api_key or not api_secret:
            raise ValueError(
                f"Missing API credentials in env {self.cfg.exchange.api_key_env}/{self.cfg.exchange.api_secret_env}"
            )
        if self.cfg.mode == "live":
            self._require_live_confirmation()
            if self.dry_run:
                raise RuntimeError("Live mode requires exchange.dry_run=false to place real orders")
        self.exchange = getattr(ccxt, name)(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
            }
        )
        # Use built-in sandbox routing when available (Binance supports this).
        sandbox_mode = self.cfg.mode == "sandbox"
        self.exchange.set_sandbox_mode(sandbox_mode)
        logging.info(
            "Connected to %s (sandbox=%s, dry_run=%s)",
            name,
            sandbox_mode,
            self.dry_run,
        )

    def _require_live_confirmation(self) -> None:
        flag = os.getenv("GRIDBOT_LIVE_TRADING", "").strip().lower()
        if flag not in {"1", "true", "yes", "on"}:
            raise RuntimeError("Live trading blocked. Set GRIDBOT_LIVE_TRADING=true to enable.")

    def get_current_price(self, symbol: str) -> float:
        ticker = self.exchange.fetch_ticker(symbol)
        return float(ticker["last"])

    def get_balances(self) -> Dict[str, Dict[str, float]]:
        bal = self.exchange.fetch_balance()
        return {"free": bal.get("free", {}), "total": bal.get("total", {})}

    def place_limit_buy(self, symbol: str, price: float, amount: float) -> Order:
        if self.dry_run:
            order = {"id": f"dry-buy-{uuid.uuid4().hex[:8]}", "side": "buy", "price": price, "amount": amount}
            self.paper_orders.append(order)
            logging.info("Dry run BUY %s %s @ %s", amount, symbol, price)
            return order
        return self.exchange.create_limit_buy_order(symbol, amount, price)

    def place_limit_sell(self, symbol: str, price: float, amount: float) -> Order:
        if self.dry_run:
            order = {"id": f"dry-sell-{uuid.uuid4().hex[:8]}", "side": "sell", "price": price, "amount": amount}
            self.paper_orders.append(order)
            logging.info("Dry run SELL %s %s @ %s", amount, symbol, price)
            return order
        return self.exchange.create_limit_sell_order(symbol, amount, price)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        if self.dry_run:
            return list(self.paper_orders)
        return self.exchange.fetch_open_orders(symbol=symbol)

    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> None:
        if self.dry_run:
            logging.info("Dry run cancel %s", order_id)
            self.paper_orders = [o for o in self.paper_orders if o.get("id") != order_id]
            return
        self.exchange.cancel_order(order_id, symbol=symbol)


class SimulationExchange:
    """
    Simple in-memory exchange to exercise trading logic without APIs.
    """

    def __init__(self, starting_base: float, starting_quote: float, fee_rate: float):
        self.price = 0.0
        self.fee_rate = fee_rate
        self.balances = {"base": starting_base, "quote": starting_quote}
        self.open_orders: List[Order] = []
        self.fills: List[Dict[str, float]] = []

    def set_price(self, price: float) -> None:
        self.price = price
        self._fill_orders()

    def get_balances(self) -> Dict[str, float]:
        return dict(self.balances)

    def place_limit_buy(self, symbol: str, price: float, amount: float) -> Order:
        cost = price * amount * (1 + self.fee_rate)
        if cost > self.balances["quote"]:
            raise ValueError("Insufficient quote balance for buy order")
        order = {"id": f"sim-buy-{uuid.uuid4().hex[:8]}", "symbol": symbol, "side": "buy", "price": price, "amount": amount, "timestamp": time.time()}
        self.open_orders.append(order)
        return order

    def place_limit_sell(self, symbol: str, price: float, amount: float) -> Order:
        if amount > self.balances["base"]:
            raise ValueError("Insufficient base balance for sell order")
        order = {"id": f"sim-sell-{uuid.uuid4().hex[:8]}", "symbol": symbol, "side": "sell", "price": price, "amount": amount, "timestamp": time.time()}
        self.open_orders.append(order)
        return order

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        if symbol:
            return [o for o in self.open_orders if o.get("symbol") == symbol]
        return list(self.open_orders)

    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> None:
        self.open_orders = [o for o in self.open_orders if o["id"] != order_id]

    def consume_fills(self) -> List[Dict[str, float]]:
        fills = list(self.fills)
        self.fills = []
        return fills

    def _fill_orders(self) -> None:
        remaining_orders: List[Order] = []
        for order in self.open_orders:
            side = order["side"]
            price = float(order["price"])
            amount = float(order["amount"])
            if side == "buy" and self.price <= price:
                cost = price * amount
                fee = cost * self.fee_rate
                if cost + fee > self.balances["quote"]:
                    remaining_orders.append(order)
                    continue
                self.balances["quote"] -= cost + fee
                self.balances["base"] += amount
                self.fills.append({"order_id": order["id"], "side": side, "price": price, "amount": amount, "fee": fee})
            elif side == "sell" and self.price >= price:
                if amount > self.balances["base"]:
                    remaining_orders.append(order)
                    continue
                proceeds = price * amount
                fee = proceeds * self.fee_rate
                self.balances["base"] -= amount
                self.balances["quote"] += proceeds - fee
                self.fills.append({"order_id": order["id"], "side": side, "price": price, "amount": amount, "fee": fee})
            else:
                remaining_orders.append(order)
        self.open_orders = remaining_orders
