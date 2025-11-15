"""Paquete raíz del sistema de trading.

Este paquete expone módulos para descarga de datos, ingeniería de variables,
entrenamiento de modelos, optimización de portafolio, backtesting y reporting.

Consulte los submódulos individuales para una documentación detallada.
"""

from .config import Config  # noqa: F401
from .data.data_loader import DataLoader  # noqa: F401
from .features.feature_engineer import FeatureEngineer  # noqa: F401
from .models.ml_pipeline import MLPipeline  # noqa: F401
from .optimization.portfolio_optimizer import PortfolioOptimizer  # noqa: F401
from .backtesting.event_backtester import EventDrivenBacktester  # noqa: F401
from .reporting.excel_reporter import ExcelReporter  # noqa: F401