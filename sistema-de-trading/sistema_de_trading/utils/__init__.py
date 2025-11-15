"""Funciones auxiliares y métricas para el sistema de trading.

Este subpaquete contiene utilidades generales que se utilizan en
distintas partes del pipeline, como cálculo de métricas de rendimiento,
funciones de manipulación de datos y cualquier otro helper que no esté
ligado a un módulo concreto.
"""

from .helpers import compute_performance_metrics  # noqa: F401

__all__ = ["compute_performance_metrics"]