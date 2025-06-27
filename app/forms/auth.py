from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models.user import User

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
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('No account found with this email address.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', 
                            validators=[DataRequired(), Length(min=6, max=20)],
                            render_kw={'placeholder': 'Enter new password'})
    password2 = PasswordField('Confirm Password', 
                             validators=[DataRequired(), EqualTo('password')],
                             render_kw={'placeholder': 'Confirm new password'})
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', 
                                   validators=[DataRequired()],
                                   render_kw={'placeholder': 'Enter current password'})
    new_password = PasswordField('New Password', 
                               validators=[DataRequired(), Length(min=6, max=20)],
                               render_kw={'placeholder': 'Enter new password'})
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[DataRequired(), EqualTo('new_password')],
                                   render_kw={'placeholder': 'Confirm new password'})
    submit = SubmitField('Change Password')