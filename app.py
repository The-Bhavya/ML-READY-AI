from fileinput import filename
import os
import io
import joblib
import pandas as pd
from flask import (Flask, render_template, request,redirect, url_for, flash, session)
from werkzeug.utils import secure_filename, send_from_directory
from modules.cleaning import handle_missing_values, handle_outliers, remove_duplicates, fix_inconsistencies, get_missing_stats, detect_outliers
from modules.data_loader import load_dataframe, allowed_file
from modules.data_summary import get_summary
from modules.eda import generate_visualizations
from modules.model_training import train_model_logic
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from modules.feature_engineering import apply_label_encoding, apply_standard_scaling, get_feature_info
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = 'mlreadyai_secret_2025' # needed for flash & session
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
# Use setattr to avoid static type-checker errors when assigning login_view
setattr(login_manager, 'login_view', 'login')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
with app.app_context():
    db.create_all()


# Folder where uploaded files are stored temporarily
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 # 50 MB limit
# We use a dict so it can be updated from any route
_store = {}
def get_df() -> pd.DataFrame | None:
    return _store.get('df')
def set_df(df: pd.DataFrame):
    _store['df'] = df  


@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # validations 
        if not name or len(name.strip())<2:
            flash('Name must be at least 2 characters long.', 'error')
            return redirect(url_for('signup'))

        if not email or '@' not in email:
            flash('Invalid email address.', 'error')
            return redirect(url_for('signup'))
        
        # password must be 8 characters long and a combination of letters and numbers and special characters
        if len(password) < 8 or not any(char.isdigit() for char in password)\
            or not any(char.isalpha() for char in password) or not any (not char.isalnum() for char in password): 

            flash('Password must be at least 8 characters long and contain letters, numbers and special characters.', 'error')
            return redirect(url_for('signup'))
        
        #check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.Please log in.', 'error')
            return redirect(url_for('login'))

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
            return redirect(url_for('signup'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash('Login successful!','success')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.",'error')
    return render_template('login.html')

@app.route('/upload', methods=['GET', 'POST'])
@login_required
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


@app.route('/cleaning', methods=['GET', 'POST'])
def cleaning():
    df = get_df()
    if df is None:
        flash('Please upload a dataset first.', 'error')
        return redirect(url_for('upload'))
    if request.method == 'POST':
        action = request.form.get('action')
        strategy = request.form.get('strategy', '')
        try:
            if action == 'impute':
                df_cleaned = handle_missing_values(df, strategy=strategy)
                set_df(df_cleaned)
                flash(f' Missing values handled using "{strategy}" strategy.', 'success')
            elif action == 'outliers':
                df_cleaned = handle_outliers(df, strategy=strategy)
                set_df(df_cleaned)
                flash(f'  Outliers handled using "{strategy}" strategy.', 'success')
            elif action == 'duplicates':
                df_cleaned = remove_duplicates(df)
                set_df(df_cleaned)
                flash(f' Duplicate rows removed.', 'success')
            elif action == 'fix_inconsistent':
                df_cleaned = fix_inconsistencies(df)
                set_df(df_cleaned)
                flash(f' Basic string inconsistencies fixed.', 'success')
        except Exception as e:
            flash(f'Error during cleaning: {e}', 'error')
        return redirect(url_for('cleaning'))
    missing_stats = get_missing_stats(df)
    outlier_stats = detect_outliers(df)
    duplicate_count = int(df.duplicated().sum())
    return render_template('cleaning.html',missing_stats=missing_stats,outlier_stats=outlier_stats,duplicate_count=duplicate_count)


@app.route('/feature_engineering', methods=['GET', 'POST'])
def feature_engineering():
    df = get_df()
    if df is None:
        flash('Please upload a dataset first.', 'error')
        return redirect(url_for('upload'))
    if request.method == 'POST':
        action = request.form.get('action')
        selected_cols = request.form.getlist('cols') # Get list of checked columns
        if not selected_cols:
            flash(' Please select at least one column.', 'error')
            return redirect(url_for('feature_engineering'))
        try:
            if action == 'label_encode':
                df_new = apply_label_encoding(df, selected_cols)
                set_df(df_new)
                flash(f' Label encoded: {", ".join(selected_cols)}', 'success')
            elif action == 'scale':
                df_new = apply_standard_scaling(df, selected_cols)
                set_df(df_new)
                flash(f' Scaled: {", ".join(selected_cols)}', 'success')
        except Exception as e:
            flash(f'Error during feature engineering: {e}', 'error')
        return redirect(url_for('feature_engineering'))
    feature_info = get_feature_info(df)
    return render_template('feature_engineering.html', features=feature_info)

@app.route('/model', methods=['GET', 'POST'])
def model():
    df = get_df()
    if df is None:
        flash('Please upload a dataset first.', 'error')
        return redirect(url_for('upload'))
    if request.method == 'POST':
        problem_type = request.form.get('problem_type')
        target_col = request.form.get('target_col', '')
        if not problem_type:
            flash(' Please select a problem type.', 'error')
            return redirect(url_for('model'))
        if problem_type in ('classification', 'regression') and not target_col:
            flash(f' Prediction for "{problem_type}" requires a Target Column.', 'error')
            return redirect(url_for('model'))
        session['problem_type'] = problem_type
        session['target_col'] = target_col
        flash(f' Problem Type: {problem_type.capitalize()} selected.', 'success')
        return redirect(url_for('algorithm_selection'))
    columns = list(df.columns)
    return render_template('model.html', columns=columns)

@app.route('/algorithm_selection', methods=['GET', 'POST'])
def algorithm_selection():
    problem_type = session.get('problem_type')
    if not problem_type:
        flash('Please select a problem type first.', 'error')
        return redirect(url_for('model'))
    if request.method == 'POST':
        algorithm = request.form.get('algorithm')
        if not algorithm:
            flash('⚠️Please select an algorithm.', 'error')
            return redirect(url_for('algorithm_selection'))
        session['algorithm'] = algorithm
        flash(f' Algorithm: {algorithm.replace("_", " ").capitalize()} selected.', 'success')
        return redirect(url_for('train_model'))
    return render_template('algorithm.html', problem_type=problem_type)


@app.route('/train_model')
def train_model():
    df = get_df()
    problem_type = session.get('problem_type')
    algorithm = session.get('algorithm')
    target_col = session.get('target_col')
    if not df or not algorithm:
        flash('Data or Algorithm missing. Please restart the process.', 'error')
        return redirect(url_for('upload'))
    try:
        model_obj, metrics, X_test, y_test = train_model_logic(df, problem_type, algorithm,target_col)
        _store['trained_model'] = model_obj
        return render_template('result.html',metrics=metrics,algorithm=algorithm,problem_type=problem_type)
    except Exception as e:
        flash(f'Error during training: {e}', 'error')
        return redirect(url_for('algorithm_selection'))

@app.route('/export_model')
def export_model():
    model_obj = _store.get('trained_model')
    algorithm = session.get('algorithm', 'model')
    if model_obj is None:
        flash(' No trained model found to export.', 'error')
        return redirect(url_for('train_model'))
    try:
        # 1. Define filename and path
        models_dir = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(models_dir, exist_ok=True)
        filename = f"{algorithm}_trained.pkl"
        filepath = os.path.join(models_dir, filename)
        # 2. Save the model using joblib
        joblib.dump(model_obj, filepath)
        # 3. Provide as download
        return send_from_directory(directory=models_dir, path=filename,as_attachment=True)
    except Exception as e:
        flash(f'Error exporting model: {e}', 'error')
        return redirect(url_for('train_model'))
    



if __name__ == '__main__':
    app.run(debug=True)