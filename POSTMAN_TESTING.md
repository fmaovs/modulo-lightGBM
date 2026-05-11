# Guía de Testing del Microservicio IA - Scoring

## Inicio rápido

El microservicio está corriendo en: `http://localhost:9000`

### Variables de entorno (opcional, para conectar con backend Java)

```bash
export BACKEND_URL="http://localhost:8080/api"
export BACKEND_USER="admin"
export BACKEND_PASS="admin123"
```

---

## 1. PREDICT - Cliente sin mora (Bajo riesgo)

**Método:** POST  
**URL:** `http://localhost:9000/predict`  
**Headers:** `Content-Type: application/json`

**Body:**
```json
{
  "obligacion_id": "CR001",
  "dias_vencidos": 5,
  "monto_adeudado": 100000,
  "pct_pagos_on_time": 0.95,
  "cliente_id": "CLI001",
  "producto": "Crédito Personal"
}
```

**Curl:**
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id": "CR001",
    "dias_vencidos": 5,
    "monto_adeudado": 100000,
    "pct_pagos_on_time": 0.95,
    "cliente_id": "CLI001",
    "producto": "Crédito Personal"
  }'
```

---

## 2. PREDICT - Cliente en mora moderada (Riesgo medio)

**Método:** POST  
**URL:** `http://localhost:9000/predict`  
**Headers:** `Content-Type: application/json`

**Body:**
```json
{
  "obligacion_id": "CR002",
  "dias_vencidos": 60,
  "monto_adeudado": 500000,
  "pct_pagos_on_time": 0.60,
  "cliente_id": "CLI002",
  "producto": "Crédito Rotativo"
}
```

**Curl:**
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id": "CR002",
    "dias_vencidos": 60,
    "monto_adeudado": 500000,
    "pct_pagos_on_time": 0.60,
    "cliente_id": "CLI002",
    "producto": "Crédito Rotativo"
  }'
```

---

## 3. PREDICT - Cliente en mora severa (Alto riesgo)

**Método:** POST  
**URL:** `http://localhost:9000/predict`  
**Headers:** `Content-Type: application/json`

**Body:**
```json
{
  "obligacion_id": "CR003",
  "dias_vencidos": 200,
  "monto_adeudado": 2000000,
  "pct_pagos_on_time": 0.15,
  "cliente_id": "CLI003",
  "producto": "Crédito Comercial"
}
```

**Curl:**
```bash
curl -X POST 'http://localhost:9000/predict' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id": "CR003",
    "dias_vencidos": 200,
    "monto_adeudado": 2000000,
    "pct_pagos_on_time": 0.15,
    "cliente_id": "CLI003",
    "producto": "Crédito Comercial"
  }'
```

---

## 4. BATCH UPLOAD - Cargar archivo CSV

**Método:** POST  
**URL:** `http://localhost:9000/batch/upload`  
**Headers:** `Content-Type: multipart/form-data`

**Body:** Seleccionar archivo CSV con columnas: `obligacion_id`, `dias_vencidos`, `monto_adeudado`, `pct_pagos_on_time`

**Ejemplo de CSV (batch.csv):**
```csv
obligacion_id,dias_vencidos,monto_adeudado,pct_pagos_on_time
CR1001,10,50000,0.85
CR1002,45,250000,0.60
CR1003,200,1500000,0.20
```

**Curl:**
```bash
curl -X POST 'http://localhost:9000/batch/upload' \
  -F "file=@batch.csv"
```

---

## 5. FEEDBACK - Registrar pago realizado

**Método:** POST  
**URL:** `http://localhost:9000/feedback`  
**Headers:** `Content-Type: application/json`

**Body:**
```json
{
  "obligacion_id": "CR001",
  "pago_realizado": true,
  "monto_pagado": 100000,
  "fecha_pago": "2026-05-11"
}
```

**Curl:**
```bash
curl -X POST 'http://localhost:9000/feedback' \
  -H 'Content-Type: application/json' \
  -d '{
    "obligacion_id": "CR001",
    "pago_realizado": true,
    "monto_pagado": 100000,
    "fecha_pago": "2026-05-11"
  }'
```

---

## Importar en Postman

1. Abrir Postman
2. Ir a **File** → **Import**
3. Seleccionar la pestaña **Raw text**
4. Copiar y pegar cualquiera de los comandos curl anteriores
5. Click en **Import**
6. Configurar las variables de entorno si es necesario
7. Enviar la solicitud

---

## Entendimiento de la respuesta `/predict`

```json
{
  "obligacion_id": "CR001",           // ID de la obligación
  "score_final": 742,                 // Score híbrido final (0-1000)
  "score_reglas": 680,                // Score puro de reglas (0-1000)
  "score_ml": 810,                    // Score del modelo ML si está disponible (0-1000)
  "probabilidad_pago": 78.5,          // Probabilidad de pago en % (0-100)
  "riesgo_incumplimiento": 21.5,      // Riesgo de no pago en % (0-100)
  "segmento": "ORO",                  // Segmento: PLATINO, ORO, PLATA, BRONCE, RECOVERY
  "model_version": "1.0.0",           // Versión del modelo usado
  "usando_ml": true,                  // ¿Está usando ML o solo reglas?
  "recomendacion": "Contacto preferente + incentivos"
}
```

### Segmentación por Score

| Score | Segmento | Acción |
|-------|----------|--------|
| 800+ | PLATINO | Mantenimiento, bajo riesgo |
| 650-799 | ORO | Seguimiento regular |
| 500-649 | PLATA | Contacto preventivo |
| 300-499 | BRONCE | Contacto administrativo |
| <300 | RECOVERY | Escalamiento a cobranza avanzada |

---

## Notas importantes

- El servidor carga **automáticamente** la configuración desde el backend Java al iniciar
- Si el backend no está disponible, usa un fallback local
- El scoring es **híbrido**: 50% reglas + 50% ML (configurable)
- Las reglas se actualizan desde el backend cada vez que se llama a `/predict`

