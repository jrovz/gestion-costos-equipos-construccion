# Datos

Esta carpeta contiene los datos del proyecto en sus distintas etapas y el notebook que pasa de uno a otro.

## Estructura

```
data/
├── raw/                        # Copia exacta de los archivos originales del caso
├── processed/                  # Salidas generadas por 01_limpieza_datos.ipynb
└── 01_limpieza_datos.ipynb     # Notebook de limpieza y preparación
```

## `raw/` — datos originales

Copia sin modificar de los archivos entregados en `Datos/` (fuera de este proyecto). Nunca se editan a mano; cualquier corrección o transformación se hace en el notebook y se guarda en `processed/`.

| Archivo | Filas | Rango de fechas | Formato |
|---|---|---|---|
| `X.csv` | 9,144 | 1988-06-27 → 2024-04-04 | `Date,Price`; separador `,`, decimal `.` |
| `Y.csv` | 4,485 | 2006-07-11 → 2023-09-12 | `Date;Price`; separador `;`, decimal `,`, fecha `D/M/YYYY`, con BOM |
| `Z.csv` | 3,565 | 2010-01-01 → 2023-08-31 | `Price,Date` (columnas invertidas) |
| `historico_equipos.csv` | 3,530 | 2010-01-04 → 2023-08-31 | `Date,Price_X,Price_Y,Price_Z,Price_Equipo1,Price_Equipo2` — combinación ya alineada de X, Y, Z más los precios de los dos equipos (variable objetivo del caso) |

No hay diccionario de datos que indique a qué materia prima o equipo corresponde cada serie (`X`, `Y`, `Z`, `Equipo1`, `Equipo2`); es una limitación conocida del caso, documentada también en el informe.

## `01_limpieza_datos.ipynb` — notebook de limpieza

Carga los cuatro archivos de `raw/`, homogeniza formatos (fechas, decimales, nombres de columnas), valida calidad (duplicados, nulos, saltos de precio anómalos), alinea las tres materias primas en el tiempo y verifica que el resultado coincide con `historico_equipos.csv` antes de guardar las salidas. El detalle de cada paso está comentado dentro del notebook.

Para ejecutarlo: abrir con Jupyter desde esta carpeta (usa rutas relativas `raw/` y `processed/`) y correr las celdas en orden. Dependencias: `pandas`, `numpy`.

## `processed/` — salidas de la limpieza

Se generan al correr el notebook; no se versionan a mano.

| Archivo | Contenido |
|---|---|
| `materias_primas_historico_completo.csv` | X, Y, Z combinadas por fecha (merge *outer*), toda la historia disponible de cada una (1988–2024), con `NaN` donde una serie no tenía dato ese día |
| `dataset_equipos_limpio.csv` | `date, price_x, price_y, price_z, price_equipo1, price_equipo2`, acotado a 2010-01-04 – 2023-08-31 (rango donde existen los precios de equipo). Es la tabla base para el análisis de relación materias primas–equipos y el modelado |
