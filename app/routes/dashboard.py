from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_
from app import db
from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.utils.allocation_helper import allocation_helper
from sqlalchemy import or_, and_, func
bp = Blueprint('dashboard', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role in ['superadmin', 'admin', 'coordinator']:
            return redirect(url_for('dashboard.admin_dashboard'))
        elif current_user.role == 'tutor':
            return redirect(url_for('dashboard.tutor_dashboard'))
    
    # Show landing page for non-authenticated users
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def admin_dashboard():
    """Main dashboard for admin roles"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get statistics
    stats = get_dashboard_statistics()
    
    # Get today's classes
    today = date.today()
    todays_classes = Class.get_classes_for_date(today)
    
    # Get recent activities (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_students = Student.query.filter(Student.created_at >= week_ago).order_by(Student.created_at.desc()).limit(5).all()
    recent_tutors = Tutor.query.filter(Tutor.created_at >= week_ago).order_by(Tutor.created_at.desc()).limit(5).all()
    
    # Get attendance alerts (late arrivals, absences)
    attendance_alerts = get_attendance_alerts()
    
    # Get pending tasks
    pending_tasks = get_pending_tasks()
    
    return render_template('dashboard/admin_dashboard.html',
                         stats=stats,
                         todays_classes=todays_classes,
                         recent_students=recent_students,
                         recent_tutors=recent_tutors,
                         attendance_alerts=attendance_alerts,
                         pending_tasks=pending_tasks)

@bp.route('/tutor-dashboard')
@login_required
def tutor_dashboard():
    """Dashboard for tutors"""
    if current_user.role != 'tutor':
        flash('Access denied. This page is for tutors only.', 'error')
        return redirect(url_for('dashboard.index'))
    
    tutor = Tutor.query.filter_by(user_id=current_user.id).first()
    if not tutor:
        flash('Tutor profile not found. Please contact administrator.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get tutor statistics
    tutor_stats = get_tutor_statistics(tutor)
    
    # Get today's classes
    today = date.today()
    todays_classes = Class.get_classes_for_date(today, tutor_id=tutor.id)
    
    # Get this week's classes
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date >= week_start,
        Class.scheduled_date <= week_end
    ).order_by(Class.scheduled_date, Class.scheduled_time).all()
    
    # Get upcoming classes (next 7 days)
    upcoming_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date > today,
        Class.scheduled_date <= today + timedelta(days=7),
        Class.status.in_(['scheduled'])
    ).order_by(Class.scheduled_date, Class.scheduled_time).limit(10).all()
    
    # Get recent attendance
    recent_attendance = Attendance.query.filter_by(tutor_id=tutor.id)\
        .order_by(Attendance.class_date.desc()).limit(10).all()
    
    # Get monthly earnings
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_earnings = tutor.get_monthly_earnings(current_month, current_year)
    
    return render_template('dashboard/tutor_dashboard.html',
                         tutor=tutor,
                         stats=tutor_stats,
                         todays_classes=todays_classes,
                         week_classes=week_classes,
                         upcoming_classes=upcoming_classes,
                         recent_attendance=recent_attendance,
                         monthly_earnings=monthly_earnings)

@bp.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    stats = get_dashboard_statistics()
    return jsonify(stats)

@bp.route('/api/attendance-chart')
@login_required
def api_attendance_chart():
    """API endpoint for attendance chart data"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get attendance data for last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # Query attendance records
    attendance_data = db.session.query(
        Attendance.class_date,
        func.count(Attendance.id).label('total_classes'),
        func.sum(func.cast(Attendance.tutor_present, db.Integer)).label('tutor_present'),
        func.sum(func.cast(Attendance.student_present, db.Integer)).label('student_present')
    ).filter(
        Attendance.class_date >= start_date,
        Attendance.class_date <= end_date
    ).group_by(Attendance.class_date).order_by(Attendance.class_date).all()
    
    chart_data = {
        'labels': [record.class_date.strftime('%Y-%m-%d') for record in attendance_data],
        'datasets': [
            {
                'label': 'Total Classes',
                'data': [record.total_classes for record in attendance_data],
                'borderColor': '#F1A150',
                'backgroundColor': 'rgba(241, 161, 80, 0.1)'
            },
            {
                'label': 'Tutor Present',
                'data': [record.tutor_present for record in attendance_data],
                'borderColor': '#28A745',
                'backgroundColor': 'rgba(40, 167, 69, 0.1)'
            },
            {
                'label': 'Student Present',
                'data': [record.student_present for record in attendance_data],
                'borderColor': '#17A2B8',
                'backgroundColor': 'rgba(23, 162, 184, 0.1)'
            }
        ]
    }
    
    return jsonify(chart_data)

def get_dashboard_statistics():
    """Get dashboard statistics for admin roles"""
    stats = {}
    
    # User statistics
    stats['total_users'] = User.query.filter_by(is_active=True).count()
    stats['total_admins'] = User.query.filter(
        User.role.in_(['superadmin', 'admin', 'coordinator']),
        User.is_active == True
    ).count()
    stats['total_tutors'] = User.query.filter_by(role='tutor', is_active=True).count()
    
    # Student statistics
    stats['total_students'] = Student.query.filter_by(is_active=True).count()
    stats['new_students_this_month'] = Student.query.filter(
        Student.created_at >= datetime.now().replace(day=1),
        Student.is_active == True
    ).count()
    
    # Class statistics
    today = date.today()
    stats['todays_classes'] = Class.query.filter_by(scheduled_date=today).count()
    stats['total_classes_this_month'] = Class.query.filter(
        Class.scheduled_date >= today.replace(day=1),
        Class.scheduled_date <= today
    ).count()
    
    # Attendance statistics for today
    todays_attendance = Attendance.query.filter_by(class_date=today).all()
    stats['todays_attendance'] = {
        'total': len(todays_attendance),
        'present': len([a for a in todays_attendance if a.tutor_present and a.student_present]),
        'absent': len([a for a in todays_attendance if not a.tutor_present or not a.student_present])
    }
    
    # Department-wise statistics
    departments = Department.query.filter_by(is_active=True).all()
    stats['departments'] = []
    for dept in departments:
        dept_stats = {
            'name': dept.name,
            'tutors': User.query.filter_by(department_id=dept.id, role='tutor', is_active=True).count(),
            'students': Student.query.filter_by(department_id=dept.id, is_active=True).count()
        }
        stats['departments'].append(dept_stats)
    
    # Revenue statistics (simplified)
    stats['monthly_revenue'] = 0  # Would calculate from fee payments
    stats['pending_fees'] = 0     # Would calculate from fee balances
    
    return stats

def get_tutor_statistics(tutor):
    """Get statistics for tutor dashboard"""
    stats = {}
    
    # Class statistics
    stats['total_classes'] = tutor.total_classes
    stats['completed_classes'] = tutor.completed_classes
    stats['completion_rate'] = tutor.get_completion_rate()
    
    # This month's classes
    current_month = datetime.now().month
    current_year = datetime.now().year
    month_start = date(current_year, current_month, 1)
    
    stats['this_month_classes'] = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date >= month_start,
        Class.scheduled_date <= date.today()
    ).count()
    
    # Attendance statistics
    attendance_summary = Attendance.get_attendance_summary(tutor_id=tutor.id)
    stats['attendance'] = attendance_summary
    
    # Student count
    unique_students = db.session.query(Class.primary_student_id)\
        .filter_by(tutor_id=tutor.id)\
        .distinct().count()
    stats['total_students'] = unique_students
    
    # Rating
    stats['rating'] = tutor.rating
    
    # Upcoming classes count
    stats['upcoming_classes'] = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date > date.today(),
        Class.status == 'scheduled'
    ).count()
    
    return stats

def get_attendance_alerts():
    """Get attendance alerts for dashboard"""
    alerts = []
    today = date.today()
    
    # Late arrivals today
    late_arrivals = Attendance.query.filter(
        Attendance.class_date == today,
        (Attendance.tutor_late_minutes > 5) | (Attendance.student_late_minutes > 5)
    ).all()
    
    for attendance in late_arrivals:
        if attendance.tutor_late_minutes > 5:
            alerts.append({
                'type': 'late_arrival',
                'message': f'Tutor {attendance.tutor.user.full_name} was {attendance.tutor_late_minutes} minutes late',
                'severity': 'warning',
                'time': attendance.tutor_join_time
            })
        
        if attendance.student_late_minutes > 5:
            alerts.append({
                'type': 'late_arrival',
                'message': f'Student {attendance.student.full_name} was {attendance.student_late_minutes} minutes late',
                'severity': 'info',
                'time': attendance.student_join_time
            })
    
    # Absences today
    absences = Attendance.query.filter(
        Attendance.class_date == today,
        (Attendance.tutor_present == False) | (Attendance.student_present == False)
    ).all()
    
    for attendance in absences:
        if not attendance.tutor_present:
            alerts.append({
                'type': 'absence',
                'message': f'Tutor {attendance.tutor.user.full_name} was absent',
                'severity': 'danger',
                'reason': attendance.tutor_absence_reason
            })
        
        if not attendance.student_present:
            alerts.append({
                'type': 'absence',
                'message': f'Student {attendance.student.full_name} was absent',
                'severity': 'warning',
                'reason': attendance.student_absence_reason
            })
    
    return alerts[:10]  # Return top 10 alerts

def get_pending_tasks():
    """Get pending tasks for dashboard"""
    tasks = []
    
    # Pending tutor verifications
    pending_tutors = Tutor.query.filter_by(verification_status='pending').count()
    if pending_tutors > 0:
        tasks.append({
            'type': 'verification',
            'title': 'Pending Tutor Verifications',
            'count': pending_tutors,
            'url': url_for('admin.tutors'),
            'priority': 'high'
        })
    
    # Overdue fee payments
    overdue_students = Student.query.filter_by(is_active=True).all()
    overdue_count = 0
    for student in overdue_students:
        if student.get_fee_status() == 'pending':
            overdue_count += 1
    
    if overdue_count > 0:
        tasks.append({
            'type': 'payment',
            'title': 'Overdue Fee Payments',
            'count': overdue_count,
            'url': url_for('admin.students'),
            'priority': 'medium'
        })
    
    # Upcoming classes without video uploads
    yesterday = date.today() - timedelta(days=1)
    classes_without_videos = Class.query.filter(
        Class.scheduled_date == yesterday,
        Class.status == 'completed',
        (Class.video_link == None) | (Class.video_link == '')
    ).count()
    
    if classes_without_videos > 0:
        tasks.append({
            'type': 'video',
            'title': 'Missing Class Videos',
            'count': classes_without_videos,
            'url': url_for('admin.classes'),
            'priority': 'medium'
        })
    
    return tasks

def get_dashboard_statistics():
    """Get comprehensive dashboard statistics including allocation data"""
    try:
        # Get basic counts
        total_users = User.query.filter_by(is_active=True).count()
        total_students = Student.query.filter_by(is_active=True, enrollment_status='active').count()
        total_tutors = Tutor.query.filter_by(status='active').count()
        
        # Get today's classes
        today = date.today()
        todays_classes = Class.query.filter_by(scheduled_date=today).count()
        
        # Get today's attendance
        todays_attendance = Attendance.query.filter_by(class_date=today).all()
        present_count = sum(1 for att in todays_attendance if att.student_present)
        absent_count = len(todays_attendance) - present_count
        
        # Get allocation analytics
        allocation_analytics = allocation_helper.get_allocation_analytics()
        
        # Get department-wise breakdown (if needed)
        departments = Department.query.filter_by(is_active=True).all()
        department_stats = []
        
        for dept in departments:
            dept_students = Student.query.filter_by(
                department_id=dept.id, 
                is_active=True, 
                enrollment_status='active'
            ).count()
            
            dept_tutors = Tutor.query.join(User).filter(
                User.department_id == dept.id,
                Tutor.status == 'active'
            ).count()
            
            department_stats.append({
                'id': dept.id,
                'name': dept.name,
                'students': dept_students,
                'tutors': dept_tutors
            })
        
        return {
            'total_users': total_users,
            'total_students': total_students,
            'total_tutors': total_tutors,
            'todays_classes': todays_classes,
            'todays_attendance': {
                'present': present_count,
                'absent': absent_count,
                'total': len(todays_attendance)
            },
            'allocation_overview': allocation_analytics['overview'],
            'department_breakdown': department_stats,
            'last_updated': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error getting dashboard statistics: {str(e)}")
        # Return default values if there's an error
        return {
            'total_users': 0,
            'total_students': 0,
            'total_tutors': 0,
            'todays_classes': 0,
            'todays_attendance': {'present': 0, 'absent': 0, 'total': 0},
            'allocation_overview': {
                'total_students': 0,
                'allocated_students': 0,
                'unallocated_students': 0,
                'allocation_percentage': 0,
                'urgent_cases': 0
            },
            'department_breakdown': [],
            'last_updated': datetime.now().isoformat()
        }

def get_tutor_statistics(tutor):
    """Get statistics for tutor dashboard"""
    try:
        # Get tutor's classes
        total_classes = Class.query.filter_by(tutor_id=tutor.id).count()
        completed_classes = Class.query.filter_by(
            tutor_id=tutor.id, 
            status='completed'
        ).count()
        
        # Get this month's classes
        today = date.today()
        month_start = today.replace(day=1)
        this_month_classes = Class.query.filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date >= month_start,
            Class.scheduled_date <= today
        ).count()
        
        # Get upcoming classes (next 7 days)
        week_ahead = today + timedelta(days=7)
        upcoming_classes = Class.query.filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date > today,
            Class.scheduled_date <= week_ahead,
            Class.status == 'scheduled'
        ).count()
        
        # Get unique students taught
        taught_students = set()
        classes = Class.query.filter_by(tutor_id=tutor.id).all()
        for cls in classes:
            try:
                if cls.primary_student_id:
                    taught_students.add(cls.primary_student_id)
                student_ids = cls.get_students() or []
                taught_students.update(student_ids)
            except:
                continue
        
        unique_students = len(taught_students)
        
        # Calculate completion rate
        completion_rate = (completed_classes / total_classes * 100) if total_classes > 0 else 0
        
        return {
            'total_classes': total_classes,
            'completed_classes': completed_classes,
            'this_month_classes': this_month_classes,
            'upcoming_classes': upcoming_classes,
            'unique_students': unique_students,
            'completion_rate': round(completion_rate, 1),
            'rating': tutor.rating or 0,
            'test_score': tutor.test_score or 0
        }
        
    except Exception as e:
        print(f"Error getting tutor statistics: {str(e)}")
        return {
            'total_classes': 0,
            'completed_classes': 0,
            'this_month_classes': 0,
            'upcoming_classes': 0,
            'unique_students': 0,
            'completion_rate': 0,
            'rating': 0,
            'test_score': 0
        }

def get_attendance_alerts():
    """Get attendance alerts for dashboard"""
    try:
        today = date.today()
        alerts = []
        
        # Get late arrivals (students who joined > 10 minutes late)
        late_arrivals = Attendance.query.filter(
            Attendance.class_date == today,
            Attendance.student_late_minutes > 10
        ).all()
        
        for attendance in late_arrivals:
            alerts.append({
                'type': 'late_arrival',
                'message': f"Student late by {attendance.student_late_minutes} minutes",
                'student_id': attendance.student_id,
                'class_id': attendance.class_id,
                'severity': 'warning'
            })
        
        # Get no-shows
        no_shows = Attendance.query.filter(
            Attendance.class_date == today,
            Attendance.student_present == False,
            Attendance.student_absence_reason.is_(None)
        ).all()
        
        for attendance in no_shows:
            alerts.append({
                'type': 'no_show',
                'message': "Student did not attend class",
                'student_id': attendance.student_id,
                'class_id': attendance.class_id,
                'severity': 'danger'
            })
        
        return alerts
        
    except Exception as e:
        print(f"Error getting attendance alerts: {str(e)}")
        return []

def get_pending_tasks():
    """Get pending administrative tasks"""
    try:
        tasks = []
        
        # Get unallocated students (top priority)
        unallocated_count = allocation_helper.get_allocation_analytics()['overview']['unallocated_students']
        if unallocated_count > 0:
            tasks.append({
                'type': 'allocation',
                'title': 'Student Allocation Required',
                'message': f"{unallocated_count} students need tutor assignment",
                'count': unallocated_count,
                'priority': 'high',
                'url': '/admin/allocation-dashboard'
            })
        
        # Get tutors without availability
        tutors_no_availability = Tutor.query.filter_by(status='active').all()
        no_availability_count = sum(1 for t in tutors_no_availability if not t.get_availability())
        
        if no_availability_count > 0:
            tasks.append({
                'type': 'availability',
                'title': 'Tutor Availability Missing',
                'message': f"{no_availability_count} tutors haven't set their availability",
                'count': no_availability_count,
                'priority': 'medium',
                'url': '/admin/tutors'
            })
        
        # Get classes scheduled for today without meeting links
        today = date.today()
        classes_no_links = Class.query.filter(
            Class.scheduled_date == today,
            Class.status == 'scheduled',
            or_(Class.meeting_link.is_(None), Class.meeting_link == '')
        ).count()
        
        if classes_no_links > 0:
            tasks.append({
                'type': 'meeting_links',
                'title': 'Missing Meeting Links',
                'message': f"{classes_no_links} today's classes need meeting links",
                'count': classes_no_links,
                'priority': 'high',
                'url': '/admin/classes'
            })
        
        return tasks
        
    except Exception as e:
        print(f"Error getting pending tasks: {str(e)}")
        return []