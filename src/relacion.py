"""Fase 2 -- relacion entre materias primas y precio de los equipos.

Extraido de `data/02_analisis_relacion_materias_primas_equipos.ipynb`. Mismas
funciones, mismos parametros (`random_state=42` donde aplica) para que el
resultado sea identico al que ya esta documentado en el informe.
"""
import warnings

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNetCV, LassoCV
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import adfuller, coint, grangercausalitytests, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from .config import GRANGER_MAXLAG, JOHANSEN_K_AR_DIFF, MAX_LAG_CCF, N_LAGS_FEATURES, VAR_MAXLAGS


def tabla_granularidad(df: pd.DataFrame, cols: list[str], nombres: dict) -> pd.DataFrame:
    """% de dias que cada serie repite el valor del dia anterior -- distingue una
    cotizacion de mercado (cambia casi a diario) de una lista de precios "pegada"."""
    filas = []
    for c in cols:
        igual = (df[c] == df[c].shift(1)).mean()
        cambia = df[c] != df[c].shift(1)
        racha = df.groupby(cambia.cumsum()).size()
        filas.append({
            "serie": nombres[c],
            "repite_dia_anterior": igual,
            "racha_mediana_dias": racha.median(),
            "racha_maxima_dias": racha.max(),
        })
    return pd.DataFrame(filas).set_index("serie")


def calcular_retornos(df: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    log_df = np.log(df[cols])
    ret_df = log_df.diff().dropna()
    return log_df, ret_df


def test_estacionariedad(serie: pd.Series, adf_reg: str, kpss_reg: str) -> tuple[float, float, float, float]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        adf_stat, adf_p, *_ = adfuller(serie, regression=adf_reg, autolag="AIC")
        kpss_stat, kpss_p, *_ = kpss(serie, regression=kpss_reg, nlags="auto")
    return adf_stat, adf_p, kpss_stat, kpss_p


def concluir_estacionariedad(adf_p: float, kpss_p: float) -> str:
    adf_estac, kpss_estac = adf_p < 0.05, kpss_p > 0.05
    if adf_estac and kpss_estac:
        return "estacionaria"
    if not adf_estac and not kpss_estac:
        return "no estacionaria"
    return "ambigua"


def tabla_estacionariedad(log_df: pd.DataFrame, ret_df: pd.DataFrame, cols: list[str], nombres: dict) -> pd.DataFrame:
    filas = []
    for c in cols:
        a_stat, a_p, k_stat, k_p = test_estacionariedad(log_df[c], "ct", "ct")
        filas.append({"serie": nombres[c], "tipo": "nivel (log)", "adf_stat": a_stat, "adf_p": a_p,
                      "kpss_stat": k_stat, "kpss_p": k_p, "conclusion": concluir_estacionariedad(a_p, k_p)})
        a_stat, a_p, k_stat, k_p = test_estacionariedad(ret_df[c], "c", "c")
        filas.append({"serie": nombres[c], "tipo": "retorno (dlog)", "adf_stat": a_stat, "adf_p": a_p,
                      "kpss_stat": k_stat, "kpss_p": k_p, "conclusion": concluir_estacionariedad(a_p, k_p)})
    return pd.DataFrame(filas)


def tabla_correlaciones(df: pd.DataFrame, ret_df: pd.DataFrame, cols: list[str]) -> dict[str, pd.DataFrame]:
    return {
        "pearson_niveles": df[cols].corr(method="pearson"),
        "pearson_retornos": ret_df.corr(method="pearson"),
        "spearman_niveles": df[cols].corr(method="spearman"),
        "spearman_retornos": ret_df.corr(method="spearman"),
    }


def tabla_engle_granger(log_df: pd.DataFrame, materias: list[str], equipos: list[str], nombres: dict) -> pd.DataFrame:
    filas = []
    for m in materias:
        for e in equipos:
            stat, pval, _ = coint(log_df[e], log_df[m])
            filas.append({"materia": nombres[m], "equipo": nombres[e], "eg_stat": stat, "eg_p": pval,
                          "cointegra_5pct": pval < 0.05})
    return pd.DataFrame(filas)


def seleccionar_orden_var(log_df: pd.DataFrame, equipos: list[str], nombres: dict, maxlags: int = VAR_MAXLAGS) -> dict:
    """Orden de rezago sugerido por AIC/BIC/HQIC/FPE para el sistema (X,Y,Z,equipo)."""
    resultados = {}
    for e in equipos:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sel = VAR(log_df[["price_x", "price_y", "price_z", e]]).select_order(maxlags=maxlags)
        resultados[nombres[e]] = dict(sel.selected_orders)
    return resultados


def tabla_johansen(
    log_df: pd.DataFrame, materias: list[str], equipos: list[str], nombres: dict, k_ar_diff: int = JOHANSEN_K_AR_DIFF
) -> tuple[pd.DataFrame, dict]:
    filas, vectores = [], {}
    for e in equipos:
        sub = log_df[[*materias, e]]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # benigna: parte imaginaria de los autovalores ~0
            res = coint_johansen(sub, det_order=0, k_ar_diff=k_ar_diff)

        trace_stat, trace_crit5 = res.lr1, res.cvt[:, 1]
        maxeig_stat, maxeig_crit5 = res.lr2, res.cvm[:, 1]
        rango_trace = int((trace_stat > trace_crit5).sum())
        rango_maxeig = int((maxeig_stat > maxeig_crit5).sum())
        filas.append({"equipo": nombres[e], "rango_trace_5pct": rango_trace, "rango_maxeig_5pct": rango_maxeig})

        evec1 = res.evec[:, 0].real
        evec1 = evec1 / evec1[0]
        vectores[nombres[e]] = pd.Series(evec1, index=[nombres[m] for m in materias] + [nombres[e]]).round(3)

    return pd.DataFrame(filas), vectores


def ccf_lags(x: pd.Series, y: pd.Series, max_lag: int) -> pd.Series:
    out = {}
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            a, b = x.shift(k).iloc[max_lag:], y.iloc[max_lag:]
        else:
            a, b = x.iloc[max_lag:], y.shift(-k).iloc[max_lag:]
        out[k] = a.corr(b)
    return pd.Series(out)


def tabla_ccf(
    ret_df: pd.DataFrame, materias: list[str], equipos: list[str], nombres: dict, max_lag: int = MAX_LAG_CCF
) -> tuple[pd.DataFrame, dict]:
    ccf_por_par, filas = {}, []
    for m in materias:
        for e in equipos:
            s = ccf_lags(ret_df[m], ret_df[e], max_lag)
            ccf_por_par[(m, e)] = s
            mejor_lag = s.abs().idxmax()
            filas.append({"materia": nombres[m], "equipo": nombres[e], "lag_optimo": mejor_lag,
                          "corr_en_lag_optimo": s[mejor_lag]})
    return pd.DataFrame(filas), ccf_por_par


def tabla_granger(
    ret_df: pd.DataFrame, materias: list[str], equipos: list[str], nombres: dict, maxlag: int = GRANGER_MAXLAG
) -> pd.DataFrame:
    filas = []
    for m in materias:
        for e in equipos:
            datos = ret_df[[e, m]].dropna()  # orden [y, x]: testea si "m" Granger-causa "e"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = grangercausalitytests(datos, maxlag=maxlag)
            pvals = {lag: res[lag][0]["ssr_ftest"][1] for lag in res}
            mejor_lag = min(pvals, key=pvals.get)
            filas.append({"materia": nombres[m], "equipo": nombres[e], "mejor_lag": mejor_lag,
                          "p_valor": pvals[mejor_lag], "granger_causa_5pct": pvals[mejor_lag] < 0.05})
    return pd.DataFrame(filas)


def calcular_vif(ret_df: pd.DataFrame, materias: list[str], nombres: dict) -> pd.DataFrame:
    x_c = ret_df[materias].assign(const=1.0)
    return pd.DataFrame({
        "materia": [nombres[m] for m in materias],
        "VIF": [variance_inflation_factor(x_c.values, i) for i in range(len(materias))],
    })


def construir_features(
    ret_df: pd.DataFrame, materias: list[str], equipo: str, nombres: dict, n_lags: int = N_LAGS_FEATURES
) -> tuple[pd.DataFrame, pd.Series]:
    feats = {f"{nombres[m]}_lag{lag}": ret_df[m].shift(lag) for m in materias for lag in range(n_lags + 1)}
    x = pd.DataFrame(feats, index=ret_df.index)
    y = ret_df[equipo]
    ambos = pd.concat([x, y.rename("target")], axis=1).dropna()
    return ambos.drop(columns="target"), ambos["target"]


def ajustar_lasso_elasticnet(
    ret_df: pd.DataFrame, materias: list[str], equipos: list[str], nombres: dict, n_lags: int = N_LAGS_FEATURES
) -> dict:
    tscv = TimeSeriesSplit(n_splits=5)
    resultados = {}
    for e in equipos:
        x, y = construir_features(ret_df, materias, e, nombres, n_lags)
        lasso = LassoCV(cv=tscv, random_state=42, max_iter=20000).fit(x, y)
        enet = ElasticNetCV(cv=tscv, random_state=42, max_iter=20000, l1_ratio=[.1, .5, .7, .9, .95, 1]).fit(x, y)
        resultados[e] = {
            "X": x, "y": y, "lasso": lasso, "enet": enet,
            "coef_lasso": pd.Series(lasso.coef_, index=x.columns),
            "coef_enet": pd.Series(enet.coef_, index=x.columns),
        }
    return resultados


def ajustar_random_forest_shap(resultados_lineales: dict, materias: list[str], nombres: dict) -> dict:
    tscv = TimeSeriesSplit(n_splits=5)
    resultados = {}
    for e, datos in resultados_lineales.items():
        x, y = datos["X"], datos["y"]
        rf = RandomForestRegressor(n_estimators=300, max_depth=5, min_samples_leaf=20, random_state=42, n_jobs=-1)
        r2_cv = cross_val_score(rf, x, y, cv=tscv, scoring="r2")
        rf.fit(x, y)

        explainer = shap.TreeExplainer(rf)
        shap_values = explainer.shap_values(x)
        shap_abs_medio = pd.Series(np.abs(shap_values).mean(axis=0), index=x.columns)
        shap_por_materia = pd.Series({
            nombres[m]: shap_abs_medio[[c for c in x.columns if c.startswith(nombres[m] + "_lag")]].sum()
            for m in materias
        }).sort_values(ascending=False)

        resultados[e] = {"rf": rf, "r2_cv": r2_cv, "shap_values": shap_values, "shap_por_materia": shap_por_materia}
    return resultados


def construir_tabla_resumen(
    materias: list[str],
    equipos: list[str],
    nombres: dict,
    df_engle_granger: pd.DataFrame,
    df_granger: pd.DataFrame,
    df_ccf: pd.DataFrame,
    resultados_lineales: dict,
    resultados_rf: dict,
) -> pd.DataFrame:
    filas = []
    for m in materias:
        for e in equipos:
            coef_lasso = resultados_lineales[e]["coef_lasso"]
            cols_materia = [c for c in coef_lasso.index if c.startswith(nombres[m] + "_lag")]
            coef_dominante = coef_lasso[cols_materia].reindex(
                coef_lasso[cols_materia].abs().sort_values(ascending=False).index
            ).iloc[0]
            rezago_dominante = coef_lasso[cols_materia].abs().idxmax().split("_lag")[1]

            eg_row = df_engle_granger[(df_engle_granger["materia"] == nombres[m]) & (df_engle_granger["equipo"] == nombres[e])].iloc[0]
            gr_row = df_granger[(df_granger["materia"] == nombres[m]) & (df_granger["equipo"] == nombres[e])].iloc[0]
            ccf_row = df_ccf[(df_ccf["materia"] == nombres[m]) & (df_ccf["equipo"] == nombres[e])].iloc[0]
            shap_val = resultados_rf[e]["shap_por_materia"][nombres[m]]

            filas.append({
                "equipo": nombres[e],
                "insumo": nombres[m],
                "signo_lasso": "+" if coef_dominante > 0 else ("-" if coef_dominante < 0 else "0"),
                "coef_lasso_dominante": coef_dominante,
                "rezago_lasso_dominante": rezago_dominante,
                "lag_optimo_ccf": ccf_row["lag_optimo"],
                "corr_ccf": ccf_row["corr_en_lag_optimo"],
                "cointegra_eg_5pct": eg_row["cointegra_5pct"],
                "granger_causa_5pct": gr_row["granger_causa_5pct"],
                "shap_medio": shap_val,
            })

    return pd.DataFrame(filas).sort_values(["equipo", "shap_medio"], ascending=[True, False]).reset_index(drop=True)
