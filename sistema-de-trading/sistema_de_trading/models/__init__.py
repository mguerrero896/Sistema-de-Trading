"""Modelos de aprendizaje automático utilizados en el sistema de trading.

Este subpaquete expone la clase :class:`MLPipeline` que encapsula la
construcción, entrenamiento y predicción de varios algoritmos de
machine learning. Al centralizar la lógica de modelado, se facilita el
mantenimiento y la extensión futura con nuevos modelos.
"""

from .ml_pipeline import MLPipeline  # noqa: F401

__all__ = ["MLPipeline"]