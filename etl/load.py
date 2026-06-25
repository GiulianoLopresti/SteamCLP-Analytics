"""
etl/load.py
------------

Tercer y ultimo paso del pipeline ETL: toma el DataFrame ya transformado
(salida de etl/transform.py) y lo carga a la base de datos propia
(data/steamclp.db, tabla juegos_clp), que es la que despues lee el
dashboard.

Este script tambien actua como punto de entrada para correr el pipeline
completo de punta a punta: extract -> transform -> load.

Uso:
    python etl/load.py
"""

import sqlite3
import logging
from pathlib import Path

import pandas as pd

from etl.extract import extraer_todo
from etl.transform import transformar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data") / "steamclp.db"


def cargar_a_base(df: pd.DataFrame, reemplazar: bool = True):
    """
    Carga el DataFrame final a la tabla juegos_clp.

    reemplazar=True borra los datos anteriores antes de cargar los nuevos,
    para que cada corrida del pipeline represente el catalogo completo y
    actualizado (no se van acumulando duplicados de corridas anteriores).
    El historico de tipo de cambio (otra tabla) no se toca aqui: ese se
    sigue acumulando en extract.py, porque ese si queremos que crezca con
    el tiempo.
    """
    if not DB_PATH.exists():
        raise RuntimeError(
            f"No existe {DB_PATH}. Corre primero crear_historico.py "
            "para inicializar la base de datos."
        )

    if df.empty:
        raise ValueError(
            "El DataFrame a cargar esta vacio. No se sobreescribe la base "
            "para no perder los datos de la corrida anterior por error."
        )

    conexion = sqlite3.connect(DB_PATH)
    try:
        if reemplazar:
            conexion.execute("DELETE FROM juegos_clp")
            logger.info("Tabla juegos_clp limpiada antes de la nueva carga.")

        df.to_sql("juegos_clp", conexion, if_exists="append", index=False)
        conexion.commit()
        logger.info("Carga completa: %d filas insertadas en juegos_clp.", len(df))

    except sqlite3.Error as error:
        conexion.rollback()
        logger.error("Error al cargar datos, se revierte la transaccion: %s", error)
        raise

    finally:
        conexion.close()


def correr_pipeline_completo():
    """Ejecuta extract -> transform -> load de punta a punta."""
    logger.info("Iniciando pipeline ETL completo...")

    resultado_extraccion = extraer_todo()
    df_transformado = transformar(
        resultado_extraccion["catalogo"],
        resultado_extraccion["tipo_cambio"],
    )
    cargar_a_base(df_transformado)

    logger.info("Pipeline ETL completo finalizado con exito.")
    return df_transformado


if __name__ == "__main__":
    correr_pipeline_completo()