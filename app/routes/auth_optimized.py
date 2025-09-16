# Ultra-Fast Authentication System
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse as url_parse
from app import db
from app.models.user import User
from app.forms.auth import LoginForm
from app.utils.performance_cache import cache, cached
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

bp = Blueprint('auth_fast', __name__)

def measure_auth_performance(func_name):
    """Decorator to measure authentication performance"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
                end_time = time.time()
                duration = round((end_time - start_time) * 1000, 2)  # milliseconds
                
                if duration > 50:  # Log if > 50ms
                    logger.warning(f"⚡ {func_name} took {duration}ms")
                else:
                    logger.info(f"✅ {func_name} took {duration}ms")
                
                return result
            except Exception as e:
                end_time = time.time()
                duration = round((end_time - start_time) * 1000, 2)
                logger.error(f"❌ {func_name} failed after {duration}ms: {e}")
                raise
        return wrapper
    return decorator

@bp.route('/login-fast', methods=['GET', 'POST'])
@measure_auth_performance('Fast Login')
def login_fast():
    """Ultra-fast login with minimal database queries"""
    start_time = time.time()
    
    # Instant redirect for authenticated users (no DB query)
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.admin_dashboard'))
    
    form = LoginForm()
    
    if request.method == 'GET':
        # Instant GET response with minimal template
        load_time = round((time.time() - start_time) * 1000, 2)
        logger.info(f"🚀 Login page loaded in {load_time}ms")
        return render_template('auth/login_fast.html', form=form, load_time=load_time)
    
    # POST request handling
    if form.validate_on_submit():
        username_or_email = form.username.data.strip().lower()
        password = form.password.data
        
        # Try cache first for frequent users
        cache_key = f"user:login:{username_or_email}"
        cached_user_data = cache.get(cache_key)
        
        user = None
        if cached_user_data:
            # Get user by ID (fastest query)
            user = User.query.get(cached_user_data['id'])
            if user and (user.username.lower() != username_or_email and user.email.lower() != username_or_email):
                user = None  # Cache mismatch, need fresh lookup
        
        if not user:
            # Database lookup with optimized query
            user = User.query.filter(
                db.or_(
                    db.func.lower(User.username) == username_or_email,
                    db.func.lower(User.email) == username_or_email
                ),
                User.is_active == True  # Only active users
            ).first()
            
            # Cache user data for next login (1 hour)
            if user:
                cache.set(cache_key, {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }, 3600)
        
        # Authentication checks
        if not user:
            # Minimal error tracking (no heavy ErrorTracker)
            logger.warning(f"Login attempt with non-existent user: {username_or_email}")
            flash('Invalid username/email or password', 'error')
            return render_template('auth/login_fast.html', form=form)
        
        if not user.check_password(password):
            # Invalid password - clear cache to prevent brute force
            cache.delete(cache_key)
            logger.warning(f"Invalid password attempt for user: {user.username}")
            flash('Invalid username/email or password', 'error')
            return render_template('auth/login_fast.html', form=form)
        
        if not user.is_active:
            logger.warning(f"Login attempt on deactivated account: {user.username}")
            flash('Your account has been deactivated. Please contact administrator.', 'error')
            return render_template('auth/login_fast.html', form=form)
        
        # Successful login
        login_user(user, remember=form.remember_me.data)
        
        # Update last login asynchronously (don't block response)
        try:
            user.last_login = db.func.now()
            db.session.commit()
        except:
            # Don't fail login if last_login update fails
            db.session.rollback()
        
        # Cache user session data
        cache.set(f"user:session:{user.id}", {
            'username': user.username,
            'role': user.role,
            'full_name': user.full_name
        }, 3600)
        
        # Log successful login (minimal)
        logger.info(f"User {user.username} logged in successfully")
        
        # Fast redirect to dashboard
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            # Redirect based on role
            if user.role in ['superadmin', 'admin', 'coordinator']:
                next_page = url_for('dashboard.admin_dashboard')
            else:
                next_page = url_for('dashboard.index')
        
        total_time = round((time.time() - start_time) * 1000, 2)
        logger.info(f"🚀 Login completed in {total_time}ms")
        
        return redirect(next_page)
    
    # Form validation failed
    return render_template('auth/login_fast.html', form=form)

@bp.route('/logout-fast')
@login_required
@measure_auth_performance('Fast Logout')
def logout_fast():
    """Ultra-fast logout"""
    if current_user.is_authenticated:
        # Clear user cache
        cache.delete(f"user:session:{current_user.id}")
        cache.delete(f"user:login:{current_user.username.lower()}")
        cache.delete(f"user:login:{current_user.email.lower()}")
        
        logout_user()
        logger.info("User logged out successfully")
    
    return redirect(url_for('auth_fast.login_fast'))

@bp.route('/api/check-auth')
@measure_auth_performance('Auth Check API')
def api_check_auth():
    """Fast authentication check API"""
    if current_user.is_authenticated:
        # Try cache first
        cached_data = cache.get(f"user:session:{current_user.id}")
        if cached_data:
            return jsonify({
                'authenticated': True,
                'user': cached_data,
                'cached': True
            })
        
        # Fresh data
        user_data = {
            'username': current_user.username,
            'role': current_user.role,
            'full_name': current_user.full_name,
            'id': current_user.id
        }
        
        # Cache for future requests
        cache.set(f"user:session:{current_user.id}", user_data, 3600)
        
        return jsonify({
            'authenticated': True,
            'user': user_data,
            'cached': False
        })
    
    return jsonify({'authenticated': False})

@bp.route('/api/login-performance')
@login_required
@measure_auth_performance('Login Performance API')
def api_login_performance():
    """Get login system performance metrics"""
    if current_user.role not in ['superadmin', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get cache statistics
        cache_stats = cache.get_stats()
        
        # Get recent login performance
        recent_logins = cache.get('auth:recent_performance', [])
        
        return jsonify({
            'success': True,
            'cache_performance': cache_stats,
            'recent_login_times': recent_logins[-10:],  # Last 10 logins
            'optimizations': {
                'user_caching': True,
                'session_caching': True,
                'minimal_queries': True,
                'async_updates': True
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Utility functions for authentication optimization

@cached(expiry=3600, key_prefix='user:by_id')
def get_user_by_id(user_id):
    """Cached user lookup by ID"""
    return User.query.get(user_id)

@cached(expiry=1800, key_prefix='user:by_email') 
def get_user_by_email(email):
    """Cached user lookup by email"""
    return User.query.filter_by(email=email.lower(), is_active=True).first()

@cached(expiry=1800, key_prefix='user:by_username')
def get_user_by_username(username):
    """Cached user lookup by username"""
    return User.query.filter_by(username=username.lower(), is_active=True).first()

def clear_user_auth_cache(user_id, username=None, email=None):
    """Clear all authentication-related cache for a user"""
    cache.delete(f"user:session:{user_id}")
    cache.delete(f"user:by_id:{user_id}")
    
    if username:
        cache.delete(f"user:login:{username.lower()}")
        cache.delete(f"user:by_username:{username.lower()}")
    
    if email:
        cache.delete(f"user:login:{email.lower()}")
        cache.delete(f"user:by_email:{email.lower()}")

def warm_auth_cache():
    """Pre-warm authentication cache with active users"""
    try:
        # Get most active users (those who logged in recently)
        active_users = User.query.filter(
            User.is_active == True,
            User.last_login.isnot(None)
        ).order_by(User.last_login.desc()).limit(100).all()
        
        for user in active_users:
            # Cache user data
            cache.set(f"user:by_id:{user.id}", user, 3600)
            cache.set(f"user:login:{user.username.lower()}", {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }, 1800)
            
            if user.email:
                cache.set(f"user:login:{user.email.lower()}", {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }, 1800)
        
        logger.info(f"✅ Auth cache warmed for {len(active_users)} users")
        
    except Exception as e:
        logger.error(f"Auth cache warming failed: {e}")

# Background task to track login performance
def track_login_performance(login_time_ms):
    """Track login performance for monitoring"""
    try:
        recent_times = cache.get('auth:recent_performance', [])
        recent_times.append({
            'timestamp': time.time(),
            'duration': login_time_ms
        })
        
        # Keep only last 50 entries
        if len(recent_times) > 50:
            recent_times = recent_times[-50:]
        
        cache.set('auth:recent_performance', recent_times, 3600)
        
    except Exception as e:
        logger.error(f"Login performance tracking failed: {e}")