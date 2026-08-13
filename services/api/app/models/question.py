"""The question bank.

A ``Question`` row is always a **template**. A template with no ``variables`` is simply a static
question — this keeps one code path instead of two, and means a teacher can parameterise an existing
static question later without a data migration.

A ``QuestionVariant`` is a template rendered with one concrete draw of its variables. Variants are
reproducible from ``(question_id, seed)`` alone, so we could regenerate rather than store them; we
store them anyway because teachers need to see *exactly* what a student was shown when reviewing a
disputed answer, and because it lets analytics ask "which variant do students fail most?".
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TranslatableMixin
from app.models.curriculum import Skill
from app.models.enums import QuestionType, ReviewStatus


class Question(Base, TimestampMixin, TranslatableMixin):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        Index("ix_questions_skill_difficulty", "skill_id", "difficulty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)

    # Taxonomy. skill_id is the load-bearing one; the rest are denormalised for fast filtering
    # in the teacher question browser without three joins on every keystroke.
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    subject_slug: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    grade: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    topic_slug: Mapped[str] = mapped_column(String(140), index=True, nullable=False)

    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    # --- template payload ------------------------------------------------------------
    # ``prompt`` may contain {placeholders} resolved from the sampled variables.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Variable specifications, e.g. {"distance": {"type": "int", "min": 20, "max": 200, "step": 5}}
    variables: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Boolean expressions every draw must satisfy, e.g. ["distance % time == 0"]
    constraints: Mapped[list[str]] = mapped_column(default=list)
    # How the correct answer is produced and compared. Shape depends on question_type;
    # see app/exercise_engine/types.py and docs/QUESTION_ENGINE.md.
    answer_spec: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Type-specific extras: choices, blanks, pairs, ordering items, units, tolerances.
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)

    # Ordered, progressively-revealing hints. Each: {"text": "...", "reveals_answer": false}
    hints: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    # Worked solution steps. Each: {"text": "...", "math": "..."}
    solution: Mapped[list[dict[str, Any]]] = mapped_column(default=list)

    tags: Mapped[list[str]] = mapped_column(default=list)
    estimated_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=ReviewStatus.PUBLISHED, nullable=False
    )
    is_parametric: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- provenance ------------------------------------------------------------------
    # Present on every row so imported open content can never lose its attribution.
    source: Mapped[str | None] = mapped_column(String(200))
    license: Mapped[str | None] = mapped_column(String(80))
    attribution: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- live statistics, updated on each graded attempt ------------------------------
    times_served: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    skill: Mapped[Skill] = relationship(back_populates="questions")
    variants: Mapped[list[QuestionVariant]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    @property
    def success_rate(self) -> float | None:
        if self.times_served == 0:
            return None
        return self.times_correct / self.times_served

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Question {self.slug} ({self.question_type})>"


class QuestionVariant(Base, TimestampMixin):
    """One concrete rendering of a template. Reproducible from ``(question_id, seed)``."""

    __tablename__ = "question_variants"
    __table_args__ = (UniqueConstraint("question_id", "seed", name="question_seed"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    # The sampled variable values, e.g. {"distance": 120, "time": 3}
    variable_values: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Fully-resolved, student-facing payload (prompt, choices, blanks ...).
    rendered: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # The computed correct answer. NEVER serialised to a student before they answer.
    answer: Mapped[dict[str, Any]] = mapped_column(default=dict)
    rendered_hints: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    rendered_solution: Mapped[list[dict[str, Any]]] = mapped_column(default=list)

    question: Mapped[Question] = relationship(back_populates="variants")


__all__ = ["Question", "QuestionVariant", "QuestionType"]
