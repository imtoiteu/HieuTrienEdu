"""Public curriculum browsing: subjects, courses, units, topics, skills and lessons."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, OptionalUser, RequestLocale
from app.core.i18n import localise
from app.models import (
    Course,
    Lesson,
    LessonProgress,
    Question,
    Resource,
    ReviewStatus,
    Skill,
    SkillPrerequisite,
    SkillRelation,
    Subject,
    Topic,
    Unit,
    UserRole,
)
from app.schemas.curriculum import (
    CourseDetail,
    CourseSummary,
    LessonDetail,
    LessonProgressUpdate,
    LessonSummary,
    ResourceRead,
    SkillDetail,
    SkillRead,
    SubjectRead,
    TopicRead,
    UnitRead,
    VideoRead,
)
from app.services.storage import playback_url

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


def _lesson_resources(db, lesson: Lesson, locale: str) -> list[ResourceRead]:
    """Further reading for a lesson: its own resources plus its topic's.

    A resource attached to the topic is relevant to every lesson in it — a simulation of the
    phenomenon, the textbook chapter behind it — so it appears under each, after the ones
    attached to this lesson specifically.
    """
    conditions = [Resource.lesson_id == lesson.id]
    if lesson.topic_id is not None:
        conditions.append(Resource.topic_id == lesson.topic_id)

    rows = db.scalars(
        select(Resource)
        .where(Resource.is_public.is_(True), or_(*conditions))
        # Lesson-specific first, then topic-wide; authored position breaks ties within each.
        .order_by(Resource.lesson_id.is_(None), Resource.position, Resource.id)
    ).all()

    return [
        ResourceRead(
            id=row.id,
            title=localise(row, "title", locale),
            description=localise(row, "description", locale),
            resource_type=row.resource_type,
            url=row.url,
            host=urlparse(row.url).hostname,
            license=row.license,
            attribution=row.attribution,
        )
        for row in rows
    ]


def _visible_to(course: Course | None, user) -> bool:
    """Whether this course's contents may be served to ``user``.

    Anything below a course inherits the course's published state — a unit or skill reachable
    while its course is a draft is the same leak by a different URL.
    """
    if course is None or course.is_published:
        return True
    return user is not None and user.role in {UserRole.TEACHER, UserRole.ADMIN}


def _skill_read(skill: Skill, locale: str) -> SkillRead:
    """Serialise a skill with its name and description in the requested language."""
    return SkillRead(
        id=skill.id,
        slug=skill.slug,
        name=localise(skill, "name", locale),
        description=localise(skill, "description", locale),
        difficulty=skill.difficulty,
        position=skill.position,
        tags=skill.tags or [],
    )


def _course_counts(db, course_ids: list[int]) -> dict[int, dict[str, int]]:
    """Unit / skill / lesson counts per course, in three queries rather than N+1."""
    if not course_ids:
        return {}

    counts: dict[int, dict[str, int]] = {
        cid: {"unit_count": 0, "skill_count": 0, "lesson_count": 0} for cid in course_ids
    }

    for course_id, total in db.execute(
        select(Unit.course_id, func.count(Unit.id))
        .where(Unit.course_id.in_(course_ids))
        .group_by(Unit.course_id)
    ):
        counts[course_id]["unit_count"] = total

    for course_id, total in db.execute(
        select(Unit.course_id, func.count(Skill.id))
        .join(Topic, Topic.unit_id == Unit.id)
        .join(Skill, Skill.topic_id == Topic.id)
        .where(Unit.course_id.in_(course_ids))
        .group_by(Unit.course_id)
    ):
        counts[course_id]["skill_count"] = total

    for course_id, total in db.execute(
        select(Unit.course_id, func.count(Lesson.id))
        .join(Topic, Topic.unit_id == Unit.id)
        .join(Lesson, Lesson.topic_id == Topic.id)
        .where(Unit.course_id.in_(course_ids), Lesson.status == ReviewStatus.PUBLISHED)
        .group_by(Unit.course_id)
    ):
        counts[course_id]["lesson_count"] = total

    return counts


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(db: DbSession, locale: RequestLocale) -> list[SubjectRead]:
    subjects = list(
        db.scalars(
            select(Subject)
            .order_by(Subject.position, Subject.id)
            .options(selectinload(Subject.courses))
        ).unique()
    )
    all_course_ids = [c.id for s in subjects for c in s.courses]
    counts = _course_counts(db, all_course_ids)

    result = []
    for subject in subjects:
        courses = [
            CourseSummary(
                id=c.id, slug=c.slug, title=localise(c, 'title', locale), grade=c.grade,
                summary=localise(c, 'summary', locale),
                estimated_hours=c.estimated_hours, **counts.get(c.id, {})
            )
            for c in sorted(subject.courses, key=lambda c: c.grade)
            if c.is_published
        ]
        result.append(
            SubjectRead(
                id=subject.id, slug=subject.slug, name=localise(subject, 'name', locale),
                description=localise(subject, 'description', locale),
                icon=subject.icon, color=subject.color,
                courses=courses,
            )
        )
    return result


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(
    db: DbSession,
    locale: RequestLocale,
    subject: Annotated[str | None, Query(description="Subject slug")] = None,
    grade: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> list[CourseSummary]:
    query = select(Course).where(Course.is_published.is_(True))
    if subject:
        query = query.join(Subject).where(Subject.slug == subject)
    if grade:
        query = query.where(Course.grade == grade)

    courses = list(db.scalars(query.order_by(Course.position, Course.grade)))
    counts = _course_counts(db, [c.id for c in courses])
    return [
        CourseSummary(
            id=c.id, slug=c.slug, title=localise(c, 'title', locale), grade=c.grade,
                summary=localise(c, 'summary', locale),
            estimated_hours=c.estimated_hours, **counts.get(c.id, {})
        )
        for c in courses
    ]


@router.get("/courses/{course_slug}", response_model=CourseDetail)
def get_course(
    course_slug: str,
    db: DbSession,
    locale: RequestLocale,
    user: OptionalUser = None,
) -> CourseDetail:
    course = db.scalar(
        select(Course)
        .where(Course.slug == course_slug)
        .options(
            selectinload(Course.subject),
            selectinload(Course.units)
            .selectinload(Unit.topics)
            .selectinload(Topic.skills),
        )
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    # Unpublishing removed a course from the listings but left this endpoint serving it in full,
    # so the slug — which is guessable and stays in search results and old links — remained a way
    # to read a draft. Staff keep access so they can preview before publishing, exactly as
    # ``get_lesson`` does.
    if not course.is_published and (
        user is None or user.role not in {UserRole.TEACHER, UserRole.ADMIN}
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    counts = _course_counts(db, [course.id]).get(course.id, {})
    return CourseDetail(
        id=course.id, slug=course.slug, title=localise(course, 'title', locale), grade=course.grade,
        summary=localise(course, 'summary', locale),
        description=localise(course, 'description', locale),
        estimated_hours=course.estimated_hours,
        subject_slug=course.subject.slug if course.subject else None,
        subject_name=localise(course.subject, 'name', locale) if course.subject else None,
        units=[
            UnitRead(
                id=u.id, slug=u.slug, title=localise(u, 'title', locale),
                summary=localise(u, 'summary', locale), icon=u.icon,
                position=u.position,
                topics=[
                    TopicRead(
                        id=t.id, slug=t.slug, title=localise(t, 'title', locale),
                        summary=localise(t, 'summary', locale),
                        position=t.position,
                        skills=[_skill_read(s, locale)
                                for s in sorted(t.skills, key=lambda s: (s.position, s.id))],
                    )
                    for t in sorted(u.topics, key=lambda t: (t.position, t.id))
                ],
            )
            for u in sorted(course.units, key=lambda u: (u.position, u.id))
        ],
        **counts,
    )


@router.get("/units/{unit_slug}", response_model=UnitRead)
def get_unit(
    unit_slug: str, db: DbSession, locale: RequestLocale, user: OptionalUser = None
) -> UnitRead:
    unit = db.scalar(
        select(Unit)
        .where(Unit.slug == unit_slug)
        .options(
            selectinload(Unit.course), selectinload(Unit.topics).selectinload(Topic.skills)
        )
    )
    if unit is None or not _visible_to(unit.course, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    return UnitRead(
        id=unit.id, slug=unit.slug, title=localise(unit, 'title', locale),
        summary=localise(unit, 'summary', locale), icon=unit.icon,
        position=unit.position,
        topics=[
            TopicRead(
                id=t.id, slug=t.slug, title=localise(t, 'title', locale),
                summary=localise(t, 'summary', locale), position=t.position,
                skills=[_skill_read(s, locale)
                        for s in sorted(t.skills, key=lambda s: (s.position, s.id))],
            )
            for t in sorted(unit.topics, key=lambda t: (t.position, t.id))
        ],
    )


@router.get("/skills/{skill_slug}", response_model=SkillDetail)
def get_skill(
    skill_slug: str, db: DbSession, locale: RequestLocale, user: OptionalUser = None
) -> SkillDetail:
    skill = db.scalar(
        select(Skill)
        .where(Skill.slug == skill_slug)
        .options(selectinload(Skill.topic).selectinload(Topic.unit).selectinload(Unit.course)
                 .selectinload(Course.subject))
    )
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    unit = skill.topic.unit if skill.topic else None
    if not _visible_to(unit.course if unit else None, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    prerequisites = list(
        db.scalars(
            select(Skill)
            .join(SkillPrerequisite, SkillPrerequisite.prerequisite_id == Skill.id)
            .where(SkillPrerequisite.skill_id == skill.id)
        )
    )
    unlocks = list(
        db.scalars(
            select(Skill)
            .join(SkillPrerequisite, SkillPrerequisite.skill_id == Skill.id)
            .where(SkillPrerequisite.prerequisite_id == skill.id)
        )
    )
    related = list(
        db.scalars(
            select(Skill)
            .join(SkillRelation, SkillRelation.related_skill_id == Skill.id)
            .where(SkillRelation.skill_id == skill.id)
        )
    )
    question_count = db.scalar(
        select(func.count()).select_from(Question).where(
            Question.skill_id == skill.id, Question.status == ReviewStatus.PUBLISHED
        )
    ) or 0
    lesson_count = db.scalar(
        select(func.count()).select_from(Lesson).where(Lesson.skill_id == skill.id)
    ) or 0

    topic = skill.topic
    unit = topic.unit if topic else None
    course = unit.course if unit else None

    return SkillDetail(
        **_skill_read(skill, locale).model_dump(),
        topic_slug=topic.slug if topic else None,
        topic_title=localise(topic, 'title', locale) if topic else None,
        unit_title=localise(unit, 'title', locale) if unit else None,
        course_title=localise(course, 'title', locale) if course else None,
        subject_slug=course.subject.slug if course and course.subject else None,
        grade=course.grade if course else None,
        prerequisites=[_skill_read(s, locale) for s in prerequisites],
        unlocks=[_skill_read(s, locale) for s in unlocks],
        related=[_skill_read(s, locale) for s in related],
        question_count=question_count,
        lesson_count=lesson_count,
    )


@router.get("/topics/{topic_slug}/lessons", response_model=list[LessonSummary])
def list_topic_lessons(
    topic_slug: str, db: DbSession, locale: RequestLocale, user: OptionalUser = None
) -> list[LessonSummary]:
    topic = db.scalar(
        select(Topic)
        .where(Topic.slug == topic_slug)
        .options(selectinload(Topic.unit).selectinload(Unit.course))
    )
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if not _visible_to(topic.unit.course if topic.unit else None, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    lessons = db.scalars(
        select(Lesson)
        .where(Lesson.topic_id == topic.id, Lesson.status == ReviewStatus.PUBLISHED)
        .order_by(Lesson.position, Lesson.id)
    )
    return [
        LessonSummary(
            id=lesson.id, slug=lesson.slug, title=localise(lesson, 'title', locale),
            summary=localise(lesson, 'summary', locale),
            estimated_minutes=lesson.estimated_minutes, position=lesson.position,
            objectives=localise(lesson, 'objectives', locale) or [],
        )
        for lesson in lessons
    ]


@router.get("/lessons/{lesson_slug}", response_model=LessonDetail)
def get_lesson(
    lesson_slug: str,
    db: DbSession,
    locale: RequestLocale,
    user: OptionalUser = None,
) -> LessonDetail:
    lesson = db.scalar(
        select(Lesson)
        .where(Lesson.slug == lesson_slug)
        .options(
            selectinload(Lesson.topic), selectinload(Lesson.skill), selectinload(Lesson.video)
        )
    )
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if lesson.status != ReviewStatus.PUBLISHED and (
        user is None or user.role not in {UserRole.TEACHER, UserRole.ADMIN}
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    video = None
    if lesson.video:
        video = VideoRead(
            **{k: getattr(lesson.video, k) for k in
               ("id", "title", "provider", "external_id", "duration_seconds",
                "thumbnail_url", "chapters", "captions", "attribution")},
            playback_url=playback_url(lesson.video.provider, lesson.video.external_id),
        )

    detail = LessonDetail(
        id=lesson.id, slug=lesson.slug, title=localise(lesson, 'title', locale),
        summary=localise(lesson, 'summary', locale),
        estimated_minutes=lesson.estimated_minutes, position=lesson.position,
        objectives=localise(lesson, 'objectives', locale) or [],
        blocks=localise(lesson, 'blocks', locale) or [],
        topic_slug=lesson.topic.slug if lesson.topic else None,
        topic_title=localise(lesson.topic, 'title', locale) if lesson.topic else None,
        skill_slug=lesson.skill.slug if lesson.skill else None,
        skill_name=localise(lesson.skill, 'name', locale) if lesson.skill else None,
        video=video, resources=_lesson_resources(db, lesson, locale),
        attribution=lesson.attribution, license=lesson.license,
    )

    if user is not None and user.student_profile is not None:
        progress = db.scalar(
            select(LessonProgress).where(
                LessonProgress.student_id == user.student_profile.id,
                LessonProgress.lesson_id == lesson.id,
            )
        )
        detail.progress_percent = progress.progress_percent if progress else 0
        detail.completed = progress.completed if progress else False
        detail.video_position_seconds = progress.video_position_seconds if progress else 0

    return detail


@router.put("/lessons/{lesson_slug}/progress", response_model=LessonDetail)
def update_lesson_progress(
    lesson_slug: str,
    payload: LessonProgressUpdate,
    db: DbSession,
    locale: RequestLocale,
    user: CurrentUser,
) -> LessonDetail:
    """Record how far a student has read/watched. Also used to resume video playback."""
    import datetime as dt

    from app.services.gamification import XP_RULES, award_xp, check_achievements, update_streak

    if user.student_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only students track lesson progress"
        )

    lesson = db.scalar(select(Lesson).where(Lesson.slug == lesson_slug))
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    student = user.student_profile
    progress = db.scalar(
        select(LessonProgress).where(
            LessonProgress.student_id == student.id, LessonProgress.lesson_id == lesson.id
        )
    )
    if progress is None:
        progress = LessonProgress(student_id=student.id, lesson_id=lesson.id)
        db.add(progress)

    was_complete = progress.completed
    now = dt.datetime.now(dt.UTC)

    # Never move progress backwards — a student scrubbing back in a video has not un-learned it.
    progress.progress_percent = max(progress.progress_percent or 0, payload.progress_percent)
    progress.video_position_seconds = payload.video_position_seconds
    progress.last_viewed_at = now

    if (payload.completed or progress.progress_percent >= 100) and not was_complete:
        progress.completed = True
        progress.completed_at = now
        award_xp(db, student, XP_RULES["lesson_complete"], "lesson_complete",
                 {"lesson": lesson.slug})
        update_streak(student)
        check_achievements(db, student)

    db.commit()
    # Keyword arguments: ``locale`` sits before ``user`` in the signature, and passing them
    # positionally once bound the User object to the locale and quietly returned English.
    return get_lesson(lesson_slug, db=db, locale=locale, user=user)
