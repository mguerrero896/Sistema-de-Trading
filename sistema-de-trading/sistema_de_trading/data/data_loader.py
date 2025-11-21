"""Descarga y preprocesamiento de datos de mercado y fundamentales.

Este módulo implementa la clase :class:`DataLoader`, encargada de:

* Obtener el universo de tickers (por defecto los constituyentes del S&P 500)
* Descargar precios OHLC diarios desde FMP (Financial Modeling Prep).
* Descargar datos fundamentales como sector, industria y capitalización de
  mercado desde Financial Modeling Prep.
* Aplicar filtros básicos de liquidez y precio mínimo.

Las funciones manejan excepciones de red y proporcionan listas de tickers
estáticas cuando las llamadas a APIs externas fallan, garantizando así que
el resto del pipeline pueda ejecutarse incluso en entornos sin conexión.
"""

from __future__ import annotations

import time
from typing import List, Optional

import numpy as np
import pandas as pd
import requests



class DataLoader:
    """Descarga y preprocesamiento de datos de mercado y fundamentales.

    Usa FMP (Financial Modeling Prep) como fuente única para OHLC diario
    mediante el endpoint `/v3/historical-price-full/{symbol}`.

    Requiere una API key válida de FMP Ultimate plan para acceso completo
    a datos históricos de acciones y fundamentales.
    """

    # Lista estática de tickers S&P500 utilizada sólo como fallback
    _STATIC_TICKERS: List[str] = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH", "JNJ",
        "V", "XOM", "WMT", "JPM", "PG", "MA", "CVX", "HD", "LLY", "ABBV",
        "MRK", "PFE", "KO", "PEP", "COST", "AVGO", "MCD", "CSCO", "ABT", "ADBE",
    ]

    def __init__(self, polygon_key: str = "", fmp_key: str = "") -> None:
        self.session = requests.Session()
        self.polygon_key = polygon_key or ""
        self.fmp_key = fmp_key or ""

    # ------------------------------------------------------------------
    # Universo de activos
    # ------------------------------------------------------------------
    def get_sp500_tickers(self, limit: Optional[int] = None) -> List[str]:
        """Devuelve una lista de tickers del S&P 500 usando FMP.

        Si la llamada a FMP falla, se devuelve una lista estática de fallback.
        """
        tickers: List[str] = []
        try:
            url = "https://financialmodelingprep.com/api/v3/sp500_constituent"
            params = {"apikey": self.fmp_key} if self.fmp_key else {}
            r = self.session.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            tickers = [x.get("symbol") for x in data if "symbol" in x]
            tickers = [t for t in tickers if t]
            if not tickers:
                raise ValueError("Respuesta vacía de FMP")
        except Exception:
            tickers = self._STATIC_TICKERS.copy()

        if limit:
            return tickers[:limit]
        return tickers

    # ------------------------------------------------------------------
    # OHLC diario desde FMP
    # ------------------------------------------------------------------
    def _fmp_ohlc(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga precios diarios OHLCV desde FMP para un ticker.

        Endpoint: /v3/historical-price-full/{symbol}?from=YYYY-MM-DD&to=YYYY-MM-DD
        """
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}"
        params = {"from": start_date, "to": end_date}
        if self.fmp_key:
            params["apikey"] = self.fmp_key
        try:
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code != 200:
                return None
            j = r.json()
            hist = j.get("historical", [])
            if not hist:
                return None
            df = pd.DataFrame(hist)
            # Asegurar columnas estándar
            required_cols = {"date", "open", "high", "low", "close", "volume"}
            missing = required_cols - set(df.columns)
            if missing:
                return None
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df[["date", "open", "high", "low", "close", "volume"]]
        except Exception:
            return None



    def download_price_data(self, tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Descarga precios OHLCV para una lista de tickers usando FMP.

        Usa FMP (Financial Modeling Prep) como fuente única de datos.
        Si FMP falla para un ticker, ese ticker se marca como fallido.

        Devuelve un DataFrame con columnas:
        ``date, open, high, low, close, volume, ticker``.

        Si no se obtiene ningún dato para ningún ticker desde FMP,
        lanza un RuntimeError.
        """
        all_frames = []
        failed: List[str] = []

        for t in tickers:
            df = self._fmp_ohlc(t, start_date, end_date)

            if df is None or df.empty:
                failed.append(t)
                continue

            df = df.copy()
            df["ticker"] = t
            all_frames.append(df)
            time.sleep(0.05)

        if not all_frames:
            raise RuntimeError(
                "No se descargaron datos de precios para los tickers indicados desde FMP. "
                "Verifica tu API key y que los tickers sean válidos."
            )

        out = pd.concat(all_frames, ignore_index=True)

        if failed:
            print(f"△ Tickers sin datos de FMP ({len(failed)}): {failed}")

        return out

    # ------------------------------------------------------------------
    # Descarga de fundamentales
    # ------------------------------------------------------------------
    def download_fundamentals(self, tickers: List[str]) -> pd.DataFrame:
        """Descarga datos básicos de perfil de empresa desde FMP.

        Devuelve un DataFrame con columnas: ``ticker, sector, industry, market_cap``.
        """
        rows = []
        for t in tickers:
            try:
                url = f"https://financialmodelingprep.com/api/v3/profile/{t}"
                params = {"apikey": self.fmp_key} if self.fmp_key else {}
                j = self.session.get(url, params=params, timeout=30).json()
                if j:
                    info = j[0]
                    rows.append(
                        {
                            "ticker": t,
                            "sector": info.get("sector", "Unknown"),
                            "industry": info.get("industry", "Unknown"),
                            "market_cap": info.get("mktCap", 0),
                        }
                    )
                else:
                    rows.append({"ticker": t, "sector": "Unknown", "industry": "Unknown", "market_cap": 0})
            except Exception:
                rows.append({"ticker": t, "sector": "Unknown", "industry": "Unknown", "market_cap": 0})
                time.sleep(0.05)
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Filtro de datos
    # ------------------------------------------------------------------
    def apply_filters(self, df: pd.DataFrame, min_price: float, min_volume: float, window: int) -> pd.DataFrame:
        """Filtra el DataFrame de precios según precio y volumen mínimo.

        Calcula un precio medio por ticker y un volumen medio rolling; conserva
        sólo los tickers que cumplen ambos criterios.
        """
        g = df.groupby("ticker").agg(
            avg_price=("close", "mean"),
            avg_volume=("volume", lambda x: x.rolling(window, min_periods=1).mean().mean()),
        ).reset_index()

        keep = g[
            (g["avg_price"] >= min_price) &
            (g["avg_volume"] >= min_volume)
        ]["ticker"].tolist()

        return df[df["ticker"].isin(keep)].copy()
