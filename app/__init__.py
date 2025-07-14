from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
from flask import render_template
from datetime import datetime


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

    return app
