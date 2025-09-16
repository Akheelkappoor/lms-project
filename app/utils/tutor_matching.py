
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
import json
import re
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class

class TutorMatchingEngine:
    """Advanced tutor matching engine with ML-like capabilities"""
    
    def __init__(self):
        self.weights = {
            'grade_match': 25,
            'board_match': 20, 
            'subject_match': 25,
            'test_score': 15,
            'rating': 10,
            'completion_rate': 5
        }
    
    def find_best_matches(self, student_id: int, subject: str = None, 
                         filters: Dict = None, limit: int = 10) -> List[Dict]:
        """Find best tutor matches using advanced algorithm"""
        student = Student.query.get(student_id)
        if not student:
            return []
        
        # Get all available tutors
        available_tutors = self._get_available_tutors(filters)
        
        # Score each tutor
        scored_tutors = []
        for tutor in available_tutors:
            score_data = self._calculate_match_score(tutor, student, subject)
            if score_data['total_score'] > 0:
                scored_tutors.append({
                    'tutor_id': tutor.id,
                    'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
                    'score_data': score_data,
                    'tutor_info': self._get_tutor_summary(tutor)
                })
        
        # Sort by total score
        scored_tutors.sort(key=lambda x: x['score_data']['total_score'], reverse=True)
        
        return scored_tutors[:limit]
    
    def _get_available_tutors(self, filters: Dict = None) -> List[Tutor]:
        """Get tutors that meet basic availability requirements"""
        query = Tutor.query.filter_by(status='active')
        
        if filters:
            if filters.get('min_test_score'):
                query = query.filter(Tutor.test_score >= filters['min_test_score'])
            if filters.get('min_rating'):
                query = query.filter(Tutor.rating >= filters['min_rating'])
            if filters.get('experience_level'):
                query = self._apply_experience_filter(query, filters['experience_level'])
        
        tutors = query.all()
        # Filter for those with availability
        return [t for t in tutors if t.get_availability()]
    
    def _apply_experience_filter(self, query, experience_level: str):
        """Apply experience level filter to query"""
        if experience_level == 'master':
            return query.filter(Tutor.qualification.ilike('%master%'))
        elif experience_level == 'phd':
            return query.filter(
                Tutor.qualification.ilike('%phd%') | 
                Tutor.qualification.ilike('%doctorate%')
            )
        elif experience_level == 'expert':
            return query.filter(
                Tutor.qualification.ilike('%expert%') |
                Tutor.qualification.ilike('%specialist%') |
                Tutor.qualification.ilike('%senior%')
            )
        return query
    
    def _calculate_match_score(self, tutor: Tutor, student: Student, 
                              subject: str = None) -> Dict:
        """Calculate detailed match score with breakdown"""
        score_breakdown = {
            'grade_match': 0,
            'board_match': 0,
            'subject_match': 0,
            'test_score_bonus': 0,
            'rating_bonus': 0,
            'completion_bonus': 0,
            'total_score': 0,
            'match_reasons': [],
            'compatibility_level': 'none'
        }
        
        # Grade matching (mandatory)
        tutor_grades = [str(g) for g in tutor.get_grades()]
        if not tutor_grades or str(student.grade) not in tutor_grades:
            return score_breakdown  # Return zero score for incompatible grades
        
        score_breakdown['grade_match'] = self.weights['grade_match']
        score_breakdown['match_reasons'].append(f"Teaches Grade {student.grade}")
        
        # Board matching (mandatory)
        tutor_boards = [b.lower() for b in tutor.get_boards()]
        if not tutor_boards or student.board.lower() not in tutor_boards:
            return score_breakdown  # Return zero score for incompatible boards
        
        score_breakdown['board_match'] = self.weights['board_match']
        score_breakdown['match_reasons'].append(f"Expert in {student.board}")
        
        # Subject matching
        subject_score, subject_reasons = self._calculate_subject_match(
            tutor, student, subject
        )
        score_breakdown['subject_match'] = subject_score
        score_breakdown['match_reasons'].extend(subject_reasons)
        
        # Performance bonuses
        test_bonus, test_reason = self._calculate_test_score_bonus(tutor)
        score_breakdown['test_score_bonus'] = test_bonus
        if test_reason:
            score_breakdown['match_reasons'].append(test_reason)
        
        rating_bonus, rating_reason = self._calculate_rating_bonus(tutor)
        score_breakdown['rating_bonus'] = rating_bonus
        if rating_reason:
            score_breakdown['match_reasons'].append(rating_reason)
        
        completion_bonus, completion_reason = self._calculate_completion_bonus(tutor)
        score_breakdown['completion_bonus'] = completion_bonus
        if completion_reason:
            score_breakdown['match_reasons'].append(completion_reason)
        
        # Calculate total score
        total = sum([
            score_breakdown['grade_match'],
            score_breakdown['board_match'], 
            score_breakdown['subject_match'],
            score_breakdown['test_score_bonus'],
            score_breakdown['rating_bonus'],
            score_breakdown['completion_bonus']
        ])
        
        score_breakdown['total_score'] = min(total, 100)
        score_breakdown['compatibility_level'] = self._get_compatibility_level(total)
        
        return score_breakdown
    
    def _calculate_subject_match(self, tutor: Tutor, student: Student, 
                                subject: str = None) -> Tuple[int, List[str]]:
        """Calculate subject matching score"""
        reasons = []
        
        tutor_subjects = [s.lower() for s in tutor.get_subjects()]
        student_subjects = [s.lower() for s in student.get_subjects_enrolled()]
        
        # If specific subject provided, prioritize it
        if subject:
            subject_lower = subject.lower()
            if any(subject_lower in ts or ts in subject_lower for ts in tutor_subjects):
                reasons.append(f"Specializes in {subject}")
                return self.weights['subject_match'], reasons
        
        # Check overlap between tutor and student subjects
        if student_subjects and tutor_subjects:
            exact_matches = set(student_subjects) & set(tutor_subjects)
            if exact_matches:
                matched = list(exact_matches)[:2]  # Show first 2 matches
                reasons.append(f"Expert in: {', '.join(matched)}")
                return self.weights['subject_match'], reasons
            
            # Check partial matches
            partial_matches = []
            for ss in student_subjects:
                for ts in tutor_subjects:
                    if ss in ts or ts in ss:
                        partial_matches.append(ss)
                        break
            
            if partial_matches:
                reasons.append(f"Related expertise: {', '.join(partial_matches[:2])}")
                return int(self.weights['subject_match'] * 0.7), reasons
        
        return 0, reasons
    
    def _calculate_test_score_bonus(self, tutor: Tutor) -> Tuple[int, str]:
        """Calculate test score bonus"""
        if not tutor.test_score:
            return 0, ""
        
        if tutor.test_score >= 90:
            return self.weights['test_score'], "Excellent test performance (A+)"
        elif tutor.test_score >= 85:
            return int(self.weights['test_score'] * 0.8), "Strong test performance (A)"
        elif tutor.test_score >= 80:
            return int(self.weights['test_score'] * 0.6), "Good test performance (B+)"
        elif tutor.test_score >= 70:
            return int(self.weights['test_score'] * 0.4), "Solid test performance (B)"
        
        return 0, ""
    
    def _calculate_rating_bonus(self, tutor: Tutor) -> Tuple[int, str]:
        """Calculate rating bonus"""
        if not tutor.rating:
            return 0, ""
        
        if tutor.rating >= 4.5:
            return self.weights['rating'], "Highly rated (4.5+★)"
        elif tutor.rating >= 4.0:
            return int(self.weights['rating'] * 0.7), "Well rated (4.0+★)"
        elif tutor.rating >= 3.5:
            return int(self.weights['rating'] * 0.5), "Good rating (3.5+★)"
        
        return 0, ""
    
    def _calculate_completion_bonus(self, tutor: Tutor) -> Tuple[int, str]:
        """Calculate completion rate bonus"""
        if tutor.total_classes < 5:  # Need meaningful data
            return 0, ""
        
        completion_rate = tutor.get_completion_rate()
        if completion_rate >= 95:
            return self.weights['completion_rate'], "Excellent completion rate (95%+)"
        elif completion_rate >= 90:
            return int(self.weights['completion_rate'] * 0.8), "High completion rate (90%+)"
        elif completion_rate >= 85:
            return int(self.weights['completion_rate'] * 0.6), "Good completion rate (85%+)"
        
        return 0, ""
    
    def _get_compatibility_level(self, score: int) -> str:
        """Get compatibility level based on score"""
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "very_good"
        elif score >= 55:
            return "good"
        elif score >= 40:
            return "fair"
        else:
            return "basic"
    
    def _get_tutor_summary(self, tutor: Tutor) -> Dict:
        """Get summary information about tutor"""
        return {
            'id': tutor.id,
            'name': tutor.user.full_name if tutor.user else 'Unknown',
            'email': tutor.user.email if tutor.user else '',
            'test_score': tutor.test_score or 0,
            'test_grade': tutor.get_test_score_grade(),
            'rating': tutor.rating or 0,
            'total_classes': tutor.total_classes or 0,
            'completion_rate': tutor.get_completion_rate(),
            'subjects': tutor.get_subjects(),
            'grades': tutor.get_grades(),
            'boards': tutor.get_boards(),
            'qualification': tutor.qualification or '',
            'availability_summary': self._get_availability_summary(tutor)
        }
    
    def _get_availability_summary(self, tutor: Tutor) -> Dict:
        """Get availability summary"""
        availability = tutor.get_availability()
        if not availability:
            return {'status': 'no_schedule', 'days': 0, 'hours': 0}
        
        available_days = [day for day, slots in availability.items() if slots]
        total_hours = 0
        
        for day, slots in availability.items():
            for slot in slots or []:
                try:
                    start = datetime.strptime(slot['start'], '%H:%M').time()
                    end = datetime.strptime(slot['end'], '%H:%M').time()
                    start_dt = datetime.combine(date.today(), start)
                    end_dt = datetime.combine(date.today(), end)
                    hours = (end_dt - start_dt).total_seconds() / 3600
                    total_hours += hours
                except:
                    continue
        
        return {
            'status': 'available',
            'days': len(available_days),
            'hours': round(total_hours, 1),
            'available_days': available_days
        }

class SearchQueryProcessor:
    """Process and normalize search queries"""
    
    @staticmethod
    def process_subject_query(query: str) -> List[str]:
        """Process subject search query and return variations"""
        if not query:
            return []
        
        query = query.lower().strip()
        variations = [query]
        
        # Common subject aliases
        subject_aliases = {
            'math': ['mathematics', 'maths', 'arithmetic'],
            'physics': ['phy', 'physical science'],
            'chemistry': ['chem', 'chemical science'],
            'biology': ['bio', 'life science'],
            'english': ['eng', 'language', 'literature'],
            'computer science': ['cs', 'computing', 'programming'],
            'social studies': ['social science', 'history', 'geography']
        }
        
        # Add aliases if query matches
        for main_subject, aliases in subject_aliases.items():
            if query in [main_subject] + aliases:
                variations.extend([main_subject] + aliases)
        
        return list(set(variations))
    
    @staticmethod
    def normalize_grade(grade_input: str) -> str:
        """Normalize grade input"""
        if not grade_input:
            return ""
        
        # Extract numeric part
        numeric = re.findall(r'\d+', str(grade_input))
        if numeric:
            return numeric[0]
        
        # Handle text grades
        grade_map = {
            'kindergarten': 'K',
            'first': '1',
            'second': '2', 
            'third': '3',
            'fourth': '4',
            'fifth': '5',
            'sixth': '6',
            'seventh': '7',
            'eighth': '8',
            'ninth': '9',
            'tenth': '10',
            'eleventh': '11',
            'twelfth': '12'
        }
        
        grade_lower = grade_input.lower()
        return grade_map.get(grade_lower, grade_input)

class AvailabilityChecker:
    """Check tutor availability and conflicts"""
    
    @staticmethod
    def check_tutor_availability(tutor_id: int, date_obj: date, 
                               time_obj: datetime.time, duration: int = 60) -> Dict:
        """Check if tutor is available at specific time"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor:
            return {'available': False, 'reason': 'Tutor not found'}
        
        # Check if tutor has availability schedule
        availability = tutor.get_availability()
        if not availability:
            return {'available': False, 'reason': 'No availability schedule set'}
        
        # Check day of week availability
        day_name = date_obj.strftime('%A').lower()
        day_schedule = availability.get(day_name, [])
        
        if not day_schedule:
            return {'available': False, 'reason': f'Not available on {day_name.title()}'}
        
        # Check time slot availability
        time_str = time_obj.strftime('%H:%M')
        end_time = (datetime.combine(date_obj, time_obj) + 
                   timedelta(minutes=duration)).time()
        end_time_str = end_time.strftime('%H:%M')
        
        available_in_slot = False
        for slot in day_schedule:
            if slot['start'] <= time_str and slot['end'] >= end_time_str:
                available_in_slot = True
                break
        
        if not available_in_slot:
            return {
                'available': False, 
                'reason': f'Not available at {time_str} on {day_name.title()}'
            }
        
        # Check for existing class conflicts
        conflict = AvailabilityChecker.check_scheduling_conflicts(
            tutor_id, date_obj, time_obj, duration
        )
        
        if conflict['has_conflict']:
            return {
                'available': False,
                'reason': f'Already has a {conflict["conflict_type"]} at this time'
            }
        
        return {'available': True, 'reason': 'Available'}
    
    @staticmethod
    def check_scheduling_conflicts(tutor_id: int, date_obj: date, 
                                 time_obj: datetime.time, duration: int) -> Dict:
        """Check for scheduling conflicts with existing classes"""
        end_time = (datetime.combine(date_obj, time_obj) + 
                   timedelta(minutes=duration)).time()
        
        existing_classes = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.scheduled_date == date_obj,
            Class.status.in_(['scheduled', 'ongoing'])
        ).all()
        
        for existing_class in existing_classes:
            existing_start = existing_class.scheduled_time
            existing_end = (datetime.combine(date_obj, existing_start) + 
                          timedelta(minutes=existing_class.duration)).time()
            
            # Check for time overlap
            if (time_obj < existing_end and end_time > existing_start):
                return {
                    'has_conflict': True,
                    'conflict_type': existing_class.class_type or 'class',
                    'conflict_class_id': existing_class.id,
                    'conflict_time': existing_start.strftime('%H:%M')
                }
        
        return {'has_conflict': False}
    
    @staticmethod
    def get_available_slots(tutor_id: int, date_obj: date, 
                          duration: int = 60) -> List[Dict]:
        """Get all available time slots for a tutor on a specific date"""
        tutor = Tutor.query.get(tutor_id)
        if not tutor:
            return []
        
        availability = tutor.get_availability()
        if not availability:
            return []
        
        day_name = date_obj.strftime('%A').lower()
        day_schedule = availability.get(day_name, [])
        
        if not day_schedule:
            return []
        
        available_slots = []
        
        for slot in day_schedule:
            slot_start = datetime.strptime(slot['start'], '%H:%M').time()
            slot_end = datetime.strptime(slot['end'], '%H:%M').time()
            
            # Generate 30-minute intervals within the slot
            current_time = datetime.combine(date_obj, slot_start)
            slot_end_dt = datetime.combine(date_obj, slot_end)
            
            while current_time + timedelta(minutes=duration) <= slot_end_dt:
                check_result = AvailabilityChecker.check_tutor_availability(
                    tutor_id, date_obj, current_time.time(), duration
                )
                
                if check_result['available']:
                    available_slots.append({
                        'start_time': current_time.time().strftime('%H:%M'),
                        'end_time': (current_time + timedelta(minutes=duration)).time().strftime('%H:%M'),
                        'duration': duration
                    })
                
                current_time += timedelta(minutes=30)  # 30-minute intervals
        
        return available_slots

# Performance monitoring decorator
def monitor_search_performance(func):
    """Decorator to monitor search performance"""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log performance metrics
            from flask import current_app
            current_app.logger.info(
                f"Search function {func.__name__} completed in {duration:.3f}s"
            )
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            from flask import current_app
            current_app.logger.error(
                f"Search function {func.__name__} failed after {duration:.3f}s: {str(e)}"
            )
            raise
    
    return wrapper