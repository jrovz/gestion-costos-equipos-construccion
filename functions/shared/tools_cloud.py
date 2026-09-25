"""Version cloud de app/tools.py: mismas herramientas del agente, mismo TOOLS/
DISPATCH (mismo esquema para Azure OpenAI), pero leyendo Cosmos DB / Blob
Storage en vez de los CSV locales de data/processed/. agente.ejecutar_turno()
no distingue entre esta version y la local -- solo se le pasa un TOOLS/DISPATCH
distinto (ver function_app.py).
"""
import tempfile
from pathlib import Path

from . import io_blob, io_cosmos

EQUIPOS_VALIDOS = {"Equipo1", "Equipo2"}

GRAFICOS_DISPONIBLES = {
    "series_normalizadas": {
        "archivo": "01_series_normalizadas.png",
        "descripcion": "Las 5 series (X, Y, Z, Equipo1, Equipo2) normalizadas en base 100 desde 2010, "
                       "para comparar su evolucion relativa.",
    },
    "correlacion_niveles_vs_retornos": {
        "archivo": "02_heatmap_niveles_vs_retornos.png",
        "descripcion": "Heatmap de correlacion de Pearson, niveles (precios crudos) vs. retornos -- "
                       "muestra por que correlacionar precios crudos es enganoso.",
    },
    "correlacion_cruzada": {
        "archivo": "03_ccf.png",
        "descripcion": "Correlacion cruzada (CCF) entre cada materia prima y cada equipo, rezagos +-20 dias "
                       "habiles -- muestra si algun insumo anticipa al equipo o si es todo contemporaneo.",
    },
    "importancia_shap": {
        "archivo": "04_shap.png",
        "descripcion": "Importancia SHAP (Random Forest) de cada materia prima sobre el precio de cada equipo.",
    },
    "comparacion_metodos_pronostico": {
        "archivo": "05_backtest_mape.png",
        "descripcion": "Error (MAPE) de los 4 metodos de pronostico probados (naive, media movil, ARIMA, VECM) "
                       "por horizonte, del backtesting de la Fase 3.",
    },
    "proyeccion_final": {
        "archivo": "06_proyeccion_final.png",
        "descripcion": "Proyeccion final de precio de cada equipo con banda de incertidumbre empirica.",
    },
}


def _validar_equipo(equipo: str) -> str | None:
    if equipo not in EQUIPOS_VALIDOS:
        return f"'{equipo}' no es valido. Usa 'Equipo1' o 'Equipo2'."
    return None


def consultar_relacion_insumo_equipo(equipo: str) -> dict:
    """Que materia prima explica el precio de este equipo, con que evidencia (Fase 2)."""
    error = _validar_equipo(equipo)
    if error:
        return {"error": error}

    filas = io_cosmos.leer_todos("resumen_relacion", particion=equipo)
    if not filas:
        return {"error": f"No hay datos de la Fase 2 para '{equipo}'."}

    dominante = max(filas, key=lambda f: f["shap_medio"])
    return {
        "equipo": equipo,
        "insumo_dominante": dominante["insumo"],
        "cointegra_largo_plazo": bool(dominante["cointegra_eg_5pct"]),
        "correlacion_en_retornos": round(float(dominante["corr_ccf"]), 3),
        "rezago_dias": int(dominante["lag_optimo_ccf"]),
        "detalle_por_insumo": [
            {k: f[k] for k in ("insumo", "signo_lasso", "cointegra_eg_5pct", "corr_ccf", "lag_optimo_ccf")}
            for f in filas
        ],
        "nota": "No hay diccionario de datos: se desconoce que materia prima real es "
                f"'{dominante['insumo']}'. Si quien pregunta la conoce, se puede usar "
                "para buscar contexto de mercado externo.",
    }


def consultar_pronostico(equipo: str) -> dict:
    """El pronostico del equipo, su horizonte confiable y la banda de incertidumbre (Fase 3)."""
    error = _validar_equipo(equipo)
    if error:
        return {"error": error}

    filas = [f for f in io_cosmos.leer_todos("pronostico_equipos", particion=equipo) if f.get("es_punto_de_control")]
    if not filas:
        return {"error": f"No hay pronostico calculado para '{equipo}'. Corre la funcion 'pronostico'."}
    fila = filas[0]

    columna = "price_equipo1" if equipo == "Equipo1" else "price_equipo2"
    hist = io_blob.leer_csv("processed", "dataset_equipos_limpio.csv", parse_dates=["date"]).set_index("date")

    return {
        "equipo": equipo,
        "ultimo_precio_conocido": round(float(hist[columna].iloc[-1]), 2),
        "fecha_ultimo_precio": str(hist.index[-1].date()),
        "pronostico": round(float(fila["pronostico"]), 2),
        "fecha_pronostico": fila["fecha"],
        "horizonte_dias_habiles": int(fila["horizonte_dias"]),
        "intervalo_90pct": [round(float(fila["ic_inferior"]), 2), round(float(fila["ic_superior"]), 2)],
        "metodo": fila["metodo"],
        "nota": "El intervalo sale del error real observado en el backtesting, no de un "
                "supuesto estadistico del modelo -- ver informe_proyeccion_costos.md.",
    }


def consultar_historico(equipo: str, dias: int = 30) -> dict:
    """Precios recientes del equipo, para dar contexto antes de hablar de pronostico."""
    error = _validar_equipo(equipo)
    if error:
        return {"error": error}
    dias = max(1, min(int(dias), 180))

    hist = io_blob.leer_csv("processed", "dataset_equipos_limpio.csv", parse_dates=["date"]).set_index("date")
    columna = "price_equipo1" if equipo == "Equipo1" else "price_equipo2"
    serie = hist[columna].tail(dias)

    return {
        "equipo": equipo,
        "dias_consultados": dias,
        "precio_minimo": round(float(serie.min()), 2),
        "precio_maximo": round(float(serie.max()), 2),
        "precio_promedio": round(float(serie.mean()), 2),
        "ultimos_5_precios": [
            {"fecha": str(fecha.date()), "precio": round(float(valor), 2)}
            for fecha, valor in serie.tail(5).items()
        ],
    }


def mostrar_grafico(nombre: str) -> dict:
    """Devuelve la ruta de un grafico ya generado en el analisis (Fase 2 o 3), para mostrarlo en el chat."""
    info = GRAFICOS_DISPONIBLES.get(nombre)
    if info is None:
        return {"error": f"'{nombre}' no es un grafico valido. Opciones: {list(GRAFICOS_DISPONIBLES)}"}

    if not io_blob.existe_blob("reports", info["archivo"]):
        return {"error": f"El archivo {info['archivo']} no existe todavia en el contenedor reports/."}

    ruta_temp = str(Path(tempfile.gettempdir()) / info["archivo"])
    io_blob.descargar_a_temp("reports", info["archivo"], ruta_temp)
    return {"nombre": nombre, "ruta": ruta_temp, "descripcion": info["descripcion"]}


def buscar_contexto_mercado(termino_busqueda: str, max_resultados: int = 5) -> dict:
    """Busqueda web de contexto de mercado externo (noticias, tendencias, precios).

    Requiere un nombre de producto o mercado concreto -- si no se conoce, hay que
    preguntarle a quien esta conversando en vez de inventar uno.
    """
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        with DDGS() as buscador:
            resultados = list(buscador.text(termino_busqueda, max_results=max_resultados))

        return {
            "termino_busqueda": termino_busqueda,
            "resultados": [
                {"titulo": r.get("title"), "resumen": r.get("body"), "url": r.get("href")}
                for r in resultados
            ],
        }
    except Exception as exc:
        return {"error": f"No se pudo completar la busqueda: {exc}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_relacion_insumo_equipo",
            "description": consultar_relacion_insumo_equipo.__doc__,
            "parameters": {
                "type": "object",
                "properties": {"equipo": {"type": "string", "enum": ["Equipo1", "Equipo2"]}},
                "required": ["equipo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_pronostico",
            "description": consultar_pronostico.__doc__,
            "parameters": {
                "type": "object",
                "properties": {"equipo": {"type": "string", "enum": ["Equipo1", "Equipo2"]}},
                "required": ["equipo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_historico",
            "description": consultar_historico.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "equipo": {"type": "string", "enum": ["Equipo1", "Equipo2"]},
                    "dias": {"type": "integer", "description": "Dias habiles hacia atras (1-180)", "default": 30},
                },
                "required": ["equipo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mostrar_grafico",
            "description": mostrar_grafico.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {
                        "type": "string",
                        "enum": list(GRAFICOS_DISPONIBLES.keys()),
                        "description": " | ".join(f"{k}: {v['descripcion']}" for k, v in GRAFICOS_DISPONIBLES.items()),
                    },
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_contexto_mercado",
            "description": buscar_contexto_mercado.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "termino_busqueda": {
                        "type": "string",
                        "description": "Nombre real de un producto o mercado (ej. 'precio del cemento'). "
                                       "Nunca uses 'X', 'Y', 'Z' o 'Equipo1/2' como termino de busqueda.",
                    },
                    "max_resultados": {"type": "integer", "default": 5},
                },
                "required": ["termino_busqueda"],
            },
        },
    },
]

DISPATCH = {
    "consultar_relacion_insumo_equipo": consultar_relacion_insumo_equipo,
    "consultar_pronostico": consultar_pronostico,
    "consultar_historico": consultar_historico,
    "mostrar_grafico": mostrar_grafico,
    "buscar_contexto_mercado": buscar_contexto_mercado,
}
