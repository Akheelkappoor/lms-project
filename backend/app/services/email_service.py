import boto3
from botocore.exceptions import ClientError
import os
import requests

class EmailService:
    def __init__(self):
        self.ses_client = boto3.client(
            'ses',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        self.from_email = os.environ.get('FROM_EMAIL', 'noreply@yourlms.com')
    
    def send_welcome_email(self, to_email, username, temp_password):
        subject = "Welcome to i2Global LMS"
        body = f"""
        Welcome to i2Global Learning Management System!
        
        Your login credentials:
        Username: {username}
        Temporary Password: {temp_password}
        
        Please login and change your password immediately.
        
        Login URL: {os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/login
        
        Best regards,
        i2Global Team
        """
        
        return self._send_email(to_email, subject, body)
    
    def send_password_reset_email(self, to_email, reset_token):
        subject = "Password Reset - i2Global LMS"
        reset_url = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={reset_token}"
        
        body = f"""
        You requested a password reset for your i2Global LMS account.
        
        Click the link below to reset your password:
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you didn't request this reset, please ignore this email.
        
        Best regards,
        i2Global Team
        """
        
        return self._send_email(to_email, subject, body)
    
    def send_class_reminder(self, to_email, class_details):
        subject = f"Class Reminder - {class_details['subject']}"
        body = f"""
        Reminder: Your class is starting soon!
        
        Subject: {class_details['subject']}
        Time: {class_details['start_time']}
        Duration: {class_details['duration']} minutes
        
        Join URL: {class_details['meeting_url']}
        
        Best regards,
        i2Global Team
        """
        
        return self._send_email(to_email, subject, body)
    
    def _send_email(self, to_email, subject, body):
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Text': {'Data': body}}
                }
            )
            return True
        except ClientError as e:
            print(f"Email sending failed: {e}")
            return False