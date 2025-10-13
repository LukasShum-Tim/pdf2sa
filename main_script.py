import streamlit as st
import pymupdf as fitz  # PyMuPDF
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from googletrans import Translator
import openai
import tempfile

# -----------------------------
# App Config
# -----------------------------
st.set_page_config(page_title="PDF Question Generator", layout="wide")

# -----------------------------
# Language Selection
# -----------------------------
languages = ["English", "French", "Spanish", "German"]  # extend as needed
selected_lang = st.selectbox("Select your language / Sélectionnez la langue", languages)

translator = Translator()
def translate(text):
    if selected_lang != "English":
        return translator.translate(text, dest=selected_lang.lower()).text
    return text

# -----------------------------
# PDF Upload
# -----------------------------
uploaded_pdf = st.file_uploader(translate("Upload your PDF file / Téléversez votre fichier PDF"), type="pdf")
pdf_text = ""
if uploaded_pdf:
    doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
    for page in doc:
        pdf_text += page.get_text()
    st.success(translate("PDF successfully loaded!"))

# -----------------------------
# Number of Questions
# -----------------------------
num_questions = st.number_input(
    translate("Number of questions / Nombre de questions"),
    min_value=1, max_value=20, value=5, step=1
)

# -----------------------------
# Generate Questions Button
# -----------------------------
if st.button(translate("Generate Questions / Générer des questions")) and pdf_text:
    st.session_state.questions = []
    
    prompt_template = PromptTemplate(
        input_variables=["text", "num_questions"],
        template="Generate {num_questions} questions from the following text:\n{text}"
    )
    
    llm = ChatOpenAI(temperature=0)
    chain = LLMChain(llm=llm, prompt=prompt_template)
    
    questions_text = chain.run(text=pdf_text, num_questions=num_questions)
    questions_list = questions_text.split("\n")  # assuming each question is on a new line
    st.session_state.questions = [q.strip() for q in questions_list if q.strip()]

# -----------------------------
# Display Questions
# -----------------------------
if 'questions' in st.session_state:
    st.session_state.answers = {}
    for i, question in enumerate(st.session_state.questions):
        st.markdown(f"**Q{i+1}: {question}**")
        # Text input
        text_input = st.text_area(translate("Type your answer here / Tapez votre réponse ici"), key=f"text_{i}")
        # Audio input
        audio_input = st.audio_input(translate("Or record your answer / Ou enregistrez votre réponse"), key=f"audio_{i}")
        
        # Transcribe if audio is recorded
        if audio_input:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
                tmpfile.write(audio_input.getbuffer())
                audio_file_path = tmpfile.name
            transcription = openai.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=open(audio_file_path, "rb")
            )
            text_input = transcription.text
        
        st.session_state.answers[i] = text_input

    # -----------------------------
    # Evaluate Answers Button
    # -----------------------------
    if st.button(translate("Evaluate Answers / Évaluer les réponses")):
        st.session_state.evaluation = {}
        for i, answer in st.session_state.answers.items():
            st.session_state.evaluation[i] = f"Answer recorded: {answer}"  # Placeholder for actual evaluation
            st.success(f"Q{i+1} Evaluation: {st.session_state.evaluation[i]}")

