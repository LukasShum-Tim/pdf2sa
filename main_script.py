import streamlit as st
import openai
import tempfile
import os

# -------------------------------------------------------
# STREAMLIT CONFIGURATION
# -------------------------------------------------------
st.set_page_config(page_title="AI Oral Board Trainer", layout="wide")
st.title("🎙️ AI Oral Board Trainer")
st.write("Practice oral board scenarios with real-time feedback in your preferred language.")

# -------------------------------------------------------
# OPENAI CLIENT SETUP
# -------------------------------------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# -------------------------------------------------------
# LANGUAGE SELECTION
# -------------------------------------------------------
LANGUAGES = {
    "English": "English",
    "French": "French",
    "Spanish": "Spanish",
    "German": "German",
    "Arabic": "Arabic",
    "Chinese": "Chinese",
    "Portuguese": "Portuguese"
}

user_language = st.selectbox("🌐 Select your language", options=list(LANGUAGES.keys()), index=0)


# -------------------------------------------------------
# TRANSLATION FUNCTION
# -------------------------------------------------------
def translate_text(text, target_language):
    """Translate text into the target language using GPT."""
    if target_language == "English":
        return text
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Translate the following text into {target_language}."},
            {"role": "user", "content": text}
        ],
    )
    return response.choices[0].message.content.strip()


# -------------------------------------------------------
# AUDIO TRANSCRIPTION FUNCTION
# -------------------------------------------------------
def transcribe_audio(audio_bytes):
    """Transcribe uploaded or recorded audio to text using OpenAI Whisper."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        with open(tmp.name, "rb") as f:
            transcript = openai.Audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            )
    os.remove(tmp.name)
    return transcript.text.strip()


# -------------------------------------------------------
# ANSWER EVALUATION FUNCTION
# -------------------------------------------------------
def evaluate_answer(question, expected_answer, user_answer, language):
    """Evaluate the user's answer in the chosen language and provide partial credit."""
    prompt = f"""
You are an experienced bilingual trauma examiner.

Language: {language}
Question: {question}
Expected ideal answer: {expected_answer}
User's answer: {user_answer}

Evaluate the user's answer **in {language}**. Provide:
1. A score out of 10 (partial credit allowed)
2. A short paragraph of feedback
3. A one-line summary of what was missing

Respond entirely in {language}.
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


# -------------------------------------------------------
# QUESTION + EXPECTED ANSWER (BASE CONTENT)
# -------------------------------------------------------
base_question = "Describe the management of a patient presenting with hemorrhagic shock due to a pelvic fracture."
base_answer = (
    "The management includes airway and breathing control, application of a pelvic binder, large-bore IV access, "
    "balanced transfusion of blood products, early hemorrhage control (interventional radiology or surgery), and continuous reassessment."
)

# Translate both to selected language
translated_question = translate_text(base_question, user_language)
translated_answer = translate_text(base_answer, user_language)

# -------------------------------------------------------
# DISPLAY QUESTION
# -------------------------------------------------------
st.markdown(f"### 🩺 Question ({user_language})")
st.info(translated_question)

# -------------------------------------------------------
# AUDIO RECORDING / UPLOAD
# -------------------------------------------------------
st.markdown(f"#### 🎤 Record or Upload Your Answer in {user_language}")
audio_file = st.audio_input(f"Click below to record or upload your answer ({user_language}):")

user_transcript = ""

if audio_file:
    audio_bytes = audio_file.read()
    with st.spinner("🎧 Transcribing your audio..."):
        try:
            user_transcript = transcribe_audio(audio_bytes)
            # Optional: translate the transcript into the user's selected language if Whisper detects another language
            user_transcript = translate_text(user_transcript, user_language)
            st.success("✅ Audio transcribed successfully. You can review and edit below.")
        except Exception as e:
            st.error(f"Transcription failed: {e}")

# -------------------------------------------------------
# USER TEXT AREA
# -------------------------------------------------------
user_answer = st.text_area(
    f"✍️ Type or edit your answer in {user_language}:",
    value=user_transcript,
    height=200,
)

# -------------------------------------------------------
# EVALUATE ANSWER
# -------------------------------------------------------
if st.button("🧠 Evaluate My Answer"):
    if not user_answer.strip():
        st.warning("Please record or type your answer before evaluating.")
    else:
        with st.spinner("Evaluating your response..."):
            feedback = evaluate_answer(translated_question, translated_answer, user_answer, user_language)
        st.markdown("### 🧾 Feedback")
        st.write(feedback)

