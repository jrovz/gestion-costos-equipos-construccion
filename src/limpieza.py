"""Fase 1 -- limpieza y preparacion de datos.

Extraido de `data/01_limpieza_datos.ipynb`, celda por celda. Ninguna funcion
de este modulo lee ni escribe un archivo por su cuenta (excepto los `cargar_*`,
que reciben la ruta como parametro): reciben y devuelven DataFrames, para que
tanto un notebook local como una Azure Function puedan usarlas igual.
"""
from pathlib import Path

import pandas as pd

from .config import UMBRAL_VARIACION


def cargar_x(path: Path) -> pd.DataFrame:
    """X.csv: separador y decimal estandar, fecha YYYY-MM-DD."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
    return df


def cargar_y(path: Path) -> pd.DataFrame:
    """Y.csv: BOM, separador ';', decimal ',', fecha D/M/YYYY."""
    df = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    return df


def cargar_z(path: Path) -> pd.DataFrame:
    """Z.csv: columnas invertidas (Price, Date), pero mismo separador/decimal que X."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
    return df


def cargar_historico_equipos(path: Path) -> pd.DataFrame:
    """historico_equipos.csv: ya combinado, formato estandar."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
    return df


def cargar_crudos(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Orquesta los 4 `cargar_*` sobre la carpeta `raw/`."""
    return {
        "X": cargar_x(raw_dir / "X.csv"),
        "Y": cargar_y(raw_dir / "Y.csv"),
        "Z": cargar_z(raw_dir / "Z.csv"),
        "historico_equipos": cargar_historico_equipos(raw_dir / "historico_equipos.csv"),
    }


def normalizar_columnas(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Renombra columnas, ordena por fecha y resetea el indice."""
    return df.rename(columns=mapping).sort_values("date").reset_index(drop=True)


def resumen_calidad(df: pd.DataFrame, nombre: str) -> dict:
    """Filas, rango de fechas, duplicados y nulos de una serie -- para revisar antes de combinar."""
    return {
        "serie": nombre,
        "filas": len(df),
        "fecha_min": df["date"].min(),
        "fecha_max": df["date"].max(),
        "fechas_duplicadas": int(df["date"].duplicated().sum()),
        "nulos": df.isna().sum().to_dict(),
    }


def tabla_resumen_calidad(series: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame([resumen_calidad(df, nombre) for nombre, df in series.items()])


def detectar_saltos_precio(df: pd.DataFrame, col: str, umbral: float = UMBRAL_VARIACION) -> pd.DataFrame:
    """Dias donde el precio varia mas de `umbral` (15% por defecto) respecto al dia anterior.

    No elimina nada -- solo lista los saltos para decidir con criterio si son un
    error de captura o un movimiento real de mercado. Se reutiliza en el agente
    (Fase 4) para validar precios reportados por Telegram antes de guardarlos.
    """
    var_pct = df[col].pct_change().abs()
    return df.loc[var_pct > umbral, ["date", col]].assign(variacion_pct=var_pct[var_pct > umbral])


def combinar_materias_primas(df_x: pd.DataFrame, df_y: pd.DataFrame, df_z: pd.DataFrame) -> pd.DataFrame:
    """Merge *outer* por fecha: conserva toda fecha en que al menos una serie cotizo."""
    return (
        df_x.merge(df_y, on="date", how="outer")
            .merge(df_z, on="date", how="outer")
            .sort_values("date")
            .reset_index(drop=True)
    )


def verificar_contra_historico(
    df_hist: pd.DataFrame,
    df_materias_primas: pd.DataFrame,
    cols: tuple[str, ...] = ("price_x", "price_y", "price_z"),
) -> pd.DataFrame:
    """Compara, en las fechas donde coinciden, que el merge produce los mismos valores que `historico_equipos.csv`."""
    chequeo = df_hist[["date", *cols]].merge(
        df_materias_primas[["date", *cols]], on="date", how="inner", suffixes=("_hist", "_merge")
    )
    filas = []
    for col in cols:
        diff = (chequeo[f"{col}_hist"] - chequeo[f"{col}_merge"]).abs()
        filas.append({"columna": col, "diferencia_maxima": diff.max(), "fechas_comparadas": len(chequeo)})
    return pd.DataFrame(filas)


def construir_dataset_equipos_limpio(
    df_hist: pd.DataFrame,
    cols: tuple[str, ...] = ("date", "price_x", "price_y", "price_z", "price_equipo1", "price_equipo2"),
) -> pd.DataFrame:
    """Acota `historico_equipos` a las columnas finales -- la tabla base para Fase 2 y 3."""
    return df_hist[list(cols)].copy()
