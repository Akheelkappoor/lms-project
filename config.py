import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File Upload Settings
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'mp4', 'avi', 'mov'}
    
    # Email Settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['admin@i2global.co.in']
    
    # Pagination
    POSTS_PER_PAGE = 25
    
    # Session Settings
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # Default Admin Settings
    DEFAULT_ADMIN_EMAIL = 'admin@i2global.co.in'
    DEFAULT_ADMIN_PASSWORD = 'admin123'
    
    # Application Settings
    APP_NAME = 'I2Global LMS'
    COMPANY_NAME = 'I2Global Virtual Learning'
    COMPANY_ADDRESS = '48, 4th Block, Koramangala, Bengaluru, Karnataka 560034'
    COMPANY_PHONE = '+91 9600127000'
    COMPANY_EMAIL = 'care@i2global.co.in'