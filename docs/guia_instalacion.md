# Guía de instalación

Pasos para instalar y correr SteamCLP Analytics desde cero, en Windows.
El proyecto se ejecuta mediante Docker: es la forma oficial y obligatoria
de correrlo, no una alternativa.

## 1. Requisitos previos

| Herramienta | Verificación | Instalación si falta |
|---|---|---|
| Git | `git --version` | [git-scm.com/download/win](https://git-scm.com/download/win) |
| Docker Desktop | `docker --version` y `docker compose version` | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |

Python no es necesario instalarlo en la máquina: Docker lo trae empaquetado
dentro del contenedor.

## 2. Clonar el repositorio

```powershell
git clone https://github.com/GiulianoLopresti/SteamCLP-Analytics.git
cd SteamCLP-Analytics
```

Si ya estaba clonado: `git pull origin main` en vez de clonar de nuevo.

## 3. Configurar variables de entorno

El proyecto se configura mediante un archivo `.env`, que no se sube al
repositorio. Se crea copiando la plantilla incluida:

```powershell
copy .env.example .env
```

Los valores por defecto funcionan sin necesidad de editar nada.

## 4. Descargar el dataset

Descargar `SteamGames_cleaned.csv` desde
[Kaggle](https://www.kaggle.com/datasets/newnguyn/steam-game-clean),
renombrarlo a `SteamGames.csv` y guardarlo en la carpeta `data/` del
proyecto (crear la carpeta si no existe). Este archivo no se versiona en
el repositorio.

## 5. Abrir Docker Desktop

Esperar a que el ícono de la ballena en la barra de tareas deje de
moverse, lo que indica que el motor de Docker ya está listo.

## 6. Inicializar la base de datos propia (solo la primera vez)

El servicio `etl` del `docker-compose.yml` solo corre el pipeline
(`python -m etl.load`); no crea la base de datos por sí mismo. Si
`data/steamclp.db` todavía no existe, hay que crearla una vez antes de
levantar el proyecto, usando la misma imagen que ya define el servicio
`etl` (sin necesidad de tener Python instalado en la máquina):

```powershell
docker compose run --rm etl python crear_historico.py
```

Esto construye la imagen si no existe todavía, corre `crear_historico.py`
dentro de un contenedor temporal, y lo elimina al terminar (`--rm`). El
archivo `data/steamclp.db` queda creado en la carpeta `data/` del proyecto,
gracias al volumen compartido ya definido en `docker-compose.yml`.

Este paso solo se repite si se borra `data/steamclp.db` y se quiere
reiniciar la base desde cero.

## 7. Levantar el proyecto

```powershell
docker compose up --build
```

Esto corre el pipeline ETL completo dentro de un contenedor (servicio
`etl`), y levanta el dashboard en otro contenedor (servicio `dashboard`)
una vez que el ETL termina con éxito.

Abrir en el navegador: [http://localhost:8050](http://localhost:8050)

## 8. Detener el proyecto

```
Ctrl + C
```

en la misma terminal, y opcionalmente:

```powershell
docker compose down
```

para eliminar los contenedores.

## Solo para depuración: correr sin Docker

Este modo es exclusivamente para diagnosticar errores puntuales en el
código (por ejemplo, revisar un traceback con más detalle). No reemplaza
el flujo con Docker descrito arriba.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python crear_historico.py
python -m etl.load
python dashboards/app.py
```

## Correr las pruebas automatizadas

Dentro del entorno virtual activado (ver sección de depuración arriba):

```powershell
python -m pytest tests/ -v
```