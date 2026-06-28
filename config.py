"""
config.py
---------
Configuracion centralizada del proyecto, leida desde variables de entorno.

Todos los scripts (crear_historico.py, etl/extract.py, etl/load.py,
dashboards/app.py) importan sus rutas y parametros desde aqui, en vez de
tener cada uno su propio Path("data")/"..." hardcodeado. Esto es lo que
permite que docker-compose.yml configure el proyecto desde afuera sin
tocar codigo (variable de entorno -> .env -> aqui -> resto del proyecto).

Si existe un archivo .env en la raiz del proyecto, sus valores se cargan
automaticamente. Si una variable no esta definida ni en el entorno ni en
.env, se usa el valor por defecto indicado en cada os.getenv().

Variables soportadas (ver .env.example para una plantilla lista para copiar):
    CSV_PATH            ruta al CSV del catalogo de Steam
    DB_PATH             ruta a la base de datos SQLite del proyecto
    EXCHANGE_API_URL    URL de la API de tipo de cambio
    API_REINTENTOS      cantidad de reintentos si la API falla
    API_ESPERA_SEGUNDOS segundos de espera entre reintentos
    DASHBOARD_PORT      puerto en el que corre el dashboard
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Busca un archivo .env en la raiz del proyecto y carga sus valores al
# entorno. Si no existe el archivo, no pasa nada: se usan los defaults.
load_dotenv()

CSV_PATH = Path(os.getenv("CSV_PATH", "data/SteamGames.csv"))
DB_PATH = Path(os.getenv("DB_PATH", "data/steamclp.db"))

EXCHANGE_API_URL = os.getenv("EXCHANGE_API_URL", "https://open.er-api.com/v6/latest/USD")
API_REINTENTOS = int(os.getenv("API_REINTENTOS", "3"))
API_ESPERA_SEGUNDOS = int(os.getenv("API_ESPERA_SEGUNDOS", "2"))

DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8050"))