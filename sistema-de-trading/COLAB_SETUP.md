# Google Colab Setup - Sistema de Trading (expOptions)

## Instalación Rápida en Google Colab

Copia y pega este código en una celda de Colab:

```python
# 1. Clonar el repositorio
%cd /content
!rm -rf Sistema-de-Trading
!git clone -b expOptions https://github.com/mguerrero896/Sistema-de-Trading.git
%cd Sistema-de-Trading/sistema-de-trading

# 2. Instalar dependencias
!pip install -q -r requirements.txt

# 3. Configurar path de Python
import sys
sys.path.insert(0, '/content/Sistema-de-Trading/sistema-de-trading')

# 4. Importar módulos
from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)

print("✅ Setup completo!")
```

## Configurar API Key de Polygon

### Opción 1: Usar Colab Secrets (Recomendado)

1. Haz clic en el ícono de llave 🔑 en la barra lateral izquierda
2. Haz clic en "Add new secret"
3. Nombre: `POLYGON_API_KEY`
4. Valor: Tu API key de Polygon.io
5. Activa el acceso para este notebook

Luego en tu código:

```python
from google.colab import userdata
api_key = userdata.get('POLYGON_API_KEY')
```

### Opción 2: Variable de Entorno

```python
import os
os.environ['POLYGON_API_KEY'] = 'tu_api_key_aqui'
```

## Uso Básico

```python
# Crear configuración
cfg = OptionsTradesConfig(
    days_before_expiry=30,
    days_after_expiry=0,
    contracts_limit=100,
    trades_limit_per_contract=50000,
    min_trades_per_day=1,
)

# Crear loader
from google.colab import userdata
api_key = userdata.get('POLYGON_API_KEY')
loader = OptionsTradesLoader(cfg, api_key=api_key)

# Obtener datos de opciones
df = loader.build_daily_features_for_underlying_and_expiry(
    underlying='AAPL',
    expiry='2025-11-21',
)

# Ver resultados
print(f"Shape: {df.shape}")
print(df.head())
```

## Script Completo de Una Celda

```python
# SETUP COMPLETO - Copia todo esto en una celda de Colab
%cd /content
!rm -rf Sistema-de-Trading
!git clone -b expOptions https://github.com/mguerrero896/Sistema-de-Trading.git
%cd Sistema-de-Trading/sistema-de-trading
!pip install -q -r requirements.txt

import sys
sys.path.insert(0, '/content/Sistema-de-Trading/sistema-de-trading')

from sistema_de_trading.data.options_trades_loader import (
    OptionsTradesLoader,
    OptionsTradesConfig
)
from google.colab import userdata

# Configuración
cfg = OptionsTradesConfig(
    days_before_expiry=30,
    days_after_expiry=0,
    contracts_limit=100,
    trades_limit_per_contract=50000,
    min_trades_per_day=1,
)

# Crear loader
api_key = userdata.get('POLYGON_API_KEY')
loader = OptionsTradesLoader(cfg, api_key=api_key)

print("✅ Todo listo! Ahora puedes usar el loader:")
print("df = loader.build_daily_features_for_underlying_and_expiry('AAPL', '2025-11-21')")
```

## Solución de Problemas

### Error: "No module named 'polygon'"

**Solución:** Asegúrate de ejecutar `!pip install -r requirements.txt`

### Error: "No se proporcionó api_key..."

**Solución:** Configura tu API key en Colab Secrets o pásala directamente:
```python
loader = OptionsTradesLoader(cfg, api_key='TU_API_KEY')
```

### Error: "ModuleNotFoundError: No module named 'sistema_de_trading'"

**Solución:** Verifica que agregaste el path correctamente:
```python
import sys
sys.path.insert(0, '/content/Sistema-de-Trading/sistema-de-trading')
```

## Dependencias Incluidas

El archivo `requirements.txt` incluye:
- pandas
- numpy
- scikit-learn
- polygon-api-client
- openpyxl
- cvxpy
- yfinance
- matplotlib
- requests
- typing_extensions

Todas se instalan automáticamente con `pip install -r requirements.txt`.
