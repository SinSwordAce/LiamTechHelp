from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set upload folder and max file size
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250MB limit

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
    return render_template('index.html', logged_in='username' in session)

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
        
        app.logger.debug(f"Login attempt for username: {username}")
        
        user = User.query.filter_by(username=username).first()
        if user:
            app.logger.debug("User found in database")
            if check_password_hash(user.password_hash, password):
                session['username'] = user.username
                app.logger.debug("Password correct, redirecting to profile")
                return redirect(url_for('profile'))
            else:
                app.logger.debug("Password incorrect")
        else:
            app.logger.debug("User not found")
        
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

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File is too large. Maximum file size is 250MB.')
    return redirect(url_for('profile')), 413

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)