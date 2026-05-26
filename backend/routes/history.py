"""
routes/history.py — Historial de precios y log de ejecuciones.

GET /history             → historial de precios por ruta
GET /history/runs        → log de ejecuciones del scheduler
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.price_tracker import get_price_history, get_search_runs
from db.database import get_db

router = APIRouter(prefix="/history", tags=["History"])


class PriceRecordOut(BaseModel):
    id: int
    route: str
    price: float
    currency: str
    airline: str
    agent: str
    booking_url: Optional[str]
    stops: int
    date_out: Optional[date]
    date_back: Optional[date]
    found_at: datetime

    model_config = {"from_attributes": True}


class SearchRunOut(BaseModel):
    id: int
    route: str
    ran_at: datetime
    results_count: int
    cheapest_price: Optional[float]
    cheapest_booking_url: Optional[str] = None
    cheapest_date_out: Optional[date] = None
    cheapest_date_back: Optional[date] = None
    cheapest_airline: Optional[str] = None
    cheapest_agent: Optional[str] = None
    alert_sent: bool
    status: str
    error_msg: Optional[str]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[PriceRecordOut], summary="Historial de precios por ruta")
def price_history(
    route: str = Query(..., description="Ej: CCS-MAD"),
    days: int = Query(30, ge=1, le=365, description="Número de días hacia atrás"),
    db: Session = Depends(get_db),
):
    return get_price_history(db, route=route.upper(), days=days)


@router.get("/runs", response_model=list[SearchRunOut], summary="Log de ejecuciones del scheduler")
def search_run_log(
    route: Optional[str] = Query(None, description="Filtrar por ruta, ej: CCS-MAD"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return get_search_runs(db, route=route.upper() if route else None, limit=limit)
