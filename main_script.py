'''import streamlit as st
import pymupdf as fitz
import openai
from openai import OpenAI
import os
import tiktoken
import json
from googletrans import Translator

# ------------------ Initialization ------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
translator = Translator()

# ------------------ PDF Utilities ------------------

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

# ------------------ GPT Short Answer Generation ------------------

def generate_short_answer_questions(text, total_questions=5):
    prompt = f"""
You are an expert medical educator creating *short-answer exam questions* in the style of the Royal College of Physicians and Surgeons of Canada (RCPSC).

Your task:
- Write exactly {total_questions} short-answer clinical questions based strictly on the provided text.
- Focus on *conceptual understanding, management steps, clinical reasoning,* or *interpretation of findings.*
- Focus on asking the surgical steps for anatomic exposure.
- Avoid simple factual recall.
- For each question, include the expected key points of the correct answer for scoring.

Return the output in **valid JSON** format, as follows:

[
  {{
    "question": "Describe the initial management steps in a patient presenting with hemorrhagic shock.",
    "answer_key": "Airway management, control of external bleeding, rapid IV access with crystalloids, initiate blood transfusion protocol, identify source of bleeding, monitor vitals."
  }},
  ...
]

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

# ------------------ Translation ------------------

def translate_questions(questions, language):
    if language == "English":
        return questions
    prompt = f"""
Translate the following short-answer questions and answer keys into {language}, preserving the JSON structure:

{json.dumps(questions, indent=2)}

Return only valid JSON.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.warning(f"⚠️ GPT translation failed: {e}")
        st.info("🔁 Falling back to Google Translate...")
        try:
            translated_questions = []
            for q in questions:
                translated_questions.append({
                    "question": translator.translate(q["question"], dest=language).text,
                    "answer_key": translator.translate(q["answer_key"], dest=language).text
                })
            return translated_questions
        except Exception as ge:
            st.error(f"❌ Google Translate failed: {ge}")
            return questions

# ------------------ AI Scoring ------------------

def score_short_answers(user_answers, questions):
    prompt = f"""
You are an examiner grading Royal College short-answer questions. 
Grade each response on a 0–1 scale (1 = correct, 0 = incorrect), and provide brief feedback.

Return JSON in the form:
[
  {{
    "score": 1,
    "feedback": "Good answer, includes all key steps."
  }},
  ...
]

QUESTIONS AND ANSWERS:
{json.dumps([{"question": q["question"], "expected": q["answer_key"], "response": a} for q,a in zip(questions, user_answers)], indent=2)}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"⚠️ Scoring failed: {e}")
        return [{"score": 0, "feedback": "Error during scoring"} for _ in questions]

# ------------------ Streamlit Interface ------------------

st.set_page_config(page_title="PDF to Short Answer Exam", layout="centered")
st.title("📘 PDF to Short-Answer Question Exam")

# Language selector
st.markdown("### 🌐 Select Exam Language")
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
language_options = list(language_map.keys())
target_language_name = st.selectbox("Translate exam to:", language_options, index=0)
target_language_code = language_map[target_language_name]

# File upload
uploaded_file = st.file_uploader("📤 Upload your PDF file", type=["pdf"])

if uploaded_file:
    st.success("✅ PDF uploaded successfully.")
    extracted_text = extract_text_from_pdf(uploaded_file)
    st.session_state["extracted_text"] = extracted_text

    with st.expander("🔍 Preview Extracted Text"):
        st.text_area("Extracted Text", extracted_text[:1000] + "...", height=300)

    total_questions = st.slider("🔢 Number of questions to generate", 1, 20, 5)

    if st.button("🧠 Generate Short-Answer Exam"):
        chunks = split_text_into_chunks(extracted_text)
        first_chunk = chunks[0] if chunks else extracted_text

        with st.spinner("Generating questions..."):
            questions = generate_short_answer_questions(first_chunk, total_questions)
            st.session_state["questions_original"] = questions

        if questions:
            with st.spinner(f"Translating to {target_language_name}..."):
                translated_questions = translate_questions(questions, target_language_code)
                st.session_state["questions_translated"] = translated_questions
        else:
            st.error("❌ No questions generated.")

# Quiz form
if st.session_state.get("questions_translated"):
    questions = st.session_state["questions_translated"]
    original_questions = st.session_state["questions_original"]
    user_answers = []

    with st.form("saq_form"):
        st.header("📝 Answer the Questions")

        for idx, q in enumerate(questions):
            st.subheader(f"Q{idx + 1}: {q['question']}")
            answer_text = st.text_area("Your answer:", key=f"ans_{idx}", height=100)
            user_answers.append(answer_text)
            st.markdown("---")

        submitted = st.form_submit_button("✅ Submit Exam")

    if submitted:
        with st.spinner("Grading your responses..."):
            results = score_short_answers(user_answers, original_questions)
            total_score = sum(r["score"] for r in results)
            st.success(f"🎯 You scored {total_score:.1f} out of {len(results)}")

        with st.expander("📊 Detailed Feedback"):
            for i, (q, r) in enumerate(zip(original_questions, results)):
                st.markdown(f"**Q{i+1}: {q['question']}**")
                st.markdown(f"**Expected answer:** {q['answer_key']}")
                st.markdown(f"**Your score:** {r['score']}")
                st.markdown(f"**Feedback:** {r['feedback']}")
                st.markdown("---")
'''

import streamlit as st
import json
import fitz  # PyMuPDF
from googletrans import Translator
from openai import OpenAI

# -------------------------------
# INITIALIZATION
# -------------------------------
client = OpenAI()
translator = Translator()

st.set_page_config(
    page_title="📘 Multilingual PDF Short-Answer Trainer",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Multilingual Short-Answer Trainer from PDF")
st.markdown("Upload a PDF, generate short-answer questions, answer in your language, and get bilingual feedback.")

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
            # Translate source text to English for consistent question generation
            pdf_text_en = pdf_text
            if target_language_name != "English":
                pdf_text_en = translator.translate(pdf_text, dest="en").text

            # Generate questions using GPT
            prompt = f"""
You are an expert medical educator.
Generate {num_questions} concise short-answer questions and their answer keys based on the following content.
Focus on clinically relevant concepts, facts, or reasoning.

Return ONLY JSON in the following format:
[
  {{"question": "string", "answer_key": "string"}},
  ...
]

SOURCE TEXT:
{pdf_text_en[:6000]}  # limit to avoid excessive prompt size
"""
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                questions = json.loads(response.choices[0].message.content)
                st.session_state["questions"] = questions
                st.success(f"✅ Generated {len(questions)} questions successfully!")
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
        st.markdown(f"**Q{i+1}. {q['question']}**")
        answer = st.text_area(f"Your Answer {i+1} ({target_language_name})", height=80)
        user_answers.append(answer)

    # -------------------------------
    # SCORING FUNCTION
    # -------------------------------
    def score_short_answers(user_answers, questions, target_language_name):
        """Evaluate answers, translate for fairness, then return bilingual feedback."""
        # Translate to English if needed
        if target_language_name != "English":
            translated_user_answers = [translator.translate(ans, dest="en").text for ans in user_answers]
            translated_questions = [
                {
                    "question": q["question"],
                    "answer_key": translator.translate(q["answer_key"], dest="en").text
                } for q in questions
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
    {"question": q["question"], "expected": q["answer_key"], "response": a}
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
            if target_language_name != "English":
                for r in results:
                    r["feedback_translated"] = translator.translate(r["feedback"], dest=language_map[target_language_name]).text
                    r["model_answer_translated"] = translator.translate(r["model_answer"], dest=language_map[target_language_name]).text
            else:
                for r in results:
                    r["feedback_translated"] = r["feedback"]
                    r["model_answer_translated"] = r["model_answer"]

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
                    st.markdown(f"### Q{i+1}: {q['question']}")
                    st.markdown(f"**Score:** {r['score']} / 2")
                    st.markdown(f"**Feedback (English):** {r['feedback']}")
                    st.markdown(f"**Feedback ({target_language_name}):** {r['feedback_translated']}")
                    st.markdown(f"**Model Answer (English):** {r['model_answer']}")
                    st.markdown(f"**Model Answer ({target_language_name}):** {r['model_answer_translated']}")
                    st.markdown("---")
