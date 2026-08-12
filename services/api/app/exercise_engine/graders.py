"""Answer evaluation.

Every grader is a pure function ``(answer, user_answer, rendered) -> GradeResult``. That shape is
borrowed from Perseus's ``perseus-score`` package, which keeps scoring completely separate from
rendering — the single best idea in that codebase, and the reason grading here can run on the
server with no UI involved.

Grading is **always** server-side. The client is never told the correct answer until after it has
submitted, so a student cannot read it out of the network tab.

Partial credit is awarded wherever a question has independently-checkable parts (multi-select,
matching, ordering, multi-blank), because "you got 3 of 4 pairs right" is far better feedback than
a flat wrong — and it gives the mastery model a more honest signal than a binary.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.exercise_engine.algebra import AlgebraError, expressions_equivalent, format_number
from app.models.enums import QuestionType

__all__ = ["GradeResult", "grade_answer", "parse_number"]

# A response is "correct" for mastery purposes at or above this score. Below it, partial credit
# still shows in the UI but BKT treats the attempt as incorrect.
CORRECTNESS_THRESHOLD = 0.999


@dataclass
class GradeResult:
    is_correct: bool
    score: float
    message: str = ""
    # Per-part breakdown for questions with multiple checkable pieces.
    details: list[dict[str, Any]] = field(default_factory=list)
    # Human-readable correct answer, attached only after grading.
    correct_answer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_correct": self.is_correct,
            "score": round(self.score, 4),
            "message": self.message,
            "details": self.details,
            "correct_answer": self.correct_answer,
        }


class AnswerFormatError(ValueError):
    """Raised when the submitted payload is not shaped the way the question type expects."""


# --------------------------------------------------------------------------------------
# input normalisation
# --------------------------------------------------------------------------------------

_NUMBER_CLEAN = re.compile(r"[\s ']")


def parse_number(raw: Any) -> float:
    """Parse a student's numeric input tolerantly but unambiguously.

    Handles the decimal-separator problem directly: Vietnamese convention writes 1.5 as "1,5" and
    one thousand as "1.000", which is the exact opposite of English. Rather than guessing from a
    locale header (which the student may not match), we disambiguate structurally:

    * both separators present -> the *last* one is the decimal separator
    * only commas, in groups of three -> thousands separators
    * a single comma otherwise -> decimal separator
    """
    if isinstance(raw, bool):
        raise AnswerFormatError("Expected a number")
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        raise AnswerFormatError("Expected a number")

    text = _NUMBER_CLEAN.sub("", raw.strip())
    if not text:
        raise AnswerFormatError("Answer is empty")

    text = text.replace("−", "-").replace("−", "-").replace("–", "-")

    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif has_comma:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", text):
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")

    # Fractions such as "3/4" are a legitimate way to write a numeric answer.
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                raise AnswerFormatError("Division by zero")
            return float(numerator) / denominator_value
        except ValueError as exc:
            raise AnswerFormatError(f"Could not read {raw!r} as a number") from exc

    # Percentages: "45%" -> 45, since questions asking for a percentage expect the number.
    text = text.rstrip("%")

    try:
        return float(text)
    except ValueError as exc:
        raise AnswerFormatError(f"Could not read {raw!r} as a number") from exc


def normalise_text(value: Any) -> str:
    """Casefold, strip accents-insensitively-safe whitespace, and collapse runs of spaces."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", " ", text)


def _within_tolerance(actual: float, expected: float, tolerance: float, mode: str) -> bool:
    if mode == "absolute":
        return abs(actual - expected) <= tolerance
    # Relative tolerance, with an absolute floor so answers near zero still work.
    return abs(actual - expected) <= max(tolerance * abs(expected), 1e-9)


# --------------------------------------------------------------------------------------
# graders
# --------------------------------------------------------------------------------------

def _grade_multiple_choice(answer, user, _rendered) -> GradeResult:
    chosen = user.get("choice_id")
    if not chosen:
        raise AnswerFormatError("Select an option before submitting")
    correct = answer.get("choice_id")
    is_correct = str(chosen) == str(correct)
    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message="Correct!" if is_correct else "Not quite — review the worked solution.",
        correct_answer=str(correct),
    )


def _grade_multiple_select(answer, user, _rendered) -> GradeResult:
    selected = user.get("choice_ids")
    if selected is None:
        raise AnswerFormatError("Select at least one option before submitting")
    if not isinstance(selected, list):
        raise AnswerFormatError("Expected a list of selected options")

    chosen = {str(c) for c in selected}
    expected = {str(c) for c in answer.get("choice_ids", [])}

    hits = len(chosen & expected)
    false_positives = len(chosen - expected)
    # Reward correct picks, penalise wrong ones, floor at zero. Without the penalty, selecting
    # every option would score 100%.
    score = 0.0 if not expected else max(0.0, (hits - false_positives) / len(expected))
    is_correct = chosen == expected

    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else min(score, 0.99),
        message=(
            "Correct!" if is_correct
            else f"You found {hits} of {len(expected)}"
                 + (f", with {false_positives} incorrect." if false_positives else ".")
        ),
        correct_answer=", ".join(sorted(expected)),
    )


def _grade_numeric(answer, user, _rendered) -> GradeResult:
    value = parse_number(user.get("value"))
    expected = float(answer["value"])
    tolerance = float(answer.get("tolerance", 1e-6))
    mode = answer.get("tolerance_mode", "relative")

    is_correct = _within_tolerance(value, expected, tolerance, mode)
    decimals = answer.get("decimals")
    display = format_number(expected, decimals)
    if answer.get("unit"):
        display = f"{display} {answer['unit']}"

    message = "Correct!"
    if not is_correct:
        # A factor-of-ten error is the single most common numeric mistake; naming it is more
        # useful than a generic "incorrect".
        if expected != 0 and abs(value / expected - 10) < 0.01:
            message = (
                "Close — your answer is ten times too large. "
                "Check your units or decimal point."
            )
        elif expected != 0 and abs(value / expected - 0.1) < 0.001:
            message = (
                "Close — your answer is ten times too small. "
                "Check your units or decimal point."
            )
        elif expected != 0 and abs(value + expected) < max(1e-9, tolerance * abs(expected)):
            message = "You have the right magnitude but the wrong sign."
        else:
            message = "Not quite — work through the solution steps."

    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message=message,
        correct_answer=display,
    )


def _grade_expression(answer, user, _rendered) -> GradeResult:
    raw = user.get("value")
    if raw is None or str(raw).strip() == "":
        raise AnswerFormatError("Enter an expression before submitting")
    expected = answer["expression"]
    try:
        is_correct = expressions_equivalent(str(raw), expected, symbols=answer.get("symbols"))
    except AlgebraError as exc:
        return GradeResult(
            is_correct=False,
            score=0.0,
            message=f"We could not read that expression: {exc}",
            correct_answer=expected,
        )
    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message="Correct — that is equivalent." if is_correct
        else "That expression is not equivalent to the answer.",
        correct_answer=expected,
    )


def _grade_one_blank(spec: dict[str, Any], raw: Any) -> bool:
    if spec.get("type") == "numeric":
        try:
            return _within_tolerance(
                parse_number(raw), float(spec["value"]),
                float(spec.get("tolerance", 1e-6)), "relative",
            )
        except (AnswerFormatError, TypeError, ValueError):
            return False
    if spec.get("type") == "expression":
        try:
            return expressions_equivalent(str(raw), str(spec["value"]))
        except AlgebraError:
            return False
    candidates = {normalise_text(spec.get("value"))}
    candidates.update(normalise_text(a) for a in spec.get("accepted", []))
    return normalise_text(raw) in candidates


def _grade_fill_blank(answer, user, _rendered) -> GradeResult:
    submitted = user.get("blanks")
    if not isinstance(submitted, dict):
        raise AnswerFormatError("Expected an object mapping blank ids to answers")

    specs = answer.get("blanks", [])
    details = []
    correct_count = 0
    for spec in specs:
        blank_id = str(spec["id"])
        ok = _grade_one_blank(spec, submitted.get(blank_id))
        correct_count += int(ok)
        details.append(
            {"id": blank_id, "is_correct": ok, "correct_answer": format_number(spec["value"])}
        )

    total = len(specs) or 1
    score = correct_count / total
    is_correct = correct_count == len(specs)
    return GradeResult(
        is_correct=is_correct,
        score=score,
        message="Correct!" if is_correct else f"{correct_count} of {len(specs)} blanks correct.",
        details=details,
        correct_answer="; ".join(f"{d['id']}: {d['correct_answer']}" for d in details),
    )


def _grade_true_false(answer, user, _rendered) -> GradeResult:
    raw = user.get("value")
    if isinstance(raw, str):
        raw = raw.strip().lower() in {"true", "yes", "1", "t"}
    if raw is None:
        raise AnswerFormatError("Choose True or False")
    is_correct = bool(raw) is bool(answer["value"])
    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message="Correct!" if is_correct else "Not quite.",
        correct_answer="True" if answer["value"] else "False",
    )


def _grade_matching(answer, user, _rendered) -> GradeResult:
    submitted = user.get("mapping")
    if not isinstance(submitted, dict):
        raise AnswerFormatError("Expected an object mapping left ids to right ids")

    expected: dict[str, str] = answer.get("mapping", {})
    details = []
    correct_count = 0
    for left_id, right_id in expected.items():
        ok = str(submitted.get(left_id)) == str(right_id)
        correct_count += int(ok)
        details.append({"id": left_id, "is_correct": ok, "correct_answer": right_id})

    total = len(expected) or 1
    is_correct = correct_count == len(expected)
    return GradeResult(
        is_correct=is_correct,
        score=correct_count / total,
        message="Correct!" if is_correct else f"{correct_count} of {len(expected)} pairs matched.",
        details=details,
    )


def _grade_ordering(answer, user, _rendered) -> GradeResult:
    submitted = user.get("order")
    if not isinstance(submitted, list):
        raise AnswerFormatError("Expected a list of item ids in order")

    expected: list[str] = [str(i) for i in answer.get("order", [])]
    given = [str(i) for i in submitted]
    is_correct = given == expected

    # Score by adjacent-pair agreement rather than exact-position matching: a student who has the
    # sequence right but shifted by one has understood the ordering, and position-matching would
    # score that zero.
    if len(expected) < 2:
        score = 1.0 if is_correct else 0.0
    else:
        expected_pairs = {(expected[i], expected[i + 1]) for i in range(len(expected) - 1)}
        given_pairs = {(given[i], given[i + 1]) for i in range(len(given) - 1)}
        score = len(expected_pairs & given_pairs) / len(expected_pairs)

    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else min(score, 0.99),
        message="Correct order!" if is_correct else "Not the right order yet.",
        correct_answer=" → ".join(expected),
    )


def _grade_short_answer(answer, user, _rendered) -> GradeResult:
    raw = user.get("value")
    if raw is None or str(raw).strip() == "":
        raise AnswerFormatError("Enter an answer before submitting")

    normalised = normalise_text(raw)
    accepted = {normalise_text(a) for a in answer.get("accepted", [])}
    if normalised in accepted:
        return GradeResult(True, 1.0, "Correct!",
                           correct_answer=next(iter(answer.get("accepted", [])), None))

    # Keyword mode: for explanation-style answers, award credit when the required ideas appear.
    keywords = [normalise_text(k) for k in answer.get("keywords", [])]
    minimum = int(answer.get("min_keywords", 0))
    if keywords and minimum:
        hits = sum(1 for keyword in keywords if keyword and keyword in normalised)
        score = min(1.0, hits / minimum) if minimum else 0.0
        is_correct = hits >= minimum
        return GradeResult(
            is_correct=is_correct,
            score=1.0 if is_correct else score * 0.99,
            message="Correct!" if is_correct
            else f"Mentioned {hits} of the {minimum} key ideas we were looking for.",
            correct_answer=next(iter(answer.get("accepted", [])), None),
        )

    return GradeResult(
        False, 0.0, "Not quite.",
        correct_answer=next(iter(answer.get("accepted", [])), None),
    )


_GRADERS = {
    QuestionType.MULTIPLE_CHOICE: _grade_multiple_choice,
    QuestionType.MULTIPLE_SELECT: _grade_multiple_select,
    QuestionType.NUMERIC: _grade_numeric,
    QuestionType.EXPRESSION: _grade_expression,
    QuestionType.FILL_BLANK: _grade_fill_blank,
    QuestionType.TRUE_FALSE: _grade_true_false,
    QuestionType.MATCHING: _grade_matching,
    QuestionType.ORDERING: _grade_ordering,
    QuestionType.SHORT_ANSWER: _grade_short_answer,
}


def grade_answer(
    question_type: str,
    answer: dict[str, Any],
    user_answer: dict[str, Any],
    rendered: dict[str, Any] | None = None,
) -> GradeResult:
    """Grade ``user_answer`` against the stored ``answer`` for a question of ``question_type``."""
    try:
        resolved_type = QuestionType(question_type)
    except ValueError as exc:
        raise AnswerFormatError(f"Unknown question type: {question_type!r}") from exc

    if not isinstance(user_answer, dict):
        raise AnswerFormatError("Answer payload must be an object")

    try:
        result = _GRADERS[resolved_type](answer, user_answer, rendered or {})
    except AnswerFormatError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise AnswerFormatError(f"Could not grade this answer: {exc}") from exc

    # Keep the "is_correct" flag and the score consistent — the mastery model reads is_correct,
    # and a mismatch between the two is the kind of bug that silently corrupts student data.
    result.is_correct = result.score >= CORRECTNESS_THRESHOLD
    return result
