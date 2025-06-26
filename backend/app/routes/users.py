# backend/app/routes/users.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.user import User
from app.models.department import Department
from app.models import db
from app.utils.decorators import require_role
from app.utils.validators import validate_user_data
import uuid

users_bp = Blueprint('users', __name__)

@users_bp.route('', methods=['GET'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    department_id = request.args.get('department_id')
    role = request.args.get('role')
    
    query = User.query
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    if role:
        query = query.filter_by(role=role)
    
    users = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'users': [user.to_dict() for user in users.items],
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    }), 200

@users_bp.route('', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def create_user():
    data = request.get_json()
    
    if not validate_user_data(data):
        return jsonify({'error': 'Invalid input data'}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    user = User(
        id=str(uuid.uuid4()),
        username=data['username'],
        email=data['email'],
        full_name=data['full_name'],
        phone_number=data.get('phone_number'),
        role=data['role'],
        department_id=data.get('department_id')
    )
    
    # Generate temporary password
    temp_password = str(uuid.uuid4())[:8]
    user.set_password(temp_password)
    
    db.session.add(user)
    db.session.commit()
    
    # Send welcome email with credentials
    # send_welcome_email(user.email, user.username, temp_password)
    
    return jsonify({
        'message': 'User created successfully',
        'user': user.to_dict(),
        'temporary_password': temp_password
    }), 201

@users_bp.route('/<user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200

@users_bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    # Update allowed fields
    for field in ['full_name', 'email', 'phone_number', 'department_id']:
        if field in data:
            setattr(user, field, data[field])
    
    db.session.commit()
    return jsonify(user.to_dict()), 200

@users_bp.route('/<user_id>/activate', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def activate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    return jsonify({'message': 'User activated successfully'}), 200

@users_bp.route('/<user_id>/deactivate', methods=['POST'])
@jwt_required()
@require_role(['superadmin', 'admin'])
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify({'message': 'User deactivated successfully'}), 200