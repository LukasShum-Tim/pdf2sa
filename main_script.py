import streamlit as st
import json
import pymupdf as fitz  # PyMuPDF
from openai import OpenAI
from googletrans import Translator
import time
from io import BytesIO

# -------------------------------
# OPTIONAL: For voice recording in Streamlit
# pip install streamlit-webrtc
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av

# -------------------------------
# INITIALIZATION
# -------------------------------
client = OpenAI()
translator = Translator()

st.set_page_config(
    page_title="📘 Multilingual Short-Answer Trainer",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Multilingual Short-Answer Trainer from PDF")
st.markdown("Upload a PDF, generate short-answer questions, answer in your chosen language, record voice if desired, and get bilingual feedback.")

# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------
if "questions" not in st.session_state:
    st.session_state["questions"] = []

if "user_answers" not in st.session_state:
    st.session_state["user_answers"] = []

if "evaluations" not in st.session_state:
    st.session_state["evaluations"] = []

# -------------------------------
# SAFE TRANSLATION FUNCTION (CACHED)
# -------------------------------
@st.cache_data(show_spinner=False)
def safe_translate(text, target_language_code):
    """Translate text safely with fallback to GPT."""
    if not text or not text.strip():
        return text
    try:
        translated = translator.translate(text, dest=target_language_code)
        if translated and hasattr(translated, "text"):
            return translated.text
    except Exception:
        pass
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"Translate this text into {target_language_code}:\n{text}"}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return text

# -------------------------------
# LANGUAGE SELECTION
# -------------------------------
language_map = {
    "English": "en",
    "French": "fr",
    "Spanish": "es",
    "Portuguese": "pt",
    "German": "de",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Arabic": "ar",
    "Mandarin Chinese": "zh-cn",
}
target_language_name = st.selectbox("🌍 Select your language:", list(language_map.keys()), index=0)
target_lang_code = language_map[target_language_name]

def bilingual_text(en_text):
    """Display English + Translated text together."""
    translated = safe_translate(en_text, target_lang_code)
    return f"{en_text}\n**({target_language_name})**: {translated}"

# -------------------------------
# PDF UPLOAD
# -------------------------------
uploaded_file = st.file_uploader(bilingual_text("📄 Upload a PDF file"), type=["pdf"])

def extract_text_from_pdf(uploaded_file):
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf_doc:
        for page in pdf_doc:
            text += page.get_text("text")
    return text

pdf_text = ""
if uploaded_file:
    pdf_text = extract_text_from_pdf(uploaded_file)
    st.success(bilingual_text("✅ PDF uploaded successfully!"))

# -------------------------------
# QUESTION GENERATION
# -------------------------------
if pdf_text:
    st.subheader(bilingual_text("🧩 Step 1: Generate Short-Answer Questions"))

    num_questions = st.slider(bilingual_text("Number of questions to generate:"), 3, 10, 5)

    if st.button(bilingual_text("⚡ Generate Questions")):
        progress = st.progress(0, text=bilingual_text("Generating questions... please wait"))

        trimmed_text = pdf_text[:4000]
        time.sleep(0.2)
        progress.progress(10, text=bilingual_text("Preparing content..."))

        prompt = f"""
You are an expert medical educator.
Generate {num_questions} concise short-answer questions and their answer keys
based on the following content. Focus on clinically relevant key facts.

Return ONLY JSON in this format:
[
  {{"question": "string", "answer_key": "string"}},
  ...
]

SOURCE TEXT:
{trimmed_text}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            raw = response.choices[0].message.content.strip()
            questions = json.loads(raw)
            progress.progress(40, text=bilingual_text("Translating questions..."))

            bilingual_questions = []
            for i, q in enumerate(questions):
                q_en = q.get("question", "")
                a_en = q.get("answer_key", "")
                q_trans = safe_translate(q_en, target_lang_code)
                a_trans = safe_translate(a_en, target_lang_code)
                bilingual_questions.append({
                    "question_en": q_en,
                    "question_translated": q_trans,
                    "answer_key_en": a_en,
                    "answer_key_translated": a_trans
                })
                progress.progress(40 + int((i+1)/len(questions)*50), text=bilingual_text("Translating..."))

            st.session_state["questions"] = bilingual_questions
            st.session_state["user_answers"] = [""] * len(bilingual_questions)
            progress.progress(100, text=bilingual_text("✅ Done! Questions ready."))
            st.success(bilingual_text(f"Generated {len(bilingual_questions)} bilingual questions successfully!"))

        except Exception as e:
            st.error(bilingual_text(f"⚠️ Question generation failed: {e}"))

# -------------------------------
# USER ANSWERS WITH VOICE
# -------------------------------
if st.session_state["questions"]:
    st.subheader(bilingual_text("🧠 Step 2: Answer the Questions (Type or Speak)"))

    questions = st.session_state["questions"]
    user_answers = st.session_state.get("user_answers", [""] * len(questions))

    # Voice transcription processor
    class AudioProcessor(AudioProcessorBase):
        def __init__(self):
            self.audio_buffer = BytesIO()
        def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
            pcm = frame.to_ndarray()
            self.audio_buffer.write(pcm.tobytes())
            return frame

    for i, q in enumerate(questions):
        st.markdown(f"### Q{i+1}. {q.get('question_en', '')}")
        st.markdown(f"**({target_language_name}):** {q.get('question_translated', '')}")
        label = bilingual_text("✏️ Your Answer:")
        
        # Text input area
        user_answers[i] = st.text_area(label, value=user_answers[i], height=80, key=f"ans_{i}")

        # Voice recorder
        st.markdown("**🎤 Record your answer (optional):**")
        webrtc_ctx = webrtc_streamer(
            key=f"recorder_{i}",
            mode=WebRtcMode.SENDONLY,
            audio_processor_factory=AudioProcessor,
            media_stream_constraints={"audio": True, "video": False},
            async_processing=True
        )

        if webrtc_ctx and webrtc_ctx.audio_receiver:
            audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
            if audio_frames:
                # Concatenate frames into bytes
                audio_bytes = b"".join([f.to_ndarray().tobytes() for f in audio_frames])
                # Transcribe using OpenAI
                try:
                    audio_file = BytesIO(audio_bytes)
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                    # Append or replace text area content
                    user_answers[i] = transcript.text
                    st.success(bilingual_text("🎤 Voice transcribed to text!"))
                except Exception as e:
                    st.error(bilingual_text(f"⚠️ Voice transcription failed: {e}"))

    st.session_state["user_answers"] = user_answers

# -------------------------------
# EVALUATION (UNCHANGED)
# -------------------------------
def score_short_answers(user_answers, questions):
    grading_prompt = f"""
You are an examiner. Score each short-answer response on a 0–2 scale.
Return ONLY JSON:
[
  {{
    "score": 2,
    "feedback": "Good answer.",
    "model_answer": "Key concept here..."
  }},
  ...
]

QUESTIONS AND RESPONSES:
{json.dumps([
    {"question": q.get("question_en", ""), "expected": q.get("answer_key_en", ""), "response": a}
    for q, a in zip(questions, user_answers)
], indent=2)}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": grading_prompt}],
            temperature=0
        )
        results = json.loads(response.choices[0].message.content)
        for r in results:
            r["feedback_translated"] = safe_translate(r.get("feedback", ""), target_lang_code)
            r["model_answer_translated"] = safe_translate(r.get("model_answer", ""), target_lang_code)
        return results
    except Exception as e:
        st.error(bilingual_text(f"⚠️ Scoring failed: {e}"))
        return []

if st.button(bilingual_text("🚀 Evaluate My Answers")):
    with st.spinner(bilingual_text("Evaluating your answers...")):
        results = score_short_answers(user_answers, questions)
        st.session_state['evaluations'] = results
    if results:
        st.success(bilingual_text("✅ Evaluation complete!"))
        with st.expander(bilingual_text("📊 Detailed Feedback")):
            for i, (q, r) in enumerate(zip(questions, results)):
                st.markdown(f"### Q{i+1}: {q.get('question_en', '')}")
                st.markdown(f"**({target_language_name}): {q.get('question_translated', '')}**")
                st.markdown(f"**Score:** {r.get('score', 'N/A')} / 2")
                st.markdown(f"**Feedback (English):** {r.get('feedback', '')}")
                st.markdown(f"**Feedback ({target_language_name}):** {r.get('feedback_translated', '')}")
                st.markdown(f"**Model Answer (English):** {r.get('model_answer', '')}")
                st.markdown(f"**Model Answer ({target_language_name}):** {r.get('model_answer_translated', '')}")
                st.markdown("---")

