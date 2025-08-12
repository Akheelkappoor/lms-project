from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os
from app import db
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from functools import wraps
from app.utils.helper import upload_file_to_s3
from flask_moment import Moment

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
def my_classes():
    """View tutor's classes with enhanced time-based controls"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Check if tutor has set availability
    availability = tutor.get_availability()
    if not availability:
        flash('Please set your availability first before viewing classes.', 'warning')
        return redirect(url_for('tutor.availability'))
    
    # Get current time and date
    current_time = datetime.now()
    today = current_time.date()
    
    # Pagination and filtering
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query with filters
    query = Class.query.filter_by(tutor_id=tutor.id)
    
    # Date filter
    if request.args.get('date'):
        try:
            filter_date = datetime.strptime(request.args.get('date'), '%Y-%m-%d').date()
            query = query.filter(Class.scheduled_date == filter_date)
        except ValueError:
            flash('Invalid date format', 'error')
    
    # Status filter
    if request.args.get('status'):
        query = query.filter(Class.status == request.args.get('status'))
    
    # Subject filter
    if request.args.get('subject'):
        query = query.filter(Class.subject == request.args.get('subject'))
    
    # Order by date and time
    query = query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc())
    
    # Paginate
    classes = query.paginate(
        page=page, per_page=per_page, 
        error_out=False
    )
    
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
        time_until = max(0, int((class_datetime - current_time).total_seconds() / 60))
        
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
                         classes=classes,
                         todays_classes=todays_classes_with_time,
                         tutor=tutor,
                         filtered_args=filtered_args,
                         current_time=current_time,
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
    
    # Get current time information
    current_time = datetime.now()
    class_datetime = datetime.combine(class_item.scheduled_date, class_item.scheduled_time)
    is_today = class_item.scheduled_date == current_time.date()
    is_time_reached = current_time >= (class_datetime - timedelta(minutes=5))
    time_until_class = max(0, int((class_datetime - current_time).total_seconds() / 60))
    
    # Get students for this class
    student_ids = class_item.get_students()
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    # Get related classes (same subject, recent)
    related_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.subject == class_item.subject,
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
    
    # Get summary statistics
    summary = Attendance.get_attendance_summary(tutor_id=tutor.id)
    
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
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(video_file.filename)
            filename = f"class_{class_id}_{timestamp}_{filename}"
            
            s3_url = upload_file_to_s3(video_file, folder=f"{current_app.config['UPLOAD_FOLDER']}/videos")
            
            if not s3_url:
                raise ValueError("Video upload failed.")
            
            # Update class record with S3 video link
            class_obj.video_link = s3_url
            db.session.commit()
                
        return jsonify({'success': True, 'message': 'Video uploaded successfully'})
        
    except Exception as e:
        return jsonify({'error': 'Error uploading video'}), 500

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
    current_time = datetime.now()
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    # Allow starting 5 minutes before scheduled time
    if current_time < (class_datetime - timedelta(minutes=5)):
        minutes_remaining = int((class_datetime - current_time).total_seconds() / 60)
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
        
        # START VIDEO UPLOAD TIMER (2 hours)
        from app.utils.video_upload_scheduler import schedule_video_upload_reminders
        schedule_video_upload_reminders(class_id, tutor.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class completed successfully! Please upload your video within 2 hours.',
            'video_upload_deadline': (current_time + timedelta(hours=2)).isoformat(),
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
    
    # Calculate time remaining for upload (2 hours from completion)
    if class_obj.actual_end_time:
        deadline = class_obj.actual_end_time + timedelta(hours=2)
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
    
    # Check file size (limit to 500MB)
    if hasattr(video_file, 'content_length') and video_file.content_length > 500 * 1024 * 1024:
        return jsonify({'error': 'File size too large. Maximum 500MB allowed.'}), 400
    
    try:
        # Generate secure filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = secure_filename(video_file.filename)
        filename = f"class_{class_id}_{timestamp}_{original_filename}"
        
        # Upload to S3
        s3_url = upload_file_to_s3(
            video_file, 
            folder=f"{current_app.config['UPLOAD_FOLDER']}/videos/classes"
        )
        
        if not s3_url:
            raise ValueError("Video upload to S3 failed")
        
        # Update class record
        class_obj.video_link = s3_url
        class_obj.video_uploaded_at = datetime.now()
        
        # Cancel any pending upload reminders
        from app.utils.video_upload_scheduler import cancel_video_upload_reminders
        cancel_video_upload_reminders(class_id)
        
        # Calculate and update tutor rating based on compliance
        from app.utils.rating_calculator import update_tutor_rating
        update_tutor_rating(tutor.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully! Class is now complete.',
            'video_url': s3_url,
            'upload_time': datetime.now().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error uploading video: {str(e)}")
        return jsonify({'error': f'Error uploading video: {str(e)}'}), 500


# ADD this helper function to calculate time until class starts
def get_time_until_class(class_obj):
    """Calculate minutes until class starts"""
    current_time = datetime.now()
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    if current_time >= class_datetime:
        return 0
    
    diff_seconds = (class_datetime - current_time).total_seconds()
    return max(0, int(diff_seconds / 60))


def can_start_class_now(class_obj):
    """Check if class can be started now based on time"""
    current_time = datetime.now()
    class_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    
    # Allow starting 5 minutes before scheduled time
    earliest_start = class_datetime - timedelta(minutes=5)
    
    # Must be today's class and within time window
    is_today = class_obj.scheduled_date == current_time.date()
    is_time_reached = current_time >= earliest_start
    
    return is_today and is_time_reached

