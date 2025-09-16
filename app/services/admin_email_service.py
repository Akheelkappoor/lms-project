"""
Admin Email Service - All admin and super admin email notifications
Extends the comprehensive email service for admin-specific functions
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
from sqlalchemy import and_, or_, func, text
import json

class AdminEmailService(ComprehensiveEmailService):
    """Extended email service for all admin and super admin notifications"""
    
    # ============ FINANCIAL OVERSIGHT ============
    
    def send_monthly_finance_summary(self, month: str, year: int, financial_data: Dict[str, Any]):
        """Send monthly financial summary to super admin and finance team"""
        admin_emails = self.get_admin_emails('superadmin')
        finance_emails = self.get_admin_emails('admin')  # Finance team typically has admin role
        
        context = {
            'month': month,
            'year': year,
            'financial_data': financial_data,
            'revenue': {
                'total_revenue': financial_data.get('total_revenue', 0),
                'student_fees': financial_data.get('student_fees', 0),
                'demo_conversions': financial_data.get('demo_revenue', 0),
                'other_income': financial_data.get('other_income', 0)
            },
            'expenses': {
                'tutor_payouts': financial_data.get('tutor_payouts', 0),
                'operational_costs': financial_data.get('operational_costs', 0),
                'marketing_spend': financial_data.get('marketing_spend', 0),
                'platform_costs': financial_data.get('platform_costs', 0)
            },
            'metrics': {
                'gross_profit': financial_data.get('gross_profit', 0),
                'profit_margin': financial_data.get('profit_margin', 0),
                'growth_rate': financial_data.get('growth_rate', 0),
                'student_ltv': financial_data.get('student_ltv', 0)
            },
            'outstanding_amounts': {
                'pending_student_fees': financial_data.get('pending_fees', 0),
                'pending_tutor_payouts': financial_data.get('pending_payouts', 0)
            },
            'trends': financial_data.get('trends', {}),
            'recommendations': financial_data.get('recommendations', [])
        }
        
        return self.send_email(
            recipients=admin_emails,
            cc=finance_emails,
            subject=f"Monthly Finance Summary - {month} {year} | Revenue: ₹{financial_data.get('total_revenue', 0):,.2f}",
            template='admin/monthly_finance_summary.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.REPORT
        )
    
    def send_payment_anomaly_alert(self, anomaly_data: Dict[str, Any]):
        """Send payment anomaly alert for unusual patterns"""
        admin_emails = self.get_admin_emails('superadmin')
        finance_emails = self.get_admin_emails('admin')
        
        severity = anomaly_data.get('severity', 'medium')
        
        context = {
            'anomaly': anomaly_data,
            'detection_time': datetime.now(),
            'anomaly_type': anomaly_data.get('type', 'unknown'),
            'affected_accounts': anomaly_data.get('affected_accounts', []),
            'financial_impact': anomaly_data.get('financial_impact', 0),
            'risk_level': severity,
            'immediate_actions': [
                "Investigate affected transactions",
                "Contact involved parties",
                "Freeze suspicious accounts if necessary",
                "Document findings for audit trail"
            ],
            'investigation_deadline': datetime.now() + timedelta(hours=4)
        }
        
        return self.send_email(
            recipients=admin_emails + finance_emails,
            subject=f"Payment Anomaly Detected - {anomaly_data.get('type', 'Unknown')} | Risk: {severity.title()}",
            template='admin/payment_anomaly_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE if severity == 'critical' else EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    def send_revenue_milestone_notification(self, milestone_data: Dict[str, Any]):
        """Send revenue milestone achievement notification"""
        admin_emails = self.get_admin_emails('superadmin')
        all_admin_emails = self.get_admin_emails()
        
        context = {
            'milestone': milestone_data,
            'achievement_date': datetime.now(),
            'milestone_amount': milestone_data.get('amount', 0),
            'previous_milestone': milestone_data.get('previous_amount', 0),
            'growth_percentage': milestone_data.get('growth_percentage', 0),
            'time_to_achieve': milestone_data.get('time_to_achieve', 'N/A'),
            'contributing_factors': milestone_data.get('factors', []),
            'next_target': milestone_data.get('next_target', 0)
        }
        
        return self.send_email(
            recipients=admin_emails,
            cc=all_admin_emails,
            subject=f"Revenue Milestone Achieved - ₹{milestone_data.get('amount', 0):,.2f}! 🎉",
            template='admin/revenue_milestone.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
    
    # ============ USER MANAGEMENT OVERSIGHT ============
    
    def send_tutor_onboarding_approval_request(self, tutor_id: int):
        """Send tutor onboarding approval request to super admin"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor or not tutor.user:
            return False
            
        admin_emails = self.get_admin_emails('superadmin')
        hr_emails = self.get_admin_emails('admin')
        
        # Get verification status and documents
        verification_data = {
            'documents_verified': tutor.verification_status == 'approved',
            'background_check': tutor.background_check_status,
            'references_checked': tutor.references_verified,
            'interview_completed': tutor.interview_status == 'completed'
        }
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'department': tutor.user.department,
            'application_date': tutor.created_at,
            'verification_data': verification_data,
            'qualifications': {
                'education': tutor.education_qualification,
                'experience': tutor.experience_years,
                'subjects': tutor.get_subjects_taught(),
                'certifications': tutor.certifications
            },
            'approval_checklist': [
                "Verify all documents are authentic",
                "Confirm educational qualifications",
                "Review teaching experience",
                "Check background verification",
                "Approve or request additional information"
            ],
            'approval_url': f"/admin/tutors/{tutor_id}/approve"
        }
        
        return self.send_email(
            recipients=admin_emails,
            cc=hr_emails,
            subject=f"Tutor Approval Required - {tutor.user.full_name} | {tutor.user.department.name if tutor.user.department else 'No Dept'}",
            template='admin/tutor_approval_request.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    def send_student_onboarding_approval_request(self, student_id: int):
        """Send high-value student onboarding approval to super admin"""
        student = Student.query.get(student_id)
        if not student:
            return False
            
        fee_structure = student.get_fee_structure()
        total_fee = fee_structure.get('total_fee', 0)
        
        # Only send for high-value students (>50k fees)
        if total_fee < 50000:
            return False
            
        admin_emails = self.get_admin_emails('superadmin')
        coord_emails = self.get_department_coordinators(student.department_id)
        
        context = {
            'student': student,
            'department': student.department,
            'fee_structure': fee_structure,
            'total_fee': total_fee,
            'parent_details': student.get_parent_details(),
            'registration_date': student.created_at,
            'high_value_indicators': [
                f"Total fee: ₹{total_fee:,.2f}",
                f"Course duration: {student.course_duration_months} months",
                f"Subjects enrolled: {len(student.get_subjects_enrolled())}",
                f"Grade: {student.grade} {student.board}"
            ],
            'approval_checklist': [
                "Verify student eligibility",
                "Confirm fee payment capacity",
                "Review parent/guardian details",
                "Ensure proper documentation",
                "Approve fee structure"
            ],
            'approval_url': f"/admin/students/{student_id}/approve"
        }
        
        return self.send_email(
            recipients=admin_emails,
            cc=coord_emails,
            subject=f"High-Value Student Approval - {student.full_name} | Fee: ₹{total_fee:,.2f}",
            template='admin/student_approval_request.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ADMINISTRATIVE
        )
    
    def send_bulk_user_operation_summary(self, operation_data: Dict[str, Any]):
        """Send bulk operation summary to super admin"""
        admin_emails = self.get_admin_emails('superadmin')
        
        context = {
            'operation': operation_data,
            'operation_type': operation_data.get('type', 'unknown'),
            'total_records': operation_data.get('total_records', 0),
            'successful': operation_data.get('successful', 0),
            'failed': operation_data.get('failed', 0),
            'success_rate': (operation_data.get('successful', 0) / max(1, operation_data.get('total_records', 1))) * 100,
            'execution_time': operation_data.get('execution_time', 'N/A'),
            'errors': operation_data.get('errors', []),
            'affected_departments': operation_data.get('affected_departments', []),
            'performed_by': operation_data.get('performed_by', 'System'),
            'completion_time': datetime.now()
        }
        
        return self.send_email(
            recipients=admin_emails,
            subject=f"Bulk Operation Completed - {operation_data.get('type', 'Unknown')} | {operation_data.get('successful', 0)}/{operation_data.get('total_records', 0)} Success",
            template='admin/bulk_operation_summary.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
    
    # ============ SYSTEM OPERATIONS ============
    
    def send_system_health_report(self, report_type: str, health_data: Dict[str, Any]):
        """Send daily/weekly system health report"""
        admin_emails = self.get_admin_emails('superadmin')
        tech_emails = self.get_admin_emails('admin')  # Technical team
        
        # Calculate overall health score
        health_score = self._calculate_system_health_score(health_data)
        health_status = self._get_health_status(health_score)
        
        context = {
            'report_type': report_type,
            'health_data': health_data,
            'health_score': health_score,
            'health_status': health_status,
            'system_metrics': {
                'uptime': health_data.get('uptime_percentage', 0),
                'response_time': health_data.get('avg_response_time', 0),
                'error_rate': health_data.get('error_rate', 0),
                'database_performance': health_data.get('db_performance', 0)
            },
            'user_metrics': {
                'active_users': health_data.get('active_users', 0),
                'concurrent_sessions': health_data.get('concurrent_sessions', 0),
                'login_success_rate': health_data.get('login_success_rate', 0)
            },
            'class_metrics': {
                'classes_conducted': health_data.get('classes_conducted', 0),
                'video_upload_rate': health_data.get('video_upload_rate', 0),
                'attendance_marking_rate': health_data.get('attendance_rate', 0)
            },
            'alerts': health_data.get('alerts', []),
            'recommendations': health_data.get('recommendations', []),
            'next_maintenance': health_data.get('next_maintenance', None)
        }
        
        priority = EmailPriority.HIGH if health_score < 80 else EmailPriority.MEDIUM
        
        return self.send_email(
            recipients=admin_emails,
            cc=tech_emails,
            subject=f"{report_type.title()} System Health Report | Status: {health_status} ({health_score}%)",
            template='admin/system_health_report.html',
            context=context,
            priority=priority,
            email_type=EmailType.REPORT
        )
    
    def send_critical_system_alert(self, alert_data: Dict[str, Any]):
        """Send critical system alert for immediate attention"""
        admin_emails = self.get_admin_emails('superadmin')
        tech_emails = self.get_admin_emails('admin')
        
        alert_type = alert_data.get('type', 'unknown')
        severity = alert_data.get('severity', 'high')
        
        context = {
            'alert': alert_data,
            'alert_type': alert_type,
            'severity': severity,
            'affected_systems': alert_data.get('affected_systems', []),
            'user_impact': alert_data.get('user_impact', 'unknown'),
            'detection_time': datetime.now(),
            'estimated_resolution': alert_data.get('estimated_resolution', 'investigating'),
            'immediate_actions': [
                "Acknowledge alert immediately",
                "Assess system status",
                "Implement emergency measures if needed",
                "Communicate with affected users",
                "Begin resolution process"
            ],
            'escalation_contacts': tech_emails
        }
        
        return self.send_email(
            recipients=admin_emails + tech_emails,
            subject=f"CRITICAL SYSTEM ALERT - {alert_type.upper()} | Severity: {severity.upper()}",
            template='admin/critical_system_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    def send_security_incident_report(self, incident_data: Dict[str, Any]):
        """Send security incident report to super admin"""
        admin_emails = self.get_admin_emails('superadmin')
        
        context = {
            'incident': incident_data,
            'incident_type': incident_data.get('type', 'unknown'),
            'severity': incident_data.get('severity', 'medium'),
            'detection_time': datetime.now(),
            'affected_accounts': incident_data.get('affected_accounts', []),
            'potential_impact': incident_data.get('potential_impact', 'under assessment'),
            'containment_status': incident_data.get('containment_status', 'in progress'),
            'investigation_findings': incident_data.get('findings', []),
            'response_actions': [
                "Secure affected systems immediately",
                "Notify affected users if required",
                "Document incident details",
                "Implement additional security measures",
                "Review security protocols"
            ],
            'follow_up_required': incident_data.get('follow_up_required', True)
        }
        
        return self.send_email(
            recipients=admin_emails,
            subject=f"Security Incident Report - {incident_data.get('type', 'Unknown')} | {incident_data.get('severity', 'Medium').title()} Severity",
            template='admin/security_incident_report.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    # ============ ESCALATION MANAGEMENT ============
    
    def send_critical_escalation_alert(self, escalation_id: int):
        """Send critical escalation alert to super admin"""
        escalation = Escalation.query.get(escalation_id)
        if not escalation or escalation.priority != 'Critical':
            return False
            
        admin_emails = self.get_admin_emails('superadmin')
        coord_emails = self.get_department_coordinators(escalation.department_id) if escalation.department_id else []
        
        context = {
            'escalation': escalation,
            'escalation_age': (datetime.now() - escalation.created_at).total_seconds() / 3600,  # hours
            'department': escalation.department if escalation.department_id else None,
            'assigned_user': User.query.get(escalation.assigned_to) if escalation.assigned_to else None,
            'impact_assessment': {
                'user_impact': escalation.impact_level,
                'business_impact': self._assess_business_impact(escalation),
                'urgency_level': escalation.priority
            },
            'immediate_actions': [
                "Review escalation details immediately",
                "Assign appropriate resources",
                "Communicate with affected parties",
                "Set realistic resolution timeline",
                "Monitor progress hourly"
            ],
            'escalation_url': f"/admin/escalations/{escalation_id}"
        }
        
        return self.send_email(
            recipients=admin_emails,
            cc=coord_emails,
            subject=f"CRITICAL ESCALATION - {escalation.title} | {escalation.category}",
            template='admin/critical_escalation_alert.html',
            context=context,
            priority=EmailPriority.IMMEDIATE,
            email_type=EmailType.ALERT
        )
    
    def send_escalation_sla_breach_alert(self, escalation_id: int):
        """Send SLA breach alert for overdue escalations"""
        escalation = Escalation.query.get(escalation_id)
        if not escalation:
            return False
            
        admin_emails = self.get_admin_emails('superadmin')
        
        overdue_hours = (datetime.now() - escalation.due_date).total_seconds() / 3600 if escalation.due_date else 0
        
        context = {
            'escalation': escalation,
            'overdue_hours': overdue_hours,
            'original_due_date': escalation.due_date,
            'assigned_user': User.query.get(escalation.assigned_to) if escalation.assigned_to else None,
            'sla_breach_severity': 'Critical' if overdue_hours > 24 else 'High' if overdue_hours > 8 else 'Medium',
            'impact_on_sla': {
                'department_sla_impact': 'High',
                'customer_satisfaction_risk': 'Medium' if overdue_hours < 12 else 'High',
                'business_reputation_risk': 'Low' if overdue_hours < 24 else 'Medium'
            },
            'required_actions': [
                "Immediately contact assigned person",
                "Reassess resource allocation",
                "Consider escalation path",
                "Update customer communication",
                "Document reason for delay"
            ]
        }
        
        return self.send_email(
            recipients=admin_emails,
            subject=f"SLA BREACH ALERT - {escalation.title} | {overdue_hours:.1f}h Overdue",
            template='admin/sla_breach_alert.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.ALERT
        )
    
    # ============ QUALITY ASSURANCE ============
    
    def send_quality_review_alert(self, quality_data: Dict[str, Any]):
        """Send quality review alert for classes needing attention"""
        admin_emails = self.get_admin_emails('superadmin')
        quality_team_emails = self.get_admin_emails('admin')
        
        context = {
            'quality_data': quality_data,
            'review_period': quality_data.get('period', 'this week'),
            'classes_reviewed': quality_data.get('total_classes', 0),
            'quality_issues': quality_data.get('issues', []),
            'low_quality_classes': quality_data.get('low_quality_count', 0),
            'affected_tutors': quality_data.get('affected_tutors', []),
            'quality_metrics': {
                'average_rating': quality_data.get('avg_rating', 0),
                'video_quality_score': quality_data.get('video_quality', 0),
                'student_satisfaction': quality_data.get('student_satisfaction', 0),
                'completion_rate': quality_data.get('completion_rate', 0)
            },
            'improvement_actions': [
                "Review low-rated classes in detail",
                "Provide feedback to affected tutors",
                "Implement additional training if needed",
                "Monitor improvement in next review cycle"
            ]
        }
        
        return self.send_email(
            recipients=admin_emails,
            cc=quality_team_emails,
            subject=f"Quality Review Alert - {quality_data.get('low_quality_count', 0)} Classes Need Attention",
            template='admin/quality_review_alert.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.ALERT
        )
    
    # ============ HELPER METHODS ============
    
    def _calculate_system_health_score(self, health_data: Dict[str, Any]) -> int:
        """Calculate overall system health score (0-100)"""
        scores = []
        
        # Uptime (25 points)
        uptime = health_data.get('uptime_percentage', 100)
        scores.append(min(25, uptime * 0.25))
        
        # Response time (25 points)
        response_time = health_data.get('avg_response_time', 500)  # ms
        response_score = max(0, 25 - (response_time - 200) * 0.05)
        scores.append(max(0, min(25, response_score)))
        
        # Error rate (25 points)
        error_rate = health_data.get('error_rate', 0)  # percentage
        error_score = max(0, 25 - error_rate * 5)
        scores.append(max(0, min(25, error_score)))
        
        # Database performance (25 points)
        db_performance = health_data.get('db_performance', 100)
        scores.append(min(25, db_performance * 0.25))
        
        return int(sum(scores))
    
    def _get_health_status(self, score: int) -> str:
        """Get health status based on score"""
        if score >= 95:
            return "Excellent"
        elif score >= 85:
            return "Good"
        elif score >= 70:
            return "Fair"
        elif score >= 50:
            return "Poor"
        else:
            return "Critical"
    
    def _assess_business_impact(self, escalation: Escalation) -> str:
        """Assess business impact of escalation"""
        if escalation.category in ['Finance', 'Security', 'System']:
            return "High"
        elif escalation.category in ['Academic', 'User Management']:
            return "Medium"
        else:
            return "Low"

# Global instance
admin_email_service = AdminEmailService()