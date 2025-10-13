import streamlit as st
from openai import OpenAI
import tempfile
import pymupdf as fitz  # PyMuPDF

# -------------------------------------------------------
# APP CONFIG
# -------------------------------------------------------
st.set_page_config(page_title="AI Oral Board Trainer", layout="wide")
st.title("🎙️ AI Oral Board Trainer")
st.write("Upload a PDF to generate bilingual oral board questions and record your answers for automated feedback.")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------------------------------------------------
# LANGUAGE SELECTION
# -------------------------------------------------------
LANGUAGES = [
    "English", "French", "Spanish", "German", "Arabic", "Chinese", "Portuguese"
]
user_language = st.selectbox("🌐 Select your language", options=LANGUAGES, index=0)

# -------------------------------------------------------
# TRANSLATION
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
# PDF TEXT EXTRACTION
# -------------------------------------------------------
def extract_text_from_pdf(pdf_file):
    text = ""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text[:6000]  # Limit to manageable length

# -------------------------------------------------------
# QUESTION GENERATION
# -------------------------------------------------------
def generate_questions(pdf_text, target_language):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a bilingual trauma surgery educator. Create 5 short-answer oral board questions and their ideal answers."},
            {"role": "user", "content": pdf_text},
        ],
    )
    english_output = response.choices[0].message.content.strip()
    translated_output = translate_text(english_output, target_language)
    return english_output, translated_output

# -------------------------------------------------------
# AUDIO TRANSCRIPTION (new OpenAI API syntax)
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
# ANSWER EVALUATION (partial credit, bilingual)
# -------------------------------------------------------
def evaluate_answer(question, expected_answer, user_answer, language):
    prompt = f"""
You are an experienced trauma examiner fluent in {language}.
Evaluate the following answer. Give partial credit when appropriate.

Question: {question}
Expected answer: {expected_answer}
User's answer: {user_answer}

Return in {language}:
1. A numeric score out of 10 (allow partial credit)
2. A short paragraph of feedback
3. One sentence describing what was missing
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()

# -------------------------------------------------------
# MAIN APP
# -------------------------------------------------------
st.markdown("### 📘 Upload a PDF to Generate Questions")
uploaded_pdf = st.file_uploader("Upload your source PDF file", type=["pdf"])

if uploaded_pdf:
    with st.spinner("📄 Reading your PDF and generating questions..."):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        q_en, q_translated = generate_questions(pdf_text, user_language)
    st.success("✅ Questions generated!")

    st.markdown("### 🧾 Generated Questions")
    st.markdown(f"**English:**\n\n{q_en}")
    st.markdown(f"**{user_language}:**\n\n{q_translated}")
    st.divider()

    # Split questions and answers into pairs (rough heuristic)
    question_blocks = [q for q in q_en.split("\n") if q.strip()][:5]

    st.markdown(f"### 🩺 Practice ({user_language})")

    for i, question_text in enumerate(question_blocks, 1):
        translated_q = translate_text(question_text, user_language)
        st.markdown(f"#### Question {i}:")
        st.info(f"{translated_q}")

        # Audio input for each question
        st.markdown(f"🎙️ Record or upload your answer ({user_language})")
        audio_file = st.audio_input(f"Record answer for Question {i}")

        user_transcript = ""
        if audio_file:
            audio_bytes = audio_file.read()
            with st.spinner(f"🎧 Transcribing your answer for Question {i}..."):
                try:
                    user_transcript = transcribe_audio(audio_bytes)
                    user_transcript = translate_text(user_transcript, user_language)
                    st.success(f"✅ Audio transcribed for Question {i}")
                except Exception as e:
                    st.error(f"Transcription failed: {e}")

        # Textbox for editing or typing the answer
        user_answer = st.text_area(
            f"✍️ Your answer in {user_language} (Question {i}):",
            value=user_transcript,
            height=150,
        )

        # Evaluate button for each question
        if st.button(f"🧠 Evaluate Question {i}"):
            if not user_answer.strip():
                st.warning("Please provide an answer before evaluation.")
            else:
                with st.spinner("Evaluating your answer..."):
                    feedback = evaluate_answer(translated_q, "Provide evidence-based trauma management.", user_answer, user_language)
                st.markdown("**🧾 Feedback:**")
                st.write(feedback)
        st.divider()
