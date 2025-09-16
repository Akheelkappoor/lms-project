from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
import re

from app.models.user import User

def validate_password_strength(form, field):
    """Validate password strength requirements"""
    password = field.data
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long.')
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must contain at least one uppercase letter.')
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must contain at least one lowercase letter.')
    if not re.search(r'\d', password):
        raise ValidationError('Password must contain at least one digit.')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError('Password must contain at least one special character.')
    # Check for common weak passwords
    weak_passwords = ['password', 'password123', '12345678', 'qwerty123']
    if password.lower() in weak_passwords:
        raise ValidationError('Password is too common. Please choose a stronger password.')

class LoginForm(FlaskForm):
    username = StringField('Username or Email', validators=[DataRequired()], 
                          render_kw={'placeholder': 'Enter username or email'})
    password = PasswordField('Password', validators=[DataRequired()], 
                            render_kw={'placeholder': 'Enter password'})
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()], 
                       render_kw={'placeholder': 'Enter your email address'})
    submit = SubmitField('Send Reset Link')

    def validate_email(self, email):
        user = User.query.filter(User.email.ilike(email.data)).first()
        if user is None:
            raise ValidationError('No account found with this email address.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', 
                            validators=[DataRequired(), Length(min=8, max=128), validate_password_strength],
                            render_kw={'placeholder': 'Enter new password (min 8 chars, 1 upper, 1 lower, 1 digit, 1 special char)'})
    password2 = PasswordField('Confirm Password', 
                             validators=[DataRequired(), EqualTo('password')],
                             render_kw={'placeholder': 'Confirm new password'})
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', 
                                   validators=[DataRequired()],
                                   render_kw={'placeholder': 'Enter current password'})
    new_password = PasswordField('New Password', 
                               validators=[DataRequired(), Length(min=8, max=128), validate_password_strength],
                               render_kw={'placeholder': 'Enter new password (min 8 chars, 1 upper, 1 lower, 1 digit, 1 special char)'})
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[DataRequired(), EqualTo('new_password')],
                                   render_kw={'placeholder': 'Confirm new password'})
    submit = SubmitField('Change Password')

# Add this to your existing app/forms/auth.py file


class SetupForm(FlaskForm):
    """Initial setup form for creating superadmin"""
    
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=20)
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    
    phone = StringField('Phone Number', validators=[
        Length(min=10, max=15)
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, max=128),
        validate_password_strength
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    
    submit = SubmitField('Complete Setup')
    
    def validate_username(self, username):
        user = User.query.filter(User.username.ilike(username.data)).first()
        if user:
            raise ValidationError('Username already exists.')
    
    def validate_email(self, email):
        user = User.query.filter(User.email.ilike(email.data)).first()
        if user:
            raise ValidationError('Email already registered.')