from flask import current_app, render_template
from flask_mail import Message
from app import mail
import threading

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        mail.send(msg)

def send_email(subject, recipients, text_body, html_body, sender=None):
    """Send email function"""
    if not sender:
        sender = current_app.config['MAIL_USERNAME']
    
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    # Send email in background thread
    thread = threading.Thread(
        target=send_async_email, 
        args=(current_app._get_current_object(), msg)
    )
    thread.start()

def send_password_reset_email(user, token):
    """Send password reset email"""
    subject = f'[{current_app.config["APP_NAME"]}] Password Reset Request'
    
    html_body = render_template(
        'email/password_reset.html',
        user=user,
        token=token,
        app_name=current_app.config['APP_NAME']
    )
    
    text_body = f"""
Hello {user.full_name},

You have requested to reset your password.

Click the link below to reset your password:
{current_app.config.get('BASE_URL', 'http://localhost:5000')}/auth/reset-password/{token}

If you didn't request this, please ignore this email.

Best regards,
{current_app.config['APP_NAME']} Team
    """
    
    send_email(
        subject=subject,
        recipients=[user.email],
        text_body=text_body,
        html_body=html_body
    )

def send_onboarding_email(user, password):
    """Send onboarding email to new user"""
    subject = f'Welcome to {current_app.config["APP_NAME"]} - Your Account is Ready!'
    
    html_body = render_template(
        'email/onboarding.html',
        user=user,
        password=password,
        app_name=current_app.config['APP_NAME']
    )
    
    text_body = f"""
Welcome to {current_app.config['APP_NAME']}!

Hello {user.full_name},

Your account has been successfully created with {user.role.title()} privileges.

Your Login Credentials:
- Username: {user.username}
- Email: {user.email}
- Password: {password}
- Role: {user.role.title()}
{f"- Department: {user.department.name}" if user.department else ""}

Login URL: {current_app.config.get('BASE_URL', 'http://localhost:5000')}/auth/login

For your account security, please change your password after your first login.

If you have any questions, please contact our support team.

Best regards,
{current_app.config['APP_NAME']} Team

---
I2Global Virtual Learning
48, 4th Block, Koramangala, Bengaluru, Karnataka 560034
Email: care@i2global.co.in | Phone: +91 9600127000
    """
    
    send_email(
        subject=subject,
        recipients=[user.email],
        text_body=text_body,
        html_body=html_body
    )