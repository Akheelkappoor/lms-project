"""
Timezone utilities for consistent time handling across the application
"""
from datetime import datetime
import pytz
from flask import current_app


def get_local_time():
    """
    Get current time in the configured timezone
    Returns naive datetime for database compatibility
    """
    try:
        timezone_name = current_app.config.get('TIMEZONE', 'Asia/Kolkata')
        local_tz = pytz.timezone(timezone_name)
        utc_time = datetime.now(pytz.UTC)
        local_time = utc_time.astimezone(local_tz).replace(tzinfo=None)
        
        # DEBUG: Log timezone calculation
        print(f"DEBUG - Timezone calculation:")
        print(f"  Configured timezone: {timezone_name}")
        print(f"  UTC time: {utc_time}")
        print(f"  Local time: {local_time}")
        print(f"  System time: {datetime.now()}")
        
        return local_time
    except Exception as e:
        print(f"DEBUG - Timezone error: {e}")
        # Fallback to system time if timezone fails
        return datetime.now()


def calculate_time_until(target_datetime):
    """
    Calculate time in minutes until target datetime
    Handles timezone issues and caps unrealistic values
    """
    if not target_datetime:
        return 0
    
    current_time = get_local_time()
    
    # If target_datetime is naive, assume it's in local timezone
    if isinstance(target_datetime, datetime):
        time_diff_seconds = (target_datetime - current_time).total_seconds()
    else:
        # Handle date + time combination
        return 0
    
    time_until_minutes = max(0, int(time_diff_seconds / 60))
    
    # DEBUG: Log time calculation
    print(f"DEBUG - calculate_time_until:")
    print(f"  Target datetime: {target_datetime}")
    print(f"  Current time: {current_time}")
    print(f"  Time diff seconds: {time_diff_seconds}")
    print(f"  Time until minutes: {time_until_minutes}")
    
    # Cap extremely large values (likely timezone issues)
    if time_until_minutes > 1440:  # More than 24 hours
        print(f"  WARNING: Large time difference detected, returning 0")
        return 0  # Assume the time has passed or there's a timezone issue
    
    return time_until_minutes


def is_time_reached(target_datetime, minutes_before=5):
    """
    Check if current time is within 'minutes_before' of target datetime
    """
    if not target_datetime:
        return False
        
    current_time = get_local_time()
    
    # Create target datetime if it's not already
    if hasattr(target_datetime, 'date') and hasattr(target_datetime, 'time'):
        # It's already a datetime
        check_time = target_datetime
    else:
        # Assume it's a date object, need to combine with time
        return False
    
    # Check if we're within the specified minutes before the target time
    from datetime import timedelta
    time_threshold = check_time - timedelta(minutes=minutes_before)
    return current_time >= time_threshold


def format_time_remaining(minutes):
    """
    Format time remaining in a human-readable way
    """
    if minutes <= 0:
        return "Time reached"
    elif minutes < 60:
        return f"{minutes}m"
    elif minutes < 1440:  # Less than 24 hours
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}m"
    else:
        days = minutes // 1440
        return f"{days}d"