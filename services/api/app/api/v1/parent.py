"""Parent dashboard.

Parents are the paying customers, so this view answers the questions they actually ask: is my
child improving, are they turning up, what are they struggling with, and what have I paid for.

Every endpoint here is scoped to the parent's linked children. A parent can never read another
family's data — the link table is the authorisation boundary and is checked on every call.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.adaptive import MASTERY_THRESHOLD
from app.core.deps import CurrentParent, CurrentUser, DbSession
from app.models import (
    Attempt,
    Attendance,
    ClassEnrollment,
    ClassGroup,
    Course,
    EnrollmentStatus,
    LiveSession,
    Order,
    ParentStudentLink,
    SessionStatus,
    Skill,
    StudentProfile,
    StudentSkillMastery,
    Subject,
    TeacherProfile,
    Topic,
    Unit,
    User,
)
from app.services.practice import summarise_student

router = APIRouter(prefix="/parent", tags=["parent"])


class ChildSummary(BaseModel):
    student_id: int
    name: str
    grade: int
    avatar_url: str | None = None
    xp_total: int
    level: int
    streak_days: int
    average_mastery_percent: int
    skills_mastered: int
    attempts: int
    accuracy: float | None = None
    last_active_at: dt.datetime | None = None


class LinkChildRequest(BaseModel):
    student_email: EmailStr
    relationship_label: str = Field(default="parent", max_length=40)


def _linked_student_ids(db, parent_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ParentStudentLink.student_id).where(ParentStudentLink.parent_id == parent_id)
        )
    )


def _require_linked(db, parent_id: int, student_id: int) -> StudentProfile:
    if student_id not in _linked_student_ids(db, parent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That student is not linked to your account",
        )
    student = db.get(StudentProfile, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.get("/children", response_model=list[ChildSummary])
def my_children(db: DbSession, parent: CurrentParent) -> list[ChildSummary]:
    student_ids = _linked_student_ids(db, parent.id)
    if not student_ids:
        return []

    students = list(
        db.scalars(
            select(StudentProfile)
            .where(StudentProfile.id.in_(student_ids))
            .options(selectinload(StudentProfile.user))
        ).unique()
    )

    summaries = []
    for student in students:
        stats = summarise_student(db, student.id)
        last_active = db.scalar(
            select(func.max(Attempt.created_at)).where(Attempt.student_id == student.id)
        )
        summaries.append(
            ChildSummary(
                student_id=student.id,
                name=student.user.full_name if student.user else "",
                grade=student.grade,
                avatar_url=student.user.avatar_url if student.user else None,
                xp_total=student.xp_total,
                level=student.level,
                streak_days=student.streak_days,
                average_mastery_percent=int(round(stats["average_mastery"] * 100)),
                skills_mastered=stats["skills_mastered"],
                attempts=stats["total_attempts"],
                accuracy=stats["accuracy"],
                last_active_at=last_active,
            )
        )
    return summaries


@router.post("/children/link", status_code=status.HTTP_201_CREATED)
def link_child(
    payload: LinkChildRequest, db: DbSession, parent: CurrentParent
) -> dict[str, Any]:
    """Link an existing student account to this parent by email.

    Kept deliberately simple for now: the centre creates family accounts during onboarding, so
    self-service linking is a convenience rather than the primary path. A production deployment
    should add a confirmation step (email or centre approval) before the link is active — noted
    as a TODO in docs/ARCHITECTURE.md rather than silently accepted as safe.
    """
    user = db.scalar(
        select(User)
        .where(func.lower(User.email) == str(payload.student_email).lower())
        .options(selectinload(User.student_profile))
    )
    if user is None or user.student_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No student account with that email"
        )

    existing = db.scalar(
        select(ParentStudentLink).where(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.student_id == user.student_profile.id,
        )
    )
    if existing is not None:
        return {"linked": True, "already_linked": True, "student_id": user.student_profile.id}

    db.add(
        ParentStudentLink(
            parent_id=parent.id,
            student_id=user.student_profile.id,
            relationship_label=payload.relationship_label,
        )
    )
    db.commit()
    return {"linked": True, "already_linked": False, "student_id": user.student_profile.id}


@router.get("/children/{student_id}/progress")
def child_progress(student_id: int, db: DbSession, parent: CurrentParent) -> dict[str, Any]:
    """Detailed progress for one child: subject mastery, weak skills, recent work."""
    student = _require_linked(db, parent.id, student_id)

    subject_rows = db.execute(
        select(
            Subject.slug, Subject.name, Subject.color,
            func.avg(StudentSkillMastery.mastery_probability),
            func.count(StudentSkillMastery.id),
        )
        .join(Course, Course.subject_id == Subject.id)
        .join(Unit, Unit.course_id == Course.id)
        .join(Topic, Topic.unit_id == Unit.id)
        .join(Skill, Skill.topic_id == Topic.id)
        .join(StudentSkillMastery, StudentSkillMastery.skill_id == Skill.id)
        .where(StudentSkillMastery.student_id == student_id)
        .group_by(Subject.id, Subject.slug, Subject.name, Subject.color)
    ).all()

    weak = list(
        db.scalars(
            select(StudentSkillMastery)
            .where(
                StudentSkillMastery.student_id == student_id,
                StudentSkillMastery.attempts > 0,
                StudentSkillMastery.mastery_probability < MASTERY_THRESHOLD,
            )
            .order_by(StudentSkillMastery.mastery_probability)
            .limit(6)
            .options(selectinload(StudentSkillMastery.skill))
        )
    )

    recent = list(
        db.scalars(
            select(Attempt)
            .where(Attempt.student_id == student_id)
            .order_by(Attempt.created_at.desc())
            .limit(10)
            .options(selectinload(Attempt.skill))
        )
    )

    return {
        "student": {
            "id": student.id,
            "name": student.user.full_name if student.user else "",
            "grade": student.grade,
            "xp_total": student.xp_total,
            "level": student.level,
            "streak_days": student.streak_days,
        },
        "stats": summarise_student(db, student_id),
        "subjects": [
            {
                "slug": slug, "name": name, "color": color,
                "mastery_percent": int(round(float(avg or 0) * 100)),
                "skills_tracked": count,
            }
            for slug, name, color, avg, count in subject_rows
        ],
        "weak_skills": [
            {
                "skill_name": row.skill.name if row.skill else "",
                "skill_slug": row.skill.slug if row.skill else "",
                "mastery_percent": int(round(row.mastery_probability * 100)),
                "attempts": row.attempts,
                "accuracy": round(row.correct / row.attempts, 3) if row.attempts else None,
            }
            for row in weak
        ],
        "recent_work": [
            {
                "skill_name": a.skill.name if a.skill else "",
                "is_correct": a.is_correct,
                "created_at": a.created_at,
            }
            for a in recent
        ],
    }


@router.get("/children/{student_id}/attendance")
def child_attendance(student_id: int, db: DbSession, parent: CurrentParent) -> dict[str, Any]:
    _require_linked(db, parent.id, student_id)

    rows = list(
        db.execute(
            select(Attendance, LiveSession, ClassGroup)
            .join(LiveSession, Attendance.session_id == LiveSession.id)
            .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
            .where(Attendance.student_id == student_id)
            .order_by(LiveSession.starts_at.desc())
            .limit(50)
        ).all()
    )

    present = sum(1 for a, _, _ in rows if a.status == "present")
    return {
        "total_sessions": len(rows),
        "present": present,
        "attendance_rate": round(present / len(rows), 3) if rows else None,
        "records": [
            {
                "session_title": live.title,
                "class_name": group.name,
                "starts_at": live.starts_at,
                "status": attendance.status,
                "minutes_attended": attendance.minutes_attended,
                "teacher_note": attendance.teacher_note,
            }
            for attendance, live, group in rows
        ],
    }


@router.get("/children/{student_id}/schedule")
def child_schedule(student_id: int, db: DbSession, parent: CurrentParent) -> list[dict[str, Any]]:
    _require_linked(db, parent.id, student_id)
    now = dt.datetime.now(dt.UTC)

    rows = list(
        db.execute(
            select(LiveSession, ClassGroup)
            .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
            .join(ClassEnrollment, ClassEnrollment.class_group_id == ClassGroup.id)
            .where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.status == EnrollmentStatus.ACTIVE,
                LiveSession.starts_at >= now - dt.timedelta(days=1),
                LiveSession.status != SessionStatus.CANCELLED,
            )
            .order_by(LiveSession.starts_at)
            .limit(20)
            .options(selectinload(ClassGroup.teacher).selectinload(TeacherProfile.user))
        ).all()
    )
    return [
        {
            "session_id": live.id,
            "title": live.title,
            "class_name": group.name,
            "starts_at": live.starts_at,
            "ends_at": live.ends_at,
            "teacher_name": (
                group.teacher.user.full_name if group.teacher and group.teacher.user else None
            ),
            "location": group.location,
            "delivery_mode": group.delivery_mode,
        }
        for live, group in rows
    ]


@router.get("/payments")
def payment_history(
    db: DbSession, user: CurrentUser, parent: CurrentParent
) -> list[dict[str, Any]]:
    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .options(selectinload(Order.items), selectinload(Order.payments))
    ).unique()

    return [
        {
            "id": order.id,
            "reference": order.reference,
            "status": order.status,
            "total": order.total,
            "currency": order.currency,
            "placed_at": order.placed_at,
            "items": [
                {"description": i.description, "line_total": i.line_total, "quantity": i.quantity}
                for i in order.items
            ],
            "payments": [
                {"amount": p.amount, "status": p.status, "paid_at": p.paid_at,
                 "provider": p.provider}
                for p in order.payments
            ],
        }
        for order in orders
    ]
