"""Placeholder substitution for question prompts, hints and solutions.

Syntax is ``{{ expression }}``, optionally with a decimal count: ``{{ distance/time : 2 }}``.

**Why double braces and not ``str.format``?** Question text is full of LaTeX, and LaTeX is full of
single braces — ``\\frac{a}{b}`` would make ``str.format`` throw or, worse, silently misinterpret.
The regex below requires the placeholder body to contain no braces at all, which has a pleasant
side effect: in ``\\frac{{{distance}}}{{{time}}}`` the engine matches the *inner* ``{{distance}}``
and leaves the outer LaTeX braces intact, so authors can write nested LaTeX naturally.
"""

from __future__ import annotations

import re
from typing import Any

from app.exercise_engine.algebra import format_number
from app.exercise_engine.safe_eval import ExpressionError, evaluate

__all__ = ["render_template", "render_blocks", "TemplateError"]

_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


class TemplateError(ValueError):
    """Raised when a placeholder cannot be resolved."""


def _resolve(body: str, namespace: dict[str, Any]) -> str:
    decimals: int | None = None
    expression = body

    if ":" in body:
        expression, _, precision = body.rpartition(":")
        expression = expression.strip()
        precision = precision.strip()
        if precision.isdigit():
            decimals = int(precision)
        else:
            expression = body  # not a precision suffix after all; treat the whole thing as an expr

    # Fast path: a bare variable name needs no parsing.
    if expression in namespace:
        return format_number(namespace[expression], decimals)

    try:
        value = evaluate(expression, namespace)
    except ExpressionError as exc:
        raise TemplateError(f"Could not resolve placeholder {{{{{body}}}}}: {exc}") from exc
    return format_number(value, decimals)


def render_template(text: str | None, namespace: dict[str, Any]) -> str:
    """Substitute every ``{{ ... }}`` placeholder in ``text``."""
    if not text:
        return ""
    if not isinstance(text, str):
        return str(text)
    return _PLACEHOLDER.sub(lambda match: _resolve(match.group(1), namespace), text)


def render_value(value: Any, namespace: dict[str, Any]) -> Any:
    """Recursively render any strings inside a nested structure."""
    if isinstance(value, str):
        return render_template(value, namespace)
    if isinstance(value, list):
        return [render_value(item, namespace) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, namespace) for key, item in value.items()}
    return value


def render_blocks(blocks: list[dict[str, Any]] | None,
                  namespace: dict[str, Any]) -> list[dict[str, Any]]:
    """Render a list of hint or solution-step objects."""
    return [render_value(block, namespace) for block in (blocks or [])]
