import json
import requests
from datetime import datetime, timedelta
from flask import current_app, url_for
from app import db
from app.models.error_log import ErrorLog
from app.models.user import User
from email.mime.text import MIMEText


# Import email modules only when needed to avoid import issues
try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    EMAIL_AVAILABLE = True
except ImportError as e:
    EMAIL_AVAILABLE = False
    print(f"Email functionality not available: {e}")  # Use print instead of logger during import


class AlertManager:
    """Advanced alert and notification system"""
    
    def __init__(self):
        self.alert_channels = {
            'email': self.send_email_alert,
            'slack': self.send_slack_alert,
            'webhook': self.send_webhook_alert,
            'database': self.log_alert_to_database
        }
    
    def process_error_alert(self, error_log):
        """Process and send alerts based on error severity and type"""
        alert_config = self.get_alert_configuration(error_log)
        
        if not alert_config['should_alert']:
            return
        
        # Prepare alert data
        alert_data = self.prepare_alert_data(error_log)
        
        # Send alerts through configured channels
        for channel in alert_config['channels']:
            if channel in self.alert_channels:
                try:
                    self.alert_channels[channel](alert_data, error_log)
                except Exception as e:
                    current_app.logger.error(f"Failed to send alert via {channel}: {str(e)}")
    
    def get_alert_configuration(self, error_log):
        """Determine alert configuration based on error properties"""
        config = {
            'should_alert': False,
            'channels': [],
            'priority': 'low',
            'recipients': []
        }
        
        # Critical errors - immediate alerts
        if error_log.severity == 'critical':
            config.update({
                'should_alert': True,
                'channels': ['email', 'slack', 'webhook'],
                'priority': 'critical',
                'recipients': self.get_critical_alert_recipients()
            })
        
        # High severity errors - quick alerts
        elif error_log.severity == 'high':
            # Check if it's a repeat error in short time
            if not self.is_repeat_error(error_log, minutes=10):
                config.update({
                    'should_alert': True,
                    'channels': ['email', 'slack'],
                    'priority': 'high',
                    'recipients': self.get_high_alert_recipients()
                })
        
        # Authentication errors - special handling
        elif error_log.error_category == 'authentication':
            # Alert for repeated authentication failures
            if self.check_authentication_pattern(error_log):
                config.update({
                    'should_alert': True,
                    'channels': ['email', 'database'],
                    'priority': 'medium',
                    'recipients': self.get_security_recipients()
                })
        
        # Database errors - system admin alerts
        elif error_log.error_category == 'database':
            config.update({
                'should_alert': True,
                'channels': ['email', 'webhook'],
                'priority': 'high',
                'recipients': self.get_system_admin_recipients()
            })
        
        return config
    
    def prepare_alert_data(self, error_log):
        """Prepare comprehensive alert data"""
        return {
            'error_id': error_log.error_id,
            'error_type': error_log.error_type,
            'error_category': error_log.error_category,
            'severity': error_log.severity,
            'message': error_log.error_message,
            'user_info': {
                'id': error_log.user_id,
                'name': error_log.user.full_name if error_log.user else 'Anonymous',
                'role': error_log.user_role,
                'email': error_log.user.email if error_log.user else None
            },
            'request_info': {
                'url': error_log.request_url,
                'method': error_log.request_method,
                'ip_address': error_log.ip_address,
                'user_agent': error_log.user_agent
            },
            'system_info': {
                'server_load': error_log.server_load,
                'memory_usage': error_log.memory_usage,
                'response_time': error_log.response_time
            },
            'timestamp': error_log.created_at.isoformat(),
            'dashboard_url': url_for('error_monitoring.error_detail', error_id=error_log.error_id, _external=True)
        }
    
    def send_email_alert(self, alert_data, error_log):
        """Send email alert"""
        try:
            if not EMAIL_AVAILABLE:
                current_app.logger.warning("Email functionality not available - skipping email alert")
                return
                
            smtp_config = current_app.config.get('MAIL_SETTINGS', {})
            if not smtp_config:
                current_app.logger.warning("No email configuration found - skipping email alert")
                return
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 {alert_data['severity'].upper()} Error Alert - {alert_data['error_type']}"
            msg['From'] = smtp_config.get('MAIL_USERNAME')
            msg['To'] = ', '.join(self.get_alert_recipients(error_log))
            
            # HTML email content
            html_content = self.create_email_template(alert_data)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            server = smtplib.SMTP(smtp_config.get('MAIL_SERVER'), smtp_config.get('MAIL_PORT'))
            server.starttls()
            server.login(smtp_config.get('MAIL_USERNAME'), smtp_config.get('MAIL_PASSWORD'))
            server.send_message(msg)
            server.quit()
            
            current_app.logger.info(f"Email alert sent for error {error_log.error_id}")
            
        except Exception as e:
            current_app.logger.error(f"Failed to send email alert: {str(e)}")
    
    def send_slack_alert(self, alert_data, error_log):
        """Send Slack alert"""
        try:
            webhook_url = current_app.config.get('SLACK_WEBHOOK_URL')
            if not webhook_url:
                return
            
            # Determine color based on severity
            color_map = {
                'critical': '#ff0000',
                'high': '#ff6600',
                'medium': '#ffcc00',
                'low': '#00ff00'
            }
            
            # Create Slack message
            slack_message = {
                "attachments": [
                    {
                        "color": color_map.get(alert_data['severity'], '#808080'),
                        "title": f"{alert_data['severity'].upper()} Error Alert",
                        "title_link": alert_data['dashboard_url'],
                        "fields": [
                            {
                                "title": "Error Type",
                                "value": alert_data['error_type'],
                                "short": True
                            },
                            {
                                "title": "Category",
                                "value": alert_data['error_category'],
                                "short": True
                            },
                            {
                                "title": "User",
                                "value": f"{alert_data['user_info']['name']} ({alert_data['user_info']['role']})",
                                "short": True
                            },
                            {
                                "title": "IP Address",
                                "value": alert_data['request_info']['ip_address'],
                                "short": True
                            },
                            {
                                "title": "Message",
                                "value": alert_data['message'][:200] + ('...' if len(alert_data['message']) > 200 else ''),
                                "short": False
                            }
                        ],
                        "footer": "LMS Error Monitoring",
                        "ts": int(datetime.fromisoformat(alert_data['timestamp']).timestamp())
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(webhook_url, json=slack_message, timeout=10)
            response.raise_for_status()
            
            current_app.logger.info(f"Slack alert sent for error {error_log.error_id}")
            
        except Exception as e:
            current_app.logger.error(f"Failed to send Slack alert: {str(e)}")
    
    def send_webhook_alert(self, alert_data, error_log):
        """Send webhook alert to external systems"""
        try:
            webhook_urls = current_app.config.get('ALERT_WEBHOOKS', [])
            
            for webhook_url in webhook_urls:
                payload = {
                    'event': 'error_alert',
                    'severity': alert_data['severity'],
                    'error_data': alert_data,
                    'timestamp': alert_data['timestamp']
                }
                
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'LMS-Error-Monitor/1.0'
                }
                
                response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
            
            current_app.logger.info(f"Webhook alerts sent for error {error_log.error_id}")
            
        except Exception as e:
            current_app.logger.error(f"Failed to send webhook alert: {str(e)}")
    
    def log_alert_to_database(self, alert_data, error_log):
        """Log alert to database for audit trail"""
        try:
            # You can create an AlertLog model to track all sent alerts
            current_app.logger.info(f"Alert logged for error {error_log.error_id}: {alert_data['severity']} - {alert_data['error_type']}")
            
        except Exception as e:
            current_app.logger.error(f"Failed to log alert to database: {str(e)}")
    
    def create_email_template(self, alert_data):
        """Create HTML email template"""
        severity_colors = {
            'critical': '#dc3545',
            'high': '#fd7e14',
            'medium': '#ffc107',
            'low': '#28a745'
        }
        
        color = severity_colors.get(alert_data['severity'], '#6c757d')
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: {color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .field {{ margin-bottom: 15px; }}
                .label {{ font-weight: bold; color: #495057; }}
                .value {{ margin-top: 5px; padding: 8px; background: #f8f9fa; border-radius: 4px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: {color}; color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 {alert_data['severity'].upper()} Error Alert</h1>
                    <p>LMS Error Monitoring System</p>
                </div>
                <div class="content">
                    <div class="field">
                        <div class="label">Error Type:</div>
                        <div class="value">{alert_data['error_type']}</div>
                    </div>
                    <div class="field">
                        <div class="label">Category:</div>
                        <div class="value">{alert_data['error_category']}</div>
                    </div>
                    <div class="field">
                        <div class="label">Message:</div>
                        <div class="value">{alert_data['message']}</div>
                    </div>
                    <div class="field">
                        <div class="label">User:</div>
                        <div class="value">{alert_data['user_info']['name']} ({alert_data['user_info']['role']})</div>
                    </div>
                    <div class="field">
                        <div class="label">Request URL:</div>
                        <div class="value">{alert_data['request_info']['url']}</div>
                    </div>
                    <div class="field">
                        <div class="label">IP Address:</div>
                        <div class="value">{alert_data['request_info']['ip_address']}</div>
                    </div>
                    <div class="field">
                        <div class="label">Timestamp:</div>
                        <div class="value">{alert_data['timestamp']}</div>
                    </div>
                    <div style="text-align: center;">
                        <a href="{alert_data['dashboard_url']}" class="button">View Error Details</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def is_repeat_error(self, error_log, minutes=10):
        """Check if this is a repeat error within specified minutes"""
        time_threshold = error_log.created_at - timedelta(minutes=minutes)
        
        similar_errors = ErrorLog.query.filter(
            ErrorLog.error_type == error_log.error_type,
            ErrorLog.created_at >= time_threshold,
            ErrorLog.id != error_log.id
        ).count()
        
        return similar_errors > 0
    
    def check_authentication_pattern(self, error_log):
        """Check for suspicious authentication patterns"""
        if error_log.error_category != 'authentication':
            return False
        
        # Check for multiple failed attempts from same IP
        one_hour_ago = error_log.created_at - timedelta(hours=1)
        
        failed_attempts = ErrorLog.query.filter(
            ErrorLog.error_category == 'authentication',
            ErrorLog.ip_address == error_log.ip_address,
            ErrorLog.created_at >= one_hour_ago
        ).count()
        
        return failed_attempts >= 5  # Alert if 5 or more attempts
    
    def get_alert_recipients(self, error_log):
        """Get appropriate recipients based on error type"""
        if error_log.severity == 'critical':
            return self.get_critical_alert_recipients()
        elif error_log.severity == 'high':
            return self.get_high_alert_recipients()
        elif error_log.error_category == 'authentication':
            return self.get_security_recipients()
        elif error_log.error_category == 'database':
            return self.get_system_admin_recipients()
        else:
            return self.get_default_recipients()
    
    def get_critical_alert_recipients(self):
        """Get recipients for critical alerts"""
        # Get all superadmins and admins
        critical_users = User.query.filter(
            User.role.in_(['superadmin', 'admin']),
            User.is_active == True
        ).all()
        
        return [user.email for user in critical_users if user.email]
    
    def get_high_alert_recipients(self):
        """Get recipients for high severity alerts"""
        # Get admins and coordinators
        high_users = User.query.filter(
            User.role.in_(['superadmin', 'admin', 'coordinator']),
            User.is_active == True
        ).all()
        
        return [user.email for user in high_users if user.email]
    
    def get_security_recipients(self):
        """Get recipients for security-related alerts"""
        # Get security-focused admins
        return self.get_critical_alert_recipients()
    
    def get_system_admin_recipients(self):
        """Get recipients for system administration alerts"""
        # Get technical admins
        system_users = User.query.filter(
            User.role == 'superadmin',
            User.is_active == True
        ).all()
        
        return [user.email for user in system_users if user.email]
    
    def get_default_recipients(self):
        """Get default recipients"""
        # Get at least one admin
        admin = User.query.filter(
            User.role.in_(['superadmin', 'admin']),
            User.is_active == True
        ).first()
        
        return [admin.email] if admin and admin.email else []


class AlertScheduler:
    """Schedule and batch alerts to prevent spam"""
    
    def __init__(self):
        self.alert_manager = AlertManager()
        self.batch_alerts = []
        self.last_batch_send = datetime.utcnow()
    
    def add_alert(self, error_log):
        """Add error to alert queue"""
        # Immediate alerts for critical errors
        if error_log.severity == 'critical':
            self.alert_manager.process_error_alert(error_log)
        else:
            self.batch_alerts.append(error_log)
    
    def process_batch_alerts(self):
        """Process batched alerts"""
        if not self.batch_alerts:
            return
        
        # Group alerts by severity and type
        grouped_alerts = self.group_alerts(self.batch_alerts)
        
        # Send summary alerts for each group
        for group_key, alerts in grouped_alerts.items():
            self.send_batch_alert(group_key, alerts)
        
        # Clear batch
        self.batch_alerts = []
        self.last_batch_send = datetime.utcnow()
    
    def group_alerts(self, alerts):
        """Group alerts by severity and type"""
        groups = {}
        
        for alert in alerts:
            key = f"{alert.severity}_{alert.error_category}"
            if key not in groups:
                groups[key] = []
            groups[key].append(alert)
        
        return groups
    
    def send_batch_alert(self, group_key, alerts):
        """Send summary alert for a group of errors"""
        try:
            # Create summary data
            summary_data = {
                'group_key': group_key,
                'count': len(alerts),
                'severity': alerts[0].severity,
                'category': alerts[0].error_category,
                'time_range': {
                    'start': min(alert.created_at for alert in alerts),
                    'end': max(alert.created_at for alert in alerts)
                },
                'affected_users': len(set(alert.user_id for alert in alerts if alert.user_id)),
                'top_errors': self.get_top_errors_from_batch(alerts),
                'dashboard_url': url_for('error_monitoring.search', _external=True)
            }
            
            # Send summary alert (implement based on your needs)
            current_app.logger.info(f"Batch alert: {summary_data['count']} {group_key} errors")
            
        except Exception as e:
            current_app.logger.error(f"Failed to send batch alert: {str(e)}")
    
    def get_top_errors_from_batch(self, alerts, limit=5):
        """Get top errors from batch"""
        error_counts = {}
        
        for alert in alerts:
            key = alert.error_type
            if key not in error_counts:
                error_counts[key] = []
            error_counts[key].append(alert)
        
        # Sort by count and return top errors
        sorted_errors = sorted(error_counts.items(), key=lambda x: len(x[1]), reverse=True)
        
        return [
            {
                'error_type': error_type,
                'count': len(error_list),
                'example_message': error_list[0].error_message
            }
            for error_type, error_list in sorted_errors[:limit]
        ]


# Global alert manager instance
alert_manager = AlertManager()
alert_scheduler = AlertScheduler()


def send_error_alert(error_log):
    """Main function to send error alerts"""
    try:
        alert_scheduler.add_alert(error_log)
    except Exception as e:
        current_app.logger.error(f"Failed to process error alert: {str(e)}")


def process_batch_alerts():
    """Function to be called by scheduler to process batched alerts"""
    try:
        alert_scheduler.process_batch_alerts()
    except Exception as e:
        current_app.logger.error(f"Failed to process batch alerts: {str(e)}")