"""Simulación de trading basada en eventos y pesos objetivo.

Este módulo implementa la clase :class:`EventDrivenBacktester`, que
ejecuta una simulación diaria de la cartera siguiendo señales de pesos
generadas por el pipeline de modelos. El backtester tiene en cuenta
costes básicos (comisiones) y actualiza el capital de forma acumulada.
No pretende reproducir todos los detalles del notebook original, pero
provee una aproximación razonable y extensible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List

from ..config import Config
from ..utils.helpers import compute_performance_metrics


@dataclass
class TradeRecord:
    """Representa una transacción ejecutada al rebalancear la cartera."""

    date: str
    ticker: str
    weight_before: float
    weight_after: float
    trade_size: float  # Cambio en peso (positivo compra, negativo venta)
    commission_cost: float


class EventDrivenBacktester:
    """Simulador de backtesting basado en pesos objetivo diarios.

    Parámetros
    ----------
    config : Config
        Configuración con parámetros de costes y control de riesgo.
    initial_capital : float, opcional
        Capital inicial de la cartera. Por defecto 1 millón de unidades.
    """

    def __init__(self, config: Config, initial_capital: float = 1_000_000.0) -> None:
        self.config = config
        self.initial_capital = initial_capital

    # ------------------------------------------------------------------
    # Ejecución principal del backtest
    # ------------------------------------------------------------------
    def run_backtest(
        self,
        df_prices: pd.DataFrame,
        df_signals: pd.DataFrame,
    ) -> Dict[str, float]:
        """Ejecuta el backtest y devuelve métricas de rendimiento.

        Se requiere que ``df_prices`` contenga las columnas ``date``,
        ``ticker`` y ``close``. ``df_signals`` debe contener las columnas
        ``date``, ``ticker`` y ``target_weight``. Las fechas deben
        representarse como cadenas ``YYYY-MM-DD`` para evitar errores de
        alineamiento.

        Retorna
        -------
        dict
            Diccionario con métricas básicas de rendimiento (retorno total,
            volatilidad anualizada, ratio de Sharpe, máximo drawdown, etc.).
        """
        # Pivotar precios a formato fechas x tickers
        prices = df_prices.pivot_table(index="date", columns="ticker", values="close").sort_index()
        returns = prices.pct_change().fillna(0.0)
        # Asegurar que las señales están ordenadas
        signals = df_signals.copy()
        signals = signals.sort_values(["date", "ticker"])
        # Crear una estructura para almacenar pesos objetivo por fecha
        # Convertir signals a diccionario: {date: {ticker: weight}}
        date_to_weights: Dict[str, pd.Series] = {}
        for d, sub in signals.groupby("date"):
            date_to_weights[d] = sub.set_index("ticker")["target_weight"]
        # Preparar contenedores
        capital = self.initial_capital
        # Pesos actuales; al inicio estamos en efectivo (cero exposición)
        current_weights = pd.Series(0.0, index=prices.columns)
        equity_curve: List[float] = []
        trades: List[TradeRecord] = []
        # Loop por fechas; la primera fecha no produce retorno pero se establecen pesos iniciales
        dates = prices.index.tolist()
        for i, date in enumerate(dates):
            date_str = str(date)
            # Determinar pesos objetivo para la fecha (si existen)
            target = date_to_weights.get(date_str, None)
            if target is not None:
                # Alinear con universo de precios
                target = target.reindex(prices.columns, fill_value=0.0)
            else:
                target = current_weights.copy()
            # Calcular retorno del día basado en pesos anteriores (hasta la fecha actual)
            if i > 0:
                r = returns.iloc[i]
                portfolio_return = float(np.nansum(current_weights.values * r.values))
                # Aplicar comisiones por rebalanceo (costes en bps sobre notional)
                delta = target - current_weights
                # Comisión total en unidades monetarias = |delta_weights| * capital * comision_bp / 10_000
                commission_cost = float(delta.abs().sum() * self.config.comision_bp / 10_000 * capital)
                # Slippage y otras estimaciones se pueden añadir aquí
                # Actualizar capital
                capital = capital * (1 + portfolio_return) - commission_cost
                # Registrar trades cuando hay cambios significativos
                changed = delta[delta != 0]
                for ticker, change in changed.items():
                    trades.append(
                        TradeRecord(
                            date=date_str,
                            ticker=ticker,
                            weight_before=float(current_weights.get(ticker, 0.0)),
                            weight_after=float(target.get(ticker, 0.0)),
                            trade_size=float(change),
                            commission_cost=float(abs(change) * self.config.comision_bp / 10_000 * capital),
                        )
                    )
            # Actualizar pesos actuales
            current_weights = target.copy()
            # Registrar equity
            equity_curve.append(capital)
        # Construir DataFrame de equity
        df_equity = pd.DataFrame({"date": dates, "equity": equity_curve})
        # Calcular métricas de rendimiento
        metrics = compute_performance_metrics(df_equity["equity"].pct_change().fillna(0.0))
        metrics["total_return"] = df_equity["equity"].iloc[-1] / self.initial_capital - 1
        # Guardar variables para acceso posterior
        self._df_equity = df_equity
        self._trades = trades
        return metrics

    # ------------------------------------------------------------------
    # Accesores
    # ------------------------------------------------------------------
    def get_equity_curve(self) -> pd.DataFrame:
        """Devuelve el DataFrame de la curva de equity tras el backtest."""
        return getattr(self, "_df_equity", pd.DataFrame())

    def get_trades(self) -> pd.DataFrame:
        """Devuelve un DataFrame con las transacciones ejecutadas."""
        if not hasattr(self, "_trades"):
            return pd.DataFrame(columns=["date", "ticker", "weight_before", "weight_after", "trade_size", "commission_cost"])
        data = [t.__dict__ for t in self._trades]
        return pd.DataFrame(data)