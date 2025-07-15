
import streamlit as st
import openai
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
import io

# Set your OpenAI API key (replace with secret management in real apps)
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="AI Grader Assistant", layout="wide")
st.title("📚 AI Student Grading Assistant")

# Helper: extract text from DOCX
def extract_text_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

# Helper: extract text from PDF
def extract_text_pdf(file):
    pdf = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    return text

# AI Grading Function
def grade_answer(student_answer, correct_answer, question_number):
    prompt = f"""
You are a teacher. Grade the following student answer to Question {question_number}.

Correct Answer:
{correct_answer}

Student's Answer:
{student_answer}

Give the student a score out of 10, and explain why you gave that score. Be kind and educational.
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# Uploads
st.sidebar.header("📤 Upload Files")
student_file = st.sidebar.file_uploader("Upload Student Answers (.docx or .pdf)", type=["docx", "pdf"])
answer_key_file = st.sidebar.file_uploader("Upload Answer Key (.docx or .pdf)", type=["docx", "pdf"])

if student_file and answer_key_file:
    st.success("✅ Both files uploaded successfully.")

    # Extract text
    if student_file.name.endswith(".docx"):
        student_text = extract_text_docx(student_file)
    else:
        student_text = extract_text_pdf(student_file)

    if answer_key_file.name.endswith(".docx"):
        answer_key_text = extract_text_docx(answer_key_file)
    else:
        answer_key_text = extract_text_pdf(answer_key_file)

    # Convert to dict (assumes Q1: ..., Q2: ... format)
    def split_answers(text):
        questions = {}
        for block in text.strip().split("Q"):
            if block.strip():
                parts = block.strip().split(":", 1)
                if len(parts) == 2:
                    q_num = parts[0].strip()
                    answer = parts[1].strip()
                    questions[q_num] = answer
        return questions

    student_answers = split_answers(student_text)
    correct_answers = split_answers(answer_key_text)

    grades = []
    for q_num, stu_ans in student_answers.items():
        correct_ans = correct_answers.get(q_num, "No answer provided.")
        feedback = grade_answer(stu_ans, correct_ans, q_num)
        grades.append({
            "Question": f"Q{q_num}",
            "Student Answer": stu_ans,
            "Correct Answer": correct_ans,
            "AI Feedback": feedback
        })

    df = pd.DataFrame(grades)

    st.subheader("📊 Grading Results")
    st.dataframe(df)

    # Download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Grades")
        writer.save()
        st.download_button("📥 Download Report", output.getvalue(), file_name="grading_report.xlsx")

else:
    st.info("👈 Please upload both student answers and the answer key to begin.")
