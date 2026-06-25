# Imagen base liviana con Python 3.11
FROM python:3.11-slim

# Evita que Python genere archivos .pyc y fuerza salida de logs sin buffer
# (asi los logs aparecen al instante en docker compose logs, no al final)
ENV PYTHONDONTWRITEBYTECODE=1