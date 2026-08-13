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

from app.core.i18n import DEFAULT_LOCALE
from app.exercise_engine.algebra import AlgebraError, expressions_equivalent, format_number
from app.exercise_engine.feedback import render_feedback, render_format_error
from app.models.enums import QuestionType

__all__ = ["GradeResult", "grade_answer", "parse_number"]

# A response is "correct" for mastery purposes at or above this score. Below it, partial credit
# still shows in the UI but BKT treats the attempt as incorrect.
CORRECTNESS_THRESHOLD = 0.999


@dataclass
class GradeResult:
    """The outcome of grading one answer.

    ``message_key`` and ``message_params`` are what the grader actually decides; ``message`` is
    the English rendering, filled in automatically so every existing caller keeps working. Call
    :meth:`localised_message` to render it in the student's language.
    """

    is_correct: bool
    score: float
    message: str = ""
    # Per-part breakdown for questions with multiple checkable pieces.
    details: list[dict[str, Any]] = field(default_factory=list)
    # Human-readable correct answer, attached only after grading.
    correct_answer: str | None = None
    # Language-free description of the feedback, resolved to prose by ``feedback.py``.
    message_key: str | None = None
    message_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.message_key and not self.message:
            self.message = render_feedback(self.message_key, DEFAULT_LOCALE, self.message_params)

    def localised_message(self, locale: str) -> str:
        if not self.message_key:
            return self.message
        return render_feedback(self.message_key, locale, self.message_params)

    def as_dict(self, locale: str = DEFAULT_LOCALE) -> dict[str, Any]:
        # ``message_key``/``message_params`` ride along so a stored attempt can be re-rendered in
        # whichever language the reader wants, years after it was graded.
        return {
            "is_correct": self.is_correct,
            "score": round(self.score, 4),
            "message": self.localised_message(locale),
            "message_key": self.message_key,
            "message_params": self.message_params,
            "details": self.details,
            "correct_answer": self.correct_answer,
        }


class AnswerFormatError(ValueError):
    """Raised when the submitted payload is not shaped the way the question type expects.

    Carries a ``key`` so the API layer can show the student the message in their own language;
    the ``str()`` form stays English for logs and for callers that predate localisation.
    """

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(render_format_error(key, DEFAULT_LOCALE))


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
        raise AnswerFormatError("expected_a_number")
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        raise AnswerFormatError("expected_a_number")

    text = _NUMBER_CLEAN.sub("", raw.strip())
    if not text:
        raise AnswerFormatError("answer_is_empty")

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
                raise AnswerFormatError("division_by_zero")
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
        raise AnswerFormatError("select_an_option")
    correct = answer.get("choice_id")
    is_correct = str(chosen) == str(correct)
    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message_key="correct" if is_correct else "wrong_review_solution",
        correct_answer=str(correct),
    )


def _grade_multiple_select(answer, user, _rendered) -> GradeResult:
    selected = user.get("choice_ids")
    if selected is None:
        raise AnswerFormatError("select_at_least_one")
    if not isinstance(selected, list):
        raise AnswerFormatError("expected_option_list")

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
        message_key=(
            "correct" if is_correct
            else "found_some_with_errors" if false_positives
            else "found_some"
        ),
        message_params={"hits": hits, "total": len(expected), "wrong": false_positives},
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

    message_key = "correct"
    if not is_correct:
        # A factor-of-ten error is the single most common numeric mistake; naming it is more
        # useful than a generic "incorrect".
        if expected != 0 and abs(value / expected - 10) < 0.01:
            message_key = "ten_times_too_large"
        elif expected != 0 and abs(value / expected - 0.1) < 0.001:
            message_key = "ten_times_too_small"
        elif expected != 0 and abs(value + expected) < max(1e-9, tolerance * abs(expected)):
            message_key = "wrong_sign"
        else:
            message_key = "wrong_work_through_steps"

    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message_key=message_key,
        correct_answer=display,
    )


def _grade_expression(answer, user, _rendered) -> GradeResult:
    raw = user.get("value")
    if raw is None or str(raw).strip() == "":
        raise AnswerFormatError("enter_an_expression")
    expected = answer["expression"]
    try:
        is_correct = expressions_equivalent(str(raw), expected, symbols=answer.get("symbols"))
    except AlgebraError as exc:
        return GradeResult(
            is_correct=False,
            score=0.0,
            message_key="unreadable_expression",
            message_params={"error": str(exc)},
            correct_answer=expected,
        )
    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message_key="correct_equivalent" if is_correct else "not_equivalent",
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
        raise AnswerFormatError("expected_blank_map")

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
        message_key="correct" if is_correct else "blanks_correct",
        message_params={"correct": correct_count, "total": len(specs)},
        details=details,
        correct_answer="; ".join(f"{d['id']}: {d['correct_answer']}" for d in details),
    )


def _grade_true_false(answer, user, _rendered) -> GradeResult:
    raw = user.get("value")
    if isinstance(raw, str):
        raw = raw.strip().lower() in {"true", "yes", "1", "t"}
    if raw is None:
        raise AnswerFormatError("choose_true_or_false")
    is_correct = bool(raw) is bool(answer["value"])
    return GradeResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        message_key="correct" if is_correct else "wrong_generic",
        correct_answer="True" if answer["value"] else "False",
    )


def _grade_matching(answer, user, _rendered) -> GradeResult:
    submitted = user.get("mapping")
    if not isinstance(submitted, dict):
        raise AnswerFormatError("expected_matching_map")

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
        message_key="correct" if is_correct else "pairs_matched",
        message_params={"correct": correct_count, "total": len(expected)},
        details=details,
    )


def _grade_ordering(answer, user, _rendered) -> GradeResult:
    submitted = user.get("order")
    if not isinstance(submitted, list):
        raise AnswerFormatError("expected_order_list")

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
        message_key="correct_order" if is_correct else "wrong_order",
        correct_answer=" → ".join(expected),
    )


def _grade_short_answer(answer, user, _rendered) -> GradeResult:
    raw = user.get("value")
    if raw is None or str(raw).strip() == "":
        raise AnswerFormatError("enter_an_answer")

    normalised = normalise_text(raw)
    accepted = {normalise_text(a) for a in answer.get("accepted", [])}
    if normalised in accepted:
        return GradeResult(
            True, 1.0, message_key="correct",
            correct_answer=next(iter(answer.get("accepted", [])), None),
        )

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
            message_key="correct" if is_correct else "key_ideas_mentioned",
            message_params={"hits": hits, "total": minimum},
            correct_answer=next(iter(answer.get("accepted", [])), None),
        )

    return GradeResult(
        False, 0.0, message_key="wrong_generic",
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
        raise AnswerFormatError("answer_must_be_object")

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
