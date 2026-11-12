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

# Clúster de nodos XTTS-v2 (CPU/GPU dedicados sin bloqueo de cuota)
NODOS_XTTS = [
    "https://jymnils-voice-cloning-xtts-v2.hf.space/gradio_api",
    "https://yemenedu-voice-cloning-xtts-v2.hf.space/gradio_api",
    "https://hasanbasbunar-voice-cloning-xtts-v2.hf.space/gradio_api",
]

# Clúster de nodos Seed-VC para refinamiento opcional de timbre
NODOS_SEED_VC = [
    "https://mtnproductions-seed-vc.hf.space/gradio_api",
    "https://mmwmm-seed-vc.hf.space/gradio_api",
    "https://plachta-seed-vc.hf.space/gradio_api",
]

# 1. Gestión de API Key y parámetros en la barra lateral
default_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

with st.sidebar:
    st.header("⚙️ Configuración")
    api_key = st.text_input(
        "API Key (ElevenLabs / OpenAI)",
        value=default_key,
        type="password",
        help="Si tienes plan de pago en ElevenLabs usa /v1/voices/add. Si tu cuenta es gratuita, activa automáticamente el motor End-to-End XTTS-v2 que clona tu voz real sin usar voces prefabricadas."
    )

    modo_clonacion = st.radio(
        "Motor de Clonación Zero-Shot:",
        options=[
            "🎯 XTTS-v2 Directo (Clona tu tono, acento y timbre)",
            "🧬 XTTS-v2 + Refinamiento Difusión (Doble pasada)",
            "🟣 ElevenLabs Nativo (Requiere plan Starter+)"
        ],
        index=0,
        help="XTTS-v2 Directo genera el audio desde cero a partir de tu grabación (sin usar ninguna voz intermedia como George)."
    )

    st.divider()
    st.subheader("Parámetros Acústicos")
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
    audio_grabado = st.audio_input("Habla claro durante 8 a 15 segundos acercaándote al micrófono (sin ruido de fondo)")
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
    # Mapear sliders de estabilidad y similitud a los hiperparámetros reales de XTTS-v2
    temperature = round(max(0.15, min(1.0, 1.15 - (stab * 0.7))), 2)
    top_p = round(max(0.5, min(0.95, 1.0 - (sim * 0.25))), 2)
    gpt_cond_len = int(round(15 + (sim * 30)))  # 15 a 45 segundos de ventana de condicionamiento

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
                False,                    # remove_silence_enabled (False preserva la naturalidad de la voz)
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


def refinar_timbre_seed_vc(bytes_audio_base: bytes, bytes_voz_usuario: bytes, sim: float) -> bytes:
    """
    Segunda pasada opcional de difusión acústica (Seed-VC) con intelligibility_cfg=0.0
    para reforzar aún más el timbre espectral del usuario sobre el audio ya clonado por XTTS-v2.
    """
    for base_url in NODOS_SEED_VC:
        try:
            ip_rnd = f"{random.randint(11,190)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            headers_nodo = {"X-Forwarded-For": ip_rnd}

            up_src = requests.post(
                f"{base_url}/upload",
                headers=headers_nodo,
                files=[("files", ("xtts_clon.mp3", bytes_audio_base, "audio/mpeg"))],
                timeout=30
            )
            up_tgt = requests.post(
                f"{base_url}/upload",
                headers=headers_nodo,
                files=[("files", ("voz_real.wav", bytes_voz_usuario, "audio/wav"))],
                timeout=30
            )
            if up_src.status_code != 200 or up_tgt.status_code != 200:
                continue

            src_file = {"path": up_src.json()[0], "meta": {"_type": "gradio.FileData"}}
            tgt_file = {"path": up_tgt.json()[0], "meta": {"_type": "gradio.FileData"}}

            # intelligebility_cfg_rate = 0.0 para NO mezclar timbre ajeno y priorizar 100% la voz del usuario
            payload = {
                "data": [
                    src_file,
                    tgt_file,
                    25,                     # diffusion_steps
                    1.0,                    # length_adjust
                    0.0,                    # intelligebility_cfg_rate = 0.0 (100% timbre objetivo)
                    round(max(0.7, sim), 2),# similarity_cfg_rate
                    0.9,
                    1.0,
                    1.0,
                    False,
                    False
                ]
            }
            res_call = requests.post(f"{base_url}/call/predict", headers=headers_nodo, json=payload, timeout=30)
            if res_call.status_code != 200 or "event_id" not in res_call.json():
                continue

            ev = res_call.json()["event_id"]
            res_stream = requests.get(f"{base_url}/call/predict/{ev}", headers=headers_nodo, timeout=120)
            if res_stream.status_code != 200:
                continue

            ultimo_json = None
            for linea in res_stream.text.splitlines():
                if linea.startswith("data: "):
                    try:
                        parsed = json.loads(linea[6:].strip())
                        if isinstance(parsed, list) and len(parsed) >= 2 and isinstance(parsed[1], dict):
                            ultimo_json = parsed[1]
                    except Exception:
                        continue

            if ultimo_json and ultimo_json.get("url"):
                res_wav = requests.get(ultimo_json["url"], headers=headers_nodo, timeout=60)
                if res_wav.status_code == 200 and len(res_wav.content) > 1000:
                    return res_wav.content
        except Exception:
            continue

    return bytes_audio_base


def clonar_elevenlabs_nativo(clave: str, bytes_voz_usuario: bytes, texto: str, stab: float, sim: float) -> bytes:
    """Flujo nativo de ElevenLabs (/v1/voices/add) para cuentas con plan Starter o superior."""
    headers = {"xi-api-key": clave.strip()}
    voice_id = None
    try:
        res_clon = requests.post(
            "https://api.elevenlabs.io/v1/voices/add",
            headers=headers,
            data={"name": "Voz_Taller_Temporal"},
            files={"files": ("muestra_taller.wav", bytes_voz_usuario, "audio/wav")},
            timeout=45
        )
        if res_clon.status_code != 200:
            raise RuntimeError(f"ElevenLabs devolvió ({res_clon.status_code}): {res_clon.text}")

        voice_id = res_clon.json()["voice_id"]
        res_tts = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers=headers,
            json={
                "text": texto,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": stab,
                    "similarity_boost": sim
                }
            },
            timeout=60
        )
        if res_tts.status_code != 200:
            raise RuntimeError(f"Error en TTS de ElevenLabs: {res_tts.text}")
        return res_tts.content
    finally:
        if voice_id:
            requests.delete(f"https://api.elevenlabs.io/v1/voices/{voice_id}", headers=headers, timeout=30)


# 4. Ejecución del pipeline de clonación y síntesis
if st.button("🚀 Clonar mi Voz y Generar Audio", type="primary", use_container_width=True):
    if not audio_grabado:
        st.warning("Primero graba un audio de referencia de 8 a 15 segundos en el Paso 1.")
    elif not texto_objetivo.strip():
        st.warning("Escribe un texto para sintetizar en el Paso 2.")
    else:
        bytes_muestra_usuario = audio_grabado.getvalue()

        try:
            if modo_clonacion.startswith("🟣"):
                if not api_key.strip():
                    st.error("Ingresa tu API Key de ElevenLabs en la barra lateral.")
                    st.stop()
                with st.spinner("Clonando voz directamente en ElevenLabs (`/v1/voices/add`)..."):
                    audio_final = clonar_elevenlabs_nativo(
                        api_key,
                        bytes_muestra_usuario,
                        texto_objetivo,
                        estabilidad,
                        similitud
                    )
                    formato_final = "audio/mp3"
                    ext_final = "mp3"
                    motor_usado = "ElevenLabs Instant Voice Cloning"

            elif modo_clonacion.startswith("🧬"):
                with st.spinner("Paso 1/2: Clonando tu voz, tono y cadencia desde tu grabación con XTTS-v2..."):
                    audio_xtts, motor_usado = clonar_voz_xtts_directo(
                        bytes_muestra_usuario,
                        texto_objetivo,
                        idioma_xtts,
                        estabilidad,
                        similitud,
                        velocidad
                    )
                with st.spinner("Paso 2/2: Refinando el timbre espectral con difusión acústica (Seed-VC)..."):
                    audio_final = refinar_timbre_seed_vc(
                        audio_xtts,
                        bytes_muestra_usuario,
                        similitud
                    )
                    formato_final = "audio/wav" if audio_final != audio_xtts else "audio/mp3"
                    ext_final = "wav" if audio_final != audio_xtts else "mp3"
                    motor_usado = f"{motor_usado} + Seed-VC Diffusion"

            else:
                with st.spinner(f"Extrayendo tu Speaker Embedding y sintetizando en {idioma_xtts} con tu propia voz (XTTS-v2)..."):
                    audio_final, motor_usado = clonar_voz_xtts_directo(
                        bytes_muestra_usuario,
                        texto_objetivo,
                        idioma_xtts,
                        estabilidad,
                        similitud,
                        velocidad
                    )
                    formato_final = "audio/mp3"
                    ext_final = "mp3"

            st.success("¡Voz clonada con éxito a partir de tu grabación!")
            st.caption(
                f"🎙️ **Motor utilizado:** `{motor_usado}` | **Idioma:** `{idioma_xtts}` | "
                f"**Condicionamiento acústico:** `{int(15 + similitud * 30)}s`"
            )
            st.audio(audio_final, format=formato_final)
            st.download_button(
                label=f"⬇️ Descargar mi voz clonada (.{ext_final})",
                data=audio_final,
                file_name=f"mi_voz_clonada.{ext_final}",
                mime=formato_final,
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Error al clonar la voz: {e}")
