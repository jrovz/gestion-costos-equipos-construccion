"""Loop conversacional del agente. Sin frameworks (LangChain, etc.): un ciclo
simple de llamar al modelo, ejecutar las herramientas que pida, devolverle el
resultado, y repetir hasta que responda en texto. Es justo ese ciclo -- decidir
que hacer, actuar, y volver a decidir -- lo que lo distingue de un modelo de IA
convencional (ver SYSTEM_PROMPT y app/README.md).
"""
import json
import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI

from tools import DISPATCH, TOOLS

load_dotenv()

SYSTEM_PROMPT = """Eres el agente de resultados del proyecto "Gestion de Costos Operativos en un
Proyecto de Construccion". Tu trabajo es explicar, a quien te pregunte, los hallazgos de las
Fases 1-3 del analisis (limpieza de datos, relacion materia prima-equipo, proyeccion de costos)
y enriquecerlos con contexto externo de mercado cuando sea util.

Reglas importantes:
- Usa siempre las herramientas para responder sobre datos del proyecto -- nunca inventes un
  numero, un p-valor o un pronostico. Si una herramienta devuelve un error, dilo tal cual.
- No hay diccionario de datos: no sabes que materia prima real son X, Y, Z, ni que equipo real
  son Equipo1 o Equipo2. Si para responder necesitas ese nombre real (por ejemplo, para buscar
  contexto de mercado externo) y quien te pregunta no te lo dio, preguntaselo primero -- nunca
  te lo inventes ni asumas uno.
- Si te preguntan por contexto de mercado, usa buscar_contexto_mercado con un termino real de
  producto, y deja claro que es informacion externa (no del dataset del proyecto). Si quien
  pregunta te da el nombre real de un insumo (ej. "es el cemento"), tratalo como un supuesto
  que ellos aportan, no como algo que el dataset o la Fase 2 confirmaron -- nunca digas "en la
  Fase 2 detectamos que Z es cemento", di algo como "asumiendo que Z es cemento, segun la Fase 2...".
- Si te preguntan que diferencia hay entre vos y un modelo de IA convencional: el modelo VECM de
  la Fase 3 es IA convencional -- recibe datos y devuelve un numero fijo, sin decidir nada por su
  cuenta. Vos sos distinto porque decidis que herramienta usar segun la pregunta (autonomia),
  podes ejecutar acciones reales como consultar datos o buscar en la web (capacidad de accion,
  uso de herramientas), y recordas el hilo de la conversacion (memoria) en vez de responder cada
  mensaje de forma aislada.
- Respuestas concisas, en espanol, citando de que fase sale cada dato cuando ayude a la
  credibilidad de la respuesta.
"""

_REQUERIDAS = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"]
_faltantes = [v for v in _REQUERIDAS if not os.environ.get(v)]
if _faltantes:
    raise RuntimeError(
        f"Faltan variables de entorno: {', '.join(_faltantes)}. "
        "Copia app/.env.example a app/.env y completa tus credenciales de Azure OpenAI."
    )

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
)
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]


def ejecutar_turno(mensajes: list[dict], tools: list[dict] = TOOLS, dispatch: dict = DISPATCH) -> tuple[list[dict], list[str]]:
    """Corre un turno completo: llama al modelo, ejecuta las tool calls que pida
    (puede ser mas de una ronda), y devuelve la lista de mensajes actualizada con
    la respuesta final en texto, mas las rutas de imagenes que se hayan pedido
    mostrar en este turno (via mostrar_grafico) -- cada interfaz (Streamlit,
    Telegram, CLI) decide como mostrarlas, esto solo dice "cuales".

    `tools`/`dispatch` son parametros (no siempre los de tools.py) para poder
    reusar este mismo loop con la version cloud de las herramientas
    (functions/shared/tools_cloud.py) sin duplicar la logica del agente.
    """
    archivos_adjuntos: list[str] = []
    while True:
        respuesta = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=mensajes,
            tools=tools,
            tool_choice="auto",
        )
        mensaje = respuesta.choices[0].message

        if mensaje.tool_calls:
            mensajes.append(mensaje.model_dump(exclude_none=True))
            for tc in mensaje.tool_calls:
                nombre = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                funcion = dispatch.get(nombre)
                resultado = funcion(**args) if funcion else {"error": f"Herramienta desconocida: {nombre}"}
                if nombre == "mostrar_grafico" and "ruta" in resultado:
                    archivos_adjuntos.append(resultado["ruta"])
                mensajes.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": nombre,
                    "content": json.dumps(resultado, ensure_ascii=False),
                })
            continue  # el modelo ve los resultados y decide el siguiente paso

        mensajes.append({"role": "assistant", "content": mensaje.content})
        return mensajes, archivos_adjuntos


if __name__ == "__main__":
    import io

    # consola de Windows en cp1252: sin esto, una respuesta con cierto caracter
    # Unicode (comillas tipograficas, guiones largos) revienta el print()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Agente listo (Ctrl+C o 'salir' para terminar).\n")
    while True:
        entrada = input("Tu: ").strip()
        if entrada.lower() in ("salir", "exit", "quit"):
            break
        mensajes.append({"role": "user", "content": entrada})
        mensajes, archivos_adjuntos = ejecutar_turno(mensajes)
        print(f"\nAgente: {mensajes[-1]['content']}\n")
        for ruta in archivos_adjuntos:
            print(f"[imagen: {ruta}]")
