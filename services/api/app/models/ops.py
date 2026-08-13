"""Back-office plumbing: notifications, the audit trail, lead notes and teacher credentials."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import NotificationKind
from app.models.user import TeacherProfile


class Notification(Base, TimestampMixin):
    """An event worth a human's attention.

    ``user_id`` is nullable and means "any administrator": a consultation request is not addressed
    to one person, and pinning it to whoever happened to be seeded first would hide it from
    everyone else. Per-user rows are used for genuinely personal events such as a course
    assignment.
    """

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Broadcast target when user_id is NULL, e.g. "admin" or "teacher".
    audience_role: Mapped[str | None] = mapped_column(String(20), index=True)

    kind: Mapped[str] = mapped_column(
        String(40), default=NotificationKind.LEAD_CREATED, nullable=False
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(String(600))

    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base, TimestampMixin):
    """Append-only record of consequential admin actions.

    Written for state changes an administrator could later need to account for — deleting a
    course, resetting a password, approving an enrollment — not for reads, which would bury the
    interesting rows in noise.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(60), nullable=False)  # create | update | delete ...
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(default=dict)


class LeadNote(Base, TimestampMixin):
    """A consultation note attached to either kind of enquiry.

    Two nullable foreign keys instead of a polymorphic ``(type, id)`` pair: contact enquiries and
    tutoring requests are genuinely different tables, and real foreign keys mean a deleted enquiry
    cannot leave orphaned notes behind.
    """

    __tablename__ = "lead_notes"
    __table_args__ = (Index("ix_lead_notes_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact_leads.id", ondelete="CASCADE")
    )
    tutoring_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("tutoring_requests.id", ondelete="CASCADE")
    )

    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_name: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # note | call | email | meeting | status_change
    kind: Mapped[str] = mapped_column(String(30), default="note", nullable=False)


class TeacherCredential(Base, TimestampMixin):
    """One structured line of a teacher's background.

    A single ``qualifications`` string array cannot answer "which university, which year, which
    degree", and the public profile page needs those as separate fields to render an education
    table. ``kind`` keeps awards, degrees, certifications and publications in one ordered list
    without four near-identical tables.
    """

    __tablename__ = "teacher_credentials"
    __table_args__ = (Index("ix_teacher_credentials_teacher_kind", "teacher_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    # education | award | certification | publication | competition | experience
    kind: Mapped[str] = mapped_column(String(30), default="award", nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    organisation: Mapped[str | None] = mapped_column(String(250))
    year_start: Mapped[int | None] = mapped_column(Integer)
    year_end: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(600))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    teacher: Mapped[TeacherProfile] = relationship(back_populates="credentials")


class TeacherSubjectAssignment(Base, TimestampMixin):
    """Which subject/grade a teacher is approved to teach.

    The JSON ``subjects``/``grades`` arrays on TeacherProfile are fine for rendering a card, but
    authorisation cannot be built on a value that is not a foreign key. These rows are what the
    teacher-scoped endpoints check before letting a teacher touch a course.
    """

    __tablename__ = "teacher_subject_assignments"
    __table_args__ = (
        Index("ix_teacher_subject_assignments_teacher", "teacher_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE")
    )
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    grade: Mapped[int | None] = mapped_column(Integer)
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
