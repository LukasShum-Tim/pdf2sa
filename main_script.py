import streamlit as st
import json
import pymupdf as fitz  # PyMuPDF
from openai import OpenAI
from googletrans import Translator

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
def safe_translate(text, target_language_code, fallback_model="gpt-4o-mini"):
    """Translate text robustly with GPT fallback."""
    if not text or not text.strip():
        return text
    try:
        translated = translator.translate(text, dest=target_language_code)
        if translated and hasattr(translated, "text"):
            return translated.text
    except Exception:
        pass
    # Fallback: GPT translation
    try:
        response = client.chat.completions.create(
            model=fallback_model,
            messages=[
                {"role": "user", "content": f"Translate the following text into {target_language_code}:\n\n{text}"}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return text  # Return original if all fails

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
# PDF UPLOAD AND TEXT EXTRACTION
# -------------------------------
uploaded_file = st.file_uploader("📄 Upload a PDF file", type=["pdf"])

def extract_text_from_pdf(uploaded_file):
    """Extract all text from an uploaded PDF."""
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf_doc:
        for page in pdf_doc:
            text += page.get_text("text")
    return text

pdf_text = ""
if uploaded_file:
    pdf_text = extract_text_from_pdf(uploaded_file)
    st.success("✅ PDF uploaded and text extracted successfully!")

# -------------------------------
# QUESTION GENERATION
# -------------------------------
if pdf_text:
    st.subheader("🧩 Step 1: Generate Short-Answer Questions")

    num_questions = st.slider("Number of questions to generate:", 3, 10, 5)

    if st.button("⚡ Generate Questions"):
        with st.spinner("Generating questions from PDF content..."):
            # Translate source text to English for consistent generation
            pdf_text_en = safe_translate(pdf_text, "en")

            # GPT prompt for question generation
            prompt = f"""
You are an expert medical educator.
Generate {num_questions} concise short-answer questions and their answer keys based on the following content.
Focus on clinically relevant concepts, facts, or reasoning.

Return ONLY JSON in the format:
[
  {{"question": "string", "answer_key": "string"}},
  ...
]

SOURCE TEXT:
{pdf_text_en[:6000]}
"""
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                questions = json.loads(response.choices[0].message.content)

                # Add bilingual translation for each question and answer
                bilingual_questions = []
                for q in questions:
                    translated_question = safe_translate(q["question"], target_lang_code)
                    translated_answer = safe_translate(q["answer_key"], target_lang_code)
                    bilingual_questions.append({
                        "question_en": q["question"],
                        "question_translated": translated_question,
                        "answer_key_en": q["answer_key"],
                        "answer_key_translated": translated_answer
                    })

                st.session_state["questions"] = bilingual_questions
                st.success(f"✅ Generated {len(bilingual_questions)} bilingual questions successfully!")

            except Exception as e:
                st.error(f"⚠️ Question generation failed: {e}")

# -------------------------------
# USER ANSWERS INPUT
# -------------------------------
if "questions" in st.session_state:
    st.subheader("🧠 Step 2: Answer the Questions")

    questions = st.session_state["questions"]
    user_answers = []
    for i, q in enumerate(questions):
        st.markdown(f"### Q{i+1}. {q['question_en']}")
        st.markdown(f"**({target_language_name}): {q['question_translated']}**")
        answer = st.text_area(f"Your Answer {i+1} ({target_language_name})", height=80)
        user_answers.append(answer)

    # -------------------------------
    # SCORING FUNCTION
    # -------------------------------
    def score_short_answers(user_answers, questions, target_language_name):
        """Evaluate answers, translate for fairness, then return bilingual feedback."""
        # Translate to English if needed
        if target_language_name != "English":
            translated_user_answers = [safe_translate(ans, "en") for ans in user_answers]
            translated_questions = [
                {"question": q["question_en"], "answer_key": q["answer_key_en"]}
                for q in questions
            ]
        else:
            translated_user_answers = user_answers
            translated_questions = questions

        # GPT evaluation
        grading_prompt = f"""
You are an examiner for the Royal College of Physicians and Surgeons of Canada.
Evaluate each short-answer response on a 0–2 scale (0 = incorrect, 1 = partial, 2 = complete).
Give a short feedback and a concise model answer.

Return ONLY JSON:
[
  {{
    "score": 2,
    "feedback": "Strong answer, clearly identifies priorities.",
    "model_answer": "Assess airway, breathing, circulation, and control hemorrhage."
  }},
  ...
]

QUESTIONS AND RESPONSES:
{json.dumps([
    {"question": q["question_en"], "expected": q["answer_key_en"], "response": a}
    for q, a in zip(translated_questions, translated_user_answers)
], indent=2)}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": grading_prompt}],
                temperature=0
            )
            results = json.loads(response.choices[0].message.content)

            # Translate feedback & model answers back into user language
            for r in results:
                r["feedback_translated"] = safe_translate(r["feedback"], target_lang_code)
                r["model_answer_translated"] = safe_translate(r["model_answer"], target_lang_code)

            return results

        except Exception as e:
            st.error(f"⚠️ Scoring failed: {e}")
            return []

    # -------------------------------
    # EVALUATION
    # -------------------------------
    if st.button("🚀 Evaluate My Answers"):
        with st.spinner("Evaluating answers..."):
            results = score_short_answers(user_answers, questions, target_language_name)
        if results:
            st.success("✅ Evaluation complete!")
            with st.expander("📊 Detailed Feedback"):
                for i, (q, r) in enumerate(zip(questions, results)):
                    st.markdown(f"### Q{i+1}: {q['question_en']}")
                    st.markdown(f"**({target_language_name}): {q['question_translated']}**")
                    st.markdown(f"**Score:** {r['score']} / 2")
                    st.markdown(f"**Feedback (English):** {r['feedback']}")
                    st.markdown(f"**Feedback ({target_language_name}):** {r['feedback_translated']}")
                    st.markdown(f"**Model Answer (English):** {r['model_answer']}")
                    st.markdown(f"**Model Answer ({target_language_name}):** {r['model_answer_translated']}")
                    st.markdown("---")
