# Sistema-de-Trading

Este repositorio contiene el núcleo del sistema de trading descrito en el notebook de Google Colab.

## Código listo para usar en Google Colab

1. **Clona o sube el repositorio** a `/content/trading_system`.
2. **Guarda las API keys** en el baúl de secretos de Colab (una vez por sesión):
   ```python
   from google.colab import userdata
   userdata.set("POLYGON_API_KEY", "<tu_api_key_polygon>")
   userdata.set("FMP_API_KEY", "<tu_api_key_fmp>")
   ```
3. **Ejecuta el siguiente bloque en una celda** para instalar dependencias, exponer el paquete y lanzar el backtest demo:
   ```python
   import asyncio
   import pathlib
   import subprocess
   import sys

   import nest_asyncio

   PROJECT_ROOT = pathlib.Path("/content/trading_system")
   if not PROJECT_ROOT.exists():
       raise FileNotFoundError("Sube o clona el repo en /content/trading_system antes de continuar.")

   parent = PROJECT_ROOT.parent
   if str(parent) not in sys.path:
       sys.path.append(str(parent))

   subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(PROJECT_ROOT / "requirements.txt")])

   nest_asyncio.apply()

   from trading_system.main import TradingSystem

   async def run_demo():
       system = TradingSystem(mode="backtest", initial_capital=25_000)
       results = await system.run_backtest(start_date="2023-01-01", end_date="2024-12-31")
       metrics, validation = results["metrics"], results["validation"]
       print("\n" + "=" * 50)
       print("RESULTADOS DEL BACKTEST")
       print("=" * 50)
       print(f"Retorno Total: {metrics['total_return']:.2%}")
       print(f"CAGR: {metrics['cagr']:.2%}")
       print(f"Sharpe Ratio: {metrics['sharpe']:.2f}")
       print(f"Sortino Ratio: {metrics['sortino']:.2f}")
       print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
       print(f"Win Rate: {metrics['win_rate']:.2%}")
       print(f"Número de Trades (aprox): {metrics['n_trades']}")
       cpcv = validation.get("cpcv", {})
       print("\nValidación:")
       print(f"Deflated Sharpe: {validation.get('deflated_sharpe', 0.0):.2f}")
       print(f"CPCV mean Sharpe: {cpcv.get('mean_sharpe', 0.0):.2f}")

   loop = asyncio.get_event_loop()
   loop.run_until_complete(run_demo())
   ```

El bloque anterior aprovecha `nest_asyncio` para reutilizar el event loop del notebook (típico en Colab) sin errores. Si prefieres evitar celdas extensas, puedes ejecutar el script `colab_bootstrap.py` incluido en el repositorio:

```bash
python /content/trading_system/colab_bootstrap.py --start 2023-01-01 --end 2024-12-31 --capital 25000
```

## Uso manual del paquete

Si deseas importar módulos individuales desde otras celdas, asegúrate de añadir `/content` al `sys.path` antes de los imports:

```python
import sys, pathlib
PROJECT_ROOT = pathlib.Path("/content/trading_system")
if str(PROJECT_ROOT.parent) not in sys.path:
    sys.path.append(str(PROJECT_ROOT.parent))
```

También puedes instalar el paquete directamente mediante `pip` (modo editable recomendado):

```bash
pip install -e /content/trading_system
```

Con cualquiera de estas opciones podrás ejecutar sin problemas instrucciones como:

```python
from trading_system.config import RISK_LIMITS, UNIVERSE_TICKERS
```

## Dependencias

Revisa `requirements.txt` para conocer las librerías necesarias. En Colab puedes instalarlas con:

```bash
pip install -r /content/trading_system/requirements.txt
```

El archivo `requirements.txt` ya incluye `nest-asyncio` para compatibilidad con event loops en notebooks.
