from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse as url_parse
from app import db
from app.models.user import User
from app.forms.auth import LoginForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm
from app.utils.email import send_password_reset_email
from werkzeug.security import check_password_hash
try:
    from app.utils.error_tracker import ErrorTracker, track_errors, track_login_attempts
    from app.utils.alert_system import send_error_alert
except ImportError:
    # Fallback to simple tracker
    from app.utils.simple_error_tracker import ErrorTracker, simple_track_errors as track_errors
    track_login_attempts = track_errors
    def send_error_alert(error_log):
        pass  # Skip alerts if not available


bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
@track_login_attempts
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username_or_email = form.username.data
        password = form.password.data
        
        # Check if username or email (case-insensitive)
        user = User.query.filter(
            (User.username.ilike(username_or_email)) | 
            (User.email.ilike(username_or_email))
        ).first()
        
        # Log authentication attempt
        if user is None:
            # User not found
            error_log = ErrorTracker.capture_error(
                error_type='login_error',
                error_message=f'Login attempt with non-existent user: {username_or_email}',
                error_category='authentication',
                severity='medium',
                action_attempted='login'
            )
            send_error_alert(error_log)
            flash('Invalid username/email or password', 'error')
            return redirect(url_for('auth.login'))
        
        if not user.check_password(password):
            # Invalid password
            error_log = ErrorTracker.capture_error(
                error_type='login_error',
                error_message=f'Invalid password attempt for user: {user.username}',
                error_category='authentication',
                severity='medium',
                user_id=user.id,
                user_role=user.role,
                action_attempted='login'
            )
            send_error_alert(error_log)
            flash('Invalid username/email or password', 'error')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            # Account deactivated
            error_log = ErrorTracker.capture_error(
                error_type='login_error',
                error_message=f'Login attempt on deactivated account: {user.username}',
                error_category='authentication',
                severity='high',
                user_id=user.id,
                user_role=user.role,
                action_attempted='login'
            )
            send_error_alert(error_log)
            flash('Your account has been deactivated. Please contact administrator.', 'error')
            return redirect(url_for('auth.login'))
        
        # Successful login
        login_user(user, remember=form.remember_me.data)
        user.update_last_login()
        
        # Log successful login
        ErrorTracker.capture_error(
            error_type='successful_login',
            error_message=f'User {user.username} logged in successfully',
            error_category='authentication',
            severity='low',
            user_id=user.id,
            user_role=user.role,
            action_attempted='login'
        )
        
        # Redirect to appropriate dashboard based on role
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            if user.role in ['superadmin', 'admin', 'coordinator']:
                next_page = url_for('dashboard.admin_dashboard')
            elif user.role == 'tutor':
                next_page = url_for('dashboard.tutor_dashboard')
            else:
                next_page = url_for('dashboard.index')
        
        flash(f'Welcome back, {user.full_name}!', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    user_name = current_user.full_name
    logout_user()
    flash(f'Goodbye {user_name}! You have been logged out successfully.', 'info')
    return redirect(url_for('dashboard.index'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter(User.email.ilike(form.email.data)).first()
        if user:
            token = user.get_reset_password_token()
            send_password_reset_email(user, token)
        
        flash('If an account exists with this email, you will receive password reset instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    user = User.verify_reset_password_token(token)
    if not user:
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset successfully.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password for logged-in users"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html', form=form)
        
        # Set new password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been changed successfully.', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/change_password.html', form=form)