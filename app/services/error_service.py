"""
Error Service for centralized error handling and logging
Provides consistent error responses and logging across the application
"""
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from flask import request, jsonify, current_app
from functools import wraps


class ErrorCode:
    """Standard error codes"""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"


class ErrorService:
    """Centralized error handling service"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """
        Log error with context information
        
        Args:
            error: Exception object
            context: Additional context information
            
        Returns:
            Error ID for tracking
        """
        error_id = self._generate_error_id()
        
        error_info = {
            'error_id': error_id,
            'timestamp': datetime.utcnow().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context or {}
        }
        
        # Add request context if available
        if request:
            error_info['request'] = {
                'method': request.method,
                'url': request.url,
                'user_agent': request.user_agent.string,
                'remote_addr': request.remote_addr,
                'user_id': getattr(request, 'user_id', None)
            }
        
        self.logger.error(f"Error {error_id}: {error_info}")
        return error_id
    
    def create_error_response(self, 
                            error_code: str, 
                            message: str, 
                            details: Dict[str, Any] = None,
                            status_code: int = 400) -> tuple:
        """
        Create standardized error response
        
        Args:
            error_code: Standard error code
            message: Human-readable error message
            details: Additional error details
            status_code: HTTP status code
            
        Returns:
            Tuple of (response, status_code)
        """
        response_data = {
            'success': False,
            'error': {
                'code': error_code,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
        
        if details:
            response_data['error']['details'] = details
            
        return jsonify(response_data), status_code
    
    def handle_validation_error(self, errors: Dict[str, Any]) -> tuple:
        """Handle validation errors"""
        return self.create_error_response(
            ErrorCode.VALIDATION_ERROR,
            "Validation failed",
            {'validation_errors': errors},
            400
        )
    
    def handle_not_found_error(self, resource: str = "Resource") -> tuple:
        """Handle not found errors"""
        return self.create_error_response(
            ErrorCode.NOT_FOUND,
            f"{resource} not found",
            status_code=404
        )
    
    def handle_unauthorized_error(self, message: str = "Authentication required") -> tuple:
        """Handle unauthorized errors"""
        return self.create_error_response(
            ErrorCode.UNAUTHORIZED,
            message,
            status_code=401
        )
    
    def handle_forbidden_error(self, message: str = "Access forbidden") -> tuple:
        """Handle forbidden errors"""
        return self.create_error_response(
            ErrorCode.FORBIDDEN,
            message,
            status_code=403
        )
    
    def handle_database_error(self, error: Exception) -> tuple:
        """Handle database errors"""
        error_id = self.log_error(error, {'type': 'database_error'})
        
        if current_app.debug:
            message = str(error)
        else:
            message = "Database operation failed"
            
        return self.create_error_response(
            ErrorCode.DATABASE_ERROR,
            message,
            {'error_id': error_id},
            500
        )
    
    def handle_external_service_error(self, service: str, error: Exception) -> tuple:
        """Handle external service errors"""
        error_id = self.log_error(error, {'type': 'external_service_error', 'service': service})
        
        return self.create_error_response(
            ErrorCode.EXTERNAL_SERVICE_ERROR,
            f"External service ({service}) error",
            {'error_id': error_id, 'service': service},
            503
        )
    
    def handle_internal_error(self, error: Exception) -> tuple:
        """Handle internal server errors"""
        error_id = self.log_error(error, {'type': 'internal_error'})
        
        if current_app.debug:
            message = str(error)
            details = {'error_id': error_id, 'traceback': traceback.format_exc()}
        else:
            message = "Internal server error"
            details = {'error_id': error_id}
            
        return self.create_error_response(
            ErrorCode.INTERNAL_ERROR,
            message,
            details,
            500
        )
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID"""
        import uuid
        return str(uuid.uuid4())[:8].upper()


# Global error service instance
error_service = ErrorService()


def handle_errors(func):
    """
    Decorator for automatic error handling in routes
    
    Usage:
        @app.route('/api/endpoint')
        @handle_errors
        def endpoint():
            # Your code here
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return error_service.create_error_response(
                ErrorCode.INVALID_INPUT,
                str(e),
                status_code=400
            )
        except PermissionError as e:
            return error_service.handle_forbidden_error(str(e))
        except FileNotFoundError as e:
            return error_service.handle_not_found_error("File")
        except Exception as e:
            # Check if it's a database error
            if 'database' in str(e).lower() or 'sql' in str(e).lower():
                return error_service.handle_database_error(e)
            else:
                return error_service.handle_internal_error(e)
    
    return wrapper


def handle_database_errors(func):
    """
    Decorator specifically for database operations
    
    Usage:
        @handle_database_errors
        def database_operation():
            # Database code here
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            from app import db
            db.session.rollback()
            return error_service.handle_database_error(e)
    
    return wrapper


class APIError(Exception):
    """Custom exception for API errors"""
    
    def __init__(self, error_code: str, message: str, status_code: int = 400, details: Dict[str, Any] = None):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class ValidationError(APIError):
    """Custom exception for validation errors"""
    
    def __init__(self, errors: Dict[str, Any]):
        super().__init__(
            ErrorCode.VALIDATION_ERROR,
            "Validation failed",
            400,
            {'validation_errors': errors}
        )
        self.validation_errors = errors


class NotFoundError(APIError):
    """Custom exception for not found errors"""
    
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            ErrorCode.NOT_FOUND,
            f"{resource} not found",
            404
        )


class UnauthorizedError(APIError):
    """Custom exception for unauthorized errors"""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            ErrorCode.UNAUTHORIZED,
            message,
            401
        )


class ForbiddenError(APIError):
    """Custom exception for forbidden errors"""
    
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            ErrorCode.FORBIDDEN,
            message,
            403
        )


# Error handlers for Flask app
def register_error_handlers(app):
    """Register error handlers with Flask app"""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        return error_service.create_error_response(
            error.error_code,
            error.message,
            error.details,
            error.status_code
        )
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return error_service.handle_validation_error(error.validation_errors)
    
    @app.errorhandler(NotFoundError)
    def handle_not_found_error(error):
        return error_service.handle_not_found_error()
    
    @app.errorhandler(UnauthorizedError)
    def handle_unauthorized_error(error):
        return error_service.handle_unauthorized_error(error.message)
    
    @app.errorhandler(ForbiddenError)
    def handle_forbidden_error(error):
        return error_service.handle_forbidden_error(error.message)
    
    @app.errorhandler(500)
    def handle_internal_server_error(error):
        return error_service.handle_internal_error(error)


# Utility functions for common error patterns
def require_permission(permission: str):
    """
    Decorator to require specific permission
    
    Usage:
        @require_permission('user_management')
        def manage_users():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask_login import current_user
            
            if not current_user.is_authenticated:
                raise UnauthorizedError()
            
            if not current_user.has_permission(permission):
                raise ForbiddenError(f"Permission '{permission}' required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: str):
    """
    Decorator to require specific role
    
    Usage:
        @require_role('admin')
        def admin_only():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask_login import current_user
            
            if not current_user.is_authenticated:
                raise UnauthorizedError()
            
            if current_user.role != role:
                raise ForbiddenError(f"Role '{role}' required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator