import streamlit as st
import pymupdf as fitz  # PyMuPDF
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from googletrans import Translator
import openai
import tempfile
import os

# --- Configuration ---
openai.api_key = st.secrets.get("OPENAI_API_KEY")  # store securely

# --- Language Selection ---
lang_codes = {
    "English": "en",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
    # Add more as needed
}

selected_lang = st.selectbox("Select your language / Sélectionnez la langue", list(lang_codes.keys()))
translator = Translator()

def translate(text):
    if selected_lang != "English":
        code = lang_codes[selected_lang]
        try:
            return translator.translate(text, dest=code).text
        except:
            return text
    return text

# --- PDF Upload ---
uploaded_pdf = st.file_uploader(translate("Upload your PDF file / Téléversez votre fichier PDF"), type="pdf")

if uploaded_pdf:
    doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
    pdf_text = ""
    for page in doc:
        pdf_text += page.get_text()

    # --- Number of Questions ---
    num_questions = st.number_input(translate("Number of questions / Nombre de questions"), min_value=1, max_value=20, value=5, step=1)

    # --- Generate Questions ---
    if st.button(translate("Generate Questions / Générer des questions")):
        llm = ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0.5)
        prompt_template = """You are a medical educator. Based on the following text, generate {num_questions} clear, concise questions suitable for trainee assessment. 
        Text: {text}"""
        prompt = PromptTemplate(input_variables=["text", "num_questions"], template=prompt_template)
        chain = LLMChain(llm=llm, prompt=prompt)
        questions_output = chain.run(text=pdf_text, num_questions=num_questions)

        questions = [q.strip() for q in questions_output.split("\n") if q.strip()]
        st.session_state.questions = questions
        st.session_state.answers = [""] * len(questions)

# --- Show Questions and Answer Inputs ---
if 'questions' in st.session_state:
    st.write(translate("Answer the following questions / Répondez aux questions suivantes:"))
    for i, question in enumerate(st.session_state.questions):
        st.markdown(f"**Q{i+1}: {translate(question)}**")

        # Text input
        st.session_state.answers[i] = st.text_area(
            translate("Your answer / Votre réponse"), 
            value=st.session_state.answers[i], 
            key=f"answer_{i}"
        )

        # Audio input
        audio_data = st.audio_input(
            label=translate("Record your answer (optional) / Enregistrez votre réponse (optionnel)"),
            key=f"audio_{i}"
        )
        if audio_data:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_data.read())
                tmp_filename = tmp_file.name
            # Transcribe audio
            with open(tmp_filename, "rb") as f:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
                st.session_state.answers[i] = transcript.text
            os.remove(tmp_filename)

# --- Evaluate Answers ---
if 'questions' in st.session_state and st.button(translate("Evaluate Answers / Évaluer les réponses")):
    st.write(translate("Evaluation / Évaluation:"))
    for i, question in enumerate(st.session_state.questions):
        llm = ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0)
        eval_prompt = f"Question: {question}\nStudent Answer: {st.session_state.answers[i]}\nProvide a concise model answer."
        response = llm.predict(eval_prompt)
        st.markdown(f"**Q{i+1} Model Answer / Réponse modèle:** {translate(response)}")


