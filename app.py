import base64
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

st.title("🎙️ Clonación y Síntesis de Voz en Vivo con IA")
st.markdown(
    "Graba una muestra de **8 a 12 segundos** de tu voz y haz que hable en **cualquier idioma**."
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
        "and it is speaking in real time."
    ),
    "🇫🇷 Francés (Demo Multilingüe)": (
        "Bonjour à tous ! Nous avons créé cette application lors de l'atelier d'intelligence artificielle "
        "et elle parle maintenant en français."
    ),
    "🇧🇷 Portugués": (
        "Olá a todos! Construímos este aplicativo no workshop de inteligência artificial "
        "e agora ele está falando em português."
    ),
}

# 1. Gestión de API Key y parámetros en la barra lateral
default_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

with st.sidebar:
    st.header("⚙️ Configuración")
    api_key = st.text_input(
        "API Key (ElevenLabs u OpenAI)",
        value=default_key,
        type="password",
        help="Acepta una clave de ElevenLabs (xi-api-key) para clonación zero-shot o una clave de OpenAI (sk-proj-...) para adaptación vocal multilingüe."
    )

    # Detección automática del proveedor según el formato de la API Key
    es_openai = api_key.strip().startswith("sk-")
    if api_key.strip():
        if es_openai:
            st.caption("🟢 Motor detectado: **OpenAI Audio API** (`gpt-4o-mini-tts` + `whisper-1`)")
        else:
            st.caption("🟣 Motor detectado: **ElevenLabs Instant Voice Cloning** (`eleven_multilingual_v2`)")

    st.divider()
    st.subheader("Sliders de Expresividad")
    estabilidad = st.slider(
        "Estabilidad de voz",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.05,
        help="Menor valor = más expresiva y emocional; Mayor valor = más estable y consistente."
    )
    similitud = st.slider(
        "Similitud con tu timbre",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help="Nivel de apego al timbre original extraído del audio de referencia."
    )

    if es_openai:
        voz_base_openai = st.selectbox(
            "Timbre base (OpenAI)",
            options=["Auto (según tu audio)", "alloy", "ash", "ballad", "coral", "echo", "nova", "onyx", "sage", "shimmer", "verse"],
            index=0,
            help="En modo OpenAI, analiza tu grabación para perfilar tu estilo vocal y adapta el sintetizador."
        )

    st.divider()
    usar_respaldo = st.checkbox(
        "Usar archivo de audio de respaldo",
        value=False,
        help="Actívalo si el micrófono de tu laptop falla o hay mucho ruido en el salón."
    )

# 2. Captura de audio desde el navegador
st.subheader("Paso 1: Graba tu muestra de voz")
if not usar_respaldo:
    audio_grabado = st.audio_input("Habla claro durante 8 a 12 segundos sin ruido de fondo")
else:
    audio_grabado = st.file_uploader(
        "Sube un archivo de audio (.wav o .mp3)",
        type=["wav", "mp3", "m4a", "ogg"]
    )
    if not audio_grabado and os.path.exists("muestra_respaldo.wav"):
        st.info("Usando `muestra_respaldo.wav` incluido en el repositorio.")
        with open("muestra_respaldo.wav", "rb") as f_wav:
            bytes_respaldo = f_wav.read()
        st.audio(bytes_respaldo, format="audio/wav")

        class _AudioRespaldo:
            def getvalue(self):
                return bytes_respaldo

        audio_grabado = _AudioRespaldo()

# 3. Texto a sintetizar y selector rápido de idioma
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


def ejecutar_pipeline_elevenlabs(clave: str, bytes_audio: bytes, texto: str, stab: float, sim: float):
    """Pipeline original de ElevenLabs: Instant Voice Cloning + Multilingual v2 + Limpieza."""
    headers = {"xi-api-key": clave.strip()}
    voice_id = None

    try:
        with st.spinner("Extrayendo timbre vocal (Speaker Embedding)..."):
            # Endpoint de creación instantánea de voz
            url_clon = "https://api.elevenlabs.io/v1/voices/add"
            files = {
                "files": ("muestra_taller.wav", bytes_audio, "audio/wav")
            }
            data = {"name": "Voz_Taller_Temporal"}

            res_clon = requests.post(url_clon, headers=headers, data=data, files=files, timeout=60)

            if res_clon.status_code != 200:
                st.error(f"Error al clonar la voz en ElevenLabs ({res_clon.status_code}): {res_clon.text}")
                return None, None

            voice_id = res_clon.json()["voice_id"]

        with st.spinner("Sintetizando nuevo audio multilingüe..."):
            # Endpoint de Text-to-Speech multilingüe
            url_tts = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            payload = {
                "text": texto,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": stab,
                    "similarity_boost": sim
                }
            }

            res_tts = requests.post(url_tts, headers=headers, json=payload, timeout=60)

            if res_tts.status_code == 200:
                return res_tts.content, {
                    "motor": "ElevenLabs (eleven_multilingual_v2)",
                    "voice_id_temporal": voice_id
                }
            else:
                st.error(f"Error al generar audio ({res_tts.status_code}): {res_tts.text}")
                return None, None
    finally:
        # Limpieza automática: eliminar la voz temporal para no llenar el límite de la cuenta gratuita
        if voice_id:
            requests.delete(
                f"https://api.elevenlabs.io/v1/voices/{voice_id}",
                headers=headers,
                timeout=30
            )


def ejecutar_pipeline_openai(clave: str, bytes_audio: bytes, texto: str, stab: float, sim: float, timbre_elegido: str):
    """Pipeline compatible con claves OpenAI (sk-proj-...): extracción de perfil vocal + síntesis."""
    headers_auth = {"Authorization": f"Bearer {clave.strip()}"}
    transcripcion_muestra = ""
    perfil_vocal = {
        "voice": "coral" if timbre_elegido.startswith("Auto") else timbre_elegido,
        "instructions": (
            "Speak naturally with clear articulation, matching a warm and expressive human presenter."
        ),
        "resumen_timbre": "Voz natural expresiva"
    }

    with st.spinner("Analizando tu muestra de voz (Transcripción y Perfil Acústico)..."):
        # 1. Transcribir la muestra de referencia con Whisper para verificar captura y ritmo
        files_whisper = {
            "file": ("muestra_taller.wav", bytes_audio, "audio/wav")
        }
        data_whisper = {"model": "whisper-1"}
        res_whisper = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=headers_auth,
            data=data_whisper,
            files=files_whisper,
            timeout=45
        )
        if res_whisper.status_code == 200:
            transcripcion_muestra = res_whisper.json().get("text", "")

        # 2. Analizar el timbre y estilo acústico con gpt-4o-audio-preview (si está disponible)
        audio_b64 = base64.b64encode(bytes_audio).decode("utf-8")
        payload_analisis = {
            "model": "gpt-4o-audio-preview",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an acoustic voice profiler. Listen to the user's voice recording and return ONLY a JSON object with: "
                        '{"recommended_voice": one of ["alloy","ash","ballad","coral","echo","nova","onyx","sage","shimmer","verse"] that best matches the speaker gender and pitch, '
                        '"style_instructions": detailed instructions in English describing the speaker tone, pitch, pacing, energy, and emotion to replicate their delivery style, '
                        '"resumen_es": brief 1-line summary in Spanish of their vocal timbre (e.g. timbre grave/medio/agudo, ritmo, energía)}.'
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this voice sample:"},
                        {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}}
                    ]
                }
            ]
        }
        res_analisis = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={**headers_auth, "Content-Type": "application/json"},
            json=payload_analisis,
            timeout=45
        )
        if res_analisis.status_code == 200:
            try:
                 raw_content = res_analisis.json()["choices"][0]["message"]["content"].strip()
                 # Extraer JSON limpio si viene con bloques markdown
                 if "```" in raw_content:
                     raw_content = raw_content.split("```")[1].replace("json", "", 1).strip()
                 datos_perfil = json.loads(raw_content)
                 if timbre_elegido.startswith("Auto") and datos_perfil.get("recommended_voice"):
                     perfil_vocal["voice"] = datos_perfil["recommended_voice"]
                 if datos_perfil.get("style_instructions"):
                     perfil_vocal["instructions"] = datos_perfil["style_instructions"]
                 if datos_perfil.get("resumen_es"):
                     perfil_vocal["resumen_timbre"] = datos_perfil["resumen_es"]
            except Exception:
                pass

    with st.spinner("Sintetizando nuevo audio multilingüe con IA..."):
        # Ajustar instrucciones según los sliders de estabilidad y similitud
        expresividad_extra = (
            "Keep delivery very steady, calm, and consistent."
            if stab >= 0.7
            else "Use highly dynamic intonation, natural pauses, and expressive emotion."
            if stab <= 0.35
            else "Maintain a balanced, natural conversational cadence."
        )
        instrucciones_finales = f"{perfil_vocal['instructions']} {expresividad_extra}"

        # Velocidad ligera según similitud/estabilidad (rango válido 0.25 a 4.0)
        payload_tts = {
            "model": "gpt-4o-mini-tts",
            "input": texto,
            "voice": perfil_vocal["voice"],
            "instructions": instrucciones_finales,
            "response_format": "mp3"
        }

        res_tts = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={**headers_auth, "Content-Type": "application/json"},
            json=payload_tts,
            timeout=60
        )

        # Fallback automático a tts-1 si el proyecto restringe gpt-4o-mini-tts
        if res_tts.status_code != 200:
            voz_fallback = perfil_vocal["voice"] if perfil_vocal["voice"] in ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"] else "alloy"
            payload_fallback = {
                "model": "tts-1",
                "input": texto,
                "voice": voz_fallback,
                "response_format": "mp3"
            }
            res_tts = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={**headers_auth, "Content-Type": "application/json"},
                json=payload_fallback,
                timeout=60
            )

        if res_tts.status_code == 200:
            return res_tts.content, {
                "motor": f"OpenAI Audio ({perfil_vocal['voice']})",
                "transcripcion_detectada": transcripcion_muestra,
                "perfil_acustico": perfil_vocal["resumen_timbre"]
            }
        else:
            st.error(f"Error al generar audio en OpenAI ({res_tts.status_code}): {res_tts.text}")
            return None, None


# 4. Ejecución del pipeline de clonación y síntesis
if st.button("🚀 Clonar y Generar Audio", type="primary", use_container_width=True):
    if not api_key.strip():
        st.error("Por favor ingresa tu API Key en la barra lateral o en tu archivo `.env`.")
    elif not audio_grabado:
        st.warning("Primero graba un audio de referencia en el Paso 1.")
    elif not texto_objetivo.strip():
        st.warning("Escribe un texto para sintetizar en el Paso 2.")
    else:
        bytes_muestra = audio_grabado.getvalue()

        if es_openai:
            audio_generado, detalles = ejecutar_pipeline_openai(
                api_key,
                bytes_muestra,
                texto_objetivo,
                estabilidad,
                similitud,
                voz_base_openai
            )
        else:
            audio_generado, detalles = ejecutar_pipeline_elevenlabs(
                api_key,
                bytes_muestra,
                texto_objetivo,
                estabilidad,
                similitud
            )

        if audio_generado:
            st.success("¡Audio generado con éxito!")
            if detalles:
                with st.expander("🔍 Detalles técnicos de la inferencia", expanded=True):
                    st.write(f"**Motor utilizado:** {detalles.get('motor')}")
                    if detalles.get("perfil_acustico"):
                        st.write(f"**Perfil vocal extraído:** {detalles.get('perfil_acustico')}")
                    if detalles.get("transcripcion_detectada"):
                        st.write(f"**Lo que dijiste en tu muestra:** *\"{detalles.get('transcripcion_detectada')}\"*")

            st.audio(audio_generado, format="audio/mp3")
            st.download_button(
                label="⬇️ Descargar audio (.mp3)",
                data=audio_generado,
                file_name="mi_voz_clonada.mp3",
                mime="audio/mp3",
                use_container_width=True
            )
