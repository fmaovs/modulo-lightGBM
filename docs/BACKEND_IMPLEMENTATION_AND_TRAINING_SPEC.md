# Especificación técnica: Integración del módulo IA y Mapa de Entrenamiento

Este documento está pensado para un agente o ingeniero que implementará la integración entre el backend (Java/Spring) y el microservicio de scoring (`modulo-lightGBM`). Contiene: contrato HTTP, requisitos no funcionales, cómo auditar/registrar cálculos, políticas de fallback/circuit-breaker, y un **mapa de entrenamiento** que pedir al equipo Core para generar datos y etiquetas.

---

## Reglas generales
- No se deben hardcodear datos sensibles ni credenciales en el servicio ni en el backend. Usar variables de entorno y secretos gestionados.
- Todo intercambio HTTP debe ser idempotente cuando aplique y con timeouts/ retries controlados desde el backend.
- Auditoría: cada cálculo debe quedar registrado con `engine_used` (ML|RULES|BACKEND_RULES_FALLBACK), las reglas aplicadas (ranges), y el resultado.

---

## Endpoints del microservicio (contrato)
- POST `/predict`
  - Request JSON: cualquiera de los campos de `PredictInput` (ver ejemplo abajo). Campo opcional `prefer_ml` (true|false|null) que el backend puede usar para forzar ML o rules.
  - Response JSON (parcial):
    - `obligacion_id`, `score_final`, `score_reglas`, `score_ml`, `probabilidad_pago`, `segmento`, `audit` (objeto con `engine_used`, `model_version`).
  - Semántica: si `prefer_ml=true` y el ML no está disponible -> respuesta con `engine_used="RULES"` y el backend debe considerar eso como fallback.

- POST `/batch/upload`
  - Form-data: `file=@<csv>`
  - Response: JSON con `processed`, `results` (array con resultados como `/predict`). Usar para pruebas masivas.

- POST `/feedback`
  - Usado por backend para reportar pagos reales (retroalimentación para re-entrenamiento offline).

- GET `/health`
  - Devuelve estado (`backend_connected`, `scoring_config_loaded`) usado por sondas de health.

- (Opcional recomendado) POST `/scoring/audit` en el backend para centralizar auditoría. Nuestro microservicio intentará enviar un POST a `${BACKEND_URL}${BACKEND_AUDIT_ENDPOINT}` (env var `BACKEND_AUDIT_ENDPOINT`, default `/scoring/audit`).

### Ejemplo de request `/predict`
{
  "obligacion_id": "OBL-002",
  "dias_vencidos": 100,
  "monto_adeudado": 8158373.99,
  "pct_pagos_on_time": 0.5,
  "prefer_ml": true
}

### Ejemplo de response (parcial)
{
  "obligacion_id": "OBL-002",
  "score_final": 420,
  "score_reglas": 380,
  "score_ml": 460,
  "probabilidad_pago": 54.3,
  "segmento": "PLATA",
  "audit": {"engine_used":"ML","model_version":"v1.0"}
}

---

## Variables de entorno que debe soportar el servicio
- `BACKEND_URL` (ej: https://backend.internal/api)
- `BACKEND_API_KEY` o `BACKEND_USER`/`BACKEND_PASS` para autenticación
- `BACKEND_AUDIT_ENDPOINT` (ruta relativa donde el backend recibe auditoría, default `/scoring/audit`)
- `MODEL_PATH` (ruta del artefacto LightGBM si se quiere overwrite)

---

## Seguridad y autenticación
- Comunicación entre backend y módulo IA debe ir por TLS (https) en producción.
- Preferible usar JWT o API keys. Si el backend emite JWT, microservicio debe validar o aceptar el token para autenticación entrante.
- Audits enviados por microservicio al backend deben autenticarse (usar misma estrategia: Authorization header).

---

## Auditoría requerida (lo que el backend debe recibir/persistir)
Cada cálculo (POST `/predict`) debe generar un registro con:
- `obligacion_id` (PK)
- `timestamp`
- `engine_used` (ML|RULES|BACKEND_RULES_FALLBACK)
- `model_version` (string)
- `score_final`, `score_reglas`, `score_ml`
- `rules_details` (opcional, array con variables, range matched, baseScore, contribution)
- `request_payload` (solo si está permitido; evitar datos sensibles)
- `calc_origin` ("IA_SERVICE" o "BACKEND_CALCULATOR")

Formato sugerido: JSON, un registro por entrada. Backend debe persistir en tabla `scoring_audit` o similar.

---

## Políticas de resiliencia (recomendadas para el backend)
- Timeout corto: 1000-2000 ms para `/predict`.
- Retries limitados: máximo 1 retry con backoff exponencial corto.
- Circuit Breaker (ej. Resilience4j): abrir después de N fallos consecutivos (p.ej. 5) y mantener abierto un tiempo (p.ej. 30s).
- Fallback: cuando CB abierto o request falla → ejecutar motor de reglas local y registrar `engine_used=BACKEND_RULES_FALLBACK`.
- Instrumentación: contar latencias, errores, ratio de fallback.

---

## Qué debe implementar el agente en el backend (lista de tareas concretas)
1. HTTP client que haga POST `/predict` con request construido a partir de la obligación.
2. Manejo de timeouts/retries/circuit-breaker con Resilience4j (o similar).
3. Si la respuesta llega con `audit` -> persistir `audit` en la tabla `scoring_audit`.
4. Si hay error/timeout/CB abierto -> ejecutar _exactamente_ la misma lógica de reglas definidas en `scoring_config` (backend ya tiene esas reglas) y persistir registro con `engine_used=BACKEND_RULES_FALLBACK`.
5. Implementar endpoint `POST /scoring/audit` que pueda recibir y persistir los JSON enviados por el microservicio (para trazabilidad centralizada).
6. Añadir pruebas unitarias y de integración que simulen: respuesta OK de IA, respuesta 5xx, timeout, y comportamientos de fallback.
7. No almacenar datos sensibles: máscara/omit `request_payload` si contiene PII, o cifrar en reposo.

---

## Requisitos para el equipo de Core: Mapa de entrenamiento del modelo
Este apartado describe exactamente qué datos, labels y preprocesos se deben entregar por Core para que el equipo de ML entrene el LightGBM reproducible.

### Objetivo del modelo
Predecir la probabilidad de pago de una obligación (en un horizonte definido) para mapear a una `score` (0..1000).

### Target (label)
- Nombre de la etiqueta: `pagara_en_horizonte` (booleano)
- Definición: si la obligación recibió un pago (parcial o total) dentro de los siguientes X días desde la fecha de valoración. `X` debe ser acordado (recomendado: 30 días para scoring operativo, 90 días para recuperación). Indicar el horizonte solicitado.
- Tipo: binario (1 = pagó dentro de X días, 0 = no pagó).

### Ventana temporal y particionado
- Periodo de extracción: mínimo 12 meses de histórico; ideal 24 meses.
- Ventana de entrenamiento: usar ventanas temporales rolling para evitar fuga temporal. Ejemplo: train hasta T0, validation T0..T1, test T1..T2.
- Split temporal: 70% train / 15% val / 15% test en orden cronológico.

### Volumen mínimo recomendado
- Mínimo 50k-100k obligaciones para modelos robustos; si no hay, documentar limitaciones.
- Balance de clases: reportar tasa de positives (pagos) — si <5% considerar oversampling/estrategias.

### Campos (features) — pedirlos sin datos hardcodeados
Proveer CSV/tabla con un registro por obligación y columnas (ejemplos y mapeos):
- `obligacion_id` (string)
- `cliente_id` (string)
- `fecha_valoracion` (ISO8601) -- fecha en la que se genera la observación
- `fecha_vencimiento` (ISO8601)
- `dias_vencidos` (int) = dias entre fecha_valoracion y fecha_vencimiento si vencida, sino 0
- `monto_adeudado` (float) -- valor en moneda base
- `currency` (string)
- `pct_pagos_on_time` (float 0..1)
- `pct_recuperacion_parcial` (float 0..1)
- `intentos_contacto_fallidos` (int)
- `dias_desde_ultimo_pago` (int)
- `producto` (string)
- `segmento_cliente` (string)
- `mobile_present` (bool)
- `email_present` (bool)
- `historico_promesas_incumplidas` (int)
- `nro_paginas_mora` (int) // si aplica
- `valor_ultima_cuota` (float)
- `historial_pagos_6m` (string) optional (e.g., "101011") o vector de features: pagos en los últimos N meses

> Importante: indicar nombre exacto de cada columna y tipos; si algún campo no existe en core, indicarlo para que se negocie sustituto.

### Preprocesamiento solicitado desde Core (entregar datos ya normalizados o reglas claras)
- Todas las columnas numéricas deben venir sin enmascarar, con unidades claras (COP, USD, etc.). Indicar columna `currency` si varía.
- Missing values: indicar cómo registrar (NULL/empty). Proveer tasa de missing por columna.
- Categorical: `producto`, `segmento_cliente` — entregar diccionario de categorías frecuentes y frecuencia por categoría.
- Fechas: ISO8601.
- ID columns: `obligacion_id`, `cliente_id` deben ser estables y únicos por registro.

### Label creation
- Para cada `obligacion_id` y `fecha_valoracion` se debe generar `pagara_en_horizonte` calculando si existe registro de pago entre `fecha_valoracion` y `fecha_valoracion + X días`.
- Entregar script SQL/py para reproducir la etiqueta desde la fuente transaccional (o un notebook con la lógica exacta).

### Features derivadas que el equipo ML usará (mapa de features)
- `dias_vencidos` (raw)
- `log_monto_adeudado` = log(1 + monto_adeudado)
- `pct_pagos_on_time` (raw)
- `recuperacion_ratio` = pct_recuperacion_parcial
- `contact_attempts` = intentos_contacto_fallidos
- `days_since_last_payment` = dias_desde_ultimo_pago
- `has_mobile` = mobile_present ? 1 : 0
- `has_email` = email_present ? 1 : 0
- `producto_*` = one-hot o top-N embedding para `producto`
- `segmento_*` = one-hot para segmento
- `recent_payment_pattern` = vector transformado a features numéricos (n pagos en 3/6/12 meses)

El equipo Core debe entregar los datos RAW y, opcionalmente, un dataset ya transformado siguiendo estas columnas.

### Evaluación y métricas
- Métricas principales: AUC-ROC, AUC-PR (si clases desbalanceadas), Accuracy, Recall@K, F1
- Calibración: Brier score y calibration plot
- Thresholding: documentación de cómo mapear probabilidad a score 0..1000 (por ejemplo score = int(probability * 10) invertido si necesario)

### Requisitos de entregables del equipo Core
- CSV/Parquet con columnas listadas arriba, cubriendo al menos 12 meses.
- Script reproducible (SQL o Python) que genera el conjunto de entrenamiento y la etiqueta `pagara_en_horizonte` para un horizonte X (indicar X en la entrega).
- Diccionario de datos (data dictionary) con tipos, descripciones y tasa de missing por columna.
- Lista de ejemplos de valores por columna (sin PII sensible; si hay PII, entregar muestras anonimizadas).

### Privacidad y cumplimiento
- Nunca incluir datos sensibles en ejemplos públicos. Si se requieren datos con PII para modelado, usar datos en entorno seguro y enviar sólo datos anonimizados fuera del entorno.

### Formato final del modelo esperado
- Artefacto LightGBM `model.txt` o `model.bin` (formato ligero) junto con `feature_list.json` (orden y nombre exacto de features) y `training_report.pdf/html` con métricas en train/val/test y curvas.
- Notebook o script reproducible `train.py` que usa los datos provistos y genera el artefacto.

---

## Criterios de aceptación (QA)
1. Backend puede llamar a `/predict` y recibe respuesta < 2s en condiciones nominales.
2. Cuando ML no está disponible, backend aplica sus reglas locales y persiste `engine_used=BACKEND_RULES_FALLBACK`.
3. Cada predicción deja un registro en `scoring_audit` (bien formado) y microservicio intenta enviar auditoría a `BACKEND_AUDIT_ENDPOINT`.
4. Existen pruebas de integración que cubren éxito, timeout y fallback.
5. Equipo ML entrega artefacto y `feature_list.json`, y la precisión/ROC cumplen las metas acordadas.

---

## Checklist para el agente de implementación (pasos ejecutables)
- [ ] Añadir cliente HTTP en backend que consuma `/predict`.
- [ ] Integrar Resilience4j (timeouts, retry, circuit-breaker).
- [ ] Implementar endpoint `POST /scoring/audit` en backend y persistencia en tabla `scoring_audit`.
- [ ] Probar con `examples/batch_test_20260507_1722.csv` usando `/batch/upload`.
- [ ] Añadir tests unit/integration para fallback y auditoría.
- [ ] Confirmar que no hay datos quemados en repositorios ni logs.

---

## Contactos y recursos
- Repo del módulo IA: ruta local del proyecto. (Entregar URL del repo si es remoto.)
- Variables de ejemplo y comandos para pruebas en `CURL_TESTING_GUIDE.md` en este repo.

---

Document created for: Agent implementer — follow these instructions exactly and ask for clarifications on ambiguous data fields before making production changes.
