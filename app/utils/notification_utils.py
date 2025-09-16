# CREATE FILE: app/utils/notification_utils.py

from flask import current_app, render_template_string
from flask_mail import Message, Mail
from datetime import datetime, timedelta
import json
from email.mime.text import MIMEText


def send_class_notification(class_obj, recipient, notification_type='reminder'):
    """Send class notification to recipient"""
    try:
        mail = Mail(current_app)
        
        # Determine email content based on notification type
        if notification_type == 'reminder':
            subject, template = get_reminder_email_content(class_obj)
        elif notification_type == 'rescheduled':
            subject, template = get_reschedule_email_content(class_obj)
        elif notification_type == 'cancelled':
            subject, template = get_cancellation_email_content(class_obj)
        elif notification_type == 'created':
            subject, template = get_creation_email_content(class_obj)
        else:
            subject, template = get_generic_email_content(class_obj, notification_type)
        
        # Render email content
        email_content = render_template_string(
            template,
            class_obj=class_obj,
            recipient=recipient,
            app_name=current_app.config.get('APP_NAME', 'LMS'),
            current_datetime=datetime.now()
        )
        
        # Create and send message
        msg = Message(
            subject=subject,
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[recipient['email']]
        )
        msg.html = email_content
        
        mail.send(msg)
        return True
        
    except Exception as e:
        print(f"Failed to send notification: {str(e)}")
        return False

def get_reminder_email_content(class_obj):
    """Get email content for class reminder"""
    time_until = class_obj.get_time_until_class_formatted()
    
    subject = f"Class Reminder: {class_obj.subject} in {time_until}"
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #F1A150, #C86706); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }
            .reminder-badge { background: #ff6b6b; color: white; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block; margin-bottom: 20px; }
            .class-details { background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .detail-row { display: flex; justify-content: space-between; margin-bottom: 10px; }
            .detail-label { font-weight: bold; color: #374151; }
            .detail-value { color: #6b7280; }
            .meeting-link { background: #F1A150; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block; margin: 20px 0; font-weight: bold; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #6c757d; font-size: 14px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Class Reminder</h1>
                <p>Your class is starting soon!</p>
            </div>
            
            <div class="reminder-badge">
                ⏰ Starting in {{ class_obj.get_time_until_class_formatted() }}
            </div>
            
            <h2>Hello {{ recipient.name }}!</h2>
            <p>This is a friendly reminder that your class is scheduled to start soon.</p>
            
            <div class="class-details">
                <h3>Class Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Subject:</span>
                    <span class="detail-value">{{ class_obj.subject }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Date:</span>
                    <span class="detail-value">{{ class_obj.scheduled_date.strftime('%A, %B %d, %Y') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Time:</span>
                    <span class="detail-value">{{ class_obj.scheduled_time.strftime('%H:%M') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Duration:</span>
                    <span class="detail-value">{{ class_obj.duration }} minutes</span>
                </div>
                {% if recipient.type == 'student' %}
                <div class="detail-row">
                    <span class="detail-label">Tutor:</span>
                    <span class="detail-value">{{ class_obj.tutor.user.full_name if class_obj.tutor and class_obj.tutor.user else 'TBA' }}</span>
                </div>
                {% endif %}
            </div>
            
            {% if class_obj.meeting_link %}
            <div style="text-align: center;">
                <a href="{{ class_obj.meeting_link }}" class="meeting-link">
                    🎥 Join Class Meeting
                </a>
            </div>
            {% endif %}
            
            {% if class_obj.class_notes %}
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #856404;">📝 Class Notes:</h4>
                <p style="margin: 0; color: #856404;">{{ class_obj.class_notes }}</p>
            </div>
            {% endif %}
            
            <div class="footer">
                <p>Need to reschedule? Contact us or login to {{ app_name }} to make changes.</p>
                <p>This email was sent automatically from {{ app_name }} on {{ current_datetime.strftime('%B %d, %Y at %I:%M %p') }}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, template

def get_reschedule_email_content(class_obj):
    """Get email content for class reschedule notification"""
    subject = f"Class Rescheduled: {class_obj.subject}"
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #17a2b8, #138496); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }
            .reschedule-badge { background: #17a2b8; color: white; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block; margin-bottom: 20px; }
            .class-details { background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .detail-row { display: flex; justify-content: space-between; margin-bottom: 10px; }
            .detail-label { font-weight: bold; color: #374151; }
            .detail-value { color: #6b7280; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #6c757d; font-size: 14px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Class Rescheduled</h1>
                <p>Your class time has been updated</p>
            </div>
            
            <div class="reschedule-badge">
                📅 Class Rescheduled
            </div>
            
            <h2>Hello {{ recipient.name }}!</h2>
            <p>Your class has been rescheduled. Please note the new date and time below.</p>
            
            <div class="class-details">
                <h3>Updated Class Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Subject:</span>
                    <span class="detail-value">{{ class_obj.subject }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">New Date:</span>
                    <span class="detail-value" style="color: #17a2b8; font-weight: bold;">{{ class_obj.scheduled_date.strftime('%A, %B %d, %Y') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">New Time:</span>
                    <span class="detail-value" style="color: #17a2b8; font-weight: bold;">{{ class_obj.scheduled_time.strftime('%H:%M') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Duration:</span>
                    <span class="detail-value">{{ class_obj.duration }} minutes</span>
                </div>
            </div>
            
            {% if class_obj.admin_notes %}
            <div style="background: #d1ecf1; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #0c5460;">📝 Reschedule Reason:</h4>
                <p style="margin: 0; color: #0c5460;">{{ class_obj.admin_notes.split('\\n')[-1] if '\\n' in class_obj.admin_notes else class_obj.admin_notes }}</p>
            </div>
            {% endif %}
            
            <div class="footer">
                <p>Please update your calendar accordingly. If you have any questions, feel free to contact us.</p>
                <p>This email was sent automatically from {{ app_name }} on {{ current_datetime.strftime('%B %d, %Y at %I:%M %p') }}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, template

def get_cancellation_email_content(class_obj):
    """Get email content for class cancellation"""
    subject = f"Class Cancelled: {class_obj.subject}"
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #dc3545, #c82333); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }
            .cancellation-badge { background: #dc3545; color: white; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block; margin-bottom: 20px; }
            .class-details { background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .detail-row { display: flex; justify-content: space-between; margin-bottom: 10px; }
            .detail-label { font-weight: bold; color: #374151; }
            .detail-value { color: #6b7280; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #6c757d; font-size: 14px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Class Cancelled</h1>
                <p>We apologize for the inconvenience</p>
            </div>
            
            <div class="cancellation-badge">
                ❌ Class Cancelled
            </div>
            
            <h2>Hello {{ recipient.name }}!</h2>
            <p>We regret to inform you that your scheduled class has been cancelled. Details are provided below.</p>
            
            <div class="class-details">
                <h3>Cancelled Class Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Subject:</span>
                    <span class="detail-value">{{ class_obj.subject }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Original Date:</span>
                    <span class="detail-value">{{ class_obj.scheduled_date.strftime('%A, %B %d, %Y') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Original Time:</span>
                    <span class="detail-value">{{ class_obj.scheduled_time.strftime('%H:%M') }}</span>
                </div>
            </div>
            
            {% if class_obj.admin_notes %}
            <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #721c24;">📝 Cancellation Reason:</h4>
                <p style="margin: 0; color: #721c24;">{{ class_obj.admin_notes.split('\\n')[-1] if '\\n' in class_obj.admin_notes else class_obj.admin_notes }}</p>
            </div>
            {% endif %}
            
            <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #155724;">What's Next?</h4>
                <p style="margin: 0; color: #155724;">
                    We will work to reschedule this class at the earliest possible time. 
                    Our team will contact you with alternative time slots.
                </p>
            </div>
            
            <div class="footer">
                <p>We apologize for any inconvenience caused. Please contact us if you have any questions.</p>
                <p>This email was sent automatically from {{ app_name }} on {{ current_datetime.strftime('%B %d, %Y at %I:%M %p') }}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, template

def get_creation_email_content(class_obj):
    """Get email content for new class creation"""
    subject = f"New Class Scheduled: {class_obj.subject}"
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }
            .new-class-badge { background: #28a745; color: white; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block; margin-bottom: 20px; }
            .class-details { background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .detail-row { display: flex; justify-content: space-between; margin-bottom: 10px; }
            .detail-label { font-weight: bold; color: #374151; }
            .detail-value { color: #6b7280; }
            .meeting-link { background: #F1A150; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block; margin: 20px 0; font-weight: bold; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #6c757d; font-size: 14px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>New Class Scheduled</h1>
                <p>Get ready for your upcoming class!</p>
            </div>
            
            <div class="new-class-badge">
                ✨ New Class Added
            </div>
            
            <h2>Hello {{ recipient.name }}!</h2>
            <p>A new class has been scheduled for you. Please review the details below and add it to your calendar.</p>
            
            <div class="class-details">
                <h3>Class Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Subject:</span>
                    <span class="detail-value">{{ class_obj.subject }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Date:</span>
                    <span class="detail-value">{{ class_obj.scheduled_date.strftime('%A, %B %d, %Y') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Time:</span>
                    <span class="detail-value">{{ class_obj.scheduled_time.strftime('%H:%M') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Duration:</span>
                    <span class="detail-value">{{ class_obj.duration }} minutes</span>
                </div>
                {% if recipient.type == 'student' %}
                <div class="detail-row">
                    <span class="detail-label">Tutor:</span>
                    <span class="detail-value">{{ class_obj.tutor.user.full_name if class_obj.tutor and class_obj.tutor.user else 'TBA' }}</span>
                </div>
                {% endif %}
            </div>
            
            {% if class_obj.meeting_link %}
            <div style="text-align: center;">
                <a href="{{ class_obj.meeting_link }}" class="meeting-link">
                    🎥 Meeting Link (Available 15 min before class)
                </a>
            </div>
            {% endif %}
            
            <div style="background: #d1ecf1; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #0c5460;">📅 Add to Calendar</h4>
                <p style="margin: 0; color: #0c5460;">
                    Don't forget to add this class to your personal calendar to avoid missing it!
                </p>
            </div>
            
            <div class="footer">
                <p>Looking forward to seeing you in class! Contact us if you have any questions.</p>
                <p>This email was sent automatically from {{ app_name }} on {{ current_datetime.strftime('%B %d, %Y at %I:%M %p') }}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, template

def get_generic_email_content(class_obj, notification_type):
    """Get generic email content for other notification types"""
    subject = f"Class Notification: {class_obj.subject}"
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #F1A150, #C86706); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }
            .class-details { background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .detail-row { display: flex; justify-content: space-between; margin-bottom: 10px; }
            .detail-label { font-weight: bold; color: #374151; }
            .detail-value { color: #6b7280; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #6c757d; font-size: 14px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Class Notification</h1>
                <p>{{ notification_type.title() }} notification for your class</p>
            </div>
            
            <h2>Hello {{ recipient.name }}!</h2>
            <p>This is a notification regarding your scheduled class.</p>
            
            <div class="class-details">
                <h3>Class Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Subject:</span>
                    <span class="detail-value">{{ class_obj.subject }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Date:</span>
                    <span class="detail-value">{{ class_obj.scheduled_date.strftime('%A, %B %d, %Y') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Time:</span>
                    <span class="detail-value">{{ class_obj.scheduled_time.strftime('%H:%M') }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="detail-value">{{ class_obj.status.title() }}</span>
                </div>
            </div>
            
            <div class="footer">
                <p>If you have any questions, please contact us through {{ app_name }}.</p>
                <p>This email was sent automatically from {{ app_name }} on {{ current_datetime.strftime('%B %d, %Y at %I:%M %p') }}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, template

def send_bulk_notifications(classes, notification_type='reminder'):
    """Send notifications for multiple classes"""
    results = {
        'sent': 0,
        'failed': 0,
        'errors': []
    }
    
    for class_obj in classes:
        try:
            # Get recipients for this class
            recipients = []
            
            # Add tutor
            if class_obj.tutor and class_obj.tutor.user and class_obj.tutor.user.email:
                recipients.append({
                    'type': 'tutor',
                    'email': class_obj.tutor.user.email,
                    'name': class_obj.tutor.user.full_name,
                    'phone': class_obj.tutor.user.phone
                })
            
            # Add students
            students = class_obj.get_student_objects()
            for student in students:
                if hasattr(student, 'email') and student.email:
                    recipients.append({
                        'type': 'student',
                        'email': student.email,
                        'name': getattr(student, 'full_name', 'Student'),
                        'phone': getattr(student, 'phone', None)
                    })
            
            # Send to each recipient
            for recipient in recipients:
                if send_class_notification(class_obj, recipient, notification_type):
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to send to {recipient['email']}")
                    
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"Class {class_obj.id}: {str(e)}")
    
    return results

# CREATE FILE: app/utils/email_utils.py

from flask_mail import Message, Mail
from flask import current_app
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to_email, subject, html_content, text_content=None):
    """Send email using Flask-Mail"""
    try:
        mail = Mail(current_app)
        
        msg = Message(
            subject=subject,
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[to_email] if isinstance(to_email, str) else to_email
        )
        
        msg.html = html_content
        if text_content:
            msg.body = text_content
        
        mail.send(msg)
        return True
        
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        return False

def send_bulk_email(recipients, subject, html_content, text_content=None):
    """Send email to multiple recipients"""
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
    """Validate email configuration"""
    required_configs = ['MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD']
    
    for config in required_configs:
        if not current_app.config.get(config):
            return False, f"Missing email configuration: {config}"
    
    return True, "Email configuration is valid"

# CREATE FILE: app/utils/file_utils.py

import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
import mimetypes

def allowed_file(filename):
    """Check if file extension is allowed"""
    if not filename:
        return False
    
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, folder='documents'):
    """Save uploaded file and return filename"""
    if not file or not allowed_file(file.filename):
        return None
    
    # Generate unique filename
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
    
    # Create directory if it doesn't exist
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(upload_path, exist_ok=True)
    
    # Save file
    file_path = os.path.join(upload_path, unique_filename)
    file.save(file_path)
    
    return os.path.join(folder, unique_filename)

def get_file_info(file_path):
    """Get file information"""
    if not os.path.exists(file_path):
        return None
    
    stat = os.stat(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    
    return {
        'size': stat.st_size,
        'size_formatted': format_file_size(stat.st_size),
        'mime_type': mime_type,
        'modified': stat.st_mtime,
        'extension': os.path.splitext(file_path)[1].lower()
    }

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def delete_file(file_path):
    """Safely delete a file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"Error deleting file {file_path}: {str(e)}")
    
    return False