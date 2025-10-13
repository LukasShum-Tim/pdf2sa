import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from deep_translator import GoogleTranslator
from gtts import gTTS
from io import BytesIO
import os

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="PDF to QA", layout="wide")
st.title("PDF to Conversational AI")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
target_language = st.selectbox("Translate answers to:", ["en", "fr", "de", "es", "it", "pt"])

if uploaded_file:
    # ---------------------------
    # Read PDF
    # ---------------------------
    pdf_reader = PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()

    # ---------------------------
    # Text Splitting
    # ---------------------------
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    chunks = text_splitter.split_text(text)

    # ---------------------------
    # Embeddings & Vectorstore
    # ---------------------------
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(chunks, embeddings)

    # ---------------------------
    # Conversational Retrieval
    # ---------------------------
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
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
        result = qa_chain({"question": user_question, "chat_history": st.session_state.conversation})
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
        # Display
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


