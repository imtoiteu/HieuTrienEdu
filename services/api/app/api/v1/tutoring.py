"""Tutoring marketplace: products, teachers, classes, booking requests and orders."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import (
    ClassEnrollment,
    ClassGroup,
    Course,
    DeliveryMode,
    EnrollmentStatus,
    LeadStatus,
    LearningFormat,
    NotificationKind,
    Order,
    OrderItem,
    OrderStatus,
    TeacherProfile,
    TutoringProduct,
    TutoringRequest,
    User,
    UserRole,
)
from app.services.notifications import notify_admins
from app.services.payments import create_order_reference, get_payment_provider

router = APIRouter(prefix="/tutoring", tags=["tutoring"])

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --------------------------------------------------------------------------------------
# schemas
# --------------------------------------------------------------------------------------


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    tagline: str | None = None
    description: str | None = None
    format: LearningFormat
    delivery_mode: DeliveryMode
    subject_slug: str | None = None
    grade_min: int
    grade_max: int
    price_vnd: int
    price_unit: str
    sessions_included: int
    session_minutes: int
    capacity: int
    features: list[str] = Field(default_factory=list)
    is_featured: bool = False


class TeacherCard(BaseModel):
    id: int
    user_id: int
    full_name: str
    headline: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    subjects: list[str] = Field(default_factory=list)
    grades: list[int] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    years_experience: int = 0
    languages: list[str] = Field(default_factory=list)
    rating: float = 0.0
    rating_count: int = 0
    is_featured: bool = False
    accepts_one_to_one: bool = True
    hourly_rate_vnd: int | None = None
    availability: list[dict[str, Any]] = Field(default_factory=list)


class ScheduleSlotRead(BaseModel):
    weekday: int
    weekday_label: str
    start_time: str
    end_time: str


class ClassGroupRead(BaseModel):
    id: int
    slug: str
    name: str
    format: LearningFormat
    delivery_mode: DeliveryMode
    capacity: int
    seats_taken: int
    seats_available: int
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    location: str | None = None
    timezone: str
    is_open_for_enrollment: bool
    course_title: str | None = None
    course_slug: str | None = None
    grade: int | None = None
    teacher: TeacherCard | None = None
    schedule: list[ScheduleSlotRead] = Field(default_factory=list)
    price_vnd: int | None = None


class TutoringRequestCreate(BaseModel):
    contact_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=40)
    subject_slug: str = Field(max_length=60)
    grade: int = Field(ge=1, le=12)
    format: LearningFormat = LearningFormat.ONE_TO_ONE
    delivery_mode: DeliveryMode = DeliveryMode.ONLINE
    preferred_teacher_id: int | None = None
    preferred_slots: list[dict[str, Any]] = Field(default_factory=list)
    sessions_requested: int = Field(default=8, ge=1, le=100)
    goals: str | None = Field(default=None, max_length=2000)
    # Optional detail so the admin consultation screen has something to work with.
    contact_student_name: str | None = Field(default=None, max_length=200)
    parent_name: str | None = Field(default=None, max_length=200)
    parent_phone: str | None = Field(default=None, max_length=40)
    source_page: str | None = Field(default=None, max_length=160)


class TutoringRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_name: str
    contact_email: EmailStr
    subject_slug: str
    grade: int
    format: LearningFormat
    delivery_mode: DeliveryMode
    sessions_requested: int
    status: LeadStatus
    created_at: dt.datetime


class EnrollRequest(BaseModel):
    class_group_id: int
    student_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class OrderRead(BaseModel):
    id: int
    reference: str
    status: OrderStatus
    currency: str
    subtotal: int
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)
    payment_instructions: str | None = None
    checkout_url: str | None = None


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _teacher_card(profile: TeacherProfile) -> TeacherCard:
    return TeacherCard(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.user.full_name if profile.user else "",
        headline=profile.headline,
        bio=profile.bio,
        avatar_url=profile.user.avatar_url if profile.user else None,
        subjects=profile.subjects or [],
        grades=profile.grades or [],
        qualifications=profile.qualifications or [],
        years_experience=profile.years_experience,
        languages=profile.languages or [],
        rating=profile.rating,
        rating_count=profile.rating_count,
        is_featured=profile.is_featured,
        accepts_one_to_one=profile.accepts_one_to_one,
        hourly_rate_vnd=profile.hourly_rate_vnd,
        availability=profile.availability or [],
    )


def _class_read(group: ClassGroup) -> ClassGroupRead:
    taken = group.seats_taken
    return ClassGroupRead(
        id=group.id,
        slug=group.slug,
        name=group.name,
        format=group.format,
        delivery_mode=group.delivery_mode,
        capacity=group.capacity,
        seats_taken=taken,
        seats_available=max(0, group.capacity - taken),
        start_date=group.start_date,
        end_date=group.end_date,
        location=group.location,
        timezone=group.timezone,
        is_open_for_enrollment=group.is_open_for_enrollment,
        course_title=group.course.title if group.course else None,
        course_slug=group.course.slug if group.course else None,
        grade=group.course.grade if group.course else None,
        teacher=_teacher_card(group.teacher) if group.teacher else None,
        schedule=[
            ScheduleSlotRead(
                weekday=slot.weekday,
                weekday_label=WEEKDAYS[slot.weekday % 7],
                start_time=slot.start_time.strftime("%H:%M"),
                end_time=slot.end_time.strftime("%H:%M"),
            )
            for slot in sorted(group.schedule_slots, key=lambda s: (s.weekday, s.start_time))
        ],
    )


# --------------------------------------------------------------------------------------
# public endpoints
# --------------------------------------------------------------------------------------


@router.get("/products", response_model=list[ProductRead])
def list_products(
    db: DbSession,
    format: Annotated[LearningFormat | None, Query()] = None,
    subject: Annotated[str | None, Query()] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> list[ProductRead]:
    query = select(TutoringProduct).where(TutoringProduct.is_active.is_(True))
    if format:
        query = query.where(TutoringProduct.format == format)
    if subject:
        query = query.where(TutoringProduct.subject_slug == subject)
    if grade:
        query = query.where(
            TutoringProduct.grade_min <= grade, TutoringProduct.grade_max >= grade
        )
    products = db.scalars(query.order_by(TutoringProduct.position, TutoringProduct.id))
    return [ProductRead.model_validate(p) for p in products]


@router.get("/products/{slug}", response_model=ProductRead)
def get_product(slug: str, db: DbSession) -> ProductRead:
    product = db.scalar(select(TutoringProduct).where(TutoringProduct.slug == slug))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductRead.model_validate(product)


@router.get("/teachers", response_model=list[TeacherCard])
def list_teachers(
    db: DbSession,
    subject: Annotated[str | None, Query()] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    featured: Annotated[bool | None, Query()] = None,
) -> list[TeacherCard]:
    query = (
        select(TeacherProfile)
        .join(User, TeacherProfile.user_id == User.id)
        .where(User.is_active.is_(True))
        .options(selectinload(TeacherProfile.user))
        .order_by(TeacherProfile.is_featured.desc(), TeacherProfile.rating.desc())
    )
    if featured is not None:
        query = query.where(TeacherProfile.is_featured.is_(featured))

    teachers = list(db.scalars(query).unique())

    # Subject and grade live in JSON arrays, which SQLite cannot index or query portably, so
    # these two filters are applied in Python. The teacher roster is small (tens, not thousands),
    # so this is cheaper than the schema complexity of a join table would be.
    if subject:
        teachers = [t for t in teachers if subject in (t.subjects or [])]
    if grade:
        teachers = [t for t in teachers if grade in (t.grades or [])]

    return [_teacher_card(t) for t in teachers]


@router.get("/teachers/{teacher_id}", response_model=TeacherCard)
def get_teacher(teacher_id: int, db: DbSession) -> TeacherCard:
    teacher = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    return _teacher_card(teacher)


@router.get("/classes", response_model=list[ClassGroupRead])
def list_classes(
    db: DbSession,
    subject: Annotated[str | None, Query()] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    format: Annotated[LearningFormat | None, Query()] = None,
    open_only: Annotated[bool, Query()] = True,
) -> list[ClassGroupRead]:
    query = (
        select(ClassGroup)
        .options(
            selectinload(ClassGroup.course),
            selectinload(ClassGroup.teacher).selectinload(TeacherProfile.user),
            selectinload(ClassGroup.schedule_slots),
            selectinload(ClassGroup.enrollments),
        )
        .order_by(ClassGroup.start_date, ClassGroup.id)
    )
    if open_only:
        query = query.where(ClassGroup.is_open_for_enrollment.is_(True))
    if format:
        query = query.where(ClassGroup.format == format)

    groups = list(db.scalars(query).unique())
    if grade:
        groups = [g for g in groups if g.course and g.course.grade == grade]
    if subject:
        groups = [
            g for g in groups
            if g.course and g.course.subject and g.course.subject.slug == subject
        ]
    return [_class_read(g) for g in groups]


@router.get("/classes/{slug}", response_model=ClassGroupRead)
def get_class(slug: str, db: DbSession) -> ClassGroupRead:
    group = db.scalar(
        select(ClassGroup)
        .where(ClassGroup.slug == slug)
        .options(
            selectinload(ClassGroup.course),
            selectinload(ClassGroup.teacher).selectinload(TeacherProfile.user),
            selectinload(ClassGroup.schedule_slots),
            selectinload(ClassGroup.enrollments),
        )
    )
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return _class_read(group)


@router.post("/requests", response_model=TutoringRequestRead, status_code=status.HTTP_201_CREATED)
def create_tutoring_request(
    payload: TutoringRequestCreate, db: DbSession, user: OptionalUser = None
) -> TutoringRequestRead:
    """Submit a tutoring enquiry.

    Deliberately available to anonymous visitors: requiring an account before a parent can ask
    about lessons would lose most enquiries.
    """
    student_id = None
    if user is not None and user.student_profile is not None:
        student_id = user.student_profile.id

    request = TutoringRequest(
        student_id=student_id,
        contact_name=payload.contact_name.strip(),
        contact_email=str(payload.contact_email).lower(),
        contact_phone=payload.contact_phone,
        subject_slug=payload.subject_slug,
        grade=payload.grade,
        format=payload.format,
        delivery_mode=payload.delivery_mode,
        preferred_teacher_id=payload.preferred_teacher_id,
        preferred_slots=payload.preferred_slots,
        sessions_requested=payload.sessions_requested,
        goals=payload.goals,
        contact_student_name=payload.contact_student_name,
        parent_name=payload.parent_name,
        parent_phone=payload.parent_phone,
        source_page=payload.source_page,
        status=LeadStatus.NEW,
    )
    db.add(request)
    db.flush()

    # Same reasoning as the contact form: a booking request that only lands in a table is a
    # request nobody has been told about.
    notify_admins(
        db,
        NotificationKind.TUTORING_REQUEST_CREATED,
        f"New {payload.format.replace('_', '-')} request from {request.contact_name}",
        body=(
            f"{payload.subject_slug}, grade {payload.grade}, "
            f"{payload.sessions_requested} session(s)"
        ),
        link_url=f"/admin/consultations/tutoring/{request.id}",
        entity_type="lead:tutoring",
        entity_id=request.id,
    )
    db.commit()
    db.refresh(request)
    return TutoringRequestRead.model_validate(request)


@router.post("/enroll", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def enroll_in_class(payload: EnrollRequest, db: DbSession, user: CurrentUser) -> OrderRead:
    """Reserve a place in a class and create the corresponding order.

    The place is held as ``pending`` until payment is confirmed — see
    ``services/payments.record_manual_payment``.
    """
    group = db.scalar(
        select(ClassGroup)
        .where(ClassGroup.id == payload.class_group_id)
        .options(selectinload(ClassGroup.enrollments), selectinload(ClassGroup.course))
    )
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if not group.is_open_for_enrollment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This class is not open for enrollment"
        )

    # Resolve which student is being enrolled: a student enrols themselves; a parent enrols one
    # of their linked children.
    student_id = payload.student_id
    if user.role == UserRole.STUDENT and user.student_profile:
        student_id = user.student_profile.id
    elif user.role == UserRole.PARENT:
        if student_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specify which child to enroll",
            )
        linked = {link.student_id for link in (user.parent_profile.student_links
                                               if user.parent_profile else [])}
        if student_id not in linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="That student is not linked to your account",
            )
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No student specified"
        )

    if len(group.enrollments) >= group.capacity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This class is full")

    existing = db.scalar(
        select(ClassEnrollment).where(
            ClassEnrollment.class_group_id == group.id,
            ClassEnrollment.student_id == student_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This student is already enrolled in the class",
        )

    product = db.get(TutoringProduct, group.product_id) if group.product_id else None
    price = product.price_vnd if product else 0

    order = Order(
        reference=create_order_reference(),
        user_id=user.id,
        student_id=student_id,
        status=OrderStatus.AWAITING_PAYMENT,
        subtotal=price,
        total=price,
        placed_at=dt.datetime.now(dt.UTC),
    )
    db.add(order)
    db.flush()

    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id if product else None,
            class_group_id=group.id,
            description=f"{group.name}" + (f" — {product.name}" if product else ""),
            unit_price=price,
            quantity=1,
            line_total=price,
        )
    )
    db.add(
        ClassEnrollment(
            class_group_id=group.id,
            student_id=student_id,
            order_id=order.id,
            status=EnrollmentStatus.PENDING,
            notes=payload.notes,
        )
    )
    db.flush()

    intent = get_payment_provider().create_intent(order)
    db.commit()
    db.refresh(order)

    return OrderRead(
        id=order.id,
        reference=order.reference,
        status=order.status,
        currency=order.currency,
        subtotal=order.subtotal,
        total=order.total,
        items=[
            {"description": item.description, "unit_price": item.unit_price,
             "quantity": item.quantity, "line_total": item.line_total}
            for item in order.items
        ],
        payment_instructions=intent.instructions,
        checkout_url=intent.checkout_url,
    )


@router.get("/orders", response_model=list[OrderRead])
def my_orders(db: DbSession, user: CurrentUser) -> list[OrderRead]:
    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .options(selectinload(Order.items))
    )
    return [
        OrderRead(
            id=o.id, reference=o.reference, status=o.status, currency=o.currency,
            subtotal=o.subtotal, total=o.total,
            items=[
                {"description": i.description, "unit_price": i.unit_price,
                 "quantity": i.quantity, "line_total": i.line_total}
                for i in o.items
            ],
        )
        for o in orders
    ]


# --------------------------------------------------------------------------------------
# public teacher profiles
# --------------------------------------------------------------------------------------
#
# These render entirely from admin-managed rows: the profile fields on TeacherProfile plus the
# structured TeacherCredential list. Nothing about a teacher's page lives in the frontend source,
# so adding a teacher or an award never requires a deploy.


def _grouped_credentials(profile: TeacherProfile) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for credential in sorted(
        profile.credentials, key=lambda c: (c.kind, c.position, -(c.year_start or 0))
    ):
        if not credential.is_published:
            continue
        grouped.setdefault(credential.kind, []).append(
            {
                "id": credential.id,
                "title": credential.title,
                "organisation": credential.organisation,
                "year_start": credential.year_start,
                "year_end": credential.year_end,
                "description": credential.description,
                "url": credential.url,
            }
        )
    return grouped


@router.get("/profiles")
def list_teacher_profiles(
    db: DbSession,
    subject: Annotated[str | None, Query(max_length=60)] = None,
    featured: Annotated[bool | None, Query()] = None,
) -> list[dict[str, Any]]:
    """Published teacher profiles, in the order an administrator arranged them."""
    query = (
        select(TeacherProfile)
        .join(User, TeacherProfile.user_id == User.id)
        .where(User.is_active.is_(True), TeacherProfile.is_published.is_(True))
        .options(selectinload(TeacherProfile.user))
        .order_by(
            TeacherProfile.position, TeacherProfile.is_featured.desc(), TeacherProfile.id
        )
    )
    if featured is not None:
        query = query.where(TeacherProfile.is_featured.is_(featured))

    rows = list(db.scalars(query).unique())
    if subject:
        rows = [row for row in rows if subject in (row.subjects or [])]

    return [
        {
            "id": row.id,
            "slug": row.slug,
            "full_name": row.user.full_name if row.user else "",
            "headline": row.headline,
            "photo_url": row.photo_url or (row.user.avatar_url if row.user else None),
            "subjects": row.subjects or [],
            "grades": row.grades or [],
            "years_experience": row.years_experience,
            "specializations": row.specializations or [],
            "learning_formats": row.learning_formats or [],
            "is_featured": row.is_featured,
            "rating": row.rating,
            "rating_count": row.rating_count,
        }
        for row in rows
    ]


@router.get("/profiles/{slug}")
def get_teacher_profile(slug: str, db: DbSession) -> dict[str, Any]:
    """One teacher's full public page, assembled from admin-managed content."""
    profile = db.scalar(
        select(TeacherProfile)
        .join(User, TeacherProfile.user_id == User.id)
        .where(
            TeacherProfile.slug == slug,
            TeacherProfile.is_published.is_(True),
            User.is_active.is_(True),
        )
        .options(
            selectinload(TeacherProfile.user), selectinload(TeacherProfile.credentials)
        )
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    courses = db.scalars(
        select(Course).where(
            Course.teacher_id == profile.id, Course.is_published.is_(True)
        )
    )
    products = db.scalars(
        select(TutoringProduct).where(
            TutoringProduct.teacher_id == profile.id, TutoringProduct.is_active.is_(True)
        )
    )
    classes = db.scalars(
        select(ClassGroup).where(
            ClassGroup.teacher_id == profile.id,
            ClassGroup.is_open_for_enrollment.is_(True),
        )
    )

    return {
        "id": profile.id,
        "slug": profile.slug,
        "full_name": profile.user.full_name if profile.user else "",
        "headline": profile.headline,
        "bio": profile.bio,
        "photo_url": profile.photo_url or (profile.user.avatar_url if profile.user else None),
        "subjects": profile.subjects or [],
        "grades": profile.grades or [],
        "specializations": profile.specializations or [],
        "years_experience": profile.years_experience,
        "languages": profile.languages or [],
        "qualifications": profile.qualifications or [],
        "teaching_philosophy": profile.teaching_philosophy,
        "teaching_style": profile.teaching_style,
        "learning_formats": profile.learning_formats or [],
        "accepts_one_to_one": profile.accepts_one_to_one,
        "hourly_rate_vnd": profile.hourly_rate_vnd,
        "rating": profile.rating,
        "rating_count": profile.rating_count,
        "is_featured": profile.is_featured,
        "video_intro_url": profile.video_intro_url,
        "gallery": profile.gallery or [],
        "social_links": profile.social_links or {},
        "contact": {
            "email": profile.public_email,
            "phone": profile.public_phone,
        },
        "availability": profile.availability or [],
        "credentials": _grouped_credentials(profile),
        "courses": [
            {"id": c.id, "slug": c.slug, "title": c.title, "grade": c.grade,
             "thumbnail_url": c.thumbnail_url}
            for c in courses
        ],
        "programs": [
            {"id": p.id, "slug": p.slug, "name": p.name, "format": p.format,
             "price_vnd": p.price_vnd, "price_unit": p.price_unit,
             "delivery_mode": p.delivery_mode}
            for p in products
        ],
        "classes": [
            {"id": g.id, "slug": g.slug, "name": g.name, "format": g.format,
             "start_date": g.start_date, "delivery_mode": g.delivery_mode}
            for g in classes
        ],
    }
