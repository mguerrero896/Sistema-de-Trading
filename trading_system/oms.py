"""Order management system components."""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict

import numpy as np


class PaperTradingOMS:
    """Simple paper trading OMS that tracks cash and positions."""

    def __init__(self, initial_cash: float = 25_000.0) -> None:
        self.cash = float(initial_cash)
        self.positions: Dict[str, Dict[str, float]] = {}
        self.total_value = self.cash
        self.idempotency_registry: set[str] = set()
        self.expected_costs: Dict[str, float] = {}
        self.equity_curve: list[float] = []

    def get_portfolio_value(self) -> float:
        return float(self.cash + sum(p.get("value", 0.0) for p in self.positions.values()))

    def get_pnl(self) -> float:
        if not self.equity_curve:
            return 0.0
        return float(self.equity_curve[-1] - self.equity_curve[0])

    def idempotency_key(self, account_id: str, ticker: str, client_order_id: str) -> str:
        return hashlib.sha256(f"{account_id}:{ticker}:{client_order_id}".encode()).hexdigest()

    def reference_price(self, ticker: str) -> float:
        return float(self.positions.get(ticker, {}).get("price", 100.0))

    def estimate_cost(
        self,
        ticker: str,
        qty: float,
        price: float,
        spread_bps: float = 5.0,
        participation: float = 0.01,
        vol_cone: float = 1.0,
    ) -> float:
        commission = 0.0005 * abs(qty) * price
        spread_cost = 0.5 * (spread_bps / 10_000.0) * abs(qty) * price
        permanent = 0.1 * participation * abs(qty) * price
        temporary = 0.01 * vol_cone * np.sqrt(participation) * abs(qty) * price
        return float(commission + spread_cost + permanent + temporary)

    def log_expected_cost(self, order_id: str, cost: float) -> None:
        self.expected_costs[order_id] = float(cost)

    def validate_implementation_shortfall(
        self, order_id: str, arrival_price: float, avg_fill_price: float, filled_qty: float
    ) -> Dict[str, float]:
        expected = self.expected_costs.get(order_id, 0.0)
        realized = abs(avg_fill_price - arrival_price) * abs(filled_qty)
        error = (realized - expected) / (expected + 1e-8)
        return {"expected": expected, "realized": realized, "slippage_error": float(error)}

    def send_order(
        self,
        account_id: str,
        ticker: str,
        side: str,
        qty: float,
        limit_price: float | None = None,
        client_order_id: str | None = None,
    ) -> Dict[str, Any]:
        client_order_id = client_order_id or f"{ticker}-{int(time.time() * 1000)}"
        key = self.idempotency_key(account_id, ticker, client_order_id)
        if key in self.idempotency_registry:
            return {"status": "IGNORED_DUPLICATE", "client_order_id": client_order_id}
        self.idempotency_registry.add(key)

        price_ref = limit_price if limit_price else self.reference_price(ticker)
        exp_cost = self.estimate_cost(ticker, qty, price_ref)
        self.log_expected_cost(client_order_id, exp_cost)

        side_up = side.upper()
        fill_price = float(price_ref * (1 + (0.0005 if side_up.startswith("BUY") else -0.0005)))
        filled_qty = float(qty)
        sign = 1.0 if side_up.startswith("BUY") else -1.0

        self.cash -= sign * filled_qty * fill_price + exp_cost
        position = self.positions.get(ticker, {"qty": 0.0, "price": fill_price, "value": 0.0})
        position["qty"] += sign * filled_qty
        position["price"] = fill_price
        position["value"] = position["qty"] * fill_price
        self.positions[ticker] = position
        self.total_value = self.get_portfolio_value()
        self.equity_curve.append(self.total_value)

        return {
            "status": "FILLED",
            "ticker": ticker,
            "side": side,
            "filled_quantity": filled_qty,
            "avg_fill_price": fill_price,
            "client_order_id": client_order_id,
        }


# Stub for production integration (disabled intentionally)
# class TastyTradeOMS:
#     """Placeholder for a future TastyTrade integration."""
#
#     def __init__(self, api_user: str, api_pass: str, account_id: str) -> None:
#         raise NotImplementedError("Activate only after completing compliance checklist")
