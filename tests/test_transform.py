"""
tests/test_transform.py
------------------------
Tests del modulo etl/transform.py: validacion de esquema, simplificacion
de genero y conversion a CLP.

Estas pruebas no dependen de red ni de archivos en disco: usan DataFrames
construidos a mano para verificar reglas de negocio especificas, por eso
corren rapido y se pueden ejecutar todas las veces que se quiera.

Uso:
    pytest tests/test_transform.py -v
"""

import pandas as pd
import pytest

from etl.transform import validar_esquema, simplificar_genero, convertir_a_clp, transformar


# --- Tests de validar_esquema -----------------------------------------

def test_descarta_filas_sin_nombre():
    df = pd.DataFrame({
        "nombre": ["Juego A", None, "  ", "Juego D"],
        "precio_usd": [10.0, 10.0, 10.0, 10.0],
        "rating": [8.0, 8.0, 8.0, 8.0],
        "genero": ["Action"] * 4,
    })
    resultado = validar_esquema(df)
    assert len(resultado) == 2
    assert set(resultado["nombre"]) == {"Juego A", "Juego D"}


def test_precio_nulo_se_convierte_en_cero():
    df = pd.DataFrame({
        "nombre": ["Juego A"],
        "precio_usd": [None],
        "rating": [8.0],
        "genero": ["Action"],
    })
    resultado = validar_esquema(df)
    assert resultado["precio_usd"].iloc[0] == 0.0


def test_precio_negativo_se_corrige_a_cero():
    df = pd.DataFrame({
        "nombre": ["Juego A"],
        "precio_usd": [-15.0],
        "rating": [8.0],
        "genero": ["Action"],
    })
    resultado = validar_esquema(df)
    assert resultado["precio_usd"].iloc[0] == 0.0


@pytest.mark.parametrize("rating_original,rating_esperado", [
    (15.0, 10.0),   # por encima del maximo, se recorta a 10
    (-3.0, 0.0),    # por debajo del minimo, se recorta a 0
    (7.5, 7.5),     # dentro de rango, no cambia
])
def test_rating_se_recorta_al_rango_valido(rating_original, rating_esperado):
    df = pd.DataFrame({
        "nombre": ["Juego A"],
        "precio_usd": [10.0],
        "rating": [rating_original],
        "genero": ["Action"],
    })
    resultado = validar_esquema(df)
    assert resultado["rating"].iloc[0] == rating_esperado


# --- Tests de simplificar_genero ----------------------------------------

def test_simplificar_genero_toma_solo_el_primer_tag():
    df = pd.DataFrame({"genero": ["Action,RPG,Adventure"]})
    resultado = simplificar_genero(df)
    assert resultado["genero"].iloc[0] == "Action"


def test_simplificar_genero_nulo_queda_sin_categoria():
    df = pd.DataFrame({"genero": [None]})
    resultado = simplificar_genero(df)
    assert resultado["genero"].iloc[0] == "Sin categoria"


def test_simplificar_genero_vacio_queda_sin_categoria():
    df = pd.DataFrame({"genero": [""]})
    resultado = simplificar_genero(df)
    assert resultado["genero"].iloc[0] == "Sin categoria"


# --- Tests de convertir_a_clp ------------------------------------------

def test_convertir_a_clp_calcula_correctamente():
    df = pd.DataFrame({"precio_usd": [10.0, 0.0, 59.99]})
    resultado = convertir_a_clp(df, valor_clp_por_usd=950.0)
    assert resultado["precio_clp"].iloc[0] == 9500.0
    assert resultado["precio_clp"].iloc[1] == 0.0
    assert resultado["precio_clp"].iloc[2] == pytest.approx(56990.5, abs=1.0)


def test_convertir_a_clp_rechaza_tipo_de_cambio_invalido():
    df = pd.DataFrame({"precio_usd": [10.0]})
    with pytest.raises(ValueError):
        convertir_a_clp(df, valor_clp_por_usd=0)

    with pytest.raises(ValueError):
        convertir_a_clp(df, valor_clp_por_usd=-5)

    with pytest.raises(ValueError):
        convertir_a_clp(df, valor_clp_por_usd=None)


# --- Tests de transformar (integracion de los pasos anteriores) ---------

def test_transformar_produce_columnas_esperadas():
    catalogo = pd.DataFrame({
        "nombre": ["Juego A", "Juego B"],
        "genero": ["Action,RPG", None],
        "desarrollador": ["Dev A", "Dev B"],
        "precio_usd": [10.0, -5.0],
        "fecha_lanzamiento": ["2020-01-01", "2021-05-05"],
        "rating": [8.5, 15.0],
    })
    tipo_cambio = {"valor_clp_por_usd": 950.0, "fecha_actualizacion": "2026-06-25"}

    resultado = transformar(catalogo, tipo_cambio)

    columnas_esperadas = {
        "nombre", "genero", "desarrollador", "precio_usd",
        "precio_clp", "fecha_lanzamiento", "rating", "fecha_carga",
    }
    assert set(resultado.columns) == columnas_esperadas
    assert len(resultado) == 2
    # precio negativo corregido a 0 antes de convertir
    assert resultado.loc[resultado["nombre"] == "Juego B", "precio_clp"].iloc[0] == 0.0
    # rating fuera de rango recortado
    assert resultado.loc[resultado["nombre"] == "Juego B", "rating"].iloc[0] == 10.0
    # genero multiple simplificado al primero
    assert resultado.loc[resultado["nombre"] == "Juego A", "genero"].iloc[0] == "Action"


def test_transformar_descarta_fila_sin_nombre_de_punta_a_punta():
    catalogo = pd.DataFrame({
        "nombre": ["Juego A", None],
        "genero": ["Action", "RPG"],
        "desarrollador": ["Dev A", "Dev B"],
        "precio_usd": [10.0, 20.0],
        "fecha_lanzamiento": ["2020-01-01", "2021-01-01"],
        "rating": [8.0, 7.0],
    })
    tipo_cambio = {"valor_clp_por_usd": 900.0, "fecha_actualizacion": "2026-06-25"}

    resultado = transformar(catalogo, tipo_cambio)
    assert len(resultado) == 1
    assert resultado["nombre"].iloc[0] == "Juego A"