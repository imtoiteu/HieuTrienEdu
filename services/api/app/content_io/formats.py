"""Converters between HieuTrienEducation question templates and interchange formats.

Supported today:

* **Moodle GIFT** — import and export. Covers multiple choice, true/false, numeric, short answer
  and matching, which is the great majority of GIFT in the wild.
* **IMS QTI 2.1** — import of the ``choiceInteraction`` and ``textEntryInteraction`` subset.
  Full QTI is a multi-month project; the limitation is documented rather than faked.
* **Khan Academy Perseus JSON** — mapping of the ``radio``, ``numeric-input`` and ``expression``
  widgets onto our schema.

Everything produced here is a **static** question (no ``variables``). Interchange formats have no
concept of parametric templates, so an imported question is one fixed item — which our engine
handles on the same code path.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import QuestionType

__all__ = [
    "ImportedQuestion",
    "parse_gift",
    "to_gift",
    "parse_qti",
    "parse_perseus_item",
    "ALLOWED_LICENSES",
    "LicenseError",
]

# Only content under these licences may be imported. Anything else is refused outright rather
# than imported with a note — an accidental licence violation is much harder to undo than an
# import that did not happen.
ALLOWED_LICENSES = {
    "CC-BY-4.0",
    "CC-BY-3.0",
    "CC-BY-SA-4.0",
    "CC-BY-SA-3.0",
    "CC0-1.0",
    "PUBLIC-DOMAIN",
    "PROPRIETARY",  # our own authored content
}


class LicenseError(ValueError):
    """Raised when content is offered under a licence we may not redistribute."""


@dataclass
class ImportedQuestion:
    """A question in our schema, ready to be written to the database."""

    prompt: str
    question_type: str
    answer_spec: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    hints: list[dict[str, str]] = field(default_factory=list)
    solution: list[dict[str, str]] = field(default_factory=list)
    difficulty: int = 2
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    license: str | None = None
    attribution: str | None = None
    external_id: str | None = None

    def validate_license(self) -> None:
        normalised = (self.license or "").upper().replace(" ", "-")
        if normalised not in ALLOWED_LICENSES:
            raise LicenseError(
                f"Refusing to import content licensed '{self.license}'. "
                f"Permitted: {', '.join(sorted(ALLOWED_LICENSES))}"
            )


# --------------------------------------------------------------------------------------
# Moodle GIFT
# --------------------------------------------------------------------------------------

_GIFT_COMMENT = re.compile(r"^//.*$", re.MULTILINE)
_GIFT_TITLE = re.compile(r"^::(?P<title>[^:]*)::")


def _unescape_gift(text: str) -> str:
    for escaped, plain in (("\\=", "="), ("\\~", "~"), ("\\#", "#"),
                           ("\\{", "{"), ("\\}", "}"), ("\\:", ":")):
        text = text.replace(escaped, plain)
    return text.strip()


def parse_gift(source: str, *, license: str = "CC-BY-4.0",
               attribution: str | None = None) -> list[ImportedQuestion]:
    """Parse a GIFT document into question templates.

    GIFT separates questions by blank lines and puts the answer block in braces:

        Which is prime? { ~9 =11 ~15 }
        The Earth is flat. {F}
        What is 2 + 2? {#4}
    """
    cleaned = _GIFT_COMMENT.sub("", source)
    questions: list[ImportedQuestion] = []

    for block in re.split(r"\n\s*\n", cleaned):
        block = block.strip()
        if not block or "{" not in block:
            continue

        title_match = _GIFT_TITLE.match(block)
        if title_match:
            block = block[title_match.end():].strip()

        stem, _, remainder = block.partition("{")
        answer_body, _, _tail = remainder.rpartition("}")
        prompt = _unescape_gift(stem)
        answer_body = answer_body.strip()

        question = _parse_gift_answer(prompt, answer_body)
        if question is None:
            continue
        question.license = license
        question.attribution = attribution
        question.source = "Moodle GIFT import"
        questions.append(question)

    return questions


def _parse_gift_answer(prompt: str, body: str) -> ImportedQuestion | None:
    if not body:
        # An empty brace pair is a GIFT "essay" question, which we have no equivalent for.
        return None

    # True / false
    if body.upper() in {"T", "TRUE", "F", "FALSE"}:
        return ImportedQuestion(
            prompt=prompt,
            question_type=QuestionType.TRUE_FALSE,
            answer_spec={"value": body.upper() in {"T", "TRUE"}},
        )

    # Numeric: {#4} or {#4:0.1}
    if body.startswith("#"):
        numeric = body[1:].strip()
        value, _, tolerance = numeric.partition(":")
        try:
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.NUMERIC,
                answer_spec={
                    "value": float(value),
                    "tolerance": float(tolerance) if tolerance else 1e-6,
                    "tolerance_mode": "absolute" if tolerance else "relative",
                },
            )
        except ValueError:
            return None

    # Matching: pairs of "=left -> right"
    if "->" in body:
        pairs = []
        for part in re.split(r"(?<!\\)=", body):
            part = part.strip()
            if "->" not in part:
                continue
            left, _, right = part.partition("->")
            pairs.append({"left": _unescape_gift(left), "right": _unescape_gift(right)})
        if len(pairs) < 2:
            return None
        return ImportedQuestion(
            prompt=prompt, question_type=QuestionType.MATCHING, options={"pairs": pairs}
        )

    # Multiple choice: "=correct ~wrong ~wrong", possibly with "#feedback"
    if "~" in body or body.startswith("="):
        # Walk the string keeping each marker with the text that follows it.
        choices: list[dict[str, Any]] = []
        for match in re.finditer(r"(?<!\\)([=~])([^=~]*)", body):
            marker, text = match.group(1), match.group(2)
            text, _, feedback = text.partition("#")
            label = _unescape_gift(text)
            if not label:
                continue
            entry: dict[str, Any] = {"label": label, "correct": marker == "="}
            if feedback.strip():
                entry["explanation"] = _unescape_gift(feedback)
            choices.append(entry)

        if not choices:
            return None

        correct_count = sum(1 for choice in choices if choice["correct"])
        if correct_count == 0:
            return None
        if len(choices) == 1 or (correct_count == len(choices)):
            # All answers correct means GIFT short answer, written as "=a =b".
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.SHORT_ANSWER,
                answer_spec={"accepted": [choice["label"] for choice in choices]},
            )
        return ImportedQuestion(
            prompt=prompt,
            question_type=QuestionType.MULTIPLE_CHOICE
            if correct_count == 1
            else QuestionType.MULTIPLE_SELECT,
            options={"choices": choices},
        )

    return None


def to_gift(question: Any) -> str:
    """Render one of our questions as GIFT. Parametric templates export their seed-1 variant."""
    from app.exercise_engine import QuestionTemplate, generate_variant

    variant = generate_variant(QuestionTemplate.from_model(question), seed=1)
    prompt = variant.rendered["prompt"].replace("=", "\\=").replace("~", "\\~")
    kind = question.question_type

    if kind == QuestionType.TRUE_FALSE:
        return f"::{question.slug}:: {prompt} {{{'T' if variant.answer['value'] else 'F'}}}"

    if kind == QuestionType.NUMERIC:
        tolerance = variant.answer.get("tolerance", 0)
        return f"::{question.slug}:: {prompt} {{#{variant.answer['value']}:{tolerance}}}"

    if kind in {QuestionType.MULTIPLE_CHOICE, QuestionType.MULTIPLE_SELECT}:
        correct = (
            {variant.answer.get("choice_id")}
            if kind == QuestionType.MULTIPLE_CHOICE
            else set(variant.answer.get("choice_ids", []))
        )
        parts = [
            f"{'=' if choice['id'] in correct else '~'}{choice['label']}"
            for choice in variant.rendered.get("choices", [])
        ]
        return f"::{question.slug}:: {prompt} {{ {' '.join(parts)} }}"

    if kind == QuestionType.SHORT_ANSWER:
        accepted = variant.answer.get("accepted", [])
        return f"::{question.slug}:: {prompt} {{ {' '.join('=' + a for a in accepted)} }}"

    if kind == QuestionType.MATCHING:
        mapping = variant.answer.get("mapping", {})
        rights = {item["id"]: item["label"] for item in variant.rendered.get("right", [])}
        parts = [
            f"={left['label']} -> {rights.get(mapping.get(left['id']), '')}"
            for left in variant.rendered.get("left", [])
        ]
        return f"::{question.slug}:: {prompt} {{ {' '.join(parts)} }}"

    # Ordering, fill-blank and expression have no faithful GIFT representation.
    raise ValueError(f"{kind} cannot be represented in GIFT")


# --------------------------------------------------------------------------------------
# IMS QTI 2.1 (partial)
# --------------------------------------------------------------------------------------

_QTI_NS = {"qti": "http://www.imsglobal.org/xsd/imsqti_v2p1"}


def _qti_text(element: ET.Element | None) -> str:
    """Flatten an element's text content, ignoring markup."""
    if element is None:
        return ""
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def parse_qti(xml_source: str, *, license: str = "CC-BY-4.0",
              attribution: str | None = None) -> ImportedQuestion | None:
    """Parse a single QTI 2.1 assessment item.

    **Partial support**: ``choiceInteraction`` (single and multiple response) and
    ``textEntryInteraction``. Anything else returns None rather than being silently mangled.
    """
    try:
        root = ET.fromstring(xml_source)
    except ET.ParseError:
        return None

    def find(path: str) -> ET.Element | None:
        found = root.find(path, _QTI_NS)
        if found is None:
            # Many exports omit the namespace; fall back to a namespace-agnostic search.
            found = root.find(path.replace("qti:", ""))
        return found

    def findall(path: str) -> list[ET.Element]:
        found = root.findall(path, _QTI_NS)
        return found or root.findall(path.replace("qti:", ""))

    identifier = root.get("identifier")

    # `is None` rather than `or`: an ElementTree Element with no child elements is *falsy*, so
    # `find(a) or find(b)` silently discards a perfectly good <p>text</p> and falls through.
    prompt_element = find(".//qti:itemBody/qti:p")
    if prompt_element is None:
        prompt_element = find(".//qti:prompt")

    body = find(".//qti:itemBody")
    prompt = _qti_text(prompt_element) or _qti_text(body)

    # Correct responses, keyed by response identifier.
    correct_values: list[str] = [
        _qti_text(value)
        for value in findall(".//qti:responseDeclaration/qti:correctResponse/qti:value")
    ]
    if not correct_values:
        return None

    choice_interaction = find(".//qti:choiceInteraction")
    if choice_interaction is not None:
        choices = []
        for choice in choice_interaction.findall("qti:simpleChoice", _QTI_NS) or \
                choice_interaction.findall("simpleChoice"):
            choices.append(
                {
                    "label": _qti_text(choice),
                    "correct": choice.get("identifier") in correct_values,
                }
            )
        if not choices or not any(choice["correct"] for choice in choices):
            return None

        max_choices = choice_interaction.get("maxChoices", "1")
        multiple = max_choices != "1" or len(correct_values) > 1
        return ImportedQuestion(
            prompt=prompt,
            question_type=QuestionType.MULTIPLE_SELECT
            if multiple
            else QuestionType.MULTIPLE_CHOICE,
            options={"choices": choices},
            license=license,
            attribution=attribution,
            source="IMS QTI import",
            external_id=identifier,
        )

    if find(".//qti:textEntryInteraction") is not None:
        first = correct_values[0]
        try:
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.NUMERIC,
                answer_spec={"value": float(first), "tolerance": 1e-6},
                license=license,
                attribution=attribution,
                source="IMS QTI import",
                external_id=identifier,
            )
        except ValueError:
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.SHORT_ANSWER,
                answer_spec={"accepted": correct_values},
                license=license,
                attribution=attribution,
                source="IMS QTI import",
                external_id=identifier,
            )

    return None


# --------------------------------------------------------------------------------------
# Khan Academy Perseus
# --------------------------------------------------------------------------------------

_PERSEUS_WIDGET = re.compile(r"\[\[\s*☃\s*([a-zA-Z0-9\- ]+)\s*\]\]")


def parse_perseus_item(item: dict[str, Any], *, license: str = "CC-BY-SA-4.0",
                       attribution: str | None = None) -> ImportedQuestion | None:
    """Map a Perseus item onto our schema.

    Supports ``radio``, ``numeric-input`` and ``expression`` widgets — the three that carry the
    overwhelming majority of Perseus content. Interactive graph widgets have no equivalent here
    and are skipped rather than approximated.

    Perseus is MIT-licensed *code*; the content is separate and typically CC BY-SA, hence the
    default. Callers must pass the licence that actually applies to the item they hold.
    """
    question = item.get("question") or {}
    content = str(question.get("content", ""))
    widgets = question.get("widgets") or {}

    prompt = _PERSEUS_WIDGET.sub("", content).strip()
    hints = [
        {"text": _PERSEUS_WIDGET.sub("", str(hint.get("content", ""))).strip()}
        for hint in (item.get("hints") or [])
        if str(hint.get("content", "")).strip()
    ]

    for widget in widgets.values():
        widget_type = widget.get("type")
        options = widget.get("options") or {}

        if widget_type == "radio":
            choices = [
                {"label": str(choice.get("content", "")), "correct": bool(choice.get("correct"))}
                for choice in options.get("choices", [])
                if str(choice.get("content", "")).strip()
            ]
            if not choices or not any(choice["correct"] for choice in choices):
                continue
            multiple = sum(1 for choice in choices if choice["correct"]) > 1
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.MULTIPLE_SELECT if multiple
                else QuestionType.MULTIPLE_CHOICE,
                options={"choices": choices},
                hints=hints,
                license=license,
                attribution=attribution,
                source="Khan Academy Perseus import",
            )

        if widget_type == "numeric-input":
            answers = options.get("answers") or []
            correct = next((a for a in answers if a.get("status") == "correct"), None)
            if correct is None or correct.get("value") is None:
                continue
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.NUMERIC,
                answer_spec={
                    "value": float(correct["value"]),
                    "tolerance": float(correct.get("maxError") or 1e-6),
                    "tolerance_mode": "absolute" if correct.get("maxError") else "relative",
                },
                hints=hints,
                license=license,
                attribution=attribution,
                source="Khan Academy Perseus import",
            )

        if widget_type == "expression":
            answers = options.get("answerForms") or []
            correct = next((a for a in answers if a.get("considered") == "correct"), None)
            if correct is None or not correct.get("value"):
                continue
            return ImportedQuestion(
                prompt=prompt,
                question_type=QuestionType.EXPRESSION,
                answer_spec={"expression": str(correct["value"])},
                hints=hints,
                license=license,
                attribution=attribution,
                source="Khan Academy Perseus import",
            )

    return None
