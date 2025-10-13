# main_script.py
import streamlit as st
import pymupdf as fitz  # PyMuPDF
import json
import tempfile
import os
from typing import List, Dict, Any

# Local audiorecorder (you added the folder to the repo)
from audiorecorder import audiorecorder

# OpenAI client (ensure OPENAI_API_KEY in Streamlit secrets)
from openai import OpenAI
from googletrans import Translator

# ----------------------------
# Config / Initialization
# ----------------------------
st.set_page_config(page_title="📄 PDF → Short Answer Trainer", layout="wide")
st.title("📄 PDF → Short Answer Trainer (Bilingual + Voice)")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
translator = Translator()

# Language map shown to user (display name -> code)
LANG_MAP = {
    "English": "en",
    "French": "fr",
    "Spanish": "es",
    "Portuguese": "pt",
    "German": "de",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Arabic": "ar",
    "Chinese (Simplified)": "zh-cn",
    "Hindi": "hi",
}

# ----------------------------
# Helpers: translation + safe wrappers
# ----------------------------
@st.cache_data(show_spinner=False)
def cached_translate(text: str, target_lang_code: str) -> str:
    """Translate using googletrans with caching and fail-safe fallback to original text."""
    if not text:
        return text
    if target_lang_code == "en":
        return text
    try:
        res = translator.translate(text, dest=target_lang_code)
        # googletrans returns attribute 'text'
        return getattr(res, "text", str(res))
    except Exception:
        return text

def bilingual(en_text: str, target_lang_code: str) -> str:
    """Return combined English + translated line for UI labels."""
    trans = cached_translate(en_text, target_lang_code)
    if target_lang_code == "en":
        return en_text
    # show English then translated in parentheses
    return f"{en_text} ({trans})"

def write_exception(e: Exception):
    st.error("An internal error occurred. See logs for details.")
    st.exception(e)

# ----------------------------
# PDF helpers
# ----------------------------
def extract_text_from_pdf_bytes(bytes_io) -> str:
    with fitz.open(stream=bytes_io.read(), filetype="pdf") as doc:
        pages = [p.get_text("text") for p in doc]
    return "\n".join(pages)

def chunk_text_simple(text: str, max_chars: int = 4000) -> List[str]:
    """Simple char-based chunking (fast and robust)."""
    chunks = []
    i = 0
    L = len(text)
    while i < L:
        chunks.append(text[i:i+max_chars])
        i += max_chars
    return chunks

# ----------------------------
# GPT: question generation
# ----------------------------
def generate_questions_from_text(text: str, n: int = 5) -> List[Dict[str,str]]:
    """
    Ask the model to return a JSON array of objects:
      [{"question":"...","answer_key":"..."} ...]
    All in English (we'll translate later).
    """
    prompt = f"""
You are an expert medical educator. Based only on the text below, generate exactly {n} concise short-answer questions
(targeted to medical trainees, Royal College style) and a one-sentence model answer for each.
Return ONLY valid JSON in this exact format:

[
  {{"question": "Question text in English", "answer_key": "Concise model answer in English"}},
  ...
]

TEXT:
\"\"\"{text}\"\"\"
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[{"role":"user","content":prompt}],
            temperature=0.3
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        # Validate and normalize
        out = []
        for item in data:
            q = item.get("question", "").strip()
            a = item.get("answer_key", "").strip()
            if q and a:
                out.append({"question_en": q, "answer_key_en": a})
        return out
    except Exception as e:
        write_exception(e)
        return []

# ----------------------------
# Transcription via OpenAI hosted Whisper
# ----------------------------
def transcribe_audio_file_to_text(filepath: str) -> str:
    """Send audio file to OpenAI transcription endpoint and return text."""
    try:
        with open(filepath, "rb") as f:
            resp = client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=f)
        # response shape may vary; try common fields
        text = getattr(resp, "text", None)
        if text is None:
            # If dict-like
            try:
                text = resp.get("text", "")
            except Exception:
                text = str(resp)
        return text.strip() if text else ""
    except Exception as e:
        write_exception(e)
        return ""

# ----------------------------
# Grading with partial credit + GPT feedback
# ----------------------------
def compute_partial_score(user_text: str, model_answer_translated: str) -> float:
    """Simple partial credit: fraction of model-answer tokens present in user answer."""
    def tokens(s: str):
        return [t.strip(".,;:()[]{}\"'").lower() for t in s.split() if t.strip()]
    key = set(tokens(model_answer_translated))
    ans = set(tokens(user_text))
    if not key:
        return 0.0
    matched = len(key & ans)
    return matched / len(key)

def ask_gpt_feedback(expected_en: str, user_answer_target: str, target_lang_code: str) -> Dict[str,str]:
    """
    Ask GPT to produce a short English feedback + model answer; return both English and translated versions.
    Return: {"feedback_en": "...", "model_en":"...", "feedback_translated":"...", "model_translated":"..."}
    """
    prompt = f"""
You are an examiner. Provide:
1) A single-sentence assessment of the student's answer (English).
2) A concise one-sentence model answer (English).

Model answer (English): "{expected_en}"
Student answer (in language code {target_lang_code}): "{user_answer_target}"

Return JSON:
{{"feedback_en":"...", "model_answer_en":"..."}}"""
    
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[{"role":"user","content":prompt}],
            temperature=0
        )
        parsed = json.loads(resp.choices[0].message.content)
        feedback_en = parsed.get("feedback_en","")
        model_en = parsed.get("model_answer_en","")
    except Exception:
        feedback_en = ""
        model_en = expected_en
    # translate both back to target language
    feedback_translated = cached_translate(feedback_en, target_lang_code)
    model_translated = cached_translate(model_en, target_lang_code)
    return {
        "feedback_en": feedback_en,
        "model_en": model_en,
        "feedback_translated": feedback_translated,
        "model_translated": model_translated
    }

# ----------------------------
# UI: Sidebar language selection & settings
# ----------------------------
st.sidebar.header("Settings")
selected_display = st.sidebar.selectbox("Select language / Sélectionnez la langue", list(LANG_MAP.keys()), index=0)
target_code = LANG_MAP[selected_display]

# Provide helpful short bilingual helper
def ui_text(en: str) -> str:
    return bilingual(en, target_code)

# ----------------------------
# Step 1: Upload PDF & generate questions
# ----------------------------
st.header(ui_text("1) Upload PDF and generate questions"))
pdf_file = st.file_uploader(ui_text("Upload PDF (PDF only)"), type=["pdf"])

if pdf_file:
    st.success(ui_text("PDF uploaded successfully"))
    if st.checkbox(ui_text("Preview extracted text (show/hide)")):
        extracted = extract_text_from_pdf_bytes(pdf_file)
        st.text_area(ui_text("Extracted Text (preview)"), extracted[:8000], height=300)

    num_q = st.slider(ui_text("Number of questions to generate"), 1, 20, 5)

    if st.button(ui_text("Generate questions")):
        with st.spinner(ui_text("Generating questions — this may take a moment...")):
            # use truncated chunk for speed
            full_text = extract_text_from_pdf_bytes(pdf_file)
            chunks = chunk_text_simple(full_text, max_chars=5000)
            first_chunk = chunks[0] if chunks else full_text
            questions = generate_questions_from_text(first_chunk, n=num_q)
            if not questions:
                st.error(ui_text("Failed to generate questions. Try a shorter document or reduce number."))
            else:
                # translate question & answers to user language and store bilingual fields
                for q in questions:
                    q["question_translated"] = cached_translate(q["question_en"], target_code)
                    q["answer_key_translated"] = cached_translate(q["answer_key_en"], target_code)
                st.session_state["questions"] = questions
                # initialize user answers array
                st.session_state["user_answers"] = [""] * len(questions)
                st.success(ui_text("Questions generated and translated."))

# ----------------------------
# Step 2: Answer questions (click-to-record + editable textbox)
# ----------------------------
if st.session_state.get("questions"):
    st.header(ui_text("2) Answer the questions"))
    questions = st.session_state["questions"]

    # iterate questions
    for i, q in enumerate(questions):
        st.subheader(f"{ui_text(f'Q{i+1} (English)')}: {q['question_en']}")
        st.markdown(f"**{ui_text(f'({selected_display}):')}** {q['question_translated']}")

        st.write(ui_text("You can either type your answer below or record your voice using the Record button. Recorded audio is transcribed and placed into the textbox for editing."))

        # --- Record in browser with local audiorecorder component ---
        # audiorecorder returns audio bytes-like object (or empty bytes when not used)
        rec_label = ui_text("Record answer (click Record → Stop)")
        audio_bytes = audiorecorder(rec_label, ui_text("Stop"))

        # Text area for editable answer (persist in session_state)
        key_txt = f"user_answer_{i}"
        if "user_answers" not in st.session_state:
            st.session_state["user_answers"] = [""] * len(questions)
        # If there's already a value (from previous transcription or typing), keep it
        default_text = st.session_state["user_answers"][i] or ""
        typed = st.text_area(ui_text("Your answer (editable)"), value=default_text, key=key_txt, height=140)

        # If recorder returned audio, save, transcribe, and populate textbox
        if audio_bytes and len(audio_bytes) > 0:
            try:
                # audio_bytes might be bytes or bytearray. Write to temp file directly.
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                    # Write bytes directly
                    if isinstance(audio_bytes, (bytes, bytearray)):
                        tmp.write(audio_bytes)
                    else:
                        # Some audiorecorder implementations return numpy array or object with tobytes()
                        try:
                            tmp.write(audio_bytes.tobytes())
                        except Exception:
                            # fallback: convert to str and write (rare)
                            tmp.write(bytes(audio_bytes))
                st.info(ui_text("Transcribing audio..."))
                transcript = transcribe_audio_file_to_text(tmp_path)
                if transcript:
                    st.session_state["user_answers"][i] = transcript
                    st.success(ui_text("Transcription complete — you can edit the text below."))
                    # update the text area by re-rendering (can't directly set value prop; use another area to show)
                    st.experimental_rerun()
                else:
                    st.warning(ui_text("No transcription produced. Please try again or type your answer."))
            except Exception as e:
                write_exception(e)

        else:
            # store typed answer into session state
            st.session_state["user_answers"][i] = typed

    # ----------------------------
    # Evaluation button and scoring
    # ----------------------------
    if st.button(ui_text("Evaluate my answers")):
        with st.spinner(ui_text("Scoring answers and generating feedback...")):
            user_answers = st.session_state.get("user_answers", [""] * len(questions))
            total_score, detailed = grade_answers(user_answers, questions, target_code)
            # show score
            st.success(ui_text(f"Scoring complete. Total score (sum of fractions): {round(total_score, 2)}"))
            # Show detailed feedback per question
            for idx, res in enumerate(detailed):
                st.markdown(f"### {ui_text('Q')} {idx+1}: {res['question_translated']}")
                st.markdown(f"- **{ui_text('Model answer')}:** {res['answer_key_translated']}  /  {res['answer_key_en']}")
                st.markdown(f"- **{ui_text('Your response')}:** {res['response']}")
                st.markdown(f"- **{ui_text('Partial score')}:** {res['score_fraction']:.2f}")
                if res.get("feedback_translated"):
                    st.markdown(f"- **{ui_text('Feedback')}:** {res['feedback_translated']}")
                st.markdown("---")


