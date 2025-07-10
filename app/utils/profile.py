"""
Profile utility functions for the LMS system
"""
import os
import secrets
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import json

def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def generate_unique_filename(original_filename):
    """Generate unique filename with timestamp and random string"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_string = secrets.token_hex(8)
    file_extension = secure_filename(original_filename).rsplit('.', 1)[1].lower()
    
    return f"{timestamp}_{random_string}.{file_extension}"

def save_profile_picture(file, user_id):
    """Save and resize profile picture"""
    if not file or not allowed_file(file.filename, {'jpg', 'jpeg', 'png', 'gif'}):
        return None
    
    # Generate unique filename
    filename = generate_unique_filename(file.filename)
    
    # Create upload path
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, filename)
    
    try:
        # Save and resize image
        image = Image.open(file)
        
        # Convert RGBA to RGB if necessary
        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Resize to 300x300 while maintaining aspect ratio
        image.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        # Create a square image with white background
        square_image = Image.new('RGB', (300, 300), (255, 255, 255))
        
        # Center the image
        x = (300 - image.width) // 2
        y = (300 - image.height) // 2
        square_image.paste(image, (x, y))
        
        # Save with optimization
        square_image.save(file_path, 'JPEG', quality=85, optimize=True)
        
        return filename
        
    except Exception as e:
        print(f"Error processing profile picture: {str(e)}")
        return None

def delete_old_profile_picture(filename):
    """Delete old profile picture file"""
    if not filename:
        return
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error deleting old profile picture: {str(e)}")

def save_document(file, document_type, user_id):
    """Save uploaded document with proper naming"""
    if not file or not allowed_file(file.filename):
        return None
    
    # Generate filename with document type
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    original_name = secure_filename(file.filename)
    file_extension = original_name.rsplit('.', 1)[1].lower()
    
    filename = f"{document_type}_{user_id}_{timestamp}.{file_extension}"
    
    # Create upload path
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, filename)
    
    try:
        file.save(file_path)
        return filename
    except Exception as e:
        print(f"Error saving document: {str(e)}")
        return None

def calculate_profile_completion(user):
    """Calculate profile completion percentage"""
    total_fields = 12
    completed_fields = 0
    
    # Basic information
    if user.full_name:
        completed_fields += 1
    if user.email:
        completed_fields += 1
    if user.phone:
        completed_fields += 1
    if user.address:
        completed_fields += 1
    
    # Profile details
    if user.profile_picture:
        completed_fields += 1
    if user.working_hours:
        completed_fields += 1
    if user.joining_date:
        completed_fields += 1
    if user.department_id:
        completed_fields += 1
    
    # Emergency contact
    emergency_contact = user.get_emergency_contact()
    if emergency_contact and emergency_contact.get('name'):
        completed_fields += 1
    
    # Role-specific fields
    if user.role == 'tutor':
        from app.models.tutor import Tutor
        tutor = Tutor.query.filter_by(user_id=user.id).first()
        if tutor:
            if tutor.qualification:
                completed_fields += 1
            if tutor.get_subjects():
                completed_fields += 1
            if tutor.get_bank_details():
                completed_fields += 1
    else:
        # For non-tutors, consider these fields as completed
        completed_fields += 3
    
    return int((completed_fields / total_fields) * 100)

def get_profile_completion_suggestions(user):
    """Get suggestions for completing profile"""
    suggestions = []
    
    if not user.phone:
        suggestions.append({
            'field': 'phone',
            'message': 'Add your phone number for SMS notifications',
            'url': 'profile.edit_profile',
            'priority': 'medium'
        })
    
    if not user.address:
        suggestions.append({
            'field': 'address',
            'message': 'Complete your address information',
            'url': 'profile.edit_profile',
            'priority': 'low'
        })
    
    if not user.profile_picture:
        suggestions.append({
            'field': 'profile_picture',
            'message': 'Upload a profile picture',
            'url': 'profile.edit_profile',
            'priority': 'medium'
        })
    
    emergency_contact = user.get_emergency_contact()
    if not emergency_contact or not emergency_contact.get('name'):
        suggestions.append({
            'field': 'emergency_contact',
            'message': 'Add an emergency contact',
            'url': 'profile.edit_profile',
            'priority': 'high'
        })
    
    if user.role == 'tutor':
        from app.models.tutor import Tutor
        tutor = Tutor.query.filter_by(user_id=user.id).first()
        if tutor:
            if not tutor.get_bank_details():
                suggestions.append({
                    'field': 'banking',
                    'message': 'Add banking details for salary payments',
                    'url': 'profile.banking_details',
                    'priority': 'high'
                })
            
            if not tutor.get_subjects():
                suggestions.append({
                    'field': 'subjects',
                    'message': 'Update your teaching subjects',
                    'url': 'profile.edit_profile',
                    'priority': 'high'
                })
    
    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    suggestions.sort(key=lambda x: priority_order.get(x['priority'], 3))
    
    return suggestions

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def get_file_info(file_path):
    """Get file information including size and modification date"""
    if not os.path.exists(file_path):
        return None
    
    stat = os.stat(file_path)
    
    return {
        'size': stat.st_size,
        'size_formatted': format_file_size(stat.st_size),
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'created': datetime.fromtimestamp(stat.st_ctime)
    }

def validate_ifsc_code(ifsc_code):
    """Validate Indian IFSC code format"""
    import re
    
    ifsc_pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
    return bool(re.match(ifsc_pattern, ifsc_code.upper()))

def validate_phone_number(phone):
    """Validate Indian phone number"""
    import re
    
    # Remove any spaces, dashes, or parentheses
    phone_clean = re.sub(r'[\s\-\(\)\+]', '', phone)
    
    # Check for Indian mobile number patterns
    patterns = [
        r'^[6-9]\d{9}$',  # 10 digit starting with 6-9
        r'^91[6-9]\d{9}$',  # 12 digit with country code
        r'^0[6-9]\d{9}$'  # 11 digit with leading 0
    ]
    
    return any(re.match(pattern, phone_clean) for pattern in patterns)

def generate_username_suggestions(full_name, email=None):
    """Generate username suggestions based on full name"""
    if not full_name:
        return []
    
    # Clean and split name
    name_parts = [part.lower().strip() for part in full_name.split() if part.strip()]
    
    if not name_parts:
        return []
    
    suggestions = []
    
    # First name + last name
    if len(name_parts) >= 2:
        suggestions.append(name_parts[0] + name_parts[-1])
        suggestions.append(name_parts[0] + '.' + name_parts[-1])
        suggestions.append(name_parts[0] + '_' + name_parts[-1])
    
    # First name + numbers
    suggestions.append(name_parts[0] + '123')
    suggestions.append(name_parts[0] + '2024')
    
    # Email-based suggestions
    if email and '@' in email:
        email_part = email.split('@')[0].lower()
        suggestions.append(email_part)
    
    # Full name concatenated
    full_name_clean = ''.join(name_parts)
    if len(full_name_clean) <= 20:
        suggestions.append(full_name_clean)
    
    # Remove duplicates and return first 5
    unique_suggestions = list(dict.fromkeys(suggestions))
    return unique_suggestions[:5]

def mask_sensitive_data(data, mask_char='*'):
    """Mask sensitive data like account numbers"""
    if not data or len(data) < 4:
        return data
    
    visible_chars = 4
    return mask_char * (len(data) - visible_chars) + data[-visible_chars:]

def get_document_icon_class(filename):
    """Get CSS class for document icon based on file extension"""
    if not filename:
        return 'fas fa-file'
    
    extension = filename.split('.')[-1].lower()
    
    icon_map = {
        'pdf': 'fas fa-file-pdf text-danger',
        'doc': 'fas fa-file-word text-primary',
        'docx': 'fas fa-file-word text-primary',
        'xls': 'fas fa-file-excel text-success',
        'xlsx': 'fas fa-file-excel text-success',
        'ppt': 'fas fa-file-powerpoint text-warning',
        'pptx': 'fas fa-file-powerpoint text-warning',
        'jpg': 'fas fa-file-image text-info',
        'jpeg': 'fas fa-file-image text-info',
        'png': 'fas fa-file-image text-info',
        'gif': 'fas fa-file-image text-info',
        'zip': 'fas fa-file-archive text-secondary',
        'rar': 'fas fa-file-archive text-secondary',
        'txt': 'fas fa-file-alt text-muted',
        'csv': 'fas fa-file-csv text-success'
    }
    
    return icon_map.get(extension, 'fas fa-file text-muted')

def create_user_activity_log(user_id, action, details=None):
    """Create activity log entry for user actions"""
    # This would typically save to a separate ActivityLog table
    # For now, just return the log entry data
    
    return {
        'user_id': user_id,
        'action': action,
        'details': details or {},
        'timestamp': datetime.utcnow(),
        'ip_address': None,  # Would get from request in real implementation
        'user_agent': None   # Would get from request in real implementation
    }

def get_notification_preferences(user):
    """Get user notification preferences with defaults"""
    # This would typically come from a UserPreferences table
    # For now, return default preferences
    
    defaults = {
        'email_notifications': True,
        'sms_notifications': bool(user.phone),
        'class_reminders': True,
        'attendance_alerts': True,
        'schedule_changes': True,
        'assignment_updates': False,
        'payment_notifications': user.role == 'tutor',
        'earnings_summary': user.role == 'tutor',
        'system_updates': True,
        'security_alerts': True,
        'policy_updates': False,
        'promotional_updates': False,
        'notification_frequency': 'daily',
        'quiet_hours': {
            'start': '22:00',
            'end': '07:00'
        }
    }
    
    return defaults