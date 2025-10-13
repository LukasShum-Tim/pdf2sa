import streamlit as st
from io import BytesIO
import pymupdf as fitz  # PyMuPDF
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import openai
from gtts import gTTS
from tempfile import NamedTemporaryFile
import os
from pydub import AudioSegment
import tempfile

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Trauma Quiz Generator", layout="wide")

# --- Sidebar ---
st.sidebar.header("Settings")
num_questions = st.sidebar.number_input("Number of questions:", min_value=1, max_value=20, value=5, step=1)
language = st.sidebar.selectbox("Select language:", ["English", "French", "Spanish", "German", "Other"])

# --- PDF Upload ---
st.header("Upload ATLS PDF Manual")
uploaded_file = st.file_uploader("Upload PDF", type="pdf")

pdf_text = ""
if uploaded_file is not None:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            pdf_text += page.get_text()
    st.success("PDF successfully loaded!")

# --- Generate Questions ---
st.header("Generated Questions")
generate_button = st.button("Generate Questions")

if generate_button:
    if not uploaded_file:
        st.warning("Please upload a PDF first.")
    else:
        # --- LLM Prompt ---
        llm = ChatOpenAI(model_name="gpt-4", temperature=0.5)
        prompt = PromptTemplate(
            input_variables=["text", "num_questions", "language"],
            template="""You are a trauma educator. 
Using the following text from a trauma manual, generate {num_questions} clinically relevant multiple-choice questions. 
Provide the question only, do NOT include answers yet. Translate into {language} if not English.
Text: {text}"""
        )
        chain = LLMChain(llm=llm, prompt=prompt)
        questions_text = chain.run(text=pdf_text, num_questions=num_questions, language=language)

        # Split questions by line breaks
        questions_list = [q.strip() for q in questions_text.split("\n") if q.strip()]
        
        # --- Display Questions with Response Boxes ---
        user_answers = {}
        for idx, question in enumerate(questions_list):
            st.markdown(f"**Q{idx+1}: {question}**")
            user_answers[idx] = st.text_area(f"Your answer for Q{idx+1}", key=f"answer_{idx}")
            
            # --- Audio Recording ---
            audio_file = st.audio_input(f"Record your answer for Q{idx+1} (will transcribe)", key=f"audio_{idx}")
            if audio_file:
                # Save temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_file.read())
                    tmp_path = tmp.name

                # Transcribe using OpenAI
                transcription = openai.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=open(tmp_path, "rb"),
                    language=language if language != "English" else "en"
                )
                st.markdown(f"**Transcription:** {transcription.text}")
                user_answers[idx] = transcription.text
                os.unlink(tmp_path)

        # --- Evaluate Answers ---
        evaluate_button = st.button("Evaluate Answers")
        if evaluate_button:
            for idx, question in enumerate(questions_list):
                prompt_eval = PromptTemplate(
                    input_variables=["question", "user_answer", "text", "language"],
                    template="""You are a trauma educator. The following is a question and a student answer.
Evaluate if the answer is correct based on the text provided. Provide a concise evaluation in {language}.

Question: {question}
Student Answer: {user_answer}
Reference Text: {text}"""
                )
                eval_chain = LLMChain(llm=llm, prompt=prompt_eval)
                result = eval_chain.run(
                    question=question, 
                    user_answer=user_answers[idx], 
                    text=pdf_text,
                    language=language
                )
                st.markdown(f"**Evaluation for Q{idx+1}:** {result}")
