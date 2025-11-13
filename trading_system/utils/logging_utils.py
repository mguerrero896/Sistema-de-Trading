"""Logging utilities for the trading system."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime


def setup_logging(log_dir: str) -> None:
    """Configure logging output to both stdout and a daily rotating file."""
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"trading_{timestamp}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )
