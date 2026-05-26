"""
sources/matan.py — Fuente de datos Google Flights Live API (Matan Rabi) via RapidAPI.
"""

import logging
from datetime import date
from typing import Optional

import httpx

from config import settings
from sources.base import FlightResult, FlightSource

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


class Matan(FlightSource):

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
        headers = {
            "x-rapidapi-key": settings.RAPIDAPI_KEY,
            "x-rapidapi-host": settings.RAPIDAPI_HOST_MATAN,
            "content-type": "application/json",
        }
        base_url = f"https://{settings.RAPIDAPI_HOST_MATAN}"

        payload = {
            "from_airport": origin,
            "to_airport": destination,
            "departure_date": _fmt_date(date_out),
            "currency": currency,
            "max_stops": 2,
            "sort_type": "Price",
            "limit": 10,
        }

        if trip_type == "roundtrip" and date_back:
            endpoint = "/api/google_flights/roundtrip/v1"
            payload["return_date"] = _fmt_date(date_back)
        else:
            endpoint = "/api/google_flights/oneway/v1"

        logger.info("Matan → %s %s", trip_type.upper(), route)

        results = []
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{base_url}{endpoint}",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    for item in data:
                        price = float(item.get("total_price_as_number", 0))
                        if price <= 0:
                            continue
                        results.append(
                            FlightResult(
                                route=route,
                                price=price,
                                currency=currency,
                                airline=item.get("departure_flight_airline", ""),
                                booking_url=item.get("buy_link", ""),
                                stops=item.get("total_stops", 0),
                                date_out=date_out,
                                date_back=date_back,
                                trip_type=trip_type,
                                source="matan",
                                price_level=item.get("price_range_in_relation_to_other_periods"),
                            )
                        )

        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %s al consultar Matan: %s", exc.response.status_code, exc)
        except httpx.RequestError as exc:
            logger.error("Error de red en Matan: %s", exc)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Error parseando resultado de Matan: %s", exc)

        return sorted(results, key=lambda r: r.price)