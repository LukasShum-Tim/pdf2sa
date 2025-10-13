import streamlit as st
import pymupdf as fitz  # PyMuPDF
import openai
from googletrans import Translator
import asyncio

# ----------------------------
# CONFIG
# ----------------------------
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
translator = Translator()

st.set_page_config(page_title="PDF Q&A Generator", layout="wide")

# ----------------------------
# TRANSLATION FUNCTION
# ----------------------------
def translate_text(text, target_lang):
    if target_lang.lower() == "en":
        return text
    try:
        translated = translator.translate(text, dest=target_lang.lower())
        return translated.text
    except Exception as e:
        st.warning(f"Translation failed: {e}")
        return text

def bilingual_text(text, target_lang):
    return f"{text}\n({translate_text(text, target_lang)})" if target_lang.lower() != "en" else text

# ----------------------------
# PDF UPLOAD AND EXTRACTION
# ----------------------------
uploaded_pdf = st.file_uploader("Upload your PDF file / Téléversez votre fichier PDF", type="pdf")

if uploaded_pdf:
    pdf_doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
    pdf_text = ""
    for page in pdf_doc:
        pdf_text += page.get_text()

    st.success("PDF loaded successfully!")

# ----------------------------
# USER SETTINGS
# ----------------------------
languages = ["en", "fr", "es", "de", "zh-cn"]
selected_lang = st.selectbox("Select your language / Sélectionnez votre langue", languages)
num_questions = st.slider(bilingual_text("Number of questions / Nombre de questions", selected_lang), 1, 5, 1)

# ----------------------------
# QUESTION GENERATION FUNCTION
# ----------------------------
def generate_questions(pdf_text, num_questions):
    prompt = f"""
    You are an educational assistant.
    Generate {num_questions} clear multiple-choice or short-answer questions from the following text.
    Provide the questions in JSON array format:
    [
        {{
            "question": "...",
            "answer": "..."
        }}
    ]
    Text:
    {pdf_text}
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        questions_json = response.choices[0].message.content
        return questions_json
    except Exception as e:
        st.error(f"Question generation failed: {e}")
        return "[]"

# ----------------------------
# GENERATE QUESTIONS BUTTON
# ----------------------------
if uploaded_pdf:
    if st.button(bilingual_text("Generate Questions / Générer les questions", selected_lang)):
        import json
        questions_data = generate_questions(pdf_text, num_questions)
        try:
            questions_list = json.loads(questions_data)
        except Exception as e:
            st.error(f"Failed to parse questions JSON: {e}")
            questions_list = []

        st.session_state["questions_list"] = questions_list

# ----------------------------
# DISPLAY QUESTIONS AND ANSWERS
# ----------------------------
if "questions_list" in st.session_state:
    for i, qdata in enumerate(st.session_state["questions_list"]):
        question_en = qdata.get("question", "")
        answer_en = qdata.get("answer", "")
        question_translated = translate_text(question_en, selected_lang)
        answer_translated = translate_text(answer_en, selected_lang)

        st.markdown(f"**Question {i+1}:** {question_en} / {question_translated}")
        user_answer = st.text_area(
            label=bilingual_text(f"Your answer / Votre réponse", selected_lang),
            key=f"answer_{i}"
        )

        st.audio_input(
            label=bilingual_text(f"Record your answer / Enregistrez votre réponse", selected_lang),
            key=f"audio_{i}"
        )

        if st.button(bilingual_text("Evaluate Answer / Évaluer la réponse", selected_lang), key=f"eval_{i}"):
            eval_prompt = f"""
            You are an educational assistant. Evaluate the student's answer.
            Question: {question_en}
            Correct Answer: {answer_en}
            Student Answer: {user_answer}
            Provide a short evaluation and mark correct/incorrect.
            """
            try:
                eval_response = openai.chat.completions.create(
                    model="gpt-4-1106-preview",
                    messages=[{"role": "user", "content": eval_prompt}],
                    temperature=0
                )
                eval_text_en = eval_response.choices[0].message.content
                eval_text_translated = translate_text(eval_text_en, selected_lang)
                st.markdown(f"**Evaluation:** {eval_text_en} / {eval_text_translated}")
                st.markdown(f"**Correct Answer:** {answer_en} / {answer_translated}")
            except Exception as e:
                st.error(f"Evaluation failed: {e}")
