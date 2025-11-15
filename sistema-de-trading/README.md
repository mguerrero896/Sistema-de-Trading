# Sistema de Trading

Este proyecto implementa un sistema cuantitativo de selección y gestión de un portafolio de acciones basado en métricas de valoración, microestructura y modelos de machine learning. El objetivo es proporcionar una arquitectura modular que permita descargar datos, construir features, entrenar modelos, optimizar posiciones, backtestear estrategias y generar reportes de forma reproducible.

El código se ha reestructurado desde un notebook de Colab en una serie de módulos organizados en carpetas. Cada módulo concentra una responsabilidad clara (descarga de datos, ingeniería de características, modelos, optimización de portafolio, backtesting y reporting) y puede ser utilizado de manera independiente o integrada en un flujo completo.

## Estructura del proyecto

```
sistema-de-trading/
├── README.md                     # Documentación general del proyecto
├── requirements.txt              # Lista de dependencias de Python
├── sistema_de_trading/           # Módulo principal con todo el código
│   ├── __init__.py
│   ├── config.py                 # Definición de parámetros y constantes del sistema
│   ├── data/
│   │   ├── __init__.py
│   │   └── data_loader.py        # Descarga y filtro de datos de precios y fundamentales
│   ├── features/
│   │   ├── __init__.py
│   │   └── feature_engineer.py   # Construcción de variables explicativas y etiquetas
│   ├── models/
│   │   ├── __init__.py
│   │   └── ml_pipeline.py        # Entrenamiento y uso de modelos de ML (Ridge, Gradient Boosting)
│   ├── optimization/
│   │   ├── __init__.py
│   │   └── portfolio_optimizer.py # Optimización de pesos del portafolio vía programación convexa
│   ├── backtesting/
│   │   ├── __init__.py
│   │   └── event_backtester.py   # Simulación discreta del portafolio y cálculo de métricas
│   ├── reporting/
│   │   ├── __init__.py
│   │   └── excel_reporter.py      # Generación de reportes y tablas en Excel
│   └── utils/
│       ├── __init__.py
│       └── helpers.py            # Funciones auxiliares (placeholder)
└── tests/
    └── test_basic.py             # Pruebas unitarias básicas
```

## Uso básico

1. Instalar las dependencias:

```bash
pip install -r requirements.txt
```

2. Definir variables de entorno `POLYGON_API_KEY` y `FMP_API_KEY` con sus claves de acceso. Estos valores se utilizan para descargar datos de precios y fundamentales; si no están definidos, se usará un listado estático de tickers y la descarga de datos vía `yfinance`.

3. Ejecutar un pipeline de ejemplo. En la raíz del proyecto hay un script de ejemplo (`run_pipeline.py`) que muestra cómo ensamblar todos los módulos:

```bash
python run_pipeline.py
```

Este script descarga los datos, construye características, entrena los modelos, genera señales, optimiza el portafolio, realiza el backtest y guarda un reporte en un archivo Excel dentro del directorio `runs/`.

## Documentación

Cada módulo contiene documentación mínima al inicio del archivo y comentarios en los métodos principales. Los nombres de variables y funciones se han mantenido en español para preservar la semántica original del notebook de Colab. Consulte el código fuente para más detalles sobre la implementación de cada componente.
