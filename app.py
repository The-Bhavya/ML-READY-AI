from fileinput import filename
import os
import io
import pandas as pd
from flask import (Flask, render_template, request,redirect, url_for, flash, session)
from werkzeug.utils import secure_filename
from modules.data_loader import load_dataframe, allowed_file
from modules.data_summary import get_summary
from modules.eda import generate_visualizations

app = Flask(__name__)
app.secret_key = 'mlreadyai_secret_2025' # needed for flash & session

# Folder where uploaded files are stored temporarily
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 # 50 MB limit

# In-memory store for the current DataFrame (simple global)
# We use a dict so it can be updated from any route

_store = {}
def get_df() -> pd.DataFrame | None:
    return _store.get('df')
def set_df(df: pd.DataFrame):
    _store['df'] = df  

# # Define User model
# class User(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100))
#     email = db.Column(db.String(100), unique=True)
#     password = db.Column(db.String(100))
# # Database initialization with app context
# with app.app_context():
#     db.create_all()


@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('home.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # Check a file was included in the form
        if 'dataset' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(url_for('upload'))

        file = request.files['dataset']

        # Check the user actually selected a file
        if file.filename == '':
            flash('Please select a file before uploading.', 'error')
            return redirect(url_for('upload'))

        # 3. Validate extension
        if not allowed_file(file.filename):
            flash('Unsupported file format. Please upload CSV, Excel, JSON, XML or HTML.', 'error')
            return redirect(url_for('upload'))

        # 4. Save the file safely
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 5. Parse the file into a DataFrame (MODULE 3)
        try:
            df = load_dataframe(filepath)
        except Exception as e:
            flash(f'Could not read file: {e}', 'error')
            return redirect(url_for('upload'))

        set_df(df)
        session['filename'] = filename
        flash(f'"{filename}" uploaded successfully — {df.shape[0]} rows × {df.shape[1]} columns.', 'success')
        return redirect(url_for('summary'))

    return render_template('upload.html')

@app.route('/summary')
def summary():
    df = get_df()
    if df is None:
        flash('Please upload a dataset first.', 'error')
        return redirect(url_for('upload'))
    summary_data = get_summary(df)
    filename = session.get('filename', 'dataset')
    return render_template('summary.html', summary=summary_data,filename=filename)


@app.route('/eda')
def eda():
    df = get_df()
    if df is None:
        flash('Please upload a dataset first.', 'error')
        return redirect(url_for('upload'))
    plots = generate_visualizations(df)
    filename = session.get('filename', 'dataset')
    return render_template('eda.html', plots=plots, filename=filename)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # validations 
        if not name or len(name.strip())<2:
            flash('Name must be at least 2 characters long.', 'error')
            return redirect(url_for('register'))

        if not email or '@' not in email:
            flash('Invalid email address.', 'error')
            return redirect(url_for('register'))
        
        # password must be 8 characters long and a combination of letters and numbers and special characters
        if len(password) < 8 or not any(char.isdigit() for char in password)\
            or not any(char.isalpha() for char in password) or not any (not char.isalnum() for char in password): 

            flash('Password must be at least 8 characters long and contain letters, numbers and special characters.', 'error')
            return redirect(url_for('register'))
        
        #check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.Please log in.', 'error')
            return redirect(url_for('register'))

        # create new user
        hashed_password = generate_password_hash(password)
        new_user = User(name=name.strip(), 
                        email=email.strip(),
                        password=hashed_password
        )
        try: 
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('register'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method =='POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password,password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash('Login successful!','success')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.",'error')
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)