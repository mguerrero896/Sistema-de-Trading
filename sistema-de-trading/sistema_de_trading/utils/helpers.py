"""Funciones auxiliares para el cálculo de métricas y otras utilidades.

Actualmente se implementa ``compute_performance_metrics`` para calcular
estadísticas básicas de una serie de rendimientos: volatilidad,
Sharpe ratio y drawdown máximo. Estas métricas se utilizan en el
backtester para evaluar el desempeño de la cartera.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict


def compute_performance_metrics(returns: pd.Series) -> Dict[str, float]:
    """Calcula métricas de performance básicas a partir de una serie de retornos.

    La volatilidad se anualiza suponiendo 252 días de trading. El ratio de
    Sharpe se calcula como el retorno medio dividido por la volatilidad,
    asumiendo tasa libre de riesgo cero. El drawdown máximo se deriva de
    la serie acumulativa de capital.

    Parámetros
    ----------
    returns : Series
        Serie de retornos periódicos (diarios).

    Retorna
    -------
    dict
        Diccionario con claves ``annual_volatility``, ``sharpe_ratio`` y
        ``max_drawdown``.
    """
    # Convertir a numpy ignorando NaNs
    r = returns.dropna().values
    if len(r) == 0:
        return {"annual_volatility": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}
    # Volatilidad anualizada
    vol = np.std(r, ddof=1) * np.sqrt(252)
    # Retorno medio anualizado
    mean_return = np.mean(r) * 252
    sharpe = mean_return / (vol + 1e-8)
    # Calcular drawdown
    cumulative = np.cumprod(1 + r)
    peak = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - peak) / peak
    max_dd = float(drawdowns.min())
    return {
        "annual_volatility": float(vol),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(-max_dd),
    }