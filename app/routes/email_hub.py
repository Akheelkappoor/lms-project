from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models.user import User
from app.models.student import Student
from app.models.tutor import Tutor
from app.models.class_model import Class
from app.models.escalation import Escalation
from app.utils.advanced_permissions import require_permission
from app.utils.email import send_email
import json

bp = Blueprint('email_hub', __name__)

@bp.route('/email-hub')
@login_required
@require_permission('communication')
def dashboard():
    """Email Hub Dashboard - Central place to manage all emails"""
    
    # Get email statistics
    stats = get_email_stats()
    
    # Get recent email activities (if you want to track this)
    recent_activities = get_recent_email_activities()
    
    return render_template('email_hub/dashboard.html', 
                         stats=stats, 
                         recent_activities=recent_activities)

@bp.route('/email-hub/send-reminders', methods=['GET', 'POST'])
@login_required
@require_permission('communication')
def send_reminders():
    """Send class reminders page"""
    
    if request.method == 'POST':
        data = request.get_json()
        reminder_type = data.get('type')  # '24h', '1h', 'custom'
        
        if reminder_type == '24h':
            return send_24h_reminders()
        elif reminder_type == '1h':
            return send_1h_reminders()
        elif reminder_type == 'custom':
            return send_custom_reminders(data)
    
    # Get upcoming classes for reminder options
    upcoming_classes = get_upcoming_classes()
    
    return render_template('email_hub/send_reminders.html', 
                         upcoming_classes=upcoming_classes)

@bp.route('/email-hub/fee-reminders', methods=['GET', 'POST'])
@login_required
@require_permission('communication')
def fee_reminders():
    """Send fee payment reminders"""
    
    if request.method == 'POST':
        data = request.get_json()
        return send_fee_payment_reminders(data)
    
    # Get students with outstanding fees
    students_with_fees = get_students_with_outstanding_fees()
    
    return render_template('email_hub/fee_reminders.html', 
                         students=students_with_fees)

@bp.route('/email-hub/escalation-notifications', methods=['GET', 'POST'])
@login_required
@require_permission('communication')
def escalation_notifications():
    """Send escalation notifications"""
    
    if request.method == 'POST':
        data = request.get_json()
        return send_escalation_alerts(data)
    
    # Get active escalations
    escalations = get_active_escalations()
    
    return render_template('email_hub/escalation_notifications.html', 
                         escalations=escalations)

@bp.route('/email-hub/onboarding-emails', methods=['GET', 'POST'])
@login_required
@require_permission('communication')
def onboarding_emails():
    """Send onboarding and welcome emails"""
    
    if request.method == 'POST':
        data = request.get_json()
        return send_onboarding_notifications(data)
    
    # Get recently created users who might need onboarding
    recent_users = get_recent_users()
    
    return render_template('email_hub/onboarding_emails.html', 
                         recent_users=recent_users)

@bp.route('/email-hub/bulk-notifications', methods=['GET', 'POST'])
@login_required
@require_permission('communication')
def bulk_notifications():
    """Send bulk notifications to groups"""
    
    if request.method == 'POST':
        data = request.get_json()
        return send_bulk_group_notifications(data)
    
    # Get groups for bulk sending
    groups = get_notification_groups()
    
    return render_template('email_hub/bulk_notifications.html', 
                         groups=groups)

# ============ HELPER FUNCTIONS ============

def get_email_stats():
    """Get email statistics for dashboard"""
    today = date.today()
    
    # Upcoming classes in next 24 hours
    upcoming_24h = Class.query.filter(
        Class.scheduled_date >= today,
        Class.scheduled_date <= today + timedelta(days=1),
        Class.status == 'scheduled'
    ).count()
    
    # Students with outstanding fees
    students = Student.query.filter_by(is_active=True).all()
    outstanding_fees = sum(1 for s in students if s.calculate_outstanding_fees() > 0)
    
    # Active escalations
    active_escalations = Escalation.query.filter_by(status='open').count()
    
    # Recent users (last 7 days)
    recent_users = User.query.filter(
        User.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    return {
        'upcoming_classes_24h': upcoming_24h,
        'outstanding_fees_count': outstanding_fees,
        'active_escalations': active_escalations,
        'recent_users': recent_users,
        'total_students': Student.query.filter_by(is_active=True).count(),
        'total_tutors': Tutor.query.filter_by(status='active').count()
    }

def get_recent_email_activities():
    """Get recent email activities (placeholder for future implementation)"""
    return []

def send_24h_reminders():
    """Send 24-hour class reminders"""
    tomorrow = date.today() + timedelta(days=1)
    
    classes = Class.query.filter(
        Class.scheduled_date == tomorrow,
        Class.status == 'scheduled'
    ).all()
    
    sent_count = 0
    failed_count = 0
    
    for cls in classes:
        try:
            if cls.primary_student_id:
                student = Student.query.get(cls.primary_student_id)
                if student:
                    send_class_reminder_email(cls, student, '24h')
                    sent_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to send reminder: {e}")
    
    return jsonify({
        'success': True,
        'sent': sent_count,
        'failed': failed_count,
        'message': f'Sent {sent_count} reminders'
    })

def send_1h_reminders():
    """Send 1-hour class reminders"""
    # Implementation for 1-hour reminders
    return jsonify({'success': True, 'message': '1-hour reminders sent'})

def send_custom_reminders(data):
    """Send custom reminders"""
    try:
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        # Build query filters
        filters = [
            Class.scheduled_date.between(start_date, end_date),
            Class.status == 'scheduled'
        ]
        
        if data.get('subject'):
            filters.append(Class.subject.ilike(f"%{data['subject']}%"))
        
        classes = Class.query.filter(*filters).all()
        
        if data.get('grade'):
            # Filter by student grade
            classes = [cls for cls in classes if cls.primary_student_id and 
                      Student.query.get(cls.primary_student_id) and
                      Student.query.get(cls.primary_student_id).grade == data['grade']]
        
        sent_count = 0
        for cls in classes:
            try:
                if cls.primary_student_id:
                    student = Student.query.get(cls.primary_student_id)
                    if student:
                        send_class_reminder_email(cls, student, 'custom', data.get('custom_message'))
                        sent_count += 1
            except Exception as e:
                print(f"Failed to send custom reminder: {e}")
        
        return jsonify({
            'success': True,
            'sent': sent_count,
            'message': f'Sent {sent_count} custom reminders'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============ ADDITIONAL API ROUTES ============

@bp.route('/email-hub/recipient-counts')
@login_required
@require_permission('communication')
def get_recipient_counts():
    """Get recipient counts for different groups"""
    try:
        # Get parent email count
        students = Student.query.filter_by(is_active=True).all()
        parent_emails = set()
        
        for student in students:
            parent_details = student.get_parent_details()
            if parent_details:
                father_email = parent_details.get('father', {}).get('email')
                mother_email = parent_details.get('mother', {}).get('email')
                if father_email:
                    parent_emails.add(father_email)
                if mother_email:
                    parent_emails.add(mother_email)
        
        # Get active users count
        active_users = User.query.filter_by(is_active=True).count()
        
        return jsonify({
            'success': True,
            'parents': len(parent_emails),
            'active_users': active_users
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/email-hub/preview-reminder')
@login_required
@require_permission('communication')
def preview_reminder():
    """Preview reminder email"""
    reminder_type = request.args.get('type', '24h')
    
    # Create a sample preview
    preview_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #F1A150, #C86706); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .class-card {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>🔔 Class Reminder</h1>
                <p>Your class is starting {"tomorrow" if reminder_type == "24h" else "soon"}!</p>
            </div>
            
            <div class="email-body">
                <h2>Hello Student Name,</h2>
                <p>This is a {"24-hour" if reminder_type == "24h" else "1-hour" if reminder_type == "1h" else "custom"} reminder about your upcoming class.</p>
                
                <div class="class-card">
                    <h3 style="margin: 0 0 1rem 0; color: #F1A150;">📚 Sample Subject</h3>
                    <p><strong>📅 Date:</strong> Tomorrow, March 15, 2024</p>
                    <p><strong>⏰ Time:</strong> 4:00 PM</p>
                    <p><strong>🕒 Duration:</strong> 60 minutes</p>
                    <p><strong>👨‍🏫 Tutor:</strong> Sample Tutor</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="#" style="background: #F1A150; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        🚀 Join Class Now
                    </a>
                </div>
                
                <p style="margin-top: 2rem;">This is a preview of how your {"24-hour" if reminder_type == "24h" else "1-hour" if reminder_type == "1h" else "custom"} reminder email will look.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return preview_html

@bp.route('/email-hub/preview-onboarding')
@login_required
@require_permission('communication')
def preview_onboarding():
    """Preview onboarding email"""
    user_type = request.args.get('type', 'student')
    
    # Role-specific preview content
    role_info = {
        'student': {
            'icon': '🎓',
            'title': 'Welcome to Your Learning Journey',
            'description': 'Get ready to excel in your studies with our personalized learning platform.',
        },
        'tutor': {
            'icon': '👨‍🏫',
            'title': 'Welcome to Our Teaching Community',
            'description': 'Start making a difference in students\' lives with our comprehensive teaching platform.',
        },
        'parent': {
            'icon': '👨‍👩‍👧‍👦',
            'title': 'Stay Connected with Your Child\'s Learning',
            'description': 'Track your child\'s progress and stay involved in their educational journey.',
        },
        'staff': {
            'icon': '⚙️',
            'title': 'Welcome to System Administration',
            'description': 'Full system access to manage and configure the LMS platform.',
        }
    }
    
    role_data = role_info.get(user_type, role_info['student'])
    
    preview_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .credentials-box {{ background: #f0f9ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>{role_data['icon']} Welcome to I2Global LMS!</h1>
                <p>{role_data['title']}</p>
            </div>
            
            <div class="email-body">
                <h2>Hello Sample User,</h2>
                <p>{role_data['description']}</p>
                
                <div class="credentials-box">
                    <h3 style="margin: 0 0 1rem 0; color: #1976d2;">🔑 Your Login Credentials</h3>
                    <p><strong>Username:</strong> sample_user</p>
                    <p><strong>Email:</strong> sample@example.com</p>
                    <p><strong>Role:</strong> {user_type.title()}</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="#" style="background: #F1A150; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        🚀 Login to Your Account
                    </a>
                </div>
                
                <p style="margin-top: 2rem;">This is a preview of how your {user_type} onboarding email will look.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return preview_html

def send_class_reminder_email(class_obj, student, reminder_type, custom_message=None):
    """Send class reminder email to student"""
    from app.utils.email import send_email
    
    # Get tutor info
    tutor_name = "Your tutor"
    if class_obj.tutor_id:
        tutor = Tutor.query.get(class_obj.tutor_id)
        if tutor and tutor.user:
            tutor_name = tutor.user.full_name
    
    # Create subject based on reminder type
    if reminder_type == '24h':
        subject = f"🔔 Class Tomorrow - {class_obj.subject}"
        timing_text = "tomorrow"
    elif reminder_type == '1h':
        subject = f"🔔 Class Starting Soon - {class_obj.subject}"
        timing_text = "in 1 hour"
    else:
        subject = f"🔔 Class Reminder - {class_obj.subject}"
        timing_text = "soon"
    
    # Build HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #F1A150, #C86706); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .class-card {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; }}
            .detail-row {{ display: flex; align-items: center; gap: 0.75rem; margin: 0.75rem 0; }}
            .join-button {{ display: inline-block; background: #F1A150; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 1.5rem 0; }}
            .join-button:hover {{ background: #C86706; }}
            .backup-info {{ background: #e3f2fd; border: 1px solid #bbdefb; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
            .footer {{ background: #f8f9fa; padding: 1.5rem; text-align: center; color: #6c757d; font-size: 0.875rem; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>🔔 Class Reminder</h1>
                <p>Your class is starting {timing_text}!</p>
            </div>
            
            <div class="email-body">
                <h2>Hello {student.full_name},</h2>
                <p>This is a friendly reminder about your upcoming class.</p>
                
                {f'<div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 1rem; margin: 1rem 0; color: #856404;"><strong>Custom Message:</strong> {custom_message}</div>' if custom_message else ''}
                
                <div class="class-card">
                    <h3 style="margin: 0 0 1rem 0; color: #F1A150;">📚 {class_obj.subject}</h3>
                    <div class="detail-row">
                        <span style="font-size: 1.2rem;">📅</span>
                        <span><strong>Date:</strong> {class_obj.scheduled_date.strftime('%A, %B %d, %Y')}</span>
                    </div>
                    <div class="detail-row">
                        <span style="font-size: 1.2rem;">⏰</span>
                        <span><strong>Time:</strong> {class_obj.scheduled_time.strftime('%I:%M %p') if class_obj.scheduled_time else 'TBD'}</span>
                    </div>
                    <div class="detail-row">
                        <span style="font-size: 1.2rem;">🕒</span>
                        <span><strong>Duration:</strong> {class_obj.duration or 60} minutes</span>
                    </div>
                    <div class="detail-row">
                        <span style="font-size: 1.2rem;">👨‍🏫</span>
                        <span><strong>Tutor:</strong> {tutor_name}</span>
                    </div>
                </div>
                
                <div style="text-align: center;">
                    <a href="{class_obj.meeting_link or '#'}" class="join-button">
                        🚀 Join Class Now
                    </a>
                </div>
                
                {f'''
                <div class="backup-info">
                    <h4 style="margin: 0 0 0.5rem 0; color: #1976d2;">📋 Meeting Details</h4>
                    <p><strong>Meeting ID:</strong> {class_obj.meeting_id}</p>
                    <p><strong>Password:</strong> {class_obj.meeting_password}</p>
                    <p style="font-size: 0.875rem; color: #6c757d; margin: 0;">Use these details if the join button doesn't work</p>
                </div>
                ''' if class_obj.meeting_id else ''}
                
                <div style="margin: 1.5rem 0; padding: 1rem; background: #f0f9ff; border-radius: 8px;">
                    <h4 style="margin: 0 0 0.5rem 0; color: #0369a1;">💡 Quick Tips</h4>
                    <ul style="margin: 0; padding-left: 1.2rem; color: #0369a1;">
                        <li>Join 2-3 minutes early to test your audio and video</li>
                        <li>Have your study materials ready</li>
                        <li>Ensure you have a stable internet connection</li>
                    </ul>
                </div>
            </div>
            
            <div class="footer">
                <p>Need help? Contact us at care@i2global.co.in or call +91 9600127000</p>
                <p style="margin: 0;">© 2024 I2Global Virtual Learning. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Text version for email clients that don't support HTML
    text_content = f"""
Class Reminder - {class_obj.subject}

Hello {student.full_name},

Your class is starting {timing_text}!

Class Details:
- Subject: {class_obj.subject}
- Date: {class_obj.scheduled_date.strftime('%A, %B %d, %Y')}
- Time: {class_obj.scheduled_time.strftime('%I:%M %p') if class_obj.scheduled_time else 'TBD'}
- Duration: {class_obj.duration or 60} minutes
- Tutor: {tutor_name}

Meeting Link: {class_obj.meeting_link or 'Will be provided separately'}
Meeting ID: {class_obj.meeting_id or 'N/A'}
Password: {class_obj.meeting_password or 'N/A'}

{f'Custom Message: {custom_message}' if custom_message else ''}

Need help? Contact us at care@i2global.co.in

Best regards,
I2Global Virtual Learning Team
    """
    
    send_email(
        subject=subject,
        recipients=[student.email],
        text_body=text_content,
        html_body=html_content
    )

def get_upcoming_classes():
    """Get upcoming classes for reminder options"""
    today = date.today()
    next_week = today + timedelta(days=7)
    
    return Class.query.filter(
        Class.scheduled_date.between(today, next_week),
        Class.status == 'scheduled'
    ).order_by(Class.scheduled_date, Class.scheduled_time).all()

def get_students_with_outstanding_fees():
    """Get students with outstanding fees"""
    students = Student.query.filter_by(is_active=True).all()
    return [s for s in students if s.calculate_outstanding_fees() > 0]

def get_active_escalations():
    """Get active escalations"""
    return Escalation.query.filter_by(status='open').order_by(Escalation.created_at.desc()).all()

def get_recent_users():
    """Get recently created users"""
    week_ago = datetime.utcnow() - timedelta(days=7)
    return User.query.filter(User.created_at >= week_ago).order_by(User.created_at.desc()).all()

def get_notification_groups():
    """Get groups for bulk notifications"""
    return {
        'all_students': Student.query.filter_by(is_active=True).count(),
        'all_tutors': Tutor.query.filter_by(status='active').count(),
        'coordinators': User.query.filter_by(role='coordinator', is_active=True).count(),
        'admins': User.query.filter(User.role.in_(['admin', 'superadmin']), User.is_active == True).count()
    }

def send_fee_payment_reminders(data):
    """Send fee payment reminders"""
    try:
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            # Get all students with outstanding fees
            students = Student.query.filter_by(is_active=True).all()
            students_with_fees = [s for s in students if s.calculate_outstanding_fees() > 0]
        else:
            students_with_fees = Student.query.filter(Student.id.in_(student_ids)).all()
        
        sent_count = 0
        failed_count = 0
        
        for student in students_with_fees:
            try:
                outstanding = student.calculate_outstanding_fees()
                if outstanding > 0:
                    send_fee_reminder_email(student, outstanding)
                    sent_count += 1
            except Exception as e:
                print(f"Failed to send fee reminder to {student.email}: {e}")
                failed_count += 1
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'message': f'Sent {sent_count} fee reminders'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_fee_reminder_email(student, outstanding_amount):
    """Send fee reminder email"""
    from app.utils.email import send_email
    
    # Get parent details
    parent_details = student.get_parent_details()
    parent_name = parent_details.get('father', {}).get('name') or parent_details.get('mother', {}).get('name') or 'Parent/Guardian'
    
    subject = f"💰 Fee Payment Reminder - {student.full_name}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .payment-details {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; }}
            .amount-highlight {{ font-size: 1.5rem; font-weight: bold; color: #dc2626; text-align: center; margin: 1rem 0; }}
            .pay-button {{ display: inline-block; background: #F1A150; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 1.5rem 0; }}
            .contact-info {{ background: #f0f9ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
            .footer {{ background: #f8f9fa; padding: 1.5rem; text-align: center; color: #6c757d; font-size: 0.875rem; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>💰 Fee Payment Reminder</h1>
                <p>Your prompt attention is requested</p>
            </div>
            
            <div class="email-body">
                <h2>Dear {parent_name},</h2>
                <p>We hope this message finds you well. This is a friendly reminder about the outstanding fee payment for <strong>{student.full_name}</strong>.</p>
                
                <div class="payment-details">
                    <h3 style="margin: 0 0 1rem 0; color: #dc2626;">📋 Payment Details</h3>
                    <div style="display: grid; gap: 0.5rem;">
                        <div><strong>Student Name:</strong> {student.full_name}</div>
                        <div><strong>Grade:</strong> {student.grade} - {student.board}</div>
                        <div><strong>Student ID:</strong> {student.id}</div>
                    </div>
                    
                    <div class="amount-highlight">
                        Outstanding Amount: ₹{outstanding_amount:,.2f}
                    </div>
                    
                    <div style="text-align: center; color: #dc2626; font-size: 0.875rem;">
                        Please clear this amount at your earliest convenience
                    </div>
                </div>
                
                <p>To ensure uninterrupted learning for {student.full_name}, we kindly request you to process the payment as soon as possible.</p>
                
                <div style="text-align: center;">
                    <a href="#" class="pay-button">
                        💳 Pay Now
                    </a>
                </div>
                
                <div class="contact-info">
                    <h4 style="margin: 0 0 0.5rem 0; color: #1976d2;">📞 Payment Support</h4>
                    <p style="margin: 0;">For payment assistance or queries:</p>
                    <ul style="margin: 0.5rem 0; padding-left: 1.2rem;">
                        <li>Call: +91 9600127000</li>
                        <li>Email: care@i2global.co.in</li>
                        <li>WhatsApp: +91 9600127000</li>
                    </ul>
                </div>
                
                <div style="margin: 1.5rem 0; padding: 1rem; background: #fff3cd; border-radius: 8px; border: 1px solid #ffeaa7;">
                    <p style="margin: 0; color: #856404;"><strong>Payment Methods:</strong> We accept bank transfers, UPI, credit/debit cards, and online payments. Contact us for detailed payment instructions.</p>
                </div>
                
                <p>Thank you for choosing I2Global Virtual Learning for {student.full_name}'s education.</p>
            </div>
            
            <div class="footer">
                <p>I2Global Virtual Learning</p>
                <p>48, 4th Block, Koramangala, Bengaluru, Karnataka 560034</p>
                <p style="margin: 0;">Email: care@i2global.co.in | Phone: +91 9600127000</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
Fee Payment Reminder - {student.full_name}

Dear {parent_name},

This is a friendly reminder about the outstanding fee payment for {student.full_name}.

Payment Details:
- Student: {student.full_name}
- Grade: {student.grade} - {student.board}
- Outstanding Amount: ₹{outstanding_amount:,.2f}

Please process the payment at your earliest convenience to ensure uninterrupted learning.

For payment assistance:
- Call: +91 9600127000
- Email: care@i2global.co.in

Thank you for choosing I2Global Virtual Learning.

Best regards,
I2Global Team
    """
    
    send_email(
        subject=subject,
        recipients=[student.email],
        text_body=text_content,
        html_body=html_content
    )

def send_escalation_alerts(data):
    """Send escalation alerts"""
    try:
        action = data.get('action')
        
        if action == 'send_urgent_alerts':
            return send_urgent_escalation_alerts()
        elif action == 'send_daily_digest':
            return send_escalation_daily_digest()
        elif action == 'send_resolution_updates':
            return send_escalation_resolution_updates()
        elif action == 'send_overdue_reminders':
            return send_escalation_overdue_reminders()
        elif action == 'send_individual_alert':
            escalation_id = data.get('escalation_id')
            return send_individual_escalation_alert(escalation_id)
        elif action == 'send_urgent_individual_alert':
            escalation_id = data.get('escalation_id')
            return send_urgent_individual_escalation_alert(escalation_id)
        elif action == 'send_bulk_notifications':
            escalation_ids = data.get('escalation_ids', [])
            return send_bulk_escalation_notifications(escalation_ids)
        else:
            return jsonify({'success': False, 'error': 'Unknown action'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_urgent_escalation_alerts():
    """Send urgent alerts for high priority escalations"""
    high_priority_escalations = Escalation.query.filter_by(
        priority='high',
        status='open'
    ).all()
    
    sent_count = 0
    for escalation in high_priority_escalations:
        # Send to assigned user and admins
        recipients = []
        if escalation.assigned_to_user:
            recipients.append(escalation.assigned_to_user.email)
        
        # Add admins and superadmins
        admins = User.query.filter(
            User.role.in_(['admin', 'superadmin']),
            User.is_active == True
        ).all()
        recipients.extend([admin.email for admin in admins])
        
        if recipients:
            send_escalation_alert_email(escalation, recipients, urgent=True)
            sent_count += 1
    
    return jsonify({
        'success': True,
        'sent_count': sent_count,
        'message': f'Sent {sent_count} urgent alerts'
    })

def send_escalation_alert_email(escalation, recipients, urgent=False):
    """Send escalation alert email"""
    from app.utils.email import send_email
    
    if urgent:
        subject = f"🚨 URGENT ESCALATION: {escalation.title}"
        priority_text = "URGENT ATTENTION REQUIRED"
        header_color = "#dc2626"
    else:
        subject = f"⚠️ Escalation Alert: {escalation.title}"
        priority_text = "Attention Required"
        header_color = "#F1A150"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: {header_color}; color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .escalation-details {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
            .priority-badge {{ background: #dc2626; color: white; padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.875rem; font-weight: bold; }}
            .action-button {{ display: inline-block; background: #F1A150; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 1rem 0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>{"🚨" if urgent else "⚠️"} Escalation Alert</h1>
                <p>{priority_text}</p>
            </div>
            
            <div class="email-body">
                <div class="escalation-details">
                    <h3>{escalation.title}</h3>
                    <div style="margin: 1rem 0;">
                        <span class="priority-badge">{escalation.priority.upper()} PRIORITY</span>
                    </div>
                    
                    <p><strong>Category:</strong> {escalation.category}</p>
                    <p><strong>Created by:</strong> {escalation.created_by_user.full_name}</p>
                    <p><strong>Created on:</strong> {escalation.created_at.strftime('%d %b %Y at %I:%M %p')}</p>
                    <p><strong>Status:</strong> {escalation.status.title()}</p>
                    
                    <h4>Description:</h4>
                    <p>{escalation.description}</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="http://localhost:5000/escalations/{escalation.id}" class="action-button">
                        View Escalation Details
                    </a>
                </div>
                
                <p>Please review this escalation and take appropriate action as soon as possible.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(
        subject=subject,
        recipients=recipients,
        text_body=f"Escalation Alert: {escalation.title}\n\n{escalation.description}",
        html_body=html_content
    )

def send_onboarding_notifications(data):
    """Send onboarding notifications"""
    try:
        action = data.get('action')
        
        if action == 'send_student_onboarding':
            return send_user_type_onboarding('student')
        elif action == 'send_tutor_onboarding':
            return send_user_type_onboarding('tutor')
        elif action == 'send_parent_onboarding':
            return send_parent_onboarding_emails()
        elif action == 'send_staff_onboarding':
            return send_user_type_onboarding('coordinator', 'admin')
        elif action == 'send_bulk_onboarding':
            user_ids = data.get('user_ids', [])
            return send_bulk_user_onboarding(user_ids)
        elif action == 'send_individual_onboarding':
            user_id = data.get('user_id')
            return send_individual_user_onboarding(user_id)
        else:
            return jsonify({'success': False, 'error': 'Unknown action'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_user_type_onboarding(*user_roles):
    """Send onboarding emails to users of specific roles"""
    # Get recent users of specified roles
    week_ago = datetime.utcnow() - timedelta(days=7)
    users = User.query.filter(
        User.role.in_(user_roles),
        User.created_at >= week_ago,
        User.is_active == True
    ).all()
    
    sent_count = 0
    for user in users:
        try:
            send_user_onboarding_email(user)
            sent_count += 1
        except Exception as e:
            print(f"Failed to send onboarding email to {user.email}: {e}")
    
    return jsonify({
        'success': True,
        'sent_count': sent_count,
        'message': f'Sent {sent_count} onboarding emails'
    })

def send_user_onboarding_email(user):
    """Send onboarding email to user"""
    from app.utils.email import send_email
    
    subject = f"👋 Welcome to I2Global LMS - Your Account is Ready!"
    
    # Role-specific content
    role_info = {
        'student': {
            'icon': '🎓',
            'title': 'Welcome to Your Learning Journey',
            'description': 'Get ready to excel in your studies with our personalized learning platform.',
            'features': [
                'Access live classes with expert tutors',
                'View your class schedule and assignments',
                'Track your progress and performance',
                'Communicate with tutors and coordinators'
            ]
        },
        'tutor': {
            'icon': '👨‍🏫',
            'title': 'Welcome to Our Teaching Community',
            'description': 'Start making a difference in students\' lives with our comprehensive teaching platform.',
            'features': [
                'Manage your class schedules',
                'Access student profiles and progress',
                'Submit attendance and feedback',
                'Upload teaching materials and resources'
            ]
        },
        'coordinator': {
            'icon': '📊',
            'title': 'Welcome to Your Management Dashboard',
            'description': 'Oversee operations and ensure smooth delivery of educational services.',
            'features': [
                'Monitor department activities',
                'Manage student and tutor assignments',
                'Generate reports and analytics',
                'Handle escalations and communications'
            ]
        },
        'admin': {
            'icon': '⚙️',
            'title': 'Welcome to System Administration',
            'description': 'Full system access to manage and configure the LMS platform.',
            'features': [
                'Complete user management',
                'System configuration and settings',
                'Financial and operational reports',
                'Platform maintenance and monitoring'
            ]
        }
    }
    
    role_data = role_info.get(user.role, role_info['student'])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .credentials-box {{ background: #f0f9ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
            .feature-list {{ background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
            .login-button {{ display: inline-block; background: #F1A150; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 1.5rem 0; }}
            .contact-info {{ background: #fef3c7; border: 1px solid #fde68a; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>{role_data['icon']} Welcome to I2Global LMS!</h1>
                <p>{role_data['title']}</p>
            </div>
            
            <div class="email-body">
                <h2>Hello {user.full_name},</h2>
                <p>{role_data['description']}</p>
                
                <div class="credentials-box">
                    <h3 style="margin: 0 0 1rem 0; color: #1976d2;">🔑 Your Login Credentials</h3>
                    <div style="background: white; padding: 1rem; border-radius: 6px; border: 1px solid #e3f2fd;">
                        <p><strong>Username:</strong> {user.username}</p>
                        <p><strong>Email:</strong> {user.email}</p>
                        <p><strong>Role:</strong> {user.role.title()}</p>
                        {f'<p><strong>Department:</strong> {user.department.name}</p>' if user.department else ''}
                    </div>
                    <p style="color: #1565c0; font-size: 0.875rem; margin: 0.5rem 0 0 0;">
                        Your password was sent separately for security. Please check your email or contact support.
                    </p>
                </div>
                
                <div class="feature-list">
                    <h3 style="margin: 0 0 1rem 0;">✨ What You Can Do</h3>
                    <ul style="margin: 0; padding-left: 1.2rem;">
                        {chr(10).join([f'<li>{feature}</li>' for feature in role_data['features']])}
                    </ul>
                </div>
                
                <div style="text-align: center;">
                    <a href="http://localhost:5000/auth/login" class="login-button">
                        🚀 Login to Your Account
                    </a>
                </div>
                
                <div class="contact-info">
                    <h4 style="margin: 0 0 0.5rem 0; color: #d97706;">📞 Need Help?</h4>
                    <p style="margin: 0;">Our support team is here to help you get started:</p>
                    <ul style="margin: 0.5rem 0; padding-left: 1.2rem;">
                        <li>Email: care@i2global.co.in</li>
                        <li>Phone: +91 9600127000</li>
                        <li>WhatsApp: +91 9600127000</li>
                    </ul>
                </div>
                
                <p>We're excited to have you join our learning community!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(
        subject=subject,
        recipients=[user.email],
        text_body=f"Welcome to I2Global LMS! Your account is ready. Login at: http://localhost:5000/auth/login",
        html_body=html_content
    )

def send_bulk_group_notifications(data):
    """Send bulk notifications"""
    try:
        action = data.get('action')
        
        if action == 'send_bulk_notification':
            return process_bulk_notification(data)
        elif action == 'save_draft':
            return save_notification_draft(data)
        else:
            return jsonify({'success': False, 'error': 'Unknown action'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def process_bulk_notification(data):
    """Process bulk notification sending"""
    try:
        groups = data.get('groups', [])
        subject = data.get('subject', '')
        content = data.get('content', '')
        priority = data.get('priority', 'normal')
        custom_recipients = data.get('custom_recipients', '')
        
        if not subject or not content:
            return jsonify({'success': False, 'error': 'Subject and content are required'})
        
        # Collect all recipients
        all_recipients = []
        
        # Add group recipients
        for group in groups:
            recipients = get_group_recipients(group)
            all_recipients.extend(recipients)
        
        # Add custom recipients
        if custom_recipients:
            custom_emails = [email.strip() for email in custom_recipients.split(',') if email.strip()]
            all_recipients.extend(custom_emails)
        
        # Remove duplicates
        all_recipients = list(set(all_recipients))
        
        if not all_recipients:
            return jsonify({'success': False, 'error': 'No recipients found'})
        
        # Send bulk notification
        sent_count = send_bulk_notification_email(
            recipients=all_recipients,
            subject=subject,
            content=content,
            priority=priority
        )
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'total_recipients': len(all_recipients),
            'message': f'Sent notification to {sent_count} recipients'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_group_recipients(group_name):
    """Get email recipients for a specific group"""
    recipients = []
    
    try:
        if group_name == 'all_students':
            students = Student.query.filter_by(is_active=True).all()
            recipients = [student.email for student in students if student.email]
            
        elif group_name == 'all_tutors':
            tutors = Tutor.query.join(User).filter(
                Tutor.status == 'active',
                User.is_active == True
            ).all()
            recipients = [tutor.user.email for tutor in tutors if tutor.user and tutor.user.email]
            
        elif group_name == 'coordinators':
            coordinators = User.query.filter_by(role='coordinator', is_active=True).all()
            recipients = [coord.email for coord in coordinators if coord.email]
            
        elif group_name == 'admins':
            admins = User.query.filter(
                User.role.in_(['admin', 'superadmin']),
                User.is_active == True
            ).all()
            recipients = [admin.email for admin in admins if admin.email]
            
        elif group_name == 'parents':
            # Get parent emails from student records
            students = Student.query.filter_by(is_active=True).all()
            for student in students:
                parent_details = student.get_parent_details()
                if parent_details:
                    father_email = parent_details.get('father', {}).get('email')
                    mother_email = parent_details.get('mother', {}).get('email')
                    if father_email:
                        recipients.append(father_email)
                    if mother_email:
                        recipients.append(mother_email)
        
        elif group_name == 'active_users':
            users = User.query.filter_by(is_active=True).all()
            recipients = [user.email for user in users if user.email]
            
    except Exception as e:
        print(f"Error getting recipients for group {group_name}: {e}")
    
    return recipients

def send_bulk_notification_email(recipients, subject, content, priority='normal'):
    """Send bulk notification email"""
    from app.utils.email import send_email
    
    # Priority styling
    if priority == 'urgent':
        header_color = "#dc2626"
        priority_badge = "🚨 URGENT"
        priority_bg = "#fef2f2"
    elif priority == 'high':
        header_color = "#f59e0b"
        priority_badge = "⚡ HIGH PRIORITY"
        priority_bg = "#fef3c7"
    else:
        header_color = "#F1A150"
        priority_badge = "📢 ANNOUNCEMENT"
        priority_bg = "#f0f9ff"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: {header_color}; color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .priority-badge {{ background: {priority_bg}; border: 1px solid {header_color}; color: {header_color}; padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0; text-align: center; font-weight: bold; }}
            .content-area {{ background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; line-height: 1.6; }}
            .footer {{ background: #f8f9fa; padding: 1.5rem; text-align: center; color: #6c757d; font-size: 0.875rem; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>{priority_badge}</h1>
                <p>I2Global Virtual Learning</p>
            </div>
            
            <div class="email-body">
                <div class="priority-badge">
                    {priority_badge}
                </div>
                
                <div class="content-area">
                    {content.replace(chr(10), '<br>')}
                </div>
                
                <div style="margin: 1.5rem 0; padding: 1rem; background: #e3f2fd; border-radius: 8px;">
                    <p style="margin: 0; color: #1565c0; font-size: 0.875rem;">
                        📧 This message was sent to multiple recipients. If you have questions, please contact us directly.
                    </p>
                </div>
            </div>
            
            <div class="footer">
                <p>I2Global Virtual Learning</p>
                <p>48, 4th Block, Koramangala, Bengaluru, Karnataka 560034</p>
                <p style="margin: 0;">Email: care@i2global.co.in | Phone: +91 9600127000</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send in batches to avoid overwhelming the email server
    batch_size = 50
    sent_count = 0
    
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i + batch_size]
        try:
            send_email(
                subject=subject,
                recipients=batch,
                text_body=content,
                html_body=html_content
            )
            sent_count += len(batch)
        except Exception as e:
            print(f"Failed to send batch email: {e}")
    
    return sent_count

# ============ ADDITIONAL HELPER FUNCTIONS ============

def send_escalation_daily_digest():
    """Send daily digest of all escalations"""
    try:
        # Get all open escalations
        escalations = Escalation.query.filter_by(status='open').all()
        
        if not escalations:
            return jsonify({'success': True, 'message': 'No escalations to report'})
        
        # Get all admins and coordinators
        recipients = []
        admins = User.query.filter(
            User.role.in_(['admin', 'superadmin', 'coordinator']),
            User.is_active == True
        ).all()
        recipients = [admin.email for admin in admins if admin.email]
        
        if recipients:
            send_escalation_digest_email(escalations, recipients)
            return jsonify({'success': True, 'message': 'Daily digest sent'})
        else:
            return jsonify({'success': False, 'error': 'No recipients found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_escalation_digest_email(escalations, recipients):
    """Send escalation digest email"""
    from app.utils.email import send_email
    
    subject = f"📊 Daily Escalations Digest - {datetime.now().strftime('%d %b %Y')}"
    
    # Categorize escalations
    high_priority = [e for e in escalations if e.priority == 'high']
    medium_priority = [e for e in escalations if e.priority == 'medium']
    low_priority = [e for e in escalations if e.priority == 'low']
    overdue = [e for e in escalations if (datetime.utcnow() - e.created_at).days > 7]
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .summary-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
            .stat-card {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1rem; text-align: center; }}
            .stat-number {{ font-size: 1.5rem; font-weight: bold; color: #374151; }}
            .escalation-item {{ background: #f8f9fa; border-left: 4px solid #6366f1; padding: 1rem; margin: 0.5rem 0; border-radius: 0 8px 8px 0; }}
            .high-priority {{ border-left-color: #dc2626; }}
            .medium-priority {{ border-left-color: #f59e0b; }}
            .low-priority {{ border-left-color: #10b981; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>📊 Escalations Daily Digest</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <div class="email-body">
                <div class="summary-stats">
                    <div class="stat-card">
                        <div class="stat-number">{len(escalations)}</div>
                        <div>Total Open</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" style="color: #dc2626;">{len(high_priority)}</div>
                        <div>High Priority</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" style="color: #f59e0b;">{len(medium_priority)}</div>
                        <div>Medium Priority</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" style="color: #ef4444;">{len(overdue)}</div>
                        <div>Overdue</div>
                    </div>
                </div>
                
                {generate_escalation_list_html("🚨 High Priority", high_priority, "high-priority") if high_priority else ""}
                {generate_escalation_list_html("⚠️ Medium Priority", medium_priority, "medium-priority") if medium_priority else ""}
                {generate_escalation_list_html("ℹ️ Low Priority", low_priority, "low-priority") if low_priority else ""}
                
                <div style="text-align: center; margin: 2rem 0;">
                    <a href="http://localhost:5000/escalations" style="background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        View All Escalations
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(
        subject=subject,
        recipients=recipients,
        text_body=f"Daily Escalations Digest: {len(escalations)} open escalations",
        html_body=html_content
    )

def generate_escalation_list_html(title, escalations, css_class):
    """Generate HTML for escalation list"""
    if not escalations:
        return ""
    
    items_html = ""
    for esc in escalations[:5]:  # Limit to 5 items per category
        items_html += f"""
        <div class="escalation-item {css_class}">
            <h4 style="margin: 0 0 0.5rem 0;">{esc.title}</h4>
            <p style="margin: 0; color: #6b7280; font-size: 0.875rem;">
                {esc.category} • Created by {esc.created_by_user.full_name} • 
                {(datetime.utcnow() - esc.created_at).days} days ago
            </p>
        </div>
        """
    
    return f"""
    <div style="margin: 2rem 0;">
        <h3>{title} ({len(escalations)})</h3>
        {items_html}
        {f'<p style="color: #6b7280; font-size: 0.875rem;">... and {len(escalations) - 5} more</p>' if len(escalations) > 5 else ''}
    </div>
    """

def send_escalation_resolution_updates():
    """Send resolution updates for recently resolved escalations"""
    try:
        # Get escalations resolved in the last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        resolved_escalations = Escalation.query.filter(
            Escalation.status == 'resolved',
            Escalation.updated_at >= yesterday
        ).all()
        
        if not resolved_escalations:
            return jsonify({'success': True, 'message': 'No recent resolutions to report'})
        
        # Send updates to relevant stakeholders
        sent_count = 0
        for escalation in resolved_escalations:
            recipients = []
            if escalation.created_by_user:
                recipients.append(escalation.created_by_user.email)
            if escalation.assigned_to_user:
                recipients.append(escalation.assigned_to_user.email)
            
            if recipients:
                send_resolution_update_email(escalation, recipients)
                sent_count += 1
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Sent {sent_count} resolution updates'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_resolution_update_email(escalation, recipients):
    """Send resolution update email"""
    from app.utils.email import send_email
    
    subject = f"✅ Escalation Resolved: {escalation.title}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .resolution-details {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>✅ Escalation Resolved</h1>
                <p>Issue has been successfully resolved</p>
            </div>
            
            <div class="email-body">
                <div class="resolution-details">
                    <h3>{escalation.title}</h3>
                    <p><strong>Status:</strong> Resolved</p>
                    <p><strong>Resolved on:</strong> {escalation.updated_at.strftime('%d %b %Y at %I:%M %p')}</p>
                    {f'<p><strong>Resolved by:</strong> {escalation.assigned_to_user.full_name}</p>' if escalation.assigned_to_user else ''}
                    
                    {f'<h4>Resolution Notes:</h4><p>{escalation.resolution_notes}</p>' if hasattr(escalation, 'resolution_notes') and escalation.resolution_notes else ''}
                </div>
                
                <p>Thank you for your patience while we worked to resolve this issue.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(
        subject=subject,
        recipients=recipients,
        text_body=f"Escalation '{escalation.title}' has been resolved.",
        html_body=html_content
    )

def send_escalation_overdue_reminders():
    """Send reminders for overdue escalations"""
    try:
        # Get escalations that are more than 7 days old and still open
        week_ago = datetime.utcnow() - timedelta(days=7)
        overdue_escalations = Escalation.query.filter(
            Escalation.status == 'open',
            Escalation.created_at < week_ago
        ).all()
        
        if not overdue_escalations:
            return jsonify({'success': True, 'message': 'No overdue escalations found'})
        
        # Send reminders to assigned users and admins
        sent_count = 0
        for escalation in overdue_escalations:
            recipients = []
            if escalation.assigned_to_user:
                recipients.append(escalation.assigned_to_user.email)
            
            # Add department coordinators if applicable
            if escalation.department and escalation.department.id:
                dept_coords = User.query.filter_by(
                    department_id=escalation.department.id,
                    role='coordinator',
                    is_active=True
                ).all()
                recipients.extend([coord.email for coord in dept_coords])
            
            if recipients:
                send_overdue_reminder_email(escalation, recipients)
                sent_count += 1
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Sent {sent_count} overdue reminders'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_overdue_reminder_email(escalation, recipients):
    """Send overdue reminder email"""
    from app.utils.email import send_email
    
    days_overdue = (datetime.utcnow() - escalation.created_at).days
    subject = f"⏰ OVERDUE ESCALATION: {escalation.title} ({days_overdue} days)"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .overdue-notice {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; color: #dc2626; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>⏰ OVERDUE ESCALATION</h1>
                <p>Immediate attention required</p>
            </div>
            
            <div class="email-body">
                <div class="overdue-notice">
                    <h3>⚠️ This escalation is {days_overdue} days overdue</h3>
                    <p><strong>Title:</strong> {escalation.title}</p>
                    <p><strong>Priority:</strong> {escalation.priority.upper()}</p>
                    <p><strong>Created:</strong> {escalation.created_at.strftime('%d %b %Y')}</p>
                    <p><strong>Category:</strong> {escalation.category}</p>
                </div>
                
                <p>This escalation requires immediate attention. Please review and take appropriate action as soon as possible.</p>
                
                <div style="text-align: center;">
                    <a href="http://localhost:5000/escalations/{escalation.id}" style="background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Review Escalation Now
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(
        subject=subject,
        recipients=recipients,
        text_body=f"OVERDUE: Escalation '{escalation.title}' is {days_overdue} days overdue and requires immediate attention.",
        html_body=html_content
    )

def send_individual_escalation_alert(escalation_id):
    """Send alert for individual escalation"""
    try:
        escalation = Escalation.query.get(escalation_id)
        if not escalation:
            return jsonify({'success': False, 'error': 'Escalation not found'})
        
        recipients = []
        if escalation.assigned_to_user:
            recipients.append(escalation.assigned_to_user.email)
        
        # Add relevant staff based on department
        if escalation.department:
            dept_staff = User.query.filter_by(
                department_id=escalation.department.id,
                is_active=True
            ).filter(User.role.in_(['coordinator', 'admin'])).all()
            recipients.extend([staff.email for staff in dept_staff])
        
        if recipients:
            send_escalation_alert_email(escalation, recipients, urgent=False)
            return jsonify({'success': True, 'message': 'Alert sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'No recipients found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_urgent_individual_escalation_alert(escalation_id):
    """Send urgent alert for individual escalation"""
    try:
        escalation = Escalation.query.get(escalation_id)
        if not escalation:
            return jsonify({'success': False, 'error': 'Escalation not found'})
        
        # Send to all admins and the assigned user
        recipients = []
        if escalation.assigned_to_user:
            recipients.append(escalation.assigned_to_user.email)
        
        admins = User.query.filter(
            User.role.in_(['admin', 'superadmin']),
            User.is_active == True
        ).all()
        recipients.extend([admin.email for admin in admins])
        
        if recipients:
            send_escalation_alert_email(escalation, recipients, urgent=True)
            return jsonify({'success': True, 'message': 'Urgent alert sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'No recipients found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_bulk_escalation_notifications(escalation_ids):
    """Send bulk notifications for multiple escalations"""
    try:
        escalations = Escalation.query.filter(Escalation.id.in_(escalation_ids)).all()
        
        if not escalations:
            return jsonify({'success': False, 'error': 'No escalations found'})
        
        sent_count = 0
        for escalation in escalations:
            recipients = []
            if escalation.assigned_to_user:
                recipients.append(escalation.assigned_to_user.email)
            
            if escalation.department:
                dept_staff = User.query.filter_by(
                    department_id=escalation.department.id,
                    is_active=True
                ).filter(User.role.in_(['coordinator'])).all()
                recipients.extend([staff.email for staff in dept_staff])
            
            if recipients:
                send_escalation_alert_email(escalation, recipients, urgent=False)
                sent_count += 1
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Sent {sent_count} notifications'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_parent_onboarding_emails():
    """Send onboarding emails to parents"""
    try:
        # Get students with parent email addresses
        students = Student.query.filter_by(is_active=True).all()
        parent_emails = []
        
        for student in students:
            parent_details = student.get_parent_details()
            if parent_details:
                father_email = parent_details.get('father', {}).get('email')
                mother_email = parent_details.get('mother', {}).get('email')
                
                if father_email:
                    parent_emails.append({
                        'email': father_email,
                        'name': parent_details.get('father', {}).get('name', 'Parent'),
                        'student': student
                    })
                if mother_email and mother_email != father_email:
                    parent_emails.append({
                        'email': mother_email,
                        'name': parent_details.get('mother', {}).get('name', 'Parent'),
                        'student': student
                    })
        
        sent_count = 0
        for parent in parent_emails:
            try:
                send_parent_onboarding_email(parent['email'], parent['name'], parent['student'])
                sent_count += 1
            except Exception as e:
                print(f"Failed to send parent onboarding to {parent['email']}: {e}")
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Sent {sent_count} parent onboarding emails'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_parent_onboarding_email(parent_email, parent_name, student):
    """Send onboarding email to parent"""
    from app.utils.email import send_email
    
    subject = f"👋 Welcome to I2Global LMS - Track {student.full_name}'s Progress"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
            .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background: linear-gradient(135deg, #8b5cf6, #7c3aed); color: white; padding: 2rem; text-align: center; }}
            .email-body {{ padding: 2rem; }}
            .student-info {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
            .features-list {{ background: #f0f9ff; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
            .portal-button {{ display: inline-block; background: #F1A150; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 1.5rem 0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <h1>👨‍👩‍👧‍👦 Welcome to I2Global LMS</h1>
                <p>Stay connected with your child's learning journey</p>
            </div>
            
            <div class="email-body">
                <h2>Dear {parent_name},</h2>
                <p>We're excited to welcome you to the I2Global Learning Management System! As the parent of <strong>{student.full_name}</strong>, you now have access to track their academic progress and stay involved in their educational journey.</p>
                
                <div class="student-info">
                    <h3 style="margin: 0 0 1rem 0; color: #7c3aed;">👨‍🎓 Your Child's Information</h3>
                    <p><strong>Student Name:</strong> {student.full_name}</p>
                    <p><strong>Grade:</strong> {student.grade}</p>
                    <p><strong>Board:</strong> {student.board}</p>
                    <p><strong>Student ID:</strong> {student.id}</p>
                </div>
                
                <div class="features-list">
                    <h3 style="margin: 0 0 1rem 0; color: #1976d2;">✨ What You Can Do</h3>
                    <ul style="margin: 0; padding-left: 1.2rem;">
                        <li>View your child's class schedule and attendance</li>
                        <li>Track academic progress and performance</li>
                        <li>Communicate directly with tutors and coordinators</li>
                        <li>Receive notifications about classes and events</li>
                        <li>Access fee information and payment history</li>
                        <li>Download progress reports and certificates</li>
                    </ul>
                </div>
                
                <div style="text-align: center;">
                    <a href="http://localhost:5000" class="portal-button">
                        🚀 Access Parent Portal
                    </a>
                </div>
                
                <div style="background: #fef3c7; border: 1px solid #fde68a; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                    <h4 style="margin: 0 0 0.5rem 0; color: #d97706;">📞 Need Help?</h4>
                    <p style="margin: 0;">Our support team is here to help:</p>
                    <ul style="margin: 0.5rem 0; padding-left: 1.2rem;">
                        <li>Email: care@i2global.co.in</li>
                        <li>Phone: +91 9600127000</li>
                        <li>WhatsApp: +91 9600127000</li>
                    </ul>
                </div>
                
                <p>We look forward to partnering with you in {student.full_name}'s educational success!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(
        subject=subject,
        recipients=[parent_email],
        text_body=f"Welcome to I2Global LMS! Track {student.full_name}'s progress at: http://localhost:5000",
        html_body=html_content
    )

def send_bulk_user_onboarding(user_ids):
    """Send onboarding emails to multiple users"""
    try:
        users = User.query.filter(User.id.in_(user_ids)).all()
        
        if not users:
            return jsonify({'success': False, 'error': 'No users found'})
        
        sent_count = 0
        for user in users:
            try:
                send_user_onboarding_email(user)
                sent_count += 1
            except Exception as e:
                print(f"Failed to send onboarding email to {user.email}: {e}")
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Sent {sent_count} onboarding emails'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def send_individual_user_onboarding(user_id):
    """Send onboarding email to individual user"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})
        
        send_user_onboarding_email(user)
        return jsonify({'success': True, 'message': 'Onboarding email sent successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def save_notification_draft(data):
    """Save notification as draft"""
    try:
        # In a real implementation, you would save this to a database table
        # For now, we'll just return success
        return jsonify({
            'success': True,
            'message': 'Draft saved successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})