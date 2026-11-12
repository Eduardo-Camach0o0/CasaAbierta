import json
import os
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
    "Graba una muestra de **8 a 12 segundos** de tu voz y haz que diga cualquier texto en **cualquier idioma** con tu propio timbre vocal."
)

# Textos sugeridos para la demo en vivo ("El Gancho": Español, Japonés, Inglés, Francés)
PLANTILLAS_IDIOMA = {
    "🇲🇽 Español (Personalizado)": (
        "¡Hola a todos! Esta aplicación la construimos en el taller de inteligencia artificial "
        "y está hablando con mi propia voz."
    ),
    "🇯🇵 Japonés (Demo en Vivo)": (
        "皆さん、こんにちは！このアプリケーションは人工知能のワークショップで作られました。"
        "今、私の声で日本語を話しています。"
    ),
    "🇺🇸 Inglés (Global Tech)": (
        "Hello everyone! We built this application live during the artificial intelligence workshop, "
        "and it is speaking with my own cloned voice."
    ),
    "🇫🇷 Francés (Demo Multilingüe)": (
        "Bonjour à tous ! Nous avons créé cette application lors de l'atelier d'intelligence artificielle "
        "et elle parle maintenant avec ma propre voix."
    ),
    "🇧🇷 Portugués": (
        "Olá a todos! Construímos este aplicativo no workshop de inteligência artificial "
        "e agora ele está falando com a minha própria voz."
    ),
}

# 1. Gestión de API Key (permite usar .env o ingresarla en la barra lateral)
default_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

with st.sidebar:
    st.header("⚙️ Configuración")
    api_key = st.text_input(
        "API Key (ElevenLabs)",
        value=default_key,
        type="password",
        help="Ingresa tu API Key de ElevenLabs (sk_...). Si tu cuenta es gratuita, el sistema activa automáticamente el clonador Zero-Shot para extraer tu Speaker Embedding sin requerir plan de pago."
    )
    estabilidad = st.slider(
        "Estabilidad de voz",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.05,
        help="Menor valor = más expresiva; Mayor valor = más estable."
    )
    similitud = st.slider(
        "Similitud con tu timbre",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help="Qué tanto se apega el clon al timbre acústico de tu grabación."
    )
    pasos_difusion = st.slider(
        "Calidad de clonación (Diffusion Steps)",
        min_value=15,
        max_value=40,
        value=25,
        step=5,
        help="Pasos de refinamiento del timbre vocal (25 ofrece excelente balance entre fidelidad y velocidad)."
    )

    st.divider()
    usar_respaldo = st.checkbox(
        "Subir archivo de audio / Usar respaldo",
        value=False,
        help="Actívalo si quieres subir un .wav/.mp3 pregrabado o si falla el micrófono en el salón."
    )

# 2. Captura de audio desde el navegador
st.subheader("Paso 1: Graba tu muestra de voz")
if not usar_respaldo:
    audio_grabado = st.audio_input("Habla claro durante 8 a 12 segundos sin ruido de fondo")
else:
    audio_grabado = st.file_uploader(
        "Sube tu muestra de voz (.wav o .mp3)",
        type=["wav", "mp3", "m4a", "ogg"]
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
st.subheader("Paso 2: Escribe lo que dirá tu clon")
idioma_seleccionado = st.selectbox(
    "Plantilla rápida de idioma:",
    options=list(PLANTILLAS_IDIOMA.keys()),
    index=0
)

texto_objetivo = st.text_area(
    "Texto en español (o cualquier otro idioma):",
    value=PLANTILLAS_IDIOMA[idioma_seleccionado],
    height=110
)


def clonar_timbre_zero_shot(bytes_tts_base: bytes, bytes_voz_usuario: bytes, stab: float, sim: float, steps: int):
    """
    Extrae el Speaker Embedding del audio grabado por el usuario (bytes_voz_usuario)
    y transfiere su timbre exacto al audio sintetizado multilingüe (bytes_tts_base)
    usando el motor Zero-Shot Diffusion Voice Cloning (Seed-VC).
    """
    base_url = "https://plachta-seed-vc.hf.space/gradio_api"

    # 1. Subir el audio base (pronunciación multilingüe) y el audio de referencia (voz del usuario)
    up_source = requests.post(
        f"{base_url}/upload",
        files=[("files", ("tts_base.mp3", bytes_tts_base, "audio/mp3"))],
        timeout=45
    )
    up_target = requests.post(
        f"{base_url}/upload",
        files=[("files", ("mi_voz_referencia.wav", bytes_voz_usuario, "audio/wav"))],
        timeout=45
    )

    if up_source.status_code != 200 or up_target.status_code != 200:
        raise RuntimeError("No se pudieron subir las muestras al motor de clonación acústica.")

    source_path = up_source.json()[0]
    target_path = up_target.json()[0]

    source_file = {"path": source_path, "meta": {"_type": "gradio.FileData"}}
    target_file = {"path": target_path, "meta": {"_type": "gradio.FileData"}}

    # Mapear los sliders del taller a los hiperparámetros acústicos del modelo
    intelligibility_cfg = round(max(0.1, min(1.0, stab)), 2)
    similarity_cfg = round(max(0.3, min(1.0, sim)), 2)

    payload_predict = {
        "data": [
            source_file,         # source_audio_path (lo que se dice y en qué idioma)
            target_file,         # target_audio_path (tu timbre vocal real a clonar)
            int(steps),          # diffusion_steps
            1.0,                 # length_adjust
            intelligibility_cfg, # intelligebility_cfg_rate
            similarity_cfg,      # similarity_cfg_rate (Similitud con tu timbre)
            0.9,                 # top_p
            1.0,                 # temperature
            1.0,                 # repetition_penalty
            False,               # convert_style
            False                # anonymization_only
        ]
    }

    res_call = requests.post(
        f"{base_url}/call/predict",
        json=payload_predict,
        timeout=30
    )
    if res_call.status_code != 200:
        raise RuntimeError(f"Error al iniciar inferencia Zero-Shot: {res_call.text}")

    event_id = res_call.json()["event_id"]

    # Escuchar el stream SSE hasta recibir el archivo WAV completo con la voz clonada
    res_stream = requests.get(f"{base_url}/call/predict/{event_id}", timeout=120)
    if res_stream.status_code != 200:
        raise RuntimeError(f"Error en la síntesis del clon vocal: {res_stream.text}")

    ultimo_json = None
    for linea in res_stream.text.splitlines():
        if linea.startswith("data: "):
            contenido = linea[6:].strip()
            try:
                parsed = json.loads(contenido)
                if isinstance(parsed, list) and len(parsed) >= 2 and isinstance(parsed[1], dict):
                    ultimo_json = parsed[1]
            except Exception:
                continue

    if not ultimo_json or not ultimo_json.get("url"):
        raise RuntimeError("El motor de clonación no devolvió el archivo de audio final.")

    audio_clonado_res = requests.get(ultimo_json["url"], timeout=60)
    if audio_clonado_res.status_code != 200:
        raise RuntimeError("No se pudo descargar el audio clonado resultante.")

    return audio_clonado_res.content


def generar_tts_base(clave: str, texto: str, stab: float, sim: float):
    """
    Genera la locución multilingüe base con ElevenLabs (eleven_multilingual_v2)
    o con OpenAI si se ingresó una clave sk-proj-...
    """
    clave = clave.strip()

    # Si es una clave de ElevenLabs (ej. sk_...)
    if not clave.startswith("sk-proj-"):
        headers = {"xi-api-key": clave}
        # Voz multilingüe neutra de alta claridad en ElevenLabs (George / Rachel)
        voice_id_base = "JBFqnCBsd6RMkjVDRZzb"
        url_tts = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id_base}"
        payload = {
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": stab,
                "similarity_boost": sim
            }
        }
        res = requests.post(url_tts, headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            return res.content, "ElevenLabs (eleven_multilingual_v2)"

    # Fallback a OpenAI TTS si se proporcionó clave de OpenAI o falló la cuota
    openai_key = clave if clave.startswith("sk-") else os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        res_oa = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini-tts",
                "input": texto,
                "voice": "coral",
                "response_format": "mp3"
            },
            timeout=60
        )
        if res_oa.status_code == 200:
            return res_oa.content, "OpenAI Multilingual TTS"

    raise RuntimeError("Error al sintetizar la pronunciación base con la API Key proporcionada.")


# 4. Ejecución del pipeline de clonación y síntesis
if st.button("🚀 Clonar y Generar Audio", type="primary", use_container_width=True):
    if not api_key.strip():
        st.error("Por favor ingresa tu API Key en la barra lateral.")
    elif not audio_grabado:
        st.warning("Primero graba un audio de referencia de 8 a 12 segundos.")
    elif not texto_objetivo.strip():
        st.warning("Escribe un texto para sintetizar.")
    else:
        headers = {"xi-api-key": api_key.strip()}
        bytes_muestra_usuario = audio_grabado.getvalue()
        clonado_en_elevenlabs_nativo = False
        voice_id = None

        # PASO A: Intentar primero el endpoint nativo de Instant Voice Cloning de ElevenLabs
        if not api_key.strip().startswith("sk-proj-"):
            with st.spinner("Extrayendo timbre vocal (Speaker Embedding)..."):
                url_clon = "https://api.elevenlabs.io/v1/voices/add"
                files = {
                    "files": ("muestra_taller.wav", bytes_muestra_usuario, "audio/wav")
                }
                data = {"name": "Voz_Taller_Temporal"}
                res_clon = requests.post(url_clon, headers=headers, data=data, files=files, timeout=45)

                if res_clon.status_code == 200:
                    voice_id = res_clon.json()["voice_id"]
                    clonado_en_elevenlabs_nativo = True

        # Si la cuenta de ElevenLabs tiene plan con Instant Voice Cloning habilitado:
        if clonado_en_elevenlabs_nativo and voice_id:
            try:
                with st.spinner("Sintetizando nuevo audio multilingüe con tu voz clonada..."):
                    url_tts = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                    payload = {
                        "text": texto_objetivo,
                        "model_id": "eleven_multilingual_v2",
                        "voice_settings": {
                            "stability": estabilidad,
                            "similarity_boost": similitud
                        }
                    }
                    res_tts = requests.post(url_tts, headers=headers, json=payload, timeout=60)

                    if res_tts.status_code == 200:
                        st.success("¡Voz clonada con éxito (ElevenLabs Instant Voice Cloning)!")
                        st.audio(res_tts.content, format="audio/mp3")
                        st.download_button(
                            label="⬇️ Descargar audio",
                            data=res_tts.content,
                            file_name="mi_voz_clonada.mp3",
                            mime="audio/mp3",
                            use_container_width=True
                        )
                    else:
                        st.error(f"Error al generar audio: {res_tts.text}")
            finally:
                # Limpieza automática: eliminar la voz temporal para no llenar el límite
                requests.delete(f"https://api.elevenlabs.io/v1/voices/{voice_id}", headers=headers, timeout=30)

        # PASO B: Si la cuenta de ElevenLabs es Gratuita (bloquea /v1/voices/add),
        # sintetizamos la pronunciación con ElevenLabs Multilingual v2 y clonamos el timbre
        # exacto de la grabación del usuario con el motor Zero-Shot Diffusion (Seed-VC)
        else:
            try:
                with st.spinner("1/2 Generando pronunciación multilingüe con ElevenLabs (`eleven_multilingual_v2`)..."):
                    bytes_tts_base, motor_tts = generar_tts_base(
                        api_key,
                        texto_objetivo,
                        estabilidad,
                        similitud
                    )

                with st.spinner("2/2 Extrayendo tu Speaker Embedding y clonando tu timbre vocal exacto (Zero-Shot Diffusion)..."):
                    audio_clonado_wav = clonar_timbre_zero_shot(
                        bytes_tts_base,
                        bytes_muestra_usuario,
                        estabilidad,
                        similitud,
                        pasos_difusion
                    )

                st.success("¡Voz clonada con éxito con tu timbre vocal!")
                st.caption(
                    f"🧬 **Pipeline ejecutado:** Pronunciación vía `{motor_tts}` + "
                    f"Extracción de *Speaker Embedding* y clonación Zero-Shot (`Seed-VC`, {pasos_difusion} pasos, similitud {int(similitud*100)}%)."
                )
                st.audio(audio_clonado_wav, format="audio/wav")
                st.download_button(
                    label="⬇️ Descargar mi voz clonada (.wav)",
                    data=audio_clonado_wav,
                    file_name="mi_voz_clonada.wav",
                    mime="audio/wav",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Ocurrió un error durante la clonación de voz: {e}")
