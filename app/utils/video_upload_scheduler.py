# CREATE: app/utils/video_upload_scheduler.py

from datetime import datetime, timedelta
from app import db
from app.models.user import User
from app.models.class_model import Class
from app.utils.email import send_email
import json

def schedule_video_upload_reminders(class_id, tutor_id):
    """Schedule reminder emails for video upload"""
    try:
        # This would integrate with Celery for background jobs
        # For now, we'll store the reminder schedule in a simple way
        
        class_obj = Class.query.get(class_id)
        if not class_obj or not class_obj.actual_end_time:
            return False
        
        # Calculate reminder times
        completion_time = class_obj.actual_end_time
        one_hour_reminder = completion_time + timedelta(hours=1)
        final_warning = completion_time + timedelta(hours=1, minutes=45)
        deadline = completion_time + timedelta(hours=2)
        
        # Store reminder schedule (in a real implementation, this would be in Celery/Redis)
        reminder_data = {
            'class_id': class_id,
            'tutor_id': tutor_id,
            'completion_time': completion_time.isoformat(),
            'one_hour_reminder': one_hour_reminder.isoformat(),
            'final_warning': final_warning.isoformat(),
            'deadline': deadline.isoformat(),
            'status': 'scheduled'
        }
        
        # In production, schedule these as Celery tasks:
        # send_one_hour_reminder.apply_async(args=[class_id], eta=one_hour_reminder)
        # send_final_warning.apply_async(args=[class_id], eta=final_warning)
        # mark_class_incomplete.apply_async(args=[class_id], eta=deadline)
        
        return True
        
    except Exception as e:
        print(f"Error scheduling reminders: {e}")
        return False

def cancel_video_upload_reminders(class_id):
    """Cancel pending upload reminders when video is uploaded"""
    try:
        # In production, this would revoke Celery tasks
        # revoke_reminder_tasks(class_id)
        
        return True
    except Exception as e:
        print(f"Error canceling reminders: {e}")
        return False

def send_one_hour_reminder(class_id):
    """Send 1-hour reminder email"""
    try:
        class_obj = Class.query.get(class_id)
        if not class_obj or class_obj.video_link:
            return  # Already uploaded
        
        tutor = class_obj.tutor
        if not tutor or not tutor.user:
            return
        
        deadline = class_obj.actual_end_time + timedelta(hours=2)
        
        subject = f"⏰ Video Upload Reminder - {class_obj.subject} Class"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                <h2 style="color: #fd7e14;">
                    <i>⏰</i> Video Upload Reminder
                </h2>
                
                <p>Dear {tutor.user.full_name},</p>
                
                <p>This is a reminder that you need to upload the video recording for your recent class:</p>
                
                <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                    <strong>Class Details:</strong><br>
                    📚 Subject: {class_obj.subject}<br>
                    📅 Date: {class_obj.scheduled_date.strftime('%d %b %Y')}<br>
                    ⏰ Time: {class_obj.scheduled_time.strftime('%I:%M %p')}<br>
                    ⏳ Deadline: {deadline.strftime('%I:%M %p')} (1 hour remaining)
                </div>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 6px; border-left: 4px solid #ffc107;">
                    <strong>Important:</strong> Video upload is mandatory for class completion and payment processing.
                </div>
                
                <p style="text-align: center; margin: 20px 0;">
                    <a href="{request.url_root}tutor/class/{class_id}/upload-video" 
                       style="background: #fd7e14; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        Upload Video Now
                    </a>
                </p>
                
                <p>If you're experiencing technical difficulties, please contact support immediately.</p>
                
                <hr style="margin: 20px 0;">
                <small style="color: #6c757d;">
                    I2Global LMS - Automated Reminder System
                </small>
            </div>
        </div>
        """
        
        send_email(
            subject=subject,
            recipient=tutor.user.email,
            html_body=html_body
        )
        
    except Exception as e:
        print(f"Error sending 1-hour reminder: {e}")

def send_final_warning(class_id):
    """Send final warning email (15 minutes before deadline)"""
    try:
        class_obj = Class.query.get(class_id)
        if not class_obj or class_obj.video_link:
            return  # Already uploaded
        
        tutor = class_obj.tutor
        if not tutor or not tutor.user:
            return
        
        deadline = class_obj.actual_end_time + timedelta(hours=2)
        
        subject = f"🚨 URGENT: Final Video Upload Warning - {class_obj.subject}"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #f8d7da; padding: 20px; border-radius: 8px; border: 2px solid #dc3545;">
                <h2 style="color: #721c24;">
                    <i>🚨</i> URGENT: Final Video Upload Warning
                </h2>
                
                <p>Dear {tutor.user.full_name},</p>
                
                <div style="background: #721c24; color: white; padding: 15px; border-radius: 6px; text-align: center; margin: 15px 0;">
                    <strong style="font-size: 18px;">⏰ 15 MINUTES REMAINING ⏰</strong>
                </div>
                
                <p><strong>Your video upload deadline is approaching!</strong></p>
                
                <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                    <strong>Class Details:</strong><br>
                    📚 Subject: {class_obj.subject}<br>
                    📅 Date: {class_obj.scheduled_date.strftime('%d %b %Y')}<br>
                    ⏰ Deadline: {deadline.strftime('%I:%M %p')} 
                </div>
                
                <div style="background: #dc3545; color: white; padding: 15px; border-radius: 6px;">
                    <strong>⚠️ WARNING:</strong> If you don't upload the video within 15 minutes:
                    <ul style="margin: 10px 0;">
                        <li>Your class will be marked as incomplete</li>
                        <li>Payment may be affected</li>
                        <li>You'll need admin approval for late uploads</li>
                    </ul>
                </div>
                
                <p style="text-align: center; margin: 20px 0;">
                    <a href="{request.url_root}tutor/class/{class_id}/upload-video" 
                       style="background: #dc3545; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; display: inline-block; font-size: 16px; font-weight: bold;">
                        🚨 UPLOAD NOW 🚨
                    </a>
                </p>
                
                <p>Contact support immediately if you need assistance: <strong>care@i2global.co.in</strong></p>
            </div>
        </div>
        """
        
        send_email(
            subject=subject,
            recipient=tutor.user.email,
            html_body=html_body
        )
        
    except Exception as e:
        print(f"Error sending final warning: {e}")

def mark_class_incomplete_for_no_video(class_id):
    """Mark class as incomplete if video not uploaded by deadline"""
    try:
        class_obj = Class.query.get(class_id)
        if not class_obj or class_obj.video_link:
            return  # Already uploaded
        
        # Mark class as incomplete
        class_obj.completion_status = 'incomplete_no_video'
        class_obj.status = 'incomplete'
        
        # Add admin note
        admin_note = f"Class marked incomplete due to missing video upload. Deadline: {(class_obj.actual_end_time + timedelta(hours=2)).strftime('%d %b %Y at %I:%M %p')}"
        class_obj.admin_notes = admin_note
        
        db.session.commit()
        
        # Notify tutor
        tutor = class_obj.tutor
        if tutor and tutor.user:
            subject = f"❌ Class Marked Incomplete - Video Upload Deadline Missed"
            
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #f8d7da; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #721c24;">Class Marked Incomplete</h2>
                    
                    <p>Dear {tutor.user.full_name},</p>
                    
                    <p>Unfortunately, your class has been marked as <strong>incomplete</strong> because the video was not uploaded within the required timeframe.</p>
                    
                    <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                        📚 Subject: {class_obj.subject}<br>
                        📅 Date: {class_obj.scheduled_date.strftime('%d %b %Y')}<br>
                        ⏰ Deadline was: {(class_obj.actual_end_time + timedelta(hours=2)).strftime('%I:%M %p')}
                    </div>
                    
                    <div style="background: #fff3cd; padding: 15px; border-radius: 6px;">
                        <strong>Next Steps:</strong>
                        <ul>
                            <li>Contact your coordinator immediately</li>
                            <li>Provide explanation for the delay</li>
                            <li>Upload video for admin review</li>
                            <li>Payment may be affected</li>
                        </ul>
                    </div>
                    
                    <p>Please reach out to support for assistance: <strong>care@i2global.co.in</strong></p>
                </div>
            </div>
            """
            
            send_email(
                subject=subject,
                recipient=tutor.user.email,
                html_body=html_body
            )
        
        return True
        
    except Exception as e:
        print(f"Error marking class incomplete: {e}")
        return False


# CREATE: app/utils/rating_calculator.py

from datetime import datetime, timedelta
from app import db
from app.models.tutor import Tutor
from app.models.class_model import Class
from app.models.attendance import Attendance
from sqlalchemy import func

def update_tutor_rating(tutor_id):
    """Calculate and update tutor rating based on performance metrics"""
    try:
        tutor = Tutor.query.get(tutor_id)
        if not tutor:
            return False
        
        # Get performance data from last 3 months
        three_months_ago = datetime.now() - timedelta(days=90)
        
        # Get completed classes
        completed_classes = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.status == 'completed',
            Class.scheduled_date >= three_months_ago.date()
        ).all()
        
        if len(completed_classes) < 5:  # Need at least 5 classes for rating
            return False
        
        # Calculate metrics
        metrics = calculate_performance_metrics(tutor_id, completed_classes)
        
        # Calculate rating using weighted formula
        rating = calculate_weighted_rating(metrics)
        
        # Update tutor rating
        old_rating = tutor.rating
        tutor.rating = round(rating, 1)
        
        # Log rating change
        print(f"Tutor {tutor_id} rating updated: {old_rating} -> {tutor.rating}")
        
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"Error updating tutor rating: {e}")
        return False

def calculate_performance_metrics(tutor_id, completed_classes):
    """Calculate detailed performance metrics"""
    metrics = {
        'completion_rate': 0.0,
        'video_compliance': 0.0,
        'punctuality_score': 0.0,
        'engagement_score': 0.0,
        'total_classes': len(completed_classes)
    }
    
    # 1. COMPLETION RATE (40% weight)
    all_classes = Class.query.filter(
        Class.tutor_id == tutor_id,
        Class.scheduled_date >= (datetime.now() - timedelta(days=90)).date()
    ).count()
    
    if all_classes > 0:
        metrics['completion_rate'] = len(completed_classes) / all_classes * 100
    
    # 2. VIDEO COMPLIANCE (30% weight)
    classes_with_video = sum(1 for cls in completed_classes if cls.video_link)
    if len(completed_classes) > 0:
        metrics['video_compliance'] = classes_with_video / len(completed_classes) * 100
    
    # 3. PUNCTUALITY SCORE (20% weight)
    punctuality_scores = []
    for cls in completed_classes:
        attendance = Attendance.query.filter_by(
            class_id=cls.id,
            tutor_id=tutor_id
        ).first()
        
        if attendance:
            if attendance.tutor_late_minutes == 0:
                punctuality_scores.append(5)  # Perfect
            elif attendance.tutor_late_minutes <= 2:
                punctuality_scores.append(4)  # Good
            elif attendance.tutor_late_minutes <= 5:
                punctuality_scores.append(3)  # Average
            elif attendance.tutor_late_minutes <= 10:
                punctuality_scores.append(2)  # Poor
            else:
                punctuality_scores.append(1)  # Very Poor
    
    if punctuality_scores:
        metrics['punctuality_score'] = sum(punctuality_scores) / len(punctuality_scores) * 20
    
    # 4. ENGAGEMENT SCORE (10% weight)
    engagement_scores = []
    for cls in completed_classes:
        attendance_records = Attendance.query.filter_by(class_id=cls.id).all()
        
        if attendance_records:
            class_engagement = []
            for attendance in attendance_records:
                if attendance.student_engagement == 'high':
                    class_engagement.append(5)
                elif attendance.student_engagement == 'medium':
                    class_engagement.append(3)
                elif attendance.student_engagement == 'low':
                    class_engagement.append(1)
            
            if class_engagement:
                avg_engagement = sum(class_engagement) / len(class_engagement)
                engagement_scores.append(avg_engagement)
    
    if engagement_scores:
        metrics['engagement_score'] = sum(engagement_scores) / len(engagement_scores) * 20
    
    return metrics

def calculate_weighted_rating(metrics):
    """Calculate final rating using weighted formula"""
    # Rating components (out of 5)
    completion_component = (metrics['completion_rate'] / 100) * 5 * 0.40
    video_component = (metrics['video_compliance'] / 100) * 5 * 0.30
    punctuality_component = (metrics['punctuality_score'] / 100) * 5 * 0.20
    engagement_component = (metrics['engagement_score'] / 100) * 5 * 0.10
    
    # Calculate final rating
    final_rating = (
        completion_component +
        video_component +
        punctuality_component +
        engagement_component
    )
    
    # Ensure rating is between 1 and 5
    return max(1.0, min(5.0, final_rating))

def get_rating_breakdown(tutor_id):
    """Get detailed breakdown of rating calculation"""
    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        return None
    
    three_months_ago = datetime.now() - timedelta(days=90)
    completed_classes = Class.query.filter(
        Class.tutor_id == tutor_id,
        Class.status == 'completed',
        Class.scheduled_date >= three_months_ago.date()
    ).all()
    
    if len(completed_classes) < 5:
        return {
            'insufficient_data': True,
            'classes_needed': 5 - len(completed_classes),
            'current_classes': len(completed_classes)
        }
    
    metrics = calculate_performance_metrics(tutor_id, completed_classes)
    
    return {
        'current_rating': tutor.rating,
        'metrics': metrics,
        'breakdown': {
            'completion_rate': {
                'score': metrics['completion_rate'],
                'weight': '40%',
                'contribution': (metrics['completion_rate'] / 100) * 5 * 0.40
            },
            'video_compliance': {
                'score': metrics['video_compliance'],
                'weight': '30%',
                'contribution': (metrics['video_compliance'] / 100) * 5 * 0.30
            },
            'punctuality': {
                'score': metrics['punctuality_score'],
                'weight': '20%',
                'contribution': (metrics['punctuality_score'] / 100) * 5 * 0.20
            },
            'engagement': {
                'score': metrics['engagement_score'],
                'weight': '10%',
                'contribution': (metrics['engagement_score'] / 100) * 5 * 0.10
            }
        },
        'classes_analyzed': len(completed_classes),
        'analysis_period': '3 months'
    }


# CREATE: app/utils/class_time_validator.py

from datetime import datetime, timedelta

def can_start_class(class_obj):
    """Check if class can be started based on time rules"""
    current_time = datetime.now()
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    # Must be today's class
    if class_obj.scheduled_date != current_time.date():
        return False, "Can only start today's classes"
    
    # Can start 5 minutes before scheduled time
    earliest_start = class_datetime - timedelta(minutes=5)
    
    if current_time < earliest_start:
        minutes_to_wait = int((earliest_start - current_time).total_seconds() / 60)
        return False, f"Please wait {minutes_to_wait} more minutes"
    
    # Can't start more than 30 minutes late without admin approval
    latest_start = class_datetime + timedelta(minutes=30)
    
    if current_time > latest_start:
        return False, "Class is too late to start. Contact admin for approval."
    
    return True, "Class can be started"

def get_meeting_link_availability(class_obj):
    """Check if meeting links should be available"""
    current_time = datetime.now()
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    # Links available from 10 minutes before class
    link_available_from = class_datetime - timedelta(minutes=10)
    
    # Links available until 2 hours after class ends
    class_end = class_datetime + timedelta(minutes=class_obj.duration)
    link_available_until = class_end + timedelta(hours=2)
    
    is_available = link_available_from <= current_time <= link_available_until
    
    if not is_available:
        if current_time < link_available_from:
            minutes_until = int((link_available_from - current_time).total_seconds() / 60)
            return False, f"Available in {minutes_until} minutes"
        else:
            return False, "Link no longer available"
    
    return True, "Link available"

def calculate_time_until_class(class_obj):
    """Calculate time until class starts"""
    current_time = datetime.now()
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    if current_time >= class_datetime:
        return 0, "Class time has arrived"
    
    diff_seconds = (class_datetime - current_time).total_seconds()
    diff_minutes = int(diff_seconds / 60)
    
    if diff_minutes > 60:
        hours = diff_minutes // 60
        remaining_minutes = diff_minutes % 60
        return diff_minutes, f"{hours}h {remaining_minutes}m"
    else:
        return diff_minutes, f"{diff_minutes} minutes"