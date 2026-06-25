"""
crear_historico.py
-------------------
Responsable: Persona A

Inicializa la base de datos propia del proyecto (SQLite). Esta base NO es
una de las tres fuentes externas: es la fuente transaccional propia del
equipo, donde se va guardando un snapshot del tipo de cambio cada vez que
corre el pipeline. Con el tiempo esto genera un historico real, propio del
proyecto, que el dashboard puede usar para graficar la evolucion del dolar.

Se corre una sola vez al inicio del proyecto (o cada vez que se quiera
reiniciar la base desde cero).

Uso:
    python crear_historico.py
"""

import sqlite3
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data") / "steamclp.db"


def crear_base():
    """Crea las tablas iniciales de la base propia si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()

    # Tabla 1: historico de tipo de cambio (la fuente "propia" del proyecto)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_tipo_cambio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_consulta TEXT NOT NULL,
            valor_clp_por_usd REAL NOT NULL,
            fuente TEXT NOT NULL DEFAULT 'open.er-api.com'
        )
    """)

    # Tabla 2: catalogo de juegos ya transformado (lo llena etl/load.py despues)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS juegos_clp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            genero TEXT,
            desarrollador TEXT,
            precio_usd REAL,
            precio_clp REAL,
            fecha_lanzamiento TEXT,
            rating REAL,
            fecha_carga TEXT NOT NULL
        )
    """)

    conexion.commit()
    conexion.close()
    logger.info("Base de datos propia creada/verificada en: %s", DB_PATH)


if __name__ == "__main__":
    crear_base()