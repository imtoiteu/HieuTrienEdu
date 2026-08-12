"""Teacher dashboard: content authoring, class management and student analytics."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentTeacher, CurrentUser, DbSession, require_roles
from app.exercise_engine import GenerationError, QuestionTemplate, generate_variant
from app.models import (
    Assignment,
    AssignmentSubmission,
    Attempt,
    ClassEnrollment,
    ClassGroup,
    Course,
    EnrollmentStatus,
    LiveSession,
    Question,
    ReviewStatus,
    SessionStatus,
    Skill,
    StudentProfile,
    StudentSkillMastery,
    Topic,
    Unit,
    UserRole,
)
from app.schemas.curriculum import (
    PaginatedQuestions,
    QuestionCreate,
    QuestionPreview,
    QuestionRead,
    QuestionUpdate,
)
from app.services.live_class import get_provider

router = APIRouter(
    prefix="/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_roles(UserRole.TEACHER))],
)


def _slugify(value: str, fallback: str = "question") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120]
    return slug or fallback


# --------------------------------------------------------------------------------------
# question bank
# --------------------------------------------------------------------------------------


@router.get("/questions", response_model=PaginatedQuestions)
def list_questions(
    db: DbSession,
    skill_id: Annotated[int | None, Query()] = None,
    subject: Annotated[str | None, Query()] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    topic: Annotated[str | None, Query()] = None,
    difficulty: Annotated[int | None, Query(ge=1, le=5)] = None,
    question_type: Annotated[str | None, Query()] = None,
    status_filter: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PaginatedQuestions:
    """Browse and filter the question bank."""
    conditions = []
    if skill_id:
        conditions.append(Question.skill_id == skill_id)
    if subject:
        conditions.append(Question.subject_slug == subject)
    if grade:
        conditions.append(Question.grade == grade)
    if topic:
        conditions.append(Question.topic_slug == topic)
    if difficulty:
        conditions.append(Question.difficulty == difficulty)
    if question_type:
        conditions.append(Question.question_type == question_type)
    if status_filter:
        conditions.append(Question.status == status_filter)
    if search:
        conditions.append(Question.prompt.ilike(f"%{search}%"))

    total = db.scalar(
        select(func.count()).select_from(Question).where(*conditions) if conditions
        else select(func.count()).select_from(Question)
    ) or 0

    query = select(Question)
    if conditions:
        query = query.where(*conditions)
    rows = db.scalars(
        query.order_by(Question.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    return PaginatedQuestions(
        items=[QuestionRead.model_validate(q) for q in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate, db: DbSession, user: CurrentUser
) -> QuestionRead:
    """Create a question. Validated by generating a variant before it is saved."""
    skill = db.scalar(
        select(Skill)
        .where(Skill.id == payload.skill_id)
        .options(selectinload(Skill.topic).selectinload(Topic.unit).selectinload(Unit.course)
                 .selectinload(Course.subject))
    )
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    template = QuestionTemplate(
        slug=payload.slug or _slugify(payload.prompt),
        question_type=payload.question_type,
        prompt=payload.prompt,
        variables=payload.variables,
        constraints=payload.constraints,
        answer_spec=payload.answer_spec,
        options=payload.options,
        hints=payload.hints,
        solution=payload.solution,
        difficulty=payload.difficulty,
    )
    # Fail fast: a template that cannot generate is broken, and a broken question in the bank
    # would surface as a 500 in front of a student mid-session.
    try:
        generate_variant(template, seed=1)
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This question template is not valid: {exc}",
        ) from exc

    course = skill.topic.unit.course
    slug = payload.slug or _slugify(f"{skill.slug}-{payload.prompt[:40]}")
    if db.scalar(select(Question).where(Question.slug == slug)) is not None:
        slug = f"{slug}-{int(dt.datetime.now(dt.UTC).timestamp())}"

    question = Question(
        slug=slug,
        skill_id=skill.id,
        subject_slug=course.subject.slug if course.subject else "",
        grade=course.grade,
        topic_slug=skill.topic.slug,
        question_type=payload.question_type,
        difficulty=payload.difficulty,
        prompt=payload.prompt,
        variables=payload.variables,
        constraints=payload.constraints,
        answer_spec=payload.answer_spec,
        options=payload.options,
        hints=payload.hints,
        solution=payload.solution,
        tags=payload.tags,
        estimated_seconds=payload.estimated_seconds,
        status=payload.status,
        is_parametric=bool(payload.variables),
        source=payload.source,
        license=payload.license,
        attribution=payload.attribution,
        created_by_id=user.id,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return QuestionRead.model_validate(question)


@router.patch("/questions/{question_id}", response_model=QuestionRead)
def update_question(
    question_id: int, payload: QuestionUpdate, db: DbSession
) -> QuestionRead:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    question.is_parametric = bool(question.variables)

    try:
        generate_variant(QuestionTemplate.from_model(question), seed=1)
    except GenerationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This question template is not valid: {exc}",
        ) from exc

    db.commit()
    db.refresh(question)
    return QuestionRead.model_validate(question)


@router.get("/questions/{question_id}/preview", response_model=QuestionPreview)
def preview_question(
    question_id: int, db: DbSession, seed: Annotated[int | None, Query()] = None
) -> QuestionPreview:
    """Render a variant *including the answer* — teachers need to check their own templates."""
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    import secrets

    chosen_seed = seed if seed is not None else secrets.randbelow(2**31 - 1)
    try:
        variant = generate_variant(QuestionTemplate.from_model(question), chosen_seed)
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return QuestionPreview(
        seed=variant.seed,
        variable_values=variant.variable_values,
        rendered=variant.rendered,
        answer=variant.answer,
        hints=variant.hints,
        solution=variant.solution,
    )


@router.post("/questions/{question_id}/publish", response_model=QuestionRead)
def publish_question(question_id: int, db: DbSession) -> QuestionRead:
    """Approve a draft (including an AI-generated one) so students can be served it."""
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    try:
        generate_variant(QuestionTemplate.from_model(question), seed=7)
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot publish an invalid template: {exc}",
        ) from exc

    question.status = ReviewStatus.PUBLISHED
    db.commit()
    db.refresh(question)
    return QuestionRead.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_question(question_id: int, db: DbSession) -> None:
    """Soft-delete by rejecting.

    Attempts reference questions, so hard deletion would lose a student's history.
    """
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    question.status = ReviewStatus.REJECTED
    db.commit()


# --------------------------------------------------------------------------------------
# classes and students
# --------------------------------------------------------------------------------------


class ClassSummary(BaseModel):
    id: int
    slug: str
    name: str
    format: str
    student_count: int
    capacity: int
    course_title: str | None = None
    next_session_at: dt.datetime | None = None


class StudentRow(BaseModel):
    student_id: int
    name: str
    grade: int
    email: str
    average_mastery: float
    skills_mastered: int
    attempts: int
    accuracy: float | None = None
    last_active_at: dt.datetime | None = None


@router.get("/classes", response_model=list[ClassSummary])
def my_classes(db: DbSession, teacher: CurrentTeacher) -> list[ClassSummary]:
    groups = list(
        db.scalars(
            select(ClassGroup)
            .where(ClassGroup.teacher_id == teacher.id)
            .options(
                selectinload(ClassGroup.enrollments),
                selectinload(ClassGroup.course),
                selectinload(ClassGroup.sessions),
            )
        ).unique()
    )
    now = dt.datetime.now(dt.UTC)
    result = []
    for group in groups:
        upcoming = sorted(
            (
                s for s in group.sessions
                if s.starts_at
                and (s.starts_at if s.starts_at.tzinfo else s.starts_at.replace(tzinfo=dt.UTC))
                >= now
                and s.status != SessionStatus.CANCELLED
            ),
            key=lambda s: s.starts_at,
        )
        result.append(
            ClassSummary(
                id=group.id, slug=group.slug, name=group.name, format=group.format,
                student_count=group.seats_taken, capacity=group.capacity,
                course_title=group.course.title if group.course else None,
                next_session_at=upcoming[0].starts_at if upcoming else None,
            )
        )
    return result


@router.get("/classes/{class_id}/students", response_model=list[StudentRow])
def class_students(class_id: int, db: DbSession, teacher: CurrentTeacher) -> list[StudentRow]:
    group = db.get(ClassGroup, class_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    student_ids = [
        e.student_id
        for e in db.scalars(
            select(ClassEnrollment).where(
                ClassEnrollment.class_group_id == class_id,
                ClassEnrollment.status == EnrollmentStatus.ACTIVE,
            )
        )
    ]
    return _student_rows(db, student_ids)


def _student_rows(db, student_ids: list[int]) -> list[StudentRow]:
    if not student_ids:
        return []

    students = list(
        db.scalars(
            select(StudentProfile)
            .where(StudentProfile.id.in_(student_ids))
            .options(selectinload(StudentProfile.user))
        ).unique()
    )

    mastery_rows = db.execute(
        select(
            StudentSkillMastery.student_id,
            func.avg(StudentSkillMastery.mastery_probability),
            func.count(StudentSkillMastery.id),
        )
        .where(StudentSkillMastery.student_id.in_(student_ids))
        .group_by(StudentSkillMastery.student_id)
    ).all()
    mastery_by_student = {sid: (avg or 0, n or 0) for sid, avg, n in mastery_rows}

    mastered_rows = db.execute(
        select(StudentSkillMastery.student_id, func.count(StudentSkillMastery.id))
        .where(
            StudentSkillMastery.student_id.in_(student_ids),
            StudentSkillMastery.mastered_at.is_not(None),
        )
        .group_by(StudentSkillMastery.student_id)
    ).all()
    mastered_by_student = dict(mastered_rows)

    attempt_rows = db.execute(
        select(
            Attempt.student_id,
            func.count(Attempt.id),
            func.sum(cast(Attempt.is_correct, Integer)),
            func.max(Attempt.created_at),
        )
        .where(Attempt.student_id.in_(student_ids))
        .group_by(Attempt.student_id)
    ).all()
    attempts_by_student = {
        sid: (total or 0, int(correct or 0), last) for sid, total, correct, last in attempt_rows
    }

    rows = []
    for student in students:
        avg_mastery, _ = mastery_by_student.get(student.id, (0.0, 0))
        total, correct, last = attempts_by_student.get(student.id, (0, 0, None))
        rows.append(
            StudentRow(
                student_id=student.id,
                name=student.user.full_name if student.user else "",
                grade=student.grade,
                email=student.user.email if student.user else "",
                average_mastery=round(float(avg_mastery), 4),
                skills_mastered=mastered_by_student.get(student.id, 0),
                attempts=total,
                accuracy=round(correct / total, 4) if total else None,
                last_active_at=last,
            )
        )
    return sorted(rows, key=lambda r: r.average_mastery)


@router.get("/students", response_model=list[StudentRow])
def all_students(db: DbSession, teacher: CurrentTeacher) -> list[StudentRow]:
    ids = list(db.scalars(select(StudentProfile.id)))
    return _student_rows(db, ids)


@router.get("/students/{student_id}/mastery")
def student_mastery(
    student_id: int, db: DbSession, teacher: CurrentTeacher
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(StudentSkillMastery)
        .where(StudentSkillMastery.student_id == student_id)
        .order_by(StudentSkillMastery.mastery_probability)
        .options(selectinload(StudentSkillMastery.skill))
    )
    return [
        {
            "skill_id": r.skill_id,
            "skill_name": r.skill.name if r.skill else "",
            "skill_slug": r.skill.slug if r.skill else "",
            "mastery": round(r.mastery_probability, 4),
            "mastery_percent": int(round(r.mastery_probability * 100)),
            "attempts": r.attempts,
            "correct": r.correct,
            "incorrect": r.incorrect,
            "is_mastered": r.mastered_at is not None,
            "last_practiced_at": r.last_practiced_at,
        }
        for r in rows
    ]


# --------------------------------------------------------------------------------------
# analytics
# --------------------------------------------------------------------------------------


@router.get("/analytics")
def analytics(
    db: DbSession,
    teacher: CurrentTeacher,
    class_id: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    """Class-level analytics: averages, hardest questions and most common mistakes."""
    if class_id is not None:
        student_ids = [
            e.student_id
            for e in db.scalars(
                select(ClassEnrollment).where(ClassEnrollment.class_group_id == class_id)
            )
        ]
    else:
        student_ids = list(db.scalars(select(StudentProfile.id)))

    if not student_ids:
        return {
            "student_count": 0, "class_average_mastery": 0, "completion_rate": 0,
            "hardest_questions": [], "weakest_skills": [], "most_common_mistakes": [],
        }

    avg_mastery = db.scalar(
        select(func.avg(StudentSkillMastery.mastery_probability)).where(
            StudentSkillMastery.student_id.in_(student_ids)
        )
    ) or 0

    total_attempts = db.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.student_id.in_(student_ids))
    ) or 0
    correct_attempts = db.scalar(
        select(func.count()).select_from(Attempt).where(
            Attempt.student_id.in_(student_ids), Attempt.is_correct.is_(True)
        )
    ) or 0

    # Hardest questions: lowest success rate among those served enough times to be meaningful.
    hardest = db.execute(
        select(
            Question.id, Question.slug, Question.prompt, Question.difficulty,
            Question.times_served, Question.times_correct,
        )
        .where(Question.times_served >= 5)
        .order_by(Question.times_correct * 1.0 / Question.times_served)
        .limit(8)
    ).all()

    weakest = db.execute(
        select(
            Skill.id, Skill.name, Skill.slug,
            func.avg(StudentSkillMastery.mastery_probability),
            func.count(StudentSkillMastery.id),
        )
        .join(StudentSkillMastery, StudentSkillMastery.skill_id == Skill.id)
        .where(StudentSkillMastery.student_id.in_(student_ids))
        .group_by(Skill.id, Skill.name, Skill.slug)
        .order_by(func.avg(StudentSkillMastery.mastery_probability))
        .limit(8)
    ).all()

    # Most common mistakes: the wrong answers students actually gave, grouped.
    wrong_attempts = list(
        db.scalars(
            select(Attempt)
            .where(Attempt.student_id.in_(student_ids), Attempt.is_correct.is_(False))
            .order_by(Attempt.created_at.desc())
            .limit(500)
            .options(selectinload(Attempt.skill))
        )
    )
    mistake_counts: dict[tuple[str, str], int] = {}
    for attempt in wrong_attempts:
        answer = attempt.user_answer or {}
        given = str(answer.get("value") or answer.get("choice_id") or "")[:60]
        if not given:
            continue
        key = (attempt.skill.name if attempt.skill else "", given)
        mistake_counts[key] = mistake_counts.get(key, 0) + 1

    return {
        "student_count": len(student_ids),
        "class_average_mastery": round(float(avg_mastery), 4),
        "class_average_mastery_percent": int(round(float(avg_mastery) * 100)),
        "total_attempts": total_attempts,
        "completion_rate": round(correct_attempts / total_attempts, 4) if total_attempts else 0,
        "hardest_questions": [
            {
                "id": qid, "slug": slug, "prompt": prompt[:160], "difficulty": difficulty,
                "times_served": served, "success_rate": round(correct / served, 3) if served else 0,
            }
            for qid, slug, prompt, difficulty, served, correct in hardest
        ],
        "weakest_skills": [
            {
                "skill_id": sid, "name": name, "slug": slug,
                "average_mastery": round(float(avg or 0), 4),
                "students_tracked": n,
            }
            for sid, name, slug, avg, n in weakest
        ],
        "most_common_mistakes": [
            {"skill": skill, "answer": given, "count": count}
            for (skill, given), count in sorted(
                mistake_counts.items(), key=lambda kv: -kv[1]
            )[:10]
        ],
    }


# --------------------------------------------------------------------------------------
# assignments and live sessions
# --------------------------------------------------------------------------------------


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    instructions: str | None = None
    class_group_id: int | None = None
    skill_ids: list[int] = Field(default_factory=list)
    question_ids: list[int] = Field(default_factory=list)
    questions_per_skill: int = Field(default=5, ge=1, le=30)
    due_at: dt.datetime | None = None
    time_limit_minutes: int | None = Field(default=None, ge=1, le=600)
    kind: str = Field(default="homework", max_length=20)
    published: bool = False


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: AssignmentCreate, db: DbSession, teacher: CurrentTeacher
) -> dict[str, Any]:
    if not payload.skill_ids and not payload.question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An assignment needs at least one skill or question",
        )

    assignment = Assignment(
        title=payload.title,
        instructions=payload.instructions,
        class_group_id=payload.class_group_id,
        teacher_id=teacher.id,
        kind=payload.kind,
        skill_ids=payload.skill_ids,
        question_ids=payload.question_ids,
        questions_per_skill=payload.questions_per_skill,
        time_limit_minutes=payload.time_limit_minutes,
        due_at=payload.due_at,
        published=payload.published,
    )
    db.add(assignment)
    db.flush()

    # Materialise a submission row per enrolled student so the assignment shows on their
    # dashboard immediately rather than only after they open it.
    if payload.class_group_id and payload.published:
        for enrollment in db.scalars(
            select(ClassEnrollment).where(
                ClassEnrollment.class_group_id == payload.class_group_id,
                ClassEnrollment.status == EnrollmentStatus.ACTIVE,
            )
        ):
            db.add(
                AssignmentSubmission(
                    assignment_id=assignment.id, student_id=enrollment.student_id
                )
            )

    db.commit()
    db.refresh(assignment)
    return {"id": assignment.id, "title": assignment.title, "published": assignment.published}


@router.get("/assignments")
def list_assignments(db: DbSession, teacher: CurrentTeacher) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Assignment)
        .where(Assignment.teacher_id == teacher.id)
        .order_by(Assignment.created_at.desc())
        .options(selectinload(Assignment.submissions))
    ).unique()
    return [
        {
            "id": a.id, "title": a.title, "kind": a.kind, "due_at": a.due_at,
            "published": a.published, "class_group_id": a.class_group_id,
            "submission_count": len(a.submissions),
            "graded_count": sum(1 for s in a.submissions if s.score_percent is not None),
        }
        for a in rows
    ]


class LiveSessionCreate(BaseModel):
    class_group_id: int
    title: str = Field(min_length=1, max_length=250)
    topic_summary: str | None = None
    starts_at: dt.datetime
    duration_minutes: int = Field(default=90, ge=15, le=480)
    join_url: str | None = Field(default=None, max_length=800)


@router.post("/live-sessions", status_code=status.HTTP_201_CREATED)
def schedule_live_session(
    payload: LiveSessionCreate, db: DbSession, teacher: CurrentTeacher
) -> dict[str, Any]:
    """Schedule a live class.

    Uses the configured provider (Zoom when credentials exist, otherwise manual). A manual
    session is fully usable — the teacher supplies the link.
    """
    group = db.get(ClassGroup, payload.class_group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    provider = get_provider()
    ends_at = payload.starts_at + dt.timedelta(minutes=payload.duration_minutes)

    details = None
    provider_error = None
    if payload.join_url is None:
        try:
            details = provider.create_meeting(
                topic=payload.title,
                starts_at=payload.starts_at,
                duration_minutes=payload.duration_minutes,
                timezone=group.timezone,
                agenda=payload.topic_summary,
            )
        except Exception as exc:  # provider outage must not lose the scheduled class
            provider_error = str(exc)

    session = LiveSession(
        class_group_id=group.id,
        title=payload.title,
        topic_summary=payload.topic_summary,
        starts_at=payload.starts_at,
        ends_at=ends_at,
        provider=details.provider if details else "manual",
        provider_meeting_id=details.meeting_id if details else None,
        join_url=payload.join_url or (details.join_url if details else None),
        host_url=details.host_url if details else None,
        passcode=details.passcode if details else None,
        status=SessionStatus.SCHEDULED,
        provider_payload=(details.payload if details else {}) | (
            {"provider_error": provider_error} if provider_error else {}
        ),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "title": session.title,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "provider": session.provider,
        "join_url": session.join_url,
        "needs_manual_link": session.join_url is None,
        "provider_error": provider_error,
    }


class AttendanceMark(BaseModel):
    student_id: int
    status: str = Field(default="present", max_length=20)
    minutes_attended: int = Field(default=0, ge=0)
    teacher_note: str | None = None


@router.post("/live-sessions/{session_id}/attendance")
def mark_attendance(
    session_id: int, records: list[AttendanceMark], db: DbSession, teacher: CurrentTeacher
) -> dict[str, Any]:
    from app.models import Attendance

    live = db.get(LiveSession, session_id)
    if live is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    for record in records:
        existing = db.scalar(
            select(Attendance).where(
                Attendance.session_id == session_id,
                Attendance.student_id == record.student_id,
            )
        )
        if existing is None:
            existing = Attendance(session_id=session_id, student_id=record.student_id)
            db.add(existing)
        existing.status = record.status
        existing.minutes_attended = record.minutes_attended
        existing.teacher_note = record.teacher_note

    db.commit()
    return {"recorded": len(records)}
