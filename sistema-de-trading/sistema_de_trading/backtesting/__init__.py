"""Subpaquete de backtesting para la simulación de carteras.

La clase :class:`EventDrivenBacktester` proporciona un framework
sencillo de simulación diaria que ejecuta órdenes de compra y venta
basadas en pesos objetivo y datos de precios, incluyendo costes de
transacción, deslizamiento y control de riesgo. Este diseño modular
permite sustituir o extender la lógica de backtesting según las
necesidades del usuario.
"""

from .event_backtester import EventDrivenBacktester  # noqa: F401

__all__ = ["EventDrivenBacktester"]