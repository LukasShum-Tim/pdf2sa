import streamlit as st
import pymupdf as fitz  # PyMuPDF
import openai
import tempfile
import sounddevice as sd
import soundfile as sf
import numpy as np
import whisper
from googletrans import Translator

# Initialize models
translator = Translator()
whisper_model = whisper.load_model("base")

st.set_page_config(page_title="PDF to Short Answers with Voice Input", page_icon="🩺")

# --- UI ---
st.title("🩺 PDF → Short Answer Generator with Voice Input")

# --- Language Selection ---
languages = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh-cn": "Chinese (Simplified)",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
}
target_lang = st.selectbox("🌍 Select your language / Seleccione su idioma", list(languages.keys()), index=0)
target_lang_name = languages[target_lang]

# --- PDF Upload ---
uploaded_file = st.file_uploader("📄 Upload a PDF file / Suba un archivo PDF", type=["pdf"])

def extract_pdf_text(file):
    """Extracts text from uploaded PDF file."""
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text")
    return text

# --- Question Generation ---
def generate_questions_from_text(pdf_text, lang_code, lang_name):
    """Generate bilingual short-answer questions using OpenAI."""
    with st.spinner("🧠 Generating questions... / Generando preguntas..."):
        trimmed_text = pdf_text[:4000]  # Limit for speed; consider chunking for longer PDFs
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert medical educator."},
                {"role": "user", "content": f"Create 3 short-answer questions (with answer keys) based on the following text:\n{trimmed_text}"}
            ],
        )
        raw_output = response.choices[0].message.content
        # Simple mock structure for demo; production version should parse structured format
        questions = [{"question_en": q.strip(), "answer_key_en": "Expected answer here"} for q in raw_output.split("\n") if q.strip()]
        
        # Translate each question and answer
        for q in questions:
            q["question_translated"] = translator.translate(q["question_en"], dest=lang_code).text
            q["answer_key_translated"] = translator.translate(q["answer_key_en"], dest=lang_code).text
        return questions

# --- Audio Recording + Transcription ---
def record_audio(duration=10, samplerate=16000):
    """Record audio using sounddevice and save to WAV file."""
    st.info("🎙 Recording... Speak now! / ¡Grabando... hable ahora!")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype="float32")
    sd.wait()
    st.success("✅ Recording complete! / ¡Grabación completa!")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        sf.write(tmpfile.name, audio, samplerate)
        return tmpfile.name

def transcribe_audio(audio_path):
    """Transcribe recorded audio with Whisper."""
    result = whisper_model.transcribe(audio_path)
    return result["text"].strip()

# --- Main Workflow ---
if uploaded_file:
    pdf_text = extract_pdf_text(uploaded_file)
    st.success("✅ PDF uploaded successfully / PDF subido correctamente")

    if st.button(f"🧠 Generate Questions / Generar preguntas"):
        questions = generate_questions_from_text(pdf_text, target_lang, target_lang_name)
        st.session_state["questions"] = questions

# --- Display Generated Questions ---
if "questions" in st.session_state:
    questions = st.session_state["questions"]
    st.subheader(f"📘 Questions / Preguntas ({languages[target_lang]})")

    if "user_answers" not in st.session_state:
        st.session_state["user_answers"] = {}

    progress_bar = st.progress(0)
    total = len(questions)

    for i, q in enumerate(questions):
        st.markdown(f"**Q{i+1}: {q['question_en']}**  \n*{q['question_translated']}*")

        key = f"answer_{i}"
        answer_text = st.text_area(f"📝 Your Answer / Su respuesta ({languages[target_lang]})", key=key)

        # 🎙 Voice input button
        if st.button(f"🎙 Record Answer {i+1} / Grabar respuesta {i+1}"):
            audio_path = record_audio(duration=10)
            transcript = transcribe_audio(audio_path)
            st.session_state["user_answers"][key] = transcript
            st.success(f"🗣 Transcribed: {transcript}")

        st.markdown("---")
        progress_bar.progress((i + 1) / total)

    # Evaluation placeholder (you can link your existing evaluator here)
    if st.button(f"✅ Evaluate My Answers / Evaluar mis respuestas"):
        st.info("✨ Evaluation feature under development / Característica de evaluación en desarrollo")


