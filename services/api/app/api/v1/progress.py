"""Student dashboard and progress reporting."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.adaptive import MASTERY_THRESHOLD, recommend_next
from app.core.deps import CurrentStudent, DbSession, RequestLocale
from app.core.i18n import localise
from app.models import (
    Achievement,
    Assignment,
    AssignmentSubmission,
    Attempt,
    ClassEnrollment,
    ClassGroup,
    Course,
    CourseEnrollment,
    EnrollmentStatus,
    LiveSession,
    SessionStatus,
    Skill,
    StudentAchievement,
    StudentSkillMastery,
    Subject,
    Topic,
    Unit,
    XPEvent,
)
from app.schemas.practice import (
    AchievementRead,
    AssignmentSummary,
    DashboardResponse,
    RecentAttemptRead,
    RecommendationRead,
    SubjectProgress,
    UpcomingSession,
    WeakSkillRead,
)
from app.services.gamification import level_for_xp, xp_for_level
from app.services.practice import summarise_student

router = APIRouter(prefix="/progress", tags=["progress"])


def _translated_name(fallback: str, i18n: dict[str, Any] | None, locale: str) -> str:
    """Pick a translated name out of a raw ``i18n`` value selected by an aggregate query.

    The progress rollup is a GROUP BY, so it works with plain columns rather than ORM instances
    and cannot use ``localise`` directly. Selecting the JSON column alongside the aggregate keeps
    this to one query instead of one extra lookup per subject.
    """
    if locale == "en":
        return fallback
    return ((i18n or {}).get(locale) or {}).get("name") or fallback


def _subject_progress(db, student_id: int, locale: str = "en") -> list[SubjectProgress]:
    """Average mastery per subject, over the skills the student has actually touched.

    Averaging over *every* skill in the curriculum would make a diligent grade-6 student look
    like they have mastered 4% of mathematics, which is demoralising and not what the number is
    trying to communicate.
    """
    rows = db.execute(
        select(
            Subject.slug,
            Subject.name,
            Subject.i18n,
            Subject.color,
            Subject.icon,
            func.avg(StudentSkillMastery.mastery_probability),
            func.count(StudentSkillMastery.id),
            func.sum(case((StudentSkillMastery.mastered_at.is_not(None), 1), else_=0)),
        )
        .join(Course, Course.subject_id == Subject.id)
        .join(Unit, Unit.course_id == Course.id)
        .join(Topic, Topic.unit_id == Unit.id)
        .join(Skill, Skill.topic_id == Topic.id)
        .join(StudentSkillMastery, StudentSkillMastery.skill_id == Skill.id)
        .where(StudentSkillMastery.student_id == student_id)
        .group_by(
            Subject.id, Subject.slug, Subject.name, Subject.i18n, Subject.color, Subject.icon
        )
        .order_by(Subject.position)
    ).all()

    return [
        SubjectProgress(
            subject_slug=slug,
            subject_name=_translated_name(name, i18n, locale),
            color=color,
            icon=icon,
            mastery_percent=int(round((avg_mastery or 0) * 100)),
            skills_tracked=tracked or 0,
            skills_mastered=int(mastered or 0),
        )
        for slug, name, i18n, color, icon, avg_mastery, tracked, mastered in rows
    ]


def _weak_skills(
    db, student_id: int, limit: int = 5, locale: str = "en"
) -> list[WeakSkillRead]:
    rows = list(
        db.scalars(
            select(StudentSkillMastery)
            .where(
                StudentSkillMastery.student_id == student_id,
                StudentSkillMastery.attempts > 0,
                StudentSkillMastery.mastery_probability < MASTERY_THRESHOLD,
            )
            .order_by(StudentSkillMastery.mastery_probability)
            .limit(limit)
            .options(
                selectinload(StudentSkillMastery.skill)
                .selectinload(Skill.topic)
                .selectinload(Topic.unit)
                .selectinload(Unit.course)
                .selectinload(Course.subject)
            )
        )
    )
    result = []
    for row in rows:
        skill = row.skill
        subject_slug = None
        if skill and skill.topic and skill.topic.unit and skill.topic.unit.course:
            subject = skill.topic.unit.course.subject
            subject_slug = subject.slug if subject else None
        result.append(
            WeakSkillRead(
                skill_id=row.skill_id,
                skill_slug=skill.slug if skill else "",
                skill_name=localise(skill, "name", locale) if skill else "",
                subject_slug=subject_slug,
                mastery=round(row.mastery_probability, 4),
                attempts=row.attempts,
                accuracy=round(row.correct / row.attempts, 4) if row.attempts else None,
            )
        )
    return result


def _activity_heatmap(db, student_id: int, days: int = 84) -> list[dict[str, Any]]:
    """Daily XP totals for the streak calendar."""
    since = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=days)
    rows = db.execute(
        select(XPEvent.occurred_on, func.sum(XPEvent.amount))
        .where(XPEvent.student_id == student_id, XPEvent.occurred_on >= since)
        .group_by(XPEvent.occurred_on)
        .order_by(XPEvent.occurred_on)
    ).all()
    return [{"date": day.isoformat(), "xp": int(total or 0)} for day, total in rows]


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: DbSession, student: CurrentStudent, locale: RequestLocale
) -> DashboardResponse:
    """Everything the student dashboard needs, in one request."""
    now = dt.datetime.now(dt.UTC)
    summary = summarise_student(db, student.id)

    subjects = _subject_progress(db, student.id, locale)
    overall = int(round(sum(s.mastery_percent for s in subjects) / len(subjects))) if subjects \
        else 0

    recommendations = [
        RecommendationRead(**rec.as_dict(locale))
        for rec in recommend_next(db, student.id, limit=4)
    ]

    recent = list(
        db.scalars(
            select(Attempt)
            .where(Attempt.student_id == student.id)
            .order_by(Attempt.created_at.desc(), Attempt.id.desc())
            .limit(8)
            .options(selectinload(Attempt.skill))
        )
    )

    # Upcoming live sessions for the classes this student is enrolled in.
    upcoming_rows = list(
        db.execute(
            select(LiveSession, ClassGroup)
            .join(ClassGroup, LiveSession.class_group_id == ClassGroup.id)
            .join(ClassEnrollment, ClassEnrollment.class_group_id == ClassGroup.id)
            .where(
                ClassEnrollment.student_id == student.id,
                ClassEnrollment.status == EnrollmentStatus.ACTIVE,
                LiveSession.starts_at >= now - dt.timedelta(hours=2),
                LiveSession.status != SessionStatus.CANCELLED,
            )
            .order_by(LiveSession.starts_at)
            .limit(5)
        ).all()
    )
    upcoming = [
        UpcomingSession(
            id=live.id,
            title=localise(live, "title", locale),
            class_name=localise(group, "name", locale),
            starts_at=live.starts_at,
            ends_at=live.ends_at,
            join_url=live.join_url,
            provider=live.provider,
            teacher_name=(
                group.teacher.user.full_name
                if group.teacher and group.teacher.user else None
            ),
        )
        for live, group in upcoming_rows
    ]

    assignment_rows = list(
        db.execute(
            select(Assignment, AssignmentSubmission)
            .join(ClassGroup, Assignment.class_group_id == ClassGroup.id)
            .join(ClassEnrollment, ClassEnrollment.class_group_id == ClassGroup.id)
            .outerjoin(
                AssignmentSubmission,
                (AssignmentSubmission.assignment_id == Assignment.id)
                & (AssignmentSubmission.student_id == student.id),
            )
            .where(
                ClassEnrollment.student_id == student.id,
                Assignment.published.is_(True),
            )
            .order_by(Assignment.due_at.is_(None), Assignment.due_at)
            .limit(6)
        ).all()
    )
    assignments = [
        AssignmentSummary(
            id=assignment.id,
            title=assignment.title,
            due_at=assignment.due_at,
            status=submission.status if submission else "assigned",
            score_percent=submission.score_percent if submission else None,
            question_count=len(assignment.question_ids or [])
            or len(assignment.skill_ids or []) * assignment.questions_per_skill,
        )
        for assignment, submission in assignment_rows
    ]

    achievements = [
        AchievementRead(
            slug=link.achievement.slug,
            name=localise(link.achievement, "name", locale),
            description=localise(link.achievement, "description", locale),
            icon=link.achievement.icon,
            tier=link.achievement.tier,
            earned_at=link.earned_at,
        )
        for link in db.scalars(
            select(StudentAchievement)
            .where(StudentAchievement.student_id == student.id)
            .order_by(StudentAchievement.earned_at.desc())
            .limit(8)
            .options(selectinload(StudentAchievement.achievement))
        )
    ]

    enrolled = [
        {
            "course_id": enrollment.course.id,
            "slug": enrollment.course.slug,
            "title": localise(enrollment.course, "title", locale),
            "grade": enrollment.course.grade,
            "last_activity_at": enrollment.last_activity_at,
        }
        for enrollment in db.scalars(
            select(CourseEnrollment)
            .where(
                CourseEnrollment.student_id == student.id,
                CourseEnrollment.is_active.is_(True),
            )
            .options(selectinload(CourseEnrollment.course))
        )
    ]

    level = student.level or level_for_xp(student.xp_total or 0)
    return DashboardResponse(
        student={
            "id": student.id,
            "name": student.user.full_name if student.user else None,
            "grade": student.grade,
            "xp_total": student.xp_total,
            "level": level,
            "xp_into_level": (student.xp_total or 0) - xp_for_level(level),
            "xp_for_next_level": xp_for_level(level + 1) - xp_for_level(level),
            "streak_days": student.streak_days,
            "longest_streak_days": student.longest_streak_days,
        },
        overall_mastery_percent=overall,
        subjects=subjects,
        recommendations=recommendations,
        weak_skills=_weak_skills(db, student.id, locale=locale),
        recent_attempts=[
            RecentAttemptRead(
                id=a.id,
                skill_name=localise(a.skill, "name", locale) if a.skill else "",
                is_correct=a.is_correct,
                score=round(a.score, 3),
                created_at=a.created_at,
            )
            for a in recent
        ],
        upcoming_sessions=upcoming,
        assignments=assignments,
        achievements=achievements,
        enrolled_courses=enrolled,
        stats=summary,
        activity=_activity_heatmap(db, student.id),
    )


@router.get("/mastery")
def mastery_breakdown(
    db: DbSession,
    student: CurrentStudent,
    locale: RequestLocale,
    subject: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    """Full per-skill mastery list, used by the detailed progress page."""
    query = (
        select(StudentSkillMastery)
        .where(StudentSkillMastery.student_id == student.id)
        .options(
            selectinload(StudentSkillMastery.skill)
            .selectinload(Skill.topic)
            .selectinload(Topic.unit)
            .selectinload(Unit.course)
            .selectinload(Course.subject)
        )
        .order_by(StudentSkillMastery.mastery_probability.desc())
    )
    rows = list(db.scalars(query))

    result = []
    for row in rows:
        skill = row.skill
        if skill is None:
            continue
        course = skill.topic.unit.course if skill.topic and skill.topic.unit else None
        subject_obj = course.subject if course else None
        if subject and (subject_obj is None or subject_obj.slug != subject):
            continue
        result.append(
            {
                "skill_id": skill.id,
                "skill_slug": skill.slug,
                "skill_name": localise(skill, "name", locale),
                "topic": localise(skill.topic, "title", locale) if skill.topic else None,
                "unit": (
                    localise(skill.topic.unit, "title", locale)
                    if skill.topic and skill.topic.unit
                    else None
                ),
                "subject_slug": subject_obj.slug if subject_obj else None,
                "grade": course.grade if course else None,
                "mastery": round(row.mastery_probability, 4),
                "mastery_percent": int(round(row.mastery_probability * 100)),
                "attempts": row.attempts,
                "correct": row.correct,
                "incorrect": row.incorrect,
                "accuracy": round(row.correct / row.attempts, 4) if row.attempts else None,
                "is_mastered": row.mastered_at is not None,
                "last_practiced_at": row.last_practiced_at,
            }
        )
    return result


@router.post("/courses/{course_slug}/enroll", status_code=status.HTTP_201_CREATED)
def enroll_in_course(
    course_slug: str, db: DbSession, student: CurrentStudent
) -> dict[str, Any]:
    """Self-serve enrollment in a free self-study course."""
    course = db.scalar(select(Course).where(Course.slug == course_slug))
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    existing = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.student_id == student.id,
            CourseEnrollment.course_id == course.id,
        )
    )
    if existing is not None:
        existing.is_active = True
        existing.last_activity_at = dt.datetime.now(dt.UTC)
        db.commit()
        return {"enrolled": True, "course_id": course.id, "already_enrolled": True}

    db.add(
        CourseEnrollment(
            student_id=student.id,
            course_id=course.id,
            last_activity_at=dt.datetime.now(dt.UTC),
        )
    )
    db.commit()
    return {"enrolled": True, "course_id": course.id, "already_enrolled": False}


@router.get("/achievements", response_model=list[AchievementRead])
def list_achievements(db: DbSession, locale: RequestLocale) -> list[AchievementRead]:
    """Every badge the platform defines, in the reader's language.

    The achievements screen used to carry its own hardcoded copy of this list so it could show
    the ones still to earn. That copy was English-only and drifted from the database the moment
    either changed; serving the catalogue makes the database the single source of truth for both
    the earned and the unearned half of the screen.
    """
    return [
        AchievementRead(
            slug=row.slug,
            name=localise(row, "name", locale),
            description=localise(row, "description", locale),
            icon=row.icon,
            tier=row.tier,
        )
        for row in db.scalars(select(Achievement).order_by(Achievement.id))
    ]
