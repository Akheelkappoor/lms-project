"""
System-Generated Email Notification Service
Handles all automated, scheduled, and system-triggered email notifications
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date, time
from app.services.comprehensive_email_service import ComprehensiveEmailService, EmailPriority, EmailType
from app.models.user import User
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.department import Department
from app.models.escalation import Escalation
from sqlalchemy import and_, or_, func, text
from app import db
import json

class SystemNotificationService(ComprehensiveEmailService):
    """Service for system-generated automated notifications"""
    
    # ============ DAILY AUTOMATED NOTIFICATIONS ============
    
    def send_daily_morning_class_reminders(self) -> Dict[str, Any]:
        """Send morning class reminders for today's classes"""
        today = datetime.now().date()
        
        # Get all classes scheduled for today
        today_classes = Class.query.filter(
            Class.scheduled_date == today,
            Class.status == 'scheduled'
        ).all()
        
        results = {
            'total_classes': len(today_classes),
            'reminders_sent': 0,
            'failed_sends': 0,
            'errors': []
        }
        
        for class_obj in today_classes:
            try:
                # Send to students
                if class_obj.primary_student_id:
                    self._send_class_reminder_to_student(class_obj.primary_student_id, class_obj.id, 'today')
                
                # Send to group students
                if class_obj.students:
                    student_ids = class_obj.get_students()
                    for student_id in student_ids:
                        self._send_class_reminder_to_student(student_id, class_obj.id, 'today')
                
                # Send to tutor
                if class_obj.tutor and class_obj.tutor.user:
                    self._send_class_reminder_to_tutor(class_obj.tutor.id, class_obj.id, 'today')
                
                results['reminders_sent'] += 1
                
            except Exception as e:
                results['failed_sends'] += 1
                results['errors'].append({
                    'class_id': class_obj.id,
                    'error': str(e)
                })
        
        return results
    
    def send_daily_attendance_follow_ups(self) -> Dict[str, Any]:
        """Send attendance follow-ups for yesterday's classes"""
        yesterday = datetime.now().date() - timedelta(days=1)
        
        # Get classes from yesterday that may need attendance follow-up
        yesterday_classes = Class.query.filter(
            Class.scheduled_date == yesterday,
            Class.status == 'completed'
        ).all()
        
        results = {
            'classes_checked': len(yesterday_classes),
            'follow_ups_sent': 0,
            'students_contacted': 0
        }
        
        for class_obj in yesterday_classes:
            # Check if attendance was marked
            attendance_records = Attendance.query.filter_by(class_id=class_obj.id).all()
            
            if not attendance_records:
                # No attendance marked - send follow-up
                self._send_attendance_marking_reminder(class_obj.tutor.id, class_obj.id)
                results['follow_ups_sent'] += 1
            else:
                # Check for absentees and send follow-up
                for attendance in attendance_records:
                    if not attendance.is_present:
                        self._send_absence_follow_up(attendance.student_id, class_obj.id)
                        results['students_contacted'] += 1
        
        return results
    
    def send_daily_payment_due_alerts(self) -> Dict[str, Any]:
        """Send payment due alerts for fees due today"""
        results = {
            'students_checked': 0,
            'alerts_sent': 0,
            'overdue_alerts': 0
        }
        
        # Get all active students
        active_students = Student.query.filter_by(
            is_active=True,
            enrollment_status='active'
        ).all()
        
        results['students_checked'] = len(active_students)
        
        for student in active_students:
            try:
                balance = student.get_balance_amount()
                if balance > 0:
                    # Check if payment is due today or overdue
                    due_date = self._calculate_next_due_date(student)
                    days_overdue = (datetime.now().date() - due_date.date()).days
                    
                    if days_overdue >= 0:  # Due today or overdue
                        context = {
                            'student': student,
                            'balance_amount': balance,
                            'due_date': due_date,
                            'days_overdue': days_overdue,
                            'is_overdue': days_overdue > 0,
                            'urgency_level': 'High' if days_overdue > 7 else 'Medium' if days_overdue > 0 else 'Normal'
                        }
                        
                        self._send_daily_payment_alert(student, context)
                        
                        if days_overdue > 0:
                            results['overdue_alerts'] += 1
                        else:
                            results['alerts_sent'] += 1
                            
            except Exception as e:
                self.logger.error(f"Error processing payment alert for student {student.id}: {str(e)}")
        
        return results
    
    def send_daily_tutor_task_reminders(self) -> Dict[str, Any]:
        """Send daily task reminders to tutors"""
        results = {
            'tutors_checked': 0,
            'reminders_sent': 0,
            'urgent_tasks': 0
        }
        
        # Get all active tutors
        active_tutors = Tutor.query.join(User).filter(
            Tutor.status == 'active',
            User.is_active == True
        ).all()
        
        results['tutors_checked'] = len(active_tutors)
        
        for tutor in active_tutors:
            try:
                tasks = self._get_tutor_pending_tasks(tutor.id)
                
                if tasks['total_tasks'] > 0:
                    context = {
                        'tutor': tutor,
                        'user': tutor.user,
                        'tasks': tasks,
                        'urgent_count': tasks['urgent_tasks'],
                        'total_count': tasks['total_tasks']
                    }
                    
                    self._send_tutor_daily_tasks(tutor, context)
                    results['reminders_sent'] += 1
                    results['urgent_tasks'] += tasks['urgent_tasks']
                    
            except Exception as e:
                self.logger.error(f"Error processing tasks for tutor {tutor.id}: {str(e)}")
        
        return results
    
    # ============ WEEKLY AUTOMATED REPORTS ============
    
    def send_weekly_performance_summaries(self) -> Dict[str, Any]:
        """Send weekly performance summaries to all stakeholders"""
        week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
        week_end = week_start + timedelta(days=6)
        
        results = {
            'student_reports': 0,
            'tutor_reports': 0,
            'coordinator_reports': 0,
            'admin_reports': 0
        }
        
        # Student weekly reports
        active_students = Student.query.filter_by(
            is_active=True,
            enrollment_status='active'
        ).all()
        
        for student in active_students:
            try:
                performance_data = self._get_student_weekly_performance(student.id, week_start, week_end)
                if performance_data['has_activity']:
                    self._send_student_weekly_report(student, performance_data)
                    results['student_reports'] += 1
            except Exception as e:
                self.logger.error(f"Error sending weekly report to student {student.id}: {str(e)}")
        
        # Tutor weekly reports
        active_tutors = Tutor.query.join(User).filter(
            Tutor.status == 'active',
            User.is_active == True
        ).all()
        
        for tutor in active_tutors:
            try:
                performance_data = self._get_tutor_weekly_performance(tutor.id, week_start, week_end)
                if performance_data['has_activity']:
                    self._send_tutor_weekly_report(tutor, performance_data)
                    results['tutor_reports'] += 1
            except Exception as e:
                self.logger.error(f"Error sending weekly report to tutor {tutor.id}: {str(e)}")
        
        # Coordinator weekly reports
        departments = Department.query.filter_by(is_active=True).all()
        
        for department in departments:
            try:
                coord_emails = self.get_department_coordinators(department.id)
                if coord_emails:
                    dept_data = self._get_department_weekly_performance(department.id, week_start, week_end)
                    self._send_coordinator_weekly_report(department, dept_data, coord_emails)
                    results['coordinator_reports'] += 1
            except Exception as e:
                self.logger.error(f"Error sending weekly report for department {department.id}: {str(e)}")
        
        # Admin weekly reports
        try:
            admin_emails = self.get_admin_emails('superadmin')
            if admin_emails:
                admin_data = self._get_admin_weekly_performance(week_start, week_end)
                self._send_admin_weekly_report(admin_data, admin_emails)
                results['admin_reports'] += 1
        except Exception as e:
            self.logger.error(f"Error sending weekly admin report: {str(e)}")
        
        return results
    
    def send_weekly_attendance_reports(self) -> Dict[str, Any]:
        """Send weekly attendance reports to coordinators"""
        week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
        week_end = week_start + timedelta(days=6)
        
        results = {
            'departments_processed': 0,
            'reports_sent': 0,
            'low_attendance_alerts': 0
        }
        
        departments = Department.query.filter_by(is_active=True).all()
        results['departments_processed'] = len(departments)
        
        for department in departments:
            try:
                coord_emails = self.get_department_coordinators(department.id)
                if not coord_emails:
                    continue
                
                attendance_data = self._get_department_attendance_report(department.id, week_start, week_end)
                
                context = {
                    'department': department,
                    'week_start': week_start,
                    'week_end': week_end,
                    'attendance_data': attendance_data,
                    'low_attendance_students': attendance_data.get('low_attendance_students', []),
                    'department_average': attendance_data.get('department_average', 0)
                }
                
                self.send_email(
                    recipients=coord_emails,
                    subject=f"Weekly Attendance Report - {department.name} | Avg: {attendance_data.get('department_average', 0):.1f}%",
                    template='reports/weekly_attendance_report.html',
                    context=context,
                    priority=EmailPriority.MEDIUM,
                    email_type=EmailType.REPORT
                )
                
                results['reports_sent'] += 1
                results['low_attendance_alerts'] += len(attendance_data.get('low_attendance_students', []))
                
            except Exception as e:
                self.logger.error(f"Error processing attendance report for department {department.id}: {str(e)}")
        
        return results
    
    # ============ MONTHLY AUTOMATED COMMUNICATIONS ============
    
    def send_monthly_salary_statements(self) -> Dict[str, Any]:
        """Send monthly salary statements to tutors"""
        current_month = datetime.now().strftime('%B %Y')
        month_start = datetime.now().replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        results = {
            'tutors_processed': 0,
            'statements_sent': 0,
            'total_payout': 0
        }
        
        # Get all tutors who were active this month
        active_tutors = Tutor.query.join(User).filter(
            Tutor.status == 'active',
            User.is_active == True
        ).all()
        
        results['tutors_processed'] = len(active_tutors)
        
        for tutor in active_tutors:
            try:
                # Calculate monthly earnings
                monthly_data = self._calculate_tutor_monthly_earnings(tutor.id, month_start, month_end)
                
                if monthly_data['total_amount'] > 0:
                    context = {
                        'tutor': tutor,
                        'user': tutor.user,
                        'month': current_month,
                        'earnings_data': monthly_data,
                        'classes_conducted': monthly_data['classes_count'],
                        'total_hours': monthly_data['total_hours'],
                        'gross_amount': monthly_data['gross_amount'],
                        'deductions': monthly_data['deductions'],
                        'net_amount': monthly_data['total_amount'],
                        'payment_schedule': monthly_data['payment_schedule']
                    }
                    
                    success = self.send_email(
                        recipients=[tutor.user.email],
                        subject=f"Monthly Salary Statement - {current_month} | ₹{monthly_data['total_amount']:,.2f}",
                        template='financial/monthly_salary_statement.html',
                        context=context,
                        priority=EmailPriority.MEDIUM,
                        email_type=EmailType.FINANCIAL
                    )
                    
                    if success:
                        results['statements_sent'] += 1
                        results['total_payout'] += monthly_data['total_amount']
                        
            except Exception as e:
                self.logger.error(f"Error processing salary statement for tutor {tutor.id}: {str(e)}")
        
        return results
    
    def send_monthly_progress_reports(self) -> Dict[str, Any]:
        """Send monthly progress reports to students and parents"""
        current_month = datetime.now().strftime('%B %Y')
        month_start = datetime.now().replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        results = {
            'students_processed': 0,
            'reports_sent': 0,
            'parent_notifications': 0
        }
        
        # Get all active students
        active_students = Student.query.filter_by(
            is_active=True,
            enrollment_status='active'
        ).all()
        
        results['students_processed'] = len(active_students)
        
        for student in active_students:
            try:
                # Generate comprehensive progress report
                progress_data = self._generate_student_monthly_progress(student.id, month_start, month_end)
                
                if progress_data['has_activity']:
                    # Get recipients (student + parents)
                    recipients = [student.email] if student.email else []
                    parent_details = student.get_parent_details()
                    
                    if parent_details:
                        if parent_details.get('father', {}).get('email'):
                            recipients.append(parent_details['father']['email'])
                            results['parent_notifications'] += 1
                        if parent_details.get('mother', {}).get('email'):
                            recipients.append(parent_details['mother']['email'])
                            results['parent_notifications'] += 1
                    
                    if recipients:
                        context = {
                            'student': student,
                            'month': current_month,
                            'progress_data': progress_data,
                            'attendance_summary': progress_data['attendance'],
                            'performance_metrics': progress_data['performance'],
                            'subjects_progress': progress_data['subjects'],
                            'recommendations': progress_data['recommendations'],
                            'next_month_goals': progress_data['goals']
                        }
                        
                        success = self.send_email(
                            recipients=recipients,
                            subject=f"Monthly Progress Report - {student.full_name} | {current_month}",
                            template='reports/monthly_progress_report.html',
                            context=context,
                            priority=EmailPriority.MEDIUM,
                            email_type=EmailType.REPORT
                        )
                        
                        if success:
                            results['reports_sent'] += 1
                            
            except Exception as e:
                self.logger.error(f"Error processing progress report for student {student.id}: {str(e)}")
        
        return results
    
    def send_monthly_system_health_report(self) -> Dict[str, Any]:
        """Send monthly system health and performance report to admins"""
        current_month = datetime.now().strftime('%B %Y')
        month_start = datetime.now().replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Collect comprehensive system metrics
        system_metrics = self._collect_monthly_system_metrics(month_start, month_end)
        
        context = {
            'month': current_month,
            'metrics': system_metrics,
            'user_growth': system_metrics['user_growth'],
            'class_statistics': system_metrics['class_stats'],
            'financial_summary': system_metrics['financial'],
            'system_performance': system_metrics['system_health'],
            'quality_metrics': system_metrics['quality'],
            'recommendations': system_metrics['recommendations']
        }
        
        admin_emails = self.get_admin_emails('superadmin')
        tech_emails = self.get_admin_emails('admin')
        
        success = self.send_email(
            recipients=admin_emails,
            cc=tech_emails,
            subject=f"Monthly System Health Report - {current_month} | Overall Score: {system_metrics['overall_health_score']}%",
            template='reports/monthly_system_health.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.REPORT
        )
        
        return {
            'report_sent': success,
            'overall_health_score': system_metrics['overall_health_score'],
            'total_users': system_metrics['user_growth']['total_users'],
            'total_classes': system_metrics['class_stats']['total_classes'],
            'system_uptime': system_metrics['system_health']['uptime_percentage']
        }
    
    # ============ EVENT-TRIGGERED NOTIFICATIONS ============
    
    def send_bulk_import_completion_notification(self, import_data: Dict[str, Any]) -> bool:
        """Send notification when bulk import is completed"""
        admin_emails = self.get_admin_emails('superadmin')
        
        context = {
            'import_data': import_data,
            'import_type': import_data.get('type', 'unknown'),
            'total_records': import_data.get('total_records', 0),
            'successful': import_data.get('successful', 0),
            'failed': import_data.get('failed', 0),
            'completion_time': datetime.now(),
            'processing_duration': import_data.get('duration', 'unknown'),
            'errors': import_data.get('errors', [])
        }
        
        return self.send_email(
            recipients=admin_emails,
            subject=f"Bulk Import Completed - {import_data.get('type', 'Unknown')} | {import_data.get('successful', 0)}/{import_data.get('total_records', 0)} Success",
            template='system/bulk_import_completion.html',
            context=context,
            priority=EmailPriority.MEDIUM,
            email_type=EmailType.SYSTEM
        )
    
    def send_database_backup_notification(self, backup_data: Dict[str, Any]) -> bool:
        """Send notification about database backup status"""
        tech_emails = self.get_admin_emails('admin')
        admin_emails = self.get_admin_emails('superadmin')
        
        context = {
            'backup_data': backup_data,
            'backup_status': backup_data.get('status', 'unknown'),
            'backup_size': backup_data.get('size', 'unknown'),
            'backup_duration': backup_data.get('duration', 'unknown'),
            'backup_location': backup_data.get('location', 'unknown'),
            'completion_time': datetime.now(),
            'next_backup': backup_data.get('next_backup', 'scheduled')
        }
        
        priority = EmailPriority.HIGH if backup_data.get('status') == 'failed' else EmailPriority.LOW
        
        return self.send_email(
            recipients=tech_emails,
            cc=admin_emails if backup_data.get('status') == 'failed' else [],
            subject=f"Database Backup {backup_data.get('status', 'Status').title()} - {datetime.now().strftime('%Y-%m-%d')}",
            template='system/database_backup_notification.html',
            context=context,
            priority=priority,
            email_type=EmailType.SYSTEM
        )
    
    def send_system_maintenance_notification(self, maintenance_data: Dict[str, Any]) -> bool:
        """Send system maintenance notifications to all users"""
        
        # Get all active user emails
        all_users = User.query.filter_by(is_active=True).all()
        user_emails = [user.email for user in all_users if user.email]
        
        # Also get parent emails
        parent_emails = []
        students = Student.query.filter_by(is_active=True).all()
        for student in students:
            parent_details = student.get_parent_details()
            if parent_details:
                if parent_details.get('father', {}).get('email'):
                    parent_emails.append(parent_details['father']['email'])
                if parent_details.get('mother', {}).get('email'):
                    parent_emails.append(parent_details['mother']['email'])
        
        all_emails = list(set(user_emails + parent_emails))
        
        context = {
            'maintenance_data': maintenance_data,
            'maintenance_type': maintenance_data.get('type', 'scheduled'),
            'start_time': maintenance_data.get('start_time'),
            'end_time': maintenance_data.get('end_time'),
            'duration': maintenance_data.get('duration', 'unknown'),
            'impact': maintenance_data.get('impact', 'minimal'),
            'services_affected': maintenance_data.get('services_affected', []),
            'preparation_steps': maintenance_data.get('preparation_steps', [])
        }
        
        # Send in batches to avoid overwhelming the email server
        batch_size = 50
        success_count = 0
        
        for i in range(0, len(all_emails), batch_size):
            batch = all_emails[i:i + batch_size]
            
            try:
                success = self.send_email(
                    recipients=[],  # Empty recipients
                    bcc=batch,     # Use BCC for bulk sending
                    subject=f"System Maintenance Notice - {maintenance_data.get('type', 'Scheduled').title()}",
                    template='system/maintenance_notification.html',
                    context=context,
                    priority=EmailPriority.MEDIUM,
                    email_type=EmailType.SYSTEM
                )
                
                if success:
                    success_count += len(batch)
                    
            except Exception as e:
                self.logger.error(f"Error sending maintenance notification batch {i//batch_size + 1}: {str(e)}")
        
        return success_count > 0
    
    # ============ HELPER METHODS ============
    
    def _send_class_reminder_to_student(self, student_id: int, class_id: int, timing: str):
        """Send class reminder to individual student"""
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
        
        if not recipients:
            return False
        
        context = {
            'student': student,
            'class': class_obj,
            'timing': timing,
            'tutor': class_obj.tutor,
            'tutor_user': class_obj.tutor.user if class_obj.tutor else None,
            'class_url': f"/student/classes/{class_id}",
            'preparation_tips': [
                "Ensure stable internet connection",
                "Have notebooks and materials ready",
                "Join 5 minutes before class time",
                "Keep a quiet study environment"
            ]
        }
        
        return self.send_email(
            recipients=recipients,
            subject=f"Class {timing.title()} - {class_obj.subject} | {class_obj.scheduled_time}",
            template='reminders/class_reminder_student.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.REMINDER
        )
    
    def _send_class_reminder_to_tutor(self, tutor_id: int, class_id: int, timing: str):
        """Send class reminder to tutor"""
        tutor = Tutor.query.get(tutor_id)
        class_obj = Class.query.get(class_id)
        
        if not tutor or not class_obj or not tutor.user:
            return False
        
        # Get student details for the class
        student_details = []
        if class_obj.primary_student_id:
            student = Student.query.get(class_obj.primary_student_id)
            if student:
                student_details.append({
                    'name': student.full_name,
                    'grade': student.grade,
                    'subjects': student.get_subjects_enrolled()
                })
        
        if class_obj.students:
            student_ids = class_obj.get_students()
            for student_id in student_ids:
                student = Student.query.get(student_id)
                if student and student.id != class_obj.primary_student_id:
                    student_details.append({
                        'name': student.full_name,
                        'grade': student.grade,
                        'subjects': student.get_subjects_enrolled()
                    })
        
        context = {
            'tutor': tutor,
            'user': tutor.user,
            'class': class_obj,
            'timing': timing,
            'students': student_details,
            'preparation_checklist': [
                "Review class materials and lesson plan",
                "Prepare teaching aids and resources",
                "Test video/audio equipment",
                "Arrive 10 minutes early for setup"
            ]
        }
        
        return self.send_email(
            recipients=[tutor.user.email],
            subject=f"Class {timing.title()} - {class_obj.subject} | {len(student_details)} Students",
            template='reminders/class_reminder_tutor.html',
            context=context,
            priority=EmailPriority.HIGH,
            email_type=EmailType.REMINDER
        )
    
    def _get_tutor_pending_tasks(self, tutor_id: int) -> Dict[str, Any]:
        """Get pending tasks for a tutor"""
        tasks = {
            'urgent_tasks': 0,
            'total_tasks': 0,
            'video_uploads': [],
            'attendance_marking': [],
            'profile_updates': [],
            'feedback_responses': []
        }
        
        # Check for video uploads due
        pending_videos = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.status == 'completed',
            Class.video_url.is_(None),
            Class.scheduled_date >= datetime.now().date() - timedelta(days=2)
        ).all()
        
        for class_obj in pending_videos:
            hours_overdue = (datetime.now() - datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time or time(9, 0))).total_seconds() / 3600
            is_urgent = hours_overdue > 2
            
            tasks['video_uploads'].append({
                'class_id': class_obj.id,
                'subject': class_obj.subject,
                'date': class_obj.scheduled_date,
                'hours_overdue': hours_overdue,
                'is_urgent': is_urgent
            })
            
            if is_urgent:
                tasks['urgent_tasks'] += 1
            tasks['total_tasks'] += 1
        
        # Check for attendance marking
        pending_attendance = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.status == 'completed',
            Class.scheduled_date >= datetime.now().date() - timedelta(days=1),
            ~Class.id.in_(
                db.session.query(Attendance.class_id).filter(Attendance.class_id.isnot(None))
            )
        ).all()
        
        for class_obj in pending_attendance:
            tasks['attendance_marking'].append({
                'class_id': class_obj.id,
                'subject': class_obj.subject,
                'date': class_obj.scheduled_date
            })
            tasks['total_tasks'] += 1
        
        return tasks

# Global instance
system_notification_service = SystemNotificationService()