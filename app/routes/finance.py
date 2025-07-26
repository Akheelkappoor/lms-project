from flask import Blueprint, render_template, request, jsonify, make_response
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
    
    return jsonify({
        'tutor_id': tutor_id,
        'salary_calculation': salary_data,
        'outstanding_amount': tutor.get_outstanding_salary(),
        'payment_history': salary_history
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
    """Record fee payment"""
    data = request.get_json()
    student_id = data.get('student_id')
    amount = data.get('amount')
    payment_mode = data.get('payment_mode', 'cash')
    notes = data.get('notes', '')
    
    student = Student.query.get_or_404(student_id)
    payment_record = student.add_fee_payment(amount, payment_mode, notes=notes)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'payment_record': payment_record,
        'new_balance': student.calculate_outstanding_fees()
    })

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