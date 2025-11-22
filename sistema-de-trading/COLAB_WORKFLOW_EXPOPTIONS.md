# 🚀 Workflow Completo: expOptions con Features de Opciones Reales

Este documento describe el flujo completo para:
1. Generar CSVs de opciones para múltiples tickers
2. Ejecutar el pipeline completo de expOptions
3. Comparar métricas contra el baseline expB

---

## 📋 Pre-requisitos

- API key de Polygon (plan Options Advanced)
- API key de FMP (plan Ultimate)
- Google Drive montado en Colab

---

## 🔹 PASO 1: Setup Inicial

```python
# ============================================================================
# CELDA 1: Clonar repositorio e instalar dependencias
# ============================================================================

%cd /content
!rm -rf Sistema-de-Trading
!git clone -b expOptions --single-branch https://github.com/mguerrero896/Sistema-de-Trading.git

%cd /content/Sistema-de-Trading/sistema-de-trading
!pip install -q -r requirements.txt

print("✅ Setup completo!")
```

---

## 🔹 PASO 2: Configurar API Keys

```python
# ============================================================================
# CELDA 2: Configurar API keys en Colab Secrets
# ============================================================================

from google.colab import userdata

# Verificar que las keys estén configuradas
try:
    polygon_key = userdata.get('POLYGON_API_KEY')
    fmp_key = userdata.get('FMP_API_KEY')
    print("✅ API keys configuradas correctamente")
except Exception as e:
    print("❌ Error: Configura las API keys en Colab Secrets (🔑)")
    print("   - POLYGON_API_KEY")
    print("   - FMP_API_KEY")
```

---

## 🔹 PASO 3: Montar Google Drive

```python
# ============================================================================
# CELDA 3: Montar Drive y crear directorio para CSVs
# ============================================================================

from google.colab import drive
import os

# Montar Drive
drive.mount('/content/drive')

# Crear directorio donde run_pipeline.py buscará los CSVs
base_dir = "/content/drive/MyDrive/sistema-de-trading/archivos descargables"
os.makedirs(base_dir, exist_ok=True)

print(f"✅ Directorio creado: {base_dir}")
print(f"   Contenido actual: {os.listdir(base_dir) if os.path.exists(base_dir) else '(vacío)'}")
```

---

## 🔹 PASO 4: Generar CSVs de Opciones

### Opción A: Un solo ticker (rápido para testing)

```python
# ============================================================================
# CELDA 4A: Generar CSV para AAPL (testing)
# ============================================================================

import sys
sys.path.insert(0, '/content/Sistema-de-Trading/sistema-de-trading')

from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)
from google.colab import userdata

# Configuración para testing (rápido)
cfg = OptionsTradesConfig(
    days_before_expiry=7,   # Solo 7 días (en lugar de 30)
    contracts_limit=10,     # Solo 10 contratos (en lugar de 100)
)

api_key = userdata.get('POLYGON_API_KEY')
loader = OptionsTradesLoader(cfg, api_key=api_key)

# Generar features para AAPL
print("Generando features de opciones para AAPL...")
df_aapl = loader.build_daily_features_for_underlying_and_expiry(
    underlying="AAPL",
    expiry="2024-01-19"  # ⚠️ Usar fecha PASADA
)

if not df_aapl.empty:
    # Guardar CSV
    file_path = os.path.join(
        base_dir,
        "AAPL_options_trades_around_2024-01-19.csv"
    )
    df_aapl.to_csv(file_path, index=False)
    
    print(f"✅ CSV guardado: {file_path}")
    print(f"   Shape: {df_aapl.shape}")
    print(f"   Columnas: {list(df_aapl.columns)}")
    print(f"   Rango de fechas: {df_aapl['date'].min()} a {df_aapl['date'].max()}")
else:
    print("⚠️ No se encontraron datos")
```

### Opción B: Múltiples tickers (producción)

```python
# ============================================================================
# CELDA 4B: Generar CSVs para múltiples tickers (producción)
# ============================================================================

# Lista de tickers a procesar
tickers_to_process = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
expiry_date = "2024-01-19"

# Configuración para producción
cfg_prod = OptionsTradesConfig(
    days_before_expiry=30,
    contracts_limit=100,
)

loader_prod = OptionsTradesLoader(cfg_prod, api_key=api_key)

# Procesar cada ticker
success_count = 0
for ticker in tickers_to_process:
    print(f"\n{'='*70}")
    print(f"Procesando {ticker}...")
    print(f"{'='*70}")
    
    try:
        df = loader_prod.build_daily_features_for_underlying_and_expiry(
            underlying=ticker,
            expiry=expiry_date
        )
        
        if not df.empty:
            file_path = os.path.join(
                base_dir,
                f"{ticker}_options_trades_around_{expiry_date}.csv"
            )
            df.to_csv(file_path, index=False)
            print(f"✅ {ticker}: Guardado {df.shape[0]} filas")
            success_count += 1
        else:
            print(f"⚠️ {ticker}: No se encontraron datos")
    
    except Exception as e:
        print(f"❌ {ticker}: Error - {e}")
        continue

print(f"\n{'='*70}")
print(f"Completado: {success_count}/{len(tickers_to_process)} tickers procesados")
print(f"{'='*70}")
```

---

## 🔹 PASO 5: Ejecutar Pipeline Completo de expOptions

```python
# ============================================================================
# CELDA 5: Ejecutar run_pipeline.py con opciones reales
# ============================================================================

%cd /content/Sistema-de-Trading/sistema-de-trading

# Ejecutar pipeline con universo limitado
!python run_pipeline.py --limit_universe 20 --seed 42

print("\n✅ Pipeline completado!")
print("   Revisa el directorio runs/ para ver los resultados")
```

---

## 🔹 PASO 6: Analizar Resultados

```python
# ============================================================================
# CELDA 6: Cargar y analizar resultados de expOptions
# ============================================================================

import pandas as pd
import glob

# Encontrar el último reporte generado
reports = sorted(glob.glob("runs/*/reporte.xlsx"))
if not reports:
    print("❌ No se encontró ningún reporte")
else:
    latest_report = reports[-1]
    print(f"📊 Último reporte: {latest_report}")
    
    # Leer métricas del backtest
    df_metrics = pd.read_excel(latest_report, sheet_name="backtest_metrics")
    
    print("\n📈 Métricas de expOptions:")
    print(df_metrics[['sharpe_ratio', 'total_return', 'max_drawdown', 'volatility']])
    
    # Descargar el reporte a Drive para comparación
    import shutil
    dest_path = f"/content/drive/MyDrive/sistema-de-trading/reporte_expOptions.xlsx"
    shutil.copy(latest_report, dest_path)
    print(f"\n✅ Reporte copiado a Drive: {dest_path}")
```

---

## 🔹 PASO 7: Ejecutar Baseline expB para Comparación

```python
# ============================================================================
# CELDA 7: Ejecutar baseline expB
# ============================================================================

%cd /content
!rm -rf Sistema-de-Trading-expB
!git clone -b expB --single-branch https://github.com/mguerrero896/Sistema-de-Trading.git Sistema-de-Trading-expB

%cd /content/Sistema-de-Trading-expB/sistema-de-trading
!pip install -q -r requirements.txt

# Ejecutar baseline (mismo universo y seed para comparación justa)
!python run_momentum_baseline.py --limit_universe 20 --seed 42

print("\n✅ Baseline expB completado!")
```

---

## 🔹 PASO 8: Comparar Métricas

```python
# ============================================================================
# CELDA 8: Comparación expOptions vs expB
# ============================================================================

import pandas as pd

# Cargar métricas de expB
reports_expb = sorted(glob.glob("/content/Sistema-de-Trading-expB/sistema-de-trading/runs/*/reporte.xlsx"))
if reports_expb:
    df_expb = pd.read_excel(reports_expb[-1], sheet_name="backtest_metrics")
    
    # Crear tabla comparativa
    comparison = pd.DataFrame({
        'Métrica': ['Sharpe Ratio', 'Total Return (%)', 'Max Drawdown (%)', 'Volatility (%)'],
        'expB (baseline)': [
            df_expb['sharpe_ratio'].values[0],
            df_expb['total_return'].values[0] * 100,
            df_expb['max_drawdown'].values[0] * 100,
            df_expb['volatility'].values[0] * 100,
        ],
        'expOptions (con opciones)': [
            df_metrics['sharpe_ratio'].values[0],
            df_metrics['total_return'].values[0] * 100,
            df_metrics['max_drawdown'].values[0] * 100,
            df_metrics['volatility'].values[0] * 100,
        ]
    })
    
    # Calcular diferencias
    comparison['Diferencia'] = comparison['expOptions (con opciones)'] - comparison['expB (baseline)']
    comparison['Mejora (%)'] = (comparison['Diferencia'] / comparison['expB (baseline)'].abs()) * 100
    
    print("\n" + "="*70)
    print("📊 COMPARACIÓN: expOptions vs expB")
    print("="*70)
    print(comparison.to_string(index=False))
    print("="*70)
    
    # Guardar comparación
    comparison.to_csv("/content/drive/MyDrive/sistema-de-trading/comparacion_expOptions_vs_expB.csv", index=False)
    print("\n✅ Comparación guardada en Drive")
else:
    print("❌ No se encontraron resultados de expB")
```

---

## 📝 Notas Importantes

### ⚠️ Performance

- **Generar CSVs de opciones es LENTO**
  - 1 ticker × 30 días × 100 contratos ≈ 10-20 minutos
  - 5 tickers ≈ 1-2 horas
  
- **Recomendación para testing:**
  - Usar `days_before_expiry=7` y `contracts_limit=10`
  - Probar con 1-2 tickers primero

### ⚠️ Fechas de Expiración

- **USAR FECHAS PASADAS** (con datos históricos)
  - ✅ "2024-01-19" (tiene trades)
  - ❌ "2025-12-19" (futura, sin trades)

### ⚠️ Merge de Opciones

- `run_pipeline.py` hace **left join** por `["date", "ticker"]`
- Si no hay CSV para un ticker, ese ticker tendrá `NaN` en columnas `opt_*`
- `FeatureEngineer._options_real` maneja `NaN` con `fillna(0)`

---

## 🎯 Checklist de Éxito

- [ ] API keys configuradas en Colab Secrets
- [ ] Drive montado y directorio creado
- [ ] CSV de opciones generado para al menos 1 ticker
- [ ] `run_pipeline.py` ejecutado sin errores
- [ ] Reporte Excel generado en `runs/`
- [ ] Baseline expB ejecutado
- [ ] Comparación de métricas completada

---

## 🚨 Troubleshooting

### "ModuleNotFoundError: No module named 'sistema_de_trading'"

```python
import sys
sys.path.insert(0, '/content/Sistema-de-Trading/sistema-de-trading')
```

### "No se encontraron contratos"

- Verifica que la fecha de expiración sea **pasada** (no futura)
- Usa `loader.debug_list_contracts("AAPL", "2024-01-19")` para verificar

### "run_pipeline.py no encuentra los CSVs"

- Verifica que los archivos estén en:
  `/content/drive/MyDrive/sistema-de-trading/archivos descargables/`
- Verifica que el nombre siga el patrón:
  `{TICKER}_options_trades_*.csv`

---

## ✅ Resultado Esperado

Al final deberías tener:

1. **CSVs de opciones** en Drive
2. **Reporte de expOptions** con features de opciones reales
3. **Reporte de expB** (baseline sin opciones)
4. **Tabla comparativa** mostrando la mejora (o no) de usar opciones

**¡Listo para analizar si las opciones reales mejoran el trading!** 🚀
