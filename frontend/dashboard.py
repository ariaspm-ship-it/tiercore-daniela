# Dashboard web para Daniela - Demo de inversores
# Ejecutar con: streamlit run frontend/dashboard.py

import os
import random
import sys
import hashlib
from io import BytesIO
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None

# Añadir raíz al path para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.claude_agent import DanielaAgent
from core.config import Config
from simulator.resort_simulator import ResortSimulator


st.set_page_config(
    page_title="DANIELA - Infrastructure Intelligence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        color: #C5A467;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #1E1E1E;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #C5A467;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .alert-high {
        background-color: rgba(255, 75, 75, 0.1);
        border-left: 4px solid #ff4b4b;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .alert-medium {
        background-color: rgba(255, 193, 7, 0.1);
        border-left: 4px solid #ffc107;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .alert-low {
        background-color: rgba(13, 110, 253, 0.1);
        border-left: 4px solid #0d6efd;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .footer {
        text-align: center;
        color: #666;
        font-size: 0.8rem;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #333;
    }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def init_simulator() -> ResortSimulator:
    return ResortSimulator(persist_to_db=False)


@st.cache_resource
def init_agent() -> DanielaAgent:
    return DanielaAgent()


def transcribe_audio_bytes(audio_bytes: bytes, language: str = "es-ES") -> str:
    if not sr:
        raise RuntimeError("SpeechRecognition no está instalado en este entorno")

    recognizer = sr.Recognizer()
    with sr.AudioFile(BytesIO(audio_bytes)) as source:
        audio = recognizer.record(source)
    return recognizer.recognize_google(audio, language=language)


def speak_in_browser(text: str, voice_lang: str = "es-ES") -> None:
    safe_text = (
        text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    safe_lang = voice_lang.replace("'", "")
    components.html(
        f"""
<script>
(() => {{
  const text = `{safe_text}`;
  const lang = '{safe_lang}';
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = lang;
  utter.rate = 1.0;
  utter.pitch = 1.0;
  const voices = window.speechSynthesis.getVoices() || [];
  const preferred = voices.find(v => v.lang && v.lang.toLowerCase().startsWith(lang.toLowerCase()));
  if (preferred) utter.voice = preferred;
  window.speechSynthesis.speak(utter);
}})();
</script>
""",
        height=0,
        width=0,
    )


sim = init_simulator()
agent = init_agent()

if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True
if "refresh_counter" not in st.session_state:
    st.session_state.refresh_counter = 0
if "voice_reply_enabled" not in st.session_state:
    st.session_state.voice_reply_enabled = True
if "voice_lang" not in st.session_state:
    st.session_state.voice_lang = "es-ES"


with st.sidebar:
    st.markdown("## 🏨 BCH-VILLA COLONY")
    st.markdown("**Marca:** Kempinski")
    st.markdown("**Ubicación:** Turks & Caicos")
    st.markdown(f"**Viviendas:** {Config.get_total_viviendas()} (187 aptos + 4 villas)")
    st.markdown("**Puntos BMS:** ~2.100")

    st.divider()

    st.markdown("## ⚙️ Controles")
    st.session_state.auto_refresh = st.toggle(
        "Actualización automática",
        value=st.session_state.auto_refresh,
        help="Actualiza datos en cada render",
    )

    if st.button("🔄 Actualizar ahora", width="stretch"):
        st.session_state.refresh_counter += 1
        sim.step()

    st.session_state.voice_reply_enabled = st.toggle(
        "🔊 Respuesta por voz",
        value=st.session_state.voice_reply_enabled,
        help="Reproduce respuestas de Daniela con voz del navegador",
    )
    st.session_state.voice_lang = st.selectbox(
        "Idioma voz",
        options=["es-ES", "en-US"],
        index=0 if st.session_state.voice_lang == "es-ES" else 1,
    )

    st.divider()

    st.markdown("## 🤖 Sobre Daniela")
    st.markdown(
        """
**DANIELA** es el núcleo de IA para infraestructura crítica.

Capacidades:
- Optimización de chillers
- Detección de fugas
- Alertas predictivas
- Agente conversacional
"""
    )


col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown('<h1 class="main-header">🤖 DANIELA</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p style="text-align: center; color: #888;">Infrastructure Intelligence · Kempinski Standard</p>',
        unsafe_allow_html=True,
    )


if st.session_state.auto_refresh:
    sim.step()

status = sim.get_global_status()

st.markdown("## 📊 KPIs en tiempo real")

kpi_cols = st.columns(4)

with kpi_cols[0]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="⚡ Electricidad hoy", value=f"{status['consumos']['electricidad_kwh']} kWh", delta="-5% vs ayer")
    st.markdown("</div>", unsafe_allow_html=True)

with kpi_cols[1]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="💧 Agua hoy", value=f"{status['consumos']['agua_m3']} m³", delta="+2% vs ayer", delta_color="inverse")
    st.markdown("</div>", unsafe_allow_html=True)

with kpi_cols[2]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="🔔 Fugas activas", value=status["habitaciones"]["fugas_activas"], delta="2 nuevas", delta_color="inverse")
    st.markdown("</div>", unsafe_allow_html=True)

with kpi_cols[3]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="💰 Ahorro anual", value="190.000€", delta="+12%")
    st.markdown("</div>", unsafe_allow_html=True)


st.markdown("## ❄️ Estado de Chillers")
chiller_cols = st.columns(3)

for i, chiller in enumerate(status["chillers"]):
    with chiller_cols[i]:
        cop = chiller.get("cop", 0)
        if cop and cop < 3.6:
            color = "#ff4b4b"
            status_text = "⚠️ Requiere atención"
        elif cop and cop < 3.8:
            color = "#ffc107"
            status_text = "🟡 Eficiencia media"
        else:
            color = "#00ff88"
            status_text = "✅ Óptimo"

        st.markdown(
            f"""
        <div style="background-color: #1E1E1E; padding: 1rem; border-radius: 10px; border-left: 4px solid {color};">
            <h3>{chiller['id']}</h3>
            <p style="font-size: 2rem; margin: 0;">{cop if cop else '--'}</p>
            <p style="color: {color};">{status_text}</p>
            <p>Potencia: {chiller.get('power_kw', 0)} kW</p>
        </div>
        """,
            unsafe_allow_html=True,
        )


st.markdown("## 📈 Consumo últimas 24h")
horas = [(datetime.now() - timedelta(hours=i)).strftime("%H:%M") for i in range(24, 0, -1)]
consumo_a = [random.randint(300, 500) for _ in range(24)]
consumo_b = [random.randint(200, 350) for _ in range(24)]
consumo_c = [random.randint(100, 250) for _ in range(24)]

fig = make_subplots(specs=[[{"secondary_y": False}]])
fig.add_trace(go.Scatter(x=horas, y=consumo_a, name="Building A", line=dict(color="#C5A467", width=2)), secondary_y=False)
fig.add_trace(go.Scatter(x=horas, y=consumo_b, name="Building B", line=dict(color="#4CAF50", width=2)), secondary_y=False)
fig.add_trace(go.Scatter(x=horas, y=consumo_c, name="Building C", line=dict(color="#2196F3", width=2)), secondary_y=False)
fig.update_layout(
    title="Consumo eléctrico por edificio (kW)",
    xaxis_title="Hora",
    yaxis_title="Potencia (kW)",
    hovermode="x unified",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="white"),
)
st.plotly_chart(fig, width="stretch")


st.markdown("## 🔔 Alertas activas")
alertas = [
    {
        "severidad": "alta",
        "mensaje": "Fuga de agua detectada en A302",
        "detalle": "Caudal nocturno: 9.6 L/h (4.2x superior al promedio)",
        "timestamp": datetime.now() - timedelta(minutes=23),
    },
    {
        "severidad": "media",
        "mensaje": "Chiller 2CH-1 con COP bajo (3.65)",
        "detalle": "Objetivo: 3.8 · Ahorro potencial: 124€/día",
        "timestamp": datetime.now() - timedelta(hours=2),
    },
    {
        "severidad": "baja",
        "mensaje": "Mantenimiento preventivo recomendado",
        "detalle": "Filtros AHU Building A · Programar en 15 días",
        "timestamp": datetime.now() - timedelta(hours=5),
    },
]

for alerta in alertas:
    if alerta["severidad"] == "alta":
        st.markdown(
            f"""
        <div class="alert-high">
            <strong>🔴 ALTA PRIORIDAD</strong><br>
            {alerta['mensaje']}<br>
            <small>{alerta['detalle']}</small><br>
            <small style="color: #888;">{alerta['timestamp'].strftime('%H:%M · %d/%m')}</small>
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif alerta["severidad"] == "media":
        st.markdown(
            f"""
        <div class="alert-medium">
            <strong>🟡 MEDIA PRIORIDAD</strong><br>
            {alerta['mensaje']}<br>
            <small>{alerta['detalle']}</small><br>
            <small style="color: #888;">{alerta['timestamp'].strftime('%H:%M · %d/%m')}</small>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
        <div class="alert-low">
            <strong>🔵 BAJA PRIORIDAD</strong><br>
            {alerta['mensaje']}<br>
            <small>{alerta['detalle']}</small><br>
            <small style="color: #888;">{alerta['timestamp'].strftime('%H:%M · %d/%m')}</small>
        </div>
        """,
            unsafe_allow_html=True,
        )


st.markdown("## 💬 Consulta a Daniela")
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hola, soy Daniela. ¿En qué puedo ayudarte con la gestión del resort?"}
    ]
if "last_voice_hash" not in st.session_state:
    st.session_state.last_voice_hash = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if hasattr(st, "audio_input"):
    voice_clip = st.audio_input("🎤 Habla con Daniela (beta)")
    if voice_clip is not None:
        clip_bytes = voice_clip.getvalue()
        clip_hash = hashlib.sha256(clip_bytes).hexdigest()

        if clip_hash != st.session_state.last_voice_hash:
            st.session_state.last_voice_hash = clip_hash
            try:
                spoken_text = transcribe_audio_bytes(clip_bytes)
                st.session_state.messages.append({"role": "user", "content": spoken_text})
                with st.chat_message("user"):
                    st.markdown(spoken_text)

                with st.chat_message("assistant"):
                    with st.spinner("Pensando..."):
                        response = agent.chat(spoken_text, include_realtime_data=True)
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        if st.session_state.voice_reply_enabled:
                            speak_in_browser(response, st.session_state.voice_lang)
            except Exception as error:
                st.warning(f"No se pudo transcribir el audio: {error}")
else:
    st.caption("Tu versión de Streamlit no soporta audio_input. Actualiza para habilitar voz en la app.")

if prompt := st.chat_input("Pregunta algo sobre el resort..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            response = agent.chat(prompt, include_realtime_data=True)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            if st.session_state.voice_reply_enabled:
                speak_in_browser(response, st.session_state.voice_lang)


st.markdown(
    """
<div class="footer">
    <p>DANIELA v0.2 · TierCore Infrastructure Kernel · Datos simulados para demostración</p>
    <p>🔄 {} · {} activo</p>
</div>
""".format(
        "Auto-refresh ON" if st.session_state.auto_refresh else "Actualización manual",
        datetime.now().strftime("%H:%M:%S"),
    ),
    unsafe_allow_html=True,
)
