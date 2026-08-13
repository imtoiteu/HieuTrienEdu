"""Identity: one ``User`` row per login, plus a role-specific profile."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.ops import TeacherCredential
    from app.models.progress import Attempt, StudentSkillMastery


class User(Base, TimestampMixin):
    """A login. Role determines which profile table carries the extra fields.

    We keep a single users table (rather than separate student/teacher logins) so that
    authentication, password reset and session handling have exactly one implementation.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.STUDENT)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(40))
    last_login_at: Mapped[dt.datetime | None]

    student_profile: Mapped[StudentProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    teacher_profile: Mapped[TeacherProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    parent_profile: Mapped[ParentProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id} {self.email} ({self.role})>"


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    grade: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    school: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[dt.date | None] = mapped_column(Date)

    # Gamification counters live here rather than in a separate table because they are read on
    # every dashboard load and are always needed together.
    xp_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_date: Mapped[dt.date | None] = mapped_column(Date)

    learning_goals: Mapped[list[str]] = mapped_column(default=list)

    user: Mapped[User] = relationship(back_populates="student_profile")
    attempts: Mapped[list[Attempt]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    skill_mastery: Mapped[list[StudentSkillMastery]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    parent_links: Mapped[list[ParentStudentLink]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class TeacherProfile(Base, TimestampMixin):
    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    headline: Mapped[str | None] = mapped_column(String(250))
    bio: Mapped[str | None] = mapped_column(Text)
    subjects: Mapped[list[str]] = mapped_column(default=list)  # ["mathematics", "physics"]
    grades: Mapped[list[Any]] = mapped_column(default=list)  # [6, 7, 8, 9]
    qualifications: Mapped[list[str]] = mapped_column(default=list)
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    languages: Mapped[list[str]] = mapped_column(default=list)
    hourly_rate_vnd: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float] = mapped_column(default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepts_one_to_one: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Weekly availability, e.g. [{"weekday": 1, "start": "18:00", "end": "20:00"}]
    availability: Mapped[list[dict[str, Any]]] = mapped_column(default=list)

    # --- public profile, managed from the admin CMS ----------------------------------
    # ``slug`` gives every teacher a stable public URL that does not leak the database id and
    # survives a rename. Nullable because profiles created before this column existed have none
    # until an administrator publishes them.
    slug: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    photo_url: Mapped[str | None] = mapped_column(String(600))
    teaching_philosophy: Mapped[str | None] = mapped_column(Text)
    teaching_style: Mapped[str | None] = mapped_column(Text)
    specializations: Mapped[list[str]] = mapped_column(default=list)
    learning_formats: Mapped[list[str]] = mapped_column(default=list)
    video_intro_url: Mapped[str | None] = mapped_column(String(600))
    # [{"url": "...", "caption": "..."}]
    gallery: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    # {"facebook": "...", "youtube": "...", "linkedin": "..."}
    social_links: Mapped[dict[str, Any]] = mapped_column(default=dict)
    public_email: Mapped[str | None] = mapped_column(String(320))
    public_phone: Mapped[str | None] = mapped_column(String(40))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="teacher_profile")
    credentials: Mapped[list[TeacherCredential]] = relationship(
        back_populates="teacher",
        cascade="all, delete-orphan",
        order_by="(TeacherCredential.kind, TeacherCredential.position)",
    )


class ParentProfile(Base, TimestampMixin):
    __tablename__ = "parent_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    contact_preference: Mapped[str] = mapped_column(String(20), default="email", nullable=False)

    user: Mapped[User] = relationship(back_populates="parent_profile")
    student_links: Mapped[list[ParentStudentLink]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )


class ParentStudentLink(Base, TimestampMixin):
    """Many-to-many: a parent may have several children, a child may have two guardians."""

    __tablename__ = "parent_student_links"
    __table_args__ = (UniqueConstraint("parent_id", "student_id", name="parent_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("parent_profiles.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    relationship_label: Mapped[str] = mapped_column(String(40), default="parent", nullable=False)

    parent: Mapped[ParentProfile] = relationship(back_populates="student_links")
    student: Mapped[StudentProfile] = relationship(back_populates="parent_links")
