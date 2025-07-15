import streamlit as st
import openai
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
import io
import re

# Set page config first
st.set_page_config(page_title="AI Grader Assistant", layout="wide")

# Initialize OpenAI client (updated API)
try:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("⚠️ OpenAI API key not found. Please check your Streamlit secrets.")
    st.stop()

st.title("📚 AI Teacher's Grading Assistant")

# Helper: extract text from DOCX
def extract_text_docx(file):
    try:
        doc = Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        st.error(f"Error reading DOCX file: {str(e)}")
        return ""

# Helper: extract text from PDF
def extract_text_pdf(file):
    try:
        # Reset file pointer
        file.seek(0)
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in pdf:
            text += page.get_text()
        pdf.close()
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {str(e)}")
        return ""

# AI Grading Function (Updated API)
def grade_answer(student_answer, correct_answer, question_number):
    try:
        prompt = f"""
You are a helpful teacher grading student work. Grade the following student answer to Question {question_number}.

CORRECT ANSWER:
{correct_answer}

STUDENT'S ANSWER:
{student_answer}

Please provide:
1. A score out of 10
2. Brief explanation of the score
3. Constructive feedback for improvement

Be encouraging and educational in your response.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error grading this question: {str(e)}"

# Improved answer parsing function
def split_answers(text):
    questions = {}
    
    # Try multiple patterns for question detection
    patterns = [
        r'Q(\d+):\s*(.*?)(?=Q\d+:|$)',  # Q1: answer
        r'Question\s+(\d+):\s*(.*?)(?=Question\s+\d+:|$)',  # Question 1: answer
        r'(\d+)\.\s*(.*?)(?=\d+\.|$)',  # 1. answer
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            for q_num, answer in matches:
                questions[q_num.strip()] = answer.strip()
            break
    
    return questions

# Sidebar
st.sidebar.header("📤 Upload Files")
student_file = st.sidebar.file_uploader(
    "Upload Student Answers", 
    type=["docx", "pdf"],
    help="Upload a document with student answers in Q1:, Q2: format"
)
answer_key_file = st.sidebar.file_uploader(
    "Upload Answer Key", 
    type=["docx", "pdf"],
    help="Upload a document with correct answers in Q1:, Q2: format"
)

# Processing section
if student_file and answer_key_file:
    with st.spinner("Processing uploaded files..."):
        # Extract text from both files
        if student_file.name.endswith(".docx"):
            student_text = extract_text_docx(student_file)
        else:
            student_text = extract_text_pdf(student_file)
        
        if answer_key_file.name.endswith(".docx"):
            answer_key_text = extract_text_docx(answer_key_file)
        else:
            answer_key_text = extract_text_pdf(answer_key_file)
        
        # Check if text was extracted successfully
        if not student_text or not answer_key_text:
            st.error("⚠️ Could not extract text from one or both files. Please check file formats.")
            st.stop()
        
        # Parse answers
        student_answers = split_answers(student_text)
        correct_answers = split_answers(answer_key_text)
        
        if not student_answers or not correct_answers:
            st.error("⚠️ Could not parse questions. Please ensure files use Q1:, Q2: format.")
            st.stop()
        
        st.success(f"✅ Found {len(student_answers)} student answers and {len(correct_answers)} correct answers.")
        
        # Preview section
        with st.expander("📋 Preview Extracted Text"):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Student Answers")
                for q, ans in list(student_answers.items())[:3]:
                    st.write(f"**Q{q}:** {ans[:100]}...")
            with col2:
                st.subheader("Answer Key")
                for q, ans in list(correct_answers.items())[:3]:
                    st.write(f"**Q{q}:** {ans[:100]}...")
        
        # Grade all questions
        if st.button("🎯 Grade All Questions", type="primary"):
            grades = []
            progress_bar = st.progress(0)
            
            for i, (q_num, stu_ans) in enumerate(student_answers.items()):
                correct_ans = correct_answers.get(q_num, "No answer key provided for this question.")
                
                with st.spinner(f"Grading Question {q_num}..."):
                    feedback = grade_answer(stu_ans, correct_ans, q_num)
                
                grades.append({
                    "Question": f"Q{q_num}",
                    "Student Answer": stu_ans,
                    "Correct Answer": correct_ans,
                    "AI Feedback": feedback
                })
                
                progress_bar.progress((i + 1) / len(student_answers))
            
            # Display results
            st.subheader("📊 Grading Results")
            df = pd.DataFrame(grades)
            
            # Show results in expandable sections
            for _, row in df.iterrows():
                with st.expander(f"📝 {row['Question']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Student Answer:**")
                        st.write(row['Student Answer'])
                    with col2:
                        st.write("**Correct Answer:**")
                        st.write(row['Correct Answer'])
                    st.write("**AI Feedback:**")
                    st.write(row['AI Feedback'])
            
            # Download functionality
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Grades')
                
                st.download_button(
                    label="📥 Download Grading Report",
                    data=output.getvalue(),
                    file_name="grading_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Error creating download file: {str(e)}")

else:
    st.info("👈 Please upload both student answers and the answer key to begin grading.")
    
    # Instructions
    st.markdown("""
    ### 📋 Instructions:
    1. **Upload student answers** - Document should contain answers in format: Q1: answer, Q2: answer, etc.
    2. **Upload answer key** - Document should contain correct answers in the same format
    3. **Click "Grade All Questions"** to get AI feedback on each answer
    4. **Download results** as an Excel file
    
    ### 📄 Supported Formats:
    - PDF files
    - Word documents (.docx)
    
    ### 🔧 Question Format:
    Your documents should use one of these formats:
    - `Q1: answer text here`
    - `Question 1: answer text here`
    - `1. answer text here`
    """)
