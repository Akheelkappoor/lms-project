# backend/app/utils/decorators.py
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt

def require_role(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get('role')
            
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def department_access_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        claims = get_jwt()
        user_role = claims.get('role')
        user_dept = claims.get('department_id')
        
        # Superadmin can access all departments
        if user_role == 'superadmin':
            return f(*args, **kwargs)
        
        # Other roles need department validation
        # Add department-specific logic here
        
        return f(*args, **kwargs)
    return decorated_function