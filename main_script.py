import streamlit as st
from googletrans import Translator
import pymupdf as fitz  # PyMuPDF
import openai
import json
import tempfile
from io import BytesIO

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
        return translator.translate(text, dest=target_lang.lower()).text
    except Exception as e:
        st.warning(f"Translation failed: {e}")
        return text

def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def generate_questions(pdf_text, num_questions):
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
    questions_json = response.choices[0].message.content.strip()
    return questions_json

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
    # Save uploaded audio temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    # Transcribe using OpenAI
    with open(tmp_path, "rb") as f:
        transcript = openai.audio.transcriptions.create(
            file=f,
            model="whisper-1"
        )
    return transcript["text"]

# -------------------- Streamlit UI -------------------- #

st.title("PDF Question Generator & Evaluator")

# Language selection
languages = ["en", "fr", "es", "de", "it", "pt"]
selected_lang = st.selectbox(
    "Select your language / Sélectionnez votre langue", languages, index=0
)

# PDF upload
uploaded_pdf = st.file_uploader(
    translate_text("Upload your PDF file / Téléversez votre fichier PDF", selected_lang),
    type="pdf"
)

num_questions = st.number_input(
    translate_text("Number of questions / Nombre de questions", selected_lang),
    min_value=1, max_value=10, value=1
)

if uploaded_pdf is not None:
    pdf_text = extract_text_from_pdf(uploaded_pdf)

    if st.button(translate_text("Generate Questions / Générer des questions", selected_lang)):
        questions_json = generate_questions(pdf_text, num_questions)
        try:
            questions_data = json.loads(questions_json)
        except Exception as e:
            st.error(f"Failed to parse questions JSON: {e}\nRaw response: {questions_json}")
            st.stop()
        st.session_state['questions'] = questions_data["questions"]

if 'questions' in st.session_state:
    for idx, q in enumerate(st.session_state['questions']):
        st.markdown(f"**Q{idx+1} (EN):** {q['question']}")
        st.markdown(f"**Q{idx+1} ({selected_lang.upper()}):** {translate_text(q['question'], selected_lang)}")

        # Audio recording
        audio_input = st.audio_input(
            f"Record your answer / Enregistrez votre réponse (Q{idx+1})",
            key=f"audio_{idx}"
        )

        # Initialize text area
        if f"answer_{idx}" not in st.session_state:
            st.session_state[f"answer_{idx}"] = ""

        # If audio recorded, transcribe and fill the text box
        if audio_input is not None:
            audio_bytes = audio_input.read()
            transcription = transcribe_audio(audio_bytes)
            st.session_state[f"answer_{idx}"] = transcription

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
            st.markdown(f"**Correct Answer ({selected_lang.upper()}):** {translate_text(q['answer'], selected_lang)}")
