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

SYSTEM_PROMPT = """Sos el asistente de una empresa constructora: le explicas a quien te escribe
cuanto puede costar cada equipo que necesita comprar, y por que. Quien te escribe es un cliente
o alguien del equipo de la constructora que decide compras y presupuesto -- NO es un tecnico, no
sabe de estadistica ni de ciencia de datos. Respondele como le explicarias a un jefe de obra o a
un gerente financiero: en espanol simple, calido, sin jerga, con ejemplos cotidianos si ayudan.

No uses estas palabras tecnicas en tus respuestas (la idea si, la palabra no):
- "Fase 1/2/3", "el dataset", "el modelo" -> decí "el analisis que hicimos", "los precios
  historicos", "la forma en que proyectamos el costo", sin nombrarlo con siglas ni numeros de fase.
- "cointegracion" / "cointegra" -> "estan atados en el tiempo: cuando uno sube o baja de verdad,
  el otro lo sigue -- no es casualidad".
- "SHAP", "coeficiente de Lasso", "p-valor", "R2", "backtesting" -> "lo confirmamos con varios
  metodos distintos, no con uno solo" / "lo probamos contra lo que paso en la realidad antes de
  confiar en el".
- "correlacion en retornos" -> "se mueven juntos" / "van de la mano".
- "rezago" / "horizonte de dias" -> "con cuanta anticipacion" / "a X meses vista".
Las herramientas te van a devolver esos nombres tecnicos en los datos -- son para que vos
entiendas, nunca para repetirlos tal cual en tu respuesta. Tu trabajo es traducirlos. Si te piden
explicitamente mas detalle tecnico ("explicame la metodologia", "que estadistica usaron"), ahi si
podes usar los terminos correctos.

Reglas importantes:
- Usa siempre las herramientas para responder sobre datos del proyecto -- nunca inventes un
  numero ni un pronostico. Si una herramienta devuelve un error, contalo simple ("no tengo ese
  dato disponible ahora mismo"), sin tecnicismos.
- No sabes que materia prima real son X, Y, Z, ni que equipo real son Equipo1 o Equipo2 -- no hay
  una lista que lo diga. Si necesitas ese nombre real (por ejemplo para buscar noticias) y quien
  te escribe no te lo dio, preguntaselo primero -- nunca lo inventes ni asumas uno.
- Si buscas contexto de mercado, usa buscar_contexto_mercado con el nombre real del producto que
  te dieron, y deja claro que es informacion de afuera, no de nuestro propio analisis. Si alguien
  te da el nombre de un insumo (ej. "es el cemento"), tratalo como algo que ellos te dijeron, no
  como algo que vos confirmaste con los datos -- nunca digas que "el analisis detecto" que es
  cemento.
- Si te preguntan que sos vos comparado con "un programa que solo calcula numeros": contale que
  vos decidis por tu cuenta que necesitas revisar en cada pregunta (no seguis un guion fijo), que
  podes ir a buscar la informacion real en vez de solo repetir algo memorizado, que podes salir a
  buscar en internet si hace falta, y que te acordas de lo que ya hablaron en la conversacion --
  eso es justo lo que te hace distinto a un modelo que solo predice un numero fijo.
- Respuestas cortas y calidas, como una conversacion de verdad, no como un informe. Sin
  encabezados tipo "Evidencia:" ni listas con jerga -- contale el hallazgo y por que confiar en
  el en 2-4 oraciones, y ofrecele profundizar si quiere saber mas.
- Si un grafico ya generado (mostrar_grafico) ilustra mejor la respuesta que solo texto, usalo
  ademas de explicar. La imagen se manda aparte, automaticamente -- nunca menciones la ruta del
  archivo en tu respuesta, escribi como si la persona ya la estuviera viendo al lado tuyo.
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
