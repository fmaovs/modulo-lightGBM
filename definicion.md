# Requerimientos del Módulo de IA - Scoring de Cobranza
 
**Versión:** 1.0  
**Fecha:** 10 de mayo de 2026  
**Autor:** Grok (Diseño Técnico)  
**Tipo de Documento:** Especificación de Requerimientos Funcionales y No Funcionales
 
---
 
## 1. Introducción
 
### 1.1 Objetivo
Desarrollar un **módulo de inteligencia artificial** híbrido para calcular scoring de riesgo y segmentación de clientes en mora, combinando reglas de negocio tradicionales con un modelo de **Machine Learning (LightGBM)**, permitiendo aprendizaje continuo a partir de los resultados reales de cobranza.
 
### 1.2 Alcance
- Cálculo de Score de Cobranza (0-1000)
- Cálculo de Probabilidad de Pago y Riesgo de Incumplimiento
- Segmentación automática de clientes
- Sistema híbrido (Reglas + ML)
- Aprendizaje incremental (online learning)
- Explicabilidad y auditoría
 
---
 
## 2. Requisitos Funcionales
 
### 2.1 Funcionalidades Principales
 
| ID | Requisito | Descripción |
|----|---------|-----------|
| RF-01 | Cálculo de Score Reglas | Calcular score tradicional basado en reglas configurables (mora, monto, historial, contacto, recency) |
| RF-02 | Predicción con LightGBM | Ejecutar modelo ML para predecir probabilidad de pago |
| RF-03 | Score Híbrido | Combinar score de reglas + score ML mediante pesos configurables |
| RF-04 | Segmentación | Asignar segmento (PLATINO, ORO, PLATA, BRONCE, RECOVERY) según score final |
| RF-05 | Feedback Loop | Registrar resultado real de pago y alimentar el sistema |
| RF-06 | Reentrenamiento Incremental | Reentrenar o actualizar modelo cuando se acumule suficiente feedback |
| RF-07 | Feature Engineering | Crear features avanzadas de forma consistente entre entrenamiento y predicción |
| RF-08 | Fallback | Si el modelo ML falla o no existe, usar solo reglas |
 
### 2.2 Entradas (Input)
 
**Campos obligatorios:**
- `obligacion_id`
- `dias_vencidos`
- `monto_adeudado`
 
**Campos recomendados:**
- `pct_pagos_on_time`
- `pct_recuperacion_parcial`
- `intentos_contacto_fallidos`
- `dias_desde_ultimo_pago`
- `producto`
- `segmento_cliente`
- `fecha_vencimiento`
- `cliente_id`
 
### 2.3 Salidas (Output)
 
```json
{
  "obligacion_id": "CR123456",
  "score_final": 742,
  "score_reglas": 680,
  "score_ml": 810,
  "probabilidad_pago": 78.5,
  "riesgo_incumplimiento": 21.5,
  "segmento": "ORO",
  "model_version": "1.0.0",
  "usando_ml": true,
  "recomendacion": "Contacto preferente + incentivos"
}
```
 
### 2.4 Feedback
 
- `obligacion_id`
- `pago_realizado` (boolean)
- `monto_pagado`
- `fecha_pago` (opcional)
 
---
 
## 3. Requisitos No Funcionales
 
### 3.1 Rendimiento
- Tiempo de respuesta por predicción ≤ 200ms (percentil 95)
- Capacidad de procesar ≥ 10.000 obligaciones por minuto en batch
- Soporte para batch y real-time
 
### 3.2 Escalabilidad
- Diseñado para manejar millones de registros mensuales
- Soporte horizontal (múltiples instancias)
 
### 3.3 Disponibilidad
- Alta disponibilidad (99.5% uptime)
- Fallback robusto ante fallos del modelo ML
 
### 3.4 Explicabilidad y Auditoría
- Todas las predicciones deben incluir `score_reglas`, `score_ml` y `model_version`
- Logging completo de features usadas
- Posibilidad de explicar predicciones (SHAP - futuro)
 
### 3.5 Configurabilidad
- Pesos del score híbrido configurables
- Umbrales de segmentos configurables
- Parámetros del modelo ajustables
 
---
 
## 4. Requisitos Técnicos
 
### 4.1 Tecnologías
- **Lenguaje:** Python 3.10+
- **Framework API:** FastAPI
- **Modelo ML:** LightGBM
- **Datos:** Pandas + NumPy
- **Almacenamiento de modelo:** Archivos `.txt` (LightGBM) + MLflow (recomendado)
- **Base de datos (opcional):** PostgreSQL para feedback histórico
 
### 4.2 Arquitectura
- Domain-Driven Design (DDD)
- Capas: Domain, Application, Infrastructure, Interfaces
- Patrón Repository + Service
 
### 4.3 Integraciones
- **Entrada:** Archivo Batch (CSV) o API del Core Bancario (JSON)
- **Salida:** API REST + Webhook (opcional)
- **Feedback:** Endpoint POST `/feedback`
 
---
 
## 5. Requisitos de Datos
 
- Datos históricos mínimos para entrenamiento inicial: **10.000 registros**
- Columnas mínimas requeridas: `target` (1 = pagó en ventana de tiempo, 0 = no pagó)
- Ventana de target recomendada: **Pago en los próximos 30 o 45 días**
- Feature Store o consistencia estricta entre entrenamiento y predicción
 
---
 
## 6. Requisitos de Seguridad y Cumplimiento
 
- Protección de datos personales (Ley de Protección de Datos)
- Logs sin información sensible
- Autenticación y autorización en API (JWT / API Key)
- Rate limiting
- Auditoría de cambios en modelos
 
---
 
## 7. Métricas de Éxito (KPI)
 
### 7.1 Técnicas
- AUC ≥ 0.78 en validación
- KS Statistic ≥ 0.35
- Precision/Recall según umbral de negocio
 
### 7.2 de Negocio
- Incremento en tasa de recuperación vs sistema anterior
- Reducción en costo de cobranza
- % de casos donde ML mejora al score de reglas
 
---
 
## 8. Fases de Implementación Recomendadas
 
1. **Fase 1:** Scoring de reglas + API básica
2. **Fase 2:** Integración LightGBM (modo híbrido)
3. **Fase 3:** Feedback + reentrenamiento incremental
4. **Fase 4:** Explicabilidad (SHAP), MLflow, monitoreo
5. **Fase 5:** Optimización y escalamiento
 
---
 
## 9. Supuestos y Restricciones
 
- Se dispone de datos históricos con resultado de pago
- El equipo de negocio puede definir umbrales y estrategias por segmento
- Se permite un período inicial de "modo sombra" (comparación)