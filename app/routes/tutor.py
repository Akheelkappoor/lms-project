from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os
import pytz
from app import db
from app.utils.timezone_utils import get_local_time, calculate_time_until
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from functools import wraps
from app.utils.helper import upload_file_to_s3, upload_organized_file_to_s3
from flask_moment import Moment
import json

# Import new services for optimization
from app.services.database_service import DatabaseService
from app.services.validation_service import ValidationService
from app.services.error_service import handle_errors, error_service

bp = Blueprint('tutor', __name__)

def tutor_required(f):
    """Decorator to require tutor access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'tutor':
            flash('Access denied. This page is for tutors only.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_tutor():
    """Get current user's tutor profile"""
    return Tutor.query.filter_by(user_id=current_user.id).first()

@bp.route('/my-classes')
@login_required
@tutor_required
@handle_errors
def my_classes():
    """View tutor's classes with optimized queries"""
    # Use optimized query for tutor lookup
    tutor = DatabaseService.get_optimized_query(
        Tutor,
        includes=['user'],
        filters={'user_id': current_user.id}
    ).first()
    
    if not tutor:
        return error_service.handle_not_found_error("Tutor profile")
    
    # Check if tutor has set availability
    availability = tutor.get_availability()
    if not availability:
        flash('Please set your availability first before viewing classes.', 'warning')
        return redirect(url_for('tutor.availability'))
    
    # Get pagination and filtering parameters
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    subject_filter = request.args.get('subject', '')
    
    # Build optimized query with eager loading
    query = Class.query.filter_by(tutor_id=tutor.id).options(
        db.joinedload(Class.primary_student),
        db.selectinload(Class.attendance_records)
    )
    
    # Apply filters
    filters = {'tutor_id': tutor.id}
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(Class.scheduled_date == filter_date)
        except ValueError:
            flash('Invalid date format', 'error')
    
    if status_filter:
        query = query.filter(Class.status == status_filter)
    
    if subject_filter:
        query = query.filter(Class.subject.ilike(subject_filter))
    
    # Order by date and time
    query = query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc())
    
    # Use DatabaseService for pagination
    classes_data = DatabaseService.paginate_query(
        query, page=page, per_page=20
    )
    
    # Define current time and today with timezone handling
    current_time = get_local_time()
    today = current_time.date()
    
    # Get today's classes
    todays_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date == today
    ).order_by(Class.scheduled_time).all()
    
    # Process today's classes with time information
    todays_classes_with_time = []
    for cls in todays_classes:
        class_datetime = datetime.combine(cls.scheduled_date, cls.scheduled_time)
        is_time_reached = current_time >= (class_datetime - timedelta(minutes=5))
        time_until = calculate_time_until(class_datetime)
        
        # Debug: Add additional logging for timezone issues
        print(f"DEBUG - Class {cls.id}: current_time={current_time}, class_datetime={class_datetime}, time_until={time_until}")
        
        # Additional safety check for timezone issues affecting some tutors
        if time_until > 300:  # More than 5 hours seems wrong
            print(f"WARNING - Large time_until detected for class {cls.id}: {time_until} minutes")
            print(f"Class scheduled for: {cls.scheduled_date} {cls.scheduled_time}")
            print(f"Current time: {current_time}")
            # Recalculate with naive datetime as fallback
            naive_current = datetime.now()
            naive_class = datetime.combine(cls.scheduled_date, cls.scheduled_time)
            naive_diff = max(0, int((naive_class - naive_current).total_seconds() / 60))
            print(f"Naive calculation: {naive_diff} minutes")
            
            # Use the smaller of the two calculations
            time_until = min(time_until, naive_diff) if naive_diff < 1440 else 0
        
        cls_data = {
            'class': cls,
            'is_time_reached': is_time_reached,
            'time_until': time_until,
            'class_datetime': class_datetime
        }
        todays_classes_with_time.append(cls_data)
    
    # Get filtered args for pagination links
    filtered_args = {}
    for key in ['date', 'status', 'subject']:
        if request.args.get(key):
            filtered_args[key] = request.args.get(key)
    
    return render_template('tutor/my_classes.html',
                         classes=classes_data,
                         todays_classes=todays_classes_with_time,
                         tutor=tutor,
                         current_time=datetime.now(),
                         filtered_args=filtered_args,
                         today=today)


@bp.route('/today-classes')
@login_required
@tutor_required
def today_classes():
    """View today's classes for tutor"""
    tutor = Tutor.query.filter_by(user_id=current_user.id).first_or_404()
    today = date.today()
    
    # Get today's classes
    classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date == today
    ).order_by(Class.scheduled_time).all()
    
    # Get all students for today's classes
    all_student_ids = set()
    for cls in classes:
        all_student_ids.update(cls.get_students())
    
    students = Student.query.filter(Student.id.in_(all_student_ids)).all() if all_student_ids else []
    students_dict = {s.id: s for s in students}
    total_students = len(students)
    
    # Get upcoming classes (next 7 days)
    upcoming_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date > today,
        Class.scheduled_date <= today + timedelta(days=7),
        Class.status == 'scheduled'
    ).order_by(Class.scheduled_date, Class.scheduled_time).all()
    
    return render_template('tutor/today_classes.html',
                         classes=classes,
                         today=today,
                         total_students=total_students,
                         students_dict=students_dict,
                         upcoming_classes=upcoming_classes,
                         moment=datetime.now)

@bp.route('/class/<int:class_id>')
@login_required
@tutor_required
def class_details(class_id):
    """View class details with time-based controls"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    class_item = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    # Get current time information with timezone handling
    current_time = get_local_time()
    class_datetime = datetime.combine(class_item.scheduled_date, class_item.scheduled_time)
    is_today = class_item.scheduled_date == current_time.date()
    is_time_reached = current_time >= (class_datetime - timedelta(minutes=5))
    time_until_class = calculate_time_until(class_datetime)
    
    # Debug: Add additional logging for timezone issues in class details
    print(f"DEBUG - Class Details {class_id}: current_time={current_time}, class_datetime={class_datetime}, time_until_class={time_until_class}")
    
    # Additional safety check for timezone issues affecting some tutors
    if time_until_class > 300:  # More than 5 hours seems wrong
        print(f"WARNING - Large time_until_class detected for class {class_id}: {time_until_class} minutes")
        print(f"Class scheduled for: {class_item.scheduled_date} {class_item.scheduled_time}")
        print(f"Current time: {current_time}")
        # Recalculate with naive datetime as fallback
        naive_current = datetime.now()
        naive_class = datetime.combine(class_item.scheduled_date, class_item.scheduled_time)
        naive_diff = max(0, int((naive_class - naive_current).total_seconds() / 60))
        print(f"Naive calculation: {naive_diff} minutes")
        
        # Use the smaller of the two calculations
        time_until_class = min(time_until_class, naive_diff) if naive_diff < 1440 else 0
    
    # Get students for this class
    student_ids = class_item.get_students()
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    # Get related classes (same subject, recent)
    related_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.subject.ilike(class_item.subject),
        Class.id != class_id
    ).order_by(Class.scheduled_date.desc()).limit(5).all()
    
    return render_template('tutor/class_details.html',
                         class_item=class_item,
                         students=students,
                         attendance_records=attendance_records,
                         related_classes=related_classes,
                         current_time=current_time,
                         class_datetime=class_datetime,
                         is_today=is_today,
                         is_time_reached=is_time_reached,
                         time_until_class=time_until_class)

@bp.route('/class/<int:class_id>/start', methods=['POST'])
@login_required
@tutor_required
def start_class(class_id):
    """Start a class"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status != 'scheduled':
        return jsonify({'error': 'Class cannot be started'}), 400
    
    class_obj.start_class()
    
    # Create attendance records if they don't exist
    existing_attendance = Attendance.query.filter_by(class_id=class_id).first()
    if not existing_attendance:
        Attendance.create_attendance_record(class_obj)
        db.session.commit()
    
    return start_class_with_auto_attendance(class_id)

@bp.route('/class/<int:class_id>/complete', methods=['POST'])
@login_required
@tutor_required
def complete_class(class_id):
    """Redirect to completion workflow"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status not in ['scheduled', 'ongoing']:
        return jsonify({'error': 'Class cannot be completed'}), 400
    
    # For API calls, return redirect URL
    return jsonify({
        'success': True,
        'message': 'Redirecting to completion workflow...',
        'redirect_url': f'/tutor/class/{class_id}/complete-workflow'
    })

@bp.route('/attendance/mark', methods=['POST'])
@login_required
@tutor_required
def mark_attendance():
    """Mark attendance for a class"""
    tutor = get_current_tutor()
    data = request.get_json()
    
    class_id = data.get('class_id')
    attendance_data = data.get('attendance', [])
    
    # Verify class belongs to tutor
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    try:
        for attendance_info in attendance_data:
            attendance_id = attendance_info.get('attendance_id')
            attendance = Attendance.query.get(attendance_id)
            
            if attendance and attendance.class_id == class_id:
                # Mark tutor attendance
                tutor_present = attendance_info.get('tutor_present', False)
                tutor_join_time = None
                tutor_leave_time = None
                
                if tutor_present:
                    tutor_join_time = datetime.now()
                    tutor_leave_time = datetime.now()
                
                attendance.mark_tutor_attendance(
                    present=tutor_present,
                    join_time=tutor_join_time,
                    leave_time=tutor_leave_time,
                    absence_reason=attendance_info.get('tutor_absence_reason')
                )
                
                # Mark student attendance
                student_present = attendance_info.get('student_present', False)
                student_join_time = None
                student_leave_time = None
                
                if student_present:
                    student_join_time = datetime.now()
                    student_leave_time = datetime.now()
                
                attendance.mark_student_attendance(
                    present=student_present,
                    join_time=student_join_time,
                    leave_time=student_leave_time,
                    absence_reason=attendance_info.get('student_absence_reason'),
                    engagement=attendance_info.get('student_engagement')
                )
                
                # Calculate actual duration and penalties
                attendance.calculate_actual_duration()
                attendance.calculate_tutor_penalty()
                
                attendance.marked_by = current_user.id
                attendance.marked_at = datetime.now()
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance marked successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error marking attendance'}), 500

@bp.route('/my-students')
@login_required
@tutor_required
def my_students():
    """View tutor's assigned students"""
    tutor = Tutor.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get students from classes taught by this tutor
    student_ids = set()
    classes = Class.query.filter_by(tutor_id=tutor.id).all()
    
    for cls in classes:
        student_ids.update(cls.get_students())
    
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Get attendance data for each student
    student_attendance = {}
    for student in students:
        attendance_summary = Attendance.get_attendance_summary(student_id=student.id, tutor_id=tutor.id)
        student_attendance[student.id] = attendance_summary
    
    # Get upcoming classes for each student
    student_upcoming_classes = {}
    for student in students:
        upcoming = Class.query.filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date >= date.today(),
            Class.status == 'scheduled'
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        student_classes = [cls for cls in upcoming if student.id in cls.get_students()]
        student_upcoming_classes[student.id] = student_classes[:5]  # Next 5 classes
    
    # Get unique grades
    grades = sorted(list(set(s.grade for s in students if s.grade)))
    
    # Count low attendance students (less than 75%)
    low_attendance_count = sum(1 for s in students 
                              if student_attendance.get(s.id, {}).get('percentage', 100) < 75)
    
    # Count total upcoming classes
    upcoming_classes_count = sum(len(classes) for classes in student_upcoming_classes.values())
    
    return render_template('tutor/my_students.html',
                         students=students,
                         student_attendance=student_attendance,
                         student_upcoming_classes=student_upcoming_classes,
                         grades=grades,
                         low_attendance_count=low_attendance_count,
                         upcoming_classes_count=upcoming_classes_count)

@bp.route('/attendance')
@login_required
@tutor_required
def attendance():
    """View tutor's attendance records"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get date range filters
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = Attendance.query.filter_by(tutor_id=tutor.id)
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.class_date >= start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.class_date <= end_date_obj)
        except ValueError:
            pass
    
    # Get paginated results
    attendance_records = query.order_by(Attendance.class_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    all_tutor_records = Attendance.query.filter_by(tutor_id=tutor.id).all()
    summary = {
        'total_classes': len(all_tutor_records),
        'present_count': sum(1 for r in all_tutor_records if r.tutor_present),
        'absent_count': sum(1 for r in all_tutor_records if not r.tutor_present),
        'late_count': sum(1 for r in all_tutor_records if r.tutor_late_minutes > 0),
        'attendance_percentage': (sum(1 for r in all_tutor_records if r.tutor_present) / len(all_tutor_records) * 100) if all_tutor_records else 0
    }
    
    return render_template('tutor/attendance.html', 
                         attendance_records=attendance_records, 
                         summary=summary, tutor=tutor)

@bp.route('/salary')
@login_required
@tutor_required
def salary():
    """View tutor's salary information"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get current month earnings
    current_month = datetime.now().month
    current_year = datetime.now().year
    current_earnings = tutor.get_monthly_earnings(current_month, current_year)
    
    # Get last 6 months earnings
    monthly_earnings = []
    for i in range(6):
        month = current_month - i
        year = current_year
        
        if month <= 0:
            month += 12
            year -= 1
        
        earnings = tutor.get_monthly_earnings(month, year)
        month_name = datetime(year, month, 1).strftime('%B %Y')
        
        monthly_earnings.append({
            'month': month_name,
            'earnings': earnings,
            'month_num': month,
            'year': year
        })
    
    monthly_earnings.reverse()  # Show oldest first
    
    # Get attendance-based deductions for current month
    current_month_penalties = db.session.query(
        db.func.sum(Attendance.penalty_amount)
    ).filter(
        Attendance.tutor_id == tutor.id,
        db.extract('month', Attendance.class_date) == current_month,
        db.extract('year', Attendance.class_date) == current_year
    ).scalar() or 0
    
    return render_template('tutor/salary.html', 
                         tutor=tutor,
                         current_earnings=current_earnings,
                         monthly_earnings=monthly_earnings,
                         current_penalties=current_month_penalties)

@bp.route('/upload-video/<int:class_id>', methods=['POST'])
@login_required
@tutor_required
def upload_video(class_id):
    """Upload class video"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400
    
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No video file selected'}), 400
    
    # Check file type
    allowed_extensions = {'mp4', 'avi', 'mov', 'wmv', 'mkv'}
    if not ('.' in video_file.filename and 
            video_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid video format'}), 400
    
    try:
        if video_file and video_file.filename:
            tutor_id = tutor.id
            
            print(f"Uploading attendance video for class {class_id}, tutor {tutor_id}")
            
            # Use organized upload for attendance videos
            s3_url = upload_organized_file_to_s3(
                file=video_file,
                file_type='video',
                category='attendance',
                user_id=tutor_id,
                class_id=class_id
            )
            
            if not s3_url:
                raise ValueError("Video upload to S3 failed.")
            
            # Update class record with S3 video link
            class_obj.video_link = s3_url
            class_obj.video_uploaded_at = datetime.now()
            db.session.commit()
            
            print(f"Video upload successful for class {class_id}: {s3_url}")
                
        return jsonify({'success': True, 'message': 'Video uploaded successfully', 'video_url': s3_url})
        
    except Exception as e:
        print(f"Error in upload_video: {str(e)}")
        current_app.logger.error(f"Video upload error for class {class_id}: {str(e)}")
        return jsonify({'error': f'Video upload failed: {str(e)}'}), 500

@bp.route('/profile')
@login_required
@tutor_required
def profile():
    """View and edit tutor profile"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    return render_template('tutor/profile.html', tutor=tutor)

@bp.route('/calendar-data')
@login_required
@tutor_required
def calendar_data():
    """Get calendar data for tutor"""
    tutor = get_current_tutor()
    if not tutor:
        return jsonify({'error': 'Tutor not found'}), 404
    
    # Get date range from request
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    
    try:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        # Default to current month
        today = date.today()
        start_date_obj = today.replace(day=1)
        next_month = today.replace(day=28) + timedelta(days=4)
        end_date_obj = next_month - timedelta(days=next_month.day)
    
    # Get classes in date range
    classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.scheduled_date >= start_date_obj,
        Class.scheduled_date <= end_date_obj
    ).all()
    
    # Format for calendar
    events = []
    for cls in classes:
        events.append({
            'id': cls.id,
            'title': f"{cls.subject} - {cls.primary_student.full_name if cls.primary_student else 'Group Class'}",
            'start': f"{cls.scheduled_date}T{cls.scheduled_time}",
            'end': f"{cls.scheduled_date}T{cls.end_time}",
            'backgroundColor': get_status_color(cls.status),
            'borderColor': get_status_color(cls.status),
            'extendedProps': {
                'status': cls.status,
                'student_count': len(cls.get_students()),
                'class_type': cls.class_type
            }
        })
    
    return jsonify(events)

def get_status_color(status):
    """Get color for class status"""
    colors = {
        'scheduled': '#F1A150',
        'ongoing': '#28A745',
        'completed': '#17A2B8',
        'cancelled': '#DC3545',
        'rescheduled': '#FFC107'
    }
    return colors.get(status, '#6C757D')

@bp.route('/student/<int:student_id>')
@login_required
@tutor_required
def student_profile(student_id):
    """View student profile - redirect to admin view"""
    return redirect(url_for('student.student_profile', student_id=student_id))


@bp.route('/student/<int:student_id>/classes')
@login_required
@tutor_required
def student_classes(student_id):
    """View student's classes with this tutor"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    student = Student.query.get_or_404(student_id)
    
    # Get classes taught by this tutor for this student
    student_classes = []
    all_classes = Class.query.filter_by(tutor_id=tutor.id).order_by(Class.scheduled_date.desc()).all()
    
    has_access = False
    for cls in all_classes:
        if student.id in cls.get_students():
            student_classes.append(cls)
            has_access = True
    
    if not has_access:
        flash('You do not have access to view this student.', 'error')
        return redirect(url_for('tutor.my_students'))
    
    # Get attendance summary for this student with this tutor
    attendance_summary = Attendance.get_attendance_summary(student_id=student.id, tutor_id=tutor.id)
    
    return render_template('tutor/student_classes.html',
                         student=student,
                         classes=student_classes,
                         attendance_summary=attendance_summary,
                         tutor=tutor)

@bp.route('/student/<int:student_id>/attendance')
@login_required
@tutor_required
def student_attendance(student_id):
    """View student's attendance with this tutor"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    student = Student.query.get_or_404(student_id)
    
    # Verify tutor has access to this student
    student_classes = Class.query.filter_by(tutor_id=tutor.id).all()
    has_access = any(student.id in cls.get_students() for cls in student_classes)
    
    if not has_access:
        flash('You do not have access to view this student.', 'error')
        return redirect(url_for('tutor.my_students'))
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(
        tutor_id=tutor.id, 
        student_id=student.id
    ).order_by(Attendance.class_date.desc()).all()
    
    # Get attendance summary
    attendance_summary = Attendance.get_attendance_summary(student_id=student.id, tutor_id=tutor.id)
    
    return render_template('tutor/student_attendance.html',
                         student=student,
                         attendance_records=attendance_records,
                         attendance_summary=attendance_summary,
                         tutor=tutor)

@bp.route('/class/<int:class_id>/mark-attendance', methods=['POST'])
@login_required
@tutor_required
def mark_class_attendance(class_id):
    """Mark attendance for a specific class with automatic calculations"""
    tutor = get_current_tutor()
    if not tutor:
        return jsonify({'error': 'Tutor profile not found'}), 400
    
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    try:
        data = request.get_json()
        current_time = datetime.now()
        
        # Get or create attendance records for this class
        attendance_records = Attendance.query.filter_by(class_id=class_id).all()
        
        if not attendance_records:
            # Create attendance records for all students in this class
            student_ids = class_obj.get_students()
            for student_id in student_ids:
                attendance = Attendance(
                    class_id=class_id,
                    tutor_id=tutor.id,
                    student_id=student_id,
                    class_date=class_obj.scheduled_date,
                    scheduled_start=class_obj.scheduled_time,
                    scheduled_end=class_obj.end_time if hasattr(class_obj, 'end_time') else None
                )
                db.session.add(attendance)
            db.session.commit()
            attendance_records = Attendance.query.filter_by(class_id=class_id).all()
        
        # Mark tutor attendance
        tutor_present = data.get('tutor_present', True)
        tutor_join_time = current_time if tutor_present else None
        tutor_leave_time = data.get('tutor_leave_time')
        if tutor_leave_time:
            tutor_leave_time = datetime.strptime(tutor_leave_time, '%H:%M')
            tutor_leave_time = tutor_leave_time.replace(
                year=current_time.year,
                month=current_time.month,
                day=current_time.day
            )
        
        # Process each student's attendance
        students_attendance = data.get('students', [])
        
        penalty_settings = {
            'late_penalty_per_minute': 10,  # ₹10 per minute late
            'absence_penalty': 500,  # ₹500 for unexcused absence
            'early_leave_penalty_per_minute': 5  # ₹5 per minute early leave
        }
        
        total_penalties = 0
        attendance_summary = []
        
        for attendance in attendance_records:
            # Mark tutor attendance on each record
            attendance.mark_tutor_attendance(
                present=tutor_present,
                join_time=tutor_join_time,
                leave_time=tutor_leave_time,
                absence_reason=data.get('tutor_absence_reason')
            )
            
            # Find student attendance data
            student_data = next(
                (s for s in students_attendance if s.get('student_id') == attendance.student_id),
                None
            )
            
            if student_data:
                student_present = student_data.get('present', False)
                student_join_time = None
                student_leave_time = None
                
                if student_present:
                    # Parse join time
                    join_time_str = student_data.get('join_time')
                    if join_time_str:
                        join_time_parsed = datetime.strptime(join_time_str, '%H:%M')
                        student_join_time = join_time_parsed.replace(
                            year=current_time.year,
                            month=current_time.month,
                            day=current_time.day
                        )
                    
                    # Parse leave time
                    leave_time_str = student_data.get('leave_time')
                    if leave_time_str:
                        leave_time_parsed = datetime.strptime(leave_time_str, '%H:%M')
                        student_leave_time = leave_time_parsed.replace(
                            year=current_time.year,
                            month=current_time.month,
                            day=current_time.day
                        )
                
                # Mark student attendance
                attendance.mark_student_attendance(
                    present=student_present,
                    join_time=student_join_time,
                    leave_time=student_leave_time,
                    absence_reason=student_data.get('absence_reason'),
                    engagement=student_data.get('engagement')
                )
            
            # Calculate actual duration
            attendance.calculate_actual_duration()
            
            # Calculate tutor penalty (automatic calculations)
            penalty = attendance.calculate_tutor_penalty(penalty_settings)
            total_penalties += penalty
            
            # Set marking details
            attendance.marked_by = current_user.id
            attendance.marked_at = current_time
            
            # Add to summary
            attendance_summary.append({
                'student_id': attendance.student_id,
                'student_name': attendance.student.full_name,
                'present': attendance.student_present,
                'late_minutes': attendance.student_late_minutes,
                'engagement': attendance.student_engagement,
                'tutor_penalty': penalty
            })
        
        # Update class status
        if class_obj.status == 'ongoing':
            class_obj.status = 'completed'
            class_obj.actual_end_time = current_time
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Attendance marked successfully',
            'summary': {
                'total_students': len(attendance_records),
                'present_students': sum(1 for a in attendance_records if a.student_present),
                'absent_students': sum(1 for a in attendance_records if not a.student_present),
                'tutor_late_minutes': attendance_records[0].tutor_late_minutes if attendance_records else 0,
                'total_penalties': total_penalties,
                'class_duration': attendance_records[0].class_duration_actual if attendance_records else 0
            },
            'attendance_details': attendance_summary
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error marking attendance: {str(e)}'}), 500


@bp.route('/class/<int:class_id>/attendance-form')
@login_required
@tutor_required
def attendance_form(class_id):
    """Show attendance marking form for a class"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    # Get students for this class
    student_ids = class_obj.get_students()
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Check if attendance already marked
    existing_attendance = Attendance.query.filter_by(class_id=class_id).first()
    
    return render_template('tutor/mark_attendance.html',
                         class_obj=class_obj,
                         students=students,
                         existing_attendance=existing_attendance,
                         current_time=datetime.now())


@bp.route('/availability')
@login_required
@tutor_required
def availability():
    """Tutor availability management page"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    current_availability = tutor.get_availability()
    
    return render_template('tutor/availability.html', 
                         tutor=tutor, 
                         availability=current_availability)

@bp.route('/availability/update', methods=['POST'])
@login_required
@tutor_required
def update_availability():
    """Update tutor availability"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    try:
        # Get form data and build availability dict
        availability = {}
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day in days:
            day_slots = []
            
            # Get start and end times for each day
            start_times = request.form.getlist(f'{day}_start')
            end_times = request.form.getlist(f'{day}_end')
            
            # Pair up start and end times
            for start_time, end_time in zip(start_times, end_times):
                if start_time and end_time:
                    # Validate time format and order
                    if start_time < end_time:
                        day_slots.append({
                            'start': start_time,
                            'end': end_time
                        })
            
            if day_slots:
                availability[day] = day_slots
        
        # Update tutor availability
        tutor.set_availability(availability)
        
        # Update status to indicate availability is set
        if tutor.status == 'pending' and availability:
            tutor.status = 'active'
        
        db.session.commit()
        flash('Availability updated successfully! You can now be assigned to classes.', 'success')
        
        return redirect(url_for('tutor.availability'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating availability: {str(e)}', 'error')
        return redirect(url_for('tutor.availability'))

@bp.route('/api/check-availability')
@login_required
@tutor_required
def check_availability():
    """Check if tutor is available for specific time"""
    tutor = get_current_tutor()
    if not tutor:
        return jsonify({'available': False, 'reason': 'Tutor not found'})
    
    day = request.args.get('day')  # monday, tuesday, etc.
    time = request.args.get('time')  # HH:MM format
    
    if not day or not time:
        return jsonify({'available': False, 'reason': 'Missing day or time'})
    
    is_available = tutor.is_available_at(day, time)
    
    return jsonify({
        'available': is_available,
        'reason': 'Available' if is_available else 'Not available at this time'
    })

@bp.route('/availability-status')
@login_required
@tutor_required
def availability_status():
    """Check if tutor has set availability"""
    tutor = get_current_tutor()
    if not tutor:
        return jsonify({'has_availability': False})
    
    availability = tutor.get_availability()
    return jsonify({
        'has_availability': bool(availability),
        'status': tutor.status,
        'can_teach': tutor.status == 'active' and bool(availability)
    })
    
    
# ADD these new routes to app/routes/tutor.py

@bp.route('/class/<int:class_id>/start-with-auto-attendance', methods=['POST'])
@login_required
@tutor_required
def start_class_with_auto_attendance(class_id):
    """Start a class with automatic attendance marking"""
    tutor = get_current_tutor()
    if not tutor:
        return jsonify({'error': 'Tutor profile not found'}), 400
    
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    # Validate class can be started
    if class_obj.status != 'scheduled':
        return jsonify({'error': 'Class cannot be started'}), 400
    
    # Time validation - only allow starting if it's class time
    current_time = get_local_time()  # Use timezone-aware time
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    # DEBUG: Log the time calculations
    print(f"DEBUG - Start Class Validation:")
    print(f"  Current time (get_local_time): {current_time}")
    print(f"  Class datetime: {class_datetime}")
    print(f"  Class date: {class_obj.scheduled_date}")
    print(f"  Class time: {class_obj.scheduled_time}")
    print(f"  System time (datetime.now): {datetime.now()}")
    
    # Allow starting 5 minutes before scheduled time
    if current_time < (class_datetime - timedelta(minutes=5)):
        minutes_remaining = calculate_time_until(class_datetime)  # Use the utility function
        print(f"  Minutes remaining calculated: {minutes_remaining}")
        print(f"  Time difference (seconds): {(class_datetime - current_time).total_seconds()}")
        return jsonify({
            'error': f'Class cannot be started yet. Please wait {minutes_remaining} more minutes.',
            'minutes_remaining': minutes_remaining
        }), 400
    
    # Check if it's today's class
    if class_obj.scheduled_date != current_time.date():
        return jsonify({'error': 'Can only start today\'s classes'}), 400
    
    try:
        # Start the class
        class_obj.start_class()
        class_obj.actual_start_time = current_time
        
        # Get all students for this class
        student_ids = class_obj.get_students()
        
        # Create or update attendance records with AUTO-ATTENDANCE
        attendance_records = Attendance.query.filter_by(class_id=class_id).all()
        
        if not attendance_records:
            # Create new attendance records
            for student_id in student_ids:
                attendance = Attendance(
                    class_id=class_id,
                    tutor_id=tutor.id,
                    student_id=student_id,
                    class_date=class_obj.scheduled_date,
                    scheduled_start=class_obj.scheduled_time,
                    scheduled_end=class_obj.end_time
                )
                db.session.add(attendance)
            
            db.session.flush()  # Get the IDs
            attendance_records = Attendance.query.filter_by(class_id=class_id).all()
        
        # AUTO-MARK ATTENDANCE FOR ALL
        students_marked = 0
        for attendance in attendance_records:
            # Mark tutor as present
            attendance.mark_tutor_attendance(
                present=True,
                join_time=current_time,
                absence_reason=None
            )
            
            # AUTO-MARK ALL STUDENTS AS PRESENT
            attendance.mark_student_attendance(
                present=True,
                join_time=current_time,  # Will calculate lateness automatically
                absence_reason=None,
                engagement='medium'  # Default engagement level
            )
            
            # Calculate actual durations and lateness
            attendance.calculate_actual_duration()
            attendance.marked_by = current_user.id
            attendance.marked_at = current_time
            students_marked += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Class started successfully! Auto-marked {students_marked} students as present.',
            'class_status': 'ongoing',
            'students_marked': students_marked,
            'auto_attendance': True
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error starting class with auto-attendance: {str(e)}")
        return jsonify({'error': f'Error starting class: {str(e)}'}), 500


@bp.route('/class/<int:class_id>/complete-workflow')
@login_required
@tutor_required
def complete_class_workflow(class_id):
    """Show class completion workflow page"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status not in ['ongoing', 'scheduled']:
        flash('Class cannot be completed.', 'error')
        return redirect(url_for('tutor.class_details', class_id=class_id))
    
    # Get students and their current attendance status
    student_ids = class_obj.get_students()
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    # Create student-attendance mapping
    student_attendance_map = {}
    for attendance in attendance_records:
        student_attendance_map[attendance.student_id] = attendance
    
    return render_template('tutor/complete_class_workflow.html',
                         class_obj=class_obj,
                         students=students,
                         attendance_records=attendance_records,
                         student_attendance_map=student_attendance_map,
                         current_time=datetime.now())


@bp.route('/class/<int:class_id>/complete-with-review', methods=['POST'])
@login_required
@tutor_required
def complete_class_with_review(class_id):
    """Complete class with attendance review and start video upload timer"""
    tutor = get_current_tutor()
    if not tutor:
        return jsonify({'error': 'Tutor profile not found'}), 400
    
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status not in ['ongoing', 'scheduled']:
        return jsonify({'error': 'Class cannot be completed'}), 400
    
    try:
        data = request.get_json()
        current_time = datetime.now()
        
        # Update class status and timing
        class_obj.status = 'completed'
        class_obj.completion_status = 'completed'
        class_obj.actual_end_time = current_time
        class_obj.class_notes = data.get('class_notes', '')
        
        # Process attendance updates
        attendance_updates = data.get('attendance_updates', [])
        attendance_records = Attendance.query.filter_by(class_id=class_id).all()
        
        for attendance in attendance_records:
            # Find update for this student
            student_update = next(
                (update for update in attendance_updates 
                 if update.get('student_id') == attendance.student_id),
                None
            )
            
            if student_update:
                # Update attendance based on tutor review
                attendance.mark_student_attendance(
                    present=student_update.get('present', True),
                    join_time=attendance.student_join_time,  # Keep original join time
                    leave_time=current_time,
                    absence_reason=student_update.get('absence_reason'),
                    engagement=student_update.get('engagement', 'medium')
                )
            
            # Update tutor leave time
            attendance.mark_tutor_attendance(
                present=True,
                join_time=attendance.tutor_join_time,
                leave_time=current_time,
                absence_reason=None
            )
            
            # Recalculate durations and penalties
            attendance.calculate_actual_duration()
            attendance.calculate_tutor_penalty()
            attendance.verified_by = current_user.id
            attendance.verified_at = current_time
        
        # START VIDEO UPLOAD TIMER (24 hours)
        from app.utils.video_upload_scheduler import schedule_video_upload_reminders
        schedule_video_upload_reminders(class_id, tutor.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class completed successfully! Please upload your video within 24 hours.',
            'video_upload_deadline': (current_time + timedelta(hours=24)).isoformat(),
            'redirect_url': f'/tutor/class/{class_id}/upload-video?deadline=true'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error completing class: {str(e)}")
        return jsonify({'error': f'Error completing class: {str(e)}'}), 500


@bp.route('/class/<int:class_id>/upload-video')
@login_required
@tutor_required
def upload_video_page(class_id):
    """Video upload page with deadline tracking"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status != 'completed':
        flash('Can only upload videos for completed classes.', 'error')
        return redirect(url_for('tutor.class_details', class_id=class_id))
    
    # Check if video already uploaded
    if class_obj.video_link:
        flash('Video already uploaded for this class.', 'success')
        return redirect(url_for('tutor.class_details', class_id=class_id))
    
    # Calculate time remaining for upload (24 hours from completion)
    if class_obj.actual_end_time:
        deadline = class_obj.actual_end_time + timedelta(hours=24)
        time_remaining = deadline - datetime.now()
        
        if time_remaining.total_seconds() <= 0:
            flash('Video upload deadline has passed. Please contact admin.', 'error')
            urgent_deadline = True
        else:
            urgent_deadline = False
    else:
        deadline = None
        time_remaining = None
        urgent_deadline = False
    
    return render_template('tutor/upload_video.html',
                         class_obj=class_obj,
                         deadline=deadline,
                         time_remaining=time_remaining,
                         urgent_deadline=urgent_deadline,
                         deadline_param=request.args.get('deadline'))


@bp.route('/class/<int:class_id>/upload-video-ajax', methods=['POST'])
@login_required
@tutor_required
def upload_video_ajax(class_id):
    """Handle video upload via AJAX with progress tracking"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400
    
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No video file selected'}), 400
    
    # Check file type and size
    allowed_extensions = {'mp4', 'avi', 'mov', 'wmv', 'mkv', 'webm'}
    if not ('.' in video_file.filename and 
            video_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid video format. Please use MP4, AVI, MOV, WMV, MKV, or WEBM'}), 400
    
    # Check file size (limit to 1GB for better video support)
    max_size = 1024 * 1024 * 1024  # 1GB
    if hasattr(video_file, 'content_length') and video_file.content_length > max_size:
        return jsonify({'error': 'File size too large. Maximum 1GB allowed.'}), 400
    
    # Log upload attempt
    print(f"AJAX Upload: Starting video upload for class {class_id}, tutor {tutor.id}")
    print(f"File: {video_file.filename}, Size: {getattr(video_file, 'content_length', 'Unknown')} bytes")
    
    try:
        tutor_id = tutor.id
        
        print(f"AJAX Upload: Uploading attendance video for class {class_id}, tutor {tutor_id}")
        
        # Use organized upload for attendance videos
        s3_url = upload_organized_file_to_s3(
            file=video_file,
            file_type='video',
            category='attendance',
            user_id=tutor_id,
            class_id=class_id
        )
        
        if not s3_url:
            raise ValueError("Video upload to S3 failed")
        
        # Update class record
        class_obj.video_link = s3_url
        class_obj.video_uploaded_at = datetime.now()
        
        # Cancel any pending upload reminders
        try:
            from app.utils.video_upload_scheduler import cancel_video_upload_reminders
            cancel_video_upload_reminders(class_id)
        except ImportError:
            print("Video upload scheduler not available")
        
        # Calculate and update tutor rating based on compliance
        try:
            from app.utils.rating_calculator import update_tutor_rating
            update_tutor_rating(tutor.id)
        except ImportError:
            print("Rating calculator not available")
        
        db.session.commit()
        
        print(f"AJAX Upload successful for class {class_id}: {s3_url}")
        
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully! Class is now complete.',
            'video_url': s3_url,
            'upload_time': datetime.now().isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in upload_video_ajax: {str(e)}")
        current_app.logger.error(f"AJAX video upload error for class {class_id}: {str(e)}")
        return jsonify({'error': f'Video upload failed: {str(e)}'}), 500


# ADD this helper function to calculate time until class starts
def get_time_until_class(class_obj):
    """Calculate minutes until class starts"""
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    return calculate_time_until(class_datetime)


def can_start_class_now(class_obj):
    """Check if class can be started now based on time"""
    current_time = get_local_time()  # Use timezone-aware time
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    # Allow starting 5 minutes before scheduled time
    earliest_start = class_datetime - timedelta(minutes=5)
    
    # Must be today's class and within time window
    is_today = class_obj.scheduled_date == current_time.date()
    is_time_reached = current_time >= earliest_start
    
    return is_today and is_time_reached


# ============ TUTOR TIMETABLE FUNCTIONALITY ============

@bp.route('/my-timetable')
@login_required
@tutor_required
def my_timetable():
    """Tutor's weekly timetable view"""
    try:
        print(f"✅ Tutor timetable route accessed by user: {current_user.username}")
        # Get tutor profile
        tutor = get_current_tutor()
        if not tutor:
            print(f"❌ No tutor profile found for user: {current_user.username}")
            flash('Tutor profile not found', 'error')
            return redirect(url_for('dashboard.index'))
            
        print(f"✅ Tutor profile found: {tutor.id}")
        return render_template('tutor/my_timetable.html', tutor=tutor)
        
    except Exception as e:
        print(f"❌ Error loading tutor timetable: {str(e)}")
        flash('Error loading timetable', 'error')
        return redirect(url_for('dashboard.index'))


@bp.route('/api/weekly-timetable')
@login_required
@tutor_required
def api_weekly_timetable():
    """Get tutor's weekly timetable data"""
    try:
        print(f"🔥 API timetable route accessed by user: {current_user.username}")
        # Get tutor profile
        tutor = get_current_tutor()
        if not tutor:
            print(f"❌ No tutor profile found for API user: {current_user.username}")
            return jsonify({'success': False, 'error': 'Tutor profile not found'}), 404
            
        # Get week offset from query params (0 = current week, -1 = previous, +1 = next)
        week_offset = request.args.get('week_offset', 0, type=int)
        
        # Calculate the start of the week (Monday)
        today = datetime.now().date()
        days_since_monday = today.weekday()  # 0 = Monday, 6 = Sunday
        week_start = today - timedelta(days=days_since_monday) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)  # Sunday
        
        # Get tutor's classes for the week
        classes = Class.query.filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date >= week_start,
            Class.scheduled_date <= week_end,
            Class.status.in_(['scheduled', 'ongoing', 'completed'])
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        # Organize classes by day
        weekly_schedule = {
            'Monday': [],
            'Tuesday': [],
            'Wednesday': [],
            'Thursday': [],
            'Friday': [],
            'Saturday': [],
            'Sunday': []
        }
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for cls in classes:
            day_name = day_names[cls.scheduled_date.weekday()]
            
            # Get student info based on class type
            student_info = "No Student"
            if cls.class_type == 'one_on_one' and cls.primary_student_id:
                student = Student.query.get(cls.primary_student_id)
                if student:
                    student_info = student.full_name
            elif cls.class_type == 'group' and cls.students:
                try:
                    student_ids = json.loads(cls.students)
                    if isinstance(student_ids, list) and student_ids:
                        students = Student.query.filter(Student.id.in_(student_ids)).all()
                        student_names = [s.full_name for s in students]
                        student_info = f"Group: {', '.join(student_names[:2])}" + (f" +{len(student_names)-2} more" if len(student_names) > 2 else "")
                except:
                    student_info = "Group Class"
            elif cls.class_type == 'demo':
                student_info = "Demo Class"
            
            class_data = {
                'id': cls.id,
                'subject': cls.subject,
                'student': student_info,
                'time': cls.scheduled_time.strftime('%I:%M %p'),
                'end_time': (datetime.combine(cls.scheduled_date, cls.scheduled_time) + 
                           timedelta(minutes=cls.duration)).time().strftime('%I:%M %p'),
                'duration': cls.duration,
                'status': cls.status,
                'class_type': cls.class_type,
                'grade': cls.grade or '',
                'board': cls.board or '',
                'platform': cls.platform or '',
                'meeting_link': cls.meeting_link or '',
                'date': cls.scheduled_date.strftime('%Y-%m-%d')
            }
            
            weekly_schedule[day_name].append(class_data)
        
        # Calculate date ranges for navigation
        week_dates = []
        for i in range(7):
            current_day = week_start + timedelta(days=i)
            week_dates.append({
                'date': current_day.strftime('%Y-%m-%d'),
                'day': day_names[i],
                'day_short': day_names[i][:3],
                'formatted': current_day.strftime('%b %d')
            })
        
        return jsonify({
            'success': True,
            'data': {
                'schedule': weekly_schedule,
                'week_dates': week_dates,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'week_title': f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}",
                'current_week_offset': week_offset,
                'total_classes': len(classes)
            }
        })
        
    except Exception as e:
        print(f"Error getting tutor weekly timetable: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

