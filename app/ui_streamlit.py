"""Interfaz de chat. Correr con: streamlit run app/ui_streamlit.py"""
import streamlit as st
from agente import SYSTEM_PROMPT, ejecutar_turno

st.set_page_config(page_title="Costos de equipos - Agente", layout="centered")
st.title("Agente de costos de equipos de construccion")
st.caption(
    "Pregunta por la relacion materia prima-equipo (Fase 2), el pronostico (Fase 3), "
    "pidele un grafico del analisis, o que busque contexto de mercado externo."
)

if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
if "imagenes" not in st.session_state:
    st.session_state.imagenes = {}  # indice en st.session_state.mensajes -> lista de rutas

for i, mensaje in enumerate(st.session_state.mensajes[1:], start=1):
    if mensaje["role"] in ("user", "assistant") and mensaje.get("content"):
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])
            for ruta in st.session_state.imagenes.get(i, []):
                st.image(ruta)

entrada = st.chat_input("Escribe tu pregunta...")
if entrada:
    st.session_state.mensajes.append({"role": "user", "content": entrada})
    with st.chat_message("user"):
        st.write(entrada)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            st.session_state.mensajes, archivos_adjuntos = ejecutar_turno(st.session_state.mensajes)
        st.write(st.session_state.mensajes[-1]["content"])
        for ruta in archivos_adjuntos:
            st.image(ruta)
        if archivos_adjuntos:
            st.session_state.imagenes[len(st.session_state.mensajes) - 1] = archivos_adjuntos
