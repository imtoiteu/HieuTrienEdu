"""Adaptive learning: Bayesian Knowledge Tracing and the recommendation engine."""

from app.adaptive.bkt import (
    MASTERY_THRESHOLD,
    STRUGGLING_THRESHOLD,
    BKTParameters,
    BKTUpdate,
    decay_mastery,
    effective_guess_probability,
    update_mastery,
)
from app.adaptive.recommender import (
    PREREQUISITE_GATE,
    Recommendation,
    SkillStatus,
    build_learning_path,
    recommend_next,
)

__all__ = [
    "BKTParameters",
    "BKTUpdate",
    "MASTERY_THRESHOLD",
    "PREREQUISITE_GATE",
    "Recommendation",
    "STRUGGLING_THRESHOLD",
    "SkillStatus",
    "build_learning_path",
    "decay_mastery",
    "effective_guess_probability",
    "recommend_next",
    "update_mastery",
]
