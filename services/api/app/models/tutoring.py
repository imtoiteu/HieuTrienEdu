"""The tutoring business: products, classes, schedules, live sessions, assignments and quizzes.

Following the separation validated during research (Frappe Learning's Course/Batch split), the
*content* hierarchy in ``curriculum.py`` is completely independent of the *cohort* hierarchy here.
A ClassGroup teaches a Course; a Course knows nothing about who is enrolled.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TranslatableMixin
from app.models.curriculum import Course
from app.models.enums import (
    AssignmentStatus,
    AttendanceStatus,
    DeliveryMode,
    EnrollmentStatus,
    LeadStatus,
    LearningFormat,
    ReviewStatus,
    SessionStatus,
)
from app.models.user import StudentProfile, TeacherProfile

if TYPE_CHECKING:
    from app.models.ops import LeadNote


class TutoringProduct(Base, TimestampMixin, TranslatableMixin):
    """A sellable learning package: 1-to-1, group, online live, recorded or hybrid."""

    __tablename__ = "tutoring_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)

    format: Mapped[str] = mapped_column(String(20), default=LearningFormat.GROUP, nullable=False)
    delivery_mode: Mapped[str] = mapped_column(
        String(20), default=DeliveryMode.ONLINE, nullable=False
    )
    subject_slug: Mapped[str | None] = mapped_column(String(60), index=True)
    grade_min: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    grade_max: Mapped[int] = mapped_column(Integer, default=9, nullable=False)

    # Prices are integer VND — VND has no minor unit, so floats would only invite rounding bugs.
    price_vnd: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_unit: Mapped[str] = mapped_column(String(20), default="session", nullable=False)
    sessions_included: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    session_minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    features: Mapped[list[str]] = mapped_column(default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- admin-managed presentation and scheduling -----------------------------------
    thumbnail_url: Mapped[str | None] = mapped_column(String(600))
    status: Mapped[str] = mapped_column(String(20), default=ReviewStatus.PUBLISHED, nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="SET NULL")
    )
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(Text)

    teacher: Mapped[TeacherProfile | None] = relationship()


class ClassGroup(Base, TimestampMixin, TranslatableMixin):
    """A concrete cohort with a teacher, a schedule and a roster."""

    __tablename__ = "class_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("tutoring_products.id", ondelete="SET NULL")
    )
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="SET NULL")
    )

    format: Mapped[str] = mapped_column(String(20), default=LearningFormat.GROUP, nullable=False)
    delivery_mode: Mapped[str] = mapped_column(
        String(20), default=DeliveryMode.ONLINE, nullable=False
    )
    capacity: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(250))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Ho_Chi_Minh", nullable=False)
    is_open_for_enrollment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course: Mapped[Course | None] = relationship()
    teacher: Mapped[TeacherProfile | None] = relationship()
    schedule_slots: Mapped[list[ScheduleSlot]] = relationship(
        back_populates="class_group", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[LiveSession]] = relationship(
        back_populates="class_group", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list[ClassEnrollment]] = relationship(
        back_populates="class_group", cascade="all, delete-orphan"
    )

    @property
    def seats_taken(self) -> int:
        return sum(1 for e in self.enrollments if e.status == EnrollmentStatus.ACTIVE)


class ScheduleSlot(Base):
    """Recurring weekly slot, e.g. Tuesdays 18:00–19:30."""

    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)

    class_group: Mapped[ClassGroup] = relationship(back_populates="schedule_slots")


class ClassEnrollment(Base, TimestampMixin):
    __tablename__ = "class_enrollments"
    __table_args__ = (UniqueConstraint("class_group_id", "student_id", name="class_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(
        String(20), default=EnrollmentStatus.PENDING, nullable=False
    )
    enrolled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    # --- admin workflow ---------------------------------------------------------------
    # ``payment_status`` is denormalised from the linked order so the enrollment table can be
    # filtered on it without a join; a class with no order (a free trial place) still needs a
    # sensible value, which an order join could not provide.
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)
    preferred_schedule: Mapped[str | None] = mapped_column(Text)
    requested_format: Mapped[str | None] = mapped_column(String(30))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(Text)

    class_group: Mapped[ClassGroup] = relationship(back_populates="enrollments")
    student: Mapped[StudentProfile] = relationship()


class LiveSession(Base, TimestampMixin, TranslatableMixin):
    """One scheduled meeting. ``provider`` is resolved by ``services/live_class.py``.

    Translatable because the title and topic summary are what a student and their parent read on
    the class schedule — the times and the join link are the same in every language, the sentence
    describing the lesson is not.
    """

    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    topic_summary: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    provider: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    provider_meeting_id: Mapped[str | None] = mapped_column(String(120))
    join_url: Mapped[str | None] = mapped_column(String(800))
    host_url: Mapped[str | None] = mapped_column(String(800))
    passcode: Mapped[str | None] = mapped_column(String(60))
    recording_url: Mapped[str | None] = mapped_column(String(800))

    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.SCHEDULED, nullable=False)
    provider_payload: Mapped[dict[str, Any]] = mapped_column(default=dict)

    class_group: Mapped[ClassGroup] = relationship(back_populates="sessions")
    attendance: Mapped[list[Attendance]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("session_id", "student_id", name="session_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=AttendanceStatus.PRESENT, nullable=False
    )
    minutes_attended: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    teacher_note: Mapped[str | None] = mapped_column(Text)

    session: Mapped[LiveSession] = relationship(back_populates="attendance")
    student: Mapped[StudentProfile] = relationship()


class TutoringRequest(Base, TimestampMixin):
    """A 1-to-1 booking request. Becomes a ClassGroup + LiveSessions once a teacher accepts."""

    __tablename__ = "tutoring_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL")
    )
    # Denormalised contact details so a parent can request tutoring before creating an account.
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40))

    subject_slug: Mapped[str] = mapped_column(String(60), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(
        String(20), default=LearningFormat.ONE_TO_ONE, nullable=False
    )
    delivery_mode: Mapped[str] = mapped_column(
        String(20), default=DeliveryMode.ONLINE, nullable=False
    )
    preferred_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="SET NULL")
    )
    # [{"weekday": 2, "start": "18:00", "end": "19:30"}]
    preferred_slots: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    sessions_requested: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    goals: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NEW, nullable=False)
    admin_note: Mapped[str | None] = mapped_column(Text)
    assigned_class_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_groups.id", ondelete="SET NULL")
    )

    # --- pipeline, mirroring ContactLead so the two feed one consultation inbox --------
    contact_student_name: Mapped[str | None] = mapped_column(String(200))
    parent_name: Mapped[str | None] = mapped_column(String(200))
    parent_phone: Mapped[str | None] = mapped_column(String(40))
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    consultation_result: Mapped[str | None] = mapped_column(Text)
    last_contacted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    converted_student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL")
    )
    converted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    source_page: Mapped[str | None] = mapped_column(String(160))

    preferred_teacher: Mapped[TeacherProfile | None] = relationship()
    notes: Mapped[list[LeadNote]] = relationship(
        cascade="all, delete-orphan",
        order_by="LeadNote.created_at.desc()",
        primaryjoin="TutoringRequest.id == LeadNote.tutoring_request_id",
    )


class Assignment(Base, TimestampMixin):
    """Homework set by a teacher: a list of skills and/or specific questions, with a due date."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    class_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE")
    )
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(20), default="homework", nullable=False)

    skill_ids: Mapped[list[Any]] = mapped_column(default=list)
    question_ids: Mapped[list[Any]] = mapped_column(default=list)
    questions_per_skill: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)

    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    submissions: Mapped[list[AssignmentSubmission]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class AssignmentSubmission(Base, TimestampMixin):
    __tablename__ = "assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="assignment_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(20), default=AssignmentStatus.ASSIGNED, nullable=False
    )
    score_percent: Mapped[float | None]
    submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    teacher_feedback: Mapped[str | None] = mapped_column(Text)

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    student: Mapped[StudentProfile] = relationship()
