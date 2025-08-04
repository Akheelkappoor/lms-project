from datetime import datetime
from app import db
import json

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)  # K12, TT, UPSKILL
    description = db.Column(db.Text)
    
    # Advanced Permissions stored as JSON
    permissions = db.Column(db.Text)  # JSON string of permissions
    permission_level = db.Column(db.String(20), default='medium')  # high, medium, low
    
    # Status and tracking
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Advanced Settings
    settings = db.Column(db.Text)  # JSON string for department-specific settings
    
    # Permission restrictions (what this department CANNOT do)
    restricted_permissions = db.Column(db.Text)  # JSON string
    
    def __init__(self, **kwargs):
        super(Department, self).__init__(**kwargs)
        if not self.permissions:
            self.set_default_permissions()
    
    def set_default_permissions(self):
        """Set default permissions based on department type"""
        # Different defaults based on department code
        if self.code == 'K12':
            default_permissions = [
                'student_management', 'tutor_management', 'class_management',
                'attendance_management', 'notice_management', 'demo_management',
                'schedule_management', 'communication', 'profile_management'
            ]
        elif self.code == 'TT':  # Tech Training
            default_permissions = [
                'student_management', 'tutor_management', 'class_management',
                'attendance_management', 'report_generation', 'system_documents',
                'schedule_management', 'communication', 'profile_management'
            ]
        elif self.code == 'UPSKILL':
            default_permissions = [
                'student_management', 'class_management', 'attendance_management',
                'notice_management', 'report_generation', 'communication',
                'profile_management', 'demo_management'
            ]
        else:
            # Generic department
            default_permissions = [
                'student_management', 'class_management', 'attendance_management',
                'communication', 'profile_management'
            ]
        
        self.permissions = json.dumps(default_permissions)
    
    def get_permissions(self):
        """Get permissions as list with validation"""
        if self.permissions:
            try:
                stored_permissions = json.loads(self.permissions)
                # Validate permissions against registry
                valid_permissions = []
                available_permissions = self.get_all_available_permissions().keys()
                
                for perm in stored_permissions:
                    if perm in available_permissions:
                        valid_permissions.append(perm)
                
                return valid_permissions
            except:
                return []
        return []
    
    def set_permissions(self, permissions_list):
        """Set permissions with validation"""
        # Validate permissions
        available_permissions = self.get_all_available_permissions().keys()
        valid_permissions = [
            p for p in permissions_list 
            if p in available_permissions
        ]
        
        # Check restrictions
        restricted = self.get_restricted_permissions()
        allowed_permissions = [p for p in valid_permissions if p not in restricted]
        
        self.permissions = json.dumps(allowed_permissions)
        return allowed_permissions
    
    def has_permission(self, permission):
        """Check if department has specific permission"""
        return permission in self.get_permissions()
    
    def get_restricted_permissions(self):
        """Get list of restricted permissions"""
        if self.restricted_permissions:
            try:
                return json.loads(self.restricted_permissions)
            except:
                return []
        return []
    
    def set_restricted_permissions(self, restrictions):
        """Set permissions that this department cannot have"""
        self.restricted_permissions = json.dumps(restrictions)
    
    def get_permission_details(self):
        """Get detailed information about department permissions"""
        try:
            from app.utils.advanced_permissions import PermissionRegistry
        except ImportError:
            # Fallback if advanced permissions not available yet
            return []
        
        permissions = self.get_permissions()
        details = []
        
        for perm in permissions:
            perm_info = PermissionRegistry.get_permission_info(perm)
            if perm_info:
                details.append({
                    'key': perm,
                    'name': perm_info.get('name'),
                    'description': perm_info.get('description'),
                    'category': perm_info.get('category'),
                    'level': perm_info.get('level'),
                    'routes_controlled': len(perm_info.get('routes', []))
                })
        
        return details
    
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
    
    def get_permission_level_weight(self):
        """Get numeric weight for permission level"""
        weights = {'low': 1, 'medium': 2, 'high': 3}
        return weights.get(self.permission_level, 2)
    
    def can_grant_permission(self, permission, target_role='coordinator'):
        """Check if department can grant specific permission to role"""
        if permission not in self.get_permissions():
            return False
        
        try:
            from app.utils.advanced_permissions import PermissionRegistry
            perm_info = PermissionRegistry.get_permission_info(permission)
            perm_level = perm_info.get('level', 'medium')
            
            # Check if department level allows granting this permission
            level_hierarchy = {'low': 1, 'medium': 2, 'high': 3}
            dept_weight = level_hierarchy.get(self.permission_level, 2)
            perm_weight = level_hierarchy.get(perm_level, 2)
            
            return dept_weight >= perm_weight
        except ImportError:
            # Fallback if advanced permissions not available
            return True
    
    def get_user_count(self):
        """Get number of users in department"""
        from app.models.user import User
        return User.query.filter_by(department_id=self.id, is_active=True).count()
    
    def get_coordinator_count(self):
        """Get number of coordinators in department"""
        from app.models.user import User
        return User.query.filter_by(
            department_id=self.id, 
            role='coordinator', 
            is_active=True
        ).count()
    
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
    
    def get_permission_categories(self):
        """Get permissions grouped by category"""
        try:
            from app.utils.advanced_permissions import PermissionRegistry
        except ImportError:
            return {}
        
        permissions = self.get_permissions()
        categories = {}
        
        for perm in permissions:
            perm_info = PermissionRegistry.get_permission_info(perm)
            category = perm_info.get('category', 'Other')
            
            if category not in categories:
                categories[category] = []
                
            categories[category].append({
                'key': perm,
                'name': perm_info.get('name'),
                'description': perm_info.get('description'),
                'level': perm_info.get('level')
            })
        
        return categories
    
    def update_permissions_bulk(self, permission_updates):
        """Bulk update permissions with validation and logging"""
        current_permissions = set(self.get_permissions())
        new_permissions = set(permission_updates)
        
        added = new_permissions - current_permissions
        removed = current_permissions - new_permissions
        
        # Validate new permissions
        available_permissions = self.get_all_available_permissions().keys()
        valid_new = [
            p for p in new_permissions 
            if p in available_permissions
        ]
        
        # Check restrictions
        restricted = set(self.get_restricted_permissions())
        final_permissions = [p for p in valid_new if p not in restricted]
        
        self.permissions = json.dumps(final_permissions)
        
        return {
            'added': list(added),
            'removed': list(removed),
            'final_count': len(final_permissions),
            'restricted_blocked': list(new_permissions & restricted)
        }
    
    @staticmethod
    def get_all_available_permissions():
        """Get all available permissions from registry"""
        try:
            from app.utils.advanced_permissions import PermissionRegistry
            return PermissionRegistry.get_all_permissions_list()
        except ImportError:
            # Fallback permissions if advanced system not available
            return {
                'user_management': 'User Management',
                'student_management': 'Student Management',
                'tutor_management': 'Tutor Management',
                'class_management': 'Class Management',
                'attendance_management': 'Attendance Management',
                'schedule_management': 'Schedule Management',
                'notice_management': 'Notice Management',
                'demo_management': 'Demo Management',
                'report_generation': 'Report Generation',
                'communication': 'Communication',
                'profile_management': 'Profile Management',
                'system_documents': 'System Documents',
                'finance_management': 'Finance Management',
                'escalation_management': 'Escalation Management'
            }
    
    @staticmethod
    def get_permissions_by_category():
        """Get all permissions grouped by category"""
        try:
            from app.utils.advanced_permissions import PermissionRegistry
            return PermissionRegistry.get_permissions_by_category()
        except ImportError:
            # Fallback categories if advanced system not available
            all_permissions = Department.get_all_available_permissions()
            return {
                'Administration': [
                    {'key': 'user_management', 'name': 'User Management', 'description': 'Manage user accounts', 'level': 'high', 'routes_count': 5, 'functions_count': 6},
                    {'key': 'system_documents', 'name': 'System Documents', 'description': 'Manage documents', 'level': 'low', 'routes_count': 3, 'functions_count': 4}
                ],
                'Academic': [
                    {'key': 'student_management', 'name': 'Student Management', 'description': 'Manage students', 'level': 'high', 'routes_count': 8, 'functions_count': 8},
                    {'key': 'tutor_management', 'name': 'Tutor Management', 'description': 'Manage tutors', 'level': 'high', 'routes_count': 7, 'functions_count': 8},
                    {'key': 'class_management', 'name': 'Class Management', 'description': 'Manage classes', 'level': 'medium', 'routes_count': 6, 'functions_count': 8},
                    {'key': 'attendance_management', 'name': 'Attendance Management', 'description': 'Track attendance', 'level': 'medium', 'routes_count': 5, 'functions_count': 8}
                ],
                'Communication': [
                    {'key': 'notice_management', 'name': 'Notice Management', 'description': 'Manage notices', 'level': 'medium', 'routes_count': 4, 'functions_count': 8},
                    {'key': 'communication', 'name': 'Communication', 'description': 'Send messages', 'level': 'low', 'routes_count': 4, 'functions_count': 8}
                ]
            }
    
    @staticmethod
    def get_department_recommended_permissions(department_code):
        """Get recommended permissions for department type"""
        try:
            from app.utils.advanced_permissions import PermissionRegistry
            return PermissionRegistry.get_department_recommended_permissions(department_code)
        except ImportError:
            # Fallback recommendations
            recommendations = {
                'K12': [
                    'student_management', 'tutor_management', 'class_management',
                    'attendance_management', 'notice_management', 'demo_management',
                    'schedule_management', 'communication', 'profile_management'
                ],
                'TT': [
                    'student_management', 'tutor_management', 'class_management',
                    'attendance_management', 'report_generation', 'system_documents',
                    'schedule_management', 'communication', 'profile_management'
                ],
                'UPSKILL': [
                    'student_management', 'class_management', 'attendance_management',
                    'notice_management', 'report_generation', 'communication',
                    'profile_management', 'demo_management'
                ]
            }
            
            return recommendations.get(department_code, [
                'student_management', 'class_management', 'attendance_management', 
                'communication', 'profile_management'
            ])
    
    @staticmethod
    def create_default_departments():
        """Create default departments if they don't exist"""
        departments_data = [
            {
                'name': 'K12 Education',
                'code': 'K12',
                'description': 'K-12 school curriculum and subjects',
                'permission_level': 'high'
            },
            {
                'name': 'Teacher Training',
                'code': 'TT',
                'description': 'Professional teacher training programs',
                'permission_level': 'medium'
            },
            {
                'name': 'Upskill Programs',
                'code': 'UPSKILL',
                'description': 'Professional development and skill enhancement',
                'permission_level': 'medium'
            }
        ]
        
        created_departments = []
        for dept_data in departments_data:
            existing = Department.query.filter_by(code=dept_data['code']).first()
            if not existing:
                dept = Department(**dept_data)
                dept.set_default_permissions()
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
            'permission_level': self.permission_level,
            'is_active': self.is_active,
            'permissions': self.get_permissions(),
            'permission_details': self.get_permission_details(),
            'permission_categories': self.get_permission_categories(),
            'user_count': self.get_user_count(),
            'coordinator_count': self.get_coordinator_count(),
            'tutor_count': self.get_tutor_count(),
            'student_count': self.get_student_count(),
            'settings': self.get_settings(),
            'restricted_permissions': self.get_restricted_permissions(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_permission_summary(self):
        """Get summary of department permissions"""
        permissions = self.get_permissions()
        categories = self.get_permission_categories()
        
        return {
            'total_permissions': len(permissions),
            'permission_level': self.permission_level,
            'categories': len(categories),
            'by_level': {
                'high': len([p for p in self.get_permission_details() if p.get('level') == 'high']),
                'medium': len([p for p in self.get_permission_details() if p.get('level') == 'medium']),
                'low': len([p for p in self.get_permission_details() if p.get('level') == 'low'])
            },
            'recommended_missing': [
                p for p in self.get_department_recommended_permissions(self.code)
                if p not in permissions
            ]
        }
    
    def __repr__(self):
        return f'<Department {self.code}: {self.name}>'