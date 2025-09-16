from flask import current_app, render_template
from flask_mail import Message
from app import mail
import threading
import logging

# Set up logging for email operations
logging.basicConfig(level=logging.INFO)
email_logger = logging.getLogger('email')

def send_async_email(app, msg):
    """Send email asynchronously with error handling"""
    try:
        with app.app_context():
            mail.send(msg)
            email_logger.info(f"Email sent successfully to {msg.recipients}")
            return True
    except Exception as e:
        email_logger.error(f"Failed to send email to {msg.recipients}: {str(e)}")
        # Log the full traceback for debugging
        import traceback
        email_logger.error(traceback.format_exc())
        return False

def send_email(subject, recipients, text_body, html_body, sender=None, sync=False):
    """
    Send email function with optional synchronous sending
    
    Args:
        subject (str): Email subject
        recipients (list): List of recipient email addresses
        text_body (str): Plain text email body
        html_body (str): HTML email body
        sender (str, optional): Sender email address
        sync (bool): If True, send synchronously and return result
    
    Returns:
        bool: True if sent successfully (only when sync=True)
    """
    try:
        if not sender:
            sender = current_app.config['MAIL_USERNAME']
        
        if not recipients:
            email_logger.error("No recipients specified for email")
            return False if sync else None
        
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body
        msg.html = html_body
        
        email_logger.info(f"Preparing to send email: '{subject}' to {recipients}")
        
        if sync:
            # Send synchronously and return result
            try:
                mail.send(msg)
                email_logger.info(f"Email sent successfully (sync) to {recipients}")
                return True
            except Exception as e:
                email_logger.error(f"Failed to send email (sync) to {recipients}: {str(e)}")
                return False
        else:
            # Send email in background thread (original behavior)
            thread = threading.Thread(
                target=send_async_email, 
                args=(current_app._get_current_object(), msg)
            )
            thread.daemon = True  # Allow main thread to exit even if email thread is running
            thread.start()
            email_logger.info(f"Email queued for async sending to {recipients}")
            
    except Exception as e:
        email_logger.error(f"Error preparing email: {str(e)}")
        if sync:
            return False

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
    
    # Send with synchronous option to get immediate feedback for password reset
    try:
        result = send_email(
            subject=subject,
            recipients=[user.email],
            text_body=text_body,
            html_body=html_body,
            sync=True  # Send synchronously for immediate feedback
        )
        if result:
            email_logger.info(f"Password reset email sent successfully to {user.email}")
        else:
            email_logger.error(f"Failed to send password reset email to {user.email}")
        return result
    except Exception as e:
        email_logger.error(f"Exception sending password reset email to {user.email}: {str(e)}")
        return False

def send_onboarding_email(user, password):
    """Send onboarding email to new user"""
    subject = f'Welcome to {current_app.config["APP_NAME"]} - Your Account is Ready!'
    
    try:
        html_body = render_template(
            'email/onboarding.html',
            user=user,
            password=password,
            app_name=current_app.config['APP_NAME']
        )
    except Exception as e:
        email_logger.warning(f"Failed to render HTML template: {str(e)}")
        html_body = f"""
        <h2>Welcome to {current_app.config['APP_NAME']}!</h2>
        <p>Hello {user.full_name},</p>
        <p>Your account has been successfully created.</p>
        <p><strong>Username:</strong> {user.username}</p>
        <p><strong>Password:</strong> {password}</p>
        <p><strong>Role:</strong> {user.role.title()}</p>
        <p>Please change your password after first login.</p>
        """
    
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
    
    # Send with synchronous option to get immediate feedback for onboarding
    try:
        result = send_email(
            subject=subject,
            recipients=[user.email],
            text_body=text_body,
            html_body=html_body,
            sync=True  # Send synchronously for immediate feedback
        )
        if result:
            email_logger.info(f"Onboarding email sent successfully to {user.email}")
        else:
            email_logger.error(f"Failed to send onboarding email to {user.email}")
        return result
    except Exception as e:
        email_logger.error(f"Exception sending onboarding email to {user.email}: {str(e)}")
        return False

def send_simple_email(to_email, subject, html_content, text_content=None):
    """
    Simple wrapper for sending basic emails
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email content
        text_content: Plain text content (optional)
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        recipients = [to_email] if isinstance(to_email, str) else to_email
        return send_email(
            subject=subject,
            recipients=recipients,
            text_body=text_content or "Please enable HTML to view this email.",
            html_body=html_content,
            sync=True
        )
    except Exception as e:
        email_logger.error(f"Error sending simple email: {str(e)}")
        return False

def test_email_connection():
    """Test email connection and configuration"""
    try:
        # Test basic configuration
        config_items = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME', 'MAIL_PASSWORD']
        for item in config_items:
            if not current_app.config.get(item):
                email_logger.error(f"Missing email configuration: {item}")
                return False
        
        email_logger.info("Email configuration appears complete")
        return True
        
    except Exception as e:
        email_logger.error(f"Email configuration test failed: {str(e)}")
        return False