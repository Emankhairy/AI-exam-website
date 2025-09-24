from flask import Flask, render_template, request, redirect
from flask import flash
import os 
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import sqlite3
import random
import google.generativeai
from flask import session
import google.generativeai as genai
from flask import make_response
from io import BytesIO
app = Flask(__name__)
app.secret_key = os.urandom(24)

genai.configure(api_key="AIzaSyAKnWwc0R1eamUpSTTT_LKkB34E9K-Yl90")

defaults = {
    'model': 'models/text-bison-001',
    'temperature': 0.7,
    'candidate_count': 1,
    'top_k': 40,
    'top_p': 0.95,
    'max_output_tokens': 1024,
    'stop_sequences': [],
    'safety_settings': [
        {"category": "HARM_CATEGORY_DEROGATORY", "threshold": 1},
        {"category": "HARM_CATEGORY_TOXICITY", "threshold": 1},
        {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 2},
        {"category": "HARM_CATEGORY_SEXUAL", "threshold": 2},
        {"category": "HARM_CATEGORY_MEDICAL", "threshold": 2},
        {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 2},
    ],
}
# Function to create tables in SQLite database
def create_tables():
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()

    # Create a table for teachers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            teacher_id TEXT NOT NULL
        )
    ''')

    # Create a table for students
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            student_id TEXT NOT NULL
        )
    ''')

    # Create a table for exams
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    ''')

    # Create a table for exam results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_results (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            similarity_score REAL,
            num_correct_answers INTEGER,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(exam_id) REFERENCES exams(id)
        )
    ''')
    # Step 1: Create a new temporary table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students_temp AS
    SELECT id, name, student_id, COALESCE(exam_taken, 0) AS exam_taken
    FROM students
    ''')
# Step 2: Rename the tables
    cursor.execute('DROP TABLE IF EXISTS students_old')
    cursor.execute('ALTER TABLE students RENAME TO students_old')
    cursor.execute('ALTER TABLE students_temp RENAME TO students')
    
    # Create a table for exam configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_configurations (
            id INTEGER PRIMARY KEY,
            start_time DATETIME,
            num_questions INTEGER
        )
    ''')
    # Insert an initial exam configuration
    cursor.execute('''
        INSERT INTO exam_configurations (start_time, num_questions)
        VALUES (?, ?)
    ''', ('2023-12-09 12:00:00', 5))  # Set a default start time and number of questions
    # Insert values into the teachers table
    cursor.execute('''
        INSERT INTO teachers (name, teacher_id)
        VALUES (?, ?)
    ''', ('fatma', 'IT123'))

    cursor.execute('''
        INSERT INTO teachers (name, teacher_id)
        VALUES (?, ?)
    ''', ('Eman', 'IT456'))
    cursor.execute('''
        INSERT INTO teachers (name, teacher_id)
        VALUES (?, ?)
    ''', ('sara', 'IT789'))
    
 

    conn.commit()
    conn.close()

# Call the function to create tables
create_tables()
# Home Page
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/teacher-login')
def teacher_login():
    return render_template('teacher_login.html')

@app.route('/validate-teacher', methods=['POST'])
def validate_teacher():
    name = request.form['name']
    teacher_id = request.form['id']

    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()

    # Check if the entered name and ID exist in the teachers table
    cursor.execute('SELECT * FROM teachers WHERE name=? AND teacher_id=?', (name, teacher_id))
    teacher = cursor.fetchone()

    conn.close()

    if teacher:
        return redirect('/prepare-exams')  # Redirect to prepare exams if teacher exists
    else:
        return redirect('/')  # Redirect back to home if teacher doesn't exist


# Assuming you store the student ID in the session upon login
def get_student_id():
    return session.get('student_id')    
# Student Login Page
# Student Login Page
@app.route('/student-login')
def student_login():
    return render_template('student_login.html')
# Student Login Page
@app.route('/validate-student', methods=['POST'])
def validate_student():
    name = request.form['name']
    student_id = request.form['id']
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()
    # Check if the entered name and ID exist in the students table and if the exam has been taken
    cursor.execute('SELECT * FROM students WHERE name=? AND student_id=? AND exam_taken=0', (name, student_id))
    student = cursor.fetchone()
    conn.close()
    if student:
        # Store the student_id in the session upon successful login
        session['student_id'] = student_id
        print("Student login successful. Redirecting to /exam")
        return redirect('/exam')  # Redirect to exam if the student exists and the exam has not been taken
    else:
        flash('Invalid login. Please check your credentials.')
        return redirect('/student-login')  # Redirect to student login if the student doesn't exist or the exam has been taken
# Student Register Page
# Student Register Page
@app.route('/student-register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        # Process student registration logic here
        name = request.form.get('name')
        student_id = request.form.get('student_id')
        # Check if the student already exists in the table
        conn = sqlite3.connect('exam_system.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE student_id=?", (student_id,))
        existing_student = cursor.fetchone()
        if existing_student:
            # If the student already exists, you can handle it accordingly (e.g., display an error message)
            flash('Student with the same ID already exists. Please choose a different ID.')
        else:
            # If the student does not exist, insert the new student into the table
            cursor.execute("INSERT INTO students (name, student_id) VALUES (?, ?)", (name, student_id))
            conn.commit()
            flash('Registration successful. You can now log in.')
        conn.close()
        return redirect('/student-login')
    return render_template('student_register.html')
@app.route('/prepare-exams')
def prepare_exams():
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()
    # Fetch the current exam configuration
    cursor.execute('SELECT start_time, num_questions FROM exam_configurations ORDER BY id DESC LIMIT 1')
    exam_config = cursor.fetchone()
    conn.close()
    return render_template('prepare_exams.html', start_time=exam_config[0], num_questions_exam=exam_config[1])

@app.route('/save-exam-configuration', methods=['POST'])
def save_exam_configuration():
    start_time = request.form['start_time']
    num_questions = int(request.form['num_questions'])
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()
    # Insert a new exam configuration
    cursor.execute('INSERT INTO exam_configurations (start_time, num_questions) VALUES (?, ?)', (start_time, num_questions))
    conn.commit()
    conn.close()
    return redirect('/prepare-exams')
@app.route('/save-exam', methods=['POST'])
def save_exam():
    num_questions = int(request.form['num_questions_exam'])
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()
    for i in range(num_questions):
        question = request.form[f'question{i}']
        answer = request.form[f'answer{i}']
        # Store questions and answers in the exam table
        cursor.execute('INSERT INTO exams (question, answer) VALUES (?, ?)', (question, answer))
    conn.commit()
    conn.close()
    return redirect('/prepare-exams')  # Redirect back to prepare exams page


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        conn = sqlite3.connect('exam_system.db')
        cursor = conn.cursor()

        # Fetch names and similarity scores of students who have taken the exam
        cursor.execute('''
            SELECT students.name, COALESCE(exam_results.similarity_score, 0) 
            FROM students 
            LEFT JOIN exam_results ON students.id = exam_results.student_id
            WHERE students.exam_taken = 1
        ''')
        exam_results = cursor.fetchall()

        # Create a BytesIO object to store the PDF content
        pdf_buffer = BytesIO()

        # Generate PDF report using ReportLab
        pdf_canvas = canvas.Canvas(pdf_buffer)
        pdf_canvas.setFont("Helvetica", 12)

        # Set up PDF content
        pdf_canvas.drawString(100, 800, "Exam Results Report")
        pdf_canvas.line(100, 795, 500, 795)  # Horizontal line

        # Write fetched data to PDF
        y_position = 780
        for student_name, similarity_score in exam_results:
            pdf_canvas.drawString(100, y_position, f"Student Name: {student_name}, Similarity Score: {similarity_score}")
            y_position -= 20  # Adjust vertical position for the next line

        pdf_canvas.save()

        # Move the BytesIO cursor to the beginning
        pdf_buffer.seek(0)

        # Create a Flask response with the PDF content
        response = make_response(pdf_buffer.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=exam_results_report.pdf'

        return response

    finally:
        if conn:
            conn.close()





# Exam Page# In the /exam route
# Exam Page# In the /exam route
# Exam Page
# Exam Page
@app.route('/exam')
def exam():
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()
    # Retrieve student ID from the session
    student_id = session.get('student_id')
    if student_id:
        print(f"Student ID: {student_id}")
        # Fetch the number of questions for the current exam configuration, or use a default value if not set
        cursor.execute('SELECT COALESCE(num_questions, 5) FROM exam_configurations ORDER BY id DESC LIMIT 1')
        num_questions_result = cursor.fetchone()
        if num_questions_result:
            num_questions = num_questions_result[0]
            # Fetch questions from the exam table based on the number specified in the configuration
            cursor.execute('SELECT id, question FROM exams ORDER BY RANDOM() LIMIT ?', (num_questions,))
            exam_questions = cursor.fetchall()
            print(f"num_questions: {num_questions}")
            print(f"exam_questions: {exam_questions}")

            print("Rendering /exam.html")
            return render_template('exam.html', exam_questions=exam_questions)
        else:
            flash('Error: Unable to fetch the number of questions.')
            print("Redirecting to /prepare-exams due to an error.")
            return redirect('/prepare-exams')

@app.route('/submit-exam', methods=['POST'])
def submit_exam():
    try:
        conn = sqlite3.connect('exam_system.db')
        cursor = conn.cursor()

        # Assuming the form fields are named as 'answer1', 'answer2', etc.
        # Compare answers and calculate similarity score and number of correct answers
        student_id = get_student_id()
        total_questions = 0
        correct_answers = 0

        for question_id, _ in request.form.items():
            if question_id.startswith('answer'):
                total_questions += 1
                student_answer = request.form[question_id]
                
                # Retrieve the corresponding teacher's answer from the database
                cursor.execute('SELECT answer FROM exams WHERE id=?', (question_id[6:],))
                teacher_answer = cursor.fetchone()[0]
                
                # Use Google Generative AI to compare answers
                prompt = f"Student's Answer: {student_answer}\nTeacher's Answer: {teacher_answer} Are these answers similar?"
                response = genai.generate_text(**defaults, prompt=prompt)

                similarity_score = 0  # Default score if no similarity indication is found
                if response.result:
                    similarity_text = response.result.lower()
                    if 'yes' in similarity_text:
                        similarity_score = 2
                        correct_answers += 1
                    elif 'no' in similarity_text:
                        similarity_score = 0

                # Store the individual question's similarity score in the exam_results table
                cursor.execute('''
                    INSERT INTO exam_results (student_id, exam_id, similarity_score, num_correct_answers)
                    VALUES (?, ?, ?, ?)
                ''', (student_id, question_id[6:], similarity_score, correct_answers))

        # Calculate overall similarity score based on correctness or other criteria
        overall_similarity_score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        # Assuming you have the student ID available in the session or elsewhere
        # Update similarity score in the student table for the specific student
        cursor.execute('UPDATE students SET exam_taken=1 WHERE student_id=?', (student_id,))

        # Redirect to the result page with the overall similarity score
        return render_template('result.html', num_correct_answers=correct_answers, similarity_score=overall_similarity_score)

    finally:
        if conn:
            conn.commit()
            conn.close()

# Result Page
@app.route('/result')
def result():
    return render_template('result.html')
if __name__ == '__main__':
    app.run(debug=True)  # Run the Flask app