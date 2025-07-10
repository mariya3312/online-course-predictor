from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pickle
import pandas as pd
from datetime import datetime
from flask_login import login_required


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config[ 'SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "supersecretkey"  # Change this to a more secure secret
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# Hardcoded admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Load ML Models
with open("best_model.pkl", "rb") as f:
    model = pickle.load(f)
with open("one_hot_encoder.pkl", "rb") as f:
    encoder = pickle.load(f)
with open("scaler.pkl", "rb") as f:
    scaler = pickle.load(f)

numeric_features = [
    "TimeSpentOnCourse",
    "NumberOfVideosWatched",
    "NumberOfQuizzesTaken",
    "QuizScores",
    "DeviceType"
]

categorical_features = [
    "CourseCategory",
    "Platform"
]

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    prediction_result = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __init__(self, user_id, course_name, prediction_result):
        self.user_id = user_id
        self.course_name = course_name
        self.prediction_result = prediction_result

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    def __init__(self, text):
        self.text = text

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    reason = db.Column(db.String(500))
    

    def __init__(self, user_id, course_name, reason, course_link=None):
        self.user_id = user_id
        self.course_name = course_name
        self.reason = reason
    

class CourseProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    progress = db.Column(db.Float, nullable=False)  # Progress percentage (0 - 100)
    status = db.Column(db.String(50), nullable=False, default="In Progress")  # In Progress / Completed

class FavoriteCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    course_link = db.Column(db.String(500), nullable=False)  # Link to course

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="questions")

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="answers")
    question = db.relationship("Question", backref="answers")

class Discussion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="discussions")

class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discussion_id = db.Column(db.Integer, db.ForeignKey('discussion.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('replies', lazy=True))
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    discussion = db.relationship('Discussion', backref=db.backref('replies', lazy=True, cascade="all, delete-orphan"))


class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    issued_date = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="certificates")

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    earned_date = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="achievements")


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()


        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))  # Redirect to admin dashboard

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session["user_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for('predict'))
    
    return render_template('login.html' ,error="Invalid username or password")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('register'))
        
        # Check if the username already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for('register'))
        
        # Hash the password before storing it
        hashed_password = generate_password_hash(password)
        
        # Create a new user and store it in the database
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        flash("If your email is registered, you will receive a password reset link.", "info")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/about_us')
def about_us():
    return render_template('about_us.html')

@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        numeric_data = {}
        for feature in numeric_features:
            value = request.form.get(feature)
            try:
                numeric_data[feature] = float(value)
            except (ValueError, TypeError):
                flash(f"Invalid input for numeric feature '{feature}': {value}", "danger")
                return redirect(url_for('predict'))

        # For categorical features: get the input (as string).
        categorical_data = {}
        for feature in categorical_features:
            categorical_data[feature] = request.form.get(feature)

        # 2. Create DataFrames for numeric and categorical parts.
        df_numeric = pd.DataFrame([numeric_data])
        df_categorical = pd.DataFrame([categorical_data])

        # 3. One-hot encode the categorical inputs.
        encoded_array = encoder.transform(df_categorical)
        encoded_df = pd.DataFrame(encoded_array, columns=encoder.get_feature_names_out(categorical_features))

        # 4. Concatenate the numeric and one-hot encoded categorical data.
        df_final = pd.concat([df_numeric, encoded_df], axis=1)

        # 5. Scale the features using the loaded scaler.
        scaled_features = scaler.transform(df_final)

        # 6. Make the prediction.
        prediction = model.predict(scaled_features)
        predicted_value = "Yes" if prediction[0] == 1 else "No"

        user_id = session['user_id']
        course_name = request.form.get('CourseName', 'Unknown Course')  # Ensure course name is passed
        new_prediction = Prediction(user_id=user_id, course_name=course_name, prediction_result=predicted_value)
        db.session.add(new_prediction)
        db.session.commit()


        # Pass prediction result to the template
        return render_template("result.html", prediction=predicted_value)

    cat_options = {}
    for i, feature in enumerate(categorical_features):
        cat_options[feature] = list(encoder.categories_[i])
    
    return render_template('predict.html', numeric_features=numeric_features, 
                           categorical_features=categorical_features,
                           cat_options=cat_options)

@app.route('/result')
def result():
    # If prediction result is not found in session, redirect to predict page
    if 'prediction_result' not in session:
        return redirect(url_for('predict'))
    
    result = session.pop('prediction_result')
    return render_template('result.html', prediction=result)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied. Admins only!", "danger")
    if not session.get("admin_logged_in"):
        return redirect(url_for('login'))  # Redirect non-admins
 
    users = [
        {"id": 1, "username": "john_doe"},
        {"id": 2, "username": "jane_smith"},
        {"id": 3, "username": "admin"}  # Admin should not be deleted
    ]
    users = User.query.all()
    return render_template('admin_dashboard.html' , users=users)  # Create this template

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    user = User.query.get(user_id)  # Fetch the user from DB
    if user and user.username != "admin":  # Prevent admin deletion
        db.session.delete(user)  # Delete the user
        db.session.commit()  # Save changes
    return redirect(url_for("admin_dashboard"))  # Redirect back

@app.route("/user_dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))  
    
    user_id = session["user_id"] # Get current user
    
    user = User.query.get(user_id)
    predictions = Prediction.query.filter_by(user_id=user_id).all()  # Get prediction history
    feedback_list = Feedback.query.all()  # Fetch all feedback entries
    recommendations = Recommendation.query.filter_by(user_id = user_id).all()
    progress_data = CourseProgress.query.filter_by(user_id=user_id).all()
    favorite_courses = FavoriteCourse.query.filter_by(user_id=user_id).all()
    user_history = Prediction.query.filter_by(user_id=user_id).all()

    return render_template("user_dashboard.html", user=user, predictions=predictions, feedbacks=feedback_list, recommendations=recommendations,  progress_data=progress_data, favorite_courses=favorite_courses, course_progress=user_history)


@app.route("/save_favorite", methods=["POST"])
def save_favorite():
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    course_name = request.form.get("course_name")
    course_link = request.form.get("course_link")

    if course_name and course_link:
        favorite = FavoriteCourse(user_id=user_id, course_name=course_name, course_link=course_link)
        db.session.add(favorite)
        db.session.commit()
        flash("Course added to favorites!", "success")

    return redirect(url_for("user_dashboard"))




@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    feedback_text = request.form.get('feedback')
    
    if feedback_text:
        new_feedback = Feedback(text=feedback_text)  # Ensure `Feedback` model exists
        db.session.add(new_feedback)
        db.session.commit()
    
    return redirect(url_for('user_dashboard'))  # Redirect back to dashboard

@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if user:
        db.session.delete(user)
        db.session.commit()
        session.clear()  # Log out user
        flash("Account deleted successfully.", "success")

    return redirect(url_for("login"))

@app.route("/forum")
def forum():
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))

    questions = Question.query.order_by(Question.timestamp.desc()).all()
    return render_template("forum.html", questions=questions)

@app.route("/post_question", methods=["POST"])
def post_question():
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))

    content = request.form["content"]
    user_id = session["user_id"]

    new_question = Question(user_id=user_id, content=content)
    db.session.add(new_question)
    db.session.commit()

    flash("Question posted successfully!", "success")
    return redirect(url_for("forum"))

@app.route("/post_answer/<int:question_id>", methods=["POST"])
def post_answer(question_id):
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))

    content = request.form["content"]
    user_id = session["user_id"]

    new_answer = Answer(question_id=question_id, user_id=user_id, content=content)
    db.session.add(new_answer)
    db.session.commit()

    flash("Answer posted successfully!", "success")
    return redirect(url_for("forum"))

@app.route('/post_discussion', methods=['POST'])
def post_discussion():
    # Your function logic
    return redirect(url_for('some_page'))


@app.route('/post_reply/<int:discussion_id>', methods=['POST'])
@login_required
def post_reply(discussion_id):
    content = request.form.get('content')
    discussion = Discussion.query.get_or_404(discussion_id)

    if content.strip():
        new_reply = Reply(discussion_id=discussion.id, user_id=current_user.id, content=content)
        db.session.add(new_reply)
        db.session.commit()
        flash("Reply posted successfully!", "success")
    else:
        flash("Reply cannot be empty.", "danger")

    return redirect(url_for('forum'))

@app.route('/discussion')
def discussion_page():
    return render_template('discussion.html')


@app.route("/generate_certificate/<course_name>")
def generate_certificate(course_name):
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    
    # Check if certificate already exists
    existing_certificate = Certificate.query.filter_by(user_id=user_id, course_name=course_name).first()
    if existing_certificate:
        flash("Certificate already issued!", "info")
        return redirect(url_for("user_dashboard"))

    # Issue new certificate
    new_certificate = Certificate(user_id=user_id, course_name=course_name)
    db.session.add(new_certificate)
    db.session.commit()

    flash("Certificate issued successfully!", "success")
    return redirect(url_for("user_dashboard"))

@app.route("/certificates")
def certificates():
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    certificates = Certificate.query.filter_by(user_id=user_id).all()
    return render_template("certificates.html", certificates=certificates)

@app.route("/achievements")
def achievements():
    return render_template("achievements.html")


def check_achievements(user_id):
    completed_courses = Certificate.query.filter_by(user_id=user_id).count()

    if completed_courses == 3:
        new_achievement = Achievement(user_id=user_id, title="Learning Enthusiast", description="Completed 3 courses!")
        db.session.add(new_achievement)

    if completed_courses == 5:
        new_achievement = Achievement(user_id=user_id, title="Knowledge Master", description="Completed 5 courses!")
        db.session.add(new_achievement)

    db.session.commit()


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
    app.run(debug=True)






