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
from app.scoring.rules_engine import calculate_rules_score, evaluate_rules_with_details
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
    
    # Evaluate rules with details for auditing
    rules_eval = evaluate_rules_with_details(data, config=cfg)
    risk_score_rules = rules_eval.get("score")
    score_reglas = 1000 - risk_score_rules

    # ML predictions (prob 0..100)
    prob = ml.predict_proba(data)
    risk_score_ml = int(prob * 10)  # map 0..100 probability to 0..1000 risk
    score_ml = 1000 - risk_score_ml  # invert to quality score

    # Decide which engine to use based on backend preference and availability
    prefer_ml = data.get("prefer_ml")
    ml_available = ml.is_available()

    if prefer_ml is True:
        if ml_available:
            engine = "ML"
            score_final = score_ml
        else:
            engine = "RULES_FALLBACK_TO_RULES_WHEN_ML_MISSING"
            score_final = score_reglas
    elif prefer_ml is False:
        engine = "RULES_FORCED_BY_BACKEND"
        score_final = score_reglas
    else:
        # default: use ML if available else rules
        if ml_available:
            engine = "ML"
            score_final = score_ml
        else:
            engine = "RULES"
            score_final = score_reglas

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

    # build audit record
    audit = {
        "obligacion_id": data.get("obligacion_id"),
        "engine_used": engine,
        "ml_available": ml_available,
        "model_version": ml.version(),
        "score_reglas": score_reglas,
        "score_ml": score_ml,
        "score_final": score_final,
        "rules_details": rules_eval.get("details", []),
    }

    # best-effort: send audit to backend and persist locally
    try:
        backend_client.send_score_audit(audit)
    except Exception:
        pass
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/score_audit.log", "a") as f:
            f.write(json.dumps(audit) + "\n")
    except Exception:
        pass

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
        , audit={"engine_used": engine, "model_version": ml.version()}
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
    # Return full results so callers can query by obligacion_id client-side
    return JSONResponse({"processed": len(results), "results": results, "results_sample": results[:3]})


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
