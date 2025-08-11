# app/routes/export_email_timetable.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response, send_file
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import os
import json
import csv
import io
from werkzeug.utils import secure_filename
from app import db
from app.models.user import User
from app.models.department import Department  
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.routes.admin import admin_required
from app.utils.advanced_permissions import require_permission
from sqlalchemy import or_, and_, func

bp = Blueprint('export_email_timetable', __name__)

# ============ HELPER FUNCTIONS ============

def simplify_subject_name(full_subject_name):
    """
    Extract simplified subject name from full class names.
    Example: "HARSHINI-GRD10-CBSE-HINDI" becomes "HINDI"
    """
    if not full_subject_name:
        return full_subject_name
    
    # Remove common prefixes and extract subject
    name = str(full_subject_name).strip()
    
    # Split by dash and get the last part (subject)
    if '-' in name:
        parts = name.split('-')
        # Get the last part which should be the subject
        subject = parts[-1].strip()
        
        # Clean up common patterns
        subject = subject.replace('CBSE', '').replace('CLASS', '').replace('CLASSES', '')
        subject = subject.strip('-').strip()
        
        return subject if subject else name
    
    return name

def format_student_name_display(student_names):
    """Format student names for better display"""
    if not student_names:
        return []
    
    # If it's a string, split by comma
    if isinstance(student_names, str):
        names = [name.strip() for name in student_names.split(',')]
    else:
        names = student_names
    
    # Limit to first name only for space
    simplified_names = []
    for name in names:
        if name:
            # Get first name only
            first_name = name.split()[0] if ' ' in name else name
            simplified_names.append(first_name)
    
    return simplified_names[:5]  # Limit to 5 names for space

# ============ MAIN EXPORT PAGE ============

@bp.route('/export-timetable')
@login_required
@require_permission('class_management')
def export_timetable_page():
    """Main timetable export and email page"""
    try:
        # Get data for dropdowns
        departments = Department.query.filter_by(is_active=True).all()
        tutors = Tutor.query.join(User).filter(
            Tutor.status == 'active',
            User.is_active == True
        ).all()
        students = Student.query.filter(
            Student.is_active == True
        ).order_by(Student.full_name).limit(200).all()
        
        return render_template('admin/export_timetable.html',
                             departments=departments,
                             tutors=tutors,
                             students=students)
                             
    except Exception as e:
        print(f"Error loading export page: {str(e)}")
        flash('Error loading export page', 'error')
        return redirect(url_for('timetable.timetable'))

# ============ UTILITY FUNCTIONS ============

def get_filtered_classes(filters):
    """Get classes based on filters"""
    try:
        # Date range
        start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d').date()
        
        # Base query
        query = Class.query.filter(
            Class.scheduled_date >= start_date,
            Class.scheduled_date <= end_date
        )
        
        # Apply filters
        if filters.get('tutor_id'):
            query = query.filter(Class.tutor_id == filters['tutor_id'])
        
        if filters.get('department_id'):
            query = query.join(Tutor, Class.tutor_id == Tutor.id)\
                         .join(User, Tutor.user_id == User.id)\
                         .filter(User.department_id == filters['department_id'])
        
        if filters.get('subject'):
            query = query.filter(Class.subject.ilike(f"%{filters['subject']}%"))
        
        # Student filtering
        if filters.get('student_id'):
            student_id = int(filters['student_id'])
            all_classes = query.all()
            
            filtered_classes = []
            for cls in all_classes:
                if (cls.primary_student_id == student_id or 
                    cls.demo_student_id == student_id):
                    filtered_classes.append(cls)
                elif cls.students:
                    try:
                        student_ids = json.loads(cls.students)
                        if isinstance(student_ids, list) and student_id in student_ids:
                            filtered_classes.append(cls)
                    except:
                        pass
            
            return filtered_classes
        
        return query.order_by(Class.scheduled_date, Class.scheduled_time).all()
        
    except Exception as e:
        print(f"Error filtering classes: {str(e)}")
        return []

def format_student_timetable_data(classes, student_info, filters):
    """Format data for student timetable template with correct variable names"""
    try:
        from datetime import datetime, timedelta
        
        # Initialize timetable structure
        timetable_data = {
            'monday': {},
            'tuesday': {},
            'wednesday': {},
            'thursday': {},
            'friday': {},
            'saturday': {},
            'sunday': {}
        }
        
        time_slots = set()
        subjects_set = set()
        tutors_set = set()
        total_duration = 0
        
        # Process each class
        for cls in classes:
            # Get day of week (0=Monday, 6=Sunday)
            day_of_week = cls.scheduled_date.weekday()
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            day_name = day_names[day_of_week]
            
            # Format time
            if cls.scheduled_time:
                start_time = cls.scheduled_time.strftime('%H:%M')
                start_time_12hr = cls.scheduled_time.strftime('%I:%M %p')
                
                # Calculate end time
                if cls.duration:
                    start_datetime = datetime.combine(datetime.today(), cls.scheduled_time)
                    end_datetime = start_datetime + timedelta(minutes=cls.duration)
                    end_time_12hr = end_datetime.time().strftime('%I:%M %p')
                    total_duration += cls.duration
                else:
                    end_time_12hr = start_time_12hr
                    total_duration += 60  # Default 1 hour
            else:
                start_time = '00:00'
                start_time_12hr = '12:00 AM'
                end_time_12hr = '01:00 AM'
            
            time_slots.add(start_time)
            
            # Get tutor name
            tutor_name = 'No Tutor'
            if cls.tutor and cls.tutor.user:
                tutor_name = cls.tutor.user.full_name
                tutors_set.add(tutor_name)
            
            # Simplify subject name
            simplified_subject = simplify_subject_name(cls.subject)
            subjects_set.add(simplified_subject)
            
            # Create class info
            class_info = {
                'subject': simplified_subject,
                'tutor_name': tutor_name,
                'start_time': start_time_12hr,
                'end_time': end_time_12hr,
                'status': cls.status or 'scheduled'
            }
            
            # Add to timetable data
            if start_time not in timetable_data[day_name]:
                timetable_data[day_name][start_time] = []
            
            timetable_data[day_name][start_time].append(class_info)
        
        # Sort time slots
        sorted_time_slots = sorted(list(time_slots))
        
        # Calculate subject details
        subject_details = {}
        for subject in subjects_set:
            subject_classes = [cls for cls in classes if simplify_subject_name(cls.subject) == subject]
            tutor_for_subject = 'N/A'
            total_subject_hours = 0
            
            for cls in subject_classes:
                if cls.tutor and cls.tutor.user:
                    tutor_for_subject = cls.tutor.user.full_name
                if cls.duration:
                    total_subject_hours += cls.duration
                else:
                    total_subject_hours += 60
            
            subject_details[subject] = {
                'tutor_name': tutor_for_subject,
                'classes_count': len(subject_classes),
                'total_hours': round(total_subject_hours / 60, 1)
            }
        
        # Prepare template data with correct variable names
        template_data = {
            'student_info': student_info,  # This is the key fix!
            'timetable_data': timetable_data,
            'time_slots': sorted_time_slots,
            'date_range': f"{filters['start_date']} to {filters['end_date']}",
            'total_classes': len(classes),
            'unique_subjects': list(subjects_set),
            'unique_tutors': list(tutors_set),
            'total_hours': round(total_duration / 60, 1),
            'subject_details': subject_details,
            'current_date': datetime.now().strftime('%B %d, %Y')
        }
        
        return template_data
        
    except Exception as e:
        print(f"Error formatting student data: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def format_tutor_timetable_data(classes, tutor_info, filters):
    """Format data for tutor timetable template with correct variable names"""
    try:
        from datetime import datetime, timedelta
        import json
        
        # Group classes by date
        schedule_by_date = {}
        subjects_set = set()
        total_students = set()
        total_duration = 0
        
        for cls in classes:
            date_str = cls.scheduled_date.strftime('%A, %B %d, %Y')
            if date_str not in schedule_by_date:
                schedule_by_date[date_str] = []
            
            # Get student names
            student_names = []
            if cls.class_type == 'demo' and cls.demo_student_id:
                from app.models.demo_student import DemoStudent
                demo_student = DemoStudent.query.get(cls.demo_student_id)
                if demo_student:
                    student_names.append(demo_student.full_name)
                    total_students.add(demo_student.full_name)
            elif cls.primary_student_id:
                student = Student.query.get(cls.primary_student_id)
                if student:
                    student_names.append(student.full_name)
                    total_students.add(student.full_name)
            elif cls.students:
                try:
                    student_ids = json.loads(cls.students)
                    if isinstance(student_ids, list):
                        students = Student.query.filter(Student.id.in_(student_ids)).all()
                        for student in students:
                            student_names.append(student.full_name)
                            total_students.add(student.full_name)
                except:
                    pass
            
            # Format time
            if cls.scheduled_time:
                start_time = cls.scheduled_time.strftime('%I:%M %p')
                
                if cls.duration:
                    start_datetime = datetime.combine(datetime.today(), cls.scheduled_time)
                    end_datetime = start_datetime + timedelta(minutes=cls.duration)
                    end_time = end_datetime.time().strftime('%I:%M %p')
                    total_duration += cls.duration
                else:
                    end_time = start_time
                    total_duration += 60
            else:
                start_time = '12:00 AM'
                end_time = '01:00 AM'
            
            # Simplify subject name
            simplified_subject = simplify_subject_name(cls.subject)
            subjects_set.add(simplified_subject)
            
            # Format student names for display
            formatted_students = format_student_name_display(student_names)
            
            # Create class info
            class_info = {
                'subject': simplified_subject,
                'students': formatted_students,
                'start_time': start_time,
                'end_time': end_time,
                'status': cls.status or 'scheduled',
                'platform': cls.platform or 'N/A',
                'meeting_link': cls.meeting_link
            }
            
            schedule_by_date[date_str].append(class_info)
        
        # Prepare template data with correct variable names
        template_data = {
            'tutor_info': tutor_info,  # This is the key fix!
            'schedule_by_date': schedule_by_date,
            'date_range': f"{filters['start_date']} to {filters['end_date']}",
            'total_classes': len(classes),
            'unique_subjects': list(subjects_set),
            'total_students': len(total_students),
            'total_hours': round(total_duration / 60, 1),
            'current_date': datetime.now().strftime('%B %d, %Y')
        }
        
        return template_data
        
    except Exception as e:
        print(f"Error formatting tutor data: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# ============ API ENDPOINTS ============

@bp.route('/api/v1/export/preview', methods=['POST'])
@login_required
@admin_required
def api_export_preview():
    """Generate preview of export data"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('start_date') or not data.get('end_date'):
            return jsonify({'success': False, 'error': 'Date range is required'}), 400
        
        # Get filtered classes
        classes = get_filtered_classes(data)
        
        if not classes:
            return jsonify({
                'success': True,
                'preview_html': '<div class="text-center"><h3>No classes found for the selected criteria</h3></div>',
                'export_type': 'empty',
                'class_count': 0
            })
        
        # Determine export type
        if data.get('student_id'):
            # Student export
            student = Student.query.get(data['student_id'])
            if not student:
                return jsonify({'success': False, 'error': 'Student not found'}), 404
            
            student_info = {
                'name': student.full_name,
                'grade': student.grade,
                'board': student.board
            }
            
            template_data = format_student_timetable_data(classes, student_info, data)
            if not template_data:
                return jsonify({'success': False, 'error': 'Error formatting student data'}), 500
            
            # Render student template for preview
            preview_html = render_template('exports/student_timetable_template.html', **template_data)
            
            return jsonify({
                'success': True,
                'preview_html': preview_html,
                'export_type': 'student',
                'class_count': len(classes),
                'student_name': student.full_name
            })
            
        elif data.get('tutor_id'):
            # Tutor export
            tutor = Tutor.query.get(data['tutor_id'])
            if not tutor or not tutor.user:
                return jsonify({'success': False, 'error': 'Tutor not found'}), 404
            
            tutor_info = {
                'name': tutor.user.full_name,
                'email': tutor.user.email,
                'phone': tutor.user.phone,
                'department': tutor.user.department.name if tutor.user.department else 'N/A'
            }
            
            template_data = format_tutor_timetable_data(classes, tutor_info, data)
            if not template_data:
                return jsonify({'success': False, 'error': 'Error formatting tutor data'}), 500
            
            # Render tutor template for preview
            preview_html = render_template('exports/tutor_timetable_template.html', **template_data)
            
            return jsonify({
                'success': True,
                'preview_html': preview_html,
                'export_type': 'tutor',
                'class_count': len(classes),
                'tutor_name': tutor.user.full_name
            })
        
        else:
            return jsonify({'success': False, 'error': 'Please select either a student or tutor'}), 400
            
    except Exception as e:
        print(f"Error generating preview: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/v1/export/download/<format_type>', methods=['POST'])
@login_required
@admin_required
def api_export_download(format_type):
    """Download export in specified format (html or csv)"""
    try:
        data = request.get_json()
        
        # Validate format
        if format_type not in ['html', 'csv']:
            return jsonify({'success': False, 'error': 'Invalid format type'}), 400
        
        # Get filtered classes
        classes = get_filtered_classes(data)
        
        if not classes:
            return jsonify({'success': False, 'error': 'No classes found'}), 404
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if data.get('student_id'):
            # Student export
            student = Student.query.get(data['student_id'])
            if not student:
                return jsonify({'success': False, 'error': 'Student not found'}), 404
            
            filename_base = f"student_timetable_{student.full_name.replace(' ', '_')}_{timestamp}"
            
            if format_type == 'html':
                return download_student_html(classes, student, data, filename_base)
            else:
                return download_student_csv(classes, student, data, filename_base)
                
        elif data.get('tutor_id'):
            # Tutor export
            tutor = Tutor.query.get(data['tutor_id'])
            if not tutor or not tutor.user:
                return jsonify({'success': False, 'error': 'Tutor not found'}), 404
            
            filename_base = f"tutor_timetable_{tutor.user.full_name.replace(' ', '_')}_{timestamp}"
            
            if format_type == 'html':
                return download_tutor_html(classes, tutor, data, filename_base)
            else:
                return download_tutor_csv(classes, tutor, data, filename_base)
        
        else:
            return jsonify({'success': False, 'error': 'Please select either a student or tutor'}), 400
            
    except Exception as e:
        print(f"Error downloading export: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ DOWNLOAD FUNCTIONS ============

def download_student_html(classes, student, filters, filename_base):
    """Download student timetable as HTML"""
    try:
        student_info = {
            'name': student.full_name,
            'grade': student.grade,
            'board': student.board
        }
        
        template_data = format_student_timetable_data(classes, student_info, filters)
        if not template_data:
            return jsonify({'success': False, 'error': 'Error formatting data'}), 500
        
        # Render your exact HTML template
        html_content = render_template('exports/student_timetable_template.html', **template_data)
        
        # Create response
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename_base}.html"'
        
        return response
        
    except Exception as e:
        print(f"Error creating student HTML: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def download_student_csv(classes, student, filters, filename_base):
    """Download student timetable as CSV"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Student Name', 'Grade', 'Board'])
        writer.writerow([student.full_name, student.grade or 'N/A', student.board or 'N/A'])
        writer.writerow([])  # Empty row
        
        # Classes header
        writer.writerow(['Date', 'Day', 'Time', 'Subject', 'Tutor', 'Duration (min)', 'Status', 'Platform'])
        
        # Classes data
        for cls in sorted(classes, key=lambda x: (x.scheduled_date, x.scheduled_time)):
            tutor_name = cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'No Tutor'
            day_name = cls.scheduled_date.strftime('%A')
            time_str = cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00'
            
            writer.writerow([
                cls.scheduled_date.strftime('%Y-%m-%d'),
                day_name,
                time_str,
                cls.subject,
                tutor_name,
                cls.duration or 60,
                cls.status,
                cls.platform or 'N/A'
            ])
        
        # Create response
        csv_content = output.getvalue()
        output.close()
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
        
        return response
        
    except Exception as e:
        print(f"Error creating student CSV: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def download_tutor_html(classes, tutor, filters, filename_base):
    """Download tutor timetable as HTML"""
    try:
        tutor_info = {
            'name': tutor.user.full_name,
            'email': tutor.user.email,
            'phone': tutor.user.phone,
            'department': tutor.user.department.name if tutor.user.department else 'N/A'
        }
        
        template_data = format_tutor_timetable_data(classes, tutor_info, filters)
        if not template_data:
            return jsonify({'success': False, 'error': 'Error formatting data'}), 500
        
        # Render tutor HTML template
        html_content = render_template('exports/tutor_timetable_template.html', **template_data)
        
        # Create response
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename_base}.html"'
        
        return response
        
    except Exception as e:
        print(f"Error creating tutor HTML: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def download_tutor_csv(classes, tutor, filters, filename_base):
    """Download tutor timetable as CSV"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Tutor Name', 'Email', 'Department'])
        writer.writerow([tutor.user.full_name, tutor.user.email or 'N/A', 
                        tutor.user.department.name if tutor.user.department else 'N/A'])
        writer.writerow([])  # Empty row
        
        # Classes header
        writer.writerow(['Date', 'Day', 'Time', 'Subject', 'Duration (min)', 'Student(s)', 
                        'Student Count', 'Status', 'Platform', 'Meeting Link'])
        
        # Classes data
        for cls in sorted(classes, key=lambda x: (x.scheduled_date, x.scheduled_time)):
            # Get student names
            student_names = []
            if cls.class_type == 'demo' and cls.demo_student_id:
                from app.models.demo_student import DemoStudent
                demo_student = DemoStudent.query.get(cls.demo_student_id)
                if demo_student:
                    student_names.append(demo_student.full_name)
            elif cls.primary_student_id:
                student = Student.query.get(cls.primary_student_id)
                if student:
                    student_names.append(student.full_name)
            elif cls.students:
                try:
                    student_ids = json.loads(cls.students)
                    if isinstance(student_ids, list):
                        students = Student.query.filter(Student.id.in_(student_ids)).all()
                        student_names = [s.full_name for s in students]
                except:
                    pass
            
            day_name = cls.scheduled_date.strftime('%A')
            time_str = cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00'
            
            writer.writerow([
                cls.scheduled_date.strftime('%Y-%m-%d'),
                day_name,
                time_str,
                cls.subject,
                cls.duration or 60,
                ', '.join(student_names) if student_names else 'No Students',
                len(student_names),
                cls.status,
                cls.platform or 'N/A',
                cls.meeting_link or 'N/A'
            ])
        
        # Create response
        csv_content = output.getvalue()
        output.close()
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
        
        return response
        
    except Exception as e:
        print(f"Error creating tutor CSV: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ EMAIL FUNCTIONS ============

@bp.route('/api/v1/export/email', methods=['POST'])
@login_required
@admin_required
def api_email_timetable():
    """Email timetable to recipients"""
    try:
        data = request.get_json()
        
        # Validate required fields
        recipients = data.get('recipients', [])
        if not recipients:
            return jsonify({'success': False, 'error': 'No recipients specified'}), 400
        
        # Get filtered classes
        classes = get_filtered_classes(data)
        
        if not classes:
            return jsonify({'success': False, 'error': 'No classes found'}), 404
        
        # Send email based on type
        if data.get('student_id'):
            return email_student_timetable(classes, data, recipients)
        elif data.get('tutor_id'):
            return email_tutor_timetable(classes, data, recipients)
        else:
            return jsonify({'success': False, 'error': 'Please select either a student or tutor'}), 400
            
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def email_student_timetable(classes, filters, recipients):
    """Email student timetable"""
    try:
        student = Student.query.get(filters['student_id'])
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        student_info = {
            'name': student.full_name,
            'grade': student.grade,
            'board': student.board
        }
        
        template_data = format_student_timetable_data(classes, student_info, filters)
        if not template_data:
            return jsonify({'success': False, 'error': 'Error formatting data'}), 500
        
        # Generate HTML content
        html_content = render_template('exports/student_timetable_template.html', **template_data)
        
        # Email configuration
        subject = f"Class Schedule - {student.full_name}"
        
        # Send to each recipient
        sent_count = 0
        failed_count = 0
        
        for recipient in recipients:
            try:
                # Use your existing email utility
                from app.utils.email import send_email
                
                send_email(
                    to=recipient,
                    subject=subject,
                    template='email/timetable_email.html',
                    student_name=student.full_name,
                    html_attachment=html_content,
                    attachment_filename=f"schedule_{student.full_name.replace(' ', '_')}.html"
                )
                sent_count += 1
                
            except Exception as e:
                print(f"Failed to send email to {recipient}: {str(e)}")
                failed_count += 1
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'message': f'Email sent to {sent_count} recipients'
        })
        
    except Exception as e:
        print(f"Error emailing student timetable: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def email_tutor_timetable(classes, filters, recipients):
    """Email tutor timetable"""
    try:
        tutor = Tutor.query.get(filters['tutor_id'])
        if not tutor or not tutor.user:
            return jsonify({'success': False, 'error': 'Tutor not found'}), 404
        
        tutor_info = {
            'name': tutor.user.full_name,
            'email': tutor.user.email,
            'phone': tutor.user.phone,
            'department': tutor.user.department.name if tutor.user.department else 'N/A'
        }
        
        template_data = format_tutor_timetable_data(classes, tutor_info, filters)
        if not template_data:
            return jsonify({'success': False, 'error': 'Error formatting data'}), 500
        
        # Generate HTML content
        html_content = render_template('exports/tutor_timetable_template.html', **template_data)
        
        # Email configuration
        subject = f"Teaching Schedule - {tutor.user.full_name}"
        
        # Send to each recipient
        sent_count = 0
        failed_count = 0
        
        for recipient in recipients:
            try:
                # Use your existing email utility
                from app.utils.email import send_email
                
                send_email(
                    to=recipient,
                    subject=subject,
                    template='email/timetable_email.html',
                    tutor_name=tutor.user.full_name,
                    html_attachment=html_content,
                    attachment_filename=f"schedule_{tutor.user.full_name.replace(' ', '_')}.html"
                )
                sent_count += 1
                
            except Exception as e:
                print(f"Failed to send email to {recipient}: {str(e)}")
                failed_count += 1
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'message': f'Email sent to {sent_count} recipients'
        })
        
    except Exception as e:
        print(f"Error emailing tutor timetable: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    
@bp.route('/api/v1/export/download-pdf', methods=['POST'])
@login_required
@admin_required
def api_export_download_pdf():
    """Download export as PDF using pdfkit with proper Windows path"""
    try:
        import pdfkit
        
        # Configure pdfkit for Windows installation
        config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
        
        data = request.get_json()
        classes = get_filtered_classes(data)
        
        if not classes:
            return jsonify({'success': False, 'error': 'No classes found'}), 404
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if data.get('student_id'):
            student = Student.query.get(data['student_id'])
            if not student:
                return jsonify({'success': False, 'error': 'Student not found'}), 404
            
            student_info = {
                'name': student.full_name,
                'grade': student.grade,
                'board': student.board
            }
            
            template_data = format_student_timetable_data(classes, student_info, data)
            html_content = render_template('exports/student_timetable_template.html', **template_data)
            filename = f"student_schedule_{student.full_name.replace(' ', '_')}_{timestamp}.pdf"
            
        elif data.get('tutor_id'):
            tutor = Tutor.query.get(data['tutor_id'])
            if not tutor or not tutor.user:
                return jsonify({'success': False, 'error': 'Tutor not found'}), 404
            
            tutor_info = {
                'name': tutor.user.full_name,
                'email': tutor.user.email,
                'phone': tutor.user.phone,
                'department': tutor.user.department.name if tutor.user.department else 'N/A'
            }
            
            template_data = format_tutor_timetable_data(classes, tutor_info, data)
            html_content = render_template('exports/tutor_timetable_template.html', **template_data)
            filename = f"tutor_schedule_{tutor.user.full_name.replace(' ', '_')}_{timestamp}.pdf"
        
        else:
            return jsonify({'success': False, 'error': 'Please select either a student or tutor'}), 400
        
        # PDF generation options
        options = {
            'page-size': 'A3',              # CHANGE TO A3
            'orientation': 'landscape',      # ADD LANDSCAPE
            'margin-top': '0.4in',          # SMALLER MARGINS FOR A3
            'margin-right': '0.4in',
            'margin-bottom': '0.4in',
            'margin-left': '0.4in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            'disable-smart-shrinking': ''
        }
        
        # Generate PDF with configuration
        pdf_bytes = pdfkit.from_string(html_content, False, options=options, configuration=config)
        
        # Create response
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Error creating PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'PDF generation failed: {str(e)}'
        }), 500
        
        
# Add this to app/routes/export_email_timetable.py

@bp.route('/api/v1/export/email-preview', methods=['POST'])
@login_required
@admin_required
def api_email_preview():
    """Generate email preview (both email template and timetable attachment)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('start_date') or not data.get('end_date'):
            return jsonify({'success': False, 'error': 'Date range is required'}), 400
        
        # Get filtered classes
        classes = get_filtered_classes(data)
        
        if not classes:
            return jsonify({
                'success': True,
                'email_html': '<div class="text-center"><h3>No classes found - Email will not be sent</h3></div>',
                'timetable_html': '<div class="text-center"><h3>No timetable to attach</h3></div>',
                'class_count': 0
            })
        
        # Determine type and generate both email and timetable previews
        if data.get('student_id'):
            # Student email preview
            student = Student.query.get(data['student_id'])
            if not student:
                return jsonify({'success': False, 'error': 'Student not found'}), 404
            
            student_info = {
                'name': student.full_name,
                'grade': student.grade,
                'board': student.board
            }
            
            # Generate timetable attachment preview
            template_data = format_student_timetable_data(classes, student_info, data)
            if not template_data:
                return jsonify({'success': False, 'error': 'Error formatting student data'}), 500
            
            timetable_html = render_template('exports/student_timetable_template.html', **template_data)
            
            # Generate email preview
            email_html = render_template('email/timetable_email.html',
                student_name=student.full_name,
                date_range=f"{data['start_date']} to {data['end_date']}",
                attachment_filename=f"schedule_{student.full_name.replace(' ', '_')}.html"
            )
            
            return jsonify({
                'success': True,
                'email_html': email_html,
                'timetable_html': timetable_html,
                'export_type': 'student',
                'class_count': len(classes),
                'student_name': student.full_name,
                'email_subject': f"Class Schedule - {student.full_name}"
            })
            
        elif data.get('tutor_id'):
            # Tutor email preview
            tutor = Tutor.query.get(data['tutor_id'])
            if not tutor or not tutor.user:
                return jsonify({'success': False, 'error': 'Tutor not found'}), 404
            
            tutor_info = {
                'name': tutor.user.full_name,
                'email': tutor.user.email,
                'phone': tutor.user.phone,
                'department': tutor.user.department.name if tutor.user.department else 'N/A'
            }
            
            # Generate timetable attachment preview
            template_data = format_tutor_timetable_data(classes, tutor_info, data)
            if not template_data:
                return jsonify({'success': False, 'error': 'Error formatting tutor data'}), 500
            
            timetable_html = render_template('exports/tutor_timetable_template.html', **template_data)
            
            # Generate email preview
            email_html = render_template('email/timetable_email.html',
                tutor_name=tutor.user.full_name,
                date_range=f"{data['start_date']} to {data['end_date']}",
                attachment_filename=f"schedule_{tutor.user.full_name.replace(' ', '_')}.html"
            )
            
            return jsonify({
                'success': True,
                'email_html': email_html,
                'timetable_html': timetable_html,
                'export_type': 'tutor',
                'class_count': len(classes),
                'tutor_name': tutor.user.full_name,
                'email_subject': f"Teaching Schedule - {tutor.user.full_name}"
            })
        
        else:
            return jsonify({'success': False, 'error': 'Please select either a student or tutor'}), 400
            
    except Exception as e:
        print(f"Error generating email preview: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500