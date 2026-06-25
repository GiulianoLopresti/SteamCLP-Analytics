"""
dashboards/app.py
------------------

Dashboard interactivo del proyecto SteamCLP Analytics, construido con Dash.
Lee directamente la base de datos final (data/steamclp.db, generada por
etl/load.py) y la presenta en tres vistas pensadas para audiencias distintas:

    - Ejecutiva: gasto promedio en CLP por genero, precio promedio general,
      cantidad de juegos analizados. Sin jerga tecnica.
    - Tecnica: distribucion de precios, estado de la ultima carga, cantidad
      de filas en la base. Para el profesor / equipo tecnico.
    - Operativa: evolucion del tipo de cambio dia a dia, para detectar
      variaciones relevantes.

No corre el pipeline ETL: asume que ya se corrio (python -m etl.load) y que
la base de datos existe con datos cargados.

Uso:
    python dashboards/app.py
    -> abrir http://localhost:8050 en el navegador
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data") / "steamclp.db"


def cargar_juegos() -> pd.DataFrame:
    """Lee la tabla juegos_clp completa desde la base de datos."""
    if not DB_PATH.exists():
        logger.warning("No existe %s. Devuelvo un DataFrame vacio.", DB_PATH)
        return pd.DataFrame(
            columns=["nombre", "genero", "desarrollador", "precio_usd",
                     "precio_clp", "fecha_lanzamiento", "rating", "fecha_carga"]
        )

    conexion = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM juegos_clp", conexion)
    conexion.close()
    return df


def cargar_historico_cambio() -> pd.DataFrame:
    """Lee el historico de tipo de cambio guardado por extract.py."""
    if not DB_PATH.exists():
        return pd.DataFrame(columns=["fecha_consulta", "valor_clp_por_usd"])

    conexion = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT fecha_consulta, valor_clp_por_usd FROM historico_tipo_cambio "
        "ORDER BY id ASC",
        conexion,
    )
    conexion.close()
    return df


# --- Construccion de figuras, una funcion por grafico para que sean faciles
#     de explicar por separado en la defensa ---

def figura_gasto_por_genero(df: pd.DataFrame):
    """Vista ejecutiva: barras horizontales de precio promedio en CLP por genero."""
    if df.empty:
        return px.bar(title="Sin datos cargados todavia")

    resumen = (
        df.groupby("genero")["precio_clp"]
        .mean()
        .round(0)
        .sort_values(ascending=True)
        .reset_index()
    )
    fig = px.bar(
        resumen,
        x="precio_clp",
        y="genero",
        orientation="h",
        title="Precio promedio en CLP por genero",
        labels={"precio_clp": "Precio promedio (CLP)", "genero": "Genero"},
    )
    return fig


def figura_distribucion_precios(df: pd.DataFrame):
    """Vista tecnica: histograma de la distribucion de precios en CLP."""
    if df.empty:
        return px.histogram(title="Sin datos cargados todavia")

    fig = px.histogram(
        df,
        x="precio_clp",
        nbins=30,
        title="Distribucion de precios (CLP)",
        labels={"precio_clp": "Precio (CLP)"},
    )
    return fig


def figura_evolucion_tipo_cambio(df_cambio: pd.DataFrame):
    """Vista operativa: evolucion del tipo de cambio consultado a lo largo del tiempo."""
    if df_cambio.empty:
        return px.line(title="Sin historico de tipo de cambio todavia")

    fig = px.line(
        df_cambio,
        x="fecha_consulta",
        y="valor_clp_por_usd",
        title="Evolucion del tipo de cambio USD -> CLP",
        labels={"fecha_consulta": "Fecha de consulta", "valor_clp_por_usd": "CLP por USD"},
        markers=True,
    )
    return fig


def construir_app() -> Dash:
    app = Dash(__name__)
    app.title = "SteamCLP Analytics"

    app.layout = html.Div([
        html.H1("SteamCLP Analytics", style={"textAlign": "center"}),
        html.P(
            "Precios de Steam traducidos a pesos chilenos en tiempo real.",
            style={"textAlign": "center", "color": "#555"},
        ),

        dcc.Tabs(id="tabs-vistas", value="ejecutiva", children=[
            dcc.Tab(label="Ejecutiva", value="ejecutiva"),
            dcc.Tab(label="Tecnica", value="tecnica"),
            dcc.Tab(label="Operativa", value="operativa"),
        ]),

        html.Div(id="contenido-vista"),

        dcc.Interval(id="intervalo-actualizacion", interval=60 * 1000, n_intervals=0),
    ])

    @app.callback(
        Output("contenido-vista", "children"),
        Input("tabs-vistas", "value"),
        Input("intervalo-actualizacion", "n_intervals"),
    )
    def actualizar_vista(vista_seleccionada, _n_intervalos):
        df_juegos = cargar_juegos()
        df_cambio = cargar_historico_cambio()

        if df_juegos.empty:
            return html.Div(
                "Todavia no hay datos cargados. Corre primero el pipeline ETL "
                "con: python -m etl.load",
                style={"textAlign": "center", "marginTop": "40px", "color": "#900"},
            )

        if vista_seleccionada == "ejecutiva":
            precio_promedio = round(df_juegos["precio_clp"].mean())
            return html.Div([
                html.Div([
                    html.Div([
                        html.H3(f"${precio_promedio:,.0f}".replace(",", ".")),
                        html.P("Precio promedio en CLP"),
                    ], className="card"),
                    html.Div([
                        html.H3(f"{len(df_juegos):,}".replace(",", ".")),
                        html.P("Juegos analizados"),
                    ], className="card"),
                ], style={"display": "flex", "gap": "20px", "justifyContent": "center", "marginBottom": "20px"}),
                dcc.Graph(figure=figura_gasto_por_genero(df_juegos)),
            ])

        if vista_seleccionada == "tecnica":
            return html.Div([
                html.P(f"Filas en la base de datos: {len(df_juegos)}"),
                html.P(f"Ultima carga registrada: {df_juegos['fecha_carga'].max()}"),
                dcc.Graph(figure=figura_distribucion_precios(df_juegos)),
            ])

        if vista_seleccionada == "operativa":
            if len(df_cambio) >= 2:
                variacion = (
                    (df_cambio["valor_clp_por_usd"].iloc[-1] - df_cambio["valor_clp_por_usd"].iloc[-2])
                    / df_cambio["valor_clp_por_usd"].iloc[-2] * 100
                )
                texto_variacion = f"Variacion respecto a la consulta anterior: {variacion:+.2f}%"
            else:
                texto_variacion = "Aun no hay suficiente historico para calcular variacion."

            return html.Div([
                html.P(texto_variacion),
                dcc.Graph(figure=figura_evolucion_tipo_cambio(df_cambio)),
            ])

        return html.Div("Vista no reconocida.")

    return app


app = construir_app()

if __name__ == "__main__":
    logger.info("Iniciando dashboard en http://localhost:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)