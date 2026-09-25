"""Lectura/escritura de documentos en Cosmos DB -- contenedores resumen_relacion,
pronostico_equipos (particionados por /equipo) y conversaciones (por /chat_id).
"""
from functools import lru_cache

from azure.cosmos import CosmosClient

from .keyvault import obtener_secreto

DATABASE_NAME = "costos-equipos-db"


@lru_cache(maxsize=1)
def _cliente() -> CosmosClient:
    return CosmosClient.from_connection_string(obtener_secreto("cosmos-connection-string"))


def _contenedor(nombre: str):
    return _cliente().get_database_client(DATABASE_NAME).get_container_client(nombre)


def reemplazar_contenido(contenedor: str, documentos: list[dict]) -> None:
    """Borra todo lo que hay en el contenedor y lo reemplaza -- usado por limpieza_analisis
    y pronostico, que recalculan la tabla completa en cada corrida (no un incremento)."""
    c = _contenedor(contenedor)
    for doc in list(c.read_all_items()):
        c.delete_item(item=doc["id"], partition_key=doc[_clave_particion(contenedor)])
    for doc in documentos:
        c.upsert_item(doc)


def leer_todos(contenedor: str, particion: str | None = None) -> list[dict]:
    c = _contenedor(contenedor)
    if particion is None:
        return list(c.read_all_items())
    campo = _clave_particion(contenedor)
    return list(c.query_items(
        query=f"SELECT * FROM c WHERE c.{campo} = @p",
        parameters=[{"name": "@p", "value": particion}],
        partition_key=particion,
    ))


def upsert_documento(contenedor: str, documento: dict) -> None:
    _contenedor(contenedor).upsert_item(documento)


def _clave_particion(contenedor: str) -> str:
    return "chat_id" if contenedor == "conversaciones" else "equipo"
