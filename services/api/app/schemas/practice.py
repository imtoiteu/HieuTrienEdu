"""Practice, progress and dashboard schemas."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StartSessionRequest(BaseModel):
    skill_id: int | None = None
    skill_slug: str | None = None
    target_questions: int = Field(default=5, ge=1, le=30)
    mode: str = Field(default="practice", max_length=30)
    assignment_id: int | None = None


class ServedQuestionRead(BaseModel):
    """The student-facing question payload.

    Deliberately has **no** field for the correct answer or the worked solution — those live in
    ``QuestionVariant.answer`` / ``.rendered_solution`` on the server and are only returned by the
    submit endpoint, after the student has committed to an answer.
    """

    variant_id: int
    question_id: int
    question_slug: str
    question_type: str
    difficulty: int
    estimated_seconds: int
    prompt: str
    skill: dict[str, Any]
    hints: list[dict[str, Any]] = Field(default_factory=list)
    hint_count: int = 0

    # Type-specific presentation payloads.
    choices: list[dict[str, Any]] | None = None
    blanks: list[dict[str, Any]] | None = None
    left: list[dict[str, Any]] | None = None
    right: list[dict[str, Any]] | None = None
    items: list[dict[str, Any]] | None = None
    unit: str | None = None
    placeholder: str | None = None
    decimals: int | None = None
    symbols: list[str] | None = None
    image_url: str | None = None
    interactive: dict[str, Any] | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    skill_id: int | None = None
    target_questions: int
    questions_answered: int
    questions_correct: int
    xp_earned: int
    mastery_before: float | None = None
    mastery_after: float | None = None
    completed_at: dt.datetime | None = None


class SubmitAnswerRequest(BaseModel):
    variant_id: int
    answer: dict[str, Any]
    hints_used: int = Field(default=0, ge=0, le=10)
    time_spent_seconds: int = Field(default=0, ge=0, le=7200)
    session_id: int | None = None


class MasteryChange(BaseModel):
    before: float
    after: float
    delta: float
    is_mastered: bool
    newly_mastered: bool


class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    score: float
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    correct_answer: str | None = None
    solution: list[dict[str, Any]] = Field(default_factory=list)
    mastery: MasteryChange
    gamification: dict[str, Any]
    session: SessionRead | None = None


class HintRead(BaseModel):
    index: int
    text: str
    is_last: bool


class RecommendationRead(BaseModel):
    skill_id: int
    skill_slug: str
    skill_name: str
    topic: str | None = None
    score: float
    reason: str
    detail: str
    mastery: float
    readiness: float
    difficulty: int


class PathNodeRead(BaseModel):
    skill_id: int
    skill_slug: str
    skill_name: str
    topic: str | None = None
    difficulty: int
    mastery: float
    status: str
    attempts: int
    blocked_by: list[str] = Field(default_factory=list)


class SubjectProgress(BaseModel):
    subject_slug: str
    subject_name: str
    color: str | None = None
    icon: str | None = None
    mastery_percent: int
    skills_tracked: int
    skills_mastered: int


class WeakSkillRead(BaseModel):
    skill_id: int
    skill_slug: str
    skill_name: str
    subject_slug: str | None = None
    mastery: float
    attempts: int
    accuracy: float | None = None


class UpcomingSession(BaseModel):
    id: int
    title: str
    class_name: str
    starts_at: dt.datetime
    ends_at: dt.datetime
    join_url: str | None = None
    provider: str
    teacher_name: str | None = None


class AssignmentSummary(BaseModel):
    id: int
    title: str
    due_at: dt.datetime | None = None
    status: str
    score_percent: float | None = None
    question_count: int = 0


class AchievementRead(BaseModel):
    slug: str
    name: str
    description: str
    icon: str
    tier: str
    earned_at: dt.datetime | None = None


class RecentAttemptRead(BaseModel):
    id: int
    skill_name: str
    is_correct: bool
    score: float
    created_at: dt.datetime


class DashboardResponse(BaseModel):
    student: dict[str, Any]
    overall_mastery_percent: int
    subjects: list[SubjectProgress] = Field(default_factory=list)
    recommendations: list[RecommendationRead] = Field(default_factory=list)
    weak_skills: list[WeakSkillRead] = Field(default_factory=list)
    recent_attempts: list[RecentAttemptRead] = Field(default_factory=list)
    upcoming_sessions: list[UpcomingSession] = Field(default_factory=list)
    assignments: list[AssignmentSummary] = Field(default_factory=list)
    achievements: list[AchievementRead] = Field(default_factory=list)
    enrolled_courses: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    activity: list[dict[str, Any]] = Field(default_factory=list)
