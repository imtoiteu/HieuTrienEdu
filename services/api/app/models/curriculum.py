"""Curriculum hierarchy and the skill graph.

    Subject → Course (one per grade) → Unit → Topic → Skill → Lesson / Question

The hierarchy is deliberately strict: **every question hangs off exactly one skill**, and every
skill hangs off exactly one topic. That is what makes it possible to answer the question the whole
adaptive system depends on — *which skill does this question test?*
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ReviewStatus

if TYPE_CHECKING:
    from app.models.content import Lesson
    from app.models.question import Question


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    courses: Mapped[list[Course]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Course.grade"
    )


class Course(Base, TimestampMixin):
    """A subject at one grade, e.g. "Mathematics — Grade 7"."""

    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("subject_id", "grade", name="subject_grade"),
        CheckConstraint("grade BETWEEN 1 AND 12", name="grade_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # ``is_published`` is the flag every existing query filters on; ``status`` adds the draft and
    # archived stages the admin workflow needs. They are kept in step by the admin API rather than
    # by a database trigger, and ``is_published`` remains the single source of truth for reads.
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ReviewStatus.PUBLISHED, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    thumbnail_url: Mapped[str | None] = mapped_column(String(600))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="SET NULL")
    )
    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(Text)

    subject: Mapped[Subject] = relationship(back_populates="courses")
    units: Mapped[list[Unit]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Unit.position"
    )


class Unit(Base, TimestampMixin):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    course: Mapped[Course] = relationship(back_populates="units")
    topics: Mapped[list[Topic]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", order_by="Topic.position"
    )


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    unit: Mapped[Unit] = relationship(back_populates="topics")
    skills: Mapped[list[Skill]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="Skill.position"
    )


class Skill(Base, TimestampMixin):
    """The atomic unit of learning and of mastery tracking.

    ``bkt_*`` columns hold the per-skill Bayesian Knowledge Tracing parameters. Keeping them on the
    skill (rather than globally) means a fiddly skill like "dividing fractions" can carry a higher
    slip probability than a mechanical one like "reading a thermometer".
    """

    __tablename__ = "skills"
    __table_args__ = (CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tags: Mapped[list[str]] = mapped_column(default=list)

    # BKT parameters — see docs/ADAPTIVE_LEARNING.md for what each one means.
    bkt_p_init: Mapped[float] = mapped_column(default=0.10, nullable=False)
    bkt_p_transit: Mapped[float] = mapped_column(default=0.08, nullable=False)
    bkt_p_slip: Mapped[float] = mapped_column(default=0.15, nullable=False)
    bkt_p_guess: Mapped[float] = mapped_column(default=0.28, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="skills")

    # ``passive_deletes`` is load-bearing, not an optimisation. ``Question.skill_id`` is NOT NULL
    # with an ``ON DELETE CASCADE`` foreign key, but SQLAlchemy's default behaviour when deleting a
    # parent is to *nullify* the child's foreign key first — which fails the NOT NULL constraint
    # and aborts the whole transaction. Deleting a course therefore crashed instead of cascading.
    # Telling the ORM to leave it to the database makes the declared cascade the one that runs.
    questions: Mapped[list[Question]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", passive_deletes=True
    )
    # ``Lesson.skill_id`` is nullable with ON DELETE SET NULL, so nullifying is correct here: a
    # lesson outlives the skill it was tagged with.
    lessons: Mapped[list[Lesson]] = relationship(back_populates="skill")

    prerequisite_links: Mapped[list[SkillPrerequisite]] = relationship(
        foreign_keys="SkillPrerequisite.skill_id",
        back_populates="skill",
        cascade="all, delete-orphan",
    )
    dependent_links: Mapped[list[SkillPrerequisite]] = relationship(
        foreign_keys="SkillPrerequisite.prerequisite_id",
        back_populates="prerequisite",
        cascade="all, delete-orphan",
    )

    @property
    def course(self) -> Course:
        return self.topic.unit.course


class SkillPrerequisite(Base):
    """Directed edge of the skill graph: ``prerequisite`` must be learned before ``skill``."""

    __tablename__ = "skill_prerequisites"
    __table_args__ = (
        UniqueConstraint("skill_id", "prerequisite_id", name="skill_prereq"),
        CheckConstraint("skill_id != prerequisite_id", name="no_self_prereq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    prerequisite_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    # 1.0 = hard prerequisite (gate on it), lower values = helpful but not blocking.
    strength: Mapped[float] = mapped_column(default=1.0, nullable=False)

    skill: Mapped[Skill] = relationship(
        foreign_keys=[skill_id], back_populates="prerequisite_links"
    )
    prerequisite: Mapped[Skill] = relationship(
        foreign_keys=[prerequisite_id], back_populates="dependent_links"
    )


class SkillRelation(Base):
    """Undirected "related skills" edge, used for lateral recommendations and cross-links."""

    __tablename__ = "skill_relations"
    __table_args__ = (UniqueConstraint("skill_id", "related_skill_id", name="skill_related"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    related_skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(250))

    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
