"""
tests/test_load.py
--------------------
Tests del modulo etl/load.py: carga a la base de datos.

Estas pruebas usan una base de datos SQLite temporal (no la base real del
proyecto), para no depender ni interferir con data/steamclp.db. El fixture
base_de_datos_temporal reemplaza DB_PATH del modulo etl.load durante cada
test y lo restaura al terminar.

Uso:
    pytest tests/test_load.py -v
"""

import sqlite3

import pandas as pd
import pytest

import etl.load as modulo_load
from etl.load import cargar_a_base


@pytest.fixture
def base_de_datos_temporal(tmp_path, monkeypatch):
    """
    Crea una base de datos SQLite vacia con la tabla juegos_clp, en un
    archivo temporal, y hace que etl.load la use en vez de la base real
    durante el test.
    """
    ruta_temporal = tmp_path / "steamclp_test.db"

    conexion = sqlite3.connect(ruta_temporal)
    conexion.execute("""
        CREATE TABLE juegos_clp (
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

    monkeypatch.setattr(modulo_load, "DB_PATH", ruta_temporal)
    return ruta_temporal


def _df_de_prueba() -> pd.DataFrame:
    return pd.DataFrame({
        "nombre": ["Juego A", "Juego B"],
        "genero": ["Action", "RPG"],
        "desarrollador": ["Dev A", "Dev B"],
        "precio_usd": [10.0, 20.0],
        "precio_clp": [9500.0, 19000.0],
        "fecha_lanzamiento": ["2020-01-01", "2021-01-01"],
        "rating": [8.0, 7.5],
        "fecha_carga": ["2026-06-25T00:00:00", "2026-06-25T00:00:00"],
    })


def test_cargar_a_base_inserta_filas(base_de_datos_temporal):
    cargar_a_base(_df_de_prueba())

    conexion = sqlite3.connect(base_de_datos_temporal)
    resultado = pd.read_sql("SELECT * FROM juegos_clp", conexion)
    conexion.close()

    assert len(resultado) == 2
    assert set(resultado["nombre"]) == {"Juego A", "Juego B"}


def test_cargar_a_base_reemplaza_en_vez_de_acumular(base_de_datos_temporal):
    cargar_a_base(_df_de_prueba())
    cargar_a_base(_df_de_prueba().head(1))  # segunda corrida, solo 1 fila

    conexion = sqlite3.connect(base_de_datos_temporal)
    resultado = pd.read_sql("SELECT * FROM juegos_clp", conexion)
    conexion.close()

    # Si reemplazara mal, habria 3 filas (2 + 1). Debe haber solo 1.
    assert len(resultado) == 1


def test_cargar_a_base_rechaza_dataframe_vacio(base_de_datos_temporal):
    with pytest.raises(ValueError):
        cargar_a_base(pd.DataFrame())


def test_cargar_a_base_falla_si_no_existe_la_base(tmp_path, monkeypatch):
    ruta_inexistente = tmp_path / "no_existe.db"
    monkeypatch.setattr(modulo_load, "DB_PATH", ruta_inexistente)

    with pytest.raises(RuntimeError):
        cargar_a_base(_df_de_prueba())