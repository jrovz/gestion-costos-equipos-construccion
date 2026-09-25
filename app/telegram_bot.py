"""Prototipo local del bot de Telegram -- long polling, sin URL publica.

Reusa el mismo `ejecutar_turno()` de `agente.py` tal cual; este archivo solo
agrega la capa de entrada/salida de Telegram (recibir mensajes, mandar
respuestas, guardar memoria por chat_id en un diccionario mientras el proceso
vive). En Azure, la misma logica correria como webhook en vez de polling
(Telegram llama a una Function en vez de que el bot este preguntando "hay
mensajes nuevos?" en un loop) y la memoria pasaria a Cosmos DB -- ver
infra/README.md -- pero el agente (agente.py, tools.py) no cambia en nada.

Correr con: python telegram_bot.py
"""
import io
import os
import sys
import time

import requests
from dotenv import load_dotenv

from agente import SYSTEM_PROMPT, ejecutar_turno

# consola de Windows en cp1252: sin esto, una respuesta con cierto caracter
# Unicode revienta el print()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "Falta TELEGRAM_BOT_TOKEN. Habla con @BotFather en Telegram, crea un bot "
        "y copia el token a app/.env (ver .env.example)."
    )
API_URL = f"https://api.telegram.org/bot{TOKEN}"

MAX_MENSAJE_TELEGRAM = 4000  # Telegram corta a los 4096; dejo margen

conversaciones: dict[int, list[dict]] = {}


def obtener_actualizaciones(offset: int | None, timeout: int = 30) -> list[dict]:
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(f"{API_URL}/getUpdates", params=params, timeout=timeout + 10)
    resp.raise_for_status()
    return resp.json()["result"]


def enviar_mensaje(chat_id: int, texto: str) -> None:
    for i in range(0, len(texto), MAX_MENSAJE_TELEGRAM):
        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": texto[i:i + MAX_MENSAJE_TELEGRAM]})


def enviar_foto(chat_id: int, ruta: str) -> None:
    with open(ruta, "rb") as archivo:
        requests.post(f"{API_URL}/sendPhoto", data={"chat_id": chat_id}, files={"photo": archivo})


def procesar_mensaje(chat_id: int, texto: str) -> tuple[str, list[str]]:
    if chat_id not in conversaciones:
        conversaciones[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversaciones[chat_id].append({"role": "user", "content": texto})
    conversaciones[chat_id], archivos_adjuntos = ejecutar_turno(conversaciones[chat_id])
    return conversaciones[chat_id][-1]["content"], archivos_adjuntos


def main() -> None:
    print("Bot de Telegram corriendo (long polling). Ctrl+C para detener.\n")
    offset = None
    while True:
        try:
            actualizaciones = obtener_actualizaciones(offset)
        except requests.RequestException as exc:
            print(f"Error consultando Telegram, reintento en 5s: {exc}")
            time.sleep(5)
            continue

        for update in actualizaciones:
            offset = update["update_id"] + 1
            mensaje = update.get("message")
            if not mensaje or "text" not in mensaje:
                continue

            chat_id = mensaje["chat"]["id"]
            texto = mensaje["text"]
            print(f"[{chat_id}] Usuario: {texto}")

            try:
                respuesta, archivos_adjuntos = procesar_mensaje(chat_id, texto)
            except Exception as exc:  # nunca dejar el bot colgado por un error de un mensaje
                respuesta, archivos_adjuntos = f"Tuve un error procesando tu mensaje: {exc}", []

            print(f"[{chat_id}] Agente: {respuesta}\n")
            enviar_mensaje(chat_id, respuesta)
            for ruta in archivos_adjuntos:
                enviar_foto(chat_id, ruta)


if __name__ == "__main__":
    main()
