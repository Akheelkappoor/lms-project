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
    
    # Check if tutor has set availability
    availability = tutor.get_availability()
    if not availability:
        flash('Please set your availability first before viewing classes.', 'warning')
        return redirect(url_for('tutor.availability'))
    
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
    
    filtered_args = request.args.to_dict()
    filtered_args.pop('page', None)
    
    return render_template('tutor/my_classes.html', 
                         classes=classes, todays_classes=todays_classes,
                         tutor=tutor, filtered_args=filtered_args)

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
    """View detailed information about a specific class"""
    tutor = Tutor.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get the class and verify it belongs to this tutor
    class_item = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    # Get students for this class
    student_ids = class_item.get_students()
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    # Get attendance records if class has started
    attendance_records = []
    if class_item.status in ['ongoing', 'completed']:
        attendance_records = Attendance.query.filter_by(class_id=class_item.id).all()
    
    # Get class feedback if completed
    class_feedback = None
    if class_item.status == 'completed':
        # You might have a ClassFeedback model
        # class_feedback = ClassFeedback.query.filter_by(class_id=class_item.id).first()
        pass
    
    # Get related classes (same subject, same students)
    related_classes = Class.query.filter(
        Class.tutor_id == tutor.id,
        Class.subject == class_item.subject,
        Class.id != class_item.id
    ).order_by(Class.scheduled_date.desc()).limit(5).all()
    
    return render_template('tutor/class_details.html',
                         class_item=class_item,
                         students=students,
                         attendance_records=attendance_records,
                         class_feedback=class_feedback,
                         related_classes=related_classes,
                         datetime=datetime)

@bp.route('/class/<int:class_id>/start', methods=['POST'])
@login_required
@tutor_required
def start_class(class_id):
    """Enhanced start class with auto-attendance and penalty calculation"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status != 'scheduled':
        return jsonify({'error': 'Class cannot be started'}), 400
    
    current_time = datetime.now()
    
    # Calculate if tutor is late
    scheduled_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
    late_minutes = 0
    late_penalty = 0
    
    if current_time > scheduled_datetime:
        late_minutes = int((current_time - scheduled_datetime).total_seconds() / 60)
        if late_minutes > 2:  # 2-minute grace period
            late_penalty = (late_minutes - 2) * 10  # ₹10 per minute
    
    # Start the class (your existing logic)
    class_obj.start_class()
    
    # Create attendance records if they don't exist (your existing logic)
    existing_attendance = Attendance.query.filter_by(class_id=class_id).first()
    if not existing_attendance:
        Attendance.create_attendance_record(class_obj)
    
    # 🔥 NEW: Auto-mark tutor attendance with timing
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    for attendance in attendance_records:
        attendance.mark_tutor_attendance(
            present=True,
            join_time=current_time,
            leave_time=None,  # Will be set when completing
            absence_reason=None
        )
        
        # Set late minutes and penalty
        attendance.tutor_late_minutes = late_minutes
        if late_penalty > 0:
            attendance.penalty_amount = late_penalty
            attendance.penalty_reason = f"Late arrival: {late_minutes} minutes"
            attendance.tutor_penalty_applied = True
    
    db.session.commit()
    
    # 🔥 NEW: Return enhanced response with meeting link
    response_data = {
        'success': True, 
        'message': 'Class started successfully',
        'meeting_link': class_obj.meeting_link,
        'auto_redirect': True,
        'timing_info': {
            'started_at': current_time.strftime('%H:%M'),
            'late_minutes': late_minutes,
            'penalty_amount': late_penalty,
            'scheduled_duration': class_obj.duration
        }
    }
    
    return jsonify(response_data)


@bp.route('/class/<int:class_id>/complete', methods=['POST'])
@login_required
@tutor_required
def complete_class(class_id):
    """Enhanced complete class with early completion detection and video upload"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if class_obj.status not in ['scheduled', 'ongoing']:
        return jsonify({'error': 'Class cannot be completed'}), 400
    
    current_time = datetime.now()
    
    # Calculate actual duration
    if class_obj.actual_start_time:
        actual_duration = int((current_time - class_obj.actual_start_time).total_seconds() / 60)
    else:
        # Fallback if start time not recorded
        scheduled_start = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
        actual_duration = int((current_time - scheduled_start).total_seconds() / 60)
    
    # Check for early completion
    scheduled_duration = class_obj.duration
    early_completion_minutes = 0
    early_penalty = 0
    is_early = False
    
    if actual_duration < (scheduled_duration * 0.9):  # Less than 90% of scheduled time
        early_completion_minutes = scheduled_duration - actual_duration
        early_penalty = early_completion_minutes * 5  # ₹5 per minute early
        is_early = True
    
    # Get completion data from request
    data = request.get_json() or {}
    completion_status = data.get('completion_status', 'completed')
    class_notes = data.get('class_notes', '')
    topics_covered = data.get('topics_covered', [])
    early_reason = data.get('early_reason', '') if is_early else ''
    student_attendance_data = data.get('student_attendance', [])
    
    # Complete the class (your existing logic)
    class_obj.complete_class(completion_status)
    class_obj.class_notes = class_notes
    class_obj.set_topics_covered(topics_covered)
    
    # 🔥 NEW: Set video upload deadline (2 hours from now)
    class_obj.video_upload_deadline = current_time + timedelta(hours=2)
    class_obj.video_upload_status = 'pending'
    
    # 🔥 NEW: Update attendance records with completion timing
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    for attendance in attendance_records:
        # Update tutor leave time
        attendance.tutor_leave_time = current_time
        attendance.class_duration_actual = actual_duration
        
        # Apply early completion penalty
        if is_early:
            existing_penalty = attendance.penalty_amount or 0
            attendance.penalty_amount = existing_penalty + early_penalty
            attendance.tutor_early_leave_minutes = early_completion_minutes
            penalty_reason = attendance.penalty_reason or ""
            attendance.penalty_reason = f"{penalty_reason}; Early completion: {early_completion_minutes} min"
            attendance.tutor_penalty_applied = True
        
        # 🔥 NEW: Mark student attendance if provided
        student_data = next(
            (s for s in student_attendance_data if s.get('student_id') == attendance.student_id), 
            None
        )
        
        if student_data:
            attendance.mark_student_attendance(
                present=student_data.get('present', True),
                join_time=class_obj.actual_start_time,  # Assume joined when class started
                leave_time=current_time,
                absence_reason=student_data.get('absence_reason', ''),
                engagement=student_data.get('engagement', 'good')
            )
    
    db.session.commit()
    
    # 🔥 NEW: Schedule video upload warning (2 hours from now)
    # You'll need to add Celery task for this
    # schedule_video_upload_warning.delay(class_id, delay=7200)
    
    response_data = {
        'success': True,
        'message': 'Class completed successfully',
        'video_upload_required': True,
        'video_deadline': class_obj.video_upload_deadline.isoformat(),
        'completion_info': {
            'actual_duration': actual_duration,
            'scheduled_duration': scheduled_duration,
            'is_early_completion': is_early,
            'early_minutes': early_completion_minutes,
            'early_penalty': early_penalty,
            'total_penalty': sum(a.penalty_amount or 0 for a in attendance_records)
        },
        'redirect_to_upload': True
    }
    
    return jsonify(response_data)


@bp.route('/class/<int:class_id>/upload-video', methods=['GET', 'POST'])
@login_required
@tutor_required
def upload_class_video(class_id):
    """Upload class recording video"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    if request.method == 'GET':
        # Show upload form
        time_remaining = None
        if class_obj.video_upload_deadline:
            time_remaining = class_obj.video_upload_deadline - datetime.now()
            
        return render_template('tutor/upload_video.html', 
                             class_obj=class_obj, 
                             time_remaining=time_remaining)
    
    # Handle POST - file upload
    if 'video_file' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video_file']
    
    if video_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check deadline
    current_time = datetime.now()
    if class_obj.video_upload_deadline and current_time > class_obj.video_upload_deadline + timedelta(minutes=5):
        return jsonify({'error': 'Upload deadline has passed. Contact coordinator.'}), 403
    
    try:
        # Upload to storage (using your existing helper)
        filename = secure_filename(f"class_{class_id}_{int(current_time.timestamp())}.{video_file.filename.rsplit('.', 1)[1]}")
        video_url = upload_file_to_s3(video_file, filename)
        
        # Update class record
        class_obj.video_link = video_url
        class_obj.video_upload_status = 'uploaded'
        class_obj.video_upload_timestamp = current_time
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully!',
            'video_url': video_url
        })
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    
@bp.route('/class/<int:class_id>/contact-coordinator', methods=['POST'])
@login_required
@tutor_required
def contact_coordinator(class_id):
    """Contact coordinator when unable to upload video on time"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    data = request.get_json()
    reason = data.get('reason', 'Unable to upload video on time')
    
    # Create escalation record (you'll need to add this model)
    from app.models.escalation import Escalation
    
    escalation = Escalation(
        escalation_type='video_upload_delay',
        created_by=current_user.id,
        related_records=json.dumps({
            'class_id': class_id,
            'tutor_id': tutor.id,
            'reason': reason
        }),
        priority='high',
        status='open'
    )
    
    db.session.add(escalation)
    class_obj.video_upload_status = 'escalated'
    db.session.commit()
    
    # Send email to coordinator (you'll need to implement)
    # send_escalation_email(escalation.id)
    
    return jsonify({
        'success': True,
        'message': 'Coordinator has been notified. You will be contacted soon.',
        'escalation_id': escalation.id
    })
    
    
@bp.route('/class/<int:class_id>/attendance-summary')
@login_required
@tutor_required
def attendance_summary(class_id):
    """View detailed attendance summary for a class"""
    tutor = get_current_tutor()
    class_obj = Class.query.filter_by(id=class_id, tutor_id=tutor.id).first_or_404()
    
    attendance_records = Attendance.query.filter_by(class_id=class_id).all()
    
    summary = {
        'class_info': {
            'subject': class_obj.subject,
            'date': class_obj.scheduled_date.strftime('%Y-%m-%d'),
            'scheduled_time': class_obj.scheduled_time.strftime('%H:%M'),
            'actual_start': class_obj.actual_start_time.strftime('%H:%M') if class_obj.actual_start_time else None,
            'actual_end': class_obj.actual_end_time.strftime('%H:%M') if class_obj.actual_end_time else None,
            'duration': class_obj.duration,
            'status': class_obj.status
        },
        'tutor_attendance': {},
        'student_attendance': [],
        'penalties': {
            'total_amount': 0,
            'breakdown': []
        }
    }
    
    if attendance_records:
        # Tutor attendance info (same across all records)
        first_record = attendance_records[0]
        summary['tutor_attendance'] = {
            'present': first_record.tutor_present,
            'join_time': first_record.tutor_join_time.strftime('%H:%M') if first_record.tutor_join_time else None,
            'leave_time': first_record.tutor_leave_time.strftime('%H:%M') if first_record.tutor_leave_time else None,
            'late_minutes': first_record.tutor_late_minutes,
            'early_leave_minutes': first_record.tutor_early_leave_minutes,
            'penalty_amount': first_record.penalty_amount or 0,
            'penalty_reason': first_record.penalty_reason
        }
        
        # Student attendance details
        for record in attendance_records:
            student_info = {
                'student_id': record.student_id,
                'student_name': record.student.full_name if record.student else 'Unknown',
                'present': record.student_present,
                'join_time': record.student_join_time.strftime('%H:%M') if record.student_join_time else None,
                'leave_time': record.student_leave_time.strftime('%H:%M') if record.student_leave_time else None,
                'late_minutes': record.student_late_minutes,
                'early_leave_minutes': record.student_early_leave_minutes,
                'engagement': record.student_engagement,
                'absence_reason': record.student_absence_reason
            }
            summary['student_attendance'].append(student_info)
            
            # Add to penalty total
            if record.penalty_amount:
                summary['penalties']['total_amount'] += record.penalty_amount
                summary['penalties']['breakdown'].append({
                    'type': 'tutor_penalty',
                    'amount': record.penalty_amount,
                    'reason': record.penalty_reason
                })
    
    return render_template('tutor/attendance_summary.html', 
                         class_obj=class_obj, 
                         summary=summary)

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
    """Enhanced attendance view with filtering and analytics"""
    tutor = get_current_tutor()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get date filters from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    student_filter = request.args.get('student_id', type=int)
    status_filter = request.args.get('status')
    
    # Build query
    query = Attendance.query.filter_by(tutor_id=tutor.id)
    
    # Apply filters (your existing logic)
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.class_date >= start_date_obj)
        except ValueError:
            flash('Invalid start date format', 'error')
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.class_date <= end_date_obj)
        except ValueError:
            flash('Invalid end date format', 'error')
    
    # Apply other filters...
    if student_filter:
        query = query.filter_by(student_id=student_filter)
    
    if status_filter:
        if status_filter == 'present':
            query = query.filter_by(student_present=True, tutor_present=True)
        elif status_filter == 'absent':
            query = query.filter(
                or_(Attendance.student_present == False, Attendance.tutor_present == False)
            )
        elif status_filter == 'late':
            query = query.filter(
                or_(Attendance.student_late_minutes > 0, Attendance.tutor_late_minutes > 0)
            )
    
    # Get attendance records with pagination
    page = request.args.get('page', 1, type=int)
    attendance_records = query.order_by(Attendance.class_date.desc(), Attendance.scheduled_start.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    # Enhanced summary with penalty information
    summary = Attendance.get_attendance_summary(tutor_id=tutor.id)
    
    # Add penalty summary
    penalty_summary = db.session.query(
        func.sum(Attendance.penalty_amount).label('total_penalties'),
        func.count(Attendance.id).filter(Attendance.penalty_amount > 0).label('penalty_count')
    ).filter_by(tutor_id=tutor.id).first()
    
    summary.update({
        'total_penalties': penalty_summary.total_penalties or 0,
        'penalty_incidents': penalty_summary.penalty_count or 0
    })
    
    # Get students for filter dropdown
    student_ids = set()
    tutor_classes = Class.query.filter_by(tutor_id=tutor.id).all()
    for cls in tutor_classes:
        student_ids.update(cls.get_students())
    
    students = Student.query.filter(Student.id.in_(student_ids)).order_by(Student.full_name).all() if student_ids else []
    
    return render_template('tutor/attendance.html',
                         attendance_records=attendance_records,
                         summary=summary,
                         students=students,
                         tutor=tutor,
                         filters={
                             'start_date': start_date,
                             'end_date': end_date,
                             'student_id': student_filter,
                             'status': status_filter
                         })

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