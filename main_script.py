import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from deep_translator import GoogleTranslator
from gtts import gTTS
from io import BytesIO

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="PDF to QA", layout="wide")
st.title("PDF to Conversational AI")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
target_language = st.selectbox("Translate answers to:", ["en", "fr", "de", "es", "it", "pt"])

MAX_CHUNKS = 50  # Limit embeddings for speed

if uploaded_file:
    with st.spinner("Reading PDF..."):
        pdf_reader = PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""

    # ---------------------------
    # Text Splitting
    # ---------------------------
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_text(text)
    
    # Limit chunks for speed
    if len(chunks) > MAX_CHUNKS:
        chunks = chunks[:MAX_CHUNKS]

    # ---------------------------
    # Embeddings & Vectorstore
    # ---------------------------
    with st.spinner("Creating embeddings..."):
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_texts(chunks, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    # ---------------------------
    # Conversational QA Chain
    # ---------------------------
    qa_chain = ConversationalRetrievalChain.from_llm(
        ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo"),
        retriever=retriever
    )

    if "conversation" not in st.session_state:
        st.session_state.conversation = []

    # ---------------------------
    # User Input
    # ---------------------------
    user_question = st.text_input("Ask a question about your PDF:")
    if user_question:
        with st.spinner("Generating answer..."):
            result = qa_chain({
                "question": user_question,
                "chat_history": st.session_state.conversation
            })
            answer = result["answer"]

        # ---------------------------
        # Translate Answer
        # ---------------------------
        if target_language != "en":
            try:
                answer_translated = GoogleTranslator(source='auto', target=target_language).translate(answer)
            except Exception as e:
                st.error(f"Translation failed: {e}")
                answer_translated = answer
        else:
            answer_translated = answer

        # ---------------------------
        # Display Answer
        # ---------------------------
        st.write("**Answer:**")
        st.write(answer_translated)

        # ---------------------------
        # Text-to-Speech
        # ---------------------------
        tts = gTTS(text=answer_translated, lang=target_language)
        mp3_fp = BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        st.audio(mp3_fp, format="audio/mp3")

        # ---------------------------
        # Update Conversation
        # ---------------------------
        st.session_state.conversation.append((user_question, answer_translated))


