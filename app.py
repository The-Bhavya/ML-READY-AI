from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'secretkey'  #secret key for session management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #to suppress a warning from SQLAlchemy
db = SQLAlchemy(app) #initialize the database

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

# Database initialization with app context
with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
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