"""Student management: search, profile, progress, results, attendance and account actions."""

from __future__ import annotations

import datetime as dt
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
    paginate,
    record_audit,
)
from app.core.deps import RequestLocale
from app.core.i18n import localise
from app.core.security import hash_password
from app.models import (
    AssignmentSubmission,
    Attempt,
    Attendance,
    ClassEnrollment,
    ClassGroup,
    ContactLead,
    Course,
    CourseEnrollment,
    LiveSession,
    Order,
    ParentProfile,
    ParentStudentLink,
    PracticeSession,
    Skill,
    StudentProfile,
    StudentSkillMastery,
    TutoringRequest,
    User,
    UserRole,
)

router = APIRouter(prefix="/students", tags=["admin:students"])

# A skill counts as mastered once BKT puts the probability above this. Same threshold the student
# dashboard uses, kept in one place so the two screens never disagree about a student's progress.
MASTERY_THRESHOLD = 0.85


class StudentCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    grade: int = Field(default=6, ge=1, le=12)
    school: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    date_of_birth: dt.date | None = None
    locale: str = Field(default="vi", max_length=8)


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    grade: int | None = Field(default=None, ge=1, le=12)
    school: str | None = Field(default=None, max_length=200)
    date_of_birth: dt.date | None = None
    locale: str | None = Field(default=None, max_length=8)
    learning_goals: list[str] | None = None
    avatar_url: str | None = Field(default=None, max_length=500)


class SetActiveRequest(BaseModel):
    is_active: bool


class ResetPasswordRequest(BaseModel):
    """A new password may be supplied, or omitted to have one generated.

    Generating is the safer default: it means staff never have to invent a password, and the
    temporary one is shown exactly once in the response rather than stored anywhere.
    """

    password: str | None = Field(default=None, min_length=8, max_length=72)


def _student_row(profile: StudentProfile) -> dict[str, Any]:
    user = profile.user
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": user.full_name if user else None,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "avatar_url": user.avatar_url if user else None,
        "is_active": user.is_active if user else False,
        "is_verified": user.is_verified if user else False,
        "locale": user.locale if user else "vi",
        "grade": profile.grade,
        "school": profile.school,
        "date_of_birth": profile.date_of_birth,
        "xp_total": profile.xp_total,
        "level": profile.level,
        "streak_days": profile.streak_days,
        "last_activity_date": profile.last_activity_date,
        "learning_goals": profile.learning_goals or [],
        "created_at": profile.created_at,
        "last_login_at": user.last_login_at if user else None,
    }


@router.get("")
def list_students(
    db: DbSession,
    admin: CurrentAdmin,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    active: Annotated[bool | None, Query()] = None,
    class_id: Annotated[int | None, Query()] = None,
    course_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    # Explicit join to User so name/email search and the active filter work without a cross join.
    query = (
        select(StudentProfile)
        .join(User, StudentProfile.user_id == User.id)
        .options(selectinload(StudentProfile.user))
    )
    if grade:
        query = query.where(StudentProfile.grade == grade)
    if active is not None:
        query = query.where(User.is_active.is_(active))
    if class_id:
        query = query.where(
            StudentProfile.id.in_(
                select(ClassEnrollment.student_id).where(
                    ClassEnrollment.class_group_id == class_id
                )
            )
        )
    if course_id:
        query = query.where(
            StudentProfile.id.in_(
                select(CourseEnrollment.student_id).where(
                    CourseEnrollment.course_id == course_id
                )
            )
        )
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                StudentProfile.school.ilike(pattern),
            )
        )

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        StudentProfile,
        params,
        {
            "name": User.full_name,
            "email": User.email,
            "grade": StudentProfile.grade,
            "xp": StudentProfile.xp_total,
            "created_at": StudentProfile.created_at,
            "last_activity": StudentProfile.last_activity_date,
            "_default": StudentProfile.created_at,
        },
    )
    rows, total = paginate(db, query, params)
    return build_page([_student_row(row) for row in rows], total, params)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Register a student on their behalf — the walk-in enrolment path.

    Returns a temporary password when one was generated, because the office needs something to
    hand the parent. It is never persisted in readable form.
    """
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
        role=UserRole.STUDENT,
        phone=payload.phone,
        locale=payload.locale,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        grade=payload.grade,
        school=payload.school,
        date_of_birth=payload.date_of_birth,
    )
    db.add(profile)
    db.flush()

    record_audit(
        db, admin, "create", "student", profile.id,
        f"Created student account for {payload.full_name}",
    )
    db.commit()
    db.refresh(profile)

    result = _student_row(profile)
    if payload.password is None:
        result["temporary_password"] = temporary_password
    return result


@router.get("/{student_id}")
def get_student(
    student_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    """Everything about one student, on one screen."""
    profile = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    data = _student_row(profile)

    # --- classes and courses ---------------------------------------------------------
    class_rows = db.execute(
        select(ClassEnrollment, ClassGroup)
        .join(ClassGroup, ClassEnrollment.class_group_id == ClassGroup.id)
        .where(ClassEnrollment.student_id == student_id)
        .order_by(ClassEnrollment.created_at.desc())
    ).all()
    data["classes"] = [
        {
            "enrollment_id": enrollment.id,
            "class_id": group.id,
            "class_name": group.name,
            "format": group.format,
            "delivery_mode": group.delivery_mode,
            "status": enrollment.status,
            "payment_status": enrollment.payment_status,
            "enrolled_at": enrollment.enrolled_at,
            "created_at": enrollment.created_at,
        }
        for enrollment, group in class_rows
    ]

    course_rows = db.execute(
        select(CourseEnrollment, Course)
        .join(Course, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.student_id == student_id)
    ).all()
    data["courses"] = [
        {
            "course_id": course.id,
            "title": localise(course, "title", locale),
            "slug": course.slug,
            "grade": course.grade,
            "is_active": enrollment.is_active,
            "last_activity_at": enrollment.last_activity_at,
        }
        for enrollment, course in course_rows
    ]

    # --- learning progress -----------------------------------------------------------
    mastery_rows = db.execute(
        select(StudentSkillMastery, Skill)
        .join(Skill, StudentSkillMastery.skill_id == Skill.id)
        .where(StudentSkillMastery.student_id == student_id)
        .order_by(StudentSkillMastery.mastery_probability.desc())
    ).all()
    data["mastery"] = [
        {
            "skill_id": skill.id,
            "skill_name": localise(skill, "name", locale),
            "skill_slug": skill.slug,
            "mastery": round(mastery.mastery_probability, 4),
            "attempts": mastery.attempts,
            "correct": mastery.correct,
            "incorrect": mastery.incorrect,
            "accuracy": mastery.recent_accuracy,
            "last_practiced_at": mastery.last_practiced_at,
            "is_mastered": mastery.mastery_probability >= MASTERY_THRESHOLD,
        }
        for mastery, skill in mastery_rows
    ]

    tracked = len(mastery_rows)
    mastered = sum(1 for m, _ in mastery_rows if m.mastery_probability >= MASTERY_THRESHOLD)
    total_attempts = sum(m.attempts for m, _ in mastery_rows)
    total_correct = sum(m.correct for m, _ in mastery_rows)
    data["stats"] = {
        "skills_tracked": tracked,
        "skills_mastered": mastered,
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "accuracy": round(total_correct / total_attempts, 4) if total_attempts else None,
        "average_mastery": (
            round(sum(m.mastery_probability for m, _ in mastery_rows) / tracked, 4)
            if tracked
            else 0.0
        ),
    }

    # --- submitted work --------------------------------------------------------------
    attempt_rows = db.execute(
        select(Attempt, Skill)
        .join(Skill, Attempt.skill_id == Skill.id)
        .where(Attempt.student_id == student_id)
        .order_by(Attempt.created_at.desc())
        .limit(50)
    ).all()
    data["recent_attempts"] = [
        {
            "id": attempt.id,
            "skill_name": localise(skill, "name", locale),
            "question_id": attempt.question_id,
            "is_correct": attempt.is_correct,
            "score": attempt.score,
            "hints_used": attempt.hints_used,
            "time_spent_seconds": attempt.time_spent_seconds,
            "created_at": attempt.created_at,
        }
        for attempt, skill in attempt_rows
    ]

    sessions = db.scalars(
        select(PracticeSession)
        .where(PracticeSession.student_id == student_id)
        .order_by(PracticeSession.created_at.desc())
        .limit(20)
    )
    data["practice_sessions"] = [
        {
            "id": s.id,
            "mode": s.mode,
            "questions_answered": s.questions_answered,
            "questions_correct": s.questions_correct,
            "xp_earned": s.xp_earned,
            "completed_at": s.completed_at,
            "created_at": s.created_at,
        }
        for s in sessions
    ]

    submissions = db.scalars(
        select(AssignmentSubmission)
        .where(AssignmentSubmission.student_id == student_id)
        .options(selectinload(AssignmentSubmission.assignment))
        .order_by(AssignmentSubmission.created_at.desc())
        .limit(30)
    ).unique()
    data["assignments"] = [
        {
            "id": sub.id,
            "assignment_id": sub.assignment_id,
            "title": sub.assignment.title if sub.assignment else None,
            "status": sub.status,
            "score_percent": sub.score_percent,
            "submitted_at": sub.submitted_at,
            "due_at": sub.assignment.due_at if sub.assignment else None,
            "teacher_feedback": sub.teacher_feedback,
        }
        for sub in submissions
    ]

    # --- attendance ------------------------------------------------------------------
    attendance_rows = db.execute(
        select(Attendance, LiveSession, ClassGroup)
        .join(LiveSession, Attendance.session_id == LiveSession.id)
        .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
        .where(Attendance.student_id == student_id)
        .order_by(LiveSession.starts_at.desc())
        .limit(50)
    ).all()
    data["attendance"] = [
        {
            "id": record.id,
            "session_title": session.title,
            "class_name": group.name,
            "starts_at": session.starts_at,
            "status": record.status,
            "minutes_attended": record.minutes_attended,
            "teacher_note": record.teacher_note,
        }
        for record, session, group in attendance_rows
    ]
    present = sum(1 for r, _, _ in attendance_rows if r.status == "present")
    data["attendance_rate"] = (
        round(present / len(attendance_rows), 4) if attendance_rows else None
    )

    # --- guardians and enquiry history ------------------------------------------------
    parent_rows = db.execute(
        select(ParentStudentLink, ParentProfile, User)
        .join(ParentProfile, ParentStudentLink.parent_id == ParentProfile.id)
        .join(User, ParentProfile.user_id == User.id)
        .where(ParentStudentLink.student_id == student_id)
    ).all()
    data["guardians"] = [
        {
            "parent_id": parent.id,
            "name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "relationship": link.relationship_label,
        }
        for link, parent, user in parent_rows
    ]

    # Match enquiries either by explicit conversion link or by the email they were submitted
    # under, so consultation history survives a lead that was converted manually.
    email = profile.user.email if profile.user else None
    lead_match = [ContactLead.converted_student_id == student_id]
    request_match = [
        TutoringRequest.converted_student_id == student_id,
        TutoringRequest.student_id == student_id,
    ]
    if email:
        lead_match.append(func.lower(ContactLead.email) == email.lower())
        request_match.append(func.lower(TutoringRequest.contact_email) == email.lower())

    leads = db.scalars(
        select(ContactLead).where(or_(*lead_match)).order_by(ContactLead.created_at.desc())
    )
    requests = db.scalars(
        select(TutoringRequest)
        .where(or_(*request_match))
        .order_by(TutoringRequest.created_at.desc())
    )
    data["consultation_history"] = [
        {"id": lead.id, "source": "contact", "interest": lead.interest, "status": lead.status,
         "created_at": lead.created_at, "message": lead.message}
        for lead in leads
    ] + [
        {"id": req.id, "source": "tutoring", "interest": req.format, "status": req.status,
         "created_at": req.created_at, "message": req.goals}
        for req in requests
    ]

    orders = db.scalars(
        select(Order).where(Order.student_id == student_id).order_by(Order.created_at.desc())
    )
    data["orders"] = [
        {"id": o.id, "reference": o.reference, "status": o.status, "total": o.total,
         "placed_at": o.placed_at}
        for o in orders
    ]

    return data


@router.patch("/{student_id}")
def update_student(
    student_id: int, payload: StudentUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    profile = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    fields = payload.model_dump(exclude_unset=True)
    user_fields = {"full_name", "email", "phone", "locale", "avatar_url"}

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

    record_audit(
        db, admin, "update", "student", profile.id,
        f"Updated student {profile.user.full_name if profile.user else student_id}",
        diff_fields(before, {k: v for k, v in fields.items()}),
    )
    db.commit()
    db.refresh(profile)
    return _student_row(profile)


@router.post("/{student_id}/set-active")
def set_student_active(
    student_id: int, payload: SetActiveRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    profile = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    if profile is None or profile.user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    profile.user.is_active = payload.is_active
    record_audit(
        db, admin, "activate" if payload.is_active else "deactivate", "student", profile.id,
        f"{'Activated' if payload.is_active else 'Deactivated'} {profile.user.full_name}",
    )
    db.commit()
    db.refresh(profile)
    return _student_row(profile)


@router.post("/{student_id}/reset-password")
def reset_student_password(
    student_id: int, payload: ResetPasswordRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Set a new password. The existing one is never readable, only replaceable."""
    profile = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    if profile is None or profile.user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    new_password = payload.password or f"HTE-{secrets.token_urlsafe(8)}"
    profile.user.password_hash = hash_password(new_password)
    record_audit(
        db, admin, "reset_password", "student", profile.id,
        f"Reset password for {profile.user.full_name}",
    )
    db.commit()
    return {
        "student_id": profile.id,
        # Echoed only when we generated it, and only in this response.
        "temporary_password": new_password if payload.password is None else None,
        "message": "Password updated. Share the temporary password securely.",
    }


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    """Permanently delete a student and all their learning history.

    Deactivation is almost always the right action instead, and the UI says so — but a genuine
    data-erasure request needs a real delete, so this exists and cascades honestly.
    """
    profile = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .options(selectinload(StudentProfile.user))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    name = profile.user.full_name if profile.user else str(student_id)
    attempts = (
        db.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.student_id == student_id)
        )
        or 0
    )
    user = profile.user
    db.delete(profile)
    if user is not None:
        db.delete(user)
    record_audit(
        db, admin, "delete", "student", student_id,
        f"Deleted student {name}", {"attempts_destroyed": attempts},
    )
    db.commit()
