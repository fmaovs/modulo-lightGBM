import os
import sys
import numpy as np
import lightgbm as lgb


class MLModel:
    def __init__(self, model_path: str = "app/models/model.txt"):
        self._model = None
        self._model_path = model_path if os.path.exists(model_path) else "model.txt"
        if os.path.exists(self._model_path):
            try:
                self._model = lgb.Booster(model_file=self._model_path)
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
            float(data.get("seniority_days") or 0.0),          # 3
            float(data.get("default_frequency") or 0.0),       # 4
            int(bool(data.get("telefono") or data.get("mobile"))), # 5 - has_telefono
            int(bool(data.get("email"))),                      # 6 - has_email
            float(data.get("broken_promises_count") or data.get("broken_promises") or 0.0),  # 7
        ]
        return np.array(features).reshape(1, -1)

    def predict_proba(self, data: dict) -> float:
        """Return probability in range 0..100 (percentage)
        If model not loaded, return 0.0. No hardcoded heuristics allowed.
        """
        if not self.is_available():
            print("[WARN] ML Model not available. Returning 0.0 as fallback.", file=sys.stderr)
            return 0.0
        
        # Use trained model with all 8 features
        try:
            arr = self._extract_features(data)
            pred = self._model.predict(arr)
            # LightGBM returns probability for binary classification
            p = float(pred[0]) * 100.0
            return max(0.0, min(100.0, p))
        except Exception as e:
            # Fallback on error
            print(f"[WARN] Model prediction error: {e}, using 0.0 fallback", file=sys.stderr)
            return 0.0

    def version(self) -> str:
        return "0.0.0" if not self.is_available() else "model-file"
