# backend/app/routes/classes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.class_model import Class
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.user import User
from app.models import db
from app.utils.decorators import require_role
from datetime import datetime, timedelta
import uuid

classes_bp = Blueprint('classes', __name__)

@classes_bp.route('', methods=['GET'])
@jwt_required()
def get_classes():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    tutor_id = request.args.get('tutor_id')
    student_id = request.args.get('student_id')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Class.query
    
    # Filter by user role
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] == 'tutor':
        # Tutors can only see their own classes
        tutor = Tutor.query.filter_by(user_id=current_user_id).first()
        if tutor:
            query = query.filter(Class.tutor_id == tutor.id)
    elif claims['role'] == 'student':
        # Students can only see classes they're enrolled in
        student = Student.query.filter_by(user_id=current_user_id).first()
        if student:
            query = query.filter(Class.students.contains([student.id]))
    
    # Apply filters
    if tutor_id:
        query = query.filter(Class.tutor_id == tutor_id)
    if student_id:
        query = query.filter(Class.students.contains([student_id]))
    if status:
        query = query.filter(Class.status == status)
    if date_from:
        query = query.filter(Class.scheduled_start >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Class.scheduled_start <= datetime.fromisoformat(date_to))
    
    query = query.order_by(Class.scheduled_start.desc())
    classes = query.paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for cls in classes.items:
        class_data = cls.to_dict()
        # Add tutor info
        class_data['tutor'] = cls.tutor.user.to_dict()
        # Add student info
        if cls.students:
            students_info = []
            for student_id in cls.students:
                student = Student.query.get(student_id)
                if student:
                    students_info.append(student.user.to_dict())
            class_data['students_info'] = students_info
        result.append(class_data)
    
    return jsonify({
        'classes': result,
        'total': classes.total,
        'pages': classes.pages,
        'current_page': page
    }), 200

@classes_bp.route('', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator'])
def create_class():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['title', 'subject', 'class_type', 'tutor_id', 'scheduled_start', 'scheduled_end']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Validate tutor exists
    tutor = Tutor.query.get(data['tutor_id'])
    if not tutor:
        return jsonify({'error': 'Tutor not found'}), 404
    
    # backend/app/routes/classes.py (continued)
    # Validate students for group classes
    if data['class_type'] == 'group' and not data.get('students'):
        return jsonify({'error': 'Students required for group classes'}), 400
    
    # Check for scheduling conflicts
    scheduled_start = datetime.fromisoformat(data['scheduled_start'])
    scheduled_end = datetime.fromisoformat(data['scheduled_end'])
    
    # Check tutor availability
    conflicting_classes = Class.query.filter(
        Class.tutor_id == data['tutor_id'],
        Class.status.in_(['scheduled', 'ongoing']),
        Class.scheduled_start < scheduled_end,
        Class.scheduled_end > scheduled_start
    ).first()
    
    if conflicting_classes:
        return jsonify({'error': 'Tutor has conflicting class at this time'}), 409
    
    # Create class
    new_class = Class(
        id=str(uuid.uuid4()),
        title=data['title'],
        subject=data['subject'],
        grade_level=data.get('grade_level'),
        class_type=data['class_type'],
        tutor_id=data['tutor_id'],
        students=data.get('students', []),
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        meeting_platform=data.get('meeting_platform', 'zoom'),
        meeting_url=data.get('meeting_url'),
        meeting_id=data.get('meeting_id'),
        meeting_password=data.get('meeting_password'),
        backup_meeting_url=data.get('backup_meeting_url')
    )
    
    db.session.add(new_class)
    db.session.commit()
    
    return jsonify({
        'message': 'Class created successfully',
        'class': new_class.to_dict()
    }), 201

@classes_bp.route('/<class_id>', methods=['GET'])
@jwt_required()
def get_class(class_id):
    cls = Class.query.get_or_404(class_id)
    
    # Check access permissions
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] == 'tutor':
        tutor = Tutor.query.filter_by(user_id=current_user_id).first()
        if not tutor or cls.tutor_id != tutor.id:
            return jsonify({'error': 'Unauthorized'}), 403
    elif claims['role'] == 'student':
        student = Student.query.filter_by(user_id=current_user_id).first()
        if not student or student.id not in cls.students:
            return jsonify({'error': 'Unauthorized'}), 403
    
    class_data = cls.to_dict()
    class_data['tutor'] = cls.tutor.user.to_dict()
    
    if cls.students:
        students_info = []
        for student_id in cls.students:
            student = Student.query.get(student_id)
            if student:
                students_info.append(student.user.to_dict())
        class_data['students_info'] = students_info
    
    return jsonify(class_data), 200

@classes_bp.route('/<class_id>', methods=['PUT'])
@jwt_required()
def update_class(class_id):
    cls = Class.query.get_or_404(class_id)
    data = request.get_json()
    
    # Check permissions
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] == 'tutor':
        tutor = Tutor.query.filter_by(user_id=current_user_id).first()
        if not tutor or cls.tutor_id != tutor.id:
            return jsonify({'error': 'Unauthorized'}), 403
    elif claims['role'] not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update allowed fields
    updatable_fields = ['title', 'class_notes', 'homework_assigned', 'materials_shared']
    
    if claims['role'] in ['superadmin', 'admin', 'coordinator']:
        updatable_fields.extend(['scheduled_start', 'scheduled_end', 'meeting_url', 'meeting_password'])
    
    for field in updatable_fields:
        if field in data:
            if field in ['scheduled_start', 'scheduled_end']:
                setattr(cls, field, datetime.fromisoformat(data[field]))
            else:
                setattr(cls, field, data[field])
    
    db.session.commit()
    return jsonify(cls.to_dict()), 200

@classes_bp.route('/<class_id>/start', methods=['POST'])
@jwt_required()
def start_class(class_id):
    cls = Class.query.get_or_404(class_id)
    
    # Only tutor can start the class
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] != 'tutor':
        return jsonify({'error': 'Only tutors can start classes'}), 403
    
    tutor = Tutor.query.filter_by(user_id=current_user_id).first()
    if not tutor or cls.tutor_id != tutor.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    cls.status = 'ongoing'
    cls.actual_start = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Class started successfully',
        'class': cls.to_dict()
    }), 200

@classes_bp.route('/<class_id>/end', methods=['POST'])
@jwt_required()
def end_class(class_id):
    cls = Class.query.get_or_404(class_id)
    
    # Only tutor can end the class
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] != 'tutor':
        return jsonify({'error': 'Only tutors can end classes'}), 403
    
    tutor = Tutor.query.filter_by(user_id=current_user_id).first()
    if not tutor or cls.tutor_id != tutor.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    cls.status = 'completed'
    cls.actual_end = datetime.utcnow()
    cls.class_notes = data.get('class_notes', cls.class_notes)
    cls.homework_assigned = data.get('homework_assigned', cls.homework_assigned)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Class ended successfully',
        'class': cls.to_dict()
    }), 200

@classes_bp.route('/<class_id>/cancel', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator', 'tutor'])
def cancel_class(class_id):
    cls = Class.query.get_or_404(class_id)
    data = request.get_json()
    
    # Check permissions
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    if claims['role'] == 'tutor':
        tutor = Tutor.query.filter_by(user_id=current_user_id).first()
        if not tutor or cls.tutor_id != tutor.id:
            return jsonify({'error': 'Unauthorized'}), 403
    
    cls.status = 'cancelled'
    cls.cancellation_reason = data.get('reason', 'No reason provided')
    
    db.session.commit()
    
    # Send notifications to students
    # notification_service.send_class_cancellation_notice(cls)
    
    return jsonify({
        'message': 'Class cancelled successfully',
        'class': cls.to_dict()
    }), 200

@classes_bp.route('/today', methods=['GET'])
@jwt_required()
def get_today_classes():
    claims = get_jwt()
    current_user_id = get_jwt_identity()
    
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    
    query = Class.query.filter(
        Class.scheduled_start >= today,
        Class.scheduled_start < tomorrow
    )
    
    # Filter by user role
    if claims['role'] == 'tutor':
        tutor = Tutor.query.filter_by(user_id=current_user_id).first()
        if tutor:
            query = query.filter(Class.tutor_id == tutor.id)
    elif claims['role'] == 'student':
        student = Student.query.filter_by(user_id=current_user_id).first()
        if student:
            query = query.filter(Class.students.contains([student.id]))
    
    classes = query.order_by(Class.scheduled_start).all()
    
    result = []
    for cls in classes:
        class_data = cls.to_dict()
        class_data['tutor'] = cls.tutor.user.to_dict()
        result.append(class_data)
    
    return jsonify({'classes': result}), 200

