"""The admin landing page: headline counts, work queues and recent activity."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import CurrentAdmin, DbSession
from app.models import (
    Attempt,
    AuditLog,
    ClassEnrollment,
    ClassGroup,
    ContactLead,
    Course,
    EnrollmentStatus,
    LeadStatus,
    Lesson,
    LiveSession,
    Order,
    OrderStatus,
    Question,
    ReviewStatus,
    SessionStatus,
    StudentProfile,
    TeacherProfile,
    TutoringProduct,
    TutoringRequest,
    User,
    UserRole,
)

router = APIRouter()

# Statuses that mean "someone still has to do something about this".
OPEN_LEAD_STATUSES = (
    LeadStatus.NEW,
    LeadStatus.CONTACTED,
    LeadStatus.CONSULTING,
    LeadStatus.INTERESTED,
)


@router.get("/overview")
def overview(db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Counts for the dashboard tiles.

    Kept as one endpoint rather than a dozen: the dashboard needs all of it at once, and twelve
    round trips on every page load would be slower than one query batch for no benefit.
    """

    def count(model, *conditions) -> int:
        query = select(func.count()).select_from(model)
        if conditions:
            query = query.where(*conditions)
        return db.scalar(query) or 0

    revenue = (
        db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status == OrderStatus.PAID
            )
        )
        or 0
    )

    now = dt.datetime.now(dt.UTC)
    week_ago = now - dt.timedelta(days=7)

    # Explicit join: filtering StudentProfile on a User column via a bare WHERE would leave the
    # two tables cross-joined, and the count would be the product of the two row counts.
    active_students = (
        db.scalar(
            select(func.count())
            .select_from(StudentProfile)
            .join(User, StudentProfile.user_id == User.id)
            .where(User.is_active.is_(True))
        )
        or 0
    )

    return {
        # people
        "students": count(StudentProfile),
        "active_students": active_students,
        "teachers": count(TeacherProfile),
        "parents": count(User, User.role == UserRole.PARENT),
        "new_students_this_week": count(StudentProfile, StudentProfile.created_at >= week_ago),
        # content
        "courses": count(Course),
        "published_courses": count(Course, Course.is_published.is_(True)),
        "lessons": count(Lesson),
        "published_lessons": count(Lesson, Lesson.status == ReviewStatus.PUBLISHED),
        "draft_lessons": count(Lesson, Lesson.status == ReviewStatus.DRAFT),
        "exercises": count(Question),
        "published_exercises": count(Question, Question.status == ReviewStatus.PUBLISHED),
        "pending_review_questions": count(
            Question, Question.status == ReviewStatus.PENDING_REVIEW
        ),
        "programs": count(TutoringProduct),
        # operations
        "classes": count(ClassGroup),
        "active_enrollments": count(
            ClassEnrollment, ClassEnrollment.status == EnrollmentStatus.ACTIVE
        ),
        "pending_enrollments": count(
            ClassEnrollment, ClassEnrollment.status == EnrollmentStatus.PENDING
        ),
        "pending_consultations": count(ContactLead, ContactLead.status.in_(OPEN_LEAD_STATUSES)),
        "new_consultations": count(ContactLead, ContactLead.status == LeadStatus.NEW),
        "pending_registrations": count(
            TutoringRequest, TutoringRequest.status.in_(OPEN_LEAD_STATUSES)
        ),
        "new_registrations": count(TutoringRequest, TutoringRequest.status == LeadStatus.NEW),
        "upcoming_classes": count(
            LiveSession,
            LiveSession.starts_at >= now,
            LiveSession.status == SessionStatus.SCHEDULED,
        ),
        "orders_awaiting_payment": count(Order, Order.status == OrderStatus.AWAITING_PAYMENT),
        "revenue_vnd": int(revenue),
    }


@router.get("/dashboard")
def dashboard(db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Work queues and activity feeds shown beneath the tiles."""
    now = dt.datetime.now(dt.UTC)

    upcoming = db.execute(
        select(LiveSession, ClassGroup)
        .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
        .where(LiveSession.starts_at >= now, LiveSession.status != SessionStatus.CANCELLED)
        .order_by(LiveSession.starts_at.asc())
        .limit(8)
    ).all()

    recent_students = db.scalars(
        select(StudentProfile)
        .options(selectinload(StudentProfile.user))
        .order_by(StudentProfile.created_at.desc())
        .limit(8)
    ).unique()

    recent_leads = db.scalars(
        select(ContactLead).order_by(ContactLead.created_at.desc()).limit(6)
    )
    recent_requests = db.scalars(
        select(TutoringRequest).order_by(TutoringRequest.created_at.desc()).limit(6)
    )

    pending_enrollments = db.scalars(
        select(ClassEnrollment)
        .where(ClassEnrollment.status == EnrollmentStatus.PENDING)
        .options(
            selectinload(ClassEnrollment.student).selectinload(StudentProfile.user),
            selectinload(ClassEnrollment.class_group),
        )
        .order_by(ClassEnrollment.created_at.desc())
        .limit(8)
    ).unique()

    recent_activity = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(12)
    )

    # Attempts in the last seven days, as a simple engagement pulse.
    week_ago = now - dt.timedelta(days=7)
    attempts_this_week = (
        db.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.created_at >= week_ago)
        )
        or 0
    )

    return {
        "upcoming_classes": [
            {
                "id": session.id,
                "title": session.title,
                "class_name": group.name,
                "class_id": group.id,
                "starts_at": session.starts_at,
                "ends_at": session.ends_at,
                "status": session.status,
                "join_url": session.join_url,
                "location": group.location,
            }
            for session, group in upcoming
        ],
        "recent_students": [
            {
                "id": profile.id,
                "user_id": profile.user_id,
                "name": profile.user.full_name if profile.user else None,
                "email": profile.user.email if profile.user else None,
                "grade": profile.grade,
                "created_at": profile.created_at,
                "is_active": profile.user.is_active if profile.user else False,
            }
            for profile in recent_students
        ],
        "recent_consultations": [
            {
                "id": lead.id,
                "source": "contact",
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "interest": lead.interest,
                "status": lead.status,
                "created_at": lead.created_at,
            }
            for lead in recent_leads
        ]
        + [
            {
                "id": request.id,
                "source": "tutoring",
                "name": request.contact_name,
                "email": request.contact_email,
                "phone": request.contact_phone,
                "interest": request.format,
                "status": request.status,
                "created_at": request.created_at,
            }
            for request in recent_requests
        ],
        "pending_enrollments": [
            {
                "id": enrollment.id,
                "student_name": (
                    enrollment.student.user.full_name
                    if enrollment.student and enrollment.student.user
                    else None
                ),
                "class_name": enrollment.class_group.name if enrollment.class_group else None,
                "status": enrollment.status,
                "payment_status": enrollment.payment_status,
                "created_at": enrollment.created_at,
            }
            for enrollment in pending_enrollments
        ],
        "recent_activity": [
            {
                "id": entry.id,
                "actor": entry.actor_email,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "summary": entry.summary,
                "created_at": entry.created_at,
            }
            for entry in recent_activity
        ],
        "attempts_this_week": attempts_this_week,
    }


@router.get("/search")
def global_search(
    db: DbSession, admin: CurrentAdmin, q: str = "", limit: int = 5
) -> dict[str, Any]:
    """Cross-entity lookup for the admin header search box."""
    term = q.strip()
    if len(term) < 2:
        return {"students": [], "teachers": [], "courses": [], "lessons": [], "leads": []}
    pattern = f"%{term}%"

    students = db.scalars(
        select(StudentProfile)
        .join(User, StudentProfile.user_id == User.id)
        .where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
        .options(selectinload(StudentProfile.user))
        .limit(limit)
    ).unique()
    teachers = db.scalars(
        select(TeacherProfile)
        .join(User, TeacherProfile.user_id == User.id)
        .where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
        .options(selectinload(TeacherProfile.user))
        .limit(limit)
    ).unique()
    courses = db.scalars(
        select(Course).where(or_(Course.title.ilike(pattern), Course.slug.ilike(pattern)))
        .limit(limit)
    )
    lessons = db.scalars(
        select(Lesson).where(or_(Lesson.title.ilike(pattern), Lesson.slug.ilike(pattern)))
        .limit(limit)
    )
    leads = db.scalars(
        select(ContactLead)
        .where(or_(ContactLead.name.ilike(pattern), ContactLead.email.ilike(pattern)))
        .limit(limit)
    )

    return {
        "students": [
            {"id": s.id, "name": s.user.full_name if s.user else "", "grade": s.grade}
            for s in students
        ],
        "teachers": [
            {"id": t.id, "name": t.user.full_name if t.user else "", "slug": t.slug}
            for t in teachers
        ],
        "courses": [{"id": c.id, "title": c.title, "slug": c.slug} for c in courses],
        "lessons": [{"id": lesson.id, "title": lesson.title, "slug": lesson.slug}
                    for lesson in lessons],
        "leads": [{"id": lead.id, "name": lead.name, "status": lead.status} for lead in leads],
    }
