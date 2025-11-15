"""Definición de parámetros globales y configuración del sistema de trading.

La clase :class:`Config` agrupa todos los parámetros usados a lo largo del
proyecto. Al separarlos en un módulo dedicado, se facilita el ajuste de
hiperparámetros y constantes sin necesidad de modificar el código del
pipeline. Muchos valores provienen directamente del notebook original y se
mantienen en español para preservar la semántica de negocio.

Los atributos ``polygon_api_key`` y ``fmp_api_key`` se leen de variables de
entorno homónimas. Si no están definidos, el sistema intentará funcionar con
listados estáticos y fuentes alternativas como yfinance.
"""

from __future__ import annotations

import os
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class Config:
    """Clase de configuración con todos los parámetros del sistema.

    Los atributos son anotados con tipos para facilitar el autocompletado y
    evitar errores de tipado. Puede instanciarse directamente o bien
    subclasarse para crear variantes del sistema (por ejemplo con distinto
    universo de activos o distinta ventana temporal).
    """

    # Claves API para Polygon.io y Financial Modeling Prep
    polygon_api_key: str = field(default_factory=lambda: os.getenv("POLYGON_API_KEY", ""))
    fmp_api_key: str = field(default_factory=lambda: os.getenv("FMP_API_KEY", ""))

    # Parámetros del universo y limpieza de datos
    precio_min: float = 5.0
    volumen_medio_min: int = 1_000_000
    ventana_volumen: int = 20

    anos_train: int = 7
    anos_val: int = 1
    anos_test: int = 1
    purga_dias: int = 10
    embargo_dias: int = 5

    # Flags de uso de componentes
    usar_opciones: bool = True
    usar_fundamental_overlay: bool = False

    # Parámetros de features
    ventanas_rendimiento: List[int] = field(default_factory=lambda: [5, 20, 60])
    ventana_vol_realizada: int = 20
    ventana_max_min: int = 252

    # Selección de modelos
    modelos: List[str] = field(default_factory=lambda: ["ridge", "gradient_boosting"])
    usar_calibracion_isotonica: bool = True
    neutralizar_por_sector: bool = False

    # Hiperparámetros de los modelos
    ridge_alpha: float = 1.0
    gb_n_estimators: int = 100
    gb_max_depth: int = 4
    gb_learning_rate: float = 0.1
    gb_subsample: float = 0.8

    # Restricciones y gestión de riesgo
    apalancamiento_bruto_max: float = 2.0
    exposicion_neta_target: float = 0.0
    exposicion_neta_tolerancia: float = 0.20
    peso_max_por_accion: float = 0.03
    peso_max_sector: float = 0.30
    peso_max_tech: float = 0.35
    kelly_fraccion: float = 0.30

    # Parámetros de función objetivo (riesgo y costes)
    lambda_riesgo: float = 0.5
    eta_costes: float = 1.0

    # Frecuencia de rebalanceo y bandas de inacción
    rebalanceo_frecuencia: str = "diario"
    banda_inaccion: float = 0.003

    # Control de volatilidad y drawdown
    control_volatilidad_activado: bool = True
    vol_target_anual: float = 0.20

    corte_por_caida_activado: bool = True
    umbral_caida: float = 0.15
    reduccion_exposicion: float = 0.50

    # Costes de transacción y deslizamiento
    comision_bp: float = 1.0
    deslizamiento_spread_mult: float = 0.5
    impacto_k: float = 0.1
    impacto_psi: float = 1.5
    participacion_max: float = 0.075
    tasa_financiacion_anual: float = 0.05

    # Definición de regímenes de mercado para el reporte
    regimenes: Dict[str, Tuple[str, str]] = field(default_factory=lambda: {
        "crisis_2007_2009": ("2007-01-01", "2009-06-30"),
        "bull_ge_2010_2014": ("2010-01-01", "2014-12-31"),
        "late_bull_2015_2019": ("2015-01-01", "2019-12-31"),
        "covid_2020": ("2020-01-01", "2020-12-31"),
        "ajuste_2022": ("2022-01-01", "2022-12-31"),
        "rebote_2023_2025": ("2023-01-01", "2025-10-31"),
    })

    # Overlays para valoración y calidad
    overlay_valoracion: Dict[str, float] = field(default_factory=lambda: {
        "caro_percentil": 95,
        "caro_mult": 0.85,
        "barato_percentil": 5,
        "barato_mult": 1.10,
    })
    overlay_calidad: Dict[str, float] = field(default_factory=lambda: {
        "peor_dec1_mult": 0.90,
        "mejor_dec1_mult": 1.05,
    })
    overlay_rango: Tuple[float, float] = (0.7, 1.3)

    # Semilla de aleatoriedad
    random_seed: int = 42

    # Directorios
    base_dir: Path = field(default_factory=lambda: Path(".").resolve())
    runs_dir: Path = field(default_factory=lambda: Path("./runs").resolve())

    # Fechas de inicio y fin del histórico (se pueden ajustar según necesidad)
    fecha_inicio: str = "2005-01-01"
    fecha_fin: str = field(default_factory=lambda: datetime.date.today().strftime("%Y-%m-%d"))

    # Horizontes para etiquetas principales y comparativas
    k_principal: int = 5
    k_comparativo: int = 20

    def to_dict(self) -> Dict[str, object]:
        """Devuelve un diccionario plano con los parámetros públicos.

        Se excluyen atributos privados (que comienzan con ``_``) y métodos. Este
        método es útil para incluir la configuración completa en reportes o
        auditorías.
        """
        return {
            k: v
            for k, v in self.__dict__.items()
            if not k.startswith("_") and not callable(v)
        }
