"""Configuration for the trading system."""
from __future__ import annotations

import os
from typing import Final, Optional


def _get_secret(name: str) -> Optional[str]:
    """Retrieve secrets from Colab userdata (if available) or environment."""
    val: Optional[str] = None
    try:
        from google.colab import userdata  # type: ignore
    except Exception:  # pragma: no cover - dependency is optional
        userdata = None  # type: ignore[assignment]
    else:
        try:
            val = userdata.get(name)  # type: ignore[attr-defined]
        except Exception:
            val = None
    if not val:
        val = os.environ.get(name)
    return val


POLYGON_API_KEY: Final[Optional[str]] = _get_secret("POLYGON_API_KEY")
FMP_API_KEY: Final[Optional[str]] = _get_secret("FMP_API_KEY")

USE_DEMO_DATA: Final[bool] = not bool(POLYGON_API_KEY and FMP_API_KEY)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
MODELS_DIR = os.path.join(ROOT_DIR, "models")

for path in (DATA_DIR, LOGS_DIR, MODELS_DIR):
    os.makedirs(path, exist_ok=True)

UNIVERSE_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "NVDA",
    "JPM",
    "BAC",
    "GS",
    "JNJ",
    "UNH",
    "PFE",
    "AMZN",
    "TSLA",
    "HD",
    "XOM",
    "CVX",
    "CAT",
    "BA",
    "META",
    "NFLX",
    "NEE",
]

RISK_LIMITS = {
    "max_daily_loss_pct": 0.03,
    "kill_switch_sigma": 3,
    "max_position_pct": 0.08,
    "max_net_exposure_pct": 0.30,
    "max_gross_exposure_pct": 2.0,
    "max_beta": 0.5,
    "max_sector_pct": 0.25,
    "max_participation_adv": 0.05,
    "drawdown_window_bars": 100,
    "drawdown_estimator": "ES",
    "cooldown_after_limit_minutes": 60,
}

GLOBAL_RANDOM_SEED = 42
DEFAULT_TZ = "America/New_York"
