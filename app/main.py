from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import io
import sys
import json
import copy

from app.schemas import PredictInput, PredictOutput, Feedback
from app.scoring.rules_engine import calculate_rules_score
from app.scoring.ml_model import MLModel
from app.integrations.backend_client import BackendClient
import os

app = FastAPI(title="Microservicio Scoring IA")

# initialize ML model (will fallback gracefully if no model file)
ml = MLModel()

# initialize backend client and fetch active model config if possible
backend_client = BackendClient(base_url=os.getenv("BACKEND_URL"))
active_model = None
scoring_config = None

def _load_config():
    global active_model, scoring_config
    try:
        print("[APP] Cargando configuración del backend...", file=sys.stderr)
        active_model = backend_client.get_active_model()
        print(f"[APP] ✓ Active model: {active_model.get('modelVersion') if active_model else 'None'}", file=sys.stderr)
        
        if active_model:
            version = active_model.get("modelVersion") or active_model.get("version") or str(active_model.get("id") or "default")
            vars_raw = backend_client.get_variables(version)
            
            if vars_raw:
                # Make deep copy to avoid cache mutation issues
                vars_cfg = copy.deepcopy(vars_raw)
                print(f"[APP] ✓ Variables cargadas: {len(vars_cfg)} variables", file=sys.stderr)
                
                for v in vars_cfg:
                    key = v.get("variableKey") or v.get("key") or v.get("name")
                    try:
                        ranges = backend_client.get_variable_ranges(version, key)
                        v["ranges"] = ranges or []
                        print(f"[APP]   - {key}: {len(ranges or [])} ranges", file=sys.stderr)
                    except Exception as e:
                        print(f"[APP]   - {key}: error cargando ranges: {e}", file=sys.stderr)
                        v["ranges"] = []
                scoring_config = {"variables": vars_cfg}
                print(f"[APP] ✓ Configuración cargada: {len(vars_cfg)} variables con ranges", file=sys.stderr)
    except Exception as e:
        print(f"[APP] ✗ Error cargando configuración: {e}", file=sys.stderr)
        active_model = None
        scoring_config = None

# Cargar config al iniciar
_load_config()


@app.post("/predict", response_model=PredictOutput)
def predict(payload: PredictInput):
    data = payload.dict()
    # Usar config en cache si está disponible
    cfg = scoring_config
    print(f"[PREDICT] cfg={cfg is not None}, vars={len(cfg.get('variables',[])) if cfg else 0}", file=sys.stderr)
    
    # Backend returns RISK scores (higher = more risk), we invert to QUALITY scores (higher = better client)
    risk_score_rules = calculate_rules_score(data, config=cfg)
    score_reglas = 1000 - risk_score_rules
    
    # ml - always inverted since ML returns probability (0-100) which we transform to risk and then invert
    prob = ml.predict_proba(data)
    risk_score_ml = int(prob * 10)  # map 0..100 probability to 0..1000 risk
    score_ml = 1000 - risk_score_ml  # invert to quality score

    # híbrido: configurable por ahora pesos por defecto
    w_rules = 0.5
    w_ml = 0.5 if ml.is_available() else 0.0
    score_final = int((score_reglas * w_rules + score_ml * w_ml) / (w_rules + w_ml if (w_rules + w_ml) > 0 else 1))

    segmento = "BRONCE"
    if score_final >= 800:
        segmento = "PLATINO"
    elif score_final >= 650:
        segmento = "ORO"
    elif score_final >= 500:
        segmento = "PLATA"
    elif score_final >= 300:
        segmento = "BRONCE"
    else:
        segmento = "RECOVERY"

    out = PredictOutput(
        obligacion_id=data.get("obligacion_id"),
        score_final=score_final,
        score_reglas=score_reglas,
        score_ml=score_ml,
        probabilidad_pago=prob,
        riesgo_incumplimiento=100 - prob,
        segmento=segmento,
        model_version=ml.version(),
        usando_ml=ml.is_available(),
        recomendacion="Contacto preferente + incentivos" if score_final < 600 else "Mantenimiento"
    )
    return out


@app.post("/batch/upload")
async def upload_batch(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Se requiere un CSV")
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    # simple validación básica
    required = ["obligacion_id", "dias_vencidos", "monto_adeudado"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail={"missing_columns": missing})
    # procesar filas y calcular scores (streaming sería ideal)
    results = []
    for _, row in df.iterrows():
        payload = PredictInput(**row.fillna(0).to_dict())
        out = predict(payload)
        results.append(out.dict())
    return JSONResponse({"processed": len(results), "results_sample": results[:3]})


@app.post("/feedback")
def post_feedback(payload: Feedback):
    # por ahora persistencia simple: log to console (integrar BD luego)
    print("FEEDBACK RECEIVED:", payload.dict())
    return {"status": "ok"}


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "backend_connected": active_model is not None,
        "scoring_config_loaded": scoring_config is not None
    }
