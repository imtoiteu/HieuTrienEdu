"""Attempts, mastery, progress and gamification."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TranslatableMixin
from app.models.curriculum import Course, Skill
from app.models.question import Question, QuestionVariant

if TYPE_CHECKING:
    from app.models.user import StudentProfile


class PracticeSession(Base, TimestampMixin):
    """A run of practice on one skill (or a mixed review). Groups attempts for reporting."""

    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id", ondelete="SET NULL"))
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(String(30), default="practice", nullable=False)

    target_questions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    questions_answered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    mastery_before: Mapped[float | None]
    mastery_after: Mapped[float | None]
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    skill: Mapped[Skill | None] = relationship()
    attempts: Mapped[list[Attempt]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Attempt(Base, TimestampMixin):
    """One graded submission. This is the append-only event log the whole system learns from."""

    __tablename__ = "attempts"
    __table_args__ = (Index("ix_attempts_student_skill", "student_id", "skill_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("question_variants.id", ondelete="SET NULL")
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE")
    )

    user_answer: Mapped[dict[str, Any]] = mapped_column(default=dict)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(default=0.0, nullable=False)  # 0..1, partial credit
    feedback: Mapped[dict[str, Any]] = mapped_column(default=dict)

    hints_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Mastery snapshot around this attempt, so a progress chart is a single query.
    mastery_before: Mapped[float | None]
    mastery_after: Mapped[float | None]

    student: Mapped[StudentProfile] = relationship(back_populates="attempts")
    question: Mapped[Question] = relationship()
    variant: Mapped[QuestionVariant | None] = relationship()
    skill: Mapped[Skill] = relationship()
    session: Mapped[PracticeSession | None] = relationship(back_populates="attempts")


class StudentSkillMastery(Base, TimestampMixin):
    """Current BKT state for one (student, skill) pair."""

    __tablename__ = "student_skill_mastery"
    __table_args__ = (UniqueConstraint("student_id", "skill_id", name="student_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )

    mastery_probability: Mapped[float] = mapped_column(default=0.10, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Rolling window of the last N outcomes as 1/0, newest last. Powers "recent performance"
    # without scanning the attempts table on every dashboard render.
    recent_outcomes: Mapped[list[Any]] = mapped_column(default=list)

    last_practiced_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    mastered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[StudentProfile] = relationship(back_populates="skill_mastery")
    skill: Mapped[Skill] = relationship()

    @property
    def recent_accuracy(self) -> float | None:
        if not self.recent_outcomes:
            return None
        return sum(self.recent_outcomes) / len(self.recent_outcomes)


class LessonProgress(Base, TimestampMixin):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("student_id", "lesson_id", name="student_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Resume point for the lesson's video, in seconds.
    video_position_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_viewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class CourseEnrollment(Base, TimestampMixin):
    """Self-serve enrollment in a *self-study* course (distinct from paid class enrollment)."""

    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="student_course"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_activity_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    course: Mapped[Course] = relationship()


class XPEvent(Base, TimestampMixin):
    """Append-only XP ledger. The denormalised total lives on StudentProfile."""

    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(60), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(default=dict)
    occurred_on: Mapped[dt.date] = mapped_column(Date, nullable=False)


class Achievement(Base, TimestampMixin, TranslatableMixin):
    """A badge and the rule that earns it.

    Translatable because the name and description are shown to the student. ``criteria`` is not:
    it is machine-checkable and must mean the same thing in every language.
    """

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(60), default="award", nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="bronze", nullable=False)
    # Machine-checkable rule, e.g. {"type": "streak_days", "value": 7}
    criteria: Mapped[dict[str, Any]] = mapped_column(default=dict)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class StudentAchievement(Base, TimestampMixin):
    __tablename__ = "student_achievements"
    __table_args__ = (UniqueConstraint("student_id", "achievement_id", name="student_achievement"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    earned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    achievement: Mapped[Achievement] = relationship()


class Certificate(Base, TimestampMixin):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    serial: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    issued_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mastery_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
