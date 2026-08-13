"""Validation for the typed content blocks a lesson is built from.

A lesson body is a JSON array, which means an authoring UI can reorder and nest it freely — but it
also means nothing stops a malformed block reaching a student's screen. This module is the gate:
every block that goes into a lesson is validated here first, so the renderer can trust its input.

Blocks are validated by *shape*, not by a strict closed schema. Unknown keys on a known block type
are preserved, because the frontend renderer ignores what it does not understand and a future
field should not require a coordinated backend release. An unknown block *type*, however, is
rejected — that is almost always a typo, and silently accepting it produces a lesson with an
invisible hole in it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

__all__ = [
    "BLOCK_TYPES",
    "LESSON_SECTIONS",
    "BlockValidationError",
    "normalise_blocks",
]


class BlockValidationError(ValueError):
    """Raised with a human-readable, block-indexed message."""


# The pedagogical grouping an admin drags blocks between. A block with no section is treated as
# theory, which is what the existing seeded lessons are.
LESSON_SECTIONS = ("theory", "examples", "practice", "homework", "materials")

# type -> required keys. Everything else on a block is optional and passed through untouched.
BLOCK_TYPES: dict[str, tuple[str, ...]] = {
    # prose and structure
    "heading": ("text",),
    "text": ("markdown",),
    "divider": (),
    "callout": ("text",),
    "summary": ("points",),
    # media
    "image": ("url",),
    "video": (),
    "audio": ("url",),
    "document": ("url",),
    "embed": ("url",),
    # mathematics
    "math": ("latex",),
    "example": ("steps",),
    "table": ("headers", "rows"),
    "interactive": ("widget",),
    "figure": ("shape",),
    # assessment
    "practice": (),
    "quiz": (),
    "homework": (),
}

_LIST_FIELDS = {"points", "steps", "headers", "rows", "question_ids", "items"}


class LessonBlock(BaseModel):
    """One block. Extra keys are kept — see the module docstring."""

    model_config = {"extra": "allow"}

    type: str
    section: str = "theory"
    id: str | None = None

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in BLOCK_TYPES:
            raise ValueError(
                f"Unknown block type “{value}”. Expected one of: {', '.join(sorted(BLOCK_TYPES))}"
            )
        return value

    @field_validator("section")
    @classmethod
    def _known_section(cls, value: str) -> str:
        if value not in LESSON_SECTIONS:
            raise ValueError(
                f"Unknown section “{value}”. Expected one of: {', '.join(LESSON_SECTIONS)}"
            )
        return value


class LessonBlocksIn(BaseModel):
    blocks: list[dict[str, Any]] = Field(default_factory=list)


def normalise_blocks(blocks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Validate and canonicalise a lesson body.

    Returns a new list where every block has a ``type``, a ``section`` and a stable ``id``. The id
    matters for the editor: React keys built from array indices make drag-and-drop reordering lose
    component state, and an id assigned server-side survives a round trip through the database.
    """
    if not blocks:
        return []

    result: list[dict[str, Any]] = []
    for index, raw in enumerate(blocks):
        if not isinstance(raw, dict):
            raise BlockValidationError(f"Block {index + 1} is not an object")

        try:
            parsed = LessonBlock.model_validate(raw)
        except ValidationError as exc:
            # Pull the message out of the structured error list. Parsing ``str(exc)`` is not an
            # option: pydantic's rendering ends with a documentation URL, so taking the last line
            # showed the author "For further information visit https://…" instead of what was
            # actually wrong with their block.
            first = exc.errors()[0]
            message = first.get("msg", "is invalid")
            message = message.removeprefix("Value error, ")
            raise BlockValidationError(f"Block {index + 1}: {message}") from exc

        block = dict(raw)
        block["type"] = parsed.type
        block["section"] = parsed.section
        block["id"] = parsed.id or f"b{index + 1}-{parsed.type}"

        for key in BLOCK_TYPES[parsed.type]:
            value = block.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise BlockValidationError(
                    f"Block {index + 1} ({parsed.type}) is missing “{key}”"
                )
            if key in _LIST_FIELDS and not isinstance(value, list):
                raise BlockValidationError(
                    f"Block {index + 1} ({parsed.type}): “{key}” must be a list"
                )

        # An assessment block has to point at *something*, otherwise it renders as a button that
        # does nothing — exactly the dead UI this system is meant to eliminate.
        if parsed.type in {"practice", "quiz", "homework"}:
            has_target = bool(
                block.get("skill")
                or block.get("skill_id")
                or block.get("question_ids")
                or block.get("assignment_id")
            )
            if not has_target:
                raise BlockValidationError(
                    f"Block {index + 1} ({parsed.type}) needs a skill or at least one question"
                )

        if parsed.type == "video" and not (block.get("url") or block.get("external_id")):
            raise BlockValidationError(
                f"Block {index + 1} (video) needs either a url or a provider external_id"
            )

        result.append(block)

    return result
