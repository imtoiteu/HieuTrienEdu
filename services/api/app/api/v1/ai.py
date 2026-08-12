"""AI Assist endpoints — **prepared, not powered**.

Per the project brief, AI is architecture-only at this stage. These endpoints exist so the
frontend, database and permission model are finished and correct, but with the default
configuration (``AI_PROVIDER=disabled``) every one of them returns ``available: false`` and an
explanation. Nothing here fabricates tutoring content.

The contract the UI relies on:

* ``GET  /ai/status``   — what is configured, and which features would be available.
* ``POST /ai/tutor-hint``, ``/ai/explain-mistake``, ``/ai/generate-questions`` — return an
  ``AIResult`` shape whether or not a provider is configured, so the client renders one code path.
* Every call is written to ``ai_interactions`` for audit, including refusals.
* Generated questions land as ``pending_review`` drafts and are **never** served to a student
  until a teacher publishes them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, require_roles
from app.models import AIGenerationBatch, Question, QuestionVariant, ReviewStatus, Skill, UserRole
from app.services.ai_provider import AI_FEATURES, get_ai_provider, log_interaction

router = APIRouter(prefix="/ai", tags=["ai"])


class AIStatus(BaseModel):
    enabled: bool
    provider: str
    model: str | None = None
    features: dict[str, str]
    message: str


class TutorHintRequest(BaseModel):
    variant_id: int
    student_answer: str = Field(default="", max_length=2000)


class ExplainMistakeRequest(BaseModel):
    variant_id: int
    student_answer: str = Field(max_length=2000)


class GenerateQuestionsRequest(BaseModel):
    skill_id: int
    count: int = Field(default=10, ge=1, le=50)
    difficulty: int = Field(default=2, ge=1, le=5)
    question_type: str = Field(default="multiple_choice", max_length=30)
    notes: str | None = Field(default=None, max_length=2000)


class AIResponse(BaseModel):
    available: bool
    content: str | None = None
    reason: str | None = None
    provider: str
    model: str | None = None
    requires_review: bool = True
    interaction_id: int | None = None


@router.get("/status", response_model=AIStatus)
def ai_status() -> AIStatus:
    provider = get_ai_provider()
    return AIStatus(
        enabled=provider.is_available,
        provider=provider.name,
        model=settings.ai_model,
        features=AI_FEATURES,
        message=(
            "AI Assist is connected and ready."
            if provider.is_available
            else (
                "AI Assist is prepared but not enabled. The interfaces, database schema and UI "
                "are in place; connecting a model provider is a later phase of the project."
            )
        ),
    )


def _load_variant(db: DbSession, variant_id: int) -> QuestionVariant:
    variant = db.get(QuestionVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return variant


@router.post("/tutor-hint", response_model=AIResponse)
def tutor_hint(
    payload: TutorHintRequest, db: DbSession, user: CurrentUser
) -> AIResponse:
    """Ask for a Socratic nudge that guides without giving the answer away."""
    variant = _load_variant(db, payload.variant_id)
    provider = get_ai_provider()

    result = provider.tutor_hint(
        question_prompt=variant.rendered.get("prompt", ""),
        student_answer=payload.student_answer,
        skill_name=variant.question.skill.name if variant.question.skill else "",
    )
    interaction = log_interaction(
        db,
        feature="tutor_hint",
        result=result,
        user_id=user.id,
        student_id=user.student_profile.id if user.student_profile else None,
        context={"variant_id": variant.id, "question_id": variant.question_id},
    )
    db.commit()

    return AIResponse(
        **result.as_dict(),
        interaction_id=interaction.id,
    )


@router.post("/explain-mistake", response_model=AIResponse)
def explain_mistake(
    payload: ExplainMistakeRequest, db: DbSession, user: CurrentUser
) -> AIResponse:
    variant = _load_variant(db, payload.variant_id)
    provider = get_ai_provider()

    result = provider.explain_mistake(
        question_prompt=variant.rendered.get("prompt", ""),
        student_answer=payload.student_answer,
        correct_answer=str(variant.answer),
    )
    interaction = log_interaction(
        db,
        feature="explain_mistake",
        result=result,
        user_id=user.id,
        student_id=user.student_profile.id if user.student_profile else None,
        context={"variant_id": variant.id},
    )
    db.commit()
    return AIResponse(**result.as_dict(), interaction_id=interaction.id)


@router.post(
    "/generate-questions",
    response_model=dict,
    dependencies=[Depends(require_roles(UserRole.TEACHER))],
)
def generate_questions(
    payload: GenerateQuestionsRequest, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    """Request draft questions for a skill.

    Creates the batch record and returns the provider result. When a provider is eventually
    connected, the drafts it produces are written as ``pending_review`` questions attached to this
    batch — the human-approval gate is enforced by the question query filters, not by convention.
    """
    skill = db.get(Skill, payload.skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    course = skill.topic.unit.course if skill.topic and skill.topic.unit else None
    provider = get_ai_provider()

    batch = AIGenerationBatch(
        requested_by_id=user.id,
        skill_id=skill.id,
        subject_slug=course.subject.slug if course and course.subject else None,
        grade=course.grade if course else None,
        difficulty=payload.difficulty,
        question_type=payload.question_type,
        count_requested=payload.count,
        status=ReviewStatus.DRAFT,
        requires_human_approval=True,
        notes=payload.notes,
    )
    db.add(batch)
    db.flush()

    result = provider.generate_questions(
        skill_name=skill.name,
        grade=course.grade if course else 6,
        difficulty=payload.difficulty,
        count=payload.count,
        question_type=payload.question_type,
    )
    log_interaction(
        db,
        feature="generate_questions",
        result=result,
        user_id=user.id,
        context={"batch_id": batch.id, "skill_id": skill.id},
    )

    if not result.available:
        batch.status = ReviewStatus.REJECTED
        batch.notes = (batch.notes or "") + f"\nNot generated: {result.reason}"

    db.commit()

    return {
        "batch_id": batch.id,
        "available": result.available,
        "reason": result.reason,
        "provider": result.provider,
        "count_requested": payload.count,
        "count_generated": batch.count_generated,
        "requires_human_approval": True,
        "content": result.content,
        "next_step": (
            "Review the drafts under Teacher → Question bank → Pending review, then publish the "
            "ones you want students to see."
            if result.available
            else "No drafts were created because AI Assist is not enabled."
        ),
    }


@router.get(
    "/batches",
    dependencies=[Depends(require_roles(UserRole.TEACHER))],
)
def list_batches(db: DbSession) -> list[dict[str, Any]]:
    batches = db.scalars(
        select(AIGenerationBatch).order_by(AIGenerationBatch.created_at.desc()).limit(50)
    )
    return [
        {
            "id": b.id, "skill_id": b.skill_id, "subject_slug": b.subject_slug, "grade": b.grade,
            "difficulty": b.difficulty, "question_type": b.question_type,
            "count_requested": b.count_requested, "count_generated": b.count_generated,
            "count_approved": b.count_approved, "status": b.status,
            "requires_human_approval": b.requires_human_approval, "notes": b.notes,
            "created_at": b.created_at,
        }
        for b in batches
    ]


@router.get(
    "/pending-questions",
    dependencies=[Depends(require_roles(UserRole.TEACHER))],
)
def pending_questions(db: DbSession) -> list[dict[str, Any]]:
    """AI-drafted questions awaiting a teacher's approval."""
    rows = db.scalars(
        select(Question)
        .where(
            Question.generated_by_ai.is_(True),
            Question.status == ReviewStatus.PENDING_REVIEW,
        )
        .order_by(Question.created_at.desc())
        .limit(200)
    )
    return [
        {
            "id": q.id, "slug": q.slug, "prompt": q.prompt, "question_type": q.question_type,
            "difficulty": q.difficulty, "skill_id": q.skill_id, "status": q.status,
            "created_at": q.created_at,
        }
        for q in rows
    ]
