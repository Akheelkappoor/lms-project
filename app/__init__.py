from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
import os
from flask import render_template

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

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
    upload_dir = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    # Create subdirectories for different file types
    subdirs = ['documents', 'videos', 'images', 'profiles']
    for subdir in subdirs:
        path = os.path.join(upload_dir, subdir)
        if not os.path.exists(path):
            os.makedirs(path)

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

    from app.routes.finance import bp as finance_bp
    app.register_blueprint(finance_bp)

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
        if datetime_obj:
            return datetime_obj.strftime('%d %b %Y, %I:%M %p')
        return ''

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

    # Context processors
    @app.context_processor
    def inject_config():
        return {
            'APP_NAME': app.config['APP_NAME'],
            'COMPANY_NAME': app.config['COMPANY_NAME']
        }

    return app
