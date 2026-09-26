# Arquitectura propuesta — Azure (diseño de costo mínimo)

Diseño y documentación del entregable "Arquitectura propuesta en la nube" del caso. **Ya desplegado**: los recursos descritos abajo existen de verdad en Azure (Functions, Cosmos DB, Blob Storage, Key Vault) y el webhook de Telegram está en producción — el código del despliegue vive en `../functions/`.

![Arquitectura propuesta en Azure](diagrama_arquitectura.svg)

## Por qué esta versión

Este diseño se ha ido ajustando varias veces (el detalle de cada cambio está más abajo), siempre por dos motivos:

1. **Minimizar costo**: usar la mayor cantidad posible de niveles gratuitos de Azure en vez de servicios que cobran desde el primer uso.
2. **Ser proporcional al volumen real de datos**: menos servicios distintos, cada uno con una razón concreta y fácil de explicar, en vez de una arquitectura "enterprise" con herramientas (Data Factory, Container Apps, orquestadores) pensadas para volúmenes y equipos mucho más grandes que los de este caso. Reconocer que no hace falta esa complejidad aquí es, en sí mismo, una señal de criterio.

Cambios respecto a la primera versión: se reemplazó Azure Data Factory + Azure Container Apps Jobs (dos servicios de cómputo distintos) por **una sola Azure Functions App** (con cuatro funciones adentro en ese momento; hoy son tres, ver el cambio v5 más abajo); se cambió Data Lake Storage Gen2 por **Blob Storage** normal (no se necesitan sus funciones de big data); y se quitó Power BI del alcance para no sumar un servicio que, para compartir tableros, requiere licencia Pro de pago.

Cambio adicional (v3): la base de resultados pasó de Azure SQL Database a **Azure Cosmos DB**, ambas gratuitas — el motivo no es de costo sino práctico: `Microsoft.DocumentDB` (el proveedor de Cosmos DB) ya está registrado en la suscripción de Azure que se va a usar para el despliegue real (por otros proyectos), mientras que `Microsoft.Sql` no — un paso menos de fricción al desplegar.

Cambio adicional (v4): el agente se consume por **Telegram** en vez de una interfaz web propia. Esto elimina Azure Container Apps del diseño por completo — no hace falta hospedar nada para la interfaz, porque la aplicación cliente ya es la propia app de Telegram (gratis) en el teléfono o computador de quien pregunta. La cuarta función de la Function App pasa de ser una API genérica a ser el webhook de Telegram, que además corre el agente completo.

Cambio adicional (v5): se elimina la función **Ingesta** como job separado con Timer. La razón es honesta, no de costo: nunca supimos cuál es la fuente real de precios nuevos de `X`, `Y`, `Z` (el caso entregó un histórico fijo, no una fuente en vivo, y no hay diccionario de datos que diga de dónde saldría la actualización). En vez de inventar una fuente externa que no podemos confirmar, la ingesta pasa a ser **conversacional**: alguien le reporta un precio al mismo bot de Telegram (`"X = 87.32"`), y el webhook toma la fecha automáticamente (del reloj del servidor, nunca se le pide al usuario ni al modelo que la escriba) y lo guarda como un dato nuevo, sin procesar todavía.

## Componentes, mapeados a lo que pide el caso

El caso pide que la arquitectura soporte: *ingesta y almacenamiento de datos, procesamiento analítico, ejecución del modelo y exposición de resultados*.

### Cómputo — una sola Azure Functions App (Consumption plan)

Las tres etapas de cómputo del proyecto viven en la **misma** Function App, como tres funciones separadas — un único recurso de Azure que desplegar y mantener:

- **Limpieza + Análisis** (Timer, diaria a las 6:00 UTC): la lógica de `01_limpieza_datos.ipynb` y `02_analisis_relacion_materias_primas_equipos.ipynb`, empaquetada como funciones de Python con las mismas dependencias de [requirements.txt](../requirements.txt) — corre hoy sobre el histórico de `raw/` tal cual. Cuando `registrar_precio_insumo` exista (ver "Qué queda pendiente"), esta función también leería los precios nuevos reportados por Telegram desde la última corrida.
- **Pronóstico** (Timer, diaria a las 6:30 UTC): el modelo de la Fase 3. "Diaria" y no "antes de cada fase del proyecto" — se dejó corriendo todos los días porque el costo de hacerlo es prácticamente nulo (ver cuota gratuita abajo), no porque haga falta esa frecuencia para este caso puntual.
- **Webhook de Telegram** (HTTP): el mismo código de `app/agente.py` y `app/tools.py` que ya probamos local. Telegram le hace un `POST` cada vez que alguien le escribe al bot; la función corre el agente completo (Azure OpenAI + herramientas) y contesta llamando a la API de Telegram. Hoy solo responde preguntas — todavía no distingue una pregunta de un precio nuevo reportado (ver "Consumo" abajo). Es el único punto de la Function App con tráfico impredecible (depende de cuánto se use el bot), pero sigue siendo consumo bajo para una demo.

No hay una función "Ingesta" separada con Timer — la idea es reemplazarla por el registro de precios vía Telegram dentro del mismo webhook (ver "Por qué esta versión" arriba y "Qué queda pendiente" abajo), pero esa herramienta todavía no está construida.

El plan **Consumption** de Azure Functions incluye una cuota gratuita mensual (1 millón de ejecuciones + 400.000 GB-s de cómputo) que se renueva cada mes, sin límite de tiempo. Los dos jobs diarios y una conversación de demo por Telegram no se acercan a ese límite — en la práctica, este componente cuesta **$0** (el único costo real que cuelga de aquí es Azure OpenAI, que se paga aparte, por token).

### Almacenamiento — Azure Blob Storage

Mismo esquema de carpetas que ya tiene este repo: `raw/` (copia fiel de la fuente), `processed/` (salidas de limpieza y análisis), `models/` (artefactos del pronóstico) y `reports/` (figuras e informes). `raw/` se cargó **una sola vez**, a mano, con los archivos que ya vinieron con el caso — no hay una función que la actualice sola (ver el cambio de "Ingesta" más arriba). Cuando `registrar_precio_insumo` exista, las actualizaciones llegarían por Telegram y quedarían en Cosmos DB, no en `raw/`; por ahora esa vía todavía no existe. Se usa Blob Storage estándar en vez de Data Lake Storage Gen2 porque no se necesita namespace jerárquico ni permisos a nivel de carpeta para este proyecto. Los primeros ~5GB son gratis durante 12 meses; después, dado que el dataset pesa unos pocos MB, el costo es de centavos de dólar al mes.

### Resultados — Azure Cosmos DB (nivel gratuito)

Tres contenedores documentales en vez de tablas relacionales, ya creados y en uso, para no depender de leer CSVs en cada consulta:

- `resumen_relacion` — un documento por combinación materia prima–equipo (particionado por `equipo`), equivalente a `resumen_relacion_materias_primas_equipos.csv`.
- `pronostico_equipos` — un documento por fecha pronosticada (particionado por `equipo`), equivalente a `pronostico_equipos.csv`.
- `conversaciones` — un documento por `chat_id` de Telegram, con el historial de mensajes de esa conversación. Hace falta porque una Azure Function no mantiene estado entre invocaciones (a diferencia del prototipo local, que guarda la memoria en `st.session_state` mientras el proceso de Streamlit sigue corriendo) — el webhook lee este documento al recibir un mensaje y lo reescribe con la respuesta antes de terminar. Hoy crece sin límite: no hay lógica que recorte o archive conversaciones viejas (ver "Qué queda pendiente").

Un cuarto contenedor, `precios_reportados`, está **diseñado pero todavía no creado**: guardaría un documento por precio nuevo que alguien registre por Telegram (`insumo`, `precio`, `fecha` puesta por el servidor, `chat_id` de quien lo mandó), para que la función de Limpieza + Análisis lo lea junto con `raw/` en cada corrida. Depende de que `registrar_precio_insumo` se implemente primero.

Azure ofrece **1.000 RU/s y 25GB de almacenamiento gratis por cuenta, sin límite de tiempo** (a diferencia del storage, que solo es gratis 12 meses) — de sobra para el volumen de este proyecto. Se prefirió sobre Azure SQL Database porque el patrón de acceso (leer un documento pequeño por clave `equipo`) encaja igual de bien con un modelo de documentos, y porque el proveedor de Cosmos DB ya está habilitado en la cuenta de Azure que se va a usar (ver "Por qué esta versión" arriba).

### Consumo — Telegram

El evaluador (o el equipo de planeación financiera) habla con el bot como hablaría con cualquier contacto de Telegram — no hay una URL que visitar, ni una interfaz que mantener funcionando:

- **Telegram Bot API**: gratis, sin costo por bot ni por mensaje. El bot se crea una sola vez hablando con `@BotFather` dentro de Telegram, que entrega un token — eso es lo único manual del lado de Telegram.
- **Webhook, no *polling***: en vez de que nuestra función esté preguntando todo el rato "¿hay mensajes nuevos?" (lo que sí hace el prototipo local, con *long polling*, para no depender de una URL pública), en producción Telegram llama directo a la función cada vez que hay un mensaje nuevo — más eficiente y más barato, encaja mejor con un modelo serverless que paga por ejecución.
- **Ya probado en local** con datos y modelo reales (ver `app/README.md`) — pasar de local a este diseño es cambiar de dónde saca el `chat_id`/mensaje (input en consola → payload del webhook) y de dónde saca la memoria (variable en memoria → contenedor `conversaciones` de Cosmos DB), sin tocar la lógica del agente en sí.

**Diseño (todavía no implementado): registrar un precio nuevo también sería una conversación**, no un formulario aparte: alguien le escribiría al bot algo como *"X = 87.32"* y el agente reconocería la intención (una herramienta nueva, `registrar_precio_insumo`, que hoy no existe en `tools.py`) en vez de tratarlo como una pregunta. Dos reglas de diseño para cuando se construya, pensadas para no repetir errores que ya vimos en este proyecto:

- **La fecha nunca la escribiría una persona ni la inventaría el modelo** — la pondría el código, con la fecha real del servidor en el momento del mensaje. Evita tanto errores de tipeo como que el modelo alucine una fecha.
- **Validación contra saltos anómalos**: mismo umbral del 15% que ya se usó en la Fase 1 para detectar saltos de precio inusuales. Si el precio reportado se alejara más de eso del último conocido, el agente no lo guardaría de una — le preguntaría a quien escribió si está seguro, igual que un analista dudaría antes de aceptar un dato así.
- **Control de acceso pendiente de decidir**: por ahora, si se construyera tal cual, cualquiera que encuentre el bot podría reportar un precio falso y contaminar el dataset — antes de habilitarla hay que restringir esta herramienta a una lista de `chat_id` autorizados (guardada en Key Vault o en el propio Cosmos DB).

Power BI y una interfaz web propia quedan fuera de esta versión — si más adelante hace falta un dashboard visual, se puede agregar un endpoint HTTP adicional en la misma Function App sin rehacer nada de esto.

## Seguridad y operación transversal

También elegidos por su nivel gratuito:

- **Azure Key Vault** — secretos y credenciales (incluido el token del bot de Telegram y la key de Azure OpenAI); costo casi nulo a este volumen de operaciones.
- **Microsoft Entra ID** — control de acceso, incluido sin costo adicional en cualquier suscripción de Azure.
- **Azure Monitor / Log Analytics** — nivel gratuito de 5GB de datos de logs al mes.
- **GitHub Actions** (en vez de Azure DevOps), propuesto para CI/CD — gratis para repositorios públicos o privados, y el código ya vive en GitHub. No hay todavía ningún workflow configurado; el despliegue actual se hizo a mano con `func azure functionapp publish`.

## Costo estimado total

**~$0/mes** dentro del uso esperado de este proyecto: el cómputo (Functions, incluido el webhook de Telegram), la base de datos (Cosmos DB) y la interfaz (Telegram Bot API) caen dentro de niveles siempre-gratuitos, y el storage es gratis los primeros 12 meses (después, centavos). El único gasto real de todo el diseño es Azure OpenAI, que paga por uso de tokens — y aun así, mínimo para una demo.

## Lecciones del primer despliegue

El primer intento de publicar la Function App terminó con **0 funciones detectadas** por el host de Azure, sin ningún error explícito. La causa real: `function_app.py` importaba `shap` (que arrastra `numba`/`llvmlite`) y `statsmodels` a nivel de módulo, y esas dos librerías juntas tardaban más de 30 segundos en cargar — tiempo suficiente para superar el timeout de indexado del host, incluso para el webhook, que no las necesita para nada. La solución fue mover esos imports pesados adentro de `limpieza_analisis` y `pronostico_fn` (las únicas funciones que los usan, y corren una vez al día), dejando el import de `function_app.py` en segundos en vez de más de 30. El detalle completo queda en los comentarios del propio archivo (`functions/function_app.py`, justo antes de `app = func.FunctionApp()`).

## Limitaciones conocidas del despliegue actual

No corregidas todavía — quedan documentadas aquí para no presentarlas como resueltas:

- **El webhook y el prototipo local le muestran a quien escribe el texto crudo de la excepción** cuando algo falla (`f"Tuve un error procesando tu mensaje: {exc}"`), en vez de un mensaje genérico — puede filtrar detalle interno que no debería llegar al usuario final.
- **El webhook no valida el `secret_token` de Telegram**: Telegram permite fijar un token secreto en `setWebhook` y lo reenvía en cada request como header (`X-Telegram-Bot-Api-Secret-Token`); esta implementación no lo pide ni lo verifica, así que cualquiera que adivine la URL de la función (protegida solo por la function key) podría intentar enviarle payloads falsos.
- **El historial de `conversaciones` en Cosmos DB crece sin límite**: cada turno se agrega al documento completo y se reescribe entero, sin ninguna lógica de recorte, resumen o archivado de conversaciones viejas.
- **No hay métricas de uso ni evaluación de la calidad de las respuestas del agente** — no se ha instrumentado ningún conteo de conversaciones, tasa de error o revisión de calidad de las respuestas más allá de las pruebas manuales hechas durante el desarrollo.

## Qué queda pendiente

- Implementar `registrar_precio_insumo` en `tools.py` — el bot ya funciona para consultas, pero la ingesta conversacional de precios sigue solo diseñada, no construida.
- Decidir y construir el control de acceso de `registrar_precio_insumo` (lista de `chat_id` autorizados) antes de habilitarla — sin eso, cualquiera podría escribirle al bot un precio falso.
- Corregir las limitaciones de la sección anterior (excepción cruda al usuario, `secret_token` del webhook, historial sin límite en Cosmos DB).
- Configurar un workflow real de GitHub Actions para el despliegue — hoy es manual (`func azure functionapp publish`).
- Revisar si conviene acotar el uso de tokens de Azure OpenAI (ej. límites de contexto, cachear respuestas) para mantener ese único costo lo más bajo posible.
