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
    except Exception as e:
        email_logger.error(f"Failed to send email to {msg.recipients}: {str(e)}")
        # Log the full traceback for debugging
        import traceback
        email_logger.error(traceback.format_exc())

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

# Additional utility functions for email sending
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
        
        msg.html = html_content
        if text_content:
            msg.body = text_content
        
        # Send email
        mail.send(msg)
        return True
        
    except Exception as e:
        logging.error(f"Email sending failed: {str(e)}")
        return False

def send_bulk_email(recipients, subject, html_content, text_content=None):
    """
    Send email to multiple recipients
    
    Args:
        recipients: List of email addresses or recipient objects
        subject: Email subject
        html_content: HTML email content
        text_content: Plain text content (optional)
    
    Returns:
        dict: Results with sent/failed counts
    """
    results = {'sent': 0, 'failed': 0, 'errors': []}
    
    for recipient in recipients:
        email = recipient if isinstance(recipient, str) else recipient.get('email')
        if email:
            if send_email(email, subject, html_content, text_content):
                results['sent'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(email)
        else:
            results['failed'] += 1
            results['errors'].append('Invalid email address')
    
    return results

def validate_email_config():
    """
    Validate email configuration
    
    Returns:
        tuple: (is_valid, message)
    """
    required_configs = ['MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD']
    
    for config in required_configs:
        if not current_app.config.get(config):
            return False, f"Missing email configuration: {config}"
    
    return True, "Email configuration is valid"

def send_password_reset_email(user_email, reset_token):
    """Send password reset email"""
    try:
        subject = "Password Reset Request"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; }}
                .header {{ background: #F1A150; color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }}
                .button {{ background: #F1A150; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset</h1>
                </div>
                <p>You have requested a password reset. Click the button below to reset your password:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{{{{ url_for('auth.reset_password', token='{reset_token}', _external=True) }}}}" class="button">Reset Password</a>
                </p>
                <p>If you did not request this reset, please ignore this email.</p>
                <p>This link will expire in 1 hour.</p>
            </div>
        </body>
        </html>
        """
        
        return send_email(user_email, subject, html_content)
        
    except Exception as e:
        logging.error(f"Failed to send password reset email: {str(e)}")
        return False

def send_onboarding_email(user_email, user_name, temporary_password):
    """Send onboarding email with temporary password"""
    try:
        subject = "Welcome to Our Platform"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; }}
                .header {{ background: #F1A150; color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }}
                .credentials {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome {user_name}!</h1>
                </div>
                <p>Your account has been created successfully. Here are your login credentials:</p>
                <div class="credentials">
                    <p><strong>Email:</strong> {user_email}</p>
                    <p><strong>Temporary Password:</strong> {temporary_password}</p>
                </div>
                <p>Please log in and change your password immediately for security purposes.</p>
                <p>Best regards,<br>The Team</p>
            </div>
        </body>
        </html>
        """
        
        return send_email(user_email, subject, html_content)
        
    except Exception as e:
        logging.error(f"Failed to send onboarding email: {str(e)}")
        return False