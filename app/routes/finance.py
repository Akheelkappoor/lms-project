from flask import Blueprint, render_template, request, jsonify, make_response, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
import csv
import io
from app import db
from app.models.tutor import Tutor
from app.models.student import Student
from app.routes.admin import admin_required

bp = Blueprint('finance', __name__)

# Salary endpoints
@bp.route('/api/v1/finance/salary/tutor/<int:tutor_id>')
@login_required
@admin_required
def get_tutor_salary(tutor_id):
    """Get tutor salary details"""
    tutor = Tutor.query.get_or_404(tutor_id)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    salary_data = tutor.calculate_monthly_salary(month, year)
    salary_history = tutor.get_salary_history()
    
    # Get enhanced breakdown
    payout_breakdown = tutor.get_monthly_payout_breakdown(month, year)
    
    return jsonify({
        'tutor_id': tutor_id,
        'salary_calculation': salary_data,
        'outstanding_amount': tutor.get_outstanding_salary(),
        'payment_history': salary_history,
        'payout_breakdown': payout_breakdown
    })

@bp.route('/api/v1/finance/salary/calculate', methods=['POST'])
@login_required
@admin_required
def calculate_salary():
    """Calculate monthly salary for tutors"""
    data = request.get_json()
    tutor_id = data.get('tutor_id')
    month = data.get('month', datetime.now().month)
    year = data.get('year', datetime.now().year)
    
    tutor = Tutor.query.get_or_404(tutor_id)
    salary_data = tutor.calculate_monthly_salary(month, year)
    
    return jsonify(salary_data)

@bp.route('/api/v1/finance/salary/generate', methods=['POST'])
@login_required
@admin_required
def generate_salary():
    """Generate salary payment"""
    data = request.get_json()
    tutor_id = data.get('tutor_id')
    month = data.get('month')
    year = data.get('year')
    amount = data.get('amount')
    
    tutor = Tutor.query.get_or_404(tutor_id)
    payment_record = tutor.add_salary_payment(amount, month, year, 'pending')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'payment_record': payment_record
    })

@bp.route('/api/v1/finance/salary/export')
@login_required
@admin_required
def export_salary():
    """Export salary data to CSV"""
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    tutors = Tutor.query.filter_by(status='active').all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Tutor Name', 'Base Salary', 'Calculated Salary', 'Classes', 'Attendance', 'Outstanding'])
    
    for tutor in tutors:
        salary_data = tutor.calculate_monthly_salary(month, year)
        writer.writerow([
            tutor.user.full_name if tutor.user else '',
            salary_data['base_salary'],
            salary_data['calculated_salary'],
            salary_data['total_classes'],
            salary_data['attended_classes'],
            tutor.get_outstanding_salary()
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=salary_report_{month}_{year}.csv'
    
    return response

# Fee endpoints
@bp.route('/api/v1/finance/fees/student/<int:student_id>')
@login_required
@admin_required
def get_student_fees(student_id):
    """Get student fee details"""
    student = Student.query.get_or_404(student_id)
    
    return jsonify({
        'student_id': student_id,
        'fee_structure': student.get_fee_structure(),
        'outstanding_amount': student.calculate_outstanding_fees(),
        'payment_history': student.get_fee_payment_history(),
        'fee_status': student.get_fee_status()
    })

@bp.route('/api/v1/finance/fees/payment', methods=['POST'])
@login_required
@admin_required
def record_fee_payment():
    """Record fee payment with optional receipt photo"""
    # Handle both JSON and FormData requests
    if request.content_type and 'multipart/form-data' in request.content_type:
        # FormData request (with file upload)
        student_id = int(request.form.get('student_id'))
        amount = float(request.form.get('amount'))
        payment_mode = request.form.get('payment_mode', 'cash')
        payment_date = request.form.get('payment_date')
        reference_number = request.form.get('reference_number', '')
        notes = request.form.get('notes', '')
        send_receipt = request.form.get('send_receipt') == 'true'
        receipt_photo = request.files.get('receipt_photo')
    else:
        # JSON request (backward compatibility)
        data = request.get_json()
        student_id = data.get('student_id')
        amount = data.get('amount')
        payment_mode = data.get('payment_mode', 'cash')
        payment_date = data.get('payment_date')
        reference_number = data.get('reference_number', '')
        notes = data.get('notes', '')
        send_receipt = data.get('send_receipt', False)
        receipt_photo = None
    
    try:
        student = Student.query.get_or_404(student_id)
        
        # Handle receipt photo upload
        receipt_url = None
        if receipt_photo and receipt_photo.filename:
            try:
                # Upload to your storage system (S3, local storage, etc.)
                from app.utils.file_upload import upload_file_to_s3
                receipt_url = upload_file_to_s3(
                    receipt_photo, 
                    folder=f"{current_app.config.get('UPLOAD_FOLDER', 'uploads')}/receipts"
                )
            except Exception as e:
                print(f"Error uploading receipt: {e}")
                # Don't fail the payment if receipt upload fails
                receipt_url = None
        
        # Parse payment date
        payment_date_obj = None
        if payment_date:
            from datetime import datetime
            payment_date_obj = datetime.fromisoformat(payment_date).date()
        
        # Add payment record with receipt URL
        payment_record = student.add_fee_payment(
            amount=amount, 
            payment_mode=payment_mode, 
            payment_date=payment_date_obj,
            notes=notes,
            recorded_by=current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
        )
        
        # Add receipt URL to payment record if available
        if receipt_url:
            fee_structure = student.get_fee_structure()
            payment_history = fee_structure.get('payment_history', [])
            if payment_history:
                payment_history[-1]['receipt_url'] = receipt_url
                student.set_fee_structure(fee_structure)
        
        db.session.commit()
        
        # Send notification to superadmin about payment
        try:
            from app.utils.notifications import send_finance_alert
            send_finance_alert(
                'payment_recorded',
                f'Payment of ₹{amount:,.0f} recorded for {student.full_name}',
                {
                    'student_id': student_id,
                    'student_name': student.full_name,
                    'amount': amount,
                    'payment_mode': payment_mode,
                    'recorded_by': current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
                }
            )
        except Exception as e:
            print(f"Error sending finance alert: {e}")
            # Don't fail the payment if notification fails
        
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'payment_record': payment_record,
            'new_balance': student.calculate_outstanding_fees(),
            'receipt_uploaded': receipt_url is not None
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error recording payment: {str(e)}'
        }), 500

@bp.route('/api/v1/finance/fees/pending')
@login_required
@admin_required
def get_pending_fees():
    """Get students with pending fees"""
    students = Student.query.filter_by(is_active=True).all()
    pending_students = []
    
    for student in students:
        outstanding = student.calculate_outstanding_fees()
        if outstanding > 0:
            pending_students.append({
                'student_id': student.id,
                'student_name': student.full_name,
                'outstanding_amount': outstanding,
                'fee_status': student.get_fee_status()
            })
    
    return jsonify(pending_students)

@bp.route('/api/v1/finance/fees/export')
@login_required
@admin_required
def export_fees():
    """Export fee data to CSV"""
    students = Student.query.filter_by(is_active=True).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student Name', 'Total Fee', 'Amount Paid', 'Outstanding', 'Status'])
    
    for student in students:
        fee_structure = student.get_fee_structure()
        writer.writerow([
            student.full_name,
            fee_structure.get('total_fee', 0),
            fee_structure.get('amount_paid', 0),
            student.calculate_outstanding_fees(),
            student.get_fee_status()
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=fee_report.csv'
    
    return response

@bp.route('/api/v1/finance/salary/<int:tutor_id>/payslip')
@login_required
@admin_required
def generate_payslip(tutor_id):
    """Generate payslip using ReportLab (Windows-friendly)"""
    from datetime import datetime
    
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Calculate salary data
        salary_data = tutor.calculate_monthly_salary(month, year)
        
        # Get attendance records
        from datetime import date
        from app.models.attendance import Attendance
        
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
            
        attendance_records = Attendance.query.filter(
            Attendance.tutor_id == tutor.id,
            Attendance.class_date >= start_date,
            Attendance.class_date < end_date
        ).all()
        
        # Try PDF first, fallback to HTML
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from io import BytesIO
            
            # Generate PDF using ReportLab
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Header
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.darkblue,
                alignment=1  # Center
            )
            
            story.append(Paragraph("I2Global LMS", title_style))
            story.append(Paragraph("SALARY SLIP", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            # Employee info
            tutor_name = tutor.user.full_name if tutor.user else 'Unknown'
            employee_id = f'TUT-{tutor.id:04d}'
            month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            month_name = month_names[month] if 1 <= month <= 12 else 'Unknown'
            
            # Employee details table
            emp_data = [
                ['Employee Name:', tutor_name],
                ['Employee ID:', employee_id],
                ['Pay Period:', f'{month_name} {year}'],
                ['Payment Date:', datetime.now().strftime('%d %B %Y')]
            ]
            
            emp_table = Table(emp_data, colWidths=[2*inch, 3*inch])
            emp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(emp_table)
            story.append(Spacer(1, 20))
            
            # Salary breakdown
            total_classes = salary_data.get('total_classes', 0)
            attended_classes = salary_data.get('attended_classes', 0)
            base_salary = salary_data.get('base_salary', 0)
            gross_salary = salary_data.get('calculated_salary', 0)
            
            # Calculate penalties
            total_late_minutes = sum(getattr(att, 'tutor_late_minutes', 0) or 0 for att in attendance_records)
            late_penalty = total_late_minutes * 10
            net_salary = gross_salary - late_penalty
            
            salary_data_table = [
                ['Description', 'Amount (₹)'],
                ['Base Salary', f'₹{base_salary:,.0f}'],
                ['Performance Calculation', f'₹{gross_salary:,.0f}'],
                ['Classes Attended', f'{attended_classes}/{total_classes}'],
            ]
            
            if late_penalty > 0:
                salary_data_table.append(['Late Penalty', f'-₹{late_penalty:,.0f}'])
            
            salary_data_table.append(['Net Salary', f'₹{net_salary:,.0f}'])
            
            salary_table = Table(salary_data_table, colWidths=[3*inch, 2*inch])
            salary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(salary_table)
            story.append(Spacer(1, 30))
            
            # Footer
            story.append(Paragraph("This is a system-generated payslip.", styles['Normal']))
            story.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}", styles['Normal']))
            
            # Build PDF
            doc.build(story)
            pdf_buffer.seek(0)
            
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=payslip_{tutor_name.replace(" ", "_")}_{month}_{year}.pdf'
            return response
            
        except ImportError:
            # Fallback to HTML
            html_content = generate_payslip_html(tutor, salary_data, attendance_records, month, year)
            response = make_response(html_content)
            response.headers['Content-Type'] = 'text/html'
            response.headers['Content-Disposition'] = f'attachment; filename=payslip_{tutor_name.replace(" ", "_")}_{month}_{year}.html'
            return response
            
    except Exception as e:
        return jsonify({'error': f'Error generating payslip: {str(e)}'}), 500

    
def generate_payslip_html(tutor, salary_data, attendance_records, month, year):
    """Generate HTML content for payslip - Safe version with field checks"""
    from datetime import datetime
    
    # Safely get tutor information
    tutor_name = getattr(tutor.user, 'full_name', 'Unknown') if tutor.user else 'Unknown'
    tutor_email = getattr(tutor.user, 'email', 'N/A') if tutor.user else 'N/A'
    employee_id = getattr(tutor, 'employee_id', None) or f'TUT-{tutor.id:04d}'
    
    # Safely get department information
    department_name = 'General'
    if tutor.user and hasattr(tutor.user, 'department') and tutor.user.department:
        department_name = tutor.user.department.name
    
    # Calculate additional metrics safely
    total_late_minutes = sum(getattr(att, 'tutor_late_minutes', 0) or 0 for att in attendance_records)
    total_early_leaves = sum(getattr(att, 'tutor_early_leave_minutes', 0) or 0 for att in attendance_records)
    
    # Calculate deductions
    late_penalty = total_late_minutes * 10  # ₹10 per minute late
    early_leave_penalty = total_early_leaves * 5  # ₹5 per minute early leave
    total_deductions = late_penalty + early_leave_penalty
    
    # Calculate final amount
    gross_salary = salary_data.get('calculated_salary', 0)
    net_salary = gross_salary - total_deductions
    
    # Get month name
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    month_name = month_names[month] if 1 <= month <= 12 else 'Unknown'
    
    # Safely get salary information
    base_salary = salary_data.get('base_salary', 0)
    salary_type = getattr(tutor, 'salary_type', 'fixed')
    monthly_salary = getattr(tutor, 'monthly_salary', 0) or 0
    hourly_rate = getattr(tutor, 'hourly_rate', 0) or 0
    
    # Calculate attendance rate safely
    total_classes = salary_data.get('total_classes', 0)
    attended_classes = salary_data.get('attended_classes', 0)
    attendance_rate = (attended_classes / total_classes * 100) if total_classes > 0 else 0
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Payslip - {tutor_name}</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f8f9fa;
                color: #333;
            }}
            
            .payslip-container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }}
            
            .payslip-header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            
            .company-logo {{
                font-size: 2.5rem;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            
            .payslip-title {{
                font-size: 1.5rem;
                margin: 10px 0;
                opacity: 0.9;
            }}
            
            .payslip-period {{
                font-size: 1.1rem;
                opacity: 0.8;
            }}
            
            .payslip-body {{
                padding: 30px;
            }}
            
            .employee-info {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin-bottom: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 8px;
            }}
            
            .info-group h4 {{
                color: #495057;
                margin-bottom: 15px;
                font-size: 1.1rem;
                border-bottom: 2px solid #dee2e6;
                padding-bottom: 5px;
            }}
            
            .info-item {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                padding: 5px 0;
            }}
            
            .info-label {{
                font-weight: 500;
                color: #6c757d;
            }}
            
            .info-value {{
                font-weight: 600;
                color: #495057;
            }}
            
            .salary-breakdown {{
                margin: 30px 0;
            }}
            
            .breakdown-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            
            .breakdown-table th {{
                background: #495057;
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
            }}
            
            .breakdown-table td {{
                padding: 12px 15px;
                border-bottom: 1px solid #dee2e6;
            }}
            
            .breakdown-table tr:nth-child(even) {{
                background: #f8f9fa;
            }}
            
            .amount {{
                font-weight: 600;
                color: #495057;
            }}
            
            .positive {{
                color: #28a745;
            }}
            
            .negative {{
                color: #dc3545;
            }}
            
            .total-row {{
                background: #e3f2fd !important;
                border-top: 2px solid #2196f3;
                font-weight: bold;
                font-size: 1.1rem;
            }}
            
            .total-row td {{
                padding: 20px 15px;
                border-bottom: none;
            }}
            
            .attendance-summary {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            
            .attendance-card {{
                background: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                border-left: 4px solid #6c757d;
            }}
            
            .attendance-card.success {{
                border-left-color: #28a745;
            }}
            
            .attendance-card.warning {{
                border-left-color: #ffc107;
            }}
            
            .attendance-card.danger {{
                border-left-color: #dc3545;
            }}
            
            .card-title {{
                font-size: 0.9rem;
                color: #6c757d;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            
            .card-value {{
                font-size: 2rem;
                font-weight: bold;
                color: #495057;
            }}
            
            .payslip-footer {{
                background: #f8f9fa;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #dee2e6;
            }}
            
            .signature-section {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 50px;
                margin-top: 40px;
            }}
            
            .signature-box {{
                text-align: center;
                padding-top: 30px;
                border-top: 1px solid #495057;
            }}
            
            .generated-info {{
                margin-top: 20px;
                color: #6c757d;
                font-size: 0.9rem;
            }}
            
            @media print {{
                body {{ background: white; }}
                .payslip-container {{ box-shadow: none; }}
            }}
            
            @media (max-width: 768px) {{
                .employee-info {{
                    grid-template-columns: 1fr;
                    gap: 20px;
                }}
                .attendance-summary {{
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                }}
                .signature-section {{
                    grid-template-columns: 1fr;
                    gap: 30px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="payslip-container">
            <!-- Header -->
            <div class="payslip-header">
                <div class="company-logo">I2Global LMS</div>
                <div class="payslip-title">SALARY SLIP</div>
                <div class="payslip-period">{month_name} {year}</div>
            </div>
            
            <!-- Body -->
            <div class="payslip-body">
                <!-- Employee Information -->
                <div class="employee-info">
                    <div class="info-group">
                        <h4>Employee Details</h4>
                        <div class="info-item">
                            <span class="info-label">Name:</span>
                            <span class="info-value">{tutor_name}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Employee ID:</span>
                            <span class="info-value">{employee_id}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Email:</span>
                            <span class="info-value">{tutor_email}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Department:</span>
                            <span class="info-value">{department_name}</span>
                        </div>
                    </div>
                    
                    <div class="info-group">
                        <h4>Salary Details</h4>
                        <div class="info-item">
                            <span class="info-label">Salary Type:</span>
                            <span class="info-value">{salary_type.title()}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Base Salary:</span>
                            <span class="info-value">₹{base_salary:,.0f}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Pay Period:</span>
                            <span class="info-value">{month_name} {year}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Payment Date:</span>
                            <span class="info-value">{datetime.now().strftime('%d %B %Y')}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Attendance Summary -->
                <div class="attendance-summary">
                    <div class="attendance-card success">
                        <div class="card-title">Total Classes</div>
                        <div class="card-value">{total_classes}</div>
                    </div>
                    <div class="attendance-card success">
                        <div class="card-title">Classes Attended</div>
                        <div class="card-value">{attended_classes}</div>
                    </div>
                    <div class="attendance-card {'success' if attendance_rate >= 90 else 'warning' if attendance_rate >= 75 else 'danger'}">
                        <div class="card-title">Attendance Rate</div>
                        <div class="card-value">{attendance_rate:.1f}%</div>
                    </div>
                    <div class="attendance-card {'danger' if total_late_minutes > 0 else 'success'}">
                        <div class="card-title">Late Minutes</div>
                        <div class="card-value">{total_late_minutes}</div>
                    </div>
                </div>
                
                <!-- Salary Breakdown -->
                <div class="salary-breakdown">
                    <h4>Salary Breakdown</h4>
                    <table class="breakdown-table">
                        <thead>
                            <tr>
                                <th>Description</th>
                                <th>Amount (₹)</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Base Salary</td>
                                <td class="amount positive">₹{base_salary:,.0f}</td>
                            </tr>
                            <tr>
                                <td>Performance Calculation ({attended_classes}/{total_classes} classes)</td>
                                <td class="amount positive">₹{gross_salary:,.0f}</td>
                            </tr>
                            {f'''<tr>
                                <td>Late Penalty ({total_late_minutes} minutes @ ₹10/min)</td>
                                <td class="amount negative">-₹{late_penalty:,.0f}</td>
                            </tr>''' if total_late_minutes > 0 else ''}
                            {f'''<tr>
                                <td>Early Leave Penalty ({total_early_leaves} minutes @ ₹5/min)</td>
                                <td class="amount negative">-₹{early_leave_penalty:,.0f}</td>
                            </tr>''' if total_early_leaves > 0 else ''}
                            <tr class="total-row">
                                <td><strong>Net Salary</strong></td>
                                <td class="amount"><strong>₹{net_salary:,.0f}</strong></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Signature Section -->
                <div class="signature-section">
                    <div class="signature-box">
                        <strong>Employee Signature</strong>
                    </div>
                    <div class="signature-box">
                        <strong>Authorized Signatory</strong>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="payslip-footer">
                <div class="generated-info">
                    <p><strong>Note:</strong> This is a system-generated payslip. No signature is required.</p>
                    <p>Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}</p>
                    <p>© {datetime.now().year} I2Global LMS. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

# Bulk payslip generation
@bp.route('/api/v1/finance/salary/payslips')
@login_required
@admin_required
def generate_bulk_payslips():
    """Generate multiple payslips as a ZIP file"""
    import zipfile
    from io import BytesIO
    from app.models.attendance import Attendance
    
    try:
        tutor_ids = request.args.get('tutor_ids', '').split(',')
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        if not tutor_ids or tutor_ids == ['']:
            return jsonify({'error': 'No tutor IDs provided'}), 400
        
        # Create a ZIP file in memory
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for tutor_id in tutor_ids:
                try:
                    tutor = Tutor.query.get(int(tutor_id))
                    if not tutor:
                        continue
                    
                    # Generate payslip HTML
                    salary_data = tutor.calculate_monthly_salary(month, year)
                    
                    # Get attendance records manually
                    from datetime import date
                    start_date = date(year, month, 1)
                    if month == 12:
                        end_date = date(year + 1, 1, 1)
                    else:
                        end_date = date(year, month + 1, 1)
                        
                    attendance_records = Attendance.query.filter(
                        Attendance.tutor_id == tutor.id,
                        Attendance.class_date >= start_date,
                        Attendance.class_date < end_date
                    ).all()
                    
                    html_content = generate_payslip_html(tutor, salary_data, attendance_records, month, year)
                    
                    # Add to ZIP
                    filename = f"payslip_{tutor.user.full_name.replace(' ', '_')}_{month}_{year}.html"
                    zip_file.writestr(filename, html_content)
                    
                except Exception as e:
                    continue  # Skip failed payslips
        
        zip_buffer.seek(0)
        
        response = make_response(zip_buffer.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename=payslips_{month}_{year}.zip'
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Error generating payslips: {str(e)}'}), 500

# ================== MONTHLY FEE TRACKING ROUTES ==================

@bp.route('/api/v1/finance/fees/monthly/<int:student_id>')
@login_required
@admin_required
def get_student_monthly_fees(student_id):
    """Get monthly fee breakdown for student"""
    student = Student.query.get_or_404(student_id)
    
    # Get parameters
    start_month = request.args.get('start_month', type=int)
    start_year = request.args.get('start_year', type=int) 
    months_count = request.args.get('months', 12, type=int)
    
    monthly_summary = student.get_monthly_fees_summary(start_month, start_year, months_count)
    overdue_months = student.get_overdue_months()
    
    return jsonify({
        'student_id': student_id,
        'student_name': student.full_name,
        'monthly_summary': monthly_summary,
        'overdue_months': overdue_months,
        'total_overdue': sum(m['outstanding'] for m in overdue_months)
    })

@bp.route('/api/v1/finance/fees/status/<int:student_id>/<int:month>/<int:year>')
@login_required  
@admin_required
def get_specific_monthly_fee_status(student_id, month, year):
    """Get fee status for specific month"""
    student = Student.query.get_or_404(student_id)
    
    status = student.get_monthly_fee_status(month, year)
    due_amount = student.get_monthly_fee_due(month, year)
    paid_amount = student.get_monthly_fee_paid(month, year)
    
    return jsonify({
        'student_id': student_id,
        'month': month,
        'year': year,
        'status': status,
        'due_amount': due_amount,
        'paid_amount': paid_amount,
        'outstanding': due_amount - paid_amount
    })

@bp.route('/api/v1/finance/fees/overdue')
@login_required
@admin_required 
def get_overdue_fees_summary():
    """Get summary of all students with overdue fees"""
    students = Student.query.filter_by(is_active=True).all()
    overdue_students = []
    total_overdue = 0
    
    for student in students:
        overdue_months = student.get_overdue_months()
        if overdue_months:
            student_overdue = sum(m['outstanding'] for m in overdue_months)
            overdue_students.append({
                'student_id': student.id,
                'student_name': student.full_name,
                'overdue_months_count': len(overdue_months),
                'total_overdue': student_overdue,
                'overdue_months': overdue_months
            })
            total_overdue += student_overdue
    
    # Sort by overdue amount descending
    overdue_students.sort(key=lambda x: x['total_overdue'], reverse=True)
    
    return jsonify({
        'overdue_students': overdue_students,
        'total_overdue_amount': total_overdue,
        'total_overdue_students': len(overdue_students)
    })

# ================== ENHANCED TUTOR PAYOUT ROUTES ==================

@bp.route('/api/v1/finance/payout/breakdown/<int:tutor_id>')
@login_required
@admin_required
def get_tutor_payout_breakdown(tutor_id):
    """Get detailed payout breakdown per student for tutor"""
    tutor = Tutor.query.get_or_404(tutor_id)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    breakdown = tutor.get_monthly_payout_breakdown(month, year)
    
    return jsonify(breakdown)

@bp.route('/api/v1/finance/payout/summary/<int:tutor_id>')
@login_required
@admin_required
def get_tutor_payout_summary(tutor_id):
    """Get payout summary for multiple months"""
    tutor = Tutor.query.get_or_404(tutor_id)
    
    start_month = request.args.get('start_month', type=int)
    start_year = request.args.get('start_year', type=int)
    months_count = request.args.get('months', 6, type=int)
    
    summary = tutor.get_payout_summary_by_period(start_month, start_year, months_count)
    
    return jsonify({
        'tutor_id': tutor_id,
        'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
        'summary': summary,
        'total_earnings': sum(m['total_earnings'] for m in summary),
        'average_monthly_earnings': sum(m['total_earnings'] for m in summary) / len(summary) if summary else 0
    })

@bp.route('/api/v1/finance/payout/student-earnings/<int:tutor_id>/<int:student_id>')
@login_required
@admin_required  
def get_student_earnings_breakdown(tutor_id, student_id):
    """Get earnings breakdown for specific student with tutor"""
    tutor = Tutor.query.get_or_404(tutor_id)
    
    start_month = request.args.get('start_month', type=int)
    start_year = request.args.get('start_year', type=int) 
    months_count = request.args.get('months', 6, type=int)
    
    earnings_summary = tutor.get_student_earnings_summary(student_id, start_month, start_year, months_count)
    
    if not earnings_summary:
        return jsonify({'error': 'Student not found'}), 404
    
    return jsonify(earnings_summary)

# ================== INSTALLMENT MANAGEMENT ROUTES ==================

@bp.route('/api/v1/finance/installments/<int:student_id>')
@login_required
@admin_required
def get_student_installments(student_id):
    """Get student's installment plan and status"""
    student = Student.query.get_or_404(student_id)
    
    fee_structure = student.get_fee_structure()
    installment_plan = student.get_installment_plan()
    upcoming_installments = student.get_upcoming_installments()
    overdue_installments = student.get_overdue_installments()
    installment_summary = student.get_installment_summary()
    
    return jsonify({
        'student_id': student_id,
        'student_name': student.full_name,
        'has_installment_plan': bool(installment_plan),
        'installment_plan': installment_plan,
        'upcoming_installments': upcoming_installments,
        'overdue_installments': overdue_installments,
        'summary': installment_summary,
        'fee_structure': {
            'total_fee': fee_structure.get('total_fee', 0),
            'amount_paid': fee_structure.get('amount_paid', 0),
            'balance_amount': fee_structure.get('balance_amount', 0)
        }
    })

@bp.route('/api/v1/finance/installments/<int:student_id>/create', methods=['POST'])
@login_required
@admin_required
def create_installment_plan(student_id):
    """Create or update installment plan for student"""
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    if not data or 'installments' not in data:
        return jsonify({'error': 'Installments data required'}), 400
    
    try:
        installments = data['installments']
        
        # Validate installments
        for inst in installments:
            if not all(k in inst for k in ['due_date', 'amount']):
                return jsonify({'error': 'Each installment must have due_date and amount'}), 400
        
        # Create the plan
        plan = student.create_installment_plan(installments)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Installment plan created with {len(installments)} installments',
            'plan': plan
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create installment plan: {str(e)}'}), 500

@bp.route('/api/v1/finance/installments/<int:student_id>/update', methods=['PUT'])
@login_required
@admin_required
def update_installment_plan(student_id):
    """Update existing installment plan"""
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    if not data or 'installments' not in data:
        return jsonify({'error': 'Installments data required'}), 400
    
    try:
        installments = data['installments']
        
        # Validate installments
        for inst in installments:
            if not all(k in inst for k in ['due_date', 'amount']):
                return jsonify({'error': 'Each installment must have due_date and amount'}), 400
        
        # Update the plan
        plan = student.update_installment_plan(installments)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Installment plan updated successfully',
            'plan': plan
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update installment plan: {str(e)}'}), 500

@bp.route('/api/v1/finance/installments/<int:student_id>/payment', methods=['POST'])
@login_required
@admin_required
def record_installment_payment(student_id):
    """Record payment against installments"""
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    if not data or not data.get('amount'):
        return jsonify({'error': 'Payment amount required'}), 400
    
    try:
        amount = float(data['amount'])
        payment_mode = data.get('payment_mode', 'cash')
        notes = data.get('notes', '')
        payment_date = datetime.fromisoformat(data['payment_date']) if data.get('payment_date') else datetime.now()
        
        # Record payment (this will automatically update installment plan)
        payment_record = student.add_fee_payment(
            amount=amount,
            payment_mode=payment_mode,
            payment_date=payment_date.date(),
            notes=notes
        )
        
        db.session.commit()
        
        # Get updated installment summary
        installment_summary = student.get_installment_summary()
        
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'payment_record': payment_record,
            'new_balance': student.calculate_outstanding_fees(),
            'installment_summary': installment_summary
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to record payment: {str(e)}'}), 500

@bp.route('/api/v1/finance/installments/overdue')
@login_required
@admin_required
def get_all_overdue_installments():
    """Get all students with overdue installments"""
    students = Student.query.filter_by(is_active=True).all()
    overdue_students = []
    
    for student in students:
        overdue_installments = student.get_overdue_installments()
        if overdue_installments:
            total_overdue_amount = sum(inst['remaining_amount'] for inst in overdue_installments)
            overdue_students.append({
                'student_id': student.id,
                'student_name': student.full_name,
                'total_overdue_amount': total_overdue_amount,
                'overdue_count': len(overdue_installments),
                'most_overdue_days': max(inst['days_overdue'] for inst in overdue_installments),
                'overdue_installments': overdue_installments
            })
    
    # Sort by most overdue
    overdue_students.sort(key=lambda x: x['most_overdue_days'], reverse=True)
    
    return jsonify({
        'overdue_students': overdue_students,
        'total_students': len(overdue_students),
        'total_overdue_amount': sum(s['total_overdue_amount'] for s in overdue_students)
    })

@bp.route('/api/v1/finance/fee-structure/<int:student_id>', methods=['PUT'])
@login_required
@admin_required
def update_fee_structure(student_id):
    """Update student's fee structure and optionally installment plan"""
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    if not data or not data.get('total_fee') or not data.get('reason'):
        return jsonify({'error': 'Total fee and reason are required'}), 400
    
    try:
        new_total_fee = float(data['total_fee'])
        reason = data['reason']
        
        # Get current fee structure
        current_fee_structure = student.get_fee_structure()
        current_amount_paid = current_fee_structure.get('amount_paid', 0)
        
        # Update fee structure
        updated_fee_structure = {
            'total_fee': new_total_fee,
            'amount_paid': current_amount_paid,
            'balance_amount': new_total_fee - current_amount_paid,
            'payment_mode': current_fee_structure.get('payment_mode', ''),
            'payment_schedule': current_fee_structure.get('payment_schedule', ''),
            'payment_history': current_fee_structure.get('payment_history', []),
            'fee_change_history': current_fee_structure.get('fee_change_history', [])
        }
        
        # Add change record
        from datetime import datetime
        change_record = {
            'date': datetime.now().isoformat(),
            'old_total_fee': current_fee_structure.get('total_fee', 0),
            'new_total_fee': new_total_fee,
            'reason': reason,
            'changed_by': current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
        }
        updated_fee_structure['fee_change_history'].append(change_record)
        
        # Set updated fee structure
        student.set_fee_structure(updated_fee_structure)
        
        # Send notification to superadmin about fee structure change
        try:
            from app.utils.notifications import send_fee_structure_change_alert
            send_fee_structure_change_alert(
                student.full_name,
                current_fee_structure.get('total_fee', 0),
                new_total_fee,
                current_user.full_name if hasattr(current_user, 'full_name') else current_user.email,
                reason
            )
        except Exception as e:
            print(f"Error sending fee structure change alert: {e}")
        
        # Handle installment plan update if provided
        if data.get('installments'):
            installments = data['installments']
            if installments:  # Only update if there are installments
                try:
                    student.update_installment_plan(installments)
                    
                    # Send installment plan alert
                    try:
                        from app.utils.notifications import send_installment_plan_alert
                        send_installment_plan_alert(
                            student.full_name,
                            'updated',
                            current_user.full_name if hasattr(current_user, 'full_name') else current_user.email,
                            {'installment_count': len(installments)}
                        )
                    except Exception as e:
                        print(f"Error sending installment plan alert: {e}")
                        
                except ValueError as e:
                    # If installment update fails, still save fee structure change
                    db.session.commit()
                    return jsonify({
                        'success': True,
                        'message': 'Fee structure updated, but installment plan could not be updated',
                        'warning': str(e)
                    })
        
        db.session.commit()
        
        # Get updated summary
        new_balance = student.calculate_outstanding_fees()
        installment_summary = student.get_installment_summary()
        
        return jsonify({
            'success': True,
            'message': 'Fee structure updated successfully',
            'new_total_fee': new_total_fee,
            'new_balance': new_balance,
            'installment_summary': installment_summary
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update fee structure: {str(e)}'}), 500

# ================== MONTHLY FEE STATUS ROUTES ==================

@bp.route('/api/v1/finance/monthly-status/<int:student_id>')
@login_required
@admin_required
def get_monthly_fee_status(student_id):
    """Get monthly fee status history for student"""
    student = Student.query.get_or_404(student_id)
    
    months = request.args.get('months', 12, type=int)
    history = student.get_monthly_fee_history(months)
    current_status = student.get_monthly_fee_status()
    
    return jsonify({
        'student_id': student_id,
        'student_name': student.full_name,
        'current_status': current_status,
        'monthly_history': history
    })

@bp.route('/api/v1/finance/monthly-status/<int:student_id>', methods=['PUT'])
@login_required
@admin_required
def update_monthly_fee_status(student_id):
    """Update monthly fee status for student"""
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request data required'}), 400
    
    try:
        # Handle single month update
        if 'month' in data:
            month = data['month']
            status_data = {
                'status': data.get('status', 'pending'),
                'due_date': data.get('due_date'),
                'amount': float(data.get('amount', 0)),
                'notes': data.get('notes', '')
            }
            
            old_status = student.get_monthly_fee_status() if month == student.get_monthly_fee_status() else {'status': 'unknown'}
            student.set_monthly_fee_status(month, status_data)
            
            # Send alert for status change
            try:
                from app.utils.notifications import send_monthly_fee_status_alert
                send_monthly_fee_status_alert(
                    student.full_name,
                    old_status.get('status', 'unknown'),
                    status_data['status'],
                    current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
                )
            except Exception as e:
                print(f"Error sending monthly fee status alert: {e}")
            
        # Handle bulk updates
        elif 'monthly_updates' in data:
            monthly_updates = data['monthly_updates']
            updated_count = student.update_monthly_fee_status_bulk(monthly_updates)
            
            # Send bulk update alert
            try:
                from app.utils.notifications import send_finance_alert
                send_finance_alert(
                    'monthly_fee_bulk_update',
                    f'Monthly fee status updated for {updated_count} months for {student.full_name}',
                    {
                        'student_name': student.full_name,
                        'updated_count': updated_count,
                        'updated_by': current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
                    }
                )
            except Exception as e:
                print(f"Error sending bulk update alert: {e}")
        
        else:
            return jsonify({'error': 'Either month or monthly_updates required'}), 400
        
        db.session.commit()
        
        # Return updated status
        updated_history = student.get_monthly_fee_history(12)
        
        return jsonify({
            'success': True,
            'message': 'Monthly fee status updated successfully',
            'updated_history': updated_history
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update monthly fee status: {str(e)}'}), 500

@bp.route('/api/v1/finance/monthly-status/bulk', methods=['POST'])
@login_required
@admin_required
def bulk_update_monthly_status():
    """Bulk update monthly fee status for multiple students"""
    data = request.get_json()
    
    if not data or 'updates' not in data:
        return jsonify({'error': 'Updates data required'}), 400
    
    try:
        results = []
        updates = data['updates']
        
        for update in updates:
            student_id = update.get('student_id')
            month = update.get('month')
            status_data = {
                'status': update.get('status', 'pending'),
                'due_date': update.get('due_date'),
                'amount': float(update.get('amount', 0)),
                'notes': update.get('notes', '')
            }
            
            try:
                student = Student.query.get(student_id)
                if student:
                    student.set_monthly_fee_status(month, status_data)
                    results.append({
                        'student_id': student_id,
                        'student_name': student.full_name,
                        'success': True
                    })
                else:
                    results.append({
                        'student_id': student_id,
                        'success': False,
                        'error': 'Student not found'
                    })
            except Exception as e:
                results.append({
                    'student_id': student_id,
                    'success': False,
                    'error': str(e)
                })
        
        db.session.commit()
        
        success_count = sum(1 for r in results if r['success'])
        
        # Send bulk update alert
        try:
            from app.utils.notifications import send_finance_alert
            send_finance_alert(
                'monthly_fee_bulk_update_multiple',
                f'Monthly fee status bulk updated for {success_count}/{len(updates)} students',
                {
                    'total_updates': len(updates),
                    'successful_updates': success_count,
                    'updated_by': current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
                }
            )
        except Exception as e:
            print(f"Error sending bulk update alert: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Bulk update completed: {success_count}/{len(updates)} successful',
            'results': results
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to perform bulk update: {str(e)}'}), 500

# ================== PAYMENT REMINDER ROUTES ==================

@bp.route('/api/v1/finance/fees/reminder', methods=['POST'])
@login_required
@admin_required
def send_fee_payment_reminder():
    """Send payment reminder to student"""
    data = request.get_json()
    student_id = data.get('student_id')
    
    if not student_id:
        return jsonify({'success': False, 'message': 'Student ID required'}), 400
    
    try:
        student = Student.query.get_or_404(student_id)
        outstanding = student.calculate_outstanding_fees()
        
        if outstanding <= 0:
            return jsonify({'success': False, 'message': 'Student has no outstanding fees'}), 400
        
        # Send reminder email (implement your email logic here)
        try:
            from app.utils.notifications import send_payment_reminder_email
            send_payment_reminder_email(student, outstanding)
            
            return jsonify({
                'success': True,
                'message': f'Payment reminder sent to {student.full_name}',
                'student_name': student.full_name,
                'outstanding_amount': outstanding
            })
        except Exception as email_error:
            print(f"Error sending payment reminder email: {email_error}")
            return jsonify({
                'success': True,
                'message': f'Reminder logged for {student.full_name} (email service unavailable)',
                'student_name': student.full_name,
                'outstanding_amount': outstanding
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error sending reminder: {str(e)}'}), 500