# app/models/__init__.py

from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.system_document import SystemDocument
from app.models.escalation import Escalation
from app.models.demo_student import DemoStudent
from app.models.notice import Notice, NoticeAttachment, NoticeDistribution

__all__ = [
    'User', 
    'Department', 
    'Tutor', 
    'Student', 
    'Class', 
    'Attendance', 
    'SystemDocument', 
    'Escalation',
    'DemoStudent',
    'Notice', 
    'NoticeAttachment', 
    'NoticeDistribution'

]