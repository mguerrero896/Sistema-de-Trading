"""Strategic ranking agent built with XGBoost."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from trading_system.utils.metrics import (
    cpcv_time_series_folds,
    deflated_sharpe,
    pbo_approx,
    sharpe_ratio,
)


class StrategicAgent:
    """Trainable ranker that outputs cross-sectional scores."""

    def __init__(self, random_state: int = 42) -> None:
        self.model = Pipeline(
            [
                ("scaler", StandardScaler(with_mean=True, with_std=True)),
                (
                    "xgb",
                    XGBRegressor(
                        n_estimators=400,
                        max_depth=6,
                        learning_rate=0.05,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        random_state=random_state,
                        tree_method="hist",
                    ),
                ),
            ]
        )
        self.is_fitted = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        self.model.fit(X, y)
        self.is_fitted = True
        preds = self.model.predict(X)
        return {"in_sample_r2": float(r2_score(y, preds))}

    def predict_scores(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("StrategicAgent no entrenado")
        return self.model.predict(X)

    def cpcv_validate(
        self, df: pd.DataFrame, feature_cols: List[str], target_col: str, n_splits: int = 8
    ) -> Dict[str, Any]:
        folds = cpcv_time_series_folds(df, n_splits=n_splits)
        sharpe_scores = []
        for train_idx, test_idx in folds:
            train = df.iloc[train_idx]
            test = df.iloc[test_idx]
            self.fit(train[feature_cols], train[target_col])
            preds = self.predict_scores(test[feature_cols])
            ranks = pd.Series(preds, index=test.index).rank(pct=True) * 2 - 1
            rets = (ranks * test[target_col]).fillna(0.0)
            sharpe_scores.append(sharpe_ratio(rets))
        mean_sharpe = float(np.mean(sharpe_scores)) if sharpe_scores else 0.0
        ds = deflated_sharpe(mean_sharpe, T=max(len(df), 1), n_trials=n_splits)
        pbo = pbo_approx(np.array(sharpe_scores), np.array(sharpe_scores)) if sharpe_scores else 0.0
        return {"cpcv": {"mean_sharpe": mean_sharpe}, "deflated_sharpe": float(ds), "pbo": float(pbo)}
