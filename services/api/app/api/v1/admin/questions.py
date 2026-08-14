"""Exercise and question-bank management, including preview-as-student and bulk import.

Questions are *templates*: a row with variables generates thousands of distinct exercises, a row
without them is a plain static question. The admin UI never has to know the difference, and
neither does this module — both go through the same create/validate/preview path.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from pydantic import Field
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
    paginate,
    record_audit,
)
from app.api.v1.admin._translations import (
    TranslationsPayload,
    apply_translations,
    read_translations,
)
from app.core.deps import RequestLocale
from app.core.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, localise, normalise_locale
from app.core.text import unique_slug
from app.exercise_engine.generator import (
    GenerationError,
    QuestionTemplate,
    generate_variant,
)
from app.models import (
    Attempt,
    Question,
    QuestionType,
    ReviewStatus,
    Skill,
    Topic,
    Unit,
)

router = APIRouter(prefix="/questions", tags=["admin:questions"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 2000


class QuestionIn(TranslationsPayload):
    skill_id: int
    question_type: QuestionType
    prompt: str = Field(min_length=1)
    slug: str | None = Field(default=None, max_length=200)
    difficulty: int = Field(default=2, ge=1, le=5)
    variables: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    answer_spec: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    hints: list[dict[str, Any]] = Field(default_factory=list)
    solution: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    estimated_seconds: int = Field(default=60, ge=5, le=3600)
    status: ReviewStatus = ReviewStatus.DRAFT
    source: str | None = Field(default=None, max_length=200)
    license: str | None = Field(default=None, max_length=80)
    attribution: str | None = None


class QuestionUpdate(TranslationsPayload):
    skill_id: int | None = None
    question_type: QuestionType | None = None
    prompt: str | None = Field(default=None, min_length=1)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    variables: dict[str, Any] | None = None
    constraints: list[str] | None = None
    answer_spec: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    hints: list[dict[str, Any]] | None = None
    solution: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    estimated_seconds: int | None = Field(default=None, ge=5, le=3600)
    status: ReviewStatus | None = None


def _question_row(
    question: Question, skill: Skill | None = None, locale: str = DEFAULT_LOCALE
) -> dict[str, Any]:
    return {
        "id": question.id,
        "slug": question.slug,
        "prompt": question.prompt,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "skill_id": question.skill_id,
        "skill_name": localise(skill, "name", locale) if skill else None,
        "subject_slug": question.subject_slug,
        "topic_slug": question.topic_slug,
        "grade": question.grade,
        "status": question.status,
        "is_parametric": question.is_parametric,
        "tags": question.tags or [],
        "estimated_seconds": question.estimated_seconds,
        "times_served": question.times_served,
        "times_correct": question.times_correct,
        "success_rate": question.success_rate,
        "generated_by_ai": question.generated_by_ai,
        "source": question.source,
        # The listing shows the prompt, and the editor needs both languages to round-trip, so
        # the row carries them here exactly as every other translatable listing does.
        "translations": read_translations(question),
        "created_at": question.created_at,
        "updated_at": question.updated_at,
    }


def _check_generates(question: Question) -> None:
    """Prove the question renders in every language it claims to be available in.

    A question is a template, so a translation is a template too — a Vietnamese prompt with a
    mistyped ``{{ }}`` placeholder fails only for Vietnamese students, and only once one of them
    hits that exercise. Generating a variant per locale here turns that into a save-time error.

    Several seeds are tried because a placeholder can be valid for one draw of the variables and
    not another (a division that only sometimes lands on a whole number, say).
    """
    for locale in SUPPORTED_LOCALES:
        if locale != DEFAULT_LOCALE and locale not in (question.i18n or {}):
            continue
        template = QuestionTemplate.from_model(question, locale)
        for seed in (1, 7, 23, 101):
            try:
                generate_variant(template, seed=seed)
            except GenerationError as exc:
                label = "" if locale == DEFAULT_LOCALE else f" [{locale}]"
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"This question could not be generated{label}: {exc}",
                ) from exc


def _resolve_taxonomy(db, skill_id: int) -> tuple[Skill, str, int, str]:
    """Denormalised subject/grade/topic for a skill, so list filters need no joins."""
    skill = db.scalar(
        select(Skill)
        .where(Skill.id == skill_id)
        .options(selectinload(Skill.topic).selectinload(Topic.unit).selectinload(Unit.course))
    )
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    topic = skill.topic
    unit = topic.unit if topic else None
    course = unit.course if unit else None
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That skill is not attached to a course, so its subject and grade are unknown",
        )
    subject_slug = course.subject.slug if course.subject else ""
    return skill, subject_slug, course.grade, topic.slug


def _validate_answerable(payload_type: str, answer_spec: dict, options: dict) -> None:
    """Refuse a question a student could not possibly answer correctly.

    Without this a well-meaning admin can save a multiple-choice question with no choices, and it
    only fails later, in front of a student, as a blank exercise.
    """
    if payload_type in {QuestionType.MULTIPLE_CHOICE, QuestionType.MULTIPLE_SELECT}:
        choices = options.get("choices") or []
        if len(choices) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A multiple-choice question needs at least two options",
            )
        correct = [c for c in choices if c.get("is_correct")]
        if not correct:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Mark at least one option as the correct answer",
            )
        if payload_type == QuestionType.MULTIPLE_CHOICE and len(correct) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "A single-answer question has more than one correct option. Use "
                    "“multiple select” if several answers are right."
                ),
            )
        return

    if payload_type == QuestionType.TRUE_FALSE:
        if answer_spec.get("value") is None and not options.get("choices"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A true/false question needs its correct value set",
            )
        return

    if payload_type == QuestionType.MATCHING:
        if not options.get("left") or not options.get("right"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A matching question needs both a left and a right column",
            )
        return

    if payload_type == QuestionType.ORDERING:
        if len(options.get("items") or []) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An ordering question needs at least two items",
            )
        return

    if payload_type == QuestionType.FILL_BLANK:
        if not options.get("blanks"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A fill-in-the-blank question needs at least one blank",
            )
        return

    # numeric / expression / short answer
    if not answer_spec:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This question type needs an answer specification",
        )


@router.get("")
def list_questions(
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
    skill_id: Annotated[int | None, Query()] = None,
    topic_slug: Annotated[str | None, Query(max_length=140)] = None,
    subject: Annotated[str | None, Query(max_length=60)] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    question_type: Annotated[QuestionType | None, Query()] = None,
    difficulty: Annotated[int | None, Query(ge=1, le=5)] = None,
    question_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(Question).options(selectinload(Question.skill))
    if skill_id:
        query = query.where(Question.skill_id == skill_id)
    if topic_slug:
        query = query.where(Question.topic_slug == topic_slug)
    if subject:
        query = query.where(Question.subject_slug == subject)
    if grade:
        query = query.where(Question.grade == grade)
    if question_type:
        query = query.where(Question.question_type == question_type)
    if difficulty:
        query = query.where(Question.difficulty == difficulty)
    if question_status:
        query = query.where(Question.status == question_status)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Question.prompt.ilike(pattern), Question.slug.ilike(pattern)))

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        Question,
        params,
        {
            "difficulty": Question.difficulty,
            "type": Question.question_type,
            "status": Question.status,
            "served": Question.times_served,
            "created_at": Question.created_at,
            "_default": Question.created_at,
        },
    )
    rows, total = paginate(db, query, params)
    return build_page([_question_row(row, row.skill, locale) for row in rows], total, params)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionIn, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    skill, subject_slug, grade, topic_slug = _resolve_taxonomy(db, payload.skill_id)
    _validate_answerable(payload.question_type, payload.answer_spec, payload.options)

    question = Question(
        **payload.model_dump(exclude={"slug", "translations"}),
        slug=unique_slug(
            payload.slug or f"{skill.slug}-{payload.prompt[:40]}",
            lambda candidate: db.scalar(select(Question.id).where(Question.slug == candidate))
            is not None,
            max_length=200,
        ),
        subject_slug=subject_slug,
        grade=grade,
        topic_slug=topic_slug,
        is_parametric=bool(payload.variables),
        created_by_id=admin.id,
    )
    apply_translations(question, payload.translations)
    db.add(question)
    db.flush()

    # Prove the question can actually be rendered and graded before it is saved. A template that
    # throws at generation time is a broken exercise; better to reject it here than to serve it.
    try:
        _check_generates(question)
    except HTTPException:
        db.rollback()
        raise

    record_audit(
        db, admin, "create", "question", question.id, f"Created exercise “{question.slug}”"
    )
    db.commit()
    db.refresh(question)
    return _question_row(question, skill, locale)


@router.get("/{question_id}")
def get_question(
    question_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    question = db.scalar(
        select(Question).where(Question.id == question_id).options(selectinload(Question.skill))
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    data = _question_row(question, question.skill, locale)
    data.update(
        {
            "variables": question.variables or {},
            "constraints": question.constraints or [],
            "answer_spec": question.answer_spec or {},
            "options": question.options or {},
            "hints": question.hints or [],
            "solution": question.solution or [],
            "license": question.license,
            "attribution": question.attribution,
        }
    )
    return data


@router.patch("/{question_id}")
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
) -> dict[str, Any]:
    question = get_or_404(db, Question, question_id, "Exercise")
    fields = payload.model_dump(exclude_unset=True, exclude={"translations"})

    if fields.get("skill_id") is not None:
        _, subject_slug, grade, topic_slug = _resolve_taxonomy(db, fields["skill_id"])
        question.subject_slug = subject_slug
        question.grade = grade
        question.topic_slug = topic_slug

    before = {key: getattr(question, key) for key in fields}
    for key, value in fields.items():
        setattr(question, key, value)
    if "variables" in fields:
        question.is_parametric = bool(question.variables)

    apply_translations(question, payload.translations)
    _validate_answerable(
        question.question_type, question.answer_spec or {}, question.options or {}
    )
    db.flush()
    try:
        _check_generates(question)
    except HTTPException:
        db.rollback()
        raise

    record_audit(
        db, admin, "update", "question", question.id, f"Updated exercise “{question.slug}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(question)
    return _question_row(question, locale=locale)


@router.get("/{question_id}/preview")
def preview_question(
    question_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    seed: Annotated[int | None, Query(ge=0, le=2**31 - 1)] = None,
    reveal: Annotated[bool, Query()] = True,
    preview_locale: Annotated[str, Query(alias="locale", max_length=10)] = DEFAULT_LOCALE,
) -> dict[str, Any]:
    """Render one concrete variant exactly as a student would receive it.

    ``reveal=false`` returns the student's view *without* the answer, which is what the "preview
    as student" toggle uses — it is the only honest way to check a question reads correctly
    without the answer being visible on the same screen.

    ``locale`` picks the language, so an editor can check that the Vietnamese prompt reads well
    with real numbers substituted in — the thing a side-by-side translation form cannot show.
    """
    preview_locale = normalise_locale(preview_locale)
    question = db.scalar(
        select(Question).where(Question.id == question_id).options(selectinload(Question.skill))
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    import random

    chosen_seed = seed if seed is not None else random.randint(1, 10**6)
    try:
        variant = generate_variant(
            QuestionTemplate.from_model(question, preview_locale), seed=chosen_seed
        )
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This question could not be generated: {exc}",
        ) from exc

    student_view = dict(variant.rendered)
    result = {
        "question_id": question.id,
        "slug": question.slug,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "estimated_seconds": question.estimated_seconds,
        "seed": chosen_seed,
        "locale": preview_locale,
        "skill": (
            {
                "id": question.skill.id,
                "slug": question.skill.slug,
                "name": localise(question.skill, "name", preview_locale),
            }
            if question.skill
            else None
        ),
        "student_view": student_view,
        "variable_values": variant.variable_values,
        "hints": variant.hints,
        "hint_count": len(variant.hints or []),
    }
    if reveal:
        result["answer"] = variant.answer
        result["solution"] = variant.solution
    return result


@router.post("/{question_id}/publish")
def publish_question(
    question_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    return _set_status(db, admin, question_id, ReviewStatus.PUBLISHED, locale)


@router.post("/{question_id}/unpublish")
def unpublish_question(
    question_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    return _set_status(db, admin, question_id, ReviewStatus.DRAFT, locale)


@router.post("/{question_id}/archive")
def archive_question(
    question_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    return _set_status(db, admin, question_id, ReviewStatus.ARCHIVED, locale)


def _set_status(
    db, admin, question_id: int, value: ReviewStatus, locale: str = DEFAULT_LOCALE
) -> dict[str, Any]:
    question = get_or_404(db, Question, question_id, "Exercise")
    question.status = value
    record_audit(
        db, admin, str(value), "question", question.id,
        f"Set exercise “{question.slug}” to {value}",
    )
    db.commit()
    db.refresh(question)
    return _question_row(question, locale=locale)


@router.post("/bulk-status")
def bulk_status(
    payload: dict[str, Any], db: DbSession, admin: CurrentAdmin,
) -> dict[str, Any]:
    """Publish or archive many exercises at once — the review queue needs this."""
    ids = payload.get("ids") or []
    value = payload.get("status")
    if value not in set(ReviewStatus):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown status. Expected one of: {sorted(str(s) for s in ReviewStatus)}",
        )
    rows = list(db.scalars(select(Question).where(Question.id.in_(ids))))
    for question in rows:
        question.status = value
    record_audit(
        db, admin, str(value), "question", None, f"Set {len(rows)} exercise(s) to {value}"
    )
    db.commit()
    return {"updated": len(rows), "status": value}


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    """Delete an exercise.

    Refused once students have attempted it — deleting would cascade their attempts away and
    silently change every affected student's mastery history. Archiving is offered instead, which
    stops the question being served without rewriting the past.
    """
    question = get_or_404(db, Question, question_id, "Exercise")
    attempts = (
        db.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.question_id == question_id)
        )
        or 0
    )
    if attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{attempts} student attempt(s) reference this exercise. Archive it instead — "
                "deleting would erase those results."
            ),
        )
    slug = question.slug
    db.delete(question)
    record_audit(db, admin, "delete", "question", question_id, f"Deleted exercise “{slug}”")
    db.commit()


# --------------------------------------------------------------------------------------
# bulk import
# --------------------------------------------------------------------------------------

IMPORT_COLUMNS = (
    "question",
    "type",
    "options",
    "correct_answer",
    "explanation",
    "difficulty",
    "skill_slug",
    "tags",
)


@router.get("/import/template")
def import_template(admin: CurrentAdmin) -> dict[str, Any]:
    """The documented import format, served from the code that actually parses it."""
    return {
        "columns": list(IMPORT_COLUMNS),
        "required": ["question", "type", "skill_slug"],
        "notes": {
            "type": [str(t) for t in QuestionType],
            "options": (
                "For multiple choice / select: separate choices with a pipe, e.g. “4|5|6|7”. "
                "Leave blank for numeric or short-answer questions."
            ),
            "correct_answer": (
                "For multiple choice: the 1-based index or the exact option text. "
                "For multiple select: several, separated by a pipe. "
                "For true/false: “true” or “false”. For numeric: the value."
            ),
            "difficulty": "1 (easiest) to 5 (hardest). Defaults to 2.",
            "tags": "Optional, separated by a pipe.",
        },
        "csv_example": (
            "question,type,options,correct_answer,explanation,difficulty,skill_slug,tags\n"
            '"What is 2 + 3?",multiple_choice,4|5|6|7,5,"Add the two numbers.",1,'
            "adding-fractions,arithmetic\n"
        ),
    }


def _parse_rows(raw: bytes, filename: str) -> list[dict[str, Any]]:
    text = raw.decode("utf-8-sig", errors="replace")
    if filename.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"That file is not valid JSON: {exc}",
            ) from exc
        rows = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Expected a JSON array of questions, or an object with a “questions” array",
            )
        return rows
    return list(csv.DictReader(io.StringIO(text)))


def _row_to_question(row: dict[str, Any], index: int, skills: dict[str, Skill]) -> dict[str, Any]:
    """Turn one import row into question fields, or explain precisely why it cannot be."""
    prompt = str(row.get("question") or row.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("missing “question” text")

    raw_type = str(row.get("type") or row.get("question_type") or "").strip().lower()
    if raw_type not in set(QuestionType):
        raise ValueError(
            f"unknown type “{raw_type}”. Expected one of: {', '.join(sorted(QuestionType))}"
        )

    skill_slug = str(row.get("skill_slug") or "").strip()
    skill = skills.get(skill_slug)
    if skill is None:
        raise ValueError(f"unknown skill “{skill_slug}”")

    def split(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [part.strip() for part in str(value or "").split("|") if part.strip()]

    raw_options = split(row.get("options"))
    correct = split(row.get("correct_answer"))
    options: dict[str, Any] = {}
    answer_spec: dict[str, Any] = {}

    if raw_type in {QuestionType.MULTIPLE_CHOICE, QuestionType.MULTIPLE_SELECT}:
        if len(raw_options) < 2:
            raise ValueError("needs at least two options")
        if not correct:
            raise ValueError("needs a correct answer")

        correct_set: set[int] = set()
        for token in correct:
            if token.isdigit() and 1 <= int(token) <= len(raw_options):
                correct_set.add(int(token) - 1)
            elif token in raw_options:
                correct_set.add(raw_options.index(token))
            else:
                raise ValueError(f"correct answer “{token}” is not one of the options")
        options["choices"] = [
            {"id": chr(ord("a") + i), "label": label, "is_correct": i in correct_set}
            for i, label in enumerate(raw_options)
        ]
        answer_spec = {"choice_ids": [chr(ord("a") + i) for i in sorted(correct_set)]}

    elif raw_type == QuestionType.TRUE_FALSE:
        if not correct:
            raise ValueError("needs a correct answer of true or false")
        value = correct[0].strip().lower()
        if value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("correct answer must be true or false")
        answer_spec = {"value": value in {"true", "1", "yes"}}

    else:
        if not correct:
            raise ValueError("needs a correct answer")
        answer_spec = {"value": correct[0]}

    difficulty_raw = str(row.get("difficulty") or "2").strip() or "2"
    try:
        difficulty = max(1, min(5, int(float(difficulty_raw))))
    except ValueError as exc:
        raise ValueError(f"difficulty “{difficulty_raw}” is not a number from 1 to 5") from exc

    explanation = str(row.get("explanation") or "").strip()
    return {
        "prompt": prompt,
        "question_type": raw_type,
        "difficulty": difficulty,
        "options": options,
        "answer_spec": answer_spec,
        "solution": [{"text": explanation}] if explanation else [],
        "tags": split(row.get("tags")),
        "skill": skill,
    }


@router.post("/import")
async def import_questions(
    db: DbSession,
    admin: CurrentAdmin,
    file: UploadFile,
    commit: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """Import a CSV or JSON question bank.

    Defaults to a **dry run**. Nothing is written until ``commit=true``, so an administrator can
    see exactly which rows would be created and which are malformed before touching the database.
    Imported questions always land as drafts, whatever the file says, so a bad import can never
    put unreviewed content in front of a student.
    """
    raw = await file.read()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That file is larger than {MAX_IMPORT_BYTES // (1024 * 1024)}MB",
        )

    rows = _parse_rows(raw, file.filename or "upload.csv")
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Import at most {MAX_IMPORT_ROWS} questions at a time (got {len(rows)})",
        )

    skills = {
        skill.slug: skill
        for skill in db.scalars(
            select(Skill).options(
                selectinload(Skill.topic).selectinload(Topic.unit).selectinload(Unit.course)
            )
        )
    }

    prepared: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        try:
            prepared.append(_row_to_question(row, index, skills))
        except ValueError as exc:
            errors.append({"row": index, "error": str(exc)})

    preview = [
        {
            "row": index,
            "prompt": item["prompt"][:120],
            "type": item["question_type"],
            "difficulty": item["difficulty"],
            "skill": item["skill"].slug,
        }
        for index, item in enumerate(prepared, start=1)
    ]

    if not commit:
        return {
            "dry_run": True,
            "parsed": len(prepared),
            "errors": errors,
            "preview": preview[:50],
            "message": (
                f"{len(prepared)} question(s) ready to import, {len(errors)} row(s) with problems."
                " Nothing has been saved yet."
            ),
        }

    created = 0
    for item in prepared:
        skill = item.pop("skill")
        _, subject_slug, grade, topic_slug = _resolve_taxonomy(db, skill.id)
        question = Question(
            **item,
            slug=unique_slug(
                f"{skill.slug}-{item['prompt'][:40]}",
                lambda candidate: db.scalar(
                    select(Question.id).where(Question.slug == candidate)
                )
                is not None,
                max_length=200,
            ),
            skill_id=skill.id,
            subject_slug=subject_slug,
            grade=grade,
            topic_slug=topic_slug,
            # Always a draft, regardless of the file — imported content is reviewed by a human
            # before any student sees it.
            status=ReviewStatus.DRAFT,
            created_by_id=admin.id,
            source=f"import:{file.filename}",
        )
        db.add(question)
        created += 1

    record_audit(
        db, admin, "import", "question", None,
        f"Imported {created} exercise(s) from {file.filename}",
        {"errors": len(errors)},
    )
    db.commit()
    return {
        "dry_run": False,
        "created": created,
        "errors": errors,
        "message": (
            f"Imported {created} exercise(s) as drafts. Review and publish them when ready."
        ),
    }
