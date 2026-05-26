"""
scheduler.py — APScheduler: 3 búsquedas automáticas por día (08:00, 14:00, 20:00).
"""

import asyncio
import logging
import random
from datetime import date, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from core.aggregator import run_all_sources, run_point_sources
from core.notifier import send_alert, send_whatsapp_report
from core.price_tracker import check_price, save_price_record, save_search_run
from db.database import SessionLocal
from db.models import AlertConfig

logger = logging.getLogger(__name__)

_TRIP_DURATION_DAYS = 14


def _sample_dates(alert: AlertConfig) -> list[tuple[date, Optional[date]]]:
    if not alert.date_from or not alert.date_to:
        date_out = date.today() + timedelta(days=90)
        date_back = (
            date_out + timedelta(days=_TRIP_DURATION_DAYS)
            if alert.trip_type == "roundtrip"
            else None
        )
        return [(date_out, date_back)]

    total_days = (alert.date_to - alert.date_from).days
    if total_days <= 0:
        return [(alert.date_from, None)]

    step = max(total_days // 3, 1)
    dates = []
    for i in range(min(3, total_days + 1)):
        d_out = alert.date_from + timedelta(days=i * step)
        if d_out > alert.date_to:
            break
        if alert.trip_type == "roundtrip":
            d_back = d_out + timedelta(days=_TRIP_DURATION_DAYS)
            if d_back > alert.date_to:
                d_back = alert.date_to
        else:
            d_back = None
        dates.append((d_out, d_back))

    return dates if dates else [(alert.date_from, None)]


async def _run_search_job(progress_queue: Optional[asyncio.Queue] = None) -> None:
    logger.info("═══ Scheduler iniciando búsqueda automática ═══")
    db = SessionLocal()

    async def _emit_progress(msg: str):
        if progress_queue:
            await progress_queue.put(msg)

    try:
        active_alerts = (
            db.query(AlertConfig).filter(AlertConfig.active == True).all()  # noqa: E712
        )
        if not active_alerts:
            logger.info("No hay rutas activas configuradas — scheduler saliendo")
            await _emit_progress("ERROR: No hay rutas activas configuradas.")
            return

        logger.info("%d ruta(s) activa(s) a procesar", len(active_alerts))
        await _emit_progress(f"Iniciando búsqueda para {len(active_alerts)} ruta(s)...")

        for alert in active_alerts:
            route = alert.route_key

            # Buscar en los 3 pares de fechas y combinar resultados
            date_pairs = _sample_dates(alert)
            all_results: list = []

            for idx, (date_out, date_back) in enumerate(date_pairs):
                logger.info("Buscando %s — %s → %s", route, date_out, date_back or "one-way")
                await _emit_progress(f"[{route}] Buscando {date_out} (Intento {idx+1}/3)...")
                try:
                    if idx == 0:
                        results = await run_all_sources(
                            alert,
                            date_out,
                            date_back,
                            date_range_from=alert.date_from,
                            date_range_to=alert.date_to,
                        )
                    else:
                        results = await run_point_sources(
                            alert,
                            date_out,
                            date_back,
                        )
                    all_results.extend(results)
                    logger.info("  %d resultados para %s en %s", len(results), route, date_out)
                    await _emit_progress(f"[{route}] {len(results)} resultados encontrados.")
                except Exception as exc:
                    logger.error("Error en aggregator para %s/%s: %s", route, date_out, exc)
                    await _emit_progress(f"[{route}] Error en búsqueda: {exc}")
                await asyncio.sleep(random.uniform(1.5, 3.0))

            if not all_results:
                logger.info("Sin resultados para %s", route)
                save_search_run(
                    db,
                    route=route,
                    results_count=0,
                    cheapest_price=None,
                    alert_sent=False,
                    status="no_results",
                )
                await asyncio.sleep(random.uniform(2.0, 5.0))
                continue

            # Ordenar todos por precio primero
            all_results.sort(key=lambda r: r.price)

            # Extraer el más barato por cada fecha para dar variedad en el reporte
            seen_dates: set = set()
            unique_results: list = []
            for r in all_results:
                if r.date_out not in seen_dates:
                    seen_dates.add(r.date_out)
                    unique_results.append(r)

            # Si de casualidad hay menos de 3 fechas distintas, rellenamos con los siguientes más baratos
            if len(unique_results) < 3:
                for r in all_results:
                    if len(unique_results) >= 3:
                        break
                    if r not in unique_results:
                        unique_results.append(r)

            # Volver a ordenar los 3 finalistas
            unique_results.sort(key=lambda r: r.price)
            cheapest = unique_results[0]
            alert_sent = False
            
            # Generar URL de fallback si la fuente no la provee (ej: datacrawler)
            if not cheapest.booking_url:
                o, d = route.split("-")
                d_out = cheapest.date_out.strftime("%y%m%d") if cheapest.date_out else ""
                if cheapest.date_back:
                    d_back = cheapest.date_back.strftime("%y%m%d")
                    cheapest.booking_url = f"https://www.skyscanner.es/transport/flights/{o.lower()}/{d.lower()}/{d_out}/{d_back}/"
                elif d_out:
                    cheapest.booking_url = f"https://www.skyscanner.es/transport/flights/{o.lower()}/{d.lower()}/{d_out}/"

            logger.info(
                "Total combinado: %d resultados unicos para %s (mejor: %.0f EUR el %s)",
                len(unique_results), route, cheapest.price, cheapest.date_out,
            )
            await _emit_progress(f"[{route}] Mejor precio: {cheapest.price:.0f} EUR")

            # Guardar top-3 en historial
            for r in unique_results[:3]:
                save_price_record(db, r)

            # WhatsApp siempre — top-3 de distintas fechas
            if settings.NOTIFY_WHATSAPP:
                try:
                    await send_whatsapp_report(unique_results[:3], alert.threshold)
                except Exception as exc:
                    logger.error("Error enviando WhatsApp report: %s", exc)

            # Email solo si baja del umbral
            if check_price(alert, cheapest.price):
                logger.info(
                    "ALERTA: %s a %.0f EUR (umbral: %.0f EUR)",
                    route, cheapest.price, alert.threshold,
                )
                try:
                    await send_alert(cheapest, alert.threshold)
                    alert_sent = True
                except Exception as exc:
                    logger.error("Error enviando alerta para %s: %s", route, exc)
            else:
                logger.info(
                    "OK: %s a %.0f EUR — sobre umbral %.0f EUR",
                    route, cheapest.price, alert.threshold,
                )

            save_search_run(
                db,
                route=route,
                results_count=len(unique_results),
                cheapest_price=cheapest.price,
                cheapest_booking_url=cheapest.booking_url,
                cheapest_date_out=cheapest.date_out,
                cheapest_date_back=cheapest.date_back,
                cheapest_airline=cheapest.airline,
                cheapest_agent=cheapest.agent,
                alert_sent=alert_sent,
                status="ok",
            )

            await asyncio.sleep(random.uniform(2.0, 5.0))

    finally:
        db.close()
        logger.info("═══ Scheduler: búsqueda finalizada ═══")
        await _emit_progress("DONE")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Madrid")

    for hour in [8, 14, 20]:
        scheduler.add_job(
            _run_search_job,
            trigger=CronTrigger(hour=hour, minute=0, timezone="Europe/Madrid"),
            id=f"search_job_{hour:02d}h",
            name=f"Búsqueda automática {hour:02d}:00",
            replace_existing=True,
            misfire_grace_time=300,
        )

    logger.info("Scheduler configurado: 08:00, 14:00, 20:00 (Europe/Madrid)")
    return scheduler