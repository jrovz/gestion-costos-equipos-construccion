"""Lectura/escritura de archivos en Blob Storage -- el equivalente cloud de
`data/raw/` y `data/processed/` en local. Contenedores: raw, processed, models, reports.
"""
import io
from functools import lru_cache

import pandas as pd
from azure.storage.blob import BlobServiceClient

from .keyvault import obtener_secreto


@lru_cache(maxsize=1)
def _cliente() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(obtener_secreto("storage-connection-string"))


def leer_csv(contenedor: str, nombre_blob: str, **kwargs) -> pd.DataFrame:
    cliente = _cliente().get_blob_client(container=contenedor, blob=nombre_blob)
    contenido = cliente.download_blob().readall()
    return pd.read_csv(io.BytesIO(contenido), **kwargs)


def escribir_csv(df: pd.DataFrame, contenedor: str, nombre_blob: str) -> None:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    cliente = _cliente().get_blob_client(container=contenedor, blob=nombre_blob)
    cliente.upload_blob(buffer.getvalue(), overwrite=True)


def existe_blob(contenedor: str, nombre_blob: str) -> bool:
    return _cliente().get_blob_client(container=contenedor, blob=nombre_blob).exists()


def descargar_a_temp(contenedor: str, nombre_blob: str, ruta_local: str) -> str:
    """Baja un blob (ej. una figura .png) a un archivo temporal, para poder mandarlo por Telegram."""
    cliente = _cliente().get_blob_client(container=contenedor, blob=nombre_blob)
    with open(ruta_local, "wb") as f:
        f.write(cliente.download_blob().readall())
    return ruta_local


def subir_archivo(ruta_local: str, contenedor: str, nombre_blob: str) -> None:
    cliente = _cliente().get_blob_client(container=contenedor, blob=nombre_blob)
    with open(ruta_local, "rb") as f:
        cliente.upload_blob(f, overwrite=True)
