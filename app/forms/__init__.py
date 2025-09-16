# REPLACE the content of app/forms/__init__.py with this:

from app.forms.auth import LoginForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm
from app.forms.user import CreateUserForm, EditUserForm, TutorRegistrationForm, StudentRegistrationForm
from app.forms.profile import EditProfileForm, TutorProfileEditForm, BankingDetailsForm  # Add TutorProfileEditForm
from app.forms.class_forms import (
    CreateClassForm, EditClassForm, RescheduleClassForm, CancelClassForm,
    AttendanceForm, ClassFeedbackForm, BulkClassForm, ClassSearchForm
)
from app.forms.demo_forms import DemoStudentForm, DemoClassForm, DemoFeedbackForm, ConvertDemoForm
from app.forms.notice_forms import NoticeForm, NoticeSearchForm, UserNoticeSearchForm, BulkNoticeActionForm

__all__ = [
    'LoginForm', 'ForgotPasswordForm', 'ResetPasswordForm', 'ChangePasswordForm',
    'CreateUserForm', 'EditUserForm', 'TutorRegistrationForm', 'StudentRegistrationForm',
    'EditProfileForm', 'TutorProfileEditForm', 'BankingDetailsForm',  # Add TutorProfileEditForm
    'CreateClassForm', 'EditClassForm', 'RescheduleClassForm', 'CancelClassForm',
    'AttendanceForm', 'ClassFeedbackForm', 'BulkClassForm', 'ClassSearchForm',
    'DemoStudentForm', 'DemoClassForm', 'DemoFeedbackForm', 'ConvertDemoForm',
    'NoticeForm', 'NoticeSearchForm', 'UserNoticeSearchForm', 'BulkNoticeActionForm'
]