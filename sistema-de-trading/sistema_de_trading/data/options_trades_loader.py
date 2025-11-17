from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import List, Dict

import os
import pandas as pd
from polygon import RESTClient


@dataclass
class OptionsTradesConfig:
    """Config para features diarios de opciones desde Polygon (por underlying+expiry).

    Este loader:
    - Usa list_options_contracts(underlying_ticker, expiration_date) para obtener
      los contratos de un vencimiento específico.
    - Usa list_trades(ticker, date=...) para obtener trades de cada contrato
      en cada día del rango.
    """

    days_before_expiry: int = 30      # días antes del vencimiento que queremos cubrir
    days_after_expiry: int = 0        # días después del vencimiento (normalmente 0)
    contracts_limit: int = 200        # máximo de contratos por underlying/expiry
    trades_limit_per_contract: int = 50000  # máximo de trades por contrato y día
    min_trades_per_day: int = 1       # mínimo de trades para considerar la fecha


class OptionsTradesLoader:
    """Cargador de features diarios de opciones para (underlying, expiry) concretos."""

    def __init__(self, cfg: OptionsTradesConfig, api_key: str | None = None) -> None:
        self.cfg = cfg

        # Preferimos api_key explícito; si no viene, usamos la env var.
        if api_key is None:
            api_key = os.getenv("POLYGON_API_KEY")

        if not api_key:
            raise ValueError(
                "Debe proporcionar api_key al constructor o configurar POLYGON_API_KEY en el entorno."
            )

        self.client = RESTClient(api_key=api_key)

    # -------------------- utilidades de fecha --------------------

    @staticmethod
    def _to_date(d: str | date | datetime) -> date:
        if isinstance(d, date) and not isinstance(d, datetime):
            return d
        if isinstance(d, datetime):
            return d.date()
        return datetime.strptime(d, "%Y-%m-%d").date()

    # -------------------- contratos por underlying+expiry --------------------

    def _list_contract_tickers_for_expiry(
        self,
        underlying: str,
        expiry: date,
    ) -> List[str]:
        """Devuelve los tickers de opciones para un underlying en un expiry concreto."""
        expiry_str = expiry.strftime("%Y-%m-%d")
        tickers: List[str] = []
        try:
            for c in self.client.list_options_contracts(
                underlying_ticker=underlying,
                expiration_date=expiry_str,
                limit=self.cfg.contracts_limit,
            ):
                if hasattr(c, "ticker"):
                    tickers.append(c.ticker)
        except Exception:
            return []
        return tickers

    # -------------------- trades por día y contrato --------------------

    def _list_trades_for_contract_on_date(
        self,
        option_ticker: str,
        d: date,
    ) -> List:
        """Devuelve trades de un contrato de opción en una fecha concreta (usando date=...)."""
        date_str = d.strftime("%Y-%m-%d")
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
            return []
        return trades

    # -------------------- features diarios para underlying+expiry --------------------

    def build_daily_features_for_underlying_and_expiry(
        self,
        underlying: str,
        expiry_date: str | date | datetime,
    ) -> pd.DataFrame:
        """Construye features diarios de opciones para (underlying, expiry).

        - underlying: ej. "AAPL"
        - expiry_date: ej. "2025-11-21"

        El rango de fechas que se cubre es:
            [expiry - days_before_expiry, expiry + days_after_expiry]
        """

        expiry = self._to_date(expiry_date)
        start_d = expiry - timedelta(days=self.cfg.days_before_expiry)
        end_d = expiry + timedelta(days=self.cfg.days_after_expiry)

        # 1) Obtener contratos para este underlying+expiry
        contract_tickers = self._list_contract_tickers_for_expiry(underlying, expiry)
        if not contract_tickers:
            return pd.DataFrame(
                columns=[
                    "date",
                    "ticker",
                    "expiry",
                    "opt_trades_count",
                    "opt_notional",
                    "opt_avg_price",
                    "opt_price_std",
                    "opt_min_price",
                    "opt_max_price",
                ]
            )

        records: List[Dict[str, object]] = []

        current = start_d
        while current <= end_d:
            prices: List[float] = []
            sizes: List[float] = []

            for opt_ticker in contract_tickers:
                trades = self._list_trades_for_contract_on_date(opt_ticker, current)
                for tr in trades:
                    p = getattr(tr, "price", None)
                    s = getattr(tr, "size", None)
                    if p is None or s is None:
                        continue
                    prices.append(float(p))
                    sizes.append(float(s))

            if len(prices) < self.cfg.min_trades_per_day:
                current += timedelta(days=1)
                continue

            prices_ser = pd.Series(prices, dtype=float)
            sizes_ser = pd.Series(sizes, dtype=float)

            total_trades = int(len(prices))
            notional = float((prices_ser * sizes_ser).sum())
            avg_price = float(prices_ser.mean())
            price_std = float(prices_ser.std(ddof=0))
            min_price = float(prices_ser.min())
            max_price = float(prices_ser.max())

            records.append(
                {
                    "date": current,
                    "ticker": underlying,
                    "expiry": expiry,
                    "opt_trades_count": total_trades,
                    "opt_notional": notional,
                    "opt_avg_price": avg_price,
                    "opt_price_std": price_std,
                    "opt_min_price": min_price,
                    "opt_max_price": max_price,
                }
            )

            current += timedelta(days=1)

        if not records:
            return pd.DataFrame(
                columns=[
                    "date",
                    "ticker",
                    "expiry",
                    "opt_trades_count",
                    "opt_notional",
                    "opt_avg_price",
                    "opt_price_std",
                    "opt_min_price",
                    "opt_max_price",
                ]
            )

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df["expiry"] = pd.to_datetime(df["expiry"])
        return df

