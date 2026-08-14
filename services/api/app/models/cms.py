"""Admin-managed website content: taxonomy, page sections, settings, media and revisions.

Everything in this module exists to answer one question with "yes": *can the centre change this
without a developer?* Categories, homepage copy, contact details, FAQs, banners and uploaded files
are all rows here rather than constants in the frontend bundle.
"""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TranslatableMixin
from app.models.enums import CategoryKind, MediaKind, ReviewStatus


class ContentCategory(Base, TimestampMixin, TranslatableMixin):
    """An admin-defined grouping — "Mathematics", "Grade 8", "Exam preparation".

    Self-referencing so the centre can nest ("Exam preparation" → "Grade 10 entrance") without a
    second table. ``kind`` is advisory: it drives which admin filter the category shows up under,
    and deliberately does *not* constrain what a category may be attached to.

    Translatable because these names are public: they label courses, drive the site navigation and
    are what a visitor filters by. They were single-valued at first, and the seed happened to write
    Vietnamese into the English column — which read correctly on ``/vi`` and put Vietnamese
    category names on the English site.
    """

    __tablename__ = "content_categories"
    __table_args__ = (Index("ix_content_categories_kind_position", "kind", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(600))
    icon: Mapped[str | None] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(20))

    kind: Mapped[str] = mapped_column(String(20), default=CategoryKind.TOPIC, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_categories.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_visible_in_nav: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(Text)

    parent: Mapped[ContentCategory | None] = relationship(
        remote_side="ContentCategory.id", back_populates="children"
    )
    children: Mapped[list[ContentCategory]] = relationship(
        back_populates="parent", order_by="ContentCategory.position"
    )


class CourseCategory(Base):
    """Join row: a curriculum course belongs to any number of categories."""

    __tablename__ = "course_categories"
    __table_args__ = (UniqueConstraint("course_id", "category_id", name="course_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("content_categories.id", ondelete="CASCADE"), nullable=False
    )


class ProductCategory(Base):
    """Join row: a sellable tutoring programme belongs to any number of categories."""

    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("product_id", "category_id", name="product_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("tutoring_products.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("content_categories.id", ondelete="CASCADE"), nullable=False
    )


class SiteSetting(Base, TimestampMixin, TranslatableMixin):
    """Single-value site configuration: address, phone, email, social links, footer text.

    Key/value with a JSON payload rather than a wide singleton row, because the set of things a
    centre wants to put on its footer grows continuously and each addition would otherwise be a
    migration. ``group`` only exists so the admin screen can render sensible sections.
    """

    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    group: Mapped[str] = mapped_column(String(60), default="general", nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(default=dict)
    value_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SiteSection(Base, TimestampMixin):
    """One editable block of a public page — the hero, a feature strip, a CTA band.

    Draft and published copy live in the same row (``body`` vs ``published_body``) so that editing
    a live page cannot accidentally push half-finished copy to visitors: the public API only ever
    reads the ``published_*`` columns, and "Publish" is what copies one into the other.
    """

    __tablename__ = "site_sections"
    __table_args__ = (
        UniqueConstraint("page", "key", "locale", name="page_key_locale"),
        Index("ix_site_sections_page_position", "page", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page: Mapped[str] = mapped_column(String(60), nullable=False)  # home | about | contact | ...
    key: Mapped[str] = mapped_column(String(80), nullable=False)  # hero | mission | cta | ...
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)

    kind: Mapped[str] = mapped_column(String(40), default="rich_text", nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ReviewStatus.DRAFT, nullable=False)

    # Working copy — what the admin is editing right now.
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Live copy — what the public site renders. Only "Publish" writes this.
    published_content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    @property
    def has_unpublished_changes(self) -> bool:
        return self.content != self.published_content


class FaqItem(Base, TimestampMixin):
    __tablename__ = "faq_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="general", nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Announcement(Base, TimestampMixin):
    """Banners, promotions and notices shown on the public site.

    ``starts_at``/``ends_at`` mean a promotion can be scheduled and then expire on its own, which
    is the difference between a CMS and a to-do list for the person who has to remember to take
    the Tết banner down.
    """

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), default="announcement", nullable=False)
    tone: Mapped[str] = mapped_column(String(20), default="brand", nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(600))
    link_label: Mapped[str | None] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(String(600))
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)

    starts_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def is_live(self, now: dt.datetime) -> bool:
        if not self.is_published:
            return False
        if self.starts_at is not None and now < self.starts_at:
            return False
        if self.ends_at is not None and now > self.ends_at:
            return False
        return True


class MediaAsset(Base, TimestampMixin):
    """A file uploaded through the admin media library.

    The bytes live on disk (or object storage); this row is the catalogue entry that makes a file
    findable and reusable across lessons, courses and pages. ``checksum`` is what stops the same
    worksheet being uploaded eight times under eight names.
    """

    __tablename__ = "media_assets"
    __table_args__ = (Index("ix_media_assets_kind_created", "kind", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    original_name: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default=MediaKind.IMAGE, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    url: Mapped[str] = mapped_column(String(800), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)

    title: Mapped[str | None] = mapped_column(String(250))
    alt_text: Mapped[str | None] = mapped_column(String(400))
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(default=list)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ContentRevision(Base, TimestampMixin):
    """Point-in-time snapshot of an editable record, written before every destructive change.

    Generic ``(entity_type, entity_id)`` rather than a revision table per model: the snapshot is
    an opaque JSON blob that only ever needs to be shown to a human or restored wholesale, so the
    referential integrity a real foreign key would buy has nothing to protect.
    """

    __tablename__ = "content_revisions"
    __table_args__ = (
        Index("ix_content_revisions_entity", "entity_type", "entity_id", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(default=dict)
    note: Mapped[str | None] = mapped_column(String(300))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
