"""Website content management: page sections, settings, FAQs, announcements, testimonials, posts.

Every endpoint here writes to a *draft* field and publishes separately, except for the simple
list-type content (FAQ, testimonials, announcements) where a single ``is_published`` flag is both
sufficient and easier to reason about. The distinction is deliberate: a hero paragraph is edited
over several sittings and must not leak half-written; an FAQ answer is written in one go.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    build_page,
    get_or_404,
    next_position,
    paginate,
    record_audit,
    snapshot,
)
from app.core.text import unique_slug
from app.models import (
    Announcement,
    BlogPost,
    ContentCategory,
    FaqItem,
    ProductCategory,
    ReviewStatus,
    SiteSection,
    SiteSetting,
    Testimonial,
    TutoringProduct,
)

router = APIRouter(prefix="/cms", tags=["admin:cms"])


# --------------------------------------------------------------------------------------
# page sections
# --------------------------------------------------------------------------------------


class SectionIn(BaseModel):
    page: str = Field(min_length=1, max_length=60)
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    locale: str = Field(default="en", max_length=8)
    kind: str = Field(default="rich_text", max_length=40)
    content: dict[str, Any] = Field(default_factory=dict)


class SectionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = Field(default=None, max_length=40)
    content: dict[str, Any] | None = None


def _section_row(section: SiteSection) -> dict[str, Any]:
    return {
        "id": section.id,
        "page": section.page,
        "key": section.key,
        "locale": section.locale,
        "kind": section.kind,
        "label": section.label,
        "position": section.position,
        "status": section.status,
        "content": section.content or {},
        "published_content": section.published_content or {},
        "has_unpublished_changes": section.has_unpublished_changes,
        "published_at": section.published_at,
        "updated_at": section.updated_at,
    }


@router.get("/sections")
def list_sections(
    db: DbSession,
    admin: CurrentAdmin,
    page_key: Annotated[str | None, Query(alias="page", max_length=60)] = None,
    locale: Annotated[str | None, Query(max_length=8)] = None,
) -> list[dict[str, Any]]:
    query = select(SiteSection)
    if page_key:
        query = query.where(SiteSection.page == page_key)
    if locale:
        query = query.where(SiteSection.locale == locale)
    rows = db.scalars(
        query.order_by(SiteSection.page, SiteSection.position, SiteSection.id)
    )
    return [_section_row(row) for row in rows]


@router.get("/pages")
def list_pages(db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    """Which pages have editable sections, and how many are awaiting publication."""
    rows = list(db.scalars(select(SiteSection)))
    pages: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = pages.setdefault(
            row.page, {"page": row.page, "sections": 0, "unpublished": 0, "locales": set()}
        )
        entry["sections"] += 1
        entry["locales"].add(row.locale)
        if row.has_unpublished_changes:
            entry["unpublished"] += 1
    return [
        {**entry, "locales": sorted(entry["locales"])}
        for entry in sorted(pages.values(), key=lambda e: e["page"])
    ]


@router.post("/sections", status_code=status.HTTP_201_CREATED)
def create_section(payload: SectionIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    existing = db.scalar(
        select(SiteSection).where(
            SiteSection.page == payload.page,
            SiteSection.key == payload.key,
            SiteSection.locale == payload.locale,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"“{payload.key}” already exists on the {payload.page} page for this locale",
        )
    section = SiteSection(
        **payload.model_dump(),
        position=next_position(db, SiteSection, SiteSection.page == payload.page),
        status=ReviewStatus.DRAFT,
        updated_by_id=admin.id,
    )
    db.add(section)
    db.flush()
    record_audit(
        db, admin, "create", "site_section", section.id,
        f"Created “{section.label}” on the {section.page} page",
    )
    db.commit()
    db.refresh(section)
    return _section_row(section)


@router.patch("/sections/{section_id}")
def update_section(
    section_id: int, payload: SectionUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Save the working copy. The public site keeps rendering the published copy."""
    section = get_or_404(db, SiteSection, section_id, "Section")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(section, key, value)
    section.updated_by_id = admin.id
    record_audit(
        db, admin, "update", "site_section", section.id, f"Edited “{section.label}”"
    )
    db.commit()
    db.refresh(section)
    return _section_row(section)


@router.post("/sections/{section_id}/publish")
def publish_section(section_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    section = get_or_404(db, SiteSection, section_id, "Section")
    snapshot(
        db, "site_section", section.id,
        {"content": section.published_content or {}, "label": section.label},
        admin, "replaced on publish",
    )
    section.published_content = section.content or {}
    section.status = ReviewStatus.PUBLISHED
    section.published_at = dt.datetime.now(dt.UTC)
    record_audit(
        db, admin, "publish", "site_section", section.id,
        f"Published “{section.label}” on the {section.page} page",
    )
    db.commit()
    db.refresh(section)
    return _section_row(section)


@router.post("/sections/{section_id}/unpublish")
def unpublish_section(section_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Take a section off the site. The draft is preserved so it can be restored."""
    section = get_or_404(db, SiteSection, section_id, "Section")
    section.status = ReviewStatus.DRAFT
    section.published_content = {}
    record_audit(
        db, admin, "unpublish", "site_section", section.id, f"Unpublished “{section.label}”"
    )
    db.commit()
    db.refresh(section)
    return _section_row(section)


@router.post("/sections/{section_id}/discard")
def discard_section_draft(
    section_id: int, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    section = get_or_404(db, SiteSection, section_id, "Section")
    section.content = dict(section.published_content or {})
    db.commit()
    db.refresh(section)
    return _section_row(section)


@router.post("/sections/publish-all")
def publish_all_sections(
    db: DbSession,
    admin: CurrentAdmin,
    page_key: Annotated[str, Query(alias="page", max_length=60)],
) -> dict[str, Any]:
    """Publish every pending change on one page at once."""
    rows = list(db.scalars(select(SiteSection).where(SiteSection.page == page_key)))
    published = 0
    now = dt.datetime.now(dt.UTC)
    for section in rows:
        if not section.has_unpublished_changes:
            continue
        section.published_content = section.content or {}
        section.status = ReviewStatus.PUBLISHED
        section.published_at = now
        published += 1
    record_audit(
        db, admin, "publish", "site_section", None,
        f"Published {published} section(s) on the {page_key} page",
    )
    db.commit()
    return {"page": page_key, "published": published}


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(section_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    section = get_or_404(db, SiteSection, section_id, "Section")
    label = section.label
    db.delete(section)
    record_audit(db, admin, "delete", "site_section", section_id, f"Deleted “{label}”")
    db.commit()


# --------------------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------------------


class SettingIn(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    group: str = Field(default="general", max_length=60)
    value: dict[str, Any] = Field(default_factory=dict)
    value_type: str = Field(default="text", max_length=20)
    description: str | None = None


class SettingValue(BaseModel):
    value: dict[str, Any]


@router.get("/settings")
def list_settings(
    db: DbSession,
    admin: CurrentAdmin,
    group: Annotated[str | None, Query(max_length=60)] = None,
) -> list[dict[str, Any]]:
    query = select(SiteSetting)
    if group:
        query = query.where(SiteSetting.group == group)
    rows = db.scalars(query.order_by(SiteSetting.group, SiteSetting.position, SiteSetting.id))
    return [
        {
            "id": s.id,
            "key": s.key,
            "group": s.group,
            "label": s.label,
            "value": s.value or {},
            "value_type": s.value_type,
            "description": s.description,
            "position": s.position,
            "updated_at": s.updated_at,
        }
        for s in rows
    ]


@router.put("/settings/{key}")
def upsert_setting(
    key: str, payload: SettingValue, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Set a value, creating the setting if the key is new.

    Upsert rather than separate create/update because settings are addressed by a stable key that
    the frontend already knows; making the UI check for existence first would be pure ceremony.
    """
    setting = db.scalar(select(SiteSetting).where(SiteSetting.key == key))
    if setting is None:
        setting = SiteSetting(
            key=key,
            label=key.replace("_", " ").replace(".", " — ").title(),
            group="general",
            position=next_position(db, SiteSetting),
        )
        db.add(setting)
    before = setting.value
    setting.value = payload.value
    record_audit(
        db, admin, "update", "site_setting", setting.id or None,
        f"Updated setting “{key}”", {"from": before, "to": payload.value},
    )
    db.commit()
    db.refresh(setting)
    return {"id": setting.id, "key": setting.key, "value": setting.value}


@router.post("/settings", status_code=status.HTTP_201_CREATED)
def create_setting(payload: SettingIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    if db.scalar(select(SiteSetting).where(SiteSetting.key == payload.key)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That setting key already exists"
        )
    setting = SiteSetting(**payload.model_dump(), position=next_position(db, SiteSetting))
    db.add(setting)
    db.flush()
    record_audit(
        db, admin, "create", "site_setting", setting.id, f"Created setting “{setting.key}”"
    )
    db.commit()
    db.refresh(setting)
    return {"id": setting.id, "key": setting.key, "value": setting.value}


@router.delete("/settings/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(key: str, db: DbSession, admin: CurrentAdmin) -> None:
    setting = db.scalar(select(SiteSetting).where(SiteSetting.key == key))
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    db.delete(setting)
    record_audit(db, admin, "delete", "site_setting", None, f"Deleted setting “{key}”")
    db.commit()


# --------------------------------------------------------------------------------------
# FAQ
# --------------------------------------------------------------------------------------


class FaqIn(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    category: str = Field(default="general", max_length=60)
    locale: str = Field(default="en", max_length=8)
    is_published: bool = True


class FaqUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=60)
    locale: str | None = Field(default=None, max_length=8)
    is_published: bool | None = None


def _faq_row(item: FaqItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "question": item.question,
        "answer": item.answer,
        "category": item.category,
        "locale": item.locale,
        "position": item.position,
        "is_published": item.is_published,
    }


@router.get("/faqs")
def list_faqs(
    db: DbSession,
    admin: CurrentAdmin,
    category: Annotated[str | None, Query(max_length=60)] = None,
    locale: Annotated[str | None, Query(max_length=8)] = None,
) -> list[dict[str, Any]]:
    query = select(FaqItem)
    if category:
        query = query.where(FaqItem.category == category)
    if locale:
        query = query.where(FaqItem.locale == locale)
    return [
        _faq_row(row)
        for row in db.scalars(query.order_by(FaqItem.position, FaqItem.id))
    ]


@router.post("/faqs", status_code=status.HTTP_201_CREATED)
def create_faq(payload: FaqIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    item = FaqItem(**payload.model_dump(), position=next_position(db, FaqItem))
    db.add(item)
    db.flush()
    record_audit(db, admin, "create", "faq", item.id, f"Added FAQ “{item.question[:60]}”")
    db.commit()
    db.refresh(item)
    return _faq_row(item)


@router.patch("/faqs/{faq_id}")
def update_faq(
    faq_id: int, payload: FaqUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    item = get_or_404(db, FaqItem, faq_id, "FAQ")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    record_audit(db, admin, "update", "faq", item.id, f"Updated FAQ “{item.question[:60]}”")
    db.commit()
    db.refresh(item)
    return _faq_row(item)


@router.delete("/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faq(faq_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    item = get_or_404(db, FaqItem, faq_id, "FAQ")
    question = item.question
    db.delete(item)
    record_audit(db, admin, "delete", "faq", faq_id, f"Deleted FAQ “{question[:60]}”")
    db.commit()


@router.post("/faqs/reorder")
def reorder_faqs(
    payload: dict[str, list[int]], db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    return _reorder(db, FaqItem, payload.get("ids") or [], "FAQ")


# --------------------------------------------------------------------------------------
# announcements and banners
# --------------------------------------------------------------------------------------


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    body: str | None = None
    kind: str = Field(default="announcement", max_length=30)
    tone: str = Field(default="brand", max_length=20)
    link_url: str | None = Field(default=None, max_length=600)
    link_label: str | None = Field(default=None, max_length=120)
    image_url: str | None = Field(default=None, max_length=600)
    locale: str = Field(default="en", max_length=8)
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None
    is_published: bool = False


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    body: str | None = None
    kind: str | None = Field(default=None, max_length=30)
    tone: str | None = Field(default=None, max_length=20)
    link_url: str | None = Field(default=None, max_length=600)
    link_label: str | None = Field(default=None, max_length=120)
    image_url: str | None = Field(default=None, max_length=600)
    locale: str | None = Field(default=None, max_length=8)
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None
    is_published: bool | None = None


def _announcement_row(item: Announcement) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "kind": item.kind,
        "tone": item.tone,
        "link_url": item.link_url,
        "link_label": item.link_label,
        "image_url": item.image_url,
        "locale": item.locale,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "is_published": item.is_published,
        "is_live": item.is_live(dt.datetime.now(dt.UTC)),
        "position": item.position,
    }


@router.get("/announcements")
def list_announcements(
    db: DbSession,
    admin: CurrentAdmin,
    kind: Annotated[str | None, Query(max_length=30)] = None,
) -> list[dict[str, Any]]:
    query = select(Announcement)
    if kind:
        query = query.where(Announcement.kind == kind)
    return [
        _announcement_row(row)
        for row in db.scalars(
            query.order_by(Announcement.position, Announcement.created_at.desc())
        )
    ]


@router.post("/announcements", status_code=status.HTTP_201_CREATED)
def create_announcement(
    payload: AnnouncementIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The end time must be after the start time",
        )
    item = Announcement(**payload.model_dump(), position=next_position(db, Announcement))
    db.add(item)
    db.flush()
    record_audit(
        db, admin, "create", "announcement", item.id, f"Created {item.kind} “{item.title}”"
    )
    db.commit()
    db.refresh(item)
    return _announcement_row(item)


@router.patch("/announcements/{announcement_id}")
def update_announcement(
    announcement_id: int, payload: AnnouncementUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    item = get_or_404(db, Announcement, announcement_id, "Announcement")
    fields = payload.model_dump(exclude_unset=True)
    starts = fields.get("starts_at", item.starts_at)
    ends = fields.get("ends_at", item.ends_at)
    if starts and ends and ends <= starts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The end time must be after the start time",
        )
    for key, value in fields.items():
        setattr(item, key, value)
    record_audit(
        db, admin, "update", "announcement", item.id, f"Updated “{item.title}”"
    )
    db.commit()
    db.refresh(item)
    return _announcement_row(item)


@router.delete("/announcements/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(
    announcement_id: int, db: DbSession, admin: CurrentAdmin
) -> None:
    item = get_or_404(db, Announcement, announcement_id, "Announcement")
    title = item.title
    db.delete(item)
    record_audit(
        db, admin, "delete", "announcement", announcement_id, f"Deleted “{title}”"
    )
    db.commit()


# --------------------------------------------------------------------------------------
# testimonials
# --------------------------------------------------------------------------------------


class TestimonialIn(BaseModel):
    author_name: str = Field(min_length=1, max_length=150)
    author_role: str = Field(default="Parent", max_length=120)
    quote: str = Field(min_length=1)
    rating: int = Field(default=5, ge=1, le=5)
    subject_slug: str | None = Field(default=None, max_length=60)
    grade: int | None = Field(default=None, ge=1, le=12)
    avatar_url: str | None = Field(default=None, max_length=600)
    is_published: bool = True
    is_featured: bool = False


class TestimonialUpdate(BaseModel):
    author_name: str | None = Field(default=None, min_length=1, max_length=150)
    author_role: str | None = Field(default=None, max_length=120)
    quote: str | None = Field(default=None, min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)
    subject_slug: str | None = Field(default=None, max_length=60)
    grade: int | None = Field(default=None, ge=1, le=12)
    avatar_url: str | None = Field(default=None, max_length=600)
    is_published: bool | None = None
    is_featured: bool | None = None


def _testimonial_row(item: Testimonial) -> dict[str, Any]:
    return {
        "id": item.id,
        "author_name": item.author_name,
        "author_role": item.author_role,
        "quote": item.quote,
        "rating": item.rating,
        "subject_slug": item.subject_slug,
        "grade": item.grade,
        "avatar_url": item.avatar_url,
        "is_published": item.is_published,
        "is_featured": item.is_featured,
        "position": item.position,
    }


@router.get("/testimonials")
def list_testimonials(db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    return [
        _testimonial_row(row)
        for row in db.scalars(select(Testimonial).order_by(Testimonial.position, Testimonial.id))
    ]


@router.post("/testimonials", status_code=status.HTTP_201_CREATED)
def create_testimonial(
    payload: TestimonialIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    item = Testimonial(**payload.model_dump(), position=next_position(db, Testimonial))
    db.add(item)
    db.flush()
    record_audit(
        db, admin, "create", "testimonial", item.id,
        f"Added testimonial from {item.author_name}",
    )
    db.commit()
    db.refresh(item)
    return _testimonial_row(item)


@router.patch("/testimonials/{testimonial_id}")
def update_testimonial(
    testimonial_id: int, payload: TestimonialUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    item = get_or_404(db, Testimonial, testimonial_id, "Testimonial")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    record_audit(
        db, admin, "update", "testimonial", item.id,
        f"Updated testimonial from {item.author_name}",
    )
    db.commit()
    db.refresh(item)
    return _testimonial_row(item)


@router.delete("/testimonials/{testimonial_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_testimonial(
    testimonial_id: int, db: DbSession, admin: CurrentAdmin
) -> None:
    item = get_or_404(db, Testimonial, testimonial_id, "Testimonial")
    author = item.author_name
    db.delete(item)
    record_audit(
        db, admin, "delete", "testimonial", testimonial_id,
        f"Deleted testimonial from {author}",
    )
    db.commit()


@router.post("/testimonials/reorder")
def reorder_testimonials(
    payload: dict[str, list[int]], db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    return _reorder(db, Testimonial, payload.get("ids") or [], "testimonial")


# --------------------------------------------------------------------------------------
# blog posts
# --------------------------------------------------------------------------------------


class PostIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    excerpt: str = Field(min_length=1)
    body_markdown: str = Field(min_length=1)
    slug: str | None = Field(default=None, max_length=180)
    category: str = Field(default="learning", max_length=60)
    tags: list[str] = Field(default_factory=list)
    cover_image_url: str | None = Field(default=None, max_length=600)
    reading_minutes: int = Field(default=5, ge=1, le=120)
    author_name: str = Field(default="HieuTrienEducation", max_length=150)
    status: ReviewStatus = ReviewStatus.DRAFT


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    excerpt: str | None = Field(default=None, min_length=1)
    body_markdown: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, max_length=180)
    category: str | None = Field(default=None, max_length=60)
    tags: list[str] | None = None
    cover_image_url: str | None = Field(default=None, max_length=600)
    reading_minutes: int | None = Field(default=None, ge=1, le=120)
    author_name: str | None = Field(default=None, max_length=150)
    status: ReviewStatus | None = None


def _post_row(post: BlogPost) -> dict[str, Any]:
    return {
        "id": post.id,
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "category": post.category,
        "tags": post.tags or [],
        "cover_image_url": post.cover_image_url,
        "reading_minutes": post.reading_minutes,
        "author_name": post.author_name,
        "status": post.status,
        "published_at": post.published_at,
        "updated_at": post.updated_at,
    }


@router.get("/posts")
def list_posts(
    db: DbSession,
    admin: CurrentAdmin,
    post_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(BlogPost)
    if post_status:
        query = query.where(BlogPost.status == post_status)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(BlogPost.title.ilike(pattern), BlogPost.excerpt.ilike(pattern)))
    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(BlogPost.created_at.desc())
    rows, total = paginate(db, query, params)
    return build_page([_post_row(row) for row in rows], total, params)


@router.get("/posts/{post_id}")
def get_post(post_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    post = get_or_404(db, BlogPost, post_id, "Post")
    return {**_post_row(post), "body_markdown": post.body_markdown}


@router.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: PostIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    post = BlogPost(
        **payload.model_dump(exclude={"slug"}),
        slug=unique_slug(
            payload.slug or payload.title,
            lambda candidate: db.scalar(select(BlogPost.id).where(BlogPost.slug == candidate))
            is not None,
            max_length=180,
        ),
        author_id=admin.id,
        published_at=(
            dt.datetime.now(dt.UTC) if payload.status == ReviewStatus.PUBLISHED else None
        ),
    )
    db.add(post)
    db.flush()
    record_audit(db, admin, "create", "post", post.id, f"Created post “{post.title}”")
    db.commit()
    db.refresh(post)
    return _post_row(post)


@router.patch("/posts/{post_id}")
def update_post(
    post_id: int, payload: PostUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    post = get_or_404(db, BlogPost, post_id, "Post")
    fields = payload.model_dump(exclude_unset=True, exclude={"slug"})
    for key, value in fields.items():
        setattr(post, key, value)
    if payload.slug:
        post.slug = unique_slug(
            payload.slug,
            lambda candidate: db.scalar(
                select(BlogPost.id).where(BlogPost.slug == candidate, BlogPost.id != post.id)
            )
            is not None,
            max_length=180,
        )
    if payload.status == ReviewStatus.PUBLISHED and post.published_at is None:
        post.published_at = dt.datetime.now(dt.UTC)
    record_audit(db, admin, "update", "post", post.id, f"Updated post “{post.title}”")
    db.commit()
    db.refresh(post)
    return _post_row(post)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    post = get_or_404(db, BlogPost, post_id, "Post")
    title = post.title
    db.delete(post)
    record_audit(db, admin, "delete", "post", post_id, f"Deleted post “{title}”")
    db.commit()


# --------------------------------------------------------------------------------------
# tutoring programmes (the sellable "courses" with a price and a format)
# --------------------------------------------------------------------------------------

programs_router = APIRouter(prefix="/programs", tags=["admin:programs"])


class ProgramIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tagline: str | None = Field(default=None, max_length=300)
    description: str | None = None
    format: str = "group"
    delivery_mode: str = "online"
    subject_slug: str | None = Field(default=None, max_length=60)
    grade_min: int = Field(default=6, ge=1, le=12)
    grade_max: int = Field(default=9, ge=1, le=12)
    price_vnd: int = Field(default=0, ge=0)
    price_unit: str = Field(default="session", max_length=20)
    sessions_included: int = Field(default=1, ge=1)
    session_minutes: int = Field(default=90, ge=15)
    capacity: int = Field(default=1, ge=1)
    features: list[str] = Field(default_factory=list)
    thumbnail_url: str | None = Field(default=None, max_length=600)
    teacher_id: int | None = None
    course_id: int | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    status: ReviewStatus = ReviewStatus.DRAFT
    is_active: bool = True
    is_featured: bool = False
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None
    category_ids: list[int] = Field(default_factory=list)


class ProgramUpdate(ProgramIn):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_ids: list[int] | None = None


def _program_row(db, product: TutoringProduct) -> dict[str, Any]:
    categories = db.execute(
        select(ContentCategory)
        .join(ProductCategory, ProductCategory.category_id == ContentCategory.id)
        .where(ProductCategory.product_id == product.id)
    ).scalars()
    return {
        "id": product.id,
        "slug": product.slug,
        "name": product.name,
        "tagline": product.tagline,
        "description": product.description,
        "format": product.format,
        "delivery_mode": product.delivery_mode,
        "subject_slug": product.subject_slug,
        "grade_min": product.grade_min,
        "grade_max": product.grade_max,
        "price_vnd": product.price_vnd,
        "price_unit": product.price_unit,
        "sessions_included": product.sessions_included,
        "session_minutes": product.session_minutes,
        "capacity": product.capacity,
        "features": product.features or [],
        "thumbnail_url": product.thumbnail_url,
        "teacher_id": product.teacher_id,
        "course_id": product.course_id,
        "start_date": product.start_date,
        "end_date": product.end_date,
        "status": product.status,
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "position": product.position,
        "seo_title": product.seo_title,
        "seo_description": product.seo_description,
        "categories": [
            {"id": c.id, "name": c.name, "slug": c.slug} for c in categories
        ],
    }


def _set_program_categories(db, product: TutoringProduct, category_ids: list[int]) -> None:
    valid = set(
        db.scalars(select(ContentCategory.id).where(ContentCategory.id.in_(category_ids))).all()
    )
    unknown = set(category_ids) - valid
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown category ids: {sorted(unknown)}",
        )
    db.execute(
        ProductCategory.__table__.delete().where(ProductCategory.product_id == product.id)
    )
    for category_id in dict.fromkeys(category_ids):
        db.add(ProductCategory(product_id=product.id, category_id=category_id))


@programs_router.get("")
def list_programs(
    db: DbSession,
    admin: CurrentAdmin,
    program_format: Annotated[str | None, Query(alias="format", max_length=30)] = None,
    program_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(TutoringProduct)
    if program_format:
        query = query.where(TutoringProduct.format == program_format)
    if program_status:
        query = query.where(TutoringProduct.status == program_status)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(TutoringProduct.name.ilike(pattern), TutoringProduct.tagline.ilike(pattern))
        )
    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(TutoringProduct.position, TutoringProduct.id)
    rows, total = paginate(db, query, params)
    return build_page([_program_row(db, row) for row in rows], total, params)


@programs_router.post("", status_code=status.HTTP_201_CREATED)
def create_program(payload: ProgramIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    if payload.grade_max < payload.grade_min:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The highest grade cannot be below the lowest grade",
        )
    product = TutoringProduct(
        **payload.model_dump(exclude={"category_ids"}),
        slug=unique_slug(
            payload.name,
            lambda candidate: db.scalar(
                select(TutoringProduct.id).where(TutoringProduct.slug == candidate)
            )
            is not None,
            max_length=120,
        ),
        position=next_position(db, TutoringProduct),
    )
    db.add(product)
    db.flush()
    if payload.category_ids:
        _set_program_categories(db, product, payload.category_ids)
    record_audit(
        db, admin, "create", "program", product.id, f"Created programme “{product.name}”"
    )
    db.commit()
    db.refresh(product)
    return _program_row(db, product)


@programs_router.get("/{program_id}")
def get_program(program_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    product = get_or_404(db, TutoringProduct, program_id, "Programme")
    return _program_row(db, product)


@programs_router.patch("/{program_id}")
def update_program(
    program_id: int, payload: ProgramUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    product = get_or_404(db, TutoringProduct, program_id, "Programme")
    fields = payload.model_dump(exclude_unset=True, exclude={"category_ids"})
    grade_min = fields.get("grade_min", product.grade_min)
    grade_max = fields.get("grade_max", product.grade_max)
    if grade_max < grade_min:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The highest grade cannot be below the lowest grade",
        )
    for key, value in fields.items():
        setattr(product, key, value)
    if payload.category_ids is not None:
        _set_program_categories(db, product, payload.category_ids)
    record_audit(
        db, admin, "update", "program", product.id, f"Updated programme “{product.name}”"
    )
    db.commit()
    db.refresh(product)
    return _program_row(db, product)


@programs_router.post("/{program_id}/status")
def set_program_status(
    program_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    value: Annotated[ReviewStatus, Query(alias="status")],
) -> dict[str, Any]:
    product = get_or_404(db, TutoringProduct, program_id, "Programme")
    product.status = value
    # ``is_active`` is what the public listing filters on; keep it consistent with the lifecycle.
    product.is_active = value == ReviewStatus.PUBLISHED
    record_audit(
        db, admin, str(value), "program", product.id,
        f"Set programme “{product.name}” to {value}",
    )
    db.commit()
    db.refresh(product)
    return _program_row(db, product)


@programs_router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(program_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    product = get_or_404(db, TutoringProduct, program_id, "Programme")
    name = product.name
    db.delete(product)
    record_audit(db, admin, "delete", "program", program_id, f"Deleted programme “{name}”")
    db.commit()


# --------------------------------------------------------------------------------------
# shared
# --------------------------------------------------------------------------------------


def _reorder(db, model, ids: list[int], label: str) -> dict[str, Any]:
    rows = {row.id: row for row in db.scalars(select(model).where(model.id.in_(ids)))}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown {label} ids: {missing}"
        )
    for index, row_id in enumerate(ids, start=1):
        rows[row_id].position = index
    db.commit()
    return {"reordered": len(ids)}
