import streamlit as st
import pymupdf as fitz  # PyMuPDF
import json
import tiktoken
from openai import OpenAI
from googletrans import Translator
import tempfile
import soundfile as sf

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

# Translation helper
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

# ----------------- Quiz Evaluation -----------------
def score_short_answers(user_answers, questions):
    results = []
    for idx, ans in enumerate(user_answers):
        correct_en = questions[idx]["answer_key_en"]
        correct_translated = questions[idx]["answer_key"]
        # For simplicity, mark correct if answer matches English key substring-insensitive
        is_correct = correct_en.strip().lower() in ans.strip().lower()
        results.append({
            "question_en": questions[idx]["question_en"],
            "question_translated": questions[idx]["question"],
            "answer_key_en": correct_en,
            "answer_key_translated": correct_translated,
            "response": ans,
            "is_correct": is_correct
        })
    score = sum([r["is_correct"] for r in results])
    return score, results

# ----------------- PDF Upload -----------------
uploaded_file = st.file_uploader("📤 Upload your PDF file", type=["pdf"])
if uploaded_file:
    st.success("✅ PDF uploaded successfully.")
    pdf_text = extract_text_from_pdf(uploaded_file)
    st.session_state["pdf_text"] = pdf_text
    with st.expander("🔍 Preview Extracted Text"):
        st.text_area("Extracted Text", pdf_text[:1000] + "...", height=300)

    total_questions = st.slider("🔢 Number of questions", 1, 20, 5)

    if st.button("🧠 Generate Questions"):
        chunks = split_text_into_chunks(pdf_text)
        first_chunk = chunks[0] if chunks else pdf_text
        with st.spinner("Generating questions..."):
            questions = generate_short_answer_questions(first_chunk, total_questions)
        if questions:
            # Add English translations for evaluation
            for q in questions:
                q["question_en"] = translate_text(q["question"], "en")
                q["answer_key_en"] = translate_text(q["answer_key"], "en")
            st.session_state["questions"] = questions
        else:
            st.error("❌ No questions generated.")

# ----------------- Quiz Form -----------------
if st.session_state.get("questions"):
    questions = st.session_state["questions"]
    user_answers = []

    st.header("📝 Take the Quiz")
    st.write(translate_text("Answer the following questions:", target_language_code))

    for idx, q in enumerate(questions):
        st.subheader(f"Q{idx+1}: {q['question_en']} / {q['question']}")
        st.markdown(f"**{translate_text('Your answer:', target_language_code)}**")

        # Audio file upload for cloud compatibility
        audio_file = st.file_uploader(
            translate_text("🎤 Upload your answer as a .wav file (optional)", target_language_code),
            type=["wav"],
            key=f"audio_{idx}"
        )

        user_input = st.text_area(
            "",
            key=f"ans_{idx}",
            placeholder=translate_text("Type your answer here...", target_language_code)
        )

        # If audio file uploaded, transcribe with Whisper
        if audio_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
                tmpfile.write(audio_file.read())
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
        score, results = score_short_answers(user_answers, questions)
        st.success(f"🎯 {translate_text('Your score', target_language_code)}: {score} / {len(results)}")
        with st.expander(translate_text("📊 Detailed Feedback", target_language_code)):
            for i, r in enumerate(results):
                st.markdown(f"**Q{i+1}: {r['question_en']} / {r['question_translated']}**")
                st.markdown(f"- ✅ {translate_text('Correct Answer', target_language_code)}: {r['answer_key_en']} / {r['answer_key_translated']}")
                st.markdown(f"- 💬 {translate_text('Your Response', target_language_code)}: {r['response']}")
                st.markdown(f"- {translate_text('Correct?', target_language_code)}: {r['is_correct']}")
                st.markdown("---")

