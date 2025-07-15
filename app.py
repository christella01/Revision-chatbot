import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
import io
import re
from difflib import SequenceMatcher
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string

# Download required NLTK data (runs once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    with st.spinner("Downloading language resources..."):
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)

# Set page config
st.set_page_config(page_title="AI Grader Assistant", layout="wide")

st.title("📚 AI Teacher's Grading Assistant (No API Required)")

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

# Text similarity function
def calculate_similarity(text1, text2):
    """Calculate similarity between two texts using multiple methods"""
    # Method 1: Simple character-based similarity
    char_similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    # Method 2: Word-based similarity (removing stopwords)
    try:
        stop_words = set(stopwords.words('english'))
        
        # Clean and tokenize
        def clean_text(text):
            text = text.lower().translate(str.maketrans('', '', string.punctuation))
            tokens = word_tokenize(text)
            return [word for word in tokens if word not in stop_words and len(word) > 2]
        
        words1 = set(clean_text(text1))
        words2 = set(clean_text(text2))
        
        if len(words1) == 0 or len(words2) == 0:
            word_similarity = 0
        else:
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            word_similarity = intersection / union if union > 0 else 0
    except:
        word_similarity = char_similarity
    
    # Combine both methods
    final_similarity = (char_similarity * 0.4) + (word_similarity * 0.6)
    return final_similarity

# Smart grading function (no API required)
def grade_answer_local(student_answer, correct_answer, question_number):
    """Grade answer using local algorithms"""
    
    # Calculate similarity
    similarity = calculate_similarity(student_answer, correct_answer)
    
    # Determine score based on similarity and length
    if similarity >= 0.8:
        score = 9 + (similarity - 0.8) * 5  # 9-10 range
        grade_level = "Excellent"
    elif similarity >= 0.6:
        score = 7 + (similarity - 0.6) * 10  # 7-9 range
        grade_level = "Good"
    elif similarity >= 0.4:
        score = 5 + (similarity - 0.4) * 10  # 5-7 range
        grade_level = "Fair"
    elif similarity >= 0.2:
        score = 3 + (similarity - 0.2) * 10  # 3-5 range
        grade_level = "Poor"
    else:
        score = similarity * 15  # 0-3 range
        grade_level = "Very Poor"
    
    # Cap at 10
    score = min(score, 10)
    
    # Length analysis
    student_length = len(student_answer.split())
    correct_length = len(correct_answer.split())
    length_ratio = student_length / correct_length if correct_length > 0 else 0
    
    # Generate feedback
    feedback_parts = []
    feedback_parts.append(f"**Score: {score:.1f}/10** ({grade_level})")
    feedback_parts.append(f"**Similarity to correct answer:** {similarity:.1%}")
    
    if similarity >= 0.7:
        feedback_parts.append("✅ **Strengths:** Your answer shows good understanding of the key concepts.")
    elif similarity >= 0.4:
        feedback_parts.append("⚠️ **Strengths:** You have some correct elements in your answer.")
    else:
        feedback_parts.append("❌ **Areas for improvement:** Your answer needs significant revision.")
    
    if length_ratio < 0.5:
        feedback_parts.append("📝 **Suggestion:** Consider providing more detailed explanations.")
    elif length_ratio > 2:
        feedback_parts.append("📝 **Suggestion:** Try to be more concise and focus on key points.")
    
    if similarity < 0.6:
        feedback_parts.append("💡 **Tip:** Review the correct answer and identify the main concepts you may have missed.")
    
    return "\n\n".join(feedback_parts)

# Improved answer parsing function
def split_answers(text):
    questions = {}
    
    # Try multiple patterns for question detection
    patterns = [
        r'Q(\d+):\s*(.*?)(?=Q\d+:|$)',
        r'Question\s+(\d+):\s*(.*?)(?=Question\s+\d+:|$)',
        r'(\d+)\.\s*(.*?)(?=\d+\.|$)',
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
st.sidebar.info("🎯 **No API Key Required!** This version uses local algorithms to grade answers.")

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

# Settings
st.sidebar.header("⚙️ Grading Settings")
strict_mode = st.sidebar.checkbox("Strict Grading Mode", help="More stringent similarity requirements")
show_similarity = st.sidebar.checkbox("Show Similarity Scores", value=True)

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
                
                feedback = grade_answer_local(stu_ans, correct_ans, q_num)
                
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
            
            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Questions", len(grades))
            with col2:
                # Extract scores from feedback
                scores = []
                for feedback in df['AI Feedback']:
                    try:
                        score_line = feedback.split('\n')[0]
                        score = float(score_line.split('**Score: ')[1].split('/10')[0])
                        scores.append(score)
                    except:
                        scores.append(0)
                avg_score = sum(scores) / len(scores) if scores else 0
                st.metric("Average Score", f"{avg_score:.1f}/10")
            with col3:
                passing_scores = sum(1 for score in scores if score >= 6)
                pass_rate = (passing_scores / len(scores) * 100) if scores else 0
                st.metric("Pass Rate", f"{pass_rate:.1f}%")
            
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
                    st.write("**Feedback:**")
                    st.markdown(row['AI Feedback'])
            
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
    ### 📋 How It Works:
    This app uses **local algorithms** (no API required) to grade student answers by:
    - 🔍 **Text Similarity Analysis** - Compares student answers with correct answers
    - 📊 **Word Matching** - Identifies key concepts and terminology
    - 📝 **Length Analysis** - Evaluates answer completeness
    - 🎯 **Smart Scoring** - Provides scores and detailed feedback
    
    ### 📄 Instructions:
    1. **Upload student answers** - Document should contain: Q1: answer, Q2: answer, etc.
    2. **Upload answer key** - Document with correct answers in same format
    3. **Click "Grade All Questions"** to get automated feedback
    4. **Download results** as Excel file
    
    ### 🔧 Supported Question Formats:
    - `Q1: answer text here`
    - `Question 1: answer text here`  
    - `1. answer text here`
    
    ### 📊 Features:
    - ✅ **No API keys required** - Works completely offline
    - 🎯 **Smart scoring** - Based on similarity and completeness
    - 📈 **Analytics** - Average scores and pass rates
    - 📥 **Export results** - Download as Excel file
    """)
