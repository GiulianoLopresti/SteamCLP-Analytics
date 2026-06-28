# Documentación técnica — SteamCLP Analytics

Esta carpeta reúne los documentos de referencia del proyecto, separados del
código fuente.

## Contenido

- **`arquitectura.png`** — diagrama de arquitectura del sistema: las tres
  fuentes de datos (CSV de Kaggle, API de tipo de cambio, base de datos
  propia), el pipeline ETL de tres pasos (extract, transform, load), la base
  de datos final y las tres vistas del dashboard.

- **`api-tipo-cambio.md`** — documentación de la API REST externa que
  consume el proyecto (endpoint, formato de respuesta, manejo de errores).

- **`guia-instalacion.md`** — guía paso a paso para instalar y correr el
  proyecto desde cero (Python, Docker, dependencias).

## Dónde están las otras partes de la documentación

- La descripción general del proyecto, el problema que resuelve y el flujo
  de Git del equipo están en el `README.md` de la raíz del repositorio.
- Las pruebas automatizadas y cómo correrlas están en `tests/`.