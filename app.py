# app.py

from flask import Flask, render_template, flash, redirect, url_for, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, ValidationError, Email, EqualTo
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from config import Config

# Ініціалізація додатку
app = Flask(__name__)
app.config.from_object(Config)

bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = 'login'

# Моделі
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(64))  # 'military' or 'doctor'
    consultations = db.relationship('Consultation', foreign_keys='Consultation.user_id', backref='author', lazy='dynamic')
    responses = db.relationship('Consultation', foreign_keys='Consultation.responder_id', backref='responder', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    responder_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    response = db.Column(db.String(140))

# Форми
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    role = StringField('Role', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class ConsultationForm(FlaskForm):
    body = TextAreaField('Consultation Request', validators=[DataRequired()])
    submit = SubmitField('Submit')

# Маршрути
@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template('index.html', title='Home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/profile')
@login_required
def profile():
    user = current_user
    return render_template('profile.html', title='Profile', user=user)

@app.route('/consultation_request', methods=['GET', 'POST'])
@login_required
def consultation_request():
    form = ConsultationForm()
    if form.validate_on_submit():
        consultation = Consultation(body=form.body.data, author=current_user)
        db.session.add(consultation)
        db.session.commit()
        flash('Your consultation request has been submitted.')
        return redirect(url_for('index'))
    return render_template('consultation_request.html', title='Consultation Request', form=form)

@app.route('/consultations')
@login_required
def consultations():
    if current_user.role != 'doctor':
        return redirect(url_for('index'))
    consultations = Consultation.query.filter_by(responder_id=None).all()
    return render_template('consultations.html', title='Consultations', consultations=consultations)

@app.route('/chat/<int:consultation_id>', methods=['GET', 'POST'])
@login_required
def chat(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    if current_user.role == 'doctor' and consultation.responder_id is None:
        consultation.responder_id = current_user.id
        db.session.commit()
    if request.method == 'POST':
        response = request.form.get('response')
        consultation.response = response
        db.session.commit()
    return render_template('chat.html', title='Chat', consultation=consultation)

# Ініціалізація бази даних
with app.app_context():
    db.create_all()

# Запуск додатку
if __name__ == '__main__':
    app.run(debug=True)
