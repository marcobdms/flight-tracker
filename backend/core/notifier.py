"""
core/notifier.py — Envío de alertas por Email (SMTP Outlook) y WhatsApp (Twilio).

Canales controlados por NOTIFY_EMAIL y NOTIFY_WHATSAPP en .env.
- send_whatsapp_digest() → UN solo mensaje de WhatsApp con todas las rutas.
- _send_email_digest()   → UN solo email con todas las rutas.
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import settings
from sources.base import FlightResult

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers de formato
# ─────────────────────────────────────────────────────────────────────────────

_IATA_NAMES = {
    "CCS": "Caracas",
    "MAD": "Madrid",
    "BCN": "Barcelona",
    "FCO": "Roma (Fiumicino)",
    "CIA": "Roma (Ciampino)",
    "LIS": "Lisboa",
    "AMS": "Ámsterdam",
    "BER": "Berlín",
    "VIE": "Viena",
    "MIA": "Miami",
    "JFK": "Nueva York",
    "BOG": "Bogotá",
    "GRU": "São Paulo",
    "EZE": "Buenos Aires",
}

# Códigos IATA que definen una ruta como intercontinental (fuera de Europa)
_INTERCONTINENTAL = {"CCS", "BOG", "MIA", "JFK", "GRU", "EZE", "MEX", "SCL", "LIM"}


def _city(code: str) -> str:
    return _IATA_NAMES.get(code.upper(), code.upper())


def _is_intercontinental(route: str) -> bool:
    """Devuelve True si algún extremo de la ruta es un aeropuerto no europeo."""
    return any(p.upper() in _INTERCONTINENTAL for p in route.split("-"))


def _fmt_date(d: Optional[date]) -> str:
    if d is None:
        return "—"
    months_es = [
        "", "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic",
    ]
    return f"{d.day} {months_es[d.month]}"


def _fmt_date_long(d: Optional[date]) -> str:
    if d is None:
        return "—"
    months_es = [
        "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{d.day} de {months_es[d.month]} de {d.year}"


def _trip_label(result: FlightResult) -> str:
    return "ida y vuelta" if result.trip_type == "roundtrip" else "solo ida"


def _stops_label(stops: int) -> str:
    if stops == 0:
        return "Directo"
    return f"{stops} escala{'s' if stops > 1 else ''}"


# ─────────────────────────────────────────────────────────────────────────────
# DIGEST — Un solo mensaje de WhatsApp con todas las rutas
# ─────────────────────────────────────────────────────────────────────────────

def _build_whatsapp_digest(
    routes_data: list[tuple[str, list[FlightResult], float]],
) -> str:
    """Construye el cuerpo de texto para el mensaje único de WhatsApp."""
    today_str = _fmt_date_long(date.today())
    lines = [f"✈️ *Flight Tracker — {today_str}*\n"]

    medals = ["1️⃣", "2️⃣", "3️⃣"]
    sep = "━" * 22

    for route, results, threshold in routes_data:
        if not results:
            continue

        origin_code, dest_code = route.split("-")
        intercontinental = _is_intercontinental(route)

        header = f"📍 *{origin_code} → {dest_code}*"
        if intercontinental:
            header += f"  |  Umbral: {threshold:.0f}€"

        lines.append(sep)
        lines.append(header)
        lines.append(sep)

        for i, r in enumerate(results[:3]):
            medal = medals[i] if i < 3 else f"{i + 1}."
            price_tag = f"*{r.price:.0f}€*"

            # Badge de precio bajo solo para intercontinentales
            level_tag = ""
            if intercontinental and r.price_level == "low":
                level_tag = " ✅ PRECIO BAJO"

            airline_tag = r.airline or "—"
            stops_tag = "Directo" if r.stops == 0 else f"{r.stops} escala(s)"

            date_line = _fmt_date(r.date_out)
            if r.date_back:
                date_line += f" → {_fmt_date(r.date_back)}"

            entry = (
                f"{medal} {price_tag}{level_tag} — {airline_tag} · {stops_tag}\n"
                f"   📅 {date_line}"
            )
            if r.booking_url:
                entry += f"\n   🔗 {r.booking_url}"

            lines.append(entry)

        lines.append("")

    # Twilio WhatsApp tiene límite de ~1600 chars — truncar con aviso si hace falta
    body = "\n".join(lines)
    if len(body) > 1550:
        body = body[:1500] + "\n\n_(mensaje truncado — ver email para detalles)_"

    return body


async def send_whatsapp_digest(
    routes_data: list[tuple[str, list[FlightResult], float]],
) -> None:
    """Envía UN solo mensaje de WhatsApp con todas las rutas."""
    if not routes_data:
        return

    loop = asyncio.get_event_loop()
    body = _build_whatsapp_digest(routes_data)
    logger.debug("WhatsApp digest (%d chars):\n%s", len(body), body)
    await loop.run_in_executor(None, _send_whatsapp_body, body)


# ─────────────────────────────────────────────────────────────────────────────
# DIGEST — Un solo email con todas las rutas
# ─────────────────────────────────────────────────────────────────────────────

def _build_email_html_digest(
    routes_data: list[tuple[str, list[FlightResult], float]],
) -> str:
    """Construye el HTML completo del email de digest con todas las rutas."""
    all_sections = ""

    for route, results, threshold in routes_data:
        if not results:
            continue

        origin_code, dest_code = route.split("-")
        intercontinental = _is_intercontinental(route)

        rows = ""
        for i, r in enumerate(results, 1):
            level_badge = ""
            if intercontinental and r.price_level == "low":
                level_badge = (
                    '<span style="background:#22c55e;color:#fff;padding:2px 8px;'
                    'border-radius:4px;font-size:11px;margin-left:8px">PRECIO BAJO</span>'
                )

            vuelta_row = ""
            if r.date_back:
                vuelta_row = (
                    f'<tr><td style="padding:2px 8px 2px 0;color:#888">Vuelta</td>'
                    f'<td style="font-weight:600;color:#1a1a1a">{_fmt_date_long(r.date_back)}</td></tr>'
                )

            reservar_btn = ""
            if r.booking_url:
                reservar_btn = (
                    f'<a href="{r.booking_url}" style="display:inline-block;margin-top:10px;'
                    f'background:#667eea;color:#fff;padding:8px 20px;border-radius:6px;'
                    f'text-decoration:none;font-weight:700;font-size:13px">Reservar →</a>'
                )

            rows += f"""
          <tr style="border-bottom:1px solid #f0f0f0">
            <td style="padding:16px 8px;font-weight:700;font-size:18px;color:#667eea;width:28px;vertical-align:top">{i}.</td>
            <td style="padding:16px 8px">
              <div style="font-size:30px;font-weight:900;color:#22c55e;line-height:1">{r.price:.0f}€{level_badge}</div>
              <div style="color:#888;font-size:12px;margin-top:2px">{_trip_label(r)}</div>
              <table style="margin-top:8px;font-size:13px;color:#888;border-collapse:collapse">
                <tr><td style="padding:2px 8px 2px 0">Aerolínea</td><td style="font-weight:600;color:#1a1a1a">{r.airline or "—"}</td></tr>
                <tr><td style="padding:2px 8px 2px 0">Escalas</td><td style="font-weight:600;color:#1a1a1a">{_stops_label(r.stops)}</td></tr>
                <tr><td style="padding:2px 8px 2px 0">Salida</td><td style="font-weight:600;color:#1a1a1a">{_fmt_date_long(r.date_out)}</td></tr>
                {vuelta_row}
              </table>
              {reservar_btn}
            </td>
          </tr>"""

        threshold_note = f" · umbral {threshold:.0f}€" if intercontinental else ""

        all_sections += f"""
  <div style="margin-bottom:36px">
    <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;
                border-radius:8px;padding:16px 24px;margin-bottom:0">
      <h2 style="margin:0;font-size:20px;font-weight:800">{_city(origin_code)} → {_city(dest_code)}</h2>
      <p style="margin:4px 0 0;opacity:.8;font-size:13px">
        {origin_code} → {dest_code}{threshold_note}
      </p>
    </div>
    <table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-top:none;
                  border-radius:0 0 8px 8px;overflow:hidden">{rows}
    </table>
  </div>"""

    today_str = _fmt_date_long(date.today())
    n = len([r for r, res, _ in routes_data if res])

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{font-family:Arial,Helvetica,sans-serif;background:#f0f2f5;margin:0;padding:20px}}
  .card{{background:#fff;border-radius:16px;padding:36px;max-width:660px;margin:0 auto;
         box-shadow:0 4px 24px rgba(0,0,0,.08)}}
  .footer{{text-align:center;color:#bbb;font-size:12px;margin-top:28px;padding-top:16px;
           border-top:1px solid #f0f0f0}}
</style>
</head>
<body>
<div class="card">
  <div style="text-align:center;margin-bottom:32px">
    <div style="font-size:40px;margin-bottom:8px">✈️</div>
    <h1 style="margin:0;font-size:26px;font-weight:900;color:#1a1a1a">Flight Tracker</h1>
    <p style="color:#888;margin:6px 0 0;font-size:14px">
      Reporte de precios · {today_str} · {n} ruta(s)
    </p>
  </div>
  {all_sections}
  <div class="footer">
    Flight Tracker — generado automáticamente<br>
    Para dejar de recibir estos reportes, desactiva las alertas en la app.
  </div>
</div>
</body>
</html>"""


def _send_email_digest(
    routes_data: list[tuple[str, list[FlightResult], float]],
) -> None:
    """Envía UN solo email digest con todas las rutas (síncrono, para run_in_executor)."""
    if not settings.SMTP_USER or not settings.ALERT_RECIPIENT:
        logger.warning("Email no configurado — omitido")
        return

    valid = [(r, res, t) for r, res, t in routes_data if res]
    if not valid:
        return

    n = len(valid)
    today_str = date.today().strftime("%d/%m/%Y")
    subject = f"✈️ Flight Tracker — {n} ruta(s) · {today_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.ALERT_RECIPIENT

    # ── Texto plano (fallback) ──────────────────────────────────────────────
    plain_lines = [f"Flight Tracker — Reporte de vuelos\n{_fmt_date_long(date.today())}\n"]
    for route, results, threshold in valid:
        origin_code, dest_code = route.split("-")
        intercontinental = _is_intercontinental(route)
        plain_lines.append(f"\n{'=' * 42}")
        plain_lines.append(f"{_city(origin_code)} ({origin_code}) → {_city(dest_code)} ({dest_code})")
        if intercontinental:
            plain_lines.append(f"Umbral: {threshold:.0f}€")
        plain_lines.append("")
        for i, r in enumerate(results, 1):
            plain_lines.append(
                f"  {i}. {r.price:.0f}€ — {_trip_label(r)}\n"
                f"     Aerolínea: {r.airline or '—'} · {_stops_label(r.stops)}\n"
                f"     Salida:    {_fmt_date_long(r.date_out)}\n"
                + (f"     Vuelta:    {_fmt_date_long(r.date_back)}\n" if r.date_back else "")
                + (f"     Reservar:  {r.booking_url}\n" if r.booking_url else "")
            )

    msg.attach(MIMEText("\n".join(plain_lines), "plain", "utf-8"))
    msg.attach(MIMEText(_build_email_html_digest(routes_data), "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, settings.ALERT_RECIPIENT, msg.as_string())

    logger.info("✉️  Email digest enviado → %d ruta(s) a %s", n, settings.ALERT_RECIPIENT)


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp via Twilio (transporte bajo nivel)
# ─────────────────────────────────────────────────────────────────────────────

def _send_whatsapp_body(body: str) -> None:
    """Envía un cuerpo de mensaje WhatsApp via Twilio (síncrono)."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio no configurado — WhatsApp omitido")
        return
    if not settings.WA_RECIPIENT:
        logger.warning("WA_RECIPIENT no configurado — WhatsApp omitido")
        return
    try:
        from twilio.rest import Client as TwilioClient
    except ImportError:
        logger.error("twilio no instalado — ejecuta: pip install twilio")
        return

    client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        from_=settings.TWILIO_WA_FROM,
        to=settings.WA_RECIPIENT,
        body=body,
    )
    logger.info("📱 WhatsApp enviado SID=%s (%d chars)", message.sid, len(body))


# ─────────────────────────────────────────────────────────────────────────────
# Funciones legacy (backward compatibility — usadas si se llama ruta a ruta)
# ─────────────────────────────────────────────────────────────────────────────

def _build_email_html_multi(results: list[FlightResult], threshold: float) -> str:
    """Construye HTML para una sola ruta (usado en send_alert legacy)."""
    return _build_email_html_digest([(results[0].route, results, threshold)])


def _send_email_sync(results_or_result, threshold: float) -> None:
    """Legacy: envía email para una sola ruta."""
    results = results_or_result if isinstance(results_or_result, list) else [results_or_result]
    if not results:
        return
    _send_email_digest([(results[0].route, results, threshold)])


async def send_alert(result: FlightResult, threshold: float) -> None:
    """Legacy — kept for backwards compatibility."""
    if not settings.NOTIFY_EMAIL:
        return
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _send_email_sync, result, threshold)
    except Exception as exc:
        logger.error("Error al enviar email: %s", exc)


async def send_whatsapp_report(results: list[FlightResult], threshold: float) -> None:
    """Legacy — kept for backwards compatibility."""
    route = results[0].route if results else "??-??"
    await send_whatsapp_digest([(route, results, threshold)])