"""AI provider abstraction — **interfaces and plumbing only, by design**.

Per the project brief, AI Assist is architecture-only at this stage: the schema, interfaces and UI
are prepared so a model can be wired in later, but **no real model or API call is implemented or
tested here**. That is a deliberate deferral, not an oversight.

What exists:

* ``AIProvider`` — the interface every future provider implements.
* ``DisabledProvider`` — the default. Every call returns ``available=False`` with a clear reason,
  so the UI can render an honest "coming soon" state instead of a broken feature.
* ``EchoProvider`` — a deterministic offline stand-in used by tests to exercise the plumbing
  (request logging, review gating, error handling) without any network access. It is explicitly
  **not** an AI and never claims to be.
* ``AIRequest`` / ``AIResult`` — the transport types.
* Full audit logging into ``ai_interactions``.

What does **not** exist yet, and must be built in the later phase:

* Any call to a real model provider (OpenAI, Anthropic, or otherwise).
* Prompt templates tuned for pedagogy and age-appropriateness.
* Safety filtering / moderation on model output before a minor sees it.
* Cost controls and rate limiting.

The four planned features are sketched below as method signatures so the API surface and the
database schema are already correct when a provider is added.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AIInteraction

__all__ = [
    "AIProvider",
    "DisabledProvider",
    "EchoProvider",
    "AIRequest",
    "AIResult",
    "get_ai_provider",
    "log_interaction",
    "AI_FEATURES",
]

AI_FEATURES = {
    "tutor_hint": "Socratic hint that guides without revealing the answer",
    "explain_mistake": "Explain why a specific answer was wrong",
    "generate_questions": "Draft new questions for teacher review",
    "summarise_progress": "Plain-language progress summary for a parent",
}


@dataclass
class AIRequest:
    feature: str
    context: dict[str, Any] = field(default_factory=dict)
    prompt: str | None = None
    max_tokens: int = 600
    temperature: float = 0.4


@dataclass
class AIResult:
    available: bool
    content: str | None = None
    reason: str | None = None
    provider: str = "disabled"
    model: str | None = None
    requires_review: bool = True
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "content": self.content,
            "reason": self.reason,
            "provider": self.provider,
            "model": self.model,
            "requires_review": self.requires_review,
        }


class AIProvider(ABC):
    name: str = "abstract"

    @property
    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def complete(self, request: AIRequest) -> AIResult:
        ...

    # --- the four planned features -------------------------------------------------
    # Each delegates to complete() so a future provider implements one method, not five.

    def tutor_hint(self, *, question_prompt: str, student_answer: str,
                   skill_name: str) -> AIResult:
        return self.complete(
            AIRequest(
                feature="tutor_hint",
                context={
                    "question": question_prompt,
                    "student_answer": student_answer,
                    "skill": skill_name,
                },
            )
        )

    def explain_mistake(self, *, question_prompt: str, student_answer: str,
                        correct_answer: str) -> AIResult:
        return self.complete(
            AIRequest(
                feature="explain_mistake",
                context={
                    "question": question_prompt,
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                },
            )
        )

    def generate_questions(self, *, skill_name: str, grade: int, difficulty: int,
                           count: int, question_type: str) -> AIResult:
        return self.complete(
            AIRequest(
                feature="generate_questions",
                context={
                    "skill": skill_name, "grade": grade, "difficulty": difficulty,
                    "count": count, "question_type": question_type,
                },
            )
        )

    def summarise_progress(self, *, student_name: str, summary: dict[str, Any]) -> AIResult:
        return self.complete(
            AIRequest(
                feature="summarise_progress",
                context={"student": student_name, "summary": summary},
            )
        )


class DisabledProvider(AIProvider):
    """The default. Reports unavailability clearly instead of pretending."""

    name = "disabled"

    @property
    def is_available(self) -> bool:
        return False

    def complete(self, request: AIRequest) -> AIResult:
        return AIResult(
            available=False,
            provider=self.name,
            reason=(
                "AI Assist is not enabled. Model integration is deliberately deferred to a later "
                "phase; the interfaces, schema and UI are in place and ready for a provider."
            ),
        )


class EchoProvider(AIProvider):
    """Deterministic offline stand-in for testing the plumbing. **Not** an AI.

    It produces a fixed, obviously-templated string so that nothing it emits could be mistaken for
    real tutoring content, while still letting tests verify logging, review gating and error paths.
    """

    name = "echo"

    @property
    def is_available(self) -> bool:
        return True

    def complete(self, request: AIRequest) -> AIResult:
        described = ", ".join(f"{k}={v!r}" for k, v in sorted(request.context.items()))
        return AIResult(
            available=True,
            provider=self.name,
            model="echo-v0",
            content=(
                f"[ECHO STUB — not generated by a language model] "
                f"feature={request.feature}; context: {described}"
            ),
            requires_review=True,
            latency_ms=0,
        )


_PROVIDERS: dict[str, type[AIProvider]] = {
    "disabled": DisabledProvider,
    "echo": EchoProvider,
}


def get_ai_provider(name: str | None = None) -> AIProvider:
    """Resolve the configured provider.

    Unknown names resolve to ``DisabledProvider`` rather than raising: a typo in an environment
    variable should degrade the AI feature, not take down the API.
    """
    key = (name or settings.ai_provider or "disabled").lower()
    return _PROVIDERS.get(key, DisabledProvider)()


def log_interaction(
    db: Session,
    *,
    feature: str,
    result: AIResult,
    user_id: int | None = None,
    student_id: int | None = None,
    context: dict[str, Any] | None = None,
    prompt: str | None = None,
) -> AIInteraction:
    """Persist an audit record. Called for every AI invocation, successful or not."""
    interaction = AIInteraction(
        user_id=user_id,
        student_id=student_id,
        feature=feature,
        provider=result.provider,
        model=result.model,
        request_context=context or {},
        prompt=prompt,
        response=result.content,
        status="succeeded" if result.available else "not_configured",
        error=None if result.available else result.reason,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
    db.add(interaction)
    db.flush()
    return interaction


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
