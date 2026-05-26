"""
config.py — Configuración global del proyecto.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path)


class Settings:
    # ── RapidAPI ─────────────────────────────────────────────────
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST: str = os.getenv("RAPIDAPI_HOST", "flights-sky.p.rapidapi.com")
    RAPIDAPI_HOST_DATACRAWLER: str = os.getenv("RAPIDAPI_HOST_DATACRAWLER", "google-flights2.p.rapidapi.com")
    RAPIDAPI_HOST_MATAN: str = os.getenv("RAPIDAPI_HOST_MATAN", "google-flights-live-api.p.rapidapi.com")
    RAPIDAPI_BASE_URL: str = f"https://{os.getenv('RAPIDAPI_HOST', 'flights-sky.p.rapidapi.com')}"

    # ── Email SMTP ───────────────────────────────────────────────
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp-mail.outlook.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    ALERT_RECIPIENT: str = os.getenv("ALERT_RECIPIENT", "")

    # ── WhatsApp / Twilio ────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WA_FROM: str = os.getenv("TWILIO_WA_FROM", "whatsapp:+14155238886")
    WA_RECIPIENT: str = os.getenv("WA_RECIPIENT", "")

    # ── Canales de notificación ──────────────────────────────────
    NOTIFY_EMAIL: bool = os.getenv("NOTIFY_EMAIL", "true").lower() == "true"
    NOTIFY_WHATSAPP: bool = os.getenv("NOTIFY_WHATSAPP", "false").lower() == "true"

    # ── App ──────────────────────────────────────────────────────
    ENV: str = os.getenv("ENV", "development")
    DB_PATH: str = os.getenv("DB_PATH", "./db/flights.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def db_url(self) -> str:
        path = Path(self.DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.resolve()}"


settings = Settings()