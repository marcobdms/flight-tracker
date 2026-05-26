"""
db/models.py — Modelos ORM: PriceRecord, AlertConfig, SearchRun.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import Integer, Float, String, Boolean, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base


class PriceRecord(Base):
    """Cada precio encontrado que sea relevante (bajo umbral o top-3)."""

    __tablename__ = "price_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route: Mapped[str] = mapped_column(String(20), index=True)        # "CCS-MAD"
    price: Mapped[float] = mapped_column(Float)                        # en euros
    currency: Mapped[str] = mapped_column(String(5), default="EUR")
    airline: Mapped[str] = mapped_column(String(100))                  # "Iberia"
    agent: Mapped[str] = mapped_column(String(100))                    # "eDreams"
    booking_url: Mapped[Optional[str]] = mapped_column(Text)           # deep link
    stops: Mapped[int] = mapped_column(Integer, default=0)             # 0=directo
    date_out: Mapped[Optional[date]] = mapped_column(Date)             # salida
    date_back: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    found_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertConfig(Base):
    """Configuración de umbral de precio por ruta."""

    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    origin: Mapped[str] = mapped_column(String(10))                    # "CCS"
    destination: Mapped[str] = mapped_column(String(10))               # "MAD"
    threshold: Mapped[float] = mapped_column(Float)                    # 650.0
    trip_type: Mapped[str] = mapped_column(String(20), default="roundtrip")  # "roundtrip" | "oneway"
    date_from: Mapped[Optional[date]] = mapped_column(Date)
    date_to: Mapped[Optional[date]] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def route_key(self) -> str:
        return f"{self.origin}-{self.destination}"


class SearchRun(Base):
    """Log de cada ejecución del scheduler."""

    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route: Mapped[str] = mapped_column(String(20), index=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    cheapest_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cheapest_booking_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cheapest_date_out: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cheapest_date_back: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cheapest_airline: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cheapest_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="ok")      # "ok"|"error"|"no_results"
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
