from app import create_app, db
from app.models import User, Department, Tutor, Student, Class, Attendance
from flask import url_for, redirect, request, jsonify, render_template

# Create Flask application instance
app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Department': Department, 
        'Tutor': Tutor, 
        'Student': Student, 
        'Class': Class, 
        'Attendance': Attendance
    }

@app.route('/')
def index():
    """Main index route - redirect based on setup status"""
    with app.app_context():
        try:
            # Check if system needs setup
            if not User.query.filter_by(role='superadmin').first():
                return redirect(url_for('setup.initial_setup'))
            else:
                return redirect(url_for('auth.login'))
        except Exception as e:
            # Database tables don't exist, redirect to setup
            print(f"Database not ready: {str(e)}")
            return redirect(url_for('setup.initial_setup'))

# ============ ADDITIONAL ERROR HANDLERS ============
# Note: 404 and 500 are already handled in app/__init__.py with your templates

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle Request Entity Too Large error (5GB limit)"""
    if request.is_json:
        return jsonify({
            'error': 'File too large',
            'message': 'The uploaded file exceeds the maximum size limit (5GB)',
            'max_size': '5GB',
            'max_bytes': app.config.get('MAX_CONTENT_LENGTH', 5368709120)
        }), 413
    
    # Use same styling as your error templates
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>File Too Large - I2Global LMS</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; background: #f8f9fa; }
            .error-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
            .error-content { max-width: 500px; padding: 60px 40px; background: white; border-radius: 24px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); text-align: center; }
            .error-icon { font-size: 80px; color: #F1A150; margin-bottom: 20px; }
            .error-code { font-size: 120px; font-weight: 800; background: linear-gradient(45deg, #F1A150, #C86706); background-clip: text; -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1; margin-bottom: 20px; }
            .error-title { font-size: 32px; font-weight: 600; color: #333; margin-bottom: 16px; }
            .error-message { color: #666; margin-bottom: 30px; font-size: 18px; line-height: 1.6; }
            .btn { display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; border-radius: 12px; font-weight: 500; text-decoration: none; background: linear-gradient(45deg, #F1A150, #C86706); color: white; }
            .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(200, 103, 6, 0.2); }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-content">
                <div class="error-icon">📁</div>
                <h1 class="error-code">413</h1>
                <h2 class="error-title">File Too Large</h2>
                <p class="error-message">The uploaded file exceeds the maximum size limit of <strong>5GB</strong>.<br>Please select a smaller file or compress your content.</p>
                <a href="javascript:history.back()" class="btn">Go Back</a>
            </div>
        </div>
    </body>
    </html>
    ''', 413

@app.errorhandler(408)
def request_timeout(error):
    """Handle request timeout for large uploads"""
    return jsonify({
        'error': 'Upload timeout',
        'message': 'The upload took too long to complete. Please try again.',
        'suggestion': 'Check your internet connection and try uploading a smaller file.'
    }), 408

@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors using your existing template"""
    db.session.rollback()
    if request.is_json:
        return jsonify({
            'error': 'Internal server error',
            'message': 'Something went wrong on our end.'
        }), 500
    
    # Use your existing 500.html template
    from flask import render_template
    try:
        return render_template('errors/500.html'), 500
    except:
        # Fallback if template fails
        return '''
        <html>
        <head><title>Server Error - I2Global LMS</title></head>
        <body>
            <h1>Server Error</h1>
            <p>Something went wrong. Please try again later.</p>
            <p><a href="javascript:history.back()">Go Back</a></p>
        </body>
        </html>
        ''', 500

def initialize_database():
    """Initialize database tables if needed"""
    with app.app_context():
        try:
            # Test if tables exist by making a simple query
            User.query.first()
            print("✅ Database tables already exist")
        except Exception as e:
            print(f"⚠️  Creating database tables: {str(e)}")
            try:
                db.create_all()
                print("✅ Database tables created successfully")
            except Exception as create_error:
                print(f"❌ Error creating tables: {str(create_error)}")

def display_config_info():
    """Display important configuration information"""
    max_size_gb = app.config.get('MAX_CONTENT_LENGTH', 5368709120) / (1024**3)
    upload_folder = app.config.get('UPLOAD_FOLDER')
    
    print("=" * 60)
    print("🚀 I2Global LMS - Configuration")
    print("=" * 60)
    print(f"📁 Upload Limit: {max_size_gb:.1f}GB")
    print(f"📂 Upload Folder: {upload_folder}")
    print(f"🗄️  Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'SQLite')[:50]}...")
    print(f"🐛 Debug Mode: {app.config.get('DEBUG', False)}")
    print(f"🔐 Secret Key: {'Set' if app.config.get('SECRET_KEY') else 'Not Set'}")
    print("=" * 60)

if __name__ == '__main__':
    print("🚀 Starting I2Global LMS...")
    
    # Display configuration
    display_config_info()
    
    print("📊 Checking database...")
    # Initialize database tables if needed
    initialize_database()
    
    print("🌐 Server starting on http://0.0.0.0:5001")
    print("⏳ Large file uploads (up to 5GB) supported")
    print("🔄 Press Ctrl+C to stop the server")
    
    