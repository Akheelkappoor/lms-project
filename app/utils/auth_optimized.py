# Auth optimization utilities
from flask import current_app
from app.models.user import User
from .performance_cache import cache
import logging

logger = logging.getLogger(__name__)

def warm_auth_cache():
    """Pre-warm authentication cache with active users"""
    try:
        if not current_app:
            logger.warning("No application context for auth cache warming")
            return
            
        # Get most active users (those who logged in recently)
        active_users = User.query.filter(
            User.is_active == True,
            User.last_login.isnot(None)
        ).order_by(User.last_login.desc()).limit(100).all()
        
        cached_count = 0
        for user in active_users:
            try:
                # Cache user data as serializable dictionary
                user_dict = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active,
                    'department_id': user.department_id,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
                cache.set(f"user:by_id:{user.id}", user_dict, 3600)
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
                
                cached_count += 1
            except Exception as e:
                logger.error(f"Error caching user {user.id}: {e}")
                continue
        
        logger.info(f"Auth cache warmed: {cached_count} users cached")
        
    except Exception as e:
        logger.error(f"Auth cache warming failed: {e}")