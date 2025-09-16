"""
Input sanitization utilities for secure form handling.
"""
import re
import html
from typing import Optional, Union

class InputSanitizer:
    """Utility class for sanitizing user input"""
    
    @staticmethod
    def sanitize_text(text: Optional[str], max_length: int = None, allow_html: bool = False) -> str:
        """
        Sanitize text input by escaping HTML and optionally limiting length.
        
        Args:
            text: The input text to sanitize
            max_length: Maximum allowed length (optional)
            allow_html: Whether to allow HTML tags (default: False)
        
        Returns:
            Sanitized text string
        """
        if not text:
            return ''
        
        # Convert to string and strip whitespace
        text = str(text).strip()
        
        # HTML escape unless HTML is explicitly allowed
        if not allow_html:
            text = html.escape(text)
        
        # Limit length if specified
        if max_length and len(text) > max_length:
            text = text[:max_length]
        
        return text
    
    @staticmethod
    def sanitize_email(email: Optional[str]) -> str:
        """
        Sanitize email input with basic validation.
        
        Args:
            email: The email to sanitize
        
        Returns:
            Sanitized email string
        """
        if not email:
            return ''
        
        email = str(email).strip().lower()
        
        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return ''
        
        return email
    
    @staticmethod
    def sanitize_phone(phone: Optional[str]) -> str:
        """
        Sanitize phone number input.
        
        Args:
            phone: The phone number to sanitize
        
        Returns:
            Sanitized phone number
        """
        if not phone:
            return ''
        
        phone = str(phone).strip()
        
        # Remove all non-digit characters except + and spaces
        phone = re.sub(r'[^0-9+\s-]', '', phone)
        
        # Limit length
        if len(phone) > 20:
            phone = phone[:20]
        
        return phone
    
    @staticmethod
    def sanitize_name(name: Optional[str]) -> str:
        """
        Sanitize name input (allows letters, spaces, hyphens, apostrophes).
        
        Args:
            name: The name to sanitize
        
        Returns:
            Sanitized name
        """
        if not name:
            return ''
        
        name = str(name).strip()
        
        # Allow only letters, spaces, hyphens, and apostrophes
        name = re.sub(r"[^a-zA-Z\s'-]", '', name)
        
        # Remove multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        # Limit length
        if len(name) > 100:
            name = name[:100]
        
        return name
    
    @staticmethod
    def sanitize_numeric(value: Optional[Union[str, int, float]], min_val: float = None, max_val: float = None) -> Optional[float]:
        """
        Sanitize numeric input.
        
        Args:
            value: The numeric value to sanitize
            min_val: Minimum allowed value (optional)
            max_val: Maximum allowed value (optional)
        
        Returns:
            Sanitized numeric value or None if invalid
        """
        if value is None or value == '':
            return None
        
        try:
            num_val = float(value)
            
            # Apply bounds if specified
            if min_val is not None and num_val < min_val:
                return min_val
            if max_val is not None and num_val > max_val:
                return max_val
            
            return num_val
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def sanitize_grade(grade: Optional[str]) -> str:
        """
        Sanitize grade input (allows numbers and common grade formats).
        
        Args:
            grade: The grade to sanitize
        
        Returns:
            Sanitized grade
        """
        if not grade:
            return ''
        
        grade = str(grade).strip()
        
        # Allow only alphanumeric characters, spaces, and common grade separators
        grade = re.sub(r'[^a-zA-Z0-9\s,-]', '', grade)
        
        # Limit length
        if len(grade) > 50:
            grade = grade[:50]
        
        return grade
    
    @staticmethod
    def sanitize_subject_list(subjects: Optional[str]) -> str:
        """
        Sanitize comma-separated subject list.
        
        Args:
            subjects: The subjects string to sanitize
        
        Returns:
            Sanitized subjects string
        """
        if not subjects:
            return ''
        
        subjects = str(subjects).strip()
        
        # Allow letters, numbers, spaces, commas, and common punctuation
        subjects = re.sub(r'[^a-zA-Z0-9\s,.-]', '', subjects)
        
        # Clean up multiple commas and spaces
        subjects = re.sub(r',+', ',', subjects)
        subjects = re.sub(r'\s+', ' ', subjects)
        
        # Limit length
        if len(subjects) > 500:
            subjects = subjects[:500]
        
        return subjects
    
    @staticmethod
    def sanitize_address(address: Optional[str]) -> str:
        """
        Sanitize address input.
        
        Args:
            address: The address to sanitize
        
        Returns:
            Sanitized address
        """
        if not address:
            return ''
        
        address = str(address).strip()
        
        # Allow letters, numbers, spaces, and common address punctuation
        address = re.sub(r'[^a-zA-Z0-9\s,.-/#]', '', address)
        
        # Clean up multiple spaces
        address = re.sub(r'\s+', ' ', address)
        
        # Limit length
        if len(address) > 500:
            address = address[:500]
        
        return address
    
    @staticmethod
    def sanitize_form_data(form_data: dict, field_types: dict = None) -> dict:
        """
        Sanitize entire form data dictionary based on field types.
        
        Args:
            form_data: Dictionary of form data
            field_types: Dictionary mapping field names to sanitization types
        
        Returns:
            Dictionary of sanitized form data
        """
        if not field_types:
            field_types = {}
        
        sanitized = {}
        
        for field, value in form_data.items():
            field_type = field_types.get(field, 'text')
            
            if field_type == 'email':
                sanitized[field] = InputSanitizer.sanitize_email(value)
            elif field_type == 'phone':
                sanitized[field] = InputSanitizer.sanitize_phone(value)
            elif field_type == 'name':
                sanitized[field] = InputSanitizer.sanitize_name(value)
            elif field_type == 'grade':
                sanitized[field] = InputSanitizer.sanitize_grade(value)
            elif field_type == 'subjects':
                sanitized[field] = InputSanitizer.sanitize_subject_list(value)
            elif field_type == 'address':
                sanitized[field] = InputSanitizer.sanitize_address(value)
            elif field_type == 'numeric':
                sanitized[field] = InputSanitizer.sanitize_numeric(value)
            else:  # default to text
                sanitized[field] = InputSanitizer.sanitize_text(value)
        
        return sanitized