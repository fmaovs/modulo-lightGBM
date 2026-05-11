from pydantic import BaseModel, Field
from typing import Optional


class PredictInput(BaseModel):
    obligacion_id: Optional[str] = None
    dias_vencidos: int = 0
    monto_adeudado: float = 0.0
    pct_pagos_on_time: Optional[float] = None
    pct_recuperacion_parcial: Optional[float] = None
    intentos_contacto_fallidos: Optional[int] = None
    dias_desde_ultimo_pago: Optional[int] = None
    producto: Optional[str] = None
    segmento_cliente: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    cliente_id: Optional[str] = None
    # Si el backend desea forzar uso de ML o reglas, puede indicar True/False.
    prefer_ml: Optional[bool] = None


class PredictOutput(BaseModel):
    obligacion_id: Optional[str]
    score_final: int
    score_reglas: int
    score_ml: int
    probabilidad_pago: float
    riesgo_incumplimiento: float
    segmento: str
    model_version: str
    usando_ml: bool
    recomendacion: str
    # resumen de auditoría (quién calculó, reglas aplicadas) enviado al backend
    audit: Optional[dict] = None


class Feedback(BaseModel):
    obligacion_id: str
    pago_realizado: bool
    monto_pagado: Optional[float] = None
    fecha_pago: Optional[str] = None
