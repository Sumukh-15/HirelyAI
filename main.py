import streamlit as st
import os
from openai import OpenAI
import pdfplumber
from io import StringIO
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
from multi_file_ingestion import load_and_split_resume

# Load environment variables
load_dotenv(override=True)
google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")


# Streamlit config
st.set_page_config(page_title="🧠 Hirely AI", layout="wide")

# CSS styling
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 1rem;
        }
        .stMarkdown, .stFileUploader {
            margin-bottom: 1rem;
        }
        .metric-box {
            display: flex;
            justify-content: space-around;
            margin-top: 1rem;
        }
        .center {
            display: flex;
            justify-content: center;
            margin-bottom: 1rem;
        }
    </style>
""", unsafe_allow_html=True)

# Extract PDF or text
def extract_text(file):
    if file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    else:
        return StringIO(file.read().decode("utf-8")).read()

# Candidate name extractor using Groq
def extract_candidate_name(resume_text):
    prompt = f"""
You are an AI assistant specialized in resume analysis.

Your task is to get full name of the candidate from the resume.

Resume:
{resume_text}

Respond with only the candidate's full name.
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a professional resume evaluator."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Unknown"

# Build common prompt
def build_prompt(resume_text, jd_text):
    return f"""
You are an AI assistant specialized in resume analysis and recruitment.
Analyze the given resume and compare it with the job description.

Provide a match percentage between 0 and 100.

Resume:
{resume_text}

Job Description:
{jd_text}

Respond with only the match percentage as an integer.
""".strip()

# Gemini
def get_google_match(prompt):
    try:
        gemini = OpenAI(api_key=google_api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        response = gemini.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        digits = ''.join(filter(str.isdigit, content))
        return min(int(digits), 100) if digits else 0
    except Exception as e:
        st.error(f"Google Gemini API Error: {e}")
        return 0

# Groq
def get_groq_match(prompt):
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        digits = ''.join(filter(str.isdigit, content))
        return min(int(digits), 100) if digits else 0
    except Exception as e:
        st.error(f"Groq API Error: {e}")
        return 0


# ==== UI with Tabs ====
tab1, tab2 = st.tabs(["📁 Upload Files", "📊 View Results"])

with tab1:
    st.header("📂 Upload Resume & Job Description")

    resume_file = st.file_uploader("📄 Upload Resume", type=None)
    jd_file = st.file_uploader("📝 Upload Job Description", type=None)

    if st.button("🔍 Analyze Fit") and resume_file and jd_file:
        with st.spinner("Analyzing..."):
            os.makedirs("temp_files", exist_ok=True)

            resume_path = os.path.join("temp_files", resume_file.name)
            with open(resume_path, "wb") as f:
                f.write(resume_file.getbuffer())
            resume_docs = load_and_split_resume(resume_path)
            resume_text = "\n".join([doc.page_content for doc in resume_docs])

            jd_path = os.path.join("temp_files", jd_file.name)
            with open(jd_path, "wb") as f:
                f.write(jd_file.getbuffer())
            jd_docs = load_and_split_resume(jd_path)
            jd_text = "\n".join([doc.page_content for doc in jd_docs])

            candidate_name = extract_candidate_name(resume_text)
            prompt = build_prompt(resume_text, jd_text)

            scores = {
                "Google Gemini": get_google_match(prompt),
                "Groq LLaMA3": get_groq_match(prompt),
            }

            st.session_state.scores = scores
            st.session_state.candidate_name = candidate_name
            st.session_state.avg_score = round(sum(scores.values()) / len(scores), 2)
            st.success("✅ Analysis Complete! Go to '📊 View Results' tab.")

with tab2:
    st.header("📊 Match Result Overview")

    if "scores" in st.session_state:
        scores = st.session_state.scores
        avg_score = st.session_state.avg_score
        name = st.session_state.candidate_name

        df = pd.DataFrame(list(scores.items()), columns=["Model", "Match %"]).sort_values("Match %", ascending=False)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📋 Candidate Summary")
            st.markdown(f"**👤 Name:** `{name}`")
            st.markdown(f"**📈 Average Score:** `{avg_score}%`")

        with col2:
            st.metric(label="📊 Avg. Match %", value=f"{avg_score:.2f}%", delta=None)

        st.markdown("---")

        # Table
        st.subheader("🔢 Model-wise Results")
        st.dataframe(df, use_container_width=True)

        # Chart
        st.subheader("📈 Visual Comparison")
        fig = px.bar(df, x="Model", y="Match %", text="Match %", color="Model",
                     title="Resume Fit Score by Model", height=400)
        fig.update_traces(textposition='outside')
        fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⬅️ Please upload files and run analysis first from the 'Upload Files' tab.")
