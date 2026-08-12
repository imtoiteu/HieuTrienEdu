"""Public marketing-site content: testimonials, blog posts and contact/assessment leads."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select

from app.core.deps import DbSession, OptionalUser
from app.models import (
    BlogPost,
    ContactLead,
    Course,
    LeadStatus,
    Question,
    ReviewStatus,
    Skill,
    Subject,
    TeacherProfile,
    Testimonial,
    User,
)

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
    """Receive a contact / free-assessment enquiry from the public site."""
    lead = ContactLead(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        phone=payload.phone,
        subject_slug=payload.subject_slug,
        grade=payload.grade,
        interest=payload.interest,
        message=payload.message,
        source_page=payload.source_page,
        status=LeadStatus.NEW,
        handled_by_id=None,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return ContactLeadAck(
        id=lead.id,
        message=(
            "Thank you — we have received your message and will be in touch within one "
            "working day."
        ),
    )
