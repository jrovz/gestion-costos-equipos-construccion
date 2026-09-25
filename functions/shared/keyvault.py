"""Acceso a secrets de Key Vault -- misma llamada sirve en local (usa tu sesion
de `az login`) y en Azure (usara la Managed Identity de la Function App, sin
cambiar una linea de codigo). Nunca hay una credencial escrita en el repo.
"""
import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

KEY_VAULT_URL = os.environ["KEY_VAULT_URL"]


@lru_cache(maxsize=1)
def _client() -> SecretClient:
    return SecretClient(vault_url=KEY_VAULT_URL, credential=DefaultAzureCredential())


@lru_cache(maxsize=32)
def obtener_secreto(nombre: str) -> str:
    return _client().get_secret(nombre).value
