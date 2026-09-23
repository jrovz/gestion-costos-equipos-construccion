"""Interfaz de chat. Correr con: streamlit run app/ui_streamlit.py"""
import streamlit as st
from agente import SYSTEM_PROMPT, ejecutar_turno

st.set_page_config(page_title="Costos de equipos - Agente", layout="centered")
st.title("Agente de costos de equipos de construccion")
st.caption(
    "Pregunta por la relacion materia prima-equipo (Fase 2), el pronostico (Fase 3), "
    "o pidele que busque contexto de mercado externo."
)

if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]

for mensaje in st.session_state.mensajes[1:]:
    if mensaje["role"] in ("user", "assistant") and mensaje.get("content"):
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])

entrada = st.chat_input("Escribe tu pregunta...")
if entrada:
    st.session_state.mensajes.append({"role": "user", "content": entrada})
    with st.chat_message("user"):
        st.write(entrada)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            st.session_state.mensajes = ejecutar_turno(st.session_state.mensajes)
        st.write(st.session_state.mensajes[-1]["content"])
