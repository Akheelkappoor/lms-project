from datetime import datetime
from app import db
import json

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)  # K12, TT, UPSKILL
    description = db.Column(db.Text)
    
    # Permissions stored as JSON
    permissions = db.Column(db.Text)  # JSON string of permissions
    
    # Status and tracking
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Settings
    settings = db.Column(db.Text)  # JSON string for department-specific settings
    
    def __init__(self, **kwargs):
        super(Department, self).__init__(**kwargs)
        if not self.permissions:
            self.set_default_permissions()
    
    def set_default_permissions(self):
        """Set default permissions for department"""
        default_permissions = [
            'user_management',
            'tutor_management', 
            'student_management',
            'class_management',
            'attendance_management',
            'schedule_management',
            'demo_management',
            'report_generation',
            'communication',
            'profile_management'
        ]
        self.permissions = json.dumps(default_permissions)
    
    def get_permissions(self):
        """Get permissions as list"""
        if self.permissions:
            try:
                return json.loads(self.permissions)
            except:
                return []
        return []
    
    def set_permissions(self, permissions_list):
        """Set permissions from list"""
        self.permissions = json.dumps(permissions_list)
    
    def has_permission(self, permission):
        """Check if department has specific permission"""
        return permission in self.get_permissions()
    
    def get_settings(self):
        """Get settings as dict"""
        if self.settings:
            try:
                return json.loads(self.settings)
            except:
                return {}
        return {}
    
    def set_settings(self, settings_dict):
        """Set settings from dict"""
        self.settings = json.dumps(settings_dict)
    
    def get_user_count(self):
        """Get number of users in department"""
        from app.models.user import User
        return User.query.filter_by(department_id=self.id, is_active=True).count()
    
    def get_tutor_count(self):
        """Get number of tutors in department"""
        from app.models.user import User
        return User.query.filter_by(
            department_id=self.id, 
            role='tutor', 
            is_active=True
        ).count()
    
    def get_student_count(self):
        """Get number of students in department"""
        from app.models.student import Student
        return Student.query.filter_by(
            department_id=self.id, 
            is_active=True
        ).count()
    
    @staticmethod
    def create_default_departments():
        """Create default departments if they don't exist"""
        departments_data = [
            {
                'name': 'K12 Education',
                'code': 'K12',
                'description': 'K-12 school curriculum and subjects'
            },
            {
                'name': 'Teacher Training',
                'code': 'TT',
                'description': 'Professional teacher training programs'
            },
            {
                'name': 'Upskill Programs',
                'code': 'UPSKILL',
                'description': 'Professional development and skill enhancement'
            }
        ]
        
        created_departments = []
        for dept_data in departments_data:
            existing = Department.query.filter_by(code=dept_data['code']).first()
            if not existing:
                dept = Department(**dept_data)
                db.session.add(dept)
                created_departments.append(dept)
        
        if created_departments:
            db.session.commit()
        
        return created_departments
    
    def to_dict(self):
        """Convert department to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'permissions': self.get_permissions(),
            'is_active': self.is_active,
            'user_count': self.get_user_count(),
            'tutor_count': self.get_tutor_count(),
            'student_count': self.get_student_count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Department {self.name}>'