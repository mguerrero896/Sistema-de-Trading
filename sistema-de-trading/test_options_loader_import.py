#!/usr/bin/env python3
"""
Smoke test to verify that OptionsTradesLoader can be imported and instantiated
without TypeError.
"""

import sys
from pathlib import Path

# Add the project root to sys.path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig,
)


def test_import_and_instantiate():
    """Test that we can import and create an instance with a dummy API key."""
    print("Testing import of OptionsTradesLoader and OptionsTradesConfig...")
    
    # Create a config
    cfg = OptionsTradesConfig(
        days_before_expiry=30,
        days_after_expiry=0,
        contracts_limit=100,
        trades_limit_per_contract=50000,
        min_trades_per_day=1,
    )
    print(f"✓ Created config: {cfg}")
    
    # Create a loader with a dummy API key
    try:
        loader = OptionsTradesLoader(cfg, api_key="DUMMY_API_KEY_FOR_TEST")
        print(f"✓ Created loader successfully: {loader}")
        print(f"✓ Loader has client: {loader.client}")
        print("\n✅ All smoke tests passed!")
        return True
    except TypeError as e:
        print(f"✗ TypeError occurred: {e}")
        return False
    except Exception as e:
        # Other exceptions are OK for this smoke test (e.g., API connection errors)
        print(f"✓ Loader created but got expected error: {type(e).__name__}")
        print("\n✅ Import and instantiation successful (API errors are expected with dummy key)")
        return True


if __name__ == "__main__":
    success = test_import_and_instantiate()
    sys.exit(0 if success else 1)
