"""
Simple Error Tracker - Minimal version without external dependencies
This is a fallback version that works without pandas, numpy, etc.
"""

import sys
import traceback
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import request, session, current_app, g
from flask_login import current_user


class SimpleErrorTracker:
    """Simplified error tracking system"""
    
    @staticmethod
    def capture_error(error_type, error_message, **kwargs):
        """Capture and log basic error information"""
        try:
            from app import db
            from app.models.error_log import ErrorLog
            
            # Get basic request info
            request_info = SimpleErrorTracker._get_basic_request_info()
            user_info = SimpleErrorTracker._get_basic_user_info()
            
            # Create error log with minimal information
            error_log = ErrorLog(
                error_type=error_type,
                error_category=SimpleErrorTracker._categorize_error(error_type),
                error_message=str(error_message),
                severity=kwargs.get('severity', 'medium'),
                **request_info,
                **user_info,
                **kwargs
            )
            
            db.session.add(error_log)
            db.session.commit()
            
            return error_log
            
        except Exception as e:
            # Fallback logging
            print(f"Error in SimpleErrorTracker: {str(e)}")
            return None
    
    @staticmethod
    def _get_basic_request_info():
        """Get basic request information"""
        try:
            if request:
                return {
                    'request_url': request.url,
                    'request_method': request.method,
                    'ip_address': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
                    'user_agent': request.headers.get('User-Agent', ''),
                }
        except:
            pass
        return {}
    
    @staticmethod
    def _get_basic_user_info():
        """Get basic user information"""
        try:
            user_info = {}
            
            if current_user and current_user.is_authenticated:
                user_info.update({
                    'user_id': current_user.id,
                    'user_role': current_user.role,
                })
            
            if session:
                user_info['session_id'] = session.get('_id', '')
            
            return user_info
        except:
            return {}
    
    @staticmethod
    def _categorize_error(error_type):
        """Basic error categorization"""
        error_type_lower = error_type.lower()
        
        if 'login' in error_type_lower or 'auth' in error_type_lower:
            return 'authentication'
        elif 'database' in error_type_lower or 'db' in error_type_lower:
            return 'database'
        elif 'network' in error_type_lower:
            return 'network'
        elif 'permission' in error_type_lower:
            return 'authorization'
        else:
            return 'general'


def simple_track_errors(error_type=None):
    """Simple decorator to track errors"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # Log the error
                error_message = str(e)
                detected_error_type = error_type or f"{f.__name__}_error"
                
                SimpleErrorTracker.capture_error(
                    error_type=detected_error_type,
                    error_message=error_message,
                    action_attempted=f.__name__
                )
                
                # Re-raise the exception
                raise
        return wrapper
    return decorator


# Use the simple tracker if the full one isn't available
try:
    from app.utils.error_tracker import ErrorTracker, track_errors
except ImportError:
    # Fallback to simple tracker
    ErrorTracker = SimpleErrorTracker
    track_errors = simple_track_errors
    print("Using simplified error tracking due to import issues")