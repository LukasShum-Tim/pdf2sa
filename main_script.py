import streamlit as st
import json
import pymupdf as fitz  # PyMuPDF
from openai import OpenAI
from googletrans import Translator
import time
import tempfile
import io
import hashlib
import os
import re

# -------------------------------
# INITIALIZATION
# -------------------------------
client = OpenAI()
translator = Translator()

st.set_page_config(
    page_title="📘 Multilingual Oral Board Exam Trainer",
    page_icon="🧠",
    layout="centered"
)

st.title("🧠 Multilingual Oral Board Exam Trainer")
st.markdown("Upload a PDF, generate short-answer questions, answer in your chosen language, and get bilingual feedback.")
st.markdown("If you are using a mobile device, make sure to use a pdf file that is downloaded locally, and not uploaded from a Cloud Drive to prevent an upload error.")

# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------
if "questions" not in st.session_state:
    st.session_state["questions"] = []

if "user_answers" not in st.session_state:
    st.session_state["user_answers"] = []

if "evaluations" not in st.session_state:
    st.session_state["evaluations"] = []

# -------------------------------
# SAFE TRANSLATION FUNCTION (CACHED)
# -------------------------------
@st.cache_data(show_spinner=False)
def safe_translate(text, target_language_code):
    """Translate text safely with fallback to GPT and skip English."""
    if not text or not text.strip():
        return text
    # ✅ Skip translation for English
    if target_language_code == "en":
        return text
    try:
        translated = translator.translate(text, dest=target_language_code)
        if translated and hasattr(translated, "text"):
            return translated.text
    except Exception:
        pass
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"Translate this text into {target_language_code}:\n{text}"}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return text

# -------------------------------
# LANGUAGE SELECTION
# -------------------------------
language_map = {
    'English': 'en',
    'Afrikaans': 'af',
    'Albanian': 'sq',
    'Amharic': 'am',
    'Arabic': 'ar',
    'Armenian': 'hy',
    'Azerbaijani': 'az',
    'Basque': 'eu',
    'Belarusian': 'be',
    'Bengali': 'bn',
    'Bosnian': 'bs',
    'Bulgarian': 'bg',
    'Catalan': 'ca',
    'Cebuano': 'ceb',
    'Chichewa': 'ny',
    'Chinese (Simplified)': 'zh-cn',
    'Chinese (Traditional)': 'zh-tw',
    'Corsican': 'co',
    'Croatian': 'hr',
    'Czech': 'cs',
    'Danish': 'da',
    'Dutch': 'nl',
    'Esperanto': 'eo',
    'Estonian': 'et',
    'Filipino': 'tl',
    'Finnish': 'fi',
    'French': 'fr',
    'Frisian': 'fy',
    'Galician': 'gl',
    'Georgian': 'ka',
    'German': 'de',
    'Greek': 'el',
    'Gujarati': 'gu',
    'Haitian Creole': 'ht',
    'Hausa': 'ha',
    'Hawaiian': 'haw',
    'Hebrew': 'he',
    'Hindi': 'hi',
    'Hmong': 'hmn',
    'Hungarian': 'hu',
    'Icelandic': 'is',
    'Igbo': 'ig',
    'Indonesian': 'id',
    'Irish': 'ga',
    'Italian': 'it',
    'Japanese': 'ja',
    'Javanese': 'jw',
    'Kannada': 'kn',
    'Kazakh': 'kk',
    'Khmer': 'km',
    'Korean': 'ko',
    'Kurdish (Kurmanji)': 'ku',
    'Kyrgyz': 'ky',
    'Lao': 'lo',
    'Latin': 'la',
    'Latvian': 'lv',
    'Lithuanian': 'lt',
    'Luxembourgish': 'lb',
    'Macedonian': 'mk',
    'Malagasy': 'mg',
    'Malay': 'ms',
    'Malayalam': 'ml',
    'Maltese': 'mt',
    'Maori': 'mi',
    'Marathi': 'mr',
    'Mongolian': 'mn',
    'Myanmar (Burmese)': 'my',
    'Nepali': 'ne',
    'Norwegian': 'no',
    'Odia': 'or',
    'Pashto': 'ps',
    'Persian': 'fa',
    'Polish': 'pl',
    'Portuguese': 'pt',
    'Punjabi': 'pa',
    'Romanian': 'ro',
    'Russian': 'ru',
    'Samoan': 'sm',
    'Scots Gaelic': 'gd',
    'Serbian': 'sr',
    'Sesotho': 'st',
    'Shona': 'sn',
    'Sindhi': 'sd',
    'Sinhala': 'si',
    'Slovak': 'sk',
    'Slovenian': 'sl',
    'Somali': 'so',
    'Spanish': 'es',
    'Sundanese': 'su',
    'Swahili': 'sw',
    'Swedish': 'sv',
    'Tajik': 'tg',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Thai': 'th',
    'Turkish': 'tr',
    'Ukrainian': 'uk',
    'Urdu': 'ur',
    'Uyghur': 'ug',
    'Uzbek': 'uz',
    'Vietnamese': 'vi',
    'Welsh': 'cy',
    'Xhosa': 'xh',
    'Yiddish': 'yi',
    'Yoruba': 'yo',
    'Zulu': 'zu',
}

target_language_name = st.selectbox("🌍 Select your language:", list(language_map.keys()), index=0)
target_lang_code = language_map[target_language_name]

def bilingual_text(en_text):
    """Display English + translated text, unless English is selected."""
    if target_lang_code == "en":
        return en_text
    translated = safe_translate(en_text, target_lang_code)
    return f"{en_text}\n**({target_language_name})**: {translated}"

# -------------------------------
# PDF UPLOAD
# -------------------------------
uploaded_file = st.file_uploader(bilingual_text("📄 Upload a PDF file"), type=["pdf"])

def extract_text_from_pdf(uploaded_file):
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf_doc:
        for page in pdf_doc:
            text += page.get_text("text")
    return text
    
if uploaded_file:
    if "pdf_text" not in st.session_state or st.session_state.get("uploaded_file_name") != uploaded_file.name:
        pdf_text = extract_text_from_pdf(uploaded_file)
        st.session_state["pdf_text"] = pdf_text
        st.session_state["uploaded_file_name"] = uploaded_file.name
        st.success(bilingual_text("✅ PDF uploaded successfully!"))
    else:
        pdf_text = st.session_state["pdf_text"]

pdf_text = st.session_state.get("pdf_text", "")

# -------------------------------
# NEW BUTTON: Generate a new set of questions
# -------------------------------
if st.session_state.get("pdf_text"):
    if st.button(bilingual_text("🔄 Generate a New Set of Questions")):
        # Clear old questions, answers, and evaluations
        st.session_state["questions"] = []
        st.session_state["user_answers"] = []
        st.session_state["evaluations"] = []

        # Trigger the question generation block using existing pdf_text
        pdf_text = st.session_state["pdf_text"]
        st.experimental_rerun()  # Optional: restart app flow to regenerate questions

# -------------------------------
# QUESTION GENERATION (SECTION-LENGTH PROPORTIONAL)
# -------------------------------
if pdf_text:
    st.subheader(bilingual_text("🧩 Step 1: Generate Short-Answer Questions"))

    num_questions = st.slider(bilingual_text("Number of questions to generate:"), 1, 20, 5)

    if st.button(bilingual_text("⚡ Generate Questions")):
        progress = st.progress(0, text=bilingual_text("Generating questions... please wait"))

        # -------------------------------
        # Helper: Split PDF into sections by headings
        # -------------------------------
        def split_into_sections(text):
            """
            Split text by headings.
            This example uses lines in ALL CAPS or numbered headings like '1. ', '2.1 '.
            Adjust regex to match your manual's heading style.
            """
            pattern = r'(\n(?:[0-9]+(?:\.[0-9]+)*\s+.*)|\n[A-Z ]{5,}\n)'
            splits = re.split(pattern, text)
            sections = []
            for s in splits:
                s_clean = s.strip()
                if s_clean:
                    sections.append(s_clean)
            return sections

        sections = split_into_sections(pdf_text)
        total_length = sum(len(s) for s in sections)

        # -------------------------------
        # Allocate questions proportionally by section length
        # -------------------------------
        questions_per_section = [
            max(1, round(len(s) / total_length * num_questions)) for s in sections
        ]

        all_questions = []

        for i, (section_text, q_count) in enumerate(zip(sections, questions_per_section)):
            progress.progress(int(i / len(sections) * 50), text=bilingual_text(f"Generating questions from section {i+1}/{len(sections)}..."))

            prompt = f"""
You are an expert medical educator.
Generate {q_count} concise short-answer questions and their answer keys based on the following content.
Your target audience is residents.
If the content is surgical, focus on surgical presentation, surgical approach, and surgical management.
If possible, generate **different questions from any previous set**, focusing on other key concepts.
Structure your questions like a Royal College of Physicians and Surgeons oral boards examiner.
Return ONLY JSON in this format:
[
  {{"question": "string", "answer_key": "string"}}
]

SOURCE TEXT:
{section_text}
"""
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-2025-04-14",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8
                )
                raw = response.choices[0].message.content.strip()
                raw = re.sub(r"```(?:json)?|```", "", raw).strip()
                section_questions = json.loads(raw)
                all_questions.extend(section_questions)
            except Exception as e:
                st.error(bilingual_text(f"⚠️ Question generation failed for section {i+1}: {e}"))

        # Limit to total number requested
        all_questions = all_questions[:num_questions]
        progress.progress(60, text=bilingual_text("Translating questions..."))

        # -------------------------------
        # Bilingual translation
        # -------------------------------
        bilingual_questions = []

        if target_language_name == "English":
            for q in all_questions:
                q_en = q.get("question", "")
                a_en = q.get("answer_key", "")
                bilingual_questions.append({
                    "question_en": q_en,
                    "answer_key_en": a_en,
                })
        else:
            for i, q in enumerate(all_questions):
                q_en = q.get("question", "")
                a_en = q.get("answer_key", "")
                q_trans = safe_translate(q_en, target_lang_code)
                a_trans = safe_translate(a_en, target_lang_code)
                bilingual_questions.append({
                    "question_en": q_en,
                    "question_translated": q_trans,
                    "answer_key_en": a_en,
                    "answer_key_translated": a_trans
                })
                progress.progress(60 + int((i+1)/len(all_questions)*30), text=bilingual_text("Translating..."))

        # -------------------------------
        # Save to session state
        # -------------------------------
        st.session_state["questions"] = bilingual_questions
        st.session_state["user_answers"] = [""] * len(bilingual_questions)
        progress.progress(100, text=bilingual_text("✅ Done! Questions ready."))

        # -------------------------------
        # Store previous sets for consultation
        # -------------------------------
        if "all_question_sets" not in st.session_state:
            st.session_state["all_question_sets"] = []
        
        # Append a copy of the current set
        st.session_state["all_question_sets"].append({
            "questions": bilingual_questions,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        st.success(bilingual_text(f"Generated {len(bilingual_questions)} representative questions successfully!"))


# -------------------------------
# USER ANSWERS (WITH AUDIO INPUT)
# -------------------------------
if st.session_state["questions"]:
    st.subheader(bilingual_text("🧠 Step 2: Answer the Questions"))

    questions = st.session_state["questions"]

    if "user_answers" not in st.session_state or len(st.session_state["user_answers"]) != len(questions):
        st.session_state["user_answers"] = [""] * len(questions)

    for i, q in enumerate(questions):
        st.markdown(f"### Q{i+1}. {q.get('question_en', '')}")

        if target_language_name == "English":
            pass
        else:    
            st.markdown(f"**({target_language_name}):** {q.get('question_translated', '')}")

        st.markdown(bilingual_text("🎤 Dictate your answer (you can record multiple times):"))
        audio_data = st.audio_input("", key=f"audio_input_{i}")

        transcriptions_key = f"transcriptions_{i}"
        last_hash_key = f"last_audio_hash_{i}"
        if transcriptions_key not in st.session_state:
            st.session_state[transcriptions_key] = []
        if last_hash_key not in st.session_state:
            st.session_state[last_hash_key] = None

        if audio_data is not None:
            try:
                audio_bytes = audio_data.getvalue()  # ✅ safer than .read()
                audio_hash = hashlib.sha256(audio_bytes).hexdigest()

                if st.session_state.get(last_hash_key) == audio_hash:
                    st.info(bilingual_text("This recording was already transcribed. Record again to add more."), icon="ℹ️")
                else:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        tmp_file.write(audio_bytes)
                        tmp_path = tmp_file.name

                    with open(tmp_path, "rb") as f:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f
                        )

                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                    text_out = getattr(transcription, "text", "").strip()
                    if text_out:
                        st.session_state[transcriptions_key].append(text_out)
                        combined_text = " ".join(st.session_state[transcriptions_key])
                        st.session_state[f"ans_{i}"] = combined_text
                        st.session_state["user_answers"][i] = combined_text
                        st.session_state[last_hash_key] = audio_hash
                        st.success(bilingual_text("🎧 New recording transcribed and appended to your answer."), icon="🎤")
                    else:
                        st.warning(bilingual_text("⚠️ Transcription returned empty text."))
            except Exception as e:
                st.error(bilingual_text(f"⚠️ Audio transcription failed: {e}"))

        label = bilingual_text("✏️ Your Answer:")
        current_text = st.text_area(label, height=80, key=f"ans_{i}")
        st.session_state["user_answers"][i] = current_text

    user_answers = st.session_state.get("user_answers", [])

    # -------------------------------
    # EVALUATION
    # -------------------------------
    def score_short_answers(user_answers, questions):
        grading_prompt = f"""
You are a Royal College of Physicians and Surgeons oral boards examiner. You are examining the chief residents' answers to oral board exam questions. Score each short-answer response on a 0–2 scale, 0 being extremely deficient, 1 being acceptable, and 2 being exemplary.
Return ONLY JSON:
[
  {{
    "score": 2,
    "feedback": "Good answer.",
    "model_answer": "Key concept here..."
  }},
  ...
]

QUESTIONS AND RESPONSES:
{json.dumps([
    {"question": q.get("question_en", ""), "expected": q.get("answer_key_en", ""), "response": a}
    for q, a in zip(questions, user_answers)
], indent=2)}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": grading_prompt}],
                temperature=0
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```(?:json)?|```", "", raw).strip()
            results = json.loads(raw)
            for r in results:
                r["feedback_translated"] = safe_translate(r.get("feedback", ""), target_lang_code)
                r["model_answer_translated"] = safe_translate(r.get("model_answer", ""), target_lang_code)
            return results
        except Exception as e:
            st.error(bilingual_text(f"⚠️ Scoring failed: {e}"))
            return []

    if st.button(bilingual_text("🚀 Evaluate My Answers")):
        with st.spinner(bilingual_text("Evaluating your answers...")):
            results = score_short_answers(user_answers, questions)
            st.session_state['evaluations'] = results

        if results:
            # -------------------------------
            # Compute total score
            # -------------------------------
            total_score = sum(r.get("score", 0) for r in results)
            max_score = len(results) * 2  # each question max 2 points
            percentage = round(total_score / max_score * 100, 1)
    
            st.success(bilingual_text("✅ Evaluation complete!"))
    
            # -------------------------------
            # Display total score
            # -------------------------------
            st.markdown(f"### 🏆 {bilingual_text('Total Score')}: {total_score}/{max_score} ({percentage}%)")
            
            st.success(bilingual_text("✅ Evaluation complete!"))
            with st.expander(bilingual_text("📊 Detailed Feedback")):
                for i, (q, r) in enumerate(zip(questions, results)):
                    st.markdown(f"### Q{i+1}: {q.get('question_en', '')}")
                    
                    if target_language_name == "English":
                        st.markdown(f"**Score:** {r.get('score', 'N/A')} / 2")
                        st.markdown(f"**Feedback (English):** {r.get('feedback', '')}")
                        st.markdown(f"**Model Answer (English):** {r.get('model_answer', '')}")
                        st.markdown("---")

                    else:                    
                        st.markdown(f"**({target_language_name}): {q.get('question_translated', '')}**")
                        st.markdown(f"**Score:** {r.get('score', 'N/A')} / 2")
                        st.markdown(f"**Feedback (English):** {r.get('feedback', '')}")
                        st.markdown(f"**Feedback ({target_language_name}):** {r.get('feedback_translated', '')}")
                        st.markdown(f"**Model Answer (English):** {r.get('model_answer', '')}")
                        st.markdown(f"**Model Answer ({target_language_name}):** {r.get('model_answer_translated', '')}")
                        st.markdown("---")
