# Agente de IA — Fase 4

Expone los hallazgos de las Fases 1-3 en un chat conversacional: qué materia prima explica a cada equipo, el pronóstico con su incertidumbre, e información de mercado externa cuando se le pide. También va a poder recibir precios nuevos por el mismo chat (ver "Qué puede responder").

## Cómo correrlo

1. Activar el entorno virtual del proyecto (`../venv`) e instalar dependencias si falta alguna:
   ```bash
   pip install -r ../requirements.txt
   ```
2. Copiar `.env.example` a `.env` en esta misma carpeta y completar los datos de tu recurso de Azure OpenAI (API key, endpoint, nombre del deployment). `.env` está en `.gitignore` — nunca se sube al repositorio.
3. Correr la interfaz de chat:
   ```bash
   streamlit run ui_streamlit.py
   ```
   O, para probar rápido desde la terminal sin abrir el navegador:
   ```bash
   python agente.py
   ```
   O, para probar por Telegram (ver la sección de abajo para crear el bot primero):
   ```bash
   python telegram_bot.py
   ```

## Qué puede responder

- "¿Qué materia prima explica el precio de Equipo1?" → `consultar_relacion_insumo_equipo`
- "¿Cuál es el pronóstico de Equipo2?" → `consultar_pronostico`
- "¿Cómo se ha movido el precio de Equipo1 el último mes?" → `consultar_historico`
- "¿Qué está pasando en el mercado de [producto real]?" → `buscar_contexto_mercado` — si no le das el nombre real del producto, te lo va a preguntar primero, porque el proyecto no tiene diccionario de datos y no sabe a qué materia prima real corresponden `X`, `Y`, `Z` (ver `../GLOSARIO.md`).
- "¿Qué diferencia hay entre vos y el modelo que hizo el pronóstico?" → lo explica él mismo (ver abajo).
- "Muéstrame el gráfico de SHAP" (o pedir cualquier figura ya generada en la Fase 2 o 3) → `mostrar_grafico`, adjunta el PNG correspondiente de `reports/figures/`.
- "X = 87.32" (o similar) → `registrar_precio_insumo` **(planeada, todavía no implementada)** — la fecha la pondría el servidor, no quien escribe ni el modelo; validaría el salto contra el último precio conocido (mismo umbral del 15% de la Fase 1) antes de guardarlo. Ver `../infra/README.md`.

## IA convencional vs. Agente de IA — aplicado a este proyecto

Este proyecto tiene ejemplos concretos de los dos, uno al lado del otro:

**El modelo VECM de la Fase 3 es IA convencional.** Recibe una entrada fija (el histórico de precios) y devuelve una salida fija (un número de pronóstico y un intervalo). No decide nada por su cuenta, no sabe que existe una pregunta detrás, no recuerda nada de una ejecución a otra. Es exactamente la definición del caso: *"modelo que predice, clasifica o genera a partir de datos"*.

**Este agente es distinto** en los cuatro conceptos que pide el caso:

- **Autonomía** — decide por sí mismo qué hacer con cada pregunta: si hace falta consultar el pronóstico, la relación insumo-equipo, buscar en la web, o combinar varias cosas. Nadie le dice qué herramienta usar en cada caso, lo decide el modelo al leer la pregunta.
- **Uso de herramientas** — no "sabe" los resultados de memoria: los obtiene llamando funciones reales (`tools.py`) que leen los archivos generados por los notebooks. Si el dato no está ahí, no lo inventa.
- **Memoria** — mantiene el historial completo de la conversación (`st.session_state.mensajes` en la interfaz), así que una pregunta de seguimiento como "¿y a 6 meses?" se entiende en el contexto de lo que se preguntó antes.
- **Capacidad de acción** — puede ejecutar una búsqueda web real y traer información que no estaba en su entrenamiento ni en el dataset del proyecto, no solo generar texto a partir de lo que ya sabía.

## Estructura

| Archivo | Contenido |
|---|---|
| `tools.py` | Las 5 herramientas actuales (leen `data/processed/*.csv`, adjuntan una figura de `reports/figures/`, o hacen búsqueda web) y sus esquemas para function calling — falta agregar `registrar_precio_insumo` |
| `agente.py` | El loop conversacional: llama al modelo, ejecuta las tool calls que pida, hasta que responde en texto. Sin frameworks — el mecanismo queda a la vista |
| `ui_streamlit.py` | La interfaz de chat para probar/depurar local |
| `telegram_bot.py` | Prototipo local del bot de Telegram (*long polling*) — la interfaz real de consumo |
| `.env.example` | Plantilla de variables de entorno (credenciales de Azure OpenAI y token de Telegram) |

## Telegram — la interfaz real de consumo

Streamlit fue la interfaz para construir y probar el agente; la interfaz con la que el evaluador va a hablar de verdad es **Telegram** — así quedó decidido con el diseño de arquitectura (`../infra/README.md`). `telegram_bot.py` reutiliza el mismo `ejecutar_turno()` de `agente.py` tal cual — no hay lógica nueva del agente, solo una capa de entrada/salida distinta.

**Cómo crear el bot y probarlo:**

1. En Telegram, buscar `@BotFather` y mandarle `/newbot`. Elegir un nombre y un usuario (debe terminar en `bot`, ej. `costos_equipos_bot`).
2. BotFather devuelve un token (`123456:ABC-...`) — copiarlo a `TELEGRAM_BOT_TOKEN` en `app/.env`.
3. Correr `python telegram_bot.py` — queda escuchando mensajes (*long polling*, no necesita URL pública ni abrir puertos).
4. Buscar el bot por su usuario dentro de Telegram y escribirle — las respuestas del agente llegan por el mismo chat.

**Diferencia con producción (Azure)**: acá el bot le pregunta a Telegram "¿hay mensajes nuevos?" en un loop (*polling*) y guarda la memoria en un diccionario `{chat_id: [mensajes]}` mientras el proceso vive. En Azure sería al revés — Telegram llama directo a una Function (*webhook*) cada vez que hay un mensaje nuevo, y la memoria vive en el contenedor `conversaciones` de Cosmos DB en vez de en RAM, porque una Function no mantiene estado entre invocaciones. El agente en sí (`agente.py`, `tools.py`) no cambia entre un modo y otro.

Falta agregar `registrar_precio_insumo` a `tools.py` (ver "Qué puede responder" arriba) — el bot ya funciona para consultas, ese es el siguiente paso.

## Limitaciones conocidas

- No hay diccionario de datos: el agente no puede nombrar la materia prima real detrás de `X`, `Y`, `Z` — solo puede describir su comportamiento estadístico (ver `GLOSARIO.md` e `INFORME.md`).
- La búsqueda web (`buscar_contexto_mercado`) usa un motor gratuito sin API key — resultados razonables para una demo, pero menos robustos que una API de búsqueda dedicada (ver alternativas en `../infra/README.md`).
- Si algo falla, tanto `telegram_bot.py` como el webhook en Azure le muestran a quien escribe el texto crudo de la excepción (`"Tuve un error procesando tu mensaje: {exc}"`) en vez de un mensaje genérico — pendiente de corregir, ver `../infra/README.md`.
- Ya desplegado en Azure (Functions + Azure OpenAI, con Telegram como interfaz) — ver `../functions/` y `../infra/README.md`.
