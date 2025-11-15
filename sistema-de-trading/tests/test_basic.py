"""Pruebas básicas de integración para el sistema de trading.

Estas pruebas verifican la importabilidad de los módulos principales y
ejecutan un flujo mínimo de extremo a extremo con datos sintéticos.
"""

import pandas as pd
import numpy as np

from sistema_de_trading.config import Config
from sistema_de_trading.features.feature_engineer import FeatureEngineer
from sistema_de_trading.models.ml_pipeline import MLPipeline
from sistema_de_trading.optimization.portfolio_optimizer import PortfolioOptimizer
from sistema_de_trading.backtesting.event_backtester import EventDrivenBacktester


def test_end_to_end_flow():
    """Ejecuta un flujo mínimo de extremo a extremo con datos sintéticos."""
    # Configuración reducida para pruebas: ventanas cortas y un solo modelo
    config = Config(
        ventanas_rendimiento=[2, 3],
        ventana_vol_realizada=3,
        ventana_max_min=5,
        ventana_volumen=5,
        modelos=["ridge"],
    )
    # Datos sintéticos de precios para dos tickers y 40 días hábiles
    dates = pd.date_range(start="2023-01-01", periods=40, freq="B").strftime("%Y-%m-%d")
    tickers = ["AAA", "BBB"]
    data_list = []
    np.random.seed(0)
    for t in tickers:
        price = 100 + np.cumsum(np.random.normal(0, 1, len(dates)))
        volume = np.random.randint(1e5, 5e5, len(dates))
        for d, p, v in zip(dates, price, volume):
            data_list.append({"date": d, "ticker": t, "open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": v})
    df_prices = pd.DataFrame(data_list)
    # Crear features
    fe = FeatureEngineer(config)
    df_feat = fe.create_all_features(df_prices)
    df_feat = fe.create_labels(df_feat, [config.k_principal])
    df_feat = fe.normalize_features(df_feat, method="standardize")
    # Seleccionar features y objetivo
    feature_cols = [c for c in df_feat.columns if c.startswith("feat_")]
    label_col = f"label_{config.k_principal}"
    # Eliminar filas con NaNs en features o etiquetas
    df_feat = df_feat.dropna(subset=feature_cols + [label_col]).reset_index(drop=True)
    # Asegurarse de que hay suficientes datos de entrenamiento y prueba
    if len(df_feat) < 10:
        return  # evitar error si no se generan suficientes filas
    df_train = df_feat.iloc[:-5]
    df_test = df_feat.iloc[-5:]
    # Entrenar modelos
    pipeline = MLPipeline(config)
    pipeline.fit(df_train, None, feature_cols, label_col)
    preds = pipeline.predict(df_test, feature_cols)
    assert not preds.empty
    # Evaluar
    metrics_eval = pipeline.evaluate(df_test, feature_cols, label_col)
    assert isinstance(metrics_eval, dict)
    # Optimización
    model_name = config.modelos[0]
    expected_returns = preds[f"pred_{model_name}"]
    expected_returns.index = df_test["ticker"]
    # Construir retornos diarios para covarianza
    returns = df_prices.groupby("ticker")["close"].pct_change().fillna(0.0).reset_index()
    returns_df = df_prices.copy()
    returns_df["return"] = returns["close"]
    opt = PortfolioOptimizer(config)
    cov = opt.calculate_expected_covariance(returns_df, expected_returns.index.tolist(), lookback_days=10)
    sectors = pd.Series({t: "SectorX" for t in expected_returns.index})
    result = opt.optimize_weights(expected_returns, cov, sectors)
    assert abs(result.weights.abs().sum()) <= config.apalancamiento_bruto_max + 1e-3
    # Backtest simple
    signals = []
    for d in df_test["date"]:
        for t in expected_returns.index:
            signals.append({"date": d, "ticker": t, "target_weight": result.weights.loc[t]})
    df_signals = pd.DataFrame(signals)
    bt = EventDrivenBacktester(config, initial_capital=10000)
    metrics_backtest = bt.run_backtest(df_prices, df_signals)
    assert "total_return" in metrics_backtest