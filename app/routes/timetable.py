# app/routes/timetable.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os
import json  # IMPORTANT: At top level
from flask_wtf.csrf import generate_csrf
from app import db
from app.models.user import User
from app.models.department import Department  
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from functools import wraps
from sqlalchemy import or_, and_, func, text
from sqlalchemy.orm import joinedload

from app.utils.advanced_permissions import (
    require_permission, 
    require_any_permission, 
    require_all_permissions,
    require_role,
    PermissionRegistry,
    PermissionUtils
)

# Import admin_required from admin module
from app.routes.admin import admin_required

# IMPORTANT: Changed blueprint name to 'timetable'
bp = Blueprint('timetable', __name__)

# ============ MAIN TIMETABLE PAGE ============

@bp.route('/timetable')
@login_required
@require_permission('class_management')
def timetable():
    """Timetable management page"""
    try:
        # Get departments, tutors, and students for the dropdowns
        departments = Department.query.filter_by(is_active=True).all()
        
        # Get ALL tutors with their user relationships (including inactive)
        tutors = Tutor.query.join(User).filter(
            User.is_active == True  # Only filter by user being active, include all tutor statuses
        ).all()
        
        # Get active students (limit to prevent slow loading)
        students = Student.query.filter(
            Student.is_active == True
        ).limit(100).all()
        
        return render_template('admin/timetable.html', 
                             departments=departments,
                             tutors=tutors,
                             students=students)
                             
    except Exception as e:
        print(f"Error loading timetable page: {str(e)}")
        flash('Error loading timetable page', 'error')
        return redirect(url_for('dashboard.index'))

# ============ TUTOR CALENDAR VIEW ============

@bp.route('/tutor/<int:tutor_id>/calendar')
@login_required
@require_permission('class_management')
def tutor_calendar_view(tutor_id):
    """Individual tutor calendar view - looks exactly like my_timetable.html"""
    try:
        # Get the specific tutor with user relationship
        tutor = Tutor.query.options(db.joinedload(Tutor.user)).filter_by(id=tutor_id).first()
        
        if not tutor:
            flash('Tutor not found', 'error')
            return redirect(url_for('timetable.timetable'))
        
        # Get tutor details
        tutor_name = tutor.user.full_name if tutor.user else 'Unknown Tutor'
        tutor_email = tutor.user.email if tutor.user else None
        tutor_status = tutor.status or 'pending'
        
        # Get students for the "Add Class" form
        students = Student.query.filter(
            Student.is_active == True
        ).limit(100).all()
        
        return render_template('admin/tutor_calendar_view.html',
                             tutor_id=tutor_id,
                             tutor_name=tutor_name,
                             tutor_email=tutor_email,
                             tutor_status=tutor_status,
                             students=students)
                             
    except Exception as e:
        print(f"Error loading tutor calendar view: {str(e)}")
        flash('Error loading tutor calendar view', 'error')
        return redirect(url_for('timetable.timetable'))

# ============ TUTOR CALENDAR API ENDPOINTS ============

@bp.route('/api/tutor/<int:tutor_id>/weekly-timetable')
@login_required
@require_permission('class_management')
def api_tutor_weekly_timetable(tutor_id):
    """API: Get weekly timetable data for specific tutor"""
    try:
        week_offset = request.args.get('week_offset', 0, type=int)
        
        # Calculate week start date
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)
        
        # Get tutor
        tutor = Tutor.query.filter_by(id=tutor_id).first()
        if not tutor:
            return jsonify({'success': False, 'error': 'Tutor not found'})
        
        # Generate week dates
        week_dates = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            week_dates.append({
                'date': current_date.isoformat(),
                'day': current_date.strftime('%A').lower(),
                'day_short': current_date.strftime('%a'),
                'formatted': current_date.strftime('%b %d')
            })
        
        # Get classes for this tutor in the week with relationships loaded
        classes = Class.query.options(
            joinedload(Class.primary_student)
        ).filter(
            Class.tutor_id == tutor_id,
            Class.scheduled_date >= week_start,
            Class.scheduled_date <= week_end
        ).all()
        
        # Organize classes by day
        schedule = {}
        for day_data in week_dates:
            day_name = day_data['day']
            schedule[day_name] = []
            
            day_classes = [cls for cls in classes if cls.scheduled_date.isoformat() == day_data['date']]
            
            for cls in day_classes:
                schedule[day_name].append({
                    'id': cls.id,
                    'time': cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00',
                    'end_time': (datetime.combine(datetime.today(), cls.scheduled_time) + timedelta(minutes=cls.duration or 60)).time().strftime('%H:%M') if cls.scheduled_time else '01:00',
                    'subject': cls.subject or 'No Subject',
                    'student': cls.primary_student.full_name if cls.primary_student else 'No Student',
                    'grade': cls.grade or '',
                    'class_type': cls.class_type or 'one_on_one',
                    'status': cls.status or 'scheduled',
                    'duration': cls.duration or 60,
                    'date': day_data['date']
                })
        
        # Get tutor availability (mock data for now)
        availability = {}
        for day_data in week_dates:
            day_name = day_data['day']
            # This should come from actual availability data
            if day_name in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
                availability[day_name] = [
                    {'start': '09:00', 'end': '10:00'},
                    {'start': '14:00', 'end': '15:00'},
                    {'start': '16:00', 'end': '17:00'}
                ]
            else:
                availability[day_name] = []
        
        # Week title
        week_title = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        
        return jsonify({
            'success': True,
            'data': {
                'week_title': week_title,
                'week_dates': week_dates,
                'schedule': schedule,
                'availability': availability
            }
        })
        
    except Exception as e:
        print(f"Error in API tutor weekly timetable: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/tutor/<int:tutor_id>/available-slots')
@login_required
@require_permission('class_management')
def api_tutor_available_slots(tutor_id):
    """API: Get available time slots for tutor on specific date"""
    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'success': False, 'error': 'Date parameter required'})
        
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = date_obj.strftime('%A').lower()
        
        # Get tutor
        tutor = Tutor.query.filter_by(id=tutor_id).first()
        if not tutor:
            return jsonify({'success': False, 'error': 'Tutor not found'})
        
        # Mock availability data (should come from actual availability table)
        if day_name in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
            available_slots = [
                {'start': '09:00', 'end': '10:00'},
                {'start': '10:00', 'end': '11:00'},
                {'start': '11:00', 'end': '12:00'},
                {'start': '14:00', 'end': '15:00'},
                {'start': '15:00', 'end': '16:00'},
                {'start': '16:00', 'end': '17:00'},
                {'start': '17:00', 'end': '18:00'}
            ]
        else:
            available_slots = [
                {'start': '10:00', 'end': '11:00'},
                {'start': '11:00', 'end': '12:00'}
            ]
        
        return jsonify({
            'success': True,
            'slots': available_slots
        })
        
    except Exception as e:
        print(f"Error in API tutor available slots: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# ============ EMAIL & EXPORT ROUTES ============

@bp.route('/timetable/email')
@login_required
@require_permission('class_management')
def timetable_email():
    """Timetable email management page"""
    try:
        # REDIRECT TO ACTUAL EXPORT PAGE
        return redirect(url_for('export_email_timetable.export_timetable_page'))
    except Exception as e:
        flash('Error accessing email functionality', 'error')
        return redirect(url_for('timetable.timetable'))


@bp.route('/timetable/export')
@login_required
@require_permission('class_management')
def timetable_export():
    """Timetable export functionality"""
    try:
        # REDIRECT TO ACTUAL EXPORT PAGE
        return redirect(url_for('export_email_timetable.export_timetable_page'))
    except Exception as e:
        flash('Error accessing export functionality', 'error')
        return redirect(url_for('timetable.timetable'))

# ============ UTILITY FUNCTIONS ============

def validate_and_convert_filters(request_args):
    """UTILITY: Validate and convert filter parameters consistently"""
    filters = {}
    
    # Search filter
    search = request_args.get('search', '').strip()
    if search:
        filters['search'] = search
    
    # Tutor filter
    tutor_id = request_args.get('tutor_id')
    if tutor_id and tutor_id not in ['', '0', None]:
        try:
            filters['tutor_id'] = int(tutor_id)
        except (ValueError, TypeError):
            pass
    
    # Student filter
    student_id = request_args.get('student_id')
    if student_id and student_id not in ['', '0', None]:
        try:
            filters['student_id'] = int(student_id)
        except (ValueError, TypeError):
            pass
    
    # Department filter
    department_id = request_args.get('department_id')
    if department_id and department_id not in ['', '0', None]:
        try:
            filters['department_id'] = int(department_id)
        except (ValueError, TypeError):
            pass
    
    return filters


def apply_precise_student_filter(classes_list, student_id):
    """UTILITY: Apply precise student filtering to a list of classes"""
    if not student_id:
        return classes_list
    
    valid_classes = []
    
    for cls in classes_list:
        student_is_in_class = False
        
        # Check primary student
        if cls.primary_student_id == student_id:
            student_is_in_class = True
        
        # Check demo student
        elif cls.demo_student_id == student_id:
            student_is_in_class = True
        
        # Check group students
        elif cls.students:
            try:
                student_ids_in_class = json.loads(cls.students)
                if isinstance(student_ids_in_class, list) and student_id in student_ids_in_class:
                    student_is_in_class = True
            except (json.JSONDecodeError, TypeError):
                # Fallback string search
                students_str = str(cls.students)
                if (f'"{student_id}"' in students_str or 
                    f'[{student_id}]' in students_str or 
                    f'{student_id},' in students_str or
                    f'[{student_id},' in students_str or
                    f',{student_id}]' in students_str):
                    student_is_in_class = True
        
        if student_is_in_class:
            valid_classes.append(cls)
    
    return valid_classes


def format_class_for_api(cls, include_details=True):
    """UTILITY: Format class object for API response consistently"""
    try:
        # Get tutor info
        tutor_name = 'No Tutor Assigned'
        tutor_email = ''
        tutor_id = None
        department_name = ''
        
        if cls.tutor and cls.tutor.user:
            tutor_name = cls.tutor.user.full_name
            tutor_email = cls.tutor.user.email or ''
            tutor_id = cls.tutor.id
            if cls.tutor.user.department:
                department_name = cls.tutor.user.department.name
        
        # Get student info
        student_count = 0
        student_names = []
        student_emails = []
        student_ids = []
        
        if cls.class_type == 'demo' and cls.demo_student_id:
            from app.models.demo_student import DemoStudent
            demo_student = DemoStudent.query.get(cls.demo_student_id)
            if demo_student:
                student_count = 1
                student_names = [demo_student.full_name]
                student_emails = [demo_student.email or '']
                student_ids = [cls.demo_student_id]
        
        elif cls.primary_student_id:
            student = Student.query.get(cls.primary_student_id)
            if student:
                student_count = 1
                student_names = [student.full_name]
                student_emails = [student.email or '']
                student_ids = [cls.primary_student_id]
        
        elif cls.students:
            try:
                parsed_student_ids = json.loads(cls.students)
                if isinstance(parsed_student_ids, list):
                    students = Student.query.filter(Student.id.in_(parsed_student_ids)).all()
                    student_count = len(students)
                    student_names = [s.full_name for s in students]
                    student_emails = [s.email or '' for s in students]
                    student_ids = [s.id for s in students]
            except (json.JSONDecodeError, TypeError):
                student_count = 0
                student_names = ['Group Students']
                student_emails = ['']
                student_ids = []
        
        # Time formatting
        scheduled_time = cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00'
        end_time = ''
        if cls.scheduled_time and cls.duration:
            start_datetime = datetime.combine(datetime.today(), cls.scheduled_time)
            end_datetime = start_datetime + timedelta(minutes=cls.duration)
            end_time = end_datetime.time().strftime('%H:%M')
        
        # Basic class data
        class_data = {
            'id': cls.id,
            'subject': cls.subject or '',
            'class_type': cls.class_type or 'one_on_one',
            'grade': cls.grade or '',
            'board': cls.board or '',
            'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
            'scheduled_time': scheduled_time,
            'time': scheduled_time,  # Alias for compatibility
            'end_time': end_time,
            'duration': cls.duration or 60,
            'status': cls.status or 'scheduled',
            'tutor_id': tutor_id,
            'tutor_name': tutor_name,
            'tutor_email': tutor_email,
            'department_name': department_name,
            'student_count': student_count,
            'student_names': student_names,
            'student_emails': student_emails,
            'student_ids': student_ids,
            'platform': cls.platform or '',
            'meeting_link': cls.meeting_link or '',
            'class_notes': cls.class_notes or ''
        }
        
        # Add detailed info if requested
        if include_details:
            class_data.update({
                'meeting_id': cls.meeting_id or '',
                'topics_covered': cls.topics_covered or '',
                'homework_assigned': cls.homework_assigned or '',
                'created_at': cls.created_at.strftime('%Y-%m-%d %H:%M') if cls.created_at else '',
                'actual_start_time': cls.actual_start_time.strftime('%Y-%m-%d %H:%M') if cls.actual_start_time else None,
                'actual_end_time': cls.actual_end_time.strftime('%Y-%m-%d %H:%M') if cls.actual_end_time else None
            })
        
        return class_data
        
    except Exception as e:
        print(f"❌ Error formatting class {cls.id}: {str(e)}")
        return {
            'id': cls.id,
            'subject': 'Error loading class',
            'error': str(e)
        }

# ============ API ROUTES ============

@bp.route('/api/v1/timetable/today')
@login_required
@admin_required
def api_timetable_today():
    """COMPLETELY FIXED: Get today's timetable data with working filters"""
    try:
        # Get date parameter
        date_param = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        
        # Get search filters - FIXED parameter names to match frontend
        search = request.args.get('search', '').strip()
        tutor_id = request.args.get('tutor_id')
        student_id = request.args.get('student_id') 
        department_id = request.args.get('department_id')
        
        # Convert empty strings and '0' to None
        tutor_id = int(tutor_id) if tutor_id and tutor_id != '0' and tutor_id != '' else None
        student_id = int(student_id) if student_id and student_id != '0' and student_id != '' else None
        department_id = int(department_id) if department_id and department_id != '0' and department_id != '' else None
        
        print(f"📅 Timetable Today - Date: {target_date}, Student: {student_id}, Tutor: {tutor_id}, Dept: {department_id}")
        
        # Base query for the specific date
        query = Class.query.filter(Class.scheduled_date == target_date)
        
        # Apply tutor filter
        if tutor_id:
            query = query.filter(Class.tutor_id == tutor_id)
            print(f"✅ Applied tutor filter: {tutor_id}")
        
        # Apply department filter
        if department_id:
            query = query.join(Tutor, Class.tutor_id == Tutor.id)\
                         .join(User, Tutor.user_id == User.id)\
                         .filter(User.department_id == department_id)
            print(f"✅ Applied department filter: {department_id}")
        
        # Apply search filter - FIXED to avoid duplicate joins
        if search:
            if not tutor_id and not department_id:  # Only join if not already joined
                query = query.join(Tutor, Class.tutor_id == Tutor.id, isouter=True)\
                             .join(User, Tutor.user_id == User.id, isouter=True)
            
            query = query.filter(
                db.or_(
                    Class.subject.ilike(f'%{search}%'),
                    User.full_name.ilike(f'%{search}%'),
                    Class.grade.ilike(f'%{search}%'),
                    Class.board.ilike(f'%{search}%')
                )
            )
            print(f"✅ Applied search filter: {search}")
        
        # COMPLETELY FIXED STUDENT FILTERING
        if student_id:
            print(f"🎯 Applying PRECISE student filter for ID: {student_id}")
            
            # Get all classes in the date range first (after other filters)
            all_classes_in_range = query.all()
            print(f"📅 Total classes on {target_date} before student filter: {len(all_classes_in_range)}")
            
            # Use utility function for precise filtering
            filtered_classes = apply_precise_student_filter(all_classes_in_range, student_id)
            print(f"🎯 Found {len(filtered_classes)} classes for student {student_id}")
            
            # Apply the precise filter
            if filtered_classes:
                valid_class_ids = [cls.id for cls in filtered_classes]
                query = Class.query.filter(
                    Class.id.in_(valid_class_ids),
                    Class.scheduled_date == target_date
                )
            else:
                # No classes found for this student
                query = Class.query.filter(Class.id == -1)  # Returns empty result
                print(f"⚠️ No classes found for student {student_id}")
        
        # Get FINAL filtered classes
        classes = query.order_by(Class.scheduled_time).all()
        
        print(f"📊 FINAL: Found {len(classes)} classes for today after filtering")
        
        # Build response data using utility function
        classes_data = [format_class_for_api(cls, include_details=False) for cls in classes]
        
        # Calculate stats - FIXED counts
        stats = {
            'total_classes': len(classes),
            'today': {
                'scheduled': len([c for c in classes if c.status == 'scheduled']),
                'ongoing': len([c for c in classes if c.status == 'ongoing']),
                'completed': len([c for c in classes if c.status == 'completed']),
                'cancelled': len([c for c in classes if c.status == 'cancelled'])
            }
        }
        
        return jsonify({
            'success': True,
            'classes': classes_data,
            'stats': stats,
            'date': target_date.strftime('%Y-%m-%d'),
            'filters_applied': {
                'search': search,
                'tutor_id': tutor_id,
                'student_id': student_id,
                'department_id': department_id
            }
        })
        
    except Exception as e:
        print(f"❌ Error in api_timetable_today: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'classes': [],
            'stats': {'total_classes': 0, 'today': {'scheduled': 0, 'ongoing': 0, 'completed': 0, 'cancelled': 0}}
        }), 500


@bp.route('/api/v1/timetable/monthly-stats')
@login_required
@admin_required
def api_timetable_monthly_stats():
    """COMPLETELY FIXED: Get monthly statistics with working filters"""
    try:
        year = request.args.get('year', datetime.now().year, type=int)
        search = request.args.get('search', '').strip()
        tutor_id = request.args.get('tutor_id')
        student_id = request.args.get('student_id')
        department_id = request.args.get('department_id')
        
        # Convert filters properly
        tutor_id = int(tutor_id) if tutor_id and tutor_id != '0' and tutor_id != '' else None
        student_id = int(student_id) if student_id and student_id != '0' and student_id != '' else None
        department_id = int(department_id) if department_id and department_id != '0' and department_id != '' else None
        
        print(f"📊 Monthly stats for year {year}, filters: tutor={tutor_id}, student={student_id}, dept={department_id}")
        
        monthly_stats = {}
        month_keys = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        for month in range(1, 13):
            # Get date range for month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            # Base query for the month
            query = Class.query.filter(
                Class.scheduled_date >= start_date,
                Class.scheduled_date <= end_date
            )
            
            # Apply non-student filters first
            if tutor_id:
                query = query.filter(Class.tutor_id == tutor_id)
            
            if department_id:
                query = query.join(Tutor, Class.tutor_id == Tutor.id)\
                             .join(User, Tutor.user_id == User.id)\
                             .filter(User.department_id == department_id)
            
            if search:
                if not tutor_id and not department_id:  # Avoid duplicate joins
                    query = query.join(Tutor, Class.tutor_id == Tutor.id, isouter=True)\
                                 .join(User, Tutor.user_id == User.id, isouter=True)
                query = query.filter(
                    db.or_(
                        Class.subject.ilike(f'%{search}%'),
                        User.full_name.ilike(f'%{search}%'),
                        Class.grade.ilike(f'%{search}%')
                    )
                )
            
            # FIXED STUDENT FILTERING for monthly stats
            if student_id:
                all_classes_in_month = query.all()
                filtered_classes = apply_precise_student_filter(all_classes_in_month, student_id)
                month_classes = len(filtered_classes)
            else:
                # No student filter - count all classes
                month_classes = query.count()
            
            monthly_stats[month_keys[month-1]] = month_classes
        
        print(f"📊 Monthly stats calculated: {monthly_stats}")
        
        return jsonify({
            'success': True,
            'stats': monthly_stats,
            'year': year
        })
        
    except Exception as e:
        print(f"❌ Error in monthly stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {key: 0 for key in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']}
        }), 500


@bp.route('/api/v1/timetable/month-details/<int:month>')
@login_required
@admin_required
def api_month_details(month):
    """COMPLETELY FIXED: Get detailed classes for a specific month"""
    try:
        year = request.args.get('year', datetime.now().year, type=int)
        search = request.args.get('search', '').strip()
        tutor_id = request.args.get('tutor_id')
        student_id = request.args.get('student_id')
        department_id = request.args.get('department_id')
        
        # Convert filters properly
        tutor_id = int(tutor_id) if tutor_id and tutor_id != '0' and tutor_id != '' else None
        student_id = int(student_id) if student_id and student_id != '0' and student_id != '' else None
        department_id = int(department_id) if department_id and department_id != '0' and department_id != '' else None
        
        print(f"📅 Month details for {month}/{year}, filters: tutor={tutor_id}, student={student_id}")
        
        # Get date range for month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Base query
        query = Class.query.filter(
            Class.scheduled_date >= start_date,
            Class.scheduled_date <= end_date
        )
        
        # Apply non-student filters
        if tutor_id:
            query = query.filter(Class.tutor_id == tutor_id)
        
        if department_id:
            query = query.join(Tutor, Class.tutor_id == Tutor.id)\
                         .join(User, Tutor.user_id == User.id)\
                         .filter(User.department_id == department_id)
        
        if search:
            if not tutor_id and not department_id:  # Avoid duplicate joins
                query = query.join(Tutor, Class.tutor_id == Tutor.id, isouter=True)\
                             .join(User, Tutor.user_id == User.id, isouter=True)
            query = query.filter(
                db.or_(
                    Class.subject.ilike(f'%{search}%'),
                    User.full_name.ilike(f'%{search}%'),
                    Class.grade.ilike(f'%{search}%')
                )
            )
        
        # FIXED STUDENT FILTERING
        if student_id:
            print(f"🎯 Applying precise student filter for month {month}")
            all_classes_in_month = query.all()
            print(f"📅 Total classes in month before student filter: {len(all_classes_in_month)}")
            
            filtered_classes = apply_precise_student_filter(all_classes_in_month, student_id)
            print(f"🎯 Found {len(filtered_classes)} classes for student in month")
            
            classes = filtered_classes
        else:
            # No student filter
            classes = query.order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        print(f"📊 FINAL: Found {len(classes)} classes for month {month}")
        
        # Group classes by date - FIXED format to match frontend
        classes_by_date = {}
        for cls in classes:
            date_str = cls.scheduled_date.strftime('%Y-%m-%d')
            if date_str not in classes_by_date:
                classes_by_date[date_str] = []
            
            tutor_name = 'No Tutor'
            if cls.tutor and cls.tutor.user:
                tutor_name = cls.tutor.user.full_name
            
            classes_by_date[date_str].append({
                'id': cls.id,
                'subject': cls.subject,
                'time': cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00',
                'tutor_name': tutor_name,
                'status': cls.status
            })
        
        return jsonify({
            'success': True,
            'classes_by_date': classes_by_date,
            'month': month,
            'year': year,
            'total_classes': len(classes)
        })
        
    except Exception as e:
        print(f"❌ Error in month details: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/timetable/week')
@login_required
@admin_required
def api_timetable_week():
    """FIXED: Get weekly timetable data with working filters"""
    try:
        date_param = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        
        # Get start of week (Monday)
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # Get filters
        search = request.args.get('search', '').strip()
        tutor_id = request.args.get('tutor_id')
        student_id = request.args.get('student_id')
        department_id = request.args.get('department_id')
        
        # Convert filters properly
        tutor_id = int(tutor_id) if tutor_id and tutor_id != '0' and tutor_id != '' else None
        student_id = int(student_id) if student_id and student_id != '0' and student_id != '' else None
        department_id = int(department_id) if department_id and department_id != '0' and department_id != '' else None
        
        print(f"📅 Timetable Week - {start_of_week} to {end_of_week}, Student: {student_id}")
        
        # Base query for the week
        query = Class.query.filter(
            Class.scheduled_date >= start_of_week,
            Class.scheduled_date <= end_of_week
        )
        
        # Apply non-student filters first
        if tutor_id:
            query = query.filter(Class.tutor_id == tutor_id)
        
        if department_id:
            query = query.join(Tutor, Class.tutor_id == Tutor.id)\
                         .join(User, Tutor.user_id == User.id)\
                         .filter(User.department_id == department_id)
        
        if search:
            if not tutor_id and not department_id:
                query = query.join(Tutor, Class.tutor_id == Tutor.id, isouter=True)\
                             .join(User, Tutor.user_id == User.id, isouter=True)
            query = query.filter(
                db.or_(
                    Class.subject.ilike(f'%{search}%'),
                    User.full_name.ilike(f'%{search}%'),
                    Class.grade.ilike(f'%{search}%')
                )
            )
        
        # FIXED STUDENT FILTERING
        if student_id:
            print(f"🎯 Applying PRECISE student filter for weekly view")
            all_classes_in_range = query.all()
            print(f"📅 Total classes in week before student filter: {len(all_classes_in_range)}")
            
            filtered_classes = apply_precise_student_filter(all_classes_in_range, student_id)
            print(f"🎯 Found {len(filtered_classes)} classes for student in week")
            
            classes = filtered_classes
        else:
            classes = query.order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        print(f"📊 FINAL: Found {len(classes)} classes for week after filtering")
        
        # Group by date for week view
        week_data = {}
        for i in range(7):
            current_date = start_of_week + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            week_data[date_str] = []
        
        for cls in classes:
            date_str = cls.scheduled_date.strftime('%Y-%m-%d')
            if date_str in week_data:
                tutor_name = cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'No Tutor'
                
                week_data[date_str].append({
                    'id': cls.id,
                    'subject': cls.subject,
                    'time': cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00',
                    'tutor_name': tutor_name,
                    'status': cls.status,
                    'duration': cls.duration
                })
        
        return jsonify({
            'success': True,
            'week_data': week_data,
            'start_date': start_of_week.strftime('%Y-%m-%d'),
            'end_date': end_of_week.strftime('%Y-%m-%d'),
            'total_classes': len(classes)
        })
        
    except Exception as e:
        print(f"❌ Error in api_timetable_week: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/timetable/year')
@login_required
@admin_required
def api_timetable_year():
    """FIXED: Get yearly timetable data with detailed calendar structure"""
    try:
        year = request.args.get('year', datetime.now().year, type=int)
        search = request.args.get('search', '').strip()
        tutor_id = request.args.get('tutor_id')
        student_id = request.args.get('student_id')
        department_id = request.args.get('department_id')
        
        # Convert filters properly
        tutor_id = int(tutor_id) if tutor_id and tutor_id != '0' and tutor_id != '' else None
        student_id = int(student_id) if student_id and student_id != '0' and student_id != '' else None
        department_id = int(department_id) if department_id and department_id != '0' and department_id != '' else None
        
        print(f"📅 Year view for {year}, filters: tutor={tutor_id}, student={student_id}")
        
        # Get all classes for the year
        start_date = datetime(year, 1, 1).date()
        end_date = datetime(year, 12, 31).date()
        
        # Build query with filters
        query = Class.query.filter(
            Class.scheduled_date >= start_date,
            Class.scheduled_date <= end_date
        )
        
        # Apply search filters
        if tutor_id:
            query = query.filter(Class.tutor_id == tutor_id)
        
        if department_id:
            query = query.join(Tutor, Class.tutor_id == Tutor.id)\
                         .join(User, Tutor.user_id == User.id)\
                         .filter(User.department_id == department_id)
        
        if search:
            if not tutor_id and not department_id:
                query = query.join(Tutor, Class.tutor_id == Tutor.id, isouter=True)\
                             .join(User, Tutor.user_id == User.id, isouter=True)
            query = query.filter(
                db.or_(
                    Class.subject.ilike(f'%{search}%'),
                    User.full_name.ilike(f'%{search}%'),
                    Class.grade.ilike(f'%{search}%')
                )
            )
        
        # FIXED STUDENT FILTERING
        if student_id:
            print(f"🎯 Applying PRECISE student filter for year view")
            all_classes_in_year = query.all()
            print(f"📅 Total classes in year before student filter: {len(all_classes_in_year)}")
            
            filtered_classes = apply_precise_student_filter(all_classes_in_year, student_id)
            print(f"🎯 Found {len(filtered_classes)} classes for student in year")
            
            classes = filtered_classes
        else:
            # Get all classes
            classes = query.order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        print(f"📊 FINAL: Found {len(classes)} classes for year")
        
        # Group classes by month and date
        year_data = {}
        monthly_stats = {}
        
        # Initialize 12 months
        month_keys = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        for i, month_key in enumerate(month_keys, 1):
            year_data[i] = {}
            monthly_stats[month_key] = 0
        
        # Process each class using utility function
        for cls in classes:
            try:
                month = cls.scheduled_date.month
                date_key = cls.scheduled_date.strftime('%Y-%m-%d')
                
                # Initialize date if not exists
                if date_key not in year_data[month]:
                    year_data[month][date_key] = []
                
                # Format class data
                class_data = format_class_for_api(cls, include_details=True)
                
                # Add to year data
                year_data[month][date_key].append(class_data)
                
                # Update monthly stats
                month_key = month_keys[month - 1]
                monthly_stats[month_key] = monthly_stats.get(month_key, 0) + 1
                
            except Exception as e:
                print(f"Error processing class {cls.id}: {str(e)}")
                continue
        
        # Calculate total statistics
        total_classes = len(classes)
        scheduled_count = len([c for c in classes if c.status == 'scheduled'])
        completed_count = len([c for c in classes if c.status == 'completed'])
        cancelled_count = len([c for c in classes if c.status == 'cancelled'])
        ongoing_count = len([c for c in classes if c.status == 'ongoing'])
        
        # Create month details for calendar rendering
        months_detail = []
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        for month_num in range(1, 13):
            month_name = month_names[month_num - 1]
            month_key = month_keys[month_num - 1]
            month_classes_count = monthly_stats.get(month_key, 0)
            
            months_detail.append({
                'month_number': month_num,
                'month_name': month_name,
                'month_key': month_key,
                'class_count': month_classes_count,
                'classes_by_date': year_data.get(month_num, {})
            })
        
        return jsonify({
            'success': True,
            'year': year,
            'total_classes': total_classes,
            'months_detail': months_detail,
            'monthly_stats': monthly_stats,
            'year_classes_by_month': year_data,
            'stats': {
                'total_classes': total_classes,
                'scheduled': scheduled_count,
                'completed': completed_count,
                'cancelled': cancelled_count,
                'ongoing': ongoing_count
            },
            'filters_applied': {
                'search': search,
                'tutor_id': tutor_id,
                'student_id': student_id,
                'department_id': department_id
            }
        })
        
    except Exception as e:
        print(f"❌ Error in api_timetable_year: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'year': year,
            'months_detail': [],
            'monthly_stats': {},
            'stats': {'total_classes': 0, 'scheduled': 0, 'completed': 0, 'cancelled': 0, 'ongoing': 0}
        }), 500


@bp.route('/api/v1/timetable/class/<int:class_id>')
@login_required
@admin_required
def api_get_class_details(class_id):
    """FIXED: Get detailed information about a specific class"""
    try:
        cls = Class.query.get_or_404(class_id)
        
        # Get tutor details
        tutor_info = {
            'id': None,
            'name': 'No Tutor Assigned',
            'email': '',
            'phone': '',
            'subjects': []
        }
        
        if cls.tutor and cls.tutor.user:
            tutor_info = {
                'id': cls.tutor.id,
                'name': cls.tutor.user.full_name,
                'email': cls.tutor.user.email or '',
                'phone': cls.tutor.user.phone or '',
                'subjects': cls.tutor.get_subjects() if hasattr(cls.tutor, 'get_subjects') else []
            }
        
        # Get student details using utility function
        class_data = format_class_for_api(cls, include_details=True)
        
        # Convert to detailed format expected by frontend
        students_info = []
        if cls.class_type == 'demo' and cls.demo_student_id:
            from app.models.demo_student import DemoStudent
            demo_student = DemoStudent.query.get(cls.demo_student_id)
            if demo_student:
                students_info.append({
                    'id': demo_student.id,
                    'name': demo_student.full_name,
                    'email': demo_student.email,
                    'phone': demo_student.phone,
                    'type': 'demo'
                })
        elif cls.primary_student_id:
            student = Student.query.get(cls.primary_student_id)
            if student:
                students_info.append({
                    'id': student.id,
                    'name': student.full_name,
                    'email': student.email,
                    'phone': student.phone,
                    'type': 'regular'
                })
        elif cls.students:
            try:
                student_ids = json.loads(cls.students)
                if isinstance(student_ids, list):
                    for student_id in student_ids:
                        student = Student.query.get(student_id)
                        if student:
                            students_info.append({
                                'id': student.id,
                                'name': student.full_name,
                                'email': student.email,
                                'phone': student.phone,
                                'type': 'regular'
                            })
            except (json.JSONDecodeError, TypeError):
                print(f"Error parsing students JSON for class {class_id}")
        
        class_details = {
            'id': cls.id,
            'subject': cls.subject,
            'class_type': cls.class_type,
            'grade': cls.grade,
            'board': cls.board,
            'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
            'scheduled_time': cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00',
            'duration': cls.duration,
            'status': cls.status,
            'platform': cls.platform,
            'meeting_link': cls.meeting_link,
            'meeting_id': cls.meeting_id,
            'class_notes': cls.class_notes,
            'topics_covered': cls.topics_covered,
            'homework_assigned': cls.homework_assigned,
            'tutor': tutor_info,
            'students': students_info,
            'created_at': cls.created_at.strftime('%Y-%m-%d %H:%M') if cls.created_at else '',
            'actual_start_time': cls.actual_start_time.strftime('%Y-%m-%d %H:%M') if cls.actual_start_time else None,
            'actual_end_time': cls.actual_end_time.strftime('%Y-%m-%d %H:%M') if cls.actual_end_time else None
        }
        
        return jsonify({
            'success': True,
            'class': class_details
        })
        
    except Exception as e:
        print(f"❌ Error getting class details: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/timetable/quick-class', methods=['POST'])
@login_required
@admin_required
def api_create_quick_class():
    """FIXED: Create a quick class with proper validation"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['subject', 'tutor_id', 'scheduled_date', 'scheduled_time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Parse date and time
        try:
            scheduled_date = datetime.strptime(data['scheduled_date'], '%Y-%m-%d').date()
            scheduled_time = datetime.strptime(data['scheduled_time'], '%H:%M').time()
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Invalid date/time format: {str(e)}'}), 400
        
        # Validate tutor exists
        tutor = Tutor.query.get(data['tutor_id'])
        if not tutor:
            return jsonify({'success': False, 'error': 'Invalid tutor selected'}), 400
        
        # Create new class
        new_class = Class(
            subject=data['subject'],
            class_type=data.get('class_type', 'one_on_one'),
            grade=data.get('grade', ''),
            board=data.get('board', ''),
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration=int(data.get('duration', 60)),
            tutor_id=data['tutor_id'],
            primary_student_id=data.get('primary_student_id') if data.get('primary_student_id') else None,
            meeting_link=data.get('meeting_link', ''),
            platform=data.get('platform', 'zoom'),
            class_notes=data.get('class_notes', ''),
            status='scheduled',
            created_by=current_user.id
        )
        
        # Calculate end time
        if hasattr(new_class, 'calculate_end_time'):
            new_class.calculate_end_time()
        
        db.session.add(new_class)
        db.session.commit()
        
        print(f"✅ Created quick class: {new_class.id} - {new_class.subject}")
        
        return jsonify({
            'success': True,
            'message': 'Class created successfully',
            'class_id': new_class.id,
            'class_data': {
                'id': new_class.id,
                'subject': new_class.subject,
                'scheduled_date': new_class.scheduled_date.strftime('%Y-%m-%d'),
                'scheduled_time': new_class.scheduled_time.strftime('%H:%M'),
                'tutor_name': new_class.tutor.user.full_name if new_class.tutor and new_class.tutor.user else 'Unknown'
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating quick class: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/v1/tutor/<int:tutor_id>/details')
@login_required
@admin_required
def api_tutor_details(tutor_id):
    """Get tutor detailed information"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        details = {
            'name': tutor.user.full_name if tutor.user else 'Unknown',
            'email': tutor.user.email if tutor.user else 'No email',
            'phone': tutor.user.phone if tutor.user else None,
            'experience': tutor.experience,
            'subjects': tutor.get_subjects() if hasattr(tutor, 'get_subjects') else [],
            'status': tutor.status,
            'qualification': tutor.qualification,
            'hourly_rate': tutor.hourly_rate,
            'monthly_salary': tutor.monthly_salary
        }
        
        return jsonify({
            'success': True,
            'details': details
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============ DEBUG & TESTING ENDPOINTS ============

@bp.route('/api/v1/timetable/debug')
@login_required
@admin_required
def api_timetable_debug():
    """Debug endpoint to check timetable system status"""
    try:
        debug_info = {
            'total_classes': Class.query.count(),
            'total_tutors': Tutor.query.count(),
            'total_students': Student.query.count(),
            'total_departments': Department.query.count(),
            'class_types': {
                'one_on_one': Class.query.filter_by(class_type='one_on_one').count(),
                'group': Class.query.filter_by(class_type='group').count(),
                'demo': Class.query.filter_by(class_type='demo').count()
            },
            'class_statuses': {
                'scheduled': Class.query.filter_by(status='scheduled').count(),
                'ongoing': Class.query.filter_by(status='ongoing').count(),
                'completed': Class.query.filter_by(status='completed').count(),
                'cancelled': Class.query.filter_by(status='cancelled').count()
            },
            'recent_classes_sample': []
        }
        
        # Get sample of recent classes for debugging
        recent_classes = Class.query.order_by(Class.created_at.desc()).limit(5).all()
        for cls in recent_classes:
            try:
                class_info = {
                    'id': cls.id,
                    'subject': cls.subject,
                    'tutor_name': cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'No Tutor',
                    'primary_student_id': cls.primary_student_id,
                    'demo_student_id': cls.demo_student_id,
                    'students_json': cls.students,
                    'class_type': cls.class_type,
                    'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
                    'status': cls.status
                }
                debug_info['recent_classes_sample'].append(class_info)
            except Exception as e:
                debug_info['recent_classes_sample'].append({
                    'id': cls.id,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/csrf-token')
@login_required
def api_get_csrf_token():
    """Get CSRF token for AJAX requests"""
    try:
        return jsonify({
            'success': True,
            'csrf_token': generate_csrf()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/timetable/test-filters')
@login_required
@admin_required
def api_test_filters():
    """Test endpoint for filter functionality"""
    try:
        # Get test parameters
        test_tutor_id = request.args.get('test_tutor_id', type=int)
        test_student_id = request.args.get('test_student_id', type=int)
        
        results = {
            'total_classes': Class.query.count(),
            'filter_tests': {}
        }
        
        # Test tutor filter
        if test_tutor_id:
            tutor_classes = Class.query.filter_by(tutor_id=test_tutor_id).count()
            results['filter_tests']['tutor_filter'] = {
                'tutor_id': test_tutor_id,
                'classes_found': tutor_classes
            }
        
        # Test student filter
        if test_student_id:
            student_classes = []
            all_classes = Class.query.all()
            
            for cls in all_classes:
                if (cls.primary_student_id == test_student_id or 
                    cls.demo_student_id == test_student_id):
                    student_classes.append(cls.id)
                elif cls.students:
                    try:
                        student_ids = json.loads(cls.students)
                        if isinstance(student_ids, list) and test_student_id in student_ids:
                            student_classes.append(cls.id)
                    except:
                        pass
            
            results['filter_tests']['student_filter'] = {
                'student_id': test_student_id,
                'classes_found': len(student_classes),
                'class_ids': student_classes
            }
        
        return jsonify({
            'success': True,
            'test_results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

