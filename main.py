import streamlit as st
import os
from openai import OpenAI
import pdfplumber
from io import StringIO
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
from multi_file_ingestion import load_and_split_resume
from fpdf import FPDF


# Load environment variables
load_dotenv(override=True)
google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

# Streamlit config
st.set_page_config(page_title="🧠 Hirely Pro", layout="wide",page_icon="📄")

if "pdf_download_clicked" not in st.session_state:
    st.session_state.pdf_download_clicked = False


# Custom CSS Styling with animations
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background-color: black;
        }
        h1, h2, h3, h4 {
            color: black;
        }
        .stMarkdown, .stFileUploader, .stButton {
            margin-bottom: 1rem;
        }
        .highlight-box {
            padding: 1.2rem;
            background-color: black;
            border-left: 5px solid #0288d1;
            border-radius: 8px;
            margin-bottom: 1.2rem;
            animation: fadeIn 0.6s ease-in-out;
        }
        .center {
            display: flex;
            justify-content: center;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .upload-area {
            border: 2px dashed #90caf9;
            padding: 1.5rem;
            border-radius: 10px;
            background-color:black;
            animation: fadeIn 1s ease;
        }
    </style>
""", unsafe_allow_html=True)

# Header Banner
st.markdown("""
    <div class="center">
        <h1 style='font-size: 2.8rem; font-family:serif; color:#D2B48C'>🚀 Hirely Pro - Smart Resume Matcher</h1>
    </div>
    <p class='center' style='color:#9D825D; text-align:center; font-size: 1.2rem;font-weight:bold;font-family: Arial, Helvetica, monospace;font-style: italic;'>
        Analyze your resume using AI, compare with job descriptions, and get personalized improvement feedback!
    </p>
""", unsafe_allow_html=True)



# Tabs Placeholder
st.markdown("---")
st.markdown("""
<div class="highlight-box">
    <h4 style="color:#D2B48C;font-family:Papyrus,fantasy;">📌 Pro Tips to Maximize Your Results</h4>
    <ul style="line-height: 1.6; color:white; ">
        <li>🔄 Upload <strong>multiple resume versions</strong> to see which one aligns best with the job role.</li>
        <li>🎯 Use a <strong>tailored job description</strong> — the more detailed, the better the AI can match.</li>
        <li>💬 Get <strong>instant AI suggestions</strong> by asking specific improvement questions.</li>
        <li>📄 Download a <strong>personalized PDF report</strong> to track and improve your resume fit.</li>
    </ul>
</div>
""", unsafe_allow_html=True)



def clean_unicode(text):
    return (
        text.encode("ascii", "ignore")
            .decode("ascii")
            .replace("•", "-")
            .replace("–", "-")
            .replace("—", "-")
    )


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

# Prompt builder
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

# Skill gap analysis
def extract_skill_gap(resume_text, jd_text):
    prompt = f"""
You are an expert HR AI. Find out which skills are missing in the resume based on the job description.

Resume:
{resume_text}

Job Description:
{jd_text}

List the missing skills only as bullet points.
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
        return "N/A"


#AI Chat assistant for Resume Feedback

def answer_resume_query(resume_text, jd_text, user_question, model="groq"):
    prompt = f"""
You are an AI career assistant. A candidate has asked a question about improving their resume based on the job description.

Resume:
{resume_text}

Job Description:
{jd_text}

Question:
{user_question}

Answer in a clear, personalized, helpful tone.
"""
    try:
        if model == "groq":
            groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
            response = groq.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": "You are a professional resume coach."},
                    {"role": "user", "content": prompt}
                ]
            )
        else:
            gemini = OpenAI(api_key=google_api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            response = gemini.chat.completions.create(
                model="gemini-2.0-flash",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"


# Resume improvement suggestions
def suggest_improvements(resume_text, jd_text):
    prompt = f"""
You are a career advisor AI. Based on the following resume and job description, provide 3 personalized suggestions to improve the resume to better match the job.

Resume:
{resume_text}
Job Description:
{jd_text}

List only 3 improvement suggestions.
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"⚠️ Error: {e}")

        return "N/A"


# Resume summary
def generate_summary(resume_text):
    prompt = f"""
Summarize the resume in 3 short bullet points. Highlight top achievements and strengths.

Resume:
{resume_text}
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"⚠️ Error: {e}")

        return "N/A"


# Get match scores

def get_google_match(prompt):
    try:
        gemini = OpenAI(api_key=google_api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        response = gemini.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[{"role": "user", "content": prompt}]
        )
        digits = ''.join(filter(str.isdigit, response.choices[0].message.content))
        return min(int(digits), 100) if digits else 0
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
        return 0

def get_groq_match(prompt):
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        digits = ''.join(filter(str.isdigit, response.choices[0].message.content))
        return min(int(digits), 100) if digits else 0
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
        return 0

def generate_pdf(candidate_name, avg_score, scores, summary, skills, suggestions):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Hirely Pro - Resume Match Report", ln=True, align="C")

    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Candidate: {clean_unicode(candidate_name)}", ln=True)
    pdf.cell(200, 10, txt=f"Average Match Score: {avg_score}%", ln=True)

    pdf.ln(5)
    pdf.cell(200, 10, txt="Model Scores:", ln=True)
    for model, score in scores.items():
        pdf.cell(200, 10, txt=f"{model}: {score}%", ln=True)

    pdf.ln(5)
    pdf.multi_cell(0, 10, f"Summary:\n{clean_unicode(summary)}")
    pdf.ln(2)
    pdf.multi_cell(0, 10, f"Missing Skills:\n{clean_unicode(skills)}")
    pdf.ln(2)
    pdf.multi_cell(0, 10, f"Suggestions:\n{clean_unicode(suggestions)}")

    output_path = "temp_files/report.pdf"
    pdf.output(output_path)
    return output_path



# ==== UI with Tabs ====
tab1, tab2 = st.tabs(["📁 Upload Files", "📊 View Results"])

with tab1:
    st.markdown("<h1 style='color:#D2B48C; font-size:2rem; font-family:Papyrus,fantasy;font-style:italic;'>📄 Upload Resume & Job Description</h1>", unsafe_allow_html=True)


    resume_files = st.file_uploader("📄 Upload Resume(s) — Upload 2 or 3 versions", type=["pdf", "txt"], accept_multiple_files=True)

    jd_file = st.file_uploader("📝 Upload Job Description", type=None)

    if st.button("🔍 Analyze Fit" , key="analyze_button_tab1") and resume_files and jd_file:
        with st.spinner("Analyzing..."):
            os.makedirs("temp_files", exist_ok=True)

            # Process JD
            jd_path = os.path.join("temp_files", jd_file.name)
            with open(jd_path, "wb") as f:
                f.write(jd_file.getbuffer())
            jd_docs = load_and_split_resume(jd_path)
            jd_text = "\n".join([doc.page_content for doc in jd_docs])

            all_scores = {}
            resume_details = []

            for resume_file in resume_files:
                resume_path = os.path.join("temp_files", resume_file.name)
                with open(resume_path, "wb") as f:
                    f.write(resume_file.getbuffer())
                resume_docs = load_and_split_resume(resume_path)
                resume_text = "\n".join([doc.page_content for doc in resume_docs])

                prompt = build_prompt(resume_text, jd_text)

                candidate_name = extract_candidate_name(resume_text)
                summary = generate_summary(resume_text)
                skills_missing = extract_skill_gap(resume_text, jd_text)
                suggestions = suggest_improvements(resume_text, jd_text)

                scores = {
                    "Google Gemini": get_google_match(prompt),
                    "Groq LLaMA3": get_groq_match(prompt),
                }

                avg_score = round(sum(scores.values()) / len(scores), 2)

                all_scores[resume_file.name] = {
                    "Candidate": candidate_name,
                    "Avg": avg_score,
                    "Scores": scores,
                    "Summary": summary,
                    "Skills": skills_missing,
                    "Suggestions": suggestions
                }

            st.session_state.all_scores = all_scores
            st.success("✅ All Resumes Analyzed! Go to '📊 View Results' tab.")


with tab2:
    st.header("📊 Match Result Overview")

    if "all_scores" in st.session_state:
        all_scores = st.session_state.all_scores
        best_resume = max(all_scores.items(), key=lambda x: x[1]["Avg"])

        st.subheader("📈 Best Resume Recommendation")
        st.success(f"🏆 {best_resume[0]} is the best match with {best_resume[1]['Avg']}% score.")

        resume_df = pd.DataFrame([
            {
                "Resume File": name,
                "Candidate": data["Candidate"],
                "Avg Score": data["Avg"],
                **data["Scores"]
            } for name, data in all_scores.items()
        ])

        st.dataframe(resume_df, use_container_width=True)

        fig = px.bar(resume_df, x="Resume File", y="Avg Score", text="Avg Score", color="Resume File")
        st.plotly_chart(fig, use_container_width=True)

        # Show individual resume details
        selected_resume = st.selectbox("📝 Select a Resume to View Details", list(all_scores.keys()))
        res = all_scores[selected_resume]

        st.markdown(f"**👤 Candidate:** {res['Candidate']}")
        st.markdown(f"**📈 Avg. Score:** {res['Avg']}%")
        st.markdown("---")
        st.markdown(f"**🧠 Summary:**\n{res['Summary']}")
        st.markdown("---")
        st.markdown(f"**📌 Missing Skills:**\n{res['Skills']}")
        st.markdown("---")
        st.markdown(f"**💡 Suggestions:**\n{res['Suggestions']}")

        # PDF Download (independent)
        st.markdown("### 📄 Download PDF")
        if st.button("📥 Generate and Download PDF for Selected Resume"):
            pdf_path = generate_pdf(
                res['Candidate'],
                res['Avg'],
                res['Scores'],
                res['Summary'],
                res['Skills'],
                res['Suggestions']
            )
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Click to Download",
                    data=f,
                    file_name=f"{selected_resume}_report.pdf",
                    mime="application/pdf"
            )

        st.markdown("---")
        st.subheader("💬 Ask AI About This Resume")

        # Always-visible AI Chat Form
        with st.form("chat_form"):
            user_query = st.text_area("Ask anything about improving this resume 👇", placeholder="E.g. How can I tailor this resume better for the job?")
            selected_model = st.selectbox("Model to use", ["groq", "gemini"])
            submit_chat = st.form_submit_button("🔍 Ask")

        if submit_chat and user_query:
            with st.spinner("Thinking..."):
                ai_response = answer_resume_query(
                    resume_text="\n".join([doc.page_content for doc in load_and_split_resume(f"temp_files/{selected_resume}")]),
                    jd_text="\n".join([doc.page_content for doc in load_and_split_resume(f"temp_files/{jd_file.name}")]),
                    user_question=user_query,
                    model=selected_model
                )
            st.markdown("### 💡 AI Feedback")
            st.success(ai_response)