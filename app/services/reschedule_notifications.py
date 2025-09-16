# app/services/reschedule_notifications.py

from flask import current_app, render_template_string
from app.utils.email import send_email
from datetime import datetime

class RescheduleNotificationService:
    """Service for sending reschedule-related notifications"""
    
    @staticmethod
    def send_reschedule_request_notification(reschedule_request):
        """Send notification when a new reschedule request is created"""
        try:
            # Notify coordinators/admins
            from app.models.user import User
            
            # Get coordinators and admins for the department
            department_id = reschedule_request.class_item.tutor.user.department_id
            recipients = User.query.filter(
                User.role.in_(['admin', 'coordinator', 'superadmin']),
                User.department_id == department_id,
                User.is_active == True
            ).all()
            
            subject = f"New Reschedule Request - {reschedule_request.class_item.subject}"
            
            for recipient in recipients:
                body = render_template_string("""
                <h3>New Class Reschedule Request</h3>
                
                <p>Dear {{ recipient.full_name }},</p>
                
                <p>A new reschedule request has been submitted that requires your review:</p>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <h4>Request Details</h4>
                    <p><strong>Class:</strong> {{ request.class_item.subject }}</p>
                    <p><strong>Tutor:</strong> {{ request.class_item.tutor.user.full_name }}</p>
                    <p><strong>Current Schedule:</strong> {{ request.original_date.strftime('%A, %d %B %Y') }} at {{ request.original_time.strftime('%I:%M %p') }}</p>
                    <p><strong>Requested Schedule:</strong> {{ request.requested_date.strftime('%A, %d %B %Y') }} at {{ request.requested_time.strftime('%I:%M %p') }}</p>
                    <p><strong>Reason:</strong> {{ request.reason }}</p>
                    {% if request.has_conflicts %}
                    <p style="color: #dc3545;"><strong>⚠️ Conflicts Detected:</strong> This request has scheduling conflicts that need attention.</p>
                    {% endif %}
                </div>
                
                <p>Please review this request at your earliest convenience:</p>
                <p><a href="{{ url }}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Review Request</a></p>
                
                <p>Best regards,<br>{{ app_name }} System</p>
                """, 
                recipient=recipient, 
                request=reschedule_request,
                url=f"{current_app.config.get('BASE_URL', '')}/reschedule/admin/reschedule-request/{reschedule_request.id}",
                app_name=current_app.config.get('APP_NAME', 'LMS')
                )
                
                send_email(
                    recipient.email,
                    subject,
                    body,
                    html=True
                )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending reschedule request notification: {str(e)}")
            return False
    
    @staticmethod
    def send_reschedule_approved_notification(reschedule_request):
        """Send notification when reschedule request is approved"""
        try:
            # Notify tutor
            tutor_email = reschedule_request.class_item.tutor.user.email
            tutor_name = reschedule_request.class_item.tutor.user.full_name
            
            subject = f"Reschedule Request Approved - {reschedule_request.class_item.subject}"
            
            tutor_body = render_template_string("""
            <h3>Reschedule Request Approved</h3>
            
            <p>Dear {{ tutor_name }},</p>
            
            <p>Good news! Your reschedule request has been approved.</p>
            
            <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #28a745;">
                <h4>Updated Class Schedule</h4>
                <p><strong>Class:</strong> {{ request.class_item.subject }}</p>
                <p><strong>New Date:</strong> {{ request.requested_date.strftime('%A, %d %B %Y') }}</p>
                <p><strong>New Time:</strong> {{ request.requested_time.strftime('%I:%M %p') }}</p>
                <p><strong>Duration:</strong> {{ request.class_item.duration }} minutes</p>
                {% if request.review_notes %}
                <p><strong>Admin Notes:</strong> {{ request.review_notes }}</p>
                {% endif %}
            </div>
            
            <p>Please make sure to:</p>
            <ul>
                <li>Update your personal calendar</li>
                <li>Prepare any materials needed for the class</li>
                <li>Inform students if you have direct contact with them</li>
            </ul>
            
            <p>Students will be automatically notified of this change.</p>
            
            <p><a href="{{ url }}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Class Details</a></p>
            
            <p>Best regards,<br>{{ app_name }} System</p>
            """, 
            tutor_name=tutor_name,
            request=reschedule_request,
            url=f"{current_app.config.get('BASE_URL', '')}/admin/class-details/{reschedule_request.class_id}",
            app_name=current_app.config.get('APP_NAME', 'LMS')
            )
            
            send_email(tutor_email, subject, tutor_body, html=True)
            
            # Notify students
            students = reschedule_request.class_item.get_student_objects()
            for student in students:
                if hasattr(student, 'email') and student.email:
                    student_body = render_template_string("""
                    <h3>Class Schedule Update</h3>
                    
                    <p>Dear {{ student.full_name }},</p>
                    
                    <p>We're writing to inform you that your upcoming class has been rescheduled.</p>
                    
                    <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ffc107;">
                        <h4>Updated Class Information</h4>
                        <p><strong>Subject:</strong> {{ request.class_item.subject }}</p>
                        <p><strong>Tutor:</strong> {{ request.class_item.tutor.user.full_name }}</p>
                        <p><strong>New Date:</strong> {{ request.requested_date.strftime('%A, %d %B %Y') }}</p>
                        <p><strong>New Time:</strong> {{ request.requested_time.strftime('%I:%M %p') }}</p>
                        <p><strong>Duration:</strong> {{ request.class_item.duration }} minutes</p>
                    </div>
                    
                    <p>Please update your calendar and make sure you're available at the new time.</p>
                    
                    <p>If you have any questions about this change, please contact your coordinator.</p>
                    
                    <p>Best regards,<br>{{ app_name }} System</p>
                    """, 
                    student=student,
                    request=reschedule_request,
                    app_name=current_app.config.get('APP_NAME', 'LMS')
                    )
                    
                    send_email(student.email, subject, student_body, html=True)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending approval notification: {str(e)}")
            return False
    
    @staticmethod
    def send_reschedule_rejected_notification(reschedule_request):
        """Send notification when reschedule request is rejected"""
        try:
            tutor_email = reschedule_request.class_item.tutor.user.email
            tutor_name = reschedule_request.class_item.tutor.user.full_name
            
            subject = f"Reschedule Request Update - {reschedule_request.class_item.subject}"
            
            body = render_template_string("""
            <h3>Reschedule Request Update</h3>
            
            <p>Dear {{ tutor_name }},</p>
            
            <p>We've reviewed your reschedule request for the following class:</p>
            
            <div style="background: #f8d7da; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #dc3545;">
                <h4>Request Status: Not Approved</h4>
                <p><strong>Class:</strong> {{ request.class_item.subject }}</p>
                <p><strong>Requested Date:</strong> {{ request.requested_date.strftime('%A, %d %B %Y') }}</p>
                <p><strong>Requested Time:</strong> {{ request.requested_time.strftime('%I:%M %p') }}</p>
                {% if request.review_notes %}
                <p><strong>Reason:</strong> {{ request.review_notes }}</p>
                {% endif %}
            </div>
            
            <p>Your class remains scheduled for its original time:</p>
            <div style="background: #e2e3e5; padding: 10px; border-radius: 5px;">
                <p><strong>Original Date:</strong> {{ request.original_date.strftime('%A, %d %B %Y') }}</p>
                <p><strong>Original Time:</strong> {{ request.original_time.strftime('%I:%M %p') }}</p>
            </div>
            
            <p>If you still need to reschedule this class, please:</p>
            <ul>
                <li>Contact your coordinator directly</li>
                <li>Submit a new request with different timing</li>
                <li>Provide additional details if needed</li>
            </ul>
            
            <p><a href="{{ url }}" style="background: #6c757d; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View My Classes</a></p>
            
            <p>Best regards,<br>{{ app_name }} System</p>
            """, 
            tutor_name=tutor_name,
            request=reschedule_request,
            url=f"{current_app.config.get('BASE_URL', '')}/tutor/my-classes",
            app_name=current_app.config.get('APP_NAME', 'LMS')
            )
            
            send_email(tutor_email, subject, body, html=True)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending rejection notification: {str(e)}")
            return False
    
    @staticmethod
    def send_conflict_alert_notification(reschedule_request):
        """Send alert when reschedule request has conflicts"""
        try:
            # Notify coordinators/admins about high-priority conflict
            from app.models.user import User
            
            department_id = reschedule_request.class_item.tutor.user.department_id
            recipients = User.query.filter(
                User.role.in_(['admin', 'coordinator', 'superadmin']),
                User.department_id == department_id,
                User.is_active == True
            ).all()
            
            subject = f"⚠️ Reschedule Conflict Alert - {reschedule_request.class_item.subject}"
            
            for recipient in recipients:
                body = render_template_string("""
                <h3 style="color: #dc3545;">⚠️ Reschedule Request with Conflicts</h3>
                
                <p>Dear {{ recipient.full_name }},</p>
                
                <p>A reschedule request has been submitted that has <strong>scheduling conflicts</strong> requiring immediate attention:</p>
                
                <div style="background: #f8d7da; padding: 15px; border-radius: 5px; margin: 15px 0; border: 1px solid #f5c6cb;">
                    <h4>Conflict Details</h4>
                    <p><strong>Class:</strong> {{ request.class_item.subject }}</p>
                    <p><strong>Tutor:</strong> {{ request.class_item.tutor.user.full_name }}</p>
                    <p><strong>Requested Time:</strong> {{ request.requested_date.strftime('%A, %d %B %Y') }} at {{ request.requested_time.strftime('%I:%M %p') }}</p>
                    
                    <h5 style="color: #721c24; margin-top: 15px;">Detected Conflicts:</h5>
                    <ul style="color: #721c24;">
                    {% for conflict in conflicts %}
                        <li>{{ conflict.message }}</li>
                    {% endfor %}
                    </ul>
                </div>
                
                <p>This request requires manual review and resolution. You may need to:</p>
                <ul>
                    <li>Coordinate with other tutors or students</li>
                    <li>Suggest alternative times</li>
                    <li>Override conflicts if necessary</li>
                </ul>
                
                <p><a href="{{ url }}" style="background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Review Conflicts</a></p>
                
                <p>Best regards,<br>{{ app_name }} System</p>
                """, 
                recipient=recipient,
                request=reschedule_request,
                conflicts=reschedule_request.get_conflicts(),
                url=f"{current_app.config.get('BASE_URL', '')}/reschedule/admin/reschedule-request/{reschedule_request.id}",
                app_name=current_app.config.get('APP_NAME', 'LMS')
                )
                
                send_email(
                    recipient.email,
                    subject,
                    body,
                    html=True
                )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending conflict alert: {str(e)}")
            return False
