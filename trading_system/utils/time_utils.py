"""Time helper utilities."""
from __future__ import annotations

from datetime import datetime

import pytz

from trading_system.config import DEFAULT_TZ


def now_ny() -> datetime:
    """Return the current time in the configured New York timezone."""
    return datetime.now(pytz.timezone(DEFAULT_TZ))


def timestamp_str() -> str:
    """Return the current timestamp formatted for logs."""
    return now_ny().strftime("%Y-%m-%d %H:%M:%S")
