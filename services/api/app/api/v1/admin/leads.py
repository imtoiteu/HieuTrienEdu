"""Consultation and enquiry management.

Every public form — "Đăng ký tư vấn", "Liên hệ", "Muốn học 1-1" — lands in one of two tables:
``ContactLead`` for general consultation enquiries and ``TutoringRequest`` for structured 1-to-1
booking requests. They stay separate because a tutoring request genuinely carries fields a contact
enquiry does not (preferred slots, session count, preferred teacher), and flattening them would
mean either losing that structure or filling a wide table mostly with nulls.

What they *share* is the pipeline: an owner, a stage, a note history, a follow-up date and a
conversion outcome. This module presents both as one inbox by projecting each onto a common shape
and unioning them, so an administrator sees a single list and never has to remember which form a
parent happened to use.
"""

from __future__ import annotations

import datetime as dt
import math
import secrets
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, literal, or_, select, union_all
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    get_or_404,
    record_audit,
)
from app.core.security import hash_password
from app.models import (
    ClassEnrollment,
    ClassGroup,
    ContactLead,
    Course,
    EnrollmentStatus,
    LeadNote,
    LeadStatus,
    StudentProfile,
    TeacherProfile,
    TutoringProduct,
    TutoringRequest,
    User,
    UserRole,
)

router = APIRouter(prefix="/leads", tags=["admin:leads"])

LeadSource = Literal["contact", "tutoring"]

# Which statuses still need work. Used by the dashboard badge and the default inbox filter.
OPEN_STATUSES = (
    LeadStatus.NEW,
    LeadStatus.CONTACTED,
    LeadStatus.CONSULTING,
    LeadStatus.INTERESTED,
)


class LeadStatusUpdate(BaseModel):
    status: LeadStatus | None = None
    assigned_to_id: int | None = None
    admin_note: str | None = None
    consultation_result: str | None = None
    next_follow_up_at: dt.datetime | None = None
    mark_contacted: bool = False


class LeadNoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    kind: str = Field(default="note", max_length=30)


class ConvertLeadRequest(BaseModel):
    """Turn an enquiry into a real student, and optionally straight into an enrollment.

    ``student_id`` links an existing student instead of creating one — the common case when a
    sibling or a returning family enquires again.
    """

    student_id: int | None = None
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=200)
    grade: int | None = Field(default=None, ge=1, le=12)
    phone: str | None = Field(default=None, max_length=40)
    school: str | None = Field(default=None, max_length=200)
    class_group_id: int | None = None
    enrollment_notes: str | None = Field(default=None, max_length=1000)


NOTE_KINDS = {"note", "call", "email", "meeting", "status_change"}


# --------------------------------------------------------------------------------------
# projection shared by both tables
# --------------------------------------------------------------------------------------


def _contact_projection():
    """``ContactLead`` mapped onto the common inbox columns."""
    return select(
        literal("contact").label("source"),
        ContactLead.id.label("id"),
        ContactLead.name.label("name"),
        ContactLead.email.label("email"),
        ContactLead.phone.label("phone"),
        ContactLead.subject_slug.label("subject_slug"),
        ContactLead.grade.label("grade"),
        ContactLead.interest.label("interest"),
        ContactLead.preferred_format.label("preferred_format"),
        ContactLead.status.label("status"),
        ContactLead.assigned_to_id.label("assigned_to_id"),
        ContactLead.created_at.label("created_at"),
        ContactLead.next_follow_up_at.label("next_follow_up_at"),
        ContactLead.converted_student_id.label("converted_student_id"),
    )


def _tutoring_projection():
    """``TutoringRequest`` mapped onto the same columns.

    ``format`` stands in for ``interest`` because that is what a tutoring request is *about* —
    the administrator scanning the inbox wants to see "one_to_one", not the literal word
    "tutoring" repeated on every row.
    """
    return select(
        literal("tutoring").label("source"),
        TutoringRequest.id.label("id"),
        TutoringRequest.contact_name.label("name"),
        TutoringRequest.contact_email.label("email"),
        TutoringRequest.contact_phone.label("phone"),
        TutoringRequest.subject_slug.label("subject_slug"),
        TutoringRequest.grade.label("grade"),
        TutoringRequest.format.label("interest"),
        TutoringRequest.format.label("preferred_format"),
        TutoringRequest.status.label("status"),
        TutoringRequest.assigned_to_id.label("assigned_to_id"),
        TutoringRequest.created_at.label("created_at"),
        TutoringRequest.next_follow_up_at.label("next_follow_up_at"),
        TutoringRequest.converted_student_id.label("converted_student_id"),
    )


def _load(db, source: str, lead_id: int):
    """Fetch either kind of enquiry by (source, id)."""
    if source == "contact":
        row = db.get(ContactLead, lead_id)
    elif source == "tutoring":
        row = db.get(TutoringRequest, lead_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown lead source. Expected “contact” or “tutoring”.",
        )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enquiry not found")
    return row


def _display_name(row) -> str:
    return getattr(row, "name", None) or getattr(row, "contact_name", "") or ""


def _display_email(row) -> str | None:
    return getattr(row, "email", None) or getattr(row, "contact_email", None)


@router.get("")
def list_leads(
    db: DbSession,
    admin: CurrentAdmin,
    source: Annotated[LeadSource | None, Query()] = None,
    lead_status: Annotated[LeadStatus | None, Query(alias="status")] = None,
    open_only: Annotated[bool, Query()] = False,
    assigned_to_id: Annotated[int | None, Query()] = None,
    unassigned: Annotated[bool, Query()] = False,
    subject: Annotated[str | None, Query(max_length=60)] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    date_from: Annotated[dt.datetime | None, Query()] = None,
    date_to: Annotated[dt.datetime | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str, Query(pattern="^(created_at|name|status|follow_up)$")] = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    """One inbox over both enquiry tables, with filters applied to each side before the union."""
    contact_query = _contact_projection()
    tutoring_query = _tutoring_projection()

    def apply(query, model, name_col, email_col, phone_col):
        if lead_status:
            query = query.where(model.status == lead_status)
        elif open_only:
            query = query.where(model.status.in_(OPEN_STATUSES))
        if assigned_to_id is not None:
            query = query.where(model.assigned_to_id == assigned_to_id)
        if unassigned:
            query = query.where(model.assigned_to_id.is_(None))
        if subject:
            query = query.where(model.subject_slug == subject)
        if grade:
            query = query.where(model.grade == grade)
        if date_from:
            query = query.where(model.created_at >= date_from)
        if date_to:
            query = query.where(model.created_at <= date_to)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    name_col.ilike(pattern),
                    email_col.ilike(pattern),
                    phone_col.ilike(pattern),
                )
            )
        return query

    contact_query = apply(
        contact_query, ContactLead, ContactLead.name, ContactLead.email, ContactLead.phone
    )
    tutoring_query = apply(
        tutoring_query,
        TutoringRequest,
        TutoringRequest.contact_name,
        TutoringRequest.contact_email,
        TutoringRequest.contact_phone,
    )

    if source == "contact":
        combined = contact_query.subquery()
    elif source == "tutoring":
        combined = tutoring_query.subquery()
    else:
        combined = union_all(contact_query, tutoring_query).subquery()

    sort_column = {
        "created_at": combined.c.created_at,
        "name": combined.c.name,
        "status": combined.c.status,
        "follow_up": combined.c.next_follow_up_at,
    }[sort]
    ordered = select(combined).order_by(
        sort_column.desc() if order == "desc" else sort_column.asc()
    )

    total = db.scalar(select(func.count()).select_from(combined)) or 0
    rows = db.execute(
        ordered.offset((page - 1) * page_size).limit(page_size)
    ).mappings().all()

    # Resolve assignee names in one query rather than per row.
    assignee_ids = {row["assigned_to_id"] for row in rows if row["assigned_to_id"]}
    assignees = {}
    if assignee_ids:
        assignees = {
            user.id: user.full_name
            for user in db.scalars(select(User).where(User.id.in_(assignee_ids)))
        }

    items = [
        {
            **dict(row),
            "assigned_to_name": assignees.get(row["assigned_to_id"]),
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size else 0,
    }


@router.get("/stats")
def lead_stats(db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Counts per pipeline stage, for the inbox's filter chips."""
    counts: dict[str, int] = {str(value): 0 for value in LeadStatus}
    for model in (ContactLead, TutoringRequest):
        for row_status, in db.execute(select(model.status)).all():
            counts[row_status] = counts.get(row_status, 0) + 1
    return {
        "by_status": counts,
        "open": sum(counts.get(str(s), 0) for s in OPEN_STATUSES),
        "total": sum(counts.values()),
    }


@router.get("/{source}/{lead_id}")
def get_lead(
    source: LeadSource, lead_id: int, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    row = _load(db, source, lead_id)

    notes = db.scalars(
        select(LeadNote)
        .where(
            LeadNote.contact_lead_id == lead_id
            if source == "contact"
            else LeadNote.tutoring_request_id == lead_id
        )
        .order_by(LeadNote.created_at.desc())
    )

    assignee = db.get(User, row.assigned_to_id) if row.assigned_to_id else None
    converted = (
        db.scalar(
            select(StudentProfile)
            .where(StudentProfile.id == row.converted_student_id)
            .options(selectinload(StudentProfile.user))
        )
        if row.converted_student_id
        else None
    )

    common = {
        "source": source,
        "id": row.id,
        "name": _display_name(row),
        "email": _display_email(row),
        "status": row.status,
        "assigned_to_id": row.assigned_to_id,
        "assigned_to_name": assignee.full_name if assignee else None,
        "admin_note": row.admin_note,
        "consultation_result": row.consultation_result,
        "last_contacted_at": row.last_contacted_at,
        "next_follow_up_at": row.next_follow_up_at,
        "converted_student_id": row.converted_student_id,
        "converted_student_name": (
            converted.user.full_name if converted and converted.user else None
        ),
        "converted_at": row.converted_at,
        "created_at": row.created_at,
        "subject_slug": row.subject_slug,
        "grade": row.grade,
        "parent_name": row.parent_name,
        "parent_phone": row.parent_phone,
        "source_page": row.source_page,
        "notes": [
            {
                "id": note.id,
                "body": note.body,
                "kind": note.kind,
                "author_id": note.author_id,
                "author_name": note.author_name,
                "created_at": note.created_at,
            }
            for note in notes
        ],
    }

    if source == "contact":
        course = db.get(Course, row.interested_course_id) if row.interested_course_id else None
        product = (
            db.get(TutoringProduct, row.interested_product_id)
            if row.interested_product_id
            else None
        )
        common.update(
            {
                "phone": row.phone,
                "interest": row.interest,
                "message": row.message,
                "student_name": row.student_name,
                "school": row.school,
                "preferred_format": row.preferred_format,
                "preferred_delivery": row.preferred_delivery,
                "preferred_schedule": row.preferred_schedule,
                "interested_course": (
                    {"id": course.id, "title": course.title} if course else None
                ),
                "interested_product": (
                    {"id": product.id, "name": product.name} if product else None
                ),
            }
        )
    else:
        teacher = (
            db.scalar(
                select(TeacherProfile)
                .where(TeacherProfile.id == row.preferred_teacher_id)
                .options(selectinload(TeacherProfile.user))
            )
            if row.preferred_teacher_id
            else None
        )
        common.update(
            {
                "phone": row.contact_phone,
                "interest": row.format,
                "message": row.goals,
                "student_name": row.contact_student_name,
                "preferred_format": row.format,
                "preferred_delivery": row.delivery_mode,
                "preferred_slots": row.preferred_slots or [],
                "sessions_requested": row.sessions_requested,
                "preferred_teacher": (
                    {
                        "id": teacher.id,
                        "name": teacher.user.full_name if teacher.user else None,
                    }
                    if teacher
                    else None
                ),
                "assigned_class_group_id": row.assigned_class_group_id,
            }
        )
    return common


@router.patch("/{source}/{lead_id}")
def update_lead(
    source: LeadSource,
    lead_id: int,
    payload: LeadStatusUpdate,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    """Change stage, owner, follow-up date or result.

    A status change also writes a timeline note automatically, so the history reads as a story
    rather than as a field that silently changed value at some point.
    """
    row = _load(db, source, lead_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"mark_contacted"})

    if payload.assigned_to_id is not None:
        assignee = get_or_404(db, User, payload.assigned_to_id, "Staff member")
        if assignee.role not in {UserRole.ADMIN, UserRole.TEACHER}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enquiries can only be assigned to staff (teacher or administrator)",
            )

    previous_status = row.status
    for key, value in fields.items():
        setattr(row, key, value)

    if payload.mark_contacted or (
        payload.status and payload.status != LeadStatus.NEW and previous_status == LeadStatus.NEW
    ):
        row.last_contacted_at = dt.datetime.now(dt.UTC)

    note_target = (
        {"contact_lead_id": lead_id} if source == "contact" else {"tutoring_request_id": lead_id}
    )
    if payload.status and payload.status != previous_status:
        db.add(
            LeadNote(
                **note_target,
                author_id=admin.id,
                author_name=admin.full_name,
                kind="status_change",
                body=f"Status changed from {previous_status} to {payload.status}",
            )
        )
    if payload.assigned_to_id is not None:
        assignee = db.get(User, payload.assigned_to_id)
        db.add(
            LeadNote(
                **note_target,
                author_id=admin.id,
                author_name=admin.full_name,
                kind="status_change",
                body=f"Assigned to {assignee.full_name if assignee else payload.assigned_to_id}",
            )
        )

    record_audit(
        db, admin, "update", f"lead:{source}", lead_id,
        f"Updated enquiry from {_display_name(row)}",
        {k: str(v) for k, v in fields.items()},
    )
    db.commit()
    return get_lead(source, lead_id, db, admin)


@router.post("/{source}/{lead_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(
    source: LeadSource,
    lead_id: int,
    payload: LeadNoteIn,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    _load(db, source, lead_id)
    if payload.kind not in NOTE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown note kind. Expected one of: {', '.join(sorted(NOTE_KINDS))}",
        )

    note = LeadNote(
        contact_lead_id=lead_id if source == "contact" else None,
        tutoring_request_id=lead_id if source == "tutoring" else None,
        author_id=admin.id,
        author_name=admin.full_name,
        body=payload.body,
        kind=payload.kind,
    )
    db.add(note)

    # Logging a call or an email is itself evidence of contact.
    if payload.kind in {"call", "email", "meeting"}:
        row = _load(db, source, lead_id)
        row.last_contacted_at = dt.datetime.now(dt.UTC)

    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "body": note.body,
        "kind": note.kind,
        "author_name": note.author_name,
        "created_at": note.created_at,
    }


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    note = get_or_404(db, LeadNote, note_id, "Note")
    db.delete(note)
    db.commit()


@router.post("/{source}/{lead_id}/convert", status_code=status.HTTP_201_CREATED)
def convert_lead(
    source: LeadSource,
    lead_id: int,
    payload: ConvertLeadRequest,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    """Turn an enquiry into a student account, and optionally an enrollment.

    This is the step that closes the loop from "a parent filled in a form" to "a child is in a
    class", and it is why the enquiry tables carry a ``converted_student_id`` — so the same family
    enquiring twice is visible rather than looking like two unrelated leads.
    """
    row = _load(db, source, lead_id)

    if row.converted_student_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This enquiry has already been converted",
        )

    temporary_password: str | None = None

    if payload.student_id is not None:
        profile = db.scalar(
            select(StudentProfile)
            .where(StudentProfile.id == payload.student_id)
            .options(selectinload(StudentProfile.user))
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
            )
    else:
        email = str(payload.email or _display_email(row) or "").lower()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An email address is required to create a student account",
            )

        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            # Reuse rather than reject: the family already has an account, which is exactly the
            # situation this endpoint exists to notice.
            profile = db.scalar(
                select(StudentProfile)
                .where(StudentProfile.user_id == existing.id)
                .options(selectinload(StudentProfile.user))
            )
            if profile is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"{email} is already registered as a {existing.role} account, so it "
                        "cannot be converted into a student."
                    ),
                )
        else:
            temporary_password = f"HTE-{secrets.token_urlsafe(8)}"
            user = User(
                email=email,
                password_hash=hash_password(temporary_password),
                full_name=payload.full_name or _display_name(row) or email,
                role=UserRole.STUDENT,
                phone=payload.phone or getattr(row, "phone", None)
                or getattr(row, "contact_phone", None),
                is_verified=True,
                locale="vi",
            )
            db.add(user)
            db.flush()
            profile = StudentProfile(
                user_id=user.id,
                grade=payload.grade or row.grade or 6,
                school=payload.school or getattr(row, "school", None),
            )
            db.add(profile)
            db.flush()

    enrollment_id = None
    if payload.class_group_id is not None:
        group = get_or_404(db, ClassGroup, payload.class_group_id, "Class")
        existing_enrollment = db.scalar(
            select(ClassEnrollment).where(
                ClassEnrollment.class_group_id == group.id,
                ClassEnrollment.student_id == profile.id,
            )
        )
        if existing_enrollment is not None:
            enrollment_id = existing_enrollment.id
        else:
            enrollment = ClassEnrollment(
                class_group_id=group.id,
                student_id=profile.id,
                status=EnrollmentStatus.CONFIRMED,
                notes=payload.enrollment_notes,
                preferred_schedule=getattr(row, "preferred_schedule", None),
                requested_format=getattr(row, "preferred_format", None)
                or getattr(row, "format", None),
                approved_by_id=admin.id,
                approved_at=dt.datetime.now(dt.UTC),
                enrolled_at=dt.datetime.now(dt.UTC),
            )
            db.add(enrollment)
            db.flush()
            enrollment_id = enrollment.id

    row.converted_student_id = profile.id
    row.converted_at = dt.datetime.now(dt.UTC)
    row.status = LeadStatus.ENROLLED

    note_target = (
        {"contact_lead_id": lead_id} if source == "contact" else {"tutoring_request_id": lead_id}
    )
    db.add(
        LeadNote(
            **note_target,
            author_id=admin.id,
            author_name=admin.full_name,
            kind="status_change",
            body=(
                f"Converted to student #{profile.id}"
                + (f" and enrolled in class #{payload.class_group_id}" if enrollment_id else "")
            ),
        )
    )
    record_audit(
        db, admin, "convert", f"lead:{source}", lead_id,
        f"Converted enquiry from {_display_name(row)} into student #{profile.id}",
        {"student_id": profile.id, "enrollment_id": enrollment_id},
    )
    db.commit()
    db.refresh(profile)

    return {
        "lead_id": lead_id,
        "source": source,
        "student_id": profile.id,
        "student_name": profile.user.full_name if profile.user else None,
        "student_email": profile.user.email if profile.user else None,
        "enrollment_id": enrollment_id,
        "temporary_password": temporary_password,
        "created_account": temporary_password is not None,
    }


@router.delete("/{source}/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    source: LeadSource, lead_id: int, db: DbSession, admin: CurrentAdmin
) -> None:
    row = _load(db, source, lead_id)
    name = _display_name(row)
    db.delete(row)
    record_audit(
        db, admin, "delete", f"lead:{source}", lead_id, f"Deleted enquiry from {name}"
    )
    db.commit()
