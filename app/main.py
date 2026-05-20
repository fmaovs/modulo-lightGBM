from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import io
import sys
import json
import copy
import time

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
last_config_load_at = 0.0
config_refresh_seconds = int(os.getenv("SCORING_CONFIG_REFRESH_SECONDS", "30"))

def _load_config(force: bool = False):
    global active_model, scoring_config, last_config_load_at
    if force:
        backend_client.clear_cache()
    try:
        print("[APP] Cargando configuración del backend...", file=sys.stderr)
        active_model = backend_client.get_active_model()
        print(f"[APP] ✓ Active model: {active_model.get('modelVersion') if active_model else 'None'}", file=sys.stderr)
        
        if active_model:
            version = active_model.get("modelVersion") or active_model.get("version") or str(active_model.get("id") or "default")
            vars_raw = backend_client.get_variables(version)
            thresholds = backend_client.get_thresholds(version)
            segment_rules = backend_client.get_segment_rules()
            
            if vars_raw:
                # Make deep copy to avoid cache mutation issues
                vars_cfg = copy.deepcopy(vars_raw)
                print(f"[APP] ✓ Variables cargadas: {len(vars_cfg)} variables", file=sys.stderr)
                
                for v in vars_cfg:
                    key = v.get("variableKey") or v.get("key") or v.get("name")
                    try:
                        ranges = backend_client.get_variable_ranges(version, key)
                        v["ranges"] = ranges or []
                    except Exception as e:
                        v["ranges"] = []

                scoring_config = {
                    "variables": vars_cfg,
                    "thresholds": thresholds or [],
                    "segment_rules": segment_rules or [],
                    "model_config": active_model
                }
                last_config_load_at = time.time()
                print(f"[APP] ✓ Configuración cargada: {len(vars_cfg)} variables, {len(thresholds or [])} thresholds, {len(segment_rules or [])} segment rules", file=sys.stderr)
    except Exception as e:
        print(f"[APP] ✗ Error cargando configuración: {e}", file=sys.stderr)
        active_model = None
        scoring_config = None


def _refresh_config_if_needed():
    if config_refresh_seconds <= 0:
        return
    if scoring_config is None or (time.time() - last_config_load_at) >= config_refresh_seconds:
        _load_config(force=True)

# Cargar config al iniciar
_load_config()


@app.post("/predict", response_model=PredictOutput)
def predict(payload: PredictInput):
    data = payload.dict()
    print(f"\n[PREDICT] Recibido payload para cliente {data.get('cliente_id')}:", file=sys.stderr)
    print(f"         {json.dumps(data, indent=2)}", file=sys.stderr)
    
    _refresh_config_if_needed()
    # Usar config en cache si está disponible
    cfg = scoring_config
    # Debug: indicate whether config was loaded and model version
    try:
        print(f"[PREDICT] Configuración cargada: {cfg is not None}, Versión: {active_model.get('modelVersion') if active_model else 'N/A'}", file=sys.stderr)
    except Exception:
        print(f"[PREDICT] Configuración cargada: {cfg is not None}", file=sys.stderr)
    # Evaluate rules with details for auditing
    rules_eval = evaluate_rules_with_details(data, config=cfg)
    score_reglas = rules_eval.get("score")

    # ML predictions (prob 0..100)
    prob = ml.predict_proba(data, config=cfg)
    score_ml = int(prob * 10)  # map 0..100 payment probability to 0..1000 quality score

    # Explainability (SHAP)
    explanation = ml.explain(data)

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

    # Debug: engine and scores
    print(f"[PREDICT] Engine Selection: prefer_ml={prefer_ml}, ml_available={ml_available} -> Selected: {engine}", file=sys.stderr)
    print(f"[PREDICT] Results: score_reglas={score_reglas}, score_ml={score_ml} -> score_final={score_final}", file=sys.stderr)

    # 1. Resolve Risk Level using configured thresholds
    risk_level = "MEDIO"
    thresholds = cfg.get("thresholds") if cfg else []
    print(f"[IA-FLOW] Evaluando {len(thresholds)} umbrales para score_final={score_final}", file=sys.stderr)
    for t in thresholds:
        min_s = t.get("minScore", 0)
        max_s = t.get("maxScore", 1000)
        if score_final >= min_s and score_final <= max_s:
            risk_level = t.get("riskLevel", "MEDIO")
            print(f"[IA-FLOW] ✓ Match umbral: {min_s}-{max_s} -> {risk_level}", file=sys.stderr)
            break

    # 2. Resolve Segment using configured segment rules (based on DPD)
    segmento = "ADMINISTRATIVA"
    dias = int(data.get("dias_vencidos") or 0)
    seg_rules = cfg.get("segment_rules") if cfg else []
    print(f"[IA-FLOW] Evaluando {len(seg_rules)} reglas de segmento para dias_vencidos={dias}", file=sys.stderr)
    for s in seg_rules:
        min_d = s.get("minDays") or 0
        max_d = s.get("maxDays") or 99999
        if dias >= min_d and (max_d is None or dias <= max_d):
            segmento = s.get("segment", "ADMINISTRATIVA")
            print(f"[IA-FLOW] ✓ Match segmento: {min_d}-{max_d} -> {segmento}", file=sys.stderr)
            break

    print(f"[IA-FLOW] Resultado Final -> Score: {score_final} | Riesgo: {risk_level} | Segmento: {segmento} | Motor: {engine}", file=sys.stderr)

    # build audit record
    audit = {
        "obligacion_id": data.get("obligacion_id"),
        "engine_used": engine,
        "ml_available": ml_available,
        "model_version": ml.version(),
        "score_reglas": score_reglas,
        "score_ml": score_ml,
        "score_final": score_final,
        "explanation": explanation,
        "rules_details": rules_eval.get("details", []),
    }

    # best-effort: send audit to backend and persist locally
    try:
        backend_client.send_score_audit(audit)
    except Exception:
        pass

    out = PredictOutput(
        obligacion_id=data.get("obligacion_id"),
        score_final=score_final,
        score_reglas=score_reglas,
        score_ml=score_ml,
        probabilidad_pago=prob,
        riesgo_incumplimiento=100 - prob,
        risk_level=risk_level,
        segmento=segmento,
        model_version=ml.version(),
        usando_ml=ml.is_available(),
        recomendacion="Contacto preferente + incentivos" if score_final < 600 else "Mantenimiento",
        audit=audit
    )
    return out


@app.post("/train")
async def train_model(file: UploadFile = File(...)):
    """Endpoint to re-train the model with historical data from the backend."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="CSV file required")

    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    # Required columns for training
    required = ["paid_within_30d"] + ml._feature_names
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail={"missing_columns": missing})

    result = ml.train(df)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@app.post("/feedback")
def post_feedback(payload: Feedback):
    # Persistencia en log para futuro entrenamiento
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
