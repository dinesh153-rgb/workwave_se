from flask import Flask, request, jsonify, send_from_directory
from flask import send_file
from fpdf import FPDF
import sqlite3
import json
from flask_cors import CORS
import jwt
import datetime
from functools import wraps
import os
import hashlib

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change to a secure key in production

# Directory for file uploads
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf'}  # Allowed file extensions for resume

# Database connection helper
def get_db():
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row  # Set row_factory to return rows as dictionaries
    return conn

# Database initialization
def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Create jobs table
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY, 
                  job_title TEXT, 
                  company TEXT, 
                  required_skills TEXT, 
                  location TEXT, 
                  job_type TEXT, 
                  experience_level TEXT)''')
    
    # Create users table with additional columns for profile data
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  name TEXT,
                  contact TEXT,
                  email TEXT,
                  resume TEXT,
                  skills TEXT, -- JSON array
                  job_roles TEXT -- JSON array
                )''')

    # Create applications table to track job applications
    c.execute('''CREATE TABLE IF NOT EXISTS applications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  job_title TEXT,
                  company TEXT,
                  location TEXT,
                  job_type TEXT,
                  experience_level TEXT,
                  required_skills TEXT,
                  application_date TEXT,
                  status TEXT,
                  FOREIGN KEY (username) REFERENCES users(username))''')
    
    # Create resources table (only for courses)
    c.execute('''CREATE TABLE IF NOT EXISTS resources (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT, -- 'course', 'certification'
                  title TEXT,
                  description TEXT,
                  url TEXT,
                  platform TEXT, -- e.g., 'Coursera', 'Udemy', 'edX'
                  skills TEXT, -- JSON array of relevant skills
                  job_roles TEXT, -- JSON array of relevant roles
                  difficulty TEXT, -- 'Beginner', 'Intermediate', 'Advanced'
                  duration TEXT, -- e.g., '4 weeks', '2 hours'
                  cost TEXT -- 'Free', 'Paid'
              )''')
    
    # Create assessments table
    c.execute('''CREATE TABLE IF NOT EXISTS assessments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  skill TEXT, -- e.g., 'Python', 'JavaScript'
                  question TEXT,
                  options TEXT, -- JSON array of options
                  correct_answer TEXT,
                  difficulty TEXT -- 'Beginner', 'Intermediate', 'Advanced'
              )''')
    
    # Create user_assessments table
    c.execute('''CREATE TABLE IF NOT EXISTS user_assessments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  skill TEXT,
                  score INTEGER, -- Score out of total questions
                  total_questions INTEGER, -- Total questions in the assessment
                  completed_at TEXT, -- Timestamp
                  FOREIGN KEY (username) REFERENCES users(username)
              )''')
    
    # Insert test users
    c.execute('''INSERT OR IGNORE INTO users 
                 (username, password, name, email, skills, job_roles) 
                 VALUES 
                 ('alice', 'password123', 'Alice Smith', 'alice@example.com', 
                  '["Python", "SQL"]', '["Data Scientist"]'),
                 ('bob', 'password123', 'Bob Johnson', 'bob@example.com', 
                  '["JavaScript", "React"]', '["Web Developer"]'),
                 ('charlie', 'password123', 'Charlie Lee', 'charlie@example.com', 
                  '["Java", "Git"]', '["Software Engineer"]')''')
    
    # Insert resources (5 courses per skill)
    c.execute('''INSERT OR IGNORE INTO resources 
                 (type, title, description, url, platform, skills, job_roles, difficulty, duration, cost)
                 VALUES 
                 -- Python Courses
                 ('course', 'Python for Everybody', 'Learn Python programming from scratch.', 
                  'https://www.coursera.org/specializations/python', 'Coursera', 
                  '["Python"]', '["Data Scientist", "Software Engineer"]', 'Beginner', '4 months', 'Free'),
                 ('course', 'Complete Python Bootcamp', 'Comprehensive Python course for all levels.', 
                  'https://www.udemy.com/course/complete-python-bootcamp/', 'Udemy', 
                  '["Python"]', '["Software Engineer"]', 'Beginner', '22 hours', 'Paid'),
                 ('course', 'Automate the Boring Stuff with Python', 'Practical Python for automation.', 
                  'https://www.udemy.com/course/automate/', 'Udemy', 
                  '["Python"]', '["Software Engineer"]', 'Beginner', '10 hours', 'Paid'),
                 ('course', 'Introduction to Python Programming', 'Learn Python basics.', 
                  'https://www.edx.org/course/introduction-to-python-programming', 'edX', 
                  '["Python"]', '["Data Scientist"]', 'Beginner', '5 weeks', 'Free'),
                 ('course', 'Python Data Structures', 'Explore Python data structures.', 
                  'https://www.coursera.org/learn/python-data-structures', 'Coursera', 
                  '["Python"]', '["Data Scientist"]', 'Intermediate', '4 weeks', 'Paid'),
                 -- Java Courses
                 ('course', 'Java Programming Masterclass', 'Comprehensive Java course.', 
                  'https://www.udemy.com/course/java-the-complete-java-developer-course/', 'Udemy', 
                  '["Java"]', '["Software Engineer"]', 'Beginner', '80 hours', 'Paid'),
                 ('course', 'Java Programming and Software Engineering Fundamentals', 'Learn Java basics.', 
                  'https://www.coursera.org/specializations/java-programming', 'Coursera', 
                  '["Java"]', '["Software Engineer"]', 'Beginner', '5 months', 'Free'),
                 ('course', 'Object Oriented Programming in Java', 'Master OOP with Java.', 
                  'https://www.coursera.org/learn/object-oriented-programming-java', 'Coursera', 
                  '["Java"]', '["Software Engineer"]', 'Intermediate', '4 weeks', 'Paid'),
                 ('course', 'Java for Android Development', 'Build Android apps with Java.', 
                  'https://www.udemy.com/course/java-android-complete-guide/', 'Udemy', 
                  '["Java"]', '["Mobile Developer"]', 'Intermediate', '30 hours', 'Paid'),
                 ('course', 'Introduction to Java', 'Learn Java fundamentals.', 
                  'https://www.edx.org/course/introduction-to-java-programming', 'edX', 
                  '["Java"]', '["Software Engineer"]', 'Beginner', '6 weeks', 'Free'),
                 -- SQL Courses
                 ('course', 'SQL for Data Science', 'Learn SQL for data analysis.', 
                  'https://www.coursera.org/learn/sql-for-data-science', 'Coursera', 
                  '["SQL"]', '["Data Analyst"]', 'Beginner', '4 weeks', 'Paid'),
                 ('course', 'The Complete SQL Bootcamp', 'Master SQL queries.', 
                  'https://www.udemy.com/course/the-complete-sql-bootcamp/', 'Udemy', 
                  '["SQL"]', '["Data Analyst"]', 'Beginner', '9 hours', 'Paid'),
                 ('course', 'Introduction to Databases and SQL', 'Learn SQL basics.', 
                  'https://www.edx.org/course/introduction-to-databases-and-sql', 'edX', 
                  '["SQL"]', '["Data Analyst"]', 'Beginner', '3 weeks', 'Free'),
                 ('course', 'Advanced SQL for Data Analysis', 'Advanced SQL techniques.', 
                  'https://www.udemy.com/course/advanced-sql-for-data-analysis/', 'Udemy', 
                  '["SQL"]', '["Data Analyst"]', 'Intermediate', '12 hours', 'Paid'),
                 ('course', 'SQL and Database Design', 'Learn database design with SQL.', 
                  'https://www.coursera.org/learn/sql-and-database-design', 'Coursera', 
                  '["SQL"]', '["Database Administrator"]', 'Intermediate', '5 weeks', 'Paid'),
                 -- Data Structures Courses
                 ('course', 'Data Structures and Algorithms in Python', 'Master DS&A with Python.', 
                  'https://www.udemy.com/course/data-structures-algorithms-python/', 'Udemy', 
                  '["Data Structures"]', '["Software Engineer"]', 'Intermediate', '20 hours', 'Paid'),
                 ('course', 'Algorithms, Part I', 'Learn algorithms and data structures.', 
                  'https://www.coursera.org/learn/algorithms-part1', 'Coursera', 
                  '["Data Structures"]', '["Software Engineer"]', 'Intermediate', '6 weeks', 'Free'),
                 ('course', 'Data Structures in Java', 'Learn DS with Java.', 
                  'https://www.udemy.com/course/data-structures-in-java/', 'Udemy', 
                  '["Data Structures"]', '["Software Engineer"]', 'Intermediate', '15 hours', 'Paid'),
                 ('course', 'Introduction to Data Structures', 'Learn DS fundamentals.', 
                  'https://www.edx.org/course/introduction-to-data-structures', 'edX', 
                  '["Data Structures"]', '["Software Engineer"]', 'Beginner', '4 weeks', 'Free'),
                 ('course', 'Algorithms and Data Structures', 'Comprehensive DS&A course.', 
                  'https://www.coursera.org/learn/algorithms-data-structures', 'Coursera', 
                  '["Data Structures"]', '["Software Engineer"]', 'Intermediate', '5 weeks', 'Paid'),
                 -- JavaScript Courses
                 ('course', 'The Complete JavaScript Course', 'Master JavaScript from scratch.', 
                  'https://www.udemy.com/course/the-complete-javascript-course/', 'Udemy', 
                  '["JavaScript"]', '["Web Developer"]', 'Beginner', '68 hours', 'Paid'),
                 ('course', 'JavaScript - The Complete Guide', 'Comprehensive JS course.', 
                  'https://www.udemy.com/course/javascript-the-complete-guide-2020/', 'Udemy', 
                  '["JavaScript"]', '["Web Developer"]', 'Beginner', '50 hours', 'Paid'),
                 ('course', 'Modern JavaScript From The Beginning', 'Learn modern JS.', 
                  'https://www.udemy.com/course/modern-javascript-from-the-beginning/', 'Udemy', 
                  '["JavaScript"]', '["Web Developer"]', 'Beginner', '21 hours', 'Paid'),
                 ('course', 'JavaScript: Understanding the Weird Parts', 'Deep dive into JS.', 
                  'https://www.udemy.com/course/understand-javascript/', 'Udemy', 
                  '["JavaScript"]', '["Web Developer"]', 'Intermediate', '11 hours', 'Paid'),
                 ('course', 'Introduction to JavaScript', 'Learn JS basics.', 
                  'https://www.edx.org/course/introduction-to-javascript', 'edX', 
                  '["JavaScript"]', '["Web Developer"]', 'Beginner', '4 weeks', 'Free'),
                 -- Git Courses
                 ('course', 'Git and GitHub for Beginners', 'Learn version control.', 
                  'https://www.youtube.com/watch?v=RGOj5yH7evk', 'freeCodeCamp', 
                  '["Git"]', '["Software Engineer"]', 'Beginner', '30 minutes', 'Free'),
                 ('course', 'Git Complete: The Definitive Guide', 'Master Git and GitHub.', 
                  'https://www.udemy.com/course/git-complete/', 'Udemy', 
                  '["Git"]', '["Software Engineer"]', 'Beginner', '6 hours', 'Paid'),
                 ('course', 'Learn Git by Doing', 'Practical Git course.', 
                  'https://www.udemy.com/course/learn-git-by-doing/', 'Udemy', 
                  '["Git"]', '["Software Engineer"]', 'Beginner', '4 hours', 'Paid'),
                 ('course', 'Introduction to Git and GitHub', 'Learn Git basics.', 
                  'https://www.coursera.org/learn/introduction-git-github', 'Coursera', 
                  '["Git"]', '["Software Engineer"]', 'Beginner', '4 weeks', 'Free'),
                 ('course', 'Version Control with Git', 'Master Git workflows.', 
                  'https://www.coursera.org/learn/version-control-with-git', 'Coursera', 
                  '["Git"]', '["Software Engineer"]', 'Intermediate', '4 weeks', 'Paid')
                 ''')

    # Insert sample assessments (5 questions per skill)
    c.execute('''INSERT OR IGNORE INTO assessments 
                 (skill, question, options, correct_answer, difficulty)
                 VALUES 
                 -- Python Questions
                 ('Python', 'What is the output of print(2 ** 3)?', 
                  '["6", "8", "9", "12"]', '8', 'Beginner'),
                 ('Python', 'Which keyword is used to define a function in Python?', 
                  '["def", "function", "lambda", "fun"]', 'def', 'Beginner'),
                 ('Python', 'What does list.append() do?', 
                  '["Adds an element to the end of the list", "Removes an element", 
                   "Sorts the list", "Reverses the list"]', 'Adds an element to the end of the list', 'Beginner'),
                 ('Python', 'What is the output of len("Hello")?', 
                  '["4", "5", "6", "7"]', '5', 'Beginner'),
                 ('Python', 'Which of these is a Python tuple?', 
                  '["[1, 2, 3]", "(1, 2, 3)", "{1, 2, 3}", "1, 2, 3"]', '(1, 2, 3)', 'Beginner'),
                 ('Python', 'What is the result of the expression 3 + 5 * 2?', 
                  '["10", "13", "16", "20"]', '13', 'Beginner'),
                 -- JavaScript Questions
                 ('JavaScript', 'What does "let" do in JavaScript?', 
                  '["Declares a block-scoped variable", "Declares a global variable", 
                   "Declares a constant", "Defines a function"]', 'Declares a block-scoped variable', 'Beginner'),
                 ('JavaScript', 'Which method converts a JSON string to an object?', 
                  '["JSON.parse()", "JSON.stringify()", "JSON.toObject()", "JSON.convert()"]', 
                  'JSON.parse()', 'Beginner'),
                 ('JavaScript', 'What is the output of typeof null?', 
                  '["object", "null", "undefined", "string"]', 'object', 'Beginner'),
                 ('JavaScript', 'What does Array.prototype.map() do?', 
                  '["Creates a new array with transformed elements", "Sorts the array", 
                   "Removes elements", "Reverses the array"]', 'Creates a new array with transformed elements', 'Beginner'),
                 ('JavaScript', 'Which keyword is used for inheritance?', 
                  '["extends", "implements", "inherits", "super"]', 'extends', 'Beginner'),
                 ('JavaScript', 'What is the purpose of the "addEventListener" method?', 
                  '["Attaches an event handler to an element", "Creates a new event", 
                  "Removes an event listener", "Triggers an event manually"]', 
                  'Attaches an event handler to an element', 'Beginner'),
                 -- SQL Questions
                 ('SQL', 'Which SQL keyword is used to retrieve data from a table?', 
                  '["SELECT", "INSERT", "UPDATE", "DELETE"]', 'SELECT', 'Beginner'),
                 ('SQL', 'What does INNER JOIN do?', 
                  '["Returns all rows from both tables", "Returns rows with matching values", 
                   "Returns unmatched rows", "Deletes rows"]', 'Returns rows with matching values', 'Beginner'),
                 ('SQL', 'Which clause filters rows after grouping?', 
                  '["WHERE", "HAVING", "GROUP BY", "ORDER BY"]', 'HAVING', 'Beginner'),
                 ('SQL', 'What is the purpose of the PRIMARY KEY?', 
                  '["Ensures unique values", "Allows duplicates", "Sorts data", "Joins tables"]', 
                  'Ensures unique values', 'Beginner'),
                 ('SQL', 'Which command adds a new column to a table?', 
                  '["ALTER TABLE", "UPDATE TABLE", "CREATE TABLE", "DROP TABLE"]', 'ALTER TABLE', 'Beginner'),
                 ('SQL', 'Which SQL function counts the number of rows in a result set?', 
                  '["COUNT()", "SUM()", "AVG()", "MAX()"]', 'COUNT()', 'Beginner'),
                 -- Java Questions
                 ('Java', 'What is the correct syntax for a main method?', 
                  '["public static void main(String[] args)", "public void main()", 
                   "static void main()", "public main(String args)"]', 
                  'public static void main(String[] args)', 'Beginner'),
                 ('Java', 'Which keyword creates an instance of a class?', 
                  '["new", "class", "this", "instance"]', 'new', 'Beginner'),
                 ('Java', 'What is the default value of an int variable?', 
                  '["0", "null", "1", "undefined"]', '0', 'Beginner'),
                 ('Java', 'Which access modifier makes a member accessible only within its package?', 
                  '["public", "private", "protected", "default"]', 'default', 'Beginner'),
                 ('Java', 'What does the "final" keyword do?', 
                  '["Prevents modification", "Allows inheritance", "Enables overriding", "Declares a variable"]', 
                  'Prevents modification', 'Beginner'),
                 ('Java', 'Which Java keyword is used to inherit a class?', 
                  '["extends", "implements", "super", "this"]', 'extends', 'Beginner'),
                 -- Git Questions
                 ('Git', 'Which command stages changes for a commit?', 
                  '["git commit", "git add", "git push", "git pull"]', 'git add', 'Beginner'),
                 ('Git', 'What does git branch do?', 
                  '["Creates a new branch", "Deletes a branch", "Switches branches", 
                   "Lists branches"]', 'Lists branches', 'Beginner'),
                 ('Git', 'Which command retrieves the latest changes from a remote repository?', 
                  '["git fetch", "git pull", "git push", "git clone"]', 'git pull', 'Beginner'),
                 ('Git', 'What does git commit -m "message" do?', 
                  '["Stages changes", "Creates a commit with a message", 
                   "Pushes changes", "Reverts changes"]', 'Creates a commit with a message', 'Beginner'),
                 ('Git', 'Which command shows the difference between staged and unstaged changes?', 
                  '["git diff", "git status", "git log", "git show"]', 'git diff', 'Beginner'),
                 ('Git', 'Which command switches to a different branch?', 
                  '["git checkout", "git merge", "git branch", "git stash"]', 'git checkout', 'Beginner'),
                 -- Data Structures Questions
                 ('Data Structures', 'What is the time complexity of accessing an element in an array?', 
                  '["O(1)", "O(n)", "O(log n)", "O(n^2)"]', 'O(1)', 'Beginner'),
                 ('Data Structures', 'Which data structure uses LIFO?', 
                  '["Queue", "Stack", "Array", "Linked List"]', 'Stack', 'Beginner'),
                 ('Data Structures', 'What is the purpose of a linked list?', 
                  '["Fixed-size storage", "Dynamic insertion/deletion", 
                   "Fast searching", "Key-value storage"]', 'Dynamic insertion/deletion', 'Beginner'),
                 ('Data Structures', 'Which sorting algorithm has the best average time complexity?', 
                  '["Bubble Sort", "Selection Sort", "Quick Sort", "Insertion Sort"]', 'Quick Sort', 'Beginner'),
                 ('Data Structures', 'What does a binary search tree ensure?', 
                  '["Sorted order", "Random order", "Fixed size", "Duplicate values"]', 'Sorted order', 'Beginner'),
                 ('Data Structures', 'Which data structure is used to implement a first-in, first-out (FIFO) order?', 
                  '["Stack", "Queue", "Heap", "Tree"]', 'Queue', 'Beginner')
                 ''')

    # Insert sample user assessments
    c.execute('''INSERT OR IGNORE INTO user_assessments 
                 (username, skill, score, total_questions, completed_at) 
                 VALUES 
                 ('alice', 'Python', 4, 5, '2025-04-15 10:00:00'),
                 ('alice', 'SQL', 3, 5, '2025-04-16 12:00:00'),
                 ('bob', 'JavaScript', 2, 5, '2025-04-17 09:00:00'),
                 ('charlie', 'Java', 5, 5, '2025-04-18 14:00:00')''')

    # Insert mock data from the JSON file
    try:
        with open('job_postings.json', 'r') as f:
            jobs = json.load(f)
    except FileNotFoundError:
        print("job_postings.json not found.")
        return
    except json.JSONDecodeError:
        print("Error decoding JSON from job_postings.json.")
        return

    for job in jobs:
        c.execute('''INSERT OR REPLACE INTO jobs 
                     (id, job_title, company, required_skills, location, job_type, experience_level) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (job['job_id'], job['job_title'], job['company'], 
                   json.dumps(job['required_skills']), job['location'], 
                   job['job_type'], job['experience_level']))

    conn.commit()
    conn.close()

# Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "Token is missing"}), 401
        try:
            token = token.split(" ")[1]  # Remove "Bearer" prefix
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            username = data['username']  # Extract username from token
        except:
            return jsonify({"error": "Invalid token"}), 401
        return f(username, *args, **kwargs)  # Pass username to the route
    return decorated

# Fetch career resources
import sqlite3
import json
import random
from flask import jsonify, request

@app.route('/user_info', methods=['GET'])
@token_required
def get_user_info(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({"username": user['username']}), 200
    except Exception as e:
        print(f"Error fetching user info: {str(e)}")
        return jsonify({"error": f"Failed to fetch user info: {str(e)}"}), 500
    
    
# Fetch career resources
@app.route('/resources', methods=['GET'])
@token_required
def get_resources(username):
    try:
        conn = get_db()
        c = conn.cursor()
        skill = request.args.get('skill')
        if not skill:
            return jsonify({"error": "Skill parameter is required"}), 400

        c.execute("SELECT * FROM resources WHERE type IN ('course', 'certification')")
        resources = c.fetchall()
        conn.close()

        filtered_resources = []
        for resource in resources:
            resource_skills = json.loads(resource['skills'])
            if skill in resource_skills:
                filtered_resources.append({
                    "id": resource['id'],
                    "type": resource['type'],
                    "title": resource['title'],
                    "description": resource['description'],
                    "url": resource['url'],
                    "platform": resource['platform'],
                    "skills": resource_skills,
                    "job_roles": json.loads(resource['job_roles']),
                    "difficulty": resource['difficulty'],
                    "duration": resource['duration'],
                    "cost": resource['cost']
                })

        return jsonify(filtered_resources), 200
    except Exception as e:
        print(f"Error fetching resources: {str(e)}")
        return jsonify({"error": f"Failed to fetch resources: {str(e)}"}), 500

# Fetch skill assessment questions
@app.route('/assessments/<skill>', methods=['GET'])
@token_required
def get_assessment(username, skill):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM assessments WHERE skill = ? ORDER BY RANDOM() LIMIT 6", (skill,))
        questions = c.fetchall()
        conn.close()

        if not questions:
            return jsonify({"error": f"No assessments found for skill: {skill}"}), 404

        return jsonify([{
            "id": q['id'],
            "skill": q['skill'],
            "question": q['question'],
            "options": json.loads(q['options']),
            "difficulty": q['difficulty']
        } for q in questions]), 200
    except Exception as e:
        print(f"Error fetching assessment: {str(e)}")
        return jsonify({"error": f"Failed to fetch assessment: {str(e)}"}), 500

# Submit assessment results
@app.route('/assessments', methods=['POST'])
@token_required
def submit_assessment(username):
    try:
        data = request.json
        skill = data.get('skill')
        answers = data.get('answers')  # {question_id: selected_option}
        total_questions = len(answers)
        score = 0

        conn = get_db()
        c = conn.cursor()
        for q_id, selected_option in answers.items():
            c.execute("SELECT correct_answer FROM assessments WHERE id = ?", (q_id,))
            result = c.fetchone()
            if result and selected_option == result['correct_answer']:
                score += 1

        # Save assessment result
        completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO user_assessments (username, skill, score, total_questions, completed_at) VALUES (?, ?, ?, ?, ?)",
                  (username, skill, score, total_questions, completed_at))
        conn.commit()
        conn.close()

        return jsonify({"message": "Assessment submitted", "score": score, "total_questions": total_questions}), 200
    except Exception as e:
        print(f"Error submitting assessment: {str(e)}")
        return jsonify({"error": f"Failed to submit assessment: {str(e)}"}), 500

# Fetch user assessment history
@app.route('/assessments/history', methods=['GET'])
@token_required
def get_assessment_history(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM user_assessments WHERE username = ? ORDER BY completed_at DESC", (username,))
        history = c.fetchall()
        conn.close()

        return jsonify([{
            "id": h['id'],
            "skill": h['skill'],
            "score": h['score'],
            "total_questions": h['total_questions'],
            "completed_at": h['completed_at']
        } for h in history]), 200
    except Exception as e:
        print(f"Error fetching assessment history: {str(e)}")
        return jsonify({"error": f"Failed to fetch assessment history: {str(e)}"}), 500

# Registration endpoint
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 400
    finally:
        conn.close()

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        token = jwt.encode({
            'username': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'])
        return jsonify({"token": token})
    return jsonify({"error": "Invalid credentials"}), 401

# Function to generate job recommendations based on user profile
def get_job_recommendations(user_profile):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM jobs")
    all_jobs = c.fetchall()

    scored_jobs = []
    user_skills = set(user_profile['skills'])
    desired_roles = [role.lower() for role in user_profile['preferences']['desired_roles']]
    preferred_locations = set(user_profile['preferences']['locations'])
    preferred_job_type = user_profile['preferences']['job_type']
    user_experience_level = user_profile['experience_level']

    for job in all_jobs:
        job_title = job['job_title']
        job_skills = set(json.loads(job['required_skills']))

        if any(role in job_title.lower() for role in desired_roles) and user_skills.intersection(job_skills):
            score = 0
            job_location = job['location']
            job_type = job['job_type']
            job_experience_level = job['experience_level']

            skill_match = len(job_skills.intersection(user_skills))
            score += skill_match * 3

            if job_experience_level == user_experience_level:
                score += 4

            if job_location in preferred_locations:
                score += 3

            if job_type == preferred_job_type:
                score += 2

            score = min(score, 20)

            scored_jobs.append((job, score))

    scored_jobs.sort(key=lambda x: x[1], reverse=True)
    top_jobs = scored_jobs[:5]

    recommendations = []
    for job, score in top_jobs:
        recommendations.append({
            "job_title": job['job_title'],
            "company": job['company'],
            "required_skills": json.loads(job['required_skills']),
            "location": job['location'],
            "job_type": job['job_type'],
            "experience_level": job['experience_level'],
            "score": score  
        })

    conn.close()
    return recommendations

# Protected routes
@app.route('/recommend', methods=['POST'])
@token_required
def recommend_jobs(username):
    user_profile = request.json
    try:
        recommendations = get_job_recommendations(user_profile)
        return jsonify(recommendations)
    except Exception as e:
        print(f"Error during job recommendation: {str(e)}")
        return jsonify({"error": str(e)}), 400

@app.route('/metadata', methods=['GET'])
@token_required
def get_metadata(username):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT required_skills, job_title FROM jobs")
    all_jobs = c.fetchall()

    skills = set()
    job_roles = set()

    for job in all_jobs:
        job_skills = set(json.loads(job['required_skills']))
        skills.update(job_skills)
        job_roles.add(job['job_title'])

    conn.close()

    return jsonify({
        "skills": list(skills),
        "job_roles": list(job_roles)
    })

# Fetch user profile
@app.route('/profile', methods=['GET'])
@token_required
def get_profile(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, contact, email, resume FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "name": user['name'] if user['name'] else "",
            "contact": user['contact'] if user['contact'] else "",
            "email": user['email'] if user['email'] else "",
            "resume": user['resume'] if user['resume'] else ""
        })
    except Exception as e:
        print(f"Error fetching profile: {str(e)}")
        return jsonify({"error": f"Failed to fetch profile: {str(e)}"}), 500

# Update user profile
@app.route('/profile', methods=['POST'])
@token_required
def update_profile(username):
    try:
        name = request.form.get('name')
        contact = request.form.get('contact')
        email = request.form.get('email')
        resume_file = request.files.get('resume')

        # Validate required fields
        if not name or not email:
            print("Missing required fields: name or email")
            return jsonify({"error": "Name and email are required"}), 400

        print(f"Received profile data - Name: {name}, Contact: {contact}, Email: {email}, Resume: {resume_file.filename if resume_file else 'None'}")

        # Handle file upload
        resume_filename = None
        if resume_file and allowed_file(resume_file.filename):
            print(f"Processing resume upload: {resume_file.filename}")
            # Fetch existing resume filename to delete old file
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT resume FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            if user and user['resume']:
                old_resume_path = os.path.join(app.config['UPLOAD_FOLDER'], user['resume'])
                if os.path.exists(old_resume_path):
                    print(f"Deleting old resume: {old_resume_path}")
                    os.remove(old_resume_path)

            # Save new resume
            resume_filename = f"resume_{username}_{resume_file.filename}"
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_filename)
            print(f"Saving new resume to: {resume_path}")
            resume_file.save(resume_path)
            conn.close()
        elif resume_file:
            print("Invalid resume file type")
            return jsonify({"error": "Resume must be a PDF file"}), 400
        else:
            print("No resume file uploaded")

        # Update user profile in the database
        conn = get_db()
        c = conn.cursor()
        if resume_filename:
            print("Updating profile with resume")
            c.execute(
                "UPDATE users SET name = ?, contact = ?, email = ?, resume = ? WHERE username = ?",
                (name, contact, email, resume_filename, username)
            )
        else:
            print("Updating profile without resume")
            c.execute(
                "UPDATE users SET name = ?, contact = ?, email = ? WHERE username = ?",
                (name, contact, email, username)
            )
        conn.commit()
        conn.close()

        print("Profile updated successfully")
        return jsonify({"message": "Profile updated successfully"}), 200

    except Exception as e:
        print(f"Error in update_profile: {str(e)}")
        return jsonify({"error": f"Failed to update profile: {str(e)}"}), 500

# Serve uploaded resumes
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

# Submit a job application
@app.route('/apply', methods=['POST'])
@token_required
def apply_job(username):
    try:
        data = request.json
        job = data.get('job')
        application_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "Applied"  # Default status

        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO applications 
                     (username, job_title, company, location, job_type, experience_level, required_skills, application_date, status) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (username, job['job_title'], job['company'], job['location'], 
                   job['job_type'], job['experience_level'], json.dumps(job['required_skills']), 
                   application_date, status))
        conn.commit()
        conn.close()

        return jsonify({"message": "Application submitted successfully"}), 200
    except Exception as e:
        print(f"Error submitting application: {str(e)}")
        return jsonify({"error": f"Failed to submit application: {str(e)}"}), 500

# Fetch user's applications
@app.route('/applications', methods=['GET'])
@token_required
def get_applications(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM applications WHERE username = ?", (username,))
        applications = c.fetchall()
        conn.close()

        return jsonify([{
            "id": app['id'],
            "job_title": app['job_title'],
            "company": app['company'],
            "location": app['location'],
            "job_type": app['job_type'],
            "experience_level": app['experience_level'],
            "required_skills": json.loads(app['required_skills']),
            "application_date": app['application_date'],
            "status": app['status']
        } for app in applications]), 200
    except Exception as e:
        print(f"Error fetching applications: {str(e)}")
        return jsonify({"error": f"Failed to fetch applications: {str(e)}"}), 500

# Update application status
@app.route('/applications/<int:app_id>', methods=['PUT'])
@token_required
def update_application(username, app_id):
    try:
        data = request.json
        new_status = data.get('status')

        if not new_status:
            return jsonify({"error": "Status is required"}), 400

        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE applications SET status = ? WHERE id = ? AND username = ?",
                  (new_status, app_id, username))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": "Application not found or not authorized"}), 404
        conn.commit()
        conn.close()

        return jsonify({"message": "Application status updated successfully"}), 200
    except Exception as e:
        print(f"Error updating application: {str(e)}")
        return jsonify({"error": f"Failed to update application: {str(e)}"}), 500

# Delete an application
@app.route('/applications/<int:app_id>', methods=['DELETE'])
@token_required
def delete_application(username, app_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM applications WHERE id = ? AND username = ?",
                  (app_id, username))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": "Application not found or not authorized"}), 404
        conn.commit()
        conn.close()

        return jsonify({"message": "Application deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting application: {str(e)}")
        return jsonify({"error": f"Failed to delete application: {str(e)}"}), 500
    
@app.route('/generate_resume', methods=['POST'])
def generate_resume():
    data = request.get_json()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    def write_line(label, value):
        pdf.set_font("Arial", 'B', size=12)
        pdf.cell(200, 10, txt=label, ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=value)
        pdf.ln(2)

    write_line("Name", data['name'])
    write_line("Email", data['email'])
    write_line("Phone", data['phone'])
    write_line("Profile Summary", data['profile'])
    write_line("B.Tech", data['btech'])
    write_line("12th", data['class12'])
    write_line("10th", data['class10'])
    write_line("Projects", data['projects'])
    write_line("Technical Skills", ', '.join(data['techSkills']))
    write_line("Soft Skills", ', '.join(data['softSkills']))
    write_line("Languages", ', '.join(data['languages']))

    output_path = 'resume.pdf'
    pdf.output(output_path)
    print("Sending resume back as PDF.")

    return send_file(output_path, as_attachment=True, mimetype='application/pdf')

@app.route('/')
def home():
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        print(f"Error serving index.html: {str(e)}")
        return f"Error serving index.html: {str(e)}", 500

if __name__ == '__main__':
    # Create uploads folder if it doesn't exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
    print("Database initialized.")
     port = int(os.environ.get("PORT", 5000))  # default to 5000 if PORT isn't set
    app.run(host="0.0.0.0", port=port)
