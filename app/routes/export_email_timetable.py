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
    """Format data for student timetable (your HTML template) - FIXED TIME FORMAT"""
    try:
        # Group classes by day of week and time
        weekly_schedule = {}
        subjects_set = set()
        
        for cls in classes:
            day_of_week = cls.scheduled_date.weekday()  # 0=Monday, 6=Sunday
            
            # FIXED: 12-hour format with start and end time
            if cls.scheduled_time:
                start_time_12hr = cls.scheduled_time.strftime('%I:%M %p')
                
                # Calculate end time
                if cls.duration:
                    start_datetime = datetime.combine(datetime.today(), cls.scheduled_time)
                    end_datetime = start_datetime + timedelta(minutes=cls.duration)
                    end_time_12hr = end_datetime.time().strftime('%I:%M %p')
                    time_display = f"{start_time_12hr} - {end_time_12hr}"
                else:
                    time_display = start_time_12hr
            else:
                time_display = '12:00 AM'
            
            # Use start time for grouping
            time_key = cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00'
            
            if time_key not in weekly_schedule:
                weekly_schedule[time_key] = [''] * 7  # 7 days
            
            # Get tutor name
            tutor_name = 'No Tutor'
            if cls.tutor and cls.tutor.user:
                tutor_name = cls.tutor.user.full_name
            
            # Format class info with FIXED 12-hour time format
            class_info = f"{cls.subject}\n{tutor_name}\n{time_display}\n{cls.status}"
            weekly_schedule[time_key][day_of_week] = class_info
            subjects_set.add(cls.subject)
        
        # Create time slots list (sorted by time)
        time_slots = []
        for time_key in sorted(weekly_schedule.keys()):
            time_slots.append(weekly_schedule[time_key])
        
        # Prepare template data
        template_data = {
            'title': f"Class Schedule - {student_info['name']}",
            'person_info': f"Student: {student_info['name']} | Grade: {student_info.get('grade', 'N/A')}",
            'grade_board': f"{student_info.get('grade', 'N/A')} / {student_info.get('board', 'N/A')}",
            'subjects_list': ', '.join(sorted(subjects_set)),
            'duration_period': f"{filters['start_date']} to {filters['end_date']}",
            'time_slots': time_slots,
            'details_subjects': list(sorted(subjects_set))[:6],  # Max 6 subjects
            'details_second_row_label': 'TUTORS',
            'details_second_row': [cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'N/A' 
                                 for cls in classes[:6]]  # Max 6 tutors
        }
        
        return template_data
        
    except Exception as e:
        print(f"Error formatting student data: {str(e)}")
        return None

def format_tutor_timetable_data(classes, tutor_info, filters):
    """Format data for tutor timetable (table format for lots of data)"""
    try:
        # Group classes by date
        classes_by_date = {}
        total_students = set()
        subjects_set = set()
        
        for cls in classes:
            date_str = cls.scheduled_date.strftime('%Y-%m-%d')
            if date_str not in classes_by_date:
                classes_by_date[date_str] = []
            
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
            
            subjects_set.add(cls.subject)
            
            class_info = {
                'id': cls.id,
                'subject': cls.subject,
                'time': cls.scheduled_time.strftime('%H:%M') if cls.scheduled_time else '00:00',
                'duration': cls.duration,
                'students': ', '.join(student_names) if student_names else 'No Students',
                'student_count': len(student_names),
                'status': cls.status,
                'platform': cls.platform or 'N/A',
                'meeting_link': cls.meeting_link or 'N/A'
            }
            
            classes_by_date[date_str].append(class_info)
        
        template_data = {
            'title': f"Teaching Schedule - {tutor_info['name']}",
            'tutor_info': tutor_info,
            'classes_by_date': classes_by_date,
            'total_classes': len(classes),
            'total_students': len(total_students),
            'subjects_taught': list(sorted(subjects_set)),
            'date_range': f"{filters['start_date']} to {filters['end_date']}"
        }
        
        return template_data
        
    except Exception as e:
        print(f"Error formatting tutor data: {str(e)}")
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
        
        # Send emails based on type
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
                    template='emails/timetable_email.html',
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
                    template='emails/timetable_email.html',
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
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
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
        
def fallback_html_as_pdf(html_content, filename):
    """Fallback: Return HTML file with PDF extension for browser print"""
    try:
        # Add print-optimized CSS to the HTML
        print_optimized_html = html_content.replace(
            '</head>',
            '''
            <style>
                @media print {
                    body { margin: 0; padding: 20px; }
                    .container { max-width: none; }
                }
            </style>
            <script>
                window.onload = function() {
                    // Auto-print when opened (optional)
                    // window.print();
                }
            </script>
            </head>'''
        )
        
        # Return as HTML but suggest printing to PDF
        response = make_response(print_optimized_html)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename.replace(".pdf", ".html")}"'
        
        return response
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': 'PDF generation not available. Please use HTML download.'
        }), 500