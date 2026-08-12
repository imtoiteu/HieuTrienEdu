"""AI interaction records.

**Status: schema and plumbing only.** No model provider is called anywhere in this codebase — that
is deliberately deferred to a later phase. These tables exist now so that when a provider is wired
up, every request and response is already auditable from day one rather than being retrofitted.

Auditability matters here more than usual: an AI tutor talking to 12-year-olds needs a reviewable
transcript, and an AI-generated question must be traceable to the prompt that produced it.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import ReviewStatus


class AIInteraction(Base, TimestampMixin):
    __tablename__ = "ai_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL")
    )

    # tutor_hint | explain_mistake | generate_questions | summarise_progress
    feature: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="disabled", nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))

    # Context the feature was invoked with (question id, skill, attempt id, ...).
    request_context: Mapped[dict[str, Any]] = mapped_column(default=dict)
    prompt: Mapped[str | None] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), default="not_configured", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)

    # Safety: whether a human reviewed this output before a student saw it.
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class AIGenerationBatch(Base, TimestampMixin):
    """A teacher's request for N draft questions.

    Drafts land in ``Question`` with ``status = pending_review`` and ``generated_by_ai = True``.
    They are invisible to students until a teacher explicitly approves them — enforced by the
    question query filters, not merely by convention.
    """

    __tablename__ = "ai_generation_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id", ondelete="SET NULL"))
    subject_slug: Mapped[str | None] = mapped_column(String(60))
    grade: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    question_type: Mapped[str | None] = mapped_column(String(30))
    count_requested: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    count_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    count_approved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=ReviewStatus.DRAFT, nullable=False)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
