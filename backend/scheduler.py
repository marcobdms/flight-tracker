"""
scheduler.py — APScheduler: 3 búsquedas automáticas por día (08:00, 14:00, 20:00).

Cambios:
- Siempre busca roundtrip (date_back siempre presente).
- Acumula resultados de TODAS las rutas antes de notificar.
- Envía UN solo mensaje de WhatsApp y UN solo email al finalizar todas las rutas.
- Umbral de alerta solo aplica a rutas intercontinentales (ej. CCS-BCN, CCS-MAD).
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
from core.notifier import (
    _is_intercontinental,
    _send_email_digest,
    send_whatsapp_digest,
)
from core.price_tracker import check_price, save_price_record, save_search_run
from db.database import SessionLocal
from db.models import AlertConfig

logger = logging.getLogger(__name__)

_TRIP_DURATION_DAYS = 14


def _sample_dates(alert: AlertConfig) -> list[tuple[date, date]]:
    """
    Genera hasta 3 pares (date_out, date_back) para la ruta.
    Siempre devuelve date_back — todas las búsquedas son roundtrip.
    """
    if not alert.date_from or not alert.date_to:
        date_out = date.today() + timedelta(days=90)
        date_back = date_out + timedelta(days=_TRIP_DURATION_DAYS)
        return [(date_out, date_back)]

    total_days = (alert.date_to - alert.date_from).days
    if total_days <= 0:
        d_back = alert.date_from + timedelta(days=_TRIP_DURATION_DAYS)
        return [(alert.date_from, d_back)]

    step = max(total_days // 3, 1)
    dates = []
    for i in range(min(3, total_days + 1)):
        d_out = alert.date_from + timedelta(days=i * step)
        if d_out > alert.date_to:
            break
        d_back = d_out + timedelta(days=_TRIP_DURATION_DAYS)
        # No exceder la fecha límite configurada
        if d_back > alert.date_to:
            d_back = alert.date_to
        dates.append((d_out, d_back))

    return dates if dates else [(alert.date_from, alert.date_from + timedelta(days=_TRIP_DURATION_DAYS))]


async def _run_search_job(progress_queue: Optional[asyncio.Queue] = None) -> None:
    logger.info("═══ Scheduler iniciando búsqueda automática ═══")
    db = SessionLocal()

    async def _emit(msg: str) -> None:
        if progress_queue:
            await progress_queue.put(msg)

    try:
        active_alerts = (
            db.query(AlertConfig).filter(AlertConfig.active == True).all()  # noqa: E712
        )
        if not active_alerts:
            logger.info("No hay rutas activas configuradas — scheduler saliendo")
            await _emit("ERROR: No hay rutas activas configuradas.")
            return

        logger.info("%d ruta(s) activa(s) a procesar", len(active_alerts))
        await _emit(f"Iniciando búsqueda para {len(active_alerts)} ruta(s)...")

        # Acumulador global: [(route_key, top3_results, threshold)]
        all_routes_data: list[tuple[str, list, float]] = []

        for alert in active_alerts:
            route = alert.route_key
            intercontinental = _is_intercontinental(route)

            date_pairs = _sample_dates(alert)
            all_results: list = []

            for idx, (date_out, date_back) in enumerate(date_pairs):
                logger.info(
                    "Buscando %s — ida: %s | vuelta: %s (roundtrip)",
                    route, date_out, date_back,
                )
                await _emit(f"[{route}] Buscando {date_out} → {date_back} (intento {idx + 1}/{len(date_pairs)})...")
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
                    await _emit(f"[{route}] {len(results)} resultados encontrados.")
                except Exception as exc:
                    logger.error("Error en aggregator para %s/%s: %s", route, date_out, exc)
                    await _emit(f"[{route}] ⚠️ Error en búsqueda: {exc}")

                await asyncio.sleep(random.uniform(1.5, 3.0))

            # ── Sin resultados para esta ruta ────────────────────────────────
            if not all_results:
                logger.warning("Sin resultados para %s", route)
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

            # ── Deduplicar: el más barato por fecha de salida ────────────────
            all_results.sort(key=lambda r: r.price)
            seen_dates: set = set()
            unique_results: list = []
            for r in all_results:
                if r.date_out not in seen_dates:
                    seen_dates.add(r.date_out)
                    unique_results.append(r)

            # Rellenar hasta top-3 si hay pocas fechas distintas
            if len(unique_results) < 3:
                for r in all_results:
                    if len(unique_results) >= 3:
                        break
                    if r not in unique_results:
                        unique_results.append(r)

            unique_results.sort(key=lambda r: r.price)
            cheapest = unique_results[0]

            # ── URL de reserva fallback (Skyscanner) ─────────────────────────
            for r in unique_results[:3]:
                if not r.booking_url:
                    o, d = route.split("-")
                    d_out_str = r.date_out.strftime("%y%m%d") if r.date_out else ""
                    if r.date_back:
                        d_back_str = r.date_back.strftime("%y%m%d")
                        r.booking_url = (
                            f"https://www.skyscanner.es/transport/flights/"
                            f"{o.lower()}/{d.lower()}/{d_out_str}/{d_back_str}/"
                        )
                    elif d_out_str:
                        r.booking_url = (
                            f"https://www.skyscanner.es/transport/flights/"
                            f"{o.lower()}/{d.lower()}/{d_out_str}/"
                        )

            logger.info(
                "Ruta %s — %d resultados únicos | mejor: %.0f€ el %s",
                route, len(unique_results), cheapest.price, cheapest.date_out,
            )
            await _emit(f"[{route}] ✓ Mejor precio: {cheapest.price:.0f}€")

            # ── Guardar top-3 en historial ───────────────────────────────────
            for r in unique_results[:3]:
                save_price_record(db, r)

            # ── Registrar si hubo alerta de precio bajo umbral ───────────────
            alert_sent = False
            if intercontinental and check_price(alert, cheapest.price):
                logger.info(
                    "🚨 ALERTA INTERCONTINENTAL: %s a %.0f€ (umbral: %.0f€)",
                    route, cheapest.price, alert.threshold,
                )
                alert_sent = True

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

            # Acumular para el digest final
            all_routes_data.append((route, unique_results[:3], alert.threshold))

            await asyncio.sleep(random.uniform(2.0, 5.0))

        # ════════════════════════════════════════════════════════════════════
        # Enviar UN SOLO mensaje de WhatsApp con todas las rutas
        # ════════════════════════════════════════════════════════════════════
        if settings.NOTIFY_WHATSAPP and all_routes_data:
            try:
                await send_whatsapp_digest(all_routes_data)
            except Exception as exc:
                logger.error("Error enviando WhatsApp digest: %s", exc)

        # ════════════════════════════════════════════════════════════════════
        # Enviar UN SOLO email con todas las rutas (siempre, sin umbral)
        # ════════════════════════════════════════════════════════════════════
        if settings.NOTIFY_EMAIL and all_routes_data:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _send_email_digest, all_routes_data)
            except Exception as exc:
                logger.error("Error enviando email digest: %s", exc)

    finally:
        db.close()
        logger.info("═══ Scheduler: búsqueda finalizada ═══")
        await _emit("DONE")


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