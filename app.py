from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash,send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import psycopg2
from psycopg2 import Error
import os
from dotenv import load_dotenv
from enum import Enum
import openai
from flask_login import login_required, current_user, LoginManager, UserMixin, login_user
from werkzeug.utils import secure_filename
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from string import punctuation
from heapq import nlargest
from flask_sqlalchemy import SQLAlchemy
from flask import current_app
from sqlalchemy import and_
from openai import OpenAI  # Update the import
import random




load_dotenv()  # Load environment variables from .env
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD', '').replace('@', '%40')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY')

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Specify the login route

# Set your OpenAI API key  # Replace with your actual OpenAI API key
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Add this BADGE_CRITERIA dictionary at the top level of your app.py, before the routes
BADGE_CRITERIA = {
    'quick_learner': {
        'title': 'Quick Learner',
        'description': 'Complete your first material',
        'icon': 'fa-bolt',
        'color': '#FFD700'
    },
    'dedicated_reader': {
        'title': 'Dedicated Reader',
        'description': 'Complete 5 materials',
        'icon': 'fa-book-reader',
        'color': '#4CAF50'
    },
    'topic_master': {
        'title': 'Topic Master',
        'description': 'Complete all materials in a topic',
        'icon': 'fa-graduation-cap',
        'color': '#2196F3'
    },
    'course_champion': {
        'title': 'Course Champion',
        'description': 'Complete all topics in a course',
        'icon': 'fa-trophy',
        'color': '#9C27B0'
    }
}

# Database connection function
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'student1'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD')
    )

# Add this before the Goals model
class GoalStatus(Enum):
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    OVERDUE = 'overdue'

# Student Model
class Student(UserMixin, db.Model):
    __tablename__ = 'students'
    
    student_id = db.Column(db.String(50), primary_key=True)
    id = db.synonym('student_id')
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    semester = db.Column(db.String(3), nullable=True)
    preferredlearningstyle = db.Column(db.String(50), default='Not Set')
    streakcount = db.Column(db.Integer, default=0)
    dateofenrollment = db.Column(db.Date, default=datetime.utcnow)
    strengths = db.Column(db.Text, nullable=True)
    weaknesses = db.Column(db.Text, nullable=True)
    goals = db.relationship('Goals', backref='student', lazy=True)

    def get_id(self):
        return str(self.student_id)
    def check_password(self, password):
        return check_password_hash(self.password, password)

# Add this after the Student model
class Goals(db.Model):
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    goal_title = db.Column(db.String(200), nullable=False)
    goal_description = db.Column(db.Text, nullable=True)
    goal_deadline = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='in_progress')
    semester = db.Column(db.Integer, nullable=True)
    goal_type = db.Column(db.String(20), nullable=False, default='short_term')
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=True)

# Add this after the Goals model
class Courses(db.Model):
    __tablename__ = 'courses'
    
    course_id = db.Column(db.Integer, primary_key=True)
    course_title = db.Column(db.String(100), nullable=False)
    course_description = db.Column(db.Text)
    course_duration = db.Column(db.String(50))
    difficulty_level = db.Column(db.String(20))
    semester = db.Column(db.String(3))
    
    # Add relationship
    topics = db.relationship('Topics', backref='course', lazy=True)

# Add this before the Progress model
class Topics(db.Model):
    __tablename__ = 'topics'
    
    topic_id = db.Column(db.Integer, primary_key=True)
    topic_name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=False)
    
    # Add relationship
    topic_materials = db.relationship('TopicMaterial', backref='topic', lazy=True)

class TopicMaterial(db.Model):
    __tablename__ = 'topic_materials'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.topic_id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)



class Note(db.Model):
    _tablename_ = 'notes'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    note_text = db.Column(db.Text)
    page_number = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('Student', backref='notes')


class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.topic_id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('topic_materials.id'), nullable=True)
    completion_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)  # 'completed', 'in_progress'
    read_duration = db.Column(db.Integer, default=0)  # Time spent reading in seconds
    last_page = db.Column(db.Integer, default=0)  # Last page read
    page_timestamps = db.Column(db.JSON, default=dict)  # Store timestamps for each page read

    # Relationships
    student = db.relationship('Student', backref='progress')
    course = db.relationship('Courses', backref='progress')
    topic = db.relationship('Topics', backref='progress')

class Achievement(db.Model):
    _tablename_ = 'achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    badge_type = db.Column(db.String(50), nullable=False)  # 'quick_learner', 'consistent_reader', etc.
    earned_date = db.Column(db.DateTime, default=datetime.utcnow)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=True)
    
    student = db.relationship('Student', backref='achievements')
    course = db.relationship('Courses', backref='achievements')


# Create upload folder if it doesn't exist
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size




@app.route('/upload_material', methods=['POST'])
@login_required
def upload_material():
    try:
        topic_id = request.form.get('topic_id')
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if file and file.filename.endswith('.pdf'):
            # Read the file
            file_data = file.read()
            
            # Create new material
            new_material = TopicMaterial(
                topic_id=topic_id,
                file_name=file.filename,
                file_path=file.filename,
                upload_date=datetime.utcnow()
            )
            
            db.session.add(new_material)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'File uploaded successfully'})
        else:
            return jsonify({'error': 'Invalid file type. Please upload a PDF'}), 400
            
    except Exception as e:
        db.session.rollback()
        print(f"Error uploading file: {str(e)}")
        return jsonify({'error': 'Failed to upload file'}), 500

@app.route('/view_material/<int:material_id>')
@login_required
def view_material(material_id):
    try:
        material = TopicMaterial.query.get_or_404(material_id)
        
        # Get the course_id through the topic relationship
        topic = Topics.query.get(material.topic_id)
        if not topic:
            return jsonify({'error': 'Topic not found'}), 404
            
        # Update path to use 'uploads' folder
        static_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        
        # Check if file exists
        if not os.path.exists(os.path.join(static_folder, material.file_name)):
            print(f"PDF file not found: {material.file_name}")
            return jsonify({'error': 'PDF file not found'}), 404
            
        # Create or update progress entry
        progress = Progress.query.filter_by(
            student_id=current_user.id,
            material_id=material_id
        ).first()
        
        if not progress:
            progress = Progress(
                student_id=current_user.id,
                material_id=material_id,
                topic_id=material.topic_id,
                course_id=topic.course_id,  # Add the course_id
                read_duration=0,
                status='in_progress'
            )
            db.session.add(progress)
            db.session.commit()
        
        # Return the PDF file from the uploads folder
        return send_from_directory(static_folder, material.file_name)
        
    except Exception as e:
        print(f"Error serving PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        
        try:
            student = Student.query.filter_by(student_id=student_id).first()
            
            if student and check_password_hash(student.password, password):
                login_user(student)
                
                student.streakcount += 1
                db.session.commit()
                
                session['student_id'] = student_id
                session['streak_count'] = student.streakcount
                
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            
            flash('Invalid credentials. Please try again.', 'error')
            return render_template('login.html')
                
        except Exception as error:
            print("Error during login:", error)
            flash('An error occurred during login. Please try again.', 'error')
            return render_template('login.html')
    
    return render_template('login.html')
                

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Check if student_id or email already exists
            existing_student = Student.query.filter(
                (Student.student_id == student_id) | (Student.email == email)
            ).first()
            
            if existing_student:
                flash("Student ID or Email already exists", "error")
                return render_template('register.html')
            
            # Create new student with basic information
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_student = Student(
                student_id=student_id,
                name=name,
                email=email,
                password=hashed_password,
                streakcount=0,
                dateofenrollment=date.today()
            )
            
            db.session.add(new_student)
            db.session.commit()
            
            flash("Registration successful! Please login and complete your profile.", "success")
            return redirect(url_for('login'))
            
        except Exception as error:
            print("Error during registration:", error)
            flash("Database error during registration", "error")
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        student = Student.query.get(current_user.id)
        if not student:
            flash('Student not found.', 'error')
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            student.semester = request.form.get('semester')
            student.preferredlearningstyle = request.form.get('learning_style')
            student.strengths = request.form.get('strengths')
            student.weaknesses = request.form.get('weaknesses')
            
            try:
                db.session.commit()
                flash('Profile updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"Error updating profile: {str(e)}")
                flash('Error updating profile. Please try again.', 'error')
            
            return redirect(url_for('profile'))
        
        return render_template('profile.html', 
                             student=student,
                             readonly=student.semester is not None)
                             
    except Exception as error:
        print("Error accessing profile:", error)
        flash('An error occurred while loading the profile.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    try:
        student = Student.query.filter_by(student_id=session['student_id']).first()
        if student:
            # Update session with current streak count
            session['streak_count'] = student.streakcount
            return render_template('dashboard.html', 
                                student=student,
                                streak_count=session['streak_count'])  # Pass streak_count to template
        else:
            flash('Student not found.', 'error')
            return redirect(url_for('login'))
            
    except Exception as error:
        print("Error accessing dashboard:", error)
        flash('An error occurred while loading the dashboard.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('home'))

@app.route('/courses')
@login_required
def courses():
    try:
        student = Student.query.get(current_user.id)
        if not student or not student.semester:
            flash('Please complete your profile first.', 'warning')
            return redirect(url_for('profile'))
        
        # Get all courses with their topics and materials
        courses = db.session.query(Courses).all()
        
        for course in courses:
            # Get topics for each course
            course.topics = Topics.query.filter_by(course_id=course.course_id).all()
            
            for topic in course.topics:
                # Get materials (PDFs) for each topic
                topic.topic_materials = TopicMaterial.query.filter_by(topic_id=topic.topic_id).all()
                
                # Get progress for each material
                for material in topic.topic_materials:
                    progress = Progress.query.filter_by(
                        student_id=current_user.id,
                        material_id=material.id
                    ).first()
                    
                    if progress:
                        material.progress = min(100, (progress.read_duration / 60) * 100)  # 1 minute = 100%
                        material.status = progress.status
                    else:
                        material.progress = 0
                        material.status = 'not_started'
                    
                    # Add the file URL
                    material.file_url = url_for('static', filename=f'uploads/{material.file_name}')
        
        return render_template('courses.html', courses=courses)
        
    except Exception as error:
        print("Error accessing courses:", error)
        flash('An error occurred while loading the courses.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/get_topic_materials/<int:topic_id>')
@login_required
def get_topic_materials(topic_id):
    materials = TopicMaterial.query.filter_by(topic_id=topic_id).all()
    
    # Get completed materials for current user
    completed_materials = Progress.query.filter_by(
        student_id=current_user.id,
        topic_id=topic_id,
        status='completed'
    ).with_entities(Progress.material_id).all()
    
    completed_material_ids = [m.material_id for m in completed_materials]
    
    return jsonify([{
        'id': m.id,
        'filename': m.file_name,
        'upload_date': m.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
        'completed': m.id in completed_material_ids
    } for m in materials])

@app.route('/get_course_materials/<int:topic_id>')
@login_required
def get_course_materials(topic_id):
    materials = TopicMaterial.query.filter_by(topic_id=topic_id).all()
    return jsonify([{
        'id': m.id,
        'filename': m.file_name,
        'path': url_for('static', filename='uploads/' + m.file_name)
    } for m in materials])


@app.route('/goals')
@login_required
def goals():
    try:
        # Get all goals for the current user
        user_goals = Goals.query.filter_by(student_id=current_user.id).all()
        
        # Get all courses for the generate goals buttons
        courses = Courses.query.all()
        
        return render_template('goals.html',
                             goals=user_goals,
                             courses=courses)
    except Exception as e:
        print(f"Error accessing goals: {str(e)}")
        flash('An error occurred while loading goals.', 'error')
        return redirect(url_for('dashboard'))


def generate_course_based_goals(student, courses):
    try:
        for course in courses:
            # Get course topics and materials
            topics = Topics.query.filter_by(course_id=course.course_id).all()
            
            # Generate AI goals for this course
            success = generate_ai_goals(student.student_id, course.course_id)
            
            if not success:
                print(f"Failed to generate goals for course {course.course_title}")
                
    except Exception as e:
        print(f"Error generating course-based goals: {str(e)}")
        db.session.rollback()


def generate_ai_goals(student_id, course_id):
    try:
        # Get course information
        course = Courses.query.get(course_id)
        if not course:
            return False

        # Get course topics
        topics = Topics.query.filter_by(course_id=course_id).all()
        topic_names = [topic.topic_name for topic in topics]

        # Template-based goals
        goal_templates = {
            'short_term': [
                {
                    'title': f'Master Fundamentals of {course.course_title}',
                    'description': f'Complete introductory materials and understand basic concepts of {", ".join(topic_names[:2] if topic_names else ["the course"])}.',
                    'weeks': 2
                },
                {
                    'title': f'Build Foundation in {course.course_title}',
                    'description': f'Complete initial assignments and practice exercises for {", ".join(topic_names[:2] if topic_names else ["core topics"])}.',
                    'weeks': 2
                }
            ],
            'mid_term': [
                {
                    'title': f'Apply {course.course_title} Concepts',
                    'description': f'Work on practical applications and projects related to {", ".join(topic_names[2:4] if len(topic_names) > 2 else ["course topics"])}.',
                    'weeks': 4
                },
                {
                    'title': f'Develop Skills in {course.course_title}',
                    'description': f'Complete intermediate level assignments and start working on course projects.',
                    'weeks': 4
                }
            ],
            'long_term': [
                {
                    'title': f'Advanced Understanding of {course.course_title}',
                    'description': f'Master advanced concepts and complete comprehensive projects covering {", ".join(topic_names)}.',
                    'weeks': 12
                },
                {
                    'title': f'Complete Mastery of {course.course_title}',
                    'description': f'Achieve proficiency in all course topics and successfully complete all course requirements.',
                    'weeks': 12
                }
            ]
        }

        # Generate goals for each type
        for goal_type, templates in goal_templates.items():
            # Randomly select one template from each type
            template = random.choice(templates)
            
            new_goal = Goals(
                student_id=student_id,
                goal_title=template['title'],
                goal_description=template['description'],
                goal_deadline=datetime.now() + timedelta(weeks=template['weeks']),
                status='in_progress',
                goal_type=goal_type,
                course_id=course_id
            )
            db.session.add(new_goal)

        db.session.commit()
        return True

    except Exception as e:
        print(f"Error generating goals: {str(e)}")
        db.session.rollback()
        return False

def get_goal_templates(course_title, topics):
    return {
        'short_term': [
            {
                'title': f'Master Fundamentals of {course_title}',
                'description': f'Complete introductory materials and understand basic concepts of {", ".join(topics[:2] if topics else ["the course"])}.',
                'weeks': 2
            },
            {
                'title': f'Build Foundation in {course_title}',
                'description': f'Complete initial assignments and practice exercises for {", ".join(topics[:2] if topics else ["core topics"])}.',
                'weeks': 2
            },
            {
                'title': f'Getting Started with {course_title}',
                'description': f'Familiarize yourself with the basic principles and terminology of {", ".join(topics[:2] if topics else ["the subject"])}.',
                'weeks': 2
            }
        ],
        'mid_term': [
            {
                'title': f'Apply {course_title} Concepts',
                'description': f'Work on practical applications and projects related to {", ".join(topics[2:4] if len(topics) > 2 else ["course topics"])}.',
                'weeks': 4
            },
            {
                'title': f'Develop Skills in {course_title}',
                'description': f'Complete intermediate level assignments and start working on course projects.',
                'weeks': 4
            },
            {
                'title': f'Practical Implementation in {course_title}',
                'description': f'Apply theoretical knowledge to solve real-world problems and complete hands-on exercises.',
                'weeks': 4
            }
        ],
        'long_term': [
            {
                'title': f'Advanced Understanding of {course_title}',
                'description': f'Master advanced concepts and complete comprehensive projects covering {", ".join(topics)}.',
                'weeks': 12
            },
            {
                'title': f'Complete Mastery of {course_title}',
                'description': f'Achieve proficiency in all course topics and successfully complete all course requirements.',
                'weeks': 12
            },
            {
                'title': f'Expert Level Knowledge in {course_title}',
                'description': f'Demonstrate comprehensive understanding through completion of advanced projects and mastery of all course concepts.',
                'weeks': 12
            }
        ]
    }

def generate_ai_goals(student_id, course_id):
    try:
        course = Courses.query.get(course_id)
        if not course:
            return False

        topics = Topics.query.filter_by(course_id=course_id).all()
        topic_names = [topic.topic_name for topic in topics]

        # Get templates based on course and topics
        templates = get_goal_templates(course.course_title, topic_names)

        # Generate goals for each type
        for goal_type, goal_templates in templates.items():
            template = random.choice(goal_templates)
            
            new_goal = Goals(
                student_id=student_id,
                goal_title=template['title'],
                goal_description=template['description'],
                goal_deadline=datetime.now() + timedelta(weeks=template['weeks']),
                status='in_progress',
                goal_type=goal_type,
                course_id=course_id
            )
            db.session.add(new_goal)

        db.session.commit()
        return True

    except Exception as e:
        print(f"Error generating goals: {str(e)}")
        db.session.rollback()
        return False




@app.route('/generate_goals/<int:course_id>', methods=['POST'])
@login_required
def generate_course_goals(course_id):
    try:
        # Delete existing goals for this course
        Goals.query.filter_by(
            student_id=current_user.id,
            course_id=course_id
        ).delete()
        
        # Generate new goals
        success = generate_ai_goals(current_user.id, course_id)
        
        if success:
            # Fetch the newly generated goals
            goals = Goals.query.filter_by(
                student_id=current_user.id,
                course_id=course_id
            ).all()
            
            # Format goals for JSON response
            goals_data = [{
                'id': goal.id,
                'title': goal.goal_title,
                'description': goal.goal_description,
                'deadline': goal.goal_deadline.strftime('%Y-%m-%d'),
                'status': goal.status,
                'type': goal.goal_type
            } for goal in goals]
            
            return jsonify({
                'success': True,
                'goals': goals_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate goals'
            }), 500
            
    except Exception as e:
        print(f"Error in generate_course_goals: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@app.route('/regenerate_goals', methods=['POST'])
@login_required
def regenerate_goals():
    try:
        # Delete existing goals
        Goals.query.filter_by(student_id=current_user.id).delete()
        db.session.commit()

        # Get enrolled courses
        courses = Courses.query.all()  # Or filter by enrollment

        # Generate new goals for each course
        for course in courses:
            generate_ai_goals(current_user.id, course.course_id)

        flash('Goals have been regenerated successfully!', 'success')
        return redirect(url_for('goals'))
    except Exception as e:
        print("Error regenerating goals:", e)
        flash('Failed to regenerate goals. Please try again.', 'error')
        return redirect(url_for('goals'))


@app.route('/update_goal_status', methods=['POST'])
@login_required
def update_goal_status():
    try:
        data = request.get_json()
        goal_id = data.get('goal_id')
        completed = data.get('completed')
        
        goal = Goals.query.get_or_404(goal_id)
        
        # Verify the goal belongs to the current user
        if goal.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update goal status
        goal.status = 'completed' if completed else 'in_progress'
        
        # If this is a course-related goal and it's completed, check other goals
        if goal.course_id and completed:
            # Check if all short-term goals for this course are completed
            course_goals = Goals.query.filter_by(
                student_id=current_user.id,
                course_id=goal.course_id,
                goal_type='short_term'
            ).all()
            
            if all(g.status == 'completed' for g in course_goals):
                # Find and update the long-term goal for this course
                long_term_goal = Goals.query.filter_by(
                    student_id=current_user.id,
                    course_id=goal.course_id,
                    goal_type='long_term'
                ).first()
                
                if long_term_goal:
                    long_term_goal.status = 'completed'
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as error:
        print("Error updating goal status:", error)
        return jsonify({'error': 'Failed to update goal status'}), 500


@app.route('/chatbot', methods=['POST'])
def chatbot():
    user_input = request.json.get('message')
    
    # Call OpenAI's API
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or "gpt-4"
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        
        bot_response = response['choices'][0]['message']['content']
        return jsonify({'response': bot_response})
    
    except Exception as e:
        return jsonify({'response': 'Error: ' + str(e)})

@app.route('/progress')
@login_required
def progress():
    try:
        student = Student.query.get(current_user.id)
        if not student:
            flash('Student not found.', 'error')
            return redirect(url_for('dashboard'))

        courses = Courses.query.all()
        progress_data = []

        for course in courses:
            course_data = {
                'title': course.course_title,
                'topics': [],
                'total_materials': 0,
                'completed_materials': 0,
                'progress_percentage': 0  # Changed from total_progress
            }

            topics = Topics.query.filter_by(course_id=course.course_id).all()
            
            for topic in topics:
                topic_data = {
                    'name': topic.topic_name,
                    'materials': [],
                    'total_materials': 0,
                    'completed_materials': 0,
                    'progress_percentage': 0  # Changed from total_progress
                }

                materials = TopicMaterial.query.filter_by(topic_id=topic.topic_id).all()
                total_topic_progress = 0
                
                for material in materials:
                    progress = Progress.query.filter_by(
                        student_id=student.student_id,
                        material_id=material.id
                    ).first()

                    material_data = {
                        'name': material.file_name,
                        'progress': 0,
                        'status': 'not_started'
                    }

                    if progress:
                        if progress.status == 'completed':
                            material_data['progress'] = 100
                            topic_data['completed_materials'] += 1
                            course_data['completed_materials'] += 1
                        else:
                            material_data['progress'] = min(100, (progress.read_duration / 60) * 100)
                        material_data['status'] = progress.status
                        total_topic_progress += material_data['progress']

                    topic_data['materials'].append(material_data)
                    topic_data['total_materials'] += 1
                    course_data['total_materials'] += 1

                # Calculate average progress for topic
                if topic_data['total_materials'] > 0:
                    topic_data['progress_percentage'] = total_topic_progress / topic_data['total_materials']
                
                course_data['topics'].append(topic_data)
                course_data['progress_percentage'] += topic_data['progress_percentage']

            # Calculate average progress for course
            if len(course_data['topics']) > 0:
                course_data['progress_percentage'] /= len(course_data['topics'])
            
            progress_data.append(course_data)

        return render_template('progress.html', progress_data=progress_data)

    except Exception as error:
        print(f"Error in progress route: {str(error)}")
        flash('An error occurred while loading progress.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/update_reading_progress/<int:material_id>', methods=['POST'])
@login_required
def update_reading_progress(material_id):
    try:
        data = request.json
        scroll_percentage = data.get('scrollPercentage', 0)  # How far user has scrolled
        time_spent = data.get('timeSpent', 0)  # Time spent in seconds
        
        # Only update if meaningful progress is made
        if scroll_percentage > 0 and time_spent > 10:  # Minimum 10 seconds
            progress = Progress.query.filter_by(
                student_id=current_user.id,
                material_id=material_id
            ).first()
            
            if not progress:
                material = TopicMaterial.query.get_or_404(material_id)
                progress = Progress(
                    student_id=current_user.id,
                    material_id=material_id,
                    topic_id=material.topic_id,
                    read_duration=0,
                    status='in_progress'
                )
                db.session.add(progress)
            
            # Update progress based on time spent and scroll position
            progress.read_duration = max(progress.read_duration or 0, time_spent)
            
            # Mark as completed if:
            # 1. User has scrolled through 90% of content
            # 2. Spent at least 60 seconds (1 minute) reading
            if scroll_percentage > 90 and time_spent >= 60:
                progress.status = 'completed'
                progress.read_duration = 60  # Set to full duration when completed
            else:
                progress.status = 'in_progress'
            
            db.session.commit()
            
            # Calculate percentage (60 seconds = 100%)
            percentage = min(100, (progress.read_duration / 60) * 100)
            
            return jsonify({
                'success': True,
                'progress': percentage,
                'status': progress.status
            })
            
    except Exception as e:
        print(f"Error updating progress: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/mark_as_done/<int:material_id>', methods=['POST'])
@login_required
def mark_as_done(material_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    try:
        cur = conn.cursor()
        
        # Get material info
        cur.execute("""
            SELECT tm.topic_id, t.course_id
            FROM topic_materials tm
            JOIN topics t ON tm.topic_id = t.topic_id
            WHERE tm.id = %s
        """, (material_id,))
        
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'Material not found'}), 404
            
        topic_id, course_id = result
        
        # Update or create progress entry
        cur.execute("""
            INSERT INTO progress (
                student_id, course_id, topic_id, 
                material_id, status, completion_date
            ) VALUES (%s, %s, %s, %s, 'completed', CURRENT_TIMESTAMP)
            ON CONFLICT (student_id, course_id, topic_id, material_id)
            DO UPDATE SET 
                status = 'completed',
                completion_date = CURRENT_TIMESTAMP
            RETURNING id
        """, (session['student_id'], course_id, topic_id, material_id))
        
        progress_id = cur.fetchone()[0]
        conn.commit()
        
        # Check and award achievements
        check_and_award_achievements(session['student_id'], material_id)
        
        return jsonify({
            'success': True,
            'message': 'Material marked as completed',
            'progress_id': progress_id
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Error in mark_as_done: {str(e)}")
        return jsonify({'error': 'Failed to update progress'}), 500
    finally:
        if conn:
            cur.close()
            conn.close()

def check_and_award_achievements(student_id, material_id):
    try:
        # Get completed materials count
        completed_count = Progress.query.filter_by(
            student_id=student_id,
            status='completed'
        ).count()
        
        # Get the current material's topic and course
        material = TopicMaterial.query.get(material_id)
        topic = Topics.query.get(material.topic_id)
        
        achievements = []
        
        # Check for Quick Learner badge
        if completed_count == 1:
            achievements.append('quick_learner')
            
        # Check for Dedicated Reader badge
        if completed_count == 5:
            achievements.append('dedicated_reader')
            
        # Check for Topic Master badge
        topic_materials = TopicMaterial.query.filter_by(topic_id=topic.topic_id).count()
        completed_in_topic = Progress.query.filter_by(
            student_id=student_id,
            topic_id=topic.topic_id,
            status='completed'
        ).count()
        
        if topic_materials == completed_in_topic:
            achievements.append('topic_master')
            
        # Check for Course Champion badge
        course_topics = Topics.query.filter_by(course_id=topic.course_id).all()
        is_course_complete = True
        
        for course_topic in course_topics:
            topic_materials = TopicMaterial.query.filter_by(topic_id=course_topic.topic_id).count()
            completed_in_topic = Progress.query.filter_by(
                student_id=student_id,
                topic_id=course_topic.topic_id,
                status='completed'
            ).count()
            
            if topic_materials != completed_in_topic:
                is_course_complete = False
                break
                
        if is_course_complete:
            achievements.append('course_champion')
            
        # Award new achievements
        for badge_type in achievements:
            existing_achievement = Achievement.query.filter_by(
                student_id=student_id,
                badge_type=badge_type
            ).first()
            
            if not existing_achievement:
                new_achievement = Achievement(
                    student_id=student_id,
                    badge_type=badge_type,
                    earned_date=datetime.utcnow()
                )
                db.session.add(new_achievement)
                
                # Create notification for new achievement
                notification = Notification(
                    student_id=student_id,
                    title=f"New Achievement: {BADGE_CRITERIA[badge_type]['title']}",
                    message=f"Congratulations! You've earned the {BADGE_CRITERIA[badge_type]['title']} badge!",
                    notification_type='achievement'
                )
                db.session.add(notification)
                
        db.session.commit()
        return achievements
        
    except Exception as e:
        print(f"Error checking achievements: {str(e)}")
        db.session.rollback()
        return []

@app.route('/achievements')
@login_required
def achievements():
    try:
        # Get user achievements
        student_achievements = Achievement.query.filter_by(
            student_id=current_user.id
        ).order_by(Achievement.earned_date.desc()).all()
        
        return render_template('achievements.html',
                             BADGE_CRITERIA=BADGE_CRITERIA,
                             student_achievements=student_achievements)
                             
    except Exception as error:
        print("Error accessing achievements:", error)
        flash('An error occurred while loading achievements.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/placement')
@login_required
def placement():
    return render_template('placement.html')

@app.route('/notes')
@login_required
def notes():
    """
    Route to display the chatbot interface
    """
    try:
        return render_template('notes.html')
    except Exception as e:
        print(f"Error loading chatbot page: {str(e)}")
        flash('Error loading the chatbot.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/about')
def about():
    return render_template('about.html')

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# Add this function in app.py after your model definitions and before the routes
def add_static_pdfs():
    # Dictionary mapping topic_ids to their PDF files in static folder
    topic_pdf_map = {
        1: 'intro_to_dbms.pdf',
        2: 'dbms_environment.pdf',
        3: 'relational_model.pdf',
        4: 'basic_sql.pdf',
        5: 'advanced_sql.pdf',
        6: 'sql_programming.pdf',
        7: 'indexing.pdf',
        8: 'query_processing.pdf',
        9: 'mlops_intro.pdf',
        10: 'model_deployment.pdf',
        11: 'pipeline_management.pdf',
        12: 'management_basics.pdf',
        13: 'economic_principles.pdf',
        14: 'business_strategy.pdf',
        15: 'ai_in_software.pdf',
        16: 'intelligent_systems.pdf',
        17: 'software_integration.pdf'
    }

    try:
        print("Starting PDF addition process...")
        for topic_id, pdf_filename in topic_pdf_map.items():
            print(f"Processing topic {topic_id} with file {pdf_filename}")
            
            # Create path relative to static folder
            file_path = f'static/uploads/pdfs/{pdf_filename}'
            
            # Check if material already exists
            existing_material = TopicMaterial.query.filter_by(topic_id=topic_id).first()
            
            if existing_material:
                print(f"Updating existing material for topic {topic_id}")
                existing_material.file_name = pdf_filename
                existing_material.file_path = file_path
            else:
                print(f"Creating new material for topic {topic_id}")
                new_material = TopicMaterial(
                    topic_id=topic_id,
                    file_name=pdf_filename,
                    file_path=file_path,
                    upload_date=datetime.utcnow()
                )
                db.session.add(new_material)
        
        db.session.commit()
        print("PDFs added successfully!")
        
        # Verify the additions
        all_materials = TopicMaterial.query.all()
        print(f"Total materials in database: {len(all_materials)}")
        for material in all_materials:
            print(f"Material ID: {material.id}, Topic ID: {material.topic_id}, File: {material.file_name}")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding PDFs: {str(e)}")
        raise e  # Re-raise the exception to see the full error trace

# Add this route to check the current materials in the database
@app.route('/check_materials')
@login_required
def check_materials():
    try:
        materials = TopicMaterial.query.all()
        return jsonify({
            'count': len(materials),
            'materials': [
                {
                    'id': m.id,
                    'topic_id': m.topic_id,
                    'file_name': m.file_name,
                    'file_path': m.file_path
                } for m in materials
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)})

def initialize_pdfs():
    try:
        # Update path to use 'uploads' folder
        pdf_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        
        # Dictionary mapping topic_ids to their PDF files
        topic_pdf_map = {
            1: 'intro_to_dbms.pdf',
            2: 'dbms_environment.pdf',
            3: 'relational_model.pdf',
            4: 'basic_sql.pdf',
            5: 'advanced_sql.pdf',
            6: 'sql_programming.pdf',
            7: 'indexing.pdf',
            8: 'query_processing.pdf',
            9: 'mlops_intro.pdf',
            10: 'model_deployment.pdf',
            11: 'pipeline_management.pdf',
            12: 'management_basics.pdf',
            13: 'economic_principles.pdf',
            14: 'business_strategy.pdf',
            15: 'ai_in_software.pdf',
            16: 'intelligent_systems.pdf',
            17: 'software_integration.pdf'
        }

        # First, clear existing records
        db.session.query(TopicMaterial).delete()
        db.session.commit()
        
        print("Starting PDF initialization...")
        
        # Insert new records with updated file paths
        for topic_id, pdf_name in topic_pdf_map.items():
            file_path = os.path.join('static', 'uploads', pdf_name)
            
            # Create new material record
            new_material = TopicMaterial(
                topic_id=topic_id,
                file_name=pdf_name,
                file_path=file_path,
                upload_date=datetime.utcnow()
            )
            db.session.add(new_material)
            print(f"Added material for topic {topic_id}: {pdf_name}")
        
        db.session.commit()
        print("PDF initialization completed successfully!")
        
        # Verify the insertions
        materials = TopicMaterial.query.all()
        print(f"\nTotal materials added: {len(materials)}")
        for material in materials:
            print(f"Topic {material.topic_id}: {material.file_name}")
            
        return True
        
    except Exception as e:
        print(f"Error initializing PDFs: {str(e)}")
        db.session.rollback()
        return False

# Add this route to initialize PDFs
@app.route('/initialize_pdfs')
@login_required
def init_pdfs():
    if initialize_pdfs():
        flash('PDFs initialized successfully!', 'success')
    else:
        flash('Error initializing PDFs.', 'error')
    return redirect(url_for('dashboard'))

# Add this route to check progress
@app.route('/check_progress/<int:material_id>')
@login_required
def check_progress(material_id):
    try:
        progress = Progress.query.filter_by(
            student_id=current_user.id,
            material_id=material_id
        ).first()
        
        if progress:
            return jsonify({
                'progress': min(100, (progress.read_duration / 60) * 100),
                'status': progress.status
            })
        else:
            return jsonify({
                'progress': 0,
                'status': 'not_started'
            })
            
    except Exception as e:
        print(f"Error checking progress: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add this route to check file paths with updated folder structure
@app.route('/check_pdf_paths')
@login_required
def check_pdf_paths():
    try:
        materials = TopicMaterial.query.all()
        static_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        
        paths = []
        for material in materials:
            full_path = os.path.join(static_folder, material.file_name)
            paths.append({
                'id': material.id,
                'file_name': material.file_name,
                'full_path': full_path,
                'exists': os.path.exists(full_path)
            })
            
        return jsonify(paths)
    except Exception as e:
        return jsonify({'error': str(e)})


# Add this at the end of your app.py, just before running the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create all database tables
        initialize_pdfs()  # Initialize PDFs
    app.run(debug=True) 