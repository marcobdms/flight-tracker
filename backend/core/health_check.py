"""
core/health_check.py — Valida que las APIs externas responden
con la estructura esperada. Se ejecuta al arrancar y antes del scheduler.
"""

import asyncio
import logging
from datetime import date, timedelta
import httpx
from config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 20.0
_TEST_DATE = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")


async def _check_skyscrapper() -> dict:
    headers = {
        "x-rapidapi-key": settings.RAPIDAPI_KEY,
        "x-rapidapi-host": settings.RAPIDAPI_HOST,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"https://{settings.RAPIDAPI_HOST}/flights/search-one-way",
                headers=headers,
                params={
                    "fromEntityId": "BCN",
                    "toEntityId": "MAD",
                    "departDate": _TEST_DATE,
                    "currency": "EUR",
                    "adults": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Validar estructura esperada
            itineraries = data.get("data", {}).get("itineraries", [])
            if not itineraries:
                return {"source": "skyscrapper", "status": "warn", "msg": "Respuesta vacía"}

            first = itineraries[0]
            price = first.get("price", {}).get("raw")
            if price is None:
                return {"source": "skyscrapper", "status": "error",
                        "msg": f"Estructura cambiada — campos esperados no encontrados. Keys: {list(first.keys())}"}

            return {"source": "skyscrapper", "status": "ok", "msg": f"precio test: {price}€"}

    except httpx.HTTPStatusError as e:
        return {"source": "skyscrapper", "status": "error", "msg": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"source": "skyscrapper", "status": "error", "msg": str(e)}


async def _check_datacrawler() -> dict:
    headers = {
        "x-rapidapi-key": settings.RAPIDAPI_KEY,
        "x-rapidapi-host": settings.RAPIDAPI_HOST_DATACRAWLER,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"https://{settings.RAPIDAPI_HOST_DATACRAWLER}/api/v1/getPriceGraph",
                headers=headers,
                params={
                    "departure_id": "BCN",
                    "arrival_id": "MAD",
                    "outbound_date": _TEST_DATE,
                    "start_date": _TEST_DATE,
                    "end_date": (date.today() + timedelta(days=120)).strftime("%Y-%m-%d"),
                    "currency": "EUR",
                    "travel_class": "ECONOMY",
                    "adults": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            items = data if isinstance(data, list) else data.get("data", [])
            if not items:
                return {"source": "datacrawler", "status": "warn", "msg": "Sin datos para la ruta test"}

            first = items[0]
            if "price" not in first or "departure" not in first:
                return {"source": "datacrawler", "status": "error",
                        "msg": f"Estructura cambiada. Keys recibidas: {list(first.keys())}"}

            return {"source": "datacrawler", "status": "ok",
                    "msg": f"{len(items)} días, precio mínimo: {min(i['price'] for i in items)}€"}

    except httpx.HTTPStatusError as e:
        return {"source": "datacrawler", "status": "error", "msg": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"source": "datacrawler", "status": "error", "msg": str(e)}


async def _check_matan() -> dict:
    headers = {
        "x-rapidapi-key": settings.RAPIDAPI_KEY,
        "x-rapidapi-host": settings.RAPIDAPI_HOST_MATAN,
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"https://{settings.RAPIDAPI_HOST_MATAN}/oneway",
                headers=headers,
                json={
                    "from_airport": "BCN",
                    "to_airport": "MAD",
                    "departure_date": _TEST_DATE,
                    "currency": "EUR",
                    "max_stops": 2,
                    "sort_type": "Price",
                    "limit": 3,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list) or len(data) == 0:
                return {"source": "matan", "status": "warn", "msg": "Respuesta vacía o formato inesperado"}

            first = data[0]
            price = first.get("total_price_as_number")
            if price is None:
                return {"source": "matan", "status": "error",
                        "msg": f"Estructura cambiada. Keys recibidas: {list(first.keys())}"}

            return {"source": "matan", "status": "ok", "msg": f"precio test: {price}€"}

    except httpx.HTTPStatusError as e:
        return {"source": "matan", "status": "error", "msg": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"source": "matan", "status": "error", "msg": str(e)}


async def run_health_check(notify_on_error: bool = True) -> list[dict]:
    """
    Corre health check de las 3 fuentes en paralelo.
    Si notify_on_error=True y alguna falla, loggea ERROR (el notifier
    puede engancharse aquí para mandar WhatsApp de aviso).
    """
    results = await asyncio.gather(
        _check_skyscrapper(),
        _check_datacrawler(),
        _check_matan(),
    )

    for r in results:
        if r["status"] == "ok":
            logger.info("HEALTH [%s] OK — %s", r["source"], r["msg"])
        elif r["status"] == "warn":
            logger.warning("HEALTH [%s] WARN — %s", r["source"], r["msg"])
        else:
            logger.error("HEALTH [%s] ERROR — %s", r["source"], r["msg"])

    return list(results)
