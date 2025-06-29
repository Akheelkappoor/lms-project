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