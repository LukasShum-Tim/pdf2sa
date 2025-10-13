import streamlit as st
from openai import OpenAI
import tempfile
import pymupdf as fitz  # PyMuPDF for PDF parsing

# -------------------------------------------------------
# SETUP
# -------------------------------------------------------
st.set_page_config(page_title="AI Oral Board Trainer", layout="wide")
st.title("🎙️ AI Oral Board Trainer")
st.write("Upload a PDF, generate bilingual short-answer questions, and practice oral responses with feedback.")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------------------------------------------------
# LANGUAGE SELECTION
# -------------------------------------------------------
LANGUAGES = [
    "English", "French", "Spanish", "German", "Arabic", "Chinese", "Portuguese"
]
user_language = st.selectbox("🌐 Select your language", options=LANGUAGES, index=0)


# -------------------------------------------------------
# TRANSLATION FUNCTION
# -------------------------------------------------------
def translate_text(text, target_language):
    if target_language == "English":
        return text
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Translate the following text into {target_language}."},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content.strip()


# -------------------------------------------------------
# PDF EXTRACTION
# -------------------------------------------------------
def extract_text_from_pdf(pdf_file):
    text = ""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text[:6000]  # Limit length for performance


# -------------------------------------------------------
# QUESTION GENERATION
# -------------------------------------------------------
def generate_questions(pdf_text, target_language):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a bilingual trauma surgery educator. Generate 5 short-answer questions and ideal answers based on the provided text."},
            {"role": "user", "content": pdf_text},
        ],
    )
    english_output = response.choices[0].message.content.strip()
    translated_output = translate_text(english_output, target_language)
    return english_output, translated_output


# -------------------------------------------------------
# AUDIO TRANSCRIPTION
# -------------------------------------------------------
def transcribe_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        with open(tmp.name, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            )
    return transcript.text.strip()


# -------------------------------------------------------
# ANSWER EVALUATION
# -------------------------------------------------------
def evaluate_answer(question, expected_answer, user_answer, language):
    prompt = f"""
You are an experienced trauma examiner fluent in {language}.
Evaluate the following answer. Provide partial credit and feedback in {language}.

Question: {question}
Expected answer: {expected_answer}
User's answer: {user_answer}

Return:
1. A numeric score out of 10 (partial credit allowed)
2. A short paragraph of feedback in {language}
3. A one-line summary of what was missing
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# -------------------------------------------------------
# PDF UPLOAD AND QUESTION GENERATION
# -------------------------------------------------------
st.markdown("### 📘 Upload a PDF to Generate Questions")
uploaded_pdf = st.file_uploader("Upload your source PDF file", type=["pdf"])

if uploaded_pdf:
    with st.spinner("📄 Reading your PDF and generating questions..."):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        q_en, q_translated = generate_questions(pdf_text, user_language)
    st.success("✅ Questions generated!")
    st.markdown(f"**Questions in English:**\n\n{q_en}")
    st.markdown(f"**Questions in {user_language}:**\n\n{q_translated}")

    st.markdown("---")

    # Ask user one sample question
    st.markdown(f"### 🩺 Practice a Question ({user_language})")
    sample_question = translate_text("Describe the management of hemorrhagic shock.", user_language)
    st.info(sample_question)

    # Audio input
    st.markdown(f"#### 🎤 Record or Upload Your Answer ({user_language})")
    audio_file = st.audio_input(f"Click below to record or upload your answer ({user_language})")

    user_transcript = ""

    if audio_file:
        audio_bytes = audio_file.read()
        with st.spinner("🎧 Transcribing your audio..."):
            try:
                user_transcript = transcribe_audio(audio_bytes)
                user_transcript = translate_text(user_transcript, user_language)
                st.success("✅ Audio transcribed successfully. You can review and edit below.")
            except Exception as e:
                st.error(f"Transcription failed: {e}")

    user_answer = st.text_area(
        f"✍️ Type or edit your answer in {user_language}:",
        value=user_transcript,
        height=200,
    )

    if st.button("🧠 Evaluate My Answer"):
        if not user_answer.strip():
            st.warning("Please provide an answer before evaluation.")
        else:
            with st.spinner("Evaluating your answer..."):
                feedback = evaluate_answer(sample_question, "Control airway, restore circulation, and stop bleeding.", user_answer, user_language)
            st.markdown("### 🧾 Feedback")
            st.write(feedback)

