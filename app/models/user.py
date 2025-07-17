from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login
import json

import jwt
from time import time
from flask import current_app

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Personal Information
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    profile_picture = db.Column(db.String(1000))
    
    # Role and Department
    role = db.Column(db.String(20), nullable=False, default='tutor')  # superadmin, admin, coordinator, tutor
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    
    # Status and Tracking
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Additional Information
    joining_date = db.Column(db.Date)
    working_hours = db.Column(db.String(50))  # "9:00 AM - 6:00 PM"
    emergency_contact = db.Column(db.Text)  # JSON string
    
    # Relationships
    department = db.relationship('Department', foreign_keys=[department_id], backref='users', lazy=True)
    tutor_profile = db.relationship('Tutor', backref='user', uselist=False, lazy=True)

    @staticmethod
    def verify_reset_password_token(token):
        """Verify password reset token"""
        try:
            id = jwt.decode(
                 token, 
                 current_app.config['SECRET_KEY'], 
                 algorithms=['HS256']
            )['reset_password']
        except:
            return None
        return User.query.get(id)
    
    def get_reset_password_token(self, expires_in=600):
     """Generate password reset token (expires in 10 minutes)"""
     return jwt.encode(
         {'reset_password': self.id, 'exp': time() + expires_in},
         current_app.config['SECRET_KEY'],
         algorithm='HS256'
    )
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_emergency_contact(self):
        """Get emergency contact as dict"""
        if self.emergency_contact:
            try:
                return json.loads(self.emergency_contact)
            except:
                return {}
        return {}
    
    def set_emergency_contact(self, contact_dict):
        """Set emergency contact from dict"""
        self.emergency_contact = json.dumps(contact_dict)
    
    def has_permission(self, permission):
        """Check if user has specific permission"""
        if self.role == 'superadmin':
            return True
        if self.role == 'admin':
            return permission in ['user_management', 'tutor_management', 'student_management', 
                                'class_management', 'attendance', 'finance', 'reports']
        if self.role == 'coordinator':
            if self.department and self.department.permissions:
                dept_permissions = json.loads(self.department.permissions)
                return permission in dept_permissions
        return False
    
    def can_access_department(self, dept_id):
        """Check if user can access specific department"""
        if self.role == 'superadmin':
            return True
        if self.role in ['admin', 'coordinator']:
            return self.department_id == dept_id
        return False
    
    def get_role_display(self):
        """Get formatted role name"""
        role_map = {
            'superadmin': 'Super Admin',
            'admin': 'Admin',
            'coordinator': 'Coordinator',
            'tutor': 'Tutor'
        }
        return role_map.get(self.role, self.role.title())
    
    def get_dashboard_url(self):
        """Get appropriate dashboard URL based on role"""
        if self.role in ['superadmin', 'admin', 'coordinator']:
            return 'dashboard.admin_dashboard'
        elif self.role == 'tutor':
            return 'dashboard.tutor_dashboard'
        return 'dashboard.index'
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def create_default_admin():
        """Create default admin user if not exists"""
        from config import Config
        admin = User.query.filter_by(email=Config.DEFAULT_ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                username='admin',
                email=Config.DEFAULT_ADMIN_EMAIL,
                full_name='System Administrator',
                role='superadmin',
                is_active=True,
                is_verified=True,
                joining_date=datetime.utcnow().date()
            )
            admin.set_password(Config.DEFAULT_ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            return admin
        return admin
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'department': self.department.name if self.department else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Add this method to the User model in app/models/user.py

def has_notice_management_permission(self):
    """Check if user can manage notices"""
    return self.role in ['superadmin', 'admin', 'coordinator']

def can_create_notices(self):
    """Check if user can create notices"""
    if self.role in ['superadmin', 'admin']:
        return True
    elif self.role == 'coordinator':
        # Coordinators can create notices for their department
        return self.department_id is not None
    return False

def can_view_notice_analytics(self):
    """Check if user can view notice analytics"""
    return self.role in ['superadmin', 'admin', 'coordinator']

# Update the existing has_permission method to include notice permissions
def has_permission(self, permission):
    """Check if user has specific permission"""
    if self.role == 'superadmin':
        return True
    
    # Get department permissions
    if self.department:
        dept_permissions = self.department.get_permissions()
        if permission in dept_permissions:
            return True
    
    # Role-based permissions
    role_permissions = {
        'admin': [
            'user_management', 'tutor_management', 'student_management',
            'class_management', 'attendance_management', 'schedule_management',
            'demo_management', 'report_generation', 'communication',
            'profile_management', 'notice_management', 'system_documents'
        ],
        'coordinator': [
            'tutor_management', 'student_management', 'class_management',
            'attendance_management', 'schedule_management', 'demo_management',
            'report_generation', 'communication', 'profile_management',
            'notice_management'
        ],
        'tutor': [
            'class_management', 'attendance_management', 'schedule_management',
            'communication', 'profile_management'
        ]
    }
    
    return permission in role_permissions.get(self.role, [])



