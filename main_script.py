import streamlit as st
import pymupdf as fitz  # PyMuPDF
import json
import tiktoken
from openai import OpenAI
from googletrans import Translator
from streamlit_webrtc import webrtc_streamer, ClientSettings
import tempfile
import soundfile as sf
import numpy as np

# ----------------- Config -----------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
translator = Translator()

st.set_page_config(page_title="PDF to Short Answer Quiz", layout="centered")
st.title("📄 PDF to Short Answer Quiz App")

# ----------------- Language Selection -----------------
st.markdown("### 🌐 Select Quiz Language")
language_map = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "Ukrainian": "uk",
    "Russian": "ru",
    "German": "de",
    "Polish": "pl",
    "Arabic": "ar",
    "Chinese": "zh-cn",
    "Hindi": "hi"
}
target_language_name = st.selectbox("Translate quiz to:", list(language_map.keys()), index=0)
target_language_code = language_map[target_language_name]

# ----------------- Translation Helper -----------------
def translate_text(text, target_lang):
    if target_lang == "en":
        return text
    try:
        return translator.translate(text, dest=target_lang).text
    except:
        return text

# ----------------- PDF Utilities -----------------
def extract_text_from_pdf(file_obj):
    doc = fitz.open(stream=file_obj.read(), filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def split_text_into_chunks(text, max_tokens=2500):
    enc = tiktoken.get_encoding("cl100k_base")
    words = text.split()
    chunks, current_chunk = [], []
    for word in words:
        current_chunk.append(word)
        tokens = len(enc.encode(" ".join(current_chunk)))
        if tokens >= max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

# ----------------- GPT Short Answer Generation -----------------
def generate_short_answer_questions(text, total_questions=5):
    prompt = f"""
You are a helpful assistant who generates clinically relevant short answer questions
strictly based on the provided text.
Make the questions clinically relevant to medical students/residents, Royal College style.
Do NOT include specific case numbers or vitals.

Generate exactly {total_questions} questions in JSON format:
[
  {{
    "question": "Question text?",
    "answer_key": "Expected answer in English."
  }},
  ...
]

Return only valid JSON.

TEXT:
\"\"\"{text}\"\"\"
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.warning(f"⚠️ GPT question generation failed: {e}")
        return []

# ----------------- Partial Credit Grading -----------------
def score_short_answers(user_answers, questions, lang_code):
    results = []
    for idx, ans in enumerate(user_answers):
        correct = questions[idx]["answer_key_translated"]
        # Partial credit: count fraction of key words present in answer
        correct_words = correct.lower().split()
        ans_words = ans.lower().split()
        matched_words = sum(1 for w in correct_words if w in ans_words)
        score_fraction = matched_words / len(correct_words) if correct_words else 0
        results.append({
            "question_en": questions[idx]["question_en"],
            "question_translated": questions[idx]["question"],
            "answer_key_en": questions[idx]["answer_key_en"],
            "answer_key_translated": questions[idx]["answer_key_translated"],
            "response": ans,
            "score_fraction": score_fraction
        })
    total_score = sum([r["score_fraction"] for r in results])
    return total_score, results

# ----------------- PDF Upload -----------------
uploaded_file = st.file_uploader(translate_text("📤 Upload your PDF file", target_language_code), type=["pdf"])
if uploaded_file:
    st.success(translate_text("✅ PDF uploaded successfully.", target_language_code))
    pdf_text = extract_text_from_pdf(uploaded_file)
    st.session_state["pdf_text"] = pdf_text
    with st.expander(translate_text("🔍 Preview Extracted Text", target_language_code)):
        st.text_area(translate_text("Extracted Text", target_language_code), pdf_text[:1000] + "...", height=300)

    total_questions = st.slider(translate_text("🔢 Number of questions", target_language_code), 1, 20, 5)

    if st.button(translate_text("🧠 Generate Questions", target_language_code)):
        chunks = split_text_into_chunks(pdf_text)
        first_chunk = chunks[0] if chunks else pdf_text
        with st.spinner(translate_text("Generating questions...", target_language_code)):
            questions = generate_short_answer_questions(first_chunk, total_questions)
        if questions:
            for q in questions:
                q["question_en"] = translate_text(q["question"], "en")
                q["answer_key_en"] = translate_text(q["answer_key"], "en")
                q["question"] = translate_text(q["question"], target_language_code)
                q["answer_key_translated"] = translate_text(q["answer_key"], target_language_code)
            st.session_state["questions"] = questions
        else:
            st.error(translate_text("❌ No questions generated.", target_language_code))

# ----------------- Quiz Form -----------------
if st.session_state.get("questions"):
    questions = st.session_state["questions"]
    user_answers = []

    st.header(translate_text("📝 Take the Quiz", target_language_code))
    st.write(translate_text("Answer the following questions:", target_language_code))

    for idx, q in enumerate(questions):
        st.subheader(f"Q{idx+1}: {q['question_en']} / {q['question']}")
        st.markdown(f"**{translate_text('Your answer:', target_language_code)}**")

        # Audio recorder using click-to-record (WebRTC)
        st.write(translate_text("🎤 Click below to record your answer", target_language_code))
        audio_bytes = st.file_uploader(
            translate_text("Upload or record your audio answer (optional)", target_language_code),
            type=["wav", "mp3"],
            key=f"audio_{idx}"
        )
        user_input = st.text_area(
            "",
            key=f"ans_{idx}",
            placeholder=translate_text("Type your answer here...", target_language_code)
        )

        if audio_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
                tmpfile.write(audio_bytes.read())
                tmpfile_path = tmpfile.name
            with open(tmpfile_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=f
                )
            user_input = transcript.text
            st.text_area("", value=user_input, key=f"ans_{idx}_transcribed")

        user_answers.append(user_input)

    if st.button(translate_text("✅ Evaluate My Answers", target_language_code)):
        score, results = score_short_answers(user_answers, questions, target_language_code)
        st.success(f"{translate_text('🎯 Your score', target_language_code)}: {score:.2f} / {len(results)}")
        with st.expander(translate_text("📊 Detailed Feedback", target_language_code)):
            for i, r in enumerate(results):
                st.markdown(f"**Q{i+1}: {r['question_en']} / {r['question_translated']}**")
                st.markdown(f"- ✅ {translate_text('Correct Answer', target_language_code)}: {r['answer_key_en']} / {r['answer_key_translated']}")
                st.markdown(f"- 💬 {translate_text('Your Response', target_language_code)}: {r['response']}")
                st.markdown(f"- {translate_text('Score Fraction', target_language_code)}: {r['score_fraction']:.2f}")
                st.markdown("---")

