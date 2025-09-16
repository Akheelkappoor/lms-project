from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_, text
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
import logging
import time
from functools import wraps

# Set up logging
logger = logging.getLogger(__name__)

def handle_errors(f):
    """Decorator to handle errors in dashboard routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            start_time = time.time()
            result = f(*args, **kwargs)
            end_time = time.time()
            logger.info(f"{f.__name__} executed in {end_time - start_time:.2f} seconds")
            return result
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            flash(f'Dashboard loading error: {str(e)}', 'error')
            return render_template('errors/dashboard_error.html', error=str(e))
    return decorated_function

bp = Blueprint('dashboard_optimized', __name__)

@bp.route('/')
def index():
    """Optimized index route with error handling"""
    try:
        if current_user.is_authenticated:
            if current_user.role in ['superadmin', 'admin', 'coordinator']:
                return redirect(url_for('dashboard_optimized.admin_dashboard'))
            elif current_user.role == 'tutor':
                return redirect(url_for('dashboard_optimized.tutor_dashboard'))
        
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Index route error: {str(e)}")
        return render_template('errors/500.html'), 500

@bp.route('/dashboard')
@login_required
@handle_errors
def admin_dashboard():
    """Optimized admin dashboard with comprehensive error handling"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_optimized.index'))
    
    try:
        # Get all data in parallel with optimized queries
        stats = get_optimized_dashboard_statistics()
        today = date.today()
        
        # Optimized today's classes query with eager loading
        todays_classes = Class.query.options(
            joinedload(Class.tutor).joinedload(Tutor.user),
            joinedload(Class.primary_student)
        ).filter_by(scheduled_date=today).all()
        
        # Get recent activities efficiently
        week_ago = today - timedelta(days=7)
        recent_students = Student.query.options(
            joinedload(Student.department)
        ).filter(
            Student.created_at >= week_ago
        ).order_by(Student.created_at.desc()).limit(5).all()
        
        recent_tutors = Tutor.query.options(
            joinedload(Tutor.user),
            joinedload(Tutor.department)
        ).filter(
            Tutor.created_at >= week_ago
        ).order_by(Tutor.created_at.desc()).limit(5).all()
        
        # Get optimized attendance alerts
        attendance_alerts = get_optimized_attendance_alerts()
        
        # Get optimized pending tasks
        pending_tasks = get_optimized_pending_tasks()
        
        return render_template('dashboard/admin_dashboard.html',
                             stats=stats,
                             todays_classes=todays_classes,
                             recent_students=recent_students,
                             recent_tutors=recent_tutors,
                             attendance_alerts=attendance_alerts,
                             pending_tasks=pending_tasks)
    
    except Exception as e:
        logger.error(f"Admin dashboard error: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('dashboard/admin_dashboard.html', 
                             stats={}, todays_classes=[], recent_students=[], 
                             recent_tutors=[], attendance_alerts=[], pending_tasks=[])

@bp.route('/tutor-dashboard')
@login_required
@handle_errors
def tutor_dashboard():
    """Optimized tutor dashboard with comprehensive error handling"""
    if current_user.role != 'tutor':
        flash('Access denied. This page is for tutors only.', 'error')
        return redirect(url_for('dashboard_optimized.index'))
    
    try:
        tutor = Tutor.query.options(
            joinedload(Tutor.user)
        ).filter_by(user_id=current_user.id).first()
        
        if not tutor:
            flash('Tutor profile not found. Please contact administrator.', 'error')
            return redirect(url_for('dashboard_optimized.index'))
        
        # Get optimized tutor statistics
        tutor_stats = get_optimized_tutor_statistics(tutor)
        
        today = date.today()
        
        # Optimized today's classes
        todays_classes = Class.query.options(
            joinedload(Class.primary_student)
        ).filter_by(
            tutor_id=tutor.id, 
            scheduled_date=today
        ).all()
        
        # Get this week's classes efficiently
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        week_classes = Class.query.options(
            joinedload(Class.primary_student)
        ).filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date >= week_start,
            Class.scheduled_date <= week_end
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        # Get upcoming classes efficiently
        upcoming_classes = Class.query.options(
            joinedload(Class.primary_student)
        ).filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date > today,
            Class.scheduled_date <= today + timedelta(days=7),
            Class.status.in_(['scheduled'])
        ).order_by(Class.scheduled_date, Class.scheduled_time).limit(10).all()
        
        # Get recent attendance efficiently
        recent_attendance = Attendance.query.options(
            joinedload(Attendance.student),
            joinedload(Attendance.class_session)
        ).filter_by(tutor_id=tutor.id).order_by(
            Attendance.class_date.desc()
        ).limit(10).all()
        
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
    
    except Exception as e:
        logger.error(f"Tutor dashboard error: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('dashboard/tutor_dashboard.html',
                             tutor=None, stats={}, todays_classes=[], 
                             week_classes=[], upcoming_classes=[], 
                             recent_attendance=[], monthly_earnings=0)

def get_optimized_dashboard_statistics():
    """Optimized dashboard statistics with single queries"""
    try:
        stats = {}
        
        # Single query for user statistics
        user_stats = db.session.query(
            func.count(User.id).label('total_users'),
            func.sum(func.case([(User.role.in_(['superadmin', 'admin', 'coordinator']), 1)], else_=0)).label('total_admins'),
            func.sum(func.case([(User.role == 'tutor', 1)], else_=0)).label('total_tutors')
        ).filter(User.is_active == True).first()
        
        stats.update({
            'total_users': user_stats.total_users or 0,
            'total_admins': user_stats.total_admins or 0,
            'total_tutors': user_stats.total_tutors or 0
        })
        
        # Single query for student statistics
        current_month_start = datetime.now().replace(day=1)
        student_stats = db.session.query(
            func.count(Student.id).label('total_students'),
            func.sum(func.case([(Student.created_at >= current_month_start, 1)], else_=0)).label('new_this_month')
        ).filter(Student.is_active == True).first()
        
        stats.update({
            'total_students': student_stats.total_students or 0,
            'new_students_this_month': student_stats.new_this_month or 0
        })
        
        # Single query for class statistics
        today = date.today()
        month_start = today.replace(day=1)
        
        class_stats = db.session.query(
            func.sum(func.case([(Class.scheduled_date == today, 1)], else_=0)).label('todays_classes'),
            func.sum(func.case([(Class.scheduled_date >= month_start, 1)], else_=0)).label('month_classes')
        ).first()
        
        stats.update({
            'todays_classes': class_stats.todays_classes or 0,
            'total_classes_this_month': class_stats.month_classes or 0
        })
        
        # Optimized attendance statistics for today
        attendance_stats = db.session.query(
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(and_(Attendance.tutor_present == True, Attendance.student_present == True), 1)], else_=0)).label('both_present'),
            func.sum(func.case([(or_(Attendance.tutor_present == False, Attendance.student_present == False), 1)], else_=0)).label('any_absent')
        ).filter(Attendance.class_date == today).first()
        
        stats['todays_attendance'] = {
            'total': attendance_stats.total or 0,
            'present': attendance_stats.both_present or 0,
            'absent': attendance_stats.any_absent or 0
        }
        
        # Optimized department statistics
        dept_stats = db.session.query(
            Department.id,
            Department.name,
            func.count(func.distinct(User.id)).filter(User.role == 'tutor').label('tutors'),
            func.count(func.distinct(Student.id)).label('students')
        ).outerjoin(User, User.department_id == Department.id).outerjoin(
            Student, Student.department_id == Department.id
        ).filter(
            Department.is_active == True,
            or_(User.is_active == True, User.id.is_(None)),
            or_(Student.is_active == True, Student.id.is_(None))
        ).group_by(Department.id, Department.name).all()
        
        stats['departments'] = [
            {
                'name': dept.name,
                'tutors': dept.tutors or 0,
                'students': dept.students or 0
            }
            for dept in dept_stats
        ]
        
        # Revenue statistics (placeholder)
        stats['monthly_revenue'] = 0
        stats['pending_fees'] = 0
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {str(e)}")
        return {
            'total_users': 0, 'total_admins': 0, 'total_tutors': 0,
            'total_students': 0, 'new_students_this_month': 0,
            'todays_classes': 0, 'total_classes_this_month': 0,
            'todays_attendance': {'total': 0, 'present': 0, 'absent': 0},
            'departments': [], 'monthly_revenue': 0, 'pending_fees': 0
        }

def get_optimized_tutor_statistics(tutor):
    """Optimized tutor statistics with single queries"""
    try:
        stats = {}
        
        # Basic tutor stats
        stats.update({
            'total_classes': tutor.total_classes or 0,
            'completed_classes': tutor.completed_classes or 0,
            'completion_rate': tutor.get_completion_rate() or 0,
            'rating': tutor.rating or 0
        })
        
        # This month's classes
        current_month = datetime.now().month
        current_year = datetime.now().year
        month_start = date(current_year, current_month, 1)
        
        month_stats = db.session.query(
            func.count(Class.id).filter(Class.scheduled_date >= month_start).label('this_month'),
            func.count(Class.id).filter(
                and_(Class.scheduled_date > date.today(), Class.status == 'scheduled')
            ).label('upcoming'),
            func.count(func.distinct(Class.primary_student_id)).label('unique_students')
        ).filter(Class.tutor_id == tutor.id).first()
        
        stats.update({
            'this_month_classes': month_stats.this_month or 0,
            'upcoming_classes': month_stats.upcoming or 0,
            'total_students': month_stats.unique_students or 0
        })
        
        # Attendance statistics (use existing method but with error handling)
        try:
            attendance_summary = Attendance.get_attendance_summary(tutor_id=tutor.id)
            stats['attendance'] = attendance_summary
        except Exception as e:
            logger.error(f"Error getting attendance summary: {str(e)}")
            stats['attendance'] = {
                'total_classes': 0, 'present_count': 0, 'absent_count': 0,
                'late_count': 0, 'attendance_percentage': 0
            }
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting tutor statistics: {str(e)}")
        return {
            'total_classes': 0, 'completed_classes': 0, 'completion_rate': 0,
            'this_month_classes': 0, 'total_students': 0, 'rating': 0,
            'upcoming_classes': 0, 'attendance': {}
        }

def get_optimized_attendance_alerts():
    """Optimized attendance alerts with single query"""
    try:
        today = date.today()
        alerts = []
        
        # Single query for all attendance issues today
        attendance_issues = Attendance.query.options(
            joinedload(Attendance.tutor).joinedload(Tutor.user),
            joinedload(Attendance.student)
        ).filter(
            Attendance.class_date == today,
            or_(
                Attendance.tutor_late_minutes > 5,
                Attendance.student_late_minutes > 5,
                Attendance.tutor_present == False,
                Attendance.student_present == False
            )
        ).limit(10).all()
        
        for attendance in attendance_issues:
            try:
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
            except AttributeError as e:
                logger.warning(f"Missing attribute in attendance alert: {str(e)}")
                continue
        
        return alerts[:10]
    
    except Exception as e:
        logger.error(f"Error getting attendance alerts: {str(e)}")
        return []

def get_optimized_pending_tasks():
    """Optimized pending tasks with single queries"""
    try:
        tasks = []
        
        # Single query for pending tutor verifications
        pending_tutors = Tutor.query.filter_by(verification_status='pending').count()
        if pending_tutors > 0:
            tasks.append({
                'type': 'verification',
                'title': 'Pending Tutor Verifications',
                'count': pending_tutors,
                'url': url_for('admin.tutors'),
                'priority': 'high'
            })
        
        # Optimized overdue fee calculation (placeholder - implement based on your fee model)
        # This would need to be optimized based on your actual fee tracking system
        overdue_count = 0  # Replace with actual optimized query
        
        if overdue_count > 0:
            tasks.append({
                'type': 'payment',
                'title': 'Overdue Fee Payments',
                'count': overdue_count,
                'url': url_for('admin.students'),
                'priority': 'medium'
            })
        
        return tasks
    
    except Exception as e:
        logger.error(f"Error getting pending tasks: {str(e)}")
        return []

@bp.route('/api/dashboard-stats')
@login_required
@handle_errors
def api_dashboard_stats():
    """Optimized API endpoint for dashboard statistics"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    stats = get_optimized_dashboard_statistics()
    return jsonify(stats)

@bp.route('/api/attendance-chart')
@login_required
@handle_errors
def api_attendance_chart():
    """Optimized API endpoint for attendance chart data"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get attendance data for last 30 days with optimized query
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
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
    
    except Exception as e:
        logger.error(f"Error generating attendance chart: {str(e)}")
        return jsonify({'error': 'Failed to load chart data'}), 500