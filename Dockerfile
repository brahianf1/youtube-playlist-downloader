FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de la aplicación
COPY . /app/

# Crear directorios necesarios
RUN mkdir -p /app/downloads /app/logs

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Exponer puerto
EXPOSE 8000

# Comando para iniciar la aplicación
CMD gunicorn --bind 0.0.0.0:8000 app:app