"""Construcción de variables y etiquetas para modelos de machine learning.

La clase :class:`FeatureEngineer` agrupa métodos para:

* Generar características basadas en series de precios (retornos de distintos
  horizontes, volatilidades realizadas, distancias a máximos/mínimos, breakout
  de precios y volumen relativo).
* Calcular métricas de microestructura de mercado como spread estimado,
  volatilidad intradía y participación de volumen.
* Crear características de opciones (en esta rama expOptions se espera que
  procedan de datos reales agregados, no sintéticos).
* Construir etiquetas de rentabilidad futura a distintos horizontes.
* Normalizar las features por fecha mediante estandarización o ranking.

Todas las funciones operan sobre DataFrames de Pandas y devuelven
nuevos DataFrames con las columnas de features añadidas. No modifican el
DataFrame original in-place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List

from ..config import Config


class FeatureEngineer:
    """Generador de características y etiquetas a partir de datos de precios."""

    def __init__(self, config: Config) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Features basadas en precios
    # ------------------------------------------------------------------
    def _price_feats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula características derivadas de precios y volumen."""
        df = df.sort_values(["ticker", "date"]).copy()
        for t in df["ticker"].unique():
            m = df["ticker"] == t
            s = df.loc[m]
            # Retornos acumulados a distintas ventanas
            for w in self.config.ventanas_rendimiento:
                df.loc[m, f"feat_ret_{w}d"] = s["close"].pct_change(w)
            # Volatilidad realizada con ventana fija
            ret = s["close"].pct_change()
            w = self.config.ventana_vol_realizada
            df.loc[m, f"feat_vol_real_{w}d"] = ret.rolling(w).std() * np.sqrt(252)
            # Distancia a máximos y mínimos de largo plazo
            wmn = self.config.ventana_max_min
            roll_max = s["close"].rolling(wmn).max()
            roll_min = s["close"].rolling(wmn).min()
            df.loc[m, "feat_dist_to_max"] = s["close"] / roll_max - 1
            df.loc[m, "feat_dist_to_min"] = s["close"] / roll_min - 1
            # Breakout por precio y volumen relativo
            vol_ratio = s["volume"] / s["volume"].rolling(self.config.ventana_volumen).mean()
            breakout = (s["close"] > roll_max.shift(1)) & (vol_ratio > 1.5)
            df.loc[m, "feat_breakout"] = breakout.astype(int)
            # Ratio de volatilidad relativa (media de retornos sobre desviación típica)
            df.loc[m, "feat_vol_relative"] = ret.rolling(w).mean() / (ret.std() + 1e-8)
        return df

    # ------------------------------------------------------------------
    # Features de microestructura
    # ------------------------------------------------------------------
    def _micro_feats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula características de microestructura de mercado."""
        df = df.copy()
        # Spread estimado como (high - low) / close
        df["feat_spread_est"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
        # Volatilidad intradía como log(high/low)
        df["feat_intraday_vol"] = np.log(df["high"] / df["low"]).replace(0, np.nan)
        # Participación de volumen: desviación estándar normalizada del volumen
        for t in df["ticker"].unique():
            m = df["ticker"] == t
            s = df.loc[m]
            mu = s["volume"].rolling(20).mean()
            sd = s["volume"].rolling(20).std()
            df.loc[m, "feat_participation"] = (s["volume"] - mu) / (sd + 1e-8)
        return df

    # ------------------------------------------------------------------
    # Features de opciones basadas en trades reales (expOptions)
    # ------------------------------------------------------------------
    def _options_real(self, df: pd.DataFrame) -> pd.DataFrame:
        """Construye features de opciones reales a partir de trades agregados.

        Se asume que df contiene columnas creadas por OptionsTradesLoader:
        - opt_trades_count
        - opt_notional
        - opt_avg_price
        - opt_price_std
        - opt_min_price
        - opt_max_price
        """
        df = df.copy()

        if "opt_trades_count" in df.columns:
            df["feat_opt_trades_count"] = df["opt_trades_count"]

        if "opt_notional" in df.columns:
            df["feat_opt_notional_log"] = np.log1p(df["opt_notional"])

        if "opt_price_std" in df.columns:
            df["feat_opt_price_std"] = df["opt_price_std"]

        if "opt_max_price" in df.columns and "opt_min_price" in df.columns:
            df["feat_opt_price_range"] = df["opt_max_price"] - df["opt_min_price"]

        return df

    # ------------------------------------------------------------------
    # Features sintéticas de opciones (NO usadas en expOptions)
    # ------------------------------------------------------------------
    def _options_synth(self, df: pd.DataFrame) -> pd.DataFrame:
        """Genera características sintéticas relacionadas con opciones.

        En la rama expOptions NO se utiliza este método; se mantiene únicamente
        por compatibilidad. Las únicas features de opciones que se usan aquí
        son las basadas en datos reales (_options_real).
        """
        df = df.copy()
        rng = np.random.default_rng(self.config.random_seed)
        for t in df["ticker"].unique():
            m = df["ticker"] == t
            s = df.loc[m]
            rv = s["close"].pct_change().rolling(20).std() * np.sqrt(252)
            noise = rng.normal(0, 0.05, len(s))
            iv = rv * (1 + noise)
            df.loc[m, "feat_iv_minus_rv"] = iv - rv
            df.loc[m, "feat_iv_term_slope"] = iv - 0.9 * rv
            df.loc[m, "feat_skew"] = rng.normal(0, 0.1, len(s))
            df.loc[m, "feat_coil_change"] = s["volume"].pct_change().fillna(0) * 0.5
            df.loc[m, "feat_call_put_ratio"] = 1 + rng.normal(0, 0.2, len(s))
        return df

    # ------------------------------------------------------------------
    # Feature wrapper
    # ------------------------------------------------------------------
    def create_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea todas las características disponibles a partir del DataFrame de precios.

        En expOptions se concatenan:
        - features de precios (si usar_features_precio),
        - features de microestructura (si usar_features_micro),
        - features de opciones reales (si usar_features_opciones).

        Las columnas de fecha se convierten a string para facilitar la operación
        por fecha en el normalizado posterior. Se eliminan las filas con
        cualquier ``NaN`` en las columnas de features.
        """
        df_feat = df.copy()

        # Features de precio
        if self.config.usar_features_precio:
            df_feat = self._price_feats(df_feat)

        # Features de microestructura
        if self.config.usar_features_micro:
            df_feat = self._micro_feats(df_feat)

        # Features de opciones REAL (no sintéticas) en expOptions
        if self.config.usar_features_opciones:
            df_feat = self._options_real(df_feat)

        # Aseguramos que todos los nombres de columna sean strings
        df_feat.columns = [str(c) for c in df_feat.columns]

        # Conversión de fecha a cadena para agrupaciones posteriores
        df_feat["date"] = df_feat["date"].astype(str)

        # Identificar columnas de features
        feat_cols = [c for c in df_feat.columns if c.startswith("feat_")]

        # Eliminar filas con NaN en alguna feature
        df_feat = df_feat.dropna(subset=feat_cols).reset_index(drop=True)
        return df_feat

    # ------------------------------------------------------------------
    # Etiquetas
    # ------------------------------------------------------------------
    def create_labels(self, df: pd.DataFrame, k_values: List[int]) -> pd.DataFrame:
        """Añade columnas de etiquetas de rentabilidad futura para cada horizonte en ``k_values``."""
        df = df.sort_values(["ticker", "date"]).copy()
        for k in k_values:
            exit_prices = df.groupby("ticker")["close"].shift(-k)
            df[f"label_{k}"] = exit_prices / df["close"] - 1
        return df

    # ------------------------------------------------------------------
    # Normalización
    # ------------------------------------------------------------------
    def normalize_features(self, df: pd.DataFrame, method: str = "standardize") -> pd.DataFrame:
        """Normaliza las columnas de features por fecha."""
        df_norm = df.copy()

        # Asegurar que los nombres de columnas sean strings
        df_norm.columns = [str(c) for c in df_norm.columns]

        feat_cols = [c for c in df_norm.columns if c.startswith("feat_")]

        # Nos aseguramos de trabajar con fechas como string
        df_norm["date"] = df_norm["date"].astype(str)

        for d in df_norm["date"].unique():
            m = df_norm["date"] == d
            if method == "standardize":
                mu = df_norm.loc[m, feat_cols].mean()
                sd = df_norm.loc[m, feat_cols].std().replace(0, np.nan)
                df_norm.loc[m, feat_cols] = (df_norm.loc[m, feat_cols] - mu) / (sd + 1e-8)
            else:
                df_norm.loc[m, feat_cols] = df_norm.loc[m, feat_cols].rank(pct=True)
        return df_norm


