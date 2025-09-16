from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.utils.allocation_helper import allocation_helper
import logging
import time
from functools import wraps

# Set up logging
logger = logging.getLogger(__name__)

def handle_dashboard_errors(f):
    """Decorator to handle errors in dashboard routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            start_time = time.time()
            result = f(*args, **kwargs)
            end_time = time.time()
            logger.info(f"Dashboard {f.__name__} executed in {end_time - start_time:.2f} seconds")
            return result
        except Exception as e:
            logger.error(f"Dashboard error in {f.__name__}: {str(e)}", exc_info=True)
            flash(f'Dashboard loading error. Please try refreshing the page.', 'error')
            # Return minimal dashboard with error handling
            if 'admin' in f.__name__:
                return render_template('dashboard/admin_dashboard.html', 
                                     stats={}, todays_classes=[], recent_students=[], 
                                     recent_tutors=[], attendance_alerts=[], pending_tasks=[],
                                     error_mode=True)
            else:
                # Create a minimal tutor object for error fallback
                class MinimalTutor:
                    def __init__(self):
                        self.user = current_user
                
                return render_template('dashboard/tutor_dashboard.html',
                                     tutor=MinimalTutor(), stats={}, todays_classes=[], 
                                     week_classes=[], upcoming_classes=[], 
                                     recent_attendance=[], monthly_earnings=0,
                                     error_mode=True)
    return decorated_function

bp = Blueprint('dashboard', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role in ['superadmin', 'admin', 'coordinator']:
            return redirect(url_for('dashboard.admin_dashboard'))
        elif current_user.role == 'tutor':
            return redirect(url_for('dashboard_optimized.tutor_dashboard'))
    
    # Show landing page for non-authenticated users
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
@handle_dashboard_errors
def admin_dashboard():
    """Main dashboard for admin roles"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get statistics
    stats = get_dashboard_statistics()
    
    # Get today's classes with optimized eager loading
    today = date.today()
    todays_classes = Class.query.options(
        joinedload(Class.tutor).joinedload(Tutor.user),
        joinedload(Class.primary_student)
    ).filter_by(scheduled_date=today).all()
    
    # Get recent activities with optimized eager loading (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_students = Student.query.options(
        joinedload(Student.department)
    ).filter(Student.created_at >= week_ago).order_by(Student.created_at.desc()).limit(5).all()
    
    recent_tutors = Tutor.query.options(
        joinedload(Tutor.user).joinedload(User.department)
    ).filter(Tutor.created_at >= week_ago).order_by(Tutor.created_at.desc()).limit(5).all()
    
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

@bp.route('/tutor-dashboard-old')
@login_required
@handle_dashboard_errors
def tutor_dashboard_old():
    """Dashboard for tutors"""
    if current_user.role != 'tutor':
        flash('Access denied. This page is for tutors only.', 'error')
        return redirect(url_for('dashboard.index'))
    
    tutor = Tutor.query.options(
        joinedload(Tutor.user),
        joinedload(Tutor.department)
    ).filter_by(user_id=current_user.id).first()
    
    if not tutor:
        flash('Tutor profile not found. Please contact administrator.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get tutor statistics
    tutor_stats = get_tutor_statistics(tutor)
    
    # Get today's classes with optimized loading
    today = date.today()
    todays_classes = Class.query.options(
        joinedload(Class.primary_student)
    ).filter_by(tutor_id=tutor.id, scheduled_date=today).all()
    
    # Get this week's classes with optimized loading
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_classes = Class.query.options(
        joinedload(Class.primary_student)
    ).filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date >= week_start,
        Class.scheduled_date <= week_end
    ).order_by(Class.scheduled_date, Class.scheduled_time).all()
    
    # Get upcoming classes with optimized loading (next 7 days)
    upcoming_classes = Class.query.options(
        joinedload(Class.primary_student)
    ).filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date > today,
        Class.scheduled_date <= today + timedelta(days=7),
        Class.status.in_(['scheduled'])
    ).order_by(Class.scheduled_date, Class.scheduled_time).limit(10).all()
    
    # Get recent attendance with optimized loading
    recent_attendance = Attendance.query.options(
        joinedload(Attendance.student),
        joinedload(Attendance.class_session)
    ).filter_by(tutor_id=tutor.id).order_by(Attendance.class_date.desc()).limit(10).all()
    
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

@bp.route('/api/attendance-trends')
@login_required
@handle_dashboard_errors
def api_attendance_trends():
    """API endpoint for attendance trends over last 30 days"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        # Get attendance data for the last 30 days
        attendance_query = db.session.query(
            func.date(Attendance.class_date).label('date'),
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(and_(Attendance.tutor_present == True, Attendance.student_present == True), 1)], else_=0)).label('present'),
            func.sum(func.case([(or_(Attendance.tutor_present == False, Attendance.student_present == False), 1)], else_=0)).label('absent'),
            func.sum(func.case([(or_(Attendance.tutor_late_minutes > 5, Attendance.student_late_minutes > 5), 1)], else_=0)).label('late')
        ).filter(
            Attendance.class_date >= start_date,
            Attendance.class_date <= end_date
        ).group_by(func.date(Attendance.class_date)).order_by(func.date(Attendance.class_date)).all()
        
        # Prepare chart data
        labels = []
        present_data = []
        absent_data = []
        late_data = []
        
        # Fill in missing dates with zeros
        current_date = start_date
        attendance_dict = {record.date: record for record in attendance_query}
        
        while current_date <= end_date:
            labels.append(current_date.strftime('%m/%d'))
            
            if current_date in attendance_dict:
                record = attendance_dict[current_date]
                present_data.append(int(record.present or 0))
                absent_data.append(int(record.absent or 0))
                late_data.append(int(record.late or 0))
            else:
                present_data.append(0)
                absent_data.append(0)
                late_data.append(0)
            
            current_date += timedelta(days=1)
        
        trends_data = {
            'labels': labels,
            'present': present_data,
            'absent': absent_data,
            'late': late_data
        }
        
        return jsonify({
            'success': True,
            'trends': trends_data,
            'period': f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
        })
        
    except Exception as e:
        logger.error(f"Error in attendance trends API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to load attendance trends',
            'trends': {
                'labels': ['No Data'],
                'present': [0],
                'absent': [0],
                'late': [0]
            }
        })

@bp.route('/api/attendance-today')
@login_required
@handle_dashboard_errors
def api_attendance_today():
    """API endpoint for today's attendance data"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    today = date.today()
    todays_attendance = Attendance.query.filter_by(class_date=today).all()
    
    attendance_data = {
        'total': len(todays_attendance),
        'present': len([a for a in todays_attendance if a.tutor_present and a.student_present]),
        'tutor_absent': len([a for a in todays_attendance if not a.tutor_present]),
        'student_absent': len([a for a in todays_attendance if not a.student_present]),
        'late_arrivals': len([a for a in todays_attendance if (a.tutor_late_minutes or 0) > 5 or (a.student_late_minutes or 0) > 5]),
        'details': [
            {
                'class_id': a.class_id,
                'tutor_present': a.tutor_present,
                'student_present': a.student_present,
                'tutor_late': (a.tutor_late_minutes or 0) > 5,
                'student_late': (a.student_late_minutes or 0) > 5,
                'subject': a.class_session.subject if a.class_session else 'Unknown'
            }
            for a in todays_attendance
        ]
    }
    
    return jsonify(attendance_data)

@bp.route('/api/performance-metrics')
@login_required
@handle_dashboard_errors
def api_performance_metrics():
    """API endpoint for performance metrics"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    metrics = {
        'tutor_utilization': get_tutor_utilization_rate(),
        'student_engagement': get_student_engagement_rate(),
        'average_class_duration': get_average_class_duration(),
        'completion_rate': get_completion_rate_last_30_days(),
        'system_load': get_system_load_metrics()
    }
    
    return jsonify(metrics)

@bp.route('/api/department-analytics')
@login_required
@handle_dashboard_errors
def api_department_analytics():
    """API endpoint for department analytics"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    departments = Department.query.filter_by(is_active=True).all()
    analytics = []
    
    for dept in departments:
        dept_data = get_department_detailed_analytics(dept)
        analytics.append(dept_data)
    
    return jsonify({'departments': analytics})

@bp.route('/api/real-time-stats')
@login_required
@handle_dashboard_errors
def api_real_time_stats():
    """API endpoint for real-time dashboard updates"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    current_time = datetime.now()
    today = current_time.date()
    
    real_time_data = {
        'timestamp': current_time.isoformat(),
        'active_classes': Class.query.filter(
            Class.scheduled_date == today,
            Class.status == 'ongoing'
        ).count(),
        'online_users': get_active_sessions_count(),
        'pending_uploads': Class.query.filter(
            Class.status == 'completed',
            or_(Class.video_link.is_(None), Class.video_link == '')
        ).count(),
        'alerts': get_real_time_alerts(),
        'system_status': {
            'database': 'healthy',
            'storage': 'healthy',
            'api': 'healthy'
        }
    }
    
    return jsonify(real_time_data)

def get_dashboard_statistics():
    """Optimized dashboard statistics with batch queries"""
    try:
        stats = {}
        today = date.today()
        current_month_start = today.replace(day=1)
        week_ago = today - timedelta(days=7)
        
        # Batch user statistics with a single query
        user_stats = db.session.query(
            func.count(User.id).label('total_users'),
            func.sum(func.case([(User.role.in_(['superadmin', 'admin', 'coordinator']), 1)], else_=0)).label('total_admins'),
            func.sum(func.case([(User.role == 'tutor', 1)], else_=0)).label('total_tutors')
        ).filter(User.is_active == True).first()
        
        stats['total_users'] = int(user_stats.total_users or 0)
        stats['total_admins'] = int(user_stats.total_admins or 0)
        stats['total_tutors'] = int(user_stats.total_tutors or 0)
        
        # Batch student statistics
        student_stats = db.session.query(
            func.count(Student.id).label('total_students'),
            func.sum(func.case([(Student.created_at >= current_month_start, 1)], else_=0)).label('new_this_month'),
            func.sum(func.case([(Student.created_at >= week_ago, 1)], else_=0)).label('new_this_week')
        ).filter(Student.is_active == True).first()
        
        stats['total_students'] = int(student_stats.total_students or 0)
        stats['new_students_this_month'] = int(student_stats.new_this_month or 0)
        stats['new_students_this_week'] = int(student_stats.new_this_week or 0)
        
        # Batch class statistics
        class_stats = db.session.query(
            func.sum(func.case([(Class.scheduled_date == today, 1)], else_=0)).label('todays_classes'),
            func.sum(func.case([(and_(Class.scheduled_date >= current_month_start, Class.scheduled_date <= today), 1)], else_=0)).label('total_this_month'),
            func.sum(func.case([(and_(Class.scheduled_date >= current_month_start, Class.scheduled_date <= today, Class.status == 'completed'), 1)], else_=0)).label('completed_this_month'),
            func.sum(func.case([(and_(Class.scheduled_date > today, Class.status == 'scheduled'), 1)], else_=0)).label('upcoming_classes')
        ).first()
        
        stats['todays_classes'] = int(class_stats.todays_classes or 0)
        stats['total_classes_this_month'] = int(class_stats.total_this_month or 0)
        stats['completed_classes_this_month'] = int(class_stats.completed_this_month or 0)
        stats['upcoming_classes'] = int(class_stats.upcoming_classes or 0)
        
        # Optimized attendance statistics with aggregation
        todays_attendance_stats = db.session.query(
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(and_(Attendance.tutor_present == True, Attendance.student_present == True), 1)], else_=0)).label('present'),
            func.sum(func.case([(or_(Attendance.tutor_present == False, Attendance.student_present == False), 1)], else_=0)).label('absent'),
            func.sum(func.case([(or_(Attendance.tutor_late_minutes > 5, Attendance.student_late_minutes > 5), 1)], else_=0)).label('late'),
            func.sum(func.case([(Attendance.tutor_present == True, 1)], else_=0)).label('tutor_present'),
            func.sum(func.case([(Attendance.student_present == True, 1)], else_=0)).label('student_present')
        ).filter(Attendance.class_date == today).first()
        
        stats['todays_attendance'] = {
            'total': int(todays_attendance_stats.total or 0),
            'present': int(todays_attendance_stats.present or 0),
            'absent': int(todays_attendance_stats.absent or 0),
            'late': int(todays_attendance_stats.late or 0),
            'tutor_present': int(todays_attendance_stats.tutor_present or 0),
            'student_present': int(todays_attendance_stats.student_present or 0)
        }
        
        # Weekly attendance summary with aggregation
        week_attendance_stats = db.session.query(
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(and_(Attendance.tutor_present == True, Attendance.student_present == True), 1)], else_=0)).label('present')
        ).filter(
            Attendance.class_date >= week_ago,
            Attendance.class_date <= today
        ).first()
        
        total_week = int(week_attendance_stats.total or 0)
        present_week = int(week_attendance_stats.present or 0)
        
        stats['week_attendance'] = {
            'total': total_week,
            'present': present_week,
            'completion_rate': round((present_week / total_week) * 100, 1) if total_week > 0 else 0
        }
        
        # Optimized department statistics with batch query
        dept_stats_query = db.session.query(
            Department.id,
            Department.name,
            Department.code,
            func.count(func.distinct(func.case([(User.role == 'tutor', User.id)]))).label('tutors'),
            func.count(func.distinct(Student.id)).label('students')
        ).outerjoin(User, and_(User.department_id == Department.id, User.is_active == True))\
         .outerjoin(Student, and_(Student.department_id == Department.id, Student.is_active == True))\
         .filter(Department.is_active == True)\
         .group_by(Department.id, Department.name, Department.code).all()
        
        stats['departments'] = []
        for dept_stat in dept_stats_query:
            stats['departments'].append({
                'name': dept_stat.name,
                'code': dept_stat.code,
                'tutors': int(dept_stat.tutors or 0),
                'students': int(dept_stat.students or 0),
                'classes_this_month': 0,  # Can be calculated separately if needed
                'attendance_rate': 0,     # Can be calculated separately if needed
                'total_resources': int(dept_stat.tutors or 0) + int(dept_stat.students or 0)
            })
        
        # Performance metrics
        stats['performance'] = {
            'avg_class_duration': get_average_class_duration(),
            'tutor_utilization': get_tutor_utilization_rate(),
            'student_engagement': get_student_engagement_rate(),
            'completion_rate': round((stats['completed_classes_this_month'] / stats['total_classes_this_month']) * 100, 1) if stats['total_classes_this_month'] > 0 else 0
        }
        
        # Financial overview (if implemented)
        stats['finance'] = {
            'monthly_revenue': calculate_monthly_revenue(),
            'pending_fees': calculate_pending_fees(),
            'collection_rate': calculate_collection_rate()
        }
        
        # System health
        stats['system_health'] = {
            'database_status': 'healthy',
            'active_sessions': get_active_sessions_count(),
            'server_load': 'normal',
            'last_backup': get_last_backup_date()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {str(e)}")
        # Return minimal stats on error
        return {
            'total_users': 0, 'total_admins': 0, 'total_tutors': 0,
            'total_students': 0, 'new_students_this_month': 0,
            'todays_classes': 0, 'total_classes_this_month': 0,
            'todays_attendance': {'total': 0, 'present': 0, 'absent': 0},
            'departments': [], 'performance': {}, 'finance': {}, 'system_health': {}
        }

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
        logger.error(f"Error getting pending tasks: {str(e)}")
        return []

# Helper functions for enhanced dashboard statistics
def get_average_class_duration():
    """Calculate average class duration"""
    try:
        avg_duration = db.session.query(func.avg(Class.duration)).filter(
            Class.status == 'completed',
            Class.scheduled_date >= date.today() - timedelta(days=30)
        ).scalar()
        return round(avg_duration, 1) if avg_duration else 60.0
    except Exception:
        return 60.0

def get_tutor_utilization_rate():
    """Calculate tutor utilization rate"""
    try:
        total_tutors = User.query.filter_by(role='tutor', is_active=True).count()
        active_tutors = db.session.query(func.count(func.distinct(Class.tutor_id))).filter(
            Class.scheduled_date >= date.today() - timedelta(days=7),
            Class.status.in_(['completed', 'ongoing', 'scheduled'])
        ).scalar()
        return round((active_tutors / total_tutors) * 100, 1) if total_tutors > 0 else 0
    except Exception:
        return 0

def get_student_engagement_rate():
    """Calculate student engagement rate"""
    try:
        total_students = Student.query.filter_by(is_active=True).count()
        engaged_students = db.session.query(func.count(func.distinct(Class.primary_student_id))).filter(
            Class.scheduled_date >= date.today() - timedelta(days=7),
            Class.status.in_(['completed', 'ongoing', 'scheduled'])
        ).scalar()
        return round((engaged_students / total_students) * 100, 1) if total_students > 0 else 0
    except Exception:
        return 0

def calculate_monthly_revenue():
    """Calculate monthly revenue (placeholder)"""
    try:
        # This would be implemented based on your fee/payment model
        # For now, return a placeholder calculation
        completed_classes = Class.query.filter(
            Class.scheduled_date >= date.today().replace(day=1),
            Class.status == 'completed'
        ).count()
        return completed_classes * 500  # Assuming average rate per class
    except Exception:
        return 0

def calculate_pending_fees():
    """Calculate pending fees (placeholder)"""
    try:
        # This would be implemented based on your fee/payment model
        active_students = Student.query.filter_by(is_active=True).count()
        return active_students * 100  # Placeholder calculation
    except Exception:
        return 0

def calculate_collection_rate():
    """Calculate fee collection rate (placeholder)"""
    try:
        # This would be implemented based on your fee/payment model
        return 85.5  # Placeholder percentage
    except Exception:
        return 0

def get_active_sessions_count():
    """Get count of active user sessions"""
    try:
        # This would depend on your session management
        # For now, return active users from last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        return User.query.filter(User.last_login >= one_hour_ago).count()
    except Exception:
        return 0

def get_last_backup_date():
    """Get last backup date (placeholder)"""
    try:
        # This would be implemented based on your backup system
        return (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    except Exception:
        return 'Unknown'

def get_completion_rate_last_30_days():
    """Get completion rate for last 30 days"""
    try:
        thirty_days_ago = date.today() - timedelta(days=30)
        total_classes = Class.query.filter(
            Class.scheduled_date >= thirty_days_ago,
            Class.scheduled_date <= date.today()
        ).count()
        completed_classes = Class.query.filter(
            Class.scheduled_date >= thirty_days_ago,
            Class.scheduled_date <= date.today(),
            Class.status == 'completed'
        ).count()
        return round((completed_classes / total_classes) * 100, 1) if total_classes > 0 else 0
    except Exception:
        return 0

def get_system_load_metrics():
    """Get system load metrics"""
    try:
        # This would include actual system metrics
        return {
            'cpu_usage': 45,  # Placeholder
            'memory_usage': 62,  # Placeholder
            'disk_usage': 78,  # Placeholder
            'network_activity': 'normal'
        }
    except Exception:
        return {'cpu_usage': 0, 'memory_usage': 0, 'disk_usage': 0, 'network_activity': 'unknown'}

def get_department_detailed_analytics(department):
    """Get detailed analytics for a department"""
    try:
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get department tutors and students
        dept_tutors = User.query.filter_by(department_id=department.id, role='tutor', is_active=True).all()
        dept_students = Student.query.filter_by(department_id=department.id, is_active=True).all()
        
        # Get classes analytics
        dept_classes = Class.query.join(Tutor).join(User).filter(
            User.department_id == department.id,
            Class.scheduled_date >= month_ago
        ).all()
        
        completed_classes = [c for c in dept_classes if c.status == 'completed']
        
        # Calculate metrics
        avg_attendance_rate = 0
        if dept_classes:
            attendance_records = Attendance.query.join(Class).join(Tutor).join(User).filter(
                User.department_id == department.id,
                Attendance.class_date >= week_ago
            ).all()
            
            if attendance_records:
                present_count = len([a for a in attendance_records if a.tutor_present and a.student_present])
                avg_attendance_rate = round((present_count / len(attendance_records)) * 100, 1)
        
        return {
            'id': department.id,
            'name': department.name,
            'code': department.code,
            'tutors_count': len(dept_tutors),
            'students_count': len(dept_students),
            'classes_this_month': len(dept_classes),
            'completed_classes': len(completed_classes),
            'completion_rate': round((len(completed_classes) / len(dept_classes)) * 100, 1) if dept_classes else 0,
            'attendance_rate': avg_attendance_rate,
            'active_tutors': len([t for t in dept_tutors if any(c.tutor_id == t.tutor_profile.id if t.tutor_profile else False for c in dept_classes)]),
            'revenue_estimate': len(completed_classes) * 500,  # Placeholder calculation
            'performance_score': calculate_department_performance_score(department)
        }
    except Exception as e:
        logger.error(f"Error getting department analytics: {str(e)}")
        return {
            'id': department.id,
            'name': department.name,
            'code': department.code,
            'error': 'Failed to load analytics'
        }

def calculate_department_performance_score(department):
    """Calculate a performance score for the department"""
    try:
        # This would be a complex calculation based on multiple factors
        # For now, return a placeholder score
        return round(75.5 + (department.id % 20), 1)  # Placeholder calculation
    except Exception:
        return 0

def get_real_time_alerts():
    """Get real-time alerts for the dashboard"""
    try:
        alerts = []
        current_time = datetime.now()
        
        # Check for classes starting soon (within 15 minutes)
        upcoming_classes = Class.query.filter(
            Class.scheduled_date == current_time.date(),
            Class.status == 'scheduled'
        ).all()
        
        for class_obj in upcoming_classes:
            if class_obj.scheduled_time:
                class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
                time_diff = (class_datetime - current_time).total_seconds() / 60
                
                if 0 <= time_diff <= 15:
                    alerts.append({
                        'type': 'class_starting',
                        'message': f'Class {class_obj.subject} starting in {int(time_diff)} minutes',
                        'severity': 'info',
                        'class_id': class_obj.id
                    })
        
        # Check for overdue video uploads
        overdue_uploads = Class.query.filter(
            Class.status == 'completed',
            Class.actual_end_time < current_time - timedelta(hours=2),
            or_(Class.video_link.is_(None), Class.video_link == '')
        ).count()
        
        if overdue_uploads > 0:
            alerts.append({
                'type': 'overdue_uploads',
                'message': f'{overdue_uploads} classes with overdue video uploads',
                'severity': 'warning',
                'count': overdue_uploads
            })
        
        # Check for system issues (placeholder)
        # Add more real-time checks as needed
        
        return alerts
    except Exception as e:
        logger.error(f"Error getting real-time alerts: {str(e)}")
        return []

@bp.route('/admin/system-logs')
@login_required
@handle_dashboard_errors
def system_logs():
    """System logs view for administrators"""
    if current_user.role not in ['superadmin', 'admin']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard.admin_dashboard'))
    
    # This is a placeholder route - you can implement actual log viewing here
    logs = [
        {'timestamp': datetime.now(), 'level': 'INFO', 'message': 'System functioning normally'},
        {'timestamp': datetime.now(), 'level': 'INFO', 'message': 'Dashboard enhanced sections loaded successfully'},
        {'timestamp': datetime.now(), 'level': 'INFO', 'message': 'Database connectivity: OK'},
    ]
    
    return render_template('dashboard/system_logs.html', logs=logs)