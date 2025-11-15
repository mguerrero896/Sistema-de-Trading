"""Construcción de variables y etiquetas para modelos de machine learning.

La clase :class:`FeatureEngineer` agrupa métodos para:

* Generar características basadas en series de precios (retornos de distintos
  horizontes, volatilidades realizadas, distancias a máximos/mínimos, breakout
  de precios y volumen relativo).
* Calcular métricas de microestructura de mercado como spread estimado,
  volatilidad intradía y participación de volumen.
* Crear características sintéticas de opciones (volatilidad implícita
  simulada) cuando se activa la bandera correspondiente.
* Construir etiquetas de rentabilidad futura a distintos horizontes.
* Normalizar las features por fecha mediante estandarización o ranking.

Todas las funciones operan sobre DataFrames de Pandas y devuelven
nuevos DataFrames con las columnas de features añadidas. No modifican el
DataFrame original in-place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Optional

from ..config import Config


class FeatureEngineer:
    """Generador de características y etiquetas a partir de datos de precios."""

    def __init__(self, config: Config) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Features basadas en precios
    # ------------------------------------------------------------------
    def _price_feats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula características derivadas de precios y volumen.

        Se añaden columnas con retornos acumulados para distintas ventanas,
        volatilidades realizadas, distancias a máximos/mínimos, indicadores de
        breakout y ratios de volumen.
        """
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
        """Calcula características de microestructura de mercado.

        Incluye la estimación del spread, la volatilidad intradía logarítmica
        y la participación relativa del volumen.
        """
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
    # Features sintéticas de opciones
    # ------------------------------------------------------------------
    def _options_synth(self, df: pd.DataFrame) -> pd.DataFrame:
        """Genera características sintéticas relacionadas con opciones.

        Dado que la obtención de datos de opciones no está disponible
        directamente, se simulan series de volatilidad implícita y otras
        variables a partir de la volatilidad realizada y ruido aleatorio.
        """
        df = df.copy()
        rng = np.random.default_rng(self.config.random_seed)
        for t in df["ticker"].unique():
            m = df["ticker"] == t
            s = df.loc[m]
            # Volatilidad realizada a 20 días anualizada
            rv = s["close"].pct_change().rolling(20).std() * np.sqrt(252)
            # Se simula una volatilidad implícita correlacionada con la realizada
            noise = rng.normal(0, 0.05, len(s))
            iv = rv * (1 + noise)
            df.loc[m, "feat_iv_minus_rv"] = iv - rv
            # Pendiente temporal de la IV: relación simple IV - 0.9
            df.loc[m, "feat_iv_term_slope"] = iv - 0.9 * rv
            # Asimetría sintética del orden del 10 %
            df.loc[m, "feat_skew"] = rng.normal(0, 0.1, len(s))
            # Cambios relativos de volumen como proxy de la variación del interés abierto
            df.loc[m, "feat_coil_change"] = s["volume"].pct_change().fillna(0) * 0.5
            # Ratio call/put sintético alrededor de 1 con dispersión
            df.loc[m, "feat_call_put_ratio"] = 1 + rng.normal(0, 0.2, len(s))
        return df

    # ------------------------------------------------------------------
    # Feature wrapper
    # ------------------------------------------------------------------
    def create_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea todas las características disponibles a partir del DataFrame de precios.

        Se concatenan las features de precios, microestructura y opciones (si
        ``config.usar_opciones`` es ``True``). Las columnas de fecha se
        convierten a string para facilitar la operación por fecha en el
        normalizado posterior. Se eliminan las filas con cualquier ``NaN`` en
        las columnas de features.
        """
        df_feat = df.copy()
        df_feat = self._price_feats(df_feat)
        df_feat = self._micro_feats(df_feat)
        if self.config.usar_opciones:
            df_feat = self._options_synth(df_feat)
        # Conversión de fecha a cadena para agrupaciones posteriores
        df_feat["date"] = df_feat["date"].astype(str)
        # Identificar columnas de features
        feat_cols = [c for c in df_feat.columns if c.startswith("feat_")]
        df_feat = df_feat.dropna(subset=feat_cols).reset_index(drop=True)
        return df_feat

    # ------------------------------------------------------------------
    # Etiquetas
    # ------------------------------------------------------------------
    def create_labels(self, df: pd.DataFrame, k_values: List[int]) -> pd.DataFrame:
        """Añade columnas de etiquetas de rentabilidad futura para cada horizonte en ``k_values``.

        La etiqueta ``label_k`` se define como ``(precio_{t+k} / precio_t) - 1``. Si
        el horizonte se extiende más allá del final de la serie, la etiqueta se
        rellena con ``NaN``.
        """
        df = df.sort_values(["ticker", "date"]).copy()
        for k in k_values:
            exit_prices = df.groupby("ticker")["close"].shift(-k)
            df[f"label_{k}"] = exit_prices / df["close"] - 1
        return df

    # ------------------------------------------------------------------
    # Normalización
    # ------------------------------------------------------------------
    def normalize_features(self, df: pd.DataFrame, method: str = "standardize") -> pd.DataFrame:
        """Normaliza las columnas de features por fecha.

        Si ``method`` es ``"standardize"``, se restan medias y dividen por
        desviaciones típicas; si ``method`` es ``"rank"``, se reemplaza cada
        valor por su percentil dentro de la misma fecha. Esta función produce
        una copia del DataFrame con las columnas de features normalizadas.
        """
        df_norm = df.copy()
        feat_cols = [c for c in df_norm.columns if c.startswith("feat_")]
        for d in df_norm["date"].unique():
            m = df_norm["date"] == d
            if method == "standardize":
                mu = df_norm.loc[m, feat_cols].mean()
                sd = df_norm.loc[m, feat_cols].std().replace(0, np.nan)
                df_norm.loc[m, feat_cols] = (df_norm.loc[m, feat_cols] - mu) / (sd + 1e-8)
            else:
                # Ranking porcentual dentro de cada fecha
                df_norm.loc[m, feat_cols] = df_norm.loc[m, feat_cols].rank(pct=True)
        return df_norm