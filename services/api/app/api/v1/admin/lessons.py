"""Lesson authoring: create, edit blocks, draft/publish, duplicate, reorder, preview.

The draft/publish split is the core idea. ``Lesson.blocks`` is what students read;
``Lesson.draft_blocks`` is what the editor writes. Saving only ever touches the draft, so an
administrator can leave a half-written lesson open for a week without a single student seeing it,
and "Publish" is the one operation that copies draft over live.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.admin._common import (
    CurrentAdmin,
    DbSession,
    PageParams,
    apply_sort,
    build_page,
    diff_fields,
    get_or_404,
    next_position,
    paginate,
    record_audit,
    snapshot,
)
from app.api.v1.admin._translations import (
    COPY_SUFFIX,
    TranslationsPayload,
    apply_translations,
    duplicate_translations,
    read_translations,
)
from app.core.deps import RequestLocale
from app.core.i18n import DEFAULT_LOCALE, localise
from app.core.text import unique_slug
from app.models import (
    ContentRevision,
    Lesson,
    MediaAsset,
    Question,
    Resource,
    ReviewStatus,
    Skill,
    Topic,
    Unit,
    Video,
)
from app.schemas.lesson_blocks import BlockValidationError, normalise_blocks
from app.services.storage import playback_url

router = APIRouter(prefix="/lessons", tags=["admin:lessons"])


class LessonIn(TranslationsPayload):
    topic_id: int
    title: str = Field(min_length=1, max_length=250)
    slug: str | None = Field(default=None, max_length=180)
    summary: str | None = None
    objectives: list[str] = Field(default_factory=list)
    estimated_minutes: int = Field(default=15, ge=1, le=600)
    skill_id: int | None = None
    video_id: int | None = None
    thumbnail_url: str | None = Field(default=None, max_length=600)
    teacher_notes: str | None = None
    status: ReviewStatus = ReviewStatus.DRAFT
    blocks: list[dict[str, Any]] = Field(default_factory=list)


class LessonUpdate(TranslationsPayload):
    topic_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=250)
    slug: str | None = Field(default=None, max_length=180)
    summary: str | None = None
    objectives: list[str] | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)
    skill_id: int | None = None
    video_id: int | None = None
    thumbnail_url: str | None = Field(default=None, max_length=600)
    teacher_notes: str | None = None
    blocks: list[dict[str, Any]] | None = None


class ResourceIn(TranslationsPayload):
    title: str = Field(min_length=1, max_length=250)
    url: str = Field(min_length=1, max_length=800)
    resource_type: str = Field(default="link", max_length=40)
    description: str | None = None
    media_asset_id: int | None = None
    is_public: bool = True


def _apply_lesson_translations(
    lesson: Lesson, translations: dict[str, dict[str, Any]] | None, *, publish_now: bool
) -> None:
    """Write translated lesson fields, honouring the draft/live split.

    The editor sends translated blocks under ``blocks``, mirroring the English payload. Both are
    working copies, so both land in the draft — a translator editing a live lesson must not change
    what students are currently reading. ``publish_now`` promotes the draft in the same call, which
    is what lesson *creation* with status published does.
    """
    if translations is None:
        return
    staged: dict[str, dict[str, Any]] = {}
    for locale, values in translations.items():
        bucket = dict(values)
        if "blocks" in bucket:
            blocks = _validate_blocks(bucket.pop("blocks") or [])
            bucket["draft_blocks"] = blocks
            if publish_now:
                bucket["blocks"] = blocks
        staged[locale] = bucket
    apply_translations(lesson, staged)


def _clone_lesson_translations(lesson: Lesson) -> dict[str, Any]:
    """Translations for a duplicated lesson, staged as a draft like the English body.

    The clone starts with an empty live body and everything in the draft, so a copy is never
    accidentally live. Each translation has to follow the same rule or the languages disagree
    about what is published.
    """
    blob = duplicate_translations(lesson, suffix_field="title")
    for values in blob.values():
        body = values.pop("draft_blocks", None) or values.pop("blocks", None)
        values.pop("blocks", None)
        if body:
            values["draft_blocks"] = body
    return blob


def _publish_lesson_translations(lesson: Lesson) -> None:
    """Promote every locale's translated draft to live, alongside the English publish."""
    blob = dict(lesson.i18n or {})
    for locale, values in blob.items():
        draft = (values or {}).get("draft_blocks")
        if draft:
            blob[locale] = {**values, "blocks": draft}
    lesson.i18n = blob


def _reset_lesson_translation_drafts(lesson: Lesson) -> None:
    """Reset every locale's translated draft back to its live body."""
    blob = dict(lesson.i18n or {})
    for locale, values in blob.items():
        live = (values or {}).get("blocks")
        if live:
            blob[locale] = {**values, "draft_blocks": live}
    lesson.i18n = blob


def _validate_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        return normalise_blocks(blocks)
    except BlockValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


def _slug_taken(db, slug: str, exclude_id: int | None = None) -> bool:
    query = select(Lesson.id).where(Lesson.slug == slug)
    if exclude_id is not None:
        query = query.where(Lesson.id != exclude_id)
    return db.scalar(query) is not None


def _lesson_row(
    lesson: Lesson, topic: Topic | None = None, locale: str = DEFAULT_LOCALE
) -> dict[str, Any]:
    return {
        "id": lesson.id,
        "slug": lesson.slug,
        "title": lesson.title,
        "topic_id": lesson.topic_id,
        # Borrowed from the parent for display; the lesson form has no topic field to edit,
        # so it arrives already in the administrator's language.
        "topic_title": localise(topic, "title", locale) if topic else None,
        "skill_id": lesson.skill_id,
        "summary": lesson.summary,
        "objectives": lesson.objectives or [],
        "estimated_minutes": lesson.estimated_minutes,
        "position": lesson.position,
        "status": lesson.status,
        "has_draft": lesson.has_draft,
        "version": lesson.version,
        "thumbnail_url": lesson.thumbnail_url,
        "block_count": len(lesson.blocks or []),
        "draft_block_count": len(lesson.draft_blocks or []),
        "published_at": lesson.published_at,
        "updated_at": lesson.updated_at,
        "created_at": lesson.created_at,
        "translations": read_translations(lesson),
    }


@router.get("")
def list_lessons(
    db: DbSession,
    locale: RequestLocale,
    admin: CurrentAdmin,
    course_id: Annotated[int | None, Query()] = None,
    unit_id: Annotated[int | None, Query()] = None,
    topic_id: Annotated[int | None, Query()] = None,
    lesson_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(Lesson).options(selectinload(Lesson.topic))
    if topic_id:
        query = query.where(Lesson.topic_id == topic_id)
    elif unit_id:
        query = query.where(
            Lesson.topic_id.in_(select(Topic.id).where(Topic.unit_id == unit_id))
        )
    elif course_id:
        query = query.where(
            Lesson.topic_id.in_(
                select(Topic.id).join(Unit, Topic.unit_id == Unit.id).where(
                    Unit.course_id == course_id
                )
            )
        )
    if lesson_status:
        query = query.where(Lesson.status == lesson_status)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Lesson.title.ilike(pattern), Lesson.slug.ilike(pattern)))

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        Lesson,
        params,
        {
            "title": Lesson.title,
            "status": Lesson.status,
            "position": Lesson.position,
            "updated_at": Lesson.updated_at,
            "_default": Lesson.updated_at,
        },
    )
    rows, total = paginate(db, query, params)
    return build_page([_lesson_row(row, row.topic, locale) for row in rows], total, params)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_lesson(
    payload: LessonIn, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    topic = get_or_404(db, Topic, payload.topic_id, "Topic")
    if payload.skill_id is not None:
        get_or_404(db, Skill, payload.skill_id, "Skill")
    if payload.video_id is not None:
        get_or_404(db, Video, payload.video_id, "Video")

    blocks = _validate_blocks(payload.blocks)
    published = payload.status == ReviewStatus.PUBLISHED

    lesson = Lesson(
        slug=unique_slug(
            payload.slug or payload.title,
            lambda candidate: _slug_taken(db, candidate),
            max_length=180,
        ),
        title=payload.title,
        topic_id=payload.topic_id,
        skill_id=payload.skill_id,
        summary=payload.summary,
        objectives=payload.objectives,
        estimated_minutes=payload.estimated_minutes,
        position=next_position(db, Lesson, Lesson.topic_id == payload.topic_id),
        # A new lesson starts with draft and live in sync; if it is created as a draft the live
        # body stays empty so nothing half-finished is ever readable.
        blocks=blocks if published else [],
        draft_blocks=blocks,
        has_draft=not published,
        video_id=payload.video_id,
        status=payload.status,
        author_id=admin.id,
        thumbnail_url=payload.thumbnail_url,
        teacher_notes=payload.teacher_notes,
        published_at=dt.datetime.now(dt.UTC) if published else None,
    )
    _apply_lesson_translations(lesson, payload.translations, publish_now=published)
    db.add(lesson)
    db.flush()
    record_audit(db, admin, "create", "lesson", lesson.id, f"Created lesson “{lesson.title}”")
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson, topic, locale)


@router.get("/{lesson_id}")
def get_lesson(
    lesson_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    """Full editing payload: draft body, live body, breadcrumb and attached materials."""
    lesson = db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.topic).selectinload(Topic.unit).selectinload(Unit.course),
            selectinload(Lesson.skill),
            selectinload(Lesson.video),
            selectinload(Lesson.resources),
        )
    )
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    topic = lesson.topic
    unit = topic.unit if topic else None
    course = unit.course if unit else None

    data = _lesson_row(lesson, topic, locale)
    data.update(
        {
            "blocks": lesson.blocks or [],
            "draft_blocks": lesson.draft_blocks or [],
            "teacher_notes": lesson.teacher_notes,
            "video_id": lesson.video_id,
            "video": (
                {
                    "id": lesson.video.id,
                    "title": lesson.video.title,
                    "provider": lesson.video.provider,
                    "external_id": lesson.video.external_id,
                    "playback_url": playback_url(
                        lesson.video.provider, lesson.video.external_id
                    ),
                }
                if lesson.video
                else None
            ),
            "skill_name": localise(lesson.skill, "name", locale) if lesson.skill else None,
            "translations": read_translations(lesson),
            "breadcrumb": {
                "course_id": course.id if course else None,
                "course_title": localise(course, "title", locale) if course else None,
                "unit_id": unit.id if unit else None,
                "unit_title": localise(unit, "title", locale) if unit else None,
                "topic_id": topic.id if topic else None,
                "topic_title": localise(topic, "title", locale) if topic else None,
            },
            "resources": [
                {
                    "id": resource.id,
                    "title": resource.title,
                    "url": resource.url,
                    "resource_type": resource.resource_type,
                    "description": resource.description,
                    "is_public": resource.is_public,
                    "position": resource.position,
                    "translations": read_translations(resource),
                }
                for resource in lesson.resources
            ],
        }
    )
    return data


@router.patch("/{lesson_id}")
def update_lesson(
    lesson_id: int, payload: LessonUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Save the working copy. Never touches what students are reading."""
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    fields = payload.model_dump(exclude_unset=True, exclude={"slug", "blocks", "translations"})

    if fields.get("topic_id") is not None:
        get_or_404(db, Topic, fields["topic_id"], "Topic")
    if fields.get("skill_id") is not None:
        get_or_404(db, Skill, fields["skill_id"], "Skill")
    if fields.get("video_id") is not None:
        get_or_404(db, Video, fields["video_id"], "Video")

    before = {key: getattr(lesson, key) for key in fields}
    for key, value in fields.items():
        setattr(lesson, key, value)

    if payload.slug:
        lesson.slug = unique_slug(
            payload.slug,
            lambda candidate: _slug_taken(db, candidate, exclude_id=lesson.id),
            max_length=180,
        )

    if payload.blocks is not None:
        lesson.draft_blocks = _validate_blocks(payload.blocks)
        lesson.has_draft = lesson.draft_blocks != (lesson.blocks or [])

    _apply_lesson_translations(lesson, payload.translations, publish_now=False)

    record_audit(
        db, admin, "update", "lesson", lesson.id, f"Saved draft of “{lesson.title}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson)


@router.post("/{lesson_id}/publish")
def publish_lesson(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Promote the draft to live, snapshotting the outgoing version first."""
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")

    draft = lesson.draft_blocks or []
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This lesson has no content yet. Add at least one block before publishing.",
        )

    # Snapshot the version being replaced so it can be inspected or restored later.
    snapshot(
        db, "lesson", lesson.id,
        {"title": lesson.title, "blocks": lesson.blocks or [], "version": lesson.version,
         "status": lesson.status},
        admin, f"replaced by v{lesson.version + 1}",
    )

    lesson.blocks = draft
    _publish_lesson_translations(lesson)
    lesson.has_draft = False
    lesson.status = ReviewStatus.PUBLISHED
    lesson.version += 1
    lesson.published_at = dt.datetime.now(dt.UTC)

    record_audit(
        db, admin, "publish", "lesson", lesson.id,
        f"Published “{lesson.title}” (v{lesson.version})",
    )
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson)


@router.post("/{lesson_id}/unpublish")
def unpublish_lesson(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Take a lesson off the site, keeping its body intact as the working draft."""
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    if not lesson.draft_blocks:
        lesson.draft_blocks = lesson.blocks or []
    lesson.status = ReviewStatus.DRAFT
    lesson.has_draft = lesson.draft_blocks != (lesson.blocks or [])
    record_audit(db, admin, "unpublish", "lesson", lesson.id, f"Unpublished “{lesson.title}”")
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson)


@router.post("/{lesson_id}/archive")
def archive_lesson(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    lesson.status = ReviewStatus.ARCHIVED
    record_audit(db, admin, "archive", "lesson", lesson.id, f"Archived “{lesson.title}”")
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson)


@router.post("/{lesson_id}/discard-draft")
def discard_draft(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """Throw away unpublished edits and reset the draft to the live version."""
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    lesson.draft_blocks = list(lesson.blocks or [])
    _reset_lesson_translation_drafts(lesson)
    lesson.has_draft = False
    record_audit(
        db, admin, "discard_draft", "lesson", lesson.id,
        f"Discarded draft changes to “{lesson.title}”",
    )
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson)


@router.post("/{lesson_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_lesson(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    clone = Lesson(
        slug=unique_slug(
            f"{lesson.title} copy", lambda candidate: _slug_taken(db, candidate), max_length=180
        ),
        title=f"{lesson.title} {COPY_SUFFIX[DEFAULT_LOCALE]}",
        i18n=_clone_lesson_translations(lesson),
        topic_id=lesson.topic_id,
        skill_id=lesson.skill_id,
        summary=lesson.summary,
        objectives=list(lesson.objectives or []),
        estimated_minutes=lesson.estimated_minutes,
        position=next_position(db, Lesson, Lesson.topic_id == lesson.topic_id),
        blocks=[],
        draft_blocks=list(lesson.draft_blocks or lesson.blocks or []),
        has_draft=True,
        video_id=lesson.video_id,
        status=ReviewStatus.DRAFT,
        author_id=admin.id,
        thumbnail_url=lesson.thumbnail_url,
        teacher_notes=lesson.teacher_notes,
    )
    db.add(clone)
    db.flush()
    record_audit(
        db, admin, "duplicate", "lesson", clone.id,
        f"Duplicated “{lesson.title}” as “{clone.title}”",
    )
    db.commit()
    db.refresh(clone)
    return _lesson_row(clone)


@router.get("/{lesson_id}/preview")
def preview_lesson(
    lesson_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
    draft: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    """Render the lesson exactly as a student would see it.

    The same payload shape as the public ``/curriculum/lessons/{slug}`` endpoint, so the preview
    screen can reuse the student renderer component rather than maintaining a second one that
    drifts out of sync with what students actually get.
    """
    lesson = db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.topic),
            selectinload(Lesson.skill),
            selectinload(Lesson.video),
            selectinload(Lesson.resources),
        )
    )
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    blocks = (lesson.draft_blocks if draft else lesson.blocks) or []

    # Resolve the questions an assessment block refers to, so the preview can show the real
    # exercise rather than a placeholder card.
    question_ids: list[int] = []
    for block in blocks:
        for value in block.get("question_ids") or []:
            if isinstance(value, int):
                question_ids.append(value)
    questions = {}
    if question_ids:
        for question in db.scalars(select(Question).where(Question.id.in_(question_ids))):
            questions[question.id] = {
                "id": question.id,
                "slug": question.slug,
                "prompt": question.prompt,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "status": question.status,
            }

    return {
        "id": lesson.id,
        "slug": lesson.slug,
        "title": lesson.title,
        "summary": lesson.summary,
        "objectives": lesson.objectives or [],
        "estimated_minutes": lesson.estimated_minutes,
        "status": lesson.status,
        "is_draft_preview": draft,
        "blocks": blocks,
        "topic_slug": lesson.topic.slug if lesson.topic else None,
        "topic_title": localise(lesson.topic, "title", locale) if lesson.topic else None,
        "skill_slug": lesson.skill.slug if lesson.skill else None,
        "skill_name": localise(lesson.skill, "name", locale) if lesson.skill else None,
        "video": (
            {
                "id": lesson.video.id,
                "title": lesson.video.title,
                "provider": lesson.video.provider,
                "external_id": lesson.video.external_id,
                "duration_seconds": lesson.video.duration_seconds,
                "thumbnail_url": lesson.video.thumbnail_url,
                "chapters": lesson.video.chapters or [],
                "captions": lesson.video.captions or [],
                "playback_url": playback_url(lesson.video.provider, lesson.video.external_id),
                "attribution": lesson.video.attribution,
            }
            if lesson.video
            else None
        ),
        "resources": [
            {"id": r.id, "title": r.title, "url": r.url, "resource_type": r.resource_type,
             "description": r.description}
            for r in lesson.resources
            if r.is_public
        ],
        "referenced_questions": questions,
        "attribution": lesson.attribution,
        "license": lesson.license,
    }


@router.get("/{lesson_id}/revisions")
def lesson_revisions(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    get_or_404(db, Lesson, lesson_id, "Lesson")
    rows = db.scalars(
        select(ContentRevision)
        .where(ContentRevision.entity_type == "lesson", ContentRevision.entity_id == lesson_id)
        .order_by(ContentRevision.version.desc())
        .limit(50)
    )
    return [
        {
            "id": rev.id,
            "version": rev.version,
            "note": rev.note,
            "author_id": rev.author_id,
            "created_at": rev.created_at,
            "block_count": len(rev.snapshot.get("blocks") or []),
        }
        for rev in rows
    ]


@router.post("/{lesson_id}/revisions/{revision_id}/restore")
def restore_revision(
    lesson_id: int, revision_id: int, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Load an old version back into the draft.

    Deliberately restores into the *draft* rather than straight to live: an accidental restore
    should be as easy to undo as any other unpublished edit.
    """
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    revision = get_or_404(db, ContentRevision, revision_id, "Revision")
    if revision.entity_type != "lesson" or revision.entity_id != lesson_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That revision belongs to a different lesson",
        )

    lesson.draft_blocks = revision.snapshot.get("blocks") or []
    lesson.has_draft = lesson.draft_blocks != (lesson.blocks or [])
    record_audit(
        db, admin, "restore", "lesson", lesson.id,
        f"Restored “{lesson.title}” draft from version {revision.version}",
    )
    db.commit()
    db.refresh(lesson)
    return _lesson_row(lesson)


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(lesson_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    snapshot(
        db, "lesson", lesson.id,
        {"title": lesson.title, "slug": lesson.slug, "blocks": lesson.blocks or [],
         "topic_id": lesson.topic_id, "summary": lesson.summary},
        admin, "before delete",
    )
    title = lesson.title
    db.delete(lesson)
    record_audit(db, admin, "delete", "lesson", lesson_id, f"Deleted lesson “{title}”")
    db.commit()


# --------------------------------------------------------------------------------------
# attached materials
# --------------------------------------------------------------------------------------


@router.post("/{lesson_id}/resources", status_code=status.HTTP_201_CREATED)
def add_resource(
    lesson_id: int, payload: ResourceIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    lesson = get_or_404(db, Lesson, lesson_id, "Lesson")
    if payload.media_asset_id is not None:
        get_or_404(db, MediaAsset, payload.media_asset_id, "Media asset")

    resource = Resource(
        lesson_id=lesson.id,
        topic_id=lesson.topic_id,
        title=payload.title,
        url=payload.url,
        resource_type=payload.resource_type,
        description=payload.description,
        media_asset_id=payload.media_asset_id,
        is_public=payload.is_public,
        position=next_position(db, Resource, Resource.lesson_id == lesson.id),
    )
    db.add(resource)
    db.flush()
    record_audit(
        db, admin, "create", "resource", resource.id,
        f"Attached “{resource.title}” to lesson “{lesson.title}”",
    )
    db.commit()
    db.refresh(resource)
    return {"id": resource.id, "title": resource.title, "url": resource.url,
            "resource_type": resource.resource_type, "position": resource.position}


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(resource_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    resource = get_or_404(db, Resource, resource_id, "Resource")
    title = resource.title
    db.delete(resource)
    record_audit(db, admin, "delete", "resource", resource_id, f"Removed material “{title}”")
    db.commit()


# --------------------------------------------------------------------------------------
# videos
# --------------------------------------------------------------------------------------


class VideoIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    provider: str = Field(default="youtube", max_length=40)
    external_id: str = Field(min_length=1, max_length=250)
    duration_seconds: int = Field(default=0, ge=0)
    thumbnail_url: str | None = Field(default=None, max_length=600)
    chapters: list[dict[str, Any]] = Field(default_factory=list)
    captions: list[dict[str, Any]] = Field(default_factory=list)
    attribution: str | None = None


@router.get("/videos/library")
def list_videos(db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    rows = db.scalars(select(Video).order_by(Video.id.desc()).limit(200))
    return [
        {
            "id": v.id, "title": v.title, "provider": v.provider, "external_id": v.external_id,
            "duration_seconds": v.duration_seconds, "thumbnail_url": v.thumbnail_url,
            "playback_url": playback_url(v.provider, v.external_id),
        }
        for v in rows
    ]


@router.post("/videos", status_code=status.HTTP_201_CREATED)
def create_video(payload: VideoIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    video = Video(**payload.model_dump())
    db.add(video)
    db.flush()
    record_audit(db, admin, "create", "video", video.id, f"Registered video “{video.title}”")
    db.commit()
    db.refresh(video)
    return {
        "id": video.id, "title": video.title, "provider": video.provider,
        "external_id": video.external_id,
        "playback_url": playback_url(video.provider, video.external_id),
    }
