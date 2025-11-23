#!/usr/bin/env python3
"""
Wrapper para ejecutar run_pipeline.py en Google Colab.

Este script lee las API keys desde el baúl de secretos de Colab
(usando google.colab.userdata) y las exporta como variables de entorno
antes de ejecutar run_pipeline.py.

Uso en Colab:
    !python run_pipeline_colab.py --limit_universe 500 --seed 42
"""

import os
import sys

def main():
    # Importar userdata de Colab
    try:
        from google.colab import userdata
    except ImportError:
        print("❌ Error: Este script solo funciona en Google Colab")
        print("   Si estás en un entorno local, usa run_pipeline.py directamente")
        print("   y configura las variables de entorno POLYGON_API_KEY y FMP_API_KEY")
        sys.exit(1)
    
    # Leer API keys desde el baúl de secretos
    try:
        fmp_key = userdata.get('FMP_API_KEY')
        print(f"✅ FMP_API_KEY leída desde baúl de secretos")
    except Exception as e:
        print(f"⚠️  No se pudo leer FMP_API_KEY desde baúl: {e}")
        fmp_key = ""
    
    try:
        polygon_key = userdata.get('POLYGON_API_KEY')
        print(f"✅ POLYGON_API_KEY leída desde baúl de secretos")
    except Exception as e:
        print(f"⚠️  No se pudo leer POLYGON_API_KEY desde baúl: {e}")
        polygon_key = ""
    
    # Exportar como variables de entorno
    if fmp_key:
        os.environ['FMP_API_KEY'] = fmp_key
        print(f"✅ FMP_API_KEY exportada a variable de entorno")
    else:
        print(f"⚠️  FMP_API_KEY no configurada")
    
    if polygon_key:
        os.environ['POLYGON_API_KEY'] = polygon_key
        print(f"✅ POLYGON_API_KEY exportada a variable de entorno")
    else:
        print(f"⚠️  POLYGON_API_KEY no configurada")
    
    print(f"\n{'='*70}")
    print(f"Ejecutando run_pipeline.py...")
    print(f"{'='*70}\n")
    
    # Importar y ejecutar run_pipeline
    # Esto asegura que las variables de entorno estén disponibles
    import run_pipeline
    
    # Pasar los argumentos de línea de comandos
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline completo de trading")
    parser.add_argument("--limit_universe", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    
    # Ejecutar main de run_pipeline
    run_pipeline.main(args)

if __name__ == "__main__":
    main()
