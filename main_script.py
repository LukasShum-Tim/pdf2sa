import streamlit as st
import pymupdf as fitz  # PyMuPDF
import openai
import json
import re
from googletrans import Translator

# ------------------ Configuration ------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

translator = Translator()

# ------------------ Helpers ------------------
def translate_text(text, target_lang):
    if target_lang.lower() == "en":
        return text
    try:
        return translator.translate(text, dest=target_lang.lower()).text
    except Exception as e:
        st.warning(f"Translation failed: {e}")
        return text

def parse_questions_json(model_output):
    """Safely extract JSON array from model output"""
    match = re.search(r'\[\s*{.*}\s*\]', model_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            return []
    return []

def extract_pdf_text(pdf_file):
    text = ""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    for page in doc:
        text += page.get_text()
    return text

def generate_questions(pdf_text, num_questions):
    prompt = f"""
    Generate {num_questions} multiple-choice questions based on the following text.
    Format your output strictly as JSON, each question with fields: "question", "options" (list), "answer" (single correct option).
    Text:
    {pdf_text}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    model_output = response.choices[0].message.content
    questions = parse_questions_json(model_output)
    return questions

def evaluate_answer(user_answer, correct_answer, lang):
    prompt = f"""
    Evaluate the user's answer and return 'Correct' or 'Incorrect'.
    User answer: {user_answer}
    Correct answer: {correct_answer}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    evaluation = response.choices[0].message.content.strip()
    evaluation_translated = translate_text(evaluation, lang)
    return evaluation, evaluation_translated

# ------------------ Streamlit UI ------------------
st.title("📄 PDF Quiz Generator with Audio & Translation")

# Language selection
langs = {"English": "en", "French": "fr", "Spanish": "es", "German": "de"}
selected_lang = st.selectbox("Select your language / Sélectionnez votre langue", list(langs.keys()))
lang_code = langs[selected_lang]

# PDF upload
uploaded_pdf = st.file_uploader(
    translate_text("Upload your PDF file / Téléversez votre fichier PDF", lang_code), type="pdf"
)

if uploaded_pdf:
    pdf_text = extract_pdf_text(uploaded_pdf)
    st.success(translate_text("PDF successfully loaded!", lang_code))

    # Number of questions
    num_questions = st.number_input(
        translate_text("Number of questions / Nombre de questions", lang_code),
        min_value=1, max_value=10, value=1, step=1
    )

    if st.button(translate_text("Generate Questions / Générer les questions", lang_code)):
        questions_data = generate_questions(pdf_text, num_questions)
        if not questions_data:
            st.error(translate_text("Failed to generate questions. Please try again.", lang_code))
        else:
            # Store questions and answers in session
            st.session_state.questions = questions_data
            st.session_state.user_answers = [""] * len(questions_data)
            st.session_state.evaluations = [""] * len(questions_data)

# Display questions
if "questions" in st.session_state:
    for idx, q in enumerate(st.session_state.questions):
        st.markdown(f"**Q{idx+1} / {translate_text(f'Question {idx+1}', lang_code)}:** {q['question']}")
        st.write(f"Options: {', '.join(q['options'])}")

        # Textbox for user answer
        user_input = st.text_input(
            translate_text("Your answer / Votre réponse", lang_code),
            key=f"user_answer_{idx}"
        )
        st.session_state.user_answers[idx] = user_input

        # Audio recording
        audio_bytes = st.audio_input(
            translate_text("Record your answer / Enregistrez votre réponse", lang_code),
            key=f"audio_{idx}"
        )
        if audio_bytes:
            st.session_state.user_answers[idx] += f" {audio_bytes.decode('utf-8', errors='ignore')}"

        # Evaluate button
        if st.button(translate_text("Evaluate Answer / Évaluer la réponse", lang_code), key=f"eval_{idx}"):
            correct_answer = q["answer"]
            eval_en, eval_translated = evaluate_answer(user_input, correct_answer, lang_code)
            st.session_state.evaluations[idx] = f"English: {eval_en} | {selected_lang}: {eval_translated}"
            st.success(st.session_state.evaluations[idx])

