# Imagen base liviana con Python 3.11
FROM python:3.11-slim

# Evita que Python genere archivos .pyc y fuerza salida de logs sin buffer
# (asi los logs aparecen al instante en docker compose logs, no al final)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Se copian primero solo las dependencias para aprovechar el cache de Docker:
# si el codigo cambia pero requirements.txt no, no se reinstalan paquetes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora se copia el resto del proyecto
COPY . .

# El dashboard escucha en este puerto dentro del contenedor
EXPOSE 8050

# Comando por defecto: levanta el dashboard. El servicio "etl" en
# docker-compose.yml sobreescribe este comando para correr el pipeline
# en vez del dashboard.
CMD ["python", "dashboards/app.py"]