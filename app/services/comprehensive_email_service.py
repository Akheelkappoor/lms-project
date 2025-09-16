"""
Comprehensive Email Service for LMS
Handles ALL email notifications across the system
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import render_template, current_app
from flask_mail import Message
from app import mail, db
from app.models.user import User
from app.models.student import Student
from app.models.tutor import Tutor
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.department import Department
from app.models.escalation import Escalation
from app.services.email_error_handler import email_error_handler
from sqlalchemy import or_
import json

class EmailPriority:
    """Email priority levels"""
    IMMEDIATE = "immediate"     # < 5 minutes
    HIGH = "high"              # < 1 hour  
    MEDIUM = "medium"          # < 4 hours
    LOW = "low"                # < 24 hours
    SCHEDULED = "scheduled"    # At specific time

class EmailType:
    """Email type categories"""
    AUTHENTICATION = "authentication"
    ONBOARDING = "onboarding"
    ACADEMIC = "academic"
    FINANCIAL = "financial"
    ADMINISTRATIVE = "administrative"
    ALERT = "alert"
    REMINDER = "reminder"
    REPORT = "report"
    SYSTEM = "system"

class ComprehensiveEmailService:
    """Centralized email service for all LMS notifications"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    # ============ CORE EMAIL INFRASTRUCTURE ============
    
    @email_error_handler.handle_email_errors
    def send_email(self, 
                  recipients: List[str], 
                  subject: str, 
                  template: str, 
                  context: Dict[str, Any],
                  priority: str = EmailPriority.MEDIUM,
                  email_type: str = EmailType.ADMINISTRATIVE,
                  cc: List[str] = None,
                  bcc: List[str] = None,
                  attachments: List[Dict] = None) -> bool:
        """
        Core email sending function with comprehensive features and error handling
        """
        # Validate and clean recipients
        recipients = email_error_handler.validate_email_recipients(recipients)
        cc = email_error_handler.validate_email_recipients(cc or []) if cc else []
        bcc = email_error_handler.validate_email_recipients(bcc or []) if bcc else []
        
        # Validate and sanitize context
        context = email_error_handler.validate_email_context(context)
        
        # Create message
        msg = Message(
            subject=subject,
            recipients=recipients,
            cc=cc,
            bcc=bcc
        )
        
        # Render HTML template with error handling
        try:
            msg.html = render_template(f'email/{template}', **context)
        except Exception as template_error:
            self.logger.error(f"Template rendering failed for {template}: {str(template_error)}")
            # Use fallback template
            msg.html = self._generate_fallback_email(subject, context, template_error)
        
        # Add attachments if any
        if attachments:
            for attachment in attachments:
                try:
                    msg.attach(
                        filename=attachment.get('filename'),
                        content_type=attachment.get('content_type'),
                        data=attachment.get('data')
                    )
                except Exception as attachment_error:
                    self.logger.warning(f"Failed to add attachment: {str(attachment_error)}")
        
        # Log email attempt
        self._log_email(recipients, subject, priority, email_type)
        
        # Send email
        mail.send(msg)
        
        self.logger.info(f"Email sent successfully to {recipients}")
        return True
    
    def _generate_fallback_email(self, subject: str, context: Dict[str, Any], error: Exception) -> str:
        """Generate fallback email when template rendering fails"""
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .error-notice {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .content {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <h2>{subject}</h2>
            <div class="error-notice">
                <strong>Notice:</strong> This email was generated using a fallback template due to a system issue.
            </div>
            <div class="content">
                <p>Dear User,</p>
                <p>You have received this notification from the Learning Management System.</p>
                <p><strong>Subject:</strong> {subject}</p>
                <p>We apologize for any inconvenience caused by the formatting of this email. 
                   Our technical team has been notified and will resolve the issue shortly.</p>
                <p>If you need immediate assistance, please contact our support team.</p>
                <p>Best regards,<br>LMS Team</p>
            </div>
        </body>
        </html>
        """
    
    def _log_email(self, recipients: List[str], subject: str, priority: str, email_type: str):
        """Log email for tracking and analytics"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'recipients': recipients,
            'subject': subject,
            'priority': priority,
            'type': email_type
        }
        self.logger.info(f"Email Log: {json.dumps(log_data)}")
    
    def get_user_emails(self, user_ids: List[int], include_parents: bool = False) -> List[str]:
        """Get email addresses for users, optionally including parent emails for students"""
        emails = []
        
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user and user.email:
                emails.append(user.email)
                
                # Add parent emails for students
                if include_parents and user.role == 'student':
                    student = Student.query.filter_by(user_id=user_id).first()
                    if student:
                        parent_details = student.get_parent_details()
                        if parent_details:
                            father_email = parent_details.get('father', {}).get('email')
                            mother_email = parent_details.get('mother', {}).get('email')
                            if father_email:
                                emails.append(father_email)
                            if mother_email:
                                emails.append(mother_email)
        
        return list(set(emails))  # Remove duplicates
    
    def get_department_coordinators(self, department_id: int) -> List[str]:
        """Get coordinator emails for a department"""
        coordinators = User.query.filter_by(
            department_id=department_id,
            role='coordinator',
            is_active=True
        ).all()
        return [coord.email for coord in coordinators if coord.email]
    
    def get_admin_emails(self, role: str = None) -> List[str]:
        """Get admin/superadmin email addresses"""
        if role:
            admins = User.query.filter_by(role=role, is_active=True).all()
        else:
            admins = User.query.filter(
                User.role.in_(['admin', 'superadmin']),
                User.is_active == True
            ).all()
        return [admin.email for admin in admins if admin.email]
    
    # ============ STUDENT EMAIL FUNCTIONS ============
    
    def send_student_registration_confirmation(self, student_id: int):
        """Send registration confirmation to student and parents"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        # Get recipients
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        # Add coordinator
        coord_emails = self.get_department_coordinators(student.department_id)
        
        context = {
            'student': student,
            'department': student.department,
            'parent_details': parent_details,
            'subjects': student.get_subjects_enrolled(),
            'fee_structure': student.get_fee_structure()
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            subject=f"Welcome to {student.department.name if student.department else 'LMS'} - Registration Confirmed",
            template='student/registration_confirmation.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ONBOARDING
        )
    
    def send_profile_update_confirmation(self, student_id: int, changes: Dict[str, Any]):
        """Send profile update confirmation"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        context = {
            'student': student,
            'changes': changes,
            'updated_at': datetime.now()
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Profile Updated - {student.full_name}",
            template='student/profile_update_confirmation.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    def send_class_assignment_notification(self, student_id: int, class_id: int):
        """Send class assignment notification to student"""
        student = Student.query.get(student_id)
        class_obj = Class.query.get(class_id)
        
        if not student or not class_obj:
            return False
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        context = {
            'student': student,
            'class': class_obj,
            'tutor': class_obj.tutor,
            'tutor_user': class_obj.tutor.user if class_obj.tutor else None
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"New Class Assigned - {class_obj.subject}",
            template='student/class_assignment.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ACADEMIC
        )
    
    def send_attendance_alert(self, student_id: int):
        """Send attendance alert when below 70%"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        attendance_percentage = student.get_attendance_percentage()
        if attendance_percentage >= 70:
            return False  # No alert needed
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        # Add coordinator and relationship manager
        coord_emails = self.get_department_coordinators(student.department_id)
        
        context = {
            'student': student,
            'attendance_percentage': attendance_percentage,
            'total_classes': student.total_classes,
            'attended_classes': student.attended_classes,
            'improvement_plan': self._generate_attendance_improvement_plan(student)
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            subject=f"Attendance Alert - {student.full_name} ({attendance_percentage:.1f}%)",
            template='student/attendance_alert.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    def send_fee_payment_confirmation(self, student_id: int, payment_record: Dict[str, Any]):
        """Send fee payment confirmation"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        # Add finance team
        finance_emails = self.get_admin_emails()
        
        context = {
            'student': student,
            'payment': payment_record,
            'fee_structure': student.get_fee_structure(),
            'balance_amount': student.get_balance_amount()
        }
        
        return self.send_email(
            recipients=recipients,
            bcc=finance_emails,
            subject=f"Payment Received - ₹{payment_record['amount']} - {student.full_name}",
            template='student/payment_confirmation.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.FINANCIAL
        )
    
    def send_payment_reminder(self, student_id: int):
        """Send payment reminder"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        fee_structure = student.get_fee_structure()
        balance_amount = student.get_balance_amount()
        
        if balance_amount <= 0:
            return False  # No payment due
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        context = {
            'student': student,
            'balance_amount': balance_amount,
            'fee_structure': fee_structure,
            'due_date': self._calculate_next_due_date(student),
            'payment_methods': self._get_payment_methods()
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Fee Payment Reminder - ₹{balance_amount} Due",
            template='student/payment_reminder.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.FINANCIAL
        )
    
    def send_class_reschedule_confirmation(self, student_id: int, class_id: int, reschedule_details: Dict[str, Any]):
        """Send class reschedule confirmation to student"""
        student = Student.query.get(student_id)
        class_obj = Class.query.get(class_id)
        
        if not student or not class_obj:
            return False
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        context = {
            'student': student,
            'class': class_obj,
            'reschedule_details': reschedule_details,
            'new_schedule': reschedule_details.get('new_schedule')
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Class Rescheduled - {class_obj.subject}",
            template='student/class_reschedule_confirmation.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ACADEMIC
        )
    
    def send_feedback_acknowledgment(self, student_id: int, feedback_data: Dict[str, Any]):
        """Send feedback acknowledgment"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        recipients = [student.email] if student.email else []
        
        context = {
            'student': student,
            'feedback': feedback_data,
            'response_time': "within 48 hours"
        }
        
        return self.send_email(
            recipients=recipients,
            subject="Thank you for your feedback",
            template='student/feedback_acknowledgment.html',
            context=context,
            priority=EmailPriority.LOW,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    def send_course_completion_certificate(self, student_id: int):
        """Send course completion certificate"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        context = {
            'student': student,
            'completion_date': datetime.now(),
            'course_duration': student.course_duration_months,
            'attendance_percentage': student.get_attendance_percentage(),
            'subjects_completed': student.get_subjects_enrolled()
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Course Completion Certificate - {student.full_name}",
            template='student/course_completion.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.ACADEMIC
        )
    
    def send_enrollment_status_update(self, student_id: int, old_status: str, new_status: str, reason: str = ""):
        """Send enrollment status change notification"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        recipients = [student.email] if student.email else []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                recipients.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                recipients.append(parent_details['mother']['email'])
        
        # Add coordinator and tutors
        coord_emails = self.get_department_coordinators(student.department_id)
        tutor_emails = self._get_student_tutor_emails(student_id)
        
        context = {
            'student': student,
            'old_status': old_status,
            'new_status': new_status,
            'reason': reason,
            'effective_date': datetime.now(),
            'next_steps': self._get_status_change_next_steps(new_status)
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails + tutor_emails,
            subject=f"Enrollment Status Updated - {student.full_name}",
            template='student/status_update.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    # ============ HELPER METHODS ============
    
    def _generate_attendance_improvement_plan(self, student: Student) -> Dict[str, Any]:
        """Generate attendance improvement plan"""
        return {
            'target_percentage': 85,
            'classes_needed': max(0, int((student.total_classes * 0.85) - student.attended_classes)),
            'recommendations': [
                "Attend all upcoming classes",
                "Communicate with tutor about challenges",
                "Set regular study schedule",
                "Contact coordinator for additional support"
            ]
        }
    
    def _calculate_next_due_date(self, student: Student) -> datetime:
        """Calculate next payment due date"""
        fee_structure = student.get_fee_structure()
        payment_schedule = fee_structure.get('payment_schedule', 'monthly')
        
        if payment_schedule == 'monthly':
            return datetime.now() + timedelta(days=30)
        elif payment_schedule == 'quarterly':
            return datetime.now() + timedelta(days=90)
        else:
            return datetime.now() + timedelta(days=30)
    
    def _get_payment_methods(self) -> List[str]:
        """Get available payment methods"""
        return [
            "Online Payment Portal",
            "Bank Transfer",
            "UPI Payment",
            "Credit/Debit Card",
            "Cash Payment at Office"
        ]
    
    def _get_student_tutor_emails(self, student_id: int) -> List[str]:
        """Get email addresses of tutors teaching this student"""
        classes = Class.query.filter(
            or_(
                Class.primary_student_id == student_id,
                Class.students.like(f'%{student_id}%')
            )
        ).all()
        
        tutor_emails = []
        for class_obj in classes:
            if class_obj.tutor and class_obj.tutor.user and class_obj.tutor.user.email:
                tutor_emails.append(class_obj.tutor.user.email)
        
        return list(set(tutor_emails))
    
    def _get_status_change_next_steps(self, new_status: str) -> List[str]:
        """Get next steps based on new enrollment status"""
        steps_map = {
            'active': [
                "Continue attending regular classes",
                "Complete all assignments on time",
                "Maintain good attendance"
            ],
            'paused': [
                "Contact coordinator to resume classes",
                "Resolve any pending issues",
                "Update availability when ready"
            ],
            'completed': [
                "Collect completion certificate",
                "Provide course feedback",
                "Consider advanced courses"
            ],
            'dropped': [
                "Complete exit formalities",
                "Settle any pending fees",
                "Contact if you wish to re-enroll"
            ]
        }
        return steps_map.get(new_status, ["Contact coordinator for guidance"])

# Global instance
email_service = ComprehensiveEmailService()