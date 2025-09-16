# Add to app/utils/email_utils.py (or create if doesn't exist)

from flask_mail import Message
from flask import current_app, render_template_string
from app import mail
import os

def send_demo_confirmation_email(demo_student, demo_class):
    """Send demo class confirmation email to student/parent"""
    try:
        # Email template for demo confirmation
        email_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .header { text-align: center; color: #2c3e50; margin-bottom: 30px; }
                .demo-details { background: #e8f4fd; padding: 20px; border-radius: 8px; margin: 20px 0; }
                .meeting-info { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; }
                .button { display: inline-block; padding: 12px 25px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 15px 0; }
                .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎓 Demo Class Confirmed!</h1>
                    <p>Your demo class has been successfully scheduled</p>
                </div>
                
                <div class="demo-details">
                    <h3>📋 Demo Class Details</h3>
                    <p><strong>Student:</strong> {{ demo_student.full_name }}</p>
                    <p><strong>Subject:</strong> {{ demo_class.subject }}</p>
                    <p><strong>Date:</strong> {{ demo_class.scheduled_date.strftime('%A, %B %d, %Y') }}</p>
                    <p><strong>Time:</strong> {{ demo_class.scheduled_time.strftime('%I:%M %p') }}</p>
                    <p><strong>Duration:</strong> {{ demo_class.duration }} minutes</p>
                    <p><strong>Tutor:</strong> {{ demo_class.tutor.user.full_name }}</p>
                </div>
                
                {% if demo_class.meeting_link %}
                <div class="meeting-info">
                    <h3>💻 Join Meeting</h3>
                    <p><strong>Meeting Link:</strong> <a href="{{ demo_class.meeting_link }}" target="_blank">{{ demo_class.meeting_link }}</a></p>
                    {% if demo_class.meeting_id %}
                    <p><strong>Meeting ID:</strong> {{ demo_class.meeting_id }}</p>
                    {% endif %}
                    {% if demo_class.meeting_password %}
                    <p><strong>Password:</strong> {{ demo_class.meeting_password }}</p>
                    {% endif %}
                    
                    <a href="{{ demo_class.meeting_link }}" class="button" target="_blank">
                        🚀 Join Demo Class
                    </a>
                </div>
                {% endif %}
                
                <div class="demo-details">
                    <h3>📝 Important Instructions</h3>
                    <ul>
                        <li>Please join the meeting 5 minutes before the scheduled time</li>
                        <li>Ensure you have a stable internet connection</li>
                        <li>Keep a notebook and pen ready for the demo</li>
                        <li>Test your audio/video before the session</li>
                        <li>Have any specific questions ready to ask the tutor</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>If you have any questions or need to reschedule, please contact us immediately.</p>
                    <p><strong>Support:</strong> support@yourlms.com | <strong>Phone:</strong> +91-XXXXXXXXXX</p>
                    <p>Thank you for choosing our learning platform!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Render template with data
        html_content = render_template_string(email_template, 
                                            demo_student=demo_student, 
                                            demo_class=demo_class)
        
        # Create message
        msg = Message(
            subject=f"Demo Class Confirmed - {demo_class.subject} on {demo_class.scheduled_date.strftime('%B %d')}",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[demo_student.email],
            html=html_content
        )
        
        # Send email
        mail.send(msg)
        print(f"✅ Demo confirmation email sent to {demo_student.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending demo confirmation email: {str(e)}")
        return False

def send_demo_reminder_email(demo_student, demo_class, hours_before=2):
    """Send demo class reminder email"""
    try:
        reminder_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .header { text-align: center; color: #e74c3c; margin-bottom: 30px; }
                .reminder-box { background: #ffe6e6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #e74c3c; }
                .meeting-link { background: #d4edda; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0; }
                .button { display: inline-block; padding: 12px 25px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⏰ Demo Class Reminder</h1>
                    <p>Your demo class is starting in {{ hours_before }} hours!</p>
                </div>
                
                <div class="reminder-box">
                    <h3>📅 Class Details</h3>
                    <p><strong>Subject:</strong> {{ demo_class.subject }}</p>
                    <p><strong>Time:</strong> {{ demo_class.scheduled_time.strftime('%I:%M %p') }}</p>
                    <p><strong>Tutor:</strong> {{ demo_class.tutor.user.full_name }}</p>
                </div>
                
                <div class="meeting-link">
                    <h3>Ready to Join?</h3>
                    <a href="{{ demo_class.meeting_link }}" class="button" target="_blank">
                        🚀 Join Demo Class Now
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        
        html_content = render_template_string(reminder_template,
                                            demo_student=demo_student,
                                            demo_class=demo_class,
                                            hours_before=hours_before)
        
        msg = Message(
            subject=f"Reminder: Demo Class in {hours_before} hours - {demo_class.subject}",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[demo_student.email],
            html=html_content
        )
        
        mail.send(msg)
        print(f"✅ Demo reminder email sent to {demo_student.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending demo reminder email: {str(e)}")
        return False

def send_demo_feedback_request(demo_student, demo_class):
    """Send feedback request after demo class"""
    try:
        feedback_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .header { text-align: center; color: #17a2b8; margin-bottom: 30px; }
                .feedback-box { background: #e6f3ff; padding: 20px; border-radius: 8px; margin: 20px 0; }
                .button { display: inline-block; padding: 12px 25px; background: #17a2b8; color: white; text-decoration: none; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 How was your Demo Class?</h1>
                    <p>We'd love to hear your feedback!</p>
                </div>
                
                <div class="feedback-box">
                    <h3>Thank you for attending the demo class!</h3>
                    <p>Subject: <strong>{{ demo_class.subject }}</strong></p>
                    <p>Tutor: <strong>{{ demo_class.tutor.user.full_name }}</strong></p>
                    
                    <p>Your feedback helps us improve our teaching quality and helps other students make informed decisions.</p>
                    
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="#" class="button">Share Your Feedback</a>
                    </div>
                </div>
                
                <div style="margin-top: 30px; text-align: center;">
                    <p>Interested in regular classes? <a href="#">Contact us</a> to enroll!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        html_content = render_template_string(feedback_template,
                                            demo_student=demo_student,
                                            demo_class=demo_class)
        
        msg = Message(
            subject=f"How was your demo class? - {demo_class.subject}",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[demo_student.email],
            html=html_content
        )
        
        mail.send(msg)
        print(f"✅ Demo feedback request sent to {demo_student.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending demo feedback request: {str(e)}")
        return False

def send_conversion_welcome_email(regular_student, demo_student):
    """Send welcome email after demo student conversion"""
    try:
        welcome_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .header { text-align: center; color: #28a745; margin-bottom: 30px; }
                .welcome-box { background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; }
                .next-steps { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to Our Learning Family!</h1>
                    <p>Congratulations on joining as a regular student!</p>
                </div>
                
                <div class="welcome-box">
                    <h3>Student Details</h3>
                    <p><strong>Name:</strong> {{ regular_student.full_name }}</p>
                    <p><strong>Grade:</strong> {{ regular_student.grade }}</p>
                    <p><strong>Subjects:</strong> {{ regular_student.get_subjects_enrolled() | join(', ') }}</p>
                    <p><strong>Student ID:</strong> {{ regular_student.id }}</p>
                </div>
                
                <div class="next-steps">
                    <h3>What's Next?</h3>
                    <ul>
                        <li>Your regular classes will be scheduled shortly</li>
                        <li>You'll receive login credentials for the student portal</li>
                        <li>Complete fee payment to activate your account</li>
                        <li>Access study materials and resources</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <p>Welcome aboard! We're excited to be part of your learning journey.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        html_content = render_template_string(welcome_template,
                                            regular_student=regular_student,
                                            demo_student=demo_student)
        
        msg = Message(
            subject=f"Welcome to Our Learning Platform - {regular_student.full_name}!",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[regular_student.email],
            html=html_content
        )
        
        mail.send(msg)
        print(f"✅ Conversion welcome email sent to {regular_student.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending conversion welcome email: {str(e)}")
        return False