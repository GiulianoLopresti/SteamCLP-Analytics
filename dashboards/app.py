"""
dashboards/app.py
------------------
Responsable: Persona C

Dashboard interactivo del proyecto SteamCLP Analytics, construido con Dash.
Lee la base de datos final (data/steamclp.db, generada por etl/load.py) y la
presenta en tres vistas pensadas para audiencias distintas: Ejecutiva,
Tecnica y Operativa.

Trabaja unicamente con las columnas que ya produce el pipeline ETL:
nombre, genero, desarrollador, precio_usd, precio_clp, fecha_lanzamiento,
rating, fecha_carga. Las variables adicionales que se ven en los graficos
(decada, sensibilidad al tipo de cambio, etc.) se derivan de esas mismas
columnas, sin tocar el ETL.

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
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data") / "steamclp.db"

# --- Paleta y tipografia del dashboard --------------------------------
# Acento inspirado en el azul caracteristico de Steam, sobre un fondo
# oscuro tipo "panel de control", para que se sienta hecho a medida del
# tema y no una plantilla generica de Dash.
COLOR_FONDO = "#12121f"
COLOR_PANEL = "#1c1c30"
COLOR_TEXTO = "#e7e7f0"
COLOR_TEXTO_SECUNDARIO = "#9494ad"
COLOR_ACENTO = "#66c0f4"       # azul Steam
COLOR_ACENTO_2 = "#a974e8"     # violeta complementario
COLOR_ALERTA_POS = "#5fd98a"
COLOR_ALERTA_NEG = "#f07868"
COLOR_BORDE = "#2c2c45"

PALETA_CATEGORICA = ["#66c0f4", "#a974e8", "#5fd98a", "#f0c868", "#f07868",
                     "#68d6d2", "#e88fc2", "#9ea8f0"]

PLANTILLA_PLOTLY = {
    "layout": {
        "paper_bgcolor": COLOR_PANEL,
        "plot_bgcolor": COLOR_PANEL,
        "font": {"family": "Inter, sans-serif", "color": COLOR_TEXTO, "size": 13},
        "title": {"font": {"family": "Space Grotesk, sans-serif", "size": 16}},
        "xaxis": {"gridcolor": COLOR_BORDE, "zerolinecolor": COLOR_BORDE},
        "yaxis": {"gridcolor": COLOR_BORDE, "zerolinecolor": COLOR_BORDE},
        "colorway": PALETA_CATEGORICA,
        "margin": {"t": 50, "l": 50, "r": 30, "b": 40},
    }
}


# --- Carga de datos -----------------------------------------------------

def cargar_juegos() -> pd.DataFrame:
    """Lee la tabla juegos_clp completa y deriva columnas auxiliares."""
    columnas = ["nombre", "genero", "desarrollador", "precio_usd",
                "precio_clp", "fecha_lanzamiento", "rating", "fecha_carga"]

    if not DB_PATH.exists():
        logger.warning("No existe %s. Devuelvo un DataFrame vacio.", DB_PATH)
        return pd.DataFrame(columns=columnas)

    conexion = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM juegos_clp", conexion)
    conexion.close()

    if df.empty:
        return df

    # Fechas: algunas pueden venir mal formadas en el CSV original, por eso
    # errors="coerce" en vez de dejar que truene todo el dashboard.
    fechas = pd.to_datetime(df["fecha_lanzamiento"], errors="coerce")
    df["anio_lanzamiento"] = fechas.dt.year
    df["decada"] = (df["anio_lanzamiento"] // 10 * 10).astype("Int64").astype(str) + "s"
    df.loc[df["anio_lanzamiento"].isna(), "decada"] = "Sin fecha"

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


def aplicar_estilo(fig: go.Figure, altura: int = 340) -> go.Figure:
    """Aplica la plantilla visual comun a cualquier figura de Plotly."""
    fig.update_layout(template=PLANTILLA_PLOTLY, height=altura,
                       legend={"bgcolor": "rgba(0,0,0,0)"})
    return fig


# --- Vista Ejecutiva ------------------------------------------------------

def fig_precio_por_genero(df: pd.DataFrame, top_n: int = 12) -> go.Figure:
    """
    El dataset real trae muchas etiquetas de genero distintas (decenas),
    asi que graficarlas todas vuelve la barra ilegible. Se muestran los
    top_n generos con mas juegos, y el resto se agrupa en "Otros" para
    no perder informacion silenciosamente.
    """
    generos_frecuentes = df["genero"].value_counts().head(top_n).index
    df_agrupado = df.copy()
    df_agrupado["genero_agrupado"] = df_agrupado["genero"].where(
        df_agrupado["genero"].isin(generos_frecuentes), "Otros"
    )

    resumen = (
        df_agrupado.groupby("genero_agrupado")["precio_clp"].mean().round(0)
        .sort_values(ascending=True).reset_index()
    )
    fig = px.bar(
        resumen, x="precio_clp", y="genero_agrupado", orientation="h",
        title=f"Precio promedio en CLP por genero (top {top_n} mas frecuentes)",
        labels={"precio_clp": "Precio promedio (CLP)", "genero_agrupado": ""},
        color="precio_clp", color_continuous_scale=["#2c2c45", COLOR_ACENTO],
    )
    fig.update_coloraxes(showscale=False)
    return aplicar_estilo(fig, altura=420)


def fig_top_desarrolladores(df: pd.DataFrame) -> go.Figure:
    resumen = df["desarrollador"].value_counts().head(10).sort_values().reset_index()
    resumen.columns = ["desarrollador", "cantidad"]
    fig = px.bar(
        resumen, x="cantidad", y="desarrollador", orientation="h",
        title="Top 10 desarrolladores con mas juegos en el catalogo",
        labels={"cantidad": "Cantidad de juegos", "desarrollador": ""},
        color_discrete_sequence=[COLOR_ACENTO_2],
    )
    return aplicar_estilo(fig)


def fig_precio_vs_rating(df: pd.DataFrame, top_n: int = 8) -> go.Figure:
    generos_frecuentes = df["genero"].value_counts().head(top_n).index
    df_coloreado = df.copy()
    df_coloreado["genero_color"] = df_coloreado["genero"].where(
        df_coloreado["genero"].isin(generos_frecuentes), "Otros"
    )

    fig = px.scatter(
        df_coloreado, x="rating", y="precio_clp", color="genero_color",
        title=f"Precio vs. calificacion (color = top {top_n} generos mas frecuentes)",
        labels={"rating": "Calificacion (0-10)", "precio_clp": "Precio (CLP)", "genero_color": "Genero"},
        opacity=0.7,
        color_discrete_map={"Otros": "#4a4a63"},
        color_discrete_sequence=PALETA_CATEGORICA,
    )
    return aplicar_estilo(fig, altura=400)


def fig_lanzamientos_por_anio(df: pd.DataFrame) -> go.Figure:
    resumen = df.dropna(subset=["anio_lanzamiento"])
    resumen = resumen.groupby("anio_lanzamiento").size().reset_index(name="cantidad")
    fig = px.area(
        resumen, x="anio_lanzamiento", y="cantidad",
        title="Juegos lanzados por anio (catalogo analizado)",
        labels={"anio_lanzamiento": "Anio", "cantidad": "Cantidad de juegos"},
        color_discrete_sequence=[COLOR_ACENTO],
    )
    fig.update_traces(line={"width": 2}, fillcolor="rgba(102, 192, 244, 0.15)")
    return aplicar_estilo(fig)


def construir_vista_ejecutiva(df: pd.DataFrame) -> html.Div:
    precio_promedio = round(df["precio_clp"].mean())
    juego_mas_caro = df.loc[df["precio_clp"].idxmax(), "nombre"]
    precio_max = round(df["precio_clp"].max())
    total_juegos = len(df)
    genero_top = df["genero"].value_counts().idxmax()

    return html.Div([
        html.Div([
            tarjeta_kpi("Precio promedio", f"${precio_promedio:,.0f}".replace(",", "."), "en pesos chilenos, catalogo completo"),
            tarjeta_kpi("Juego mas caro", juego_mas_caro, f"${precio_max:,.0f}".replace(",", ".") + " CLP"),
            tarjeta_kpi("Juegos analizados", f"{total_juegos:,}".replace(",", "."), "en el catalogo cargado"),
            tarjeta_kpi("Genero mas comun", genero_top, "por cantidad de titulos"),
        ], className="fila-kpis"),

        html.Div([
            html.Div([
                dcc.Graph(figure=fig_precio_por_genero(df)),
                html.P("Cada barra es el promedio de precio en CLP de todos los juegos de ese genero. "
                       "Sirve para detectar que tan caro es, en promedio, jugar en cada categoria.",
                       className="texto-apoyo"),
            ], className="panel panel-mitad"),

            html.Div([
                dcc.Graph(figure=fig_top_desarrolladores(df)),
                html.P("Los 10 estudios con mas titulos presentes en el catalogo analizado.",
                       className="texto-apoyo"),
            ], className="panel panel-mitad"),
        ], className="fila-paneles"),

        html.Div([
            dcc.Graph(figure=fig_precio_vs_rating(df)),
            html.P("Cada punto es un juego. Mas arriba significa mas caro, mas a la derecha significa "
                   "mejor calificado. El color indica el genero. Util para detectar si pagar mas "
                   "realmente se traduce en mejor calificacion.",
                   className="texto-apoyo"),
        ], className="panel"),

        html.Div([
            dcc.Graph(figure=fig_lanzamientos_por_anio(df)),
            html.P("Cantidad de juegos del catalogo lanzados cada anio, util para entender que tan "
                   "reciente es el catalogo que se esta analizando.",
                   className="texto-apoyo"),
        ], className="panel"),
    ])


# --- Vista Tecnica ---------------------------------------------------------

def fig_distribucion_precios(df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        df, x="precio_clp", nbins=25,
        title="Distribucion de precios en CLP",
        labels={"precio_clp": "Precio (CLP)", "count": "Cantidad de juegos"},
        color_discrete_sequence=[COLOR_ACENTO],
    )
    return aplicar_estilo(fig)


def fig_distribucion_rating(df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        df, x="rating", nbins=20,
        title="Distribucion de calificaciones",
        labels={"rating": "Calificacion (0-10)", "count": "Cantidad de juegos"},
        color_discrete_sequence=[COLOR_ACENTO_2],
    )
    return aplicar_estilo(fig)


def fig_boxplot_precio_genero(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    generos_frecuentes = df["genero"].value_counts().head(top_n).index
    df_filtrado = df[df["genero"].isin(generos_frecuentes)]

    fig = px.box(
        df_filtrado, x="genero", y="precio_clp",
        title=f"Dispersion de precios por genero (top {top_n} mas frecuentes)",
        labels={"genero": "", "precio_clp": "Precio (CLP)"},
        color="genero", color_discrete_sequence=PALETA_CATEGORICA,
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickangle=-30)
    return aplicar_estilo(fig, altura=400)


def fig_heatmap_genero_decada(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    generos_frecuentes = df["genero"].value_counts().head(top_n).index
    df_filtrado = df[df["genero"].isin(generos_frecuentes)]

    tabla = pd.crosstab(df_filtrado["genero"], df_filtrado["decada"])
    fig = px.imshow(
        tabla, text_auto=True, aspect="auto",
        title=f"Cantidad de juegos por genero y decada (top {top_n} generos)",
        labels={"x": "Decada", "y": "Genero", "color": "Cantidad"},
        color_continuous_scale=["#1c1c30", COLOR_ACENTO],
    )
    return aplicar_estilo(fig, altura=400)


def construir_vista_tecnica(df: pd.DataFrame) -> html.Div:
    nulos_rating = int(df["rating"].isna().sum())
    nulos_anio = int(df["anio_lanzamiento"].isna().sum())

    return html.Div([
        html.Div([
            tarjeta_kpi("Filas en la base", f"{len(df):,}".replace(",", "."), "tabla juegos_clp"),
            tarjeta_kpi("Ultima carga", str(df["fecha_carga"].max())[:19].replace("T", " "), "hora UTC"),
            tarjeta_kpi("Sin rating", str(nulos_rating), "filas con calificacion nula"),
            tarjeta_kpi("Sin fecha valida", str(nulos_anio), "filas con fecha no interpretable"),
        ], className="fila-kpis"),

        html.Div([
            html.Div([
                dcc.Graph(figure=fig_distribucion_precios(df)),
                html.P("Forma general de los precios del catalogo: donde se concentra la mayoria "
                       "de los juegos y que tan frecuentes son los precios altos.",
                       className="texto-apoyo"),
            ], className="panel panel-mitad"),

            html.Div([
                dcc.Graph(figure=fig_distribucion_rating(df)),
                html.P("Forma general de las calificaciones: si el catalogo tiende a juegos bien "
                       "calificados o hay mucha variedad.",
                       className="texto-apoyo"),
            ], className="panel panel-mitad"),
        ], className="fila-paneles"),

        html.Div([
            dcc.Graph(figure=fig_boxplot_precio_genero(df)),
            html.P("Cada caja resume el rango de precios de un genero: la linea del medio es la "
                   "mediana, la caja contiene a la mitad central de los juegos, y los puntos "
                   "sueltos son precios atipicos (outliers) dentro de ese genero.",
                   className="texto-apoyo"),
        ], className="panel"),

        html.Div([
            dcc.Graph(figure=fig_heatmap_genero_decada(df)),
            html.P("Cada celda indica cuantos juegos de un genero se lanzaron en una decada. "
                   "Celdas mas claras significan mayor concentracion de titulos.",
                   className="texto-apoyo"),
        ], className="panel"),
    ])


# --- Vista Operativa --------------------------------------------------------

def fig_evolucion_tipo_cambio(df_cambio: pd.DataFrame) -> go.Figure:
    fig = px.line(
        df_cambio, x="fecha_consulta", y="valor_clp_por_usd",
        title="Evolucion del tipo de cambio USD -> CLP",
        labels={"fecha_consulta": "Fecha de consulta", "valor_clp_por_usd": "CLP por USD"},
        markers=True, color_discrete_sequence=[COLOR_ACENTO],
    )
    return aplicar_estilo(fig)


def tabla_sensibilidad_tipo_cambio(df: pd.DataFrame) -> html.Table:
    """
    Los juegos mas caros en USD son los que mas "se mueven" en CLP cuando
    el tipo de cambio varia. Esta tabla no es un grafico, es informacion
    operativa concreta: que titulos vigilar si el dolar sube o baja.
    """
    top = df.nlargest(10, "precio_usd")[["nombre", "genero", "precio_usd", "precio_clp"]]

    encabezado = html.Tr([html.Th(c) for c in ["Juego", "Genero", "Precio USD", "Precio CLP"]])
    filas = [
        html.Tr([
            html.Td(fila["nombre"]),
            html.Td(fila["genero"]),
            html.Td(f"${fila['precio_usd']:.2f}"),
            html.Td(f"${fila['precio_clp']:,.0f}".replace(",", ".")),
        ])
        for _, fila in top.iterrows()
    ]
    return html.Table([encabezado] + filas, className="tabla-datos")


def construir_vista_operativa(df: pd.DataFrame, df_cambio: pd.DataFrame) -> html.Div:
    if len(df_cambio) >= 2:
        variacion = (
            (df_cambio["valor_clp_por_usd"].iloc[-1] - df_cambio["valor_clp_por_usd"].iloc[-2])
            / df_cambio["valor_clp_por_usd"].iloc[-2] * 100
        )
        valor_actual = df_cambio["valor_clp_por_usd"].iloc[-1]
        color_variacion = COLOR_ALERTA_POS if variacion < 0 else COLOR_ALERTA_NEG
        texto_variacion = f"{variacion:+.2f}%"
    else:
        valor_actual = df_cambio["valor_clp_por_usd"].iloc[-1] if len(df_cambio) else 0
        texto_variacion = "Sin datos suficientes"
        color_variacion = COLOR_TEXTO_SECUNDARIO

    return html.Div([
        html.Div([
            tarjeta_kpi("Tipo de cambio actual", f"${valor_actual:,.1f}".replace(",", "."), "CLP por 1 USD"),
            tarjeta_kpi("Variacion ultima consulta", texto_variacion, "respecto a la consulta anterior",
                        color_valor=color_variacion),
            tarjeta_kpi("Snapshots guardados", str(len(df_cambio)), "historico propio del proyecto"),
        ], className="fila-kpis"),

        html.Div([
            dcc.Graph(figure=fig_evolucion_tipo_cambio(df_cambio)),
            html.P("Cada punto es una consulta a la API de tipo de cambio guardada en la base "
                   "propia del proyecto. Permite ver si el dolar viene subiendo o bajando.",
                   className="texto-apoyo"),
        ], className="panel"),

        html.Div([
            html.H3("Juegos mas sensibles a la variacion del dolar", className="titulo-seccion"),
            html.P("Estos son los juegos mas caros en USD del catalogo: como su precio en CLP se "
                   "recalcula con el tipo de cambio del dia, son los que mas pesos ganan o pierden "
                   "cuando el dolar se mueve.",
                   className="texto-apoyo"),
            tabla_sensibilidad_tipo_cambio(df),
        ], className="panel"),
    ])


# --- Componentes reutilizables ------------------------------------------

def tarjeta_kpi(etiqueta: str, valor: str, nota: str, color_valor: str = COLOR_ACENTO) -> html.Div:
    return html.Div([
        html.P(etiqueta, className="kpi-etiqueta"),
        html.H2(valor, className="kpi-valor", style={"color": color_valor}),
        html.P(nota, className="kpi-nota"),
    ], className="tarjeta-kpi")


# --- Layout principal y CSS ------------------------------------------------

ESTILOS_GLOBALES = f"""
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=swap');

body {{
    background-color: {COLOR_FONDO};
    color: {COLOR_TEXTO};
    font-family: 'Inter', sans-serif;
    margin: 0;
}}

.contenedor-app {{
    max-width: 1180px;
    margin: 0 auto;
    padding: 32px 24px 60px;
}}

.encabezado {{
    margin-bottom: 8px;
}}

.encabezado h1 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 28px;
    margin: 0;
    color: {COLOR_TEXTO};
}}

.encabezado p {{
    color: {COLOR_TEXTO_SECUNDARIO};
    margin-top: 4px;
    font-size: 14px;
}}

.fila-kpis {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 24px 0;
}}

.tarjeta-kpi {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDE};
    border-radius: 10px;
    padding: 16px 18px;
}}

.kpi-etiqueta {{
    color: {COLOR_TEXTO_SECUNDARIO};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 0 0 6px;
}}

.kpi-valor {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 24px;
    margin: 0 0 4px;
    overflow-wrap: anywhere;
}}

.kpi-nota {{
    color: {COLOR_TEXTO_SECUNDARIO};
    font-size: 12px;
    margin: 0;
}}

.fila-paneles {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}}

.panel {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDE};
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 14px;
}}

.panel-mitad {{
    margin-bottom: 0;
}}

.titulo-seccion {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 16px;
    margin: 0 0 6px;
}}

.texto-apoyo {{
    color: {COLOR_TEXTO_SECUNDARIO};
    font-size: 13px;
    line-height: 1.5;
    margin: 4px 4px 0;
}}

.tabla-datos {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 13px;
}}

.tabla-datos th {{
    text-align: left;
    color: {COLOR_TEXTO_SECUNDARIO};
    font-weight: 500;
    border-bottom: 1px solid {COLOR_BORDE};
    padding: 8px 10px;
}}

.tabla-datos td {{
    padding: 8px 10px;
    border-bottom: 1px solid {COLOR_BORDE};
}}

.tabla-datos tr:hover td {{
    background-color: rgba(102, 192, 244, 0.06);
}}

.aviso-sin-datos {{
    text-align: center;
    margin-top: 60px;
    color: {COLOR_TEXTO_SECUNDARIO};
    font-size: 15px;
}}

@media (max-width: 720px) {{
    .fila-kpis, .fila-paneles {{
        grid-template-columns: 1fr;
    }}
}}

/* Pestanas de Dash, sobreescritura de su estilo default */
.tab--selected {{
    border-top: 2px solid {COLOR_ACENTO} !important;
    color: {COLOR_ACENTO} !important;
}}
"""


def construir_app() -> Dash:
    app = Dash(__name__)
    app.title = "SteamCLP Analytics"

    app.index_string = f"""
    <!DOCTYPE html>
    <html>
        <head>
            {{%metas%}}
            <title>{{%title%}}</title>
            {{%favicon%}}
            {{%css%}}
            <style>{ESTILOS_GLOBALES}</style>
        </head>
        <body>
            {{%app_entry%}}
            <footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>
        </body>
    </html>
    """

    app.layout = html.Div([
        html.Div([
            html.Div([
                html.H1("SteamCLP Analytics"),
                html.P("Precios de Steam traducidos a pesos chilenos en tiempo real."),
            ], className="encabezado"),

            dcc.Tabs(id="tabs-vistas", value="ejecutiva", children=[
                dcc.Tab(label="Ejecutiva", value="ejecutiva"),
                dcc.Tab(label="Tecnica", value="tecnica"),
                dcc.Tab(label="Operativa", value="operativa"),
            ]),

            html.Div(id="contenido-vista"),

            dcc.Interval(id="intervalo-actualizacion", interval=60 * 1000, n_intervals=0),
        ], className="contenedor-app")
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
                "Todavia no hay datos cargados. Corre primero el pipeline ETL con: python -m etl.load",
                className="aviso-sin-datos",
            )

        if vista_seleccionada == "ejecutiva":
            return construir_vista_ejecutiva(df_juegos)
        if vista_seleccionada == "tecnica":
            return construir_vista_tecnica(df_juegos)
        if vista_seleccionada == "operativa":
            return construir_vista_operativa(df_juegos, df_cambio)

        return html.Div("Vista no reconocida.")

    return app


app = construir_app()

if __name__ == "__main__":
    logger.info("Iniciando dashboard en http://localhost:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)