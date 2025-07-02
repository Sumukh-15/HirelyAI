import streamlit as st
import os
from openai import OpenAI
import pdfplumber
from io import StringIO
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
from multi_file_ingestion import load_and_split_resume
import plotly.graph_objects as go
from fpdf import FPDF
import re
from firebase_config import auth
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Load environment variables
load_dotenv(override=True)

if "user" not in st.session_state:
    st.session_state.user = None

def login():
    with st.form("login_form"):
        st.subheader("🔐 Login to Save Your Reports")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state.user = user
                st.success("✅ Logged in!")
                st.session_state.logged_in = True
                st.session_state.user_email = email
            except:
                st.error("❌ Login Failed. Try Again.")

def signup():
    with st.form("signup_form"):
        st.subheader("🆕 New? Sign Up")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Create Account")
        if submitted:
            try:
                auth.create_user_with_email_and_password(email, password)
                st.success("✅ Account created! Please login.")
            except:
                st.error("❌ Signup failed. Try again.")

if not st.session_state.user:
    login()
    st.markdown("---")
    signup()
    st.stop()

google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

# Streamlit config
st.set_page_config(page_title="🧠 Hirely Pro", layout="wide", page_icon="📄")

if "pdf_download_clicked" not in st.session_state:
    st.session_state.pdf_download_clicked = False


# Custom CSS Styling with animations
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# Header Banner
st.markdown(
    """
    <div class="center">
        <h1 style='font-size: 2.8rem; font-family:serif; color:#D2B48C'>🚀 Hirely Pro - Smart Resume Matcher</h1>
    </div>
    <p class='center' style='color:#9D825D; text-align:center; font-size: 1.2rem;font-weight:bold;font-family: Arial, Helvetica, monospace;font-style: italic;'>
        Analyze your resume using AI, compare with job descriptions, and get personalized improvement feedback!
    </p>
""",
    unsafe_allow_html=True,
)


# Tabs Placeholder
st.markdown("---")
st.markdown(
    """
<div class="highlight-box">
    <h4 style="color:#D2B48C;font-family:Papyrus,fantasy;">📌 Pro Tips to Maximize Your Results</h4>
    <ul style="line-height: 1.6; color:white; ">
        <li>🔄 Upload <strong>multiple resume versions</strong> to see which one aligns best with the job role.</li>
        <li>🎯 Use a <strong>tailored job description</strong> — the more detailed, the better the AI can match.</li>
        <li>💬 Get <strong>instant AI suggestions</strong> by asking specific improvement questions.</li>
        <li>📄 Download a <strong>personalized PDF report</strong> to track and improve your resume fit.</li>
    </ul>
</div>
""",
    unsafe_allow_html=True,
)


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
            return "\n".join(
                [page.extract_text() for page in pdf.pages if page.extract_text()]
            )
    else:
        return StringIO(file.read().decode("utf-8")).read()

def fetch_jobs_from_indeed(keywords, location="India", max_results=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.indeed.com/jobs?q={keywords}&l={location}"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    job_cards = soup.find_all("a", class_="tapItem", limit=max_results)
    job_list = []

    for job in job_cards:
        title_tag = job.find("h2", class_="jobTitle")
        if title_tag:
            title = title_tag.text.strip()
            link = "https://www.indeed.com" + job.get("href", "")
            job_list.append({"title": title, "link": link})

    return job_list

def send_email_alert(to_email, subject, message):
    sender_email = "your_email@example.com"  # Replace with your email
    sender_password = "your_password"        # Replace with your email app password

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(message, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

def trigger_job_alerts(resume_text, avg_score, user_email):
    if avg_score >= 80:
        # Derive keywords from resume (simplified)
        keywords = " ".join(resume_text.lower().split()[:5])  # first few keywords

        jobs = fetch_jobs_from_indeed(keywords)

        if jobs:
            message = f"Based on your resume (Match Score: {avg_score}%), here are some jobs:\n\n"
            for job in jobs:
                message += f"- {job['title']}\n{job['link']}\n\n"

            send_email_alert(
                user_email,
                subject="🚨 Job Alert: Resume Match Found!",
                message=message
            )
            print("✅ Email sent!")
        else:
            print("No matching jobs found.")
    else:
        print("⚠️ Match score < 80%. Skipping alert.")


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
                {
                    "role": "system",
                    "content": "You are a professional resume evaluator.",
                },
                {"role": "user", "content": prompt},
            ],
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
            model="llama3-8b-8192", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error:", e)
        return "N/A"



def categorize_and_match_keywords(resume_text, jd_text):
    prompt = f"""
You're an expert resume analyzer. Categorize matched vs missing keywords across these 4 categories:
- Skills
- Experience
- Tools & Technologies
- Education

Instructions:
1. Analyze the resume and job description carefully.
2. Use only relevant terms in each category.
3. Do NOT include names or unrelated text as matches.
4. For "Education", only include degrees, majors, institutions, and certifications.
5. For "Experience", focus on years, roles, industries, and achievements.

Resume:
{resume_text}

Job Description:
{jd_text}

Respond in this format exactly:

📁 Skills
✅ Matched:
- ...
❌ Missing:
- ...

📁 Experience
✅ Matched:
❌ Missing:

📁 Tools & Technologies
✅ Matched:
❌ Missing:

📁 Education
✅ Matched:
❌ Missing:
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        output = response.choices[0].message.content.strip()

        # Helper to extract lists under each ✅/❌
        def extract_items(section_name, block):
            matched = re.findall(r"✅ Matched:\s*(.*?)\n❌", block, re.DOTALL)
            missing = re.findall(r"❌ Missing:\s*(.*?)(\n📁|\Z)", block, re.DOTALL)

            def parse_lines(raw):
                return [line.strip("- ").strip() for line in raw.strip().splitlines() if line.strip()]

            return {
                "matched": parse_lines(matched[0]) if matched else [],
                "missing": parse_lines(missing[0][0]) if missing else [],
            }

        # Extract all 4 sections
        categories = ["Skills", "Experience", "Tools", "Education"]
        result = {}
        for cat in categories:
            pattern = rf"📁 {cat}(.+?)(?=(📁|$))"
            match = re.search(pattern, output, re.DOTALL)
            if match:
                result[cat] = extract_items(cat, match.group(1))
            else:
                result[cat] = {"matched": [], "missing": []}

        return result

    except Exception as e:
        print("Parsing error:", e)
        return {}



# AI Chat assistant for Resume Feedback


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
            groq = OpenAI(
                api_key=groq_api_key, base_url="https://api.groq.com/openai/v1"
            )
            response = groq.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional resume coach.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        else:
            gemini = OpenAI(
                api_key=google_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            response = gemini.chat.completions.create(
                model="gemini-2.0-flash", messages=[{"role": "user", "content": prompt}]
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
            model="llama3-8b-8192", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error:", e)
        return "N/A"

def analyze_linkedin_profile(profile_text):
    prompt = f"""
You are a professional LinkedIn optimization expert.

Analyze the following LinkedIn profile content and respond with:
1. A short summary of the profile
2. 3 personalized suggestions to improve it
3. Highlight any missing key elements (e.g. skills, achievements, metrics)

Format:
**📝 Summary**:
<short summary>

**✅ Suggestions**:
- Suggestion 1
- Suggestion 2
- Suggestion 3

**⚠️ Missing Elements**:
- Item 1
- Item 2

LinkedIn Content:
{profile_text}
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"


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
            model="llama3-8b-8192", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error:", e)
        return "N/A"

def get_score_breakdown(resume_text, jd_text):
    prompt = f"""
You're an expert recruiter AI. Analyze this resume vs job description and give a score breakdown (0-100) for:

- Skills match
- Experience alignment
- Education relevance
- Tone/language fit

Respond ONLY as valid JSON in this format:
{{
  "Skills": 87,
  "Experience": 75,
  "Education": 65,
  "Tone": 80
}}

Resume:
{resume_text}

Job Description:
{jd_text}
"""
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        print("⚠️ Breakdown Error:", e)
        return None



def recommend_jobs_from_resume(resume_text):
    prompt = f"""
You are an AI career assistant. A user has uploaded their resume but does not have a job description.

Based on the resume, suggest 3 to 5 job roles they are most suited for, with a 1-line description each.

Format the output as:

- **Job Title**: short description

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
        return f"⚠️ Could not generate recommendations: {e}"


# Get match scores

def get_google_match(prompt):
    try:
        gemini = OpenAI(
            api_key=google_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        response = gemini.chat.completions.create(
            model="gemini-2.0-flash", messages=[{"role": "user", "content": prompt}]
        )
        digits = "".join(filter(str.isdigit, response.choices[0].message.content))
        return min(int(digits), 100) if digits else 0
    except:
        return 0


def get_groq_match(prompt):
    try:
        groq = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = groq.chat.completions.create(
            model="llama3-70b-8192", messages=[{"role": "user", "content": prompt}]
        )
        digits = "".join(filter(str.isdigit, response.choices[0].message.content))
        return min(int(digits), 100) if digits else 0
    except:
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

def send_job_alert_email(recipient_email, job_title, job_link):
    sender_email = "your_email@example.com"
    sender_password = "your_password"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🚀 New Job Match Found!"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    html_content = f"""
    <html>
        <body>
            <p>Hi there! 👋</p>
            <p>A job matching your resume has been found:</p>
            <b>{job_title}</b><br>
            👉 <a href="{job_link}">View Job Posting</a>
        </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Email sending failed: {e}")


def check_and_send_job_alerts():
    sample_jobs = [
        {"title": "AI Research Intern", "link": "https://example.com/job1"},
        {"title": "Python Developer", "link": "https://example.com/job2"},
    ]

    for candidate in st.session_state.get("alert_candidates", []):
        for job in sample_jobs:
            # You can improve this with actual scraping/matching logic
            send_job_alert_email(candidate["email"], job["title"], job["link"])

def get_resume_level(score):
    if score < 50:
        return "🥉 Beginner"
    elif score < 70:
        return "🥈 Intermediate"
    elif score < 85:
        return "🥇 Expert"
    else:
        return "🏆 Master"



# ==== UI with Tabs ====
if "logged_in" in st.session_state and st.session_state.logged_in:
    # Show the rest of your app
    tab1, tab2, tab3, tab4, tab5, tab6= st.tabs(["📁 Upload Files", "📊 View Results", "🔗 LinkedIn Optimizer", "📚 History", "📄 AI Resume Templates", "📬 Alerts & Settings"])

    with tab1:
        st.markdown(
            "<h1 style='color:#D2B48C; font-size:2rem; font-family:Papyrus,fantasy;font-style:italic;'>📄 Upload Resume & Job Description</h1>",
            unsafe_allow_html=True,
        )

        resume_files = st.file_uploader(
            "📄 Upload Resume(s) — Upload 2 or 3 versions",
            type=["pdf", "txt"],
            accept_multiple_files=True,
        )

        jd_file = st.file_uploader("📝 Upload Job Description", type=None)

        if resume_files:
            if jd_file:
                if (
                    st.button("🔍 Analyze Fit", key="analyze_button_tab1")
                ):
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
                            original_resume_text = resume_text  # Save unmodified resume


                            prompt = build_prompt(resume_text, jd_text)

                            candidate_name = extract_candidate_name(resume_text)
                            summary = generate_summary(resume_text)
                            skills_missing = extract_skill_gap(resume_text, jd_text)
                            suggestions = suggest_improvements(resume_text, jd_text)
                            score_breakdown = get_score_breakdown(resume_text, jd_text)
                            keyword_analysis = categorize_and_match_keywords(resume_text, jd_text)


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
                                "Suggestions": suggestions,
                                "KeywordMatch": keyword_analysis,
                                "ResumeText": original_resume_text,
                                "Breakdown": score_breakdown,

                            }

                            # Save to Firestore if logged in
                            if st.session_state.user:
                                try:
                                    firestore.collection("hirely_reports").add({
                                        "user_email": st.session_state.user["email"],
                                        "resume_name": resume_file.name,
                                        "timestamp": firestore.SERVER_TIMESTAMP,
                                        "candidate_name": candidate_name,
                                        "avg_score": avg_score,
                                        "scores": scores,
                                        "summary": summary,
                                        "skills_missing": skills_missing,
                                        "suggestions": suggestions,
                                        })
                                except Exception as e:
                                    st.warning("⚠️ Could not save to cloud: " + str(e))


                        st.session_state.all_scores = all_scores
                        st.success("✅ All Resumes Analyzed! Go to '📊 View Results' tab.")

            else:
                if st.button("🤖 Suggest Jobs from Resume Only", key="resume_only_button") and resume_files:
                    with st.spinner("Analyzing your resume..."):
                        os.makedirs("temp_files", exist_ok=True)

                        for resume_file in resume_files:
                            resume_path = os.path.join("temp_files", resume_file.name)
                            with open(resume_path, "wb") as f:
                                f.write(resume_file.getbuffer())

                            resume_docs = load_and_split_resume(resume_path)
                            resume_text = "\n".join([doc.page_content for doc in resume_docs])
                            job_suggestions = recommend_jobs_from_resume(resume_text)

                            st.markdown("### 🧲 Suggested Jobs Based on Your Resume")
                            st.info(job_suggestions)
                            st.markdown("---")


    with tab2:
        st.header("📊 Match Result Overview")

        if "all_scores" in st.session_state:
            all_scores = st.session_state.all_scores
            best_resume = max(all_scores.items(), key=lambda x: x[1]["Avg"])

            st.subheader("📈 Best Resume Recommendation")
            st.success(
                f"🏆 `{best_resume[0]}` is the best match with `{best_resume[1]['Avg']}%` score."
            )

            resume_df = pd.DataFrame(
                [
                    {
                        "Resume File": name,
                        "Candidate": data["Candidate"],
                        "Avg Score": data["Avg"],
                        **data["Scores"],
                 }
                    for name, data in all_scores.items()
                ]
            )

            st.dataframe(resume_df, use_container_width=True)

            fig = px.bar(
                resume_df,
                x="Resume File",
                y="Avg Score",
                text="Avg Score",
                color="Resume File",
            )
            st.plotly_chart(fig, use_container_width=True)

            # Show individual resume details
            selected_resume = st.selectbox(
                "📝 Select a Resume to View Details", list(all_scores.keys())
            )
            res = all_scores[selected_resume]
            st.markdown("### ✍️ Edit Resume Text")

            edited_resume_text = st.text_area(
                "Modify your resume content below before re-analysis 👇",
                value=res["ResumeText"],
                height=300
            )

            if st.button("♻️ Re-analyze Edited Resume"):
                with st.spinner("Re-evaluating..."):
                    prompt = build_prompt(edited_resume_text, jd_text)

                    # Re-run the AI pipeline
                    updated_summary = generate_summary(edited_resume_text)
                    updated_skills = extract_skill_gap(edited_resume_text, jd_text)
                    updated_suggestions = suggest_improvements(edited_resume_text, jd_text)
                    updated_keywords = categorize_and_match_keywords(edited_resume_text, jd_text)

                    updated_scores = {
                        "Google Gemini": get_google_match(prompt),
                        "Groq LLaMA3": get_groq_match(prompt),
                    }
                    updated_avg = round(sum(updated_scores.values()) / len(updated_scores), 2)

                    # Update session state for this resume
                    res.update({
                        "ResumeText": edited_resume_text,
                        "Avg": updated_avg,
                        "Scores": updated_scores,
                        "Summary": updated_summary,
                        "Skills": updated_skills,
                        "Suggestions": updated_suggestions,
                        "KeywordMatch": updated_keywords,
                    })

                    # 🔔 Trigger email alerts if score ≥ 80%
                    user_email = "user@example.com"  # Replace with actual email (from login or form)
                    trigger_job_alerts(
                        resume_text=res["ResumeText"],
                        avg_score=res["Avg"],
                        user_email=user_email
                )


                    st.success("✅ Resume re-analyzed with updated content!")



            st.markdown(f"**👤 Candidate:** `{res['Candidate']}`")
            st.markdown(f"**📈 Avg. Score:** `{res['Avg']}%`")
            level = get_resume_level(res['Avg'])
            st.markdown(f"**🎮 Resume Level:** `{level}`")

            if res['Avg'] < 85:
                st.info("💡 Tip: Improve your resume to reach '🏆 Master' level!")

            st.markdown("---")
            st.markdown(f"**🧠 Summary:**\n{res['Summary']}")
            st.markdown("---")
            st.markdown(f"**📌 Missing Skills:**\n{res['Skills']}")
            st.markdown("---")
            st.markdown(f"**💡 Suggestions:**\n{res['Suggestions']}")

            if res.get("Breakdown"):
                st.markdown("### 📊 Category-wise Score Breakdown")

                radar_data = pd.DataFrame({
                    "Category": list(res["Breakdown"].keys()),
                    "Score": list(res["Breakdown"].values())
                })

                radar_fig = go.Figure()
                radar_fig.add_trace(go.Scatterpolar(
                    r=radar_data["Score"],
                    theta=radar_data["Category"],
                    fill='toself',
                    name='Score Breakdown',
                    line_color='gold'
             ))

                radar_fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100])
                    ),
                    showlegend=False,
                    height=400
                )

                st.plotly_chart(radar_fig, use_container_width=True)


            if res.get("KeywordMatch"):
                st.markdown("### 🔍 ATS Keyword Match Breakdown")

                categories = ["Skills", "Tools", "Experience", "Education"]
                for cat in categories:
                    data = res["KeywordMatch"].get(cat, {})
                    matched = data.get("matched", [])
                    missing = data.get("missing", [])

                    st.markdown(f"#### 📁 {cat}")
                    cols = st.columns(2)

                    with cols[0]:
                        st.markdown("✅ **Matched:**")
                        if matched:
                            st.markdown(", ".join(f"`{item}`" for item in matched))
                        else:
                            st.markdown("*None*")

                    with cols[1]:
                        st.markdown("❌ **Missing:**")
                        if missing:
                            st.markdown(", ".join(f"`{item}`" for item in missing))
                        else:
                            st.markdown("*None*")

                    st.markdown("---")


            # PDF Download (independent)
            st.markdown("### 📄 Download PDF")
            if st.button("📥 Generate and Download PDF for Selected Resume"):
                pdf_path = generate_pdf(
                    res["Candidate"],
                    res["Avg"],
                    res["Scores"],
                    res["Summary"],
                    res["Skills"],
                    res["Suggestions"],
                )
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Click to Download",
                        data=f,
                        file_name=f"{selected_resume}_report.pdf",
                        mime="application/pdf",
                    )

            st.markdown("---")

            st.subheader("💬 Ask AI About This Resume")

            # Always-visible AI Chat Form
            with st.form("chat_form"):
                user_query = st.text_area(
                    "Ask anything about improving this resume 👇",
                    placeholder="E.g. How can I tailor this resume better for the job?",
                )
                selected_model = st.selectbox("Model to use", ["groq", "gemini"])
                submit_chat = st.form_submit_button("🔍 Ask")

            if submit_chat and user_query:
                with st.spinner("Thinking..."):
                    ai_response = answer_resume_query(
                        resume_text="\n".join(
                            [
                                doc.page_content
                                for doc in load_and_split_resume(
                                    f"temp_files/{selected_resume}"
                                )
                            ]
                        ),
                        jd_text="\n".join(
                            [
                                doc.page_content
                                for doc in load_and_split_resume(
                                    f"temp_files/{jd_file.name}"
                                )
                            ]
                        ),
                        user_question=user_query,
                        model=selected_model,
                    )
                st.markdown("### 💡 AI Feedback")
                st.success(ai_response)


    with tab3:
        st.header("🔗 LinkedIn Profile Optimizer")
        linkedin_text = st.text_area("Paste your LinkedIn profile content here 👇", height=250)

        if st.button("🧠 Analyze LinkedIn Profile"):
            with st.spinner("Analyzing..."):
                analysis = analyze_linkedin_profile(linkedin_text)
                st.markdown("### 📋 Profile Feedback")
                st.success(analysis)

    with tab4:
        st.header("📚 My Resume History")

        if st.session_state.user:
            try:
                docs = firestore.collection("hirely_reports")\
                    .where("user_email", "==", st.session_state.user["email"])\
                    .order_by("timestamp", direction="DESCENDING")\
                    .limit(10).stream()

                for doc in docs:
                    data = doc.to_dict()
                    st.markdown(f"#### 📄 {data['resume_name']}")
                    st.markdown(f"**👤 Candidate:** {data['candidate_name']}")
                    st.markdown(f"**📊 Score:** {data['avg_score']}%")
                    st.markdown(f"**📌 Missing Skills:** {data['skills_missing']}")
                    st.markdown(f"**💡 Suggestions:** {data['suggestions']}")
                    st.markdown("---")
            except:
                st.warning("⚠️ Error loading history.")


    with tab5:
        st.header("📄 Generate Resume from JD with AI ✨")

        jd_input = st.text_area(
            "Paste the Job Description here",
            placeholder="Enter or paste the full JD text here...",
            height=300
        )

        template_options = ["Modern Minimal", "Bold Professional", "Creative Designer"]
        template_choice = st.selectbox("🧾 Choose a Resume Template", template_options)

        if st.button("🪄 Generate Resume with AI"):
            with st.spinner("Crafting a tailored resume..."):

                # Call your existing AI logic
                ai_summary = generate_summary(jd_input)
                ai_skills = extract_skill_gap("", jd_input)  # no resume given
                ai_suggestions = suggest_improvements("", jd_input)

                filled_resume = f"""
    📌 **Summary**  
    {ai_summary}

    📌 **Skills**  
    {', '.join(ai_skills)}

    📌 **Suggestions to Stand Out**  
    {ai_suggestions}
            """

                st.markdown("### 🧾 AI-Filled Resume Preview")
                st.markdown(filled_resume)

                # Save PDF using fpdf
                from fpdf import FPDF

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                for line in filled_resume.split("\n"):
                    pdf.multi_cell(0, 10, txt=line, align="L")

                resume_path = "ai_generated_resume.pdf"
                pdf.output(resume_path)

                with open(resume_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Resume PDF",
                        data=f,
                        file_name="AI_Generated_Resume.pdf",
                        mime="application/pdf"
                        )


    with tab6:
        st.header("📬 Alerts & Settings")

        st.markdown("Enable this if you want to receive job alert emails when a good match is found.")

        if st.button("📬 Enable Job Alert Emails"):
            st.success("📧 You will now receive job alerts for matching jobs.")
            # Scheduler is running in background

else:
    st.warning("🔐 Please login to access the app.")

