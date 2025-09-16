"""
Email Error Handler Service - Provides robust error handling and fallback mechanisms
"""
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from functools import wraps
from flask import current_app
import traceback
import json

class EmailErrorHandler:
    """Centralized error handling for email services"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_log = []
        self.max_retry_attempts = 3
        self.fallback_recipients = []
        
    def handle_email_errors(self, func: Callable) -> Callable:
        """Decorator for robust email error handling"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Attempt to execute the email function
                return self._execute_with_retry(func, *args, **kwargs)
            except Exception as e:
                self._log_critical_error(func.__name__, e, args, kwargs)
                return False
        return wrapper
    
    def _execute_with_retry(self, func: Callable, *args, **kwargs) -> bool:
        """Execute function with retry mechanism"""
        last_exception = None
        
        for attempt in range(self.max_retry_attempts):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    self.logger.info(f"Email function {func.__name__} succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"Email function {func.__name__} failed on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.max_retry_attempts - 1:
                    # Wait between retries (exponential backoff)
                    import time
                    time.sleep(2 ** attempt)
                    continue
                else:
                    # All retries exhausted
                    raise e
        
        return False
    
    def _log_critical_error(self, function_name: str, error: Exception, args: tuple, kwargs: dict):
        """Log critical email errors for monitoring"""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'function': function_name,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'args': str(args)[:500],  # Limit size
            'kwargs': str(kwargs)[:500]  # Limit size
        }
        
        self.error_log.append(error_data)
        self.logger.error(f"CRITICAL EMAIL ERROR: {json.dumps(error_data, indent=2)}")
        
        # Send emergency notification to admin if configured
        try:
            self._send_error_notification(error_data)
        except Exception as notification_error:
            self.logger.error(f"Failed to send error notification: {str(notification_error)}")
    
    def _send_error_notification(self, error_data: Dict[str, Any]):
        """Send error notification to system administrators"""
        if not self.fallback_recipients:
            return
        
        try:
            from flask_mail import Message
            from app import mail
            
            msg = Message(
                subject=f"CRITICAL EMAIL SYSTEM ERROR - {error_data['function']}",
                recipients=self.fallback_recipients,
                html=self._generate_error_email_html(error_data)
            )
            
            mail.send(msg)
        except Exception as e:
            self.logger.error(f"Emergency notification failed: {str(e)}")
    
    def _generate_error_email_html(self, error_data: Dict[str, Any]) -> str:
        """Generate HTML for error notification email"""
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .error-box {{ background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .code {{ background: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; white-space: pre-wrap; }}
                h1 {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <h1>🚨 Critical Email System Error</h1>
            
            <div class="error-box">
                <h3>Error Details</h3>
                <p><strong>Function:</strong> {error_data['function']}</p>
                <p><strong>Error Type:</strong> {error_data['error_type']}</p>
                <p><strong>Time:</strong> {error_data['timestamp']}</p>
                <p><strong>Message:</strong> {error_data['error_message']}</p>
            </div>
            
            <div class="error-box">
                <h3>Stack Trace</h3>
                <div class="code">{error_data['traceback']}</div>
            </div>
            
            <div class="error-box">
                <h3>Function Arguments</h3>
                <p><strong>Args:</strong> {error_data['args']}</p>
                <p><strong>Kwargs:</strong> {error_data['kwargs']}</p>
            </div>
            
            <p><strong>Action Required:</strong> Please investigate and resolve this email system error immediately.</p>
        </body>
        </html>
        """
    
    def validate_email_recipients(self, recipients: List[str]) -> List[str]:
        """Validate and clean email recipients"""
        valid_recipients = []
        
        for email in recipients:
            if self._is_valid_email(email):
                valid_recipients.append(email.strip().lower())
            else:
                self.logger.warning(f"Invalid email address detected: {email}")
        
        if not valid_recipients:
            self.logger.error("No valid email recipients found!")
            raise ValueError("No valid email recipients provided")
        
        return valid_recipients
    
    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation"""
        if not email or not isinstance(email, str):
            return False
        
        email = email.strip()
        if '@' not in email or len(email) < 5:
            return False
        
        local_part, domain = email.rsplit('@', 1)
        if not local_part or not domain or '.' not in domain:
            return False
        
        return True
    
    def validate_email_context(self, context: Dict[str, Any], required_fields: List[str] = None) -> Dict[str, Any]:
        """Validate email template context"""
        if not isinstance(context, dict):
            raise ValueError("Email context must be a dictionary")
        
        # Check for required fields
        if required_fields:
            missing_fields = [field for field in required_fields if field not in context]
            if missing_fields:
                self.logger.warning(f"Missing required context fields: {missing_fields}")
                # Add default values for missing fields
                for field in missing_fields:
                    context[field] = f"[{field} not provided]"
        
        # Sanitize context values
        sanitized_context = {}
        for key, value in context.items():
            try:
                # Convert None values to empty strings
                if value is None:
                    sanitized_context[key] = ""
                # Convert datetime objects to strings
                elif hasattr(value, 'strftime'):
                    sanitized_context[key] = value
                # Keep other values as-is
                else:
                    sanitized_context[key] = value
            except Exception as e:
                self.logger.warning(f"Error processing context field {key}: {str(e)}")
                sanitized_context[key] = str(value) if value is not None else ""
        
        return sanitized_context
    
    def check_mail_configuration(self) -> Dict[str, Any]:
        """Check mail server configuration"""
        try:
            config_status = {
                'mail_server': bool(current_app.config.get('MAIL_SERVER')),
                'mail_port': bool(current_app.config.get('MAIL_PORT')),
                'mail_username': bool(current_app.config.get('MAIL_USERNAME')),
                'mail_password': bool(current_app.config.get('MAIL_PASSWORD')),
                'mail_use_tls': bool(current_app.config.get('MAIL_USE_TLS')),
                'mail_default_sender': bool(current_app.config.get('MAIL_DEFAULT_SENDER')),
                'overall_status': 'configured'
            }
            
            # Check if all required settings are present
            required_settings = ['mail_server', 'mail_port', 'mail_default_sender']
            missing_settings = [setting for setting, configured in config_status.items() 
                              if setting in required_settings and not configured]
            
            if missing_settings:
                config_status['overall_status'] = 'incomplete'
                config_status['missing_settings'] = missing_settings
                self.logger.error(f"Mail configuration incomplete. Missing: {missing_settings}")
            else:
                config_status['overall_status'] = 'complete'
            
            return config_status
            
        except Exception as e:
            self.logger.error(f"Error checking mail configuration: {str(e)}")
            return {'overall_status': 'error', 'error': str(e)}
    
    def get_error_summary(self, limit: int = 10) -> Dict[str, Any]:
        """Get summary of recent email errors"""
        recent_errors = self.error_log[-limit:]
        
        error_counts = {}
        for error in recent_errors:
            error_type = error.get('error_type', 'Unknown')
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return {
            'total_errors': len(self.error_log),
            'recent_errors': len(recent_errors),
            'error_types': error_counts,
            'last_error': self.error_log[-1] if self.error_log else None,
            'configuration_status': self.check_mail_configuration()
        }
    
    def set_fallback_recipients(self, emails: List[str]):
        """Set fallback recipients for error notifications"""
        self.fallback_recipients = self.validate_email_recipients(emails)
        self.logger.info(f"Fallback recipients set: {len(self.fallback_recipients)} emails")

# Global instance
email_error_handler = EmailErrorHandler()