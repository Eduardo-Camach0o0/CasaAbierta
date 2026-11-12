import json
import os
import random
import streamlit as st
import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env (si existe localmente)
load_dotenv()

# Configuración básica de la página
st.set_page_config(
    page_title="Clonador de Voz IA",
    page_icon="🎙️",
    layout="centered"
)

st.title("🎙️ Clonación de Voz en Vivo con IA")
st.markdown(
    "Graba una muestra de **8 a 15 segundos** de tu voz y haz que diga cualquier texto en **cualquier idioma** clonando directamente tu timbre, tono y cadencia."
)

# Textos sugeridos y su código de idioma para XTTS-v2
PLANTILLAS_IDIOMA = {
    "🇲🇽 Español": {
        "lang": "Spanish",
        "text": "¡Hola a todos! Esta aplicación la construimos en el taller de inteligencia artificial y está hablando con mi propia voz."
    },
    "🇯🇵 Japonés (Demo en Vivo)": {
        "lang": "Japanese",
        "text": "皆さん、こんにちは！このアプリケーションは人工知能のワークショップで作られました。今、私の声で日本語を話しています。"
    },
    "🇺🇸 Inglés": {
        "lang": "English",
        "text": "Hello everyone! We built this application live during the artificial intelligence workshop, and it is speaking with my own cloned voice."
    },
    "🇫🇷 Francés": {
        "lang": "French",
        "text": "Bonjour à tous ! Nous avons créé cette application lors de l'atelier d'intelligence artificielle et elle parle maintenant avec ma propre voix."
    },
    "🇧🇷 Portugués": {
        "lang": "Portuguese",
        "text": "Olá a todos! Construímos este aplicativo no workshop de inteligência artificial e agora ele está falando com a minha própria voz."
    },
    "🇩🇪 Alemán": {
        "lang": "German",
        "text": "Hallo zusammen! Wir haben diese Anwendung im Workshop für künstliche Intelligenz gebaut und sie spricht jetzt mit meiner eigenen Stimme."
    },
    "🇮🇹 Italiano": {
        "lang": "Italian",
        "text": "Ciao a tutti! Abbiamo costruito questa applicazione durante il workshop sull'intelligenza artificiale e ora parla con la mia voce."
    },
}

# Clúster de nodos XTTS-v2 (con respaldo automático)
NODOS_XTTS = [
    "https://jymnils-voice-cloning-xtts-v2.hf.space/gradio_api",
    "https://yemenedu-voice-cloning-xtts-v2.hf.space/gradio_api",
    "https://hasanbasbunar-voice-cloning-xtts-v2.hf.space/gradio_api",
]

# 1. Parámetros acústicos en la barra lateral
with st.sidebar:
    st.header("⚙️ Configuración Acústica")
    st.caption("🎯 **Motor activo:** `Coqui XTTS-v2 End-to-End` (Clonación directa de tono, acento y timbre)")

    estabilidad = st.slider(
        "Estabilidad de voz",
        min_value=0.1,
        max_value=1.0,
        value=0.65,
        step=0.05,
        help="Mayor estabilidad = temperatura más baja y mayor apego a tu cadencia original."
    )
    similitud = st.slider(
        "Similitud con tu timbre",
        min_value=0.1,
        max_value=1.0,
        value=0.85,
        step=0.05,
        help="Controla la ventana de condicionamiento acústico (gpt_cond_len / top_p) sobre tu muestra."
    )
    velocidad = st.slider(
        "Velocidad de habla",
        min_value=0.7,
        max_value=1.3,
        value=1.0,
        step=0.05
    )

    st.divider()
    usar_respaldo = st.checkbox(
        "Subir archivo .wav / Usar audio de respaldo",
        value=False,
        help="Actívalo si deseas subir un archivo de audio o si falla el micrófono en el salón."
    )

# 2. Captura de audio desde el navegador
st.subheader("Paso 1: Graba tu muestra de voz")
if not usar_respaldo:
    audio_grabado = st.audio_input("Habla claro durante 8 a 15 segundos acercándote al micrófono (sin ruido de fondo)")
else:
    audio_grabado = st.file_uploader(
        "Sube tu muestra de voz (.wav recomendado)",
        type=["wav", "mp3"]
    )
    if not audio_grabado and os.path.exists("muestra_respaldo.wav"):
        st.info("Usando `muestra_respaldo.wav` de respaldo.")
        with open("muestra_respaldo.wav", "rb") as f_wav:
            bytes_respaldo = f_wav.read()
        st.audio(bytes_respaldo, format="audio/wav")

        class _AudioRespaldo:
            def getvalue(self):
                return bytes_respaldo

        audio_grabado = _AudioRespaldo()

# 3. Texto a sintetizar
st.subheader("Paso 2: Elige el idioma y escribe lo que dirá tu clon")
etiqueta_idioma = st.selectbox(
    "Idioma de síntesis:",
    options=list(PLANTILLAS_IDIOMA.keys()),
    index=0
)

idioma_xtts = PLANTILLAS_IDIOMA[etiqueta_idioma]["lang"]
texto_objetivo = st.text_area(
    f"Texto a sintetizar ({idioma_xtts}):",
    value=PLANTILLAS_IDIOMA[etiqueta_idioma]["text"],
    height=110
)


def clonar_voz_xtts_directo(
    bytes_wav_usuario: bytes,
    texto: str,
    idioma: str,
    stab: float,
    sim: float,
    vel: float
) -> tuple[bytes, str]:
    """
    Clona directamente el tono, ritmo, acento y timbre del usuario desde su grabación WAV
    usando Coqui XTTS-v2 (sin pasar por ninguna voz prefabricada).
    """
    temperature = round(max(0.15, min(1.0, 1.15 - (stab * 0.7))), 2)
    top_p = round(max(0.5, min(0.95, 1.0 - (sim * 0.25))), 2)
    gpt_cond_len = int(round(15 + (sim * 30)))

    errores = []
    for base_url in NODOS_XTTS:
        try:
            ip_rnd = f"{random.randint(11,190)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            headers_nodo = {"X-Forwarded-For": ip_rnd}

            # 1. Subir la grabación WAV original del usuario al nodo XTTS-v2
            res_up = requests.post(
                f"{base_url}/upload",
                headers=headers_nodo,
                files=[("files", ("muestra_usuario.wav", bytes_wav_usuario, "audio/wav"))],
                timeout=30
            )
            if res_up.status_code != 200:
                errores.append(f"{base_url} upload HTTP {res_up.status_code}")
                continue

            ruta_remota = res_up.json()[0]
            url_referencia = f"{base_url}/file={ruta_remota}"

            # 2. Invocar /voice_clone_synthesis condicionando el GPT directamente con el audio del usuario
            data_xtts = [
                texto,                    # text
                url_referencia,           # reference_audio_url (voz real del usuario)
                None,                     # example_audio_name
                idioma,                   # language ('Spanish', 'Japanese', 'English', etc.)
                temperature,              # temperature
                float(vel),               # speed
                True,                     # do_sample
                2.5,                      # repetition_penalty
                1.0,                      # length_penalty
                gpt_cond_len,             # gpt_cond_len (ventana de extracción de Speaker Embedding)
                50,                       # top_k
                top_p,                    # top_p
                False,                    # remove_silence_enabled
                -45,                      # silence_threshold
                300,                      # min_silence_len
                150,                      # keep_silence
                "Native XTTS splitting",  # text_splitting_method
                250,                      # max_chars_per_segment
                True                      # enable_preprocessing
            ]

            res_call = requests.post(
                f"{base_url}/call/voice_clone_synthesis",
                headers=headers_nodo,
                json={"data": data_xtts},
                timeout=30
            )
            if res_call.status_code != 200 or "event_id" not in res_call.json():
                errores.append(f"{base_url} call error: {res_call.text[:120]}")
                continue

            event_id = res_call.json()["event_id"]

            # 3. Esperar el resultado del stream SSE
            res_sse = requests.get(
                f"{base_url}/call/voice_clone_synthesis/{event_id}",
                headers=headers_nodo,
                timeout=120
            )
            if res_sse.status_code != 200:
                errores.append(f"{base_url} sse HTTP {res_sse.status_code}")
                continue

            url_audio_final = None
            for linea in res_sse.text.splitlines():
                if linea.startswith("data: "):
                    cuerpo = linea[6:].strip()
                    if not cuerpo or cuerpo == "null":
                        continue
                    try:
                        parsed = json.loads(cuerpo)
                        if isinstance(parsed, list) and len(parsed) >= 1 and isinstance(parsed[0], dict):
                            url_audio_final = parsed[0].get("url")
                            if not url_audio_final and parsed[0].get("path"):
                                url_audio_final = f"{base_url}/file={parsed[0]['path']}"
                    except Exception:
                        continue

            if not url_audio_final:
                errores.append(f"{base_url} no devolvió URL de audio ({res_sse.text[:120]})")
                continue

            res_audio = requests.get(url_audio_final, headers=headers_nodo, timeout=60)
            if res_audio.status_code == 200 and len(res_audio.content) > 1000:
                nombre_nodo = base_url.split("//")[1].split(".")[0]
                return res_audio.content, f"Coqui XTTS-v2 End-to-End ({nombre_nodo})"

        except Exception as exc:
            errores.append(f"{base_url}: {exc}")
            continue

    raise RuntimeError("No se pudo completar la síntesis en los nodos XTTS-v2: " + " | ".join(errores))


# 4. Ejecución del pipeline de clonación y síntesis
if st.button("🚀 Clonar mi Voz y Generar Audio", type="primary", use_container_width=True):
    if not audio_grabado:
        st.warning("Primero graba un audio de referencia de 8 a 15 segundos en el Paso 1.")
    elif not texto_objetivo.strip():
        st.warning("Escribe un texto para sintetizar en el Paso 2.")
    else:
        bytes_muestra_usuario = audio_grabado.getvalue()

        try:
            with st.spinner(f"Extrayendo tu Speaker Embedding y sintetizando en {idioma_xtts} con tu propia voz (XTTS-v2)..."):
                audio_final, motor_usado = clonar_voz_xtts_directo(
                    bytes_muestra_usuario,
                    texto_objetivo,
                    idioma_xtts,
                    estabilidad,
                    similitud,
                    velocidad
                )

            st.success("¡Voz clonada con éxito a partir de tu grabación!")
            st.caption(
                f"🎙️ **Motor utilizado:** `{motor_usado}` | **Idioma:** `{idioma_xtts}` | "
                f"**Condicionamiento acústico:** `{int(15 + similitud * 30)}s`"
            )
            st.audio(audio_final, format="audio/mp3")
            st.download_button(
                label="⬇️ Descargar mi voz clonada (.mp3)",
                data=audio_final,
                file_name="mi_voz_clonada.mp3",
                mime="audio/mp3",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Error al clonar la voz: {e}")
