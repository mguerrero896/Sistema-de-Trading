from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import List, Dict

import pandas as pd
from polygon import RESTClient


@dataclass
class OptionsTradesConfig:
    """Configuración para construir features diarios de opciones desde Polygon.

    Este loader:
    - Usa list_options_contracts() para encontrar contratos de un underlying.
    - Usa list_trades() para construir features diarios a nivel subyacente.

    NOTA:
    - No calcula IV todavía; construye features de precio/volumen de opciones
      como paso previo a modelos más complejos.
    """

    contracts_limit: int = 100            # máximo de contratos por underlying
    trades_limit_per_contract: int = 50000  # máximo de trades por contrato (por día)
    min_trades_per_day: int = 1           # mínimo de trades para considerar la fecha


class OptionsTradesLoader:
    """Cargador de datos históricos de opciones basado en trades de Polygon."""

    def __init__(self, cfg: OptionsTradesConfig) -> None:
        self.cfg = cfg
        # RESTClient usará POLYGON_API_KEY desde la variable de entorno
        self.client = RESTClient()

    @staticmethod
    def _to_date(d: str | date | datetime) -> date:
        if isinstance(d, date) and not isinstance(d, datetime):
            return d
        if isinstance(d, datetime):
            return d.date()
        return datetime.strptime(d, "%Y-%m-%d").date()

    # ------------------------------------------------------------------
    # Obtener lista de contratos para un underlying (sin filtrar por expiry)
    # ------------------------------------------------------------------
    def _list_contract_tickers_for_underlying(
        self,
        underlying: str,
    ) -> List[str]:
        """Devuelve la lista de tickers de contratos de opciones para un underlying.

        Usa list_options_contracts(underlying_ticker) y corta a contracts_limit.
        """
        tickers: List[str] = []
        try:
            for c in self.client.list_options_contracts(
                underlying_ticker=underlying,
                limit=self.cfg.contracts_limit,
            ):
                if hasattr(c, "ticker"):
                    tickers.append(c.ticker)
                if len(tickers) >= self.cfg.contracts_limit:
                    break
        except Exception:
            return []
        return tickers

    # ------------------------------------------------------------------
    # Obtener trades de un día para un contrato concreto
    # ------------------------------------------------------------------
    def _list_trades_for_contract_on_date(
        self,
        option_ticker: str,
        d: date,
    ) -> List:
        """Devuelve la lista de trades para un contrato de opción en una fecha concreta."""
        start_ts = d.strftime("%Y-%m-%d")
        end_ts = (d + timedelta(days=1)).strftime("%Y-%m-%d")

        trades: List = []
        try:
            for tr in self.client.list_trades(
                option_ticker,
                timestamp_gte=start_ts,
                timestamp_lte=end_ts,
                limit=self.cfg.trades_limit_per_contract,
            ):
                trades.append(tr)
        except Exception:
            return []

        return trades

    # ------------------------------------------------------------------
    # Construir features diarios para un underlying en un rango de fechas
    # ------------------------------------------------------------------
    def build_daily_features_for_underlying(
        self,
        underlying: str,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
    ) -> pd.DataFrame:
        """Construye features diarios de opciones para un subyacente.

        Para cada fecha d en [start_date, end_date]:
        - Lista contratos de opciones para el underlying (list_options_contracts).
        - Obtiene trades de ese día para cada contrato (list_trades).
        - Agrega todos los trades en features diarios a nivel underlying.

        Retorna un DataFrame con columnas:
        ['date', 'ticker',
         'opt_trades_count', 'opt_notional', 'opt_avg_price',
         'opt_price_std', 'opt_min_price', 'opt_max_price']
        """

        start_d = self._to_date(start_date)
        end_d = self._to_date(end_date)
        if end_d < start_d:
            raise ValueError("end_date debe ser >= start_date")

        # Listamos contratos una sola vez por underlying
        contract_tickers = self._list_contract_tickers_for_underlying(underlying)
        if not contract_tickers:
            return pd.DataFrame(
                columns=[
                    "date",
                    "ticker",
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
        return df

