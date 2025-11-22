#!/usr/bin/env python3
"""
Script para generar CSVs de opciones para múltiples tickers.

Uso:
    python generate_options_csvs.py --tickers AAPL MSFT GOOGL --expiry 2024-01-19 --output_dir /path/to/output

Este script:
1. Carga OptionsTradesLoader con configuración optimizada
2. Para cada ticker, descarga features de opciones
3. Guarda cada DataFrame como CSV en el formato esperado por run_pipeline.py
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Agregar el directorio actual al path para imports
sys.path.insert(0, str(Path(__file__).parent))

from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)


def generate_options_csv(
    ticker: str,
    expiry: str,
    output_dir: str,
    api_key: str,
    days_before: int = 30,
    contracts_limit: int = 100,
) -> None:
    """
    Genera un CSV de features de opciones para un ticker y expiry dados.
    
    Args:
        ticker: Símbolo del subyacente (ej. "AAPL")
        expiry: Fecha de expiración en formato YYYY-MM-DD
        output_dir: Directorio donde guardar el CSV
        api_key: API key de Polygon
        days_before: Días antes de la expiración a incluir
        contracts_limit: Límite de contratos a procesar
    """
    print(f"\n{'='*70}")
    print(f"Procesando {ticker} con expiry {expiry}")
    print(f"{'='*70}")
    
    # Configurar loader
    cfg = OptionsTradesConfig(
        days_before_expiry=days_before,
        days_after_expiry=0,
        contracts_limit=contracts_limit,
        trades_limit_per_contract=50000,
        min_trades_per_day=1,
    )
    
    loader = OptionsTradesLoader(cfg, api_key=api_key)
    
    # Generar features
    print(f"Descargando features de opciones...")
    df = loader.build_daily_features_for_underlying_and_expiry(ticker, expiry)
    
    if df.empty:
        print(f"⚠️ No se encontraron datos para {ticker} con expiry {expiry}")
        return
    
    # Guardar CSV
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{ticker}_options_trades_around_{expiry}.csv"
    filepath = os.path.join(output_dir, filename)
    
    df.to_csv(filepath, index=False)
    
    print(f"✅ Guardado: {filepath}")
    print(f"   Shape: {df.shape}")
    print(f"   Columnas: {list(df.columns)}")
    print(f"   Rango de fechas: {df['date'].min()} a {df['date'].max()}")


def main():
    parser = argparse.ArgumentParser(
        description="Genera CSVs de features de opciones para múltiples tickers"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="Lista de tickers a procesar (ej. AAPL MSFT GOOGL)"
    )
    parser.add_argument(
        "--expiry",
        required=True,
        help="Fecha de expiración en formato YYYY-MM-DD"
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directorio donde guardar los CSVs"
    )
    parser.add_argument(
        "--api_key",
        help="API key de Polygon (si no se proporciona, usa POLYGON_API_KEY env var)"
    )
    parser.add_argument(
        "--days_before",
        type=int,
        default=30,
        help="Días antes de la expiración a incluir (default: 30)"
    )
    parser.add_argument(
        "--contracts_limit",
        type=int,
        default=100,
        help="Límite de contratos a procesar (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Obtener API key
    api_key = args.api_key or os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("❌ Error: Se requiere API key de Polygon")
        print("   Proporciona --api_key o configura POLYGON_API_KEY env var")
        sys.exit(1)
    
    # Validar fecha
    try:
        datetime.strptime(args.expiry, "%Y-%m-%d")
    except ValueError:
        print(f"❌ Error: Fecha inválida '{args.expiry}'. Usa formato YYYY-MM-DD")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"Generación de CSVs de Opciones")
    print(f"{'='*70}")
    print(f"Tickers: {', '.join(args.tickers)}")
    print(f"Expiry: {args.expiry}")
    print(f"Output dir: {args.output_dir}")
    print(f"Days before: {args.days_before}")
    print(f"Contracts limit: {args.contracts_limit}")
    
    # Procesar cada ticker
    success_count = 0
    for ticker in args.tickers:
        try:
            generate_options_csv(
                ticker=ticker,
                expiry=args.expiry,
                output_dir=args.output_dir,
                api_key=api_key,
                days_before=args.days_before,
                contracts_limit=args.contracts_limit,
            )
            success_count += 1
        except Exception as e:
            print(f"❌ Error procesando {ticker}: {e}")
            continue
    
    print(f"\n{'='*70}")
    print(f"Completado: {success_count}/{len(args.tickers)} tickers procesados")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
