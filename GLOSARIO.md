# Glosario

Términos técnicos usados en el proyecto, explicados en lenguaje simple y, cuando aplica, con lo que significaron concretamente en este análisis (ver [INFORME.md](INFORME.md) para el detalle completo).

## Del caso y del negocio

**Backtesting** — Probar un método de pronóstico "haciendo de cuenta" que no se conoce el futuro: se pronostica desde una fecha pasada y se compara contra lo que realmente pasó después. Es la forma de elegir un método con evidencia en vez de por preferencia. En la Fase 3 se hizo en 18 fechas distintas de los últimos ~2 años de historia.

**Equipo (Equipo1, Equipo2)** — Los dos tipos de maquinaria crítica que la constructora debe comprar durante el proyecto; su precio de adquisición es la variable que se quiere explicar y proyectar. No se sabe qué maquinaria real son (no hay diccionario de datos).

**Fase** — Cada etapa del proyecto: Fase 1 (limpieza de datos), Fase 2 (qué materia prima explica a cada equipo), Fase 3 (proyección de costos), Fase 4 (Agente de IA, desplegado en Azure con Telegram como interfaz).

**Horizonte de predicción** — Hasta cuántos días/meses hacia adelante se pronostica. No es el mismo para los dos equipos en este proyecto: se determinó con backtesting, no se fijó de antemano.

**Insumo / materia prima** — Los tres productos de mercado (`X`, `Y`, `Z`) cuyo precio se sospecha que influye en el costo de los equipos.

**Precio "pegado"** — Un precio que se mantiene igual varios días seguidos y cambia en saltos, típico de una lista de precios que se actualiza cada cierto tiempo (no de una cotización de mercado que se mueve a diario). Así se comporta `Y` en este proyecto (55% de los días repite el valor anterior).

**Rezago (lag)** — Cuántos días de diferencia hay entre que se mueve el precio de un insumo y que se mueve el precio del equipo. Un rezago de 0 significa que se mueven el mismo día (relación "contemporánea"), sin ventaja de anticipación.

## Series de tiempo y econometría

**ADF (prueba de Dickey-Fuller aumentada)** — Prueba estadística que revisa si una serie tiene "raíz unitaria" (no es estacionaria, tiende a alejarse sin volver a un nivel). Se usa junto con KPSS porque cada una parte de una hipótesis contraria.

**ARIMA** — Modelo clásico de pronóstico que usa solo el pasado de una serie (sus propios valores anteriores) para proyectar su futuro, sin usar otras variables. En este proyecto se usó como punto de comparación contra el VECM.

**Causalidad de Granger** — Prueba que revisa si el pasado de una serie ayuda a predecir a otra, más allá de lo que ya aporta el propio pasado de esa segunda serie. Ojo: mide capacidad predictiva, no causalidad real en el sentido causa-efecto.

**Cointegración** — Cuando dos series suben y bajan cada una por su cuenta (no son estacionarias), pero existe una combinación de ambas que sí es estable — señal de que comparten un equilibrio de largo plazo real, y no solo una tendencia parecida por casualidad. Es la base de por qué se usó el VECM en la Fase 3.

**Correlación cruzada (CCF)** — Mide la correlación entre una serie y otra, pero desplazando el tiempo (por ejemplo, el precio de la materia prima de "hace 5 días" contra el del equipo "hoy"). Sirve para ver si un insumo anticipa al equipo o si se mueven el mismo día.

**Correlación espuria** — Dos series que parecen correlacionadas solo porque ambas tienen tendencia (por ejemplo, ambas suben con los años), sin que exista una relación real entre ellas. El motivo principal por el que en este proyecto no se confió en la correlación sobre precios crudos.

**Engle-Granger** — Método para probar cointegración entre dos series: se usó para confirmar, uno por uno, qué pares materia prima–equipo tienen una relación de largo plazo real.

**Johansen** — Versión del test de cointegración para más de dos series a la vez (en este caso, las 3 materias primas y un equipo juntos). Se usó como evidencia secundaria porque, con series financieras diarias y muestras grandes, tiende a sobre-detectar cointegración.

**KPSS** — Prueba estadística parecida al ADF, pero que parte de la hipótesis contraria (asume que la serie es estacionaria y busca evidencia de que no lo es). Usarlas juntas da más confianza que usar solo una.

**MAE, RMSE, MAPE** — Formas de medir qué tan lejos estuvo un pronóstico del valor real. MAPE (error porcentual) fue la principal en este proyecto porque permite comparar equipos con precios de escalas distintas usando un solo número (%).

**Rolling-origin / walk-forward** — La forma concreta de hacer backtesting: mover el punto de partida del pronóstico hacia adelante en el tiempo, repitiendo la evaluación en varias fechas distintas en vez de en una sola.

**Serie estacionaria / no estacionaria (I(0) / I(1))** — Una serie estacionaria se mueve alrededor de un nivel estable; una no estacionaria (I(1)) tiende a alejarse con el tiempo, como los precios en niveles de este proyecto. Los retornos (variación día a día) sí suelen ser estacionarios (I(0)).

**VAR (Vector Autoregression)** — Modelo que pronostica varias series a la vez, cada una en función de los valores pasados de todas ellas. Se usó para elegir cuántos días de rezago incluir en el Johansen y el VECM.

**VECM (Vector Error Correction Model)** — Versión del VAR pensada específicamente para series cointegradas: combina el movimiento de corto plazo con un "jalón" de vuelta hacia el equilibrio de largo plazo. Fue el modelo principal de pronóstico en la Fase 3, justo porque `Y`-Equipo1 y `Z`-Equipo2 están cointegrados.

## Modelos y estadística

**Banda de incertidumbre (intervalo de confianza)** — El rango alrededor de un pronóstico puntual que indica qué tan seguro se está de ese número. En este proyecto se calculó con el error real observado en el backtesting, no con la fórmula interna del modelo (que asume una forma de error que no siempre se cumple en precios financieros).

**Elastic Net** — Variante del Lasso que combina dos tipos de penalización; suele ser más estable cuando las variables predictoras están correlacionadas entre sí.

**Lasso** — Tipo de regresión que "castiga" los coeficientes grandes y puede llevar a cero el de una variable que no aporta — en la práctica, selecciona variables automáticamente en vez de que el analista decida a mano cuáles incluir.

**Multicolinealidad / VIF** — Cuando dos o más variables predictoras están correlacionadas entre sí, lo que puede distorsionar la interpretación de un modelo. El VIF mide qué tan grave es ese problema; en este proyecto salió bajo (sin problema) entre `X`, `Y` y `Z`.

**R²** — Qué proporción de la variación del precio del equipo queda explicada por el modelo. Los modelos de este proyecto dieron valores modestos (0.10–0.17): explican una parte real pero parcial — el resto es mano de obra, logística, margen del proveedor, que no están en los datos.

**Random Forest** — Modelo basado en muchos árboles de decisión combinados. Se usó como contraste no lineal para verificar que el resultado del Lasso (lineal) no se estuviera perdiendo alguna relación más compleja.

**SHAP (valores de Shapley)** — Método que reparte, para cada predicción de un modelo, cuánto aportó cada variable — una forma más precisa de medir "importancia" que solo mirar los coeficientes.

**TimeSeriesSplit** — Forma de dividir los datos en entrenamiento/prueba que respeta el orden del tiempo (nunca usa el futuro para predecir el pasado), en vez de mezclar los datos al azar como se haría con datos que no son una serie de tiempo.

## Arquitectura en la nube (Azure)

**Azure Blob Storage** — Servicio de almacenamiento de archivos en la nube. En la arquitectura propuesta, guarda los datos crudos, procesados, el modelo entrenado y los reportes.

**Azure Functions (Consumption plan)** — Servicio que ejecuta código bajo demanda (por ejemplo, una vez al día, o cada vez que llega un mensaje de Telegram) sin mantener un servidor prendido todo el tiempo. Incluye una cuota gratuita mensual que cubre el uso esperado de este proyecto. Es donde vive todo el cómputo de la arquitectura propuesta (ingesta, limpieza, pronóstico y el webhook del agente).

**Azure Key Vault** — Bóveda para guardar contraseñas y credenciales de forma segura (incluido el token del bot de Telegram), en vez de dejarlas escritas en el código.

**Azure Cosmos DB (nivel gratuito)** — Base de datos de documentos donde quedan los resultados listos para consultar rápido (resumen de relación insumo-equipo, pronóstico, y el historial de cada conversación de Telegram), en vez de leer un CSV cada vez. Azure ofrece 1.000 RU/s y 25GB gratis por cuenta, sin límite de tiempo.

**CI/CD** — Automatizar el proceso de probar y desplegar código cada vez que se actualiza el repositorio. En la arquitectura propuesta se usa GitHub Actions, que es gratuito.

**Webhook** — Una forma de que un servicio (Telegram) le avise a otro (nuestra Azure Function) apenas pasa algo, llamándolo directamente, en vez de que el segundo esté preguntando todo el rato "¿hay algo nuevo?" (eso último se llama *polling*, y es lo que usa el prototipo local del agente para no necesitar una dirección pública en internet).

**Microsoft Entra ID** — Servicio que controla quién puede acceder a qué recursos dentro de Azure.

**Serverless** — Forma de usar servicios en la nube donde no se administra un servidor propio; se paga (o no se paga, si cae dentro de la cuota gratuita) solo por el tiempo real de ejecución. Es el principio detrás de todo el diseño de costo mínimo de este proyecto.

## Agente de IA

**Agente de IA** — A diferencia de un modelo de IA convencional (que solo predice, clasifica o genera algo a partir de datos), un agente decide por sí mismo qué hacer paso a paso para responder una pregunta: puede elegir qué herramienta usar, recordar el contexto de la conversación y encadenar acciones — no solo produce una salida fija.

**Autonomía** — Que el agente decida sus propios pasos (por ejemplo, si necesita consultar el pronóstico, buscar en la web, o ambas cosas) en vez de seguir un guion fijo.

**Capacidad de acción** — Que el agente pueda efectivamente hacer algo (consultar una base de datos, llamar una API), no solo generar texto.

**IA convencional** — Un modelo que recibe una entrada y produce una salida fija: por ejemplo, el modelo de pronóstico de la Fase 3 recibe historia de precios y devuelve un número. No decide nada por su cuenta ni usa herramientas.

**Memoria** — Que el agente recuerde lo que se habló antes en la misma conversación, para no perder contexto entre una pregunta y la siguiente.

**Uso de herramientas (tool calling)** — La capacidad del agente de llamar funciones externas (como la API de resultados o un buscador web) para obtener información que no tiene de entrada, en vez de inventar la respuesta.
