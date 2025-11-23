# Sistema de Trading - expOptions Branch

## Overview

The `expOptions` branch extends the baseline trading system (`expB`) with **real options data** from Polygon.io. This branch includes the `OptionsTradesLoader` module for fetching and processing historical options trade data.

## Key Features

- **Real Options Data**: Fetch historical options trades from Polygon.io API
- **Daily Feature Aggregation**: Build daily-level features from intraday options trades
- **Flexible Configuration**: Customizable time windows, contract limits, and trade thresholds
- **Integration with Trading System**: Seamlessly integrates with the existing feature engineering pipeline

## Installation

### Prerequisites

```bash
pip install pandas numpy scikit-learn polygon-api-client
```

### Clone the Repository

```bash
git clone -b expOptions https://github.com/mguerrero896/Sistema-de-Trading.git
cd Sistema-de-Trading/sistema-de-trading
```

## Usage

### Basic Example

```python
import sys
sys.path.append('/path/to/Sistema-de-Trading/sistema-de-trading')

from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)

# Configure the loader
cfg = OptionsTradesConfig(
    days_before_expiry=30,      # Days before expiration to fetch
    days_after_expiry=0,        # Days after expiration to fetch
    contracts_limit=100,        # Max contracts per expiry
    trades_limit_per_contract=50000,  # Max trades per contract
    min_trades_per_day=1,       # Minimum trades required for a day
)

# Create loader with API key
loader = OptionsTradesLoader(cfg, api_key="YOUR_POLYGON_API_KEY")

# Or use environment variable POLYGON_API_KEY
# loader = OptionsTradesLoader(cfg)

# Fetch options data
df_options = loader.build_daily_features_for_underlying_and_expiry(
    underlying="AAPL",
    expiry="2025-11-21",
)

print(df_options.head())
```

### Output Features

The loader generates the following daily features:

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `ticker` | Underlying ticker symbol |
| `expiry` | Options expiration date |
| `opt_trades_count` | Total number of trades |
| `opt_notional` | Total notional value (price × size) |
| `opt_avg_price` | Average trade price |
| `opt_price_std` | Standard deviation of prices |
| `opt_min_price` | Minimum trade price |
| `opt_max_price` | Maximum trade price |

### Google Colab Usage

```python
# 1. Clone repository
%cd /content
!git clone -b expOptions https://github.com/mguerrero896/Sistema-de-Trading.git
%cd Sistema-de-Trading/sistema-de-trading

# 2. Add to path
import sys
sys.path.append('/content/Sistema-de-Trading/sistema-de-trading')

# 3. Import and use
from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)

# 4. Get API key from Colab secrets
from google.colab import userdata
api_key = userdata.get('POLYGON_API_KEY')

# 5. Create loader and fetch data
cfg = OptionsTradesConfig()
loader = OptionsTradesLoader(cfg, api_key=api_key)
df = loader.build_daily_features_for_underlying_and_expiry('AAPL', '2025-11-21')
```

## API Key Setup

### Method 1: Pass Directly

```python
loader = OptionsTradesLoader(cfg, api_key="your_api_key_here")
```

### Method 2: Environment Variable

```bash
export POLYGON_API_KEY="your_api_key_here"
```

```python
loader = OptionsTradesLoader(cfg)  # Will use POLYGON_API_KEY from environment
```

### Method 3: Google Colab Secrets

1. In Colab, click the key icon (🔑) in the left sidebar
2. Add a new secret named `POLYGON_API_KEY`
3. Use in code:

```python
from google.colab import userdata
api_key = userdata.get('POLYGON_API_KEY')
loader = OptionsTradesLoader(cfg, api_key=api_key)
```

## Configuration Options

### OptionsTradesConfig Parameters

- **`days_before_expiry`** (int, default=30): Number of days before expiration to start fetching data
- **`days_after_expiry`** (int, default=0): Number of days after expiration to continue fetching
- **`contracts_limit`** (int, default=100): Maximum number of option contracts to fetch per expiry
- **`trades_limit_per_contract`** (int, default=50000): Maximum trades to fetch per contract per day
- **`min_trades_per_day`** (int, default=1): Minimum trades required to include a day in results

## Testing

Run the test suite:

```bash
cd /path/to/Sistema-de-Trading/sistema-de-trading
python -m pytest tests/ -v
```

Run the smoke test for options loader:

```bash
python test_options_loader_import.py
```

## Recent Changes (Integration Fix)

**Pull Request #2** fixed the following issues:

1. ✅ Removed duplicate `options_trades_loader.py` at repo root
2. ✅ Hardened API key handling with environment variable fallback
3. ✅ Removed all `__pycache__` directories from git tracking
4. ✅ Added `.gitignore` to prevent future compiled file tracking

See `INTEGRATION_SUMMARY.md` for detailed information.

## Project Structure

```
sistema-de-trading/
├── sistema_de_trading/           # Main package
│   ├── data/
│   │   ├── options_trades_loader.py  # Options data loader (CANONICAL)
│   │   └── data_loader.py
│   ├── features/
│   │   └── feature_engineer.py
│   ├── models/
│   │   └── ml_pipeline.py
│   ├── optimization/
│   │   └── portfolio_optimizer.py
│   ├── backtesting/
│   │   └── event_backtester.py
│   └── config.py
├── tests/
│   └── test_basic.py
├── run_pipeline.py
└── run_momentum_baseline.py
```

## Troubleshooting

### Import Error: "No module named 'polygon'"

Install the Polygon client:
```bash
pip install polygon-api-client
```

### ValueError: "No se proporcionó api_key..."

This means no API key was provided. Either:
1. Pass `api_key` parameter to `OptionsTradesLoader()`
2. Set `POLYGON_API_KEY` environment variable
3. Use Colab secrets (if in Colab)

### TypeError: "__init__() got an unexpected keyword argument 'api_key'"

This indicates you're using an old version of the code. Make sure you're on the latest `expOptions` branch:

```bash
git fetch origin
git checkout expOptions
git pull origin expOptions
```

## Contributing

When making changes to this branch:

1. Create a feature branch from `expOptions`
2. Make your changes with clear commit messages
3. Run tests to ensure nothing breaks
4. Create a PR targeting `expOptions` (not `main`)

## License

[Add your license information here]

## Support

For issues or questions:
- Open an issue on GitHub
- Check `INTEGRATION_SUMMARY.md` for recent fixes
- Review the test files for usage examples
