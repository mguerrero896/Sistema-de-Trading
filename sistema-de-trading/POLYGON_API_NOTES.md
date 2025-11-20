# Notas sobre la API de Polygon para Options Trades

## Parámetros Correctos Confirmados por Polygon

### 1. Para Obtener Trades de Opciones

✅ **Usar `timestamp_gte` y `timestamp_lte`** (NO `date`):

```python
for tr in client.list_trades(
    option_ticker,
    timestamp_gte="2025-10-22T00:00:00Z",
    timestamp_lte="2025-10-22T23:59:59Z",
    order="asc",
    limit=50000,
):
    price = tr.price
    size = tr.size
```

**Formato de timestamps:**
- UTC timezone con sufijo `Z`
- Formato: `YYYY-MM-DDTHH:MM:SSZ`
- Ejemplo: `2025-10-22T00:00:00Z`

### 2. Issue Conocido: Filtro de Fecha de Expiración

⚠️ **Problema:** `expiration_date_gte` puede devolver contratos con fechas anteriores.

✅ **Solución:** Verificar manualmente la fecha de expiración:

```python
for c in client.list_options_contracts(
    underlying_ticker="AAPL",
    expiration_date="2025-11-21",
    limit=100,
):
    # Verificar que la fecha coincida exactamente
    if c.expiration_date == "2025-11-21":
        ticker = c.ticker
        # Procesar contrato...
```

**Implementado en:** `_list_contract_tickers_for_expiry` (línea 70-72)

### 3. Campos Disponibles en Trade Objects

Según la respuesta oficial de Polygon, estos campos están disponibles:

- `price` - Precio del trade
- `size` - Tamaño (número de contratos)
- `timestamp` - Timestamp del trade (nanosegundos desde epoch)
- `exchange` - Código del exchange
- `conditions` - Condiciones del trade
- `transaction_id` - ID único de transacción
- `tape` - Identificador de tape

**Actualmente usamos:** `price` y `size`

**Potenciales mejoras futuras:**
- Agregar `timestamp` para análisis intradiario
- Usar `exchange` para filtrar por exchange
- Analizar `conditions` para filtrar tipos de trades

### 4. Rate Limits

Con el plan **Options Advanced** de Polygon:
- ✅ Acceso completo al historial
- ⚠️ Considerar paginación para grandes volúmenes
- ℹ️ No hay límite estricto documentado, pero usar `limit` apropiadamente

**Configuración actual:**
- `contracts_limit: int = 100` (máximo de contratos por expiry)
- `trades_limit_per_contract: int = 50000` (máximo de trades por contrato)

### 5. Múltiples Días

⚠️ **No hay endpoint para rangos de fechas múltiples**

Necesitas hacer:
- **Una llamada por día** (enfoque actual)
- O usar rangos de timestamp más amplios y filtrar después

**Implementación actual:**
```python
# Loop por cada día en el rango
current = start_date
while current <= end_date:
    trades = _list_trades_for_contract_on_date(ticker, current)
    # Procesar trades...
    current += timedelta(days=1)
```

## Cambios Implementados en el Código

### Commit: "Fix Polygon API parameters: use timestamp_gte/lte and verify expiration dates"

1. **`_list_trades_for_contract_on_date`:**
   - Cambiado de `date=date_str` a `timestamp_gte` y `timestamp_lte`
   - Formato correcto de timestamps UTC
   - Documentación de campos disponibles

2. **`_list_contract_tickers_for_expiry`:**
   - Agregada verificación manual de `expiration_date`
   - Workaround para issue conocido de la API
   - Solo acepta contratos que coincidan exactamente

## Pregunta Original a Polygon AI

La pregunta que generó esta respuesta fue sobre:
- Forma correcta de obtener contratos y trades
- Parámetros correctos para las llamadas
- Consideraciones de rate limits y paginación
- Campos disponibles en los objetos

## Respuesta de Polygon AI

La IA confirmó que:
1. ✅ Los parámetros `timestamp_gte/lte` son correctos
2. ⚠️ Existe un issue conocido con `expiration_date_gte`
3. ℹ️ Campos disponibles documentados
4. ℹ️ No hay endpoint para múltiples días
5. ✅ Plan Options Advanced tiene acceso completo

**Pregunta adicional de la IA:**
> "¿Has probado con contratos que realmente existían en las fechas que consultas?"

Esto sugiere que debemos:
- Verificar que los contratos existan antes de buscar trades
- Usar fechas realistas (días de trading, no fines de semana)
- Considerar que no todos los subyacentes tienen opciones activas

## Recomendaciones para Uso

### 1. Verificar Existencia de Contratos

Antes de buscar trades masivamente, verifica que hay contratos:

```python
contracts = loader._list_contract_tickers_for_expiry("AAPL", "2025-11-21")
print(f"Contratos encontrados: {len(contracts)}")
```

### 2. Usar Fechas de Trading

Evita fines de semana y festivos:

```python
import pandas as pd
# Usar solo días laborables
trading_days = pd.bdate_range(start_date, end_date)
```

### 3. Manejar Errores Gracefully

El código actual captura excepciones genéricas. Considera:

```python
try:
    for tr in self.client.list_trades(...):
        # Procesar
except Exception as e:
    print(f"Error obteniendo trades para {option_ticker}: {e}")
    # Log o manejar específicamente
```

### 4. Monitorear Volumen de Llamadas

Para 100 contratos × 30 días = 3,000 llamadas:
- Considerar agregar progress bar
- Implementar retry logic para errores transitorios
- Cachear resultados cuando sea posible

## Referencias

- **Documentación oficial:** https://polygon.io/docs/options/getting-started
- **Python SDK:** https://polygon-api-client.readthedocs.io/
- **GitHub del SDK:** https://github.com/polygon-io/client-python
