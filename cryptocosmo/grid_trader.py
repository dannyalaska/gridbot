import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .config import AppConfig
from .exchange import Order


@dataclass
class GridOrder:
    level_price: float
    side: str  # buy or sell
    amount: float
    order_id: Optional[str] = None


class GridTrader:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.symbol = cfg.symbol
        self.center = cfg.grid.center_price
        self.spacing = cfg.grid.spacing
        self.buy_levels = [self.center - self.spacing * i for i in range(1, cfg.grid.levels + 1)]
        self.active_orders: Dict[str, GridOrder] = {}
        self.pending_sells: List[GridOrder] = []

    def sync(
        self,
        connector,
        price: float,
        balances: Dict[str, float],
        open_orders: List[Order],
        allow_new_buys: bool,
    ) -> None:
        """Main entry point per tick to manage the grid."""
        if not self._within_bounds(price):
            logging.info(
                "Price %.2f outside bounds [%.2f, %.2f]; pausing new orders",
                price,
                self.cfg.grid.lower_bound,
                self.cfg.grid.upper_bound,
                extra={"action": "out_of_bounds"},
            )
            allow_new_buys = False

        # IMPORTANT: in live/sandbox, an order missing from open-orders is not guaranteed to be filled.
        self._reconcile_orders(connector, open_orders)
        self._place_pending_sells(connector, balances)

        if allow_new_buys:
            self._place_grid_buys(connector, price, balances)

    def _within_bounds(self, price: float) -> bool:
        return self.cfg.grid.lower_bound <= price <= self.cfg.grid.upper_bound

    def _reconcile_orders(self, connector, open_orders: List[Order]) -> None:
        """Reconcile our internal active order map with exchange state."""
        open_ids: Set[str] = {str(o.get("id")) for o in open_orders}
        to_remove: List[str] = []

        for oid, meta in self.active_orders.items():
            if oid in open_ids:
                continue

            # Missing from open orders. In simulation, that implies a fill.
            filled_amount: Optional[float] = None
            status: Optional[str] = None

            if self.cfg.mode == "simulation":
                treat_as_fill = True
            else:
                treat_as_fill = False
                # Try to confirm fill/cancel using fetch_order when available.
                if hasattr(connector, "get_order") and not self.cfg.exchange.dry_run and self.cfg.mode in ("sandbox", "live"):
                    remote = connector.get_order(oid, symbol=self.symbol)
                    if remote:
                        status = str(remote.get("status") or "")
                        try:
                            filled_amount = float(remote.get("filled") or 0.0)
                        except Exception:  # noqa: BLE001
                            filled_amount = 0.0
                        if status == "closed" or (filled_amount and filled_amount > 0):
                            treat_as_fill = True

            if treat_as_fill:
                if meta.side == "buy":
                    sell_price = meta.level_price + self.spacing
                    amt = meta.amount if not filled_amount else min(meta.amount, filled_amount)
                    self.pending_sells.append(GridOrder(level_price=sell_price, side="sell", amount=amt, order_id=None))
                    logging.info(
                        "Buy fill detected @ %.2f -> queuing sell @ %.2f",
                        meta.level_price,
                        sell_price,
                        extra={"action": "fill_buy"},
                    )
                elif meta.side == "sell":
                    logging.info("Sell fill detected @ %.2f", meta.level_price, extra={"action": "fill_sell"})
            else:
                logging.warning(
                    "Order %s disappeared from open set but does not look filled (status=%s). Treating as cancel.",
                    oid,
                    status,
                    extra={"action": "order_disappeared"},
                )

            to_remove.append(oid)

        for oid in to_remove:
            self.active_orders.pop(oid, None)

    def _place_grid_buys(self, connector, price: float, balances: Dict[str, float]) -> None:
        open_buys = [o for o in self.active_orders.values() if o.side == "buy"]
        current_allocation = sum(o.level_price * o.amount for o in open_buys)
        base_value = balances.get("base", 0.0) * price
        exposure = current_allocation + base_value
        max_exposure = self.cfg.grid.max_exposure_quote
        if exposure >= max_exposure:
            logging.info(
                "Exposure %.2f exceeds max %.2f; skipping new buys",
                exposure,
                max_exposure,
                extra={"action": "exposure_limit"},
            )
            return

        for lvl in self.buy_levels:
            if price < self.cfg.grid.lower_bound:
                break
            already_open = any(abs(o.level_price - lvl) < 1e-9 and o.side == "buy" for o in self.active_orders.values())
            if already_open:
                continue
            if exposure + lvl * self.cfg.grid.order_size > max_exposure:
                continue
            try:
                order = connector.place_limit_buy(self.symbol, lvl, self.cfg.grid.order_size)
                gid = str(order.get("id"))
                self.active_orders[gid] = GridOrder(level_price=lvl, side="buy", amount=self.cfg.grid.order_size, order_id=gid)
                exposure += lvl * self.cfg.grid.order_size
                logging.info("Placed buy @ %.2f (exposure now %.2f)", lvl, exposure, extra={"action": "place_buy"})
            except Exception as exc:  # noqa: BLE001
                logging.error("Failed to place buy @ %.2f: %s", lvl, exc, extra={"action": "place_buy_error"})

    def _place_pending_sells(self, connector, balances: Dict[str, float]) -> None:
        reserved_base = sum(o.amount for o in self.active_orders.values() if o.side == "sell")
        available_base = max(0.0, balances.get("base", 0.0) - reserved_base)

        remaining_pending: List[GridOrder] = []
        for pending in self.pending_sells:
            already_open = any(
                abs(o.level_price - pending.level_price) < 1e-9 and o.side == "sell" for o in self.active_orders.values()
            )
            if already_open:
                continue
            if pending.amount > available_base:
                remaining_pending.append(pending)
                continue
            try:
                order = connector.place_limit_sell(self.symbol, pending.level_price, pending.amount)
                gid = str(order.get("id"))
                self.active_orders[gid] = GridOrder(
                    level_price=pending.level_price,
                    side="sell",
                    amount=pending.amount,
                    order_id=gid,
                )
                available_base -= pending.amount
                logging.info(
                    "Placed sell @ %.2f for %.6f",
                    pending.level_price,
                    pending.amount,
                    extra={"action": "place_sell"},
                )
            except Exception as exc:  # noqa: BLE001
                logging.error(
                    "Failed to place sell @ %.2f: %s",
                    pending.level_price,
                    exc,
                    extra={"action": "place_sell_error"},
                )
                remaining_pending.append(pending)
        self.pending_sells = remaining_pending

    def update_grid(self, center_price: float, spacing: float) -> None:
        """Update grid levels for future orders."""
        self.center = center_price
        self.spacing = spacing
        self.buy_levels = [center_price - spacing * i for i in range(1, self.cfg.grid.levels + 1)]
        logging.info("Updated grid: center=%.2f spacing=%.2f", center_price, spacing, extra={"action": "update_grid"})

    def seed_sell_ladder(self, connector, price: float, base_available: float) -> None:
        """Place sell orders against existing holdings above current price."""
        if base_available <= 0:
            return
        ladder_amount = base_available
        level = 1
        placed = 0
        while ladder_amount > 0 and level <= self.cfg.grid.levels:
            amt = min(self.cfg.grid.order_size, ladder_amount)
            sell_price = price + self.spacing * level
            already_open = any(o.side == "sell" and abs(o.level_price - sell_price) < 1e-9 for o in self.active_orders.values())
            if not already_open:
                try:
                    order = connector.place_limit_sell(self.symbol, sell_price, amt)
                    gid = str(order.get("id"))
                    self.active_orders[gid] = GridOrder(level_price=sell_price, side="sell", amount=amt, order_id=gid)
                    placed += 1
                except Exception as exc:  # noqa: BLE001
                    logging.error(
                        "Failed to seed sell @ %.2f: %s",
                        sell_price,
                        exc,
                        extra={"action": "seed_sell_error"},
                    )
                    break
            ladder_amount -= amt
            level += 1
        if placed:
            logging.info("Seeded %d sell orders from existing holdings", placed, extra={"action": "seed_sells"})

    def cancel_all(self, connector) -> None:
        for oid in list(self.active_orders.keys()):
            try:
                connector.cancel_order(oid, symbol=self.symbol)
            except Exception as exc:  # noqa: BLE001
                logging.error("Failed to cancel order %s: %s", oid, exc, extra={"action": "cancel_order_error"})
        self.active_orders.clear()
        self.pending_sells.clear()
