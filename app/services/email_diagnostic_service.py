"""
Email Diagnostic Service
Comprehensive email troubleshooting and fixing service for LMS
"""

import logging
import smtplib
import ssl
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import current_app, render_template
from flask_mail import Message
from app import mail, db
from app.models.user import User
from app.models.student import Student
from app.utils.email import send_email, test_email_connection
import traceback
import re

class EmailDiagnosticService:
    """Service for diagnosing and fixing email issues"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def run_comprehensive_email_diagnostic(self) -> Dict[str, Any]:
        """
        Run a comprehensive email diagnostic check
        """
        diagnostic_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'unknown',
            'tests': {}
        }
        
        try:
            # Test 1: Configuration Check
            config_result = self._test_email_configuration()
            diagnostic_results['tests']['configuration'] = config_result
            
            # Test 2: SMTP Connection Test
            smtp_result = self._test_smtp_connection()
            diagnostic_results['tests']['smtp_connection'] = smtp_result
            
            # Test 3: Authentication Test
            auth_result = self._test_smtp_authentication()
            diagnostic_results['tests']['authentication'] = auth_result
            
            # Test 4: Template Rendering Test
            template_result = self._test_template_rendering()
            diagnostic_results['tests']['template_rendering'] = template_result
            
            # Test 5: Email Sending Test
            send_result = self._test_email_sending()
            diagnostic_results['tests']['email_sending'] = send_result
            
            # Test 6: Recipient Validation Test
            recipient_result = self._test_recipient_validation()
            diagnostic_results['tests']['recipient_validation'] = recipient_result
            
            # Determine overall status
            all_passed = all(test.get('status') == 'passed' for test in diagnostic_results['tests'].values())
            has_critical_failure = any(test.get('status') == 'critical_failure' for test in diagnostic_results['tests'].values())
            
            if all_passed:
                diagnostic_results['overall_status'] = 'healthy'
            elif has_critical_failure:
                diagnostic_results['overall_status'] = 'critical'
            else:
                diagnostic_results['overall_status'] = 'warning'
            
            # Generate recommendations
            diagnostic_results['recommendations'] = self._generate_recommendations(diagnostic_results['tests'])
            
            return diagnostic_results
            
        except Exception as e:
            self.logger.error(f"Error during email diagnostic: {str(e)}")
            diagnostic_results['overall_status'] = 'error'
            diagnostic_results['error'] = str(e)
            return diagnostic_results
    
    def _test_email_configuration(self) -> Dict[str, Any]:
        """Test email configuration completeness"""
        result = {
            'name': 'Email Configuration Check',
            'status': 'passed',
            'details': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            required_configs = {
                'MAIL_SERVER': current_app.config.get('MAIL_SERVER'),
                'MAIL_PORT': current_app.config.get('MAIL_PORT'),
                'MAIL_USERNAME': current_app.config.get('MAIL_USERNAME'),
                'MAIL_PASSWORD': current_app.config.get('MAIL_PASSWORD'),
                'MAIL_USE_TLS': current_app.config.get('MAIL_USE_TLS')
            }
            
            for key, value in required_configs.items():
                result['details'][key] = 'configured' if value else 'missing'
                if not value:
                    result['issues'].append(f"{key} is not configured")
                    result['status'] = 'failed'
            
            # Check for common configuration issues
            if current_app.config.get('MAIL_SERVER') == 'smtp.gmail.com':
                if not current_app.config.get('MAIL_PASSWORD'):
                    result['issues'].append("Gmail requires App Password, not regular password")
                    result['recommendations'].append("Generate Gmail App Password in Google Account settings")
            
            if current_app.config.get('MAIL_PORT') not in [587, 465, 25]:
                result['issues'].append(f"Unusual mail port: {current_app.config.get('MAIL_PORT')}")
                result['status'] = 'warning'
            
            return result
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            return result
    
    def _test_smtp_connection(self) -> Dict[str, Any]:
        """Test SMTP server connection"""
        result = {
            'name': 'SMTP Connection Test',
            'status': 'passed',
            'details': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            mail_server = current_app.config.get('MAIL_SERVER')
            mail_port = current_app.config.get('MAIL_PORT', 587)
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            
            if not mail_server:
                result['status'] = 'critical_failure'
                result['issues'].append("MAIL_SERVER not configured")
                return result
            
            # Test connection
            if use_tls and mail_port == 587:
                server = smtplib.SMTP(mail_server, mail_port)
                server.starttls()
            elif mail_port == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(mail_server, mail_port, context=context)
            else:
                server = smtplib.SMTP(mail_server, mail_port)
            
            # Test basic connection
            status = server.noop()
            result['details']['smtp_response'] = status
            
            server.quit()
            
            result['details']['connection_method'] = 'TLS' if use_tls else 'SSL' if mail_port == 465 else 'Plain'
            result['status'] = 'passed'
            
        except smtplib.SMTPConnectError as e:
            result['status'] = 'critical_failure'
            result['issues'].append(f"Cannot connect to SMTP server: {str(e)}")
            result['recommendations'].append("Check MAIL_SERVER and MAIL_PORT configuration")
        except smtplib.SMTPServerDisconnected as e:
            result['status'] = 'failed'
            result['issues'].append(f"SMTP server disconnected: {str(e)}")
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['issues'].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def _test_smtp_authentication(self) -> Dict[str, Any]:
        """Test SMTP authentication"""
        result = {
            'name': 'SMTP Authentication Test',
            'status': 'passed',
            'details': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            mail_server = current_app.config.get('MAIL_SERVER')
            mail_port = current_app.config.get('MAIL_PORT', 587)
            mail_username = current_app.config.get('MAIL_USERNAME')
            mail_password = current_app.config.get('MAIL_PASSWORD')
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            
            if not all([mail_server, mail_username, mail_password]):
                result['status'] = 'critical_failure'
                result['issues'].append("Missing authentication credentials")
                return result
            
            # Test authentication
            if use_tls and mail_port == 587:
                server = smtplib.SMTP(mail_server, mail_port)
                server.starttls()
            elif mail_port == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(mail_server, mail_port, context=context)
            else:
                server = smtplib.SMTP(mail_server, mail_port)
            
            # Attempt login
            server.login(mail_username, mail_password)
            result['details']['username'] = mail_username
            result['details']['auth_method'] = 'LOGIN'
            result['status'] = 'passed'
            
            server.quit()
            
        except smtplib.SMTPAuthenticationError as e:
            result['status'] = 'critical_failure'
            result['issues'].append(f"Authentication failed: {str(e)}")
            if 'gmail' in mail_server.lower():
                result['recommendations'].extend([
                    "For Gmail, use App Password instead of regular password",
                    "Enable 2-factor authentication and generate App Password",
                    "Make sure 'Less secure app access' is enabled (if not using App Password)"
                ])
            else:
                result['recommendations'].append("Verify MAIL_USERNAME and MAIL_PASSWORD are correct")
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _test_template_rendering(self) -> Dict[str, Any]:
        """Test email template rendering"""
        result = {
            'name': 'Template Rendering Test',
            'status': 'passed',
            'details': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test templates that are commonly used
            test_templates = [
                ('email/password_reset.html', {
                    'user': {'full_name': 'Test User'},
                    'token': 'test_token',
                    'app_name': 'Test LMS'
                }),
                ('email/onboarding.html', {
                    'user': {'full_name': 'Test User', 'username': 'testuser'},
                    'password': 'test_password',
                    'app_name': 'Test LMS'
                })
            ]
            
            rendered_templates = []
            
            for template_name, context in test_templates:
                try:
                    rendered = render_template(template_name, **context)
                    rendered_templates.append({
                        'template': template_name,
                        'status': 'success',
                        'size': len(rendered)
                    })
                except Exception as template_error:
                    rendered_templates.append({
                        'template': template_name,
                        'status': 'error',
                        'error': str(template_error)
                    })
                    result['issues'].append(f"Template {template_name} failed to render: {str(template_error)}")
                    result['status'] = 'failed'
            
            result['details']['templates'] = rendered_templates
            
            # Test notification templates
            notification_templates = [
                'email/notifications/general_notification.html',
                'email/notifications/holiday_notification.html',
                'email/notifications/emergency_notification.html'
            ]
            
            for template_name in notification_templates:
                try:
                    test_context = {
                        'user': {'full_name': 'Test User', 'role': 'student'},
                        'notification': {
                            'title': 'Test Notification',
                            'message': 'This is a test message',
                            'type': 'general',
                            'priority': 'normal',
                            'created_at': datetime.utcnow()
                        },
                        'app_name': 'Test LMS',
                        'company_name': 'Test Institution'
                    }
                    
                    rendered = render_template(template_name, **test_context)
                    rendered_templates.append({
                        'template': template_name,
                        'status': 'success',
                        'size': len(rendered)
                    })
                except Exception as template_error:
                    rendered_templates.append({
                        'template': template_name,
                        'status': 'error',
                        'error': str(template_error)
                    })
                    result['issues'].append(f"Notification template {template_name} failed: {str(template_error)}")
                    result['status'] = 'warning'  # Not critical for basic email functionality
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _test_email_sending(self) -> Dict[str, Any]:
        """Test actual email sending"""
        result = {
            'name': 'Email Sending Test',
            'status': 'passed',
            'details': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get admin user for testing
            admin_user = User.query.filter_by(role='superadmin').first()
            if not admin_user or not admin_user.email:
                admin_user = User.query.filter_by(role='admin').first()
            
            if not admin_user or not admin_user.email:
                result['status'] = 'warning'
                result['issues'].append("No admin user with email found for testing")
                return result
            
            # Test sending a simple email
            test_subject = f"[LMS] Email System Test - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            test_html = """
            <html>
            <body>
                <h2>Email System Test</h2>
                <p>This is a test email to verify the email system is working correctly.</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Test Status:</strong> Email delivery successful</p>
                <p>If you received this email, the LMS email system is functioning properly.</p>
            </body>
            </html>
            """.format(timestamp=datetime.utcnow().isoformat())
            
            test_text = f"""
            Email System Test
            
            This is a test email to verify the email system is working correctly.
            
            Timestamp: {datetime.utcnow().isoformat()}
            Test Status: Email delivery successful
            
            If you received this email, the LMS email system is functioning properly.
            """
            
            # Send test email synchronously to get immediate result
            success = send_email(
                subject=test_subject,
                recipients=[admin_user.email],
                html_body=test_html,
                text_body=test_text,
                sync=True
            )
            
            if success:
                result['status'] = 'passed'
                result['details']['test_recipient'] = admin_user.email
                result['details']['test_subject'] = test_subject
            else:
                result['status'] = 'failed'
                result['issues'].append("Email sending failed")
                result['recommendations'].append("Check SMTP configuration and credentials")
        
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['issues'].append(f"Email sending test error: {str(e)}")
        
        return result
    
    def _test_recipient_validation(self) -> Dict[str, Any]:
        """Test recipient email validation"""
        result = {
            'name': 'Recipient Validation Test',
            'status': 'passed',
            'details': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test various email scenarios
            test_emails = [
                ('valid@example.com', True),
                ('user.name+tag@domain.co.uk', True),
                ('invalid-email', False),
                ('missing@domain', False),
                ('spaces in@email.com', False),
                ('@domain.com', False),
                ('user@', False),
                ('', False)
            ]
            
            validation_results = []
            
            for email, should_be_valid in test_emails:
                is_valid = self._validate_email(email)
                validation_results.append({
                    'email': email,
                    'expected': should_be_valid,
                    'actual': is_valid,
                    'correct': is_valid == should_be_valid
                })
                
                if is_valid != should_be_valid:
                    result['issues'].append(f"Email validation incorrect for: {email}")
                    result['status'] = 'warning'
            
            result['details']['validation_tests'] = validation_results
            
            # Test user email validation
            users_with_invalid_emails = []
            users = User.query.filter(User.email.isnot(None)).all()
            
            for user in users[:50]:  # Check first 50 users to avoid overwhelming
                if user.email and not self._validate_email(user.email):
                    users_with_invalid_emails.append({
                        'user_id': user.id,
                        'username': user.username,
                        'email': user.email
                    })
            
            if users_with_invalid_emails:
                result['status'] = 'warning'
                result['issues'].append(f"Found {len(users_with_invalid_emails)} users with invalid email addresses")
                result['details']['invalid_user_emails'] = users_with_invalid_emails[:10]  # Show first 10
                result['recommendations'].append("Review and update invalid user email addresses")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address format"""
        if not email or not isinstance(email, str):
            return False
        
        # Basic email regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip()))
    
    def _generate_recommendations(self, test_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Collect all recommendations from individual tests
        for test_name, test_result in test_results.items():
            if 'recommendations' in test_result:
                recommendations.extend(test_result['recommendations'])
        
        # Add general recommendations based on overall results
        failed_tests = [name for name, result in test_results.items() if result.get('status') in ['failed', 'critical_failure']]
        
        if failed_tests:
            recommendations.append("Address failed tests in order of priority: Configuration → SMTP → Authentication → Sending")
        
        if test_results.get('smtp_connection', {}).get('status') == 'critical_failure':
            recommendations.append("SMTP connection issues are blocking all email functionality - fix this first")
        
        if test_results.get('authentication', {}).get('status') == 'critical_failure':
            recommendations.append("Authentication issues prevent email sending - verify credentials")
        
        # Remove duplicates while preserving order
        unique_recommendations = []
        for rec in recommendations:
            if rec not in unique_recommendations:
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def fix_common_email_issues(self) -> Dict[str, Any]:
        """Attempt to fix common email issues automatically"""
        fix_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'fixes_applied': [],
            'manual_actions_required': []
        }
        
        try:
            # Run diagnostic first
            diagnostic = self.run_comprehensive_email_diagnostic()
            
            # Fix 1: Clean up invalid user emails
            invalid_email_fix = self._fix_invalid_user_emails()
            if invalid_email_fix['fixed_count'] > 0:
                fix_results['fixes_applied'].append(invalid_email_fix)
            
            # Fix 2: Add missing configuration placeholders
            config_fix = self._add_config_placeholders()
            if config_fix['changes_made']:
                fix_results['fixes_applied'].append(config_fix)
            
            # Generate manual action items based on diagnostic
            if diagnostic['tests'].get('configuration', {}).get('status') in ['failed', 'critical_failure']:
                fix_results['manual_actions_required'].append({
                    'action': 'Update email configuration',
                    'description': 'Set MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, and MAIL_PASSWORD in environment variables',
                    'priority': 'high'
                })
            
            if diagnostic['tests'].get('authentication', {}).get('status') == 'critical_failure':
                fix_results['manual_actions_required'].append({
                    'action': 'Fix email authentication',
                    'description': 'Verify email credentials and enable App Password for Gmail',
                    'priority': 'critical'
                })
            
        except Exception as e:
            self.logger.error(f"Error during email issue fixing: {str(e)}")
            fix_results['error'] = str(e)
        
        return fix_results
    
    def _fix_invalid_user_emails(self) -> Dict[str, Any]:
        """Fix invalid user email addresses"""
        result = {
            'name': 'Invalid Email Fix',
            'fixed_count': 0,
            'issues_found': []
        }
        
        try:
            users = User.query.filter(User.email.isnot(None)).all()
            
            for user in users:
                if user.email and not self._validate_email(user.email):
                    # Try to fix common issues
                    original_email = user.email
                    fixed_email = self._attempt_email_fix(user.email)
                    
                    if fixed_email and self._validate_email(fixed_email):
                        user.email = fixed_email
                        result['fixed_count'] += 1
                        result['issues_found'].append({
                            'user_id': user.id,
                            'original': original_email,
                            'fixed': fixed_email
                        })
                    else:
                        result['issues_found'].append({
                            'user_id': user.id,
                            'email': original_email,
                            'status': 'requires_manual_fix'
                        })
            
            if result['fixed_count'] > 0:
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            result['error'] = str(e)
        
        return result
    
    def _attempt_email_fix(self, email: str) -> Optional[str]:
        """Attempt to fix common email issues"""
        if not email:
            return None
        
        # Remove whitespace
        email = email.strip()
        
        # Fix missing TLD
        if '@' in email and '.' not in email.split('@')[1]:
            parts = email.split('@')
            if len(parts) == 2:
                domain = parts[1].lower()
                # Common domain fixes
                domain_fixes = {
                    'gmail': 'gmail.com',
                    'yahoo': 'yahoo.com',
                    'hotmail': 'hotmail.com',
                    'outlook': 'outlook.com'
                }
                if domain in domain_fixes:
                    email = f"{parts[0]}@{domain_fixes[domain]}"
        
        return email if self._validate_email(email) else None
    
    def _add_config_placeholders(self) -> Dict[str, Any]:
        """Add configuration placeholders if missing"""
        result = {
            'name': 'Configuration Placeholder Fix',
            'changes_made': False,
            'placeholders_added': []
        }
        
        # This would typically involve updating a config file or environment
        # For now, we'll just identify what's missing
        required_configs = [
            'MAIL_SERVER',
            'MAIL_PORT',
            'MAIL_USERNAME',
            'MAIL_PASSWORD',
            'MAIL_USE_TLS'
        ]
        
        missing_configs = []
        for config in required_configs:
            if not current_app.config.get(config):
                missing_configs.append(config)
        
        if missing_configs:
            result['placeholders_added'] = missing_configs
            # In a real implementation, you might update a .env file or config
            # result['changes_made'] = True
        
        return result

# Global service instance
email_diagnostic_service = EmailDiagnosticService()