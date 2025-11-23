#!/usr/bin/env python3
"""
Wrapper para ejecutar run_pipeline.py con configuración de entorno.

Este script lee las API keys desde variables de entorno (os.getenv).
La configuración de estas variables debe hacerse ANTES de ejecutar este script,
típicamente desde el notebook de Colab usando google.colab.userdata.

Uso en Colab:
    # En el notebook, primero configurar las variables de entorno:
    from google.colab import userdata
    import os
    os.environ['FMP_API_KEY'] = userdata.get('FMP_API_KEY')
    os.environ['POLYGON_API_KEY'] = userdata.get('POLYGON_API_KEY')
    
    # Luego ejecutar este script:
    !python run_pipeline_colab.py --limit_universe 500 --seed 42

Uso local:
    export FMP_API_KEY="tu_clave"
    export POLYGON_API_KEY="tu_clave"
    python run_pipeline_colab.py --limit_universe 500 --seed 42
"""

import os
import sys
import argparse

def main():
    # Verificar que las API keys estén configuradas en el entorno
    fmp_key = os.getenv("FMP_API_KEY", "")
    polygon_key = os.getenv("POLYGON_API_KEY", "")
    
    if not fmp_key:
        print("⚠️  FMP_API_KEY no configurada en el entorno")
        print("    Configúrala en el notebook antes de ejecutar este script:")
        print("    os.environ['FMP_API_KEY'] = userdata.get('FMP_API_KEY')")
    else:
        print("✅ FMP_API_KEY configurada en el entorno")
    
    if not polygon_key:
        print("⚠️  POLYGON_API_KEY no configurada en el entorno")
        print("    Configúrala en el notebook antes de ejecutar este script:")
        print("    os.environ['POLYGON_API_KEY'] = userdata.get('POLYGON_API_KEY')")
    else:
        print("✅ POLYGON_API_KEY configurada en el entorno")
    
    print(f"\n{'='*70}")
    print(f"Ejecutando run_pipeline.py...")
    print(f"{'='*70}\n")
    
    # Importar y ejecutar run_pipeline
    import run_pipeline
    
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Pipeline completo de trading")
    parser.add_argument("--limit_universe", type=int, default=500,
                        help="Número máximo de tickers a procesar")
    parser.add_argument("--seed", type=int, default=42,
                        help="Semilla para reproducibilidad")
    args = parser.parse_args()
    
    # Ejecutar main de run_pipeline
    run_pipeline.main(args)

if __name__ == "__main__":
    main()
