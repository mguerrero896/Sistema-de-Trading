# 🔧 Workflow Corregido: Guardar CSVs en Drive y Ejecutar Pipeline

Este workflow corrige el problema donde `run_pipeline.py` no encuentra los CSVs de opciones en Drive.

---

## 🚨 Problema Identificado

```
No se encontraron CSVs de opciones compatibles en Drive; se continúa sin ellas.
```

**Causa:** El CSV no está guardado en la ubicación exacta que `run_pipeline.py` espera:
```
/content/drive/MyDrive/sistema-de-trading/archivos descargables/
```

---

## ✅ Solución: Workflow Paso a Paso

### 🔹 CELDA 1: Setup Inicial

```python
# ============================================================================
# SETUP: Clonar repo e instalar dependencias
# ============================================================================

%cd /content
!rm -rf Sistema-de-Trading
!git clone -b expOptions --single-branch https://github.com/mguerrero896/Sistema-de-Trading.git

%cd /content/Sistema-de-Trading/sistema-de-trading
!pip install -q -r requirements.txt

print("✅ Setup completo!")
```

---

### 🔹 CELDA 2: Montar Drive y Crear Directorio

```python
# ============================================================================
# IMPORTANTE: Montar Drive PRIMERO
# ============================================================================

from google.colab import drive
import os

# Montar Drive
drive.mount('/content/drive')

# Crear directorio exacto que run_pipeline.py espera
BASE_DIR = "/content/drive/MyDrive/sistema-de-trading/archivos descargables"
os.makedirs(BASE_DIR, exist_ok=True)

print(f"✅ Drive montado")
print(f"✅ Directorio creado: {BASE_DIR}")

# Verificar que el directorio existe
if os.path.exists(BASE_DIR):
    print(f"✅ Directorio verificado")
    existing_files = os.listdir(BASE_DIR)
    print(f"   Archivos existentes: {len(existing_files)}")
    if existing_files:
        for f in existing_files:
            print(f"   - {f}")
else:
    print(f"❌ ERROR: El directorio no existe")
```

---

### 🔹 CELDA 3: Configurar API Keys

```python
# ============================================================================
# Configurar API keys
# ============================================================================

from google.colab import userdata

try:
    polygon_key = userdata.get('POLYGON_API_KEY')
    fmp_key = userdata.get('FMP_API_KEY')
    print("✅ API keys configuradas")
except Exception as e:
    print("❌ Error: Configura las API keys en Colab Secrets (🔑)")
```

---

### 🔹 CELDA 4: Generar y Guardar CSV en Drive

```python
# ============================================================================
# Generar features de opciones y guardar EN DRIVE
# ============================================================================

import sys
sys.path.insert(0, '/content/Sistema-de-Trading/sistema-de-trading')

from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)

# Configuración para testing (rápido)
cfg = OptionsTradesConfig(
    days_before_expiry=7,   # Solo 7 días
    contracts_limit=10,     # Solo 10 contratos
)

loader = OptionsTradesLoader(cfg, api_key=polygon_key)

# Generar features
print("Generando features de opciones para AAPL...")
df_aapl = loader.build_daily_features_for_underlying_and_expiry(
    underlying="AAPL",
    expiry="2024-01-19"
)

if df_aapl.empty:
    print("❌ No se generaron datos")
else:
    print(f"✅ Datos generados: {df_aapl.shape}")
    
    # IMPORTANTE: Guardar EN DRIVE (no en /content)
    ticker = "AAPL"
    expiry = "2024-01-19"
    filename = f"{ticker}_options_trades_around_{expiry}.csv"
    filepath = os.path.join(BASE_DIR, filename)
    
    df_aapl.to_csv(filepath, index=False)
    
    print(f"\n✅ CSV guardado EN DRIVE:")
    print(f"   Path: {filepath}")
    print(f"   Shape: {df_aapl.shape}")
    
    # Verificar que el archivo existe
    if os.path.exists(filepath):
        file_size = os.path.getsize(filepath)
        print(f"   Tamaño: {file_size:,} bytes")
        print(f"✅ Archivo verificado en Drive")
    else:
        print(f"❌ ERROR: El archivo no existe después de guardarlo")
```

---

### 🔹 CELDA 5: Verificar Patrón (CRÍTICO)

```python
# ============================================================================
# VERIFICAR que run_pipeline.py puede encontrar el CSV
# ============================================================================

import glob

ticker = "AAPL"
pattern = os.path.join(BASE_DIR, f"{ticker}_options_trades_*.csv")

print(f"\n{'='*70}")
print(f"VERIFICACIÓN DE PATRÓN")
print(f"{'='*70}")
print(f"Patrón: {pattern}")

files = glob.glob(pattern)

if files:
    print(f"✅ ÉXITO: Encontrados {len(files)} archivo(s)")
    for f in files:
        print(f"   - {f}")
    print(f"\n✅ run_pipeline.py PODRÁ encontrar estos archivos")
else:
    print(f"❌ ERROR: El patrón NO encuentra ningún archivo")
    print(f"\nArchivos en el directorio:")
    all_files = os.listdir(BASE_DIR)
    for f in all_files:
        print(f"   - {f}")
    print(f"\n❌ run_pipeline.py NO encontrará los archivos")

print(f"{'='*70}\n")
```

---

### 🔹 CELDA 6: Ejecutar Pipeline

```python
# ============================================================================
# Ejecutar run_pipeline.py (ahora SÍ encontrará los CSVs)
# ============================================================================

%cd /content/Sistema-de-Trading/sistema-de-trading

!python run_pipeline.py --limit_universe 20 --seed 42

print("\n✅ Pipeline completado!")
```

---

### 🔹 CELDA 7: Verificar que se Usaron las Opciones

```python
# ============================================================================
# Verificar que el pipeline usó los CSVs de opciones
# ============================================================================

import glob
import pandas as pd

# Encontrar el último reporte
reports = sorted(glob.glob("runs/*/reporte.xlsx"))

if reports:
    latest_report = reports[-1]
    print(f"📊 Último reporte: {latest_report}")
    
    # Leer métricas
    df_metrics = pd.read_excel(latest_report, sheet_name="backtest_metrics")
    
    print("\n📈 Métricas:")
    print(f"   Sharpe Ratio: {df_metrics['sharpe_ratio'].values[0]:.4f}")
    print(f"   Total Return: {df_metrics['total_return'].values[0]*100:.2f}%")
    print(f"   Max Drawdown: {df_metrics['max_drawdown'].values[0]*100:.2f}%")
    
    # Verificar si hay columnas de opciones en los datos
    # (esto requeriría leer los datos intermedios, pero al menos vemos las métricas)
    
else:
    print("❌ No se encontró ningún reporte")
```

---

## 📋 Checklist de Verificación

Antes de ejecutar `run_pipeline.py`, asegúrate de que:

- [ ] Drive está montado (`/content/drive` existe)
- [ ] Directorio creado (`/content/drive/MyDrive/sistema-de-trading/archivos descargables`)
- [ ] CSV guardado EN DRIVE (no en `/content`)
- [ ] Patrón `glob` encuentra el CSV
- [ ] Nombre del archivo: `{TICKER}_options_trades_*.csv`

---

## 🚨 Errores Comunes

### Error 1: "No se encontraron CSVs de opciones"

**Causa:** El CSV no está en Drive o el nombre no coincide con el patrón.

**Solución:**
1. Ejecuta la CELDA 5 (verificación de patrón)
2. Si no encuentra nada, verifica que el CSV esté en Drive
3. Verifica que el nombre sea: `AAPL_options_trades_around_2024-01-19.csv`

### Error 2: CSV guardado en `/content` en lugar de Drive

**Causa:** Guardaste el CSV antes de montar Drive.

**Solución:**
1. Monta Drive PRIMERO (CELDA 2)
2. Luego genera y guarda el CSV (CELDA 4)

### Error 3: Drive no montado

**Causa:** No ejecutaste `drive.mount('/content/drive')`.

**Solución:**
1. Ejecuta la CELDA 2
2. Autoriza el acceso a Drive cuando te lo pida

---

## ✅ Resultado Esperado

Cuando ejecutes `run_pipeline.py`, deberías ver:

```
✅ Encontrados 1 CSV(s) de opciones para AAPL
✅ Merge completado: df_prices tiene columnas opt_*
```

En lugar de:

```
❌ No se encontraron CSVs de opciones compatibles en Drive
```

---

## 🎯 Próximos Pasos

Una vez que el pipeline encuentre los CSVs:

1. Compara métricas con expB (baseline)
2. Genera CSVs para más tickers
3. Ejecuta con universo más grande

**¡Ahora sí debería funcionar!** 🚀
