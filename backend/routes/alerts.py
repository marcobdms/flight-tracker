"""
routes/alerts.py — CRUD completo de AlertConfig.

GET    /alerts          → lista todas las configs
POST   /alerts          → crea nueva alerta
PUT    /alerts/{id}     → edita umbral / activa-desactiva
DELETE /alerts/{id}     → elimina
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import AlertConfig

router = APIRouter(prefix="/alerts", tags=["Alerts"])
logger = logging.getLogger(__name__)


# ─── Pydantic schemas ────────────────────────────────────────────────────────

class AlertConfigIn(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="IATA origen, ej: CCS")
    destination: str = Field(..., min_length=3, max_length=3, description="IATA destino, ej: MAD")
    threshold: float = Field(..., gt=0, description="Umbral de precio en EUR")
    trip_type: str = Field("roundtrip", pattern="^(roundtrip|oneway)$")
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    active: bool = True


class AlertConfigUpdate(BaseModel):
    threshold: Optional[float] = Field(None, gt=0)
    active: Optional[bool] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class AlertConfigOut(BaseModel):
    id: int
    origin: str
    destination: str
    threshold: float
    trip_type: str
    date_from: Optional[date]
    date_to: Optional[date]
    active: bool
    created_at: datetime
    route_key: str

    model_config = {"from_attributes": True}


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[AlertConfigOut], summary="Listar todas las alertas")
def list_alerts(db: Session = Depends(get_db)):
    return db.query(AlertConfig).order_by(AlertConfig.id).all()


@router.post("", response_model=AlertConfigOut, status_code=201, summary="Crear nueva alerta")
def create_alert(payload: AlertConfigIn, db: Session = Depends(get_db)):
    alert = AlertConfig(
        origin=payload.origin.upper(),
        destination=payload.destination.upper(),
        threshold=payload.threshold,
        trip_type=payload.trip_type,
        date_from=payload.date_from,
        date_to=payload.date_to,
        active=payload.active,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("Nueva alerta creada: %s umbral=%.0f€", alert.route_key, alert.threshold)
    return alert


@router.put("/{alert_id}", response_model=AlertConfigOut, summary="Actualizar alerta")
def update_alert(alert_id: int, payload: AlertConfigUpdate, db: Session = Depends(get_db)):
    alert = db.get(AlertConfig, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alerta {alert_id} no encontrada")

    if payload.threshold is not None:
        alert.threshold = payload.threshold
    if payload.active is not None:
        alert.active = payload.active
    if payload.date_from is not None:
        alert.date_from = payload.date_from
    if payload.date_to is not None:
        alert.date_to = payload.date_to

    db.commit()
    db.refresh(alert)
    logger.info("Alerta %d actualizada: %s umbral=%.0f€ active=%s", alert_id, alert.route_key, alert.threshold, alert.active)
    return alert


@router.delete("/{alert_id}", status_code=204, summary="Eliminar alerta")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(AlertConfig, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alerta {alert_id} no encontrada")
    db.delete(alert)
    db.commit()
    logger.info("Alerta %d eliminada (%s)", alert_id, alert.route_key)
