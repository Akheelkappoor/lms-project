from datetime import datetime, date
from app import db
import json
import re 


class Tutor(db.Model):
    __tablename__ = "tutors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )

    date_of_birth = db.Column(db.Date)
    state = db.Column(db.String(50))
    pin_code = db.Column(db.String(10))

    # Professional Information
    qualification = db.Column(db.String(200), nullable=False)
    experience = db.Column(db.Text)  # Years and background
    subjects = db.Column(db.Text)  # JSON array of subjects
    grades = db.Column(db.Text)  # JSON array of grade levels
    boards = db.Column(db.Text)  # JSON array of education boards

    # Test Score Information - NEW FIELDS ADDED
    test_score = db.Column(db.Float)  # Total test score (out of 100)
    test_date = db.Column(db.Date)  # Date when test was taken
    test_notes = db.Column(db.Text)  # Additional notes about the test performance

    # Availability
    availability = db.Column(db.Text)  # JSON object for weekly schedule

    # Compensation
    salary_type = db.Column(db.String(20), nullable=False)  # 'monthly' or 'hourly'
    monthly_salary = db.Column(db.Float)
    hourly_rate = db.Column(db.Float)

    # Documents and Media
    documents = db.Column(db.Text)  # JSON object with document file paths
    demo_video = db.Column(db.String(2000))
    interview_video = db.Column(db.String(2000))

    # Banking Information
    bank_details = db.Column(db.Text)  # JSON object with banking info

    # Status and Performance
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, active, inactive, suspended
    verification_status = db.Column(
        db.String(20), default="pending"
    )  # pending, verified, rejected
    rating = db.Column(db.Float, default=0.0)
    total_classes = db.Column(db.Integer, default=0)
    completed_classes = db.Column(db.Integer, default=0)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_class = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        super(Tutor, self).__init__(**kwargs)

    def get_subjects(self):
        """Get subjects as list"""
        if self.subjects:
            try:
                return json.loads(self.subjects)
            except:
                return []
        return []

    def set_subjects(self, subjects_list):
        """Set subjects from list"""
        self.subjects = json.dumps(subjects_list)

    def get_grades(self):
        """Get grades as list"""
        if self.grades:
            try:
                return json.loads(self.grades)
            except:
                return []
        return []

    def set_grades(self, grades_list):
        """Set grades from list"""
        self.grades = json.dumps(grades_list)

    def get_boards(self):
        """Get boards as list"""
        if self.boards:
            try:
                return json.loads(self.boards)
            except:
                return []
        return []

    def set_boards(self, boards_list):
        """Set boards from list"""
        self.boards = json.dumps(boards_list)

    def get_availability(self):
        """Get availability as dict"""
        if self.availability:
            try:
                return json.loads(self.availability)
            except:
                return {}
        return {}

    def set_availability(self, availability_dict):
        """Set availability from dict
        Format: {
            'monday': [{'start': '09:00', 'end': '12:00'}, {'start': '14:00', 'end': '17:00'}],
            'tuesday': [...],
            ...
        }
        """
        self.availability = json.dumps(availability_dict)

    def get_documents(self):
        """Get documents as dict"""
        if self.documents:
            try:
                return json.loads(self.documents)
            except:
                return {}
        return {}

    def set_documents(self, documents_dict):
        """Set documents from dict"""
        self.documents = json.dumps(documents_dict)

    def get_bank_details(self):
        """Get bank details as dict"""
        if self.bank_details:
            try:
                return json.loads(self.bank_details)
            except:
                return {}
        return {}

    def set_bank_details(self, bank_dict):
        """Set bank details from dict"""
        self.bank_details = json.dumps(bank_dict)

    # NEW TEST SCORE METHODS ADDED
    def get_test_score_grade(self):
        """Get test score as letter grade"""
        if not self.test_score:
            return "Not Tested"

        score = self.test_score
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "C+"
        elif score >= 65:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def is_test_score_excellent(self):
        """Check if test score is excellent (85+)"""
        return self.test_score and self.test_score >= 85

    def is_test_score_good(self):
        """Check if test score is good (75+)"""
        return self.test_score and self.test_score >= 75

    def calculate_overall_score(self):
        """Calculate overall tutor score combining test score and performance"""
        base_score = self.test_score or 0

        # Add performance bonuses
        if self.total_classes > 0:
            completion_rate = (self.completed_classes / self.total_classes) * 100
            if completion_rate >= 95:
                base_score += 5
            elif completion_rate >= 90:
                base_score += 3
            elif completion_rate >= 85:
                base_score += 1

        # Add rating bonus
        if self.rating:
            if self.rating >= 4.5:
                base_score += 3
            elif self.rating >= 4.0:
                base_score += 2
            elif self.rating >= 3.5:
                base_score += 1

        return min(base_score, 100)  # Cap at 100

    def is_available_at(self, day_of_week, time_str):
        """Check if tutor is available at specific day and time
        Args:
            day_of_week: 'monday', 'tuesday', etc.
            time_str: '14:30' format
        """
        availability = self.get_availability()
        if day_of_week.lower() not in availability:
            return False

        day_slots = availability[day_of_week.lower()]
        for slot in day_slots:
            if slot["start"] <= time_str <= slot["end"]:
                return True
        return False

    def get_monthly_earnings(self, month=None, year=None):
        """Calculate monthly earnings based on classes taught"""
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year

        # This would need to be implemented with actual attendance/class data
        # For now, return based on salary type
        if self.salary_type == "monthly":
            return self.monthly_salary or 0
        else:
            # Calculate based on hours taught (would need attendance records)
            return 0

    def get_completion_rate(self):
        """Get class completion rate as percentage"""
        if self.total_classes == 0:
            return 0
        return (self.completed_classes / self.total_classes) * 100

    def get_status_display(self):
        """Get formatted status"""
        status_map = {
            "pending": "Pending Review",
            "active": "Active",
            "inactive": "Inactive",
            "suspended": "Suspended",
        }
        return status_map.get(self.status, self.status.title())

    def can_teach_subject(self, subject):
        """Check if tutor can teach specific subject"""
        return subject.lower() in [s.lower() for s in self.get_subjects()]

    def can_teach_grade(self, grade):
        """Check if tutor can teach specific grade"""
        return str(grade) in [str(g) for g in self.get_grades()]

    def can_teach_board(self, board):
        """Check if tutor is familiar with specific board"""
        return board.lower() in [b.lower() for b in self.get_boards()]

    @staticmethod
    def get_available_tutors(subject=None, grade=None, board=None, day=None, time=None):
        """Get available tutors based on criteria"""
        query = Tutor.query.filter_by(status="active")

        available_tutors = []
        for tutor in query:
            # Check subject compatibility
            if subject and not tutor.can_teach_subject(subject):
                continue

            # Check grade compatibility
            if grade and not tutor.can_teach_grade(grade):
                continue

            # Check board compatibility
            if board and not tutor.can_teach_board(board):
                continue

            # Check availability
            if day and time and not tutor.is_available_at(day, time):
                continue

            available_tutors.append(tutor)

        return available_tutors

    def to_dict(self):
        """Convert tutor to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.full_name if self.user else "",
            "qualification": self.qualification,
            "experience": self.experience,
            "subjects": self.get_subjects(),
            "grades": self.get_grades(),
            "boards": self.get_boards(),
            "salary_type": self.salary_type,
            "monthly_salary": self.monthly_salary,
            "hourly_rate": self.hourly_rate,
            "test_score": self.test_score,  # NEW FIELD ADDED
            "test_grade": self.get_test_score_grade(),  # NEW FIELD ADDED
            "test_date": (
                self.test_date.isoformat() if self.test_date else None
            ),  # NEW FIELD ADDED
            "status": self.status,
            "verification_status": self.verification_status,
            "rating": self.rating,
            "total_classes": self.total_classes,
            "completed_classes": self.completed_classes,
            "completion_rate": self.get_completion_rate(),
            "overall_score": self.calculate_overall_score(),  # NEW FIELD ADDED
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Tutor {self.user.full_name if self.user else self.id}>"

    def calculate_monthly_salary(self, month=None, year=None):
        """Calculate monthly salary based on attendance and performance"""
        from datetime import datetime, date
        from app.models.attendance import Attendance

        # Set default month/year if not provided
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year

        # Initialize salary calculation components
        base_salary = self.monthly_salary or 0
        attendance_records = self._get_monthly_attendance_records(month, year)
        attended_classes = [
            att for att in attendance_records if att.status == "present"
        ]

        # Calculate salary based on type
        if self.salary_type == "hourly":
            calculated_salary = self._calculate_hourly_salary(attended_classes)
        else:
            calculated_salary = self._calculate_fixed_monthly_salary(
                base_salary, attendance_records, attended_classes
            )

        return {
            "base_salary": base_salary,
            "calculated_salary": calculated_salary,
            "total_classes": len(attendance_records),
            "attended_classes": len(attended_classes),
            "month": month,
            "year": year,
        }

    def _get_monthly_attendance_records(self, month, year):
        """Helper method to get attendance records for a specific month"""
        from datetime import date
        from app.models.attendance import Attendance

        start_date = date(year, month, 1)
        end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

        return Attendance.query.filter(
            Attendance.tutor_id == self.id,
            Attendance.class_date >= start_date,
            Attendance.class_date < end_date,
        ).all()

    def _calculate_hourly_salary(self, attended_classes):
        """Helper method to calculate hourly-based salary"""
        total_hours = sum(att.duration_hours or 1 for att in attended_classes)
        return total_hours * (self.hourly_rate or 0)

    def _calculate_fixed_monthly_salary(
        self, base_salary, all_classes, attended_classes
    ):
        """Helper method to calculate fixed monthly salary with attendance adjustment"""
        total_classes = len(all_classes)
        if total_classes > 0:
            attendance_rate = len(attended_classes) / total_classes
            return base_salary * attendance_rate
        return base_salary

    # Salary history and payment methods
    def get_salary_history(self):
        """Get salary payment history"""
        if hasattr(self, "salary_payments") and self.salary_payments:
            try:
                return json.loads(self.salary_payments)
            except:
                return []
        return []

    def get_outstanding_salary(self):
        """Get pending salary payments"""
        salary_history = self.get_salary_history()
        return sum(
            payment["amount"]
            for payment in salary_history
            if payment["status"] == "pending"
        )

    def add_salary_payment(
        self, amount, month, year, status="pending", payment_date=None
    ):
        """Add salary payment record"""
        from datetime import datetime

        salary_history = self.get_salary_history()
        payment_record = {
            "id": len(salary_history) + 1,
            "amount": amount,
            "month": month,
            "year": year,
            "status": status,
            "payment_date": payment_date.isoformat() if payment_date else None,
            "created_at": datetime.now().isoformat(),
        }

        salary_history.append(payment_record)
        self.salary_payments = json.dumps(salary_history)
        return payment_record

    def get_compatibility_score(self, student, subject=None):
        """Calculate compatibility score with a specific student"""
        score = 0
        reasons = []

        # Grade compatibility (mandatory)
        tutor_grades = [str(g) for g in self.get_grades()]
        if tutor_grades and str(student.grade) in tutor_grades:
            score += 20
            reasons.append(f"Teaches Grade {student.grade}")
        else:
            return 0, ["Grade mismatch"]  # No compatibility if grade doesn't match

        # Board compatibility (mandatory)
        tutor_boards = [b.lower() for b in self.get_boards()]
        if tutor_boards and student.board.lower() in tutor_boards:
            score += 15
            reasons.append(f"Familiar with {student.board}")
        else:
            return 0, ["Board mismatch"]  # No compatibility if board doesn't match

        # Subject compatibility
        student_subjects = [s.lower() for s in student.get_subjects_enrolled()]
        tutor_subjects = [s.lower() for s in self.get_subjects()]

        if student_subjects and tutor_subjects:
            # Exact matches
            exact_matches = set(student_subjects) & set(tutor_subjects)
            # Partial matches (subject contains or is contained in)
            partial_matches = [
                s
                for s in student_subjects
                for ts in tutor_subjects
                if s in ts or ts in s
            ]

            if exact_matches:
                score += 25
                reasons.append(f"Expert in: {', '.join(list(exact_matches)[:2])}")
            elif partial_matches:
                score += 15
                reasons.append(f"Related expertise: {', '.join(partial_matches[:2])}")

        # If specific subject provided, check for that
        if subject:
            subject_lower = subject.lower()
            if any(subject_lower in ts or ts in subject_lower for ts in tutor_subjects):
                score += 20
                reasons.append(f"Specializes in {subject}")

        # Experience and completion rate bonus
        if self.total_classes > 10:
            completion_rate = self.get_completion_rate()
            if completion_rate >= 95:
                score += 8
                reasons.append("Excellent completion rate (95%+)")
            elif completion_rate >= 90:
                score += 5
                reasons.append("High completion rate (90%+)")
            elif completion_rate >= 85:
                score += 3
                reasons.append("Good completion rate (85%+)")

        # Qualification bonus
        if self.qualification:
            qual_lower = self.qualification.lower()
            if any(
                term in qual_lower for term in ["master", "phd", "doctorate", "ph.d"]
            ):
                score += 8
                reasons.append("Advanced qualification")
            elif any(term in qual_lower for term in ["expert", "specialist", "senior"]):
                score += 5
                reasons.append("Specialist expertise")

    def get_smart_availability_status(self, day=None, time=None):
        """Get detailed availability status for smart matching"""
        availability = self.get_availability()

        if not availability:
            return {
                "status": "no_schedule",
                "message": "No availability schedule set",
                "available_days": [],
                "total_hours_per_week": 0,
            }

        available_days = []
        total_hours = 0

        for day_name, slots in availability.items():
            if slots:
                available_days.append(day_name.title())
                # Calculate hours for this day
                for slot in slots:
                    try:
                        from datetime import datetime, date

                        start = datetime.strptime(slot["start"], "%H:%M").time()
                        end = datetime.strptime(slot["end"], "%H:%M").time()
                        start_dt = datetime.combine(date.today(), start)
                        end_dt = datetime.combine(date.today(), end)
                        hours = (end_dt - start_dt).total_seconds() / 3600
                        total_hours += hours
                    except:
                        continue

        status_info = {
            "status": "available",
            "available_days": available_days,
            "total_hours_per_week": round(total_hours, 1),
            "day_count": len(available_days),
        }

        # Check specific day/time if provided
        if day and time:
            is_available_now = self.is_available_at(day.lower(), time)
            status_info["specific_availability"] = {
                "day": day.title(),
                "time": time,
                "available": is_available_now,
            }

            if not is_available_now:
                status_info["status"] = "busy_at_time"
                status_info["message"] = f"Not available on {day.title()} at {time}"

        return status_info

    def get_student_match_score(self, student_id):
        """Get cached or calculate match score for specific student"""
        from app.models.student import Student

        student = Student.query.get(student_id)
        if not student:
            return 0, []

        return self.get_compatibility_score(student)

    def get_performance_metrics(self):
        """Get comprehensive performance metrics for tutor evaluation"""
        metrics = {
            "test_performance": {
                "score": self.test_score or 0,
                "grade": self.get_test_score_grade(),
                "date": self.test_date.isoformat() if self.test_date else None,
                "percentile": self.get_test_score_percentile(),
            },
            "student_feedback": {
                "average_rating": self.rating or 0,
                "total_ratings": self.total_classes or 0,
                "rating_distribution": self.get_rating_distribution(),
            },
            "class_performance": {
                "total_classes": self.total_classes or 0,
                "completed_classes": self.completed_classes or 0,
                "completion_rate": self.get_completion_rate(),
                "attendance_rate": self.get_attendance_rate(),
            },
            "experience_metrics": {
                "years_active": self.get_years_of_service(),
                "subjects_taught": len(self.get_subjects()),
                "grades_taught": len(self.get_grades()),
                "boards_covered": len(self.get_boards()),
            },
        }

        return metrics

    def get_test_score_percentile(self):
        """Calculate percentile ranking based on test scores"""
        if not self.test_score:
            return 0

        # Get all tutors with test scores
        from app import db

        all_scores = (
            db.session.query(Tutor.test_score)
            .filter(Tutor.test_score.isnot(None))
            .filter(Tutor.status == "active")
            .all()
        )

        if not all_scores:
            return 50  # Default percentile if no data

        scores_list = [score[0] for score in all_scores]
        scores_below = len([s for s in scores_list if s < self.test_score])
        total_scores = len(scores_list)

        return round((scores_below / total_scores) * 100) if total_scores > 0 else 50

    def get_rating_distribution(self):
        """Get distribution of ratings (would need feedback/rating model)"""
        # This would need to be implemented based on your feedback system
        # For now, return a placeholder structure
        return {"5_star": 0, "4_star": 0, "3_star": 0, "2_star": 0, "1_star": 0}

    def get_attendance_rate(self):
        """Calculate tutor attendance rate"""
        from app.models.attendance import Attendance

        total_classes = Attendance.query.filter_by(tutor_id=self.id).count()
        if total_classes == 0:
            return 100.0  # Default for new tutors

        attended_classes = Attendance.query.filter_by(
            tutor_id=self.id, status="present"
        ).count()

        return round((attended_classes / total_classes) * 100, 1)

    def get_years_of_service(self):
        """Calculate years since joining"""
        if not self.created_at:
            return 0

        from datetime import datetime

        years = (datetime.utcnow() - self.created_at).days / 365.25
        return round(years, 1)

    def get_subject_expertise_level(self, subject):
        """Get expertise level for a specific subject"""
        if not subject:
            return "unknown"

        subject_lower = subject.lower()
        tutor_subjects = [s.lower() for s in self.get_subjects()]

        # Check if it's an exact match or close match
        if subject_lower in tutor_subjects:
            # Could add logic to determine expertise level based on:
            # - Number of classes taught in this subject
            # - Student ratings for this subject
            # - Test scores in related areas

            if self.test_score and self.test_score >= 90:
                return "expert"
            elif self.test_score and self.test_score >= 80:
                return "advanced"
            elif self.rating and self.rating >= 4.0:
                return "proficient"
            else:
                return "basic"

        # Check partial matches
        partial_matches = [
            s for s in tutor_subjects if subject_lower in s or s in subject_lower
        ]
        if partial_matches:
            return "related"

        return "none"

    def get_preferred_student_profile(self):
        """Determine what type of students this tutor works best with"""
        # Based on teaching history and performance
        profile = {
            "preferred_grades": self.get_grades(),
            "preferred_boards": self.get_boards(),
            "strength_subjects": self.get_subjects()[:3],  # Top 3 subjects
            "teaching_style": self.get_teaching_style_indicators(),
            "student_level_preference": self.get_student_level_preference(),
        }

        return profile

    def get_teaching_style_indicators(self):
        """Infer teaching style from performance data"""
        styles = []

        if self.test_score and self.test_score >= 85:
            styles.append("academic_focused")

        if self.rating and self.rating >= 4.5:
            styles.append("student_friendly")

        completion_rate = self.get_completion_rate()
        if completion_rate >= 95:
            styles.append("structured")
        elif completion_rate >= 85:
            styles.append("flexible")

        if len(self.get_subjects()) >= 5:
            styles.append("multi_subject")
        else:
            styles.append("specialist")

        return styles or ["balanced"]

    def get_student_level_preference(self):
        """Determine if tutor works better with beginners, intermediate, or advanced students"""
        # This could be enhanced with actual student performance data
        if self.test_score and self.test_score >= 90:
            return "advanced"
        elif self.rating and self.rating >= 4.5:
            return "all_levels"  # High rating suggests adaptability
        else:
            return "beginner_intermediate"

    @staticmethod
    def find_best_matches_for_student(student, subject=None, limit=10):
        """Find best tutor matches for a student with detailed scoring"""
        active_tutors = Tutor.query.filter_by(status="active").all()
        scored_tutors = []

        for tutor in active_tutors:
            # Must have availability
            if not tutor.get_availability():
                continue

            score, reasons = tutor.get_compatibility_score(student, subject)

            if score > 0:  # Only include compatible tutors
                scored_tutors.append(
                    {
                        "tutor": tutor,
                        "score": score,
                        "reasons": reasons,
                        "availability_status": tutor.get_smart_availability_status(),
                        "performance_metrics": tutor.get_performance_metrics(),
                    }
                )

        # Sort by score (highest first)
        scored_tutors.sort(key=lambda x: x["score"], reverse=True)

        return scored_tutors[:limit]

    @staticmethod
    def search_tutors_advanced(search_criteria):
        """Advanced search with multiple criteria"""
        query = Tutor.query.filter_by(status="active")

        # Apply filters
        if search_criteria.get("min_test_score"):
            query = query.filter(Tutor.test_score >= search_criteria["min_test_score"])

        if search_criteria.get("min_rating"):
            query = query.filter(Tutor.rating >= search_criteria["min_rating"])

        if search_criteria.get("subjects"):
            # This would need a more complex query for JSON field search
            pass

        if search_criteria.get("experience_level"):
            level = search_criteria["experience_level"]
            if level == "master":
                query = query.filter(Tutor.qualification.ilike("%master%"))
            elif level == "phd":
                query = query.filter(
                    db.or_(
                        Tutor.qualification.ilike("%phd%"),
                        Tutor.qualification.ilike("%doctorate%"),
                    )
                )

        return query.all()

    def to_dict_enhanced(self):
        """Enhanced dictionary representation with all matching data"""
        base_dict = self.to_dict()  # Your existing to_dict method

        # Add enhanced fields
        base_dict.update(
            {
                "availability_status": self.get_smart_availability_status(),
                "performance_metrics": self.get_performance_metrics(),
                "teaching_style": self.get_teaching_style_indicators(),
                "student_level_preference": self.get_student_level_preference(),
                "years_of_service": self.get_years_of_service(),
                "test_score_percentile": self.get_test_score_percentile(),
                "attendance_rate": self.get_attendance_rate(),
            }
        )

        return base_dict
    
    def get_experience(self):
        """
        Return a dict with 'years' and 'raw'.
        - If `experience` is like "5 years in CBSE / ICSE...",
          extracts 5.
        - If parsing fails, returns 0.
        """
        if not self.experience:
            return {"years": 0, "raw": ""}

        # try to pull the first integer → years
        match = re.search(r"\d+", self.experience)
        years = int(match.group()) if match else 0
        return {"years": years, "raw": self.experience}
    
    def get_rating(self):
        """Return the tutor’s rating rounded to one decimal (0.0 if missing)."""
        return round(self.rating or 0, 1)
