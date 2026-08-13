"""Public marketing-site content: testimonials, blog posts and contact/assessment leads."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select

from app.core.deps import DbSession, OptionalUser
from app.models import (
    Announcement,
    BlogPost,
    ContactLead,
    ContentCategory,
    Course,
    FaqItem,
    LeadStatus,
    NotificationKind,
    Question,
    ReviewStatus,
    SiteSection,
    SiteSetting,
    Skill,
    Subject,
    TeacherProfile,
    Testimonial,
    User,
)
from app.services.notifications import notify_admins

router = APIRouter(prefix="/site", tags=["site"])


class TestimonialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_name: str
    author_role: str
    quote: str
    rating: int
    subject_slug: str | None = None
    grade: int | None = None
    avatar_url: str | None = None
    is_featured: bool = False


class BlogPostSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    excerpt: str
    category: str
    tags: list[str] = Field(default_factory=list)
    cover_image_url: str | None = None
    reading_minutes: int
    author_name: str
    published_at: dt.datetime | None = None


class BlogPostDetail(BlogPostSummary):
    body_markdown: str


class ContactLeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    subject_slug: str | None = Field(default=None, max_length=60)
    grade: int | None = Field(default=None, ge=1, le=12)
    interest: str = Field(default="general", max_length=40)
    message: str | None = Field(default=None, max_length=4000)
    source_page: str | None = Field(default=None, max_length=160)

    # Optional richer detail, supplied by the consultation and enrolment forms. All optional so
    # the plain "contact us" box keeps working with three fields.
    student_name: str | None = Field(default=None, max_length=200)
    parent_name: str | None = Field(default=None, max_length=200)
    parent_phone: str | None = Field(default=None, max_length=40)
    school: str | None = Field(default=None, max_length=200)
    preferred_format: str | None = Field(default=None, max_length=30)
    preferred_delivery: str | None = Field(default=None, max_length=30)
    preferred_schedule: str | None = Field(default=None, max_length=1000)
    interested_course_id: int | None = None
    interested_product_id: int | None = None


class ContactLeadAck(BaseModel):
    id: int
    received: bool = True
    message: str


class SiteStats(BaseModel):
    """Headline numbers for the marketing site.

    These are computed from real database content rather than hard-coded, so the site can never
    advertise figures the platform cannot back up.
    """

    subjects: int
    courses: int
    skills: int
    questions: int
    teachers: int
    grade_range: str


@router.get("/testimonials", response_model=list[TestimonialRead])
def list_testimonials(
    db: DbSession,
    featured: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> list[TestimonialRead]:
    query = select(Testimonial).where(Testimonial.is_published.is_(True))
    if featured is not None:
        query = query.where(Testimonial.is_featured.is_(featured))
    rows = db.scalars(query.order_by(Testimonial.position, Testimonial.id).limit(limit))
    return [TestimonialRead.model_validate(t) for t in rows]


@router.get("/posts", response_model=list[BlogPostSummary])
def list_posts(
    db: DbSession,
    category: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[BlogPostSummary]:
    query = select(BlogPost).where(BlogPost.status == ReviewStatus.PUBLISHED)
    if category:
        query = query.where(BlogPost.category == category)
    rows = db.scalars(
        query.order_by(BlogPost.published_at.desc(), BlogPost.id.desc()).limit(limit)
    )
    return [BlogPostSummary.model_validate(p) for p in rows]


@router.get("/posts/{slug}", response_model=BlogPostDetail)
def get_post(slug: str, db: DbSession) -> BlogPostDetail:
    post = db.scalar(
        select(BlogPost).where(
            BlogPost.slug == slug, BlogPost.status == ReviewStatus.PUBLISHED
        )
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return BlogPostDetail.model_validate(post)


@router.get("/stats", response_model=SiteStats)
def site_stats(db: DbSession) -> SiteStats:
    def count(model, *conditions) -> int:
        query = select(func.count()).select_from(model)
        if conditions:
            query = query.where(*conditions)
        return db.scalar(query) or 0

    grades = db.execute(select(func.min(Course.grade), func.max(Course.grade))).one()
    grade_range = f"{grades[0]}-{grades[1]}" if grades[0] is not None else "6-9"

    # Explicit join — filtering TeacherProfile on a User column without one would produce a
    # cross join and badly inflate the count.
    active_teachers = db.scalar(
        select(func.count())
        .select_from(TeacherProfile)
        .join(User, TeacherProfile.user_id == User.id)
        .where(User.is_active.is_(True))
    ) or 0

    return SiteStats(
        subjects=count(Subject),
        courses=count(Course, Course.is_published.is_(True)),
        skills=count(Skill),
        questions=count(Question, Question.status == ReviewStatus.PUBLISHED),
        teachers=active_teachers,
        grade_range=grade_range,
    )


@router.post("/contact", response_model=ContactLeadAck, status_code=status.HTTP_201_CREATED)
def submit_contact(
    payload: ContactLeadCreate, db: DbSession, user: OptionalUser = None
) -> ContactLeadAck:
    """Receive a contact / consultation enquiry from the public site.

    The submission is a database row *and* an admin notification. Before, an enquiry landed
    silently in a table nobody was watching; raising a notification is what makes "the request
    must not disappear" true rather than a matter of someone remembering to check.
    """
    lead = ContactLead(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        phone=payload.phone,
        subject_slug=payload.subject_slug,
        grade=payload.grade,
        interest=payload.interest,
        message=payload.message,
        source_page=payload.source_page,
        student_name=payload.student_name,
        parent_name=payload.parent_name,
        parent_phone=payload.parent_phone,
        school=payload.school,
        preferred_format=payload.preferred_format,
        preferred_delivery=payload.preferred_delivery,
        preferred_schedule=payload.preferred_schedule,
        interested_course_id=payload.interested_course_id,
        interested_product_id=payload.interested_product_id,
        status=LeadStatus.NEW,
        handled_by_id=None,
    )
    db.add(lead)
    db.flush()

    notify_admins(
        db,
        NotificationKind.LEAD_CREATED,
        f"New consultation request from {lead.name}",
        body=(lead.message or "")[:500] or f"Interest: {lead.interest}",
        link_url=f"/admin/consultations/contact/{lead.id}",
        entity_type="lead:contact",
        entity_id=lead.id,
    )
    db.commit()
    db.refresh(lead)
    return ContactLeadAck(
        id=lead.id,
        message=(
            "Thank you — we have received your message and will be in touch within one "
            "working day."
        ),
    )


# --------------------------------------------------------------------------------------
# admin-managed website content
# --------------------------------------------------------------------------------------
#
# Everything below reads only *published* rows. The admin CMS writes to a draft field and
# publishes separately, so an unfinished edit can never be served here — that separation is the
# whole reason the public site can be edited live without a staging environment.


@router.get("/settings")
def public_settings(db: DbSession) -> dict[str, Any]:
    """Contact details, social links and footer copy, keyed for direct lookup."""
    rows = db.scalars(select(SiteSetting).order_by(SiteSetting.group, SiteSetting.position))
    return {row.key: row.value for row in rows}


@router.get("/sections")
def public_sections(
    db: DbSession,
    page: Annotated[str | None, Query(max_length=60)] = None,
    locale: Annotated[str, Query(max_length=8)] = "en",
) -> dict[str, Any]:
    """Published page sections, keyed by section key so a template can look one up directly.

    Falls back to the English row when a locale has no translation: a missing Vietnamese
    translation should show the English copy, not an empty page.
    """
    query = select(SiteSection).where(SiteSection.status == ReviewStatus.PUBLISHED)
    if page:
        query = query.where(SiteSection.page == page)
    rows = list(db.scalars(query.order_by(SiteSection.position, SiteSection.id)))

    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.published_content:
            continue
        existing = by_key.get(row.key)
        # Prefer the requested locale; otherwise keep whatever was found first.
        if existing is None or row.locale == locale:
            by_key[row.key] = {
                "key": row.key,
                "page": row.page,
                "kind": row.kind,
                "locale": row.locale,
                "position": row.position,
                **(row.published_content or {}),
            }
    return by_key


@router.get("/faqs")
def public_faqs(
    db: DbSession,
    category: Annotated[str | None, Query(max_length=60)] = None,
    locale: Annotated[str | None, Query(max_length=8)] = None,
) -> list[dict[str, Any]]:
    query = select(FaqItem).where(FaqItem.is_published.is_(True))
    if category:
        query = query.where(FaqItem.category == category)
    if locale:
        query = query.where(FaqItem.locale == locale)
    return [
        {
            "id": item.id,
            "question": item.question,
            "answer": item.answer,
            "category": item.category,
        }
        for item in db.scalars(query.order_by(FaqItem.position, FaqItem.id))
    ]


@router.get("/announcements")
def public_announcements(
    db: DbSession,
    kind: Annotated[str | None, Query(max_length=30)] = None,
) -> list[dict[str, Any]]:
    """Banners and notices that are published *and* currently within their date window."""
    now = dt.datetime.now(dt.UTC)
    query = select(Announcement).where(Announcement.is_published.is_(True))
    if kind:
        query = query.where(Announcement.kind == kind)
    rows = db.scalars(query.order_by(Announcement.position, Announcement.created_at.desc()))
    return [
        {
            "id": item.id,
            "title": item.title,
            "body": item.body,
            "kind": item.kind,
            "tone": item.tone,
            "link_url": item.link_url,
            "link_label": item.link_label,
            "image_url": item.image_url,
        }
        for item in rows
        if item.is_live(now)
    ]


@router.get("/categories")
def public_categories(
    db: DbSession,
    kind: Annotated[str | None, Query(max_length=20)] = None,
    nav_only: Annotated[bool, Query()] = False,
) -> list[dict[str, Any]]:
    """The admin-defined taxonomy, as a nested tree of published categories."""
    query = select(ContentCategory).where(ContentCategory.is_published.is_(True))
    if kind:
        query = query.where(ContentCategory.kind == kind)
    if nav_only:
        query = query.where(ContentCategory.is_visible_in_nav.is_(True))
    rows = list(db.scalars(query.order_by(ContentCategory.position, ContentCategory.id)))

    by_parent: dict[int | None, list[ContentCategory]] = {}
    ids = {row.id for row in rows}
    for row in rows:
        # A published child whose parent is unpublished is promoted to the top level rather than
        # being hidden — otherwise unpublishing a container silently removes its whole subtree.
        parent = row.parent_id if row.parent_id in ids else None
        by_parent.setdefault(parent, []).append(row)

    def build(parent_id: int | None) -> list[dict[str, Any]]:
        return [
            {
                "id": row.id,
                "slug": row.slug,
                "name": row.name,
                "description": row.description,
                "image_url": row.image_url,
                "icon": row.icon,
                "color": row.color,
                "kind": row.kind,
                "seo_title": row.seo_title,
                "seo_description": row.seo_description,
                "children": build(row.id),
            }
            for row in by_parent.get(parent_id, [])
        ]

    return build(None)
