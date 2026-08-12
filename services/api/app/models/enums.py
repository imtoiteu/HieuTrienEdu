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
    PENDING = "pending"
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
    """Lifecycle for teacher- and AI-authored content."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    ENROLLED = "enrolled"
    CLOSED = "closed"
