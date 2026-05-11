# Microservicio IA - Scoring (FastAPI)

**Status**: ✅ **OPERACIONAL EN PRODUCCIÓN**

Este repositorio contiene un microservicio en Python (FastAPI) que implementa un motor híbrido de scoring (Reglas + ML) integrado con el backend Java para obtener configuración dinámica de scoring.

## 🚀 Quick Start

### 1. Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Microservice
```bash
BACKEND_URL="http://localhost:8080/api" \
BACKEND_USER="admin" \
BACKEND_PASS="admin123" \
uvicorn app.main:app --host 0.0.0.0 --port 9001
```

### 3. Test Endpoints
```bash
# Individual scoring
curl -X POST 'http://localhost:9001/predict' \
  -H 'Content-Type: application/json' \
  -d '{"dias_vencidos":30,"monto_adeudado":250000,"pct_pagos_on_time":0.85}'

# Health check
curl http://localhost:9001/health
```

## 📡 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/predict` | Individual scoring (0-1000 scale) |
| POST | `/batch/upload` | Batch CSV processing |
| POST | `/feedback` | Payment feedback recording |
| GET | `/health` | Service health & config status |

## 📊 Scoring Architecture

**Formula**: `score_final = (score_reglas × 0.5 + score_ml × 0.5) / 1.0`

**Scale**: 0-1000 (higher = better customer)

**Segmentation**:
- **800+**: PLATINO (excellent)
- **650-799**: ORO (good)
- **500-649**: PLATA (acceptable)
- **300-499**: BRONCE (alert)
- **<300**: RECOVERY (high risk)

## 🔗 Backend Integration

✅ **Connected** to Java backend at `http://localhost:8080/api`

- Fetches active scoring model on startup
- Loads 6 weighted variables with dynamic ranges
- Respects client-defined scoring rules
- JWT authentication (admin/admin123)

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application with 4 endpoints |
| `app/schemas.py` | Pydantic validation models |
| `app/scoring/rules_engine.py` | Configurable rules-based scoring |
| `app/scoring/ml_model.py` | LightGBM wrapper with fallback |
| `app/integrations/backend_client.py` | Java backend HTTP client |
| `MICROSERVICIO_STATUS.md` | Detailed status & testing results |
| `CURL_TESTING_GUIDE.md` | Complete curl testing examples |
| `POSTMAN_TESTING.md` | Postman collection guide |

## ✅ Validation Results

- ✓ Backend connectivity verified
- ✓ Configuration loading (6 variables + ranges)
- ✓ Rules engine scoring (matches backend ranges)
- ✓ Score direction (high=good, low=bad)
- ✓ Batch processing (CSV upload)
- ✓ Health monitoring enabled

## 📚 Documentation

- **[MICROSERVICIO_STATUS.md](MICROSERVICIO_STATUS.md)** - Full status report with testing results
- **[CURL_TESTING_GUIDE.md](CURL_TESTING_GUIDE.md)** - Complete curl command examples
- **[POSTMAN_TESTING.md](POSTMAN_TESTING.md)** - Postman collection & GUI testing

## 🔮 Next Phase

- [ ] Train and integrate LightGBM model (`model.txt`)
- [ ] Database persistence for predictions/feedback
- [ ] Structured logging and monitoring
- [ ] Background batch processing
- [ ] Redis caching layer
- [ ] Docker containerization
