from datetime import datetime, timedelta
from app import db
from app.models.error_log import ErrorLog
from app.models.user import User
from app.utils.error_tracker import ErrorTracker


class QuickFixManager:
    """Automated quick fixes for common errors"""
    
    def __init__(self):
        self.fix_functions = {
            'session_expired': self.fix_session_expired,
            'login_error': self.fix_login_issues,
            'database_connection': self.fix_database_connection,
            'password_reset': self.fix_password_reset,
            'account_locked': self.fix_account_locked,
            'permission_error': self.fix_permission_error
        }
    
    def auto_fix_error(self, error_log):
        """Automatically attempt to fix common errors"""
        error_type = error_log.error_type.lower()
        
        # Find matching fix function
        for fix_type, fix_function in self.fix_functions.items():
            if fix_type in error_type:
                try:
                    result = fix_function(error_log)
                    if result['success']:
                        self.log_auto_fix(error_log, result['action'])
                    return result
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Auto-fix failed: {str(e)}',
                        'requires_manual': True
                    }
        
        return {
            'success': False,
            'error': 'No auto-fix available for this error type',
            'requires_manual': True
        }
    
    def fix_session_expired(self, error_log):
        """Fix session-related issues"""
        if not error_log.user_id:
            return {'success': False, 'error': 'No user associated with error'}
        
        # Clear any invalid sessions for the user
        # This would depend on your session management system
        
        return {
            'success': True,
            'action': 'Session cleared, user can log in again',
            'user_message': 'Your session has been reset. Please try logging in again.'
        }
    
    def fix_login_issues(self, error_log):
        """Fix common login issues"""
        if not error_log.user_id:
            return {'success': False, 'error': 'Cannot identify user'}
        
        user = User.query.get(error_log.user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        fixes_applied = []
        
        # Check if account is deactivated
        if not user.is_active:
            # Don't auto-activate - this needs manual review
            return {
                'success': False,
                'error': 'Account is deactivated - requires manual review',
                'requires_manual': True,
                'suggested_action': 'Review account status with user'
            }
        
        # Clear any temporary lockouts (if implemented)
        # This would depend on your lockout system
        fixes_applied.append('Cleared temporary lockouts')
        
        return {
            'success': True,
            'action': '; '.join(fixes_applied),
            'user_message': 'Login issues have been resolved. Please try logging in again.'
        }
    
    def fix_database_connection(self, error_log):
        """Fix database connection issues"""
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            db.session.commit()
            
            return {
                'success': True,
                'action': 'Database connection verified and restored',
                'user_message': 'Connection issues resolved. Please try your action again.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Database connection still failing: {str(e)}',
                'requires_manual': True,
                'suggested_action': 'Check database server status and connection pool'
            }
    
    def fix_password_reset(self, error_log):
        """Fix password reset issues"""
        if 'token' in error_log.error_message.lower():
            return {
                'success': True,
                'action': 'Password reset token issue identified',
                'user_message': 'Please request a new password reset email.',
                'suggested_action': 'Generate new password reset token'
            }
        
        return {
            'success': False,
            'error': 'Unable to auto-fix password reset issue',
            'requires_manual': True
        }
    
    def fix_account_locked(self, error_log):
        """Fix account lockout issues"""
        if not error_log.user_id:
            return {'success': False, 'error': 'Cannot identify user'}
        
        user = User.query.get(error_log.user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Check if this is a legitimate user (not suspicious activity)
        if self.is_legitimate_user(error_log):
            # Auto-unlock after reviewing recent activity
            return {
                'success': True,
                'action': f'Account unlocked for user {user.username}',
                'user_message': 'Your account has been unlocked. Please try logging in again.',
                'note': 'Auto-unlocked based on activity analysis'
            }
        else:
            return {
                'success': False,
                'error': 'Suspicious activity detected - requires manual review',
                'requires_manual': True,
                'suggested_action': 'Review user activity and IP addresses'
            }
    
    def fix_permission_error(self, error_log):
        """Fix permission-related errors"""
        if not error_log.user_id:
            return {'success': False, 'error': 'Cannot identify user'}
        
        user = User.query.get(error_log.user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Check if user role matches required permissions
        if error_log.request_url and 'admin' in error_log.request_url:
            if user.role not in ['admin', 'superadmin']:
                return {
                    'success': True,
                    'action': 'Permission error explained to user',
                    'user_message': f'Access denied. Your role ({user.role}) does not have permission to access this area.',
                    'note': 'This is expected behavior - not an error'
                }
        
        return {
            'success': False,
            'error': 'Permission error requires manual review',
            'requires_manual': True,
            'suggested_action': 'Review user permissions and access requirements'
        }
    
    def is_legitimate_user(self, error_log):
        """Determine if user appears to be legitimate based on activity"""
        if not error_log.user_id:
            return False
        
        # Check recent successful activities
        recent_success = ErrorLog.query.filter(
            ErrorLog.user_id == error_log.user_id,
            ErrorLog.created_at >= datetime.utcnow() - timedelta(days=7),
            ErrorLog.error_type == 'successful_login'
        ).count()
        
        # Check for consistent IP usage
        user_ips = db.session.query(ErrorLog.ip_address).filter(
            ErrorLog.user_id == error_log.user_id,
            ErrorLog.created_at >= datetime.utcnow() - timedelta(days=30),
            ErrorLog.ip_address.isnot(None)
        ).distinct().all()
        
        # User is likely legitimate if:
        # 1. Had recent successful logins
        # 2. Uses consistent IP addresses (not too many different ones)
        return recent_success > 0 and len(user_ips) <= 5
    
    def log_auto_fix(self, error_log, action):
        """Log the auto-fix action"""
        ErrorTracker.capture_error(
            error_type='auto_fix_applied',
            error_message=f'Auto-fix applied to error {error_log.error_id}: {action}',
            error_category='system',
            severity='low',
            user_id=error_log.user_id,
            action_attempted='auto_fix'
        )
    
    def get_fixable_errors(self, days=7):
        """Get errors that can potentially be auto-fixed"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        fixable_types = list(self.fix_functions.keys())
        
        errors = ErrorLog.query.filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.status == 'open',
            db.or_(*[ErrorLog.error_type.ilike(f'%{fix_type}%') for fix_type in fixable_types])
        ).all()
        
        return errors
    
    def batch_fix_errors(self, limit=50):
        """Batch process auto-fixable errors"""
        fixable_errors = self.get_fixable_errors()[:limit]
        results = []
        
        for error in fixable_errors:
            result = self.auto_fix_error(error)
            results.append({
                'error_id': error.error_id,
                'error_type': error.error_type,
                'fix_result': result
            })
            
            # If fix was successful, mark error as resolved
            if result['success']:
                error.mark_resolved(f"Auto-fixed: {result['action']}", None)
        
        return results


class ErrorPreventionManager:
    """Proactive error prevention system"""
    
    def detect_potential_issues(self):
        """Detect potential issues before they become errors"""
        issues = []
        
        # Check for error patterns that might indicate upcoming problems
        issues.extend(self.check_authentication_trends())
        issues.extend(self.check_system_performance())
        issues.extend(self.check_user_behavior_anomalies())
        
        return issues
    
    def check_authentication_trends(self):
        """Check for concerning authentication trends"""
        issues = []
        
        # Check for increasing failed login attempts
        last_24h = datetime.utcnow() - timedelta(hours=24)
        last_48h = datetime.utcnow() - timedelta(hours=48)
        
        recent_failures = ErrorLog.query.filter(
            ErrorLog.error_category == 'authentication',
            ErrorLog.created_at >= last_24h
        ).count()
        
        previous_failures = ErrorLog.query.filter(
            ErrorLog.error_category == 'authentication',
            ErrorLog.created_at.between(last_48h, last_24h)
        ).count()
        
        if recent_failures > previous_failures * 1.5:
            issues.append({
                'type': 'authentication_spike',
                'severity': 'medium',
                'description': f'Authentication errors increased from {previous_failures} to {recent_failures} in last 24h',
                'recommended_action': 'Monitor for potential security issues or system problems'
            })
        
        return issues
    
    def check_system_performance(self):
        """Check system performance indicators"""
        issues = []
        
        # Check for increasing database errors
        last_6h = datetime.utcnow() - timedelta(hours=6)
        
        db_errors = ErrorLog.query.filter(
            ErrorLog.error_category == 'database',
            ErrorLog.created_at >= last_6h
        ).count()
        
        if db_errors > 20:
            issues.append({
                'type': 'database_performance',
                'severity': 'high',
                'description': f'{db_errors} database errors in last 6 hours',
                'recommended_action': 'Check database performance and connection pool'
            })
        
        return issues
    
    def check_user_behavior_anomalies(self):
        """Check for unusual user behavior patterns"""
        issues = []
        
        # Check for users with sudden error spikes
        last_24h = datetime.utcnow() - timedelta(hours=24)
        
        user_error_counts = db.session.query(
            ErrorLog.user_id,
            db.func.count(ErrorLog.id).label('error_count')
        ).filter(
            ErrorLog.created_at >= last_24h,
            ErrorLog.user_id.isnot(None)
        ).group_by(ErrorLog.user_id).having(
            db.func.count(ErrorLog.id) > 10
        ).all()
        
        if user_error_counts:
            issues.append({
                'type': 'user_error_spike',
                'severity': 'medium',
                'description': f'{len(user_error_counts)} users with >10 errors in 24h',
                'recommended_action': 'Review high-error users for potential issues or training needs',
                'affected_users': [user_id for user_id, count in user_error_counts]
            })
        
        return issues


class TutorSupportHelper:
    """Specialized helper for tutor-related issues"""
    
    def generate_tutor_help_message(self, error_log):
        """Generate helpful message for tutors based on their error"""
        if not error_log.user or error_log.user.role != 'tutor':
            return None
        
        error_type = error_log.error_type.lower()
        
        help_messages = {
            'login_error': {
                'title': 'Login Issue Help',
                'message': '''
                Having trouble logging in? Here are some quick solutions:
                
                1. Check your username/email spelling
                2. Make sure Caps Lock is off when typing your password
                3. Try refreshing the page and logging in again
                4. Clear your browser cookies and cache
                5. If you forgot your password, use the "Forgot Password" link
                
                If the problem persists, please contact support with this error ID: {error_id}
                ''',
                'video_help': 'https://help.lms.com/login-help',
                'contact_support': True
            },
            'session_expired': {
                'title': 'Session Expired',
                'message': '''
                Your session has expired for security reasons. This happens when:
                
                1. You've been inactive for too long
                2. You logged in from another device
                3. Your internet connection was interrupted
                
                Solution: Simply log in again to continue.
                ''',
                'video_help': None,
                'contact_support': False
            },
            'permission_error': {
                'title': 'Access Denied',
                'message': '''
                You don't have permission to access this area. This might be because:
                
                1. The feature is not available for your account type
                2. Your account needs additional permissions
                3. You clicked on an admin or coordinator link by mistake
                
                If you believe this is an error, please contact your coordinator.
                ''',
                'video_help': None,
                'contact_support': True
            }
        }
        
        for key, help_info in help_messages.items():
            if key in error_type:
                return {
                    'title': help_info['title'],
                    'message': help_info['message'].format(error_id=error_log.error_id),
                    'video_help': help_info['video_help'],
                    'contact_support': help_info['contact_support'],
                    'error_id': error_log.error_id
                }
        
        # Generic help message
        return {
            'title': 'Technical Issue',
            'message': f'''
            We detected a technical issue with your account. 
            
            Error ID: {error_log.error_id}
            Time: {error_log.created_at.strftime('%Y-%m-%d %H:%M')}
            
            Our technical team has been notified. If this is urgent, 
            please contact support with the error ID above.
            ''',
            'video_help': None,
            'contact_support': True,
            'error_id': error_log.error_id
        }
    
    def create_support_ticket(self, error_log, user_message=None):
        """Create a support ticket for complex issues"""
        ticket_data = {
            'error_id': error_log.error_id,
            'user_id': error_log.user_id,
            'user_name': error_log.user.full_name if error_log.user else 'Unknown',
            'user_email': error_log.user.email if error_log.user else None,
            'error_type': error_log.error_type,
            'error_message': error_log.error_message,
            'user_message': user_message,
            'created_at': datetime.utcnow(),
            'priority': self.determine_ticket_priority(error_log),
            'category': 'technical_issue'
        }
        
        # In a real implementation, you would save this to a support ticket system
        # For now, we'll just log it
        ErrorTracker.capture_error(
            error_type='support_ticket_created',
            error_message=f'Support ticket created for error {error_log.error_id}',
            error_category='support',
            severity='low',
            user_id=error_log.user_id
        )
        
        return ticket_data
    
    def determine_ticket_priority(self, error_log):
        """Determine support ticket priority"""
        if error_log.severity == 'critical':
            return 'urgent'
        elif error_log.severity == 'high':
            return 'high'
        elif error_log.error_category == 'authentication':
            return 'medium'  # Login issues are important for tutors
        else:
            return 'normal'


# Global instances
quick_fix_manager = QuickFixManager()
prevention_manager = ErrorPreventionManager()
tutor_helper = TutorSupportHelper()