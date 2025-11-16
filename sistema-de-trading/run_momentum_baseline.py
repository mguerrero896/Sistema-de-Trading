from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from sistema_de_trading.config import Config
from sistema_de_trading.data.data_loader import DataLoader
from sistema_de_trading.features.feature_engineer import FeatureEngineer
from sistema_de_trading.backtesting.event_backtester import EventDrivenBacktester
from sistema_de_trading.reporting.excel_reporter import ExcelReporter


def split_by_year(
    df: pd.DataFrame,
    config: Config,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Divide el DataFrame en train/val/test basándose en años (sin usar labels)."""
    df_sorted = df.sort_values("date").copy()
    df_sorted["year"] = pd.to_datetime(df_sorted["date"]).dt.year

    unique_years = sorted(df_sorted["year"].unique())
    train_years = unique_years[: config.anos_train]
    val_years = unique_years[config.anos_train : config.anos_train + config.anos_val]
    test_years = unique_years[-config.anos_test :]

    df_train = df_sorted[df_sorted["year"].isin(train_years)].reset_index(drop=True)
    df_val = df_sorted[df_sorted["year"].isin(val_years)].reset_index(drop=True)
    df_test = df_sorted[df_sorted["year"].isin(test_years)].reset_index(drop=True)
    return df_train, df_val, df_test


def main(args: argparse.Namespace) -> None:
    # 1. Configuración
    config = Config()

    run_dir = Path(config.runs_dir) / f"baseline_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[BASELINE] Guardar resultados en: {run_dir}")

    # 2. Datos
    loader = DataLoader(config.polygon_api_key, config.fmp_api_key)
    tickers: List[str] = loader.get_sp500_tickers(limit=args.limit_universe)
    print(f"[BASELINE] Obtenidos {len(tickers)} tickers")

    df_prices = loader.download_price_data(tickers, config.fecha_inicio, config.fecha_fin)
    print("[BASELINE] Tickers descargados (sin filtros):", df_prices["ticker"].nunique())

    df_fund = loader.download_fundamentals(tickers)
    df_prices = df_prices.merge(df_fund, on="ticker", how="left")
    df_prices = loader.apply_filters(
        df_prices,
        min_price=config.precio_min,
        min_volume=config.volumen_medio_min,
        window=config.ventana_volumen,
    )
    print("[BASELINE] Tickers tras filtros:", df_prices["ticker"].nunique())

    # 3. Features (NO labels necesarias aquí)
    fe = FeatureEngineer(config)
    df_feat = fe.create_all_features(df_prices)
    df_feat = fe.normalize_features(df_feat, method="standardize")

    feature_cols = [c for c in df_feat.columns if c.startswith("feat_")]

    # 4. Split temporal
    df_train, df_val, df_test = split_by_year(df_feat, config)
    print(
        f"[BASELINE] Tamaño train: {len(df_train)}, "
        f"val: {len(df_val)}, test: {len(df_test)}"
    )

    # ------------------------------------------------------------------
    # 5. Señal de momentum simple en test
    # ------------------------------------------------------------------
    # Ejemplo: score = retorno acumulado 60d (feat_ret_60d)
    if "feat_ret_60d" not in df_test.columns:
        raise ValueError(
            "[BASELINE] No se encontró feat_ret_60d en df_test. "
            "Asegúrate de que FeatureEngineer la genera."
        )

    df_sig = df_test[["date", "ticker", "feat_ret_60d"]].copy()
    df_sig.rename(columns={"feat_ret_60d": "expected_return"}, inplace=True)

    # ------------------------------------------------------------------
    # 6. Asignación Top-N long/short sobre test
    # ------------------------------------------------------------------
    import pandas as _pd

    N_LONG = 5
    N_SHORT = 5
    LEVERAGE = config.apalancamiento_bruto_max

    print(
        f"[BASELINE] Esquema Top-N long/short (sólo test): "
        f"N_LONG={N_LONG}, N_SHORT={N_SHORT}, LEVERAGE={LEVERAGE}"
    )

    df_sig["target_weight"] = 0.0
    weights_rows: List[pd.DataFrame] = []

    for d, sub in df_sig.groupby("date"):
        sub = sub.sort_values("expected_return")

        shorts = sub.head(N_SHORT)["ticker"].tolist()
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
        print("[BASELINE] No se generaron pesos en test; abortando backtest.")
        return

    df_weights = _pd.concat(weights_rows, ignore_index=True)

    # 7. Backtest sólo en tramo de test
    start_test = pd.to_datetime(df_test["date"].min()).date()
    df_prices_bt = df_prices[df_prices["date"] >= start_test].copy()

    bt = EventDrivenBacktester(config, initial_capital=1_000_000)
    metrics = bt.run_backtest(df_prices_bt, df_weights)
    print(f"[BASELINE] Métricas backtest (sólo test): {metrics}")

    df_equity = bt.get_equity_curve()
    df_trades = bt.get_trades()

    # 8. Reporte
    reporter = ExcelReporter(config)
    # Para baseline, no hay importancias de features por modelo
    fi_dict = {}
    output_path = run_dir / "reporte_baseline.xlsx"
    reporter.generate(
        output_path,
        metrics,
        {"predictions": df_sig, "weights": df_weights},
        df_equity,
        df_trades,
        fi_dict,
    )
    print(f"[BASELINE] Reporte generado en {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecuta baseline momentum Top-N")
    parser.add_argument(
        "--limit_universe",
        type=int,
        default=30,
        help="Número máximo de tickers en el universo",
    )
    args = parser.parse_args()
    main(args)
