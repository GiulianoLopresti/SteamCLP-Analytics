"""
etl/extract.py
---------------
Primer paso del pipeline ETL: extraer las tres fuentes de datos en crudo,
sin transformar nada todavia. Eso lo hace etl/transform.py despues (Persona B).

Las tres fuentes son:
    1. CSV estatico (catalogo de Steam, descargado de Kaggle)
    2. API REST (tipo de cambio USD -> CLP, open.er-api.com)
    3. Base de datos propia (historico_tipo_cambio, creada por crear_historico.py)

Este script no decide nombres de columnas "a ciegas": lee el CSV real y
normaliza los encabezados (minusculas, sin espacios) para no romperse si
el archivo de Kaggle trae mayusculas o espacios distintos a los esperados.

Uso:
    python etl/extract.py
"""

import sqlite3
import logging
import time
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

CSV_PATH = Path("data") / "SteamGames.csv"
DB_PATH = Path("data") / "steamclp.db"
API_URL = "https://open.er-api.com/v6/latest/USD"

# Columnas que esperamos encontrar en el CSV (en formato normalizado),
# segun SteamGames_cleaned.csv de Kaggle. Si cambian de dataset o el CSV
# trae nombres distintos, se ajusta este mapeo, no el resto del pipeline.
COLUMNAS_ESPERADAS = ["name", "tags", "developers", "price_numeric", "releasedate", "reviewscore"]

# Mapeo de columnas reales del CSV -> nombres internos que usa el resto
# del pipeline (transform.py y load.py trabajan con estos nombres internos).
MAPEO_COLUMNAS = {
    "name": "nombre",
    "tags": "genero",
    "developers": "desarrollador",
    "price_numeric": "precio_usd",
    "releasedate": "fecha_lanzamiento",
    "reviewscore": "rating",
}


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Pasa todos los encabezados a minusculas y sin espacios extra."""
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def extraer_csv() -> pd.DataFrame:
    """Lee el catalogo de Steam desde el CSV de Kaggle."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro {CSV_PATH}. Descarga SteamGames.csv desde Kaggle "
            "y guardalo en la carpeta data/."
        )

    df = pd.read_csv(CSV_PATH)
    df = normalizar_columnas(df)

    columnas_faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
    if columnas_faltantes:
        logger.warning(
            "El CSV no tiene estas columnas esperadas: %s. "
            "Columnas reales encontradas: %s. "
            "Revisa COLUMNAS_ESPERADAS y MAPEO_COLUMNAS en este script si es necesario.",
            columnas_faltantes,
            list(df.columns),
        )

    # Nos quedamos solo con las columnas que de verdad usa el proyecto y
    # las renombramos a nombres internos, para que transform.py y load.py
    # no dependan de los nombres exactos del CSV de Kaggle.
    columnas_disponibles = [c for c in COLUMNAS_ESPERADAS if c in df.columns]
    df = df[columnas_disponibles].rename(columns=MAPEO_COLUMNAS)

    logger.info("CSV extraido: %d filas, %d columnas utiles.", len(df), len(df.columns))
    return df


def extraer_tipo_cambio(reintentos: int = 3, espera_segundos: int = 2) -> dict:
    """
    Consulta la API de tipo de cambio (USD -> todas las monedas, incluye CLP).
    Reintenta si falla la conexion antes de rendirse.
    """
    for intento in range(1, reintentos + 1):
        try:
            respuesta = requests.get(API_URL, timeout=10)
            respuesta.raise_for_status()
            data = respuesta.json()

            if data.get("result") != "success":
                raise ValueError(f"La API no devolvio 'success': {data}")

            valor_clp = data["rates"]["CLP"]
            logger.info(
                "Tipo de cambio obtenido: 1 USD = %.2f CLP (actualizado: %s)",
                valor_clp,
                data.get("time_last_update_utc"),
            )
            return {
                "valor_clp_por_usd": valor_clp,
                "fecha_actualizacion": data.get("time_last_update_utc"),
            }

        except (requests.RequestException, ValueError, KeyError) as error:
            logger.warning(
                "Intento %d/%d fallo al consultar la API: %s", intento, reintentos, error
            )
            if intento < reintentos:
                time.sleep(espera_segundos)

    # Si todos los intentos fallan, se usa el ultimo valor guardado en la
    # base propia como respaldo, en vez de detener todo el pipeline.
    logger.error("No se pudo consultar la API tras %d intentos. Usando respaldo local.", reintentos)
    return extraer_respaldo_local()


def extraer_respaldo_local() -> dict:
    """Recupera el ultimo tipo de cambio guardado en la base propia, por si la API falla."""
    if not DB_PATH.exists():
        raise RuntimeError(
            "No hay base de datos propia para usar como respaldo. "
            "Corre primero crear_historico.py."
        )

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT valor_clp_por_usd, fecha_consulta FROM historico_tipo_cambio "
        "ORDER BY id DESC LIMIT 1"
    )
    fila = cursor.fetchone()
    conexion.close()

    if fila is None:
        raise RuntimeError(
            "La API fallo y no hay ningun registro previo en la base propia. "
            "No se puede continuar sin un tipo de cambio."
        )

    logger.info("Respaldo local usado: 1 USD = %.2f CLP (guardado el %s)", fila[0], fila[1])
    return {"valor_clp_por_usd": fila[0], "fecha_actualizacion": fila[1]}


def guardar_snapshot_tipo_cambio(info_cambio: dict):
    """Guarda el valor consultado en la base propia, para tener historico real."""
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO historico_tipo_cambio (fecha_consulta, valor_clp_por_usd, fuente) "
        "VALUES (?, ?, ?)",
        (info_cambio["fecha_actualizacion"], info_cambio["valor_clp_por_usd"], "open.er-api.com"),
    )
    conexion.commit()
    conexion.close()
    logger.info("Snapshot del tipo de cambio guardado en la base propia.")


def extraer_todo() -> dict:
    """Punto de entrada: extrae las tres fuentes y devuelve todo junto."""
    catalogo = extraer_csv()
    tipo_cambio = extraer_tipo_cambio()
    guardar_snapshot_tipo_cambio(tipo_cambio)

    return {
        "catalogo": catalogo,
        "tipo_cambio": tipo_cambio,
    }


if __name__ == "__main__":
    resultado = extraer_todo()
    print(f"\nResumen de extraccion:")
    print(f"  Juegos en catalogo: {len(resultado['catalogo'])}")
    print(f"  Tipo de cambio: 1 USD = {resultado['tipo_cambio']['valor_clp_por_usd']} CLP")