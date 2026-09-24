# Arquitectura propuesta — Azure (diseño de costo mínimo)

Diseño y documentación del entregable "Arquitectura propuesta en la nube" del caso. Es un **borrador de diseño**: por ahora no se despliega ningún recurso real en Azure, solo se documenta cómo se vería la solución completa en producción. El despliegue mínimo real queda para una siguiente etapa, una vez validado este planteamiento.

![Arquitectura propuesta en Azure](diagrama_arquitectura.svg)

## Por qué esta versión

Esta es la segunda versión del diseño, ajustada por dos motivos:

1. **Minimizar costo**: usar la mayor cantidad posible de niveles gratuitos de Azure en vez de servicios que cobran desde el primer uso.
2. **Ser defendible como candidato junior**: menos servicios distintos, cada uno con una razón concreta y fácil de explicar, en vez de una arquitectura "enterprise" con herramientas (Data Factory, Container Apps, orquestadores) que un junior normalmente no ha operado todavía. Reconocer que no hace falta esa complejidad para este volumen de datos es, en sí mismo, una señal de criterio.

Cambios respecto a la primera versión: se reemplazó Azure Data Factory + Azure Container Apps Jobs (dos servicios de cómputo distintos) por **una sola Azure Functions App** con cuatro funciones adentro; se cambió Data Lake Storage Gen2 por **Blob Storage** normal (no se necesitan sus funciones de big data); y se quitó Power BI del alcance para no sumar un servicio que, para compartir tableros, requiere licencia Pro de pago.

Cambio adicional (v3): la base de resultados pasó de Azure SQL Database a **Azure Cosmos DB**, ambas gratuitas — el motivo no es de costo sino práctico: `Microsoft.DocumentDB` (el proveedor de Cosmos DB) ya está registrado en la suscripción de Azure que se va a usar para el despliegue real (por otros proyectos), mientras que `Microsoft.Sql` no — un paso menos de fricción al desplegar.

Cambio adicional (v4): el agente se consume por **Telegram** en vez de una interfaz web propia. Esto elimina Azure Container Apps del diseño por completo — no hace falta hospedar nada para la interfaz, porque la aplicación cliente ya es la propia app de Telegram (gratis) en el teléfono o computador de quien pregunta. La cuarta función de la Function App pasa de ser una API genérica a ser el webhook de Telegram, que además corre el agente completo.

## Componentes, mapeados a lo que pide el caso

El caso pide que la arquitectura soporte: *ingesta y almacenamiento de datos, procesamiento analítico, ejecución del modelo y exposición de resultados*.

### Cómputo — una sola Azure Functions App (Consumption plan)

Las cuatro etapas de cómputo del proyecto viven en la **misma** Function App, como cuatro funciones separadas — un único recurso de Azure que desplegar y mantener:

- **Ingesta** (Timer, diaria): trae los archivos fuente (precios de X, Y, Z; registros de compra de Equipo1/Equipo2) y los deja en `raw/`. Reemplaza a Azure Data Factory.
- **Limpieza + Análisis** (Timer): la lógica de `01_limpieza_datos.ipynb` y `02_analisis_relacion_materias_primas_equipos.ipynb`, empaquetada como funciones de Python con las mismas dependencias de [requirements.txt](../requirements.txt).
- **Pronóstico** (Timer): el modelo de la Fase 3, se reentrena antes de cada fase del proyecto.
- **Webhook de Telegram** (HTTP): el mismo código de `app/agente.py` y `app/tools.py` que ya probamos local — Telegram le hace un `POST` cada vez que alguien le escribe al bot, la función corre el ciclo completo del agente (decide qué herramienta usar, la ejecuta, le responde a Azure OpenAI, redacta la respuesta) y contesta llamando a la API de Telegram. Es el único punto de la Function App con tráfico impredecible (depende de cuánto use el bot el evaluador), pero sigue siendo consumo bajo para una demo.

El plan **Consumption** de Azure Functions incluye una cuota gratuita mensual (1 millón de ejecuciones + 400.000 GB-s de cómputo) que se renueva cada mes, sin límite de tiempo. Los tres jobs diarios y una conversación de demo por Telegram no se acercan a ese límite — en la práctica, este componente cuesta **$0** (el único costo real que cuelga de aquí es Azure OpenAI, que se paga aparte, por token).

### Almacenamiento — Azure Blob Storage

Mismo esquema de carpetas que ya tiene este repo: `raw/` (copia fiel de la fuente), `processed/` (salidas de limpieza y análisis), `models/` (artefactos del pronóstico) y `reports/` (figuras e informes). Se usa Blob Storage estándar en vez de Data Lake Storage Gen2 porque no se necesita namespace jerárquico ni permisos a nivel de carpeta para este proyecto. Los primeros ~5GB son gratis durante 12 meses; después, dado que el dataset pesa unos pocos MB, el costo es de centavos de dólar al mes.

### Resultados — Azure Cosmos DB (nivel gratuito)

Dos contenedores documentales en vez de tablas relacionales, para no depender de leer CSVs en cada consulta:

- `resumen_relacion` — un documento por combinación materia prima–equipo (particionado por `equipo`), equivalente a `resumen_relacion_materias_primas_equipos.csv`.
- `pronostico_equipos` — un documento por fecha pronosticada (particionado por `equipo`), equivalente a `pronostico_equipos.csv`.
- `conversaciones` — un documento por `chat_id` de Telegram, con el historial de mensajes de esa conversación. Hace falta porque una Azure Function no mantiene estado entre invocaciones (a diferencia del prototipo local, que guarda la memoria en `st.session_state` mientras el proceso de Streamlit sigue corriendo) — el webhook lee este documento al recibir un mensaje y lo reescribe con la respuesta antes de terminar.

Azure ofrece **1.000 RU/s y 25GB de almacenamiento gratis por cuenta, sin límite de tiempo** (a diferencia del storage, que solo es gratis 12 meses) — de sobra para el volumen de este proyecto. Se prefirió sobre Azure SQL Database porque el patrón de acceso (leer un documento pequeño por clave `equipo`) encaja igual de bien con un modelo de documentos, y porque el proveedor de Cosmos DB ya está habilitado en la cuenta de Azure que se va a usar (ver "Por qué esta versión" arriba).

### Consumo — Telegram

El evaluador (o el equipo de planeación financiera) habla con el bot como hablaría con cualquier contacto de Telegram — no hay una URL que visitar, ni una interfaz que mantener funcionando:

- **Telegram Bot API**: gratis, sin costo por bot ni por mensaje. El bot se crea una sola vez hablando con `@BotFather` dentro de Telegram, que entrega un token — eso es lo único manual del lado de Telegram.
- **Webhook, no *polling***: en vez de que nuestra función esté preguntando todo el rato "¿hay mensajes nuevos?" (lo que sí hace el prototipo local, con *long polling*, para no depender de una URL pública), en producción Telegram llama directo a la función cada vez que hay un mensaje nuevo — más eficiente y más barato, encaja mejor con un modelo serverless que paga por ejecución.
- **Ya probado en local** con datos y modelo reales (ver `app/README.md`) — pasar de local a este diseño es cambiar de dónde saca el `chat_id`/mensaje (input en consola → payload del webhook) y de dónde saca la memoria (variable en memoria → contenedor `conversaciones` de Cosmos DB), sin tocar la lógica del agente en sí.

Power BI y una interfaz web propia quedan fuera de esta versión — si más adelante hace falta un dashboard visual, se puede agregar un endpoint HTTP adicional en la misma Function App sin rehacer nada de esto.

## Seguridad y operación transversal

También elegidos por su nivel gratuito:

- **Azure Key Vault** — secretos y credenciales (incluido el token del bot de Telegram y la key de Azure OpenAI); costo casi nulo a este volumen de operaciones.
- **Microsoft Entra ID** — control de acceso, incluido sin costo adicional en cualquier suscripción de Azure.
- **Azure Monitor / Log Analytics** — nivel gratuito de 5GB de datos de logs al mes.
- **GitHub Actions** (en vez de Azure DevOps) — CI/CD gratis para repositorios públicos o privados, y ya es donde vive el código.

## Costo estimado total

**~$0/mes** dentro del uso esperado de este proyecto: el cómputo (Functions, incluido el webhook de Telegram), la base de datos (Cosmos DB) y la interfaz (Telegram Bot API) caen dentro de niveles siempre-gratuitos, y el storage es gratis los primeros 12 meses (después, centavos). El único gasto real de todo el diseño es Azure OpenAI, que paga por uso de tokens — y aun así, mínimo para una demo.

## Qué queda pendiente

- Validar este planteamiento contigo antes de pasarlo al informe.
- Crear el bot en Telegram (hablar con `@BotFather`, elegir nombre y obtener el token) — es un paso manual tuyo, nadie más puede hacerlo por vos.
- Revisar si conviene acotar el uso de tokens de Azure OpenAI (ej. límites de contexto, cachear respuestas) para mantener ese único costo lo más bajo posible.
- Despliegue mínimo real (ej. la Function App + Blob Storage + registrar el webhook con Telegram) para capturar el punto adicional que ofrece el caso por resolverlo en una nube — pendiente de tu confirmación, ya que implica usar una suscripción de Azure real.
