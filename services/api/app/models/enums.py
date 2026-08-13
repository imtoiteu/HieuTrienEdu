"""Shared enumerations.

These are stored as plain strings rather than native database enums: adding a value to a PostgreSQL
enum requires a migration and locks the type, whereas string columns with a Python-side enum give us
validation where it matters (the application) and zero migration friction where it does not.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    PARENT = "parent"
    TEACHER = "teacher"
    ADMIN = "admin"


class QuestionType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    MULTIPLE_SELECT = "multiple_select"
    NUMERIC = "numeric"
    EXPRESSION = "expression"
    FILL_BLANK = "fill_blank"
    TRUE_FALSE = "true_false"
    MATCHING = "matching"
    ORDERING = "ordering"
    SHORT_ANSWER = "short_answer"


class LearningFormat(StrEnum):
    ONE_TO_ONE = "one_to_one"
    GROUP = "group"
    ONLINE_LIVE = "online_live"
    RECORDED = "recorded"
    HYBRID = "hybrid"


class DeliveryMode(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    HYBRID = "hybrid"


class EnrollmentStatus(StrEnum):
    """Enrollment lifecycle.

    ``CONFIRMED`` sits between pending and active: an administrator has approved the request and
    the place is held, but the course has not started yet. Collapsing the two would make "how many
    students are actually sitting in class this week" unanswerable.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class SessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"


class ReviewStatus(StrEnum):
    """Lifecycle for teacher- and AI-authored content.

    ``ARCHIVED`` is distinct from ``REJECTED``: rejected means "this was never good enough to
    publish", archived means "this was published and has now been retired". Retiring content must
    not look like a failed review in the admin lists, and archived rows are kept rather than
    deleted so historical attempts and lesson progress keep referring to something real.
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class LeadStatus(StrEnum):
    """Consultation / enquiry pipeline.

    The centre's staff actually work this as a funnel, so the values are the funnel stages rather
    than a generic open/closed pair. ``ENROLLED`` is kept as an alias of the "registered" stage
    because rows created before this enum was widened already use it.
    """

    NEW = "new"
    CONTACTED = "contacted"
    CONSULTING = "consulting"
    INTERESTED = "interested"
    ENROLLED = "enrolled"
    COMPLETED = "completed"
    REJECTED = "rejected"
    NO_RESPONSE = "no_response"
    CLOSED = "closed"


class CategoryKind(StrEnum):
    """What a ``ContentCategory`` is used for.

    One table rather than one per taxonomy: the centre invents new groupings (a new exam-prep
    track, a new grade band) far more often than a developer is available to add a table, and the
    admin UI is identical for all of them.
    """

    SUBJECT = "subject"
    GRADE = "grade"
    PROGRAM = "program"
    TOPIC = "topic"
    TAG = "tag"


class MediaKind(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"


class NotificationKind(StrEnum):
    LEAD_CREATED = "lead_created"
    TUTORING_REQUEST_CREATED = "tutoring_request_created"
    ENROLLMENT_REQUESTED = "enrollment_requested"
    STUDENT_REGISTERED = "student_registered"
    COURSE_ASSIGNED = "course_assigned"
    CLASS_UPCOMING = "class_upcoming"
    ORDER_PLACED = "order_placed"
