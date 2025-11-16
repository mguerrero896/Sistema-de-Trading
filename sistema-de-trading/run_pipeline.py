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
from typing import List, Tuple

import pandas as pd

from sistema_de_trading.config import Config
from sistema_de_trading.data.data_loader import DataLoader
from sistema_de_trading.features.feature_engineer import FeatureEngineer
from sistema_de_trading.models.ml_pipeline import MLPipeline
from sistema_de_trading.backtesting.event_backtester import EventDrivenBacktester
from sistema_de_trading.reporting.excel_reporter import ExcelReporter


def split_by_year(
    df: pd.DataFrame,
    config: Config,
    label_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Divide el DataFrame en train/val/test basándose en años.

    Los primeros ``config.anos_train`` años se usan para train,
    los siguientes ``config.anos_val`` para validación
    y los últimos ``config.anos_test`` para test.
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
    # 1. Configuración
    config = Config()

    # 2. Directorio de ejecución
    run_dir = Path(config.runs_dir) / pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Guardar resultados en: {run_dir}")

    # 3. Descarga de datos brutos
    loader = DataLoader(config.polygon_api_key, config.fmp_api_key)
    tickers: List[str] = loader.get_sp500_tickers(limit=args.limit_universe)
    print(f"Obtenidos {len(tickers)} tickers")

    df_prices = loader.download_price_data(tickers, config.fecha_inicio, config.fecha_fin)
    print("Tickers descargados (sin filtros):", df_prices["ticker"].nunique())

    # Añadir fundamentales y aplicar filtros suaves
    df_fund = loader.download_fundamentals(tickers)
    df_prices = df_prices.merge(df_fund, on="ticker", how="left")
    df_prices = loader.apply_filters(
        df_prices,
        min_price=config.precio_min,
        min_volume=config.volumen_medio_min,
        window=config.ventana_volumen,
    )
    print("Tickers tras filtros:", df_prices["ticker"].nunique())

    # 4. Features + etiquetas
    fe = FeatureEngineer(config)
    df_feat = fe.create_all_features(df_prices)
    df_feat = fe.create_labels(df_feat, [config.k_principal])
    df_feat = fe.normalize_features(df_feat, method="standardize")

    # 5. Split temporal
    feature_cols = [c for c in df_feat.columns if c.startswith("feat_")]
    label_col = f"label_{config.k_principal}"
    df_train, df_val, df_test = split_by_year(df_feat, config, label_col)
    print(f"Tamaño train: {len(df_train)}, val: {len(df_val)}, test: {len(df_test)}")

    # 6. Entrenar modelos sólo con train (y calibrar con val)
    pipeline = MLPipeline(config)
    pipeline.fit(df_train, df_val, feature_cols, label_col)
    metrics_eval = pipeline.evaluate(df_val, feature_cols, label_col)
    print(f"Métricas de validación: {metrics_eval}")

    # 7. Predicciones SÓLO en test (evitar leak)
    df_pred_test = pipeline.predict(df_test, feature_cols)

    # Neutralizar por sector si se solicita
    if config.neutralizar_por_sector:
        for model in config.modelos:
            col = f"pred_{model}"
            if col in df_pred_test.columns:
                df_pred_test = pipeline.neutralize_by_sector(df_pred_test, col, "sector")

    # ------------------------------------------------------------------
    # 8. Asignación Top-N long/short sobre test (sin solver)
    # ------------------------------------------------------------------
    import pandas as _pd  # alias local

    N_LONG = 5
    N_SHORT = 5
    LEVERAGE = config.apalancamiento_bruto_max

    print(
        f"Esquema Top-N long/short (sólo test): N_LONG={N_LONG}, "
        f"N_SHORT={N_SHORT}, LEVERAGE={LEVERAGE}"
    )

    # Usamos el primer modelo definido en Config como fuente de expected_return
    pred_col = f"pred_{config.modelos[0]}"
    if pred_col not in df_pred_test.columns:
        raise ValueError(
            f"La columna de predicciones '{pred_col}' no existe en df_pred_test. "
            f"Columnas disponibles: {df_pred_test.columns.tolist()}"
        )

    # Señales sólo en test
    sig = df_pred_test[["date", "ticker", pred_col]].copy()
    sig.rename(columns={pred_col: "expected_return"}, inplace=True)
    sig["target_weight"] = 0.0

    weights_rows: List[pd.DataFrame] = []

    for d, sub in sig.groupby("date"):
        sub = sub.sort_values("expected_return")

        # Peores N -> short
        shorts = sub.head(N_SHORT)["ticker"].tolist()
        # Mejores N -> long
        longs = sub.tail(N_LONG)["ticker"].tolist()

        weights = _pd.Series(0.0, index=sub["ticker"])

        if len(longs) > 0:
            weights.loc[longs] = LEVERAGE / (2 * len(longs))
        if len(shorts) > 0:
            weights.loc[shorts] = -LEVERAGE / (2 * len(shorts))

        tmp = weights.reset_index()
        tmp.columns = ["ticker", "target_weight"]
        tmp["date"] = d
        weights_rows.append(tmp)

    if not weights_rows:
        print("No se generaron pesos en test; abortando backtest.")
        return

    df_weights = _pd.concat(weights_rows, ignore_index=True)

    # 9. Backtest sólo en tramo de test
    # Usamos df_prices desde la primera fecha de test en adelante
    start_test = pd.to_datetime(df_test["date"].min()).date()
    df_prices_bt = df_prices[df_prices["date"] >= start_test].copy()

    bt = EventDrivenBacktester(config, initial_capital=1_000_000)
    metrics = bt.run_backtest(df_prices_bt, df_weights)
    print(f"Métricas backtest (sólo test): {metrics}")

    df_equity = bt.get_equity_curve()
    df_trades = bt.get_trades()

    # 10. Reporte (predicciones y pesos sólo de test)
    reporter = ExcelReporter(config)
    fi_dict = {m: pipeline.get_feature_importance(m, feature_cols) for m in config.modelos}
    output_path = run_dir / "reporte.xlsx"
    reporter.generate(
        output_path,
        metrics,
        {"predictions": df_pred_test, "weights": df_weights},
        df_equity,
        df_trades,
        fi_dict,
    )
    print(f"Reporte generado en {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecuta el sistema de trading completo")
    parser.add_argument(
        "--limit_universe",
        type=int,
        default=30,
        help="Número máximo de tickers en el universo",
    )
    args = parser.parse_args()
    main(args)

