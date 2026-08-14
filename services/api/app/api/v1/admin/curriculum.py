"""Course structure management: subjects, courses, modules (units), topics and skills.

The public curriculum API is read-only and slug-addressed. This module is the write side, and it
is id-addressed on purpose: an administrator renaming a course changes its slug, and a UI that had
to re-resolve slugs after every save would be unusable.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
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
    ContentCategory,
    Course,
    CourseCategory,
    Lesson,
    Question,
    ReviewStatus,
    Skill,
    Subject,
    TeacherProfile,
    Topic,
    Unit,
)

router = APIRouter(tags=["admin:curriculum"])


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _slug_free(db, model, slug: str, exclude_id: int | None = None) -> bool:
    query = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    return db.scalar(query) is None


def _make_slug(db, model, source: str, max_length: int, exclude_id: int | None = None) -> str:
    return unique_slug(
        source,
        lambda candidate: not _slug_free(db, model, candidate, exclude_id),
        max_length=max_length,
    )


def _sync_publish_flag(course: Course) -> None:
    """Keep the legacy ``is_published`` boolean in step with the richer ``status`` column.

    Every existing read path — the public course list, site stats, the student dashboard — filters
    on ``is_published``. Rather than rewrite all of them and risk missing one, the admin API treats
    ``status`` as authoritative and derives the boolean from it.
    """
    course.is_published = course.status == ReviewStatus.PUBLISHED


# --------------------------------------------------------------------------------------
# subjects
# --------------------------------------------------------------------------------------


class SubjectIn(TranslationsPayload):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=60)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    position: int
    translations: dict[str, dict[str, Any]] = Field(default_factory=dict)


def _subject_row(subject: Subject) -> dict[str, Any]:
    return {
        **{
            key: getattr(subject, key)
            for key in ("id", "slug", "name", "description", "icon", "color", "position")
        },
        "translations": read_translations(subject),
    }


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(db: DbSession, admin: CurrentAdmin) -> list[dict[str, Any]]:
    return [
        _subject_row(subject)
        for subject in db.scalars(select(Subject).order_by(Subject.position, Subject.id))
    ]


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    subject = Subject(
        **payload.model_dump(exclude={"slug", "translations"}),
        slug=_make_slug(db, Subject, payload.slug or payload.name, 60),
        position=next_position(db, Subject),
    )
    apply_translations(subject, payload.translations)
    db.add(subject)
    db.flush()
    record_audit(db, admin, "create", "subject", subject.id, f"Created subject “{subject.name}”")
    db.commit()
    db.refresh(subject)
    return _subject_row(subject)


@router.patch("/subjects/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int, payload: SubjectIn, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    subject = get_or_404(db, Subject, subject_id, "Subject")
    fields = payload.model_dump(exclude_unset=True, exclude={"slug", "translations"})
    before = {key: getattr(subject, key) for key in fields}
    for key, value in fields.items():
        setattr(subject, key, value)
    if payload.slug:
        subject.slug = _make_slug(db, Subject, payload.slug, 60, exclude_id=subject.id)
    apply_translations(subject, payload.translations)
    record_audit(
        db, admin, "update", "subject", subject.id, f"Updated subject “{subject.name}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(subject)
    return _subject_row(subject)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    subject = get_or_404(db, Subject, subject_id, "Subject")
    course_count = (
        db.scalar(select(func.count()).select_from(Course).where(Course.subject_id == subject_id))
        or 0
    )
    if course_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"“{subject.name}” still has {course_count} course(s). Move or delete them first."
            ),
        )
    name = subject.name
    db.delete(subject)
    record_audit(db, admin, "delete", "subject", subject_id, f"Deleted subject “{name}”")
    db.commit()


# --------------------------------------------------------------------------------------
# courses
# --------------------------------------------------------------------------------------


class CourseIn(TranslationsPayload):
    subject_id: int
    title: str = Field(min_length=1, max_length=200)
    grade: int = Field(ge=1, le=12)
    slug: str | None = Field(default=None, max_length=80)
    summary: str | None = None
    description: str | None = None
    estimated_hours: int = Field(default=0, ge=0, le=2000)
    status: ReviewStatus = ReviewStatus.DRAFT
    thumbnail_url: str | None = Field(default=None, max_length=600)
    is_featured: bool = False
    teacher_id: int | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None
    category_ids: list[int] = Field(default_factory=list)


class CourseUpdate(TranslationsPayload):
    subject_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    grade: int | None = Field(default=None, ge=1, le=12)
    slug: str | None = Field(default=None, max_length=80)
    summary: str | None = None
    description: str | None = None
    estimated_hours: int | None = Field(default=None, ge=0, le=2000)
    status: ReviewStatus | None = None
    thumbnail_url: str | None = Field(default=None, max_length=600)
    is_featured: bool | None = None
    teacher_id: int | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None
    category_ids: list[int] | None = None


def _course_row(
    db, course: Course, category_map: dict[int, list[dict[str, Any]]], locale: str = DEFAULT_LOCALE
) -> dict:
    return {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "grade": course.grade,
        "subject_id": course.subject_id,
        # Borrowed from the parent row for display only — there is no subject field on this
        # form to round-trip, so it arrives ready to read rather than as English plus a blob.
        "subject_name": localise(course.subject, "name", locale) if course.subject else None,
        "summary": course.summary,
        "description": course.description,
        "estimated_hours": course.estimated_hours,
        "status": course.status,
        "is_published": course.is_published,
        "is_featured": course.is_featured,
        "thumbnail_url": course.thumbnail_url,
        "teacher_id": course.teacher_id,
        "position": course.position,
        "seo_title": course.seo_title,
        "seo_description": course.seo_description,
        "categories": category_map.get(course.id, []),
        "translations": read_translations(course),
        "created_at": course.created_at,
        "updated_at": course.updated_at,
    }


def _categories_for_courses(
    db, course_ids: list[int], locale: str = DEFAULT_LOCALE
) -> dict[int, list[dict[str, Any]]]:
    if not course_ids:
        return {}
    rows = db.execute(
        select(CourseCategory.course_id, ContentCategory)
        .join(ContentCategory, CourseCategory.category_id == ContentCategory.id)
        .where(CourseCategory.course_id.in_(course_ids))
    ).all()
    mapping: dict[int, list[dict[str, Any]]] = {}
    for course_id, category in rows:
        mapping.setdefault(course_id, []).append(
            {"id": category.id, "slug": category.slug,
             "name": localise(category, "name", locale), "kind": category.kind}
        )
    return mapping


def _set_course_categories(db, course: Course, category_ids: list[int]) -> None:
    valid = set(
        db.scalars(select(ContentCategory.id).where(ContentCategory.id.in_(category_ids))).all()
    )
    unknown = set(category_ids) - valid
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown category ids: {sorted(unknown)}",
        )
    db.execute(
        CourseCategory.__table__.delete().where(CourseCategory.course_id == course.id)
    )
    for category_id in dict.fromkeys(category_ids):
        db.add(CourseCategory(course_id=course.id, category_id=category_id))


@router.get("/courses")
def list_courses(
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
    subject_id: Annotated[int | None, Query()] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
    course_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    category_id: Annotated[int | None, Query()] = None,
    featured: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str | None, Query(max_length=40)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    query = select(Course).options(selectinload(Course.subject))
    if subject_id:
        query = query.where(Course.subject_id == subject_id)
    if grade:
        query = query.where(Course.grade == grade)
    if course_status:
        query = query.where(Course.status == course_status)
    if featured is not None:
        query = query.where(Course.is_featured.is_(featured))
    if category_id:
        query = query.where(
            Course.id.in_(
                select(CourseCategory.course_id).where(CourseCategory.category_id == category_id)
            )
        )
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Course.title.ilike(pattern), Course.slug.ilike(pattern)))

    params = PageParams(page=page, page_size=page_size, sort=sort, order=order)
    query = apply_sort(
        query,
        Course,
        params,
        {
            "title": Course.title,
            "grade": Course.grade,
            "status": Course.status,
            "updated_at": Course.updated_at,
            "position": Course.position,
            "_default": Course.position,
        },
    )
    rows, total = paginate(db, query, params)

    category_map = _categories_for_courses(db, [row.id for row in rows], locale)
    counts = _structure_counts(db, [row.id for row in rows])
    items = []
    for row in rows:
        data = _course_row(db, row, category_map, locale)
        data.update(
            counts.get(
                row.id,
                {"unit_count": 0, "topic_count": 0, "skill_count": 0, "lesson_count": 0},
            )
        )
        items.append(data)
    return build_page(items, total, params)


def _structure_counts(db, course_ids: list[int]) -> dict[int, dict[str, int]]:
    """Unit / topic / skill / lesson totals per course, in four grouped queries rather than 4N."""
    if not course_ids:
        return {}
    result: dict[int, dict[str, int]] = {
        cid: {"unit_count": 0, "topic_count": 0, "skill_count": 0, "lesson_count": 0}
        for cid in course_ids
    }

    for course_id, total in db.execute(
        select(Unit.course_id, func.count())
        .where(Unit.course_id.in_(course_ids))
        .group_by(Unit.course_id)
    ).all():
        result[course_id]["unit_count"] = total

    for course_id, total in db.execute(
        select(Unit.course_id, func.count())
        .join(Topic, Topic.unit_id == Unit.id)
        .where(Unit.course_id.in_(course_ids))
        .group_by(Unit.course_id)
    ).all():
        result[course_id]["topic_count"] = total

    for course_id, total in db.execute(
        select(Unit.course_id, func.count())
        .join(Topic, Topic.unit_id == Unit.id)
        .join(Skill, Skill.topic_id == Topic.id)
        .where(Unit.course_id.in_(course_ids))
        .group_by(Unit.course_id)
    ).all():
        result[course_id]["skill_count"] = total

    for course_id, total in db.execute(
        select(Unit.course_id, func.count())
        .join(Topic, Topic.unit_id == Unit.id)
        .join(Lesson, Lesson.topic_id == Topic.id)
        .where(Unit.course_id.in_(course_ids))
        .group_by(Unit.course_id)
    ).all():
        result[course_id]["lesson_count"] = total

    return result


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseIn, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    get_or_404(db, Subject, payload.subject_id, "Subject")
    if payload.teacher_id is not None:
        get_or_404(db, TeacherProfile, payload.teacher_id, "Teacher")

    existing = db.scalar(
        select(Course).where(
            Course.subject_id == payload.subject_id, Course.grade == payload.grade
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"“{existing.title}” already covers grade {payload.grade} for this subject. "
                "Each subject has one course per grade."
            ),
        )

    course = Course(
        **payload.model_dump(exclude={"slug", "category_ids", "translations"}),
        slug=_make_slug(db, Course, payload.slug or f"{payload.title}", 80),
        position=next_position(db, Course, Course.subject_id == payload.subject_id),
    )
    apply_translations(course, payload.translations)
    _sync_publish_flag(course)
    db.add(course)
    db.flush()
    if payload.category_ids:
        _set_course_categories(db, course, payload.category_ids)
    record_audit(db, admin, "create", "course", course.id, f"Created course “{course.title}”")
    db.commit()
    db.refresh(course)
    return _course_row(db, course, _categories_for_courses(db, [course.id], locale), locale)


@router.get("/courses/{course_id}")
def get_course(
    course_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    """One course with its full module → topic → skill → lesson tree.

    This is the payload the structure builder screen renders, so it is assembled in one request:
    the alternative — lazily fetching each level on expand — makes drag-and-drop reordering across
    levels impossible to keep consistent.
    """
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.subject),
            selectinload(Course.units)
            .selectinload(Unit.topics)
            .selectinload(Topic.skills),
        )
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    topic_ids = [topic.id for unit in course.units for topic in unit.topics]
    lessons_by_topic: dict[int, list[Lesson]] = {}
    if topic_ids:
        for lesson in db.scalars(
            select(Lesson)
            .where(Lesson.topic_id.in_(topic_ids))
            .order_by(Lesson.position, Lesson.id)
        ):
            lessons_by_topic.setdefault(lesson.topic_id, []).append(lesson)

    skill_ids = [skill.id for unit in course.units for topic in unit.topics
                 for skill in topic.skills]
    question_counts: dict[int, int] = {}
    if skill_ids:
        question_counts = dict(
            db.execute(
                select(Question.skill_id, func.count())
                .where(Question.skill_id.in_(skill_ids))
                .group_by(Question.skill_id)
            ).all()
        )

    data = _course_row(db, course, _categories_for_courses(db, [course.id], locale), locale)
    data["units"] = [
        {
            "id": unit.id,
            "slug": unit.slug,
            "title": unit.title,
            "summary": unit.summary,
            "icon": unit.icon,
            "position": unit.position,
            "translations": read_translations(unit),
            "topics": [
                {
                    "id": topic.id,
                    "slug": topic.slug,
                    "title": topic.title,
                    "summary": topic.summary,
                    "position": topic.position,
                    "translations": read_translations(topic),
                    "skills": [
                        {
                            "id": skill.id,
                            "slug": skill.slug,
                            "name": skill.name,
                            "difficulty": skill.difficulty,
                            "position": skill.position,
                            "question_count": question_counts.get(skill.id, 0),
                            "translations": read_translations(skill),
                        }
                        for skill in topic.skills
                    ],
                    "lessons": [
                        {
                            "id": lesson.id,
                            "slug": lesson.slug,
                            "title": lesson.title,
                            "status": lesson.status,
                            "position": lesson.position,
                            "estimated_minutes": lesson.estimated_minutes,
                            "block_count": len(lesson.blocks or []),
                            "has_draft": lesson.has_draft,
                            "translations": read_translations(lesson),
                        }
                        for lesson in lessons_by_topic.get(topic.id, [])
                    ],
                }
                for topic in unit.topics
            ],
        }
        for unit in course.units
    ]
    return data


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
) -> dict[str, Any]:
    course = get_or_404(db, Course, course_id, "Course")
    fields = payload.model_dump(
        exclude_unset=True, exclude={"category_ids", "slug", "translations"}
    )

    if "subject_id" in fields and fields["subject_id"] is not None:
        get_or_404(db, Subject, fields["subject_id"], "Subject")
    if fields.get("teacher_id") is not None:
        get_or_404(db, TeacherProfile, fields["teacher_id"], "Teacher")

    # The (subject, grade) pair is uniquely constrained; catch it here so the admin gets a clear
    # message instead of a database integrity error.
    new_subject = fields.get("subject_id", course.subject_id)
    new_grade = fields.get("grade", course.grade)
    if (new_subject, new_grade) != (course.subject_id, course.grade):
        clash = db.scalar(
            select(Course).where(
                Course.subject_id == new_subject,
                Course.grade == new_grade,
                Course.id != course.id,
            )
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"“{clash.title}” already covers grade {new_grade} for that subject",
            )

    before = {key: getattr(course, key) for key in fields}
    snapshot(
        db, "course", course.id,
        {
            "title": course.title, "summary": course.summary, "description": course.description,
            "status": course.status, "grade": course.grade, "subject_id": course.subject_id,
        },
        admin, "before update",
    )

    for key, value in fields.items():
        setattr(course, key, value)
    if payload.slug:
        course.slug = _make_slug(db, Course, payload.slug, 80, exclude_id=course.id)
    if "status" in fields:
        _sync_publish_flag(course)
    apply_translations(course, payload.translations)
    if payload.category_ids is not None:
        _set_course_categories(db, course, payload.category_ids)

    record_audit(
        db, admin, "update", "course", course.id, f"Updated course “{course.title}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(course)
    return _course_row(db, course, _categories_for_courses(db, [course.id], locale), locale)


@router.post("/courses/{course_id}/status")
def set_course_status(
    course_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    locale: RequestLocale,
    value: Annotated[ReviewStatus, Query(alias="status")],
) -> dict[str, Any]:
    course = get_or_404(db, Course, course_id, "Course")
    course.status = value
    _sync_publish_flag(course)
    record_audit(
        db, admin, str(value), "course", course.id,
        f"Set course “{course.title}” to {value}",
    )
    db.commit()
    db.refresh(course)
    return _course_row(db, course, _categories_for_courses(db, [course.id], locale), locale)


@router.post("/courses/{course_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_course(
    course_id: int, db: DbSession, admin: CurrentAdmin, locale: RequestLocale
) -> dict[str, Any]:
    """Deep-copy a course, including modules, topics, skills and lessons.

    The copy always lands as a draft: duplicating a live course and having the clone appear on the
    public site immediately would be a surprising and hard-to-undo side effect. Questions are
    *not* copied — they hang off skills and are reusable content in their own right, so the copy
    references fresh skills with an empty bank rather than silently doubling the question count.
    """
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(selectinload(Course.units).selectinload(Unit.topics).selectinload(Topic.skills))
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # A course is unique on (subject, grade), so the copy cannot keep the same grade. Find the
    # first free grade rather than failing outright.
    used_grades = set(
        db.scalars(select(Course.grade).where(Course.subject_id == course.subject_id)).all()
    )
    free_grade = next((g for g in range(1, 13) if g not in used_grades), None)
    if free_grade is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Every grade from 1 to 12 already has a course in this subject, so there is no "
                "free slot for a duplicate."
            ),
        )

    clone = Course(
        subject_id=course.subject_id,
        slug=_make_slug(db, Course, f"{course.title} copy", 80),
        title=f"{course.title} {COPY_SUFFIX[DEFAULT_LOCALE]}",
        i18n=duplicate_translations(course, suffix_field="title"),
        grade=free_grade,
        summary=course.summary,
        description=course.description,
        estimated_hours=course.estimated_hours,
        status=ReviewStatus.DRAFT,
        is_published=False,
        is_featured=False,
        thumbnail_url=course.thumbnail_url,
        teacher_id=course.teacher_id,
        position=next_position(db, Course, Course.subject_id == course.subject_id),
    )
    db.add(clone)
    db.flush()

    lessons_by_topic: dict[int, list[Lesson]] = {}
    topic_ids = [topic.id for unit in course.units for topic in unit.topics]
    if topic_ids:
        for lesson in db.scalars(select(Lesson).where(Lesson.topic_id.in_(topic_ids))):
            lessons_by_topic.setdefault(lesson.topic_id, []).append(lesson)

    copied = {"units": 0, "topics": 0, "skills": 0, "lessons": 0}
    for unit in course.units:
        new_unit = Unit(
            course_id=clone.id,
            slug=_make_slug(db, Unit, f"{unit.title} copy", 120),
            title=unit.title,
            i18n=duplicate_translations(unit),
            summary=unit.summary,
            icon=unit.icon,
            position=unit.position,
        )
        db.add(new_unit)
        db.flush()
        copied["units"] += 1

        for topic in unit.topics:
            new_topic = Topic(
                unit_id=new_unit.id,
                slug=_make_slug(db, Topic, f"{topic.title} copy", 140),
                title=topic.title,
                i18n=duplicate_translations(topic),
                summary=topic.summary,
                position=topic.position,
            )
            db.add(new_topic)
            db.flush()
            copied["topics"] += 1

            for skill in topic.skills:
                db.add(
                    Skill(
                        topic_id=new_topic.id,
                        slug=_make_slug(db, Skill, f"{skill.name} copy", 160),
                        name=skill.name,
                        i18n=duplicate_translations(skill),
                        description=skill.description,
                        difficulty=skill.difficulty,
                        position=skill.position,
                        tags=list(skill.tags or []),
                        bkt_p_init=skill.bkt_p_init,
                        bkt_p_transit=skill.bkt_p_transit,
                        bkt_p_slip=skill.bkt_p_slip,
                        bkt_p_guess=skill.bkt_p_guess,
                    )
                )
                copied["skills"] += 1

            for lesson in lessons_by_topic.get(topic.id, []):
                db.add(
                    Lesson(
                        slug=_make_slug(db, Lesson, f"{lesson.title} copy", 180),
                        title=lesson.title,
                        i18n=duplicate_translations(lesson),
                        topic_id=new_topic.id,
                        summary=lesson.summary,
                        objectives=list(lesson.objectives or []),
                        estimated_minutes=lesson.estimated_minutes,
                        position=lesson.position,
                        blocks=list(lesson.blocks or []),
                        draft_blocks=list(lesson.blocks or []),
                        status=ReviewStatus.DRAFT,
                        thumbnail_url=lesson.thumbnail_url,
                        teacher_notes=lesson.teacher_notes,
                        author_id=admin.id,
                    )
                )
                copied["lessons"] += 1

    record_audit(
        db, admin, "duplicate", "course", clone.id,
        f"Duplicated course “{course.title}” as “{clone.title}”", copied,
    )
    db.commit()
    db.refresh(clone)
    result = _course_row(db, clone, {}, locale)
    result["copied"] = copied
    return result


@router.post("/courses/reorder")
def reorder_courses(
    payload: dict[str, list[int]], db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    ids = payload.get("ids") or []
    rows = {row.id: row for row in db.scalars(select(Course).where(Course.id.in_(ids)))}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown course ids: {missing}"
        )
    for index, course_id in enumerate(ids, start=1):
        rows[course_id].position = index
    record_audit(db, admin, "reorder", "course", None, f"Reordered {len(ids)} courses")
    db.commit()
    return {"reordered": len(ids)}


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    """Delete a course and everything under it.

    The cascade is real and wide (units → topics → skills → questions → attempts), so a snapshot
    is written first and the deletion is recorded with the counts it destroyed. The admin UI
    requires a typed confirmation before calling this.
    """
    course = get_or_404(db, Course, course_id, "Course")
    counts = _structure_counts(db, [course_id]).get(course_id, {})
    snapshot(
        db, "course", course.id,
        {"title": course.title, "slug": course.slug, "grade": course.grade,
         "subject_id": course.subject_id, "summary": course.summary,
         "description": course.description, "structure": counts},
        admin, "before delete",
    )
    title = course.title
    db.delete(course)
    record_audit(
        db, admin, "delete", "course", course_id, f"Deleted course “{title}”", counts
    )
    db.commit()


# --------------------------------------------------------------------------------------
# units (presented as "modules" in the admin UI)
# --------------------------------------------------------------------------------------


class UnitIn(TranslationsPayload):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    summary: str | None = None
    icon: str | None = Field(default=None, max_length=60)


class UnitUpdate(TranslationsPayload):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    summary: str | None = None
    icon: str | None = Field(default=None, max_length=60)
    course_id: int | None = None


@router.post("/units", status_code=status.HTTP_201_CREATED)
def create_unit(payload: UnitIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    get_or_404(db, Course, payload.course_id, "Course")
    unit = Unit(
        course_id=payload.course_id,
        slug=_make_slug(db, Unit, payload.slug or payload.title, 120),
        title=payload.title,
        summary=payload.summary,
        icon=payload.icon,
        position=next_position(db, Unit, Unit.course_id == payload.course_id),
    )
    apply_translations(unit, payload.translations)
    db.add(unit)
    db.flush()
    record_audit(db, admin, "create", "unit", unit.id, f"Created module “{unit.title}”")
    db.commit()
    db.refresh(unit)
    return {"id": unit.id, "slug": unit.slug, "title": unit.title, "position": unit.position,
            "translations": read_translations(unit)}


@router.patch("/units/{unit_id}")
def update_unit(
    unit_id: int, payload: UnitUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    unit = get_or_404(db, Unit, unit_id, "Module")
    fields = payload.model_dump(exclude_unset=True, exclude={"slug", "translations"})
    if fields.get("course_id") is not None:
        get_or_404(db, Course, fields["course_id"], "Course")
    before = {key: getattr(unit, key) for key in fields}
    for key, value in fields.items():
        setattr(unit, key, value)
    if payload.slug:
        unit.slug = _make_slug(db, Unit, payload.slug, 120, exclude_id=unit.id)
    apply_translations(unit, payload.translations)
    record_audit(
        db, admin, "update", "unit", unit.id, f"Updated module “{unit.title}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(unit)
    return {"id": unit.id, "slug": unit.slug, "title": unit.title, "position": unit.position,
            "translations": read_translations(unit)}


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(unit_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    unit = get_or_404(db, Unit, unit_id, "Module")
    title = unit.title
    db.delete(unit)
    record_audit(db, admin, "delete", "unit", unit_id, f"Deleted module “{title}”")
    db.commit()


# --------------------------------------------------------------------------------------
# topics
# --------------------------------------------------------------------------------------


class TopicIn(TranslationsPayload):
    unit_id: int
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=140)
    summary: str | None = None


class TopicUpdate(TranslationsPayload):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=140)
    summary: str | None = None
    unit_id: int | None = None


@router.post("/topics", status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    get_or_404(db, Unit, payload.unit_id, "Module")
    topic = Topic(
        unit_id=payload.unit_id,
        slug=_make_slug(db, Topic, payload.slug or payload.title, 140),
        title=payload.title,
        summary=payload.summary,
        position=next_position(db, Topic, Topic.unit_id == payload.unit_id),
    )
    apply_translations(topic, payload.translations)
    db.add(topic)
    db.flush()
    record_audit(db, admin, "create", "topic", topic.id, f"Created topic “{topic.title}”")
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "slug": topic.slug, "title": topic.title,
            "position": topic.position, "translations": read_translations(topic)}


@router.patch("/topics/{topic_id}")
def update_topic(
    topic_id: int, payload: TopicUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    topic = get_or_404(db, Topic, topic_id, "Topic")
    fields = payload.model_dump(exclude_unset=True, exclude={"slug", "translations"})
    if fields.get("unit_id") is not None:
        get_or_404(db, Unit, fields["unit_id"], "Module")
    before = {key: getattr(topic, key) for key in fields}
    for key, value in fields.items():
        setattr(topic, key, value)
    if payload.slug:
        topic.slug = _make_slug(db, Topic, payload.slug, 140, exclude_id=topic.id)
    apply_translations(topic, payload.translations)
    record_audit(
        db, admin, "update", "topic", topic.id, f"Updated topic “{topic.title}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "slug": topic.slug, "title": topic.title,
            "position": topic.position, "translations": read_translations(topic)}


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    topic = get_or_404(db, Topic, topic_id, "Topic")
    title = topic.title
    db.delete(topic)
    record_audit(db, admin, "delete", "topic", topic_id, f"Deleted topic “{title}”")
    db.commit()


# --------------------------------------------------------------------------------------
# skills
# --------------------------------------------------------------------------------------


class SkillIn(TranslationsPayload):
    topic_id: int
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=160)
    description: str | None = None
    difficulty: int = Field(default=2, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)


class SkillUpdate(TranslationsPayload):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=160)
    description: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    tags: list[str] | None = None
    topic_id: int | None = None


@router.post("/skills", status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillIn, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    get_or_404(db, Topic, payload.topic_id, "Topic")
    skill = Skill(
        topic_id=payload.topic_id,
        slug=_make_slug(db, Skill, payload.slug or payload.name, 160),
        name=payload.name,
        description=payload.description,
        difficulty=payload.difficulty,
        tags=payload.tags,
        position=next_position(db, Skill, Skill.topic_id == payload.topic_id),
    )
    apply_translations(skill, payload.translations)
    db.add(skill)
    db.flush()
    record_audit(db, admin, "create", "skill", skill.id, f"Created skill “{skill.name}”")
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "slug": skill.slug, "name": skill.name,
            "difficulty": skill.difficulty, "position": skill.position,
            "translations": read_translations(skill)}


@router.patch("/skills/{skill_id}")
def update_skill(
    skill_id: int, payload: SkillUpdate, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    skill = get_or_404(db, Skill, skill_id, "Skill")
    fields = payload.model_dump(exclude_unset=True, exclude={"slug", "translations"})
    if fields.get("topic_id") is not None:
        get_or_404(db, Topic, fields["topic_id"], "Topic")
    before = {key: getattr(skill, key) for key in fields}
    for key, value in fields.items():
        setattr(skill, key, value)
    if payload.slug:
        skill.slug = _make_slug(db, Skill, payload.slug, 160, exclude_id=skill.id)
    apply_translations(skill, payload.translations)
    record_audit(
        db, admin, "update", "skill", skill.id, f"Updated skill “{skill.name}”",
        diff_fields(before, fields),
    )
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "slug": skill.slug, "name": skill.name,
            "difficulty": skill.difficulty, "position": skill.position,
            "translations": read_translations(skill)}


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    """Delete a skill.

    Refused while questions still hang off it: the FK cascades, so allowing this would silently
    delete the question bank and every student attempt against it. The admin must move or delete
    the questions first, which the UI offers as an explicit step.
    """
    skill = get_or_404(db, Skill, skill_id, "Skill")
    question_count = (
        db.scalar(select(func.count()).select_from(Question).where(Question.skill_id == skill_id))
        or 0
    )
    if question_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"“{skill.name}” still has {question_count} exercise(s). Deleting it would "
                "destroy them and every student attempt. Move or delete the exercises first."
            ),
        )
    name = skill.name
    db.delete(skill)
    record_audit(db, admin, "delete", "skill", skill_id, f"Deleted skill “{name}”")
    db.commit()


# --------------------------------------------------------------------------------------
# generic reorder for structure nodes
# --------------------------------------------------------------------------------------

_REORDERABLE = {"units": Unit, "topics": Topic, "skills": Skill, "lessons": Lesson}


@router.post("/structure/{node_type}/reorder")
def reorder_structure(
    node_type: str, payload: dict[str, list[int]], db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """Reorder modules, topics, skills or lessons in one call."""
    model = _REORDERABLE.get(node_type)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reorder “{node_type}”. Expected one of: {sorted(_REORDERABLE)}",
        )
    ids = payload.get("ids") or []
    rows = {row.id: row for row in db.scalars(select(model).where(model.id.in_(ids)))}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown {node_type} ids: {missing}"
        )
    for index, row_id in enumerate(ids, start=1):
        rows[row_id].position = index
    record_audit(db, admin, "reorder", node_type[:-1], None, f"Reordered {len(ids)} {node_type}")
    db.commit()
    return {"reordered": len(ids)}
