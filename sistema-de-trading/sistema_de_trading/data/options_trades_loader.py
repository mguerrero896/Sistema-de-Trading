from __future__ import annotations

import os
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

        # Prefer explicit parameter; fallback to environment variable if not provided
        if not api_key:
            api_key = os.getenv("POLYGON_API_KEY", "")

        if not api_key:
            raise ValueError(
                "No se proporcionó api_key y POLYGON_API_KEY no está definida en el entorno."
            )

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
        """Return option contract tickers for a given underlying and expiration date.
        
        Polygon recomienda usar filtros de fecha mediante el diccionario `params`
        con claves `expiration_date.gte` y `expiration_date.lte` para filtrar
        del lado del servidor.
        """
        expiry_str = expiry.strftime("%Y-%m-%d")
        tickers: List[str] = []
        try:
            for c in self.client.list_options_contracts(
                underlying_ticker=underlying,
                expiration_date=expiry_str,
                expired=True,  # Required to get historical/expired contracts
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
        
        Uses timestamp_gte and timestamp_lte parameters as recommended by Polygon API.
        Timestamps are in UTC timezone (Z suffix).
        
        Available fields in trade objects:
        - price: Trade price
        - size: Trade size (number of contracts)
        - timestamp: Trade timestamp (nanoseconds since epoch)
        - exchange: Exchange code
        - conditions: Trade conditions
        - transaction_id: Unique transaction ID
        - tape: Tape identifier
        """
        # Convert date to UTC timestamp strings
        timestamp_gte = f"{trade_date.strftime('%Y-%m-%d')}T00:00:00Z"
        timestamp_lte = f"{trade_date.strftime('%Y-%m-%d')}T23:59:59Z"
        
        trades: List = []
        try:
            for tr in self.client.list_trades(
                option_ticker,
                timestamp_gte=timestamp_gte,
                timestamp_lte=timestamp_lte,
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
        
        # Debug messages when no contracts or trades found
        if not contract_tickers:
            print(
                f"[OptionsTradesLoader] No se encontraron contratos para "
                f"{underlying} con expiry {expiry_date}. "
                "Verifica que exista esa expiración para el subyacente y que "
                "tu plan de Polygon la cubra."
            )
        
        if not records:
            print(
                f"[OptionsTradesLoader] No se encontraron trades para "
                f"{underlying} con expiry {expiry_date} en el rango "
                f"[{start_d}, {end_d}]. "
                "Si estás usando una fecha de expiración futura, es normal que "
                "no haya trades históricos."
            )
        
        return pd.DataFrame(records)

    def debug_list_contracts(self, underlying: str, expiry: str | date | datetime) -> None:
        """Helper method to inspect available contracts for debugging.
        
        Prints the number of contracts found and lists up to 20 contract tickers.
        Useful for troubleshooting when no trades are found.
        """
        expiry_date = self._to_date(expiry)
        expiry_str = expiry_date.strftime("%Y-%m-%d")
        tickers = self._list_contract_tickers_for_expiry(underlying, expiry_date)
        print(
            f"[OptionsTradesLoader] Contratos para {underlying} "
            f"con expiry {expiry_str}: {len(tickers)}"
        )
        if tickers:
            print("Primeros contratos:")
            print(tickers[:20])
        else:
            print("No se encontraron contratos.")


