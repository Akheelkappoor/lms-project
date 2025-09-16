from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
from flask import render_template
from datetime import datetime, timedelta
import json
from flask_moment import Moment
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
mail = Mail()
csrf = CSRFProtect()
moment = Moment()

def initialize_s3(app):
    """Initialize AWS S3 client with proper error handling"""
    try:
        # Check if all required S3 config is present
        required_config = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET']
        missing_config = [key for key in required_config if not app.config.get(key)]
        
        if missing_config:
            app.logger.warning(f"S3 configuration incomplete. Missing: {missing_config}")
            app.s3_client = None
            return False
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=app.config.get('AWS_REGION', 'ap-south-1')
        )
        
        # Test S3 connection
        try:
            s3_client.head_bucket(Bucket=app.config['S3_BUCKET'])
            app.s3_client = s3_client
            app.logger.info(f"S3 client initialized successfully for bucket: {app.config['S3_BUCKET']}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                app.logger.error(f"S3 bucket '{app.config['S3_BUCKET']}' does not exist")
            elif error_code == 'Forbidden':
                app.logger.error("S3 access denied. Check your AWS credentials and permissions.")
            else:
                app.logger.error(f"S3 connection test failed: {error_code}")
            app.s3_client = None
            return False
            
    except NoCredentialsError:
        app.logger.error("AWS credentials not found")
        app.s3_client = None
        return False
    except Exception as e:
        app.logger.error(f"Unexpected error initializing S3: {str(e)}")
        app.s3_client = None
        return False

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize S3
    s3_initialized = initialize_s3(app)
    if not s3_initialized:
        app.logger.warning("S3 features will be disabled")
    
    # Register error handlers for consistent error responses
    try:
        from app.services.error_service import register_error_handlers
        register_error_handlers(app)
    except ImportError:
        app.logger.warning("Error service not available, using basic error handlers")
        register_basic_error_handlers(app)
    
    login.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    moment.init_app(app)
    
    
    # Configure login (will be updated for fast login if available)
    login.login_view = 'auth.login'
    login.login_message = 'Please log in to access this page.'
    login.login_message_category = 'info'

    # 🚀 ACTIVATE ULTRA-PERFORMANCE SYSTEM
    try:
        from app.utils.performance_init import setup_ultra_performance_app
        app = setup_ultra_performance_app(app)
        # Keep using original beautiful login page
        # login.login_view = 'auth_fast.login_fast'
        app.logger.info("🚀 Ultra-Performance LMS System Activated!")
    except ImportError as e:
        app.logger.warning(f"⚠️  Performance optimization not available: {e}")
        app.logger.info("📝 Install performance modules for ultra-fast loading")
    except Exception as e:
        app.logger.error(f"❌ Performance initialization failed: {e}")

    # Register Blueprints
    register_blueprints(app)
    
    # Register template filters and context processors
    register_template_filters(app)
    register_context_processors(app)
    
    return app

def register_basic_error_handlers(app):
    """Register basic error handlers if error service is not available"""
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

def register_blueprints(app):
    """Register all application blueprints"""
    from app.routes.setup import bp as setup_bp
    app.register_blueprint(setup_bp)
    
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    try:
        from app.routes.tutor import bp as tutor_bp
        app.register_blueprint(tutor_bp, url_prefix='/tutor')
    except ImportError:
        app.logger.info("Tutor routes not available")

    try:
        from app.routes.student import bp as student_bp
        app.register_blueprint(student_bp, url_prefix='/student')
    except ImportError:
        app.logger.info("Student routes not available")

    try:
        from app.routes import demo
        app.register_blueprint(demo.bp, url_prefix='/demo')
    except ImportError:
        app.logger.info("Demo routes not available")
    
    try:
        from app.routes.timetable import bp as timetable_bp
        app.register_blueprint(timetable_bp, url_prefix='/admin')
    except ImportError:
        app.logger.info("Timetable routes not available")

    try:
        from app.routes.finance import bp as finance_bp
        app.register_blueprint(finance_bp)
    except ImportError:
        app.logger.info("Finance routes not available")

    try:
        from app.routes.profile import bp as profile_bp
        app.register_blueprint(profile_bp)
    except ImportError:
        app.logger.info("Profile routes not available")

    try:
        from app.routes.escalation import bp as escalation_bp
        app.register_blueprint(escalation_bp)
    except ImportError:
        app.logger.info("Escalation routes not available")
    
    try:
        from app.routes import reschedule
        app.register_blueprint(reschedule.bp, url_prefix='/reschedule')
    except ImportError:
        app.logger.info("Reschedule routes not available")
    
    # Optional routes - register if available
    try:
        from app.routes.lazy_loading_demo import lazy_demo_bp
        app.register_blueprint(lazy_demo_bp)
    except ImportError:
        pass
    
    try:
        from app.routes.export_email_timetable import bp as export_email_bp
        app.register_blueprint(export_email_bp, url_prefix='/admin')
    except ImportError:
        pass

    try:
        from app.routes import notice
        app.register_blueprint(notice.bp)
    except ImportError:
        pass
    
    # System Notifications Blueprint
    try:
        from app.routes import system_notifications
        app.register_blueprint(system_notifications.bp)
        app.logger.info("System notifications blueprint registered successfully")
    except ImportError:
        app.logger.warning("System notifications not available")
    
    # Health Check Blueprint
    try:
        from app.routes import health
        app.register_blueprint(health.bp)
        app.logger.info("Health check blueprint registered successfully")
    except ImportError:
        app.logger.warning("Health check not available")
    
    try:
        from app.routes.api_monitoring import bp as api_monitoring_bp
        app.register_blueprint(api_monitoring_bp)
    except ImportError:
        pass
    
    # Error monitoring blueprint (simplified version)
    try:
        from app.routes.simple_error_monitoring import bp as error_monitoring_bp
        app.register_blueprint(error_monitoring_bp)
    except ImportError:
        pass

def register_template_filters(app):
    """Register all template filters"""
    
    @app.template_filter('datetime')
    def datetime_filter(datetime_obj):
        if not datetime_obj:
            return ''
    
        if hasattr(datetime_obj, 'strftime'):
            return datetime_obj.strftime('%d %b %Y, %I:%M %p')

        if isinstance(datetime_obj, str):
            try:
                # Try parsing ISO format (from JSON timestamps)
                if 'T' in datetime_obj:
                    # Remove Z or timezone info and parse
                    clean_str = datetime_obj.replace('Z', '').split('.')[0]
                    parsed_dt = datetime.fromisoformat(clean_str)
                    return parsed_dt.strftime('%d %b %Y, %I:%M %p')
                else:
                    # Try standard datetime format
                    parsed_dt = datetime.strptime(datetime_obj, '%Y-%m-%d %H:%M:%S')
                    return parsed_dt.strftime('%d %b %Y, %I:%M %p')
            except (ValueError, AttributeError):
                # If can't parse, return original string
                return datetime_obj
        
        # Fallback - return as string
        return str(datetime_obj)

    @app.template_filter('date')
    def date_filter(date_obj):
        if date_obj:
            return date_obj.strftime('%d %b %Y')
        return ''

    @app.template_filter('dateformat')
    def dateformat_filter(date_obj, fmt='%d %b %Y'):
        if date_obj:
            return date_obj.strftime(fmt)
        return ''

    @app.template_filter('currency')
    def currency_filter(amount):
        if amount:
            return f"₹{amount:,.2f}"
        return "₹0.00"
    
    @app.template_filter('format_emp_id')
    def format_emp_id_filter(user_id):
        """Format user ID as employee ID"""
        if user_id:
            return f"EMP{user_id:04d}"  # e.g., EMP0001, EMP0023
        return "EMP0000"
    
    @app.template_filter('mask_account')
    def mask_account_filter(account_number):
        """Mask account number for security"""
        if not account_number or len(str(account_number)) < 4:
            return account_number or 'Not provided'
        account_str = str(account_number)
        visible_chars = 4
        return '*' * (len(account_str) - visible_chars) + account_str[-visible_chars:]
    
    @app.template_filter('nl2br')
    def nl2br_filter(value):
        """Convert newlines and <br> tags to proper HTML line breaks"""
        from markupsafe import Markup
        if not value:
            return value
        
        # First convert any literal <br> tags to newlines, then convert all newlines to <br>
        # This handles cases where users input <br> tags directly
        import re
        
        # Replace existing <br> tags (with or without closing slash) with newlines
        value = re.sub(r'<br\s*/?>', '\n', value, flags=re.IGNORECASE)
        
        # Convert newlines to <br> tags
        value = value.replace('\n', '<br>')
        
        # Preserve spaces by converting multiple spaces to &nbsp;
        value = re.sub(r'  +', lambda m: '&nbsp;' * len(m.group()), value)
        
        # Return as safe HTML so it doesn't get escaped
        return Markup(value)

    # Add other template filters here...
    @app.template_filter('safe_date')
    def safe_date(value):
        """Safely format date - returns empty string if None"""
        if value is None:
            return ''
        try:
            if isinstance(value, str):
                # Try to parse string to datetime
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return value.strftime('%B %d, %Y at %I:%M %p')
        except (ValueError, AttributeError):
            return str(value) if value else ''

    @app.template_filter('tojsonify')
    def tojsonify(obj):
        """Convert object to JSON string for use in templates"""
        def default_serializer(o):
            if hasattr(o, '__dict__'):
                # Convert SQLAlchemy objects to dict
                return {c.name: getattr(o, c.name) for c in o.__table__.columns}
            if hasattr(o, 'isoformat'):
                # Handle datetime objects
                return o.isoformat()
            return str(o)
        
        return json.dumps(obj, default=default_serializer, ensure_ascii=False)
    
    @app.template_global()
    def csrf_token():
        return generate_csrf()

def register_context_processors(app):
    """Register context processors"""
    @app.context_processor
    def inject_config():
        return {
            'APP_NAME': app.config.get('APP_NAME', 'LMS'),
            'COMPANY_NAME': app.config.get('COMPANY_NAME', 'Learning Management System'),
            'now': datetime.now
        }

# User loader for Flask-Login
@login.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))


