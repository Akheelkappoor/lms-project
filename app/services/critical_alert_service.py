"""
Critical Alert Service - High-priority and emergency email notifications
Handles immediate alerts, emergency notifications, and critical system events
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.services.comprehensive_email_service import ComprehensiveEmailService, EmailPriority, EmailType
from app.models.user import User
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.department import Department
from app.models.escalation import Escalation
from sqlalchemy import and_, or_, func
from app import db
import json

class CriticalAlertService(ComprehensiveEmailService):
    """Service for critical alerts and emergency notifications"""
    
    # ============ EMERGENCY STUDENT ALERTS ============
    
    def send_student_emergency_contact_alert(self, student_id: int, emergency_data: Dict[str, Any]) -> bool:
        """Send emergency alert to student's emergency contacts"""
        student = Student.query.get(student_id)
        if not student:
            return False
        
        # Get emergency contacts
        emergency_contacts = []
        parent_details = student.get_parent_details()
        
        if parent_details:
            # Primary contacts (parents)
            if parent_details.get('father', {}).get('phone'):
                emergency_contacts.append({
                    'name': parent_details['father'].get('name', 'Father'),
                    'email': parent_details['father'].get('email'),
                    'phone': parent_details['father']['phone'],
                    'relation': 'Father'
                })
            
            if parent_details.get('mother', {}).get('phone'):
                emergency_contacts.append({
                    'name': parent_details['mother'].get('name', 'Mother'),
                    'email': parent_details['mother'].get('email'),
                    'phone': parent_details['mother']['phone'],
                    'relation': 'Mother'
                })
            
            # Additional emergency contacts
            if parent_details.get('emergency_contact'):
                emergency_contacts.append({
                    'name': parent_details['emergency_contact'].get('name', 'Emergency Contact'),
                    'email': parent_details['emergency_contact'].get('email'),
                    'phone': parent_details['emergency_contact'].get('phone'),
                    'relation': parent_details['emergency_contact'].get('relation', 'Guardian')
                })
        
        # Get emails for notification
        recipient_emails = [contact['email'] for contact in emergency_contacts if contact.get('email')]
        
        if not recipient_emails:
            return False
        
        # Add coordinators and admins to emergency loop
        coord_emails = self.get_department_coordinators(student.department_id)
        admin_emails = self.get_admin_emails('superadmin')
        
        context = {
            'student': student,
            'emergency_data': emergency_data,
            'emergency_type': emergency_data.get('type', 'unknown'),
            'severity': emergency_data.get('severity', 'high'),
            'reported_by': emergency_data.get('reported_by', 'system'),
            'report_time': datetime.now(),
            'emergency_contacts': emergency_contacts,
            'immediate_actions': [
                "Contact student immediately",
                "Verify student safety and wellbeing",
                "Contact school/college if applicable",
                "Coordinate with medical services if needed",
                "Keep LMS coordinators informed"
            ],
            'contact_numbers': {
                'coordinator': coord_emails[0] if coord_emails else None,
                'emergency_services': '911',
                'lms_emergency': emergency_data.get('lms_contact', '+1-XXX-XXX-XXXX')
            }
        }
        
        return self.send_email(
            recipients=recipient_emails,
            cc=coord_emails,
            bcc=admin_emails,
            subject=f"EMERGENCY ALERT - {student.full_name} | {emergency_data.get('type', 'Unknown Emergency').upper()}",
            template='alerts/student_emergency_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    def send_student_safety_concern_alert(self, student_id: int, concern_data: Dict[str, Any]) -> bool:
        """Send safety concern alert for student welfare"""
        student = Student.query.get(student_id)
        if not student:
            return False
        
        # Get stakeholders
        coord_emails = self.get_department_coordinators(student.department_id)
        admin_emails = self.get_admin_emails('superadmin')
        counselor_emails = self.get_admin_emails('admin')  # Assuming counselors have admin role
        
        # Get parent emails for notification
        parent_emails = []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                parent_emails.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                parent_emails.append(parent_details['mother']['email'])
        
        context = {
            'student': student,
            'concern_data': concern_data,
            'concern_type': concern_data.get('type', 'welfare'),
            'risk_level': concern_data.get('risk_level', 'medium'),
            'reported_by': concern_data.get('reported_by'),
            'report_date': datetime.now(),
            'observations': concern_data.get('observations', []),
            'recommended_actions': [
                "Schedule immediate welfare check",
                "Contact student for direct conversation",
                "Involve counseling services if needed",
                "Monitor student closely",
                "Document all interactions",
                "Escalate to authorities if required"
            ],
            'escalation_timeline': "Within 2 hours for high risk, 24 hours for medium risk",
            'support_resources': [
                "Student counseling services",
                "Mental health helplines",
                "Academic support programs",
                "Financial assistance programs"
            ]
        }
        
        # Determine recipients based on risk level
        recipients = coord_emails + admin_emails
        if concern_data.get('risk_level') == 'high':
            recipients.extend(parent_emails)  # Include parents for high-risk concerns
        
        cc_recipients = counselor_emails if concern_data.get('risk_level') in ['high', 'critical'] else []
        
        return self.send_email(
            recipients=recipients,
            cc=cc_recipients,
            subject=f"Safety Concern Alert - {student.full_name} | Risk Level: {concern_data.get('risk_level', 'Medium').upper()}",
            template='alerts/student_safety_concern.html',
            context=context,
            priority=EmailPriority.IMMEDIATE if concern_data.get('risk_level') == 'critical' else EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    def send_attendance_crisis_alert(self, student_id: int) -> bool:
        """Send critical alert for extremely low attendance (below 50%)"""
        student = Student.query.get(student_id)
        if not student:
            return False
        
        attendance_percentage = student.get_attendance_percentage()
        if attendance_percentage >= 50:
            return False  # Not critical enough
        
        # Get all stakeholders
        coord_emails = self.get_department_coordinators(student.department_id)
        admin_emails = self.get_admin_emails('superadmin')
        
        # Get parent emails
        parent_emails = []
        parent_details = student.get_parent_details()
        if parent_details:
            if parent_details.get('father', {}).get('email'):
                parent_emails.append(parent_details['father']['email'])
            if parent_details.get('mother', {}).get('email'):
                parent_emails.append(parent_details['mother']['email'])
        
        # Get tutor emails
        tutor_emails = self._get_student_tutor_emails(student_id)
        
        # Calculate attendance crisis metrics
        total_classes = student.total_classes or 0
        attended_classes = student.attended_classes or 0
        missed_classes = total_classes - attended_classes
        
        # Recent attendance pattern (last 2 weeks)
        recent_classes = Class.query.filter(
            or_(
                Class.primary_student_id == student_id,
                Class.students.like(f'%{student_id}%')
            ),
            Class.scheduled_date >= datetime.now().date() - timedelta(days=14),
            Class.status.in_(['completed', 'missed'])
        ).count()
        
        recent_attended = Attendance.query.join(Class).filter(
            Attendance.student_id == student_id,
            Attendance.is_present == True,
            Class.scheduled_date >= datetime.now().date() - timedelta(days=14)
        ).count()
        
        recent_attendance_rate = (recent_attended / max(1, recent_classes)) * 100
        
        context = {
            'student': student,
            'attendance_percentage': attendance_percentage,
            'total_classes': total_classes,
            'attended_classes': attended_classes,
            'missed_classes': missed_classes,
            'recent_attendance_rate': recent_attendance_rate,
            'crisis_level': 'Critical' if attendance_percentage < 30 else 'Severe',
            'intervention_required': True,
            'immediate_actions': [
                "Contact student and parents immediately",
                "Schedule emergency intervention meeting",
                "Suspend new class assignments temporarily",
                "Implement intensive monitoring",
                "Consider academic probation",
                "Evaluate continuation of enrollment"
            ],
            'consequences': [
                f"Current attendance: {attendance_percentage:.1f}% (Minimum required: 75%)",
                "Risk of course failure",
                "Possible enrollment termination",
                "Impact on academic progression",
                "Financial implications"
            ],
            'recovery_plan': {
                'target_attendance': 85,
                'classes_needed': max(0, int((total_classes * 0.75) - attended_classes)),
                'timeline': "Immediate improvement required",
                'support_available': [
                    "Flexible scheduling options",
                    "Makeup class arrangements",
                    "Academic counseling",
                    "Study support programs"
                ]
            }
        }
        
        return self.send_email(
            recipients=parent_emails + coord_emails,
            cc=admin_emails + tutor_emails,
            subject=f"ATTENDANCE CRISIS ALERT - {student.full_name} | {attendance_percentage:.1f}% Attendance",
            template='alerts/attendance_crisis_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    # ============ TUTOR EMERGENCY ALERTS ============
    
    def send_tutor_no_show_critical_alert(self, tutor_id: int, class_id: int, impact_data: Dict[str, Any]) -> bool:
        """Send critical alert when tutor doesn't show up for class"""
        tutor = Tutor.query.get(tutor_id)
        class_obj = Class.query.get(class_id)
        
        if not tutor or not class_obj or not tutor.user:
            return False
        
        # Get affected students
        affected_students = []
        if class_obj.primary_student_id:
            student = Student.query.get(class_obj.primary_student_id)
            if student:
                affected_students.append(student)
        
        if class_obj.students:
            student_ids = class_obj.get_students()
            for student_id in student_ids:
                student = Student.query.get(student_id)
                if student and student.id != class_obj.primary_student_id:
                    affected_students.append(student)
        
        # Get stakeholders
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        admin_emails = self.get_admin_emails('superadmin')
        hr_emails = self.get_admin_emails('admin')
        
        # Get parent emails for affected students
        parent_emails = []
        for student in affected_students:
            parent_details = student.get_parent_details()
            if parent_details:
                if parent_details.get('father', {}).get('email'):
                    parent_emails.append(parent_details['father']['email'])
                if parent_details.get('mother', {}).get('email'):
                    parent_emails.append(parent_details['mother']['email'])
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'class': class_obj,
            'affected_students': affected_students,
            'student_count': len(affected_students),
            'no_show_time': datetime.now(),
            'impact_data': impact_data,
            'severity': 'Critical' if len(affected_students) > 3 else 'High',
            'immediate_actions': [
                "Contact tutor immediately via all available channels",
                "Arrange emergency substitute tutor if possible",
                "Inform affected students and parents",
                "Document incident for performance review",
                "Consider disciplinary action",
                "Review tutor reliability patterns"
            ],
            'student_compensation': [
                "Arrange makeup class immediately",
                "Provide alternative learning resources",
                "Extend course duration if needed",
                "Consider fee adjustment if pattern continues"
            ],
            'escalation_required': True,
            'follow_up_deadline': datetime.now() + timedelta(hours=2)
        }
        
        return self.send_email(
            recipients=coord_emails + admin_emails,
            cc=hr_emails + parent_emails,
            subject=f"CRITICAL: Tutor No-Show - {tutor.user.full_name} | {len(affected_students)} Students Affected",
            template='alerts/tutor_no_show_critical.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    def send_tutor_performance_crisis_alert(self, tutor_id: int, crisis_data: Dict[str, Any]) -> bool:
        """Send alert for severe tutor performance issues"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
        
        # Get stakeholders
        coord_emails = self.get_department_coordinators(tutor.user.department_id)
        admin_emails = self.get_admin_emails('superadmin')
        hr_emails = self.get_admin_emails('admin')
        
        crisis_score = self._calculate_crisis_score(crisis_data)
        crisis_level = self._get_crisis_level(crisis_score)
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'crisis_data': crisis_data,
            'crisis_score': crisis_score,
            'crisis_level': crisis_level,
            'performance_issues': crisis_data.get('issues', []),
            'affected_students': crisis_data.get('affected_students', []),
            'complaint_count': crisis_data.get('complaint_count', 0),
            'rating_drop': crisis_data.get('rating_drop', 0),
            'immediate_actions': [
                "Suspend tutor from new class assignments",
                "Schedule emergency performance review",
                "Contact affected students and parents",
                "Arrange alternative tutors immediately",
                "Implement intensive monitoring",
                "Consider probationary measures"
            ],
            'investigation_required': True,
            'escalation_timeline': "Within 4 hours",
            'potential_consequences': [
                "Temporary suspension",
                "Mandatory retraining",
                "Probationary period",
                "Contract termination if severe"
            ]
        }
        
        recipients = coord_emails + admin_emails
        if crisis_level == 'Critical':
            recipients.extend(hr_emails)
        
        return self.send_email(
            recipients=recipients,
            subject=f"PERFORMANCE CRISIS - {tutor.user.full_name} | Level: {crisis_level}",
            template='alerts/tutor_performance_crisis.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    # ============ SYSTEM EMERGENCY ALERTS ============
    
    def send_system_outage_alert(self, outage_data: Dict[str, Any]) -> bool:
        """Send system outage alert to all stakeholders"""
        
        # Get all stakeholder emails
        admin_emails = self.get_admin_emails('superadmin')
        tech_emails = self.get_admin_emails('admin')
        coord_emails = []
        
        departments = Department.query.filter_by(is_active=True).all()
        for dept in departments:
            coord_emails.extend(self.get_department_coordinators(dept.id))
        
        context = {
            'outage_data': outage_data,
            'outage_type': outage_data.get('type', 'system'),
            'severity': outage_data.get('severity', 'high'),
            'start_time': outage_data.get('start_time', datetime.now()),
            'affected_services': outage_data.get('affected_services', []),
            'user_impact': outage_data.get('user_impact', 'high'),
            'estimated_resolution': outage_data.get('estimated_resolution', 'investigating'),
            'immediate_actions': [
                "All technical team to respond immediately",
                "Activate disaster recovery protocols",
                "Communicate with affected users",
                "Monitor system recovery progress",
                "Document incident for post-mortem"
            ],
            'communication_plan': {
                'user_notification': 'Immediate via all channels',
                'update_frequency': 'Every 30 minutes',
                'resolution_notification': 'As soon as resolved'
            },
            'escalation_contacts': tech_emails
        }
        
        # Send to technical team immediately
        tech_success = self.send_email(
            recipients=tech_emails,
            cc=admin_emails,
            subject=f"SYSTEM OUTAGE - {outage_data.get('type', 'Unknown').upper()} | Severity: {outage_data.get('severity', 'High').upper()}",
            template='alerts/system_outage_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
        
        # Send to coordinators with different template
        coord_context = context.copy()
        coord_context['coordinator_actions'] = [
            "Inform students about service disruption",
            "Reschedule classes if necessary",
            "Provide alternative communication channels",
            "Monitor for updates from technical team"
        ]
        
        coord_success = self.send_email(
            recipients=coord_emails,
            subject=f"Service Disruption Alert - {outage_data.get('type', 'System')} Outage",
            template='alerts/system_outage_coordinator.html',
            context=coord_context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
        
        return tech_success and coord_success
    
    def send_data_breach_alert(self, breach_data: Dict[str, Any]) -> bool:
        """Send critical data breach alert"""
        
        # Get highest level stakeholders
        admin_emails = self.get_admin_emails('superadmin')
        
        context = {
            'breach_data': breach_data,
            'breach_type': breach_data.get('type', 'unknown'),
            'severity': breach_data.get('severity', 'critical'),
            'detection_time': datetime.now(),
            'affected_records': breach_data.get('affected_records', 'unknown'),
            'data_types_affected': breach_data.get('data_types', []),
            'breach_vector': breach_data.get('vector', 'under investigation'),
            'immediate_actions': [
                "Isolate affected systems immediately",
                "Activate incident response team",
                "Preserve forensic evidence",
                "Notify legal and compliance teams",
                "Prepare user notification plan",
                "Contact cybersecurity experts"
            ],
            'legal_requirements': [
                "Regulatory notification within 72 hours",
                "User notification as required by law",
                "Law enforcement notification if applicable",
                "Documentation for compliance audit"
            ],
            'containment_status': breach_data.get('containment_status', 'in progress'),
            'next_update': datetime.now() + timedelta(hours=1)
        }
        
        return self.send_email(
            recipients=admin_emails,
            subject=f"CRITICAL DATA BREACH ALERT - {breach_data.get('type', 'Unknown').upper()}",
            template='alerts/data_breach_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    def send_financial_fraud_alert(self, fraud_data: Dict[str, Any]) -> bool:
        """Send financial fraud detection alert"""
        
        admin_emails = self.get_admin_emails('superadmin')
        finance_emails = self.get_admin_emails('admin')
        
        context = {
            'fraud_data': fraud_data,
            'fraud_type': fraud_data.get('type', 'payment'),
            'amount_involved': fraud_data.get('amount', 0),
            'accounts_affected': fraud_data.get('accounts', []),
            'detection_method': fraud_data.get('detection_method', 'automated'),
            'risk_level': fraud_data.get('risk_level', 'high'),
            'detection_time': datetime.now(),
            'immediate_actions': [
                "Freeze affected accounts immediately",
                "Block suspicious transactions",
                "Notify affected users",
                "Contact financial institutions",
                "Preserve transaction evidence",
                "Report to authorities if required"
            ],
            'investigation_steps': [
                "Review transaction logs",
                "Analyze fraud patterns",
                "Interview affected parties",
                "Coordinate with payment processors",
                "Implement additional security measures"
            ],
            'prevention_measures': fraud_data.get('prevention_recommendations', [])
        }
        
        return self.send_email(
            recipients=admin_emails + finance_emails,
            subject=f"FINANCIAL FRAUD ALERT - ₹{fraud_data.get('amount', 0):,.2f} | {fraud_data.get('type', 'Payment').title()} Fraud",
            template='alerts/financial_fraud_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    # ============ MASS NOTIFICATION ALERTS ============
    
    def send_emergency_mass_notification(self, emergency_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send emergency notification to all users"""
        
        # Get all active user emails
        all_users = User.query.filter_by(is_active=True).all()
        user_emails = [user.email for user in all_users if user.email]
        
        # Get parent emails
        parent_emails = []
        active_students = Student.query.filter_by(is_active=True).all()
        for student in active_students:
            parent_details = student.get_parent_details()
            if parent_details:
                if parent_details.get('father', {}).get('email'):
                    parent_emails.append(parent_details['father']['email'])
                if parent_details.get('mother', {}).get('email'):
                    parent_emails.append(parent_details['mother']['email'])
        
        all_recipients = list(set(user_emails + parent_emails))
        
        context = {
            'emergency_data': emergency_data,
            'emergency_type': emergency_data.get('type', 'general'),
            'severity': emergency_data.get('severity', 'high'),
            'message': emergency_data.get('message', ''),
            'instructions': emergency_data.get('instructions', []),
            'contact_info': emergency_data.get('contact_info', {}),
            'effective_immediately': emergency_data.get('immediate', True),
            'duration': emergency_data.get('duration', 'until further notice')
        }
        
        # Send in batches
        batch_size = 100
        results = {
            'total_recipients': len(all_recipients),
            'batches_sent': 0,
            'successful_sends': 0,
            'failed_sends': 0
        }
        
        for i in range(0, len(all_recipients), batch_size):
            batch = all_recipients[i:i + batch_size]
            
            try:
                success = self.send_email(
                    recipients=[],  # Empty recipients
                    bcc=batch,     # Use BCC for mass sending
                    subject=f"EMERGENCY NOTIFICATION - {emergency_data.get('type', 'Important Update').upper()}",
                    template='alerts/emergency_mass_notification.html',
                    context=context,
                    priority=EmailPriority.IMMEDIATE,
                    email_type=EmailType.ALERT
                )
                
                if success:
                    results['successful_sends'] += len(batch)
                    results['batches_sent'] += 1
                else:
                    results['failed_sends'] += len(batch)
                    
            except Exception as e:
                self.logger.error(f"Error sending emergency notification batch {i//batch_size + 1}: {str(e)}")
                results['failed_sends'] += len(batch)
        
        return results
    
    # ============ HELPER METHODS ============
    
    def _calculate_crisis_score(self, crisis_data: Dict[str, Any]) -> int:
        """Calculate crisis severity score (0-100)"""
        score = 0
        
        # Rating drop (30 points)
        rating_drop = crisis_data.get('rating_drop', 0)
        if rating_drop > 1.5:
            score += 30
        elif rating_drop > 1.0:
            score += 20
        elif rating_drop > 0.5:
            score += 10
        
        # Complaint count (25 points)
        complaints = crisis_data.get('complaint_count', 0)
        if complaints > 5:
            score += 25
        elif complaints > 3:
            score += 15
        elif complaints > 1:
            score += 8
        
        # Student impact (25 points)
        affected_students = len(crisis_data.get('affected_students', []))
        if affected_students > 10:
            score += 25
        elif affected_students > 5:
            score += 15
        elif affected_students > 2:
            score += 8
        
        # Performance issues (20 points)
        issues = crisis_data.get('issues', [])
        critical_issues = len([issue for issue in issues if issue.get('severity') == 'critical'])
        if critical_issues > 2:
            score += 20
        elif critical_issues > 0:
            score += 12
        elif len(issues) > 3:
            score += 8
        
        return min(100, score)
    
    def _get_crisis_level(self, score: int) -> str:
        """Get crisis level based on score"""
        if score >= 80:
            return "Critical"
        elif score >= 60:
            return "Severe"
        elif score >= 40:
            return "High"
        elif score >= 20:
            return "Medium"
        else:
            return "Low"

# Global instance
critical_alert_service = CriticalAlertService()