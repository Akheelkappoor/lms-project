from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
from app.config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app)
    limiter.init_app(app)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.tutors import tutors_bp
    from app.routes.students import students_bp
    from app.routes.classes import classes_bp
    from app.routes.attendance import attendance_bp
    from app.routes.finance import finance_bp
    from app.routes.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(users_bp, url_prefix='/api/v1/users')
    app.register_blueprint(tutors_bp, url_prefix='/api/v1/tutors')
    app.register_blueprint(students_bp, url_prefix='/api/v1/students')
    app.register_blueprint(classes_bp, url_prefix='/api/v1/classes')
    app.register_blueprint(attendance_bp, url_prefix='/api/v1/attendance')
    app.register_blueprint(finance_bp, url_prefix='/api/v1/finance')
    app.register_blueprint(dashboard_bp, url_prefix='/api/v1/dashboard')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)