"""Teacher management and the public teacher-profile CMS.

Two concerns share this module because they share a row: the *account* (login, active flag,
permitted subjects) and the *public profile* (biography, education, awards, courses taught). They
are edited on the same screen and both live on ``TeacherProfile``.
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    apply_sort,
    build_page,
    diff_fields,
    get_or_404,
    next_position,
    notify_user,
    paginate,
    record_audit,
)
from app.api.v1.admin._translations import (
    TranslationsPayload,
    apply_translations,
    read_translations,
)
from app.core.deps import RequestLocale
from app.core.i18n import localise
from app.core.security import hash_password
from app.core.text import unique_slug
from app.models import (
    Assignment,
    ClassEnrollment,
    ClassGroup,
    Course,
    LiveSession,
    NotificationKind,
    ScheduleSlot,
    StudentProfile,
    Subject,
    TeacherCredential,
    TeacherProfile,
    TeacherSubjectAssignment,
    TutoringProduct,
    User,
    UserRole,
)

router = APIRouter(prefix="/teachers", tags=["admin:teachers"])

CREDENTIAL_KINDS = (
    "education",
    "award",
    "certification",
    "publication",
    "competition",
    "experience",
)


class TeacherCreate(TranslationsPayload):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    headline: str | None = Field(default=None, max_length=250)
    bio: str | None = None
    subjects: list[str] = Field(default_factory=list)
    grades: list[int] = Field(default_factory=list)
    years_experience: int = Field(default=0, ge=0, le=70)
    phone: str | None = Field(default=None, max_length=40)
    is_published: bool = False


class TeacherUpdate(TranslationsPayload):
    # account
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    avatar_url: str | None = Field(default=None, max_length=500)
    # profile
    slug: str | None = Field(default=None, max_length=160)
    headline: str | None = Field(default=None, max_length=250)
    bio: str | None = None
    subjects: list[str] | None = None
    grades: list[int] | None = None
    qualifications: list[str] | None = None
    years_experience: int | None = Field(default=None, ge=0, le=70)
    languages: list[str] | None = None
    hourly_rate_vnd: int | None = Field(default=None, ge=0)
    accepts_one_to_one: bool | None = None
    availability: list[dict[str, Any]] | None = None
    photo_url: str | None = Field(default=None, max_length=600)
    teaching_philosophy: str | None = None
    teaching_style: str | None = None
    specializations: list[str] | None = None
    learning_formats: list[str] | None = None
    video_intro_url: str | None = Field(default=None, max_length=600)
    gallery: list[dict[str, Any]] | None = None
    social_links: dict[str, Any] | None = None
    public_email: str | None = Field(default=None, max_length=320)
    public_phone: str | None = Field(default=None, max_length=40)
    is_featured: bool | None = None
    is_published: bool | None = None


class CredentialIn(BaseModel):
    kind: str = Field(default="award", max_length=30)
    title: str = Field(min_length=1, max_length=250)
    organisation: str | None = Field(default=None, max_length=250)
    year_start: int | None = Field(default=None, ge=1900, le=2200)
    year_end: int | None = Field(default=None, ge=1900, le=2200)
    description: str | None = None
    url: str | None = Field(default=None, max_length=600)
    is_published: bool = True


class AssignmentIn(BaseModel):
    """Which subject / course / grade a teacher is approved to teach."""

    subject_id: int | None = None
    course_id: int | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    is_lead: bool = False


class SetActiveRequest(BaseModel):
    is_active: bool


class ResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=72)


def _teacher_row(profile: TeacherProfile) -> dict[str, Any]:
    user = profile.user
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "slug": profile.slug,
        "full_name": user.full_name if user else None,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "avatar_url": user.avatar_url if user else None,
        "photo_url": profile.photo_url or (user.avatar_url if user else None),
        "is_active": user.is_active if user else False,
        "headline": profile.headline,
        "bio": profile.bio,
        "subjects": profile.subjects or [],
        "grades": profile.grades or [],
        "qualifications": profile.qualifications or [],
        "years_experience": profile.years_experience,
        "languages": profile.languages or [],
        "hourly_rate_vnd": profile.hourly_rate_vnd,
        "rating": profile.rating,
        "rating_count": profile.rating_count,
        "is_featured": profile.is_featured,
        "is_published": profile.is_published,
        "accepts_one_to_one": profile.accepts_one_to_one,
        "availability": profile.availability or [],
        "teaching_philosophy": profile.teaching_philosophy,
        "teaching_style": profile.teaching_style,
        "specializations": profile.specializations or [],
        "learning_formats": profile.learning_formats or [],
        "video_intro_url": profile.video_intro_url,
        "gallery": profile.gallery or [],
        "social_links": profile.social_links or {},
        "public_email": profile.public_email,
        "public_phone": profile.public_phone,
        "position": profile.position,
        # The public teacher page reads every prose field through ``localise``. Returning the
        # translations here is what lets the editor round-trip them; without it the Vietnamese
        # copy is readable by students but invisible and uneditable to the person maintaining it.
        "translations": read_translations(profile),
        "created_at": profile.created_at,
    }


def _credential_row(credential: TeacherCredential) -> dict[str, Any]:
    return {
        "id": credential.id,
        "kind": credential.kind,
        "title": credential.title,
        "organisation": credential.organisation,
        "year_start": credential.year_start,
        "year_end": credential.year_end,
        "description": credential.description,
        "url": credential.url,
        "position": credential.position,
        "is_published": credential.is_published,
    }


def _slug_taken(db, slug: str, exclude_id: int | None = None) -> bool:
    query = select(TeacherProfile.id).where(TeacherProfile.slug == slug)
    if exclude_id is not None:
        query = query.where(TeacherProfile.id != exclude_id)
    return db.scalar(query) is not None


@router.get("")
def list_teachers(
    db: DbSession,
    admin: CurrentAdmin,
    subject: Annotated[str | None, Query(max_length=60)] = None,
    active: Annotated[bool | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = (
        select(TeacherProfile)
        .join(User, TeacherProfile.user_id == User.id)
        .options(selectinload(TeacherProfile.user))
    )
    if active is not None:
        query = query.where(User.is_active.is_(active))
    if published is not None:
        query = query.where(TeacherProfile.is_published.is_(published))
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                TeacherProfile.headline.ilike(pattern),
            )
        )

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        TeacherProfile,
        params,
        {
            "name": User.full_name,
            "experience": TeacherProfile.years_experience,
            "rating": TeacherProfile.rating,
            "position": TeacherProfile.position,
            "_default": TeacherProfile.position,
        },
    )
    rows, total = paginate(db, query, params)

    # Subjects live in a JSON array, which SQLite cannot filter portably; the roster is small
    # enough (tens of rows) that filtering in Python costs nothing.
    if subject:
        rows = [row for row in rows if subject in (row.subjects or [])]
        total = len(rows)

    class_counts = dict(
        db.execute(
            select(ClassGroup.teacher_id, func.count())
            .where(ClassGroup.teacher_id.isnot(None))
            .group_by(ClassGroup.teacher_id)
        ).all()
    )
    items = []
    for row in rows:
        data = _teacher_row(row)
        data["class_count"] = class_counts.get(row.id, 0)
        items.append(data)
    return build_page(items, total, params)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    email = str(payload.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        )

    temporary_password = payload.password or f"HTE-{secrets.token_urlsafe(8)}"
    user = User(
        email=email,
        password_hash=hash_password(temporary_password),
        full_name=payload.full_name,
        role=UserRole.TEACHER,
        phone=payload.phone,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    profile = TeacherProfile(
        user_id=user.id,
        slug=unique_slug(
            payload.full_name, lambda candidate: _slug_taken(db, candidate), max_length=160
        ),
        headline=payload.headline,
        bio=payload.bio,
        subjects=payload.subjects,
        grades=payload.grades,
        years_experience=payload.years_experience,
        is_published=payload.is_published,
        position=next_position(db, TeacherProfile),
    )
    db.add(profile)
    db.flush()
    apply_translations(profile, payload.translations)

    record_audit(
        db, admin, "create", "teacher", profile.id,
        f"Created teacher account for {payload.full_name}",
    )
    db.commit()
    db.refresh(profile)

    result = _teacher_row(profile)
    if payload.password is None:
        result["temporary_password"] = temporary_password
    return result


@router.get("/{teacher_id}")
def get_teacher(
    teacher_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(
            selectinload(TeacherProfile.user), selectinload(TeacherProfile.credentials)
        )
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    data = _teacher_row(profile)
    data["credentials"] = [_credential_row(c) for c in profile.credentials]

    # classes and their rosters
    groups = db.scalars(
        select(ClassGroup)
        .where(ClassGroup.teacher_id == teacher_id)
        .options(selectinload(ClassGroup.enrollments), selectinload(ClassGroup.schedule_slots))
    ).unique()
    data["classes"] = [
        {
            "id": g.id,
            "name": g.name,
            "format": g.format,
            "delivery_mode": g.delivery_mode,
            "capacity": g.capacity,
            "enrolled": len(g.enrollments),
            "active": g.seats_taken,
            "start_date": g.start_date,
            "end_date": g.end_date,
            "is_open": g.is_open_for_enrollment,
        }
        for g in groups
    ]

    class_ids = [row["id"] for row in data["classes"]]
    if class_ids:
        student_rows = db.execute(
            select(StudentProfile, User, ClassEnrollment)
            .join(User, StudentProfile.user_id == User.id)
            .join(ClassEnrollment, ClassEnrollment.student_id == StudentProfile.id)
            .where(ClassEnrollment.class_group_id.in_(class_ids))
        ).all()
        data["students"] = [
            {
                "id": student.id,
                "name": user.full_name,
                "email": user.email,
                "grade": student.grade,
                "class_id": enrollment.class_group_id,
                "status": enrollment.status,
            }
            for student, user, enrollment in student_rows
        ]
    else:
        data["students"] = []

    # schedule: recurring slots plus concrete upcoming sessions
    slots = db.scalars(
        select(ScheduleSlot).where(ScheduleSlot.class_group_id.in_(class_ids or [0]))
    )
    data["schedule_slots"] = [
        {
            "id": slot.id,
            "class_group_id": slot.class_group_id,
            "weekday": slot.weekday,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
        }
        for slot in slots
    ]
    sessions = db.execute(
        select(LiveSession, ClassGroup)
        .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
        .where(ClassGroup.teacher_id == teacher_id)
        .order_by(LiveSession.starts_at.desc())
        .limit(40)
    ).all()
    data["sessions"] = [
        {
            "id": session.id,
            "title": session.title,
            "class_name": group.name,
            "starts_at": session.starts_at,
            "ends_at": session.ends_at,
            "status": session.status,
            "join_url": session.join_url,
        }
        for session, group in sessions
    ]

    # permitted subjects/courses
    assignments = db.execute(
        select(TeacherSubjectAssignment, Subject, Course)
        .outerjoin(Subject, TeacherSubjectAssignment.subject_id == Subject.id)
        .outerjoin(Course, TeacherSubjectAssignment.course_id == Course.id)
        .where(TeacherSubjectAssignment.teacher_id == teacher_id)
    ).all()
    data["assignments"] = [
        {
            "id": assignment.id,
            "subject_id": assignment.subject_id,
            "subject_name": localise(subject, "name", locale) if subject else None,
            "course_id": assignment.course_id,
            "course_title": localise(course, "title", locale) if course else None,
            "grade": assignment.grade,
            "is_lead": assignment.is_lead,
        }
        for assignment, subject, course in assignments
    ]

    # content this teacher owns
    courses = db.scalars(select(Course).where(Course.teacher_id == teacher_id))
    data["courses_taught"] = [
        {"id": c.id, "title": c.title, "slug": c.slug, "grade": c.grade, "status": c.status}
        for c in courses
    ]
    products = db.scalars(select(TutoringProduct).where(TutoringProduct.teacher_id == teacher_id))
    data["programs"] = [
        {"id": p.id, "name": p.name, "slug": p.slug, "format": p.format,
         "price_vnd": p.price_vnd}
        for p in products
    ]
    homework = (
        db.scalar(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.teacher_id == teacher_id)
        )
        or 0
    )
    data["assignment_count"] = homework
    return data


@router.patch("/{teacher_id}")
def update_teacher(
    teacher_id: int, payload: TeacherUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    # ``translations`` is not a column: it is merged into ``i18n`` below, so setting it as an
    # attribute would either raise or shadow the real blob.
    fields = payload.model_dump(exclude_unset=True, exclude={"slug", "translations"})
    user_fields = {"full_name", "email", "phone", "avatar_url"}

    before: dict[str, Any] = {}
    for key, value in fields.items():
        target = profile.user if key in user_fields else profile
        if target is None:
            continue
        if key == "email" and value is not None:
            value = str(value).lower()
            clash = db.scalar(
                select(User).where(func.lower(User.email) == value, User.id != profile.user_id)
            )
            if clash is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another account already uses that email",
                )
        before[key] = getattr(target, key)
        setattr(target, key, value)

    if payload.slug:
        profile.slug = unique_slug(
            payload.slug,
            lambda candidate: _slug_taken(db, candidate, exclude_id=profile.id),
            max_length=160,
        )
    elif profile.slug is None and profile.user is not None:
        # A profile about to be published needs a public URL.
        profile.slug = unique_slug(
            profile.user.full_name,
            lambda candidate: _slug_taken(db, candidate, exclude_id=profile.id),
            max_length=160,
        )

    apply_translations(profile, payload.translations)

    record_audit(
        db, admin, "update", "teacher", profile.id,
        f"Updated teacher {profile.user.full_name if profile.user else teacher_id}",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(profile)
    return _teacher_row(profile)


@router.post("/{teacher_id}/publish")
def publish_teacher(teacher_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    return _set_published(db, admin, teacher_id, True)


@router.post("/{teacher_id}/unpublish")
def unpublish_teacher(teacher_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    return _set_published(db, admin, teacher_id, False)


def _set_published(db, admin, teacher_id: int, value: bool) -> dict[str, Any]:
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    if value and not profile.slug and profile.user:
        profile.slug = unique_slug(
            profile.user.full_name,
            lambda candidate: _slug_taken(db, candidate, exclude_id=profile.id),
            max_length=160,
        )
    profile.is_published = value
    record_audit(
        db, admin, "publish" if value else "unpublish", "teacher", profile.id,
        f"{'Published' if value else 'Unpublished'} profile for "
        f"{profile.user.full_name if profile.user else teacher_id}",
    )
    db.commit()
    db.refresh(profile)
    return _teacher_row(profile)


@router.post("/{teacher_id}/set-active")
def set_teacher_active(
    teacher_id: int, payload: SetActiveRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None or profile.user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    profile.user.is_active = payload.is_active
    record_audit(
        db, admin, "activate" if payload.is_active else "deactivate", "teacher", profile.id,
        f"{'Activated' if payload.is_active else 'Deactivated'} {profile.user.full_name}",
    )
    db.commit()
    db.refresh(profile)
    return _teacher_row(profile)


@router.post("/{teacher_id}/reset-password")
def reset_teacher_password(
    teacher_id: int, payload: ResetPasswordRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None or profile.user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    new_password = payload.password or f"HTE-{secrets.token_urlsafe(8)}"
    profile.user.password_hash = hash_password(new_password)
    record_audit(
        db, admin, "reset_password", "teacher", profile.id,
        f"Reset password for {profile.user.full_name}",
    )
    db.commit()
    return {
        "teacher_id": profile.id,
        "temporary_password": new_password if payload.password is None else None,
    }


@router.post("/reorder")
def reorder_teachers(
    payload: dict[str, list[int]], db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    ids = payload.get("ids") or []
    rows = {r.id: r for r in db.scalars(select(TeacherProfile).where(TeacherProfile.id.in_(ids)))}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown teacher ids: {missing}"
        )
    for index, teacher_id in enumerate(ids, start=1):
        rows[teacher_id].position = index
    record_audit(db, admin, "reorder", "teacher", None, f"Reordered {len(ids)} teachers")
    db.commit()
    return {"reordered": len(ids)}


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(teacher_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    # Classes keep their history; the FK is ON DELETE SET NULL, so they become unassigned rather
    # than disappearing. Warn if that is about to happen to a live class.
    active_classes = (
        db.scalar(
            select(func.count())
            .select_from(ClassGroup)
            .where(
                ClassGroup.teacher_id == teacher_id,
                ClassGroup.is_open_for_enrollment.is_(True),
            )
        )
        or 0
    )
    if active_classes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This teacher still leads {active_classes} open class(es). Reassign them, or "
                "deactivate the teacher instead of deleting."
            ),
        )

    name = profile.user.full_name if profile.user else str(teacher_id)
    user = profile.user
    db.delete(profile)
    if user is not None:
        db.delete(user)
    record_audit(db, admin, "delete", "teacher", teacher_id, f"Deleted teacher {name}")
    db.commit()


# --------------------------------------------------------------------------------------
# structured credentials
# --------------------------------------------------------------------------------------


@router.get("/{teacher_id}/credentials")
def list_credentials(
    teacher_id: int, db: DbSession, admin: CurrentAdmin
) -> list[dict[str, Any]]:
    get_or_404(db, TeacherProfile, teacher_id, "Teacher")
    rows = db.scalars(
        select(TeacherCredential)
        .where(TeacherCredential.teacher_id == teacher_id)
        .order_by(TeacherCredential.kind, TeacherCredential.position)
    )
    return [_credential_row(row) for row in rows]


@router.post("/{teacher_id}/credentials", status_code=status.HTTP_201_CREATED)
def add_credential(
    teacher_id: int, payload: CredentialIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    get_or_404(db, TeacherProfile, teacher_id, "Teacher")
    if payload.kind not in CREDENTIAL_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown credential kind. Expected one of: {', '.join(CREDENTIAL_KINDS)}",
        )
    if payload.year_end is not None and payload.year_start is not None:
        if payload.year_end < payload.year_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End year cannot be before start year",
            )

    credential = TeacherCredential(
        teacher_id=teacher_id,
        **payload.model_dump(),
        position=next_position(
            db, TeacherCredential, TeacherCredential.teacher_id == teacher_id
        ),
    )
    db.add(credential)
    db.flush()
    record_audit(
        db, admin, "create", "teacher_credential", credential.id,
        f"Added {payload.kind} “{payload.title}”",
    )
    db.commit()
    db.refresh(credential)
    return _credential_row(credential)


@router.patch("/credentials/{credential_id}")
def update_credential(
    credential_id: int, payload: CredentialIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    credential = get_or_404(db, TeacherCredential, credential_id, "Credential")
    fields = payload.model_dump(exclude_unset=True)
    before = {key: getattr(credential, key) for key in fields}
    for key, value in fields.items():
        setattr(credential, key, value)
    record_audit(
        db, admin, "update", "teacher_credential", credential.id,
        f"Updated “{credential.title}”", diff_fields(before, fields),
    )
    db.commit()
    db.refresh(credential)
    return _credential_row(credential)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(credential_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    credential = get_or_404(db, TeacherCredential, credential_id, "Credential")
    title = credential.title
    db.delete(credential)
    record_audit(
        db, admin, "delete", "teacher_credential", credential_id, f"Removed “{title}”"
    )
    db.commit()


@router.post("/{teacher_id}/credentials/reorder")
def reorder_credentials(
    teacher_id: int, payload: dict[str, list[int]], db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    ids = payload.get("ids") or []
    rows = {
        r.id: r
        for r in db.scalars(
            select(TeacherCredential).where(
                TeacherCredential.id.in_(ids), TeacherCredential.teacher_id == teacher_id
            )
        )
    }
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown credential ids: {missing}"
        )
    for index, credential_id in enumerate(ids, start=1):
        rows[credential_id].position = index
    db.commit()
    return {"reordered": len(ids)}


# --------------------------------------------------------------------------------------
# teaching permissions
# --------------------------------------------------------------------------------------


@router.post("/{teacher_id}/assignments", status_code=status.HTTP_201_CREATED)
def assign_subject(
    teacher_id: int, payload: AssignmentIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Grant a teacher rights over a subject, course or grade.

    Unlike the JSON ``subjects`` array — which is presentation only — these rows are what the
    teacher-scoped endpoints check, so this is a real permission grant.
    """
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if payload.subject_id is None and payload.course_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify at least a subject or a course",
        )
    if payload.subject_id is not None:
        get_or_404(db, Subject, payload.subject_id, "Subject")
    course = None
    if payload.course_id is not None:
        course = get_or_404(db, Course, payload.course_id, "Course")

    existing = db.scalar(
        select(TeacherSubjectAssignment).where(
            TeacherSubjectAssignment.teacher_id == teacher_id,
            TeacherSubjectAssignment.subject_id == payload.subject_id,
            TeacherSubjectAssignment.course_id == payload.course_id,
            TeacherSubjectAssignment.grade == payload.grade,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That assignment already exists"
        )

    assignment = TeacherSubjectAssignment(teacher_id=teacher_id, **payload.model_dump())
    db.add(assignment)
    db.flush()

    if profile.user is not None:
        notify_user(
            db,
            profile.user_id,
            NotificationKind.COURSE_ASSIGNED,
            "You have a new teaching assignment",
            body=(
                f"You have been assigned to {course.title}"
                if course
                else "You have been assigned a new subject"
            ),
            link_url="/teacher",
            entity_type="teacher_assignment",
            entity_id=assignment.id,
        )

    record_audit(
        db, admin, "assign", "teacher", teacher_id,
        f"Assigned {course.title if course else 'a subject'} to "
        f"{profile.user.full_name if profile.user else teacher_id}",
    )
    db.commit()
    db.refresh(assignment)
    return {
        "id": assignment.id,
        "subject_id": assignment.subject_id,
        "course_id": assignment.course_id,
        "grade": assignment.grade,
        "is_lead": assignment.is_lead,
    }


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(assignment_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    assignment = get_or_404(db, TeacherSubjectAssignment, assignment_id, "Assignment")
    teacher_id = assignment.teacher_id
    db.delete(assignment)
    record_audit(
        db, admin, "unassign", "teacher", teacher_id, "Removed a teaching assignment"
    )
    db.commit()


@router.post("/{teacher_id}/classes/{class_id}")
def assign_class(
    teacher_id: int, class_id: int, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Put a teacher in charge of a class."""
    profile = db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    group = get_or_404(db, ClassGroup, class_id, "Class")

    group.teacher_id = teacher_id
    if profile.user is not None:
        notify_user(
            db,
            profile.user_id,
            NotificationKind.COURSE_ASSIGNED,
            f"You are now teaching {group.name}",
            link_url="/teacher",
            entity_type="class",
            entity_id=group.id,
        )
    record_audit(
        db, admin, "assign", "class", group.id,
        f"Assigned {profile.user.full_name if profile.user else teacher_id} to “{group.name}”",
    )
    db.commit()
    return {"class_id": group.id, "teacher_id": teacher_id, "class_name": group.name}
