"""Recommendation engine and learning-path construction.

The rule that shapes everything here: **never recommend a skill whose prerequisites are not in
place.** OATutor's heuristic picks the single lowest-mastery skill, which is a good idea taken one
step too far — the lowest-mastery skill is very often the one the student is not ready for, and
sending them there produces failure, not learning. When we find such a skill we walk *down* the
prerequisite graph and recommend the foundation instead.

Scoring blends four signals:

1. **Mastery gap** — how far below mastery the skill sits. The dominant term.
2. **Readiness** — how well the prerequisites are established. Gates, and also boosts.
3. **Recency** — skills untouched for a while, decayed by the forgetting model, resurface.
4. **Recent errors** — a skill the student got wrong in the last few attempts jumps the queue.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adaptive.bkt import MASTERY_THRESHOLD, STRUGGLING_THRESHOLD, decay_mastery
from app.models import (
    Course,
    Skill,
    SkillPrerequisite,
    StudentSkillMastery,
    Subject,
    Topic,
    Unit,
)

__all__ = [
    "Recommendation",
    "SkillStatus",
    "recommend_next",
    "build_learning_path",
    "PREREQUISITE_GATE",
]

# A prerequisite counts as "in place" at this mastery. Deliberately below MASTERY_THRESHOLD:
# requiring full mastery of every prerequisite would stall students on foundations forever, and
# partial knowledge is enough to start the next skill productively.
PREREQUISITE_GATE = 0.60

# Skills untouched for longer than this are candidates for review.
REVIEW_AFTER_DAYS = 14


@dataclass
class Recommendation:
    skill: Skill
    score: float
    reason: str            # machine-readable code, translated in the UI
    detail: str            # human-readable English fallback
    mastery: float
    readiness: float
    is_locked: bool = False
    blocked_by: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill.id,
            "skill_slug": self.skill.slug,
            "skill_name": self.skill.name,
            "topic": self.skill.topic.title if self.skill.topic else None,
            "score": round(self.score, 4),
            "reason": self.reason,
            "detail": self.detail,
            "mastery": round(self.mastery, 4),
            "readiness": round(self.readiness, 4),
            "difficulty": self.skill.difficulty,
        }


@dataclass
class SkillStatus:
    skill: Skill
    mastery: float
    status: str            # mastered | in_progress | available | locked
    attempts: int
    blocked_by: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------------------


def _load_skills(db: Session, *, subject_slug: str | None, grades: list[int] | None) -> list[Skill]:
    query = (
        select(Skill)
        .join(Topic, Skill.topic_id == Topic.id)
        .join(Unit, Topic.unit_id == Unit.id)
        .join(Course, Unit.course_id == Course.id)
        .options(selectinload(Skill.topic).selectinload(Topic.unit).selectinload(Unit.course))
    )
    if subject_slug:
        query = query.join(Subject, Course.subject_id == Subject.id).where(
            Subject.slug == subject_slug
        )
    if grades:
        query = query.where(Course.grade.in_(grades))
    return list(db.scalars(query).unique())


def _mastery_map(db: Session, student_id: int) -> dict[int, StudentSkillMastery]:
    rows = db.scalars(
        select(StudentSkillMastery).where(StudentSkillMastery.student_id == student_id)
    )
    return {row.skill_id: row for row in rows}


def _prerequisite_map(db: Session, skill_ids: list[int]) -> dict[int, list[SkillPrerequisite]]:
    if not skill_ids:
        return {}
    rows = db.scalars(
        select(SkillPrerequisite)
        .where(SkillPrerequisite.skill_id.in_(skill_ids))
        .options(selectinload(SkillPrerequisite.prerequisite))
    )
    mapping: dict[int, list[SkillPrerequisite]] = {}
    for row in rows:
        mapping.setdefault(row.skill_id, []).append(row)
    return mapping


def _current_mastery(record: StudentSkillMastery | None, skill: Skill, now: dt.datetime) -> float:
    """Mastery with forgetting applied, or the skill's prior for an untouched skill."""
    if record is None:
        return skill.bkt_p_init
    if record.last_practiced_at is None:
        return record.mastery_probability

    last = record.last_practiced_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=dt.UTC)
    days = max(0.0, (now - last).total_seconds() / 86400.0)
    return decay_mastery(record.mastery_probability, days)


# --------------------------------------------------------------------------------------
# recommendation
# --------------------------------------------------------------------------------------


def recommend_next(
    db: Session,
    student_id: int,
    *,
    limit: int = 5,
    subject_slug: str | None = None,
    grades: list[int] | None = None,
) -> list[Recommendation]:
    """Rank the most valuable next skills for this student."""
    now = dt.datetime.now(dt.UTC)
    skills = _load_skills(db, subject_slug=subject_slug, grades=grades)
    if not skills:
        return []

    mastery_records = _mastery_map(db, student_id)
    prerequisites = _prerequisite_map(db, [s.id for s in skills])

    mastery_of: dict[int, float] = {
        skill.id: _current_mastery(mastery_records.get(skill.id), skill, now) for skill in skills
    }

    def readiness_of(skill: Skill) -> tuple[float, list[Skill], list[Skill]]:
        """Classify a skill's hard prerequisites.

        Returns ``(lowest_prerequisite_mastery, demonstrated_weak, never_assessed)``.

        The distinction is essential. A prerequisite the student has *tried and struggled with*
        is real evidence that they are not ready. A prerequisite they have simply never touched
        is not — a grade 8 student has almost certainly met grade 6 place value at school, even
        though our database has no record of it.

        Treating both cases as blocking was a genuine bug: every skill in the curriculum
        ultimately depends on some grade 6 foundation, so a new student found *everything*
        locked and was recommended nothing but the most elementary skills in the platform.
        Only demonstrated weakness gates; unassessed prerequisites merely reduce the score.
        """
        links = prerequisites.get(skill.id, [])
        hard = [link for link in links if link.strength >= 0.75]
        if not hard:
            return 1.0, [], []

        demonstrated_weak: list[Skill] = []
        never_assessed: list[Skill] = []
        for link in hard:
            record = mastery_records.get(link.prerequisite_id)
            mastery = mastery_of.get(link.prerequisite_id, link.prerequisite.bkt_p_init)
            if record is None or record.attempts == 0:
                never_assessed.append(link.prerequisite)
            elif mastery < PREREQUISITE_GATE:
                demonstrated_weak.append(link.prerequisite)

        lowest = min(
            mastery_of.get(link.prerequisite_id, link.prerequisite.bkt_p_init) for link in hard
        )
        return lowest, demonstrated_weak, never_assessed

    candidates: dict[int, Recommendation] = {}

    for skill in skills:
        mastery = mastery_of[skill.id]
        record = mastery_records.get(skill.id)
        readiness, missing, unassessed = readiness_of(skill)

        # A blocked skill is not itself a recommendation — the weakest missing prerequisite is.
        if missing:
            target = min(missing, key=lambda s: mastery_of.get(s.id, s.bkt_p_init))
            target_mastery = mastery_of.get(target.id, target.bkt_p_init)
            target_readiness, target_missing, _ = readiness_of(target)
            if target_missing:
                continue  # the foundation has its own gaps; it will surface on its own pass
            score = 1.0 + (1.0 - target_mastery)  # foundations outrank everything else
            existing = candidates.get(target.id)
            if existing is None or existing.score < score:
                candidates[target.id] = Recommendation(
                    skill=target,
                    score=score,
                    reason="prerequisite_gap",
                    detail=f"Needed before you can start {skill.name}",
                    mastery=target_mastery,
                    readiness=target_readiness,
                    blocked_by=[],
                )
            continue

        if mastery >= MASTERY_THRESHOLD:
            # Mastered. Only resurface it if it is genuinely going stale.
            stale_days = _days_since(record, now)
            if stale_days is not None and stale_days >= REVIEW_AFTER_DAYS:
                candidates.setdefault(
                    skill.id,
                    Recommendation(
                        skill=skill,
                        score=0.30 + min(stale_days / 120.0, 0.25),
                        reason="review_due",
                        detail=f"Keep {skill.name} sharp — last practised "
                               f"{int(stale_days)} days ago",
                        mastery=mastery,
                        readiness=readiness,
                    ),
                )
            continue

        score = 0.0
        # 1. Mastery gap — the main driver.
        score += 1.2 * (MASTERY_THRESHOLD - mastery)
        # 2. Readiness bonus: prefer skills the student is genuinely equipped for.
        score += 0.35 * readiness
        # 3. Recent errors.
        if record is not None and record.recent_outcomes:
            window = record.recent_outcomes[-5:]
            error_rate = 1.0 - (sum(window) / len(window))
            score += 0.45 * error_rate
        # 4. Already started but unfinished — finishing beats starting something new.
        if record is not None and 0 < record.attempts:
            score += 0.20
        # 5. Nudge toward easier skills when the student is struggling overall.
        if mastery < STRUGGLING_THRESHOLD:
            score += 0.15 * (5 - skill.difficulty) / 4.0
        # 6. Mild penalty when foundations are unproven — prefer skills we know they are
        #    ready for, without locking them out of anything.
        if unassessed:
            score -= 0.08 * min(len(unassessed), 3)

        reason, detail = _classify(record, mastery)
        candidates[skill.id] = Recommendation(
            skill=skill,
            score=score,
            reason=reason,
            detail=detail,
            mastery=mastery,
            readiness=readiness,
        )

    ranked = sorted(candidates.values(), key=lambda r: (-r.score, r.skill.difficulty, r.skill.id))
    return ranked[:limit]


def _days_since(record: StudentSkillMastery | None, now: dt.datetime) -> float | None:
    if record is None or record.last_practiced_at is None:
        return None
    last = record.last_practiced_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=dt.UTC)
    return max(0.0, (now - last).total_seconds() / 86400.0)


def _classify(record: StudentSkillMastery | None, mastery: float) -> tuple[str, str]:
    if record is None or record.attempts == 0:
        return "new_skill", "A new skill you are ready to start"
    if mastery < STRUGGLING_THRESHOLD:
        return "weak_skill", "This one needs more work — let's build it up"
    return "in_progress", "You have made a start — keep going to reach mastery"


# --------------------------------------------------------------------------------------
# learning path
# --------------------------------------------------------------------------------------


def build_learning_path(db: Session, student_id: int, *, unit_id: int) -> list[SkillStatus]:
    """Ordered skills for one unit, each tagged mastered / in_progress / available / locked.

    This is what drives the Duolingo-style path UI, so the ordering must be stable and the lock
    state must be honest — a student should never be able to click into a skill the engine
    considers locked.
    """
    now = dt.datetime.now(dt.UTC)
    skills = list(
        db.scalars(
            select(Skill)
            .join(Topic, Skill.topic_id == Topic.id)
            .where(Topic.unit_id == unit_id)
            .order_by(Topic.position, Skill.position, Skill.id)
            .options(selectinload(Skill.topic))
        ).unique()
    )
    if not skills:
        return []

    records = _mastery_map(db, student_id)
    prerequisites = _prerequisite_map(db, [s.id for s in skills])

    # Prerequisites may point outside this unit, so mastery has to be resolved globally.
    external_ids = {
        link.prerequisite_id
        for links in prerequisites.values()
        for link in links
    }
    external = {
        skill.id: skill
        for skill in db.scalars(select(Skill).where(Skill.id.in_(external_ids))).unique()
    } if external_ids else {}

    def mastery_for(skill_id: int, fallback: Skill | None) -> float:
        record = records.get(skill_id)
        skill = external.get(skill_id) or fallback
        if skill is None:
            return record.mastery_probability if record else 0.0
        return _current_mastery(record, skill, now)

    unit_skill_ids = {skill.id for skill in skills}

    path: list[SkillStatus] = []
    for skill in skills:
        record = records.get(skill.id)
        mastery = _current_mastery(record, skill, now)

        # Locking rules mirror the recommender, with one addition: an unassessed prerequisite
        # *inside this unit* still locks, so the path reads as a sequence the student works
        # through. An unassessed prerequisite from another grade does not, because we have no
        # evidence the student lacks it and locking it would make a fresh course look broken.
        blocked_by: list[str] = []
        for link in prerequisites.get(skill.id, []):
            if link.strength < 0.75:
                continue
            prerequisite_record = records.get(link.prerequisite_id)
            prerequisite_mastery = mastery_for(link.prerequisite_id, link.prerequisite)
            attempted = prerequisite_record is not None and prerequisite_record.attempts > 0

            if attempted and prerequisite_mastery < PREREQUISITE_GATE:
                blocked_by.append(link.prerequisite.name)
            elif not attempted and link.prerequisite_id in unit_skill_ids:
                blocked_by.append(link.prerequisite.name)

        if mastery >= MASTERY_THRESHOLD:
            status = "mastered"
        elif blocked_by:
            status = "locked"
        elif record is not None and record.attempts > 0:
            status = "in_progress"
        else:
            status = "available"

        path.append(
            SkillStatus(
                skill=skill,
                mastery=mastery,
                status=status,
                attempts=record.attempts if record else 0,
                blocked_by=blocked_by,
            )
        )

    return path
