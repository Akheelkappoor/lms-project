import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AWS S3 Settings
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_REGION = os.environ.get('S3_REGION', 'ap-south-1')
    S3_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID')
    S3_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_URL = f"https://{os.environ.get('S3_BUCKET')}.s3.{os.environ.get('S3_REGION', 'ap-south-1')}.amazonaws.com"

    # S3 Upload Settings
    UPLOAD_FOLDER = 'lms'  # S3 logical folder
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024 * 1024))  # 5GB

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
    DEFAULT_ADMIN_EMAIL = 'care@i2global.co.in'
    DEFAULT_ADMIN_PASSWORD = 'i2global123'
    APP_NAME = 'I2Global LMS'
    COMPANY_NAME = 'I2Global Virtual Learning'
    COMPANY_ADDRESS = '48, 4th Block, Koramangala, Bengaluru, Karnataka 560034'
    COMPANY_PHONE = '+91 9600127000'
    COMPANY_EMAIL = 'care@i2global.co.in'
