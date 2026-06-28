# API de tipo de cambio

El proyecto consume una API externa para obtener el valor del dólar
estadounidense en pesos chilenos, usada para convertir los precios de Steam
(publicados en USD) a CLP.

## Endpoint

```
GET https://open.er-api.com/v6/latest/USD
```

No requiere autenticación ni API key. Es de uso gratuito, sin límite de
peticiones documentado, y se actualiza una vez al día.

## Formato de respuesta

La API devuelve un JSON con la siguiente estructura relevante para el
proyecto:

```json
{
  "result": "success",
  "base_code": "USD",
  "time_last_update_utc": "Thu, 25 Jun 2026 00:02:30 GMT",
  "rates": {
    "CLP": 945.32,
    "EUR": 0.91,
    "...": "..."
  }
}
```

El proyecto solo utiliza dos campos de esta respuesta:

| Campo | Uso en el proyecto |
|---|---|
| `result` | Se valida que sea `"success"` antes de usar la respuesta. Si no lo es, se trata como un fallo de la API. |
| `rates.CLP` | Valor de conversión: cuántos pesos chilenos equivalen a 1 dólar en este momento. |
| `time_last_update_utc` | Se guarda junto al valor en la base de datos propia, como referencia de cuándo se actualizó ese tipo de cambio. |

## Dónde se consume en el código

La función `extraer_tipo_cambio()` en `etl/extract.py` hace la petición a
este endpoint.

## Manejo de errores

Si la petición falla (sin conexión, la API no responde, devuelve un error
HTTP, o el campo `result` no es `"success"`), el sistema:

1. Reintenta la petición hasta 3 veces (configurable), con una espera entre
   intentos.
2. Si los reintentos se agotan, busca el último valor de tipo de cambio
   guardado en la base de datos propia (tabla `historico_tipo_cambio`) y lo
   usa como respaldo, en vez de detener todo el pipeline.
3. Si tampoco existe un valor de respaldo (por ejemplo, en la primera
   ejecución del proyecto sin conexión a internet), el pipeline se detiene
   con un error explícito, porque no hay ningún tipo de cambio disponible
   con el cual convertir los precios.

Cada vez que la API responde con éxito, ese valor se guarda como un nuevo
registro en `historico_tipo_cambio`, lo que construye con el tiempo un
histórico propio del proyecto (no solo el de la API), que es lo que alimenta
el gráfico de evolución del tipo de cambio en la vista operativa del
dashboard.