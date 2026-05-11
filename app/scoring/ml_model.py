import os
import numpy as np
import lightgbm as lgb


class MLModel:
    def __init__(self, model_path: str = "model.txt"):
        self._model = None
        self._model_path = model_path
        if os.path.exists(model_path):
            try:
                self._model = lgb.Booster(model_file=model_path)
            except Exception:
                self._model = None

    def is_available(self) -> bool:
        return self._model is not None

    def _extract_features(self, data: dict) -> np.ndarray:
        """
        Extract 8 features in exact order that model was trained with.
        Features must match scripts/generate_synthetic_data.py and train.py exactly.
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

    def predict_proba(self, data: dict) -> float:
        """Return probability in range 0..100 (percentage)
        If model not loaded, return heuristic fallback based on days past due.
        """
        if not self.is_available():
            # Fallback to simple heuristic (only uses dias_vencidos)
            dias = int(data.get("dias_vencidos") or 0)
            if dias <= 0:
                return 95.0
            if dias <= 30:
                return 75.0
            if dias <= 90:
                return 45.0
            if dias <= 180:
                return 20.0
            return 5.0
        
        # Use trained model with all 8 features
        try:
            arr = self._extract_features(data)
            pred = self._model.predict(arr)
            # LightGBM returns probability for binary classification
            p = float(pred[0]) * 100.0
            return max(0.0, min(100.0, p))
        except Exception as e:
            # Fallback on error
            print(f"[WARN] Model prediction error: {e}, using fallback")
            return self.predict_proba_fallback(data)
    
    def predict_proba_fallback(self, data: dict) -> float:
        """Heuristic fallback if model fails."""
        dias = int(data.get("dias_vencidos") or 0)
        if dias <= 0:
            return 95.0
        if dias <= 30:
            return 75.0
        if dias <= 90:
            return 45.0
        if dias <= 180:
            return 20.0
        return 5.0

    def version(self) -> str:
        return "0.0.0" if not self.is_available() else "model-file"

