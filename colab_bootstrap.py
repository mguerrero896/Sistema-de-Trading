"""Bootstrap y ejecución del sistema de trading dentro de Google Colab.

Este script asume que el repositorio se encuentra en ``/content/trading_system``
y que las API keys necesarias fueron guardadas en el baúl de secretos de Colab
(`google.colab.userdata`). Al ejecutar el script se instalarán las dependencias,
se expondrá el paquete ``trading_system`` en ``sys.path`` y se lanzará un
backtest de demostración.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import subprocess
import sys
from typing import Coroutine, Any

PROJECT_ROOT = pathlib.Path("/content/trading_system")
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
MAIN_SHIM = pathlib.Path("/content/main.py")


def ensure_project_present() -> None:
    if not PROJECT_ROOT.exists():
        raise FileNotFoundError(
            "No se encontró /content/trading_system. Asegúrate de clonar o "
            "copiar el repositorio en esa ruta antes de ejecutar este script."
        )


def ensure_sys_path() -> None:
    parent = PROJECT_ROOT.parent
    if str(parent) not in sys.path:
        sys.path.append(str(parent))


def ensure_main_shim() -> None:
    if MAIN_SHIM.exists():
        return
    MAIN_SHIM.write_text("from trading_system.main import TradingSystem\n", encoding="utf-8")


def install_dependencies() -> None:
    if not REQUIREMENTS.exists():
        raise FileNotFoundError(
            "No se encontró requirements.txt en el repositorio."
        )
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)]
    )


def detect_asyncio_runner() -> bool:
    """Devuelve True si ya hay un event loop corriendo (entornos Colab/Jupyter)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    else:
        return loop.is_running()


def run_async(coro: Coroutine[Any, Any, None]) -> None:
    if detect_asyncio_runner():
        # Compatibilidad con Colab/Jupyter
        import nest_asyncio  # type: ignore

        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(coro)
    else:
        asyncio.run(coro)


async def execute_backtest(start: str, end: str, capital: float) -> None:
    from main import TradingSystem  # shim en /content/main.py

    system = TradingSystem(mode="backtest", initial_capital=capital)
    results = await system.run_backtest(start_date=start, end_date=end)

    metrics = results.get("metrics", {})
    validation = results.get("validation", {})

    print("\n" + "=" * 50)
    print("RESULTADOS DEL BACKTEST")
    print("=" * 50)
    print(f"Retorno Total: {metrics.get('total_return', 0.0):.2%}")
    print(f"CAGR: {metrics.get('cagr', 0.0):.2%}")
    print(f"Sharpe Ratio: {metrics.get('sharpe', 0.0):.2f}")
    print(f"Sortino Ratio: {metrics.get('sortino', 0.0):.2f}")
    print(f"Max Drawdown: {metrics.get('max_drawdown', 0.0):.2%}")
    print(f"Win Rate: {metrics.get('win_rate', 0.0):.2%}")
    print(f"Número de Trades (aprox): {metrics.get('n_trades', 0)}")

    cpcv = validation.get("cpcv", {})
    print("\nValidación:")
    print(f"Deflated Sharpe: {validation.get('deflated_sharpe', 0.0):.2f}")
    print(f"CPCV mean Sharpe: {cpcv.get('mean_sharpe', 0.0):.2f}")


async def main(start: str, end: str, capital: float, skip_install: bool) -> None:
    ensure_project_present()
    ensure_sys_path()
    ensure_main_shim()
    if not skip_install:
        install_dependencies()
    await execute_backtest(start, end, capital)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap para Google Colab")
    parser.add_argument("--start", default="2023-01-01", help="Fecha de inicio (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="Fecha de fin (YYYY-MM-DD)")
    parser.add_argument(
        "--capital",
        type=float,
        default=25_000.0,
        help="Capital inicial para el backtest",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Omitir la instalación de dependencias (si ya se instaló previamente)",
    )
    args = parser.parse_args()

    run_async(main(args.start, args.end, args.capital, args.skip_install))
