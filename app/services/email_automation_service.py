"""
Email Automation Service - Automated sequences and workflow-based emails
Handles time-based email sequences and multi-step workflows
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.services.comprehensive_email_service import ComprehensiveEmailService, EmailPriority, EmailType
from app.models.user import User
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app import db
from sqlalchemy import and_, or_
import json

class EmailSequence:
    """Email sequence definition"""
    def __init__(self, name: str, trigger_event: str, emails: List[Dict[str, Any]]):
        self.name = name
        self.trigger_event = trigger_event
        self.emails = emails  # List of email definitions with timing and conditions

class EmailAutomationService(ComprehensiveEmailService):
    """Service for automated email sequences and workflows"""
    
    def __init__(self):
        super().__init__()
        self.sequences = self._initialize_sequences()
    
    def _initialize_sequences(self) -> Dict[str, EmailSequence]:
        """Initialize all email sequences"""
        return {
            'student_onboarding': self._create_student_onboarding_sequence(),
            'tutor_onboarding': self._create_tutor_onboarding_sequence(),
            'class_workflow': self._create_class_workflow_sequence(),
            'escalation_workflow': self._create_escalation_workflow_sequence(),
            'attendance_intervention': self._create_attendance_intervention_sequence(),
            'payment_reminder': self._create_payment_reminder_sequence(),
            'performance_monitoring': self._create_performance_monitoring_sequence()
        }
    
    # ============ SEQUENCE DEFINITIONS ============
    
    def _create_student_onboarding_sequence(self) -> EmailSequence:
        """Create student onboarding sequence (7 emails)"""
        emails = [
            {
                'name': 'registration_welcome',
                'delay_hours': 0,  # Immediate
                'template': 'sequences/student_onboarding_welcome.html',
                'subject': 'Welcome to LMS - Your Learning Journey Begins!',
                'condition': 'registration_complete'
            },
            {
                'name': 'profile_completion_reminder',
                'delay_hours': 24,
                'template': 'sequences/student_profile_reminder.html',
                'subject': 'Complete Your Profile - Get Better Tutor Matches',
                'condition': 'profile_incomplete'
            },
            {
                'name': 'first_class_assignment',
                'delay_hours': 48,
                'template': 'sequences/student_first_class.html',
                'subject': 'Your First Class is Scheduled!',
                'condition': 'tutor_assigned'
            },
            {
                'name': 'pre_class_preparation',
                'delay_hours': 2,  # 2 hours before first class
                'template': 'sequences/student_class_preparation.html',
                'subject': 'Prepare for Your First Class - Tips & Materials',
                'condition': 'first_class_today'
            },
            {
                'name': 'post_class_experience',
                'delay_hours': 2,  # 2 hours after first class
                'template': 'sequences/student_first_class_feedback.html',
                'subject': 'How was your first class? Share your experience',
                'condition': 'first_class_completed'
            },
            {
                'name': 'weekly_progress_update',
                'delay_hours': 168,  # Weekly (7 days)
                'template': 'sequences/student_weekly_progress.html',
                'subject': 'Your Weekly Progress Update',
                'condition': 'active_student',
                'recurring': True
            },
            {
                'name': 'monthly_performance_report',
                'delay_hours': 720,  # Monthly (30 days)
                'template': 'sequences/student_monthly_report.html',
                'subject': 'Your Monthly Performance Report',
                'condition': 'active_student',
                'recurring': True
            }
        ]
        return EmailSequence('student_onboarding', 'student_registered', emails)
    
    def _create_tutor_onboarding_sequence(self) -> EmailSequence:
        """Create tutor onboarding sequence (6 emails)"""
        emails = [
            {
                'name': 'application_confirmation',
                'delay_hours': 0,
                'template': 'sequences/tutor_application_confirmation.html',
                'subject': 'Application Received - Welcome to LMS Teaching Team',
                'condition': 'application_submitted'
            },
            {
                'name': 'document_verification_update',
                'delay_hours': 24,
                'template': 'sequences/tutor_document_status.html',
                'subject': 'Document Verification Status Update',
                'condition': 'documents_under_review'
            },
            {
                'name': 'approval_welcome',
                'delay_hours': 0,  # Immediate when approved
                'template': 'sequences/tutor_approval_welcome.html',
                'subject': 'Congratulations! You are now part of LMS',
                'condition': 'tutor_approved'
            },
            {
                'name': 'first_assignment',
                'delay_hours': 24,
                'template': 'sequences/tutor_first_assignment.html',
                'subject': 'Your First Teaching Assignment',
                'condition': 'first_class_assigned'
            },
            {
                'name': 'training_completion',
                'delay_hours': 168,  # 1 week
                'template': 'sequences/tutor_training_milestone.html',
                'subject': 'Training Milestone Achieved',
                'condition': 'training_completed'
            },
            {
                'name': 'monthly_performance_review',
                'delay_hours': 720,  # Monthly
                'template': 'sequences/tutor_monthly_review.html',
                'subject': 'Your Monthly Performance Review',
                'condition': 'active_tutor',
                'recurring': True
            }
        ]
        return EmailSequence('tutor_onboarding', 'tutor_registered', emails)
    
    def _create_class_workflow_sequence(self) -> EmailSequence:
        """Create class management workflow (5 emails)"""
        emails = [
            {
                'name': 'class_creation_notification',
                'delay_hours': 0,
                'template': 'sequences/class_creation.html',
                'subject': 'New Class Scheduled',
                'condition': 'class_created'
            },
            {
                'name': '24h_reminder',
                'delay_hours': -24,  # 24 hours before class
                'template': 'sequences/class_24h_reminder.html',
                'subject': 'Class Tomorrow - Prepare & Review',
                'condition': 'class_scheduled'
            },
            {
                'name': '2h_reminder',
                'delay_hours': -2,  # 2 hours before class
                'template': 'sequences/class_2h_reminder.html',
                'subject': 'Class in 2 Hours - Final Preparation',
                'condition': 'class_scheduled'
            },
            {
                'name': '30min_reminder',
                'delay_hours': -0.5,  # 30 minutes before class
                'template': 'sequences/class_30min_reminder.html',
                'subject': 'Class Starting Soon - Join Now',
                'condition': 'class_scheduled'
            },
            {
                'name': 'completion_confirmation',
                'delay_hours': 0.5,  # 30 minutes after class end
                'template': 'sequences/class_completion.html',
                'subject': 'Class Completed - Next Steps',
                'condition': 'class_completed'
            }
        ]
        return EmailSequence('class_workflow', 'class_scheduled', emails)
    
    def _create_escalation_workflow_sequence(self) -> EmailSequence:
        """Create escalation management workflow (4 emails)"""
        emails = [
            {
                'name': 'escalation_created',
                'delay_hours': 0,
                'template': 'sequences/escalation_created.html',
                'subject': 'New Escalation - Immediate Attention Required',
                'condition': 'escalation_created'
            },
            {
                'name': 'assignment_notification',
                'delay_hours': 1,
                'template': 'sequences/escalation_assigned.html',
                'subject': 'Escalation Assigned - Action Required',
                'condition': 'escalation_assigned'
            },
            {
                'name': 'progress_update',
                'delay_hours': 24,
                'template': 'sequences/escalation_progress.html',
                'subject': 'Escalation Progress Update Required',
                'condition': 'escalation_in_progress'
            },
            {
                'name': 'resolution_confirmation',
                'delay_hours': 0,
                'template': 'sequences/escalation_resolved.html',
                'subject': 'Escalation Resolved - Closure Confirmation',
                'condition': 'escalation_resolved'
            }
        ]
        return EmailSequence('escalation_workflow', 'escalation_created', emails)
    
    def _create_attendance_intervention_sequence(self) -> EmailSequence:
        """Create attendance intervention sequence (4 emails)"""
        emails = [
            {
                'name': 'first_warning',
                'delay_hours': 0,
                'template': 'sequences/attendance_first_warning.html',
                'subject': 'Attendance Alert - Improvement Needed',
                'condition': 'attendance_below_80'
            },
            {
                'name': 'second_warning',
                'delay_hours': 48,
                'template': 'sequences/attendance_second_warning.html',
                'subject': 'Second Attendance Warning - Action Required',
                'condition': 'attendance_below_70'
            },
            {
                'name': 'intervention_meeting',
                'delay_hours': 72,
                'template': 'sequences/attendance_intervention.html',
                'subject': 'Attendance Intervention - Meeting Scheduled',
                'condition': 'attendance_below_60'
            },
            {
                'name': 'improvement_plan',
                'delay_hours': 168,  # 1 week
                'template': 'sequences/attendance_improvement_plan.html',
                'subject': 'Attendance Improvement Plan - Next Steps',
                'condition': 'intervention_completed'
            }
        ]
        return EmailSequence('attendance_intervention', 'attendance_dropped', emails)
    
    def _create_payment_reminder_sequence(self) -> EmailSequence:
        """Create payment reminder sequence (4 emails)"""
        emails = [
            {
                'name': 'gentle_reminder',
                'delay_hours': 24,  # 1 day after due
                'template': 'sequences/payment_gentle_reminder.html',
                'subject': 'Friendly Payment Reminder',
                'condition': 'payment_overdue'
            },
            {
                'name': 'formal_notice',
                'delay_hours': 168,  # 1 week after due
                'template': 'sequences/payment_formal_notice.html',
                'subject': 'Payment Due - Formal Notice',
                'condition': 'payment_overdue'
            },
            {
                'name': 'final_notice',
                'delay_hours': 336,  # 2 weeks after due
                'template': 'sequences/payment_final_notice.html',
                'subject': 'Final Payment Notice - Immediate Action Required',
                'condition': 'payment_overdue'
            },
            {
                'name': 'service_suspension_warning',
                'delay_hours': 504,  # 3 weeks after due
                'template': 'sequences/payment_suspension_warning.html',
                'subject': 'Service Suspension Warning - Urgent',
                'condition': 'payment_overdue'
            }
        ]
        return EmailSequence('payment_reminder', 'payment_due', emails)
    
    def _create_performance_monitoring_sequence(self) -> EmailSequence:
        """Create performance monitoring sequence (3 emails)"""
        emails = [
            {
                'name': 'performance_dip_alert',
                'delay_hours': 0,
                'template': 'sequences/performance_dip_alert.html',
                'subject': 'Performance Monitoring Alert',
                'condition': 'performance_below_threshold'
            },
            {
                'name': 'improvement_support',
                'delay_hours': 48,
                'template': 'sequences/performance_improvement_support.html',
                'subject': 'Performance Improvement Support Available',
                'condition': 'performance_still_low'
            },
            {
                'name': 'review_meeting',
                'delay_hours': 168,  # 1 week
                'template': 'sequences/performance_review_meeting.html',
                'subject': 'Performance Review Meeting Scheduled',
                'condition': 'performance_review_needed'
            }
        ]
        return EmailSequence('performance_monitoring', 'performance_declined', emails)
    
    # ============ SEQUENCE EXECUTION ============
    
    def trigger_sequence(self, sequence_name: str, trigger_data: Dict[str, Any]) -> bool:
        """Trigger an email sequence"""
        if sequence_name not in self.sequences:
            self.logger.error(f"Unknown sequence: {sequence_name}")
            return False
        
        sequence = self.sequences[sequence_name]
        
        # Create sequence instance record
        sequence_instance = {
            'sequence_name': sequence_name,
            'trigger_data': trigger_data,
            'started_at': datetime.now(),
            'status': 'active',
            'emails_sent': 0,
            'next_email_index': 0
        }
        
        # Schedule first email
        return self._schedule_next_email(sequence, sequence_instance)
    
    def _schedule_next_email(self, sequence: EmailSequence, instance: Dict[str, Any]) -> bool:
        """Schedule the next email in the sequence"""
        next_index = instance['next_email_index']
        
        if next_index >= len(sequence.emails):
            instance['status'] = 'completed'
            return True
        
        email_def = sequence.emails[next_index]
        
        # Check condition
        if not self._check_email_condition(email_def['condition'], instance['trigger_data']):
            # Skip this email and move to next
            instance['next_email_index'] += 1
            return self._schedule_next_email(sequence, instance)
        
        # Calculate send time
        send_time = instance['started_at'] + timedelta(hours=email_def['delay_hours'])
        
        # If send time is in the past or immediate, send now
        if send_time <= datetime.now():
            return self._send_sequence_email(email_def, instance)
        else:
            # Schedule for later (in a real implementation, this would use a task queue)
            self.logger.info(f"Email '{email_def['name']}' scheduled for {send_time}")
            return True
    
    def _send_sequence_email(self, email_def: Dict[str, Any], instance: Dict[str, Any]) -> bool:
        """Send an email from a sequence"""
        trigger_data = instance['trigger_data']
        
        # Determine recipients based on trigger data
        recipients = self._get_sequence_recipients(trigger_data)
        
        if not recipients:
            self.logger.warning(f"No recipients found for sequence email: {email_def['name']}")
            return False
        
        # Build context
        context = {
            'trigger_data': trigger_data,
            'sequence_info': {
                'email_name': email_def['name'],
                'sequence_step': instance['next_email_index'] + 1,
                'total_steps': len(instance.get('sequence_emails', []))
            }
        }
        
        # Add specific context based on trigger data type
        context.update(self._build_sequence_context(trigger_data))
        
        # Send email
        success = self.send_email(
            recipients=recipients,
            subject=email_def['subject'],
            template=email_def['template'],
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.AUTOMATED
        )
        
        if success:
            instance['emails_sent'] += 1
            instance['next_email_index'] += 1
            
            # Schedule next email if not recurring
            if not email_def.get('recurring', False):
                return self._schedule_next_email(
                    self.sequences[instance['sequence_name']], 
                    instance
                )
        
        return success
    
    def _check_email_condition(self, condition: str, trigger_data: Dict[str, Any]) -> bool:
        """Check if email condition is met"""
        conditions = {
            'registration_complete': lambda: True,  # Always true after registration
            'profile_incomplete': self._check_profile_incomplete,
            'tutor_assigned': self._check_tutor_assigned,
            'first_class_today': self._check_first_class_today,
            'first_class_completed': self._check_first_class_completed,
            'active_student': self._check_active_student,
            'application_submitted': lambda: True,
            'documents_under_review': self._check_documents_under_review,
            'tutor_approved': self._check_tutor_approved,
            'first_class_assigned': self._check_first_class_assigned,
            'training_completed': self._check_training_completed,
            'active_tutor': self._check_active_tutor,
            'class_created': lambda: True,
            'class_scheduled': self._check_class_scheduled,
            'class_completed': self._check_class_completed,
            'escalation_created': lambda: True,
            'escalation_assigned': self._check_escalation_assigned,
            'escalation_in_progress': self._check_escalation_in_progress,
            'escalation_resolved': self._check_escalation_resolved,
            'attendance_below_80': self._check_attendance_below_80,
            'attendance_below_70': self._check_attendance_below_70,
            'attendance_below_60': self._check_attendance_below_60,
            'intervention_completed': self._check_intervention_completed,
            'payment_overdue': self._check_payment_overdue,
            'performance_below_threshold': self._check_performance_below_threshold,
            'performance_still_low': self._check_performance_still_low,
            'performance_review_needed': self._check_performance_review_needed
        }
        
        condition_func = conditions.get(condition)
        if condition_func:
            try:
                return condition_func(trigger_data) if condition_func.__code__.co_argcount > 0 else condition_func()
            except Exception as e:
                self.logger.error(f"Error checking condition '{condition}': {str(e)}")
                return False
        
        self.logger.warning(f"Unknown condition: {condition}")
        return False
    
    def _get_sequence_recipients(self, trigger_data: Dict[str, Any]) -> List[str]:
        """Get email recipients based on trigger data"""
        recipients = []
        
        if 'student_id' in trigger_data:
            student = Student.query.get(trigger_data['student_id'])
            if student and student.email:
                recipients.append(student.email)
                
                # Add parent emails for students
                parent_details = student.get_parent_details()
                if parent_details:
                    for parent_type in ['father', 'mother']:
                        parent_email = parent_details.get(parent_type, {}).get('email')
                        if parent_email:
                            recipients.append(parent_email)
        
        if 'tutor_id' in trigger_data:
            tutor = Tutor.query.get(trigger_data['tutor_id'])
            if tutor and tutor.user and tutor.user.email:
                recipients.append(tutor.user.email)
        
        if 'user_id' in trigger_data:
            user = User.query.get(trigger_data['user_id'])
            if user and user.email:
                recipients.append(user.email)
        
        return list(set(recipients))  # Remove duplicates
    
    def _build_sequence_context(self, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for sequence emails"""
        context = {}
        
        if 'student_id' in trigger_data:
            student = Student.query.get(trigger_data['student_id'])
            if student:
                context['student'] = student
                context['department'] = student.department
                context['parent_details'] = student.get_parent_details()
        
        if 'tutor_id' in trigger_data:
            tutor = Tutor.query.get(trigger_data['tutor_id'])
            if tutor:
                context['tutor'] = tutor
                context['user'] = tutor.user
        
        if 'class_id' in trigger_data:
            class_obj = Class.query.get(trigger_data['class_id'])
            if class_obj:
                context['class'] = class_obj
                context['tutor'] = class_obj.tutor
                context['students'] = class_obj.get_student_objects()
        
        return context
    
    # ============ CONDITION CHECKING METHODS ============
    
    def _check_profile_incomplete(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if student profile is incomplete"""
        if 'student_id' not in trigger_data:
            return False
        student = Student.query.get(trigger_data['student_id'])
        if not student:
            return False
        
        # Check if required fields are missing
        required_fields = ['phone', 'address', 'parent_details', 'subjects_enrolled']
        for field in required_fields:
            if not getattr(student, field, None):
                return True
        return False
    
    def _check_tutor_assigned(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if tutor is assigned to student"""
        if 'student_id' not in trigger_data:
            return False
        
        classes = Class.query.filter(
            or_(
                Class.primary_student_id == trigger_data['student_id'],
                Class.students.like(f"%{trigger_data['student_id']}%")
            )
        ).first()
        
        return classes is not None
    
    def _check_first_class_today(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if first class is today"""
        if 'student_id' not in trigger_data:
            return False
        
        today_class = Class.query.filter(
            and_(
                or_(
                    Class.primary_student_id == trigger_data['student_id'],
                    Class.students.like(f"%{trigger_data['student_id']}%")
                ),
                Class.scheduled_date == datetime.now().date(),
                Class.status == 'scheduled'
            )
        ).first()
        
        return today_class is not None
    
    def _check_first_class_completed(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if first class is completed"""
        if 'student_id' not in trigger_data:
            return False
        
        completed_class = Class.query.filter(
            and_(
                or_(
                    Class.primary_student_id == trigger_data['student_id'],
                    Class.students.like(f"%{trigger_data['student_id']}%")
                ),
                Class.status == 'completed'
            )
        ).first()
        
        return completed_class is not None
    
    def _check_active_student(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if student is active"""
        if 'student_id' not in trigger_data:
            return False
        student = Student.query.get(trigger_data['student_id'])
        return student and student.is_active and student.enrollment_status == 'active'
    
    def _check_attendance_below_80(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if attendance is below 80%"""
        if 'student_id' not in trigger_data:
            return False
        student = Student.query.get(trigger_data['student_id'])
        return student and student.get_attendance_percentage() < 80
    
    def _check_attendance_below_70(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if attendance is below 70%"""
        if 'student_id' not in trigger_data:
            return False
        student = Student.query.get(trigger_data['student_id'])
        return student and student.get_attendance_percentage() < 70
    
    def _check_attendance_below_60(self, trigger_data: Dict[str, Any]) -> bool:
        """Check if attendance is below 60%"""
        if 'student_id' not in trigger_data:
            return False
        student = Student.query.get(trigger_data['student_id'])
        return student and student.get_attendance_percentage() < 60
    
    # Add more condition checking methods as needed...
    
    # ============ PUBLIC API METHODS ============
    
    def start_student_onboarding(self, student_id: int) -> bool:
        """Start student onboarding sequence"""
        return self.trigger_sequence('student_onboarding', {'student_id': student_id})
    
    def start_tutor_onboarding(self, tutor_id: int) -> bool:
        """Start tutor onboarding sequence"""
        return self.trigger_sequence('tutor_onboarding', {'tutor_id': tutor_id})
    
    def start_class_workflow(self, class_id: int) -> bool:
        """Start class workflow sequence"""
        return self.trigger_sequence('class_workflow', {'class_id': class_id})
    
    def start_escalation_workflow(self, escalation_id: int) -> bool:
        """Start escalation workflow sequence"""
        return self.trigger_sequence('escalation_workflow', {'escalation_id': escalation_id})
    
    def start_attendance_intervention(self, student_id: int) -> bool:
        """Start attendance intervention sequence"""
        return self.trigger_sequence('attendance_intervention', {'student_id': student_id})
    
    def start_payment_reminder(self, student_id: int) -> bool:
        """Start payment reminder sequence"""
        return self.trigger_sequence('payment_reminder', {'student_id': student_id})
    
    def start_performance_monitoring(self, user_id: int, user_type: str) -> bool:
        """Start performance monitoring sequence"""
        trigger_data = {'user_id': user_id, 'user_type': user_type}
        if user_type == 'student':
            trigger_data['student_id'] = user_id
        elif user_type == 'tutor':
            trigger_data['tutor_id'] = user_id
        
        return self.trigger_sequence('performance_monitoring', trigger_data)

# Global instance
email_automation_service = EmailAutomationService()