import streamlit as st
from io import BytesIO
import pymupdf as fitz  # PyMuPDF
import openai
from googletrans import Translator

# Set your OpenAI API key in your environment
# openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="PDF Question Generator", layout="wide")

translator = Translator()

# -------------------------
# Helper functions
# -------------------------
def translate_text(text, target_lang):
    if target_lang.lower() == "en":
        return text
    try:
        return translator.translate(text, dest=target_lang.lower()).text
    except Exception as e:
        st.warning(f"Translation failed: {e}")
        return text

def extract_pdf_text(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def generate_questions(pdf_text, num_questions):
    prompt = f"""
    Generate {num_questions} high-quality questions based on the following text.
    Provide the question and the model answer for evaluation.
    Output format: JSON with "question" and "answer" keys.
    Text: {pdf_text[:1500]}...
    """
    response = openai.ChatCompletion.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    import json
    try:
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Failed to parse questions: {e}")
        return []

def evaluate_answer(user_answer, model_answer, question, user_lang):
    prompt = f"""
    Evaluate the user's answer to the following question.
    Question: {question}
    Model Answer: {model_answer}
    User Answer: {user_answer}
    Provide a short feedback and the correct answer.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    evaluation_en = response.choices[0].message.content
    evaluation_translated = translate_text(evaluation_en, user_lang)
    return evaluation_en, evaluation_translated

def transcribe_audio(audio_bytes):
    try:
        audio_file = BytesIO(audio_bytes)
        transcription = openai.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )
        return transcription.text
    except Exception as e:
        st.error(f"Transcription failed: {e}")
        return ""

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("Settings / Paramètres")
selected_lang = st.sidebar.selectbox(
    "Select your language / Sélectionnez votre langue",
    ["English", "French", "Spanish", "German", "Chinese", "Arabic"]
)

num_questions = st.sidebar.number_input(
    translate_text("Number of questions / Nombre de questions", selected_lang),
    min_value=1, max_value=10, value=3, step=1
)

# -------------------------
# Main app
# -------------------------
st.title(translate_text("PDF Question Generator", selected_lang))

uploaded_pdf = st.file_uploader(
    translate_text("Upload your PDF file / Téléversez votre fichier PDF", selected_lang),
    type="pdf"
)

if uploaded_pdf:
    pdf_text = extract_pdf_text(uploaded_pdf)
    st.success(translate_text("PDF successfully uploaded and processed!", selected_lang))

    if st.button(translate_text("Generate Questions / Générer des questions", selected_lang)):
        with st.spinner(translate_text("Generating questions...", selected_lang)):
            questions_data = generate_questions(pdf_text, num_questions)

        if questions_data:
            st.session_state["questions_data"] = questions_data
            st.session_state["user_answers"] = [""] * len(questions_data)

# -------------------------
# Display questions & record answers
# -------------------------
if "questions_data" in st.session_state:
    for idx, q in enumerate(st.session_state["questions_data"]):
        question_en = q["question"]
        answer_model = q["answer"]
        question_translated = translate_text(question_en, selected_lang)
        st.subheader(f"Q{idx+1}: {question_en}\n{question_translated}")

        # Textbox for typed answer
        user_input = st.text_area(
            label=translate_text("Your answer / Votre réponse", selected_lang),
            value=st.session_state["user_answers"][idx],
            key=f"user_answer_{idx}"
        )

        st.session_state["user_answers"][idx] = user_input

        # Record & transcribe
        audio_bytes = st.audio_input(
            label=translate_text("Record your answer / Enregistrez votre réponse", selected_lang),
            key=f"audio_input_{idx}"
        )
        if audio_bytes:
            transcription = transcribe_audio(audio_bytes)
            st.session_state["user_answers"][idx] = transcription
            st.text_area(
                label=translate_text("Transcribed answer / Réponse transcrite", selected_lang),
                value=transcription,
                key=f"transcribed_{idx}"
            )

        # Evaluate answer
        if st.button(
            translate_text("Evaluate Answer / Évaluer la réponse", selected_lang),
            key=f"eval_{idx}"
        ):
            eval_en, eval_translated = evaluate_answer(
                st.session_state["user_answers"][idx],
                answer_model,
                question_en,
                selected_lang
            )
            st.markdown(f"**Evaluation (English):** {eval_en}")
            st.markdown(f"**Evaluation ({selected_lang}):** {eval_translated}")
