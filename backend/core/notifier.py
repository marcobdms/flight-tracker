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

def _build_email_html(result: FlightResult, threshold: float) -> str:
    origin_code, dest_code = result.route.split("-")
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 32px; max-width: 560px;
           margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,.1); }}
  .header {{ background: linear-gradient(135deg, #667eea, #764ba2);
             color: #fff; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 24px; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .price-badge {{ font-size: 48px; font-weight: 900; color: #22c55e; text-align: center;
                  margin: 16px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  td {{ padding: 10px 8px; border-bottom: 1px solid #f0f0f0; }}
  td:first-child {{ color: #666; font-size: 13px; width: 130px; }}
  td:last-child {{ font-weight: 600; color: #1a1a1a; }}
  .cta {{ display: block; background: #667eea; color: #fff; text-align: center;
          padding: 16px; border-radius: 8px; text-decoration: none;
          font-weight: 700; font-size: 16px; margin: 24px 0; }}
  .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 16px; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>Vuelo {_city(origin_code)} → {_city(dest_code)}</h1>
    <p style="margin:4px 0 0">¡Por debajo del umbral!</p>
  </div>
  <div class="price-badge">{result.price:.0f} €</div>
  <p style="text-align:center;color:#666;margin-top:-8px">{_trip_label(result)}</p>
  <table>
    <tr><td>Ruta</td><td>{_city(origin_code)} ({origin_code}) → {_city(dest_code)} ({dest_code})</td></tr>
    <tr><td>Aerolínea</td><td>{result.airline or "—"}</td></tr>
    <tr><td>Agente</td><td>{result.agent or "—"}</td></tr>
    <tr><td>Escalas</td><td>{_stops_label(result.stops)}</td></tr>
    <tr><td>Salida</td><td>{_fmt_date(result.date_out)}</td></tr>
    <tr><td>Vuelta</td><td>{_fmt_date(result.date_back)}</td></tr>
    <tr><td>Umbral</td><td>{threshold:.0f} €</td></tr>
  </table>
  {'<a class="cta" href="' + result.booking_url + '">Reservar ahora</a>' if result.booking_url else ''}
  <div class="footer">
    Flight Tracker — Alerta automática<br>
    Encontrado el {_fmt_date(date.today())}
  </div>
</div>
</body>
</html>
"""


def _send_email_sync(result: FlightResult, threshold: float) -> None:
    """Envía el email de alerta (función síncrona, se ejecuta en thread pool)."""
    if not settings.SMTP_USER or not settings.ALERT_RECIPIENT:
        logger.warning("Email no configurado (SMTP_USER o ALERT_RECIPIENT vacíos) — omitido")
        return

    origin_code, dest_code = result.route.split("-")
    subject = (
        f"Vuelo {origin_code} → {dest_code} a {result.price:.0f}€ "
        f"— ¡Por debajo del umbral!"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.ALERT_RECIPIENT

    # Texto plano como fallback
    plain = (
        f"Ruta: {_city(origin_code)} → {_city(dest_code)}\n"
        f"Precio: {result.price:.0f} € {_trip_label(result)}\n"
        f"Aerolínea: {result.airline}\n"
        f"Agente: {result.agent}\n"
        f"Escalas: {_stops_label(result.stops)}\n"
        f"Salida: {_fmt_date(result.date_out)}\n"
        f"Vuelta: {_fmt_date(result.date_back)}\n"
        f"\nReservar: {result.booking_url}\n\n"
        f"Umbral: {threshold:.0f} €\n"
        f"Flight Tracker — Alerta automática"
    )

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(_build_email_html(result, threshold), "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, settings.ALERT_RECIPIENT, msg.as_string())

    logger.info("Email de alerta enviado → %s (%.0f€)", result.route, result.price)


# ─────────────────────────────────────────────────────────────────────────────
# Orquestador principal de alertas
# ─────────────────────────────────────────────────────────────────────────────

async def send_alert(result: FlightResult, threshold: float) -> None:
    """
    Lanza email y/o WhatsApp en paralelo según la configuración NOTIFY_*.
    Llamada por el scheduler y por el endpoint /search/manual cuando el precio
    cae por debajo del umbral.
    """
    tasks = []

    if settings.NOTIFY_EMAIL:
        loop = asyncio.get_event_loop()
        tasks.append(loop.run_in_executor(None, _send_email_sync, result, threshold))

    if settings.NOTIFY_WHATSAPP:
        tasks.append(send_whatsapp_report([result], threshold))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for exc in results:
            if isinstance(exc, Exception):
                logger.error("Error al enviar notificación: %s", exc)
    else:
        logger.warning("Ningún canal de notificación activo (NOTIFY_EMAIL y NOTIFY_WHATSAPP están desactivados)")


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