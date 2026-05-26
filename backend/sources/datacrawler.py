"""
sources/datacrawler.py — Fuente de datos Google Flights DataCrawler via RapidAPI.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from config import settings
from sources.base import FlightResult, FlightSource

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


class DataCrawler(FlightSource):
    """
    Cliente para la API Google Flights DataCrawler en RapidAPI.
    Host: google-flights-api1.p.rapidapi.com
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
        date_range_from: Optional[date] = None,
        date_range_to: Optional[date] = None,
    ) -> list[FlightResult]:

        if not settings.RAPIDAPI_KEY:
            logger.error("RAPIDAPI_KEY no configurada — omitiendo búsqueda")
            return []

        route = f"{origin}-{destination}"
        headers = {
            "x-rapidapi-key": settings.RAPIDAPI_KEY,
            "x-rapidapi-host": settings.RAPIDAPI_HOST_DATACRAWLER,
        }
        base_url = f"https://{settings.RAPIDAPI_HOST_DATACRAWLER}"

        range_start = date_range_from or date_out
        range_end = date_range_to or date_out

        params = {
            "departure_id": origin,
            "arrival_id": destination,
            "start_date": _fmt_date(range_start),
            "end_date": _fmt_date(range_end),
            "currency": currency,
            "travel_class": "ECONOMY",
            "adults": adults,
        }
        if trip_type == "roundtrip":
            params["trip_type"] = "ROUND"
            if date_back:
                params["trip_days"] = max((date_back - date_out).days, 1)
            else:
                params["trip_days"] = 14
        else:
            params["trip_type"] = "ONE_WAY"

        logger.info("DataCrawler getPriceGraph → %s rango %s a %s", route, range_start, range_end)

        results = []
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{base_url}/api/v1/getCalendarPicker",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict) and "data" in data:
                    items = data["data"]

                if items:
                    items_sorted = sorted(
                        items,
                        key=lambda x: float(x.get("price", float("inf"))),
                    )
                    for item in items_sorted[:3]:
                        price = float(item.get("price", 0))
                        if price <= 0:
                            continue

                        day_str = item.get("departure", _fmt_date(date_out))
                        try:
                            best_date = date.fromisoformat(day_str)
                        except Exception:
                            best_date = date_out

                        d_back = None
                        ret_str = item.get("return")
                        if ret_str:
                            try:
                                d_back = date.fromisoformat(ret_str)
                            except Exception:
                                pass
                        elif trip_type == "roundtrip" and date_back:
                            d_back = best_date + timedelta(days=params.get("trip_days", 14))

                        if date_range_to and best_date > date_range_to:
                            continue

                        results.append(
                            FlightResult(
                                route=route,
                                price=price,
                                currency=currency,
                                date_out=best_date,
                                date_back=d_back,
                                trip_type=trip_type,
                                source="datacrawler",
                            )
                        )
                else:
                    logger.info("DataCrawler: sin datos, intentando searchFlights")
                    fallback_params = {
                        "departure_id": origin,
                        "arrival_id": destination,
                        "outbound_date": _fmt_date(date_out),
                        "currency": currency,
                        "travel_class": "ECONOMY",
                        "adults": adults,
                    }
                    if trip_type == "roundtrip" and date_back:
                        fallback_params["return_date"] = _fmt_date(date_back)

                    resp_fb = await client.get(
                        f"{base_url}/api/v1/searchFlights",
                        headers=headers,
                        params=fallback_params,
                    )
                    resp_fb.raise_for_status()
                    data_fb = resp_fb.json()
                    itineraries = (
                        data_fb.get("data", {})
                        .get("itineraries", {})
                        .get("topFlights", [])
                        if isinstance(data_fb, dict)
                        else []
                    )
                    for fl in itineraries[:3]:
                        price = float(fl.get("price", 0))
                        if price > 0:
                            results.append(
                                FlightResult(
                                    route=route,
                                    price=price,
                                    currency=currency,
                                    stops=fl.get("stops", 0),
                                    date_out=date_out,
                                    date_back=date_back,
                                    trip_type=trip_type,
                                    source="datacrawler",
                                )
                            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.error("HTTP 429: DataCrawler (Google Flights) alcanzó el límite de peticiones de RapidAPI.")
            else:
                logger.error("HTTP %s al consultar DataCrawler: %s", exc.response.status_code, exc)
        except httpx.RequestError as exc:
            logger.error("Error de red en DataCrawler: %s", exc)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Error parseando resultado de DataCrawler: %s", exc)

        return results