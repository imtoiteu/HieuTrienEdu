"""Marketing-site content managed from the admin dashboard.

These rows exist so the public website is not a wall of hard-coded strings that a developer must
redeploy to change. Testimonials, blog posts and contact leads are all admin-editable.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import LeadStatus, ReviewStatus


class Testimonial(Base, TimestampMixin):
    __tablename__ = "testimonials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_name: Mapped[str] = mapped_column(String(150), nullable=False)
    author_role: Mapped[str] = mapped_column(String(120), default="Parent", nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    subject_slug: Mapped[str | None] = mapped_column(String(60))
    grade: Mapped[int | None] = mapped_column(Integer)
    avatar_url: Mapped[str | None] = mapped_column(String(600))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class BlogPost(Base, TimestampMixin):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="learning", nullable=False)
    tags: Mapped[list[str]] = mapped_column(default=list)
    cover_image_url: Mapped[str | None] = mapped_column(String(600))
    reading_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_name: Mapped[str] = mapped_column(String(150), default="HieuTrienEducation",
                                             nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ReviewStatus.PUBLISHED, nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ContactLead(Base, TimestampMixin):
    """Submissions from the contact / free-assessment forms."""

    __tablename__ = "contact_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    subject_slug: Mapped[str | None] = mapped_column(String(60))
    grade: Mapped[int | None] = mapped_column(Integer)
    interest: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    source_page: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NEW, nullable=False)
    handled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    admin_note: Mapped[str | None] = mapped_column(Text)
