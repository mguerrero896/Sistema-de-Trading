"""Performance metric utilities."""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.sandwich_covariance import cov_hac


def sharpe_ratio(returns: pd.Series, ann_factor: int = 252) -> float:
    cleaned = returns.dropna()
    if cleaned.std() == 0:
        return 0.0
    return float((cleaned.mean() / cleaned.std()) * np.sqrt(ann_factor))


def sortino_ratio(returns: pd.Series, ann_factor: int = 252) -> float:
    cleaned = returns.dropna()
    downside = cleaned[cleaned < 0]
    if downside.std() == 0:
        return 0.0
    return float((cleaned.mean() / downside.std()) * np.sqrt(ann_factor))


def max_drawdown(series: pd.Series) -> float:
    data = series.dropna().astype(float)
    if data.empty:
        return 0.0
    running_max = data.cummax()
    drawdown = (data - running_max) / running_max
    return float(drawdown.min())


def calmar_ratio(returns: pd.Series, equity: pd.Series, ann_factor: int = 252) -> float:
    mdd = abs(max_drawdown(equity))
    if mdd == 0:
        return 0.0
    return float(returns.mean() * ann_factor / mdd)


def expected_shortfall(returns: pd.Series, q: float = 0.95) -> float:
    cleaned = returns.dropna()
    if cleaned.empty:
        return 0.0
    cutoff = np.quantile(cleaned, 1 - q)
    tail = cleaned[cleaned <= cutoff]
    return float(tail.mean()) if not tail.empty else 0.0


def alpha_tstat_newey_west(returns: pd.Series, bench: pd.Series, lags: int = 5) -> Tuple[float, float]:
    y, X = returns.align(bench, join="inner")
    X = sm.add_constant(X)
    model = OLS(y, X).fit()
    cov = cov_hac(model, nlags=lags)
    alpha = model.params[0]
    alpha_se = np.sqrt(cov[0, 0])
    alpha_t = 0.0 if alpha_se == 0 else alpha / alpha_se
    return float(alpha * 252), float(alpha_t)


def deflated_sharpe(sr: float, T: int, n_trials: int = 1) -> float:
    if T <= 2:
        return 0.0
    penalty = np.sqrt(max(np.log(max(n_trials, 1)), 0) / max(T, 1))
    return float(max(sr - penalty, 0.0))


def cpcv_time_series_folds(df: pd.DataFrame, n_splits: int = 8) -> List[Tuple[List[int], List[int]]]:
    n = len(df)
    if n_splits <= 0:
        return [(list(range(n)), list(range(n)))]
    fold = n // n_splits if n_splits > 0 else n
    folds: List[Tuple[List[int], List[int]]] = []
    for idx in range(n_splits):
        start = idx * fold
        end = (idx + 1) * fold if idx < n_splits - 1 else n
        test_idx = list(range(start, end))
        train_idx = list(range(0, max(0, start))) + list(range(end, n))
        folds.append((train_idx, test_idx))
    return folds


def pbo_approx(scores_is: np.ndarray, scores_oos: np.ndarray) -> float:
    if len(scores_is) != len(scores_oos) or len(scores_is) == 0:
        return 1.0
    best_is = int(np.argsort(scores_is)[::-1][0])
    best_oos = int(np.argsort(scores_oos)[::-1][0])
    return 0.0 if best_is == best_oos else 1.0
