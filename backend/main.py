"""
main.py — FastAPI app: monta routers, crea tablas, inicia el scheduler.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.database import create_tables
from routes import alerts, history, search
from scheduler import create_scheduler

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("Flight Tracker arrancando…")
    create_tables()
    logger.info("Base de datos lista: %s", settings.DB_PATH)

    # ── Health Check ─────────────────────────────────────────
    from core.health_check import run_health_check
    logger.info("Corriendo Health Check de APIs antes del scheduler...")
    await run_health_check(notify_on_error=True)

    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Scheduler iniciado (08:00, 14:00, 20:00 Europe/Madrid)")

    yield  # la app está corriendo

    # ── Shutdown ─────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Flight Tracker apagado correctamente")


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Flight Tracker",
    description=(
        "API para monitorizar precios de vuelos y lanzar alertas automáticas "
        "por email y WhatsApp cuando el precio baja del umbral configurado."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — permitimos peticiones desde el frontend (local o Vercel)
frontend_url = settings.FRONTEND_URL.rstrip('/')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(search.router)
app.include_router(alerts.router)
app.include_router(history.router)


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
async def health():
    return {
        "status": "ok",
        "env": settings.ENV,
        "notify_email": settings.NOTIFY_EMAIL,
        "notify_whatsapp": settings.NOTIFY_WHATSAPP,
    }


@app.get("/", tags=["System"], summary="Bienvenida")
async def root():
    return {
        "app": "Flight Tracker",
        "version": "1.0.0",
        "docs": "/docs",
    }
