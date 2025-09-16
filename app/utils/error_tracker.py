import sys
import traceback
import psutil
import time
from datetime import datetime
from functools import wraps
from flask import request, session, current_app, g
from flask_login import current_user
from user_agents import parse
from app import db
from app.models.error_log import ErrorLog, UserActivityLog, SystemHealthLog


class ErrorTracker:
    """Advanced error tracking and monitoring system"""
    
    @staticmethod
    def capture_error(error_type, error_message, **kwargs):
        """Capture and log comprehensive error information"""
        try:
            # Get request context if available
            request_info = ErrorTracker._get_request_info()
            system_info = ErrorTracker._get_system_info()
            user_info = ErrorTracker._get_user_info()
            
            # Determine error severity
            severity = ErrorTracker._determine_severity(error_type, error_message)
            
            # Create error log with merged kwargs
            merged_kwargs = kwargs.copy()
            if 'error_category' not in merged_kwargs:
                merged_kwargs['error_category'] = ErrorTracker._categorize_error(error_type)
            if 'severity' not in merged_kwargs:
                merged_kwargs['severity'] = severity
            
            # Merge all data, ensuring no duplicate keys by prioritizing in order:
            # request_info < system_info < user_info < merged_kwargs
            all_params = {}
            all_params.update(request_info)
            all_params.update(system_info)
            all_params.update(user_info)
            all_params.update(merged_kwargs)
            
            error_log = ErrorLog(
                error_type=error_type,
                error_message=str(error_message),
                **all_params
            )
            
            # Set additional data
            try:
                if hasattr(request, 'form') and request.form:
                    error_log.set_form_data(dict(request.form))
                
                if hasattr(request, 'headers'):
                    error_log.set_request_headers(dict(request.headers))
            except RuntimeError:
                # Working outside of request context
                pass
            
            db.session.add(error_log)
            db.session.commit()
            
            # Send real-time alerts for critical errors
            if severity in ['high', 'critical']:
                ErrorTracker._send_alert(error_log)
            
            return error_log
            
        except Exception as e:
            # Fallback logging if our error tracker fails
            try:
                current_app.logger.error(f"Error in ErrorTracker: {str(e)}")
            except:
                print(f"Error in ErrorTracker: {str(e)}")  # Fallback to print
            return None
    
    @staticmethod
    def _get_request_info():
        """Extract comprehensive request information"""
        try:
            if not request:
                return {}
            
            return {
                'request_url': request.url,
                'request_method': request.method,
                'ip_address': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
                'user_agent': request.headers.get('User-Agent', ''),
                'previous_page': request.referrer or '',
            }
        except RuntimeError:
            # Working outside of request context
            return {}
    
    @staticmethod
    def _get_system_info():
        """Get current system performance metrics"""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            return {
                'server_load': cpu_percent,
                'memory_usage': memory.percent,
                'response_time': getattr(g, 'request_start_time', time.time()) - time.time() if hasattr(g, 'request_start_time') else 0
            }
        except:
            return {}
    @staticmethod
    def _get_user_info():
        """Extract user context information"""
        user_info = {}
        
        try:
            if current_user and current_user.is_authenticated:
                user_info.update({
                    'user_id': current_user.id,
                    'user_role': current_user.role,
                })
            
            if session:
                user_info['session_id'] = session.get('_id', '')
            
            # Parse user agent for device info
            if request and request.headers.get('User-Agent'):
                user_agent = parse(request.headers.get('User-Agent'))
                user_info.update({
                    'browser': f"{user_agent.browser.family} {user_agent.browser.version_string}",
                    'device_type': 'mobile' if user_agent.is_mobile else 'tablet' if user_agent.is_tablet else 'desktop',
                    'operating_system': f"{user_agent.os.family} {user_agent.os.version_string}"
                })
        except RuntimeError:
            # Working outside of request context
            pass
        
        return user_info
    
    @staticmethod
    def _categorize_error(error_type):
        """Categorize errors for better organization"""
        categories = {
            'login_error': 'authentication',
            'logout_error': 'authentication',
            'password_error': 'authentication',
            'permission_error': 'authorization',
            'database_error': 'database',
            'connection_error': 'database',
            'network_error': 'network',
            'api_error': 'external_service',
            'validation_error': 'input_validation',
            'file_error': 'file_system',
            'email_error': 'communication',
            'payment_error': 'payment',
            'session_error': 'session_management'
        }
        
        for key, category in categories.items():
            if key in error_type.lower():
                return category
        
        return 'general'
    
    @staticmethod
    def _determine_severity(error_type, error_message):
        """Automatically determine error severity"""
        error_lower = f"{error_type} {error_message}".lower()
        
        # Critical errors
        if any(word in error_lower for word in [
            'database connection failed', 'cannot connect to database',
            'payment failed', 'security breach', 'unauthorized access',
            'system crash', 'out of memory', 'disk full'
        ]):
            return 'critical'
        
        # High severity errors
        if any(word in error_lower for word in [
            'login failed', 'authentication error', 'permission denied',
            'timeout', 'service unavailable', 'api error'
        ]):
            return 'high'
        
        # Medium severity errors
        if any(word in error_lower for word in [
            'validation error', 'form error', 'upload failed',
            'email failed', 'session expired'
        ]):
            return 'medium'
        
        # Default to low severity
        return 'low'
    
    @staticmethod
    def _send_alert(error_log):
        """Send real-time alerts for critical errors"""
        try:
            # You can integrate with Slack, email, SMS, etc.
            alert_message = f"""
            🚨 CRITICAL ERROR DETECTED
            
            Error Type: {error_log.error_type}
            User: {error_log.user.full_name if error_log.user else 'Anonymous'}
            Message: {error_log.error_message}
            Time: {error_log.created_at}
            URL: {error_log.request_url}
            
            View Details: /admin/errors/{error_log.error_id}
            """
            
            # Send to admin notification system
            current_app.logger.critical(alert_message)
            
            # TODO: Integrate with your notification system
            # send_slack_alert(alert_message)
            # send_email_alert(alert_message)
            
        except Exception as e:
            current_app.logger.error(f"Failed to send alert: {str(e)}")


def track_errors(error_type=None, capture_args=True):
    """Decorator to automatically track errors in functions/routes"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                # Record start time for performance tracking
                g.request_start_time = time.time()
                
                # Execute the function
                result = f(*args, **kwargs)
                
                # Log successful activity
                if current_user and current_user.is_authenticated:
                    UserActivityLog.log_activity(
                        user_id=current_user.id,
                        activity_type='action',
                        page_url=request.url if request else '',
                        action_taken=f.__name__,
                        success=True,
                        response_time=time.time() - g.request_start_time,
                        ip_address=request.environ.get('HTTP_X_REAL_IP', request.remote_addr) if request else '',
                        user_agent=request.headers.get('User-Agent', '') if request else ''
                    )
                
                return result
                
            except Exception as e:
                # Capture error details
                error_message = str(e)
                stack_trace = traceback.format_exc()
                
                # Determine error type
                detected_error_type = error_type or f"{f.__name__}_error"
                
                # Log the error
                error_log = ErrorTracker.capture_error(
                    error_type=detected_error_type,
                    error_message=error_message,
                    stack_trace=stack_trace,
                    action_attempted=f.__name__
                )
                
                # Log failed activity
                if current_user and current_user.is_authenticated:
                    UserActivityLog.log_activity(
                        user_id=current_user.id,
                        activity_type='error',
                        page_url=request.url if request else '',
                        action_taken=f.__name__,
                        success=False,
                        response_time=time.time() - g.request_start_time,
                        ip_address=request.environ.get('HTTP_X_REAL_IP', request.remote_addr) if request else '',
                        user_agent=request.headers.get('User-Agent', '') if request else ''
                    )
                
                # Re-raise the exception (or handle it based on your needs)
                current_app.logger.error(f"Error in {f.__name__}: {error_message}")
                raise
                
        return wrapper
    return decorator


def track_login_attempts(f):
    """Specialized decorator for tracking login attempts"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            
            # If login was successful (you'll need to adapt this logic)
            if request.method == 'POST' and not any(word in str(result) for word in ['error', 'invalid', 'failed']):
                ErrorTracker.capture_error(
                    error_type='successful_login',
                    error_message='User logged in successfully',
                    severity='low'
                )
            
            return result
            
        except Exception as e:
            # Capture failed login attempt
            username = request.form.get('username', '') if request.form else ''
            
            ErrorTracker.capture_error(
                error_type='login_error',
                error_message=f"Login failed for user: {username} - {str(e)}",
                action_attempted='login',
                form_data={'username': username} if username else None
            )
            
            raise
            
    return wrapper


class SystemHealthMonitor:
    """Monitor overall system health"""
    
    @staticmethod
    def record_health_metrics():
        """Record current system health metrics"""
        try:
            # System metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database health check
            db_start_time = time.time()
            try:
                db.session.execute('SELECT 1')
                db_response_time = time.time() - db_start_time
                db_status = 'healthy'
            except:
                db_response_time = None
                db_status = 'unhealthy'
            
            # Application metrics
            error_rate = SystemHealthMonitor._calculate_error_rate()
            login_success_rate = SystemHealthMonitor._calculate_login_success_rate()
            
            # Determine overall health
            overall_health = SystemHealthMonitor._determine_overall_health(
                cpu_usage, memory.percent, error_rate
            )
            
            # Log health metrics
            health_log = SystemHealthLog.log_health_metrics(
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                database_response_time=db_response_time,
                error_rate=error_rate,
                login_success_rate=login_success_rate,
                overall_health=overall_health
            )
            
            return health_log
            
        except Exception as e:
            current_app.logger.error(f"Failed to record health metrics: {str(e)}")
            return None
    
    @staticmethod
    def _calculate_error_rate():
        """Calculate current error rate"""
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import func
            
            # Get errors from last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            error_count = ErrorLog.query.filter(
                ErrorLog.created_at >= one_hour_ago,
                ErrorLog.severity.in_(['high', 'critical'])
            ).count()
            
            total_requests = UserActivityLog.query.filter(
                UserActivityLog.created_at >= one_hour_ago
            ).count()
            
            if total_requests > 0:
                return (error_count / total_requests) * 100
            
            return 0.0
            
        except:
            return 0.0
    
    @staticmethod
    def _calculate_login_success_rate():
        """Calculate login success rate"""
        try:
            from datetime import datetime, timedelta
            
            # Get login attempts from last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            total_logins = UserActivityLog.query.filter(
                UserActivityLog.created_at >= one_hour_ago,
                UserActivityLog.activity_type.in_(['login', 'error']),
                UserActivityLog.action_taken == 'login'
            ).count()
            
            successful_logins = UserActivityLog.query.filter(
                UserActivityLog.created_at >= one_hour_ago,
                UserActivityLog.activity_type == 'action',
                UserActivityLog.action_taken == 'login',
                UserActivityLog.success == True
            ).count()
            
            if total_logins > 0:
                return (successful_logins / total_logins) * 100
            
            return 100.0
            
        except:
            return 100.0
    
    @staticmethod
    def _determine_overall_health(cpu_usage, memory_usage, error_rate):
        """Determine overall system health status"""
        if cpu_usage > 90 or memory_usage > 90 or error_rate > 10:
            return 'critical'
        elif cpu_usage > 70 or memory_usage > 70 or error_rate > 5:
            return 'warning'
        else:
            return 'healthy'


def init_error_tracking(app):
    """Initialize error tracking for the Flask app"""
    
    @app.before_request
    def before_request():
        """Set up request tracking"""
        g.request_start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """Log request completion"""
        try:
            if current_user and current_user.is_authenticated:
                response_time = time.time() - g.request_start_time
                
                UserActivityLog.log_activity(
                    user_id=current_user.id,
                    activity_type='page_view',
                    page_url=request.url,
                    success=response.status_code < 400,
                    response_time=response_time,
                    ip_address=request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
                    user_agent=request.headers.get('User-Agent', '')
                )
        except:
            pass
        
        return response
    
    @app.errorhandler(404)
    def handle_404(e):
        ErrorTracker.capture_error(
            error_type='page_not_found',
            error_message=f"Page not found: {request.url}",
            error_code='404'
        )
        return "Page not found", 404
    
    @app.errorhandler(500)
    def handle_500(e):
        ErrorTracker.capture_error(
            error_type='internal_server_error',
            error_message=str(e),
            error_code='500'
        )
        return "Internal server error", 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        ErrorTracker.capture_error(
            error_type='unhandled_exception',
            error_message=str(e),
            stack_trace=traceback.format_exc()
        )
        return "An unexpected error occurred", 500