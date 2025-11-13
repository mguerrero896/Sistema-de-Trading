"""Main orchestrator for the trading system."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from trading_system.backtester import Backtester
from trading_system.config import LOGS_DIR
from trading_system.oms import PaperTradingOMS
from trading_system.utils.logging_utils import setup_logging


class TradingSystem:
    """High level entrypoint that wires backtesting and paper trading."""

    def __init__(self, mode: str = "backtest", initial_capital: float = 25_000.0) -> None:
        self.mode = mode
        self.initial_capital = initial_capital
        setup_logging(LOGS_DIR)
        self.oms = PaperTradingOMS(initial_cash=initial_capital)

    async def run_backtest(self, start_date: str, end_date: str) -> Dict[str, Any]:
        backtester = Backtester(initial_capital=self.initial_capital, oms=self.oms)
        return await backtester.run(start_date=start_date, end_date=end_date)

    async def run_paper_trading(self, duration_days: int = 30) -> None:
        for _ in range(duration_days):
            await asyncio.sleep(0.05)
        return None
