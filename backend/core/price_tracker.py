"""
core/price_tracker.py — Lógica de alertas: check, guardar historial, consultar historial.
"""

import logging
from datetime import datetime, timedelta
import datetime as dt
from typing import Optional

from sqlalchemy.orm import Session

from db.models import AlertConfig, PriceRecord, SearchRun
from sources.base import FlightResult

logger = logging.getLogger(__name__)


def check_price(alert: AlertConfig, price: float) -> bool:
    """Devuelve True si el precio está por debajo del umbral configurado."""
    return price < alert.threshold


def save_price_record(db: Session, result: FlightResult) -> PriceRecord:
    """Persiste un FlightResult como PriceRecord en la base de datos."""
    record = PriceRecord(
        route=result.route,
        price=result.price,
        currency=result.currency,
        airline=result.airline,
        agent=result.agent,
        booking_url=result.booking_url,
        stops=result.stops,
        date_out=result.date_out,
        date_back=result.date_back,
        found_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.debug("PriceRecord guardado: %s %.2f€", result.route, result.price)
    return record


def save_search_run(
    db: Session,
    route: str,
    results_count: int,
    cheapest_price: Optional[float],
    cheapest_booking_url: Optional[str] = None,
    cheapest_date_out: Optional[dt.date] = None,
    cheapest_date_back: Optional[dt.date] = None,
    cheapest_airline: Optional[str] = None,
    cheapest_agent: Optional[str] = None,
    alert_sent: bool = False,
    status: str = "ok",
    error_msg: Optional[str] = None,
) -> SearchRun:
    """Guarda el log de una ejecución del scheduler."""
    run = SearchRun(
        route=route,
        ran_at=datetime.utcnow(),
        results_count=results_count,
        cheapest_price=cheapest_price,
        cheapest_booking_url=cheapest_booking_url,
        cheapest_date_out=cheapest_date_out,
        cheapest_date_back=cheapest_date_back,
        cheapest_airline=cheapest_airline,
        cheapest_agent=cheapest_agent,
        alert_sent=alert_sent,
        status=status,
        error_msg=error_msg,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_price_history(
    db: Session,
    route: str,
    days: int = 30,
) -> list[PriceRecord]:
    """Devuelve el historial de precios de una ruta en los últimos N días."""
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(PriceRecord)
        .filter(PriceRecord.route == route, PriceRecord.found_at >= since)
        .order_by(PriceRecord.found_at.desc())
        .all()
    )


def get_search_runs(
    db: Session,
    route: Optional[str] = None,
    limit: int = 100,
) -> list[SearchRun]:
    """Devuelve el log de ejecuciones, opcionalmente filtrado por ruta."""
    q = db.query(SearchRun)
    if route:
        q = q.filter(SearchRun.route == route)
    return q.order_by(SearchRun.ran_at.desc()).limit(limit).all()
