"""All ORM models.

Importing this package registers every table on ``Base.metadata``. Alembic's ``env.py`` and the
test fixtures both rely on that, so new model modules must be imported here.
"""

from app.models.ai import AIGenerationBatch, AIInteraction
from app.models.base import Base, TimestampMixin, utcnow
from app.models.commerce import Order, OrderItem, Payment, Subscription
from app.models.content import Lesson, Resource, Video
from app.models.curriculum import (
    Course,
    Skill,
    SkillPrerequisite,
    SkillRelation,
    Subject,
    Topic,
    Unit,
)
from app.models.enums import (
    AssignmentStatus,
    AttendanceStatus,
    DeliveryMode,
    EnrollmentStatus,
    LeadStatus,
    LearningFormat,
    OrderStatus,
    PaymentStatus,
    QuestionType,
    ReviewStatus,
    SessionStatus,
    UserRole,
)
from app.models.progress import (
    Achievement,
    Attempt,
    Certificate,
    CourseEnrollment,
    LessonProgress,
    PracticeSession,
    StudentAchievement,
    StudentSkillMastery,
    XPEvent,
)
from app.models.question import Question, QuestionVariant
from app.models.site import BlogPost, ContactLead, Testimonial
from app.models.tutoring import (
    Assignment,
    AssignmentSubmission,
    Attendance,
    ClassEnrollment,
    ClassGroup,
    LiveSession,
    ScheduleSlot,
    TutoringProduct,
    TutoringRequest,
)
from app.models.user import (
    ParentProfile,
    ParentStudentLink,
    StudentProfile,
    TeacherProfile,
    User,
)

__all__ = [
    "AIGenerationBatch",
    "AIInteraction",
    "Achievement",
    "Assignment",
    "AssignmentStatus",
    "AssignmentSubmission",
    "Attempt",
    "Attendance",
    "AttendanceStatus",
    "Base",
    "BlogPost",
    "Certificate",
    "ClassEnrollment",
    "ClassGroup",
    "ContactLead",
    "Course",
    "CourseEnrollment",
    "DeliveryMode",
    "EnrollmentStatus",
    "LeadStatus",
    "LearningFormat",
    "Lesson",
    "LessonProgress",
    "LiveSession",
    "Order",
    "OrderItem",
    "OrderStatus",
    "ParentProfile",
    "ParentStudentLink",
    "Payment",
    "PaymentStatus",
    "PracticeSession",
    "Question",
    "QuestionType",
    "QuestionVariant",
    "Resource",
    "ReviewStatus",
    "ScheduleSlot",
    "SessionStatus",
    "Skill",
    "SkillPrerequisite",
    "SkillRelation",
    "StudentAchievement",
    "StudentProfile",
    "StudentSkillMastery",
    "Subject",
    "Subscription",
    "TeacherProfile",
    "Testimonial",
    "TimestampMixin",
    "Topic",
    "TutoringProduct",
    "TutoringRequest",
    "Unit",
    "User",
    "UserRole",
    "Video",
    "XPEvent",
    "utcnow",
]
