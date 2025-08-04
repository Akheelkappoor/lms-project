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
    
    # ============ ADVANCED PERMISSION SYSTEM ============
    
    def has_permission(self, permission):
        """Enhanced permission checking with department integration"""
        if self.role == 'superadmin':
            return True
        
        # For admin role - has all permissions  
        if self.role == 'admin':
            return True
        
        # For coordinator - check department permissions first
        if self.role == 'coordinator':
            if self.department:
                dept_permissions = self.department.get_permissions()
                return permission in dept_permissions
            return False
        
        # For tutor - limited permissions
        if self.role == 'tutor':
            tutor_permissions = [
                'class_management', 'attendance_management', 
                'profile_management', 'communication', 'schedule_management'
            ]
            return permission in tutor_permissions
        
        # For student - very limited permissions
        if self.role == 'student':
            student_permissions = ['profile_management', 'communication']
            return permission in student_permissions
        
        return False

    def can_access_department_data(self, department_id):
        """Check if user can access specific department data"""
        if self.role == 'superadmin':
            return True
        if self.role == 'admin':
            return True  # Admins can access all departments
        if self.role == 'coordinator':
            return self.department_id == department_id
        if self.role in ['tutor', 'student']:
            # Tutors and students can only access their own department
            return self.department_id == department_id
        return False

    def get_permission_level(self):
        """Get user's permission level"""
        if self.role == 'superadmin':
            return 'high'
        if self.role == 'admin':
            return 'high'
        if self.role == 'coordinator':
            return self.department.permission_level if self.department else 'medium'
        return 'low'

    def get_all_permissions(self):
        """Get list of all permissions this user has"""
        if self.role == 'superadmin':
            from app.utils.advanced_permissions import PermissionRegistry
            return list(PermissionRegistry.PERMISSION_STRUCTURE.keys())
        
        if self.role == 'admin':
            from app.utils.advanced_permissions import PermissionRegistry
            return list(PermissionRegistry.PERMISSION_STRUCTURE.keys())
        
        if self.role == 'coordinator' and self.department:
            return self.department.get_permissions()
        
        # Role-based permissions for other roles
        role_permissions = {
            'tutor': [
                'class_management', 'attendance_management', 'profile_management', 
                'communication', 'schedule_management'
            ],
            'student': ['profile_management', 'communication']
        }
        
        return role_permissions.get(self.role, [])

    def get_permission_summary(self):
        """Get detailed permission summary"""
        from app.utils.advanced_permissions import PermissionUtils
        return PermissionUtils.get_user_permission_summary(self)

    def get_menu_permissions(self):
        """Get permissions for menu display"""
        permissions = self.get_all_permissions()
        
        return {
            'can_manage_users': 'user_management' in permissions,
            'can_manage_students': 'student_management' in permissions,
            'can_manage_tutors': 'tutor_management' in permissions,
            'can_manage_classes': 'class_management' in permissions,
            'can_view_reports': 'report_generation' in permissions,
            'can_manage_notices': 'notice_management' in permissions,
            'can_manage_finance': 'finance_management' in permissions,
            'can_handle_escalations': 'escalation_management' in permissions,
            'can_manage_documents': 'system_documents' in permissions,
            'can_manage_schedules': 'schedule_management' in permissions,
            'can_manage_demos': 'demo_management' in permissions,
            'can_view_attendance': 'attendance_management' in permissions,
        }

    def can_manage_user(self, target_user):
        """Check if current user can manage target user"""
        if self.role == 'superadmin':
            return True
        
        if self.role == 'admin':
            # Admins can manage everyone except superadmins
            return target_user.role != 'superadmin'
        
        if self.role == 'coordinator':
            # Coordinators can manage users in their department (except admins/superadmins)
            return (
                target_user.department_id == self.department_id and
                target_user.role in ['tutor', 'student']
            )
        
        return False

    def can_assign_permission(self, permission, target_user):
        """Check if user can assign specific permission to target user"""
        if not self.has_permission(permission):
            return False
        
        if self.role == 'superadmin':
            return True
        
        if self.role == 'admin':
            return target_user.role != 'superadmin'
        
        if self.role == 'coordinator':
            if target_user.department_id != self.department_id:
                return False
            
            # Check if department can grant this permission
            return self.department.can_grant_permission(permission, target_user.role)
        
        return False

    def get_accessible_departments(self):
        """Get list of departments this user can access"""
        from app.models.department import Department
        
        if self.role == 'superadmin':
            return Department.query.filter_by(is_active=True).all()
        
        if self.role == 'admin':
            return Department.query.filter_by(is_active=True).all()
        
        if self.role == 'coordinator' and self.department:
            return [self.department]
        
        if self.role in ['tutor', 'student'] and self.department:
            return [self.department]
        
        return []

    def can_view_user(self, target_user):
        """Check if current user can view target user's profile"""
        if self.role in ['superadmin', 'admin']:
            return True
        
        if self.role == 'coordinator':
            return target_user.department_id == self.department_id
        
        if self.role == 'tutor':
            # Tutors can view students in their department
            return (
                target_user.department_id == self.department_id and
                target_user.role == 'student'
            )
        
        return self.id == target_user.id  # Users can view themselves

    def has_route_access(self, endpoint):
        """Check if user has access to specific route endpoint"""
        from app.utils.advanced_permissions import PermissionRegistry
        
        user_permissions = self.get_all_permissions()
        return PermissionRegistry.check_route_permission(endpoint, user_permissions)

    def validate_permission_request(self, requested_permissions):
        """Validate if user can request specific permissions"""
        from app.utils.advanced_permissions import PermissionUtils
        
        return PermissionUtils.validate_permission_assignment(self, requested_permissions)

    # ============ NOTICE MANAGEMENT METHODS ============
    
    def has_notice_management_permission(self):
        """Check if user can manage notices"""
        return self.has_permission('notice_management')

    def can_create_notices(self):
        """Check if user can create notices"""
        if self.role in ['superadmin', 'admin']:
            return True
        elif self.role == 'coordinator':
            # Coordinators can create notices if they have notice_management permission
            return self.has_permission('notice_management') and self.department_id is not None
        return False

    def can_view_notice_analytics(self):
        """Check if user can view notice analytics"""
        return self.has_permission('notice_management')

    # ============ LEGACY COMPATIBILITY METHODS ============
    
    def can_access_department(self, dept_id):
        """Legacy method - redirects to new method"""
        return self.can_access_department_data(dept_id)
    
    # ============ EXISTING METHODS (UNCHANGED) ============
    
    def get_role_display(self):
        """Get formatted role name"""
        role_map = {
            'superadmin': 'Super Admin',
            'admin': 'Admin',
            'coordinator': 'Coordinator',
            'tutor': 'Tutor',
            'student': 'Student'
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
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'permissions': self.get_all_permissions(),
            'permission_level': self.get_permission_level()
        }
    
    # ============ STATIC UTILITY METHODS ============
    
    @staticmethod
    def get_role_hierarchy():
        """Get role hierarchy for permission checking"""
        return {
            'superadmin': 5,
            'admin': 4, 
            'coordinator': 3,
            'tutor': 2,
            'student': 1
        }

    @staticmethod
    def can_role_manage_role(manager_role, target_role):
        """Check if manager role can manage target role"""
        hierarchy = User.get_role_hierarchy()
        return hierarchy.get(manager_role, 0) > hierarchy.get(target_role, 0)
    
    def __repr__(self):
        return f'<User {self.username}>'


@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))