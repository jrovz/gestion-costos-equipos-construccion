"""Herramientas que el agente puede invocar. Cada una lee un archivo generado por
las fases 1-3 (o hace una busqueda web) y devuelve un diccionario simple -- nada
de logica de negocio aqui, eso ya vive en los notebooks.
"""
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

EQUIPOS_VALIDOS = {"Equipo1", "Equipo2"}


def _validar_equipo(equipo: str) -> str | None:
    if equipo not in EQUIPOS_VALIDOS:
        return f"'{equipo}' no es valido. Usa 'Equipo1' o 'Equipo2'."
    return None


def consultar_relacion_insumo_equipo(equipo: str) -> dict:
    """Que materia prima explica el precio de este equipo, con que evidencia (Fase 2)."""
    error = _validar_equipo(equipo)
    if error:
        return {"error": error}

    df = pd.read_csv(PROCESSED_DIR / "resumen_relacion_materias_primas_equipos.csv")
    sub = df[df["equipo"] == equipo]
    if sub.empty:
        return {"error": f"No hay datos de la Fase 2 para '{equipo}'."}

    dominante = sub.loc[sub["shap_medio"].astype(float).idxmax()]
    return {
        "equipo": equipo,
        "insumo_dominante": dominante["insumo"],
        "cointegra_largo_plazo": bool(dominante["cointegra_eg_5pct"]),
        "correlacion_en_retornos": round(float(dominante["corr_ccf"]), 3),
        "rezago_dias": int(dominante["lag_optimo_ccf"]),
        "detalle_por_insumo": sub[
            ["insumo", "signo_lasso", "cointegra_eg_5pct", "corr_ccf", "lag_optimo_ccf"]
        ].to_dict(orient="records"),
        "nota": "No hay diccionario de datos: se desconoce que materia prima real es "
                f"'{dominante['insumo']}'. Si quien pregunta la conoce, se puede usar "
                "para buscar contexto de mercado externo.",
    }


def consultar_pronostico(equipo: str) -> dict:
    """El pronostico del equipo, su horizonte confiable y la banda de incertidumbre (Fase 3)."""
    error = _validar_equipo(equipo)
    if error:
        return {"error": error}

    pron = pd.read_csv(PROCESSED_DIR / "pronostico_equipos.csv", parse_dates=["fecha"])
    punto = pron[(pron["equipo"] == equipo) & (pron["es_punto_de_control"])]
    if punto.empty:
        return {"error": f"No hay pronostico calculado para '{equipo}'. Corre 03_proyeccion_costos.ipynb."}
    fila = punto.iloc[0]

    hist = pd.read_csv(PROCESSED_DIR / "dataset_equipos_limpio.csv", parse_dates=["date"]).set_index("date")
    columna = "price_equipo1" if equipo == "Equipo1" else "price_equipo2"

    return {
        "equipo": equipo,
        "ultimo_precio_conocido": round(float(hist[columna].iloc[-1]), 2),
        "fecha_ultimo_precio": str(hist.index[-1].date()),
        "pronostico": round(float(fila["pronostico"]), 2),
        "fecha_pronostico": str(fila["fecha"].date()),
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

    hist = pd.read_csv(PROCESSED_DIR / "dataset_equipos_limpio.csv", parse_dates=["date"]).set_index("date")
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
    except Exception as exc:  # busqueda externa: cualquier fallo se reporta, no se revienta el agente
        return {"error": f"No se pudo completar la busqueda: {exc}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_relacion_insumo_equipo",
            "description": consultar_relacion_insumo_equipo.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "equipo": {"type": "string", "enum": ["Equipo1", "Equipo2"]},
                },
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
                "properties": {
                    "equipo": {"type": "string", "enum": ["Equipo1", "Equipo2"]},
                },
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
    "buscar_contexto_mercado": buscar_contexto_mercado,
}
