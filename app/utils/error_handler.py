"""
Error handling utilities for consistent error responses and logging.
"""
import logging
import traceback
import json
from functools import wraps
from flask import request, jsonify, flash, redirect, url_for
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import BadRequest

# Configure logger
error_logger = logging.getLogger('lms.errors')

class ErrorHandler:
    """Utility class for handling errors consistently"""
    
    @staticmethod
    def log_error(error, context=None):
        """
        Log error with context information.
        
        Args:
            error: The exception that occurred
            context: Additional context information
        """
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'user': getattr(request, 'user', 'anonymous') if request else 'no_request',
            'endpoint': request.endpoint if request else 'no_endpoint',
            'method': request.method if request else 'no_method',
            'url': request.url if request else 'no_url',
            'context': context
        }
        
        error_logger.error(f"Error occurred: {error_info}", exc_info=True)
    
    @staticmethod
    def handle_database_error(error):
        """
        Handle database-specific errors.
        
        Args:
            error: Database exception
            
        Returns:
            Tuple of (error_message, status_code)
        """
        if isinstance(error, IntegrityError):
            if 'UNIQUE constraint failed' in str(error) or 'Duplicate entry' in str(error):
                return 'A record with this information already exists.', 400
            elif 'FOREIGN KEY constraint failed' in str(error):
                return 'Cannot complete this action due to related data constraints.', 400
            elif 'NOT NULL constraint failed' in str(error):
                return 'Required information is missing.', 400
            else:
                return 'Database constraint violation occurred.', 400
        
        elif isinstance(error, OperationalError):
            return 'Database operation failed. Please try again later.', 500
        
        else:
            return 'Database error occurred.', 500
    
    @staticmethod
    def handle_validation_error(error):
        """
        Handle validation errors.
        
        Args:
            error: Validation exception
            
        Returns:
            Tuple of (error_message, status_code)
        """
        return f'Validation failed: {str(error)}', 400
    
    @staticmethod
    def safe_json_response(data=None, error=None, status_code=200):
        """
        Create a safe JSON response with error handling.
        
        Args:
            data: Response data
            error: Error message if any
            status_code: HTTP status code
            
        Returns:
            JSON response
        """
        try:
            response_data = {}
            
            if error:
                response_data['success'] = False
                response_data['error'] = str(error)
            else:
                response_data['success'] = True
                if data is not None:
                    response_data['data'] = data
            
            return jsonify(response_data), status_code
            
        except Exception as e:
            ErrorHandler.log_error(e, 'Failed to create JSON response')
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500

def handle_errors(f):
    """
    Decorator to handle errors in route functions.
    
    Usage:
        @handle_errors
        def my_route():
            # route logic here
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except IntegrityError as e:
            ErrorHandler.log_error(e, f'Database integrity error in {f.__name__}')
            error_msg, status_code = ErrorHandler.handle_database_error(e)
            
            if request.is_json:
                return ErrorHandler.safe_json_response(error=error_msg, status_code=status_code)
            else:
                flash(error_msg, 'error')
                return redirect(request.referrer or url_for('dashboard.index'))
        
        except OperationalError as e:
            ErrorHandler.log_error(e, f'Database operational error in {f.__name__}')
            error_msg = 'Database is temporarily unavailable. Please try again later.'
            
            if request.is_json:
                return ErrorHandler.safe_json_response(error=error_msg, status_code=500)
            else:
                flash(error_msg, 'error')
                return redirect(request.referrer or url_for('dashboard.index'))
        
        except BadRequest as e:
            ErrorHandler.log_error(e, f'Bad request in {f.__name__}')
            error_msg = 'Invalid request data.'
            
            if request.is_json:
                return ErrorHandler.safe_json_response(error=error_msg, status_code=400)
            else:
                flash(error_msg, 'error')
                return redirect(request.referrer or url_for('dashboard.index'))
        
        except ValueError as e:
            ErrorHandler.log_error(e, f'Value error in {f.__name__}')
            error_msg = 'Invalid data provided.'
            
            if request.is_json:
                return ErrorHandler.safe_json_response(error=error_msg, status_code=400)
            else:
                flash(error_msg, 'error')
                return redirect(request.referrer or url_for('dashboard.index'))
        
        except Exception as e:
            ErrorHandler.log_error(e, f'Unexpected error in {f.__name__}')
            error_msg = 'An unexpected error occurred. Please try again.'
            
            if request.is_json:
                return ErrorHandler.safe_json_response(error=error_msg, status_code=500)
            else:
                flash(error_msg, 'error')
                return redirect(request.referrer or url_for('dashboard.index'))
    
    return decorated_function

def handle_json_errors(f):
    """
    Decorator specifically for JSON API endpoints.
    
    Usage:
        @handle_json_errors
        def api_endpoint():
            # API logic here
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except IntegrityError as e:
            ErrorHandler.log_error(e, f'Database integrity error in {f.__name__}')
            error_msg, status_code = ErrorHandler.handle_database_error(e)
            return ErrorHandler.safe_json_response(error=error_msg, status_code=status_code)
        
        except OperationalError as e:
            ErrorHandler.log_error(e, f'Database operational error in {f.__name__}')
            return ErrorHandler.safe_json_response(error='Database temporarily unavailable', status_code=500)
        
        except BadRequest as e:
            ErrorHandler.log_error(e, f'Bad request in {f.__name__}')
            return ErrorHandler.safe_json_response(error='Invalid request data', status_code=400)
        
        except json.JSONDecodeError as e:
            ErrorHandler.log_error(e, f'JSON decode error in {f.__name__}')
            return ErrorHandler.safe_json_response(error='Failed to decode JSON object: Invalid JSON format', status_code=400)
        
        except ValueError as e:
            ErrorHandler.log_error(e, f'Value error in {f.__name__}')
            return ErrorHandler.safe_json_response(error='Invalid data provided', status_code=400)
        
        except Exception as e:
            ErrorHandler.log_error(e, f'Unexpected error in {f.__name__}')
            return ErrorHandler.safe_json_response(error='Internal server error', status_code=500)
    
    return decorated_function