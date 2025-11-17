from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

import pandas as pd
from polygon import RESTClient


@dataclass
class OptionsTradesConfig:
    """
    Configuration for building daily option trade features using Polygon.
    `days_before_expiry` and `days_after_expiry` define the window around
    the target expiry date.
    """
    days_before_expiry: int = 30
    days_after_expiry: int = 0
    contracts_limit: int = 100
    trades_limit_per_contract: int = 50000
    min_trades_per_day: int = 1


class OptionsTradesLoader:
    """
    Load historical option trade data from Polygon and build daily features.
    """
    def __init__(self, cfg: OptionsTradesConfig, api_key: Optional[str] = None) -> None:
        self.cfg = cfg
        # Use provided API key or default to environment variable
        self.client = RESTClient(api_key=api_key)

    @staticmethod
    def _to_date(d: str | date | datetime) -> date:
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        return datetime.strptime(d, "%Y-%m-%d").date()

    def _list_contract_tickers_for_expiry(
        self, underlying: str, expiry: date
    ) -> List[str]:
        """Return option contract tickers for a given underlying and expiration date."""
        expiry_str = expiry.strftime("%Y-%m-%d")
        tickers: List[str] = []
        try:
            for c in self.client.list_options_contracts(
                underlying_ticker=underlying,
                expiration_date=expiry_str,
                limit=self.cfg.contracts_limit,
            ):
                ticker = getattr(c, "ticker", None)
                if ticker:
                    tickers.append(ticker)
        except Exception:
            pass
        return tickers

    def _list_trades_for_contract_on_date(
        self, option_ticker: str, trade_date: date
    ) -> List:
        """
        Return trades for a given option contract and date.
        Uses the `date` parameter (not timestamp_gte/lte) as per Polygon's docs.
        """
        date_str = trade_date.strftime("%Y-%m-%d")
        trades: List = []
        try:
            for tr in self.client.list_trades(
                option_ticker,
                date=date_str,
                order="asc",
                limit=self.cfg.trades_limit_per_contract,
            ):
                trades.append(tr)
        except Exception:
            pass
        return trades

    def build_daily_features_for_underlying_and_expiry(
        self, underlying: str, expiry: str | date | datetime
    ) -> pd.DataFrame:
        """
        Build daily aggregated trade features for a specific underlying and expiry.
        Returns a DataFrame with columns:
        [date, ticker, expiry, opt_trades_count, opt_notional, opt_avg_price,
         opt_price_std, opt_min_price, opt_max_price].
        """
        expiry_date = self._to_date(expiry)
        start_d = expiry_date - timedelta(days=self.cfg.days_before_expiry)
        end_d = expiry_date + timedelta(days=self.cfg.days_after_expiry)

        records: List[Dict[str, object]] = []
        current = start_d
        # Cache contract tickers once per expiry
        contract_tickers = self._list_contract_tickers_for_expiry(underlying, expiry_date)
        while current <= end_d:
            prices: List[float] = []
            sizes: List[float] = []
            for opt_ticker in contract_tickers:
                trades = self._list_trades_for_contract_on_date(opt_ticker, current)
                for tr in trades:
                    p = getattr(tr, "price", None)
                    s = getattr(tr, "size", None)
                    if p is not None and s is not None:
                        prices.append(float(p))
                        sizes.append(float(s))
            if len(prices) >= self.cfg.min_trades_per_day:
                prices_ser = pd.Series(prices, dtype=float)
                sizes_ser = pd.Series(sizes, dtype=float)
                total_trades = len(prices)
                notional = float((prices_ser * sizes_ser).sum())
                avg_price = float(prices_ser.mean())
                price_std = float(prices_ser.std(ddof=0))
                min_price = float(prices_ser.min())
                max_price = float(prices_ser.max())
                records.append({
                    "date": current,
                    "ticker": underlying,
                    "expiry": expiry_date,
                    "opt_trades_count": total_trades,
                    "opt_notional": notional,
                    "opt_avg_price": avg_price,
                    "opt_price_std": price_std,
                    "opt_min_price": min_price,
                    "opt_max_price": max_price,
                })
            current += timedelta(days=1)
        return pd.DataFrame(records)
