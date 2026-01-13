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
if "question_set_id" not in st.session_state:
    st.session_state["question_set_id"] = 0

if "generate_new_set" not in st.session_state:
    st.session_state["generate_new_set"] = False

if "questions" not in st.session_state:
    st.session_state["questions"] = []

if "user_answers" not in st.session_state:
    st.session_state["user_answers"] = []

if "evaluations" not in st.session_state:
    st.session_state["evaluations"] = []

if "selected_prev_set" not in st.session_state:
    st.session_state["selected_prev_set"] = None

if "mode" not in st.session_state:
    st.session_state["mode"] = "idle"  # idle | generate | retry

# -------------------------------
# SAFE TRANSLATION FUNCTION (CACHED)
# -------------------------------
def _looks_english(text):
    english_words = ["the", "and", "identify", "make", "open"]
    hits = sum(word in text.lower() for word in english_words)
    return hits >= 2

@st.cache_data(show_spinner=False)
def safe_translate(text, target_language_name):
    """Translate text safely with fallback to google translate and skip English."""
    if not text or not text.strip():
        return text
                
    # ✅ Skip translation for English
    if target_language_code == "en":
        return text
    try:
        prompt = f"""
        You are a professional medical translator.
        
        TASK:
        Translate the following medical text into **{target_language_name}**.
        
        STRICT RULES:
        - Output MUST be written entirely in {target_language_name}
        - DO NOT keep English sentences
        - Medical terms may remain Latin-based if appropriate
        - Do NOT summarize or paraphrase
        - If unsure, still translate
        
        TEXT:
        {text}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        translated = response.choices[0].message.content.strip()

        # 🔎 Post-check: still looks English?
        if _looks_english(translated):
            raise ValueError("GPT returned English")

        return translated 
    except Exception:
        pass
        
    try:
        translated = translator.translate(text, dest=target_language_name)
        return translated.text if translated else text
    except Exception:
        pass

    return text

#Google translate first
def ui_translate(text, target_language_name):
    """Translate text safely with fallback to ChatGPT and skip English."""
    if not text or not text.strip():
        return text
    if target_language_code == "en":
        return text
    try:
        translated = translator.translate(text, dest=target_language_name)
        if translated and hasattr(translated, "text"):
            return translated.text
    except Exception:
        pass
    
    try:
        prompt = f"""Translate this text into {target_language_name}:\n{text}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()    
    except Exception:
        pass
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
target_language_code = language_map[target_language_name]

def bilingual_text(en_text):
    """Display English + translated text, unless English is selected."""
    if target_language_code == "en":
        return en_text
    translated = safe_translate(en_text, target_language_name)
    return f"{en_text}\n**({target_language_name})**: {translated}"

def bilingual_text_ui(en_text):
    """Display English + translated text, unless English is selected. Function specifically for not medically important information."""
    if target_language_code == "en":
        return en_text
    translated = ui_translate(en_text, target_language_name)
    return f"{en_text}\n**({target_language_name})**: {translated}"

# -------------------------------
# PDF UPLOAD
# -------------------------------
uploaded_file = st.file_uploader(bilingual_text_ui("📄 Upload a PDF file"), type=["pdf"])

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
        st.success(bilingual_text_ui("✅ PDF uploaded successfully!"))
    else:
        pdf_text = st.session_state["pdf_text"]

pdf_text = st.session_state.get("pdf_text", "")


# -------------------------------
# Question Topic Extraction
# -------------------------------
def extract_topics_from_questions(questions):
    """
    Extract short topic labels from a list of questions.
    """
    prompt = f"""
Extract a concise topic label (2–5 words) for each of the following oral board questions.
Return ONLY a JSON list of UNIQUE topic strings.

QUESTIONS:
{json.dumps([q["question_en"] for q in questions], indent=2)}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    return json.loads(raw)


def get_used_topics():
    """
    Aggregate all previously used topics from session state.
    """
    used = set()
    for s in st.session_state.get("all_question_sets", []):
        for t in s.get("topics", []):
            used.add(t)
    return sorted(list(used))

# -------------------------------
# QUESTION GENERATION (Single GPT Call, Bilingual, Previous Sets)
# -------------------------------
if pdf_text:
    st.subheader(bilingual_text_ui("🧩 Step 1: Generate Short-Answer Questions"))

    num_questions = st.slider(bilingual_text_ui("Number of questions to generate:"),1, 10, key="num_questions")

    # Trigger generation if user clicks "Generate Questions" OR new set flag is set
    if st.button(bilingual_text_ui("⚡ Generate Questions")) or st.session_state.get("generate_new_set"):
        st.session_state["mode"] = "generate"
        st.session_state["question_set_id"] += 1
        
        # Clear the flag
        if st.session_state.get("generate_new_set"):
            st.session_state["generate_new_set"] = False
    
        # Use existing pdf_text from session_state
        pdf_text = st.session_state["pdf_text"]
    
        # Initialize progress bar
        progress = st.progress(0, text=bilingual_text_ui("Generating questions... please wait"))
        # -------------------------------
        # 1️⃣ Prompt GPT to generate all questions
        # -------------------------------
        used_topics = get_used_topics()
        prompt = f"""
You are an expert medical educator.
Generate {num_questions} concise short-answer questions and their answer keys based on the following content.
PREVIOUSLY USED TOPICS (avoid these unless no alternatives remain): {json.dumps(used_topics, indent=2)}
Your target audience is residents.

TASK:
1. Identify ALL major topics in the source material.
2. Exclude any topics listed above.
3. Randomly select {num_questions} DIFFERENT remaining topics.
4. Write ONE concise short-answer question per topic, structured like a Royal College of Physicians and Surgeons oral boards exam.

RULES:
- Ensure the questions are **proportional across the manual**, covering all major topics.
- Each question must test a DIFFERENT topic
- Do NOT generate multiple questions from the same subsection
- Do NOT follow the order of the manual
- Do NOT repeat themes from earlier question sets
- Focus on clinical relevance
- If surgical content exists, include presentation, approach, and management
- Questions should resemble Royal College oral board style

Return ONLY JSON in this format:
[
  {{"topic": "string", "question": "string", "answer_key": "string"}}
]

SOURCE TEXT:
{pdf_text}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini-2025-04-14",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```(?:json)?|```", "", raw).strip()
            all_items = json.loads(raw)

            # Normalize structure
            all_questions = [
                {
                    "topic": item.get("topic", "").strip(),
                    "question": item.get("question", "").strip(),
                    "answer_key": item.get("answer_key", "").strip()
                }
                for item in all_items
                if item.get("question") and item.get("answer_key")
            ]
            
            progress.progress(50, text=bilingual_text_ui("Questions generated. Translating..."))

        except Exception as e:
            st.error(bilingual_text_ui(f"⚠️ Question generation failed: {e}"))
            all_questions = []

        if all_questions:
            # -------------------------------
            # 2️⃣ Bilingual translation (batched)
            # -------------------------------
            bilingual_questions = []

            if target_language_name == "English":
                for q in all_questions:
                    bilingual_questions.append({
                        "question_en": q.get("question", ""),
                        "answer_key_en": q.get("answer_key", "")
                    })
            else:
                # Prepare batch text for GPT translation to minimize API calls
                batch_text = "\n\n".join(
                    [f"Q: {q.get('question','')}\nA: {q.get('answer_key','')}" for q in all_questions]
                )
                translation_prompt = f"""
Translate the following questions and answers into {target_language_name}.
Return JSON in the same order with this format:
[
  {{"question_translated": "string", "answer_key_translated": "string"}}
]

TEXT:
{batch_text}
"""
                try:
                    translation_resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": translation_prompt}],
                        temperature=0
                    )
                    raw_trans = translation_resp.choices[0].message.content.strip()
                    raw_trans = re.sub(r"```(?:json)?|```", "", raw_trans).strip()
                    translations = json.loads(raw_trans)
                except Exception:
                    translations = [{}] * len(all_questions)

                for q, t in zip(all_questions, translations):
                    bilingual_questions.append({
                        "question_en": q.get("question", ""),
                        "answer_key_en": q.get("answer_key", ""),
                        "question_translated": t.get("question_translated", ""),
                        "answer_key_translated": t.get("answer_key_translated", "")
                    })

            # -------------------------------
            # 3️⃣ Save to session state
            # -------------------------------
            st.session_state["questions"] = bilingual_questions
            st.session_state["user_answers"] = [""] * len(bilingual_questions)
            progress.progress(100, text=bilingual_text_ui("✅ Done! Questions ready."))

            # -------------------------------
            # 4️⃣ Store previous sets
            # -------------------------------
            if "all_question_sets" not in st.session_state:
                st.session_state["all_question_sets"] = []

            topics = [q.get("topic", "") for q in all_questions if q.get("topic")]
            
            st.session_state["all_question_sets"].append({
                "questions": bilingual_questions,
                "topics": topics,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })

            st.success(bilingual_text_ui(f"Generated {len(bilingual_questions)} representative questions successfully!"))

# -------------------------------
# USER ANSWERS (WITH AUDIO INPUT)
# -------------------------------
if st.session_state["questions"]:
    st.subheader(bilingual_text_ui("🧠 Step 2: Answer the Questions"))

    questions = st.session_state["questions"]

    if "user_answers" not in st.session_state or len(st.session_state["user_answers"]) != len(questions):
        st.session_state["user_answers"] = [""] * len(questions)

    for i, q in enumerate(questions):
        st.markdown(f"### Q{i+1}. {q.get('question_en', '')}")

        if target_language_name == "English":
            pass
        else:    
            st.markdown(f"**({target_language_name}):** {q.get('question_translated', '')}")

        st.markdown(bilingual_text_ui("🎤 Dictate your answer (you can record multiple times):"))
        qid = st.session_state["question_set_id"]
        audio_data = st.audio_input(
            "",
            key=f"audio_input_{qid}_{i}"
        )

        transcriptions_key = f"transcriptions_{i}"
        last_hash_key = f"last_audio_hash_{i}"
        if transcriptions_key not in st.session_state:
            st.session_state[transcriptions_key] = []
        if last_hash_key not in st.session_state:
            st.session_state[last_hash_key] = None

        dictated_text = ""
        
        if audio_data is not None:
            try:
                audio_bytes = audio_data.getvalue()
                audio_hash = hashlib.sha256(audio_bytes).hexdigest()
        
                if st.session_state.get(last_hash_key) == audio_hash:
                    st.info(bilingual_text_ui("This recording was already transcribed."), icon="ℹ️")
                else:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        tmp_file.write(audio_bytes)
                        tmp_path = tmp_file.name
        
                    with open(tmp_path, "rb") as f:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f
                        )
        
                    os.remove(tmp_path)
        
                    dictated_text = getattr(transcription, "text", "").strip()
        
                    if dictated_text:
                        # ✅ Append to CURRENT text area value
                        existing_text = st.session_state.get(f"ans_{i}", "").strip()
                        if existing_text:
                            new_text = f"{existing_text} {dictated_text}"
                        else:
                            new_text = dictated_text
        
                        st.session_state[f"ans_{qid}_{i}"] = new_text
                        st.session_state["user_answers"][i] = new_text
                        st.session_state[last_hash_key] = audio_hash
        
                        st.success(bilingual_text_ui("🎧 Dictation appended to your answer."), icon="🎤")
                    else:
                        st.warning(bilingual_text_ui("⚠️ Transcription returned empty text."))
        
            except Exception as e:
                st.error(bilingual_text_ui(f"⚠️ Audio transcription failed: {e}"))

        label = bilingual_text_ui("✏️ Your Answer:")
        key = f"ans_{qid}_{i}"  # unified key
        existing_text = st.session_state.get(key, "").strip()
        if existing_text:
            new_text = f"{existing_text} {dictated_text}"
        else:
            new_text = dictated_text
        
        st.session_state[key] = new_text
        st.session_state["user_answers"][i] = new_text
        
        current_text = st.text_area(label, height=80, key=key)

    user_answers = st.session_state.get("user_answers", [])

    # -------------------------------
    # EVALUATION
    # -------------------------------
    def score_short_answers(user_answers, questions):
        grading_prompt = f"""
You are a multilingual Royal College of Physicians and Surgeons oral boards examiner. You are examining the chief residents' answers to oral board exam questions. Score each short-answer response on a 0–2 scale, 0 being extremely deficient, 1 being acceptable, and 2 being exemplary.
The chief residents' answers can be provided in a different language from English.
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
                r["feedback_translated"] = safe_translate(r.get("feedback", ""), target_language_name)
                r["model_answer_translated"] = safe_translate(r.get("model_answer", ""), target_language_name)
            return results
        except Exception as e:
            st.error(bilingual_text_ui(f"⚠️ Scoring failed: {e}"))
            return []

    if st.button(bilingual_text_ui("🚀 Evaluate My Answers")):
        with st.spinner(bilingual_text_ui("Evaluating your answers...")):
            results = score_short_answers(user_answers, questions)
            st.session_state['evaluations'] = results

        if results:
            # -------------------------------
            # Compute total score
            # -------------------------------
            total_score = sum(r.get("score", 0) for r in results)
            max_score = len(results) * 2  # each question max 2 points
            percentage = round(total_score / max_score * 100, 1)
    
            st.success(bilingual_text_ui("✅ Evaluation complete!"))
    
            # -------------------------------
            # Display total score
            # -------------------------------
            st.markdown(f"### 🏆 {bilingual_text_ui('Total Score')}: {total_score}/{max_score} ({percentage}%)")
            
            st.success(bilingual_text_ui("✅ Evaluation complete!"))
            with st.expander(bilingual_text_ui("📊 Detailed Feedback")):
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

        if st.session_state.get("all_question_sets"):
            with st.expander(bilingual_text_ui("📚 Topics Covered So Far")):
                for used_topic_item in get_used_topics():
                    st.write(bilingual_text_ui(used_topic_item))

        # -------------------------------
        # Previous Question Sets Viewer
        # -------------------------------
        if st.session_state.get("all_question_sets"):
            st.subheader(bilingual_text_ui("📚 Retry Previous Question Sets"))
        
            prev_sets = {}
            for idx, s in enumerate(st.session_state["all_question_sets"]):
                set_questions = s.get("questions", [])
                preview_text = " | ".join(q.get("question_en", "") for q in set_questions[:3])
                if len(preview_text) > 100:
                    preview_text = preview_text[:100] + "..."
                label = f"Set {idx+1}: {preview_text} ({s.get('timestamp','')})"
                prev_sets[label] = s
        
            selected_label = st.selectbox(
                bilingual_text_ui("Select a previous question set to view:"),
                options=list(prev_sets.keys()),
                key="selected_prev_set"
            )
        
            if selected_label:
                selected_set = prev_sets[selected_label]
        
                with st.expander(bilingual_text_ui("📄 Preview Selected Question Set"), expanded=True):
                    for i, q in enumerate(selected_set["questions"]):
                        st.markdown(f"**Q{i+1}:** {q.get('question_en','')}")
                        if target_language_code != "en":
                            st.markdown(f"*({target_language_name})* {q.get('question_translated','')}")
                        st.markdown("---")

                if st.session_state.get("active_prev_label") != selected_label:
                    st.session_state["active_prev_label"] = selected_label
                    st.session_state["questions"] = selected_set["questions"]
                    st.session_state["user_answers"] = [""] * len(selected_set["questions"])
                    st.session_state["evaluations"] = []
                    st.session_state["question_set_id"] += 1
                    st.session_state["mode"] = "retry"
                    st.rerun()

    # -------------------------------
    # NEW BUTTON: Generate a new set of questions
    # -------------------------------
    if st.button(bilingual_text_ui("🔄 Generate a New Set of Questions")):
        st.session_state["questions"] = []
        st.session_state["user_answers"] = []
        st.session_state["evaluations"] = []
        st.session_state["generate_new_set"] = True
        st.session_state["question_set_id"] += 1
        st.rerun()
    
            
    url_instructors = "https://forms.gle/GdMqpvikomBRTcvJ6"
    url_students = "https://forms.gle/CWKRqptQhpdLKaj8A"
    st.write(bilingual_text_ui("Thank you for trying this multilingual short answer question generator! Please click on the following links to provide feedback to help improve this tool:"))
    st.markdown(bilingual_text_ui("Feedback form for instructors:"))
    st.markdown(url_instructors)
    st.markdown(bilingual_text_ui("Feedback form for students:"))
    st.markdown(url_students)
