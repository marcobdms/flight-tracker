"""
core/notifier.py — Envío de alertas por Email (SMTP Outlook) y WhatsApp (Twilio).

Canales controlados por NOTIFY_EMAIL y NOTIFY_WHATSAPP en .env.
Lanza ambos canales en paralelo si están activos.
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
}


def _city(code: str) -> str:
    return _IATA_NAMES.get(code.upper(), code.upper())


def _fmt_date(d: Optional[date]) -> str:
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
# Email SMTP
# ─────────────────────────────────────────────────────────────────────────────

def _build_email_html_multi(results: list[FlightResult], threshold: float) -> str:
    first = results[0]
    origin_code, dest_code = first.route.split("-")

    rows = ""
    for i, r in enumerate(results, 1):
        level_badge = (
            '<span style="background:#22c55e;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;margin-left:6px">PRECIO BAJO</span>'
            if r.price_level == "low" else ""
        )
        vuelta_row = (
            f'<tr><td style="padding:2px 8px 2px 0">Vuelta</td>'
            f'<td style="font-weight:600;color:#1a1a1a">{_fmt_date(r.date_back)}</td></tr>'
            if r.date_back else ""
        )
        reservar_btn = (
            f'<a href="{r.booking_url}" style="display:inline-block;margin-top:10px;'
            f'background:#667eea;color:#fff;padding:8px 18px;border-radius:6px;'
            f'text-decoration:none;font-weight:700;font-size:13px">Reservar</a>'
            if r.booking_url else ""
        )
        rows += f"""
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:16px 8px;font-weight:700;font-size:18px;color:#667eea;width:30px;vertical-align:top">{i}.</td>
          <td style="padding:16px 8px">
            <div style="font-size:28px;font-weight:900;color:#22c55e">{r.price:.0f}€{level_badge}</div>
            <div style="color:#666;font-size:13px;margin-top:2px">{_trip_label(r)}</div>
            <table style="margin-top:8px;font-size:13px;color:#666;border-collapse:collapse">
              <tr><td style="padding:2px 8px 2px 0">Aerolínea</td><td style="font-weight:600;color:#1a1a1a">{r.airline or "—"}</td></tr>
              <tr><td style="padding:2px 8px 2px 0">Escalas</td><td style="font-weight:600;color:#1a1a1a">{_stops_label(r.stops)}</td></tr>
              <tr><td style="padding:2px 8px 2px 0">Salida</td><td style="font-weight:600;color:#1a1a1a">{_fmt_date(r.date_out)}</td></tr>
              {vuelta_row}
            </table>
            {reservar_btn}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px}}
  .card{{background:#fff;border-radius:12px;padding:32px;max-width:600px;margin:0 auto;box-shadow:0 4px 20px rgba(0,0,0,.1)}}
  .header{{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border-radius:8px;padding:20px;text-align:center;margin-bottom:24px}}
  .footer{{text-align:center;color:#999;font-size:12px;margin-top:20px}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1 style="margin:0;font-size:22px">{_city(origin_code)} → {_city(dest_code)}</h1>
    <p style="margin:6px 0 0;opacity:.85">Mejores precios encontrados · umbral {threshold:.0f}€</p>
  </div>
  <table style="width:100%;border-collapse:collapse">{rows}</table>
  <div class="footer">Flight Tracker — {_fmt_date(date.today())}</div>
</div>
</body>
</html>"""


def _send_email_sync(results_or_result, threshold: float) -> None:
    if not settings.SMTP_USER or not settings.ALERT_RECIPIENT:
        logger.warning("Email no configurado — omitido")
        return

    results = results_or_result if isinstance(results_or_result, list) else [results_or_result]
    if not results:
        return

    first = results[0]
    origin_code, dest_code = first.route.split("-")

    subject = f"Vuelo {origin_code} → {dest_code} a {first.price:.0f}€ — ¡Por debajo del umbral!"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.ALERT_RECIPIENT

    plain_lines = [
        f"Flight Tracker — Alerta de precio\n",
        f"Ruta: {_city(origin_code)} ({origin_code}) → {_city(dest_code)} ({dest_code})\n",
    ]
    for i, r in enumerate(results, 1):
        plain_lines.append(
            f"\n{i}. {r.price:.0f}€ {_trip_label(r)}\n"
            f"   Aerolinea: {r.airline or '—'}\n"
            f"   Escalas: {_stops_label(r.stops)}\n"
            f"   Salida: {_fmt_date(r.date_out)}\n"
            f"   Vuelta: {_fmt_date(r.date_back)}\n"
            f"   Reservar: {r.booking_url or '—'}\n"
        )
    plain_lines.append(f"\nUmbral configurado: {threshold:.0f}€")

    msg.attach(MIMEText("".join(plain_lines), "plain", "utf-8"))
    msg.attach(MIMEText(_build_email_html_multi(results, threshold), "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, settings.ALERT_RECIPIENT, msg.as_string())

    logger.info("Email enviado → %s (%.0f€)", first.route, first.price)


async def send_alert(result: FlightResult, threshold: float) -> None:
    """
    Kept for backwards compatibility — solo envía email.
    El scheduler llama _send_email_sync directamente con la lista completa.
    """
    if not settings.NOTIFY_EMAIL:
        return
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _send_email_sync, result, threshold)
    except Exception as exc:
        logger.error("Error al enviar email: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp via Twilio
# ─────────────────────────────────────────────────────────────────────────────

async def send_whatsapp_report(results: list[FlightResult], threshold: float) -> None:
    """
    Envía reporte de WhatsApp con los top-3 vuelos encontrados.
    Se llama SIEMPRE que el scheduler ejecuta, sin importar el precio.
    """
    if not results:
        return

    loop = asyncio.get_event_loop()
    top3 = results[:3]
    origin_code, dest_code = top3[0].route.split("-")

    medals = ["1", "2", "3"]
    lines = [f"*Flight Tracker — Reporte {top3[0].route}*\n"]
    for i, r in enumerate(top3):
        medal = medals[i] if i < 3 else "-"
        price_tag = f"*{r.price:.0f}€*"
        level_tag = " ✅ PRECIO BAJO" if r.price_level == "low" else ""
        airline_tag = r.airline or "—"
        stops_tag = "Directo" if r.stops == 0 else f"{r.stops} escala(s)"
        date_tag = f"{_fmt_date(r.date_out)}" + (f" → {_fmt_date(r.date_back)}" if r.date_back else "")
        lines.append(
            f"{medal}. {price_tag}{level_tag}\n"
            f"   {airline_tag} · {stops_tag}\n"
            f"   {date_tag}\n"
        )

    lines.append(f"\nUmbral alerta email: {threshold:.0f}€")
    body = "\n".join(lines)

    await loop.run_in_executor(None, _send_whatsapp_body, body)


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
        logger.error("twilio no instalado")
        return

    client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        from_=settings.TWILIO_WA_FROM,
        to=settings.WA_RECIPIENT,
        body=body,
    )
    logger.info("WhatsApp reporte enviado SID=%s", message.sid)