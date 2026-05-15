# Guía de Integración Backend: BankVision IA

Este documento describe los componentes necesarios en el Backend (Java/Spring Boot) para la correcta comunicación y paridad lógica con el Microservicio de IA.

## 1. Endpoints Requeridos (REST API)

El backend debe exponer los siguientes endpoints para que la IA consuma la configuración dinámica.

### A. Modelo Activo
*   **Endpoint**: `GET /api/scoring/config/models/active`
*   **Descripción**: Retorna la versión del modelo que debe usarse para el cálculo de reglas.
*   **Response esperado**:
    ```json
    {
      "id": 1,
      "modelVersion": "v1.0",
      "description": "Modelo Estándar 2025",
      "segmentationThresholds": {
        "PLATINO": 800,
        "ORO": 650,
        "PLATA": 500,
        "BRONCE": 300,
        "RECOVERY": 0
      },
      "recommendations": {
        "PLATINO": "Mantenimiento preventivo",
        "ORO": "Contacto regular",
        "BRONCE": "Acción inmediata requerida"
      }
    }
    ```

### B. Variables del Modelo
*   **Endpoint**: `GET /api/scoring/config/models/{version}/variables`
*   **Descripción**: Lista las variables paramétricas y sus pesos.
*   **Response esperado**:
    ```json
    [
      { "variableKey": "DAYS_PAST_DUE", "weight": 0.40 },
      { "variableKey": "AMOUNT_DUE", "weight": 0.20 },
      { "variableKey": "SENIORITY", "weight": 0.10 }
    ]
    ```

### C. Rangos por Variable
*   **Endpoint**: `GET /api/scoring/config/models/{version}/variables/{key}/ranges`
*   **Descripción**: Retorna los rangos de valores y el `baseScore` asociado para una variable.
*   **Response esperado**:
    ```json
    [
      { "minValue": 0, "maxValue": 30, "baseScore": 1000 },
      { "minValue": 31, "maxValue": 90, "baseScore": 500 }
    ]
    ```

### D. Registro de Auditoría
*   **Endpoint**: `POST /api/scoring/audit`
*   **Descripción**: Recibe el detalle del cálculo realizado por la IA para persistencia y auditoría.
*   **Payload**: Objeto JSON con `score_final`, `engine_used`, y `rules_details`.

## 2. Servicios Java Sugeridos

Para garantizar la paridad, se recomienda que el Backend implemente:

1.  **ScoringConfigService**: Encargado de gestionar las entidades `ScoringModel`, `ScoringVariable` y `ScoringRange`.
2.  **NativeScoringEngine**: (Opcional) Motor espejo en Java que use la misma lógica de cálculo: `Σ (BaseScore * Weight) / Σ Weight`.
3.  **IAIntegrationClient**: Cliente Feign o RestTemplate para enviar el payload a la IA (`POST /predict`).

## 3. Matriz de Paridad de Datos

| Variable IA | Campo Backend | Lógica de Normalización |
| :--- | :--- | :--- |
| `dias_vencidos` | `DAYS_PAST_DUE` | Máximo de días de mora entre obligaciones. |
| `monto_adeudado` | `AMOUNT_DUE` | Suma total de saldos pendientes. |
| `seniority_days` | `SENIORITY` | Días entre `fecha_creacion_cliente` y `hoy`. |
| `default_frequency` | `DEFAULT_FREQUENCY` | Conteo de productos con mora > 0. |

## 4. Flujo de Control
1.  El Backend recibe una solicitud de scoring.
2.  El Backend normaliza los datos del cliente.
3.  El Backend decide si prefiere ML (`prefer_ml: true`).
4.  El Backend llama a la IA enviando el JSON.
5.  La IA responde, y el Backend persiste el resultado y el log de auditoría.
