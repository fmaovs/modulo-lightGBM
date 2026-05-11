#!/usr/bin/env bash
# Ejemplos de curl para probar el microservicio de scoring
# Importar en Postman o ejecutar directamente

BASE_URL="http://localhost:9000"

echo "=== 1. PREDICT - Cliente sin mora (Bajo riesgo) ==="
curl -X POST "$BASE_URL/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "obligacion_id": "CR001",
    "dias_vencidos": 5,
    "monto_adeudado": 100000,
    "pct_pagos_on_time": 0.95,
    "cliente_id": "CLI001",
    "producto": "Crédito Personal"
  }' | python3 -m json.tool

echo -e "\n=== 2. PREDICT - Cliente en mora moderada (Riesgo medio) ==="
curl -X POST "$BASE_URL/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "obligacion_id": "CR002",
    "dias_vencidos": 60,
    "monto_adeudado": 500000,
    "pct_pagos_on_time": 0.60,
    "cliente_id": "CLI002",
    "producto": "Crédito Rotativo"
  }' | python3 -m json.tool

echo -e "\n=== 3. PREDICT - Cliente en mora severa (Alto riesgo) ==="
curl -X POST "$BASE_URL/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "obligacion_id": "CR003",
    "dias_vencidos": 200,
    "monto_adeudado": 2000000,
    "pct_pagos_on_time": 0.15,
    "cliente_id": "CLI003",
    "producto": "Crédito Comercial"
  }' | python3 -m json.tool

echo -e "\n=== 4. BATCH UPLOAD - Cargar archivo CSV ==="
echo "obligacion_id,dias_vencidos,monto_adeudado,pct_pagos_on_time" > /tmp/batch_test.csv
echo "CR1001,10,50000,0.85" >> /tmp/batch_test.csv
echo "CR1002,45,250000,0.60" >> /tmp/batch_test.csv
echo "CR1003,200,1500000,0.20" >> /tmp/batch_test.csv

curl -X POST "$BASE_URL/batch/upload" \
  -F "file=@/tmp/batch_test.csv" | python3 -m json.tool

echo -e "\n=== 5. FEEDBACK - Registrar pago ==="
curl -X POST "$BASE_URL/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "obligacion_id": "CR001",
    "pago_realizado": true,
    "monto_pagado": 100000,
    "fecha_pago": "2026-05-11"
  }' | python3 -m json.tool
