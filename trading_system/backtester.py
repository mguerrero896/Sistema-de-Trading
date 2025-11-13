"""Backtesting engine for the trading system."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from trading_system.config import RISK_LIMITS, UNIVERSE_TICKERS
from trading_system.data_provider import DataProvider
from trading_system.feature_engineering import validate_features_by_ticker
from trading_system.risk_management import bayesian_kelly
from trading_system.strategic_agent import StrategicAgent
from trading_system.utils.metrics import (
    calmar_ratio,
    deflated_sharpe,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)


class Backtester:
    """Run historical simulations using the demo data provider."""

    def __init__(self, initial_capital: float = 25_000.0, oms=None, random_state: int = 42) -> None:
        self.initial_capital = float(initial_capital)
        self.random_state = random_state
        self.oms = oms

    async def run(self, start_date: str, end_date: str) -> Dict[str, Any]:
        async with DataProvider() as dp:
            equity_data = await dp.get_equity_ohlcv(UNIVERSE_TICKERS, start_date, end_date, freq="1D")

        frames = []
        for ticker, df in equity_data.items():
            temp = df.copy()
            temp["ticker"] = ticker
            temp["ret_1d"] = temp["close"].pct_change()
            temp["vol_20"] = temp["ret_1d"].rolling(20).std()
            temp["mom_10"] = temp["close"].pct_change(10)
            temp["target_rank"] = temp["ret_1d"].shift(-1)
            frames.append(temp)
        daily = pd.concat(frames).dropna().sort_index()
        daily = validate_features_by_ticker(daily)

        feature_cols = ["vol_20", "mom_10"]
        target_col = "target_rank"

        agent = StrategicAgent(random_state=self.random_state)
        agent.fit(daily[feature_cols], daily[target_col])
        validation = agent.cpcv_validate(daily, feature_cols, target_col, n_splits=8)

        daily["score"] = agent.predict_scores(daily[feature_cols])
        panel = (
            daily.reset_index()
            .pivot(index="index", columns="ticker", values=["ret_1d", "score", "close", "volume"])
            .dropna()
        )
        panel.columns = ["_".join(col).strip() for col in panel.columns.values]

        def day_weights(scores_row: pd.Series) -> pd.Series:
            ranks = scores_row.rank(pct=True) * 2 - 1
            return ranks / (ranks.abs().sum() + 1e-8)

        score_cols = [col for col in panel.columns if col.startswith("score_")]
        ret_cols = [col for col in panel.columns if col.startswith("ret_1d_")]
        close_cols = [col for col in panel.columns if col.startswith("close_")]
        volume_cols = [col for col in panel.columns if col.startswith("volume_")]
        tickers = [col.replace("score_", "") for col in score_cols]

        portfolio_value = self.initial_capital
        weights_hist: List[pd.Series] = []
        returns_hist: List[float] = []
        turnover_hist: List[float] = []

        prev_weights = pd.Series(0.0, index=tickers)

        for dt, row in panel.iterrows():
            scores = row[score_cols]
            base_w = day_weights(scores)

            last_window = panel.loc[:dt].tail(60)
            returns_for_kelly = last_window[ret_cols] if len(last_window) >= 20 else panel[ret_cols].head(20)
            returns_for_kelly.columns = tickers
            kelly_w = bayesian_kelly(
                returns_for_kelly,
                get_price=lambda t: float(row[f"close_{t}"]),
                get_adv=lambda t: float(row[f"volume_{t}"]),
                get_portfolio_value=lambda: portfolio_value,
            )

            combined = (0.5 * base_w + 0.5 * kelly_w).fillna(0.0)
            combined = combined / (combined.abs().sum() + 1e-8)
            combined = combined.clip(-RISK_LIMITS["max_position_pct"], RISK_LIMITS["max_position_pct"])

            day_ret = float((combined.values * row[ret_cols].values).sum())
            portfolio_value *= 1 + day_ret
            returns_hist.append(day_ret)
            weights_hist.append(combined)

            turnover = float((combined - prev_weights).abs().sum())
            turnover_hist.append(turnover)
            prev_weights = combined

        equity = pd.Series(
            np.cumprod(1 + np.array(returns_hist)) * self.initial_capital,
            index=panel.index,
            name="total_value",
        )
        port_returns = equity.pct_change().dropna()

        metrics = {
            "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) > 1 else 0.0,
            "cagr": float((1 + port_returns.mean()) ** 252 - 1.0) if len(port_returns) else 0.0,
            "sharpe": float(sharpe_ratio(port_returns)),
            "sortino": float(sortino_ratio(port_returns)),
            "max_drawdown": float(max_drawdown(equity)),
            "calmar": float(calmar_ratio(port_returns, equity)),
            "win_rate": float((np.array(returns_hist) > 0).mean()) if returns_hist else 0.0,
            "n_trades": int(sum(np.array(turnover_hist) > 0.02)),
        }

        validation.update({
            "deflated_sharpe": float(deflated_sharpe(metrics["sharpe"], T=len(port_returns), n_trials=8))
        })

        return {"metrics": metrics, "validation": validation, "portfolio_history": equity.to_frame()}
