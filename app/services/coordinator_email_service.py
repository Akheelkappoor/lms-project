"""
Coordinator Email Service - All coordinator-related email notifications
Extends the comprehensive email service for coordinator-specific functions
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.services.comprehensive_email_service import ComprehensiveEmailService, EmailPriority, EmailType
from app.models.user import User
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.escalation import Escalation
from app.models.attendance import Attendance
from app.models.department import Department
from sqlalchemy import and_, or_, func
import json

class CoordinatorEmailService(ComprehensiveEmailService):
    """Extended email service for all coordinator notifications"""
    
    # ============ STUDENT MANAGEMENT ALERTS ============
    
    def send_student_onboarding_alert(self, student_id: int, coordinator_id: int = None):
        """Send new student onboarding alert to coordinator"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        # Get department coordinators
        coord_emails = self.get_department_coordinators(student.department_id)
        if coordinator_id:
            coordinator = User.query.get(coordinator_id)
            if coordinator and coordinator.email:
                coord_emails = [coordinator.email]
        
        context = {
            'student': student,
            'department': student.department,
            'registration_date': datetime.now(),
            'parent_details': student.get_parent_details(),
            'subjects_enrolled': student.get_subjects_enrolled(),
            'fee_structure': student.get_fee_structure(),
            'action_items': [
                "Assign relationship manager",
                "Schedule tutor matching",
                "Set up first class",
                "Send welcome packet"
            ],
            'priority_deadline': datetime.now() + timedelta(hours=24)
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"New Student Onboarding - {student.full_name} | {student.grade} {student.board}",
            template='coordinator/student_onboarding_alert.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    def send_student_risk_alert(self, student_id: int, risk_factors: Dict[str, Any]):
        """Send student at-risk alert to coordinator"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        coord_emails = self.get_department_coordinators(student.department_id)
        admin_emails = self.get_admin_emails()
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(risk_factors)
        risk_level = self._get_risk_level(risk_score)
        
        context = {
            'student': student,
            'risk_factors': risk_factors,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'attendance_percentage': student.get_attendance_percentage(),
            'recommended_actions': self._get_risk_intervention_actions(risk_factors),
            'escalation_required': risk_score >= 80,
            'review_deadline': datetime.now() + timedelta(days=2)
        }
        
        # High-risk students get escalated to admins
        recipients = coord_emails
        if risk_score >= 80:
            recipients.extend(admin_emails)
        
        return self.send_email(
            recipients=recipients,
            subject=f"Student Risk Alert - {student.full_name} | Risk Level: {risk_level}",
            template='coordinator/student_risk_alert.html',
            context=context,
            priority=EmailPriority.HIGH if risk_score >= 60 else EmailPriority.MEDIUM,
            email_type=EmailType.ALERT
        )
    
    def send_attendance_intervention_alert(self, student_id: int):
        """Send attendance intervention alert"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        attendance_percentage = student.get_attendance_percentage()
        if attendance_percentage >= 70:
            return False  # No intervention needed
            
        coord_emails = self.get_department_coordinators(student.department_id)
        
        # Get recent attendance pattern
        recent_classes = Class.query.filter(
            or_(
                Class.primary_student_id == student_id,
                Class.students.like(f'%{student_id}%')
            ),
            Class.scheduled_date >= datetime.now().date() - timedelta(days=30)
        ).order_by(Class.scheduled_date.desc()).limit(10).all()
        
        context = {
            'student': student,
            'attendance_percentage': attendance_percentage,
            'total_classes': student.total_classes,
            'attended_classes': student.attended_classes,
            'recent_classes': recent_classes,
            'intervention_steps': [
                "Contact student and parents immediately",
                "Schedule counseling session",
                "Review class timings and conflicts",
                "Consider schedule adjustments",
                "Set up makeup classes if needed"
            ],
            'target_improvement': 85,
            'review_date': datetime.now() + timedelta(days=7)
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"Attendance Intervention Required - {student.full_name} ({attendance_percentage:.1f}%)",
            template='coordinator/attendance_intervention.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    # ============ TUTOR SUPERVISION ============
    
    def send_tutor_performance_alert(self, tutor_id: int, performance_issues: Dict[str, Any]):
        """Send tutor performance alert to coordinator"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        hr_emails = self.get_admin_emails('admin')
        
        # Calculate severity
        severity = self._calculate_performance_severity(performance_issues)
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'performance_issues': performance_issues,
            'severity': severity,
            'current_rating': tutor.rating or 0,
            'classes_affected': performance_issues.get('classes_affected', 0),
            'student_complaints': performance_issues.get('student_complaints', []),
            'recommended_actions': self._get_performance_improvement_actions(severity),
            'escalation_required': severity == 'Critical',
            'review_deadline': datetime.now() + timedelta(days=3)
        }
        
        recipients = coord_emails
        if severity == 'Critical':
            recipients.extend(hr_emails)
        
        return self.send_email(
            recipients=recipients,
            subject=f"Tutor Performance Alert - {tutor.user.full_name} | {severity} Issues",
            template='coordinator/tutor_performance_alert.html',
            context=context,
            priority=EmailPriority.HIGH if severity in ['High', 'Critical'] else EmailPriority.MEDIUM,
            email_type=EmailType.ALERT
        )
    
    def send_video_compliance_alert(self, department_id: int, non_compliant_tutors: List[Dict[str, Any]]):
        """Send video upload compliance alert"""
        coord_emails = self.get_department_coordinators(department_id)
        department = Department.query.get(department_id)
        
        if not coord_emails or not department:
            return False
        
        # Calculate compliance statistics
        total_tutors = len(non_compliant_tutors)
        overdue_count = len([t for t in non_compliant_tutors if t.get('hours_overdue', 0) > 2])
        
        context = {
            'department': department,
            'non_compliant_tutors': non_compliant_tutors,
            'total_count': total_tutors,
            'overdue_count': overdue_count,
            'compliance_rate': max(0, 100 - (total_tutors / max(1, department.active_tutors_count) * 100)),
            'action_required': [
                "Contact non-compliant tutors immediately",
                "Review video upload policies",
                "Escalate repeated violations",
                "Update training if necessary"
            ],
            'deadline': datetime.now() + timedelta(hours=4)
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"Video Upload Compliance Alert - {total_tutors} Tutors Non-Compliant",
            template='coordinator/video_compliance_alert.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    def send_tutor_availability_report(self, department_id: int, week_start: datetime):
        """Send weekly tutor availability report"""
        coord_emails = self.get_department_coordinators(department_id)
        department = Department.query.get(department_id)
        
        if not coord_emails or not department:
            return False
        
        # Get department tutors
        tutors = Tutor.query.join(User).filter(
            User.department_id == department_id,
            Tutor.status == 'active'
        ).all()
        
        # Compile availability data
        availability_data = []
        total_hours = 0
        tutors_with_availability = 0
        
        for tutor in tutors:
            tutor_availability = tutor.get_availability()
            if tutor_availability:
                tutors_with_availability += 1
                # Calculate weekly hours
                weekly_hours = self._calculate_weekly_hours(tutor_availability)
                total_hours += weekly_hours
                
                availability_data.append({
                    'tutor': tutor,
                    'user': tutor.user,
                    'weekly_hours': weekly_hours,
                    'availability': tutor_availability,
                    'subjects': tutor.get_subjects_taught(),
                    'current_load': self._get_tutor_current_load(tutor.id)
                })
        
        context = {
            'department': department,
            'week_start': week_start,
            'week_end': week_start + timedelta(days=6),
            'availability_data': availability_data,
            'total_tutors': len(tutors),
            'tutors_with_availability': tutors_with_availability,
            'total_available_hours': total_hours,
            'average_hours_per_tutor': total_hours / max(1, tutors_with_availability),
            'recommendations': self._get_availability_recommendations(availability_data)
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"Weekly Availability Report - {department.name} | Week {week_start.strftime('%m/%d')}",
            template='coordinator/availability_report.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
    
    # ============ OPERATIONAL NOTIFICATIONS ============
    
    def send_group_creation_notification(self, class_id: int, coordinator_id: int = None):
        """Send group class creation notification"""
        class_obj = Class.query.get(class_id)
        if not class_obj or class_obj.class_type != 'group':
            return False
        
        # Get coordinators
        if coordinator_id:
            coordinator = User.query.get(coordinator_id)
            coord_emails = [coordinator.email] if coordinator and coordinator.email else []
        else:
            # Get all department coordinators
            coord_emails = []
            if class_obj.tutor and class_obj.tutor.user:
                coord_emails = self.get_department_coordinators(class_obj.tutor.user.department_id)
        
        # Get enrolled students info
        student_ids = class_obj.get_students()
        students_info = []
        for student_id in student_ids:
            student = Student.query.get(student_id)
            if student:
                students_info.append({
                    'name': student.full_name,
                    'grade': student.grade,
                    'board': student.board
                })
        
        context = {
            'class': class_obj,
            'students': students_info,
            'student_count': len(students_info),
            'max_capacity': class_obj.max_students,
            'tutor_assigned': class_obj.tutor is not None,
            'tutor_details': {
                'name': class_obj.tutor.user.full_name if class_obj.tutor and class_obj.tutor.user else None,
                'email': class_obj.tutor.user.email if class_obj.tutor and class_obj.tutor.user else None
            } if class_obj.tutor else None,
            'action_items': [
                "Verify tutor assignment" if not class_obj.tutor else "Confirm tutor availability",
                "Review student compatibility",
                "Set up meeting room",
                "Send welcome email to all participants"
            ]
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"New Group Created - {class_obj.subject} | {len(students_info)} Students",
            template='coordinator/group_creation.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    def send_escalation_assignment_alert(self, escalation_id: int):
        """Send escalation assignment alert to coordinator"""
        escalation = Escalation.query.get(escalation_id)
        if not escalation:
            return False
        
        # Get relevant coordinators
        coord_emails = []
        if escalation.department_id:
            coord_emails = self.get_department_coordinators(escalation.department_id)
        else:
            coord_emails = self.get_admin_emails('coordinator')
        
        # Get assigned user details
        assigned_user = User.query.get(escalation.assigned_to) if escalation.assigned_to else None
        
        context = {
            'escalation': escalation,
            'assigned_user': assigned_user,
            'priority_level': escalation.priority,
            'category': escalation.category,
            'description': escalation.description,
            'created_date': escalation.created_at,
            'due_date': escalation.due_date,
            'days_remaining': (escalation.due_date - datetime.now()).days if escalation.due_date else None,
            'action_required': [
                "Review escalation details",
                "Contact assigned person if needed",
                "Monitor progress",
                "Ensure timely resolution"
            ]
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"Escalation Assignment - {escalation.title} | Priority: {escalation.priority}",
            template='coordinator/escalation_assignment.html',
            context=context,
            priority=EmailPriority.HIGH if escalation.priority in ['High', 'Critical'] else EmailPriority.MEDIUM,
            email_type=EmailType.ALERT
        )
    
    def send_department_performance_summary(self, department_id: int, period: str, metrics: Dict[str, Any]):
        """Send department performance summary to coordinator"""
        coord_emails = self.get_department_coordinators(department_id)
        department = Department.query.get(department_id)
        
        if not coord_emails or not department:
            return False
        
        context = {
            'department': department,
            'period': period,
            'metrics': metrics,
            'student_metrics': {
                'total_students': metrics.get('total_students', 0),
                'active_students': metrics.get('active_students', 0),
                'attendance_rate': metrics.get('avg_attendance', 0),
                'satisfaction_score': metrics.get('student_satisfaction', 0)
            },
            'tutor_metrics': {
                'total_tutors': metrics.get('total_tutors', 0),
                'active_tutors': metrics.get('active_tutors', 0),
                'average_rating': metrics.get('avg_tutor_rating', 0),
                'compliance_rate': metrics.get('compliance_rate', 0)
            },
            'class_metrics': {
                'total_classes': metrics.get('total_classes', 0),
                'completed_classes': metrics.get('completed_classes', 0),
                'completion_rate': metrics.get('completion_rate', 0),
                'reschedule_rate': metrics.get('reschedule_rate', 0)
            },
            'trends': metrics.get('trends', {}),
            'recommendations': metrics.get('recommendations', [])
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"Department Performance Summary - {department.name} | {period}",
            template='coordinator/performance_summary.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
    
    def send_class_scheduling_conflict_alert(self, conflicts: List[Dict[str, Any]], department_id: int):
        """Send class scheduling conflict alert"""
        coord_emails = self.get_department_coordinators(department_id)
        department = Department.query.get(department_id)
        
        if not coord_emails or not conflicts:
            return False
        
        context = {
            'department': department,
            'conflicts': conflicts,
            'total_conflicts': len(conflicts),
            'critical_conflicts': len([c for c in conflicts if c.get('severity') == 'Critical']),
            'resolution_deadline': datetime.now() + timedelta(hours=4),
            'suggested_actions': [
                "Review conflicting schedules immediately",
                "Contact affected tutors and students",
                "Reschedule or reassign classes",
                "Update availability settings"
            ]
        }
        
        return self.send_email(
            recipients=coord_emails,
            subject=f"Scheduling Conflicts Detected - {len(conflicts)} Conflicts in {department.name}",
            template='coordinator/scheduling_conflicts.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    # ============ HELPER METHODS ============
    
    def _calculate_risk_score(self, risk_factors: Dict[str, Any]) -> int:
        """Calculate student risk score (0-100)"""
        score = 0
        
        # Attendance factor (40 points)
        attendance = risk_factors.get('attendance_percentage', 100)
        if attendance < 50:
            score += 40
        elif attendance < 70:
            score += 25
        elif attendance < 80:
            score += 10
        
        # Payment factor (30 points)
        payment_status = risk_factors.get('payment_status', 'current')
        if payment_status == 'overdue':
            score += 30
        elif payment_status == 'partial':
            score += 15
        
        # Performance factor (20 points)
        performance = risk_factors.get('performance_score', 100)
        if performance < 50:
            score += 20
        elif performance < 70:
            score += 12
        elif performance < 80:
            score += 5
        
        # Engagement factor (10 points)
        engagement = risk_factors.get('engagement_level', 'high')
        if engagement == 'low':
            score += 10
        elif engagement == 'medium':
            score += 5
        
        return min(100, score)
    
    def _get_risk_level(self, score: int) -> str:
        """Get risk level based on score"""
        if score >= 80:
            return "Critical"
        elif score >= 60:
            return "High"
        elif score >= 40:
            return "Medium"
        else:
            return "Low"
    
    def _get_risk_intervention_actions(self, risk_factors: Dict[str, Any]) -> List[str]:
        """Get recommended intervention actions"""
        actions = []
        
        if risk_factors.get('attendance_percentage', 100) < 70:
            actions.extend([
                "Schedule immediate attendance counseling",
                "Review class timing preferences",
                "Contact parents for support"
            ])
        
        if risk_factors.get('payment_status') == 'overdue':
            actions.extend([
                "Follow up on pending payments",
                "Discuss payment plan options",
                "Consider temporary class suspension"
            ])
        
        if risk_factors.get('performance_score', 100) < 70:
            actions.extend([
                "Assign additional tutoring support",
                "Review learning methodology",
                "Consider subject-specific intervention"
            ])
        
        return actions or ["Monitor closely and provide support"]
    
    def _calculate_performance_severity(self, issues: Dict[str, Any]) -> str:
        """Calculate performance issue severity"""
        score = 0
        
        if issues.get('rating', 5) < 3:
            score += 30
        elif issues.get('rating', 5) < 4:
            score += 15
        
        if issues.get('student_complaints', 0) > 3:
            score += 25
        elif issues.get('student_complaints', 0) > 1:
            score += 10
        
        if issues.get('attendance_issues', False):
            score += 20
        
        if issues.get('video_compliance', 100) < 80:
            score += 15
        
        if score >= 60:
            return "Critical"
        elif score >= 40:
            return "High"
        elif score >= 20:
            return "Medium"
        else:
            return "Low"
    
    def _get_performance_improvement_actions(self, severity: str) -> List[str]:
        """Get performance improvement actions based on severity"""
        actions_map = {
            'Critical': [
                "Immediate review meeting required",
                "Suspend new class assignments",
                "Implement intensive monitoring",
                "Consider probationary period"
            ],
            'High': [
                "Schedule performance review meeting",
                "Provide additional training",
                "Assign mentor for support",
                "Weekly progress monitoring"
            ],
            'Medium': [
                "Provide constructive feedback",
                "Offer skill development resources",
                "Monitor for improvement",
                "Schedule follow-up in 2 weeks"
            ],
            'Low': [
                "Document issues for tracking",
                "Provide general guidance",
                "Monitor ongoing performance"
            ]
        }
        return actions_map.get(severity, ["Provide appropriate support"])
    
    def _calculate_weekly_hours(self, availability: Dict[str, Any]) -> int:
        """Calculate total weekly available hours"""
        total_hours = 0
        for day, slots in availability.items():
            if isinstance(slots, list):
                for slot in slots:
                    if 'start' in slot and 'end' in slot:
                        # Calculate hours in slot (simplified)
                        try:
                            start_hour = int(slot['start'].split(':')[0])
                            end_hour = int(slot['end'].split(':')[0])
                            total_hours += max(0, end_hour - start_hour)
                        except:
                            pass
        return total_hours
    
    def _get_tutor_current_load(self, tutor_id: int) -> Dict[str, Any]:
        """Get tutor's current class load"""
        current_classes = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.scheduled_date >= datetime.now().date(),
            Class.status == 'scheduled'
        ).count()
        
        this_week_classes = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.scheduled_date >= datetime.now().date(),
            Class.scheduled_date <= datetime.now().date() + timedelta(days=7),
            Class.status == 'scheduled'
        ).count()
        
        return {
            'upcoming_classes': current_classes,
            'this_week_classes': this_week_classes,
            'load_status': 'High' if this_week_classes > 20 else 'Medium' if this_week_classes > 10 else 'Low'
        }
    
    def _get_availability_recommendations(self, availability_data: List[Dict]) -> List[str]:
        """Get recommendations based on availability analysis"""
        total_tutors = len(availability_data)
        high_load_tutors = len([t for t in availability_data if t.get('current_load', {}).get('load_status') == 'High'])
        low_hours_tutors = len([t for t in availability_data if t.get('weekly_hours', 0) < 20])
        
        recommendations = []
        
        if high_load_tutors / max(1, total_tutors) > 0.3:
            recommendations.append("Consider recruiting additional tutors - 30%+ have high load")
        
        if low_hours_tutors / max(1, total_tutors) > 0.4:
            recommendations.append("Encourage tutors to increase availability - 40%+ have low hours")
        
        if not recommendations:
            recommendations.append("Availability levels appear balanced")
        
        return recommendations

# Global instance
coordinator_email_service = CoordinatorEmailService()