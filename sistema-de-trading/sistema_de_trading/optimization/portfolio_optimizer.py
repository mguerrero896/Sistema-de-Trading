"""Optimización de carteras con restricciones y costes.

Este módulo implementa la clase :class:`PortfolioOptimizer`, encargada
de calcular matrices de covarianza a partir de series de retornos
históricos y de resolver un problema de optimización convexa para
determinar los pesos óptimos de una cartera. Las restricciones y la
función objetivo se inspiran en el notebook original e incluyen
apalancamiento bruto máximo, exposición neta objetivo, límites por
acción y sector, y un término de penalización por riesgo (varianza) y
costes lineales. Se utiliza ``cvxpy`` como motor de resolución.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

# cvxpy puede no estar instalado en algunos entornos; se importa de forma opcional.
try:
    import cvxpy as cp  # type: ignore
except ImportError:  # pragma: no cover
    cp = None  # type: ignore

from ..config import Config


@dataclass
class OptimizationResult:
    """Contenedor para los resultados de la optimización.

    Atributos
    ---------
    weights : pandas.Series
        Pesos óptimos para cada ticker.
    expected_return : float
        Retorno esperado de la cartera con los pesos resultantes.
    risk : float
        Riesgo (varianza) de la cartera.
    objective_value : float
        Valor final de la función objetivo de optimización.
    status : str
        Estado devuelto por cvxpy (``optimal``, ``infeasible``, etc.).
    """

    weights: pd.Series
    expected_return: float
    risk: float
    objective_value: float
    status: str


class PortfolioOptimizer:
    """Optimiza pesos de una cartera dadas expectativas y covarianzas.

    El optimizador acepta entradas relativamente simples (retornos
    esperados, matriz de covarianza y sectores) y devuelve un
    :class:`OptimizationResult` con los pesos óptimos y métricas
    asociadas. En caso de imposibilidad de resolución, se utiliza un
    esquema de pesos de fallback basado en la señal de retorno esperada.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Cálculo de covarianza
    # ------------------------------------------------------------------
    def calculate_expected_covariance(
        self, returns_df: pd.DataFrame, tickers: Iterable[str], lookback_days: int = 60
    ) -> pd.DataFrame:
        """Calcula la matriz de covarianza de retornos usando un periodo de lookback.

        Los retornos se pivotan a formato ancho (fechas como índices,
        tickers como columnas) y se calcula la covarianza muestral sobre
        las últimas ``lookback_days`` observaciones. Si hay pocas
        observaciones, se toma el máximo disponible.

        Parámetros
        ----------
        returns_df : DataFrame
            DataFrame con columnas ``date``, ``ticker`` y ``return``.
        tickers : iterable de str
            Tickers para los que se requiere la covarianza.
        lookback_days : int
            Número de días hacia atrás para calcular la covarianza.

        Retorna
        -------
        DataFrame
            Matriz de covarianza con índices y columnas en el orden de
            ``tickers``.
        """
        # Filtrar retornos para los tickers solicitados
        sub = returns_df[returns_df["ticker"].isin(tickers)].copy()
        # Pivotar a formato fechas x tickers
        pivot = sub.pivot_table(index="date", columns="ticker", values="return").dropna()
        # Seleccionar últimas filas
        pivot = pivot.tail(lookback_days)
        # Si no hay suficientes datos, rellenar con medias
        if pivot.shape[0] < 2:
            # Covarianza nula si no hay datos; usar matriz identidad con pequeña varianza
            n = len(tickers)
            return pd.DataFrame(0.0001 * np.eye(n), index=tickers, columns=tickers)
        cov = pivot.cov()
        # Reordenar según tickers
        cov = cov.reindex(index=tickers, columns=tickers).fillna(0)
        return cov

    # ------------------------------------------------------------------
    # Optimización de pesos
    # ------------------------------------------------------------------
    def optimize_weights(
        self,
        expected_returns: pd.Series,
        covariance_matrix: pd.DataFrame,
        sectors: pd.Series,
    ) -> OptimizationResult:
        """Resuelve el problema de optimización y devuelve un ``OptimizationResult``.

        La función objetivo maximiza el retorno esperado menos un término
        cuadrático de riesgo ponderado por ``config.lambda_riesgo``. Se
        incluyen restricciones de apalancamiento bruto máximo, exposición
        neta objetivo con tolerancia, límites de peso por acción y sector,
        y un límite específico para el sector tecnológico (si se
        identifica por su nombre).

        Si la optimización resulta infeasible o falla por cualquier
        motivo, se aplica un esquema de fallback que asigna pesos
        proporcionalmente al ranking de retornos esperados, normalizando
        para cumplir con el apalancamiento bruto permitido.

        Parámetros
        ----------
        expected_returns : Series
            Serie con índice de tickers y valores de retorno esperado.
        covariance_matrix : DataFrame
            Matriz de covarianza de los tickers correspondientes.
        sectors : Series
            Serie con índice de tickers e información del sector.

        Retorna
        -------
        OptimizationResult
            Objeto con los pesos resultantes y métricas asociadas.
        """
        tickers = expected_returns.index.tolist()
        n = len(tickers)
        if n == 0:
            raise ValueError("No hay tickers para optimizar.")
        # Si cvxpy no está disponible, retornar pesos de fallback
        if cp is None:
            weights = self._fallback_weights(expected_returns)
            exp_ret = float(np.dot(weights.values, expected_returns.values))
            risk = float(weights.values.T @ covariance_matrix.values @ weights.values)
            return OptimizationResult(weights, exp_ret, risk, np.nan, "cvxpy_unavailable")
        # Variables de decisión
        w = cp.Variable(n)
        mu = expected_returns.values
        Sigma = covariance_matrix.values
        # Función objetivo: maximizar mu^T w - lambda * w^T Sigma w
        risk_term = cp.quad_form(w, Sigma)
        objective = cp.Maximize(mu @ w - self.config.lambda_riesgo * risk_term)
        # Restricciones
        constraints: List = []  # type: ignore
        # Apalancamiento bruto <= límite
        constraints.append(cp.norm1(w) <= self.config.apalancamiento_bruto_max)
        # Exposición neta target dentro de tolerancia
        net_exposure = cp.sum(w)
        constraints.append(net_exposure >= self.config.exposicion_neta_target - self.config.exposicion_neta_tolerancia)
        constraints.append(net_exposure <= self.config.exposicion_neta_target + self.config.exposicion_neta_tolerancia)
        # Límites por acción
        for i in range(n):
            constraints.append(w[i] <= self.config.peso_max_por_accion)
            constraints.append(w[i] >= -self.config.peso_max_por_accion)
        # Límites por sector
        sector_groups: Dict[str, List[int]] = {}
        for i, ticker in enumerate(tickers):
            sec = sectors.loc[ticker] if ticker in sectors.index else "Unknown"
            sector_groups.setdefault(sec, []).append(i)
        for sec, idxs in sector_groups.items():
            limit = self.config.peso_max_tech if sec.lower().startswith("tech") else self.config.peso_max_sector
            if limit > 0:
                constraints.append(cp.sum(cp.abs(w[idxs])) <= limit)
        # Resolver
        problem = cp.Problem(objective, constraints)
        try:
            problem.solve(solver=cp.ECOS, warm_start=True)
        except Exception:
            try:
                problem.solve(solver=cp.SCS)
            except Exception:
                problem.status = "error"
        # Comprobar resultado
        if problem.status not in ("optimal", "optimal_inaccurate"):
            weights = self._fallback_weights(expected_returns)
            exp_ret = float(np.dot(weights.values, expected_returns.values))
            risk = float(weights.values.T @ covariance_matrix.values @ weights.values)
            return OptimizationResult(weights, exp_ret, risk, np.nan, problem.status)
        # Convertir a serie y normalizar con apalancamiento bruto
        raw_w = w.value
        if raw_w is None:
            weights = self._fallback_weights(expected_returns)
            exp_ret = float(np.dot(weights.values, expected_returns.values))
            risk = float(weights.values.T @ covariance_matrix.values @ weights.values)
            return OptimizationResult(weights, exp_ret, risk, np.nan, problem.status)
        weights = pd.Series(raw_w, index=tickers)
        current_leverage = weights.abs().sum()
        if current_leverage > 0:
            weights = weights * (self.config.apalancamiento_bruto_max / current_leverage)
        exp_ret = float(np.dot(weights.values, expected_returns.values))
        risk = float(weights.values.T @ covariance_matrix.values @ weights.values)
        return OptimizationResult(weights, exp_ret, risk, float(problem.value), problem.status)

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------
    def _fallback_weights(self, expected_returns: pd.Series) -> pd.Series:
        """Genera un vector de pesos de fallback basado en el ranking de retornos.

        Cuando el problema de optimización es infeasible o la resolución
        falla, se recurre a un esquema simple en el que los pesos son
        proporcionales a los retornos esperados, normalizados para cumplir
        con la restricción de apalancamiento bruto máximo.

        Parámetros
        ----------
        expected_returns : Series
            Serie de retornos esperados.

        Retorna
        -------
        Series
            Pesos normalizados según el ranking de las señales.
        """
        if expected_returns.empty:
            return pd.Series(dtype=float)
        # Asignar pesos proporcionales a señales positivas y negativas
        pos = expected_returns.clip(lower=0)
        neg = (-expected_returns).clip(lower=0)
        total = pos.sum() + neg.sum()
        if total == 0:
            # Si todos son cero se asignan pesos iguales long/short
            n = len(expected_returns)
            weights = pd.Series(1.0 / n, index=expected_returns.index)
        else:
            long_weights = pos / (pos.sum() + 1e-8)
            short_weights = neg / (neg.sum() + 1e-8)
            weights = long_weights - short_weights
        # Normalizar con apalancamiento bruto
        leverage = weights.abs().sum()
        if leverage > 0:
            weights = weights * (self.config.apalancamiento_bruto_max / leverage)
        return weights