# Arquitectura propuesta — Azure (diseño de costo mínimo)

Diseño y documentación del entregable "Arquitectura propuesta en la nube" del caso. Es un **borrador de diseño**: por ahora no se despliega ningún recurso real en Azure, solo se documenta cómo se vería la solución completa en producción. El despliegue mínimo real queda para una siguiente etapa, una vez validado este planteamiento.

![Arquitectura propuesta en Azure](diagrama_arquitectura.svg)

## Por qué esta versión

Esta es la segunda versión del diseño, ajustada por dos motivos:

1. **Minimizar costo**: usar la mayor cantidad posible de niveles gratuitos de Azure en vez de servicios que cobran desde el primer uso.
2. **Ser defendible como candidato junior**: menos servicios distintos, cada uno con una razón concreta y fácil de explicar, en vez de una arquitectura "enterprise" con herramientas (Data Factory, Container Apps, orquestadores) que un junior normalmente no ha operado todavía. Reconocer que no hace falta esa complejidad para este volumen de datos es, en sí mismo, una señal de criterio.

Cambios respecto a la primera versión: se reemplazó Azure Data Factory + Azure Container Apps Jobs (dos servicios de cómputo distintos) por **una sola Azure Functions App** con cuatro funciones adentro; se cambió Data Lake Storage Gen2 por **Blob Storage** normal (no se necesitan sus funciones de big data); y se quitó Power BI del alcance para no sumar un servicio que, para compartir tableros, requiere licencia Pro de pago.

## Componentes, mapeados a lo que pide el caso

El caso pide que la arquitectura soporte: *ingesta y almacenamiento de datos, procesamiento analítico, ejecución del modelo y exposición de resultados*.

### Cómputo — una sola Azure Functions App (Consumption plan)

Las cuatro etapas de cómputo del proyecto viven en la **misma** Function App, como cuatro funciones separadas — un único recurso de Azure que desplegar y mantener:

- **Ingesta** (Timer, diaria): trae los archivos fuente (precios de X, Y, Z; registros de compra de Equipo1/Equipo2) y los deja en `raw/`. Reemplaza a Azure Data Factory.
- **Limpieza + Análisis** (Timer): la lógica de `01_limpieza_datos.ipynb` y `02_analisis_relacion_materias_primas_equipos.ipynb`, empaquetada como funciones de Python con las mismas dependencias de [requirements.txt](../requirements.txt).
- **Pronóstico** (Timer): el modelo de la Fase 3, se reentrena antes de cada fase del proyecto.
- **API de resultados** (HTTP): expone el resumen y el pronóstico — el punto que consumirá el Agente de IA.

El plan **Consumption** de Azure Functions incluye una cuota gratuita mensual (1 millón de ejecuciones + 400.000 GB-s de cómputo) que se renueva cada mes, sin límite de tiempo. Un job que corre una vez al día y una API de bajo tráfico no se acercan a ese límite — en la práctica, este componente cuesta **$0**.

### Almacenamiento — Azure Blob Storage

Mismo esquema de carpetas que ya tiene este repo: `raw/` (copia fiel de la fuente), `processed/` (salidas de limpieza y análisis), `models/` (artefactos del pronóstico) y `reports/` (figuras e informes). Se usa Blob Storage estándar en vez de Data Lake Storage Gen2 porque no se necesita namespace jerárquico ni permisos a nivel de carpeta para este proyecto. Los primeros ~5GB son gratis durante 12 meses; después, dado que el dataset pesa unos pocos MB, el costo es de centavos de dólar al mes.

### Resultados — Azure SQL Database (nivel gratuito)

Tablas consultables (`resumen_relacion_materias_primas_equipos`, `pronostico_equipos`) para no depender de leer CSVs en cada consulta. Azure ofrece **una base de datos gratis por suscripción** (hasta 32GB de almacenamiento y 100.000 vCore-segundos de cómputo al mes) — alcanza de sobra para el volumen de este proyecto.

### Consumo

- **Agente de IA (Fase 4, todavía no construido)**: consumiría la API de resultados como herramienta, y podría combinarla con búsqueda web para contexto de mercado externo. Es el **único componente sin nivel gratuito** — Azure OpenAI Service cobra por token — pero para una demo el consumo esperado es de centavos.
- **Evaluador / equipo de planeación financiera**: usuario final de la API (vía el agente, o directo si se necesita).

Power BI queda fuera de esta versión: la API ya deja los datos disponibles si más adelante se decide agregar un dashboard, sin comprometerse ahora a un servicio que para compartirse necesita licencia de pago.

## Seguridad y operación transversal

También elegidos por su nivel gratuito:

- **Azure Key Vault** — secretos y credenciales; costo casi nulo a este volumen de operaciones.
- **Microsoft Entra ID** — control de acceso, incluido sin costo adicional en cualquier suscripción de Azure.
- **Azure Monitor / Log Analytics** — nivel gratuito de 5GB de datos de logs al mes.
- **GitHub Actions** (en vez de Azure DevOps) — CI/CD gratis para repositorios públicos o privados, y ya es donde vive el código.

## Costo estimado total

**~$0/mes** dentro del uso esperado de este proyecto: todo el cómputo y la base de datos caen dentro de niveles siempre-gratuitos de Azure, y el storage es gratis los primeros 12 meses (después, centavos). El único gasto real de todo el diseño es el Agente de IA de la Fase 4, que paga por uso de tokens — y aun así, mínimo para una demo.

## Qué queda pendiente

- Validar este planteamiento contigo antes de pasarlo al informe.
- Cuando se aborde la Fase 4 (Agente de IA), revisar si conviene acotar aún más el uso de tokens (ej. límites de contexto, cachear respuestas) para mantener ese único costo lo más bajo posible.
- Despliegue mínimo real (ej. la Function App + Blob Storage) para capturar el punto adicional que ofrece el caso por resolverlo en una nube — pendiente de tu confirmación, ya que implica usar una suscripción de Azure real.
