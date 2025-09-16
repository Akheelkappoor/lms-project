"""
Database Service Layer for centralized query operations
Provides reusable database operations with optimizations
"""
from app import db
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta


class DatabaseService:
    """Centralized database operations service"""
    
    @staticmethod
    def get_optimized_query(model_class, includes=None, filters=None):
        """
        Get optimized query with eager loading
        
        Args:
            model_class: SQLAlchemy model class
            includes: List of relationships to eager load
            filters: Dictionary of filters to apply
        
        Returns:
            Optimized SQLAlchemy query
        """
        query = model_class.query
        
        # Add eager loading
        if includes:
            for include in includes:
                if hasattr(model_class, include):
                    query = query.options(joinedload(getattr(model_class, include)))
        
        # Add filters
        if filters:
            for field, value in filters.items():
                if hasattr(model_class, field):
                    if isinstance(value, list):
                        query = query.filter(getattr(model_class, field).in_(value))
                    else:
                        query = query.filter(getattr(model_class, field) == value)
        
        return query
    
    @staticmethod
    def paginate_query(query, page=1, per_page=20):
        """
        Paginate query results with metadata
        
        Args:
            query: SQLAlchemy query object
            page: Page number (1-based)
            per_page: Items per page
        
        Returns:
            Dictionary with items and pagination info
        """
        paginated = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return {
            'items': paginated.items,
            'pagination': {
                'page': paginated.page,
                'pages': paginated.pages,
                'per_page': paginated.per_page,
                'total': paginated.total,
                'has_next': paginated.has_next,
                'has_prev': paginated.has_prev,
                'next_num': paginated.next_num,
                'prev_num': paginated.prev_num
            }
        }
    
    @staticmethod
    def bulk_insert(model_class, data_list):
        """
        Efficient bulk insert operation
        
        Args:
            model_class: SQLAlchemy model class
            data_list: List of dictionaries with model data
        
        Returns:
            Number of inserted records
        """
        try:
            db.session.bulk_insert_mappings(model_class, data_list)
            db.session.commit()
            return len(data_list)
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def bulk_update(model_class, data_list, update_fields):
        """
        Efficient bulk update operation
        
        Args:
            model_class: SQLAlchemy model class
            data_list: List of dictionaries with id and updated data
            update_fields: List of fields to update
        
        Returns:
            Number of updated records
        """
        try:
            # Filter data to only include specified fields + id
            filtered_data = []
            for item in data_list:
                filtered_item = {'id': item['id']}
                for field in update_fields:
                    if field in item:
                        filtered_item[field] = item[field]
                filtered_data.append(filtered_item)
            
            db.session.bulk_update_mappings(model_class, filtered_data)
            db.session.commit()
            return len(filtered_data)
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def get_dashboard_stats(model_class, user_filter=None, date_field='created_at', days=30):
        """
        Generic dashboard statistics generator
        
        Args:
            model_class: SQLAlchemy model class
            user_filter: Filter function for user-specific data
            date_field: Field to use for date filtering
            days: Number of days to include in stats
        
        Returns:
            Dictionary with statistics
        """
        query = model_class.query
        
        if user_filter:
            query = user_filter(query)
        
        # Date range for recent stats
        start_date = datetime.now() - timedelta(days=days)
        date_column = getattr(model_class, date_field)
        
        stats = {
            'total': query.count(),
            'recent': query.filter(date_column >= start_date).count(),
            'today': query.filter(
                func.date(date_column) == datetime.now().date()
            ).count()
        }
        
        # Add status-based counts if model has status field
        if hasattr(model_class, 'status'):
            # Handle Attendance model which has status as @property, use final_status column instead
            if model_class.__name__ == 'Attendance' and hasattr(model_class, 'final_status'):
                status_column = model_class.final_status
                column_name = 'final_status'
            else:
                status_column = model_class.status
                column_name = 'status'
                
            status_query = query.with_entities(
                status_column,
                func.count(model_class.id).label('count')
            ).group_by(status_column)
            
            stats['by_status'] = {
                getattr(row, column_name): row.count for row in status_query.all()
            }
        
        # Add active/inactive counts if model has is_active field
        if hasattr(model_class, 'is_active'):
            stats['active'] = query.filter_by(is_active=True).count()
            stats['inactive'] = query.filter_by(is_active=False).count()
        
        return stats
    
    @staticmethod
    def search_across_fields(model_class, search_term, search_fields):
        """
        Search across multiple text fields
        
        Args:
            model_class: SQLAlchemy model class
            search_term: Term to search for
            search_fields: List of field names to search in
        
        Returns:
            SQLAlchemy query with search filters
        """
        query = model_class.query
        
        if not search_term or not search_fields:
            return query
        
        search_conditions = []
        search_term = f"%{search_term}%"
        
        for field in search_fields:
            if hasattr(model_class, field):
                search_conditions.append(
                    getattr(model_class, field).ilike(search_term)
                )
        
        if search_conditions:
            query = query.filter(or_(*search_conditions))
        
        return query
    
    @staticmethod
    def get_related_count(model_instance, relationship_name):
        """
        Get count of related objects without loading them
        
        Args:
            model_instance: SQLAlchemy model instance
            relationship_name: Name of the relationship
        
        Returns:
            Count of related objects
        """
        if hasattr(model_instance, relationship_name):
            relationship = getattr(model_instance, relationship_name)
            return relationship.count() if hasattr(relationship, 'count') else len(relationship)
        return 0
    
    @staticmethod
    def safe_delete(model_instance, check_relationships=None):
        """
        Safely delete a model instance with relationship checks
        
        Args:
            model_instance: SQLAlchemy model instance to delete
            check_relationships: List of relationship names to check for dependencies
        
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            # Check for dependencies
            if check_relationships:
                for rel_name in check_relationships:
                    count = DatabaseService.get_related_count(model_instance, rel_name)
                    if count > 0:
                        return False, f"Cannot delete: {count} related {rel_name} exist"
            
            # Perform soft delete if model supports it
            if hasattr(model_instance, 'is_active'):
                model_instance.is_active = False
                db.session.commit()
                return True, "Record deactivated successfully"
            else:
                # Hard delete
                db.session.delete(model_instance)
                db.session.commit()
                return True, "Record deleted successfully"
                
        except Exception as e:
            db.session.rollback()
            return False, f"Delete failed: {str(e)}"


class CacheService:
    """Simple in-memory cache service for database results"""
    
    _cache = {}
    _cache_timestamps = {}
    
    @classmethod
    def get(cls, key, default=None):
        """Get cached value"""
        if key in cls._cache:
            # Check if cache is still valid (5 minutes)
            if datetime.now() - cls._cache_timestamps[key] < timedelta(minutes=5):
                return cls._cache[key]
            else:
                # Cache expired
                cls.invalidate(key)
        return default
    
    @classmethod
    def set(cls, key, value):
        """Set cached value"""
        cls._cache[key] = value
        cls._cache_timestamps[key] = datetime.now()
    
    @classmethod
    def invalidate(cls, key):
        """Invalidate specific cache key"""
        cls._cache.pop(key, None)
        cls._cache_timestamps.pop(key, None)
    
    @classmethod
    def clear(cls):
        """Clear all cached values"""
        cls._cache.clear()
        cls._cache_timestamps.clear()