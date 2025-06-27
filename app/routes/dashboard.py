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