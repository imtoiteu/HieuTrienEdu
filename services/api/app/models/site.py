"""Marketing-site content managed from the admin dashboard.

These rows exist so the public website is not a wall of hard-coded strings that a developer must
redeploy to change. Testimonials, blog posts and contact leads are all admin-editable.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TranslatableMixin
from app.models.enums import LeadStatus, ReviewStatus

if TYPE_CHECKING:
    from app.models.ops import LeadNote


class Testimonial(Base, TimestampMixin, TranslatableMixin):
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


class BlogPost(Base, TimestampMixin, TranslatableMixin):
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
    """A consultation enquiry from any public form — contact, free assessment, "đăng ký tư vấn".

    This is a worked pipeline, not an inbox. Everything after ``source_page`` exists so that an
    enquiry cannot be silently lost: it has an owner, a stage, a follow-up date, a note history
    (see ``LeadNote``) and a record of what it was converted into.
    """

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

    # --- who the enquiry is actually about -------------------------------------------
    # The person filling the form is often a parent, so the student's details are separate.
    student_name: Mapped[str | None] = mapped_column(String(200))
    parent_name: Mapped[str | None] = mapped_column(String(200))
    parent_phone: Mapped[str | None] = mapped_column(String(40))
    school: Mapped[str | None] = mapped_column(String(200))
    preferred_format: Mapped[str | None] = mapped_column(String(30))
    preferred_delivery: Mapped[str | None] = mapped_column(String(30))
    preferred_schedule: Mapped[str | None] = mapped_column(Text)
    interested_course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL")
    )
    interested_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("tutoring_products.id", ondelete="SET NULL")
    )

    # --- pipeline ---------------------------------------------------------------------
    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NEW, nullable=False)
    handled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    admin_note: Mapped[str | None] = mapped_column(Text)
    consultation_result: Mapped[str | None] = mapped_column(Text)
    last_contacted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    converted_student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL")
    )
    converted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[list[LeadNote]] = relationship(
        cascade="all, delete-orphan",
        order_by="LeadNote.created_at.desc()",
        primaryjoin="ContactLead.id == LeadNote.contact_lead_id",
    )
