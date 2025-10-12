import streamlit as st
import json
import pymupdf as fitz  # PyMuPDF
from openai import OpenAI
from googletrans import Translator
import time

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
st.markdown("Upload a PDF, generate short-answer questions, answer in your language, and get bilingual feedback.")

# -------------------------------
# SAFE TRANSLATION FUNCTION
# -------------------------------
@st.cache_data(show_spinner=False)
def safe_translate(text, target_language_code):
    """Translate text with fallback to GPT."""
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
                {"role": "user", "content": f"Translate this into {target_language_code}:\n{text}"}
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

# -------------------------------
# PDF UPLOAD
# -------------------------------
uploaded_file = st.file_uploader("📄 Upload a PDF file", type=["pdf"])

def extract_text_from_pdf(uploaded_file):
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf_doc:
        for page in pdf_doc:
            text += page.get_text("text")
    return text

pdf_text = ""
if uploaded_file:
    pdf_text = extract_text_from_pdf(uploaded_file)
    st.success("✅ PDF uploaded successfully!")

# -------------------------------
# QUESTION GENERATION
# -------------------------------
if pdf_text:
    st.subheader("🧩 Step 1: Generate Short-Answer Questions")

    num_questions = st.slider("Number of questions to generate:", 3, 10, 5)

    if st.button("⚡ Generate Questions"):
        with st.spinner("Generating questions (this may take up to 30 seconds)..."):
            # Use only first 4000 characters for speed
            trimmed_text = pdf_text[:4000]

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

                bilingual_questions = []
                for q in questions:
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

                st.session_state["questions"] = bilingual_questions
                st.session_state["user_answers"] = [""] * len(bilingual_questions)
                st.success(f"✅ Generated {len(bilingual_questions)} bilingual questions successfully!")

            except Exception as e:
                st.error(f"⚠️ Question generation failed: {e}")

# -------------------------------
# USER ANSWERS
# -------------------------------
if "questions" in st.session_state:
    st.subheader("🧠 Step 2: Answer the Questions")

    questions = st.session_state["questions"]
    user_answers = st.session_state.get("user_answers", [""] * len(questions))

    for i, q in enumerate(questions):
        st.markdown(f"### Q{i+1}. {q.get('question_en', '')}")
        st.markdown(f"**({target_language_name}): {q.get('question_translated', '')}**")
        user_answers[i] = st.text_area(f"Your Answer {i+1}", value=user_answers[i], height=80, key=f"ans_{i}")

    st.session_state["user_answers"] = user_answers

    # -------------------------------
    # EVALUATION
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
            st.error(f"⚠️ Scoring failed: {e}")
            return []

    if st.button("🚀 Evaluate My Answers"):
        with st.spinner("Evaluating answers..."):
            results = score_short_answers(user_answers, questions)
        if results:
            st.success("✅ Evaluation complete!")
            with st.expander("📊 Detailed Feedback"):
                for i, (q, r) in enumerate(zip(questions, results)):
                    st.markdown(f"### Q{i+1}: {q.get('question_en', '')}")
                    st.markdown(f"**({target_language_name}): {q.get('question_translated', '')}**")
                    st.markdown(f"**Score:** {r.get('score', 'N/A')} / 2")
                    st.markdown(f"**Feedback (English):** {r.get('feedback', '')}")
                    st.markdown(f"**Feedback ({target_language_name}):** {r.get('feedback_translated', '')}")
                    st.markdown(f"**Model Answer (English):** {r.get('model_answer', '')}")
                    st.markdown(f"**Model Answer ({target_language_name}):** {r.get('model_answer_translated', '')}")
                    st.markdown("---")
