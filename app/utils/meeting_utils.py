# app/utils/meeting_utils.py

import uuid
from datetime import datetime, timedelta
import requests
import json
from flask import current_app

def generate_meeting_link(platform='zoom'):
    """Generate meeting link for demo classes"""
    if platform == 'zoom':
        return create_zoom_meeting()
    elif platform == 'google_meet':
        return create_google_meet()
    elif platform == 'teams':
        return create_teams_meeting()
    else:
        # Default/fallback meeting
        return create_default_meeting()

def create_zoom_meeting(topic="Demo Class", duration=60):
    """Create Zoom meeting using Zoom API"""
    try:
        # Zoom API credentials (configure in your app config)
        zoom_api_key = current_app.config.get('ZOOM_API_KEY')
        zoom_api_secret = current_app.config.get('ZOOM_API_SECRET')
        zoom_user_email = current_app.config.get('ZOOM_USER_EMAIL')
        
        if not all([zoom_api_key, zoom_api_secret, zoom_user_email]):
            return create_default_meeting()
        
        # Create JWT token for Zoom API
        import jwt
        
        payload = {
            'iss': zoom_api_key,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, zoom_api_secret, algorithm='HS256')
        
        # Zoom API endpoint
        url = f"https://api.zoom.us/v2/users/{zoom_user_email}/meetings"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Meeting settings
        meeting_data = {
            'topic': topic,
            'type': 2,  # Scheduled meeting
            'duration': duration,
            'password': generate_meeting_password(),
            'settings': {
                'host_video': True,
                'participant_video': True,
                'join_before_host': False,
                'mute_upon_entry': True,
                'waiting_room': True,
                'auto_recording': 'cloud'
            }
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(meeting_data))
        
        if response.status_code == 201:
            meeting_info = response.json()
            return {
                'platform': 'zoom',
                'join_url': meeting_info['join_url'],
                'meeting_id': meeting_info['id'],
                'password': meeting_info['password'],
                'start_url': meeting_info['start_url']
            }
        else:
            print(f"Zoom API Error: {response.status_code} - {response.text}")
            return create_default_meeting()
            
    except Exception as e:
        print(f"Error creating Zoom meeting: {str(e)}")
        return create_default_meeting()

def create_google_meet():
    """Create Google Meet link"""
    try:
        # For Google Meet, you would use Google Calendar API
        # For now, return a placeholder that opens Google Meet
        meeting_id = str(uuid.uuid4())[:10]
        
        return {
            'platform': 'google_meet',
            'join_url': f"https://meet.google.com/{meeting_id}",
            'meeting_id': meeting_id,
            'password': None,
            'start_url': f"https://meet.google.com/{meeting_id}"
        }
        
    except Exception as e:
        print(f"Error creating Google Meet: {str(e)}")
        return create_default_meeting()

def create_teams_meeting():
    """Create Microsoft Teams meeting"""
    try:
        # For Teams, you would use Microsoft Graph API
        # For now, return a placeholder
        meeting_id = str(uuid.uuid4())[:10]
        
        return {
            'platform': 'teams',
            'join_url': f"https://teams.microsoft.com/l/meetup-join/{meeting_id}",
            'meeting_id': meeting_id,
            'password': generate_meeting_password(),
            'start_url': f"https://teams.microsoft.com/l/meetup-join/{meeting_id}"
        }
        
    except Exception as e:
        print(f"Error creating Teams meeting: {str(e)}")
        return create_default_meeting()

def create_default_meeting():
    """Create a default meeting link when APIs are not available"""
    meeting_id = str(uuid.uuid4())[:10]
    password = generate_meeting_password()
    
    return {
        'platform': 'default',
        'join_url': f"https://your-lms-domain.com/demo/join/{meeting_id}",
        'meeting_id': meeting_id,
        'password': password,
        'start_url': f"https://your-lms-domain.com/demo/start/{meeting_id}"
    }

def generate_meeting_password(length=6):
    """Generate random meeting password"""
    import random
    import string
    
    characters = string.digits + string.ascii_uppercase
    return ''.join(random.choice(characters) for _ in range(length))

def validate_meeting_link(link):
    """Validate if a meeting link is valid"""
    if not link:
        return False
    
    valid_domains = [
        'zoom.us',
        'meet.google.com',
        'teams.microsoft.com',
        'your-lms-domain.com'  # Your own domain
    ]
    
    for domain in valid_domains:
        if domain in link:
            return True
    
    return False

def get_meeting_platform_from_link(link):
    """Determine meeting platform from link"""
    if 'zoom.us' in link:
        return 'zoom'
    elif 'meet.google.com' in link:
        return 'google_meet'
    elif 'teams.microsoft.com' in link:
        return 'teams'
    else:
        return 'other'

def format_meeting_info(meeting_data):
    """Format meeting information for display"""
    if not meeting_data:
        return {}
    
    platform_names = {
        'zoom': 'Zoom',
        'google_meet': 'Google Meet',
        'teams': 'Microsoft Teams',
        'default': 'Video Call'
    }
    
    return {
        'platform_name': platform_names.get(meeting_data.get('platform'), 'Video Call'),
        'join_url': meeting_data.get('join_url'),
        'meeting_id': meeting_data.get('meeting_id'),
        'password': meeting_data.get('password'),
        'start_url': meeting_data.get('start_url')
    }