"""Distractor generation for multiple-choice questions.

A multiple-choice question is only as good as its wrong answers. Random noise around the correct
value teaches nothing — a student can eliminate it by estimation. Distractors that encode the
*mistakes students actually make* turn each question into a diagnostic: which option a student
picks tells you which misconception they hold.

Priority order:

1. **Author-supplied** ``distractors`` expressions — always preferred. An author writing
   ``time / distance`` for a speed question is encoding "inverted the formula", which is exactly
   the error we want to detect.
2. **Structural mistakes** derived from the answer expression — swapping the operands of a
   non-commutative operation, or using the inverse operation.
3. **Magnitude and arithmetic slips** — off-by-one, factor-of-ten, sign flip, doubling.

Category 3 is the weakest and is only used to top up a short list.
"""

from __future__ import annotations

import ast
import random
from typing import Any

from app.exercise_engine.algebra import format_number
from app.exercise_engine.safe_eval import ExpressionError, evaluate

__all__ = ["generate_numeric_distractors", "build_choice_set"]


def _swapped_operand_expressions(expression: str) -> list[str]:
    """Rewrite ``a / b`` as ``b / a`` and ``a - b`` as ``b - a`` — the classic reversal errors."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        return []

    body = tree.body
    if not isinstance(body, ast.BinOp) or not isinstance(body.op, (ast.Div, ast.Sub)):
        return []

    try:
        left = ast.unparse(body.left)
        right = ast.unparse(body.right)
    except (AttributeError, ValueError):
        return []

    symbol = "/" if isinstance(body.op, ast.Div) else "-"
    inverse = "*" if isinstance(body.op, ast.Div) else "+"
    return [f"({right}) {symbol} ({left})", f"({left}) {inverse} ({right})"]


def _perturbations(value: float) -> list[float]:
    """Plausible arithmetic slips, ordered from most to least pedagogically useful."""
    candidates: list[float] = []
    if value != 0:
        candidates.extend([value * 10, value / 10, value * 2, value / 2, -value])
    candidates.extend([value + 1, value - 1, value + 10, value - 10])
    return candidates


def _tidy(value: Any, decimals: int | None) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return None
    if decimals is not None:
        return round(float(value), decimals)
    if isinstance(value, float) and value == int(value) and abs(value) < 1e12:
        return int(value)
    return round(float(value), 4) if isinstance(value, float) else value


def generate_numeric_distractors(
    correct_value: Any,
    *,
    namespace: dict[str, Any],
    answer_expression: str | None = None,
    authored: list[str] | None = None,
    count: int = 3,
    decimals: int | None = None,
    allow_negative: bool = True,
    rng: random.Random | None = None,
) -> list[Any]:
    """Produce ``count`` distinct wrong answers for a numeric multiple-choice question."""
    rng = rng or random.Random(0)
    correct = _tidy(correct_value, decimals)
    seen: set[float] = {float(correct)} if correct is not None else set()
    results: list[Any] = []

    def offer(raw: Any) -> None:
        if len(results) >= count:
            return
        tidied = _tidy(raw, decimals)
        if tidied is None:
            return
        if not allow_negative and tidied < 0:
            return
        key = float(tidied)
        if key in seen:
            return
        seen.add(key)
        results.append(tidied)

    # 1. Author-supplied misconceptions.
    for expression in authored or []:
        try:
            offer(evaluate(str(expression), namespace))
        except ExpressionError:
            continue

    # 2. Structural mistakes inferred from the answer expression.
    if len(results) < count and answer_expression:
        for variant in _swapped_operand_expressions(answer_expression):
            try:
                offer(evaluate(variant, namespace))
            except ExpressionError:
                continue

    # 3. Magnitude / arithmetic slips, as a top-up.
    if len(results) < count and isinstance(correct, (int, float)):
        for candidate in _perturbations(float(correct)):
            offer(candidate)

    # 4. Last resort so we never return a short list and break the UI.
    guard = 0
    while len(results) < count and guard < 100:
        guard += 1
        base = float(correct) if isinstance(correct, (int, float)) and correct != 0 else 10.0
        offer(base * rng.uniform(0.3, 2.5))

    return results[:count]


def build_choice_set(
    correct: Any,
    distractors: list[Any],
    *,
    seed: int,
    formatter=format_number,
    unit: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Assemble shuffled, id-stamped choices and return ``(choices, correct_choice_id)``.

    The shuffle is seeded so a student who reloads sees the options in the same order — otherwise
    "the third one" changes meaning mid-question, which is confusing and looks broken.
    """
    entries = [{"value": correct, "is_correct": True}]
    entries.extend({"value": value, "is_correct": False} for value in distractors)

    random.Random(seed ^ 0x5EED).shuffle(entries)

    choices: list[dict[str, Any]] = []
    correct_id = ""
    for index, entry in enumerate(entries):
        choice_id = chr(ord("a") + index)
        label = formatter(entry["value"]) if not isinstance(entry["value"], str) \
            else entry["value"]
        if unit:
            label = f"{label} {unit}"
        choices.append({"id": choice_id, "label": label})
        if entry["is_correct"]:
            correct_id = choice_id

    return choices, correct_id
