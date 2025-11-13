"""Risk management utilities."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from trading_system.config import RISK_LIMITS


def expected_shortfall(series: pd.Series, q: float = 0.95) -> float:
    cleaned = series.dropna()
    if cleaned.empty:
        return 0.0
    cutoff = np.quantile(cleaned, 1 - q)
    tail = cleaned[cleaned <= cutoff]
    return float(tail.mean()) if not tail.empty else 0.0


def hierarchical_stop_price(
    position_side: str,
    entry_price: float,
    current_price: float,
    intraday_returns_15m: pd.Series,
    overnight_vol: float,
    supertrend_stop: float,
    mae_stop: float,
    regime_change: bool,
) -> float:
    es95 = expected_shortfall(intraday_returns_15m, q=0.95)
    hard_r = es95
    gap_r = -2.0 * max(overnight_vol, 0.0)
    hard_r = min(hard_r, gap_r)

    regime_r = -0.02 if regime_change else -0.10
    tech_rs = []
    if supertrend_stop > 0:
        tech_rs.append((supertrend_stop - current_price) / current_price)
    if mae_stop > 0:
        tech_rs.append((mae_stop - current_price) / current_price)
    tech_r = np.quantile(tech_rs, 0.2) if tech_rs else -0.05

    if position_side.upper() == "LONG":
        stop_r = max(hard_r, regime_r, tech_r)
        stop_price = current_price * (1.0 + stop_r)
        stop_price = min(stop_price, current_price)
    else:
        hard_r_s = -hard_r
        regime_r_s = 0.02 if regime_change else 0.10
        tech_r_s = -tech_r
        stop_r = min(hard_r_s, regime_r_s, tech_r_s)
        stop_price = current_price * (1.0 + stop_r)
        stop_price = max(stop_price, current_price)
    return float(stop_price)


def bayesian_kelly(
    returns: pd.DataFrame,
    confidence: float = 0.95,
    kelly_fraction: float = 0.25,
    es_budget: float = 0.03,
    adv_limit: float = 0.05,
    get_price=None,
    get_adv=None,
    get_portfolio_value=None,
) -> pd.Series:
    mu, cov = returns.mean(), returns.cov()
    n_boot = 500
    ks = []
    rng = np.random.default_rng(42)
    for _ in range(n_boot):
        sample = returns.sample(n=len(returns), replace=True, random_state=int(rng.integers(0, 1_000_000_000)))
        mu_b, cov_b = sample.mean(), sample.cov()
        try:
            k_b = np.linalg.solve(cov_b + 1e-8 * np.eye(cov_b.shape[0]), mu_b.values)
        except np.linalg.LinAlgError:
            k_b = np.zeros_like(mu_b.values)
        ks.append(k_b)
    ks = np.array(ks)
    lower = np.percentile(ks, (1 - confidence) * 100 / 2, axis=0)
    weights = pd.Series(lower * kelly_fraction, index=returns.columns)

    port = (returns * weights.values).sum(axis=1)
    es95 = expected_shortfall(port, q=0.95)
    if abs(es95) > es_budget and es_budget > 0:
        weights *= es_budget / abs(es95)

    if get_price and get_adv and get_portfolio_value:
        portfolio_value = get_portfolio_value()
        for ticker in weights.index:
            px = max(1e-6, float(get_price(ticker)))
            adv = max(1.0, float(get_adv(ticker)))
            participation = abs(weights[ticker]) * portfolio_value / (adv * px)
            if participation > adv_limit:
                weights[ticker] *= adv_limit / participation
    return weights


def check_risk_limits_with_cooldown(
    portfolio: Dict[str, Any], pnl_intraday: pd.Series, get_adv=None
) -> Dict[str, Any]:
    window = int(RISK_LIMITS["drawdown_window_bars"])
    recent = pnl_intraday.tail(window)
    if len(recent) >= 10:
        es95 = expected_shortfall(recent, q=0.95)
        dd = abs(recent.sum())
        if dd > RISK_LIMITS["kill_switch_sigma"] * abs(es95):
            return {
                "status": "KILL_SWITCH",
                "reason": f"DD {dd:.4f} > {RISK_LIMITS['kill_switch_sigma']}×|ES| {abs(es95):.4f}",
            }

    gross = sum(abs(p.get("value", 0.0)) for p in portfolio["positions"].values()) / max(
        portfolio.get("total_value", 1.0), 1e-8
    )
    if gross > RISK_LIMITS["max_gross_exposure_pct"]:
        return {
            "status": "REJECTED",
            "reason": f"Gross {gross:.2f} > {RISK_LIMITS['max_gross_exposure_pct']:.2f}",
        }

    if get_adv:
        for ticker, pos in portfolio["positions"].items():
            price = max(1e-6, pos.get("price", 1.0))
            adv = max(1.0, get_adv(ticker))
            participation = abs(pos.get("value", 0.0)) / (adv * price)
            if participation > RISK_LIMITS["max_participation_adv"]:
                return {
                    "status": "REJECTED",
                    "reason": f"{ticker} %ADV {participation:.2%} > {RISK_LIMITS['max_participation_adv']:.2%}",
                }
    return {"status": "PASSED"}


def check_exposure_limits_production(portfolio: Dict[str, Any]) -> Dict[str, Any]:
    total_value = max(portfolio.get("total_value", 1.0), 1e-8)
    weights = []
    for pos in portfolio["positions"].values():
        weight = abs(pos.get("value", 0.0)) / total_value
        if weight > 0:
            weights.append(weight)
    hhi = sum(w * w for w in weights)
    violations = []
    if hhi > 0.15:
        violations.append(
            {
                "type": "HHI_CONCENTRATION",
                "value": hhi,
                "limit": 0.15,
                "severity": "MEDIUM",
            }
        )
    return {"status": "REJECTED" if violations else "PASSED", "violations": violations}
