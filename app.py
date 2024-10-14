from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import time


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.instance_path = os.path.join(os.getcwd(), 'instance')  # Change instance path to a safe location
db = SQLAlchemy(app)

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set upload folder and max file size
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(120), nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'

# Comment model
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(120), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Comment {self.username}>'

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def delete_old_files():
    now = time.time()
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(file_path):
            if now - os.path.getmtime(file_path) > 7 * 24 * 60 * 60:  # 7 days
                os.remove(file_path)

@app.before_request
def create_tables():
    db.create_all()
    # Schedule old file deletion
    delete_old_files()

@app.route('/')
def home():
    comments = Comment.query.order_by(Comment.timestamp.desc()).all()
    return render_template('index.html', logged_in='username' in session, comments=comments)

@app.route('/info')
def info():
    return render_template('info.html', logged_in='username' in session)

@app.route('/contact')
def contact():
    return render_template('contact.html', logged_in='username' in session)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        # Check if the username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already in use. Please choose a different one.')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email, password_hash=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            return redirect(url_for('home'))
        else:
            flash("Invalid login credentials")
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' in session:
        username = session['username']
        user = User.query.filter_by(username=username).first()
        if request.method == 'POST':
            user.bio = request.form['bio']
            # Handle profile picture upload
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and allowed_file(file.filename):
                    if file.mimetype.startswith('image'):
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        user.profile_pic = filename
                    else:
                        flash('File type not allowed.')
                        return redirect(url_for('profile'))
            db.session.commit()
            flash('Profile updated successfully')
        return render_template('profile.html', user=user, logged_in=True)
    else:
        flash("You need to login first.")
        return redirect(url_for('login'))

@app.route('/account-settings', methods=['GET', 'POST'])
def account_settings():
    if 'username' in session:
        username = session['username']
        user = User.query.filter_by(username=username).first()
        if request.method == 'POST':
            if 'email' in request.form:
                user.email = request.form['email']
            if 'password' in request.form:
                user.password_hash = generate_password_hash(request.form['password'])
            db.session.commit()
            flash('Account settings updated successfully')
        return render_template('account_settings.html', user=user, logged_in=True)
    else:
        flash("You need to login first.")
        return redirect(url_for('login'))

@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'username' in session:
        username = session['username']
        content = request.form.get('content', '')
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                if file.mimetype.startswith('image'):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image = filename
                else:
                    flash('File type not allowed.')
                    return redirect(url_for('home'))
        if not content and not image:
            flash('You must provide either a comment or an image.')
            return redirect(url_for('home'))
        new_comment = Comment(username=username, content=content, image=image)
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('home'))
    else:
        flash("You need to login first.")
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))



@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File is too large. Maximum file size is 10MB.')
    return redirect(url_for('profile')), 413

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)