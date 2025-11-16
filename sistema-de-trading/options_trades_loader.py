from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

import pandas as pd
from polygon import RESTClient


@dataclass
class OptionsTradesConfig:
    """Configuración para construir features diarios de opciones desde Polygon.

    Este loader:
    - Usa list_options_contracts() para encontrar contratos por underlying y vencimiento.
    - Usa list_trades() para construir features diarios a nivel subyacente.

    NOTA:
    - No calcula IV todavía; construye features de precio/volumen de opciones
      como paso previo a modelos más complejos.
    """

    days_to_expiry: int = 30              # horizonte de vencimiento objetivo (ej. +30 días)
    contracts_limit: int = 100            # máximo de contratos por underlying/expiry
    trades_limit_per_contract: int = 50000  # máximo de trades por contrato (por día)
    min_trades_per_day: int = 1           # mínimo de trades para considerar la fecha


class OptionsTradesLoader:
    """Cargador de datos históricos de opciones basado en trades de Polygon.

    Uso típico (ejemplo):
    ---------------------
    from sistema_de_trading.data.options_trades_loader import OptionsTradesLoader, OptionsTradesConfig

    cfg = OptionsTradesConfig(days_to_expiry=30, contracts_limit=50)
    loader = OptionsTradesLoader(cfg)
    df_opt = loader.build_daily_features_for_underlying(
        underlying="AAPL",
        start_date="2024-01-01",
        end_date="2024-03-31",
    )

    df_opt tendrá una fila por día con columnas:
    ['date', 'ticker',
     'opt_trades_count', 'opt_notional', 'opt_avg_price',
     'opt_price_std', 'opt_min_price', 'opt_max_price']
    """

    def __init__(self, cfg: OptionsTradesConfig) -> None:
        self.cfg = cfg
        # RESTClient usará POLYGON_API_KEY desde la variable de entorno
        self.client = RESTClient()

    # ------------------------------------------------------------------
    # Utilidad interna: convertir string/datetime a date
    # ------------------------------------------------------------------
    @staticmethod
    def _to_date(d: str | date | datetime) -> date:
        if isinstance(d, date) and not isinstance(d, datetime):
            return d
        if isinstance(d, datetime):
            return d.date()
        return datetime.strptime(d, "%Y-%m-%d").date()

    # ------------------------------------------------------------------
    # Obtener lista de contratos para un underlying y un vencimiento
    # ------------------------------------------------------------------
    def _list_contract_tickers_for_expiry(
        self,
        underlying: str,
        expiry: date,
    ) -> List[str]:
        """Devuelve la lista de tickers de contratos de opciones para un underlying+expiry.

        Usa list_options_contracts(underlying_ticker, expiration_date).
        """
        expiry_str = expiry.strftime("%Y-%m-%d")
        tickers: List[str] = []

        try:
            for c in self.client.list_options_contracts(
                underlying_ticker=underlying,
                expiration_date=expiry_str,
                limit=self.cfg.contracts_limit,
            ):
                # Asumimos que cada contrato tiene atributo .ticker
                if hasattr(c, "ticker"):
                    tickers.append(c.ticker)
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
        """Devuelve la lista de trades para un contrato de opción en una fecha concreta.

        Usa list_trades(option_ticker, timestamp_gte, timestamp_lte).
        """
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
        - Determina un vencimiento objetivo d + days_to_expiry.
        - Lista contratos de opciones para ese vencimiento (list_options_contracts).
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

        records: List[Dict[str, object]] = []

        current = start_d
        while current <= end_d:
            target_expiry = current + timedelta(days=self.cfg.days_to_expiry)

            # 1) Listar contratos para este underlying y vencimiento
            contract_tickers = self._list_contract_tickers_for_expiry(underlying, target_expiry)
            if not contract_tickers:
                current += timedelta(days=1)
                continue

            prices: List[float] = []
            sizes: List[float] = []

            # 2) Recoger trades de esos contratos en el día current
            for opt_ticker in contract_tickers:
                trades = self._list_trades_for_contract_on_date(opt_ticker, current)
                for tr in trades:
                    # Atributos confirmados: price, size, sip_timestamp, participant_timestamp, exchange, conditions
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
