"""XP, levels, streaks and achievements.

The brief asks for *moderate* gamification aimed at 11-15 year olds: motivating without being
patronising. Concretely that means rewards track genuine effort and progress rather than raw
volume — a student cannot farm XP by hammering the easiest skill, because mastered skills stop
paying out, and a wrong answer still earns a little for the attempt.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    StudentAchievement,
    StudentProfile,
    StudentSkillMastery,
    XPEvent,
)

__all__ = ["XP_RULES", "award_xp", "update_streak", "check_achievements", "level_for_xp",
           "xp_for_level", "GamificationResult"]

XP_RULES = {
    "correct_first_try": 12,
    "correct_with_hints": 6,
    "incorrect_attempt": 2,      # effort still counts — this keeps struggling students engaged
    "skill_mastered": 60,
    "session_complete": 15,
    "perfect_session": 25,
    "lesson_complete": 20,
    "streak_day": 5,
}

# Levels get progressively more expensive: level L needs 150 * L^1.6 XP in total.
_LEVEL_EXPONENT = 1.6
_LEVEL_BASE = 150
MAX_LEVEL = 60


@dataclass
class GamificationResult:
    xp_awarded: int = 0
    level_before: int = 1
    level_after: int = 1
    streak_days: int = 0
    streak_extended: bool = False
    new_achievements: list[Achievement] = field(default_factory=list)

    @property
    def levelled_up(self) -> bool:
        return self.level_after > self.level_before

    def as_dict(self) -> dict[str, Any]:
        return {
            "xp_awarded": self.xp_awarded,
            "level_before": self.level_before,
            "level_after": self.level_after,
            "levelled_up": self.levelled_up,
            "streak_days": self.streak_days,
            "streak_extended": self.streak_extended,
            "new_achievements": [
                {"slug": a.slug, "name": a.name, "description": a.description,
                 "icon": a.icon, "tier": a.tier}
                for a in self.new_achievements
            ],
        }


def xp_for_level(level: int) -> int:
    """Total XP needed to reach ``level``."""
    if level <= 1:
        return 0
    return int(_LEVEL_BASE * (level - 1) ** _LEVEL_EXPONENT)


def level_for_xp(xp: int) -> int:
    level = 1
    while level < MAX_LEVEL and xp >= xp_for_level(level + 1):
        level += 1
    return level


def award_xp(
    db: Session,
    student: StudentProfile,
    amount: int,
    reason: str,
    context: dict[str, Any] | None = None,
) -> int:
    """Append to the XP ledger and update the denormalised total. Returns the amount awarded."""
    if amount <= 0:
        return 0
    db.add(
        XPEvent(
            student_id=student.id,
            amount=amount,
            reason=reason,
            context=context or {},
            occurred_on=dt.datetime.now(dt.UTC).date(),
        )
    )
    student.xp_total = (student.xp_total or 0) + amount
    student.level = level_for_xp(student.xp_total)
    return amount


def update_streak(student: StudentProfile, today: dt.date | None = None) -> bool:
    """Advance the daily streak. Returns True if today extended it.

    Called on any meaningful learning activity. Idempotent within a day, so a student who does
    five sessions gets one streak day, not five.
    """
    today = today or dt.datetime.now(dt.UTC).date()
    last = student.last_activity_date

    if last == today:
        return False

    if last is not None and (today - last).days == 1:
        student.streak_days = (student.streak_days or 0) + 1
    else:
        # Either the first ever activity, or the chain broke.
        student.streak_days = 1

    student.last_activity_date = today
    student.longest_streak_days = max(student.longest_streak_days or 0, student.streak_days)
    return True


def _criteria_met(db: Session, student: StudentProfile, criteria: dict[str, Any]) -> bool:
    kind = criteria.get("type")
    target = criteria.get("value", 0)

    if kind == "streak_days":
        return (student.streak_days or 0) >= target
    if kind == "xp_total":
        return (student.xp_total or 0) >= target
    if kind == "level":
        return (student.level or 1) >= target
    if kind == "skills_mastered":
        count = db.scalar(
            select(func.count())
            .select_from(StudentSkillMastery)
            .where(
                StudentSkillMastery.student_id == student.id,
                StudentSkillMastery.mastered_at.is_not(None),
            )
        )
        return (count or 0) >= target
    if kind == "questions_correct":
        total = db.scalar(
            select(func.coalesce(func.sum(StudentSkillMastery.correct), 0)).where(
                StudentSkillMastery.student_id == student.id
            )
        )
        return (total or 0) >= target
    if kind == "questions_attempted":
        total = db.scalar(
            select(func.coalesce(func.sum(StudentSkillMastery.attempts), 0)).where(
                StudentSkillMastery.student_id == student.id
            )
        )
        return (total or 0) >= target
    # Unknown criteria never fire, rather than firing by accident.
    return False


def check_achievements(db: Session, student: StudentProfile) -> list[Achievement]:
    """Award any newly-earned achievements. Returns the ones granted by this call."""
    earned_ids = set(
        db.scalars(
            select(StudentAchievement.achievement_id).where(
                StudentAchievement.student_id == student.id
            )
        )
    )
    granted: list[Achievement] = []
    now = dt.datetime.now(dt.UTC)

    for achievement in db.scalars(select(Achievement)):
        if achievement.id in earned_ids:
            continue
        if not _criteria_met(db, student, achievement.criteria or {}):
            continue
        db.add(
            StudentAchievement(
                student_id=student.id, achievement_id=achievement.id, earned_at=now
            )
        )
        if achievement.xp_reward:
            award_xp(db, student, achievement.xp_reward, "achievement",
                     {"achievement": achievement.slug})
        granted.append(achievement)

    return granted
