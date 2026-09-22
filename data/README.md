# Datos

Esta carpeta contiene los datos del proyecto en sus distintas etapas y el notebook que pasa de uno a otro.

## Estructura

```
data/
├── raw/                                                # Copia exacta de los archivos originales del caso
├── processed/                                          # Salidas generadas por los notebooks 01, 02 y 03
├── 01_limpieza_datos.ipynb                             # Notebook de limpieza y preparación
├── 02_analisis_relacion_materias_primas_equipos.ipynb  # Notebook de análisis de relación insumos-equipos
└── 03_proyeccion_costos.ipynb                          # Notebook de proyección de costos (Fase 3)
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

## `02_analisis_relacion_materias_primas_equipos.ipynb` — relación insumos-equipos

Responde la pregunta central del caso: ¿el precio de cada equipo realmente depende de alguna materia prima, o solo lo parece porque ambos suben con el tiempo?

Primero revisamos cómo se comporta cada serie: `Y` resultó ser una lista de precios que se actualiza cada cierto tiempo (repite el mismo valor el 55% de los días, con tramos de hasta 35 días sin cambiar), mientras que `X` y `Z` sí se mueven casi a diario, como una cotización de mercado normal.

Comparar los precios tal cual, sin ajustar, engaña: casi todas las series suben con los años, así que salen "correlacionadas" aunque no tengan ninguna relación real entre sí. Por eso el análisis se hace sobre las variaciones día a día (no sobre el precio en sí), y se cruzan varias pruebas estadísticas distintas — no solo una — para confirmar con evidencia, y no con supuestos, qué insumo mueve de verdad a cada equipo.

**Resultado, confirmado por 5 métodos independientes:**
- El precio del **Equipo1** está explicado principalmente por la materia prima **`Y`**. Como `Y` es una lista de precios que se actualiza cada tanto (no una cotización diaria), esto se interpreta mejor como que Equipo1 está indexado a esa lista, más que como un efecto de mercado día a día.
- El precio del **Equipo2** está explicado principalmente por la materia prima **`Z`**.
- La materia prima **`X`** no tiene una relación real con ninguno de los dos equipos: su correlación aparente era casi toda un espejismo por la tendencia compartida.
- En ambos casos la relación es del mismo día: el insumo no anticipa el precio del equipo con días de anticipación, se mueven juntos.

Dependencias adicionales sobre las de `01`: `statsmodels`, `scikit-learn`, `shap`, `matplotlib`, `seaborn`.

## `03_proyeccion_costos.ipynb` — proyección de costos

Con `Y` explicando a Equipo1 y `Z` explicando a Equipo2 (hallazgo de `02`), esta fase responde dos preguntas: ¿con qué método se proyecta mejor cada equipo, y hasta cuántos meses adelante ese pronóstico sigue siendo mejor que no pronosticar nada?

Se probaron 4 métodos con backtesting real (comparar el pronóstico contra lo que efectivamente pasó, en distintos puntos del histórico): repetir el último precio, un promedio móvil de 3 meses (el método que proponía el texto inyectado en el PDF del caso), un modelo ARIMA sobre el equipo solo, y un VECM que usa la materia prima y el equipo juntos — este último aprovecha que ambas series están cointegradas (hallazgo de `02`), por lo que es el candidato más sólido.

**Resultado:** el promedio móvil de 3 meses fue el peor método en las 6 combinaciones equipo–horizonte probadas — descartado con evidencia, no solo por sospecha. El VECM sí aporta una mejora real, pero solo hasta cierto punto, y ese punto es distinto para cada equipo:
- **Equipo1**: se puede confiar en el pronóstico hasta **3 meses** adelante (error histórico ~13%).
- **Equipo2**: solo hasta **1 mes** adelante (error histórico ~6%); más allá de eso, repetir el último precio conocido funciona igual o mejor.

Esta diferencia tiene sentido: `Y` (el insumo de Equipo1) es una lista de precios que cambia cada 5-7 semanas, así que un pronóstico a 3 meses todavía "ve" el próximo cambio de lista; `Z` (el de Equipo2) cotiza a diario como un mercado normal, con más ruido de corto plazo que erosiona la ventaja del modelo más rápido.

La banda de incertidumbre del pronóstico final no sale de la fórmula interna del modelo (que asume que los errores son "normales", algo que no siempre se cumple en precios financieros), sino del error real que ese mismo método tuvo en el backtesting — una banda más honesta porque viene de evidencia, no de un supuesto.

Dependencias: las mismas de `02`.

## `processed/` — salidas de los notebooks

Se generan al correr los notebooks; no se versionan a mano.

| Archivo | Generado por | Contenido |
|---|---|---|
| `materias_primas_historico_completo.csv` | `01` | X, Y, Z combinadas por fecha (merge *outer*), toda la historia disponible de cada una (1988–2024), con `NaN` donde una serie no tenía dato ese día |
| `dataset_equipos_limpio.csv` | `01` | `date, price_x, price_y, price_z, price_equipo1, price_equipo2`, acotado a 2010-01-04 – 2023-08-31 (rango donde existen los precios de equipo). Es la tabla base para el análisis de relación materias primas–equipos y el modelado |
| `resumen_relacion_materias_primas_equipos.csv` | `02` | Una fila por combinación materia prima–equipo, con qué tan fuerte es la relación y si las distintas pruebas la confirman. Insumo para la fase de proyección de costos |
| `pronostico_equipos.csv` | `03` | Pronóstico diario de cada equipo hasta su horizonte recomendado (3 meses Equipo1, 1 mes Equipo2), con banda de incertidumbre en el punto de control final. Insumo para la tabla `pronostico_equipos` de la arquitectura en Azure |
