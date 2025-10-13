import streamlit as st
from PyPDF2 import PdfReader
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from deep_translator import GoogleTranslator
import tempfile
import os
from gtts import gTTS
from io import BytesIO

st.set_page_config(page_title="Royal College Oral Exam AI", layout="wide")

# --- Sidebar ---
st.sidebar.title("Settings")
language = st.sidebar.selectbox("Select Language", ["English", "French", "Spanish", "German"])
num_questions = st.sidebar.slider("Number of Questions", 1, 20, 5)

# --- Initialize session state ---
if 'questions' not in st.session_state:
    st.session_state['questions'] = []
if 'answers' not in st.session_state:
    st.session_state['answers'] = []
if 'evaluations' not in st.session_state:
    st.session_state['evaluations'] = []

# --- Upload PDF ---
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    # --- Read PDF efficiently ---
    reader = PdfReader(pdf_path)
    text = "\n".join([page.extract_text() or "" for page in reader.pages])

    # --- Vectorstore for faster retrieval ---
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts([text], embeddings)

    # --- Generate questions ---
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
    prompt_template = PromptTemplate(
        input_variables=["content", "num_questions"],
        template="Create {num_questions} Royal College-style oral exam questions based on the following content:\n{content}"
    )
    chain = LLMChain(llm=llm, prompt=prompt_template)
    raw_questions = chain.run(content=text, num_questions=num_questions)
    
    # Split questions into list
    questions_list = [q.strip() for q in raw_questions.split("\n") if q.strip()]
    st.session_state['questions'] = questions_list[:num_questions]
    st.session_state['answers'] = [""] * len(st.session_state['questions'])
    st.session_state['evaluations'] = [""] * len(st.session_state['questions'])
    
    os.unlink(pdf_path)

# --- Display questions & answer input ---
for i, q in enumerate(st.session_state['questions']):
    # Translate question if necessary
    display_q = GoogleTranslator(source='auto', target=language.lower()).translate(q) if language != "English" else q
    st.markdown(f"**Question {i+1}:** {display_q}")
    
    # Text input for answer
    st.session_state['answers'][i] = st.text_area(f"Answer {i+1}", st.session_state['answers'][i], key=f"answer_{i}")

    # Optional: Text-to-speech button
    tts_button = st.button(f"Dictate Answer {i+1}", key=f"tts_{i}")
    if tts_button and st.session_state['answers'][i]:
        tts = gTTS(text=st.session_state['answers'][i], lang=language[:2].lower())
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        st.audio(audio_bytes.getvalue(), format="audio/mp3")

# --- Evaluate answers ---
if st.button("Evaluate Answers"):
    for i, q in enumerate(st.session_state['questions']):
        # Escape any curly braces in the answer to avoid f-string errors
        answer_text = st.session_state['answers'][i].replace("{", "{{").replace("}", "}}")
        
        prompt_eval = f"""
You are an examiner. Evaluate the following answer on a 2-point scale (0, 1, 2) according to Royal College standards.
Question: {q}
Student Answer: {answer_text}
Respond ONLY with the score and a brief justification.
"""
        eval_result = llm(prompt_eval)
        # Translate evaluation if necessary
        eval_display = GoogleTranslator(source='auto', target=language.lower()).translate(eval_result) if language != "English" else eval_result
        st.session_state['evaluations'][i] = eval_display

# --- Display evaluations ---
for i, evaluation in enumerate(st.session_state['evaluations']):
    if evaluation:
        st.markdown(f"**Evaluation {i+1}:** {evaluation}")


