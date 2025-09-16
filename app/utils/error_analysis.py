import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from sqlalchemy import func, desc, and_, or_
from app import db
from app.models.error_log import ErrorLog, UserActivityLog, SystemHealthLog
from app.models.user import User


class ErrorAnalyzer:
    """Advanced error analysis and pattern detection"""
    
    def __init__(self):
        self.analysis_cache = {}
        self.cache_ttl = timedelta(minutes=15)
    
    def get_comprehensive_error_report(self, days=30):
        """Generate comprehensive error analysis report"""
        cache_key = f"comprehensive_report_{days}"
        
        if self._is_cache_valid(cache_key):
            return self.analysis_cache[cache_key]['data']
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        report = {
            'summary': self.get_error_summary(start_date),
            'trends': self.get_error_trends(start_date),
            'patterns': self.detect_error_patterns(start_date),
            'user_analysis': self.get_user_error_analysis(start_date),
            'system_correlation': self.analyze_system_correlation(start_date),
            'recommendations': self.generate_recommendations(start_date),
            'top_issues': self.get_top_issues(start_date),
            'resolution_analysis': self.get_resolution_analysis(start_date)
        }
        
        # Cache the results
        self._cache_data(cache_key, report)
        
        return report
    
    def get_error_summary(self, start_date):
        """Get error summary statistics"""
        total_errors = ErrorLog.query.filter(ErrorLog.created_at >= start_date).count()
        
        # Errors by severity
        severity_stats = dict(db.session.query(
            ErrorLog.severity, func.count(ErrorLog.id)
        ).filter(ErrorLog.created_at >= start_date).group_by(ErrorLog.severity).all())
        
        # Errors by category
        category_stats = dict(db.session.query(
            ErrorLog.error_category, func.count(ErrorLog.id)
        ).filter(ErrorLog.created_at >= start_date).group_by(ErrorLog.error_category).all())
        
        # Resolution statistics
        resolution_stats = dict(db.session.query(
            ErrorLog.status, func.count(ErrorLog.id)
        ).filter(ErrorLog.created_at >= start_date).group_by(ErrorLog.status).all())
        
        # Calculate error rate
        total_activities = UserActivityLog.query.filter(
            UserActivityLog.created_at >= start_date
        ).count()
        
        error_rate = (total_errors / total_activities * 100) if total_activities > 0 else 0
        
        return {
            'total_errors': total_errors,
            'error_rate': round(error_rate, 2),
            'severity_breakdown': severity_stats,
            'category_breakdown': category_stats,
            'resolution_breakdown': resolution_stats,
            'avg_errors_per_day': round(total_errors / max((datetime.utcnow() - start_date).days, 1), 2)
        }
    
    def get_error_trends(self, start_date, granularity='daily'):
        """Get error trends over time"""
        if granularity == 'daily':
            date_format = func.date(ErrorLog.created_at)
        elif granularity == 'hourly':
            date_format = func.date_format(ErrorLog.created_at, '%Y-%m-%d %H:00:00')
        else:
            date_format = func.date(ErrorLog.created_at)
        
        # Error trends by date
        trend_data = db.session.query(
            date_format.label('date'),
            ErrorLog.severity,
            func.count(ErrorLog.id).label('count')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            date_format, ErrorLog.severity
        ).order_by(date_format).all()
        
        # Process trend data
        trends = defaultdict(lambda: defaultdict(int))
        for date, severity, count in trend_data:
            trends[str(date)][severity] = count
        
        # Error trends by category
        category_trends = db.session.query(
            date_format.label('date'),
            ErrorLog.error_category,
            func.count(ErrorLog.id).label('count')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            date_format, ErrorLog.error_category
        ).order_by(date_format).all()
        
        category_trend_data = defaultdict(lambda: defaultdict(int))
        for date, category, count in category_trends:
            category_trend_data[str(date)][category] = count
        
        return {
            'severity_trends': dict(trends),
            'category_trends': dict(category_trend_data)
        }
    
    def detect_error_patterns(self, start_date):
        """Detect suspicious error patterns"""
        patterns = {}
        
        # Pattern 1: Rapid succession errors
        patterns['rapid_succession'] = self._detect_rapid_succession_errors(start_date)
        
        # Pattern 2: User-specific error spikes
        patterns['user_spikes'] = self._detect_user_error_spikes(start_date)
        
        # Pattern 3: Time-based patterns
        patterns['time_patterns'] = self._detect_time_patterns(start_date)
        
        # Pattern 4: IP-based suspicious activity
        patterns['ip_suspicious'] = self._detect_suspicious_ip_activity(start_date)
        
        # Pattern 5: Error clustering
        patterns['error_clusters'] = self._detect_error_clusters(start_date)
        
        return patterns
    
    def _detect_rapid_succession_errors(self, start_date):
        """Detect errors happening in rapid succession"""
        # Find errors within 5 minutes of each other from same user/IP
        rapid_errors = []
        
        errors = ErrorLog.query.filter(
            ErrorLog.created_at >= start_date
        ).order_by(ErrorLog.created_at).all()
        
        for i in range(len(errors) - 1):
            current = errors[i]
            next_error = errors[i + 1]
            
            time_diff = (next_error.created_at - current.created_at).total_seconds()
            
            if (time_diff <= 300 and  # Within 5 minutes
                (current.user_id == next_error.user_id or 
                 current.ip_address == next_error.ip_address)):
                
                rapid_errors.append({
                    'error1_id': current.error_id,
                    'error2_id': next_error.error_id,
                    'time_diff_seconds': time_diff,
                    'user_id': current.user_id,
                    'ip_address': current.ip_address
                })
        
        return rapid_errors[:20]  # Return top 20
    
    def _detect_user_error_spikes(self, start_date):
        """Detect users with unusual error spikes"""
        # Get average errors per user
        user_error_counts = db.session.query(
            ErrorLog.user_id,
            func.count(ErrorLog.id).label('error_count')
        ).filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.user_id.isnot(None)
        ).group_by(ErrorLog.user_id).all()
        
        if not user_error_counts:
            return []
        
        error_counts = [count for _, count in user_error_counts]
        avg_errors = np.mean(error_counts)
        std_errors = np.std(error_counts)
        
        # Find users with errors > mean + 2*std (outliers)
        threshold = avg_errors + 2 * std_errors
        
        spikes = []
        for user_id, count in user_error_counts:
            if count > threshold:
                user = User.query.get(user_id)
                spikes.append({
                    'user_id': user_id,
                    'user_name': user.full_name if user else 'Unknown',
                    'error_count': count,
                    'avg_errors': round(avg_errors, 2),
                    'spike_ratio': round(count / avg_errors, 2)
                })
        
        return sorted(spikes, key=lambda x: x['spike_ratio'], reverse=True)[:10]
    
    def _detect_time_patterns(self, start_date):
        """Detect time-based error patterns"""
        # Errors by hour of day
        hourly_errors = db.session.query(
            func.extract('hour', ErrorLog.created_at).label('hour'),
            func.count(ErrorLog.id).label('count')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            func.extract('hour', ErrorLog.created_at)
        ).all()
        
        # Errors by day of week
        daily_errors = db.session.query(
            func.dayofweek(ErrorLog.created_at).label('day'),
            func.count(ErrorLog.id).label('count')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            func.dayofweek(ErrorLog.created_at)
        ).all()
        
        return {
            'hourly_pattern': dict(hourly_errors),
            'daily_pattern': dict(daily_errors)
        }
    
    def _detect_suspicious_ip_activity(self, start_date):
        """Detect suspicious IP-based activity"""
        # IPs with high error rates
        ip_errors = db.session.query(
            ErrorLog.ip_address,
            func.count(ErrorLog.id).label('error_count'),
            func.count(func.distinct(ErrorLog.user_id)).label('unique_users')
        ).filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.ip_address.isnot(None)
        ).group_by(ErrorLog.ip_address).all()
        
        suspicious_ips = []
        for ip, error_count, unique_users in ip_errors:
            if error_count > 50 or (unique_users > 5 and error_count > 20):
                suspicious_ips.append({
                    'ip_address': ip,
                    'error_count': error_count,
                    'unique_users': unique_users,
                    'suspicion_score': error_count + (unique_users * 2)
                })
        
        return sorted(suspicious_ips, key=lambda x: x['suspicion_score'], reverse=True)[:10]
    
    def _detect_error_clusters(self, start_date):
        """Detect clusters of similar errors"""
        # Group similar errors
        error_clusters = db.session.query(
            ErrorLog.error_type,
            ErrorLog.error_message,
            func.count(ErrorLog.id).label('count'),
            func.min(ErrorLog.created_at).label('first_seen'),
            func.max(ErrorLog.created_at).label('last_seen')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            ErrorLog.error_type,
            ErrorLog.error_message
        ).having(
            func.count(ErrorLog.id) >= 5
        ).order_by(desc(func.count(ErrorLog.id))).limit(20).all()
        
        clusters = []
        for error_type, message, count, first_seen, last_seen in error_clusters:
            duration = (last_seen - first_seen).total_seconds() / 3600  # hours
            clusters.append({
                'error_type': error_type,
                'error_message': message[:100] + '...' if len(message) > 100 else message,
                'count': count,
                'first_seen': first_seen,
                'last_seen': last_seen,
                'duration_hours': round(duration, 2),
                'frequency': round(count / max(duration, 0.1), 2)  # errors per hour
            })
        
        return clusters
    
    def get_user_error_analysis(self, start_date):
        """Analyze errors by user segments"""
        # Errors by user role
        role_analysis = db.session.query(
            ErrorLog.user_role,
            func.count(ErrorLog.id).label('error_count'),
            func.count(func.distinct(ErrorLog.user_id)).label('affected_users')
        ).filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.user_role.isnot(None)
        ).group_by(ErrorLog.user_role).all()
        
        # Top error-prone users
        top_error_users = db.session.query(
            ErrorLog.user_id,
            User.full_name,
            User.role,
            func.count(ErrorLog.id).label('error_count')
        ).join(User, ErrorLog.user_id == User.id).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            ErrorLog.user_id, User.full_name, User.role
        ).order_by(desc(func.count(ErrorLog.id))).limit(20).all()
        
        return {
            'role_analysis': [
                {
                    'role': role,
                    'error_count': error_count,
                    'affected_users': affected_users,
                    'avg_errors_per_user': round(error_count / affected_users, 2)
                }
                for role, error_count, affected_users in role_analysis
            ],
            'top_error_users': [
                {
                    'user_id': user_id,
                    'name': name,
                    'role': role,
                    'error_count': error_count
                }
                for user_id, name, role, error_count in top_error_users
            ]
        }
    
    def analyze_system_correlation(self, start_date):
        """Analyze correlation between system metrics and errors"""
        # Get system health data
        health_data = SystemHealthLog.query.filter(
            SystemHealthLog.created_at >= start_date
        ).all()
        
        if not health_data:
            return {'correlation': 'No system health data available'}
        
        # Convert to DataFrame for analysis
        health_df = pd.DataFrame([{
            'timestamp': h.created_at,
            'cpu_usage': h.cpu_usage or 0,
            'memory_usage': h.memory_usage or 0,
            'error_rate': h.error_rate or 0
        } for h in health_data])
        
        if len(health_df) < 2:
            return {'correlation': 'Insufficient data for correlation analysis'}
        
        # Calculate correlations
        correlations = {}
        if 'cpu_usage' in health_df.columns:
            correlations['cpu_error_correlation'] = health_df['cpu_usage'].corr(health_df['error_rate'])
        if 'memory_usage' in health_df.columns:
            correlations['memory_error_correlation'] = health_df['memory_usage'].corr(health_df['error_rate'])
        
        # Find high-error periods
        high_error_periods = []
        if 'error_rate' in health_df.columns:
            threshold = health_df['error_rate'].mean() + health_df['error_rate'].std()
            high_periods = health_df[health_df['error_rate'] > threshold]
            
            for _, period in high_periods.iterrows():
                high_error_periods.append({
                    'timestamp': period['timestamp'].isoformat(),
                    'error_rate': period['error_rate'],
                    'cpu_usage': period['cpu_usage'],
                    'memory_usage': period['memory_usage']
                })
        
        return {
            'correlations': correlations,
            'high_error_periods': high_error_periods[:10]
        }
    
    def generate_recommendations(self, start_date):
        """Generate actionable recommendations based on error analysis"""
        recommendations = []
        
        # Get error data for analysis
        errors = ErrorLog.query.filter(ErrorLog.created_at >= start_date).all()
        
        if not errors:
            return ['No errors found in the specified period.']
        
        # Analyze authentication errors
        auth_errors = [e for e in errors if e.error_category == 'authentication']
        if len(auth_errors) > 50:
            recommendations.append({
                'category': 'Security',
                'priority': 'High',
                'title': 'High Authentication Error Rate',
                'description': f'{len(auth_errors)} authentication errors detected. Consider implementing account lockout and reviewing login security.',
                'action_items': [
                    'Implement progressive account lockout',
                    'Add CAPTCHA for repeated failures',
                    'Review suspicious IP addresses',
                    'Enable two-factor authentication'
                ]
            })
        
        # Analyze critical errors
        critical_errors = [e for e in errors if e.severity == 'critical']
        if len(critical_errors) > 10:
            recommendations.append({
                'category': 'System Stability',
                'priority': 'Critical',
                'title': 'High Critical Error Count',
                'description': f'{len(critical_errors)} critical errors need immediate attention.',
                'action_items': [
                    'Review all critical errors immediately',
                    'Implement automated recovery procedures',
                    'Set up proactive monitoring',
                    'Create incident response plan'
                ]
            })
        
        # Analyze database errors
        db_errors = [e for e in errors if e.error_category == 'database']
        if len(db_errors) > 20:
            recommendations.append({
                'category': 'Database',
                'priority': 'High',
                'title': 'Database Performance Issues',
                'description': f'{len(db_errors)} database errors suggest performance problems.',
                'action_items': [
                    'Review database query performance',
                    'Check connection pool settings',
                    'Monitor database server resources',
                    'Consider query optimization'
                ]
            })
        
        # Analyze unresolved errors
        unresolved = [e for e in errors if e.status == 'open']
        if len(unresolved) > 100:
            recommendations.append({
                'category': 'Operations',
                'priority': 'Medium',
                'title': 'High Unresolved Error Count',
                'description': f'{len(unresolved)} errors remain unresolved.',
                'action_items': [
                    'Assign errors to team members',
                    'Set up error triage process',
                    'Implement SLA for error resolution',
                    'Create error resolution workflows'
                ]
            })
        
        return recommendations
    
    def get_top_issues(self, start_date, limit=20):
        """Get top issues that need attention"""
        # Most frequent errors
        frequent_errors = db.session.query(
            ErrorLog.error_type,
            ErrorLog.error_message,
            ErrorLog.error_category,
            ErrorLog.severity,
            func.count(ErrorLog.id).label('count'),
            func.max(ErrorLog.created_at).label('last_occurrence')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            ErrorLog.error_type,
            ErrorLog.error_message,
            ErrorLog.error_category,
            ErrorLog.severity
        ).order_by(desc(func.count(ErrorLog.id))).limit(limit).all()
        
        issues = []
        for error_type, message, category, severity, count, last_occurrence in frequent_errors:
            # Calculate impact score
            severity_weights = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
            impact_score = count * severity_weights.get(severity, 1)
            
            issues.append({
                'error_type': error_type,
                'error_message': message[:100] + '...' if len(message) > 100 else message,
                'category': category,
                'severity': severity,
                'count': count,
                'last_occurrence': last_occurrence,
                'impact_score': impact_score
            })
        
        return sorted(issues, key=lambda x: x['impact_score'], reverse=True)
    
    def get_resolution_analysis(self, start_date):
        """Analyze error resolution patterns"""
        resolved_errors = ErrorLog.query.filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.status == 'resolved',
            ErrorLog.resolved_at.isnot(None)
        ).all()
        
        if not resolved_errors:
            return {'message': 'No resolved errors found'}
        
        # Calculate resolution times
        resolution_times = []
        for error in resolved_errors:
            resolution_time = (error.resolved_at - error.created_at).total_seconds() / 3600  # hours
            resolution_times.append(resolution_time)
        
        # Resolution statistics
        avg_resolution_time = np.mean(resolution_times)
        median_resolution_time = np.median(resolution_times)
        
        # Resolution by severity
        resolution_by_severity = {}
        for error in resolved_errors:
            if error.severity not in resolution_by_severity:
                resolution_by_severity[error.severity] = []
            resolution_time = (error.resolved_at - error.created_at).total_seconds() / 3600
            resolution_by_severity[error.severity].append(resolution_time)
        
        # Calculate averages by severity
        avg_by_severity = {}
        for severity, times in resolution_by_severity.items():
            avg_by_severity[severity] = round(np.mean(times), 2)
        
        return {
            'total_resolved': len(resolved_errors),
            'avg_resolution_time_hours': round(avg_resolution_time, 2),
            'median_resolution_time_hours': round(median_resolution_time, 2),
            'resolution_by_severity': avg_by_severity,
            'resolution_rate': self._calculate_resolution_rate(start_date)
        }
    
    def _calculate_resolution_rate(self, start_date):
        """Calculate the rate at which errors are being resolved"""
        total_errors = ErrorLog.query.filter(ErrorLog.created_at >= start_date).count()
        resolved_errors = ErrorLog.query.filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.status == 'resolved'
        ).count()
        
        return round((resolved_errors / total_errors * 100), 2) if total_errors > 0 else 0
    
    def _is_cache_valid(self, cache_key):
        """Check if cached data is still valid"""
        if cache_key not in self.analysis_cache:
            return False
        
        cache_time = self.analysis_cache[cache_key]['timestamp']
        return datetime.utcnow() - cache_time < self.cache_ttl
    
    def _cache_data(self, cache_key, data):
        """Cache analysis data"""
        self.analysis_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }


class TutorErrorAnalyzer:
    """Specialized analyzer for tutor-specific errors"""
    
    def analyze_tutor_login_issues(self, tutor_id=None, days=30):
        """Analyze login issues specifically for tutors"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = ErrorLog.query.filter(
            ErrorLog.created_at >= start_date,
            ErrorLog.error_category == 'authentication',
            ErrorLog.user_role == 'tutor'
        )
        
        if tutor_id:
            query = query.filter(ErrorLog.user_id == tutor_id)
        
        login_errors = query.all()
        
        analysis = {
            'total_login_errors': len(login_errors),
            'affected_tutors': len(set(e.user_id for e in login_errors if e.user_id)),
            'error_breakdown': {},
            'time_patterns': {},
            'recommendations': []
        }
        
        # Breakdown by error type
        error_types = Counter(e.error_type for e in login_errors)
        analysis['error_breakdown'] = dict(error_types.most_common())
        
        # Time patterns
        hours = Counter(e.created_at.hour for e in login_errors)
        analysis['time_patterns'] = dict(hours.most_common())
        
        # Generate recommendations
        if len(login_errors) > 20:
            analysis['recommendations'].append('High login error rate detected. Consider user training.')
        
        if len(set(e.ip_address for e in login_errors)) < len(login_errors) * 0.5:
            analysis['recommendations'].append('Multiple errors from same IPs. Check for network issues.')
        
        return analysis
    
    def get_tutor_error_profile(self, tutor_id, days=90):
        """Get comprehensive error profile for a specific tutor"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        errors = ErrorLog.query.filter(
            ErrorLog.user_id == tutor_id,
            ErrorLog.created_at >= start_date
        ).order_by(desc(ErrorLog.created_at)).all()
        
        if not errors:
            return {'message': 'No errors found for this tutor'}
        
        profile = {
            'total_errors': len(errors),
            'error_categories': dict(Counter(e.error_category for e in errors)),
            'severity_breakdown': dict(Counter(e.severity for e in errors)),
            'recent_errors': [e.to_dict() for e in errors[:10]],
            'error_frequency': self._calculate_error_frequency(errors),
            'problematic_areas': self._identify_problematic_areas(errors),
            'improvement_trend': self._analyze_improvement_trend(errors),
            'risk_assessment': self._assess_tutor_risk(errors)
        }
        
        return profile
    
    def _calculate_error_frequency(self, errors):
        """Calculate error frequency over time"""
        if not errors:
            return 0
        
        first_error = min(e.created_at for e in errors)
        last_error = max(e.created_at for e in errors)
        time_span = (last_error - first_error).days or 1
        
        return round(len(errors) / time_span, 2)
    
    def _identify_problematic_areas(self, errors):
        """Identify areas where tutor has most issues"""
        categories = Counter(e.error_category for e in errors)
        return dict(categories.most_common(5))
    
    def _analyze_improvement_trend(self, errors):
        """Analyze if tutor's error rate is improving or worsening"""
        if len(errors) < 10:
            return 'insufficient_data'
        
        # Split errors into two halves by time
        sorted_errors = sorted(errors, key=lambda x: x.created_at)
        mid_point = len(sorted_errors) // 2
        
        first_half = sorted_errors[:mid_point]
        second_half = sorted_errors[mid_point:]
        
        first_half_days = (max(e.created_at for e in first_half) - min(e.created_at for e in first_half)).days or 1
        second_half_days = (max(e.created_at for e in second_half) - min(e.created_at for e in second_half)).days or 1
        
        first_rate = len(first_half) / first_half_days
        second_rate = len(second_half) / second_half_days
        
        if second_rate < first_rate * 0.8:
            return 'improving'
        elif second_rate > first_rate * 1.2:
            return 'worsening'
        else:
            return 'stable'
    
    def _assess_tutor_risk(self, errors):
        """Assess the risk level of a tutor based on error patterns"""
        if not errors:
            return 'low'
        
        risk_score = 0
        
        # High number of errors
        if len(errors) > 50:
            risk_score += 3
        elif len(errors) > 20:
            risk_score += 2
        elif len(errors) > 10:
            risk_score += 1
        
        # Critical errors
        critical_errors = [e for e in errors if e.severity == 'critical']
        risk_score += len(critical_errors) * 2
        
        # Authentication errors (security concern)
        auth_errors = [e for e in errors if e.error_category == 'authentication']
        if len(auth_errors) > 10:
            risk_score += 2
        
        # Recent error spike
        recent_errors = [e for e in errors if e.created_at >= datetime.utcnow() - timedelta(days=7)]
        if len(recent_errors) > len(errors) * 0.3:  # More than 30% of errors in last week
            risk_score += 2
        
        # Determine risk level
        if risk_score >= 8:
            return 'high'
        elif risk_score >= 4:
            return 'medium'
        else:
            return 'low'


# Global analyzer instances
error_analyzer = ErrorAnalyzer()
tutor_analyzer = TutorErrorAnalyzer()