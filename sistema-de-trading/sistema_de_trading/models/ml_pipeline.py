"""Pipeline de modelos de machine learning para predicción de retornos.

Este módulo define la clase :class:`MLPipeline`, encargada de entrenar
distintos modelos de regresión sobre las características generadas por
``FeatureEngineer`` y producir predicciones calibradas que sirven de
entrada al optimizador de cartera. La implementación se inspira en el
notebook original, empleando Ridge Regression y Gradient Boosting
Regressor, con opcional calibración isotónica de las salidas para
corregir sesgos de escala en los retornos esperados.

La clase también ofrece métodos de evaluación y extracción de
importancias de características para propósitos de análisis.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import mean_squared_error, r2_score

from ..config import Config


class MLPipeline:
    """Gestor de modelos de regresión para la predicción de retornos.

    Este pipeline admite múltiples modelos definidos en ``Config.modelos``.
    Soporta entrenamiento, evaluación, predicción y calibración
    isotónica de las salidas. También ofrece un método de neutralización
    sectorial que elimina la media de las predicciones por sector en
    cada fecha, reduciendo así la exposición sistemática a sectores.

    Parámetros
    ----------
    config : Config
        Instancia de configuración con hiperparámetros y opciones.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.models: Dict[str, object] = {}
        self.calibrators: Dict[str, IsotonicRegression] = {}

    # ------------------------------------------------------------------
    # Utilidad interna: limpieza de datos
    # ------------------------------------------------------------------
    def _clean_df(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        label_col: str,
    ) -> pd.DataFrame:
        """Devuelve un DataFrame sin NaN/inf en features ni en la etiqueta."""
        cols = list(feature_cols) + [label_col]
        df_clean = (
            df[cols]
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=cols)
        )
        return df_clean

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------
    def fit(
        self,
        df_train: pd.DataFrame,
        df_val: Optional[pd.DataFrame],
        feature_cols: List[str],
        label_col: str,
    ) -> None:
        """Entrena los modelos definidos en la configuración.

        Se inicializan y ajustan las instancias de los modelos sobre los datos
        de entrenamiento. Si se proporciona un conjunto de validación y la
        opción ``config.usar_calibracion_isotonica`` está activada, se entrena
        un modelo de regresión isotónica para ajustar la escala de las
        predicciones a los retornos observados en validación.
        """
        # Reiniciar modelos y calibradores por si se reentrena
        self.models = {}
        self.calibrators = {}

        # --- limpiar y preparar TRAIN ---
        df_train_clean = self._clean_df(df_train, feature_cols, label_col)
        if df_train_clean.empty:
            raise ValueError(
                "Después de limpiar NaN/inf no quedan filas de entrenamiento. "
                "Revisa las ventanas de features o la calidad de los datos."
            )
        X_train = df_train_clean[feature_cols].values
        y_train = df_train_clean[label_col].values

        # --- limpiar y preparar VALIDACIÓN (opcional) ---
        has_val = df_val is not None and len(df_val) > 0
        if has_val:
            df_val_clean = self._clean_df(df_val, feature_cols, label_col)
            if df_val_clean.empty:
                has_val = False  # no hay datos útiles de validación
            else:
                X_val = df_val_clean[feature_cols].values
                y_val = df_val_clean[label_col].values

        # Entrenar Ridge Regression
        if "ridge" in self.config.modelos:
            ridge = Ridge(alpha=self.config.ridge_alpha)
            ridge.fit(X_train, y_train)
            self.models["ridge"] = ridge

            # Calibración isotónica opcional
            if self.config.usar_calibracion_isotonica and has_val:
                preds = ridge.predict(X_val)
                # Evitar problemas numéricos: ordenar
                order = np.argsort(preds)
                preds_sorted = preds[order]
                y_sorted = y_val[order]
                isotonic = IsotonicRegression(out_of_bounds="clip")
                isotonic.fit(preds_sorted, y_sorted)
                self.calibrators["ridge"] = isotonic

        # Entrenar Gradient Boosting Regressor
        if "gradient_boosting" in self.config.modelos:
            gbr = GradientBoostingRegressor(
                n_estimators=self.config.gb_n_estimators,
                max_depth=self.config.gb_max_depth,
                learning_rate=self.config.gb_learning_rate,
                subsample=self.config.gb_subsample,
                random_state=self.config.random_seed,
            )
            gbr.fit(X_train, y_train)
            self.models["gradient_boosting"] = gbr

            if self.config.usar_calibracion_isotonica and has_val:
                preds = gbr.predict(X_val)
                order = np.argsort(preds)
                preds_sorted = preds[order]
                y_sorted = y_val[order]
                isotonic = IsotonicRegression(out_of_bounds="clip")
                isotonic.fit(preds_sorted, y_sorted)
                self.calibrators["gradient_boosting"] = isotonic

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------
    def predict(self, df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """Calcula predicciones de retorno para los modelos entrenados.

        Devuelve un DataFrame con las mismas filas que ``df`` y columnas
        ``pred_<modelo>`` para cada modelo entrenado. Si existe un
        calibrador isotónico para un modelo, se aplica al vector de
        predicciones antes de devolverlo.
        """
        result = df.copy()

        # Rellenar NaN/inf en features para no romper en predicción
        X_feats = (
            df[feature_cols]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
        X = X_feats.values

        for name, model in self.models.items():
            preds = model.predict(X)
            # Aplicar calibración isotónica si está disponible
            if name in self.calibrators:
                calibrator = self.calibrators[name]
                preds = calibrator.predict(preds)
            result[f"pred_{name}"] = preds
        return result

    # ------------------------------------------------------------------
    # Evaluación
    # ------------------------------------------------------------------
    def evaluate(
        self, df: pd.DataFrame, feature_cols: List[str], label_col: str
    ) -> Dict[str, Dict[str, float]]:
        """Evalúa cada modelo sobre un conjunto de datos.

        Se calcula el error cuadrático medio (MSE) y el coeficiente de
        determinación :math:`R^2` para cada modelo entrenado.
        """
        metrics: Dict[str, Dict[str, float]] = {}

        # Limpiar conjunto de evaluación
        cols = list(feature_cols) + [label_col]
        df_eval = (
            df[cols]
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=cols)
        )
        if df_eval.empty:
            return metrics  # nada que evaluar

        X = df_eval[feature_cols].values
        y_true = df_eval[label_col].values

        for name, model in self.models.items():
            preds = model.predict(X)
            if name in self.calibrators:
                preds = self.calibrators[name].predict(preds)
            mse = mean_squared_error(y_true, preds)
            r2 = r2_score(y_true, preds)
            metrics[name] = {"mse": mse, "r2": r2}
        return metrics

    # ------------------------------------------------------------------
    # Importancias de características
    # ------------------------------------------------------------------
    def get_feature_importance(self, model_name: str, feature_cols: List[str]) -> pd.Series:
        """Extrae importancias de características para el modelo especificado.

        Actualmente se soportan importancias del modelo de Gradient Boosting.
        Para modelos lineales como Ridge se devuelven los coeficientes.
        """
        if model_name not in self.models:
            raise ValueError(f"El modelo {model_name} no está entrenado.")
        model = self.models[model_name]
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = model.coef_
        else:
            raise ValueError(f"El modelo {model_name} no admite importancias.")
        return pd.Series(importances, index=feature_cols)

    # ------------------------------------------------------------------
    # Neutralización por sector
    # ------------------------------------------------------------------
    def neutralize_by_sector(self, df: pd.DataFrame, pred_col: str, sector_col: str) -> pd.DataFrame:
        """Neutraliza las predicciones eliminando la media por sector en cada fecha.

        Esta función es útil cuando se desea reducir la exposición relativa
        a determinados sectores, evitando que las señales de trading estén
        sesgadas por comportamientos sectoriales. Dada una columna de
        predicciones y otra de sector, sustrae la media de predicciones
        dentro de cada sector y fecha.
        """
        out = df.copy()
        if "date" not in out.columns:
            raise ValueError("Se requiere una columna 'date' para neutralizar por sector.")

        for d in out["date"].unique():
            mask_date = out["date"] == d
            # Calcular la media por sector dentro de la fecha
            sector_means = out.loc[mask_date].groupby(sector_col)[pred_col].mean()
            # Sustraer la media del sector
            adj = out.loc[mask_date, sector_col].map(sector_means)
            out.loc[mask_date, pred_col] = out.loc[mask_date, pred_col] - adj
        return out
