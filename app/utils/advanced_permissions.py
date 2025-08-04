from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

class PermissionRegistry:
    """Registry that maps permissions to routes and controls access"""
    
    PERMISSION_STRUCTURE = {
        # ============ USER MANAGEMENT CATEGORY ============
        'user_management': {
            'name': 'User Management',
            'description': 'Create, edit, delete user accounts and manage roles',
            'category': 'Administration',
            'level': 'high',
            'routes': [
                'admin.users',                      # /admin/users - List all users
                'admin.create_user',                # /admin/create-user - Create new user
                'admin.edit_user',                  # /admin/edit-user/<id> - Edit user
                'admin.delete_user',                # /admin/delete-user/<id> - Delete user
                'admin.reset_user_password',        # /admin/reset-password/<id>
                'admin.toggle_user_status',         # /admin/toggle-status/<id>
                'admin.user_profile',               # /admin/user/<id>
                'admin.bulk_user_operations',       # /admin/users/bulk-actions
            ],
            'functions': [
                'Create user accounts', 'Edit user profiles', 'Delete users', 
                'Reset passwords', 'Change user roles', 'Manage user status'
            ]
        },
        
        # ============ STUDENT MANAGEMENT CATEGORY ============
        'student_management': {
            'name': 'Student Management', 
            'description': 'Manage student profiles, enrollment, fees, and academic records',
            'category': 'Academic',
            'level': 'high',
            'routes': [
                'admin.students',                   # /admin/students - List students
                'admin.create_student',             # /admin/create-student
                'admin.edit_student',               # /admin/edit-student/<id>
                'admin.view_student_profile',       # /admin/student/<id>
                'student.student_profile',          # /student/students/<id>
                'admin.student_fee_management',     # /admin/student/<id>/fees
                'admin.student_class_history',      # /admin/student/<id>/classes
                'admin.bulk_student_operations',    # /admin/students/bulk-actions
                'admin.student_documents',          # /admin/student/<id>/documents
                'admin.student_attendance_report',  # /admin/student/<id>/attendance
            ],
            'functions': [
                'Create student accounts', 'Edit student profiles', 'View student details',
                'Manage student fees', 'View academic records', 'Generate student reports',
                'Manage student enrollment', 'Handle student documents'
            ]
        },
        
        # ============ TUTOR MANAGEMENT CATEGORY ============ 
        'tutor_management': {
            'name': 'Tutor Management',
            'description': 'Manage tutor profiles, assignments, performance, and availability',
            'category': 'Academic',
            'level': 'high',
            'routes': [
                'admin.tutors',                     # /admin/tutors - List tutors
                'admin.create_tutor',               # /admin/create-tutor  
                'admin.edit_tutor',                 # /admin/edit-tutor/<id>
                'admin.view_tutor_profile',         # /admin/tutor/<id>
                'admin.tutor_assignments',          # /admin/tutor/<id>/assignments
                'admin.tutor_performance',          # /admin/tutor/<id>/performance
                'admin.tutor_availability',         # /admin/tutor/<id>/availability
                'admin.assign_tutor_to_student',    # /admin/assign-tutor
                'admin.tutor_class_history',        # /admin/tutor/<id>/classes
            ],
            'functions': [
                'Create tutor accounts', 'Edit tutor profiles', 'View tutor details',
                'Assign tutors to students', 'Manage tutor schedules', 'Track performance',
                'Set tutor availability', 'Manage tutor documents'
            ]
        },
        
        # ============ CLASS MANAGEMENT CATEGORY ============
        'class_management': {
            'name': 'Class Management',
            'description': 'Schedule, manage, cancel classes and handle class operations',
            'category': 'Academic',
            'level': 'medium',
            'routes': [
                'admin.classes',                    # /admin/classes - List classes
                'admin.create_class',               # /admin/create-class
                'admin.edit_class',                 # /admin/edit-class/<id>
                'admin.cancel_class',               # /admin/cancel-class/<id>
                'admin.class_details',              # /admin/class/<id>
                'tutor.my_classes',                 # /tutor/my-classes
                'tutor.create_class',               # /tutor/create-class
                'admin.bulk_class_operations',      # /admin/classes/bulk-actions
                'admin.class_schedule',             # /admin/schedule
            ],
            'functions': [
                'Create new classes', 'Edit class details', 'Cancel classes',
                'View class schedules', 'Manage class assignments', 'Bulk class operations',
                'Handle class conflicts', 'Generate class reports'
            ]
        },
        
        # ============ ATTENDANCE MANAGEMENT CATEGORY ============
        'attendance_management': {
            'name': 'Attendance Management',
            'description': 'Track, mark, and manage student attendance records',
            'category': 'Academic', 
            'level': 'medium',
            'routes': [
                'admin.attendance_reports',         # /admin/attendance
                'admin.mark_attendance',            # /admin/mark-attendance/<class_id>
                'tutor.mark_attendance',            # /tutor/mark-attendance/<class_id>
                'admin.attendance_analytics',       # /admin/attendance/analytics
                'admin.bulk_attendance_update',     # /admin/attendance/bulk-update
                'admin.attendance_alerts',          # /admin/attendance/alerts
                'tutor.attendance_dashboard',       # /tutor/attendance
            ],
            'functions': [
                'Mark student attendance', 'View attendance reports', 'Edit attendance records',
                'Generate attendance analytics', 'Set attendance alerts', 'Bulk attendance updates',
                'Track attendance patterns', 'Export attendance data'
            ]
        },
        
        # ============ SCHEDULE MANAGEMENT CATEGORY ============
        'schedule_management': {
            'name': 'Schedule Management',
            'description': 'Manage class schedules, timetables, and reschedule requests',
            'category': 'Academic',
            'level': 'medium',
            'routes': [
                'admin.schedule_dashboard',         # /admin/schedule
                'admin.create_schedule',            # /admin/create-schedule
                'admin.edit_schedule',              # /admin/edit-schedule/<id>
                'reschedule.list_requests',         # /reschedule/requests
                'reschedule.approve_request',       # /reschedule/approve/<id>
                'admin.schedule_conflicts',         # /admin/schedule/conflicts
                'tutor.request_reschedule',         # /tutor/request-reschedule
            ],
            'functions': [
                'Create class schedules', 'Edit timetables', 'Handle reschedule requests',
                'Resolve schedule conflicts', 'Manage tutor availability', 'Generate schedule reports',
                'Approve/reject reschedules', 'Set schedule policies'
            ]
        },
        
        # ============ NOTICE MANAGEMENT CATEGORY ============
        'notice_management': {
            'name': 'Notice Management',
            'description': 'Create, publish, and manage system notices and announcements',
            'category': 'Communication',
            'level': 'medium',
            'routes': [
                'notice.admin_notices',             # /admin/notices
                'notice.create_notice',             # /admin/create-notice
                'notice.edit_notice',               # /admin/edit-notice/<id>
                'notice.publish_notice',            # /admin/publish-notice/<id>
                'notice.delete_notice',             # /admin/delete-notice/<id>
                'notice.notice_analytics',          # /admin/notices/analytics
                'notice.bulk_notice_operations',    # /admin/notices/bulk-actions
            ],
            'functions': [
                'Create system notices', 'Edit notice content', 'Publish announcements',
                'Delete outdated notices', 'Manage notice recipients', 'Schedule notice delivery',
                'Track notice engagement', 'Bulk notice operations'
            ]
        },
        
        # ============ ESCALATION MANAGEMENT CATEGORY ============
        'escalation_management': {
            'name': 'Escalation Management',
            'description': 'Handle, assign, and resolve user escalations and support tickets',
            'category': 'Support',
            'level': 'high',
            'routes': [
                'escalation.list_escalations',      # /escalations/
                'escalation.view_escalation',       # /escalations/<id>
                'escalation.assign_escalation',     # /escalations/<id>/assign
                'escalation.resolve_escalation',    # /escalations/<id>/resolve
                'escalation.escalation_reports',    # /escalations/reports
                'escalation.create_escalation',     # /escalations/create
                'escalation.escalation_analytics',  # /escalations/analytics
            ],
            'functions': [
                'View all escalations', 'Assign escalations to staff', 'Resolve tickets',
                'Track escalation status', 'Generate escalation reports', 'Set escalation priorities',
                'Manage escalation categories', 'Handle escalation follow-ups'
            ]
        },
        
        # ============ FINANCE MANAGEMENT CATEGORY ============
        'finance_management': {
            'name': 'Finance Management',
            'description': 'Manage fees, payments, financial records, and billing',
            'category': 'Financial',
            'level': 'high',
            'routes': [
                'finance.fee_dashboard',            # /finance/dashboard
                'finance.payment_history',          # /finance/payments
                'finance.fee_collection',           # /finance/collect-fees
                'finance.financial_reports',        # /finance/reports
                'finance.payment_reminders',        # /finance/reminders
                'finance.fee_structure',            # /finance/fee-structure
                'finance.payment_methods',          # /finance/payment-methods
            ],
            'functions': [
                'Collect student fees', 'Process payments', 'Generate invoices',
                'Track payment history', 'Send payment reminders', 'Manage fee structures',
                'Handle refunds', 'Generate financial reports'
            ]
        },
        
        # ============ REPORT GENERATION CATEGORY ============
        'report_generation': {
            'name': 'Report Generation',
            'description': 'Generate, view, and export system reports and analytics',
            'category': 'Analytics',
            'level': 'medium',
            'routes': [
                'admin.reports_dashboard',          # /admin/reports
                'admin.student_reports',            # /admin/reports/students
                'admin.tutor_reports',              # /admin/reports/tutors
                'admin.class_reports',              # /admin/reports/classes
                'admin.financial_reports',          # /admin/reports/finance
                'admin.custom_reports',             # /admin/reports/custom
                'admin.export_reports',             # /admin/reports/export
            ],
            'functions': [
                'Generate student reports', 'Create tutor performance reports', 'View class analytics',
                'Export data to Excel/PDF', 'Create custom reports', 'Schedule automated reports',
                'View system statistics', 'Generate department summaries'
            ]
        },
        
        # ============ SYSTEM DOCUMENTS CATEGORY ============
        'system_documents': {
            'name': 'System Documents',
            'description': 'Manage official documents, certificates, and file uploads',
            'category': 'Administration',
            'level': 'low',
            'routes': [
                'admin.document_management',        # /admin/documents
                'admin.upload_document',            # /admin/upload-document  
                'admin.document_templates',         # /admin/document-templates
                'profile.download_document',        # /profile/documents/<id>
                'admin.certificate_generation',     # /admin/certificates
                'admin.document_approval',          # /admin/documents/approve
            ],
            'functions': [
                'Upload system documents', 'Manage document templates', 'Generate certificates',
                'Approve document submissions', 'Organize file library', 'Set document permissions',
                'Handle document requests', 'Maintain document versions'
            ]
        },
        
        # ============ DEMO MANAGEMENT CATEGORY ============
        'demo_management': {
            'name': 'Demo Management', 
            'description': 'Manage demo classes, trial students, and conversion tracking',
            'category': 'Sales',
            'level': 'medium',
            'routes': [
                'demo.list_demos',                  # /demo/list
                'demo.create_demo',                 # /demo/create
                'demo.demo_feedback',               # /demo/<id>/feedback
                'demo.convert_demo_student',        # /demo/<id>/convert
                'demo.demo_analytics',              # /demo/analytics
                'demo.demo_schedule',               # /demo/schedule
                'demo.demo_reports',                # /demo/reports
            ],
            'functions': [
                'Schedule demo classes', 'Manage trial students', 'Collect demo feedback',
                'Convert demos to enrollments', 'Track conversion rates', 'Assign demo tutors',
                'Generate demo reports', 'Follow up with prospects'
            ]
        },
        
        # ============ COMMUNICATION CATEGORY ============
        'communication': {
            'name': 'Communication',
            'description': 'Send messages, emails, and manage communication channels',
            'category': 'Communication',
            'level': 'low',
            'routes': [
                'admin.send_message',               # /admin/send-message
                'admin.email_templates',            # /admin/email-templates
                'admin.sms_management',             # /admin/sms
                'admin.notification_center',        # /admin/notifications
                'admin.communication_logs',         # /admin/communication/logs
                'admin.broadcast_message',          # /admin/broadcast
            ],
            'functions': [
                'Send individual messages', 'Broadcast announcements', 'Manage email templates',
                'Send SMS notifications', 'Track communication history', 'Set up automated messages',
                'Manage communication preferences', 'Handle message responses'
            ]
        },
        
        # ============ PROFILE MANAGEMENT CATEGORY ============
        'profile_management': {
            'name': 'Profile Management',
            'description': 'Manage user profiles, personal information, and account settings',
            'category': 'Personal',
            'level': 'low',
            'routes': [
                'profile.edit_profile',             # /profile/edit
                'profile.change_password',          # /profile/change-password
                'profile.upload_photo',             # /profile/upload-photo
                'profile.manage_documents',         # /profile/documents
                'profile.notification_settings',    # /profile/notifications
                'profile.account_settings',         # /profile/settings
            ],
            'functions': [
                'Edit personal information', 'Change passwords', 'Upload profile photos',
                'Manage personal documents', 'Set notification preferences', 'Update contact details',
                'Configure account settings', 'Manage privacy settings'
            ]
        }
    }
    
    @classmethod
    def get_permission_info(cls, permission_key):
        """Get detailed information about a permission"""
        return cls.PERMISSION_STRUCTURE.get(permission_key, {})
    
    @classmethod
    def get_controlled_routes(cls, permission_key):
        """Get all routes controlled by a permission"""
        perm_info = cls.get_permission_info(permission_key)
        return perm_info.get('routes', [])
    
    @classmethod
    def get_controlled_functions(cls, permission_key):
        """Get all functions controlled by a permission"""
        perm_info = cls.get_permission_info(permission_key)
        return perm_info.get('functions', [])
    
    @classmethod
    def get_permissions_by_category(cls):
        """Group permissions by category"""
        categories = {}
        for perm_key, perm_info in cls.PERMISSION_STRUCTURE.items():
            category = perm_info.get('category', 'Other')
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'key': perm_key,
                'name': perm_info.get('name'),
                'description': perm_info.get('description'),
                'level': perm_info.get('level'),
                'routes_count': len(perm_info.get('routes', [])),
                'functions_count': len(perm_info.get('functions', []))
            })
        return categories
    
    @classmethod
    def get_all_permissions_list(cls):
        """Get simple list of all permissions for forms"""
        return {
            perm_key: perm_info.get('name', perm_key.replace('_', ' ').title())
            for perm_key, perm_info in cls.PERMISSION_STRUCTURE.items()
        }
    
    @classmethod
    def check_route_permission(cls, endpoint, user_permissions):
        """Check if user has permission for specific route"""
        for perm_key, perm_info in cls.PERMISSION_STRUCTURE.items():
            if endpoint in perm_info.get('routes', []):
                return perm_key in user_permissions
        return True  # Allow access if route not restricted
    
    @classmethod
    def get_permission_by_level(cls, level):
        """Get all permissions of specific level"""
        return {
            perm_key: perm_info for perm_key, perm_info in cls.PERMISSION_STRUCTURE.items()
            if perm_info.get('level') == level
        }
    
    @classmethod
    def get_department_recommended_permissions(cls, department_code):
        """Get recommended permissions for department type"""
        recommendations = {
            'K12': [
                'student_management', 'tutor_management', 'class_management',
                'attendance_management', 'notice_management', 'demo_management',
                'schedule_management', 'communication', 'profile_management'
            ],
            'TT': [  # Tech Training
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


# ============ ADVANCED DECORATORS ============

def require_permission(permission_key):
    """Decorator to check specific permission with detailed logging"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            if not current_user.has_permission(permission_key):
                perm_info = PermissionRegistry.get_permission_info(permission_key)
                perm_name = perm_info.get('name', permission_key)
                
                flash(f'Access denied. You need "{perm_name}" permission to access this page.', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_any_permission(*permission_keys):
    """Decorator to check if user has ANY of the specified permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            has_permission = any(
                current_user.has_permission(perm) for perm in permission_keys
            )
            
            if not has_permission:
                perm_names = [
                    PermissionRegistry.get_permission_info(perm).get('name', perm) 
                    for perm in permission_keys
                ]
                flash(f'Access denied. You need one of these permissions: {", ".join(perm_names)}', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_all_permissions(*permission_keys):
    """Decorator to check if user has ALL of the specified permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            missing_permissions = [
                perm for perm in permission_keys 
                if not current_user.has_permission(perm)
            ]
            
            if missing_permissions:
                missing_names = [
                    PermissionRegistry.get_permission_info(perm).get('name', perm) 
                    for perm in missing_permissions
                ]
                flash(f'Access denied. Missing permissions: {", ".join(missing_names)}', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(*roles):
    """Decorator to check specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
                
            if current_user.role not in roles:
                flash('Access denied. Insufficient role permissions.', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_department_access(dept_id_param='department_id'):
    """Decorator to check department access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Get department ID from kwargs or request args
            dept_id = kwargs.get(dept_id_param) or request.args.get(dept_id_param)
            
            if dept_id and not current_user.can_access_department_data(int(dept_id)):
                flash('Access denied. You cannot access this department data.', 'error')  
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_level_required(min_level):
    """Decorator to check permission level (high, medium, low)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
                
            user_level = current_user.get_permission_level()
            level_hierarchy = {'low': 1, 'medium': 2, 'high': 3}
            
            if level_hierarchy.get(user_level, 0) < level_hierarchy.get(min_level, 0):
                flash(f'Access denied. Requires {min_level} level permissions.', 'error')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============ PERMISSION UTILITIES ============

class PermissionUtils:
    """Utility functions for permission management"""
    
    @staticmethod
    def get_user_permission_summary(user):
        """Get summary of user's permissions with details"""
        if user.role == 'superadmin':
            return {
                'level': 'superadmin',
                'permissions': list(PermissionRegistry.PERMISSION_STRUCTURE.keys()),
                'description': 'Full system access - All permissions granted',
                'department': None,
                'restrictions': []
            }
        
        user_permissions = []
        if user.department:
            user_permissions = user.department.get_permissions()
        
        # Add role-based permissions
        role_permissions = {
            'admin': list(PermissionRegistry.PERMISSION_STRUCTURE.keys()),
            'coordinator': user_permissions,  # Gets from department
            'tutor': ['class_management', 'attendance_management', 'profile_management'],
            'student': ['profile_management']
        }
        
        final_permissions = role_permissions.get(user.role, [])
        
        return {
            'level': user.role,
            'permissions': final_permissions,
            'department': user.department.name if user.department else None,
            'permission_details': [
                PermissionRegistry.get_permission_info(perm) for perm in final_permissions
            ],
            'total_permissions': len(final_permissions),
            'by_category': PermissionUtils.group_permissions_by_category(final_permissions)
        }
    
    @staticmethod
    def group_permissions_by_category(permissions):
        """Group given permissions by category"""
        categories = {}
        for perm in permissions:
            perm_info = PermissionRegistry.get_permission_info(perm)
            category = perm_info.get('category', 'Other')
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'key': perm,
                'name': perm_info.get('name'),
                'level': perm_info.get('level')
            })
        return categories
    
    @staticmethod
    def validate_permission_assignment(user, permissions):
        """Validate if permissions can be assigned to user"""
        if user.role == 'superadmin':
            return True, []
        
        # Define role limits
        role_limits = {
            'admin': list(PermissionRegistry.PERMISSION_STRUCTURE.keys()),
            'coordinator': [  # Coordinators get permissions from department
                'student_management', 'tutor_management', 'class_management',
                'attendance_management', 'notice_management', 'report_generation',
                'demo_management', 'escalation_management', 'schedule_management',
                'communication', 'profile_management', 'system_documents'
            ],
            'tutor': [
                'class_management', 'attendance_management', 'profile_management',
                'communication', 'schedule_management'
            ],
            'student': [
                'profile_management', 'communication'
            ]
        }
        
        allowed_permissions = role_limits.get(user.role, [])
        invalid_permissions = [p for p in permissions if p not in allowed_permissions]
        
        return len(invalid_permissions) == 0, invalid_permissions
    
    @staticmethod
    def get_permission_comparison(user1, user2):
        """Compare permissions between two users"""
        user1_perms = set(user1.get_all_permissions())
        user2_perms = set(user2.get_all_permissions())
        
        return {
            'user1_only': list(user1_perms - user2_perms),
            'user2_only': list(user2_perms - user1_perms),
            'common': list(user1_perms & user2_perms),
            'user1_total': len(user1_perms),
            'user2_total': len(user2_perms)
        }
    
    @staticmethod
    def get_missing_permissions_for_role(user, target_role):
        """Get permissions missing for user to have target role capabilities"""
        role_permissions = {
            'admin': list(PermissionRegistry.PERMISSION_STRUCTURE.keys()),
            'coordinator': [
                'student_management', 'tutor_management', 'class_management',
                'attendance_management', 'notice_management', 'report_generation'
            ],
            'tutor': ['class_management', 'attendance_management', 'profile_management']
        }
        
        target_permissions = set(role_permissions.get(target_role, []))
        current_permissions = set(user.get_all_permissions())
        
        return list(target_permissions - current_permissions)


# ============ TEMPLATE HELPERS ============

def get_permission_badge_class(level):
    """Get CSS class for permission level badge"""
    badge_classes = {
        'high': 'badge-danger',
        'medium': 'badge-warning', 
        'low': 'badge-success'
    }
    return badge_classes.get(level, 'badge-secondary')


def format_permission_name(permission_key):
    """Format permission key to readable name"""
    perm_info = PermissionRegistry.get_permission_info(permission_key)
    return perm_info.get('name', permission_key.replace('_', ' ').title())


def get_route_permission_info(endpoint):
    """Get permission info for a specific route"""
    for perm_key, perm_info in PermissionRegistry.PERMISSION_STRUCTURE.items():
        if endpoint in perm_info.get('routes', []):
            return {
                'permission': perm_key,
                'name': perm_info.get('name'),
                'level': perm_info.get('level'),
                'category': perm_info.get('category')
            }
    return None


# ============ DEBUGGING AND MONITORING ============

def log_permission_check(user, permission, granted):
    """Log permission checks for debugging"""
    import logging
    logger = logging.getLogger('permissions')
    
    logger.info(f"Permission check - User: {user.username}, "
                f"Permission: {permission}, Granted: {granted}, "
                f"Role: {user.role}, Department: {user.department.name if user.department else None}")


def get_system_permission_stats():
    """Get statistics about permission usage"""
    from app.models.user import User
    from app.models.department import Department
    
    stats = {
        'total_permissions': len(PermissionRegistry.PERMISSION_STRUCTURE),
        'by_level': {
            'high': len(PermissionRegistry.get_permission_by_level('high')),
            'medium': len(PermissionRegistry.get_permission_by_level('medium')),
            'low': len(PermissionRegistry.get_permission_by_level('low'))
        },
        'by_category': {},
        'department_stats': [],
        'user_role_stats': {}
    }
    
    # Category stats
    categories = PermissionRegistry.get_permissions_by_category()
    for category, perms in categories.items():
        stats['by_category'][category] = len(perms)
    
    # Department stats
    departments = Department.query.filter_by(is_active=True).all()
    for dept in departments:
        stats['department_stats'].append({
            'name': dept.name,
            'code': dept.code,
            'permission_count': len(dept.get_permissions()),
            'user_count': dept.get_user_count()
        })
    
    # User role stats
    from sqlalchemy import func
    role_counts = User.query.with_entities(
        User.role, func.count(User.id)
    ).group_by(User.role).all()
    
    for role, count in role_counts:
        stats['user_role_stats'][role] = count
    
    return stats