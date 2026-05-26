"""
seed.py — Carga las rutas del spec en AlertConfig si la tabla está vacía.
Ejecutar una sola vez: python seed.py
"""

from datetime import date

from db.database import create_tables, SessionLocal
from db.models import AlertConfig

ROUTES = [
    # origin  dest   threshold  trip_type   date_from         date_to
    ("CCS",  "MAD",   650.0,   "roundtrip", date(2026, 8, 1), date(2026, 9, 30)),
    ("CCS",  "BCN",   650.0,   "roundtrip", date(2026, 8, 1), date(2026, 9, 30)),
    ("BCN",  "FCO",    80.0,   "oneway",    date(2026, 8, 1), date(2026, 9, 30)),
    ("BCN",  "LIS",    60.0,   "oneway",    date(2026, 8, 1), date(2026, 9, 30)),
    ("BCN",  "AMS",    80.0,   "oneway",    date(2026, 8, 1), date(2026, 9, 30)),
    ("BCN",  "BER",    80.0,   "oneway",    date(2026, 8, 1), date(2026, 9, 30)),
    ("BCN",  "VIE",    70.0,   "oneway",    date(2026, 8, 1), date(2026, 9, 30)),
]


def seed():
    create_tables()
    db = SessionLocal()
    try:
        existing = db.query(AlertConfig).count()
        if existing > 0:
            print(f"Ya hay {existing} alertas en la DB — seed omitido")
            return

        for origin, dest, threshold, trip_type, date_from, date_to in ROUTES:
            alert = AlertConfig(
                origin=origin,
                destination=dest,
                threshold=threshold,
                trip_type=trip_type,
                date_from=date_from,
                date_to=date_to,
                active=True,
            )
            db.add(alert)
            print(f"  ✅  {origin}-{dest}  umbral={threshold}€  ({trip_type})")

        db.commit()
        print(f"\nSeed completado: {len(ROUTES)} rutas cargadas.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
