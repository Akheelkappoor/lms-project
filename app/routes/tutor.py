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
    """View tutor's classes"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get filter parameters
    date_filter = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = Class.query.filter_by(tutor_id=tutor.id)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(scheduled_date=filter_date)
        except ValueError:
            pass
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Get paginated results
    classes = query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get today's classes
    today = date.today()
    todays_classes = Class.query.filter_by(
        tutor_id=tutor.id,
        scheduled_date=today
    ).order_by(Class.scheduled_time).all()
    
    return render_template('tutor/my_classes.html', 
                         classes=classes, todays_classes=todays_classes,
                         tutor=tutor)

@bp.route('/today-classes')
@login_required
@tutor_required
def today_classes():
    """View today's classes only"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    today = date.today()
    todays_classes = Class.query.filter_by(
        tutor_id=tutor.id,
        scheduled_date=today
    ).order_by(Class.scheduled_time).all()
    
    return render_template('tutor/today_classes.html', 
                         classes=todays_classes, tutor=tutor)

@bp.route('/class/<int:class_id>')
@login_required
@tutor_required
def class_details(class_id):
    """View class details"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    # Get attendance record if exists
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    # Get student objects for this class
    students = class_obj.get_student_objects()
    
    return render_template('tutor/class_details.html', 
                         class_obj=class_obj, attendance_records=attendance_records,
                         students=students, tutor=tutor)

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
    
    return jsonify({'success': True, 'message': 'Class started successfully'})

@bp.route('/class/<int:class_id>/complete', methods=['POST'])
@login_required
@tutor_required
def complete_class(class_id):
    """Complete a class"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status not in ['scheduled', 'ongoing']:
        return jsonify({'error': 'Class cannot be completed'}), 400
    
    completion_status = request.json.get('completion_status', 'completed')
    class_notes = request.json.get('class_notes', '')
    topics_covered = request.json.get('topics_covered', [])
    
    class_obj.complete_class(completion_status)
    class_obj.class_notes = class_notes
    class_obj.set_topics_covered(topics_covered)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Class completed successfully'})

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
    """View tutor's students"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get unique students from classes
    student_ids = db.session.query(Class.primary_student_id)\
        .filter_by(tutor_id=tutor.id)\
        .distinct().all()
    
    student_ids = [sid[0] for sid in student_ids if sid[0]]
    
    # Also get students from group classes
    group_classes = Class.query.filter_by(tutor_id=tutor.id, class_type='group').all()
    for cls in group_classes:
        student_ids.extend(cls.get_students())
    
    # Remove duplicates
    student_ids = list(set(student_ids))
    
    # Get student objects
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Get additional info for each student
    student_info = []
    for student in students:
        # Count classes with this student
        total_classes = Class.query.filter(
            Class.tutor_id == tutor.id,
            ((Class.primary_student_id == student.id) | 
             (Class.students.contains(str(student.id))))
        ).count()
        
        # Get attendance summary
        attendance_summary = Attendance.get_attendance_summary(
            tutor_id=tutor.id, 
            student_id=student.id
        )
        
        student_info.append({
            'student': student,
            'total_classes': total_classes,
            'attendance': attendance_summary
        })
    
    return render_template('tutor/my_students.html', 
                         student_info=student_info, tutor=tutor)

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
        # Save video file
        filename = secure_filename(video_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = f"class_{class_id}_{timestamp}{filename}"
        
        video_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos', filename)
        os.makedirs(os.path.dirname(video_path), exist_ok=True)
        video_file.save(video_path)
        
        # Update class record
        class_obj.video_link = filename
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