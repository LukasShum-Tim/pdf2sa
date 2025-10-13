# main_script.py
import streamlit as st
import pymupdf as fitz  # PyMuPDF
from googletrans import Translator
from openai import OpenAI

# Initialize OpenAI client
openai = OpenAI()

# Initialize translator
translator = Translator()

# ------------------------------
# Helper functions
# ------------------------------

def translate(text, dest_lang):
    if dest_lang.lower() == "english":
        return text
    try:
        return translator.translate(text, dest=dest_lang).text
    except:
        return text

def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def generate_questions(text, num_questions):
    prompt = f"Generate {num_questions} short-answer questions from the following text:\n\n{text}"
    response = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}]
    )
    raw_questions = response.choices[0].message.content.strip().split("\n")
    questions_list = [q.strip() for q in raw_questions if q.strip()]
    return questions_list[:num_questions]  # ensure exact number

def transcribe_audio(audio_data):
    if audio_data is None:
        return ""
    response = openai.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=audio_data
    )
    return response["text"]

# ------------------------------
# Streamlit App
# ------------------------------

st.title("PDF to Short Answer Question Generator / Générateur de questions à réponse courte à partir de PDF")

# Language selection
languages = ["English", "French", "Spanish", "German", "Italian"]
selected_lang = st.selectbox("Select Language / Choisir la langue", languages)

# Upload PDF
uploaded_pdf = st.file_uploader(
    translate("Upload your PDF file", selected_lang), type="pdf"
)

# Number of questions
num_questions = st.number_input(
    translate("Number of Questions / Nombre de questions", selected_lang),
    min_value=1, max_value=10, value=3, step=1
)

# Generate questions button
if uploaded_pdf and st.button(translate("Generate Questions / Générer des questions", selected_lang)):
    pdf_text = extract_text_from_pdf(uploaded_pdf)
    questions_list = generate_questions(pdf_text, num_questions)

    # Translate questions if necessary
    if selected_lang.lower() != "english":
        questions_list = [translate(q, selected_lang) for q in questions_list]

    st.session_state["questions"] = questions_list
    st.session_state["answers"] = [""] * len(questions_list)

# Display questions with textareas and record buttons
if "questions" in st.session_state:
    for i, q in enumerate(st.session_state["questions"]):
        st.markdown(f"**{translate('Question', selected_lang)} {i+1}:** {q}")
        
        # Answer textarea
        st.text_area(
            translate("Your Answer / Votre réponse", selected_lang),
            key=f"answer_{i}",
            value=st.session_state["answers"][i]
        )
        
        # Audio recorder
        audio_data = st.audio_input(
            translate("Record your answer / Enregistrez votre réponse", selected_lang),
            key=f"audio_{i}"
        )
        
        # Transcribe audio and update textarea
        if st.button(translate("Transcribe / Transcrire", selected_lang), key=f"transcribe_{i}"):
            transcript = transcribe_audio(audio_data)
            st.session_state[f"answer_{i}"] = transcript
            st.session_state["answers"][i] = transcript
            st.success(translate("Transcription complete / Transcription terminée", selected_lang))
        
        # Evaluate answer button (example placeholder)
        if st.button(translate("Evaluate Answer / Évaluer la réponse", selected_lang), key=f"eval_{i}"):
            st.info(translate("Evaluation not yet implemented / Évaluation non encore implémentée", selected_lang))


