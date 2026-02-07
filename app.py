# app.py (Imports at the top)
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from transcribe import transcribe_audio_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename
import os
from tts import generate_audio
from flask import send_from_directory
import requests  # 🔁 For calling Krishna’s FastAPI from Flask
from flask_cors import CORS

from flask import stream_with_context, Response

# --- NEW IMPORTS FOR AUTH & FORMS ---
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, HiddenField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, Optional, URL
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_bcrypt import Bcrypt
# --- END NEW IMPORTS ---


app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pdfs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-this') # 👈 UPDATED for Env

db = SQLAlchemy(app)
bcrypt = Bcrypt(app) # 👈 ADD THIS
login_manager = LoginManager(app) # 👈 ADD THIS
login_manager.login_view = 'login' # 👈 Page to redirect to
login_manager.login_message = 'Please log in to access this page.' # 👈 Flash message
login_manager.login_message_category = 'info' # 👈 Flash message category

# --- NEW: User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- UPDATED: User Model ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True, default='New User') # 👈 NEW: Full name
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Roles: 'teacher', 'professional', 'institute', 'student', 'student_invited' (placeholder)
    role = db.Column(db.String(50), nullable=False)

    institution = db.Column(db.String(200), nullable=True) # 👈 NEW: Institution/Org

    # 👈 NEW: Link for tracking who invited a student
    invited_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    chatbots = db.relationship('Chatbot', backref='owner', lazy=True, cascade="all, delete-orphan")
    
    # 👈 NEW: For a teacher to see their *invited* students (placeholders)
    # This finds Users where 'invited_by_id' matches this user's 'id'
    invited_users_placeholders = db.relationship('User', 
                                     backref=db.backref('inviter', remote_side=[id]), 
                                     lazy='dynamic',
                                     foreign_keys=[invited_by_id])

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    # 👈 NEW: Helper to show 'Name' or 'Username'
    def get_display_name(self):
        return self.name if self.name and self.name != 'New User' else self.username

# --- UPDATED: Chatbot Model ---
class Chatbot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    domain = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # 👈 NEW: Relationship to uploaded PDFs
    pdfs = db.relationship('UploadedPDF', backref='chatbot', lazy=True, cascade="all, delete-orphan")
    # 👈 NEW: For "coming soon" website links
    website_url = db.Column(db.String(500), nullable=True) 

    def __repr__(self):
        return f"Chatbot('{self.name}', '{self.domain}')"

# --- UPDATED: UploadedPDF Model ---
class UploadedPDF(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    file_size_kb = db.Column(db.Integer, nullable=True)
    pages = db.Column(db.Integer, nullable=True)
    # 👈 REMOVED: session_id (no longer needed)
    
    # 👈 NEW: Link PDF to a *specific chatbot*, not just a user
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbot.id'), nullable=False)


# --- NEW: Flask-WTF Forms ---

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)]) # 👈 NEW
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    role = HiddenField('Role', validators=[DataRequired()])
    submit = SubmitField('Create Account')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        # Allow validation *if* it's just an invited placeholder, but not if it's an active user
        if user and user.role not in ['student_invited']:
            raise ValidationError('That email is already in use by an active account.')

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# 👈 NEW: Form for Profile Page
class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address (Read-Only)', validators=[DataRequired(), Email()], render_kw={'readonly': True})
    username = StringField('Username (Read-Only)', validators=[DataRequired()], render_kw={'readonly': True})
    institution = StringField('Institution / Organization', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Update Profile')

# Forms removed: BotConfigForm, InviteStudentForm, OrganizationForm
# Bot creation, student invites, and org management UI removed
    
# --- AUTHENTICATION & WELCOME ROUTES ---

@app.route("/")
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('welcome.html', title='Welcome')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('welcome'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Check if email is from an invited placeholder
        invited_placeholder = User.query.filter_by(email=form.email.data, role='student_invited').first()
        
        user = None # Initialize user to None

        if invited_placeholder:
            # --- CORRECTED LOGIC: UPDATE THE PLACEHOLDER ---
            user = invited_placeholder # Assign the existing placeholder to 'user'
            user.name = form.name.data
            user.username = form.username.data
            user.set_password(form.password.data) # Set the new password
            user.role = form.role.data # Change role from 'student_invited' to 'student'
            # invited_by_id is already correctly set on the placeholder
            # No need to db.session.add(user) as it's an existing object
        else:
            # This is a normal (non-invited) registration
            user = User(
                name=form.name.data, 
                username=form.username.data, 
                email=form.email.data, 
                role=form.role.data
            )
            user.set_password(form.password.data)
            db.session.add(user) # Only add if it's a completely new user
        
        db.session.commit() # Commit the changes (either update or add)
        
        login_user(user)
        flash(f'Account created for {user.get_display_name()}! You are now logged in.', 'success')
        return redirect(url_for('chat'))
            
    role = request.args.get('role', 'student')
    form.role.data = role
    
    return render_template('register.html', title='Register', form=form, role=role.title())

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('welcome'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f'Welcome back, {user.get_display_name()}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('chat'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
            
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- CORE APPLICATION ROUTES ---

# Dashboard route removed - bot creation, student invites, and org management UI removed
# Database models (User, Chatbot, UploadedPDF) kept intact for existing functionality

# 👈 --- NEW: Profile Page Route ---
@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.institution = form.institution.data
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('profile'))
    
    # Pre-fill the form with existing data on GET request
    form.name.data = current_user.name
    form.email.data = current_user.email
    form.username.data = current_user.username
    form.institution.data = current_user.institution
    
    instructor = None
    if current_user.role == 'student' and current_user.invited_by_id:
        instructor = User.query.get(current_user.invited_by_id)
        
    return render_template('profile.html', title='My Profile', form=form, instructor=instructor)

# --- CHAT & KNOWLEDGE BASE ROUTES ---

@app.route("/chat")
@login_required
def chat():
    # This just renders the chat page. The old PDF sidebar logic is removed.
    # We will later add logic to select *which* bot to chat with.
    return render_template("index.html", title='AI Chat Assistant')

# 👈 NEW: /knowledge/upload route
@app.route("/knowledge/upload", methods=["GET"])
@login_required
def upload():
    # Fetch user's bots to populate the dropdown
    user_bots = Chatbot.query.filter_by(user_id=current_user.id).all()
    if not user_bots:
        flash('You must have an AI Assistant configured before you can upload knowledge. Please contact your administrator.', 'warning')
        return redirect(url_for('chat'))
        
    return render_template("upload.html", title='Upload Knowledge', bots=user_bots)

# --- UPDATED: /upload/preview route ---
@app.route("/upload/preview", methods=["POST"])
@login_required
def preview_pdf():
    pdf_file = request.files.get("pdf")
    chatbot_id = request.form.get("chatbot_id") # 👈 Get selected bot ID
    user_bots = Chatbot.query.filter_by(user_id=current_user.id).all()

    if not pdf_file:
        flash("No file selected for upload.", 'danger')
        return render_template("upload.html", title='Upload Knowledge', bots=user_bots)
    if not chatbot_id:
        flash("You must select an AI Assistant to link this knowledge to.", 'danger')
        return render_template("upload.html", title='Upload Knowledge', bots=user_bots, error="You must select an assistant.")

    # Send file to backend FastAPI /upload endpoint
    backend_url = "http://127.0.0.1:8000/upload"
    files = {"files": (pdf_file.filename, pdf_file.stream, pdf_file.mimetype)}
    try:
        resp = requests.post(backend_url, files=files, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            flash(f"Upload successful: {result.get('message', '')}", 'success')
        else:
            flash(f"Upload failed: {resp.text}", 'danger')
    except Exception as e:
        flash(f"Error uploading to backend: {str(e)}", 'danger')

    # No local save, no preview image
    return render_template("upload.html", title='Upload Knowledge', bots=user_bots, selected_bot_id=int(chatbot_id))

# --- UPDATED: /upload/submit route ---
@app.route("/upload/submit", methods=["POST"])
@login_required
def upload_submit():
    # 👈 Link PDF to the selected chatbot
    new_pdf = UploadedPDF(
        filename=request.form["filename"],
        filepath=request.form["filepath"],
        file_size_kb=int(request.form["filesize"]),
        pages=int(request.form["pages"]),
        chatbot_id=int(request.form["chatbot_id"]) # 👈 Save the bot ID
    )
    db.session.add(new_pdf)
    db.session.commit()
    
    flash(f'File "{request.form["filename"]}" uploaded successfully.', 'success')
    return redirect(url_for('upload')) # Stay on upload page


# --- API / UTILITY ROUTES ---

# 👈 NEW: Custom route to serve preview images from the UPLOADS folder
@app.route('/uploads/previews/<filename>')
def uploaded_preview(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'previews'), filename)

@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400
    audio_file = request.files["audio"]
    try:
        text = transcribe_audio_file(audio_file)
        return jsonify({"transcribedText": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Constant for static response
STATIC_MESSAGE = "The backend is currently under development. Please check back later for the full AI experience."

@app.route("/speak", methods=["POST"])
def speak():
    # Optimization: Ignore input text, always use static audio for the static message
    audio_filename = 'audio/backend_message.mp3'
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], '../static', audio_filename)
    
    # Generate once if not exists
    if not os.path.exists(audio_path):
        from tts import generate_audio
        generate_audio(STATIC_MESSAGE, audio_path)
        
    return jsonify({"audio_url": url_for('static', filename=audio_filename)})

# 👈 Set your FastAPI URL here
BASE_FASTAPI_URL = os.environ.get('BASE_FASTAPI_URL', "http://127.0.0.1:8000") # 👈 UPDATED for Env

@app.route("/stream_response", methods=["POST"])
def stream_response():
    question = request.json.get("question")
    if not question:
        return jsonify({"error": "Missing question"}), 400

    import json as json_lib
    import time
    
    @stream_with_context
    def generate():
        # Simulate thinking delay
        time.sleep(0.5)
        
        # Stream the message word by word to mimic AI generation
        words = STATIC_MESSAGE.split(' ')
        for i, word in enumerate(words):
            # Add space if not the first word
            chunk = word if i == 0 else " " + word
            
            # 1. Yield the token event (for displaying text)
            yield f"event: token\ndata: {json_lib.dumps({'text': chunk})}\n\n"
            time.sleep(0.05) # Simulate typing speed
            
        # 2. Yield the final_response event (to trigger TTS and finalize)
        yield f"event: final_response\ndata: {json_lib.dumps({'text': STATIC_MESSAGE})}\n\n"

    return Response(generate(), content_type='text/event-stream')

@app.route('/favicon.ico')
def favicon():
    return '', 204

# --- NEW: Placeholder Routes for Sidebar Navigation ---
@app.route("/resources")
@login_required
def resources():
    return render_template("resources.html", title="Resources/Documents")

# Removed routes: /knowledge_base and /admin_tools (unused pages)

# --- App Execution ---
if __name__ == "__main__":
    # Ensure all necessary directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'previews'), exist_ok=True)
    os.makedirs('static/audio', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)

    with app.app_context():
        db.create_all() # This creates/updates all tables (User, Chatbot, UploadedPDF)
    
    # 👈 UPDATED: Use PORT from environment for Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False) # Debug=False for production!