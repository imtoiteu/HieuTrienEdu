"""The practice loop: start a session, get a question, submit an answer, get recommendations."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.adaptive import build_learning_path, recommend_next
from app.exercise_engine import AnswerFormatError
from app.models import (
    PracticeSession,
    Question,
    QuestionVariant,
    Skill,
    Topic,
    Unit,
)
from app.core.deps import CurrentStudent, DbSession
from app.schemas.practice import (
    HintRead,
    MasteryChange,
    PathNodeRead,
    RecommendationRead,
    ServedQuestionRead,
    SessionRead,
    StartSessionRequest,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services.gamification import XP_RULES, award_xp
from app.services.practice import record_attempt, serve_question

router = APIRouter(prefix="/practice", tags=["practice"])


def _resolve_skill(db: DbSession, skill_id: int | None, skill_slug: str | None) -> Skill:
    if skill_id is None and not skill_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either skill_id or skill_slug",
        )
    query = select(Skill).options(selectinload(Skill.topic))
    query = query.where(Skill.id == skill_id) if skill_id else query.where(Skill.slug == skill_slug)
    skill = db.scalar(query)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def start_session(
    payload: StartSessionRequest, db: DbSession, student: CurrentStudent
) -> SessionRead:
    skill = _resolve_skill(db, payload.skill_id, payload.skill_slug)

    session = PracticeSession(
        student_id=student.id,
        skill_id=skill.id,
        mode=payload.mode,
        target_questions=payload.target_questions,
        assignment_id=payload.assignment_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionRead.model_validate(session)


@router.get("/sessions/{session_id}/next", response_model=ServedQuestionRead)
def next_question(session_id: int, db: DbSession, student: CurrentStudent) -> ServedQuestionRead:
    """Serve the next question in a session, avoiding templates already seen in it."""
    session = db.get(PracticeSession, session_id)
    if session is None or session.student_id != student.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This session is already complete"
        )
    if session.skill_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Session has no skill attached"
        )

    skill = db.get(Skill, session.skill_id)
    already_seen = [attempt.question_id for attempt in session.attempts]

    try:
        served = serve_question(
            db, student, skill, session=session, exclude_question_ids=already_seen
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db.commit()
    return ServedQuestionRead(**served.payload)


@router.get("/skills/{skill_slug}/question", response_model=ServedQuestionRead)
def quick_question(skill_slug: str, db: DbSession, student: CurrentStudent) -> ServedQuestionRead:
    """Serve a single question outside a session — used by the 'try it' widgets."""
    skill = _resolve_skill(db, None, skill_slug)
    try:
        served = serve_question(db, student, skill)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return ServedQuestionRead(**served.payload)


@router.get("/variants/{variant_id}/hints/{index}", response_model=HintRead)
def get_hint(
    variant_id: int, index: int, db: DbSession, student: CurrentStudent
) -> HintRead:
    """Reveal one hint. Hints are served one at a time so ``hints_used`` is meaningful."""
    variant = db.get(QuestionVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    hints = variant.rendered_hints or []
    if index < 0 or index >= len(hints):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such hint")

    return HintRead(
        index=index,
        text=hints[index].get("text", ""),
        is_last=index == len(hints) - 1,
    )


@router.post("/submit", response_model=SubmitAnswerResponse)
def submit_answer(
    payload: SubmitAnswerRequest, db: DbSession, student: CurrentStudent
) -> SubmitAnswerResponse:
    """Grade an answer and apply every consequence: mastery, XP, streak, achievements."""
    variant = db.scalar(
        select(QuestionVariant)
        .where(QuestionVariant.id == payload.variant_id)
        .options(
            selectinload(QuestionVariant.question).selectinload(Question.skill)
        )
    )
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    session = None
    if payload.session_id is not None:
        session = db.get(PracticeSession, payload.session_id)
        if session is None or session.student_id != student.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        outcome = record_attempt(
            db,
            student,
            variant,
            payload.answer,
            hints_used=payload.hints_used,
            time_spent_seconds=payload.time_spent_seconds,
            session=session,
        )
    except AnswerFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc

    db.commit()

    return SubmitAnswerResponse(
        is_correct=outcome.grade.is_correct,
        score=round(outcome.grade.score, 4),
        message=outcome.grade.message,
        details=outcome.grade.details,
        correct_answer=outcome.grade.correct_answer,
        # The worked solution is released only now, after the student has committed.
        solution=variant.rendered_solution or [],
        mastery=MasteryChange(
            before=round(outcome.mastery_before, 4),
            after=round(outcome.mastery_after, 4),
            delta=round(outcome.mastery_after - outcome.mastery_before, 4),
            is_mastered=outcome.mastery_after >= 0.95,
            newly_mastered=outcome.is_newly_mastered,
        ),
        gamification=outcome.gamification.as_dict(),
        session=SessionRead.model_validate(session) if session else None,
    )


@router.post("/sessions/{session_id}/complete", response_model=SessionRead)
def complete_session(session_id: int, db: DbSession, student: CurrentStudent) -> SessionRead:
    session = db.get(PracticeSession, session_id)
    if session is None or session.student_id != student.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session.completed_at is None:
        session.completed_at = dt.datetime.now(dt.UTC)
        awarded = award_xp(db, student, XP_RULES["session_complete"], "session_complete",
                           {"session_id": session.id})
        if (
            session.questions_answered > 0
            and session.questions_correct == session.questions_answered
        ):
            awarded += award_xp(db, student, XP_RULES["perfect_session"], "perfect_session",
                                {"session_id": session.id})
        session.xp_earned = (session.xp_earned or 0) + awarded
        db.commit()
        db.refresh(session)

    return SessionRead.model_validate(session)


@router.get("/sessions/{session_id}", response_model=SessionRead)
def get_session(session_id: int, db: DbSession, student: CurrentStudent) -> SessionRead:
    session = db.get(PracticeSession, session_id)
    if session is None or session.student_id != student.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionRead.model_validate(session)


@router.get("/recommendations", response_model=list[RecommendationRead])
def recommendations(
    db: DbSession,
    student: CurrentStudent,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    subject: Annotated[str | None, Query()] = None,
) -> list[RecommendationRead]:
    results = recommend_next(db, student.id, limit=limit, subject_slug=subject)
    return [RecommendationRead(**rec.as_dict()) for rec in results]


@router.get("/path/{unit_slug}", response_model=list[PathNodeRead])
def learning_path(unit_slug: str, db: DbSession, student: CurrentStudent) -> list[PathNodeRead]:
    """The visual learning path for one unit: mastered / in progress / available / locked."""
    unit = db.scalar(select(Unit).where(Unit.slug == unit_slug))
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

    nodes = build_learning_path(db, student.id, unit_id=unit.id)
    return [
        PathNodeRead(
            skill_id=node.skill.id,
            skill_slug=node.skill.slug,
            skill_name=node.skill.name,
            topic=node.skill.topic.title if node.skill.topic else None,
            difficulty=node.skill.difficulty,
            mastery=round(node.mastery, 4),
            status=node.status,
            attempts=node.attempts,
            blocked_by=node.blocked_by,
        )
        for node in nodes
    ]


@router.get("/topics/{topic_slug}/path", response_model=list[PathNodeRead])
def topic_path(topic_slug: str, db: DbSession, student: CurrentStudent) -> list[PathNodeRead]:
    topic = db.scalar(select(Topic).where(Topic.slug == topic_slug))
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    nodes = build_learning_path(db, student.id, unit_id=topic.unit_id)
    return [
        PathNodeRead(
            skill_id=n.skill.id, skill_slug=n.skill.slug, skill_name=n.skill.name,
            topic=n.skill.topic.title if n.skill.topic else None,
            difficulty=n.skill.difficulty, mastery=round(n.mastery, 4), status=n.status,
            attempts=n.attempts, blocked_by=n.blocked_by,
        )
        for n in nodes
        if n.skill.topic_id == topic.id
    ]
