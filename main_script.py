import streamlit as st
from googletrans import Translator
import pymupdf as fitz  # PyMuPDF
import openai
import json
import tempfile

# Initialize translator
translator = Translator()

# OpenAI API Key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="PDF Question Generator", layout="wide")

# -------------------- Helper Functions -------------------- #

def translate_text(text, target_lang):
    if target_lang.lower() == "en":
        return text
    try:
        translated = translator.translate(text, dest=target_lang.lower())
        return translated.text
    except Exception as e:
        st.warning(f"Translation failed: {e}")
        return text

def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def generate_questions(pdf_text, num_questions, target_lang="en"):
    prompt = f"""
    Generate {num_questions} high-quality questions based on the following text.
    Return ONLY valid JSON in this exact format:
    {{
        "questions": [
            {{
                "question": "Question text here",
                "answer": "Model answer here"
            }}
        ]
    }}
    Text:
    {pdf_text}
    """
    response = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    raw_json = response.choices[0].message.content.strip()

    # Ensure JSON parsing
    try:
        questions_data = json.loads(raw_json)
    except Exception as e:
        st.error(f"Failed to parse questions JSON: {e}\nRaw response: {raw_json}")
        return []

    # Automatically translate questions to target language
    for q in questions_data["questions"]:
        q["question_local"] = translate_text(q["question"], target_lang)
        q["answer_local"] = translate_text(q["answer"], target_lang)

    return questions_data["questions"]

def evaluate_answer(user_answer, correct_answer):
    prompt = f"""
    Evaluate the user's answer against the correct answer.
    User Answer: {user_answer}
    Correct Answer: {correct_answer}
    Provide a short evaluation and indicate correctness (Correct/Incorrect).
    """
    response = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    evaluation = response.choices[0].message.content.strip()
    return evaluation

def transcribe_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as f:
        transcript = openai.audio.transcriptions.create(
            file=f,
            model="whisper-1"
        )
    return transcript["text"]

# -------------------- Streamlit UI -------------------- #

st.title("PDF Question Generator & Evaluator")

languages = ["en", "fr", "es", "de", "it", "pt"]
selected_lang = st.selectbox(
    "Select your language / Sélectionnez votre langue", languages, index=0
)

uploaded_pdf = st.file_uploader(
    translate_text("Upload your PDF file / Téléversez votre fichier PDF", selected_lang),
    type="pdf"
)

num_questions = st.number_input(
    translate_text("Number of questions / Nombre de questions", selected_lang),
    min_value=1, max_value=10, value=1
)

if uploaded_pdf:
    pdf_text = extract_text_from_pdf(uploaded_pdf)

    if st.button(translate_text("Generate Questions / Générer des questions", selected_lang)):
        questions = generate_questions(pdf_text, num_questions, selected_lang)
        if questions:
            st.session_state['questions'] = questions

if 'questions' in st.session_state:
    for idx, q in enumerate(st.session_state['questions']):
        st.markdown(f"**Q{idx+1} (EN):** {q['question']}")
        st.markdown(f"**Q{idx+1} ({selected_lang.upper()}):** {q['question_local']}")

        # Audio recording
        audio_input = st.audio_input(
            f"Record your answer / Enregistrez votre réponse (Q{idx+1})",
            key=f"audio_{idx}"
        )

        # Initialize text area
        if f"answer_{idx}" not in st.session_state:
            st.session_state[f"answer_{idx}"] = ""

        # Transcribe audio into text box
        if audio_input:
            audio_bytes = audio_input.read()
            st.session_state[f"answer_{idx}"] = transcribe_audio(audio_bytes)

        user_answer = st.text_area(
            f"Your Answer / Votre réponse (Q{idx+1})",
            value=st.session_state[f"answer_{idx}"],
            key=f"answer_area_{idx}"
        )

        if st.button(translate_text("Evaluate Answer / Évaluer la réponse", selected_lang), key=f"eval_{idx}"):
            evaluation_en = evaluate_answer(user_answer, q['answer'])
            evaluation_local = translate_text(evaluation_en, selected_lang)
            st.markdown(f"**Evaluation (EN):** {evaluation_en}")
            st.markdown(f"**Evaluation ({selected_lang.upper()}):** {evaluation_local}")
            st.markdown(f"**Correct Answer (EN):** {q['answer']}")
            st.markdown(f"**Correct Answer ({selected_lang.upper()}):** {q['answer_local']}")
