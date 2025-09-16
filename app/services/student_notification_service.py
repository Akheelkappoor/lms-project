from app.utils.email import send_email
from flask import render_template, current_app
from datetime import datetime

class StudentNotificationService:
    """Service for sending student lifecycle notifications"""
    
    @staticmethod
    def send_graduation_notification(student, graduation_record):
        """Send graduation congratulations to student and parents"""
        try:
            # Email to student
            subject = f"🎓 Congratulations on Your Graduation from {current_app.config.get('APP_NAME', 'LMS')}!"
            
            # Student email
            student_body = f"""
Dear {student.full_name},

🎉 CONGRATULATIONS! 🎉

We are thrilled to inform you that you have successfully completed your course and have officially graduated!

Graduation Details:
• Graduation Date: {graduation_record.graduation_date.strftime('%d %B %Y')}
• Final Grade: {graduation_record.final_grade or 'Not specified'}
• Performance Rating: {graduation_record.overall_performance_rating.title()}
• Certificate Number: {graduation_record.certificate_number}

Your dedication, hard work, and perseverance have paid off. We are incredibly proud of your achievement and wish you all the best in your future endeavors.

{graduation_record.feedback if graduation_record.feedback else 'Best wishes for your bright future ahead!'}

Best regards,
The Academic Team
{current_app.config.get('APP_NAME', 'LMS')}
"""

            send_email(
                subject=subject,
                recipients=[student.email],
                text_body=student_body,
                html_body=StudentNotificationService._render_graduation_email(student, graduation_record)
            )
            
            # Email to parents
            parent_contact = student.get_primary_contact()
            if parent_contact and parent_contact.get('email'):
                parent_subject = f"🎓 Your Child Has Graduated - {student.full_name}"
                parent_body = f"""
Dear Parent/Guardian,

We are delighted to share the wonderful news that {student.full_name} has successfully completed their course and graduated!

This is a moment of great pride for both you and {student.full_name}. Your support and encouragement have been instrumental in this achievement.

Graduation Summary:
• Student: {student.full_name}
• Graduation Date: {graduation_record.graduation_date.strftime('%d %B %Y')}
• Final Grade: {graduation_record.final_grade or 'Excellent Performance'}
• Performance Rating: {graduation_record.overall_performance_rating.title()}

We extend our heartfelt congratulations to you and your family on this significant milestone.

Warm regards,
The Academic Team
{current_app.config.get('APP_NAME', 'LMS')}
"""
                
                send_email(
                    subject=parent_subject,
                    recipients=[parent_contact['email']],
                    text_body=parent_body,
                    html_body=StudentNotificationService._render_parent_graduation_email(student, graduation_record, parent_contact)
                )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending graduation notification: {str(e)}")
            return False
    
    @staticmethod
    def send_drop_notification(student, drop_record):
        """Send drop notification to student and parents"""
        try:
            subject = f"Course Enrollment Status Update - {current_app.config.get('APP_NAME', 'LMS')}"
            
            # Student email
            student_body = f"""
Dear {student.full_name},

We regret to inform you that your enrollment in the course has been discontinued as of {drop_record.drop_date.strftime('%d %B %Y')}.

Details:
• Drop Date: {drop_record.drop_date.strftime('%d %B %Y')}
• Reason: {drop_record.get_drop_reason_display()}

{drop_record.detailed_reason}

{'If there is a refund due, it will be processed according to our refund policy and you will be notified separately.' if drop_record.refund_amount and drop_record.refund_amount > 0 else ''}

{'We appreciate your interest in our programs and welcome you to re-enroll in the future.' if drop_record.re_enrollment_allowed and not drop_record.blacklisted else ''}

If you have any questions or concerns, please don't hesitate to contact our support team.

Best regards,
The Academic Team
{current_app.config.get('APP_NAME', 'LMS')}
"""

            send_email(
                subject=subject,
                recipients=[student.email],
                text_body=student_body,
                html_body=StudentNotificationService._render_drop_email(student, drop_record)
            )
            
            # Email to parents
            parent_contact = student.get_primary_contact()
            if parent_contact and parent_contact.get('email'):
                parent_subject = f"Course Enrollment Update - {student.full_name}"
                parent_body = f"""
Dear Parent/Guardian,

We are writing to inform you that {student.full_name}'s enrollment in the course has been discontinued as of {drop_record.drop_date.strftime('%d %B %Y')}.

We understand this may be disappointing, and we want to ensure you have all the necessary information regarding this decision.

If you have any questions or would like to discuss this matter further, please feel free to contact us.

Best regards,
The Academic Team
{current_app.config.get('APP_NAME', 'LMS')}
"""
                
                send_email(
                    subject=parent_subject,
                    recipients=[parent_contact['email']],
                    text_body=parent_body
                )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending drop notification: {str(e)}")
            return False
    
    @staticmethod
    def send_reactivation_notification(student):
        """Send reactivation welcome back message"""
        try:
            subject = f"🎉 Welcome Back! Your Enrollment Has Been Reactivated"
            
            student_body = f"""
Dear {student.full_name},

Great news! Your enrollment has been successfully reactivated as of {datetime.now().strftime('%d %B %Y')}.

We're excited to welcome you back and look forward to continuing your learning journey with us.

Next Steps:
• Your classes will resume as scheduled
• You will receive class notifications and updates
• All learning materials remain accessible

If you have any questions or need assistance getting back on track, please don't hesitate to reach out to our support team.

Welcome back!

Best regards,
The Academic Team
{current_app.config.get('APP_NAME', 'LMS')}
"""

            send_email(
                subject=subject,
                recipients=[student.email],
                text_body=student_body
            )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending reactivation notification: {str(e)}")
            return False
    
    @staticmethod
    def send_tutor_drop_notification(student, drop_record):
        """Notify tutors about student drop"""
        try:
            # Get student's tutors (you'll need to implement this based on your tutor-student relationship)
            from app.models.class_model import Class
            from app.models.tutor import Tutor
            
            # Find tutors who have taught this student
            tutor_classes = Class.query.filter(
                Class.primary_student_id == student.id,
                Class.tutor_id.isnot(None)
            ).distinct(Class.tutor_id).all()
            
            tutors = []
            for cls in tutor_classes:
                if cls.tutor and cls.tutor not in tutors:
                    tutors.append(cls.tutor)
            
            for tutor in tutors:
                if tutor.user and tutor.user.email:
                    subject = f"Student Withdrawal Notification - {student.full_name}"
                    
                    tutor_body = f"""
Dear {tutor.user.full_name},

We want to inform you that {student.full_name}, one of your students, has been withdrawn from the course.

Student Details:
• Name: {student.full_name}
• Grade: {student.grade}
• Drop Date: {drop_record.drop_date.strftime('%d %B %Y')}
• Reason: {drop_record.get_drop_reason_display()}

{'All future scheduled classes with this student have been cancelled.' if drop_record.future_classes_cancelled else ''}

Thank you for your understanding.

Best regards,
Academic Administration
{current_app.config.get('APP_NAME', 'LMS')}
"""
                    
                    send_email(
                        subject=subject,
                        recipients=[tutor.user.email],
                        text_body=tutor_body
                    )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending tutor drop notification: {str(e)}")
            return False
    
    @staticmethod
    def send_tutor_reactivation_notification(student):
        """Notify tutors about student reactivation"""
        try:
            # Similar to drop notification, find relevant tutors
            from app.models.class_model import Class
            
            tutor_classes = Class.query.filter(
                Class.primary_student_id == student.id,
                Class.tutor_id.isnot(None)
            ).distinct(Class.tutor_id).limit(3).all()  # Limit to recent tutors
            
            tutors = []
            for cls in tutor_classes:
                if cls.tutor and cls.tutor not in tutors:
                    tutors.append(cls.tutor)
            
            for tutor in tutors:
                if tutor.user and tutor.user.email:
                    subject = f"Student Reactivation Notice - {student.full_name}"
                    
                    tutor_body = f"""
Dear {tutor.user.full_name},

We're pleased to inform you that {student.full_name} has been reactivated and will be resuming classes.

Student Details:
• Name: {student.full_name}
• Grade: {student.grade}
• Reactivation Date: {datetime.now().strftime('%d %B %Y')}

Please welcome them back warmly when you see them in class.

Best regards,
Academic Administration
{current_app.config.get('APP_NAME', 'LMS')}
"""
                    
                    send_email(
                        subject=subject,
                        recipients=[tutor.user.email],
                        text_body=tutor_body
                    )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending tutor reactivation notification: {str(e)}")
            return False
    
    @staticmethod
    def _render_graduation_email(student, graduation_record):
        """Render HTML email template for graduation"""
        return f"""
        <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 2rem;">🎓 Congratulations!</h1>
                <h2 style="margin: 0.5rem 0; font-weight: normal;">You've Graduated!</h2>
            </div>
            
            <div style="padding: 2rem; background: white;">
                <h3>Dear {student.full_name},</h3>
                
                <p style="font-size: 1.1rem; color: #333;">
                    We are absolutely thrilled to congratulate you on successfully completing your course! 
                    This is a significant achievement that represents your hard work, dedication, and perseverance.
                </p>
                
                <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 8px; margin: 1.5rem 0;">
                    <h4 style="margin-top: 0; color: #495057;">🏆 Graduation Details</h4>
                    <ul style="list-style: none; padding: 0;">
                        <li style="margin-bottom: 0.5rem;"><strong>Graduation Date:</strong> {graduation_record.graduation_date.strftime('%d %B %Y')}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Final Grade:</strong> {graduation_record.final_grade or 'Excellent'}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Performance:</strong> {graduation_record.overall_performance_rating.title()}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Certificate #:</strong> {graduation_record.certificate_number}</li>
                    </ul>
                </div>
                
                {f'<div style="background: #e7f3ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #0066cc;"><p><strong>Personal Message:</strong><br>{graduation_record.feedback}</p></div>' if graduation_record.feedback else ''}
                
                <p style="font-size: 1.1rem; margin-top: 2rem;">
                    We wish you all the best in your future endeavors and are confident that you will continue to achieve great things!
                </p>
                
                <div style="text-align: center; margin-top: 2rem;">
                    <p style="font-weight: bold; color: #667eea;">The Academic Team</p>
                    <p>{current_app.config.get('APP_NAME', 'LMS')}</p>
                </div>
            </div>
        </div>
        """
    
    @staticmethod
    def _render_parent_graduation_email(student, graduation_record, parent_contact):
        """Render HTML email template for parent graduation notification"""
        return f"""
        <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
            <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); padding: 2rem; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 2rem;">🎉 Great News!</h1>
                <h2 style="margin: 0.5rem 0; font-weight: normal;">Your Child Has Graduated!</h2>
            </div>
            
            <div style="padding: 2rem; background: white;">
                <h3>Dear {parent_contact.get('name', 'Parent/Guardian')},</h3>
                
                <p style="font-size: 1.1rem; color: #333;">
                    We are delighted to share this wonderful milestone with you. <strong>{student.full_name}</strong> has 
                    successfully completed their course and graduated with flying colors!
                </p>
                
                <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 8px; margin: 1.5rem 0;">
                    <h4 style="margin-top: 0; color: #495057;">🌟 Achievement Summary</h4>
                    <ul style="list-style: none; padding: 0;">
                        <li style="margin-bottom: 0.5rem;"><strong>Student:</strong> {student.full_name}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Graduation Date:</strong> {graduation_record.graduation_date.strftime('%d %B %Y')}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Final Grade:</strong> {graduation_record.final_grade or 'Outstanding'}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Performance:</strong> {graduation_record.overall_performance_rating.title()}</li>
                    </ul>
                </div>
                
                <p style="font-size: 1.1rem; margin-top: 2rem;">
                    Your support and encouragement have been instrumental in {student.full_name}'s success. 
                    This achievement is a testament to both your guidance and their dedication.
                </p>
                
                <div style="text-align: center; margin-top: 2rem; padding: 1rem; background: #e8f5e8; border-radius: 8px;">
                    <p style="font-size: 1.2rem; margin: 0; color: #155724;">
                        <strong>Congratulations to your entire family! 🎊</strong>
                    </p>
                </div>
                
                <div style="text-align: center; margin-top: 2rem;">
                    <p style="font-weight: bold; color: #28a745;">Warm Regards,</p>
                    <p>The Academic Team<br>{current_app.config.get('APP_NAME', 'LMS')}</p>
                </div>
            </div>
        </div>
        """
    
    @staticmethod
    def _render_drop_email(student, drop_record):
        """Render HTML email template for drop notification"""
        return f"""
        <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
            <div style="background: #6c757d; padding: 2rem; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 1.8rem;">Course Enrollment Update</h1>
            </div>
            
            <div style="padding: 2rem; background: white;">
                <h3>Dear {student.full_name},</h3>
                
                <p style="color: #333;">
                    We are writing to inform you that your enrollment has been discontinued as of 
                    <strong>{drop_record.drop_date.strftime('%d %B %Y')}</strong>.
                </p>
                
                <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 8px; margin: 1.5rem 0;">
                    <h4 style="margin-top: 0; color: #495057;">📋 Details</h4>
                    <ul style="list-style: none; padding: 0;">
                        <li style="margin-bottom: 0.5rem;"><strong>Drop Date:</strong> {drop_record.drop_date.strftime('%d %B %Y')}</li>
                        <li style="margin-bottom: 0.5rem;"><strong>Reason:</strong> {drop_record.get_drop_reason_display()}</li>
                        {f'<li style="margin-bottom: 0.5rem;"><strong>Refund Due:</strong> ₹{drop_record.refund_amount:.2f}</li>' if drop_record.refund_amount and drop_record.refund_amount > 0 else ''}
                    </ul>
                    
                    <div style="margin-top: 1rem; padding: 1rem; background: white; border-radius: 4px;">
                        <strong>Additional Details:</strong><br>
                        {drop_record.detailed_reason}
                    </div>
                </div>
                
                {f'<div style="background: #d4edda; padding: 1rem; border-radius: 8px; border-left: 4px solid #28a745; margin: 1rem 0;"><p style="margin: 0;"><strong>Good News:</strong> You are welcome to re-enroll with us in the future.</p></div>' if drop_record.re_enrollment_allowed and not drop_record.blacklisted else ''}
                
                <p style="margin-top: 2rem;">
                    If you have any questions or concerns, please don't hesitate to contact our support team.
                </p>
                
                <div style="text-align: center; margin-top: 2rem;">
                    <p style="font-weight: bold; color: #6c757d;">Best Regards,</p>
                    <p>The Academic Team<br>{current_app.config.get('APP_NAME', 'LMS')}</p>
                </div>
            </div>
        </div>
        """