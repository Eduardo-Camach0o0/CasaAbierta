# Documento de Planeación de Taller Práctico: Clonación de Voz en Tiempo Real con IA

## 1. Ficha Técnica del Evento
* **Título del Taller:** *Tu Voz en Cualquier Idioma: Construye tu Propia App de Clonación Vocal con IA*
* **Duración Total:** 75 – 90 minutos.
* **Modalidad:** Práctica guiada en vivo (*Hands-on* / *Code-along*).
* **Público Objetivo:** Estudiantes, desarrolladores y entusiastas de la IA (conocimientos básicos de Python o lógica de programación deseables, no obligatorios).
* **Entregable para el Asistente:** Una aplicación web funcional en Streamlit conectada a una API de síntesis y clonación de voz, más el repositorio público en GitHub listo para reutilizar.

---

## 2. Arquitectura Técnica (Lo que se construirá y explicará)
El sistema elimina la fricción de instalar GPUs locales o compilar librerías pesadas en vivo, separando el frontend de la inferencia pesada:

1. **Frontend / Interfaz Web (`Streamlit`):**
   * Componente nativo `st.audio_input` para grabar voz directamente desde el navegador (sin subir archivos externos).
   * Caja de texto para el guion y selector de idioma/estabilidad.
   * Reproductor `st.audio` para escuchar y descargar el resultado.
2. **Capa de Comunicación (`REST API / SDK`):**
   * Envío del flujo de bytes (`BytesIO`) del audio grabado hacia la nube.
   * Gestión segura de credenciales mediante variables de entorno (`.env` o `st.secrets`).
3. **Motor de Inferencia Generativa (API de Voz, ej. ElevenLabs o Cartesia):**
   * **Extracción de *Speaker Embedding*:** Conversión de la muestra de 10 segundos en un vector numérico de identidad vocal.
   * **Síntesis Multilingüe (*Zero-Shot*):** Generación de onda sonora aplicando el timbre extraído al texto en español o cualquier otro idioma.

---

## 3. Cronograma Detallado (Minuto a Minuto)

| Bloque | Tiempo | Tema / Actividad | Objetivo Didáctico |
| :--- | :--- | :--- | :--- |
| **1. Impacto Inicial** | 00 – 10 min | **Demo en Vivo ("El Gancho")** | Mostrar la app terminada: grabar tu voz en el escenario y hacerla hablar japonés y español al instante. |
| **2. Teoría Aplicada** | 10 – 25 min | **¿Cómo funciona por dentro?** | Explicar qué es un espectrograma, cómo se comprime el timbre humano en un *Speaker Embedding* y por qué la inferencia en nube supera las limitaciones de hardware local. |
| **3. Setup Express** | 25 – 40 min | **Clonación del Repo y Credenciales** | Los asistentes clonan el repo público de GitHub, crean su cuenta gratuita en la plataforma de API, obtienen su API Key e instalan `requirements.txt`. |
| **4. Anatomía del Código** | 40 – 65 min | **Recorrido guiado por `app.py`** | Revisar bloque por bloque el código regalado: captura de audio en memoria, llamada *multipart/form-data* a la API y renderizado de respuesta. |
| **5. Laboratorio Libre** | 65 – 80 min | **Pruebas y Retos Creativos** | Cada asistente graba su voz, prueba distintos tonos, cambia idiomas y ajusta parámetros (`stability`, `similarity_boost`). |
| **6. Cierre y Ética** | 80 – 90 min | **Seguridad, Deepfakes y Q&A** | Breve reflexión sobre marcas de agua en audio, consentimiento y próximos pasos para integrar esto en agentes telefónicos o bots de WhatsApp. |

---

## 4. Estructura del Repositorio Público (GitHub)
Para que los asistentes puedan levantarlo en menos de 3 minutos sin errores, el repositorio debe mantenerse minimalista:

```text
taller-clonacion-voz-ia/
├── app.py                # Código principal de Streamlit (comentado línea por línea)
├── requirements.txt      # Dependencias mínimas (streamlit, requests, python-dotenv)
├── .env.example          # Plantilla para colocar la API Key
├── .gitignore            # Excluye .env y archivos temporales .wav/.mp3
└── README.md             # Guía rápida de instalación en 3 pasos + diagrama de arquitectura
```

### Contenido recomendado para `requirements.txt`:
```text
streamlit>=1.40.0
requests>=2.31.0
python-dotenv>=1.0.0
```
*(Nota: Usar `st.audio_input` nativo de Streamlit 1.40+ evita instalar dependencias externas de grabación).*

---

## 5. Código Base Comentado (`app.py`)
Este es el código limpio que puedes regalar en el repositorio. Está diseñado para ser fácil de leer y explicar durante el taller:

```python
import os
import streamlit as st
import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

# Configuración básica de la página
st.set_page_config(page_title="Clonador de Voz IA", page_icon="🎙️", layout="centered")
st.title("🎙️ Clonación de Voz en Vivo con IA")
st.markdown("Graba una muestra de 10 segundos de tu voz y haz que diga cualquier texto.")

# 1. Gestión de API Key (permite usar .env o ingresarla en la barra lateral)
with st.sidebar:
    st.header("Configuración")
    api_key = st.text_input(
        "API Key (ElevenLabs)", 
        value=os.getenv("ELEVENLABS_API_KEY", ""), 
        type="password"
    )
    estabilidad = st.slider("Estabilidad de voz", 0.0, 1.0, 0.5, help="Menor valor = más expresiva; Mayor valor = más monótona.")
    similitud = st.slider("Similitud con tu timbre", 0.0, 1.0, 0.8)

# 2. Captura de audio desde el navegador
st.subheader("Paso 1: Graba tu muestra de voz")
audio_grabado = st.audio_input("Habla claro durante 8 a 12 segundos sin ruido de fondo")

# 3. Texto a sintetizar
st.subheader("Paso 2: Escribe lo que dirá tu clon")
texto_objetivo = st.text_area(
    "Texto en español (o cualquier otro idioma):",
    value="¡Hola a todos! Esta aplicación la construimos en el taller de inteligencia artificial y está hablando con mi propia voz."
)

# 4. Ejecución del pipeline de clonación y síntesis
if st.button("🚀 Clonar y Generar Audio", type="primary"):
    if not api_key:
        st.error("Por favor ingresa tu API Key en la barra lateral.")
    elif not audio_grabado:
        st.warning("Primero graba un audio de referencia.")
    elif not texto_objetivo.strip():
        st.warning("Escribe un texto para sintetizar.")
    else:
        headers = {"xi-api-key": api_key}
        
        with st.spinner("Extrayendo timbre vocal (Speaker Embedding)..."):
            # Endpoint de creación instantánea de voz
            url_clon = "https://api.elevenlabs.io/v1/voices/add"
            files = {
                "files": ("muestra_taller.wav", audio_grabado.getvalue(), "audio/wav")
            }
            data = {"name": "Voz_Taller_Temporal"}
            
            res_clon = requests.post(url_clon, headers=headers, data=data, files=files)
            
            if res_clon.status_code != 200:
                st.error(f"Error al clonar la voz: {res_clon.text}")
                st.stop()
                
            voice_id = res_clon.json()["voice_id"]

        with st.spinner("Sintetizando nuevo audio en español..."):
            # Endpoint de Text-to-Speech multilingüe
            url_tts = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            payload = {
                "text": texto_objetivo,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": estabilidad,
                    "similarity_boost": similitud
                }
            }
            
            res_tts = requests.post(url_tts, headers=headers, json=payload)
            
            if res_tts.status_code == 200:
                st.success("¡Voz clonada con éxito!")
                st.audio(res_tts.content, format="audio/mp3")
                st.download_button(
                    label="⬇️ Descargar audio",
                    data=res_tts.content,
                    file_name="mi_voz_clonada.mp3",
                    mime="audio/mp3"
                )
            else:
                st.error(f"Error al generar audio: {res_tts.text}")
                
            # Limpieza automática: eliminar la voz temporal para no llenar el límite de la cuenta gratuita
            requests.delete(f"https://api.elevenlabs.io/v1/voices/{voice_id}", headers=headers)
```

---

## 6. Checklist Previo para el Organizador
* **Verificar la red Wi-Fi del lugar:** Asegurar que no haya bloqueos de puertos hacia APIs externas (`api.elevenlabs.io` o `github.com`).
* **Preparar un QR en la primera diapositiva:** Con el enlace directo al repositorio público de GitHub y al registro gratuito de la API para ahorrar 10 minutos de escritura de URLs.
* **Tener un audio WAV pregrabado de respaldo:** Por si el micrófono de alguna laptop del público falla o hay demasiado ruido ambiental en el salón.
* **Limpieza automática de voces:** Mantener la línea `requests.delete(...)` al final del script evita que los asistentes alcancen el límite de voces guardadas de las cuentas gratuitas si hacen muchas pruebas seguidas.