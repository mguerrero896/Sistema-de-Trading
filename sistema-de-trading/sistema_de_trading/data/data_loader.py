"""Descarga y preprocesamiento de datos de mercado y fundamentales.

Este módulo implementa la clase :class:`DataLoader`, encargada de:

* Obtener el universo de tickers (por defecto los constituyentes del S&P 500)
* Descargar precios OHLC diarios desde Polygon.io o como alternativa desde
  yfinance en caso de fallo o ausencia de clave API.
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
    """Clase para descargar datos de mercado y fundamentales.

    Parámetros
    ----------
    polygon_key : str
        Clave de API para Polygon.io. Si está vacía, se omitirá la descarga desde
        Polygon y se usará `yfinance` como fuente alternativa.
    fmp_key : str
        Clave de API para Financial Modeling Prep. Se utiliza para obtener
        constituyentes del S&P 500 y datos de perfil de empresas.
    """

    # Lista estática de tickers S&P500 utilizada como fallback cuando la API falla
    _STATIC_TICKERS: List[str] = [
        'AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','BRK.B','UNH','JNJ','V','XOM','WMT','JPM','PG','MA',
        'CVX','HD','LLY','ABBV','MRK','PFE','KO','PEP','COST','AVGO','MCD','CSCO','ABT','ADBE','TXN','CRM',
        'LIN','QCOM','ORCL','INTC','AMD','GE','CAT','IBM','AXP','AMGN','LOW','BLK','DE','SYK','INTU','GILD',
        'ADP','TJX'
    ]

    def __init__(self, polygon_key: str = "", fmp_key: str = "") -> None:
        self.session = requests.Session()
        self.polygon_key = polygon_key or ""
        self.fmp_key = fmp_key or ""

    # ------------------------------------------------------------------
    # Universo de activos
    # ------------------------------------------------------------------
    def get_sp500_tickers(self, limit: Optional[int] = None) -> List[str]:
        """Devuelve una lista de tickers del S&P 500.

        Si la llamada a FMP falla o devuelve una lista vacía, se devuelve una
        lista estática predeterminada.

        Parámetros
        ----------
        limit : int, opcional
            Si se especifica, limita el número de tickers devueltos.
        """
        tickers: List[str] = []
        try:
            url = "https://financialmodelingprep.com/api/v3/sp500_constituent"
            params = {"apikey": self.fmp_key} if self.fmp_key else {}
            data = self.session.get(url, params=params, timeout=30).json()
            tickers = [x.get("symbol") for x in data if "symbol" in x]
            # Filtrar valores None
            tickers = [t for t in tickers if t]
            if not tickers:
                raise ValueError("Respuesta vacía de FMP")
        except Exception:
            # Fallback a lista estática cuando falla la API
            tickers = self._STATIC_TICKERS.copy()
        if limit:
            return tickers[:limit]
        return tickers

    # ------------------------------------------------------------------
    # Descarga de precios
    # ------------------------------------------------------------------
    def _polygon_ohlc(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga precios diarios de Polygon.io en formato OHLC.

        Devuelve ``None`` si la respuesta es inválida o se produce algún
        error de red. Las fechas deben especificarse en formato ``YYYY-MM-DD``.
        """
        if not self.polygon_key:
            return None
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {"adjusted": "true", "sort": "asc", "apikey": self.polygon_key}
        try:
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code != 200:
                return None
            j = r.json()
            results = j.get("results")
            if not results:
                return None
            df = pd.DataFrame(results)
            df = df.rename(
                columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
            )
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.date
            return df[["date", "open", "high", "low", "close", "volume"]]
        except Exception:
            return None

    def _yfinance_ohlc(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga precios diarios utilizando yfinance como fuente alternativa.

        Si no se puede obtener el DataFrame o éste es vacío, devuelve ``None``.
        """
        try:
            import yfinance as yf

            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                return None
            df = df.reset_index()
            df = df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df[["date", "open", "high", "low", "close", "volume"]]
        except Exception:
            return None

    def download_price_data(self, tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Descarga precios OHLC para una lista de tickers en el intervalo dado.

        Se intenta primero con Polygon; en caso de fallo se recurre a yfinance. El
        resultado es un DataFrame con las columnas ``ticker``, ``date``, ``open``,
        ``high``, ``low``, ``close`` y ``volume``. Cuando no se obtienen datos para
        ningún ticker se lanza una excepción.
        """
        all_frames = []
        failed = []
        for t in tickers:
            df = self._polygon_ohlc(t, start_date, end_date)
            if df is None:
                df = self._yfinance_ohlc(t, start_date, end_date)
            if df is None:
                failed.append(t)
                continue
            df = df.copy()
            df["ticker"] = t
            all_frames.append(df)
            # Respetar límites de la API evitando burst
            time.sleep(0.15)
        if not all_frames:
            raise RuntimeError("No se descargaron datos de precios para los tickers indicados.")
        out = pd.concat(all_frames, ignore_index=True)
        if failed:
            # Mensaje informativo sobre tickers sin datos, sin interrumpir el flujo
            print(f"△ Tickers sin datos: {len(failed)} -> {failed}")
        return out

    # ------------------------------------------------------------------
    # Descarga de fundamentales
    # ------------------------------------------------------------------
    def download_fundamentals(self, tickers: List[str]) -> pd.DataFrame:
        """Descarga datos de perfil de empresa para los tickers especificados.

        Devuelve un DataFrame con columnas ``ticker``, ``sector``, ``industry`` y
        ``market_cap``. Si la API de FMP no está disponible o responde con
        información vacía, se devuelven valores por defecto.
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
                # Pequeña pausa para no saturar la API
                time.sleep(0.05)
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Filtro de datos
    # ------------------------------------------------------------------
    def apply_filters(self, df: pd.DataFrame, min_price: float, min_volume: float, window: int) -> pd.DataFrame:
        """Filtra el DataFrame de precios según un precio y volumen mínimo.

        Se calcula el precio medio por ticker y un volumen medio rolling de
        longitud ``window``. Se conservan únicamente aquellos tickers que cumplen
        ambos criterios.
        """
        # Calcular estadísticas por ticker
        g = df.groupby("ticker").agg(
            avg_price=("close", "mean"),
            avg_volume=("volume", lambda x: x.rolling(window, min_periods=1).mean().mean()),
        ).reset_index()
        keep = g[(g["avg_price"] >= min_price) & (g["avg_volume"] >= min_volume)]["ticker"].tolist()
        return df[df["ticker"].isin(keep)].copy()