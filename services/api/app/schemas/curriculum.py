"""Curriculum, lesson and question-bank schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import QuestionType, ReviewStatus


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None = None
    difficulty: int
    position: int
    tags: list[str] = Field(default_factory=list)


class SkillDetail(SkillRead):
    topic_slug: str | None = None
    topic_title: str | None = None
    unit_title: str | None = None
    course_title: str | None = None
    subject_slug: str | None = None
    grade: int | None = None
    prerequisites: list[SkillRead] = Field(default_factory=list)
    unlocks: list[SkillRead] = Field(default_factory=list)
    related: list[SkillRead] = Field(default_factory=list)
    question_count: int = 0
    lesson_count: int = 0


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str | None = None
    position: int
    skills: list[SkillRead] = Field(default_factory=list)


class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str | None = None
    icon: str | None = None
    position: int
    topics: list[TopicRead] = Field(default_factory=list)


class CourseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    grade: int
    summary: str | None = None
    estimated_hours: int = 0
    unit_count: int = 0
    skill_count: int = 0
    lesson_count: int = 0


class CourseDetail(CourseSummary):
    description: str | None = None
    subject_slug: str | None = None
    subject_name: str | None = None
    units: list[UnitRead] = Field(default_factory=list)


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    courses: list[CourseSummary] = Field(default_factory=list)


class LessonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str | None = None
    estimated_minutes: int
    position: int
    objectives: list[str] = Field(default_factory=list)


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    provider: str
    external_id: str
    duration_seconds: int
    thumbnail_url: str | None = None
    chapters: list[dict[str, Any]] = Field(default_factory=list)
    captions: list[dict[str, Any]] = Field(default_factory=list)
    playback_url: str | None = None
    attribution: str | None = None


class LessonDetail(LessonSummary):
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    topic_slug: str | None = None
    topic_title: str | None = None
    skill_slug: str | None = None
    skill_name: str | None = None
    video: VideoRead | None = None
    attribution: str | None = None
    license: str | None = None
    # Student-specific, absent for anonymous callers.
    progress_percent: int | None = None
    completed: bool | None = None
    video_position_seconds: int | None = None


class LessonProgressUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)
    video_position_seconds: int = Field(default=0, ge=0)
    completed: bool = False


# --------------------------------------------------------------------------------------
# question bank (teacher/admin facing)
# --------------------------------------------------------------------------------------


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    skill_id: int
    subject_slug: str
    grade: int
    topic_slug: str
    question_type: QuestionType
    difficulty: int
    prompt: str
    variables: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    answer_spec: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    hints: list[dict[str, Any]] = Field(default_factory=list)
    solution: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: ReviewStatus
    is_parametric: bool
    generated_by_ai: bool
    source: str | None = None
    license: str | None = None
    attribution: str | None = None
    times_served: int = 0
    times_correct: int = 0
    success_rate: float | None = None


class QuestionCreate(BaseModel):
    slug: str | None = Field(default=None, max_length=200)
    skill_id: int
    question_type: QuestionType
    difficulty: int = Field(default=2, ge=1, le=5)
    prompt: str = Field(min_length=1)
    variables: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    answer_spec: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    hints: list[dict[str, Any]] = Field(default_factory=list)
    solution: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    estimated_seconds: int = Field(default=60, ge=5, le=3600)
    status: ReviewStatus = ReviewStatus.DRAFT
    source: str | None = None
    license: str | None = None
    attribution: str | None = None


class QuestionUpdate(BaseModel):
    question_type: QuestionType | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    prompt: str | None = None
    variables: dict[str, Any] | None = None
    constraints: list[str] | None = None
    answer_spec: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    hints: list[dict[str, Any]] | None = None
    solution: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    status: ReviewStatus | None = None


class QuestionPreview(BaseModel):
    """A generated variant, including the answer — teacher/admin only."""

    seed: int
    variable_values: dict[str, Any]
    rendered: dict[str, Any]
    answer: dict[str, Any]
    hints: list[dict[str, Any]]
    solution: list[dict[str, Any]]


class PaginatedQuestions(BaseModel):
    items: list[QuestionRead]
    total: int
    page: int
    page_size: int
