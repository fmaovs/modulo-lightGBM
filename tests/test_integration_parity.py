import unittest
from app.schemas import PredictInput
from app.scoring.rules_engine import calculate_rules_score, evaluate_rules_with_details
from app.scoring.ml_model import MLModel

class TestIntegrationParity(unittest.TestCase):
    def test_predict_input_schema(self):
        # Verify seniority_days is accepted
        data = {
            "obligacion_id": "TEST001",
            "dias_vencidos": 30,
            "monto_adeudado": 1000.0,
            "seniority_days": 450,
            "default_frequency": 1.0
        }
        payload = PredictInput(**data)
        self.assertEqual(payload.seniority_days, 450)

    def test_rules_engine_no_config(self):
        # No burned data: should return 0 if no config
        data = {"dias_vencidos": 10}
        score = calculate_rules_score(data, config=None)
        self.assertEqual(score, 0)

    def test_ml_model_no_file(self):
        # No burned data: should return 0.0 if no model file
        ml = MLModel(model_path="non_existent.txt")
        prob = ml.predict_proba({"dias_vencidos": 0})
        self.assertEqual(prob, 0.0)

    def test_rules_engine_parity_logic(self):
        # Mock config matching the requested parity logic
        config = {
            "variables": [
                {
                    "variableKey": "SENIORITY",
                    "weight": 1.0,
                    "ranges": [
                        {"minValue": 365, "maxValue": 730, "baseScore": 800}
                    ]
                }
            ]
        }
        data = {"seniority_days": 450}
        eval_res = evaluate_rules_with_details(data, config=config)
        self.assertEqual(eval_res["score"], 800)

        # Check details for parity logging
        detail = eval_res["details"][0]
        self.assertEqual(detail["variable"], "SENIORITY")
        self.assertEqual(detail["value"], 450.0)
        self.assertEqual(detail["baseScore"], 800.0)

if __name__ == "__main__":
    unittest.main()
