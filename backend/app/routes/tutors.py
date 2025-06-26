from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.user import User
from app.models.tutor import Tutor
from app.models import db
from app.utils.decorators import require_role
from app.services.file_service import FileService
import uuid

tutors_bp = Blueprint('tutors', __name__)
file_service = FileService()

@tutors_bp.route('', methods=['GET'])
@jwt_required()
@require_role(['superadmin', 'admin', 'coordinator'])
def get_tutors():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    verification_status = request.args.get('verification_status')
    
    query = Tutor.query.join(User)
    
    if subject:
        query = query.filter(Tutor.subjects.contains([subject]))
    if grade:
        query = query.filter(Tutor.grades.contains([grade]))
    if verification_status:
        query = query.filter(Tutor.verification_status == verification_status)
    
    tutors = query.paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for tutor in tutors.items:
        tutor_data = tutor.to_dict()
        tutor_data['user'] = tutor.user.to_dict()
        result.append(tutor_data)
    
    return jsonify({
        'tutors': result,
        'total': tutors.total,
        'pages': tutors.pages,
        'current_page': page
    }), 200

@tutors_bp.route('', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def create_tutor():
    data = request.get_json()
    
    # First create user account
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
        role='tutor',
        department_id=user_data.get('department_id')
    )
    
    # Generate temporary password
    temp_password = str(uuid.uuid4())[:12]
    user.set_password(temp_password)
    
    db.session.add(user)
    db.session.flush()  # Get user ID
    
    # Create tutor profile
    tutor_data = data.get('tutor', {})
    tutor = Tutor(
        id=str(uuid.uuid4()),
        user_id=user.id,
        qualification=tutor_data.get('qualification'),
        experience_years=tutor_data.get('experience_years'),
        experience_description=tutor_data.get('experience_description'),
        subjects=tutor_data.get('subjects', []),
        grades=tutor_data.get('grades', []),
        boards=tutor_data.get('boards', []),
        availability_schedule=tutor_data.get('availability_schedule', {}),
        salary_type=tutor_data.get('salary_type'),
        fixed_monthly_amount=tutor_data.get('fixed_monthly_amount'),
        hourly_rate=tutor_data.get('hourly_rate'),
        bank_account_holder=tutor_data.get('bank_account_holder'),
        bank_name=tutor_data.get('bank_name'),
        bank_account_number=tutor_data.get('bank_account_number'),
        bank_ifsc_code=tutor_data.get('bank_ifsc_code')
    )
    
    db.session.add(tutor)
    db.session.commit()
    
    # Send welcome email
    # email_service.send_welcome_email(user.email, user.username, temp_password)
    
    return jsonify({
        'message': 'Tutor created successfully',
        'user': user.to_dict(),
        'tutor': tutor.to_dict(),
        'temporary_password': temp_password
    }), 201

@tutors_bp.route('/<tutor_id>', methods=['GET'])
@jwt_required()
def get_tutor(tutor_id):
    tutor = Tutor.query.get_or_404(tutor_id)
    tutor_data = tutor.to_dict()
    tutor_data['user'] = tutor.user.to_dict()
    return jsonify(tutor_data), 200

@tutors_bp.route('/<tutor_id>', methods=['PUT'])
@jwt_required()
@require_role(['superadmin', 'admin', 'tutor'])
def update_tutor(tutor_id):
    tutor = Tutor.query.get_or_404(tutor_id)
    
    # Check if user can edit this tutor
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    if claims['role'] == 'tutor' and tutor.user_id != current_user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    # Update tutor fields
    updatable_fields = [
        'qualification', 'experience_years', 'experience_description',
        'subjects', 'grades', 'boards', 'availability_schedule',
        'bank_account_holder', 'bank_name', 'bank_account_number', 'bank_ifsc_code'
    ]
    
    for field in updatable_fields:
        if field in data:
            setattr(tutor, field, data[field])
    
    # Only admin can update salary info
    if claims['role'] in ['superadmin', 'admin']:
        salary_fields = ['salary_type', 'fixed_monthly_amount', 'hourly_rate']
        for field in salary_fields:
            if field in data:
                setattr(tutor, field, data[field])
    
    db.session.commit()
    return jsonify(tutor.to_dict()), 200

@tutors_bp.route('/<tutor_id>/documents', methods=['POST'])
@jwt_required()
def upload_tutor_documents(tutor_id):
    tutor = Tutor.query.get_or_404(tutor_id)
    
    # Check authorization
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    if claims['role'] == 'tutor' and tutor.user_id != current_user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    document_type = request.form.get('document_type')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Upload to S3
    file_url = file_service.upload_file(file, 'tutor-documents', tutor.user_id)
    
    if not file_url:
        return jsonify({'error': 'File upload failed'}), 500
    
    # Update tutor documents
    if not tutor.documents:
        tutor.documents = {}
    
    tutor.documents[document_type] = file_url
    db.session.commit()
    
    return jsonify({
        'message': 'Document uploaded successfully',
        'file_url': file_url
    }), 200

@tutors_bp.route('/<tutor_id>/verify', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def verify_tutor(tutor_id):
    tutor = Tutor.query.get_or_404(tutor_id)
    data = request.get_json()
    
    status = data.get('status')  # verified, rejected
    if status not in ['verified', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400
    
    tutor.verification_status = status
    db.session.commit()
    
    return jsonify({
        'message': f'Tutor {status} successfully'
    }), 200
