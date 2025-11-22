#!/usr/bin/env python3
"""
Helper script para guardar CSVs de opciones en Google Drive y verificar que están accesibles.

Este script:
1. Monta Google Drive (si no está montado)
2. Crea el directorio necesario
3. Guarda el CSV en la ubicación correcta
4. Verifica que el archivo es encontrado por el patrón de run_pipeline.py
"""

import os
import glob
import sys
from pathlib import Path


def mount_drive():
    """Monta Google Drive si no está montado."""
    try:
        from google.colab import drive
        
        if not os.path.exists("/content/drive"):
            print("Montando Google Drive...")
            drive.mount('/content/drive')
            print("✅ Drive montado correctamente")
        else:
            print("✅ Drive ya está montado")
        
        return True
    except ImportError:
        print("⚠️ No estás en Colab - no se puede montar Drive")
        return False
    except Exception as e:
        print(f"❌ Error montando Drive: {e}")
        return False


def create_directory(base_dir):
    """Crea el directorio donde se guardarán los CSVs."""
    try:
        os.makedirs(base_dir, exist_ok=True)
        print(f"✅ Directorio creado/verificado: {base_dir}")
        return True
    except Exception as e:
        print(f"❌ Error creando directorio: {e}")
        return False


def save_csv_to_drive(df, ticker, expiry, base_dir):
    """
    Guarda un DataFrame de opciones en Drive con el nombre correcto.
    
    Args:
        df: DataFrame con features de opciones
        ticker: Símbolo del ticker (ej. "AAPL")
        expiry: Fecha de expiración (ej. "2024-01-19")
        base_dir: Directorio base en Drive
    
    Returns:
        str: Path del archivo guardado, o None si hubo error
    """
    try:
        filename = f"{ticker}_options_trades_around_{expiry}.csv"
        filepath = os.path.join(base_dir, filename)
        
        df.to_csv(filepath, index=False)
        
        print(f"✅ CSV guardado: {filepath}")
        print(f"   Shape: {df.shape}")
        print(f"   Columnas: {list(df.columns)}")
        
        # Verificar que el archivo existe
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"   Tamaño: {file_size:,} bytes")
            return filepath
        else:
            print(f"❌ Error: El archivo no existe después de guardarlo")
            return None
            
    except Exception as e:
        print(f"❌ Error guardando CSV: {e}")
        return None


def verify_pattern_match(base_dir, ticker):
    """
    Verifica que el CSV guardado es encontrado por el patrón de run_pipeline.py.
    
    Args:
        base_dir: Directorio base en Drive
        ticker: Símbolo del ticker
    
    Returns:
        list: Lista de archivos encontrados
    """
    pattern = os.path.join(base_dir, f"{ticker}_options_trades_*.csv")
    files = glob.glob(pattern)
    
    print(f"\n{'='*70}")
    print(f"Verificación de Patrón")
    print(f"{'='*70}")
    print(f"Patrón: {pattern}")
    print(f"Archivos encontrados: {len(files)}")
    
    if files:
        print("✅ El patrón encuentra los siguientes archivos:")
        for f in files:
            print(f"   - {f}")
    else:
        print("❌ El patrón NO encuentra ningún archivo")
        print("\nArchivos en el directorio:")
        if os.path.exists(base_dir):
            all_files = os.listdir(base_dir)
            if all_files:
                for f in all_files:
                    print(f"   - {f}")
            else:
                print("   (directorio vacío)")
        else:
            print("   (directorio no existe)")
    
    print(f"{'='*70}\n")
    
    return files


def list_all_options_csvs(base_dir):
    """Lista todos los CSVs de opciones en el directorio."""
    if not os.path.exists(base_dir):
        print(f"⚠️ El directorio no existe: {base_dir}")
        return []
    
    all_files = [f for f in os.listdir(base_dir) if f.endswith('.csv')]
    options_files = [f for f in all_files if '_options_trades_' in f]
    
    print(f"\n{'='*70}")
    print(f"CSVs de Opciones en Drive")
    print(f"{'='*70}")
    print(f"Directorio: {base_dir}")
    print(f"Total CSVs: {len(all_files)}")
    print(f"CSVs de opciones: {len(options_files)}")
    
    if options_files:
        print("\nArchivos de opciones encontrados:")
        for f in options_files:
            filepath = os.path.join(base_dir, f)
            size = os.path.getsize(filepath)
            print(f"   - {f} ({size:,} bytes)")
    else:
        print("\n⚠️ No se encontraron CSVs de opciones")
    
    print(f"{'='*70}\n")
    
    return options_files


# Configuración por defecto
DEFAULT_BASE_DIR = "/content/drive/MyDrive/sistema-de-trading/archivos descargables"


if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"Helper: Guardar y Verificar CSVs de Opciones en Drive")
    print(f"{'='*70}\n")
    
    # Montar Drive
    if not mount_drive():
        print("\n❌ No se pudo montar Drive. Saliendo...")
        sys.exit(1)
    
    # Crear directorio
    if not create_directory(DEFAULT_BASE_DIR):
        print("\n❌ No se pudo crear el directorio. Saliendo...")
        sys.exit(1)
    
    # Listar archivos existentes
    list_all_options_csvs(DEFAULT_BASE_DIR)
    
    print("\n✅ Setup completo!")
    print(f"\nPara guardar un CSV, usa:")
    print(f"```python")
    print(f"from save_options_to_drive import save_csv_to_drive, verify_pattern_match")
    print(f"")
    print(f"# Guardar")
    print(f"save_csv_to_drive(df, 'AAPL', '2024-01-19', '{DEFAULT_BASE_DIR}')")
    print(f"")
    print(f"# Verificar")
    print(f"verify_pattern_match('{DEFAULT_BASE_DIR}', 'AAPL')")
    print(f"```")
