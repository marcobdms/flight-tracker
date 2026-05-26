# Flight Tracker — Buscador y Alertas de Vuelos Baratos

Tracker personal de precios de vuelos con alertas automáticas por **email** y **WhatsApp**.
Busca en Skyscanner vía Sky Scrapper API (RapidAPI) y alerta cuando un vuelo baja del umbral configurado.

---

## Rutas monitoreadas

| Ruta | Umbral | Tipo |
|------|--------|------|
| CCS → MAD | < 650 € | Ida y vuelta |
| CCS → BCN | < 650 € | Ida y vuelta |
| BCN → Roma (FCO) | < 80 € | Solo ida |
| BCN → Lisboa (LIS) | < 60 € | Solo ida |
| BCN → Ámsterdam (AMS) | < 80 € | Solo ida |
| BCN → Berlín (BER) | < 80 € | Solo ida |
| BCN → Viena (VIE) | < 70 € | Solo ida |

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11 + FastAPI |
| Scheduler | APScheduler 3.x (08:00, 14:00, 20:00) |
| Fuente de datos | Sky Scrapper API via RapidAPI |
| Base de datos | SQLite + SQLAlchemy 2.0 |
| Alertas | SMTP Outlook/Hotmail + WhatsApp (Twilio) |
| Deploy | Hetzner + Coolify + Docker |
| Frontend | React 18 + Vite + Recharts |

---

## Puesta en marcha rápida

### 1. Clonar y configurar variables de entorno

```bash
cp backend/.env.example backend/.env
# Edita backend/.env con tus keys
```

### 2. Backend local (sin Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                  # Carga las 7 rutas en la DB
uvicorn main:app --reload
# → http://localhost:8000/docs
```

### 3. Frontend local

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 4. Docker (producción)

```bash
docker-compose up -d
```

---

## Variables de entorno

Crea `backend/.env` (nunca subir a git):

```env
# Sky Scrapper — RapidAPI
RAPIDAPI_KEY=tu_key_aqui
RAPIDAPI_HOST=flights-sky.p.rapidapi.com

# Email SMTP (Outlook/Hotmail)
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=tucuenta@hotmail.com
SMTP_PASSWORD=tu_app_password
ALERT_RECIPIENT=destino@email.com

# WhatsApp — Twilio Business
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WA_FROM=whatsapp:+14155238886
WA_RECIPIENT=whatsapp:+34612345678

# Canales activos
NOTIFY_EMAIL=true
NOTIFY_WHATSAPP=true

# App
ENV=development
DB_PATH=./db/flights.db
LOG_LEVEL=INFO
```

> **Nota SMTP Hotmail:** Si falla con usuario/contraseña, activa "contraseñas de aplicación"
> en la configuración de seguridad Microsoft (microsoft.com → Cuenta → Seguridad avanzada).

> **Nota WhatsApp Twilio:** En sandbox usa el número `whatsapp:+14155238886`.
> Para producción con tu número WA Business, solicita aprobación en Twilio Console.

---

## API endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/search?origin=CCS&dest=MAD&date_out=2026-08-15` | Búsqueda puntual |
| POST | `/search/manual` | Dispara búsqueda en todas las rutas activas |
| GET | `/alerts` | Lista todas las alertas |
| POST | `/alerts` | Crea nueva alerta |
| PUT | `/alerts/{id}` | Edita umbral / activa-desactiva |
| DELETE | `/alerts/{id}` | Elimina alerta |
| GET | `/history?route=CCS-MAD&days=30` | Historial de precios |
| GET | `/history/runs` | Log de ejecuciones del scheduler |

---

## Arquitectura de notificaciones

```
check_price() → precio < umbral
    │
    ├── NOTIFY_EMAIL=true  → SMTP Outlook (HTML + plain text)
    └── NOTIFY_WHATSAPP=true → Twilio WA Business API
         (ambos en paralelo, errores independientes)
```

---

## Roadmap

- [x] Fase 1: Backend completo (config, DB, sources, core, routes, scheduler)
- [x] Seed de las 7 rutas del spec
- [x] Notificaciones duales: Email + WhatsApp
- [x] Frontend React: RouteCards, PriceChart, AlertForm, RunLog
- [ ] Fase 3: Scraping directo (Iberia, AirEuropa, Vueling)
