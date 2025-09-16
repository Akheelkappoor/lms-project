import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection pooling to optimize memory usage
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 300,  # Recycle connections every 5 minutes
        'pool_pre_ping': True,  # Verify connections before use
        'pool_timeout': 20
    }

    # AWS S3 Settings - Fixed variable names to match .env
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')  # Alternative key used by some routes
    S3_REGION = os.environ.get('S3_REGION', 'ap-south-1')
    S3_URL = os.environ.get('S3_URL')

    # S3 Upload Settings
    UPLOAD_FOLDER = 'lms'  # S3 logical folder
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024 * 1024))  # 5GB
    UPLOAD_TIMEOUT = int(os.environ.get('UPLOAD_TIMEOUT', 3600))  # 1 hour timeout for large uploads

    # Allowed Extensions
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'mp4', 'avi', 'mov'}

    # Email Settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['care@i2global.co.in']

    # Pagination & Session
    POSTS_PER_PAGE = 25
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Application Info
    DEFAULT_ADMIN_EMAIL = os.environ.get('DEFAULT_ADMIN_EMAIL')
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD')
    APP_NAME = os.environ.get('APP_NAME')
    COMPANY_NAME = os.environ.get('COMPANY_NAME')
    COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS')
    COMPANY_PHONE = os.environ.get('COMPANY_PHONE')
    COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL')
    
    # Timezone Configuration
    TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kolkata')  # Default to India timezone

class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = 'production'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}