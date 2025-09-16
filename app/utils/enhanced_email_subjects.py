# app/utils/enhanced_email_subjects.py

from datetime import datetime, date
import json

def generate_enhanced_email_subject(period, period_name, recipient, relevant_classes, target_date):
    """
    Generate enhanced, personalized email subjects
    
    Args:
        period: 'single', 'week', 'month', 'year'
        period_name: Generated period name (e.g., "July 2025")
        recipient: {'type': 'tutor/student', 'name': 'John Doe', 'email': '...'}
        relevant_classes: List of classes for this recipient
        target_date: Date object
    
    Returns:
        Enhanced subject string
    """
    
    class_count = len(relevant_classes)
    recipient_type = recipient.get('type', 'user')
    first_name = recipient.get('name', '').split()[0] if recipient.get('name') else 'there'
    
    # Time context
    now = datetime.now()
    is_today = target_date == now.date() if isinstance(target_date, date) else False
    is_tomorrow = target_date == (now.date().replace(day=now.day + 1)) if isinstance(target_date, date) else False
    
    # DAILY SUBJECTS
    if period == 'single':
        if class_count == 0:
            return f"📅 No classes scheduled for {period_name}"
        
        # Urgency-based subjects for today/tomorrow
        if is_today:
            if recipient_type == 'tutor':
                if class_count == 1:
                    return f"🔔 {first_name}, you have 1 class TODAY!"
                else:
                    return f"🔔 {first_name}, you have {class_count} classes TODAY!"
            else:  # student
                if class_count == 1:
                    return f"📚 {first_name}, your class is TODAY!"
                else:
                    return f"📚 {first_name}, you have {class_count} classes TODAY!"
        
        elif is_tomorrow:
            if recipient_type == 'tutor':
                return f"⏰ Tomorrow's Teaching Schedule - {class_count} class{'es' if class_count != 1 else ''}"
            else:
                return f"⏰ Tomorrow's Classes - {class_count} session{'s' if class_count != 1 else ''}"
        
        else:
            # Regular daily subjects
            if recipient_type == 'tutor':
                return f"👨‍🏫 Teaching Schedule for {period_name} ({class_count} class{'es' if class_count != 1 else ''})"
            else:
                return f"🎓 Class Schedule for {period_name} ({class_count} session{'s' if class_count != 1 else ''})"
    
    # WEEKLY SUBJECTS
    elif period == 'week':
        week_start = target_date.strftime('%b %d')
        
        if class_count == 0:
            return f"📅 No classes this week ({week_start})"
        
        if recipient_type == 'tutor':
            return f"📋 Weekly Teaching Plan - {class_count} classes starting {week_start}"
        else:
            return f"📅 Your Week Ahead - {class_count} classes starting {week_start}"
    
    # MONTHLY SUBJECTS  
    elif period == 'month':
        month_name = target_date.strftime('%B %Y')
        
        if class_count == 0:
            return f"📅 No classes scheduled for {month_name}"
        
        # Different subjects based on class volume
        if class_count <= 5:
            intensity = "Light"
            emoji = "😊"
        elif class_count <= 15:
            intensity = "Busy"
            emoji = "💪"
        else:
            intensity = "Super Busy"
            emoji = "🚀"
        
        if recipient_type == 'tutor':
            return f"{emoji} {intensity} {month_name} - {class_count} classes to teach"
        else:
            return f"{emoji} {intensity} {month_name} - {class_count} classes ahead"
    
    # YEARLY SUBJECTS
    elif period == 'year':
        year = target_date.year if hasattr(target_date, 'year') else datetime.now().year
        
        if class_count == 0:
            return f"📅 No classes scheduled for {year}"
        
        # Academic year context
        if class_count <= 50:
            return f"📚 Your {year} Academic Journey - {class_count} classes"
        elif class_count <= 150:
            return f"🎯 Complete {year} Schedule - {class_count} classes planned"
        else:
            return f"🏆 Intensive {year} Program - {class_count} classes ahead!"
    
    # FALLBACK (should not reach here)
    return f"📅 Your Schedule for {period_name}"


def generate_personalized_greeting_subject(recipient, period, class_count):
    """Generate personalized greeting-style subjects"""
    
    first_name = recipient.get('name', '').split()[0] if recipient.get('name') else ''
    recipient_type = recipient.get('type', 'user')
    
    # Time-based greetings
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
        emoji = "🌅"
    elif hour < 17:
        greeting = "Good afternoon" 
        emoji = "☀️"
    else:
        greeting = "Good evening"
        emoji = "🌆"
    
    if period == 'single':  # Daily
        if recipient_type == 'tutor':
            return f"{emoji} {greeting} {first_name}! Today's teaching lineup ({class_count} classes)"
        else:
            return f"{emoji} {greeting} {first_name}! Your classes today ({class_count} sessions)"
    
    elif period == 'week':  # Weekly
        return f"🗓️ {first_name}'s Weekly Planner - {class_count} upcoming classes"
    
    elif period == 'month':  # Monthly
        return f"📋 {first_name}'s Monthly Overview - {class_count} classes ahead"
    
    else:  # Yearly
        return f"📈 {first_name}'s Annual Schedule - {class_count} classes total"


def generate_smart_subject_with_context(period, recipient, relevant_classes, target_date, period_name):
    """
    Generate smart subjects with contextual information
    """
    
    class_count = len(relevant_classes)
    recipient_type = recipient.get('type', 'user')
    
    # Analyze class patterns
    subjects_taught = list(set([cls.subject for cls in relevant_classes if hasattr(cls, 'subject')]))
    subject_variety = len(subjects_taught)
    
    # Get most common subject
    most_common_subject = ""
    if subjects_taught:
        subject_counts = {}
        for cls in relevant_classes:
            if hasattr(cls, 'subject'):
                subject_counts[cls.subject] = subject_counts.get(cls.subject, 0) + 1
        if subject_counts:
            most_common_subject = max(subject_counts, key=subject_counts.get)
    
    # CONTEXT-AWARE SUBJECTS
    if period == 'single':
        # Single subject day
        if subject_variety == 1 and most_common_subject:
            if class_count == 1:
                return f"📖 {most_common_subject} class on {period_name}"
            else:
                return f"📖 {class_count} {most_common_subject} classes on {period_name}"
        
        # Multiple subjects
        elif subject_variety > 1:
            return f"🎯 Mixed schedule: {subject_variety} subjects, {class_count} classes on {period_name}"
        
        # No specific subject info
        else:
            return f"📅 {class_count} classes scheduled for {period_name}"
    
    elif period == 'week':
        return f"📊 Weekly Breakdown: {class_count} classes across {subject_variety} subjects"
    
    elif period == 'month':
        if recipient_type == 'tutor':
            return f"👨‍🏫 {period_name} Teaching Load: {class_count} classes, {subject_variety} subjects"
        else:
            return f"🎓 {period_name} Learning Path: {class_count} classes in {subject_variety} subjects"
    
    else:  # year
        return f"📚 {period_name} Academic Plan: {class_count} total classes"


# USAGE EXAMPLES AND INTEGRATION

def get_enhanced_subject_options(period, period_name, recipient, relevant_classes, target_date):
    """
    Get multiple subject options to choose from
    """
    
    options = {
        'standard': generate_enhanced_email_subject(period, period_name, recipient, relevant_classes, target_date),
        'personal': generate_personalized_greeting_subject(recipient, period, len(relevant_classes)),
        'contextual': generate_smart_subject_with_context(period, recipient, relevant_classes, target_date, period_name),
        'simple': f"📅 {recipient.get('name', '').split()[0] if recipient.get('name') else 'Your'} Schedule - {period_name}"
    }
    
    return options


# INTEGRATION FUNCTION FOR YOUR EXISTING CODE
def create_better_email_subject(period, period_name, recipient, relevant_classes, target_date, style='standard'):
    """
    Main function to integrate with your existing email system
    
    Usage in your send_email function:
    subject = create_better_email_subject(period, period_name, recipient, relevant_classes, target_date)
    """
    
    if style == 'standard':
        return generate_enhanced_email_subject(period, period_name, recipient, relevant_classes, target_date)
    elif style == 'personal':
        return generate_personalized_greeting_subject(recipient, period, len(relevant_classes))
    elif style == 'contextual':
        return generate_smart_subject_with_context(period, recipient, relevant_classes, target_date, period_name)
    else:
        # Fallback to current system
        return f"Your Timetable for {period_name}"