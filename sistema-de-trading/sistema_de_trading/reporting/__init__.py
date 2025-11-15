"""Subpaquete de generación de reportes.

El reporte se exporta principalmente a formato Excel mediante la
clase :class:`ExcelReporter`, que combina métricas, curvas de equity,
transacciones y cualquier otra información relevante en hojas de
cálculo separadas. Esta clase puede personalizarse para añadir
gráficos y tablas adicionales según las necesidades.
"""

from .excel_reporter import ExcelReporter  # noqa: F401

__all__ = ["ExcelReporter"]