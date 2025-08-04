# app/utils/allocation_helper.py

from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy import and_, or_, func, text
from app import db
from app.models.student import Student
from app.models.tutor import Tutor
from app.models.class_model import Class
from app.models.user import User
from app.utils.tutor_matching import TutorMatchingEngine
import json

class AllocationHelper:
    """Smart allocation helper for managing student-tutor assignments"""
    
    def __init__(self):
        self.matching_engine = TutorMatchingEngine()
    
    def get_unallocated_students(self, filters: Dict = None) -> List[Dict]:
        """Get students who are not allocated to any classes"""
        
        # Get all student IDs who are in classes (both one-on-one and group)
        allocated_student_ids = set()
        
        # Get one-on-one allocated students
        one_on_one_classes = Class.query.filter(
            Class.primary_student_id.isnot(None),
            Class.status.in_(['scheduled', 'ongoing'])
        ).all()
        
        for cls in one_on_one_classes:
            if cls.primary_student_id:
                allocated_student_ids.add(cls.primary_student_id)
        
        # Get group class allocated students
        group_classes = Class.query.filter(
            Class.students.isnot(None),
            Class.status.in_(['scheduled', 'ongoing'])
        ).all()
        
        for cls in group_classes:
            try:
                student_ids = cls.get_students() or []
                allocated_student_ids.update(student_ids)
            except:
                continue
        
        # Build base query for unallocated students
        query = Student.query.filter(
            Student.is_active == True,
            Student.enrollment_status == 'active'
        )
        
        if allocated_student_ids:
            query = query.filter(~Student.id.in_(allocated_student_ids))
        
        # Apply filters
        if filters:
            if filters.get('grade'):
                query = query.filter(Student.grade == filters['grade'])
            if filters.get('board'):
                query = query.filter(Student.board.ilike(f"%{filters['board']}%"))
            if filters.get('subject'):
                # Filter by enrolled subjects
                subject_filter = filters['subject'].lower()
                query = query.filter(
                    Student.subjects_enrolled.ilike(f"%{subject_filter}%")
                )
            if filters.get('department_id'):
                query = query.filter(Student.department_id == filters['department_id'])
            if filters.get('days_unallocated'):
                days_ago = date.today() - timedelta(days=int(filters['days_unallocated']))
                query = query.filter(Student.created_at <= days_ago)
        
        students = query.order_by(Student.created_at.asc()).all()
        
        # Build result with additional context
        unallocated_students = []
        for student in students:
            student_data = {
                'id': student.id,
                'full_name': student.full_name,
                'grade': student.grade,
                'board': student.board,
                'subjects_enrolled': student.get_subjects_enrolled(),
                'difficult_subjects': student.get_difficult_subjects(),
                'days_since_enrollment': (date.today() - student.created_at.date()).days if student.created_at else 0,
                'priority': self._calculate_student_priority(student),
                'department_id': student.department_id,
                'parent_phone': getattr(student, 'parent_phone', ''),
                'status': student.enrollment_status
            }
            unallocated_students.append(student_data)
        
        return unallocated_students
    
    def get_available_tutors(self, filters: Dict = None) -> List[Dict]:
        """Get tutors who have availability and capacity for more students"""
        
        # Get active tutors with availability
        tutors = Tutor.query.filter_by(status='active').all()
        available_tutors = []
        
        for tutor in tutors:
            # Must have availability schedule
            availability = tutor.get_availability()
            if not availability:
                continue
            
            # Get current class load
            current_classes = Class.query.filter(
                Class.tutor_id == tutor.id,
                Class.status.in_(['scheduled', 'ongoing'])
            ).count()
            
            # Calculate capacity (assuming max 8 students per tutor)
            max_capacity = 8
            available_slots = max_capacity - current_classes
            
            if available_slots <= 0:
                continue
            
            # Apply filters
            if filters:
                if filters.get('subject'):
                    if not tutor.can_teach_subject(filters['subject']):
                        continue
                if filters.get('grade'):
                    if not tutor.can_teach_grade(filters['grade']):
                        continue
                if filters.get('board'):
                    if not tutor.can_teach_board(filters['board']):
                        continue
                if filters.get('min_rating'):
                    if (tutor.rating or 0) < float(filters['min_rating']):
                        continue
                if filters.get('min_test_score'):
                    if (tutor.test_score or 0) < float(filters['min_test_score']):
                        continue
            
            tutor_data = {
                'id': tutor.id,
                'full_name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'rating': tutor.rating or 0,
                'test_score': tutor.test_score or 0,
                'current_students': current_classes,
                'available_slots': available_slots,
                'qualification': tutor.qualification,
                'availability_summary': self._get_availability_summary(tutor),
                'department_id': tutor.user.department_id if tutor.user else None
            }
            available_tutors.append(tutor_data)
        
        # Sort by rating and availability
        available_tutors.sort(key=lambda x: (-x['rating'], -x['available_slots']))
        
        return available_tutors
    
    def get_smart_matches(self, student_id: int, limit: int = 3) -> List[Dict]:
        """Get smart tutor matches for a specific student"""
        return self.matching_engine.find_best_matches(
            student_id=student_id, 
            limit=limit
        )
    
    def get_allocation_analytics(self) -> Dict:
        """Get comprehensive allocation analytics"""
        
        # Get total counts
        total_students = Student.query.filter_by(is_active=True, enrollment_status='active').count()
        total_tutors = Tutor.query.filter_by(status='active').count()
        
        # Get allocated student count
        allocated_student_ids = set()
        
        # One-on-one allocations
        one_on_one = Class.query.filter(
            Class.primary_student_id.isnot(None),
            Class.status.in_(['scheduled', 'ongoing'])
        ).with_entities(Class.primary_student_id).distinct().all()
        
        allocated_student_ids.update([x[0] for x in one_on_one if x[0]])
        
        # Group allocations
        group_classes = Class.query.filter(
            Class.students.isnot(None),
            Class.status.in_(['scheduled', 'ongoing'])
        ).all()
        
        for cls in group_classes:
            try:
                student_ids = cls.get_students() or []
                allocated_student_ids.update(student_ids)
            except:
                continue
        
        allocated_count = len(allocated_student_ids)
        unallocated_count = total_students - allocated_count
        
        # Get subject-wise breakdown
        subject_breakdown = self._get_subject_breakdown()
        
        # Get tutor utilization
        tutor_utilization = self._get_tutor_utilization()
        
        # Get urgent cases (students waiting > 5 days)
        urgent_threshold = date.today() - timedelta(days=5)
        urgent_students = Student.query.filter(
            Student.is_active == True,
            Student.enrollment_status == 'active',
            Student.created_at <= urgent_threshold
        ).count()
        
        urgent_unallocated = max(0, urgent_students - allocated_count)
        
        return {
            'overview': {
                'total_students': total_students,
                'allocated_students': allocated_count,
                'unallocated_students': unallocated_count,
                'allocation_percentage': round((allocated_count / total_students * 100) if total_students > 0 else 0, 1),
                'total_tutors': total_tutors,
                'urgent_cases': urgent_unallocated
            },
            'subject_breakdown': subject_breakdown,
            'tutor_utilization': tutor_utilization,
            'priority_metrics': {
                'high_priority': urgent_unallocated,
                'medium_priority': max(0, unallocated_count - urgent_unallocated),
                'needs_attention': self._get_attention_cases()
            }
        }
    
    def bulk_auto_assign(self, filters: Dict = None, dry_run: bool = True) -> Dict:
        """Bulk auto-assign students to best matching tutors"""
        
        unallocated_students = self.get_unallocated_students(filters)
        available_tutors = self.get_available_tutors()
        
        assignments = []
        conflicts = []
        
        for student_data in unallocated_students:
            student_id = student_data['id']
            
            # Get best matches
            matches = self.get_smart_matches(student_id, limit=3)
            
            if not matches:
                conflicts.append({
                    'student_id': student_id,
                    'student_name': student_data['full_name'],
                    'reason': 'No compatible tutors found'
                })
                continue
            
            # Find best available tutor
            best_match = None
            for match in matches:
                tutor_id = match['tutor_id']
                
                # Check if tutor has capacity
                tutor_data = next((t for t in available_tutors if t['id'] == tutor_id), None)
                if tutor_data and tutor_data['available_slots'] > 0:
                    best_match = {
                        'student_id': student_id,
                        'student_name': student_data['full_name'],
                        'tutor_id': tutor_id,
                        'tutor_name': match['tutor_name'],
                        'match_score': match['score_data']['total_score'],
                        'subjects': student_data['subjects_enrolled']
                    }
                    # Reduce available slots for next iteration
                    tutor_data['available_slots'] -= 1
                    break
            
            if best_match:
                assignments.append(best_match)
            else:
                conflicts.append({
                    'student_id': student_id,
                    'student_name': student_data['full_name'],
                    'reason': 'All compatible tutors at capacity'
                })
        
        result = {
            'success': True,
            'dry_run': dry_run,
            'assignments': assignments,
            'conflicts': conflicts,
            'summary': {
                'students_processed': len(unallocated_students),
                'successful_assignments': len(assignments),
                'conflicts': len(conflicts),
                'success_rate': round(len(assignments) / len(unallocated_students) * 100 if unallocated_students else 0, 1)
            }
        }
        
        if not dry_run:
            # Execute actual assignments
            result['execution_results'] = self._execute_assignments(assignments)
        
        return result
    
    def _calculate_student_priority(self, student: Student) -> str:
        """Calculate priority level for student allocation"""
        days_waiting = (date.today() - student.created_at.date()).days if student.created_at else 0
        
        if days_waiting > 7:
            return 'urgent'
        elif days_waiting > 3:
            return 'high'
        else:
            return 'normal'
    
    def _get_availability_summary(self, tutor: Tutor) -> Dict:
        """Get tutor availability summary"""
        availability = tutor.get_availability()
        if not availability:
            return {'status': 'no_schedule', 'summary': 'No schedule set'}
        
        available_days = [day.title() for day, slots in availability.items() if slots]
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
            'hours_per_week': round(total_hours, 1),
            'available_days': available_days[:3],  # Show first 3 days
            'summary': f"{len(available_days)} days/week ({total_hours:.1f}h total)"
        }
    
    def _get_subject_breakdown(self) -> List[Dict]:
        """Get subject-wise allocation breakdown"""
        # This is a simplified version - you may want to enhance based on your needs
        subjects = {}
        
        # Get all enrolled subjects
        students = Student.query.filter_by(is_active=True, enrollment_status='active').all()
        for student in students:
            student_subjects = student.get_subjects_enrolled()
            for subject in student_subjects:
                if subject not in subjects:
                    subjects[subject] = {'total': 0, 'allocated': 0, 'unallocated': 0}
                subjects[subject]['total'] += 1
        
        # Count allocations by subject (simplified)
        allocated_students = set()
        classes = Class.query.filter(Class.status.in_(['scheduled', 'ongoing'])).all()
        
        for cls in classes:
            try:
                student_ids = []
                if cls.primary_student_id:
                    student_ids = [cls.primary_student_id]
                else:
                    student_ids = cls.get_students() or []
                
                for student_id in student_ids:
                    allocated_students.add(student_id)
                    
                    # Get student and check subjects
                    student = Student.query.get(student_id)
                    if student:
                        student_subjects = student.get_subjects_enrolled()
                        for subject in student_subjects:
                            if subject in subjects:
                                subjects[subject]['allocated'] += 1
            except:
                continue
        
        # Calculate unallocated
        for subject in subjects:
            subjects[subject]['unallocated'] = subjects[subject]['total'] - subjects[subject]['allocated']
        
        return [{'subject': k, **v} for k, v in subjects.items()]
    
    def _get_tutor_utilization(self) -> List[Dict]:
        """Get tutor utilization rates"""
        utilization = []
        tutors = Tutor.query.filter_by(status='active').all()
        
        for tutor in tutors:
            current_classes = Class.query.filter(
                Class.tutor_id == tutor.id,
                Class.status.in_(['scheduled', 'ongoing'])
            ).count()
            
            max_capacity = 8  # Assuming max 8 students per tutor
            utilization_rate = (current_classes / max_capacity * 100) if max_capacity > 0 else 0
            
            utilization.append({
                'tutor_id': tutor.id,
                'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
                'current_students': current_classes,
                'max_capacity': max_capacity,
                'utilization_rate': round(utilization_rate, 1),
                'available_slots': max(0, max_capacity - current_classes)
            })
        
        return sorted(utilization, key=lambda x: x['utilization_rate'], reverse=True)
    
    def _get_attention_cases(self) -> int:
        """Get cases that need special attention"""
        # Students with difficult subjects but no allocation
        difficult_subject_students = Student.query.filter(
            Student.is_active == True,
            Student.enrollment_status == 'active',
            Student.difficult_subjects.isnot(None)
        ).count()
        
        return difficult_subject_students
    
    def _execute_assignments(self, assignments: List[Dict]) -> List[Dict]:
        """Execute the actual student-tutor assignments"""
        results = []
        
        for assignment in assignments:
            try:
                # Create a one-on-one class for the assignment
                # You can customize this based on your class creation logic
                new_class = Class(
                    subject=assignment['subjects'][0] if assignment['subjects'] else 'General',
                    class_type='one_on_one',
                    tutor_id=assignment['tutor_id'],
                    primary_student_id=assignment['student_id'],
                    status='scheduled',
                    # You'll need to set scheduled_date and scheduled_time based on availability
                    # This is a simplified version
                    created_by=1  # You may want to pass current_user.id
                )
                
                db.session.add(new_class)
                db.session.commit()
                
                results.append({
                    'student_id': assignment['student_id'],
                    'success': True,
                    'class_id': new_class.id,
                    'message': 'Assignment created successfully'
                })
                
            except Exception as e:
                db.session.rollback()
                results.append({
                    'student_id': assignment['student_id'],
                    'success': False,
                    'error': str(e),
                    'message': 'Failed to create assignment'
                })
        
        return results


# Create global instance
allocation_helper = AllocationHelper()