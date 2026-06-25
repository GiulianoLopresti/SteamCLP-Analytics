"""
etl/transform.py
-----------------

Segundo paso del pipeline ETL: toma lo que entrega etl/extract.py (catalogo
crudo + tipo de cambio) y lo transforma en un DataFrame limpio, validado y
con precios convertidos a CLP. No lee archivos ni hace requests: solo recibe
datos en memoria y los devuelve transformados. Quien carga el resultado a la
base de datos final es etl/load.py (tambien Persona B).

Reglas de validacion de esquema:
    - nombre: no puede ser nulo ni vacio. Fila se descarta si lo es.
    - precio_usd: debe ser numerico y no negativo. Si es nulo o invalido,
      se asume 0.0 (juego gratuito) en vez de descartar la fila completa,
      porque varios juegos de Steam son legitimamente gratis.
    - rating: debe estar entre 0 y 10. Fuera de rango se recorta (clip) al
      limite mas cercano, no se descarta la fila.
    - genero: si viene con varios tags separados por coma (ej. "Action,RPG"),
      se usa solo el primero como genero principal, para simplificar los
      graficos del dashboard.

Cada fila descartada o corregida queda registrada en el log, para poder
mostrar evidencia de manejo de errores en la documentacion tecnica.

Uso (normalmente no se corre solo, lo llama run_pipeline.py o load.py):
    python etl/transform.py
"""

import logging
from datetime import datetime, timezone

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

RATING_MIN = 0.0
RATING_MAX = 10.0


def validar_esquema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida tipos y reglas de negocio basicas antes de transformar.
    Descarta filas irrecuperables (sin nombre) y corrige las que se
    pueden corregir (precio nulo, rating fuera de rango), dejando
    registro de cada caso en el log.
    """
    filas_originales = len(df)
    df = df.copy()

    # --- nombre: obligatorio ---
    sin_nombre = df["nombre"].isna() | (df["nombre"].astype(str).str.strip() == "")
    if sin_nombre.any():
        logger.warning(
            "Se descartan %d filas sin nombre de juego (dato irrecuperable).",
            sin_nombre.sum(),
        )
        df = df[~sin_nombre]

    # --- precio_usd: numerico, no negativo, nulo -> 0.0 ---
    df["precio_usd"] = pd.to_numeric(df["precio_usd"], errors="coerce")
    nulos_precio = df["precio_usd"].isna().sum()
    if nulos_precio > 0:
        logger.warning(
            "%d filas con precio invalido o nulo, se asumen como gratuitas (0.0 USD).",
            nulos_precio,
        )
    df["precio_usd"] = df["precio_usd"].fillna(0.0)

    negativos = (df["precio_usd"] < 0).sum()
    if negativos > 0:
        logger.warning("%d filas con precio negativo, se corrigen a 0.0 USD.", negativos)
        df.loc[df["precio_usd"] < 0, "precio_usd"] = 0.0

    # --- rating: numerico, recortado a [0, 10] ---
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    nulos_rating = df["rating"].isna().sum()
    if nulos_rating > 0:
        logger.warning("%d filas sin rating, se deja como NaN (no se grafica para esos juegos).", nulos_rating)

    fuera_de_rango = ((df["rating"] < RATING_MIN) | (df["rating"] > RATING_MAX)).sum()
    if fuera_de_rango > 0:
        logger.warning(
            "%d filas con rating fuera del rango [0, 10], se recortan al limite valido.",
            fuera_de_rango,
        )
        df["rating"] = df["rating"].clip(lower=RATING_MIN, upper=RATING_MAX)

    logger.info(
        "Validacion de esquema completa: %d filas originales -> %d filas validas.",
        filas_originales,
        len(df),
    )
    return df


def simplificar_genero(df: pd.DataFrame) -> pd.DataFrame:
    """
    El CSV trae varios tags por juego (ej. "Action,Strategy"). Para que
    los graficos del dashboard sean legibles, nos quedamos con el primer
    tag como genero principal.
    """
    df = df.copy()
    df["genero"] = (
        df["genero"]
        .fillna("Sin categoria")
        .astype(str)
        .str.split(",")
        .str[0]
        .str.strip()
    )
    df.loc[df["genero"] == "", "genero"] = "Sin categoria"
    return df


def convertir_a_clp(df: pd.DataFrame, valor_clp_por_usd: float) -> pd.DataFrame:
    """Agrega la columna precio_clp usando el tipo de cambio del dia."""
    if valor_clp_por_usd is None or valor_clp_por_usd <= 0:
        raise ValueError(
            f"Tipo de cambio invalido: {valor_clp_por_usd}. "
            "No se puede continuar la conversion sin un valor positivo."
        )

    df = df.copy()
    df["precio_clp"] = (df["precio_usd"] * valor_clp_por_usd).round(0)
    logger.info(
        "Conversion a CLP aplicada con tipo de cambio 1 USD = %.2f CLP.",
        valor_clp_por_usd,
    )
    return df


def transformar(catalogo: pd.DataFrame, tipo_cambio: dict) -> pd.DataFrame:
    """
    Punto de entrada del modulo. Recibe lo que devuelve extract.extraer_todo()
    y entrega el DataFrame final listo para cargar a la base de datos.
    """
    df = validar_esquema(catalogo)
    df = simplificar_genero(df)
    df = convertir_a_clp(df, tipo_cambio["valor_clp_por_usd"])

    df["fecha_carga"] = datetime.now(timezone.utc).isoformat()

    columnas_finales = [
        "nombre", "genero", "desarrollador", "precio_usd",
        "precio_clp", "fecha_lanzamiento", "rating", "fecha_carga",
    ]
    df = df[columnas_finales]

    logger.info("Transformacion completa: %d filas listas para cargar.", len(df))
    return df


if __name__ == "__main__":
    # Modo de prueba manual: simula una extraccion pequena para verificar
    # que el modulo corre de punta a punta sin depender de extract.py.
    catalogo_prueba = pd.DataFrame({
        "nombre": ["Juego A", "Juego B", None, "Juego D"],
        "genero": ["Action,RPG", None, "Indie", "Strategy"],
        "desarrollador": ["Dev A", "Dev B", "Dev C", "Dev D"],
        "precio_usd": [19.99, -5.0, 10.0, None],
        "fecha_lanzamiento": ["2020-01-01", "2021-05-05", "2019-09-09", "2022-03-03"],
        "rating": [8.5, 15.0, 7.0, -2.0],
    })
    tipo_cambio_prueba = {"valor_clp_por_usd": 950.0, "fecha_actualizacion": "prueba"}

    resultado = transformar(catalogo_prueba, tipo_cambio_prueba)
    print(resultado)