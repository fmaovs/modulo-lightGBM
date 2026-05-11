# 📡 Testing Guide - Curl Commands

## Quick Start

**Service running on**: `http://localhost:9000`

### Health Check
```bash
curl http://localhost:9000/health
```

Expected:
```json
{"status":"ok","backend_connected":true,"scoring_config_loaded":true}
```

---

## 🎯 Individual Scoring Tests

### Test 1: Low Risk Customer (No arrears)
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"PROFILE_LOW_RISK",
    "dias_vencidos":5,
    "monto_adeudado":100000,
    "pct_pagos_on_time":0.95,
    "cliente_id":"CLI_001",
    "seniority_months":36,
    "default_frequency":0.05,
    "telefono":"+57123456789",
    "email":"customer@example.com"
  }' | jq .
```

**Expected Output**: 
- score_final: 700-800 (ORO/PLATINO)
- segmento: ORO
- riesgo_incumplimiento: 5-25%

---

### Test 2: Medium Risk Customer (30-60 days arrears)
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"PROFILE_MEDIUM_RISK",
    "dias_vencidos":45,
    "monto_adeudado":500000,
    "pct_pagos_on_time":0.70,
    "cliente_id":"CLI_002",
    "seniority_months":12,
    "default_frequency":0.30,
    "telefono":"+57123456789"
  }' | jq .
```

**Expected Output**:
- score_final: 600-700 (PLATA/ORO)
- segmento: ORO o PLATA
- riesgo_incumplimiento: 30-55%

---

### Test 3: High Risk Customer (>90 days arrears)
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"PROFILE_HIGH_RISK",
    "dias_vencidos":150,
    "monto_adeudado":2000000,
    "pct_pagos_on_time":0.20,
    "cliente_id":"CLI_003",
    "seniority_months":6,
    "default_frequency":0.80,
    "email":"customer@example.com"
  }' | jq .
```

**Expected Output**:
- score_final: 300-500 (BRONCE/PLATA)
- segmento: BRONCE
- riesgo_incumplimiento: 75-95%

---

### Test 4: Minimal Input (Only required fields)
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "dias_vencidos":30,
    "monto_adeudado":250000,
    "pct_pagos_on_time":0.50
  }' | jq .
```

---

### Test 5: Edge Case - No arrears, Large amount
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"EDGE_HIGH_AMOUNT",
    "dias_vencidos":0,
    "monto_adeudado":50000000,
    "pct_pagos_on_time":0.99
  }' | jq .
```

---

## 📦 Batch Upload Tests

### Upload Sample CSV
```bash
curl -X POST 'http://localhost:9000/batch/upload' \
  -F 'file=@examples/sample_batch.csv'
```

### Create Custom CSV and Upload
```bash
# Create custom CSV
cat > /tmp/custom_batch.csv << 'EOF'
obligacion_id,dias_vencidos,monto_adeudado,pct_pagos_on_time
TEST_B001,0,100000,0.95
TEST_B002,45,500000,0.60
TEST_B003,180,3000000,0.10
EOF

# Upload
curl -X POST 'http://localhost:9000/batch/upload' \
  -F 'file=@/tmp/custom_batch.csv' | jq .
```

---

## 💳 Feedback Tests

### Record Successful Payment
```bash
curl -X POST 'http://localhost:9000/feedback' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"PROD001",
    "pago_realizado":true,
    "monto_pagado":250000,
    "fecha_pago":"2025-01-15"
  }' | jq .
```

### Record Payment Failure
```bash
curl -X POST 'http://localhost:9000/feedback' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"PROD002",
    "pago_realizado":false,
    "monto_pagado":0,
    "fecha_pago":"2025-01-15"
  }' | jq .
```

### Partial Payment
```bash
curl -X POST 'http://localhost:9000/feedback' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id":"PROD003",
    "pago_realizado":true,
    "monto_pagado":125000,
    "fecha_pago":"2025-01-15"
  }' | jq .
```

---

## 🔍 Debugging

### Pretty Print JSON Response
```bash
curl -s -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{"dias_vencidos":30,"monto_adeudado":100000}' | jq .
```

### View HTTP Headers
```bash
curl -i -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{"dias_vencidos":30,"monto_adeudado":100000}'
```

### Verbose Output (debug)
```bash
curl -v -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{"dias_vencidos":30,"monto_adeudado":100000}'
```

### Check Microservice Logs
```bash
# Follow logs
tail -f /tmp/microservicio.log

# Or if running in terminal, check terminal output
```

---

## 📊 Response Structure Reference

### Full Predict Response
```json
{
  "obligacion_id": "string",
  "score_final": 0-1000,
  "score_reglas": 0-1000,
  "score_ml": 0-1000,
  "probabilidad_pago": 0-100,
  "riesgo_incumplimiento": 0-100,
  "segmento": "PLATINO|ORO|PLATA|BRONCE|RECOVERY",
  "model_version": "string",
  "usando_ml": boolean,
  "recomendacion": "string"
}
```

### Segmentation Guide
| Segmento | Score Range | Acción |
|----------|-------------|--------|
| PLATINO | 800+ | Mantenimiento |
| ORO | 650-799 | Mantenimiento |
| PLATA | 500-649 | Monitoreo |
| BRONCE | 300-499 | Contacto + Incentivos |
| RECOVERY | <300 | Cobranza intensiva |

---

## ⚙️ Environment Variables

```bash
# Backend connection
export BACKEND_URL="http://localhost:8080/api"
export BACKEND_USER="admin"
export BACKEND_PASS="admin123"

# Microservice startup
export UVICORN_HOST="0.0.0.0"
export UVICORN_PORT="9000"
```

---

## 🚀 Postman Import

Import the provided `POSTMAN_TESTING.md` collection into Postman for GUI testing.

Or use jq for automatic JSON formatting:
```bash
sudo apt-get install jq  # if not installed
```

---

**Last Updated**: 2025-01-15  
**Testing Status**: All endpoints verified ✓
