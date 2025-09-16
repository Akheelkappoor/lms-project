# Enterprise-Grade Performance Cache System
import json
import time
import hashlib
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import current_app, request, g
from app import db
import threading
import pickle

class PerformanceCache:
    """High-performance caching system with multiple backend support"""
    
    def __init__(self):
        self.cache_dir = None
        self.redis_client = None
        self.memory_cache = {}
        self.cache_stats = {'hits': 0, 'misses': 0, 'sets': 0}
        self.initialized = False
    
    def init_cache(self):
        """Initialize cache backends"""
        if self.initialized:
            return
            
        try:
            # Check if we have app context
            try:
                app_context_available = current_app is not None
            except RuntimeError:
                app_context_available = False
            
            if not app_context_available:
                # Use default cache directory if no app context
                import tempfile
                self.cache_dir = os.path.join(tempfile.gettempdir(), 'lms_cache')
                os.makedirs(self.cache_dir, exist_ok=True)
                print(f"⚠️  No app context, using temp cache at {self.cache_dir}")
                self.initialized = True
                return
            
            # Try Redis first (best performance)
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=current_app.config.get('REDIS_HOST', 'localhost'),
                    port=current_app.config.get('REDIS_PORT', 6379),
                    db=current_app.config.get('REDIS_DB', 1),
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1
                )
                # Test connection
                self.redis_client.ping()
                print("✅ Redis cache initialized successfully")
            except:
                self.redis_client = None
                print("⚠️  Redis not available, using file cache")
            
            # File cache fallback
            if not self.redis_client:
                self.cache_dir = os.path.join(current_app.instance_path, 'cache')
                os.makedirs(self.cache_dir, exist_ok=True)
                print(f"✅ File cache initialized at {self.cache_dir}")
                
            self.initialized = True
                
        except Exception as e:
            print(f"❌ Cache initialization failed: {e}")
    
    def _generate_key(self, key_parts):
        """Generate cache key from parts"""
        if isinstance(key_parts, str):
            return f"lms:{key_parts}"
        
        key_string = ':'.join(str(part) for part in key_parts)
        return f"lms:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def get(self, key, default=None):
        """Get value from cache with multi-level fallback"""
        self.init_cache()
        cache_key = self._generate_key(key)
        
        try:
            # Level 1: Memory cache (fastest)
            if cache_key in self.memory_cache:
                cached_data = self.memory_cache[cache_key]
                if cached_data['expires'] > time.time():
                    self.cache_stats['hits'] += 1
                    return cached_data['data']
                else:
                    del self.memory_cache[cache_key]
            
            # Level 2: Redis cache (very fast)
            if self.redis_client:
                try:
                    cached = self.redis_client.get(cache_key)
                    if cached:
                        data = json.loads(cached)
                        # Store in memory for next time
                        self.memory_cache[cache_key] = {
                            'data': data,
                            'expires': time.time() + 60  # 1 minute in memory
                        }
                        self.cache_stats['hits'] += 1
                        return data
                except Exception as e:
                    print(f"Redis get error: {e}")
            
            # Level 3: File cache (slower but reliable)
            if self.cache_dir:
                try:
                    cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r') as f:
                            cached_data = json.load(f)
                            if cached_data['expires'] > time.time():
                                # Store in higher levels for next time
                                self._store_in_higher_levels(cache_key, cached_data['data'], cached_data['expires'] - time.time())
                                self.cache_stats['hits'] += 1
                                return cached_data['data']
                            else:
                                os.remove(cache_file)
                except Exception as e:
                    print(f"File cache get error: {e}")
            
            self.cache_stats['misses'] += 1
            return default
            
        except Exception as e:
            print(f"Cache get error: {e}")
            self.cache_stats['misses'] += 1
            return default
    
    def set(self, key, value, expiry=300):
        """Set value in cache with multi-level storage"""
        self.init_cache()
        cache_key = self._generate_key(key)
        expires_at = time.time() + expiry
        
        try:
            # Store in all available levels
            self._store_in_higher_levels(cache_key, value, expiry)
            self.cache_stats['sets'] += 1
            return True
            
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    def _store_in_higher_levels(self, cache_key, value, expiry):
        """Store data in all available cache levels"""
        # Memory cache
        self.memory_cache[cache_key] = {
            'data': value,
            'expires': time.time() + min(expiry, 300)  # Max 5 minutes in memory
        }
        
        # Redis cache
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, int(expiry), json.dumps(value))
            except Exception as e:
                print(f"Redis set error: {e}")
        
        # File cache
        if self.cache_dir:
            try:
                cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
                cache_data = {
                    'data': value,
                    'expires': time.time() + expiry,
                    'created': time.time()
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
            except Exception as e:
                print(f"File cache set error: {e}")
    
    def delete(self, key):
        """Delete from all cache levels"""
        self.init_cache()
        cache_key = self._generate_key(key)
        
        # Memory
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]
        
        # Redis
        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except:
                pass
        
        # File
        if self.cache_dir:
            try:
                cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            except:
                pass
    
    def clear_pattern(self, pattern):
        """Clear cache entries matching pattern"""
        pattern_key = self._generate_key(pattern)
        
        # Clear memory cache
        keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.memory_cache[key]
        
        # Clear Redis
        if self.redis_client:
            try:
                keys = self.redis_client.keys(f"*{pattern}*")
                if keys:
                    self.redis_client.delete(*keys)
            except:
                pass
        
        # Clear file cache
        if self.cache_dir:
            try:
                for filename in os.listdir(self.cache_dir):
                    if pattern in filename:
                        os.remove(os.path.join(self.cache_dir, filename))
            except:
                pass
    
    def get_stats(self):
        """Get cache performance statistics"""
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'sets': self.cache_stats['sets'],
            'hit_rate': round(hit_rate, 2),
            'memory_entries': len(self.memory_cache),
            'backends': {
                'redis': self.redis_client is not None,
                'file': self.cache_dir is not None,
                'memory': True
            }
        }

# Global cache instance
cache = PerformanceCache()

def cached(expiry=300, key_prefix='', invalidate_on_user=False):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            
            # Add user context if needed
            if invalidate_on_user:
                try:
                    from flask_login import current_user
                    if current_user and current_user.is_authenticated:
                        key_parts.append(f"user:{current_user.id}")
                except:
                    pass
            
            # Add function arguments to key
            if args:
                key_parts.extend([str(arg) for arg in args])
            if kwargs:
                key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
            
            cache_key = key_parts
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, expiry)
            return result
        
        return wrapper
    return decorator

def cache_dashboard_data(func):
    """Special decorator for dashboard data with smart invalidation"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Cache key based on current hour for automatic refresh
        current_hour = datetime.now().strftime('%Y-%m-%d-%H')
        cache_key = f"dashboard:{func.__name__}:{current_hour}"
        
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        result = func(*args, **kwargs)
        # Cache for 30 minutes max
        cache.set(cache_key, result, 1800)
        return result
    
    return wrapper

def warm_cache():
    """Pre-populate cache with commonly accessed data"""
    try:
        print("🔥 Warming up cache...")
        
        # Import here to avoid circular imports
        from app.routes.dashboard import get_dashboard_statistics
        from app.models.user import User
        from app.models.student import Student
        
        # Pre-cache dashboard statistics
        stats = get_dashboard_statistics()
        cache.set('dashboard:stats', stats, 600)  # 10 minutes
        
        # Pre-cache user counts
        user_count = User.query.filter_by(is_active=True).count()
        cache.set('users:active_count', user_count, 300)  # 5 minutes
        
        student_count = Student.query.filter_by(is_active=True).count()
        cache.set('students:active_count', student_count, 300)
        
        print("✅ Cache warmed successfully")
        
    except Exception as e:
        print(f"❌ Cache warming failed: {e}")

def clear_user_cache(user_id):
    """Clear cache entries for specific user"""
    cache.clear_pattern(f"user:{user_id}")

def clear_dashboard_cache():
    """Clear all dashboard-related cache"""
    cache.clear_pattern("dashboard")
    cache.clear_pattern("stats")

# Background cache warming
def setup_cache_warming(app):
    """Setup background cache warming"""
    def warm_cache_background():
        with app.app_context():
            warm_cache()
    
    # Warm cache every 10 minutes
    import threading
    import time
    
    def cache_warmer():
        while True:
            try:
                time.sleep(600)  # 10 minutes
                warm_cache_background()
            except Exception as e:
                print(f"Cache warmer error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    # Start background thread
    warming_thread = threading.Thread(target=cache_warmer, daemon=True)
    warming_thread.start()
    
    # Initial warm
    warm_cache_background()