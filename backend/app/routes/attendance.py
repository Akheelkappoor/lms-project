# backend/app/routes/attendance.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.attendance import Attendance
from app.models.class_model import Class
from app.models.user import User
from app.models.tutor import Tutor
from app.models.student import Student
from app.models import db
from app.utils.decorators import require_role
from datetime import datetime, timedelta
import uuid

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('', methods=['POST'])
@jwt_required()
def mark_attendance():
    data = request.get_json()
    
    required_fields = ['class_id', 'user_id', 'user_type', 'status']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Validate class exists
    cls = Class.query.get(data['class_id'])
    if not cls:
        return jsonify({'error': 'Class not found'}), 404
    
    # Check if attendance already marked
    existing_attendance = Attendance.query.filter_by(
        class_id=data['class_id'],
        user_id=data['user_id']
    ).first()
    
    if existing_attendance:
        return jsonify({'error': 'Attendance already marked for this user'}), 409
    
    # Calculate late minutes if status is 'late'
    late_minutes = 0
    if data['status'] == 'late' and data.get('join_time'):
        join_time = datetime.fromisoformat(data['join_time'])
        scheduled_start = cls.scheduled_start
        if join_time > scheduled_start:
            late_minutes = int((join_time - scheduled_start).total_seconds() / 60)
    
    # Create attendance record
    attendance = Attendance(
        id=str(uuid.uuid4()),
        class_id=data['class_id'],
        user_id=data['user_id'],
        user_type=data['user_type'],
        status=data['status'],
        join_time=datetime.fromisoformat(data['join_time']) if data.get('join_time') else None,
        leave_time=datetime.fromisoformat(data['leave_time']) if data.get('leave_time') else None,
        late_minutes=late_minutes,
        participation_rating=data.get('participation_rating'),
        notes=data.get('notes'),
        marked_by=get_jwt_identity()
    )
    
    db.session.add(attendance)
    db.session.commit()
    
    return jsonify({
        'message': 'Attendance marked successfully',
        'attendance': {
            'id': attendance.id,
            'class_id': attendance.class_id,
            'user_id': attendance.user_id,
            'status': attendance.status,
            'late_minutes': attendance.late_minutes,
            'marked_at': attendance.marked_at.isoformat()
        }
    }), 201

@attendance_bp.route('/class/<class_id>', methods=['GET'])
@jwt_required()
def get_class_attendance(class_id):
    cls = Class.query.get_or_404(class_id)
    
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    result = []
    for record in attendance_records:
        user = User.query.get(record.user_id)
        attendance_data = {
            'id': record.id,
            'user_id': record.user_id,
            'user_name': user.full_name if user else 'Unknown',
            'user_type': record.user_type,
            'status': record.status,
            'join_time': record.join_time.isoformat() if record.join_time else None,
            'leave_time': record.leave_time.isoformat() if record.leave_time else None,
            'late_minutes': record.late_minutes,
            'participation_rating': record.participation_rating,
            'notes': record.notes,
            'marked_at': record.marked_at.isoformat()
        }
        result.append(attendance_data)
    
    return jsonify({
        'class_id': class_id,
        'class_title': cls.title,
        'attendance': result
    }), 200

@attendance_bp.route('/tutor/<tutor_id>', methods=['GET'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator', 'tutor'])
def get_tutor_attendance(tutor_id):
    # Date filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Check permissions
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] == 'tutor':
        tutor = Tutor.query.filter_by(user_id=current_user_id).first()
        if not tutor or tutor.id != tutor_id:
            return jsonify({'error': 'Unauthorized'}), 403
    
    # Get tutor's classes
    query = Class.query.filter(Class.tutor_id == tutor_id)
    
    if date_from:
        query = query.filter(Class.scheduled_start >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Class.scheduled_start <= datetime.fromisoformat(date_to))
    
    classes = query.all()
    class_ids = [cls.id for cls in classes]
    
    # Get attendance records for tutor
    attendance_records = Attendance.query.filter(
        Attendance.class_id.in_(class_ids),
        Attendance.user_type == 'tutor'
    ).order_by(Attendance.marked_at.desc()).all()
    
    # Calculate statistics
    total_classes = len(classes)
    present_count = len([r for r in attendance_records if r.status == 'present'])
    late_count = len([r for r in attendance_records if r.status == 'late'])
    absent_count = total_classes - present_count - late_count
    
    return jsonify({
        'tutor_id': tutor_id,
        'total_classes': total_classes,
        'present': present_count,
        'late': late_count,
        'absent': absent_count,
        'attendance_percentage': (present_count + late_count) / total_classes * 100 if total_classes > 0 else 0,
        'records': [
            {
                'class_id': record.class_id,
                'status': record.status,
                'late_minutes': record.late_minutes,
                'marked_at': record.marked_at.isoformat()
            }
            for record in attendance_records
        ]
    }), 200