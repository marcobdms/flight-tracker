"""
core/aggregator.py — Combina y deduplica resultados de todas las fuentes.
"""

import asyncio
import logging
from datetime import date
from typing import Optional

from db.models import AlertConfig
from sources.base import FlightResult
from sources.datacrawler import DataCrawler
from sources.matan import Matan
from sources.skyscrapper import SkyScrapper

logger = logging.getLogger(__name__)

# Fuentes que operan sobre una fecha puntual (no tienen soporte de rango)
_POINT_SOURCES = [SkyScrapper, Matan]


async def run_all_sources(
    alert: AlertConfig,
    date_out: date,
    date_back: Optional[date] = None,
    date_range_from: Optional[date] = None,
    date_range_to: Optional[date] = None,
) -> list[FlightResult]:

    dc_source = DataCrawler()
    other_sources = [Matan(), SkyScrapper()]

    # DataCrawler recibe el rango completo — siempre roundtrip
    dc_task = dc_source.search_flights(
        origin=alert.origin,
        destination=alert.destination,
        date_out=date_out,
        date_back=date_back,
        trip_type="roundtrip",
        date_range_from=date_range_from,
        date_range_to=date_range_to,
    )

    # Matan y Skyscanner reciben fecha puntual — siempre roundtrip
    other_tasks = [
        s.search_flights(
            origin=alert.origin,
            destination=alert.destination,
            date_out=date_out,
            date_back=date_back,
            trip_type="roundtrip",
        )
        for s in other_sources
    ]

    all_tasks = [dc_task] + other_tasks
    results_per_source = await asyncio.gather(*all_tasks, return_exceptions=True)

    combined: list[FlightResult] = []
    for idx, result in enumerate(results_per_source):
        if isinstance(result, Exception):
            logger.error("Fuente %d falló: %s", idx, result)
        else:
            combined.extend(result)

    seen: set[tuple] = set()
    unique: list[FlightResult] = []
    for r in combined:
        key = (r.route, r.price, r.airline, r.date_out)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    unique.sort(key=lambda r: r.price)
    logger.info("Aggregator → %d resultados únicos para %s-%s", len(unique), alert.origin, alert.destination)
    return unique


async def run_point_sources(
    alert: AlertConfig,
    date_out: date,
    date_back: Optional[date] = None,
) -> list[FlightResult]:
    """
    Ejecuta solo las fuentes de fecha puntual (SkyScrapper, Matan) para
    una fecha concreta. Usar en iteraciones adicionales donde DataCrawler
    ya fue consultado con el rango completo en la primera iteracion.
    """
    sources = [cls() for cls in _POINT_SOURCES]
    tasks = [
        s.search_flights(
            origin=alert.origin,
            destination=alert.destination,
            date_out=date_out,
            date_back=date_back,
            trip_type="roundtrip",  # siempre roundtrip
        )
        for s in sources
    ]
    results_per_source = await asyncio.gather(*tasks, return_exceptions=True)

    combined: list[FlightResult] = []
    for idx, result in enumerate(results_per_source):
        if isinstance(result, Exception):
            logger.error("Fuente puntual %d fallo: %s", idx, result)
        else:
            combined.extend(result)

    logger.info(
        "Fuentes puntuales -> %d resultados para %s-%s en %s",
        len(combined), alert.origin, alert.destination, date_out,
    )
    return combined