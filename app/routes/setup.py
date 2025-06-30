from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user
from app import db
from app.models.user import User
from app.models.department import Department
from app.forms.auth import SetupForm
from datetime import datetime

bp = Blueprint('setup', __name__)

@bp.route('/setup', methods=['GET', 'POST'])
def initial_setup():
    """Initial setup page for creating superadmin"""
    
    # Check for force setup parameter
    force_setup = request.args.get('force') == 'true'
    
    try:
        # Check if setup is already completed (unless forced)
        if not force_setup and User.query.filter_by(role='superadmin').first():
            flash('Setup already completed. Please login.', 'info')
            return redirect(url_for('auth.login'))
    except Exception as e:
        # Database might not exist yet, continue with setup
        print(f"Database check failed: {e}, continuing with setup...")
        pass
    
    form = SetupForm()
    
    if form.validate_on_submit():
        try:
            # Create all tables if they don't exist
            db.create_all()
            
            # Create default departments
            Department.create_default_departments()
            
            # Create superadmin user
            superadmin = User(
                username=form.username.data,
                email=form.email.data,
                full_name=form.full_name.data,
                phone=form.phone.data,
                role='superadmin',
                is_active=True,
                is_verified=True,
                joining_date=datetime.utcnow().date()
            )
            superadmin.set_password(form.password.data)
            
            db.session.add(superadmin)
            db.session.commit()
            
            # Auto login the superadmin
            login_user(superadmin)
            superadmin.update_last_login()
            
            flash('Setup completed successfully! Welcome to your LMS.', 'success')
            return redirect(url_for('dashboard.admin_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Setup failed: {str(e)}', 'error')
    
    return render_template('setup/initial_setup.html', form=form)

@bp.route('/reset-setup', methods=['POST'])
def reset_setup():
    """Reset the system for fresh setup (Development only)"""
    
    # Only allow in development mode
    if not current_app.debug:
        flash('Reset not allowed in production mode.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Drop and recreate all tables
        db.drop_all()
        db.create_all()
        
        flash('System reset successfully. Please run initial setup.', 'success')
        return redirect(url_for('setup.initial_setup'))
        
    except Exception as e:
        flash(f'Reset failed: {str(e)}', 'error')
        return redirect(url_for('auth.login'))