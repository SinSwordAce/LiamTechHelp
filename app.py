import os
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = '1892'

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set upload folder and max file size
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250MB limit

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Set up logging
log_dir = os.path.join(basedir, 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
file_handler = RotatingFileHandler(os.path.join(log_dir, 'app.log'), maxBytes=10240, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

app.logger.setLevel(logging.INFO)
app.logger.info('App startup')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(120), nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'

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

@app.before_request
def create_tables():
    db.create_all()

@app.route('/')
def home():
    comments = Comment.query.order_by(Comment.timestamp.desc()).all()
    logged_in = 'username' in session
    return render_template('index.html', logged_in=logged_in, comments=comments)

@app.route('/home')
def home_page():
    return render_template('index.html')

@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

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

@app.route('/profile')
def profile():
    if 'username' in session:
        username = session['username']
        user = User.query.filter_by(username=username).first()
        return render_template('profile.html', user=user, logged_in=True)
    else:
        flash("You need to login first.")
        return redirect(url_for('login'))

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' in session:
        username = session['username']
        user = User.query.filter_by(username=username).first()

        if request.method == 'POST':
            user.bio = request.form['bio']

            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    user.profile_pic = filename
                else:
                    flash('File type not allowed.')
                    return redirect(url_for('edit_profile'))

            db.session.commit()
            flash('Profile updated successfully')
            return redirect(url_for('profile'))

        return render_template('edit_profile.html', user=user, logged_in=True)
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            return redirect(url_for('profile'))
        else:
            flash("Invalid login credentials")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File is too large. Maximum file size is 10MB.')
    return redirect(url_for('profile')), 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)