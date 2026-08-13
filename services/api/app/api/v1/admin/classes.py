"""Classes, schedules and live sessions.

A ``ClassGroup`` is the cohort: who teaches it, who is in it, when it meets and where. A
``LiveSession`` is one concrete meeting. ``ScheduleSlot`` is the recurring weekly pattern the
sessions are generated from — keeping the pattern separate from the instances is what makes
"every Tuesday at 18:00 for ten weeks" one piece of data rather than ten.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    apply_sort,
    build_page,
    get_or_404,
    paginate,
    record_audit,
)
from app.core.text import unique_slug
from app.models import (
    Attendance,
    ClassEnrollment,
    ClassGroup,
    Course,
    EnrollmentStatus,
    LiveSession,
    ScheduleSlot,
    SessionStatus,
    StudentProfile,
    TeacherProfile,
    TutoringProduct,
)
from app.services.live_class import get_provider

router = APIRouter(prefix="/classes", tags=["admin:classes"])

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class ScheduleSlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("end_time")
    @classmethod
    def _after_start(cls, value: str, info) -> str:
        start = info.data.get("start_time")
        if start and value <= start:
            raise ValueError("End time must be after start time")
        return value


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    course_id: int | None = None
    product_id: int | None = None
    teacher_id: int | None = None
    format: str = "group"
    delivery_mode: str = "online"
    capacity: int = Field(default=12, ge=1, le=500)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    location: str | None = Field(default=None, max_length=250)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", max_length=60)
    is_open_for_enrollment: bool = True
    schedule: list[ScheduleSlotIn] = Field(default_factory=list)


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    course_id: int | None = None
    product_id: int | None = None
    teacher_id: int | None = None
    format: str | None = None
    delivery_mode: str | None = None
    capacity: int | None = Field(default=None, ge=1, le=500)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    location: str | None = Field(default=None, max_length=250)
    timezone: str | None = Field(default=None, max_length=60)
    is_open_for_enrollment: bool | None = None
    schedule: list[ScheduleSlotIn] | None = None


class SessionIn(BaseModel):
    class_group_id: int
    title: str = Field(min_length=1, max_length=250)
    starts_at: dt.datetime
    ends_at: dt.datetime
    topic_summary: str | None = None
    join_url: str | None = Field(default=None, max_length=800)
    passcode: str | None = Field(default=None, max_length=60)
    create_meeting: bool = False

    @field_validator("ends_at")
    @classmethod
    def _after_start(cls, value: dt.datetime, info) -> dt.datetime:
        start = info.data.get("starts_at")
        if start and value <= start:
            raise ValueError("A session must end after it starts")
        return value


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None
    topic_summary: str | None = None
    join_url: str | None = Field(default=None, max_length=800)
    recording_url: str | None = Field(default=None, max_length=800)
    status: SessionStatus | None = None


class GenerateSessionsRequest(BaseModel):
    """Materialise the weekly pattern into real sessions between two dates."""

    from_date: dt.date
    to_date: dt.date
    title_template: str = Field(default="{class_name} — {date}", max_length=200)


def _class_row(group: ClassGroup) -> dict[str, Any]:
    active = sum(
        1
        for e in group.enrollments
        if e.status in {EnrollmentStatus.CONFIRMED, EnrollmentStatus.ACTIVE}
    )
    return {
        "id": group.id,
        "slug": group.slug,
        "name": group.name,
        "course_id": group.course_id,
        "course_title": group.course.title if group.course else None,
        "product_id": group.product_id,
        "teacher_id": group.teacher_id,
        "teacher_name": (
            group.teacher.user.full_name if group.teacher and group.teacher.user else None
        ),
        "format": group.format,
        "delivery_mode": group.delivery_mode,
        "capacity": group.capacity,
        "enrolled": len(group.enrollments),
        "seats_taken": active,
        "seats_available": max(0, group.capacity - active),
        "start_date": group.start_date,
        "end_date": group.end_date,
        "location": group.location,
        "timezone": group.timezone,
        "is_open_for_enrollment": group.is_open_for_enrollment,
        "schedule": [
            {
                "id": slot.id,
                "weekday": slot.weekday,
                "weekday_label": WEEKDAYS[slot.weekday % 7],
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
            }
            for slot in sorted(group.schedule_slots, key=lambda s: (s.weekday, s.start_time))
        ],
        "session_count": len(group.sessions),
        "created_at": group.created_at,
    }


def _loaded(db, class_id: int) -> ClassGroup:
    group = db.scalar(
        select(ClassGroup)
        .where(ClassGroup.id == class_id)
        .options(
            selectinload(ClassGroup.enrollments),
            selectinload(ClassGroup.schedule_slots),
            selectinload(ClassGroup.sessions),
            selectinload(ClassGroup.course),
            selectinload(ClassGroup.teacher).selectinload(TeacherProfile.user),
        )
    )
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return group


def _replace_schedule(db, group: ClassGroup, slots: list[ScheduleSlotIn]) -> None:
    db.execute(
        ScheduleSlot.__table__.delete().where(ScheduleSlot.class_group_id == group.id)
    )
    for slot in slots:
        db.add(
            ScheduleSlot(
                class_group_id=group.id,
                weekday=slot.weekday,
                start_time=dt.time.fromisoformat(slot.start_time),
                end_time=dt.time.fromisoformat(slot.end_time),
            )
        )


@router.get("")
def list_classes(
    db: DbSession,
    admin: CurrentAdmin,
    teacher_id: Annotated[int | None, Query()] = None,
    course_id: Annotated[int | None, Query()] = None,
    class_format: Annotated[str | None, Query(alias="format", max_length=30)] = None,
    delivery_mode: Annotated[str | None, Query(max_length=30)] = None,
    open_only: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(ClassGroup).options(
        selectinload(ClassGroup.enrollments),
        selectinload(ClassGroup.schedule_slots),
        selectinload(ClassGroup.sessions),
        selectinload(ClassGroup.course),
        selectinload(ClassGroup.teacher).selectinload(TeacherProfile.user),
    )
    if teacher_id:
        query = query.where(ClassGroup.teacher_id == teacher_id)
    if course_id:
        query = query.where(ClassGroup.course_id == course_id)
    if class_format:
        query = query.where(ClassGroup.format == class_format)
    if delivery_mode:
        query = query.where(ClassGroup.delivery_mode == delivery_mode)
    if open_only is not None:
        query = query.where(ClassGroup.is_open_for_enrollment.is_(open_only))
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(ClassGroup.name.ilike(pattern), ClassGroup.location.ilike(pattern))
        )

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        ClassGroup,
        params,
        {
            "name": ClassGroup.name,
            "start_date": ClassGroup.start_date,
            "capacity": ClassGroup.capacity,
            "created_at": ClassGroup.created_at,
            "_default": ClassGroup.created_at,
        },
    )
    rows, total = paginate(db, query, params)
    return build_page([_class_row(row) for row in rows], total, params)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    if payload.course_id is not None:
        get_or_404(db, Course, payload.course_id, "Course")
    if payload.product_id is not None:
        get_or_404(db, TutoringProduct, payload.product_id, "Programme")
    if payload.teacher_id is not None:
        get_or_404(db, TeacherProfile, payload.teacher_id, "Teacher")
    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The end date cannot be before the start date",
        )

    group = ClassGroup(
        **payload.model_dump(exclude={"schedule"}),
        slug=unique_slug(
            payload.name,
            lambda candidate: db.scalar(
                select(ClassGroup.id).where(ClassGroup.slug == candidate)
            )
            is not None,
            max_length=140,
        ),
    )
    db.add(group)
    db.flush()
    _replace_schedule(db, group, payload.schedule)

    record_audit(db, admin, "create", "class", group.id, f"Created class “{group.name}”")
    db.commit()
    return _class_row(_loaded(db, group.id))


@router.get("/{class_id}")
def get_class(class_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    group = _loaded(db, class_id)
    data = _class_row(group)

    roster = db.execute(
        select(ClassEnrollment, StudentProfile)
        .join(StudentProfile, ClassEnrollment.student_id == StudentProfile.id)
        .where(ClassEnrollment.class_group_id == class_id)
        .options(selectinload(StudentProfile.user))
    ).all()
    data["roster"] = [
        {
            "enrollment_id": enrollment.id,
            "student_id": student.id,
            "name": student.user.full_name if student.user else None,
            "email": student.user.email if student.user else None,
            "grade": student.grade,
            "status": enrollment.status,
            "payment_status": enrollment.payment_status,
            "enrolled_at": enrollment.enrolled_at,
        }
        for enrollment, student in roster
    ]

    data["sessions"] = [
        {
            "id": s.id,
            "title": s.title,
            "starts_at": s.starts_at,
            "ends_at": s.ends_at,
            "status": s.status,
            "join_url": s.join_url,
            "recording_url": s.recording_url,
            "provider": s.provider,
            "topic_summary": s.topic_summary,
        }
        for s in sorted(group.sessions, key=lambda s: s.starts_at, reverse=True)
    ]
    return data


@router.patch("/{class_id}")
def update_class(
    class_id: int, payload: ClassUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    group = _loaded(db, class_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"schedule"})

    if fields.get("course_id") is not None:
        get_or_404(db, Course, fields["course_id"], "Course")
    if fields.get("product_id") is not None:
        get_or_404(db, TutoringProduct, fields["product_id"], "Programme")
    if fields.get("teacher_id") is not None:
        get_or_404(db, TeacherProfile, fields["teacher_id"], "Teacher")

    new_capacity = fields.get("capacity")
    if new_capacity is not None:
        taken = sum(
            1
            for e in group.enrollments
            if e.status in {EnrollmentStatus.CONFIRMED, EnrollmentStatus.ACTIVE}
        )
        if new_capacity < taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Capacity cannot be set below the {taken} student(s) already holding a "
                    "place. Move them to another class first."
                ),
            )

    start = fields.get("start_date", group.start_date)
    end = fields.get("end_date", group.end_date)
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The end date cannot be before the start date",
        )

    for key, value in fields.items():
        setattr(group, key, value)
    if payload.schedule is not None:
        _replace_schedule(db, group, payload.schedule)

    record_audit(
        db, admin, "update", "class", group.id, f"Updated class “{group.name}”",
        {k: str(v) for k, v in fields.items()},
    )
    db.commit()
    return _class_row(_loaded(db, class_id))


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    group = _loaded(db, class_id)
    active = sum(
        1
        for e in group.enrollments
        if e.status in {EnrollmentStatus.CONFIRMED, EnrollmentStatus.ACTIVE}
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"“{group.name}” still has {active} enrolled student(s). Move or cancel them "
                "before deleting the class."
            ),
        )
    name = group.name
    db.delete(group)
    record_audit(db, admin, "delete", "class", class_id, f"Deleted class “{name}”")
    db.commit()


# --------------------------------------------------------------------------------------
# live sessions
# --------------------------------------------------------------------------------------

sessions_router = APIRouter(prefix="/live-sessions", tags=["admin:sessions"])


@sessions_router.get("")
def list_sessions(
    db: DbSession,
    admin: CurrentAdmin,
    class_group_id: Annotated[int | None, Query()] = None,
    teacher_id: Annotated[int | None, Query()] = None,
    session_status: Annotated[SessionStatus | None, Query(alias="status")] = None,
    date_from: Annotated[dt.datetime | None, Query()] = None,
    date_to: Annotated[dt.datetime | None, Query()] = None,
    upcoming: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    query = select(LiveSession).options(
        selectinload(LiveSession.class_group).selectinload(ClassGroup.teacher).selectinload(
            TeacherProfile.user
        )
    )
    if class_group_id:
        query = query.where(LiveSession.class_group_id == class_group_id)
    if teacher_id:
        query = query.where(
            LiveSession.class_group_id.in_(
                select(ClassGroup.id).where(ClassGroup.teacher_id == teacher_id)
            )
        )
    if session_status:
        query = query.where(LiveSession.status == session_status)
    if date_from:
        query = query.where(LiveSession.starts_at >= date_from)
    if date_to:
        query = query.where(LiveSession.starts_at <= date_to)
    if upcoming:
        query = query.where(LiveSession.starts_at >= dt.datetime.now(dt.UTC))

    params = PageParams(page=page, page_size=page_size)
    query = query.order_by(
        LiveSession.starts_at.asc() if upcoming else LiveSession.starts_at.desc()
    )
    rows, total = paginate(db, query, params)
    items = [
        {
            "id": s.id,
            "title": s.title,
            "class_group_id": s.class_group_id,
            "class_name": s.class_group.name if s.class_group else None,
            "teacher_name": (
                s.class_group.teacher.user.full_name
                if s.class_group and s.class_group.teacher and s.class_group.teacher.user
                else None
            ),
            "starts_at": s.starts_at,
            "ends_at": s.ends_at,
            "status": s.status,
            "provider": s.provider,
            "join_url": s.join_url,
            "recording_url": s.recording_url,
            "location": s.class_group.location if s.class_group else None,
            "topic_summary": s.topic_summary,
        }
        for s in rows
    ]
    return build_page(items, total, params)


@sessions_router.post("", status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    group = get_or_404(db, ClassGroup, payload.class_group_id, "Class")

    session = LiveSession(
        class_group_id=group.id,
        title=payload.title,
        topic_summary=payload.topic_summary,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        join_url=payload.join_url,
        passcode=payload.passcode,
        status=SessionStatus.SCHEDULED,
    )

    if payload.create_meeting:
        # The provider is pluggable and defaults to "manual", which creates nothing and returns an
        # empty join URL — so the typed-in link is kept. Nothing here pretends to have booked a
        # meeting it did not book.
        provider = get_provider()
        meeting = provider.create_meeting(
            topic=payload.title,
            starts_at=payload.starts_at,
            duration_minutes=int((payload.ends_at - payload.starts_at).total_seconds() // 60),
            timezone=group.timezone,
            agenda=payload.topic_summary,
        )
        session.provider = meeting.provider
        session.provider_meeting_id = meeting.meeting_id
        session.join_url = meeting.join_url or payload.join_url
        session.host_url = meeting.host_url
        session.passcode = meeting.passcode or payload.passcode
        session.provider_payload = meeting.payload

    db.add(session)
    db.flush()
    record_audit(
        db, admin, "create", "live_session", session.id,
        f"Scheduled “{session.title}” for “{group.name}”",
    )
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "class_group_id": session.class_group_id,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "status": session.status,
        "provider": session.provider,
        "join_url": session.join_url,
    }


@sessions_router.patch("/{session_id}")
def update_session(
    session_id: int, payload: SessionUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    session = get_or_404(db, LiveSession, session_id, "Session")
    fields = payload.model_dump(exclude_unset=True)

    starts = fields.get("starts_at", session.starts_at)
    ends = fields.get("ends_at", session.ends_at)
    if ends <= starts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A session must end after it starts",
        )

    for key, value in fields.items():
        setattr(session, key, value)
    record_audit(
        db, admin, "update", "live_session", session.id, f"Updated session “{session.title}”"
    )
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "status": session.status,
        "join_url": session.join_url,
        "recording_url": session.recording_url,
    }


@sessions_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    session = get_or_404(db, LiveSession, session_id, "Session")
    title = session.title
    db.delete(session)
    record_audit(db, admin, "delete", "live_session", session_id, f"Deleted session “{title}”")
    db.commit()


@sessions_router.get("/{session_id}/attendance")
def session_attendance(
    session_id: int, db: DbSession, admin: CurrentAdmin
) -> list[dict[str, Any]]:
    session = get_or_404(db, LiveSession, session_id, "Session")
    rows = db.execute(
        select(Attendance, StudentProfile)
        .join(StudentProfile, Attendance.student_id == StudentProfile.id)
        .where(Attendance.session_id == session.id)
        .options(selectinload(StudentProfile.user))
    ).all()
    return [
        {
            "id": record.id,
            "student_id": student.id,
            "name": student.user.full_name if student.user else None,
            "status": record.status,
            "minutes_attended": record.minutes_attended,
            "teacher_note": record.teacher_note,
        }
        for record, student in rows
    ]


@router.post("/{class_id}/generate-sessions", status_code=status.HTTP_201_CREATED)
def generate_sessions(
    class_id: int,
    payload: GenerateSessionsRequest,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    """Expand the weekly schedule into concrete sessions across a date range.

    Skips any date/time that already has a session, so running it twice — or extending the range
    later — adds only what is missing instead of producing duplicates.
    """
    group = _loaded(db, class_id)
    if not group.schedule_slots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This class has no weekly schedule yet. Add at least one time slot first.",
        )
    if payload.to_date < payload.from_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The end date cannot be before the start date",
        )
    if (payload.to_date - payload.from_date).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate at most one year of sessions at a time",
        )

    existing = {
        (session.starts_at.date(), session.starts_at.time().replace(second=0, microsecond=0))
        for session in group.sessions
    }

    created = 0
    day = payload.from_date
    while day <= payload.to_date:
        for slot in group.schedule_slots:
            if slot.weekday != day.weekday():
                continue
            key = (day, slot.start_time.replace(second=0, microsecond=0))
            if key in existing:
                continue
            starts_at = dt.datetime.combine(day, slot.start_time, tzinfo=dt.UTC)
            ends_at = dt.datetime.combine(day, slot.end_time, tzinfo=dt.UTC)
            db.add(
                LiveSession(
                    class_group_id=group.id,
                    title=payload.title_template.format(
                        class_name=group.name, date=day.isoformat()
                    )[:250],
                    starts_at=starts_at,
                    ends_at=ends_at,
                    status=SessionStatus.SCHEDULED,
                    provider="manual",
                )
            )
            existing.add(key)
            created += 1
        day += dt.timedelta(days=1)

    record_audit(
        db, admin, "generate", "class", group.id,
        f"Generated {created} session(s) for “{group.name}”",
        {"from": payload.from_date.isoformat(), "to": payload.to_date.isoformat()},
    )
    db.commit()
    return {"class_id": group.id, "created": created}
