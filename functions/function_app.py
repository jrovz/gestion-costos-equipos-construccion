"""Las 3 funciones de la arquitectura, en una sola Azure Functions App:

- limpieza_analisis (Timer, diario): Fase 1 + Fase 2, reusando src/limpieza.py
  y src/relacion.py sin modificarlos -- baja los CSV de raw/ a un temporal,
  llama las mismas funciones que corren en los notebooks, sube los resultados.
- pronostico (Timer, diario): Fase 3, reusando src/pronostico.py igual de intacto.
- webhook_telegram (HTTP): recibe los mensajes del bot y corre el mismo
  agente.ejecutar_turno() ya probado en local, con la version cloud de las
  herramientas (shared/tools_cloud.py) en vez de la que lee CSV local.

NOTA DE DESPLIEGUE: para publicar a Azure, `src/` y `app/` deben copiarse
dentro de esta carpeta (`functions/src/`, `functions/app/`) porque el zip de
despliegue solo incluye lo que esta en `functions/`. Para probar local con
`func start` no hace falta: este archivo ya sabe buscarlos en `../src` y
`../app` si no encuentra la copia local.
"""
import json
import logging
import math
import os
import sys
import tempfile
from pathlib import Path

import azure.functions as func
import numpy as np
import pandas as pd

FUNCTIONS_DIR = Path(__file__).resolve().parent
REPO_ROOT = FUNCTIONS_DIR.parent

# "src" se importa como paquete (`from src import limpieza`) -> hace falta su carpeta
# padre en sys.path. "app" se importa plano (`from agente import ...`, y agente.py a su
# vez hace `from tools import ...`) -> hace falta la carpeta de app/ misma en sys.path.
_src_local = FUNCTIONS_DIR / "src"
sys.path.insert(0, str(_src_local.parent if _src_local.exists() else REPO_ROOT))

_app_local = FUNCTIONS_DIR / "app"
sys.path.insert(0, str(_app_local if _app_local.exists() else REPO_ROOT / "app"))

from shared import io_blob, io_cosmos, tools_cloud  # noqa: E402

# OJO: nada de "from src import relacion / pronostico" aca arriba. relacion.py
# carga shap (que arrastra numba/llvmlite) y pronostico.py carga statsmodels --
# juntos tardan mas de 30s en importarse. Si esto estuviera a nivel de modulo,
# el host de Azure tendria que pagar ese costo en CADA arranque, incluso para
# el webhook, que no los necesita -- y probablemente supera el timeout de
# indexado del host (fue la causa real del primer despliegue fallido: 0
# funciones detectadas). Se importan adentro de limpieza_analisis y
# pronostico_fn, que son las unicas que los usan y corren una vez al dia.

app = func.FunctionApp()

# Todo lo que necesita Key Vault (y por lo tanto una llamada de red) queda afuera
# del nivel de modulo a proposito: el host de Azure Functions tiene que poder
# *importar* function_app.py rapido y sin depender de un servicio externo para
# poder indexar las funciones. Se inicializa perezoso, una vez, en el primer
# request real -- no en el import.
_ejecutar_turno = None
_TELEGRAM_API = None


def _inicializar():
    global _ejecutar_turno, _TELEGRAM_API
    if _ejecutar_turno is not None:
        return

    from shared.keyvault import obtener_secreto

    for var, secreto in [
        ("AZURE_OPENAI_API_KEY", "azure-openai-api-key"),
        ("AZURE_OPENAI_ENDPOINT", "azure-openai-endpoint"),
        ("AZURE_OPENAI_DEPLOYMENT", "azure-openai-deployment"),
        ("AZURE_OPENAI_API_VERSION", "azure-openai-api-version"),
    ]:
        os.environ.setdefault(var, obtener_secreto(secreto))

    from agente import ejecutar_turno
    _ejecutar_turno = ejecutar_turno
    _TELEGRAM_API = f"https://api.telegram.org/bot{obtener_secreto('telegram-bot-token')}"


def _blob_a_temp(contenedor: str, nombre_blob: str) -> str:
    ruta = str(Path(tempfile.gettempdir()) / nombre_blob)
    return io_blob.descargar_a_temp(contenedor, nombre_blob, ruta)


def _limpio(valor):
    """Convierte tipos de numpy/pandas a tipos nativos de Python, serializables a JSON.
    NaN (los campos de banda en filas que no son el punto de control) se vuelve None:
    JSON no soporta NaN, y Cosmos rechaza el documento entero si lo encuentra."""
    if hasattr(valor, "item"):
        valor = valor.item()
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


@app.timer_trigger(schedule="0 0 6 * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def limpieza_analisis(timer: func.TimerRequest) -> None:
    """Fase 1 + Fase 2: corre sobre el historico en Blob Storage, publica resumen_relacion en Cosmos DB."""
    from src import limpieza, relacion
    from src.config import COLS, EQUIPOS, MATERIAS, NOMBRES

    logging.info("limpieza_analisis: inicio")

    df_x = limpieza.normalizar_columnas(limpieza.cargar_x(_blob_a_temp("raw", "X.csv")), {"Date": "date", "Price": "price_x"})
    df_y = limpieza.normalizar_columnas(limpieza.cargar_y(_blob_a_temp("raw", "Y.csv")), {"Date": "date", "Price": "price_y"})
    df_z = limpieza.normalizar_columnas(limpieza.cargar_z(_blob_a_temp("raw", "Z.csv")), {"Date": "date", "Price": "price_z"})
    df_hist = limpieza.normalizar_columnas(
        limpieza.cargar_historico_equipos(_blob_a_temp("raw", "historico_equipos.csv")),
        {"Date": "date", "Price_X": "price_x", "Price_Y": "price_y", "Price_Z": "price_z",
         "Price_Equipo1": "price_equipo1", "Price_Equipo2": "price_equipo2"},
    )

    df_materias_primas = limpieza.combinar_materias_primas(df_x, df_y, df_z)
    chequeo = limpieza.verificar_contra_historico(df_hist, df_materias_primas)
    if (chequeo["diferencia_maxima"] > 1e-6).any():
        logging.warning("verificar_contra_historico encontro diferencias: %s", chequeo.to_dict())
    dataset_equipos_limpio = limpieza.construir_dataset_equipos_limpio(df_hist)

    io_blob.escribir_csv(df_materias_primas, "processed", "materias_primas_historico_completo.csv")
    io_blob.escribir_csv(dataset_equipos_limpio, "processed", "dataset_equipos_limpio.csv")
    logging.info("limpieza_analisis: Fase 1 lista (%s filas)", len(dataset_equipos_limpio))

    df = dataset_equipos_limpio.set_index("date")
    log_df, ret_df = relacion.calcular_retornos(df, COLS)

    tabla_eg = relacion.tabla_engle_granger(log_df, MATERIAS, EQUIPOS, NOMBRES)
    tabla_ccf, _ = relacion.tabla_ccf(ret_df, MATERIAS, EQUIPOS, NOMBRES)
    tabla_gr = relacion.tabla_granger(ret_df, MATERIAS, EQUIPOS, NOMBRES)
    resultados_lineales = relacion.ajustar_lasso_elasticnet(ret_df, MATERIAS, EQUIPOS, NOMBRES)
    resultados_rf = relacion.ajustar_random_forest_shap(resultados_lineales, MATERIAS, NOMBRES)
    tabla_resumen = relacion.construir_tabla_resumen(
        MATERIAS, EQUIPOS, NOMBRES, tabla_eg, tabla_gr, tabla_ccf, resultados_lineales, resultados_rf
    )

    documentos = []
    for fila in tabla_resumen.to_dict(orient="records"):
        fila = {k: _limpio(v) for k, v in fila.items()}
        fila["id"] = f"{fila['equipo']}_{fila['insumo']}"
        documentos.append(fila)
    io_cosmos.reemplazar_contenido("resumen_relacion", documentos)
    logging.info("limpieza_analisis: Fase 2 lista, %s filas en resumen_relacion", len(documentos))


@app.timer_trigger(schedule="0 30 6 * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def pronostico_fn(timer: func.TimerRequest) -> None:
    """Fase 3: backtesting + proyeccion final, publica pronostico_equipos en Cosmos DB."""
    from src import pronostico
    from src.config import HORIZONTES, NOMBRES, ORIGIN_STEP, TEST_DIAS

    logging.info("pronostico: inicio")

    df = io_blob.leer_csv("processed", "dataset_equipos_limpio.csv", parse_dates=["date"]).set_index("date")
    df = df.asfreq("B").ffill()
    log_df = np.log(df)

    resumen_df = pd.DataFrame(io_cosmos.leer_todos("resumen_relacion"))
    pares = pronostico.determinar_pares_dominantes(resumen_df)

    orden_arima = {e: pronostico.orden_arima(log_df[e].iloc[: len(log_df) - TEST_DIAS]) for e in pares}
    backtest = pronostico.correr_backtest(log_df, pares, HORIZONTES, orden_arima, NOMBRES, ORIGIN_STEP, TEST_DIAS)
    tabla_metricas = pronostico.calcular_metricas_backtest(backtest)
    horizon_final = pronostico.elegir_horizonte_final(tabla_metricas)
    pronostico_equipos = pronostico.generar_pronostico_final(log_df, pares, horizon_final, orden_arima, backtest, NOMBRES)

    documentos = []
    for fila in pronostico_equipos.to_dict(orient="records"):
        fila = {k: _limpio(v) for k, v in fila.items()}
        fila["fecha"] = str(fila["fecha"])[:10]
        fila["id"] = f"{fila['equipo']}_{fila['fecha']}"
        documentos.append(fila)
    io_cosmos.reemplazar_contenido("pronostico_equipos", documentos)
    logging.info("pronostico: listo, %s filas en pronostico_equipos", len(documentos))


@app.route(route="webhook_telegram", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def webhook_telegram(req: func.HttpRequest) -> func.HttpResponse:
    """Telegram llama aca cada vez que alguien le escribe al bot."""
    import requests

    try:
        return _webhook_telegram_impl(req, requests)
    except Exception:
        # Un error ANTES del try/except interno (ej. _inicializar(), o el JSON
        # que manda Telegram viene mal formado) -- se loguea completo para
        # Application Insights, pero nunca se expone el traceback por HTTP.
        logging.exception("Error no manejado en webhook_telegram")
        return func.HttpResponse(status_code=200)


def _webhook_telegram_impl(req: func.HttpRequest, requests) -> func.HttpResponse:
    _inicializar()

    update = req.get_json()
    mensaje = update.get("message")
    if not mensaje or "text" not in mensaje:
        return func.HttpResponse(status_code=200)  # nada que responder (ej. un sticker)

    chat_id = mensaje["chat"]["id"]
    texto = mensaje["text"]

    previas = io_cosmos.leer_todos("conversaciones", particion=str(chat_id))
    if previas:
        historial = previas[0]["mensajes"]
    else:
        from agente import SYSTEM_PROMPT
        historial = [{"role": "system", "content": SYSTEM_PROMPT}]

    historial.append({"role": "user", "content": texto})
    try:
        historial, archivos_adjuntos = _ejecutar_turno(historial, tools=tools_cloud.TOOLS, dispatch=tools_cloud.DISPATCH)
        respuesta = historial[-1]["content"]
    except Exception as exc:
        logging.exception("Error corriendo el agente")
        respuesta, archivos_adjuntos = f"Tuve un error procesando tu mensaje: {exc}", []

    io_cosmos.upsert_documento("conversaciones", {"id": str(chat_id), "chat_id": str(chat_id), "mensajes": historial})

    requests.post(f"{_TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": respuesta[:4000]})
    for ruta in archivos_adjuntos:
        with open(ruta, "rb") as foto:
            requests.post(f"{_TELEGRAM_API}/sendPhoto", data={"chat_id": chat_id}, files={"photo": foto})

    return func.HttpResponse(status_code=200)
