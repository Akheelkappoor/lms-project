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


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    print("=== S3 CONFIG DEBUG ===")
    print(f"S3_BUCKET: {app.config.get('S3_BUCKET')}")
    print(f"S3_REGION: {app.config.get('S3_REGION')}")
    print(f"S3_ACCESS_KEY: {app.config.get('S3_ACCESS_KEY')}")
    print(f"S3_SECRET_KEY: {app.config.get('S3_SECRET_KEY')}")
    print("========================")

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    
    # Configure login
    login.login_view = 'auth.login'
    login.login_message = 'Please log in to access this page.'
    login.login_message_category = 'info'

    # Create upload directories
    # upload_dir = app.config['UPLOAD_FOLDER']
    # if not os.path.exists(upload_dir):
    #     os.makedirs(upload_dir)
        
    # # Create subdirectories for different file types
    # subdirs = ['documents', 'videos', 'images', 'profiles']
    # for subdir in subdirs:
    #     path = os.path.join(upload_dir, subdir)
    #     if not os.path.exists(path):
    #         os.makedirs(path)

    # Register Blueprints
    from app.routes.setup import bp as setup_bp
    app.register_blueprint(setup_bp)
    
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.routes.tutor import bp as tutor_bp
    app.register_blueprint(tutor_bp, url_prefix='/tutor')

    from app.routes.student import bp as student_bp
    app.register_blueprint(student_bp, url_prefix='/student')

    from app.routes import demo
    app.register_blueprint(demo.bp, url_prefix='/demo')

    from app.routes.finance import bp as finance_bp
    app.register_blueprint(finance_bp)

    from app.routes.profile import bp as profile_bp
    app.register_blueprint(profile_bp)

    from app.routes.escalation import bp as escalation_bp
    app.register_blueprint(escalation_bp)

    # Notice Management System Blueprint
    from app.routes import notice
    app.register_blueprint(notice.bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Template filters
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
        """Convert newlines to <br> tags"""
        if not value:
            return value
        return value.replace('\n', '<br>')

    # Notice Management System Template Filters
    @app.template_filter('dateformat')
    def dateformat_filter(datetime_obj, format='%b %d, %H:%M'):
        """Custom date formatter for notice system (similar to moment.js)"""
        if not datetime_obj:
            return ''
        
        # Handle datetime objects
        if hasattr(datetime_obj, 'strftime'):
            return datetime_obj.strftime(format)
        
        # Handle string representations
        if isinstance(datetime_obj, str):
            try:
                # Try parsing ISO format with timezone
                if 'T' in datetime_obj:
                    # Handle various ISO formats
                    clean_str = datetime_obj.replace('Z', '').split('+')[0].split('.')[0]
                    if len(clean_str) == 19:  # YYYY-MM-DDTHH:MM:SS
                        parsed_dt = datetime.strptime(clean_str, '%Y-%m-%dT%H:%M:%S')
                    else:
                        parsed_dt = datetime.fromisoformat(clean_str)
                    return parsed_dt.strftime(format)
                # Handle standard datetime format
                elif ' ' in datetime_obj and ':' in datetime_obj:
                    try:
                        parsed_dt = datetime.strptime(datetime_obj, '%Y-%m-%d %H:%M:%S')
                        return parsed_dt.strftime(format)
                    except ValueError:
                        # Try with microseconds
                        parsed_dt = datetime.strptime(datetime_obj.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        return parsed_dt.strftime(format)
                # Handle date only
                elif '-' in datetime_obj:
                    parsed_dt = datetime.strptime(datetime_obj, '%Y-%m-%d')
                    return parsed_dt.strftime(format)
            except (ValueError, AttributeError):
                # If all parsing fails, return the original string
                return datetime_obj
        
        return str(datetime_obj)

    @app.template_filter('timeago') 
    def timeago_filter(datetime_obj):
        """Simple time ago filter for notice system"""
        if not datetime_obj:
            return ''
        
        if isinstance(datetime_obj, str):
            try:
                if 'T' in datetime_obj:
                    clean_str = datetime_obj.replace('Z', '').split('.')[0]
                    datetime_obj = datetime.fromisoformat(clean_str)
                else:
                    datetime_obj = datetime.strptime(datetime_obj, '%Y-%m-%d %H:%M:%S')
            except (ValueError, AttributeError):
                return datetime_obj
        
        if not hasattr(datetime_obj, 'strftime'):
            return str(datetime_obj)
            
        now = datetime.utcnow()
        diff = now - datetime_obj
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    @app.template_filter('safe_date')
    def safe_date_filter(datetime_obj):
        """Safe date formatter that handles any input type"""
        if not datetime_obj:
            return 'Not available'
        
        # Handle datetime objects
        if hasattr(datetime_obj, 'strftime'):
            return datetime_obj.strftime('%b %d, %H:%M')
        
        # Handle strings - try to parse and format, or return as-is
        if isinstance(datetime_obj, str):
            try:
                # Common parsing attempts
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        clean_str = datetime_obj.replace('Z', '').split('+')[0].split('.')[0]
                        parsed_dt = datetime.strptime(clean_str, fmt)
                        return parsed_dt.strftime('%b %d, %H:%M')
                    except ValueError:
                        continue
                # If no format works, return the string as-is
                return datetime_obj
            except:
                return datetime_obj
        
        return str(datetime_obj)

    @app.template_filter('notice_status')
    def notice_status_filter(notice):
        """Get notice status for display"""
        if not notice:
            return 'Unknown'
            
        if not notice.is_published:
            return 'Draft'
        elif notice.expiry_date and notice.expiry_date < datetime.utcnow():
            return 'Expired'
        else:
            return 'Published'

    @app.template_filter('notice_priority_class')
    def notice_priority_class_filter(priority):
        """Get CSS class for notice priority"""
        priority_classes = {
            'urgent': 'badge-danger',
            'high': 'badge-warning', 
            'normal': 'badge-secondary'
        }
        return priority_classes.get(priority, 'badge-secondary')

    @app.template_filter('notice_category_class')
    def notice_category_class_filter(category):
        """Get CSS class for notice category"""
        category_classes = {
            'academic': 'badge-info',
            'administrative': 'badge-secondary',
            'emergency': 'badge-danger',
            'celebration': 'badge-success'
        }
        return category_classes.get(category, 'badge-secondary')

    @app.template_global()
    def hasattr_filter(obj, name):
        return hasattr(obj, name)

    @app.template_global()
    def csrf_token():
        return generate_csrf()

    # Context processors
    @app.context_processor
    def inject_config():
        return {
            'APP_NAME': app.config['APP_NAME'],
            'COMPANY_NAME': app.config['COMPANY_NAME']
        }

    # Notice system context processor
    @app.context_processor
    def inject_notice_context():
        """Inject notice-related context for all templates"""
        context = {}
        
        # Only inject notice data if user is authenticated
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                from app.services.notice_service import NoticeService
                
                # Get unread notice count
                unread_count = NoticeService.get_unread_count(current_user.id)
                pending_acknowledgments = NoticeService.get_pending_acknowledgments_count(current_user.id)
                
                context.update({
                    'unread_notices_count': unread_count,
                    'pending_acknowledgments_count': pending_acknowledgments
                })
        except Exception:
            # If there's any error (e.g., during setup), just return empty context
            pass
            
        return context

    return app