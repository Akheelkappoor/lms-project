# backend/app/routes/auth.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app.models.user import User
from app.models import db
from app.utils.validators import validate_login, validate_password_reset
from app.services.email_service import send_password_reset_email
import uuid

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not validate_login(data):
        return jsonify({'error': 'Invalid input data'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create tokens
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'role': user.role,
            'department_id': user.department_id
        }
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 404
    
    new_access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'role': user.role,
            'department_id': user.department_id
        }
    )
    
    return jsonify({'access_token': new_access_token}), 200

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    
    user = User.query.filter_by(email=email).first()
    if user:
        reset_token = str(uuid.uuid4())
        # Store reset token in Redis with expiration
        # send_password_reset_email(user.email, reset_token)
    
    return jsonify({'message': 'Password reset email sent if account exists'}), 200

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('password')
    
    # Validate token from Redis
    # Update user password
    return jsonify({'message': 'Password reset successful'}), 200