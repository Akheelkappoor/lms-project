"""
Tutor Email Service - All tutor-related email notifications
Extends the comprehensive email service for tutor-specific functions
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.services.comprehensive_email_service import ComprehensiveEmailService, EmailPriority, EmailType
from app.models.tutor import Tutor
from app.models.user import User
from app.models.class_model import Class
from app.models.student import Student
from app.models.attendance import Attendance
from sqlalchemy import and_, or_
import json

class TutorEmailService(ComprehensiveEmailService):
    """Extended email service for all tutor notifications"""
    
    # ============ TUTOR ONBOARDING & PROFILE ============
    
    def send_tutor_application_confirmation(self, tutor_id: int):
        """Send tutor application confirmation"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        hr_emails = self.get_admin_emails('admin')
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'application_date': datetime.now(),
            'next_steps': [
                "Document verification within 48 hours",
                "Background check completion",
                "Interview scheduling if required",
                "Platform access setup"
            ],
            'timeline': "5-7 business days"
        }
        
        return self.send_email(
            recipients=recipients,
            cc=hr_emails,
            subject=f"Application Received - Welcome to LMS, {tutor.user.full_name}",
            template='tutor/application_confirmation.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ONBOARDING
        )
    
    def send_document_verification_update(self, tutor_id: int, verification_status: str, missing_docs: List[str] = None):
        """Send document verification status update"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        hr_emails = self.get_admin_emails('admin')
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'verification_status': verification_status,
            'missing_documents': missing_docs or [],
            'required_actions': self._get_verification_actions(verification_status, missing_docs),
            'deadline': datetime.now() + timedelta(days=3),
            'upload_portal': "/tutor/documents"
        }
        
        subject_map = {
            'pending': "Document Verification Required",
            'in_progress': "Document Verification In Progress", 
            'approved': "Documents Verified Successfully",
            'rejected': "Document Verification Issues"
        }
        
        return self.send_email(
            recipients=recipients,
            cc=hr_emails if verification_status in ['pending', 'rejected'] else [],
            subject=subject_map.get(verification_status, "Document Status Update"),
            template='tutor/document_verification.html',
            context=context,
            priority=EmailPriority.HIGH if verification_status == 'rejected' else EmailPriority.MEDIUM,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    def send_tutor_approval_notification(self, tutor_id: int):
        """Send tutor approval and welcome notification"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        admin_emails = self.get_admin_emails()
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'department': tutor.user.department,
            'approval_date': datetime.now(),
            'platform_access': {
                'dashboard_url': "/tutor/dashboard",
                'profile_url': "/tutor/profile",
                'classes_url': "/tutor/my-classes",
                'availability_url': "/tutor/availability"
            },
            'first_steps': [
                "Complete your tutor profile",
                "Set your availability schedule", 
                "Review teaching guidelines",
                "Wait for first class assignment"
            ],
            'support_contact': coord_emails[0] if coord_emails else admin_emails[0] if admin_emails else None
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            bcc=admin_emails,
            subject=f"Welcome to LMS Teaching Team - {tutor.user.full_name}",
            template='tutor/approval_welcome.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ONBOARDING
        )
    
    def send_profile_completion_reminder(self, tutor_id: int, missing_fields: List[str]):
        """Send profile completion reminder"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'missing_fields': missing_fields,
            'completion_percentage': self._calculate_profile_completion(tutor),
            'profile_url': "/tutor/profile/edit",
            'benefits': [
                "Get assigned to more classes",
                "Better student matching",
                "Higher visibility to coordinators",
                "Access to advanced features"
            ]
        }
        
        return self.send_email(
            recipients=recipients,
            subject="Complete Your Teaching Profile - Get More Classes",
            template='tutor/profile_completion_reminder.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REMINDER
        )
    
    # ============ CLASS MANAGEMENT ============
    
    def send_class_assignment_notification(self, tutor_id: int, class_id: int):
        """Send class assignment notification to tutor"""
        tutor = Tutor.query.get(tutor_id)
        class_obj = Class.query.get(class_id)
        
        if not tutor or not class_obj or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        
        # Get student details
        student_details = []
        student_ids = class_obj.get_students()
        for student_id in student_ids:
            student = Student.query.get(student_id)
            if student:
                student_details.append({
                    'name': student.full_name,
                    'grade': student.grade,
                    'board': student.board,
                    'subjects': student.get_subjects_enrolled(),
                    'phone': student.phone,
                    'email': student.email
                })
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'class': class_obj,
            'students': student_details,
            'class_type': class_obj.class_type,
            'preparation_time': (datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time) - datetime.now()).total_seconds() / 3600,
            'class_guidelines': self._get_class_guidelines(class_obj.class_type),
            'emergency_contact': coord_emails[0] if coord_emails else None
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            subject=f"New Class Assigned - {class_obj.subject} | {class_obj.scheduled_date}",
            template='tutor/class_assignment.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ACADEMIC
        )
    
    def send_bulk_class_assignment(self, tutor_id: int, class_ids: List[int]):
        """Send bulk class assignment notification"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        if not classes:
            return False
            
        recipients = [tutor.user.email]
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        
        # Organize classes by subject and date
        classes_by_subject = {}
        for class_obj in classes:
            subject = class_obj.subject
            if subject not in classes_by_subject:
                classes_by_subject[subject] = []
            classes_by_subject[subject].append(class_obj)
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'total_classes': len(classes),
            'classes_by_subject': classes_by_subject,
            'date_range': {
                'start': min(c.scheduled_date for c in classes),
                'end': max(c.scheduled_date for c in classes)
            },
            'schedule_url': "/tutor/my-classes",
            'preparation_tips': [
                "Review all student profiles",
                "Prepare subject-specific materials",
                "Check your availability matches",
                "Set up meeting rooms in advance"
            ]
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            subject=f"Multiple Classes Assigned - {len(classes)} New Classes",
            template='tutor/bulk_class_assignment.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ACADEMIC
        )
    
    def send_student_assignment_update(self, tutor_id: int, class_id: int, added_students: List[int], removed_students: List[int]):
        """Send student assignment change notification"""
        tutor = Tutor.query.get(tutor_id)
        class_obj = Class.query.get(class_id)
        
        if not tutor or not class_obj or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        
        # Get student details for added/removed students
        added_student_details = []
        removed_student_details = []
        
        for student_id in added_students:
            student = Student.query.get(student_id)
            if student:
                added_student_details.append({
                    'name': student.full_name,
                    'grade': student.grade,
                    'board': student.board,
                    'subjects': student.get_subjects_enrolled()
                })
        
        for student_id in removed_students:
            student = Student.query.get(student_id)
            if student:
                removed_student_details.append({
                    'name': student.full_name,
                    'grade': student.grade
                })
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'class': class_obj,
            'added_students': added_student_details,
            'removed_students': removed_student_details,
            'current_student_count': len(class_obj.get_students()),
            'class_capacity': class_obj.max_students
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Student Assignment Updated - {class_obj.subject}",
            template='tutor/student_assignment_update.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.ACADEMIC
        )
    
    def send_class_reschedule_request_response(self, tutor_id: int, class_id: int, request_status: str, admin_notes: str = ""):
        """Send reschedule request response to tutor"""
        tutor = Tutor.query.get(tutor_id)
        class_obj = Class.query.get(class_id)
        
        if not tutor or not class_obj or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'class': class_obj,
            'request_status': request_status,
            'admin_notes': admin_notes,
            'next_steps': self._get_reschedule_next_steps(request_status),
            'original_schedule': {
                'date': class_obj.scheduled_date,
                'time': class_obj.scheduled_time
            }
        }
        
        status_subjects = {
            'approved': f"Reschedule Approved - {class_obj.subject}",
            'rejected': f"Reschedule Request Declined - {class_obj.subject}",
            'pending': f"Reschedule Request Under Review - {class_obj.subject}"
        }
        
        return self.send_email(
            recipients=recipients,
            subject=status_subjects.get(request_status, "Reschedule Request Update"),
            template='tutor/reschedule_response.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    # ============ PERFORMANCE & FEEDBACK ============
    
    def send_performance_review(self, tutor_id: int, review_period: str, metrics: Dict[str, Any]):
        """Send monthly/quarterly performance review"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'review_period': review_period,
            'metrics': metrics,
            'performance_grade': self._calculate_performance_grade(metrics),
            'strengths': metrics.get('strengths', []),
            'improvement_areas': metrics.get('improvement_areas', []),
            'recommendations': metrics.get('recommendations', []),
            'next_review_date': datetime.now() + timedelta(days=30)
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            subject=f"Performance Review - {review_period} | {tutor.user.full_name}",
            template='tutor/performance_review.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
    
    def send_student_feedback_summary(self, tutor_id: int, month: str, feedback_data: Dict[str, Any]):
        """Send monthly student feedback summary"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'month': month,
            'feedback_summary': feedback_data,
            'average_rating': feedback_data.get('average_rating', 0),
            'total_feedback': feedback_data.get('total_responses', 0),
            'positive_feedback': feedback_data.get('positive_comments', []),
            'areas_for_improvement': feedback_data.get('improvement_suggestions', []),
            'student_satisfaction': feedback_data.get('satisfaction_percentage', 0)
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Student Feedback Summary - {month} | Rating: {feedback_data.get('average_rating', 0):.1f}/5",
            template='tutor/feedback_summary.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
    
    def send_availability_update_confirmation(self, tutor_id: int, updated_schedule: Dict[str, Any]):
        """Send availability update confirmation"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'updated_schedule': updated_schedule,
            'effective_date': datetime.now(),
            'affected_classes': self._get_affected_classes_by_schedule_change(tutor_id, updated_schedule),
            'next_assignment_timeline': "within 24-48 hours"
        }
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails,
            subject=f"Availability Updated - {tutor.user.full_name}",
            template='tutor/availability_confirmation.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    # ============ FINANCIAL NOTIFICATIONS ============
    
    def send_payout_notification(self, tutor_id: int, payout_data: Dict[str, Any]):
        """Send monthly payout notification"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        finance_emails = self.get_admin_emails()
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'payout': payout_data,
            'total_amount': payout_data.get('total_amount', 0),
            'classes_conducted': payout_data.get('classes_count', 0),
            'payment_date': payout_data.get('payment_date', datetime.now()),
            'payment_method': payout_data.get('payment_method', 'Bank Transfer'),
            'breakdown': payout_data.get('breakdown', {}),
            'tax_details': payout_data.get('tax_info', {})
        }
        
        return self.send_email(
            recipients=recipients,
            bcc=finance_emails,
            subject=f"Payout Processed - ₹{payout_data.get('total_amount', 0):,.2f} | {payout_data.get('period', 'This Month')}",
            template='tutor/payout_notification.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.FINANCIAL
        )
    
    def send_training_completion_certificate(self, tutor_id: int, training_data: Dict[str, Any]):
        """Send training completion certificate"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        hr_emails = self.get_admin_emails()
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'training': training_data,
            'completion_date': datetime.now(),
            'certificate_id': f"CERT-{tutor_id}-{datetime.now().strftime('%Y%m%d')}",
            'skills_gained': training_data.get('skills', []),
            'next_level_training': training_data.get('next_training', None)
        }
        
        return self.send_email(
            recipients=recipients,
            cc=hr_emails,
            subject=f"Training Completed - {training_data.get('training_name', 'Professional Development')}",
            template='tutor/training_certificate.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.ACADEMIC
        )
    
    def send_video_upload_reminder(self, tutor_id: int, class_id: int, deadline: datetime):
        """Send video upload reminder"""
        tutor = Tutor.query.get(tutor_id)
        class_obj = Class.query.get(class_id)
        
        if not tutor or not class_obj or not tutor.user:
            return False
            
        recipients = [tutor.user.email]
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        
        time_remaining = deadline - datetime.now()
        is_urgent = time_remaining.total_seconds() < 3600  # Less than 1 hour
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'class': class_obj,
            'deadline': deadline,
            'time_remaining': time_remaining,
            'is_urgent': is_urgent,
            'upload_url': f"/tutor/classes/{class_id}/upload-video",
            'consequences': [
                "Class marked as incomplete",
                "Impact on performance rating",
                "Coordinator notification",
                "Follow-up required"
            ]
        }
        
        priority = EmailPriority.IMMEDIATE if is_urgent else EmailPriority.HIGH
        
        return self.send_email(
            recipients=recipients,
            cc=coord_emails if is_urgent else [],
            subject=f"Video Upload {'URGENT' if is_urgent else 'Reminder'} - {class_obj.subject}",
            template='tutor/video_upload_reminder.html',
            context=context,
            priority=priority,
            email_type=EmailType.ALERT if is_urgent else EmailType.REMINDER
        )
    
    # ============ HELPER METHODS ============
    
    def _get_verification_actions(self, status: str, missing_docs: List[str]) -> List[str]:
        """Get required actions based on verification status"""
        if status == 'pending':
            return [
                "Upload all required documents",
                "Ensure documents are clear and legible",
                "Submit within 48 hours"
            ]
        elif status == 'rejected':
            return [
                f"Re-upload: {', '.join(missing_docs)}" if missing_docs else "Correct document issues",
                "Contact HR for clarification",
                "Resubmit within 24 hours"
            ]
        elif status == 'approved':
            return [
                "Wait for final approval",
                "Complete profile setup",
                "Prepare for first assignment"
            ]
        return ["Contact HR for guidance"]
    
    def _calculate_profile_completion(self, tutor: Tutor) -> int:
        """Calculate profile completion percentage"""
        required_fields = [
            'experience_years', 'education_qualification', 'subjects_taught',
            'teaching_boards', 'availability', 'preferred_teaching_mode'
        ]
        
        completed = 0
        for field in required_fields:
            if hasattr(tutor, field) and getattr(tutor, field):
                completed += 1
        
        return int((completed / len(required_fields)) * 100)
    
    def _get_class_guidelines(self, class_type: str) -> List[str]:
        """Get class-specific guidelines"""
        guidelines = {
            'one_on_one': [
                "Personalize teaching approach",
                "Focus on individual student needs",
                "Regular progress assessment",
                "Maintain detailed notes"
            ],
            'group': [
                "Ensure equal participation",
                "Manage group dynamics",
                "Use collaborative teaching methods",
                "Monitor individual progress"
            ],
            'demo': [
                "Make excellent first impression",
                "Demonstrate teaching style",
                "Engage student effectively",
                "Highlight learning benefits"
            ]
        }
        return guidelines.get(class_type, ["Follow standard teaching protocols"])
    
    def _get_reschedule_next_steps(self, status: str) -> List[str]:
        """Get next steps based on reschedule status"""
        steps = {
            'approved': [
                "New schedule has been updated",
                "Students have been notified",
                "Prepare for new time slot",
                "Confirm attendance as usual"
            ],
            'rejected': [
                "Attend class at original time",
                "Contact coordinator if urgent",
                "Plan better for future requests",
                "Consider availability updates"
            ],
            'pending': [
                "Wait for admin review",
                "Prepare for original schedule",
                "You'll be notified of decision",
                "Contact coordinator for urgent cases"
            ]
        }
        return steps.get(status, ["Contact coordinator for guidance"])
    
    def _calculate_performance_grade(self, metrics: Dict[str, Any]) -> str:
        """Calculate overall performance grade"""
        score = metrics.get('overall_score', 0)
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Very Good"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Satisfactory"
        else:
            return "Needs Improvement"
    
    def _get_affected_classes_by_schedule_change(self, tutor_id: int, new_schedule: Dict[str, Any]) -> List[Dict]:
        """Get classes affected by availability change"""
        # This would analyze upcoming classes against new availability
        future_classes = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.scheduled_date >= datetime.now().date(),
            Class.status == 'scheduled'
        ).all()
        
        affected = []
        for class_obj in future_classes:
            # Logic to check if class conflicts with new availability
            affected.append({
                'id': class_obj.id,
                'subject': class_obj.subject,
                'date': class_obj.scheduled_date,
                'time': class_obj.scheduled_time,
                'conflict': False  # Would implement actual conflict detection
            })
        
        return affected

# Global instance
tutor_email_service = TutorEmailService()