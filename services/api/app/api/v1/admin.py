"""Admin dashboard: people, classes, enrollments, payments, leads and site content."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, require_roles
from app.core.security import hash_password
from app.models import (
    BlogPost,
    ClassEnrollment,
    ClassGroup,
    ContactLead,
    Course,
    LeadStatus,
    LiveSession,
    Order,
    OrderStatus,
    ParentProfile,
    Question,
    ReviewStatus,
    ScheduleSlot,
    StudentProfile,
    TeacherProfile,
    Testimonial,
    TutoringProduct,
    TutoringRequest,
    User,
    UserRole,
)
from app.services.payments import record_manual_payment

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120] or "item"


# --------------------------------------------------------------------------------------
# overview
# --------------------------------------------------------------------------------------


@router.get("/overview")
def overview(db: DbSession) -> dict[str, Any]:
    def count(model, *conditions) -> int:
        query = select(func.count()).select_from(model)
        if conditions:
            query = query.where(*conditions)
        return db.scalar(query) or 0

    revenue = db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(Order.status == OrderStatus.PAID)
    ) or 0

    return {
        "students": count(StudentProfile),
        "parents": count(ParentProfile),
        "teachers": count(TeacherProfile),
        "classes": count(ClassGroup),
        "active_enrollments": count(ClassEnrollment, ClassEnrollment.status == "active"),
        "questions": count(Question),
        "published_questions": count(Question, Question.status == ReviewStatus.PUBLISHED),
        "pending_review_questions": count(
            Question, Question.status == ReviewStatus.PENDING_REVIEW
        ),
        "courses": count(Course),
        "new_leads": count(ContactLead, ContactLead.status == LeadStatus.NEW),
        "new_tutoring_requests": count(TutoringRequest, TutoringRequest.status == LeadStatus.NEW),
        "orders_awaiting_payment": count(
            Order, Order.status == OrderStatus.AWAITING_PAYMENT
        ),
        "revenue_vnd": int(revenue),
    }


# --------------------------------------------------------------------------------------
# users
# --------------------------------------------------------------------------------------


class UserRow(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: dt.datetime
    last_login_at: dt.datetime | None = None


class CreateStaffRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole
    headline: str | None = None
    subjects: list[str] = Field(default_factory=list)
    grades: list[int] = Field(default_factory=list)


@router.get("/users", response_model=list[UserRow])
def list_users(
    db: DbSession,
    role: Annotated[UserRole | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[UserRow]:
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if search:
        pattern = f"%{search}%"
        query = query.where(User.full_name.ilike(pattern) | User.email.ilike(pattern))
    rows = db.scalars(query.order_by(User.created_at.desc()).limit(limit))
    return [UserRow.model_validate(u, from_attributes=True) for u in rows]


@router.post("/users/staff", response_model=UserRow, status_code=status.HTTP_201_CREATED)
def create_staff(payload: CreateStaffRequest, db: DbSession) -> UserRow:
    """Create a teacher or admin. This is the *only* way such accounts come into existence."""
    if payload.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the public registration endpoint for student and parent accounts",
        )

    email = str(payload.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    if payload.role == UserRole.TEACHER:
        db.add(
            TeacherProfile(
                user_id=user.id,
                headline=payload.headline,
                subjects=payload.subjects,
                grades=payload.grades,
            )
        )

    db.commit()
    db.refresh(user)
    return UserRow.model_validate(user, from_attributes=True)


@router.post("/users/{user_id}/toggle-active", response_model=UserRow)
def toggle_active(user_id: int, db: DbSession) -> UserRow:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return UserRow.model_validate(user, from_attributes=True)


# --------------------------------------------------------------------------------------
# classes
# --------------------------------------------------------------------------------------


class ScheduleSlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")


class ClassGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    course_id: int | None = None
    product_id: int | None = None
    teacher_id: int | None = None
    format: str = "group"
    delivery_mode: str = "online"
    capacity: int = Field(default=12, ge=1, le=200)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    location: str | None = None
    schedule: list[ScheduleSlotIn] = Field(default_factory=list)


@router.post("/classes", status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassGroupCreate, db: DbSession) -> dict[str, Any]:
    slug = _slugify(payload.name)
    if db.scalar(select(ClassGroup).where(ClassGroup.slug == slug)) is not None:
        slug = f"{slug}-{int(dt.datetime.now(dt.UTC).timestamp())}"

    group = ClassGroup(
        slug=slug,
        name=payload.name,
        course_id=payload.course_id,
        product_id=payload.product_id,
        teacher_id=payload.teacher_id,
        format=payload.format,
        delivery_mode=payload.delivery_mode,
        capacity=payload.capacity,
        start_date=payload.start_date,
        end_date=payload.end_date,
        location=payload.location,
    )
    db.add(group)
    db.flush()

    for slot in payload.schedule:
        db.add(
            ScheduleSlot(
                class_group_id=group.id,
                weekday=slot.weekday,
                start_time=dt.time.fromisoformat(slot.start_time),
                end_time=dt.time.fromisoformat(slot.end_time),
            )
        )

    db.commit()
    db.refresh(group)
    return {"id": group.id, "slug": group.slug, "name": group.name}


@router.get("/classes")
def list_classes(db: DbSession) -> list[dict[str, Any]]:
    groups = db.scalars(
        select(ClassGroup).options(
            selectinload(ClassGroup.enrollments),
            selectinload(ClassGroup.teacher).selectinload(TeacherProfile.user),
            selectinload(ClassGroup.course),
            selectinload(ClassGroup.sessions),
        )
    ).unique()
    return [
        {
            "id": g.id, "slug": g.slug, "name": g.name, "format": g.format,
            "capacity": g.capacity, "enrolled": len(g.enrollments),
            "active": g.seats_taken,
            "teacher": g.teacher.user.full_name if g.teacher and g.teacher.user else None,
            "course": g.course.title if g.course else None,
            "sessions": len(g.sessions),
            "is_open": g.is_open_for_enrollment,
        }
        for g in groups
    ]


# --------------------------------------------------------------------------------------
# orders and payments
# --------------------------------------------------------------------------------------


@router.get("/orders")
def list_orders(
    db: DbSession, status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None
) -> list[dict[str, Any]]:
    query = select(Order).options(selectinload(Order.items), selectinload(Order.user))
    if status_filter:
        query = query.where(Order.status == status_filter)
    orders = db.scalars(query.order_by(Order.created_at.desc()).limit(200)).unique()
    return [
        {
            "id": o.id, "reference": o.reference, "status": o.status, "total": o.total,
            "currency": o.currency, "placed_at": o.placed_at,
            "customer": o.user.full_name if o.user else None,
            "customer_email": o.user.email if o.user else None,
            "items": [{"description": i.description, "line_total": i.line_total}
                      for i in o.items],
        }
        for o in orders
    ]


class MarkPaidRequest(BaseModel):
    amount: int | None = None
    reference: str | None = Field(default=None, max_length=160)


@router.post("/orders/{order_id}/mark-paid")
def mark_order_paid(
    order_id: int, payload: MarkPaidRequest, db: DbSession
) -> dict[str, Any]:
    """Reconcile an offline payment. This is what activates the student's place in the class."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status == OrderStatus.PAID:
        return {"order_id": order.id, "status": order.status, "already_paid": True}

    payment = record_manual_payment(
        db, order, amount=payload.amount, reference=payload.reference
    )
    db.commit()
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_id": payment.id,
        "amount": payment.amount,
        "already_paid": False,
    }


# --------------------------------------------------------------------------------------
# leads
# --------------------------------------------------------------------------------------


@router.get("/leads")
def list_leads(
    db: DbSession, status_filter: Annotated[LeadStatus | None, Query(alias="status")] = None
) -> list[dict[str, Any]]:
    query = select(ContactLead)
    if status_filter:
        query = query.where(ContactLead.status == status_filter)
    rows = db.scalars(query.order_by(ContactLead.created_at.desc()).limit(200))
    return [
        {
            "id": lead.id, "name": lead.name, "email": lead.email, "phone": lead.phone,
            "subject_slug": lead.subject_slug, "grade": lead.grade, "interest": lead.interest,
            "message": lead.message, "status": lead.status, "created_at": lead.created_at,
            "source_page": lead.source_page,
        }
        for lead in rows
    ]


@router.get("/tutoring-requests")
def list_tutoring_requests(db: DbSession) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(TutoringRequest)
        .order_by(TutoringRequest.created_at.desc())
        .limit(200)
        .options(selectinload(TutoringRequest.preferred_teacher).selectinload(
            TeacherProfile.user))
    ).unique()
    return [
        {
            "id": r.id, "contact_name": r.contact_name, "contact_email": r.contact_email,
            "contact_phone": r.contact_phone, "subject_slug": r.subject_slug, "grade": r.grade,
            "format": r.format, "delivery_mode": r.delivery_mode,
            "sessions_requested": r.sessions_requested, "goals": r.goals, "status": r.status,
            "preferred_slots": r.preferred_slots, "created_at": r.created_at,
            "preferred_teacher": (
                r.preferred_teacher.user.full_name
                if r.preferred_teacher and r.preferred_teacher.user else None
            ),
        }
        for r in rows
    ]


class LeadStatusUpdate(BaseModel):
    status: LeadStatus
    admin_note: str | None = None


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, payload: LeadStatusUpdate, db: DbSession) -> dict[str, Any]:
    lead = db.get(ContactLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    lead.status = payload.status
    if payload.admin_note is not None:
        lead.admin_note = payload.admin_note
    db.commit()
    return {"id": lead.id, "status": lead.status}


@router.patch("/tutoring-requests/{request_id}")
def update_tutoring_request(
    request_id: int, payload: LeadStatusUpdate, db: DbSession
) -> dict[str, Any]:
    request = db.get(TutoringRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    request.status = payload.status
    if payload.admin_note is not None:
        request.admin_note = payload.admin_note
    db.commit()
    return {"id": request.id, "status": request.status}


# --------------------------------------------------------------------------------------
# site content
# --------------------------------------------------------------------------------------


class TestimonialIn(BaseModel):
    author_name: str = Field(min_length=1, max_length=150)
    author_role: str = Field(default="Parent", max_length=120)
    quote: str = Field(min_length=1)
    rating: int = Field(default=5, ge=1, le=5)
    subject_slug: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    is_published: bool = True
    is_featured: bool = False


@router.post("/testimonials", status_code=status.HTTP_201_CREATED)
def create_testimonial(payload: TestimonialIn, db: DbSession) -> dict[str, Any]:
    testimonial = Testimonial(**payload.model_dump())
    db.add(testimonial)
    db.commit()
    db.refresh(testimonial)
    return {"id": testimonial.id}


@router.delete("/testimonials/{testimonial_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_testimonial(testimonial_id: int, db: DbSession) -> None:
    testimonial = db.get(Testimonial, testimonial_id)
    if testimonial is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(testimonial)
    db.commit()


class BlogPostIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    excerpt: str = Field(min_length=1)
    body_markdown: str = Field(min_length=1)
    category: str = Field(default="learning", max_length=60)
    tags: list[str] = Field(default_factory=list)
    cover_image_url: str | None = None
    reading_minutes: int = Field(default=5, ge=1, le=120)
    author_name: str = Field(default="HieuTrienEducation", max_length=150)
    status: ReviewStatus = ReviewStatus.PUBLISHED


@router.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: BlogPostIn, db: DbSession) -> dict[str, Any]:
    slug = _slugify(payload.title)
    if db.scalar(select(BlogPost).where(BlogPost.slug == slug)) is not None:
        slug = f"{slug}-{int(dt.datetime.now(dt.UTC).timestamp())}"
    post = BlogPost(
        slug=slug,
        published_at=dt.datetime.now(dt.UTC) if payload.status == ReviewStatus.PUBLISHED else None,
        **payload.model_dump(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"id": post.id, "slug": post.slug}


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tagline: str | None = None
    description: str | None = None
    format: str = "group"
    delivery_mode: str = "online"
    subject_slug: str | None = None
    grade_min: int = Field(default=6, ge=1, le=12)
    grade_max: int = Field(default=9, ge=1, le=12)
    price_vnd: int = Field(default=0, ge=0)
    price_unit: str = "session"
    sessions_included: int = Field(default=1, ge=1)
    session_minutes: int = Field(default=90, ge=15)
    capacity: int = Field(default=1, ge=1)
    features: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_featured: bool = False


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductIn, db: DbSession) -> dict[str, Any]:
    slug = _slugify(payload.name)
    if db.scalar(select(TutoringProduct).where(TutoringProduct.slug == slug)) is not None:
        slug = f"{slug}-{int(dt.datetime.now(dt.UTC).timestamp())}"
    product = TutoringProduct(slug=slug, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "slug": product.slug}


@router.get("/live-sessions")
def list_live_sessions(db: DbSession) -> list[dict[str, Any]]:
    rows = db.execute(
        select(LiveSession, ClassGroup)
        .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
        .order_by(LiveSession.starts_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": live.id, "title": live.title, "class_name": group.name,
            "starts_at": live.starts_at, "ends_at": live.ends_at, "status": live.status,
            "provider": live.provider, "join_url": live.join_url,
            "recording_url": live.recording_url,
        }
        for live, group in rows
    ]
