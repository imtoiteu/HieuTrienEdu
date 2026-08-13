"""Lessons, videos and downloadable resources."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TranslatableMixin
from app.models.curriculum import Skill, Topic
from app.models.enums import ReviewStatus


class Lesson(Base, TimestampMixin, TranslatableMixin):
    """A lesson is an ordered list of typed blocks stored as JSON.

    Blocks rather than one HTML blob, because the student UI needs to treat an ``interactive``
    block very differently from a ``text`` block, and because a JSON array can be reordered by the
    teacher editor without an HTML parser. Block shapes are documented in docs/CURRICULUM.md and
    validated by ``app.schemas.content.LessonBlock``.
    """

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id", ondelete="SET NULL"))

    summary: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[list[str]] = mapped_column(default=list)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    blocks: Mapped[list[dict[str, Any]]] = mapped_column(default=list)

    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(
        String(20), default=ReviewStatus.PUBLISHED, nullable=False
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    source: Mapped[str | None] = mapped_column(String(200))
    license: Mapped[str | None] = mapped_column(String(80))
    attribution: Mapped[str | None] = mapped_column(Text)

    # --- authoring ---------------------------------------------------------------------
    # ``blocks`` is the live, student-visible body. ``draft_blocks`` is the admin's working copy.
    # Separating them is what makes "edit a published lesson without breaking it" true rather than
    # aspirational: students keep reading ``blocks`` until the author presses Publish.
    draft_blocks: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    has_draft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(600))
    teacher_notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    topic: Mapped[Topic] = relationship()
    skill: Mapped[Skill | None] = relationship(back_populates="lessons")
    video: Mapped[Video | None] = relationship()
    resources: Mapped[list[Resource]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="Resource.position",
    )


class Video(Base, TimestampMixin):
    """Video metadata only — never the bytes.

    ``provider`` + ``external_id`` keep us portable across YouTube (unlisted), Cloudflare Stream,
    S3/R2 and Mux. ``storage.py`` turns these two fields into a playable URL, so switching provider
    is a config change and a backfill, not a schema migration.
    """

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="youtube", nullable=False)
    external_id: Mapped[str] = mapped_column(String(250), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(600))

    # [{"time": 0, "label": "Introduction"}, ...]
    chapters: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    # [{"lang": "en", "url": "...", "label": "English"}, ...]
    captions: Mapped[list[dict[str, Any]]] = mapped_column(default=list)

    license: Mapped[str | None] = mapped_column(String(80))
    attribution: Mapped[str | None] = mapped_column(Text)


class Resource(Base, TimestampMixin, TranslatableMixin):
    """Downloadable or linked material attached to a topic (worksheets, formula sheets, links)."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(String(40), default="link", nullable=False)
    url: Mapped[str] = mapped_column(String(800), nullable=False)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    # A worksheet usually belongs to one lesson rather than a whole topic. Both are nullable so a
    # resource can be attached at either level, or to neither while it sits in the library.
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    license: Mapped[str | None] = mapped_column(String(80))
    attribution: Mapped[str | None] = mapped_column(Text)

    lesson: Mapped[Lesson | None] = relationship(back_populates="resources")
