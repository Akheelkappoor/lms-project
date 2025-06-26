from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.user import User
from app.models.student import Student
from app.models import db
from app.utils.decorators import require_role
from app.services.file_service import FileService
import uuid

students_bp = Blueprint('students', __name__)
file_service = FileService()

@students_bp.route('', methods=['GET'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator'])
def get_students():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    grade_level = request.args.get('grade_level')
    educational_board = request.args.get('educational_board')
    fee_status = request.args.get('fee_status')
    
    query = Student.query.join(User)
    
    if grade_level:
        query = query.filter(Student.grade_level == grade_level)
    if educational_board:
        query = query.filter(Student.educational_board == educational_board)
    
    students = query.paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for student in students.items:
        student_data = student.to_dict()
        student_data['user'] = student.user.to_dict()
        result.append(student_data)
    
    return jsonify({
        'students': result,
        'total': students.total,
        'pages': students.pages,
        'current_page': page
    }), 200

@students_bp.route('', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator'])
def create_student():
    data = request.get_json()
    
    # Create user account
    user_data = data.get('user', {})
    
    # Check if username or email already exists
    if User.query.filter_by(username=user_data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=user_data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    # Create user
    user = User(
        id=str(uuid.uuid4()),
        username=user_data['username'],
        email=user_data['email'],
        full_name=user_data['full_name'],
        phone_number=user_data.get('phone_number'),
        role='student',
        department_id=user_data.get('department_id')
    )
    
    # Generate temporary password
    temp_password = str(uuid.uuid4())[:12]
    user.set_password(temp_password)
    
    db.session.add(user)
    db.session.flush()
    
    # Create student profile
    student_data = data.get('student', {})
    student = Student(
        id=str(uuid.uuid4()),
        user_id=user.id,
        grade_level=student_data.get('grade_level'),
        educational_board=student_data.get('educational_board'),
        academic_year=student_data.get('academic_year'),
        school_name=student_data.get('school_name'),
        date_of_birth=student_data.get('date_of_birth'),
        address=student_data.get('address'),
        state=student_data.get('state'),
        pin_code=student_data.get('pin_code'),
        father_name=student_data.get('father_name'),
        father_phone=student_data.get('father_phone'),
        father_email=student_data.get('father_email'),
        father_profession=student_data.get('father_profession'),
        father_workplace=student_data.get('father_workplace'),
        mother_name=student_data.get('mother_name'),
        mother_phone=student_data.get('mother_phone'),
        mother_email=student_data.get('mother_email'),
        mother_profession=student_data.get('mother_profession'),
        mother_workplace=student_data.get('mother_workplace'),
        siblings_count=student_data.get('siblings_count', 0),
        hobbies=student_data.get('hobbies', []),
        learning_styles=student_data.get('learning_styles', []),
        learning_patterns=student_data.get('learning_patterns', []),
        favorite_subjects=student_data.get('favorite_subjects', []),
        difficult_subjects=student_data.get('difficult_subjects', []),
        parent_feedback=student_data.get('parent_feedback'),
        availability_schedule=student_data.get('availability_schedule', {}),
        relationship_manager=student_data.get('relationship_manager'),
        classes_enrolled=student_data.get('classes_enrolled', []),
        class_hours_per_week=student_data.get('class_hours_per_week'),
        number_of_classes_per_week=student_data.get('number_of_classes_per_week'),
        course_duration_months=student_data.get('course_duration_months'),
        total_fee=student_data.get('total_fee'),
        amount_paid=student_data.get('amount_paid', 0),
        payment_schedule=student_data.get('payment_schedule')
    )
    
    # Calculate balance amount
    if student.total_fee and student.amount_paid:
        student.balance_amount = student.total_fee - student.amount_paid
    
    db.session.add(student)
    db.session.commit()
    
    return jsonify({
        'message': 'Student created successfully',
        'user': user.to_dict(),
        'student': student.to_dict(),
        'temporary_password': temp_password
    }), 201

@students_bp.route('/<student_id>', methods=['GET'])
@jwt_required()
def get_student(student_id):
    student = Student.query.get_or_404(student_id)
    student_data = student.to_dict()
    student_data['user'] = student.user.to_dict()
    return jsonify(student_data), 200

@students_bp.route('/<student_id>', methods=['PUT'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator'])
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    # Update student fields
    updatable_fields = [
        'grade_level', 'educational_board', 'academic_year', 'school_name',
        'address', 'state', 'pin_code', 'father_name', 'father_phone',
        'father_email', 'father_profession', 'father_workplace',
        'mother_name', 'mother_phone', 'mother_email', 'mother_profession',
        'mother_workplace', 'siblings_count', 'hobbies', 'learning_styles',
        'learning_patterns', 'favorite_subjects', 'difficult_subjects',
        'parent_feedback', 'availability_schedule', 'relationship_manager',
        'classes_enrolled', 'class_hours_per_week', 'number_of_classes_per_week',
        'course_duration_months'
    ]
    
    for field in updatable_fields:
        if field in data:
            setattr(student, field, data[field])
    
    db.session.commit()
    return jsonify(student.to_dict()), 200