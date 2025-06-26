from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
from app.models import db
from datetime import datetime, timedelta
import redis
import uuid
import os

class AuthService:
    def __init__(self):
        self.redis_client = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
    
    def authenticate_user(self, username, password):
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return None, "Invalid credentials"
        
        if not user.is_active:
            return None, "Account is deactivated"
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return user, None
    
    def create_tokens(self, user):
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={
                'role': user.role,
                'department_id': user.department_id,
                'username': user.username
            }
        )
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return access_token, refresh_token
    
    def create_password_reset_token(self, email):
        user = User.query.filter_by(email=email).first()
        if not user:
            return None
        
        reset_token = str(uuid.uuid4())
        # Store in Redis with 1 hour expiration
        self.redis_client.setex(f"reset_token:{reset_token}", 3600, user.id)
        return reset_token
    
    def verify_reset_token(self, token):
        user_id = self.redis_client.get(f"reset_token:{token}")
        if user_id:
            return User.query.get(user_id.decode())
        return None
    
    def reset_password(self, token, new_password):
        user = self.verify_reset_token(token)
        if not user:
            return False
        
        user.set_password(new_password)
        db.session.commit()
        
        # Delete the token
        self.redis_client.delete(f"reset_token:{token}")
        return True