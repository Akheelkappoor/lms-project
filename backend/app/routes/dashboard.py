# backend/app/routes/dashboard.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.user import User
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.finance import TutorSalary, StudentFee
from app.models import db
from datetime import datetime, timedelta
from sqlalchemy import func, and_

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] in ['superadmin', 'admin']:
        return get_admin_stats()
    elif claims['role'] == 'coordinator':
        return get_coordinator_stats(claims.get('department_id'))
    elif claims['role'] == 'tutor':
        return get_tutor_stats(current_user_id)
    elif claims['role'] == 'student':
        return get_student_stats(current_user_id)
    else:
        return jsonify({'error': 'Unauthorized'}), 403

def get_admin_stats():
    today = datetime.utcnow().date()
    this_month_start = today.replace(day=1)
    
    # User counts
    total_users = User.query.filter_by(is_active=True).count()
    total_tutors = User.query.filter_by(role='tutor', is_active=True).count()
    total_students = User.query.filter_by(role='student', is_active=True).count()
    total_coordinators = User.query.filter_by(role='coordinator', is_active=True).count()
    
    # Today's classes
    today_classes = Class.query.filter(
        func.date(Class.scheduled_start) == today
    ).count()
    
    # This month's stats
    classes_this_month = Class.query.filter(
        Class.scheduled_start >= this_month_start
    ).count()
    
    # Revenue this month
    revenue_this_month = db.session.query(func.sum(StudentFee.paid_amount)).filter(
        StudentFee.payment_date >= this_month_start,
        StudentFee.status == 'paid'
    ).scalar() or 0
    
    # Pending fees
    pending_fees = db.session.query(func.sum(StudentFee.amount - StudentFee.paid_amount)).filter(
        StudentFee.status.in_(['pending', 'partial'])
    ).scalar() or 0
    
    # Recent activities
    recent_classes = Class.query.filter(
        Class.scheduled_start >= datetime.utcnow() - timedelta(days=7)
    ).order_by(Class.scheduled_start.desc()).limit(10).all()
    
    return jsonify({
        'user_stats': {
            'total_users': total_users,
            'total_tutors': total_tutors,
            'total_students': total_students,
            'total_coordinators': total_coordinators
        },
        'class_stats': {
            'today_classes': today_classes,
            'classes_this_month': classes_this_month
        },
        'financial_stats': {
            'revenue_this_month': float(revenue_this_month),
            'pending_fees': float(pending_fees)
        },
        'recent_activities': [
            {
                'id': cls.id,
                'title': cls.title,
                'subject': cls.subject,
                'scheduled_start': cls.scheduled_start.isoformat(),
                'status': cls.status
            }
            for cls in recent_classes
        ]
    }), 200

def get_tutor_stats(user_id):
    tutor = Tutor.query.filter_by(user_id=user_id).first()
    if not tutor:
        return jsonify({'error': 'Tutor profile not found'}), 404
    
    today = datetime.utcnow().date()
    this_month_start = today.replace(day=1)
    
    # Today's classes
    today_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        func.date(Class.scheduled_start) == today
    ).order_by(Class.scheduled_start).all()
    
    # This month's classes
    classes_this_month = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_start >= this_month_start
    ).count()
    
    # Completed classes this month
    completed_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_start >= this_month_start,
        Class.status == 'completed'
    ).count()
    
    # Attendance stats
    attendance_records = Attendance.query.join(Class).filter(
        Class.tutor_id == tutor.id,
        Attendance.user_id == user_id,
        Attendance.marked_at >= this_month_start
    ).all()
    
    present_count = len([r for r in attendance_records if r.status == 'present'])
    late_count = len([r for r in attendance_records if r.status == 'late'])
    
    # Earnings this month
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year
    
    salary_record = TutorSalary.query.filter_by(
        tutor_id=tutor.id,
        month=current_month,
        year=current_year
    ).first()
    
    projected_earnings = salary_record.total_amount if salary_record else 0
    
    return jsonify({
        'today_classes': [
            {
                'id': cls.id,
                'title': cls.title,
                'subject': cls.subject,
                'scheduled_start': cls.scheduled_start.isoformat(),
                'scheduled_end': cls.scheduled_end.isoformat(),
                'status': cls.status,
                'meeting_url': cls.meeting_url
            }
            for cls in today_classes
        ],
        'monthly_stats': {
            'total_classes': classes_this_month,
            'completed_classes': completed_classes,
            'attendance_rate': (present_count + late_count) / len(attendance_records) * 100 if attendance_records else 0,
            'projected_earnings': float(projected_earnings)
        },
        'performance': {
            'total_classes_taught': tutor.total_classes_taught,
            'performance_rating': tutor.performance_rating,
            'verification_status': tutor.verification_status
        }
    }), 200

def get_student_stats(user_id):
    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({'error': 'Student profile not found'}), 404
    
    today = datetime.utcnow().date()
    this_month_start = today.replace(day=1)
    
    # Today's classes
    today_classes = Class.query.filter(
        Class.students.contains([student.id]),
        func.date(Class.scheduled_start) == today
    ).order_by(Class.scheduled_start).all()
    
    # This month's classes
    classes_this_month = Class.query.filter(
        Class.students.contains([student.id]),
        Class.scheduled_start >= this_month_start
    ).count()
    
    # Attendance stats
    attendance_records = Attendance.query.join(Class).filter(
        Class.students.contains([student.id]),
        Attendance.user_id == user_id,
        Attendance.marked_at >= this_month_start
    ).all()
    
    present_count = len([r for r in attendance_records if r.status == 'present'])
    
    # Fee status
    pending_fees = StudentFee.query.filter(
        StudentFee.student_id == student.id,
        StudentFee.status.in_(['pending', 'partial'])
    ).all()
    
    total_pending = sum(fee.amount - fee.paid_amount for fee in pending_fees)
    
    return jsonify({
        'today_classes': [
            {
                'id': cls.id,
                'title': cls.title,
                'subject': cls.subject,
                'scheduled_start': cls.scheduled_start.isoformat(),
                'scheduled_end': cls.scheduled_end.isoformat(),
                'status': cls.status,
                'meeting_url': cls.meeting_url
            }
            for cls in today_classes
        ],
        'monthly_stats': {
            'total_classes': classes_this_month,
            'attendance_rate': present_count / len(attendance_records) * 100 if attendance_records else 0
        },
        'fee_info': {
            'total_pending': float(total_pending),
            'pending_fees_count': len(pending_fees)
        },
        'academic_info': {
            'grade_level': student.grade_level,
            'educational_board': student.educational_board,
            'classes_enrolled': student.classes_enrolled
        }
    }), 200