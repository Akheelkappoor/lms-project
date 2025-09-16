"""
Email System Validator - Comprehensive validation of email system components
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import os
from flask import current_app

class EmailSystemValidator:
    """Validates email system integrity and configuration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_results = []
        
    def validate_complete_system(self) -> Dict[str, Any]:
        """Perform comprehensive validation of the email system"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'unknown',
            'validations': {},
            'errors': [],
            'warnings': [],
            'recommendations': []
        }
        
        # Run all validation checks
        validations = [
            ('service_files', self._validate_service_files),
            ('template_files', self._validate_template_files),
            ('imports', self._validate_imports),
            ('configuration', self._validate_configuration),
            ('models', self._validate_model_methods),
            ('error_handling', self._validate_error_handling)
        ]
        
        for validation_name, validation_func in validations:
            try:
                validation_result = validation_func()
                results['validations'][validation_name] = validation_result
                
                if validation_result.get('status') == 'error':
                    results['errors'].extend(validation_result.get('errors', []))
                elif validation_result.get('status') == 'warning':
                    results['warnings'].extend(validation_result.get('warnings', []))
                    
            except Exception as e:
                error_msg = f"Validation {validation_name} failed: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        # Determine overall status
        if results['errors']:
            results['overall_status'] = 'error'
        elif results['warnings']:
            results['overall_status'] = 'warning'
        else:
            results['overall_status'] = 'success'
        
        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results)
        
        return results
    
    def _validate_service_files(self) -> Dict[str, Any]:
        """Validate email service files exist and are properly structured"""
        required_services = [
            'comprehensive_email_service.py',
            'tutor_email_service.py',
            'coordinator_email_service.py',
            'admin_email_service.py',
            'email_automation_service.py',
            'system_notification_service.py',
            'critical_alert_service.py',
            'email_error_handler.py'
        ]
        
        services_path = os.path.join(os.getcwd(), 'app', 'services')
        missing_services = []
        existing_services = []
        
        for service_file in required_services:
            service_path = os.path.join(services_path, service_file)
            if os.path.exists(service_path):
                existing_services.append(service_file)
                # Check file size (basic validation)
                file_size = os.path.getsize(service_path)
                if file_size < 1000:  # Less than 1KB might indicate empty or incomplete file
                    missing_services.append(f"{service_file} (file too small: {file_size} bytes)")
            else:
                missing_services.append(service_file)
        
        return {
            'status': 'error' if missing_services else 'success',
            'existing_services': len(existing_services),
            'total_required': len(required_services),
            'missing_services': missing_services,
            'errors': [f"Missing service file: {service}" for service in missing_services] if missing_services else []
        }
    
    def _validate_template_files(self) -> Dict[str, Any]:
        """Validate email template files and structure"""
        templates_path = os.path.join(os.getcwd(), 'app', 'templates', 'email')
        
        required_directories = [
            'student', 'tutor', 'coordinator', 'admin', 
            'sequences', 'reports', 'alerts', 'system', 'reminders'
        ]
        
        required_templates = [
            'base_email.html',
            'student/registration_confirmation.html',
            'student/attendance_alert.html',
            'student/payment_confirmation.html',
            'tutor/class_assignment.html',
            'tutor/payout_notification.html',
            'alerts/student_emergency_alert.html',
            'admin/monthly_finance_summary.html'
        ]
        
        missing_dirs = []
        missing_templates = []
        existing_templates = []
        
        # Check directories
        for directory in required_directories:
            dir_path = os.path.join(templates_path, directory)
            if not os.path.exists(dir_path):
                missing_dirs.append(directory)
        
        # Check templates
        for template in required_templates:
            template_path = os.path.join(templates_path, template)
            if os.path.exists(template_path):
                existing_templates.append(template)
            else:
                missing_templates.append(template)
        
        errors = []
        if missing_dirs:
            errors.extend([f"Missing template directory: {d}" for d in missing_dirs])
        if missing_templates:
            errors.extend([f"Missing template file: {t}" for t in missing_templates])
        
        return {
            'status': 'error' if errors else 'success',
            'existing_templates': len(existing_templates),
            'total_required': len(required_templates),
            'missing_directories': missing_dirs,
            'missing_templates': missing_templates,
            'errors': errors
        }
    
    def _validate_imports(self) -> Dict[str, Any]:
        """Validate that all imports work correctly"""
        import_tests = [
            ('comprehensive_email_service', 'from app.services.comprehensive_email_service import ComprehensiveEmailService'),
            ('tutor_email_service', 'from app.services.tutor_email_service import TutorEmailService'),
            ('coordinator_email_service', 'from app.services.coordinator_email_service import CoordinatorEmailService'),
            ('admin_email_service', 'from app.services.admin_email_service import AdminEmailService'),
            ('email_automation_service', 'from app.services.email_automation_service import EmailAutomationService'),
            ('system_notification_service', 'from app.services.system_notification_service import SystemNotificationService'),
            ('critical_alert_service', 'from app.services.critical_alert_service import CriticalAlertService'),
            ('email_error_handler', 'from app.services.email_error_handler import EmailErrorHandler')
        ]
        
        import_errors = []
        successful_imports = []
        
        for service_name, import_statement in import_tests:
            try:
                exec(import_statement)
                successful_imports.append(service_name)
            except ImportError as e:
                import_errors.append(f"{service_name}: {str(e)}")
            except Exception as e:
                import_errors.append(f"{service_name}: Unexpected error - {str(e)}")
        
        return {
            'status': 'error' if import_errors else 'success',
            'successful_imports': len(successful_imports),
            'total_tests': len(import_tests),
            'import_errors': import_errors,
            'errors': import_errors
        }
    
    def _validate_configuration(self) -> Dict[str, Any]:
        """Validate Flask-Mail configuration"""
        try:
            from app.services.email_error_handler import email_error_handler
            config_status = email_error_handler.check_mail_configuration()
            
            return {
                'status': 'error' if config_status['overall_status'] == 'error' else 'warning' if config_status['overall_status'] == 'incomplete' else 'success',
                'configuration': config_status,
                'errors': [f"Mail configuration error: {config_status.get('error', '')}"] if config_status['overall_status'] == 'error' else [],
                'warnings': [f"Incomplete mail configuration: {config_status.get('missing_settings', [])}"] if config_status['overall_status'] == 'incomplete' else []
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'errors': [f"Could not validate configuration: {str(e)}"]
            }
    
    def _validate_model_methods(self) -> Dict[str, Any]:
        """Validate that required model methods exist"""
        required_methods = {
            'Student': [
                'get_parent_details', 'get_subjects_enrolled', 'get_fee_structure',
                'get_balance_amount', 'get_attendance_percentage'
            ],
            'Tutor': [
                'get_subjects_taught', 'get_availability'
            ]
        }
        
        missing_methods = []
        existing_methods = []
        
        try:
            from app.models.student import Student
            from app.models.tutor import Tutor
            
            models = {'Student': Student, 'Tutor': Tutor}
            
            for model_name, methods in required_methods.items():
                model_class = models[model_name]
                for method_name in methods:
                    if hasattr(model_class, method_name):
                        existing_methods.append(f"{model_name}.{method_name}")
                    else:
                        missing_methods.append(f"{model_name}.{method_name}")
                        
        except ImportError as e:
            missing_methods.append(f"Could not import models: {str(e)}")
        
        return {
            'status': 'error' if missing_methods else 'success',
            'existing_methods': len(existing_methods),
            'missing_methods': missing_methods,
            'errors': [f"Missing model method: {method}" for method in missing_methods] if missing_methods else []
        }
    
    def _validate_error_handling(self) -> Dict[str, Any]:
        """Validate error handling mechanisms"""
        try:
            from app.services.email_error_handler import email_error_handler
            
            # Test email validation
            test_emails = ['valid@example.com', 'invalid-email', '', None, 'test@domain.com']
            valid_emails = email_error_handler.validate_email_recipients([e for e in test_emails if e])
            
            # Test context validation
            test_context = {'student': None, 'class': 'Test Class', 'date': datetime.now()}
            sanitized_context = email_error_handler.validate_email_context(test_context)
            
            return {
                'status': 'success',
                'email_validation_working': len(valid_emails) > 0,
                'context_sanitization_working': 'student' in sanitized_context,
                'error_handler_available': True
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'errors': [f"Error handler validation failed: {str(e)}"]
            }
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if results['overall_status'] == 'error':
            recommendations.append("CRITICAL: Resolve all errors before deploying email system")
            
        if results.get('validations', {}).get('configuration', {}).get('status') == 'warning':
            recommendations.append("Configure missing mail server settings for production use")
            
        if results.get('validations', {}).get('template_files', {}).get('missing_templates'):
            recommendations.append("Create missing email templates for complete functionality")
            
        if results['overall_status'] == 'success':
            recommendations.extend([
                "Email system validation passed - ready for integration",
                "Consider setting up email monitoring and analytics",
                "Test email sending in development environment",
                "Configure fallback recipients for error notifications"
            ])
        
        return recommendations
    
    def generate_validation_report(self) -> str:
        """Generate a comprehensive validation report"""
        results = self.validate_complete_system()
        
        report = f"""
# EMAIL SYSTEM VALIDATION REPORT
Generated: {results['timestamp']}
Overall Status: {results['overall_status'].upper()}

## VALIDATION RESULTS

"""
        
        for validation_name, validation_result in results['validations'].items():
            status_icon = "✅" if validation_result.get('status') == 'success' else "⚠️" if validation_result.get('status') == 'warning' else "❌"
            report += f"### {validation_name.replace('_', ' ').title()} {status_icon}\n"
            
            if validation_result.get('errors'):
                report += "**Errors:**\n"
                for error in validation_result['errors']:
                    report += f"- {error}\n"
                report += "\n"
            
            if validation_result.get('warnings'):
                report += "**Warnings:**\n"
                for warning in validation_result['warnings']:
                    report += f"- {warning}\n"
                report += "\n"
        
        if results['recommendations']:
            report += "## RECOMMENDATIONS\n\n"
            for recommendation in results['recommendations']:
                report += f"- {recommendation}\n"
        
        return report

# Global instance
email_validator = EmailSystemValidator()