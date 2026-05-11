# 🎓 ML Training Pipeline - Mapa Completo

## Objetivo
Entrenar un modelo LightGBM que mejore las predicciones de scoring frente a la heurística actual (fallback basada en reglas).

---

## 📊 Flujo de Datos

```
┌─────────────────────────────────────────────────────────────┐
│ FUENTE DE DATOS (Core del negocio)                           │
│ - Histórico obligaciones: dias_vencidos, monto, pct_pagos   │
│ - Histórico pagos: fecha_pago, monto_pagado                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. EXTRACCIÓN (extract_training_data.py)                    │
│ - Conectar a BD/API del core                                │
│ - Generar snapshots: features + label (paid_within_30d)     │
│ - Guardar: training_data.csv (min. 500-1000 rows)           │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. PREPARACIÓN (train.py)                                   │
│ - Carga training_data.csv                                   │
│ - Feature engineering y validación                          │
│ - Split train/val/test (70/15/15)                           │
│ - Balanceo de clases (SMOTE si imbalance > 3:1)            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ENTRENAMIENTO (train.py)                                 │
│ - LightGBM con params optimizados                           │
│ - Early stopping en validation set                          │
│ - Feature importance logging                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. EVALUACIÓN (train.py)                                    │
│ - Métricas en test: AUC, Precision, Recall, F1              │
│ - Calibración (Expected Calibration Error)                  │
│ - Comparación vs baseline (fallback)                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. DESPLIEGUE (model.txt)                                   │
│ - Guardar modelo en app/models/model.txt                    │
│ - MLModel carga automáticamente al iniciar                  │
│ - Predicciones en /predict usan modelo entrenado            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. COMPARACIÓN (compare_models.py)                          │
│ - Predicciones con heurística (sin modelo)                  │
│ - Predicciones con modelo entrenado                         │
│ - Métricas lado a lado, visualizaciones, insights           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Estructura de Carpetas

```
modulo-lightGBM/
├── app/
│   ├── models/
│   │   └── model.txt                 ← Modelo guardado (generado por train.py)
│   └── scoring/
│       ├── ml_model.py               ← Wrapper que carga model.txt
│       └── rules_engine.py           ← Fallback heurístico
├── data/
│   ├── training_data.csv             ← CSV con features + label (generado por extractor)
│   ├── test_data.csv                 ← CSV de test para compare
│   └── synthetic_data.csv            ← Datos sintéticos para bootstrap (generado aquí)
├── scripts/
│   ├── extract_training_data.py      ← Conecta a core, extrae datos
│   ├── train.py                      ← Prepara datos, entrena, evalúa
│   ├── generate_synthetic_data.py    ← Genera datos sintéticos para bootstrap
│   └── compare_models.py             ← Demo: sin modelo vs. con modelo
├── TRAINING_PIPELINE.md              ← Este archivo
├── MODEL_COMPARISON.html             ← Report generado por compare_models.py
└── requirements.txt                  ← Asegurar: lightgbm, pandas, scikit-learn, numpy
```

---

## 📋 Features Utilizados

| Feature | Origen | Tipo | Rango/Escala | Uso |
|---------|--------|------|---------|-----|
| `dias_vencidos` | obligaciones.dias_vencidos | int | 0-365+ | Predictor clave |
| `monto_adeudado` | obligaciones.monto_adeudado | float | 0-N | Predictor clave |
| `pct_pagos_on_time` | obligaciones.pct_pagos_on_time | float | 0-1 | Histórico de comportamiento |
| `seniority_months` | obligaciones.seniority_months | int | 0-360+ | Antigüedad cliente |
| `default_frequency` | obligaciones.default_frequency | float | 0-1 | Tasa de incumplimiento |
| `has_telefono` | obligaciones.telefono IS NOT NULL | bool | 0/1 | Ubicabilidad |
| `has_email` | obligaciones.email IS NOT NULL | bool | 0/1 | Ubicabilidad |
| `broken_promises_count` | obligaciones.broken_promises | int | 0-N | Incumplimientos previos |

### Target (Label)

| Label | Definición | Tipo | Clase Positiva |
|-------|-----------|------|----------------|
| `paid_within_30d` | ¿Pagó en los próximos 30 días? | bool (0/1) | 1 = Sí, pagó |

---

## 🚀 Quickstart: Entrenar sin Datos Reales

### Opción A: Generar datos sintéticos y entrenar

```bash
cd /home/fvillanueva/Escritorio/modulo-lightGBM
source .venv/bin/activate

# 1. Generar datos sintéticos de bootstrap
python3 scripts/generate_synthetic_data.py
# Output: data/synthetic_data.csv (1000 filas)

# 2. Entrenar modelo
python3 scripts/train.py --data data/synthetic_data.csv --output app/models/model.txt
# Output: app/models/model.txt + reporte de métricas

# 3. Comparar: heurística vs modelo entrenado
python3 scripts/compare_models.py --data data/synthetic_data.csv
# Output: MODEL_COMPARISON.html + estadísticas en terminal
```

### Opción B: Usar datos reales del core (cuando disponibles)

```bash
# 1. Extraer datos del core (requiere API/DB acceso)
python3 scripts/extract_training_data.py \
  --core-url "http://core-backend/api" \
  --start-date "2024-01-01" \
  --end-date "2025-01-01" \
  --output "data/training_data.csv"

# 2-3. Pasos iguales que Opción A, reemplazando datos sintéticos por reales
python3 scripts/train.py --data data/training_data.csv --output app/models/model.txt
python3 scripts/compare_models.py --data data/training_data.csv
```

---

## 📊 Comparación: Con vs Sin Entrenamiento

### Escenario Sin Modelo (Fallback Heurístico)

```
Input:  dias_vencidos=60, monto_adeudado=500000, pct_pagos_on_time=0.60
Fallback (ml_model.py sin model.txt):
  - dias <= 30? NO
  - dias <= 90? SÍ → prob = 45.0%
  
score_ml = 1000 - (45.0 * 10) = 550
score_final = (score_reglas × 0.5 + 550 × 0.5) / 1.0
```

**Característica**: Predicción basada solo en dias_vencidos, ignorando otros factores (monto, historial de pagos).

### Escenario Con Modelo Entrenado

```
Input:  dias_vencidos=60, monto_adeudado=500000, pct_pagos_on_time=0.60
Model (ml_model.py con model.txt):
  - Features: [60, 500000, 0.60]
  - LightGBM predice: prob = 62.3%  ← Considera múltiples factores + relaciones no-lineales
  
score_ml = 1000 - (62.3 * 10) = 377
score_final = (score_reglas × 0.5 + 377 × 0.5) / 1.0
```

**Característica**: Modelo captura correlaciones (p. ej. cliente con monto alto + buen historial es más confiable).

### Diferencias Esperadas

| Métrica | Fallback | Modelo | Mejora |
|---------|----------|--------|--------|
| AUC | ~0.65-0.70 | 0.75-0.85 | +10-15% |
| Calibración | Pobre | Buena | Scores ≈ probs reales |
| Precisión | Baja (~60%) | Alta (~75%) | +15% |
| Falsos Positivos | Altos | Bajos | Menos rechazos innecesarios |

---

## 🔄 Ciclo de Mejora (MLOps)

### Reentrenamiento Programado

```bash
# Cron (diaria, 2 AM)
0 2 * * * cd /home/fvillanueva/Escritorio/modulo-lightGBM && \
  source .venv/bin/activate && \
  python3 scripts/extract_training_data.py --recent 7 && \
  python3 scripts/train.py --data data/training_data.csv --output app/models/model.txt.new && \
  python3 scripts/validate_model.py --old app/models/model.txt --new app/models/model.txt.new && \
  if [ $? -eq 0 ]; then mv app/models/model.txt.new app/models/model.txt; fi
```

### Validación de Modelo

```python
# scripts/validate_model.py (pseudo-código)
def validate_new_model(old_model_path, new_model_path):
    # 1. Cargar ambos modelos
    old_ml = MLModel(old_model_path)
    new_ml = MLModel(new_model_path)
    
    # 2. Predicciones en test set
    old_preds = [old_ml.predict_proba(x) for x in X_test]
    new_preds = [new_ml.predict_proba(x) for x in X_test]
    
    # 3. Comparar AUC
    old_auc = roc_auc_score(y_test, old_preds)
    new_auc = roc_auc_score(y_test, new_preds)
    
    # 4. Aceptar si mejora ≥ 1% y no degrada falsos negativos
    if new_auc >= old_auc * 1.01 and specificity(new_preds) >= 0.9:
        return True
    return False
```

---

## 🛠️ Guía Rápida de Implementación

### Paso 1: Requisitos
```bash
pip install lightgbm pandas scikit-learn numpy matplotlib plotly
```

### Paso 2: Generar Datos Sintéticos (bootstrap inmediato)
- Ejecutar `scripts/generate_synthetic_data.py`
- Genera 1000 ejemplos siguiendo reglas de negocio
- Simula distribución realista de pagos/incumplimientos

### Paso 3: Entrenar Modelo
- Ejecutar `scripts/train.py`
- Usa datos sintéticos o reales
- Output: `app/models/model.txt` (compatible con `MLModel`)

### Paso 4: Comparación Demo
- Ejecutar `scripts/compare_models.py`
- Genera HTML con gráficos lado a lado
- Muestra mejoras en métricas

### Paso 5: Integración
- Reiniciar microservicio: `uvicorn app.main:app --port 9001`
- `/predict` usa automáticamente el modelo si existe `app/models/model.txt`

---

## 📈 Métricas Clave a Seguir

| Métrica | Definición | Objetivo |
|---------|-----------|----------|
| **AUC** | Area Under ROC Curve | > 0.75 |
| **Precision** | TP / (TP + FP) | > 0.75 |
| **Recall** | TP / (TP + FN) | > 0.70 |
| **F1** | Harmonic mean P/R | > 0.70 |
| **ECE** | Expected Calibration Error | < 0.05 |
| **Baseline AUC** | Fallback model | ~0.65 |
| **Lift** | AUC_model / AUC_baseline | > 1.10 |

---

## ⚠️ Consideraciones Importantes

### Data Leakage
- ❌ Usar features que no estaban disponibles en tiempo de predicción (p. ej. `fecha_pago` en features).
- ✅ Usar snapshots con features en el momento exacto de la solicitud.

### Imbalance de Clases
- Si `paid_within_30d` es 90/10 (bias a pagos), aplicar:
  - SMOTE (synthetic oversampling)
  - Class weights en LightGBM
  - Metrics: Precision-Recall en lugar de Accuracy

### Privacidad/Seguridad
- Anonimizar PII antes de guardar training_data.csv
- Encriptar datos sensibles en tránsito
- Auditar acceso al modelo y predicciones

### Reproducibilidad
- Guardar random seed y hiperparámetros en metadata del modelo
- Versionar código + datos + modelo juntos (p. ej. git tags)
- Documentar cambios en features o lógica

---

## 📁 Archivos a Generar/Modificar

### Nuevos (scripts de ML)
- ✅ `scripts/generate_synthetic_data.py` → Genera datos sintéticos
- ✅ `scripts/train.py` → Entrena LightGBM
- ✅ `scripts/compare_models.py` → Demo: con vs sin modelo
- ✅ `scripts/extract_training_data.py` → Template para extraer del core

### Modificados
- `app/scoring/ml_model.py` → Ya soporta `model.txt` (sin cambios necesarios)
- `app/models/` → Nueva carpeta para guardar `model.txt`

### Outputs
- `data/synthetic_data.csv` → Datos para bootstrap
- `app/models/model.txt` → Modelo entrenado
- `MODEL_COMPARISON.html` → Reporte de comparación

---

## 🎯 Próximos Pasos

1. **Inmediato**: Ejecutar pipeline con datos sintéticos para validar end-to-end.
2. **Corto plazo**: Integrar acceso a datos reales del core (DB o API).
3. **Mediano plazo**: Implementar reentrenamiento automático semanal.
4. **Largo plazo**: MLOps completo (versionado, A/B testing, monitoreo de drift).

---

**Creado**: 2025-01-15  
**Status**: Plan Operacional  
**Próxima acción**: Ejecutar `generate_synthetic_data.py` → `train.py` → `compare_models.py`
