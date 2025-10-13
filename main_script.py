import streamlit as st
import pdfplumber
from deep_translator import GoogleTranslator
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import speech_recognition as sr

# ----------------- UI -----------------
st.set_page_config(page_title="Oral Exam Generator", layout="wide")
st.title("📄 Royal College-style Oral Exam Generator")

# Language selection
language = st.selectbox("Select your language / Seleccione su idioma:", 
                        ["English", "French", "Spanish", "German", "Portuguese", "Chinese"])

# Translation helper
def translate(text, target_lang):
    if target_lang.lower() == "english":
        return text
    try:
        return GoogleTranslator(source='auto', target=target_lang.lower()).translate(text)
    except:
        return text

# ----------------- PDF Upload -----------------
uploaded_file = st.file_uploader(translate("Upload your PDF file", language), type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])

    st.success(translate("PDF successfully processed!", language))

    # ----------------- Split and Vectorize -----------------
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_text(text)
    
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(chunks, embeddings)

    st.session_state['vectorstore'] = vectorstore

    # ----------------- Question Generation -----------------
    num_questions = st.number_input(translate("Number of oral exam questions to generate:", language), 
                                    min_value=1, max_value=50, value=5, step=1)

    if st.button(translate("Generate Questions", language)):
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.7)

        # Retrieve relevant chunks first
        docs = vectorstore.similarity_search("Generate exam questions", k=min(5, len(chunks)))
        context_text = " ".join([d.page_content for d in docs])

        answer_text = st.session_state['answers'][i].replace("{", "{{").replace("}", "}}")

      
        prompt = f"""
        You are an expert examiner. Generate {num_questions} Royal College-style oral exam questions from the following text. 
        Provide only the question text.
        Text: {context_text}
        """
        response = llm.predict(prompt)
        questions = [q.strip() for q in response.split("\n") if q.strip()]

        st.session_state['questions'] = questions
        st.session_state['answers'] = [""] * len(questions)
        st.session_state['scores'] = [None] * len(questions)

# ----------------- Display Questions -----------------
if 'questions' in st.session_state:
    st.subheader(translate("Answer the following questions:", language))
    
    for i, q in enumerate(st.session_state['questions']):
        st.markdown(f"**Q{i+1}:** {translate(q, language)}")
        st.session_state['answers'][i] = st.text_area(
            translate("Your answer:", language), 
            value=st.session_state['answers'][i], 
            key=f"answer_{i}", height=100
        )

        # Voice input
        if st.button(translate("🎤 Dictate Answer", language), key=f"voice_{i}"):
            r = sr.Recognizer()
            with sr.Microphone() as source:
                st.info(translate("Listening...", language))
                audio = r.listen(source)
            try:
                transcription = r.recognize_google(audio, language=language[:2].lower())
                st.session_state['answers'][i] = transcription
                st.success(translate("Answer transcribed successfully!", language))
            except:
                st.error(translate("Could not transcribe audio.", language))
    
    # ----------------- Evaluate Answers -----------------
    if st.button(translate("Evaluate Answers", language)):
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
        for i, q in enumerate(st.session_state['questions']):
            prompt_eval = f"""
            You are an examiner. Evaluate the following answer on a 2-point scale (0, 1, 2) according to Royal College standards.
            Question: {q}
            Student Answer: {st.sessi

