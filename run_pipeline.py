"""Script de ejemplo para ejecutar el pipeline completo del sistema de trading.

Este script orquesta la descarga de datos, generación de features,
entrenamiento de modelos, optimización de portafolio, backtesting y
generación de reportes. Sirve como punto de entrada para usuarios
interesados en reproducir el flujo end-to-end.

Para utilizarlo, asegúrese de haber configurado correctamente las
variables de entorno ``POLYGON_API_KEY`` y ``FMP_API_KEY`` si desea
descargar datos reales. En ausencia de claves API, el DataLoader
utilizará listas estáticas de tickers y yfinance como fuente de
precios, aunque la cobertura puede ser limitada.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

from sistema_de_trading.config import Config
from sistema_de_trading.data.data_loader import DataLoader
from sistema_de_trading.features.feature_engineer import FeatureEngineer
from sistema_de_trading.models.ml_pipeline import MLPipeline
from sistema_de_trading.optimization.portfolio_optimizer import PortfolioOptimizer
from sistema_de_trading.backtesting.event_backtester import EventDrivenBacktester
from sistema_de_trading.reporting.excel_reporter import ExcelReporter


def split_by_year(df: pd.DataFrame, config: Config, label_col: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Divide el DataFrame en conjuntos de entrenamiento, validación y prueba basándose en años.

    La división se realiza ordenando por fecha y asignando los primeros
    ``config.anos_train`` años a entrenamiento, los siguientes
    ``config.anos_val`` a validación y los últimos ``config.anos_test`` a
    prueba. Si la columna de etiquetas contiene NaNs al final de la
    serie, estos registros se excluyen del conjunto de prueba.
    """
    df_sorted = df.sort_values("date").copy()
    df_sorted["year"] = pd.to_datetime(df_sorted["date"]).dt.year
    unique_years = sorted(df_sorted["year"].unique())
    train_years = unique_years[: config.anos_train]
    val_years = unique_years[config.anos_train : config.anos_train + config.anos_val]
    test_years = unique_years[-config.anos_test :]
    df_train = df_sorted[df_sorted["year"].isin(train_years)].reset_index(drop=True)
    df_val = df_sorted[df_sorted["year"].isin(val_years)].reset_index(drop=True)
    df_test = df_sorted[df_sorted["year"].isin(test_years)].reset_index(drop=True)
    # Excluir registros sin etiqueta en test
    df_test = df_test[~df_test[label_col].isna()].reset_index(drop=True)
    return df_train, df_val, df_test


def main(args: argparse.Namespace) -> None:
    # 1. Instanciar configuración
    config = Config()
    # 2. Crear directorio de ejecución
    run_dir = Path(config.runs_dir) / pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Guardar resultados en: {run_dir}")
    # 3. Descarga de datos
    loader = DataLoader(config.polygon_api_key, config.fmp_api_key)
    tickers: List[str] = loader.get_sp500_tickers(limit=args.limit_universe)
    print(f"Obtenidos {len(tickers)} tickers")
    df_prices = loader.download_price_data(tickers, config.fecha_inicio, config.fecha_fin)
    # Añadir fundamentales y filtrar
    df_fund = loader.download_fundamentals(tickers)
    df_prices = df_prices.merge(df_fund, on="ticker", how="left")
    df_prices = loader.apply_filters(
        df_prices,
        min_price=config.precio_min,
        min_volume=config.volumen_medio_min,
        window=config.ventana_volumen,
    )
    # 4. Generar features y etiquetas
    fe = FeatureEngineer(config)
    df_feat = fe.create_all_features(df_prices)
    df_feat = fe.create_labels(df_feat, [config.k_principal])
    df_feat = fe.normalize_features(df_feat, method="standardize")
    # 5. Dividir datasets
    feature_cols = [c for c in df_feat.columns if c.startswith("feat_")]
    label_col = f"label_{config.k_principal}"
    df_train, df_val, df_test = split_by_year(df_feat, config, label_col)
    print(f"Tamaño train: {len(df_train)}, val: {len(df_val)}, test: {len(df_test)}")
    # 6. Entrenar modelos
    pipeline = MLPipeline(config)
    pipeline.fit(df_train, df_val, feature_cols, label_col)
    metrics_eval = pipeline.evaluate(df_val, feature_cols, label_col)
    print(f"Métricas de validación: {metrics_eval}")
    # 7. Generar predicciones sobre el conjunto completo (train+val+test)
    df_pred = pipeline.predict(df_feat, feature_cols)
    # Neutralizar predicciones si se solicita
    if config.neutralizar_por_sector:
        # Se asume que df_feat contiene columna 'sector'
        for model in config.modelos:
            col = f"pred_{model}"
            df_pred = pipeline.neutralize_by_sector(df_pred, col, "sector")
    # 8. Optimización por fecha
    opt = PortfolioOptimizer(config)
    # Calcular retornos para covarianza
    df_returns = df_prices[["date", "ticker", "close"]].copy()
    df_returns["return"] = df_returns.groupby("ticker")["close"].pct_change().fillna(0.0)
    # Determinar predicciones que usar (primer modelo)
    pred_col = f"pred_{config.modelos[0]}"
    weights_list = []
    for d in df_pred["date"].unique():
        sub = df_pred[df_pred["date"] == d]
        expected = sub.set_index("ticker")[pred_col]
        if expected.isnull().all():
            continue
        cov = opt.calculate_expected_covariance(df_returns, expected.index.tolist(), lookback_days=60)
        sectors = sub.set_index("ticker")["sector"] if "sector" in sub.columns else pd.Series("Unknown", index=expected.index)
        res = opt.optimize_weights(expected, cov, sectors)
        weights = res.weights.reset_index()
        weights.columns = ["ticker", "target_weight"]
        weights["date"] = d
        weights_list.append(weights)
    if not weights_list:
        print("No se generaron pesos; abortando backtest.")
        return
    df_weights = pd.concat(weights_list, ignore_index=True)
    # 9. Backtest
    bt = EventDrivenBacktester(config, initial_capital=1_000_000)
    metrics = bt.run_backtest(df_prices, df_weights)
    print(f"Métricas backtest: {metrics}")
    df_equity = bt.get_equity_curve()
    df_trades = bt.get_trades()
    # 10. Reporte
    reporter = ExcelReporter(config)
    fi_dict = {
        m: pipeline.get_feature_importance(m, feature_cols) for m in config.modelos
    }
    output_path = run_dir / "reporte.xlsx"
    reporter.generate(output_path, metrics, {"predictions": df_pred, "weights": df_weights}, df_equity, df_trades, fi_dict)
    print(f"Reporte generado en {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecuta el sistema de trading completo")
    parser.add_argument("--limit_universe", type=int, default=30, help="Número máximo de tickers en el universo")
    args = parser.parse_args()
    main(args)