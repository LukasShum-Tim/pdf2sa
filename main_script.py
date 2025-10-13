# main_script.py
import streamlit as st
import pymupdf as fitz  # PyMuPDF
from googletrans import Translator
import openai
import os

# ------------------ CONFIG ------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
translator = Translator()
GPT_MODEL = "gpt-4-1106-preview"

# ------------------ FUNCTIONS ------------------
def translate(text, dest_lang):
    if dest_lang.lower() == "english":
        return text
    try:
        return translator.translate(text, dest=dest_lang.lower()).text
    except Exception:
        return text  # fallback if translation fails

def extract_pdf_text(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def generate_questions(text, num_questions):
    prompt = (
        f"Generate {num_questions} short answer questions based on the following text:\n\n{text}\n\n"
        "Return each question on a new line."
    )
    response = openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    questions = response.choices[0].message.content.split("\n")
    # clean up empty lines and limit to requested number
    questions = [q.strip() for q in questions if q.strip()][:num_questions]
    return questions

def transcribe_audio(audio_bytes):
    # audio_bytes comes from st.audio_input
    transcript = openai.Audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=audio_bytes
    )["text"]
    return transcript

# ------------------ STREAMLIT APP ------------------
st.set_page_config(page_title="PDF Short Answer Generator", layout="wide")
st.title("PDF Short Answer Generator")

# 1. Select language
langs = ["English", "French", "Spanish", "German", "Chinese"]
selected_lang = st.selectbox("Select language / Sélectionnez la langue", langs)

# 2. Upload PDF
uploaded_pdf = st.file_uploader(translate("Upload your PDF file", selected_lang), type="pdf")
if uploaded_pdf:
    pdf_text = extract_pdf_text(uploaded_pdf)
    
    # 3. Select number of questions
    num_questions = st.number_input(
        translate("Number of questions to generate", selected_lang),
        min_value=1, max_value=20, value=5
    )

    if st.button(translate("Generate Questions", selected_lang)):
        questions_list = generate_questions(pdf_text, num_questions)
        st.session_state['questions_list'] = questions_list
        # Initialize answers in session_state
        for i in range(len(questions_list)):
            st.session_state[f"answer_{i}"] = ""

# 4. Display questions and answer boxes
if 'questions_list' in st.session_state:
    for i, question in enumerate(st.session_state['questions_list']):
        q_text = question if selected_lang == "English" else translate(question, selected_lang)
        st.text_area(f"{translate('Question', selected_lang)} {i+1}", value=q_text, key=f"question_{i}", height=80)
        st.text_area(f"{translate('Your Answer', selected_lang)} {i+1}", key=f"answer_{i}", height=80)

        # Record button
        audio_input = st.audio_input(translate("Record your answer", selected_lang), key=f"record_{i}")
        if audio_input:
            transcript = transcribe_audio(audio_input)
            st.session_state[f"answer_{i}"] = transcript
            st.success(translate("Transcription updated!", selected_lang))

        # Evaluate button (example: just displays the answer for now)
        if st.button(translate("Evaluate Answer", selected_lang), key=f"eval_{i}"):
            st.info(f"{translate('Your Answer', selected_lang)} {i+1}: {st.session_state[f'answer_{i}']}")

