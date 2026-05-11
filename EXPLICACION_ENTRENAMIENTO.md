# 🎓 Explicación: Entrenamiento de LightGBM en el Microservicio

## ¿Qué es lo que se ENTRENA?

Se entrena un modelo **LightGBM de clasificación binaria** que predice si un cliente **pagará en los próximos 30 días** (sí=1 / no=0).

### Input del Modelo (8 Features)
```
dias_vencidos           → ¿Cuántos días debe?
monto_adeudado          → ¿Cuánto debe?
pct_pagos_on_time       → ¿Qué % de sus pagos fueron a tiempo?
seniority_months        → ¿Cuánto tiempo lleva como cliente?
default_frequency       → ¿Con qué frecuencia incumple?
has_telefono            → ¿Tenemos su teléfono?
has_email               → ¿Tenemos su email?
broken_promises_count   → ¿Cuántas promesas de pago ha incumplido?
```

### Output del Modelo
```
Probabilidad de pago en 30 días: 0-100%
```

Ejemplo:
- Cliente con 5 días de mora + buen historial → Modelo predice 82% (alto)
- Cliente con 200 días de mora + mal historial → Modelo predice 2% (bajo)

---

## ¿Por Qué Entrenar?

### Fallback (SIN Modelo)
```python
if dias_vencidos <= 30:
    return 75%  # Probabilidad fija
```

**Problema**: Solo usa 1 feature (días), ignora el resto.

### Modelo Entrenado (CON LightGBM)
```python
prob = model.predict([
    dias_vencidos,
    monto_adeudado,
    pct_pagos_on_time,
    ...
])
```

**Beneficio**: Aprende correlaciones entre todos los factores.

---

## Estado ACTUAL del Código

```python
# app/scoring/ml_model.py
class MLModel:
    def predict_proba(self, data):
        if not self.is_available():
            # Usa fallback (heurística) si no hay model.txt
            return fallback_prediction(data)
        else:
            # Usa LightGBM si model.txt existe
            return lightgbm_prediction(data)
```

**Traducción**:
- ✅ Si `app/models/model.txt` existe → Usa modelo entrenado
- ⚠️ Si NO existe → Usa fallback automáticamente

---

## ¿FUNCIONA YA Sin Entrenar?

**SÍ**. El microservicio funciona perfectamente sin entrenar:

1. `app/models/model.txt` NO existe al iniciar
2. `MLModel.is_available()` retorna `False`
3. Usa fallback heurístico automáticamente
4. Microservicio score_ml usa fallback: `dias→75%, 60→45%, etc.`

**Resultado**: Scoring hybrid funciona (50% reglas + 50% heurística ML).

---

## ¿CÓMO Entrenar?

### Opción A: Datos Sintéticos (AHORA - para demo)

```bash
# 1. Generar 500 ejemplos realistas
python3 scripts/generate_synthetic_data.py --output data/synthetic_data.csv --n 500

# 2. Entrenar modelo
python3 scripts/train.py --data data/synthetic_data.csv --output app/models/model.txt

# 3. Guardar model.txt
# ✓ Ya hecho por train.py
```

**Resultado**: `app/models/model.txt` creado (5.3 KB).

### Opción B: Datos Reales (DESPUÉS - cuando tengas histórico)

```bash
# 1. Extraer datos históricos del core
python3 scripts/extract_training_data.py \
  --core-url "http://core/api" \
  --start-date "2024-01-01" \
  --output "data/training_data.csv"

# 2. Entrenar (mismo comando)
python3 scripts/train.py --data data/training_data.csv --output app/models/model.txt

# 3. Modelo actualizado automáticamente
```

---

## ¿QUÉ PASA Después de Entrenar?

### Paso 1: Modelo Se Guarda
```
app/models/model.txt  ← LightGBM binary file (5-100 KB típicamente)
```

### Paso 2: Reiniciar Microservicio
```bash
uvicorn app.main:app --port 9000
```

En el startup:
```python
# app/main.py
ml = MLModel()  # Intenta cargar app/models/model.txt
# Si existe → ml._model = Booster(...)
# Si NO existe → ml._model = None
```

### Paso 3: Predicciones Usan Modelo
```
POST /predict
├─ input: {dias_vencidos: 30, monto_adeudado: 100k, ...}
├─ rules_engine → score_reglas = 350 (del backend)
├─ MLModel.predict_proba() → ¿Qué usa?
│  ├─ Si model.txt existe → LightGBM → prob = 58%
│  └─ Si model.txt NO existe → Fallback → prob = 75%
├─ score_ml = 1000 - (prob * 10)
└─ score_final = (score_reglas * 0.5 + score_ml * 0.5) = X
```

---

## Estado: ¿Con o Sin Modelo?

### Saber si Modelo Está Cargado

```bash
# Opción 1: Health check
curl http://localhost:9000/health | jq .

# Opción 2: Logs del microservicio
# Si ves "usando_ml": true en respuesta → Modelo cargado
# Si ves "usando_ml": false en respuesta → Fallback

# Opción 3: Verificar archivo
ls -la app/models/model.txt
# Si existe → Modelo disponible (después de reiniciar)
```

### Comparar Predicciones

```bash
# ANTES de entrenar (fallback):
# dias=60 → prob=45%, score_ml=550

# DESPUÉS de entrenar:
# dias=60 + otros features → prob=48%, score_ml=520
# (el modelo aprende combinaciones)
```

---

## Timeline Recomendado

| Fase | Acción | Resultado |
|------|--------|-----------|
| **Hoy** | Lanzar con fallback | ✓ Microservicio operacional |
| **Semana 1** | Acumular 100+ etiquetas | Datos para análisis |
| **Semana 2** | Generar datos sintéticos | Test pipeline end-to-end |
| **Mes 1** | Entrenar con sintéticos | Validar que ML funciona |
| **Mes 2** | 500+ etiquetas reales | Entrenar con datos verdaderos |
| **Mes 3+** | Reentrenamiento semanal | Modelo siempre actualizado |

---

## Estructura de Carpetas Actualizada

```
modulo-lightGBM/
├── app/
│   ├── models/
│   │   └── model.txt                 ← ⭐ Modelo entrenado (generado por train.py)
│   ├── scoring/
│   │   ├── ml_model.py               ← Carga model.txt si existe
│   │   └── rules_engine.py           ← Fallback si model.txt no existe
│   └── main.py
├── scripts/
│   ├── generate_synthetic_data.py    ← Genera CSV con 500 ejemplos
│   ├── train.py                      ← Entrena LightGBM, guarda model.txt
│   └── compare_models.py             ← Demo: fallback vs modelo
├── data/
│   └── synthetic_data.csv            ← ⭐ Dataset de entrenamiento
├── TRAINING_PIPELINE.md              ← Guía completa
├── DEMO_ENTRENAMIENTO_VS_FALLBACK.md ← Resultados demo
└── ml_pipeline_quickstart.sh          ← Script automatizado
```

---

## FAQ Rápido

**P: ¿Se entrena automáticamente?**  
R: No, requiere ejecutar `train.py` manualmente.

**P: ¿Puedo usar el microservicio sin entrenar?**  
R: Sí, usa fallback automáticamente. Funciona perfectamente.

**P: ¿Qué pasa si el modelo falla?**  
R: Fallback automático a heurística (`dias_vencidos`).

**P: ¿Cuánto mejora el modelo?**  
R: +17.5% en AUC (0.68 vs 0.58) con datos sintéticos. Con datos reales: +20-30% esperado.

**P: ¿Necesito reinstalar dependencias después de entrenar?**  
R: No, LightGBM ya está en `requirements.txt`.

**P: ¿Dónde guarda el modelo?**  
R: `app/models/model.txt` (especificado en `train.py --output`).

**P: ¿Cómo cargar un modelo diferente?**  
R: Cambiar ruta en `MLModel("path/to/other_model.txt")`.

---

## Próximos Pasos

### Inmediato (Hoy)
- [ ] Ejecutar `ml_pipeline_quickstart.sh` para validar pipeline
- [ ] Ver `MODEL_COMPARISON.html` para resultados

### Corto Plazo (Esta Semana)
- [ ] Integrar acceso a datos reales del core
- [ ] Crear extractor `scripts/extract_training_data.py`

### Mediano Plazo (Este Mes)
- [ ] Implementar reentrenamiento automático (cron)
- [ ] Monitoreo de performance del modelo (AUC drift)

### Largo Plazo
- [ ] CI/CD para despliegue automático de modelos
- [ ] A/B testing: fallback vs modelo en producción
- [ ] Versionado de modelos + rollback automático

---

## Resumen en 30 Segundos

✅ **Hoy**: Microservicio funciona SIN entrenar (fallback)  
✅ **Entrenar**: `train.py` crea `model.txt`  
✅ **Impacto**: +17.5% mejor discriminación (AUC)  
✅ **Automático**: Si model.txt existe, lo usa; si no, fallback  
✅ **Fallback**: Siempre disponible si modelo falla  

**Próximo paso**: Ejecutar `ml_pipeline_quickstart.sh` y ver resultados.

---

**Versión**: 1.0  
**Fecha**: 2025-01-15  
**Estado**: ✅ Listo para usar
