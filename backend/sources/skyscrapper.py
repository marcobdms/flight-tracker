"""
sources/skyscrapper.py — Fuente de datos Sky Scrapper API via RapidAPI.

Implementa FlightSource para búsquedas roundtrip y one-way.
Parsea la estructura JSON de Sky Scrapper:
  data.itineraries[].legs[].segments[].marketingCarrier
  data.itineraries[].pricingOptions[].agents[]
"""

import logging
from datetime import date
from typing import Optional

import httpx

from config import settings
from sources.base import FlightResult, FlightSource

logger = logging.getLogger(__name__)

# Tiempo máximo de espera para la API (en segundos)
_TIMEOUT = 30.0


def _fmt_date(d: date) -> str:
    """Sky Scrapper espera fechas en formato YYYY-MM-DD."""
    return d.strftime("%Y-%m-%d")


def _parse_itineraries(
    itineraries: list,
    route: str,
    trip_type: str,
    date_out: date,
    date_back: Optional[date],
) -> list[FlightResult]:
    """
    Parsea la lista de itinerarios de Sky Scrapper y devuelve FlightResult normalizados.
    Toma el primer agente del primer pricingOption como precio representativo.
    """
    results: list[FlightResult] = []

    for itin in itineraries:
        try:
            # ── Precio ──────────────────────────────────────────────────
            price = 0.0
            agent_name = ""
            booking_url = ""

            # Formato 1: price como objeto directo (nuevo API)
            price_obj = itin.get("price")
            if isinstance(price_obj, dict) and "raw" in price_obj:
                price = float(price_obj["raw"])
            else:
                # Formato 2: pricingOptions (viejo API)
                pricing_options = itin.get("pricingOptions", [])
                if pricing_options:
                    agents = pricing_options[0].get("agents", [])
                    if agents:
                        best_agent = agents[0]
                        price = float(best_agent.get("price", 0))
                        agent_name = best_agent.get("name", "")
                        booking_url = best_agent.get("url", "")

            if price <= 0:
                continue

            # ── Aerolínea y escalas (del primer leg) ─────────────────────
            legs = itin.get("legs", [])
            if not legs:
                continue
            first_leg = legs[0]
            stops = first_leg.get("stopCount", 0)

            # Aerolínea principal: primer segmento del primer leg
            segments = first_leg.get("segments", [])
            if segments:
                carrier = segments[0].get("marketingCarrier", {})
                airline = carrier.get("name", carrier.get("displayCode", ""))
            else:
                airline = ""

            results.append(
                FlightResult(
                    route=route,
                    price=price,
                    currency="EUR",
                    airline=airline,
                    agent=agent_name,
                    booking_url=booking_url,
                    stops=stops,
                    date_out=date_out,
                    date_back=date_back,
                    trip_type=trip_type,
                    source="skyscrapper",
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Error parseando itinerario: %s", exc)
            continue

    return sorted(results, key=lambda r: r.price)


class SkyScrapper(FlightSource):
    """
    Cliente para la Sky Scrapper API en RapidAPI.
    Soporta roundtrip y one-way.
    """

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_out: date,
        date_back: Optional[date] = None,
        trip_type: str = "roundtrip",
        adults: int = 1,
        currency: str = "EUR",
    ) -> list[FlightResult]:

        if not settings.RAPIDAPI_KEY:
            logger.error("RAPIDAPI_KEY no configurada — omitiendo búsqueda")
            return []

        route = f"{origin}-{destination}"

        if trip_type == "roundtrip" and date_back:
            endpoint = "/flights/search-roundtrip"
            params = {
                "fromEntityId": origin,
                "toEntityId": destination,
                "departDate": _fmt_date(date_out),
                "returnDate": _fmt_date(date_back),
                "adults": adults,
                "currency": currency,
                "market": "ES",
                "locale": "es-ES",
            }
        else:
            endpoint = "/flights/search-one-way"
            params = {
                "fromEntityId": origin,
                "toEntityId": destination,
                "departDate": _fmt_date(date_out),
                "adults": adults,
                "currency": currency,
                "market": "ES",
                "locale": "es-ES",
            }

        url = f"{settings.RAPIDAPI_BASE_URL}{endpoint}"
        headers = {
            "x-rapidapi-key": settings.RAPIDAPI_KEY,
            "x-rapidapi-host": settings.RAPIDAPI_HOST,
        }
        logger.info("Sky Scrapper → %s %s", trip_type.upper(), route)

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %s al consultar Sky Scrapper: %s", exc.response.status_code, exc)
            return []
        except httpx.RequestError as exc:
            logger.error("Error de red en Sky Scrapper: %s", exc)
            return []

        itineraries = data.get("data", {}).get("itineraries", [])
        logger.info("Sky Scrapper → %d itinerarios para %s", len(itineraries), route)

        return _parse_itineraries(itineraries, route, trip_type, date_out, date_back)
