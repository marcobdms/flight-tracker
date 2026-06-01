import asyncio
import logging
from datetime import date, timedelta
from db.models import AlertConfig
from core.aggregator import run_all_sources
from scheduler import _sample_dates

# Desactivar logs detallados para no ensuciar la consola
logging.getLogger("sources").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def test_scheduler_logic():
    # Creamos un alert simulado
    alert = AlertConfig(
        id=1,
        origin="CCS",
        destination="BCN",
        trip_type="roundtrip",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
        threshold=650.0
    )
    
    date_pairs = _sample_dates(alert)
    all_results = []
    
    print(f"===========================================================")
    print(f" TESTING: {alert.origin} -> {alert.destination} (Agosto 2026) ")
    print(f"===========================================================")
    
    for date_out, date_back in date_pairs:
        print(f"[*] Buscando fechas: Ida {date_out} -> Vuelta {date_back}")
        results = await run_all_sources(
            alert,
            date_out,
            date_back,
            date_range_from=alert.date_from,
            date_range_to=alert.date_to,
        )
        print(f"    -> Encontrados {len(results)} vuelos")
        all_results.extend(results)

    # Lógica idéntica al scheduler.py para deduplicar
    all_results.sort(key=lambda r: r.price)
    
    seen_dates = set()
    unique_results = []
    for r in all_results:
        if r.date_out not in seen_dates:
            seen_dates.add(r.date_out)
            unique_results.append(r)
            
    if len(unique_results) < 3:
        for r in all_results:
            if len(unique_results) >= 3:
                break
            if r not in unique_results:
                unique_results.append(r)
                
    unique_results.sort(key=lambda r: r.price)
    
    print(f"\n--- LOS 3 VUELOS SELECCIONADOS PARA EL REPORTE ---")
    for i, r in enumerate(unique_results[:3], 1):
        print(f"{i}. Precio: {r.price}€  ({r.trip_type})")
        print(f"   Ida:      {r.date_out}")
        print(f"   Vuelta:   {r.date_back}")
        print(f"   Aerolínea:{r.airline or '—'} | Escalas: {r.stops}")
        print(f"   Fuente:   {r.source}")
        print(f"   URL:      {r.booking_url or '(sin URL)'}")
        print()

if __name__ == '__main__':
    asyncio.run(test_scheduler_logic())
