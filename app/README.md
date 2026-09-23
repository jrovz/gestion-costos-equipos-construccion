# Agente de IA — Fase 4

Expone los hallazgos de las Fases 1-3 en un chat conversacional: qué materia prima explica a cada equipo, el pronóstico con su incertidumbre, e información de mercado externa cuando se le pide.

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

## Qué puede responder

- "¿Qué materia prima explica el precio de Equipo1?" → `consultar_relacion_insumo_equipo`
- "¿Cuál es el pronóstico de Equipo2?" → `consultar_pronostico`
- "¿Cómo se ha movido el precio de Equipo1 el último mes?" → `consultar_historico`
- "¿Qué está pasando en el mercado de [producto real]?" → `buscar_contexto_mercado` — si no le das el nombre real del producto, te lo va a preguntar primero, porque el proyecto no tiene diccionario de datos y no sabe a qué materia prima real corresponden `X`, `Y`, `Z` (ver `../GLOSARIO.md`).
- "¿Qué diferencia hay entre vos y el modelo que hizo el pronóstico?" → lo explica él mismo (ver abajo).

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
| `tools.py` | Las 4 herramientas (leen `data/processed/*.csv` o hacen búsqueda web) y sus esquemas para function calling |
| `agente.py` | El loop conversacional: llama al modelo, ejecuta las tool calls que pida, hasta que responde en texto. Sin frameworks — el mecanismo queda a la vista |
| `ui_streamlit.py` | La interfaz de chat |
| `.env.example` | Plantilla de variables de entorno (credenciales de Azure OpenAI) |

## Limitaciones conocidas

- No hay diccionario de datos: el agente no puede nombrar la materia prima real detrás de `X`, `Y`, `Z` — solo puede describir su comportamiento estadístico (ver `GLOSARIO.md` e `INFORME.md`).
- La búsqueda web (`buscar_contexto_mercado`) usa un motor gratuito sin API key — resultados razonables para una demo, pero menos robustos que una API de búsqueda dedicada (ver alternativas en `../infra/README.md`).
- Corre en local por ahora; el despliegue en Azure (Container Apps + Azure OpenAI) está en el diseño de `../infra/` pero no se ha desplegado todavía.
