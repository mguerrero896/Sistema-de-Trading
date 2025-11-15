"""Módulos de optimización de cartera.

Este subpaquete agrupa utilidades relacionadas con el cálculo de
covarianzas y la optimización de pesos de la cartera bajo diversas
restricciones de apalancamiento, exposición neta y límites por acción y
sector. La clase principal :class:`PortfolioOptimizer` ofrece una
interfaz sencilla para construir matrices de covarianza y resolver
problemas de asignación óptima usando cvxpy.
"""

from .portfolio_optimizer import PortfolioOptimizer  # noqa: F401

__all__ = ["PortfolioOptimizer"]