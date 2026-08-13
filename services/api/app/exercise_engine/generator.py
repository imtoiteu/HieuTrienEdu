"""Turn a question template plus a seed into a concrete, student-facing question.

The output is split in two:

* ``rendered`` — everything the student may see. Safe to serialise over the API.
* ``answer``   — the correct answer. **Never** included in a student-facing response.

Keeping them in separate dictionaries (rather than one dict with a "don't send this key" rule)
means a mistake in a serialiser cannot leak the answer: the student schema simply has no field
for it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.exercise_engine.algebra import AlgebraError, format_number, parse_author_expression
from app.exercise_engine.distractors import build_choice_set, generate_numeric_distractors
from app.exercise_engine.safe_eval import ExpressionError, evaluate
from app.exercise_engine.sampling import SamplingError, sample_variables
from app.exercise_engine.templating import TemplateError, render_blocks, render_template
from app.models.enums import QuestionType

__all__ = ["GeneratedVariant", "GenerationError", "generate_variant", "QuestionTemplate"]


class GenerationError(RuntimeError):
    """Raised when a template cannot produce a valid variant."""


@dataclass
class QuestionTemplate:
    """The engine's view of a question — decoupled from SQLAlchemy so it is unit-testable."""

    slug: str
    question_type: str
    prompt: str
    variables: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    answer_spec: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    hints: list[dict[str, Any]] = field(default_factory=list)
    solution: list[dict[str, Any]] = field(default_factory=list)
    difficulty: int = 2

    @classmethod
    def from_model(cls, question: Any, locale: str = "en") -> QuestionTemplate:
        """Build a template from a ``Question`` row, in the requested language.

        Localising here rather than after generation is the whole point: the prompt, hints and
        solution are *templates* containing ``{{ placeholders }}``, so a Vietnamese question has
        to be chosen before the renderer substitutes the sampled values. Translating the rendered
        output instead would mean translating "What is 7 + 12?" for every draw.

        ``answer_spec`` is deliberately never localised — it is the machine-checkable answer, and
        a translated copy could silently disagree with the original. The one exception is
        ``unit``, which is a *label* shown next to the answer box ("thousand dong", "degrees")
        rather than part of the check, so a translation may override it.
        """
        from app.core.i18n import localise

        options = dict(question.options or {})
        localised_options = localise(question, "options", locale, default=None)
        if isinstance(localised_options, dict):
            # Merge so a translation supplying only ``choices`` keeps units, tolerances and the
            # rest of the machinery from the base row.
            options = {**options, **localised_options}

        answer_spec = dict(question.answer_spec or {})
        if isinstance(localised_options, dict) and localised_options.get("unit"):
            # The renderer reads ``answer_spec["unit"]`` first, so a translated unit has to be
            # copied here to take effect. Nothing else from the spec is touched.
            answer_spec["unit"] = localised_options["unit"]

        return cls(
            slug=question.slug,
            question_type=question.question_type,
            prompt=localise(question, "prompt", locale, default=""),
            variables=question.variables or {},
            constraints=question.constraints or [],
            answer_spec=answer_spec,
            options=options,
            hints=localise(question, "hints", locale, default=[]) or [],
            solution=localise(question, "solution", locale, default=[]) or [],
            difficulty=question.difficulty,
        )


@dataclass
class GeneratedVariant:
    seed: int
    variable_values: dict[str, Any]
    rendered: dict[str, Any]
    answer: dict[str, Any]
    hints: list[dict[str, Any]]
    solution: list[dict[str, Any]]


# --------------------------------------------------------------------------------------
# per-type builders
# --------------------------------------------------------------------------------------

def _compute_value(spec: dict[str, Any], namespace: dict[str, Any]) -> Any:
    """Resolve an answer's value from an ``expression`` or a literal ``value``."""
    if "expression" in spec:
        return evaluate(str(spec["expression"]), namespace)
    if "value" in spec:
        value = spec["value"]
        return render_template(value, namespace) if isinstance(value, str) else value
    raise GenerationError("answer_spec must provide either 'expression' or 'value'")


def _static_choices(
    raw_choices: list[Any], namespace: dict[str, Any], seed: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalise author-written choices into ``{id, label}`` plus the list of correct ids."""
    def _is_correct(raw: Any) -> bool:
        """Resolve a choice's ``correct`` flag, which may itself be a template.

        Authors write ``correct: "{{ a > b }}"`` so that which option is right depends on the
        sampled values. Without rendering first, any non-empty string would be truthy and every
        such choice would be marked correct.
        """
        if isinstance(raw, str):
            rendered = render_template(raw, namespace).strip().lower()
            return rendered in {"true", "1", "yes"}
        return bool(raw)

    entries: list[dict[str, Any]] = []
    for item in raw_choices:
        if isinstance(item, str):
            entries.append({"label": render_template(item, namespace), "is_correct": False})
        elif isinstance(item, dict):
            entries.append(
                {
                    "label": render_template(str(item.get("label", "")), namespace),
                    "is_correct": _is_correct(item.get("correct", item.get("is_correct", False))),
                    "explanation": render_template(item.get("explanation"), namespace) or None,
                }
            )
        else:
            raise GenerationError(f"Unsupported choice entry: {item!r}")

    random.Random(seed ^ 0x5EED).shuffle(entries)

    choices: list[dict[str, Any]] = []
    correct_ids: list[str] = []
    for index, entry in enumerate(entries):
        choice_id = chr(ord("a") + index)
        choice: dict[str, Any] = {"id": choice_id, "label": entry["label"]}
        if entry.get("explanation"):
            choice["explanation"] = entry["explanation"]
        choices.append(choice)
        if entry["is_correct"]:
            correct_ids.append(choice_id)
    return choices, correct_ids


def _build_multiple_choice(
    template: QuestionTemplate, namespace: dict[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_choices = template.options.get("choices")

    if raw_choices:
        choices, correct_ids = _static_choices(raw_choices, namespace, seed)
        if len(correct_ids) != 1:
            raise GenerationError(
                f"{template.slug}: multiple_choice needs exactly one correct choice, "
                f"found {len(correct_ids)}"
            )
        return {"choices": choices}, {"choice_id": correct_ids[0]}

    # Parametric path: compute the answer, then build wrong answers around it.
    spec = template.answer_spec
    correct_value = _compute_value(spec, namespace)
    decimals = spec.get("decimals")
    unit = spec.get("unit") or template.options.get("unit")

    distractor_values = generate_numeric_distractors(
        correct_value,
        namespace=namespace,
        answer_expression=str(spec.get("expression", "")) or None,
        authored=[str(d) for d in (template.options.get("distractors") or [])],
        count=int(template.options.get("choice_count", 4)) - 1,
        decimals=decimals,
        allow_negative=bool(template.options.get("allow_negative", True)),
        rng=random.Random(seed),
    )
    choices, correct_id = build_choice_set(
        correct_value,
        distractor_values,
        seed=seed,
        formatter=lambda v: format_number(v, decimals),
        unit=unit,
    )
    return {"choices": choices}, {"choice_id": correct_id, "value": correct_value}


def _build_multiple_select(
    template: QuestionTemplate, namespace: dict[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_choices = template.options.get("choices")
    if not raw_choices:
        raise GenerationError(f"{template.slug}: multiple_select requires options.choices")
    choices, correct_ids = _static_choices(raw_choices, namespace, seed)
    if not correct_ids:
        raise GenerationError(f"{template.slug}: multiple_select needs at least one correct choice")
    return {"choices": choices}, {"choice_ids": sorted(correct_ids)}


def _build_numeric(
    template: QuestionTemplate, namespace: dict[str, Any], _seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = template.answer_spec
    value = _compute_value(spec, namespace)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise GenerationError(f"{template.slug}: numeric answer did not evaluate to a number")

    decimals = spec.get("decimals")
    rendered = {
        "unit": spec.get("unit") or template.options.get("unit"),
        "placeholder": template.options.get("placeholder"),
        "decimals": decimals,
    }
    answer = {
        "value": round(float(value), decimals) if decimals is not None else float(value),
        # Relative tolerance by default so it scales with magnitude; absolute if the author asks.
        "tolerance": float(spec.get("tolerance", 1e-6)),
        "tolerance_mode": spec.get("tolerance_mode", "relative"),
        "unit": rendered["unit"],
        "decimals": decimals,
    }
    return rendered, answer


def _build_expression(
    template: QuestionTemplate, namespace: dict[str, Any], _seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = template.answer_spec
    expected = render_template(str(spec.get("expression", "")), namespace)
    if not expected:
        raise GenerationError(f"{template.slug}: expression answer_spec needs an 'expression'")
    try:
        parse_author_expression(expected)
    except AlgebraError as exc:
        raise GenerationError(f"{template.slug}: expected answer is not parseable: {exc}") from exc

    rendered = {
        "symbols": spec.get("symbols", []),
        "placeholder": template.options.get("placeholder", "e.g. 2x + 3"),
    }
    return rendered, {"expression": expected, "symbols": spec.get("symbols", [])}


def _build_fill_blank(
    template: QuestionTemplate, namespace: dict[str, Any], _seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_blanks = template.options.get("blanks")
    if not raw_blanks:
        raise GenerationError(f"{template.slug}: fill_blank requires options.blanks")

    blanks: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    for index, blank in enumerate(raw_blanks, start=1):
        blank_id = str(blank.get("id", index))
        kind = blank.get("type", "numeric")
        blanks.append(
            {
                "id": blank_id,
                "type": kind,
                "label": render_template(blank.get("label"), namespace) or None,
                "unit": blank.get("unit"),
            }
        )
        if "expression" in blank:
            value = evaluate(str(blank["expression"]), namespace)
        else:
            value = render_template(str(blank.get("answer", "")), namespace)
        answers.append(
            {
                "id": blank_id,
                "type": kind,
                "value": value,
                "tolerance": float(blank.get("tolerance", 1e-6)),
                "accepted": [render_template(a, namespace)
                             for a in (blank.get("accepted") or [])],
            }
        )
    return {"blanks": blanks}, {"blanks": answers}


def _build_true_false(
    template: QuestionTemplate, namespace: dict[str, Any], _seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    value = _compute_value(template.answer_spec, namespace)
    if isinstance(value, str):
        value = value.strip().lower() in {"true", "yes", "1", "t"}
    return {}, {"value": bool(value)}


def _build_matching(
    template: QuestionTemplate, namespace: dict[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    pairs = template.options.get("pairs")
    if not pairs:
        raise GenerationError(f"{template.slug}: matching requires options.pairs")

    left_items = []
    right_items = []
    mapping: dict[str, str] = {}
    for index, pair in enumerate(pairs):
        left_id = f"l{index + 1}"
        right_id = f"r{index + 1}"
        left_items.append({"id": left_id, "label": render_template(str(pair["left"]), namespace)})
        right_items.append(
            {"id": right_id, "label": render_template(str(pair["right"]), namespace)}
        )
        mapping[left_id] = right_id

    # Shuffle only the right column — shuffling both makes the question needlessly hard to read.
    random.Random(seed ^ 0xA11CE).shuffle(right_items)
    return {"left": left_items, "right": right_items}, {"mapping": mapping}


def _build_ordering(
    template: QuestionTemplate, namespace: dict[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    items = template.options.get("items")
    if not items:
        raise GenerationError(f"{template.slug}: ordering requires options.items")

    ordered = []
    for index, item in enumerate(items):
        label = item if isinstance(item, str) else str(item.get("label", ""))
        ordered.append({"id": f"i{index + 1}", "label": render_template(label, namespace)})

    correct_order = [entry["id"] for entry in ordered]
    shuffled = list(ordered)
    rng = random.Random(seed ^ 0x0DDE5)
    # Guarantee the presented order differs from the answer, otherwise the question is free.
    # A single-item list can never be reordered, so bail out rather than looping pointlessly.
    if len(shuffled) > 1:
        for _ in range(10):
            rng.shuffle(shuffled)
            if [entry["id"] for entry in shuffled] != correct_order:
                break
    return {"items": shuffled}, {"order": correct_order}


def _build_short_answer(
    template: QuestionTemplate, namespace: dict[str, Any], _seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = template.answer_spec
    accepted = [render_template(str(a), namespace) for a in (spec.get("accepted") or [])]
    if "expression" in spec or "value" in spec:
        accepted.insert(0, format_number(_compute_value(spec, namespace)))
    if not accepted:
        raise GenerationError(f"{template.slug}: short_answer needs 'accepted' answers")
    return (
        {"placeholder": template.options.get("placeholder")},
        {
            "accepted": accepted,
            "keywords": [render_template(str(k), namespace)
                         for k in (spec.get("keywords") or [])],
            "min_keywords": int(spec.get("min_keywords", 0)),
        },
    )


_BUILDERS = {
    QuestionType.MULTIPLE_CHOICE: _build_multiple_choice,
    QuestionType.MULTIPLE_SELECT: _build_multiple_select,
    QuestionType.NUMERIC: _build_numeric,
    QuestionType.EXPRESSION: _build_expression,
    QuestionType.FILL_BLANK: _build_fill_blank,
    QuestionType.TRUE_FALSE: _build_true_false,
    QuestionType.MATCHING: _build_matching,
    QuestionType.ORDERING: _build_ordering,
    QuestionType.SHORT_ANSWER: _build_short_answer,
}


def generate_variant(template: QuestionTemplate, seed: int) -> GeneratedVariant:
    """Render ``template`` with the variable draw determined by ``seed``."""
    try:
        question_type = QuestionType(template.question_type)
    except ValueError as exc:
        raise GenerationError(f"Unsupported question type: {template.question_type!r}") from exc

    builder = _BUILDERS[question_type]

    try:
        namespace = sample_variables(template.variables, template.constraints, seed=seed)
    except SamplingError as exc:
        raise GenerationError(f"{template.slug}: {exc}") from exc

    try:
        prompt = render_template(template.prompt, namespace)
        type_rendered, answer = builder(template, namespace, seed)
        hints = render_blocks(template.hints, namespace)
        solution = render_blocks(template.solution, namespace)
    except (TemplateError, ExpressionError, AlgebraError, KeyError) as exc:
        raise GenerationError(f"{template.slug}: {exc}") from exc

    rendered: dict[str, Any] = {
        "prompt": prompt,
        "question_type": template.question_type,
        "hint_count": len(hints),
        **type_rendered,
    }
    if template.options.get("image_url"):
        rendered["image_url"] = template.options["image_url"]
    if template.options.get("interactive"):
        rendered["interactive"] = template.options["interactive"]

    return GeneratedVariant(
        seed=seed,
        variable_values=namespace,
        rendered=rendered,
        answer=answer,
        hints=hints,
        solution=solution,
    )
