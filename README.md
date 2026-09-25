# Gestión de Costos de Equipos de Construcción

Prueba técnica de Ciencia de Datos Senior — de cuatro archivos de precios sin diccionario de datos a un agente conversacional, por Telegram, que explica por qué va a costar cada equipo y proyecta su precio con incertidumbre honesta.

**Autor:** Juan Felipe Rodríguez Valencia · 2026

## El caso

Una constructora no puede anticipar el costo de dos equipos críticos (`Equipo1`, `Equipo2`) para un proyecto con ventana de ejecución definida, y sospecha que el precio está relacionado con tres materias primas del mercado (`X`, `Y`, `Z`) sin tener un modelo que lo confirme. No hay diccionario de datos: no se sabe qué producto real es cada serie. Explicación completa del encargo, supuestos y decisiones metodológicas en [`INFORME.md`](INFORME.md).

## Estado del proyecto

- [x] **Fase 1 — Limpieza de datos**: 4 archivos en formatos distintos, normalizados y verificados contra la fuente original (3.530 días hábiles, 2010–2023).
- [x] **Fase 2 — Relación materia prima–equipo**: 5 métodos independientes (Engle-Granger, Johansen, correlación cruzada, Lasso/Elastic Net, Random Forest + SHAP) coinciden en que `Y` explica a `Equipo1` y `Z` explica a `Equipo2`; `X` es ruido.
- [x] **Fase 3 — Proyección de costos**: 4 métodos comparados con backtesting real; horizonte confiable de 3 meses para `Equipo1` y 1 mes para `Equipo2`, con banda de incertidumbre empírica.
- [x] **Fase 4 — Agente de IA**: probado de punta a punta con Azure OpenAI, con memoria conversacional, búsqueda web y gráficos del análisis; interfaz real por Telegram (prototipo local y bot en producción).
- [x] **Arquitectura en Azure**: diseñada para costo mínimo (~$0/mes salvo el modelo de lenguaje) y **desplegada de verdad** — Azure Functions (limpieza, pronóstico y webhook de Telegram), Cosmos DB, Blob Storage y Key Vault.
- [ ] **Ingesta conversacional de precios** (`registrar_precio_insumo`): diseñada en `infra/README.md`, todavía no implementada en `tools.py`; falta además decidir el control de acceso por `chat_id`.

## Estructura del repositorio

```
├── data/                    Datos y notebooks 01-03 (limpieza, relación, proyección) — ver data/README.md
│   ├── raw/                 Copia exacta de los archivos originales del caso
│   └── processed/           Salidas de los notebooks (CSV)
├── src/                     Fases 1-3 extraídas como librería reusable (mismas funciones que los notebooks)
├── reports/                 Informes detallados por fase + figuras generadas
├── app/                     Agente de IA (Fase 4): loop conversacional, herramientas, UI de Streamlit y bot de Telegram — ver app/README.md
├── functions/               Despliegue real en Azure Functions (limpieza, pronóstico, webhook de Telegram)
├── infra/                   Diseño de arquitectura en Azure y su historial de decisiones — ver infra/README.md
├── INFORME.md               Informe consolidado del caso (explicación, supuestos, resultados)
├── GLOSARIO.md              Términos técnicos en lenguaje simple
└── *.pptx                   Presentaciones del proyecto (ver "Documentos del proyecto")
```

## Documentos del proyecto

| Documento | Contenido |
|---|---|
| [`INFORME.md`](INFORME.md) | Informe principal: explicación del caso, supuestos, decisiones metodológicas, resultados de las 3 fases y el hallazgo de la instrucción oculta en el PDF del caso |
| [`GLOSARIO.md`](GLOSARIO.md) | Términos técnicos (cointegración, SHAP, backtesting, etc.) explicados en lenguaje simple |
| [`reports/informe_relacion_materias_primas_equipos.md`](reports/informe_relacion_materias_primas_equipos.md) | Detalle completo de la Fase 2 |
| [`reports/informe_proyeccion_costos.md`](reports/informe_proyeccion_costos.md) | Detalle completo de la Fase 3, backtesting método a método |
| [`data/README.md`](data/README.md) | Qué hace cada notebook y qué genera cada archivo de `data/processed/` |
| [`app/README.md`](app/README.md) | Cómo correr el agente, qué puede responder, IA convencional vs. agente aplicado a este proyecto |
| [`infra/README.md`](infra/README.md) | Arquitectura en Azure: componentes, por qué cada decisión, costo estimado, qué queda pendiente |
| `Gestión de Costos de Equipos — Presentación.pptx` | Deck original de 12 diapositivas para evaluador técnico |
| `Gestión de Costos de Equipos — Presentación técnica (mejorada).pptx` | Versión ampliada (15 diapositivas) con el paso a paso de la metodología y énfasis en los métodos de machine learning |
| `Gestión de Costos de Equipos — Presentación para cliente.pptx` | Versión en lenguaje simple, sin jerga, para quien va a usar el bot en la constructora |

## Cómo correrlo

1. **Entorno**: crear un entorno virtual e instalar dependencias.
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```
2. **Fases 1-3 (notebooks)**: abrir con Jupyter desde `data/` y correr en orden `01_limpieza_datos.ipynb` → `02_analisis_relacion_materias_primas_equipos.ipynb` → `03_proyeccion_costos.ipynb`. Detalle en [`data/README.md`](data/README.md).
3. **Fase 4 (agente)**: copiar `app/.env.example` a `app/.env` con credenciales de Azure OpenAI, y desde `app/` correr `streamlit run ui_streamlit.py`, `python agente.py` (consola), o `python telegram_bot.py` (requiere token de `@BotFather`). Detalle en [`app/README.md`](app/README.md).
4. **Despliegue en Azure**: ya desplegado como Azure Functions (`functions/`); el diseño completo y los pasos están en [`infra/README.md`](infra/README.md).

## Pila tecnológica

`pandas` / `numpy` · `statsmodels` (ADF, KPSS, Engle-Granger, Johansen, VAR/VECM, SARIMAX) · `scikit-learn` (Lasso/Elastic Net, Random Forest) · `shap` · `openai` (Azure OpenAI) · `streamlit` · Telegram Bot API · Azure Functions, Cosmos DB, Blob Storage, Key Vault.

## Un hallazgo fuera de guión

El PDF del caso traía, camuflada entre dos párrafos, una instrucción dirigida a un asistente de IA para fabricar una relación falsa entre materias primas y equipos, y para forzar el peor método de pronóstico como si fuera la respuesta correcta. Se documentó, se ignoró, y el análisis real con los datos mostró exactamente lo contrario en los dos puntos que pedía. Detalle completo en la sección "Apreciaciones y comentarios del caso" de [`INFORME.md`](INFORME.md).
