"""
Validation Service for reusable form and data validation
Provides consistent validation logic across the application
"""
import re
from datetime import datetime, date, time
from typing import Dict, List, Any, Tuple, Optional


class ValidationService:
    """Centralized validation service"""
    
    # Common validation patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^(\+91|91)?[6789]\d{9}$')  # Indian phone numbers
    STRONG_PASSWORD_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Validate email format
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email:
            return False, "Email is required"
        
        if len(email) > 120:
            return False, "Email address is too long"
        
        if not ValidationService.EMAIL_PATTERN.match(email):
            return False, "Invalid email format"
        
        return True, ""
    
    @staticmethod
    def validate_phone(phone: str, required: bool = True) -> Tuple[bool, str]:
        """
        Validate phone number (Indian format)
        
        Args:
            phone: Phone number to validate
            required: Whether phone is required
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not phone:
            return not required, "Phone number is required" if required else ""
        
        # Remove spaces and dashes
        clean_phone = re.sub(r'[\s-]', '', phone)
        
        if not ValidationService.PHONE_PATTERN.match(clean_phone):
            return False, "Invalid phone number format (10 digits starting with 6,7,8,9)"
        
        return True, ""
    
    @staticmethod
    def validate_password(password: str, confirm_password: str = None) -> Tuple[bool, str]:
        """
        Validate password strength and confirmation
        
        Args:
            password: Password to validate
            confirm_password: Password confirmation (optional)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"
        
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if len(password) > 128:
            return False, "Password is too long"
        
        # Check for basic requirements
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        if not re.search(r'[@$!%*?&]', password):
            return False, "Password must contain at least one special character (@$!%*?&)"
        
        # Check confirmation if provided
        if confirm_password is not None and password != confirm_password:
            return False, "Passwords do not match"
        
        return True, ""
    
    @staticmethod
    def validate_name(name: str, field_name: str = "Name") -> Tuple[bool, str]:
        """
        Validate name fields
        
        Args:
            name: Name to validate
            field_name: Name of the field for error messages
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, f"{field_name} is required"
        
        if len(name.strip()) < 2:
            return False, f"{field_name} must be at least 2 characters long"
        
        if len(name) > 100:
            return False, f"{field_name} is too long"
        
        # Only allow letters, spaces, hyphens, and apostrophes
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", name):
            return False, f"{field_name} contains invalid characters"
        
        return True, ""
    
    @staticmethod
    def validate_date(date_str: str, field_name: str = "Date", 
                     min_date: date = None, max_date: date = None) -> Tuple[bool, str]:
        """
        Validate date fields
        
        Args:
            date_str: Date string to validate
            field_name: Name of the field for error messages
            min_date: Minimum allowed date
            max_date: Maximum allowed date
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not date_str:
            return False, f"{field_name} is required"
        
        try:
            # Parse date
            if isinstance(date_str, str):
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            elif isinstance(date_str, date):
                parsed_date = date_str
            else:
                return False, f"Invalid {field_name} format"
            
            # Check range
            if min_date and parsed_date < min_date:
                return False, f"{field_name} cannot be before {min_date.strftime('%Y-%m-%d')}"
            
            if max_date and parsed_date > max_date:
                return False, f"{field_name} cannot be after {max_date.strftime('%Y-%m-%d')}"
            
            return True, ""
            
        except ValueError:
            return False, f"Invalid {field_name} format (YYYY-MM-DD expected)"
    
    @staticmethod
    def validate_time(time_str: str, field_name: str = "Time") -> Tuple[bool, str]:
        """
        Validate time fields
        
        Args:
            time_str: Time string to validate
            field_name: Name of the field for error messages
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not time_str:
            return False, f"{field_name} is required"
        
        try:
            # Parse time
            if isinstance(time_str, str):
                parsed_time = datetime.strptime(time_str, '%H:%M').time()
            elif isinstance(time_str, time):
                parsed_time = time_str
            else:
                return False, f"Invalid {field_name} format"
            
            return True, ""
            
        except ValueError:
            return False, f"Invalid {field_name} format (HH:MM expected)"
    
    @staticmethod
    def validate_choice(value: str, choices: List[str], field_name: str = "Selection") -> Tuple[bool, str]:
        """
        Validate choice fields
        
        Args:
            value: Value to validate
            choices: List of valid choices
            field_name: Name of the field for error messages
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, f"{field_name} is required"
        
        if value not in choices:
            return False, f"Invalid {field_name}. Must be one of: {', '.join(choices)}"
        
        return True, ""
    
    @staticmethod
    def validate_json_field(json_str: str, field_name: str = "Field", required: bool = False) -> Tuple[bool, str]:
        """
        Validate JSON fields
        
        Args:
            json_str: JSON string to validate
            field_name: Name of the field for error messages
            required: Whether the field is required
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not json_str:
            return not required, f"{field_name} is required" if required else ""
        
        try:
            import json
            json.loads(json_str)
            return True, ""
        except json.JSONDecodeError:
            return False, f"Invalid {field_name} format"
    
    @staticmethod
    def validate_student_data(data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Comprehensive student data validation
        
        Args:
            data: Student data dictionary
            
        Returns:
            Dictionary of field errors
        """
        errors = {}
        
        # Validate name
        is_valid, error = ValidationService.validate_name(data.get('full_name'), 'Full Name')
        if not is_valid:
            errors['full_name'] = [error]
        
        # Validate email
        is_valid, error = ValidationService.validate_email(data.get('email'))
        if not is_valid:
            errors['email'] = [error]
        
        # Validate phone (optional)
        is_valid, error = ValidationService.validate_phone(data.get('phone'), required=False)
        if not is_valid:
            errors['phone'] = [error]
        
        # Validate date of birth
        if data.get('date_of_birth'):
            max_date = date.today() - timedelta(days=365*5)  # At least 5 years old
            min_date = date.today() - timedelta(days=365*100)  # Not more than 100 years old
            
            is_valid, error = ValidationService.validate_date(
                data.get('date_of_birth'), 'Date of Birth', min_date, max_date
            )
            if not is_valid:
                errors['date_of_birth'] = [error]
        
        # Validate grade
        valid_grades = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        is_valid, error = ValidationService.validate_choice(
            data.get('grade'), valid_grades, 'Grade'
        )
        if not is_valid:
            errors['grade'] = [error]
        
        # Validate board
        valid_boards = ['CBSE', 'ICSE', 'State Board', 'IB', 'IGCSE', 'Other']
        is_valid, error = ValidationService.validate_choice(
            data.get('board'), valid_boards, 'Board'
        )
        if not is_valid:
            errors['board'] = [error]
        
        return errors
    
    @staticmethod
    def validate_class_data(data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Comprehensive class data validation
        
        Args:
            data: Class data dictionary
            
        Returns:
            Dictionary of field errors
        """
        errors = {}
        
        # Validate subject
        if not data.get('subject') or len(data.get('subject', '').strip()) < 2:
            errors['subject'] = ['Subject is required and must be at least 2 characters']
        
        # Validate date
        is_valid, error = ValidationService.validate_date(
            data.get('scheduled_date'), 'Scheduled Date', min_date=date.today()
        )
        if not is_valid:
            errors['scheduled_date'] = [error]
        
        # Validate time
        is_valid, error = ValidationService.validate_time(
            data.get('scheduled_time'), 'Scheduled Time'
        )
        if not is_valid:
            errors['scheduled_time'] = [error]
        
        # Validate duration
        try:
            duration = int(data.get('duration', 0))
            if duration < 15:
                errors['duration'] = ['Duration must be at least 15 minutes']
            elif duration > 480:
                errors['duration'] = ['Duration cannot exceed 8 hours']
        except (ValueError, TypeError):
            errors['duration'] = ['Invalid duration format']
        
        # Validate class type
        valid_types = ['one_on_one', 'group', 'demo']
        is_valid, error = ValidationService.validate_choice(
            data.get('class_type'), valid_types, 'Class Type'
        )
        if not is_valid:
            errors['class_type'] = [error]
        
        return errors


# Decorator for route validation
def validate_form_data(validation_func):
    """
    Decorator to validate form data before processing
    
    Args:
        validation_func: Function to validate the form data
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            # Get form data
            data = request.get_json() if request.is_json else request.form.to_dict()
            
            # Validate data
            errors = validation_func(data)
            
            if errors:
                if request.is_json:
                    return jsonify({'success': False, 'errors': errors}), 400
                else:
                    # For form submissions, you might want to flash errors
                    from flask import flash
                    for field, field_errors in errors.items():
                        for error in field_errors:
                            flash(f"{field}: {error}", 'error')
                    return func(*args, **kwargs)  # Continue with original function
            
            return func(*args, **kwargs)
        return wrapper
    return decorator