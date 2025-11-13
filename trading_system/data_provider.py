"""Async data provider with demo fallbacks."""
from __future__ import annotations

import asyncio
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import numpy as np
import pandas as pd

from trading_system.config import (
    DATA_DIR,
    FMP_API_KEY,
    GLOBAL_RANDOM_SEED,
    POLYGON_API_KEY,
    UNIVERSE_TICKERS,
    USE_DEMO_DATA,
)

random.seed(GLOBAL_RANDOM_SEED)
np.random.seed(GLOBAL_RANDOM_SEED)


class RateLimiter:
    """Simple async rate limiter."""

    def __init__(self, rate_per_sec: float = 4.0) -> None:
        self.delay = 1.0 / max(rate_per_sec, 1e-6)
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        if delta < self.delay:
            await asyncio.sleep(self.delay - delta)
        self._last = time.monotonic()


class DataProvider:
    """Fetch market data asynchronously."""

    def __init__(self) -> None:
        self.session: Optional[aiohttp.ClientSession] = None
        self.rl = RateLimiter(4.0)
        os.makedirs(DATA_DIR, exist_ok=True)

    async def __aenter__(self) -> "DataProvider":
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self.session:
            await self.session.close()

    def _demo_equity_ohlcv(
        self, tickers: List[str], start: str, end: str, freq: str = "1D"
    ) -> Dict[str, pd.DataFrame]:
        idx = pd.date_range(pd.to_datetime(start), pd.to_datetime(end), freq=freq)
        out: Dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            base = 100 + (hash(ticker) % 17)
            mu, sigma = 0.10 / 252, 0.20 / np.sqrt(252)
            prices = [float(base)]
            for _ in range(1, len(idx)):
                prices.append(prices[-1] * (1 + np.random.normal(mu, sigma)))
            df = pd.DataFrame(index=idx)
            df["open"] = pd.Series(prices).shift(1).bfill()
            df["close"] = prices
            df["high"] = np.maximum(df["open"], df["close"]) * (
                1 + np.random.rand(len(df)) * 0.01
            )
            df["low"] = np.minimum(df["open"], df["close"]) * (
                1 - np.random.rand(len(df)) * 0.01
            )
            df["volume"] = (1e6 + np.random.rand(len(df)) * 5e6).astype(int)
            out[ticker] = df
        return out

    async def _fetch_json(self, url: str, params: Dict[str, Any]) -> Any:
        assert self.session is not None, "Session not initialized"
        await self.rl.wait()
        for attempt in range(5):
            try:
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(1 + attempt)
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except Exception:  # pragma: no cover - network backoff
                if attempt == 4:
                    raise
                await asyncio.sleep(2 ** attempt + random.random())

    async def get_equity_ohlcv(
        self, tickers: List[str], start: str, end: str, freq: str = "1D"
    ) -> Dict[str, pd.DataFrame]:
        if USE_DEMO_DATA:
            return self._demo_equity_ohlcv(tickers, start, end, freq)
        raise RuntimeError("Polygon integration required for live data")

    async def get_options_surface(self, ticker: str, asof: str) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "dte": [30, 30, 60, 60],
                "delta": [-0.25, -0.5, -0.25, -0.5],
                "iv": [0.35, 0.30, 0.33, 0.29],
            }
        )

    async def get_fmp_events(
        self, tickers: List[str], start: str, end: str
    ) -> pd.DataFrame:
        return pd.DataFrame(columns=["ticker", "date", "type", "value", "consensus"])
