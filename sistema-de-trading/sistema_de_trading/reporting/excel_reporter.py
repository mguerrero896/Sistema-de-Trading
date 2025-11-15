"""Generación de reportes en Excel para el sistema de trading.

Este módulo implementa :class:`ExcelReporter`, responsable de
compilar datos y métricas en distintas hojas de un archivo Excel. El
objetivo es que, tras finalizar el pipeline, el usuario obtenga un
documento profesional con un resumen de resultados, curvas de equity,
histórico de transacciones y cualquier otra tabla relevante.

La implementación utiliza :mod:`pandas` y la librería ``openpyxl``
para escribir los archivos. Si se necesita compatibilidad con otros
formatos, se puede extender esta clase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from ..config import Config


class ExcelReporter:
    """Crea reportes en formato Excel a partir de los resultados del pipeline.

    Parámetros
    ----------
    config : Config
        Configuración usada para obtener parámetros adicionales si fuera
        necesario (por ejemplo, nombres de regímenes de mercado).
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def generate(
        self,
        output_path: Path,
        metrics: Dict[str, float],
        full_results: Dict[str, object],
        df_equity: pd.DataFrame,
        df_trades: pd.DataFrame,
        feature_importance: Optional[Dict[str, pd.Series]] = None,
    ) -> None:
        """Genera un archivo Excel con las métricas y tablas proporcionadas.

        El archivo contendrá al menos tres hojas:

        - ``Resumen``: resumen de métricas principales.
        - ``Equity``: curva de equity a lo largo del tiempo.
        - ``Trades``: registro de transacciones ejecutadas.
        - ``FeatureImportance``: importancias de características por modelo (si se suministra).

        Parámetros
        ----------
        output_path : Path
            Ruta del archivo Excel a crear.
        metrics : dict
            Métricas globales del backtest (retorno total, volatilidad, Sharpe, drawdown, etc.).
        full_results : dict
            Diccionario con resultados completos; puede incluir
            predicciones, pesos, etc. Por defecto se ignora, pero se
            reserva para extensiones.
        df_equity : DataFrame
            DataFrame con columnas ``date`` y ``equity``.
        df_trades : DataFrame
            DataFrame con registros de transacciones.
        feature_importance : dict, opcional
            Diccionario de importancias de características por modelo.
        """
        # Crear DataFrame de métricas resumen
        summary = pd.DataFrame(list(metrics.items()), columns=["metric", "value"])
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Resumen", index=False)
            df_equity.to_excel(writer, sheet_name="Equity", index=False)
            df_trades.to_excel(writer, sheet_name="Trades", index=False)
            # Si hay importancias de características
            if feature_importance:
                # Combinar en una sola hoja con columna de modelo
                rows = []
                for model_name, fi in feature_importance.items():
                    tmp = fi.reset_index()
                    tmp.columns = ["feature", "importance"]
                    tmp["model"] = model_name
                    rows.append(tmp)
                df_fi = pd.concat(rows, ignore_index=True)
                df_fi.to_excel(writer, sheet_name="FeatureImportance", index=False)