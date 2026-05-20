import os
import sys
import numpy as np
import lightgbm as lgb
import pandas as pd
import shap
from sklearn.model_selection import train_test_split
from datetime import datetime


class MLModel:
    def __init__(self, model_path: str = "app/models/model.txt"):
        self._model = None
        self._explainer = None
        self._model_path = model_path if os.path.exists(model_path) else "model.txt"
        self._feature_names = [
            "dias_vencidos",
            "monto_adeudado",
            "pct_pagos_on_time",
            "seniority_months",
            "default_frequency",
            "has_telefono",
            "has_email",
            "broken_promises_count",
        ]
        self._load_model()

    def _load_model(self):
        if os.path.exists(self._model_path):
            try:
                self._model = lgb.Booster(model_file=self._model_path)
                # Initialize SHAP explainer
                self._explainer = shap.TreeExplainer(self._model)
            except Exception as e:
                print(f"[MLModel] Error loading model: {e}")
                self._model = None

    def is_available(self) -> bool:
        return self._model is not None

    def _extract_features(self, data: dict) -> np.ndarray:
        """
        Extract 8 features in exact order that model was trained with.
        """
        features = [
            float(data.get("dias_vencidos") or 0.0),           # 0
            float(data.get("monto_adeudado") or 0.0),          # 1
            float(data.get("pct_pagos_on_time") or 0.5),       # 2
            float(data.get("seniority_months") or 0.0),        # 3
            float(data.get("default_frequency") or 0.5),       # 4
            int(bool(data.get("telefono") or data.get("mobile"))), # 5 - has_telefono
            int(bool(data.get("email"))),                      # 6 - has_email
            float(data.get("broken_promises_count") or data.get("broken_promises") or 0.0),  # 7
        ]
        return np.array(features).reshape(1, -1)

    def predict_proba(self, data: dict, config: dict = None) -> float:
        """Return probability in range 0..100 (percentage)"""
        if not self.is_available():
            return self.predict_proba_fallback(data, config)
        
        try:
            arr = self._extract_features(data)
            pred = self._model.predict(arr)
            p = float(pred[0]) * 100.0
            print(f"[IA-FLOW] ML Prediction -> Probabilidad Pago: {p:.2f}%", file=sys.stderr)
            return max(0.0, min(100.0, p))
        except Exception as e:
            print(f"[WARN] Model prediction error: {e}, using fallback", file=sys.stderr)
            return self.predict_proba_fallback(data, config)
    
    def explain(self, data: dict) -> dict:
        """Calculate SHAP values for a single prediction."""
        if not self.is_available() or self._explainer is None:
            return {}

        try:
            arr = self._extract_features(data)
            shap_values = self._explainer.shap_values(arr)

            # For binary classification, shap_values might be a list of arrays (one per class)
            # or just one array if it's a single output model.
            if isinstance(shap_values, list):
                vals = shap_values[1][0]  # take class 1 (paid)
            else:
                vals = shap_values[0]

            return {
                name: float(val)
                for name, val in zip(self._feature_names, vals)
            }
        except Exception as e:
            print(f"[WARN] SHAP explanation error: {e}")
            return {}

    def train(self, df: pd.DataFrame) -> dict:
        """Train model with provided DataFrame and update production model."""
        try:
            # Prepare data
            X = df[self._feature_names].fillna(0)
            y = df["paid_within_30d"] # Target name must match backend export

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            dtrain = lgb.Dataset(X_train, label=y_train)
            dval = lgb.Dataset(X_test, label=y_test, reference=dtrain)

            params = {
                "objective": "binary",
                "metric": "auc",
                "verbosity": -1,
                "seed": 42
            }

            bst = lgb.train(
                params,
                dtrain,
                valid_sets=[dval],
                num_boost_round=100,
                callbacks=[lgb.early_stopping(stopping_rounds=10)]
            )

            # Save and Reload
            bst.save_model(self._model_path)
            self._load_model()

            return {
                "status": "success",
                "trees": bst.num_trees(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def predict_proba_fallback(self, data: dict, config: dict = None) -> float:
        """Heuristic fallback if model fails, optionally guided by backend config."""
        dias = int(data.get("dias_vencidos") or 0)

        if config and "variables" in config:
            # Try to find DAYS_PAST_DUE and use its ranges
            for var in config["variables"]:
                if var.get("variableKey") == "DAYS_PAST_DUE":
                    ranges = var.get("ranges") or []
                    for r in ranges:
                        if dias >= float(r.get("minValue", 0)) and dias <= float(r.get("maxValue", 99999)):
                            base = float(r.get("baseScore", 500))
                            return base / 10.0  # Map 0..1000 to 0..100

        # Original hardcoded fallback
        if dias <= 0: return 95.0
        if dias <= 30: return 75.0
        if dias <= 90: return 45.0
        if dias <= 180: return 20.0
        return 5.0

    def version(self) -> str:
        return "0.0.0" if not self.is_available() else "model-file"
