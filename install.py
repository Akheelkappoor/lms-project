#!/usr/bin/env python3
"""
Installation script for I2Global LMS
This script sets up the virtual environment and installs dependencies
"""

import os
import sys
import subprocess
import platform

def run_command(command, description):
    """Run a system command with error handling"""
    print(f"🔄 {description}...")
    try:
        if platform.system() == "Windows":
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(command.split(), check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False

def create_env_file():
    """Create .env file with default settings"""
    env_content = """# Flask Configuration
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=development

# Database Configuration
DATABASE_URL=sqlite:///app.db

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=

# Application Settings
APP_NAME=I2Global LMS
COMPANY_NAME=I2Global Virtual Learning
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ .env file created")
    else:
        print("📋 .env file already exists")

def main():
    """Main installation function"""
    print("🚀 I2Global LMS Installation Script")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version.split()[0]} detected")
    
    # Create virtual environment
    venv_command = "python -m venv venv"
    if not run_command(venv_command, "Creating virtual environment"):
        sys.exit(1)
    
    # Activate virtual environment and install dependencies
    if platform.system() == "Windows":
        activate_command = "venv\\Scripts\\activate && pip install -r requirements.txt"
    else:
        activate_command = "source venv/bin/activate && pip install -r requirements.txt"
    
    if not run_command(activate_command, "Installing dependencies"):
        print("❌ Failed to install dependencies. Make sure requirements.txt exists.")
        sys.exit(1)
    
    # Create .env file
    create_env_file()
    
    # Create necessary directories
    directories = [
        'app/static/uploads',
        'app/static/uploads/documents',
        'app/static/uploads/videos',
        'app/static/uploads/images',
        'app/static/uploads/profiles'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    print("✅ Directory structure created")
    
    print("\n🎉 Installation completed successfully!")
    print("=" * 40)
    print("Next steps:")
    print("1. Activate virtual environment:")
    
    if platform.system() == "Windows":
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    
    print("2. Run the application:")
    print("   python run.py")
    print("3. Visit http://localhost:5001/setup to complete setup")
    print("=" * 40)

if __name__ == '__main__':
    main()