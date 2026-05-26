"""
sources/base.py — Clase abstracta FlightSource e interfaz común FlightResult.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class FlightResult:
    """Resultado normalizado de cualquier fuente de datos."""

    route: str                               # "CCS-MAD"
    price: float                             # EUR
    currency: str = "EUR"
    airline: str = ""
    agent: str = ""
    booking_url: str = ""
    stops: int = 0
    date_out: Optional[date] = None
    date_back: Optional[date] = None
    trip_type: str = "roundtrip"
    source: str = "unknown"
    price_level: Optional[str] = None       # "low"|"typical"|"high" — solo Matan


class FlightSource(ABC):
    """Interfaz común para todas las fuentes de precios de vuelos."""

    @abstractmethod
    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_out: date,
        date_back: Optional[date] = None,
        trip_type: str = "roundtrip",
        adults: int = 1,
        currency: str = "EUR",
    ) -> list["FlightResult"]:
        ...