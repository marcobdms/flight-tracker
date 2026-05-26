"""
routes/search.py — Endpoints de búsqueda manual de vuelos.

GET  /search           → búsqueda on-demand con parámetros
POST /search/manual    → lanza una búsqueda para todas las rutas activas ya
"""

import asyncio
import logging
import random
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.aggregator import run_all_sources
from core.notifier import send_alert
from core.price_tracker import check_price, save_price_record, save_search_run
from db.database import get_db
from db.models import AlertConfig
from sources.skyscrapper import SkyScrapper

router = APIRouter(prefix="/search", tags=["Search"])
logger = logging.getLogger(__name__)


class FlightResultOut(BaseModel):
    route: str
    price: float
    currency: str
    airline: str
    agent: str
    booking_url: str
    stops: int
    date_out: Optional[date]
    date_back: Optional[date]
    trip_type: str
    source: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[FlightResultOut], summary="Búsqueda on-demand")
async def search_flights(
    origin: str = Query(..., description="IATA de origen, ej: CCS", min_length=3, max_length=3),
    destination: str = Query(..., description="IATA de destino, ej: MAD", min_length=3, max_length=3),
    date_out: date = Query(..., description="Fecha de salida (YYYY-MM-DD)"),
    date_back: Optional[date] = Query(None, description="Fecha de vuelta (YYYY-MM-DD) — omitir para one-way"),
    adults: int = Query(1, ge=1, le=9, description="Número de adultos"),
):
    """Lanza una búsqueda puntual en todas las fuentes activas y devuelve resultados sin guardar."""
    trip_type = "roundtrip" if date_back else "oneway"
    source = SkyScrapper()
    try:
        results = await source.search_flights(
            origin=origin.upper(),
            destination=destination.upper(),
            date_out=date_out,
            date_back=date_back,
            trip_type=trip_type,
            adults=adults,
        )
    except Exception as exc:
        logger.error("Error en búsqueda manual: %s", exc)
        raise HTTPException(status_code=502, detail=f"Error al consultar la API: {exc}")

    return [r.__dict__ for r in results]


class ManualRunResult(BaseModel):
    route: str
    results_count: int
    cheapest_price: Optional[float]
    alert_sent: bool
    status: str


@router.post("/manual", response_model=list[ManualRunResult], summary="Ejecutar búsqueda en todas las rutas activas")
async def manual_search_all(db: Session = Depends(get_db)):
    """
    Dispara inmediatamente una búsqueda para todas las AlertConfig activas,
    exactamente igual que haría el scheduler.
    """
    from scheduler import _run_search_job  # importación diferida para evitar circular

    active = db.query(AlertConfig).filter(AlertConfig.active == True).all()  # noqa: E712
    if not active:
        raise HTTPException(status_code=404, detail="No hay rutas activas configuradas")

    # Ejecutamos el job del scheduler directamente
    await _run_search_job()

    # Devolvemos el resumen de los últimos runs
    from core.price_tracker import get_search_runs
    runs = get_search_runs(db, limit=len(active) * 3)
    return [
        ManualRunResult(
            route=r.route,
            results_count=r.results_count,
            cheapest_price=r.cheapest_price,
            alert_sent=r.alert_sent,
            status=r.status,
        )
        for r in runs[:len(active)]
    ]

@router.get("/stream", summary="Búsqueda manual con eventos SSE")
async def manual_search_stream(db: Session = Depends(get_db)):
    """Ejecuta la búsqueda manual y emite eventos de progreso (SSE)."""
    from scheduler import _run_search_job
    
    active = db.query(AlertConfig).filter(AlertConfig.active == True).all()
    if not active:
        raise HTTPException(status_code=404, detail="No hay rutas activas configuradas")
        
    queue = asyncio.Queue()
    
    async def event_generator():
        # Lanzar tarea en background
        task = asyncio.create_task(_run_search_job(queue))
        
        while True:
            msg = await queue.get()
            if msg == "DONE":
                yield f"data: DONE\n\n"
                break
            elif msg.startswith("ERROR:"):
                yield f"data: {msg}\n\n"
                break
            else:
                yield f"data: {msg}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
