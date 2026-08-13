"""The practice loop: serve a question, grade it, update mastery, award progress.

This module is where the exercise engine, the BKT model and the gamification layer meet. It is
the single write path for student learning data, which is deliberate — mastery must never be
updated from two places with slightly different rules.
"""

from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.adaptive.bkt import MASTERY_THRESHOLD, BKTParameters, update_mastery
from app.exercise_engine import (
    GenerationError,
    QuestionTemplate,
    generate_variant,
    grade_answer,
)
from app.exercise_engine.graders import GradeResult
from app.models import (
    Attempt,
    PracticeSession,
    Question,
    QuestionVariant,
    ReviewStatus,
    Skill,
    StudentProfile,
    StudentSkillMastery,
)
from app.services.gamification import (
    XP_RULES,
    GamificationResult,
    award_xp,
    check_achievements,
    level_for_xp,
    update_streak,
)

__all__ = [
    "ServedQuestion",
    "AttemptOutcome",
    "serve_question",
    "record_attempt",
    "get_or_create_mastery",
    "RECENT_WINDOW",
]

# How many recent outcomes to keep for the "recent performance" signal.
RECENT_WINDOW = 10

# Avoid showing the same template twice in a row within a session where possible.
_MAX_SELECTION_TRIES = 12


@dataclass
class ServedQuestion:
    question: Question
    variant: QuestionVariant
    payload: dict[str, Any]


@dataclass
class AttemptOutcome:
    attempt: Attempt
    grade: GradeResult
    mastery_before: float
    mastery_after: float
    is_newly_mastered: bool
    gamification: GamificationResult


# --------------------------------------------------------------------------------------
# mastery bookkeeping
# --------------------------------------------------------------------------------------


def get_or_create_mastery(
    db: Session, student_id: int, skill: Skill
) -> StudentSkillMastery:
    record = db.scalar(
        select(StudentSkillMastery).where(
            StudentSkillMastery.student_id == student_id,
            StudentSkillMastery.skill_id == skill.id,
        )
    )
    if record is None:
        record = StudentSkillMastery(
            student_id=student_id,
            skill_id=skill.id,
            mastery_probability=skill.bkt_p_init,
            recent_outcomes=[],
        )
        db.add(record)
        db.flush()
    return record


# --------------------------------------------------------------------------------------
# serving
# --------------------------------------------------------------------------------------


def _candidate_questions(
    db: Session,
    skill_id: int,
    *,
    difficulty: int | None = None,
    exclude_ids: list[int] | None = None,
) -> list[Question]:
    query = select(Question).where(
        Question.skill_id == skill_id,
        # AI-drafted and teacher-draft questions must never reach a student unreviewed.
        Question.status == ReviewStatus.PUBLISHED,
    )
    if difficulty is not None:
        query = query.where(Question.difficulty == difficulty)
    if exclude_ids:
        query = query.where(Question.id.not_in(exclude_ids))
    return list(db.scalars(query))


def _target_difficulty(mastery: float) -> int:
    """Pick a difficulty that sits just above the student's current level.

    Practising at the edge of ability is where learning happens; questions that are far too easy
    or far too hard both waste the student's time.
    """
    if mastery < 0.25:
        return 1
    if mastery < 0.50:
        return 2
    if mastery < 0.75:
        return 3
    if mastery < 0.90:
        return 4
    return 5


def serve_question(
    db: Session,
    student: StudentProfile,
    skill: Skill,
    *,
    session: PracticeSession | None = None,
    exclude_question_ids: list[int] | None = None,
    locale: str = "en",
) -> ServedQuestion:
    """Choose a question for this student and skill, render a fresh variant, and persist it."""
    record = get_or_create_mastery(db, student.id, skill)
    target = _target_difficulty(record.mastery_probability)
    exclude = list(exclude_question_ids or [])

    # Widen the difficulty search outward from the target until we find something.
    candidates: list[Question] = []
    for offset in (0, -1, 1, -2, 2, None):
        difficulty = None if offset is None else max(1, min(5, target + offset))
        candidates = _candidate_questions(
            db, skill.id, difficulty=difficulty, exclude_ids=exclude
        )
        if candidates:
            break

    if not candidates and exclude:
        # Everything has been seen this session; allow repeats rather than failing.
        candidates = _candidate_questions(db, skill.id)

    if not candidates:
        raise LookupError(f"No published questions available for skill '{skill.slug}'")

    question = secrets.choice(candidates)

    # A fresh random seed per serve is what makes a parametric template feel like an endless
    # supply of questions. secrets rather than random: seeds are effectively question identity,
    # and predictable seeds would let a student precompute answers.
    for _ in range(_MAX_SELECTION_TRIES):
        seed = secrets.randbelow(2**31 - 1)
        try:
            generated = generate_variant(QuestionTemplate.from_model(question, locale), seed)
            break
        except GenerationError:
            # A template whose constraints failed on this seed may succeed on another; but if it
            # keeps failing, fall through to the error below rather than looping forever.
            continue
    else:
        raise LookupError(f"Question template '{question.slug}' failed to generate a variant")

    variant = db.scalar(
        select(QuestionVariant).where(
            QuestionVariant.question_id == question.id, QuestionVariant.seed == seed
        )
    )
    if variant is None:
        variant = QuestionVariant(
            question_id=question.id,
            seed=seed,
            variable_values=generated.variable_values,
            rendered=generated.rendered,
            answer=generated.answer,
            rendered_hints=generated.hints,
            rendered_solution=generated.solution,
        )
        db.add(variant)
        db.flush()

    question.times_served = (question.times_served or 0) + 1

    # The student-facing payload. Note what is absent: `answer` and `solution`.
    payload: dict[str, Any] = {
        "variant_id": variant.id,
        "question_id": question.id,
        "question_slug": question.slug,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "estimated_seconds": question.estimated_seconds,
        "skill": {"id": skill.id, "slug": skill.slug, "name": skill.name},
        **generated.rendered,
        "hints": [{"index": i, "text": h.get("text", "")}
                  for i, h in enumerate(generated.hints)],
    }
    return ServedQuestion(question=question, variant=variant, payload=payload)


# --------------------------------------------------------------------------------------
# grading + recording
# --------------------------------------------------------------------------------------


def record_attempt(
    db: Session,
    student: StudentProfile,
    variant: QuestionVariant,
    user_answer: dict[str, Any],
    *,
    hints_used: int = 0,
    time_spent_seconds: int = 0,
    session: PracticeSession | None = None,
) -> AttemptOutcome:
    """Grade a submission and apply every downstream effect in one transaction."""
    question = variant.question
    skill = question.skill

    grade = grade_answer(
        question.question_type, variant.answer, user_answer, variant.rendered
    )

    record = get_or_create_mastery(db, student.id, skill)
    mastery_before = record.mastery_probability

    choice_count = len(variant.rendered.get("choices", []) or []) or None
    update = update_mastery(
        mastery_before,
        grade.is_correct,
        BKTParameters.from_skill(skill),
        question_type=question.question_type,
        choice_count=choice_count,
        hints_used=hints_used,
    )

    now = dt.datetime.now(dt.UTC)
    was_mastered = record.mastered_at is not None

    record.mastery_probability = update.mastery
    record.attempts = (record.attempts or 0) + 1
    if grade.is_correct:
        record.correct = (record.correct or 0) + 1
        record.consecutive_correct = (record.consecutive_correct or 0) + 1
    else:
        record.incorrect = (record.incorrect or 0) + 1
        record.consecutive_correct = 0
    record.last_practiced_at = now
    record.recent_outcomes = (
        [*(record.recent_outcomes or []), 1 if grade.is_correct else 0]
    )[-RECENT_WINDOW:]

    is_newly_mastered = False
    if update.mastery >= MASTERY_THRESHOLD and not was_mastered:
        record.mastered_at = now
        is_newly_mastered = True

    question.times_correct = (question.times_correct or 0) + int(grade.is_correct)

    attempt = Attempt(
        student_id=student.id,
        question_id=question.id,
        variant_id=variant.id,
        skill_id=skill.id,
        session_id=session.id if session else None,
        user_answer=user_answer,
        is_correct=grade.is_correct,
        score=grade.score,
        feedback=grade.as_dict(),
        hints_used=hints_used,
        time_spent_seconds=max(0, time_spent_seconds),
        mastery_before=mastery_before,
        mastery_after=update.mastery,
    )
    db.add(attempt)

    if session is not None:
        session.questions_answered = (session.questions_answered or 0) + 1
        session.questions_correct = (session.questions_correct or 0) + int(grade.is_correct)
        if session.mastery_before is None:
            session.mastery_before = mastery_before
        session.mastery_after = update.mastery

    # --- gamification -------------------------------------------------------------
    level_before = student.level or level_for_xp(student.xp_total or 0)
    result = GamificationResult(level_before=level_before)

    if grade.is_correct:
        reason = "correct_first_try" if hints_used == 0 else "correct_with_hints"
    else:
        reason = "incorrect_attempt"
    result.xp_awarded += award_xp(
        db, student, XP_RULES[reason], reason, {"skill": skill.slug, "question": question.slug}
    )

    if is_newly_mastered:
        result.xp_awarded += award_xp(
            db, student, XP_RULES["skill_mastered"], "skill_mastered", {"skill": skill.slug}
        )

    if update_streak(student):
        result.streak_extended = True
        result.xp_awarded += award_xp(db, student, XP_RULES["streak_day"], "streak_day")
    result.streak_days = student.streak_days or 0

    if session is not None:
        session.xp_earned = (session.xp_earned or 0) + result.xp_awarded

    result.new_achievements = check_achievements(db, student)
    result.level_after = student.level or level_before

    db.flush()

    return AttemptOutcome(
        attempt=attempt,
        grade=grade,
        mastery_before=mastery_before,
        mastery_after=update.mastery,
        is_newly_mastered=is_newly_mastered,
        gamification=result,
    )


def summarise_student(db: Session, student_id: int) -> dict[str, Any]:
    """Aggregate mastery figures used across the student and parent dashboards."""
    rows = list(
        db.scalars(
            select(StudentSkillMastery)
            .where(StudentSkillMastery.student_id == student_id)
            .options(selectinload(StudentSkillMastery.skill))
        )
    )
    total_attempts = db.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.student_id == student_id)
    ) or 0
    total_correct = db.scalar(
        select(func.count())
        .select_from(Attempt)
        .where(Attempt.student_id == student_id, Attempt.is_correct.is_(True))
    ) or 0

    mastered = [r for r in rows if r.mastered_at is not None]
    practising = [r for r in rows if r.mastered_at is None and r.attempts > 0]

    return {
        "skills_tracked": len(rows),
        "skills_mastered": len(mastered),
        "skills_in_progress": len(practising),
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "accuracy": round(total_correct / total_attempts, 4) if total_attempts else None,
        "average_mastery": (
            round(sum(r.mastery_probability for r in rows) / len(rows), 4) if rows else 0.0
        ),
    }
