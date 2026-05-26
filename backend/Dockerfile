# Dockerfile — backend Flight Tracker
FROM python:3.11-slim

# Variable de entorno para que Python no escriba .pyc y no bufferice stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias primero (caching de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Crear directorio de la DB (montado como volumen en Coolify)
RUN mkdir -p /app/data

# Puerto de la API
EXPOSE 8000

# Arrancar: seed + uvicorn
CMD ["sh", "-c", "python seed.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
