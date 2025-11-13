"""Feature engineering helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd


def cumulative_vwap(df: pd.DataFrame) -> pd.Series:
    pxv = (df["close"] * df["volume"]).cumsum()
    vol = df["volume"].cumsum().replace(0, np.nan)
    return pxv / vol


def lee_ready_trade_sign(df: pd.DataFrame) -> pd.Series:
    if "midpoint" in df.columns:
        return np.sign(df["close"].diff().fillna(0.0) + (df["close"] - df["midpoint"]))
    return np.sign(df["close"].diff().fillna(0.0))


def validate_features_by_ticker(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if not isinstance(result.index, pd.DatetimeIndex):
        raise ValueError("Se requiere DatetimeIndex")
    result["hour"] = result.index.hour
    result["minute"] = result.index.minute

    for feature in ["volume", "spread", "obi"]:
        if feature in result.columns:
            result[f"{feature}_normalized"] = (
                result.groupby(["ticker", "hour", "minute"])[feature]
                .transform(lambda x: (x - x.mean()) / (x.std() if x.std() > 0 else 1.0))
            )

    result["trade_sign"] = lee_ready_trade_sign(result)

    if {"bid_size_l1", "ask_size_l1"}.issubset(result.columns):
        denom = (result["bid_size_l1"] + result["ask_size_l1"]).replace(0, np.nan)
        result["queue_imbalance_l1"] = (result["bid_size_l1"] - result["ask_size_l1"]) / denom

    if {"close", "volume"}.issubset(result.columns):
        result["vwap_no_leak"] = cumulative_vwap(result)

    return result
