# SteamCLP Analytics

Pipeline ETL y dashboard interactivo que analiza el catálogo de videojuegos de Steam y traduce sus precios a pesos chilenos usando el tipo de cambio del día, para entender qué tan caro es realmente jugar en Steam desde Chile.

Proyecto desarrollado para la Evaluación Parcial N°3 de SCY1101 (Programación para la Ciencia de Datos), Duoc UC.

## Equipo

## El problema que resolvemos

Steam fija sus precios en dólares estadounidenses, pero el costo real para un usuario chileno depende del tipo de cambio del día. Este proyecto cruza el catálogo histórico de juegos con el valor del dólar en tiempo real para responder: ¿cuánto cuesta hoy un juego en CLP?, ¿qué géneros son más caros?, ¿cómo varía el "costo real" cuando se mueve el tipo de cambio?

## Arquitectura

El sistema integra tres fuentes de datos distintas que alimentan un pipeline ETL, el cual carga una base de datos final que consume el dashboard:

1. **Catálogo (CSV estático)** — `SteamGames.csv`, dataset público de Kaggle con ~30.000 juegos (nombre, género, desarrollador, precio en USD, fecha de lanzamiento, rating).
2. **Tipo de cambio (API REST)** — [open.er-api.com](https://www.exchangerate-api.com/), consulta en vivo del valor USD → CLP, sin necesidad de API key.
3. **Histórico propio (base de datos SQLite)** — registro generado por el propio proyecto: snapshots diarios del tipo de cambio consultado y métricas calculadas, para tener una fuente transaccional propia además de las dos externas.

```
data/SteamGames.csv ─┐
                      ├──► etl/ (extract → transform → load) ──► data/steamclp.db ──► dashboards/app.py
API tipo de cambio ───┘
```

## Estructura del repositorio

```
steam-clp-analytics/
├── data/               # CSV original y base de datos generada (no se versiona el .db)
├── etl/                # extract.py, transform.py, load.py
├── dashboards/         # app.py (Dash)
├── tests/              # pruebas del pipeline ETL
├── docs/               # diagramas, capturas, notas de arquitectura
├── crear_historico.py  # script de inicialización de la base propia
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Cómo correr el proyecto

### Opción 1: entorno local con Python

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

python crear_historico.py       # inicializa la base propia (una sola vez)
python etl/extract.py           # extrae las tres fuentes
python etl/transform.py         # limpia, valida y convierte a CLP
python etl/load.py              # carga la base final

python dashboards/app.py        # levanta el dashboard en http://localhost:8050
```

### Opción 2: con Docker

```bash
docker compose up --build
```

El dashboard queda disponible en `http://localhost:8050`.

## Dashboard

El dashboard tiene tres vistas pensadas para audiencias distintas:

- **Ejecutiva**: gasto promedio en CLP por género, evolución del tipo de cambio, precio promedio del catálogo.
- **Técnica**: estado de la última corrida del ETL, filas procesadas, errores capturados, distribución de precios.
- **Operativa**: variación porcentual del dólar día a día y juegos cuyo precio en CLP cambió de forma significativa por ese movimiento.

## Manejo de errores y validación

El pipeline valida el esquema del CSV antes de transformar, registra en log cualquier fila inconsistente en vez de detener la ejecución, y usa reintentos con backoff si la consulta al tipo de cambio falla, recurriendo al último valor guardado en la base propia como respaldo.

## Flujo de trabajo en Git

Se trabajó con una rama por área funcional (`feature/extract-sources`, `feature/etl-transform`, `feature/dashboard-docker`), integradas a `main` mediante pull requests revisados por al menos un integrante distinto al autor. El historial de issues y PRs documenta las decisiones técnicas tomadas durante el desarrollo.

## Fuentes de datos

- Dataset de Steam: [Kaggle — Steam Game Clean](https://www.kaggle.com/datasets/newnguyn/steam-game-clean)
- Tipo de cambio: [ExchangeRate-API](https://www.exchangerate-api.com/)
