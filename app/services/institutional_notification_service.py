"""
Institutional Notification Service
Handles system-wide notifications including holidays, emergencies, and announcements
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from flask import render_template, current_app
from app import db
from app.models.system_notification import SystemNotification, UserSystemNotification
from app.models.user import User
from app.models.student import Student
from app.models.department import Department
from app.utils.email import send_email
import json

class NotificationType:
    """Notification type constants"""
    HOLIDAY = "holiday"
    EMERGENCY = "emergency"
    ACADEMIC = "academic"
    ADMINISTRATIVE = "administrative"
    GENERAL = "general"
    MAINTENANCE = "maintenance"

class NotificationPriority:
    """Notification priority levels"""
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

class InstitutionalNotificationService:
    """Service for managing institutional notifications"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    # ============ NOTIFICATION CREATION ============
    
    def create_system_notification(self, 
                                  title: str,
                                  message: str,
                                  created_by: int,
                                  notification_type: str = NotificationType.GENERAL,
                                  priority: str = NotificationPriority.NORMAL,
                                  target_type: str = 'all',
                                  target_departments: List[int] = None,
                                  target_roles: List[str] = None,
                                  target_users: List[int] = None,
                                  email_enabled: bool = True,
                                  popup_enabled: bool = False,
                                  include_parents: bool = False,
                                  send_immediately: bool = True,
                                  scheduled_for: datetime = None,
                                  expires_at: datetime = None) -> SystemNotification:
        """
        Create a new system notification
        """
        try:
            # Create the notification
            notification = SystemNotification(
                title=title,
                message=message,
                type=notification_type,
                priority=priority,
                target_type=target_type,
                email_enabled=email_enabled,
                popup_enabled=popup_enabled,
                include_parents=include_parents,
                send_immediately=send_immediately,
                scheduled_for=scheduled_for,
                expires_at=expires_at,
                created_by=created_by
            )
            
            # Set targeting
            if target_departments:
                notification.set_target_departments(target_departments)
            if target_roles:
                notification.set_target_roles(target_roles)
            if target_users:
                notification.set_target_users(target_users)
            
            db.session.add(notification)
            db.session.commit()
            
            self.logger.info(f"System notification created: {notification.id} - {title}")
            
            # Send notification if immediate
            if send_immediately:
                self.send_notification(notification.id)
            
            return notification
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error creating system notification: {str(e)}")
            raise
    
    def create_holiday_notification(self,
                                   title: str,
                                   message: str,
                                   holiday_date: datetime,
                                   created_by: int,
                                   target_departments: List[int] = None) -> SystemNotification:
        """Create a holiday notification"""
        
        # Automatically set to high priority and include popup for holidays
        return self.create_system_notification(
            title=title,
            message=message,
            created_by=created_by,
            notification_type=NotificationType.HOLIDAY,
            priority=NotificationPriority.HIGH,
            target_type='department' if target_departments else 'all',
            target_departments=target_departments,
            email_enabled=True,
            popup_enabled=True,
            include_parents=True,  # Include parents for student notifications
            expires_at=holiday_date + timedelta(days=1)
        )
    
    def create_emergency_notification(self,
                                    title: str,
                                    message: str,
                                    created_by: int,
                                    target_type: str = 'all',
                                    target_departments: List[int] = None) -> SystemNotification:
        """Create an emergency notification"""
        
        return self.create_system_notification(
            title=title,
            message=message,
            created_by=created_by,
            notification_type=NotificationType.EMERGENCY,
            priority=NotificationPriority.CRITICAL,
            target_type=target_type,
            target_departments=target_departments,
            email_enabled=True,
            popup_enabled=True,
            include_parents=True,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
    
    def create_maintenance_notification(self,
                                      title: str,
                                      message: str,
                                      maintenance_start: datetime,
                                      maintenance_end: datetime,
                                      created_by: int) -> SystemNotification:
        """Create a system maintenance notification"""
        
        return self.create_system_notification(
            title=title,
            message=message,
            created_by=created_by,
            notification_type=NotificationType.MAINTENANCE,
            priority=NotificationPriority.HIGH,
            target_type='all',
            email_enabled=True,
            popup_enabled=True,
            scheduled_for=maintenance_start - timedelta(hours=2),  # Send 2 hours before
            expires_at=maintenance_end
        )
    
    # ============ NOTIFICATION SENDING ============
    
    def send_notification(self, notification_id: int) -> bool:
        """Send a system notification to all targeted users"""
        try:
            notification = SystemNotification.query.get(notification_id)
            if not notification:
                self.logger.error(f"Notification {notification_id} not found")
                return False
            
            if not notification.can_be_sent():
                self.logger.warning(f"Notification {notification_id} cannot be sent (inactive or expired)")
                return False
            
            # Get target users
            target_user_ids = notification.get_target_user_ids()
            if not target_user_ids:
                self.logger.warning(f"No target users found for notification {notification_id}")
                return False
            
            # Create user notification records
            self._create_user_notification_records(notification, target_user_ids)
            
            # Send emails if enabled
            email_count = 0
            if notification.email_enabled:
                email_count = self._send_notification_emails(notification, target_user_ids)
            
            # Update delivery counts
            notification.update_delivery_count(email_sent=email_count)
            notification.mark_as_sent()
            
            self.logger.info(f"Notification {notification_id} sent to {len(target_user_ids)} users")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending notification {notification_id}: {str(e)}")
            return False
    
    def _create_user_notification_records(self, notification: SystemNotification, user_ids: List[int]):
        """Create UserSystemNotification records for tracking"""
        try:
            for user_id in user_ids:
                # Check if record already exists
                existing = UserSystemNotification.query.filter_by(
                    system_notification_id=notification.id,
                    user_id=user_id
                ).first()
                
                if not existing:
                    user_notification = UserSystemNotification(
                        system_notification_id=notification.id,
                        user_id=user_id
                    )
                    db.session.add(user_notification)
            
            db.session.commit()
            self.logger.info(f"Created {len(user_ids)} user notification records")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error creating user notification records: {str(e)}")
    
    def _send_notification_emails(self, notification: SystemNotification, user_ids: List[int]) -> int:
        """Send notification emails to users"""
        email_count = 0
        
        try:
            users = User.query.filter(User.id.in_(user_ids)).all()
            
            for user in users:
                if user.email:
                    # Prepare email recipients
                    recipients = [user.email]
                    
                    # Add parent emails for students if enabled
                    if notification.include_parents and user.role == 'student':
                        parent_emails = self._get_parent_emails(user.id)
                        recipients.extend(parent_emails)
                    
                    # Prepare email context
                    context = {
                        'user': user,
                        'notification': notification,
                        'app_name': current_app.config.get('APP_NAME', 'LMS'),
                        'company_name': current_app.config.get('COMPANY_NAME', 'Institution'),
                        'base_url': current_app.config.get('BASE_URL', 'http://localhost:5000')
                    }
                    
                    # Determine email template based on notification type
                    template = self._get_email_template(notification.type)
                    
                    # Send email
                    try:
                        result = send_email(
                            subject=f"[{context['app_name']}] {notification.title}",
                            recipients=recipients,
                            html_body=render_template(template, **context),
                            text_body=self._generate_text_body(notification, user),
                            sync=False  # Send asynchronously
                        )
                        
                        if result:
                            email_count += 1
                            # Mark email as sent in user notification record
                            user_notification = UserSystemNotification.query.filter_by(
                                system_notification_id=notification.id,
                                user_id=user.id
                            ).first()
                            if user_notification:
                                user_notification.email_sent = True
                                db.session.commit()
                    
                    except Exception as email_error:
                        self.logger.error(f"Failed to send email to {user.email}: {str(email_error)}")
            
            self.logger.info(f"Sent {email_count} notification emails")
            return email_count
            
        except Exception as e:
            self.logger.error(f"Error sending notification emails: {str(e)}")
            return email_count
    
    def _get_parent_emails(self, user_id: int) -> List[str]:
        """Get parent email addresses for a student"""
        try:
            student = Student.query.filter_by(user_id=user_id).first()
            if not student:
                return []
            
            parent_details = student.get_parent_details()
            if not parent_details:
                return []
            
            emails = []
            father_email = parent_details.get('father', {}).get('email')
            mother_email = parent_details.get('mother', {}).get('email')
            
            if father_email:
                emails.append(father_email)
            if mother_email:
                emails.append(mother_email)
            
            return emails
            
        except Exception as e:
            self.logger.error(f"Error getting parent emails for user {user_id}: {str(e)}")
            return []
    
    def _get_email_template(self, notification_type: str) -> str:
        """Get appropriate email template based on notification type"""
        template_map = {
            NotificationType.HOLIDAY: 'email/notifications/holiday_notification.html',
            NotificationType.EMERGENCY: 'email/notifications/emergency_notification.html',
            NotificationType.ACADEMIC: 'email/notifications/academic_notification.html',
            NotificationType.ADMINISTRATIVE: 'email/notifications/administrative_notification.html',
            NotificationType.MAINTENANCE: 'email/notifications/maintenance_notification.html',
            NotificationType.GENERAL: 'email/notifications/general_notification.html'
        }
        return template_map.get(notification_type, 'email/notifications/general_notification.html')
    
    def _generate_text_body(self, notification: SystemNotification, user: User) -> str:
        """Generate plain text email body"""
        return f"""
Hello {user.full_name},

{notification.title}

{notification.message}

This is a {notification.priority} priority {notification.type} notification from {current_app.config.get('APP_NAME', 'LMS')}.

If you have any questions, please contact our support team.

Best regards,
{current_app.config.get('COMPANY_NAME', 'Institution')} Team
        """.strip()
    
    # ============ NOTIFICATION MANAGEMENT ============
    
    def get_user_unread_notifications(self, user_id: int, include_popup_only: bool = False) -> List[UserSystemNotification]:
        """Get unread notifications for a user"""
        query = UserSystemNotification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).join(SystemNotification).filter(
            SystemNotification.is_active == True
        )
        
        if include_popup_only:
            query = query.filter(SystemNotification.popup_enabled == True)
        
        return query.order_by(SystemNotification.created_at.desc()).all()
    
    def get_user_popup_notifications(self, user_id: int) -> List[UserSystemNotification]:
        """Get notifications that should show popup for user"""
        return UserSystemNotification.query.filter_by(
            user_id=user_id,
            popup_shown=False
        ).join(SystemNotification).filter(
            SystemNotification.popup_enabled == True,
            SystemNotification.is_active == True
        ).all()
    
    def mark_notification_read(self, notification_id: int, user_id: int) -> bool:
        """Mark a notification as read for a user"""
        try:
            user_notification = UserSystemNotification.query.filter_by(
                system_notification_id=notification_id,
                user_id=user_id
            ).first()
            
            if user_notification:
                user_notification.mark_as_read()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error marking notification as read: {str(e)}")
            return False
    
    def mark_popup_shown(self, notification_id: int, user_id: int) -> bool:
        """Mark a popup as shown for a user"""
        try:
            user_notification = UserSystemNotification.query.filter_by(
                system_notification_id=notification_id,
                user_id=user_id
            ).first()
            
            if user_notification:
                user_notification.mark_popup_shown()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error marking popup as shown: {str(e)}")
            return False
    
    def dismiss_notification(self, notification_id: int, user_id: int) -> bool:
        """Dismiss a notification for a user"""
        try:
            user_notification = UserSystemNotification.query.filter_by(
                system_notification_id=notification_id,
                user_id=user_id
            ).first()
            
            if user_notification:
                user_notification.dismiss()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error dismissing notification: {str(e)}")
            return False
    
    def get_notification_analytics(self, notification_id: int) -> Dict[str, Any]:
        """Get analytics for a notification"""
        try:
            notification = SystemNotification.query.get(notification_id)
            if not notification:
                return {}
            
            stats = notification.get_delivery_stats()
            
            # Get user breakdown
            user_notifications = notification.user_notifications.all()
            user_breakdown = {
                'total_users': len(user_notifications),
                'emails_sent': len([un for un in user_notifications if un.email_sent]),
                'popups_shown': len([un for un in user_notifications if un.popup_shown]),
                'read_notifications': len([un for un in user_notifications if un.is_read]),
                'dismissed_notifications': len([un for un in user_notifications if un.is_dismissed])
            }
            
            return {
                'basic_stats': stats,
                'user_breakdown': user_breakdown,
                'notification_details': notification.to_dict()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting notification analytics: {str(e)}")
            return {}
    
    # ============ BULK OPERATIONS ============
    
    def send_bulk_department_notification(self,
                                        title: str,
                                        message: str,
                                        department_ids: List[int],
                                        created_by: int,
                                        notification_type: str = NotificationType.ADMINISTRATIVE,
                                        priority: str = NotificationPriority.NORMAL,
                                        include_parents: bool = False) -> SystemNotification:
        """Send notification to multiple departments"""
        
        return self.create_system_notification(
            title=title,
            message=message,
            created_by=created_by,
            notification_type=notification_type,
            priority=priority,
            target_type='department',
            target_departments=department_ids,
            email_enabled=True,
            popup_enabled=(priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL]),
            include_parents=include_parents
        )
    
    def send_role_based_notification(self,
                                   title: str,
                                   message: str,
                                   target_roles: List[str],
                                   created_by: int,
                                   notification_type: str = NotificationType.ADMINISTRATIVE,
                                   priority: str = NotificationPriority.NORMAL) -> SystemNotification:
        """Send notification to specific roles"""
        
        return self.create_system_notification(
            title=title,
            message=message,
            created_by=created_by,
            notification_type=notification_type,
            priority=priority,
            target_type='role',
            target_roles=target_roles,
            email_enabled=True,
            popup_enabled=(priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL])
        )


# Global service instance
institutional_notification_service = InstitutionalNotificationService()