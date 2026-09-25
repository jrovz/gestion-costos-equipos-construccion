"""Fase 3 -- proyeccion de costos.

Extraido de `data/03_proyeccion_costos.ipynb`. `correr_backtest` y
`generar_pronostico_final` son las dos funciones mas largas -- son
literalmente el cuerpo de las celdas 12 y 21 del notebook, parametrizadas.
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.vector_ar.vecm import VECM

from .config import ORIGIN_STEP, TEST_DIAS, VECM_COINT_RANK, VECM_K_AR_DIFF

MATERIA_COL_POR_LETRA = {"X": "price_x", "Y": "price_y", "Z": "price_z"}


def determinar_pares_dominantes(resumen_df: pd.DataFrame, equipos_nombres: tuple[str, ...] = ("Equipo1", "Equipo2")) -> dict:
    """Lee el resumen de la Fase 2 y arma {columna_equipo: columna_materia_dominante}."""
    pares = {}
    for equipo in equipos_nombres:
        sub = resumen_df[resumen_df["equipo"] == equipo]
        fila = sub.reindex(sub["shap_medio"].sort_values(ascending=False).index).iloc[0]
        pares[f"price_{equipo.lower()}"] = MATERIA_COL_POR_LETRA[fila["insumo"]]
    return pares


def orden_arima(
    serie_log: pd.Series,
    ordenes: tuple[tuple[int, int, int], ...] = ((1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 1), (1, 1, 2), (2, 1, 2)),
) -> tuple[int, int, int]:
    mejor_aic, mejor_orden = np.inf, (1, 1, 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for orden in ordenes:
            try:
                aic = SARIMAX(serie_log, order=orden, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False).aic
            except Exception:
                continue
            if aic < mejor_aic:
                mejor_aic, mejor_orden = aic, orden
    return mejor_orden


def forecast_naive(hist_equipo: pd.Series, max_h: int) -> np.ndarray:
    return np.full(max_h, hist_equipo.iloc[-1])


def forecast_media_movil(hist_equipo: pd.Series, max_h: int, ventana: int = 63) -> np.ndarray:
    return np.full(max_h, hist_equipo.iloc[-ventana:].mean())


def forecast_arima(hist_equipo: pd.Series, max_h: int, orden: tuple[int, int, int]) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = SARIMAX(hist_equipo, order=orden, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        return res.get_forecast(steps=max_h).predicted_mean.to_numpy()


def forecast_vecm(
    hist_pair_df: pd.DataFrame,
    max_h: int,
    equipo_col: str,
    k_ar_diff: int = VECM_K_AR_DIFF,
    coint_rank: int = VECM_COINT_RANK,
    alpha: float | None = None,
):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = VECM(hist_pair_df, k_ar_diff=k_ar_diff, coint_rank=coint_rank, deterministic="ci").fit()
        j = list(hist_pair_df.columns).index(equipo_col)
        if alpha is None:
            return res.predict(steps=max_h)[:, j]
        pred, lo, hi = res.predict(steps=max_h, alpha=alpha)
        return pred[:, j], lo[:, j], hi[:, j]


def correr_backtest(
    log_df: pd.DataFrame,
    pares: dict,
    horizontes: dict,
    orden_arima_por_equipo: dict,
    nombres: dict,
    origin_step: int = ORIGIN_STEP,
    test_dias: int = TEST_DIAS,
) -> pd.DataFrame:
    """Backtesting rolling-origin de los 4 metodos (naive, media movil, ARIMA, VECM)."""
    train_size = len(log_df) - test_dias
    max_h = max(horizontes.values())
    origenes = list(range(train_size, len(log_df) - max_h, origin_step))

    filas = []
    for equipo, materia in pares.items():
        for origen in origenes:
            hist_pair = log_df[[materia, equipo]].iloc[: origen + 1]
            hist_equipo = hist_pair[equipo]

            preds = {
                "Naive": forecast_naive(hist_equipo, max_h),
                "Media movil 3m": forecast_media_movil(hist_equipo, max_h),
                "ARIMA": forecast_arima(hist_equipo, max_h, orden_arima_por_equipo[equipo]),
                "VECM": forecast_vecm(hist_pair, max_h, equipo),
            }

            for nombre_h, h in horizontes.items():
                real = np.exp(log_df[equipo].iloc[origen + h])
                for metodo, pred_log in preds.items():
                    pronost = np.exp(pred_log[h - 1])
                    filas.append({
                        "equipo": nombres[equipo], "origen": log_df.index[origen], "horizonte": nombre_h,
                        "horizonte_dias": h, "metodo": metodo, "real": real, "pronostico": pronost,
                        "error_pct": (pronost - real) / real,
                    })
    return pd.DataFrame(filas)


def calcular_metricas_backtest(backtest_df: pd.DataFrame) -> pd.DataFrame:
    def metricas(g):
        return pd.Series({
            "MAE": mean_absolute_error(g["real"], g["pronostico"]),
            "RMSE": mean_squared_error(g["real"], g["pronostico"]) ** 0.5,
            "MAPE": mean_absolute_percentage_error(g["real"], g["pronostico"]),
        })

    tabla = (
        backtest_df.groupby(["equipo", "horizonte", "horizonte_dias", "metodo"])
        .apply(metricas, include_groups=False)
        .reset_index()
        .sort_values(["equipo", "horizonte_dias", "MAPE"])
    )
    tabla["MAPE"] = tabla["MAPE"].round(4)
    return tabla


def mejor_por_horizonte(tabla_metricas: pd.DataFrame) -> pd.DataFrame:
    """El metodo con menor MAPE en cada combinacion equipo x horizonte."""
    return (
        tabla_metricas.loc[tabla_metricas.groupby(["equipo", "horizonte_dias"])["MAPE"].idxmin()]
        .sort_values(["equipo", "horizonte_dias"])
    )


def elegir_horizonte_final(tabla_metricas: pd.DataFrame, equipos_nombres: tuple[str, ...] = ("Equipo1", "Equipo2")) -> dict:
    """El horizonte mas largo en el que el mejor metodo siga siendo ARIMA o VECM (no naive/media movil)."""
    mejor = mejor_por_horizonte(tabla_metricas)

    horizon_final = {}
    for equipo in equipos_nombres:
        sub = mejor[mejor["equipo"] == equipo].sort_values("horizonte_dias")
        elegido = None
        for _, fila in sub.iterrows():
            if fila["metodo"] in ("ARIMA", "VECM"):
                elegido = fila
            else:
                break
        horizon_final[equipo] = elegido
    return horizon_final


def banda_empirica(backtest_df: pd.DataFrame, equipo: str, metodo: str, horizonte_dias: int, punto: float) -> tuple[float, float]:
    """Banda de incertidumbre del percentil 5-95 del error real de backtesting -- no de la formula interna del modelo."""
    errores = backtest_df[
        (backtest_df["equipo"] == equipo) & (backtest_df["metodo"] == metodo) & (backtest_df["horizonte_dias"] == horizonte_dias)
    ]["error_pct"]
    lo = punto * (1 + errores.quantile(0.05))
    hi = punto * (1 + errores.quantile(0.95))
    return min(lo, hi), max(lo, hi)


def generar_pronostico_final(
    log_df: pd.DataFrame,
    pares: dict,
    horizon_final: dict,
    orden_arima_por_equipo: dict,
    backtest_df: pd.DataFrame,
    nombres: dict,
) -> pd.DataFrame:
    """Reentrena con todo el historico y proyecta con el metodo/horizonte ganador de cada equipo."""
    filas = []
    for equipo, materia in pares.items():
        nombre_equipo = nombres[equipo]
        info = horizon_final[nombre_equipo]
        metodo_final = info["metodo"]
        horizonte_final_dias = int(info["horizonte_dias"])

        if metodo_final == "VECM":
            path_log = forecast_vecm(log_df[[materia, equipo]], horizonte_final_dias, equipo)
        else:
            path_log = forecast_arima(log_df[equipo], horizonte_final_dias, orden_arima_por_equipo[equipo])
        path_precio = np.exp(path_log)

        fechas_futuras = pd.bdate_range(log_df.index[-1] + pd.Timedelta(days=1), periods=horizonte_final_dias)
        for i, (fecha, precio) in enumerate(zip(fechas_futuras, path_precio), start=1):
            es_control = i == horizonte_final_dias
            lo, hi = banda_empirica(backtest_df, nombre_equipo, metodo_final, horizonte_final_dias, precio) if es_control else (np.nan, np.nan)
            filas.append({
                "equipo": nombre_equipo, "fecha": fecha, "pronostico": precio,
                "ic_inferior": lo, "ic_superior": hi, "metodo": metodo_final,
                "horizonte_dias": horizonte_final_dias, "es_punto_de_control": es_control,
            })

    return pd.DataFrame(filas)
