import asyncio
import json
import logging
import sys
import os
from datetime import date, timedelta

import httpx

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
from config import settings

logging.basicConfig(level=logging.WARNING)  # solo errores de httpx

DATE_OUT  = date.today() + timedelta(days=90)
DATE_BACK = DATE_OUT + timedelta(days=14)
ORIGIN    = "CCS"
DEST      = "BCN"
CURRENCY  = "EUR"

SEP = "=" * 60

print(f"\n{SEP}")
print(f" DIAGNOSTICO RAW -- {ORIGIN}->{DEST}")
print(f" Salida: {DATE_OUT} | Vuelta: {DATE_BACK}")
print(f"{SEP}\n")


async def test_skyscrapper():
    print("[1] SKYSCRAPPER")
    url = f"https://{settings.RAPIDAPI_HOST}/flights/search-roundtrip"
    params = {
        "fromEntityId": ORIGIN,
        "toEntityId":   DEST,
        "departDate":   DATE_OUT.strftime("%Y-%m-%d"),
        "returnDate":   DATE_BACK.strftime("%Y-%m-%d"),
        "adults":       1,
        "currency":     CURRENCY,
        "market":       "ES",
        "locale":       "es-ES",
    }
    headers = {
        "x-rapidapi-key":  settings.RAPIDAPI_KEY,
        "x-rapidapi-host": settings.RAPIDAPI_HOST,
    }
    print(f"  URL    : {url}")
    print(f"  Params : {params}")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
    print(f"  Status : {resp.status_code}")
    try:
        data = resp.json()
        itineraries = data.get("data", {}).get("itineraries", [])
        print(f"  Itinerarios: {len(itineraries)}")
        if itineraries:
            print("  Primeros 2:")
            print(json.dumps(itineraries[:2], indent=2, ensure_ascii=False))
        else:
            print("  Respuesta completa (no hay itinerarios):")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
    except Exception as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw text: {resp.text[:2000]}")
    print()


async def test_matan_endpoint(label, method, path, payload=None, params=None):
    print(f"[{label}] MATAN -- {method} {path}")
    host = settings.RAPIDAPI_HOST_MATAN
    url  = f"https://{host}{path}"
    headers = {
        "x-rapidapi-key":  settings.RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "content-type":    "application/json",
    }
    print(f"  URL : {url}")
    if payload:
        print(f"  Body: {payload}")
    if params:
        print(f"  Params: {params}")
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "POST":
            resp = await client.post(url, headers=headers, json=payload)
        else:
            resp = await client.get(url, headers=headers, params=params)
    print(f"  Status: {resp.status_code}")
    try:
        data = resp.json()
        if isinstance(data, list):
            print(f"  Lista de {len(data)} items. Primeros 2:")
            print(json.dumps(data[:2], indent=2, ensure_ascii=False)[:3000])
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
    except Exception as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw: {resp.text[:2000]}")
    print()


async def test_datacrawler_verbose():
    print("[5] DATACRAWLER -- getPriceGraph rango 30 dias")
    host = settings.RAPIDAPI_HOST_DATACRAWLER
    url  = f"https://{host}/api/v1/getPriceGraph"
    range_start = date.today() + timedelta(days=60)
    range_end   = date.today() + timedelta(days=90)
    params = {
        "departure_id":  ORIGIN,
        "arrival_id":    DEST,
        "outbound_date": range_start.strftime("%Y-%m-%d"),
        "start_date":    range_start.strftime("%Y-%m-%d"),
        "end_date":      range_end.strftime("%Y-%m-%d"),
        "return_date":   DATE_BACK.strftime("%Y-%m-%d"),
        "currency":      CURRENCY,
        "travel_class":  "ECONOMY",
        "adults":        1,
    }
    headers = {
        "x-rapidapi-key":  settings.RAPIDAPI_KEY,
        "x-rapidapi-host": host,
    }
    print(f"  Rango: {range_start} -> {range_end}")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
    print(f"  Status: {resp.status_code}")
    try:
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        print(f"  Items en rango: {len(items)}")
        if items:
            sorted_items = sorted(items, key=lambda x: float(x.get("price", 9999)))
            print("  Top 3 mas baratos:")
            print(json.dumps(sorted_items[:3], indent=2, ensure_ascii=False))
        else:
            print("  Raw:")
            print(json.dumps(data, indent=2)[:2000])
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  Raw: {resp.text[:2000]}")
    print()


async def main():
    base_payload = {
        "from_airport":   ORIGIN,
        "to_airport":     DEST,
        "departure_date": DATE_OUT.strftime("%Y-%m-%d"),
        "return_date":    DATE_BACK.strftime("%Y-%m-%d"),
        "currency":       CURRENCY,
        "max_stops":      2,
        "sort_type":      "Price",
        "limit":          5,
    }
    base_params = {
        "from_airport":   ORIGIN,
        "to_airport":     DEST,
        "departure_date": DATE_OUT.strftime("%Y-%m-%d"),
        "return_date":    DATE_BACK.strftime("%Y-%m-%d"),
        "currency":       CURRENCY,
        "trip_type":      "roundtrip",
        "adults":         1,
    }

    await test_skyscrapper()
    await test_matan_endpoint("2", "POST", "/",         payload=base_payload)
    await test_matan_endpoint("3", "GET",  "/search",   params=base_params)
    await test_matan_endpoint("4", "GET",  "/flights",  params=base_params)
    await test_matan_endpoint("5", "POST", "/roundtrip", payload=base_payload)
    await test_datacrawler_verbose()

if __name__ == "__main__":
    asyncio.run(main())
