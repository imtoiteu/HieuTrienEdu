"""Bilingual authoring for the admin API.

Administrators enter Vietnamese content *directly* — there is no runtime machine translation
anywhere in this system. Every admin write endpoint for a translatable model accepts an optional
``translations`` object alongside the English fields::

    {
      "title": "Mathematics — Grade 6",
      "translations": {"vi": {"title": "Toán học — Lớp 6", "summary": "…"}}
    }

and every admin read returns the same shape, so the editor can round-trip both languages in one
form. The English columns stay authoritative for ``/en``; ``i18n`` is what ``/vi`` reads.

Two rules are enforced here rather than left to the UI:

* **Only whitelisted fields per model.** ``TRANSLATABLE`` is the whitelist. It deliberately
  excludes anything that carries meaning beyond prose — a question's ``answer_spec``, a skill's
  BKT parameters, a course's ``grade``. A translation must never be able to change what counts as
  a correct answer.
* **Never ``en``.** English lives in the columns. Accepting ``translations.en`` would create a
  second, shadow copy that ``localise`` never reads — silently discarded edits.
"""

from __future__ import annotations

import copy
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.core.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, merge_translation
from app.models import (
    BlogPost,
    ClassGroup,
    ContentCategory,
    Course,
    Lesson,
    LiveSession,
    Question,
    Resource,
    SiteSetting,
    Skill,
    Subject,
    TeacherProfile,
    Testimonial,
    Topic,
    TutoringProduct,
    Unit,
)

__all__ = [
    "COPY_SUFFIX",
    "TRANSLATABLE",
    "TranslationsPayload",
    "apply_translations",
    "duplicate_translations",
    "read_translations",
]


# The marker "Duplicate" appends to a title. It is a word an administrator reads, so it needs a
# translation like any other: a Vietnamese course whose copy is called "Toán học — Lớp 6 (copy)"
# is the one English word on an otherwise Vietnamese screen.
COPY_SUFFIX: dict[str, str] = {"en": "(copy)", "vi": "(bản sao)"}


# Which fields of each model an administrator may translate. Anything absent is either structural
# (ids, positions, flags) or correctness-bearing (answers, BKT parameters) and stays single-valued.
TRANSLATABLE: dict[Any, tuple[str, ...]] = {
    # Category names label courses and fill the public navigation, so they are read by
    # visitors in both languages.
    ContentCategory: ("name", "description", "seo_title", "seo_description"),
    Subject: ("name", "description"),
    Course: ("title", "summary", "description", "seo_title", "seo_description"),
    Unit: ("title", "summary"),
    Topic: ("title", "summary"),
    Skill: ("name", "description"),
    # A lesson's translated body is drafted exactly like its English body: ``draft_blocks``
    # is the working copy the editor writes, ``blocks`` is what students read. Publishing
    # promotes one to the other per locale — see ``admin/lessons.py``.
    Lesson: ("title", "summary", "objectives", "blocks", "draft_blocks"),
    # ``options`` carries choice labels and the display unit. The loader merges translated choice
    # labels positionally onto the English choices so ``correct`` can never be overwritten; the
    # same merge runs below.
    Question: ("prompt", "hints", "solution", "options"),
    Resource: ("title", "description"),
    # Marketing content. An author's *name* is absent on purpose: a real person's name is the
    # same in every language, and translating it would be wrong rather than merely unnecessary.
    TutoringProduct: ("name", "tagline", "description", "features"),
    ClassGroup: ("name",),
    # What the next lesson is about, as a student and their parent read it on the schedule.
    LiveSession: ("title", "topic_summary"),
    Testimonial: ("quote", "author_role"),
    BlogPost: ("title", "excerpt", "body_markdown", "tags"),
    TeacherProfile: (
        "headline", "bio", "qualifications", "languages", "specializations",
        "teaching_philosophy", "teaching_style",
    ),
    # A setting's value is one JSON blob, translated whole.
    SiteSetting: ("value",),
}

TRANSLATABLE_LOCALES = tuple(code for code in SUPPORTED_LOCALES if code != DEFAULT_LOCALE)


class TranslationsPayload(BaseModel):
    """Mixin field for admin write schemas.

    ``None`` means "leave translations alone" — a PATCH that omits the key must not wipe the
    Vietnamese content. ``{}`` for a locale clears that locale.
    """

    translations: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Per-locale field overrides, e.g. {\"vi\": {\"title\": \"Toán học\"}}",
    )


def _merge_choice_labels(bucket: dict[str, Any], base_options: dict[str, Any]) -> dict[str, Any]:
    """Turn a list of translated choice labels into full choice dicts.

    The editor sends only the labels, in order. Copying the English choices and replacing the
    label means ``correct`` (and anything else on a choice) is carried over from the source of
    truth and cannot be edited through the translation form.
    """
    options = dict(bucket.get("options") or {})
    labels = options.get("choices")
    if not isinstance(labels, list) or not labels:
        return bucket
    base_choices = (base_options or {}).get("choices") or []
    if len(labels) != len(base_choices):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Expected {len(base_choices)} translated choice label(s) to match the English "
                f"choices, got {len(labels)}."
            ),
        )
    merged = []
    for label, base in zip(labels, base_choices, strict=True):
        choice = dict(base) if isinstance(base, dict) else {"label": base}
        choice["label"] = label
        merged.append(choice)
    options["choices"] = merged
    return {**bucket, "options": options}


def apply_translations(obj: Any, translations: dict[str, dict[str, Any]] | None) -> None:
    """Validate and write ``translations`` onto ``obj.i18n``.

    Rejects unknown locales and unknown fields with 422 rather than dropping them: a typo in the
    admin form must fail loudly, not silently leave a page in English.
    """
    if translations is None:
        return

    allowed = TRANSLATABLE.get(type(obj))
    if allowed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{type(obj).__name__} is not translatable.",
        )

    blob = dict(getattr(obj, "i18n", None) or {})
    for locale, values in translations.items():
        if locale == DEFAULT_LOCALE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "English is stored in the main fields, not in translations. "
                    "Edit the English fields directly."
                ),
            )
        if locale not in TRANSLATABLE_LOCALES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported locale “{locale}”. "
                    f"Supported: {', '.join(TRANSLATABLE_LOCALES)}."
                ),
            )
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot translate {', '.join(unknown)} on {type(obj).__name__.lower()}. "
                    f"Translatable fields: {', '.join(allowed)}."
                ),
            )
        bucket = dict(values)
        if isinstance(obj, Question) and "options" in bucket:
            bucket = _merge_choice_labels(bucket, obj.options or {})
        blob = merge_translation(blob, locale, bucket)
    obj.i18n = blob


def duplicate_translations(source: Any, *, suffix_field: str | None = None) -> dict[str, Any]:
    """The ``i18n`` blob a clone of ``source`` should start life with.

    Duplication builds the clone field by field, and every duplicate endpoint simply forgot this
    one: a copied course or lesson arrived with an empty ``i18n``, so it read as English on ``/vi``
    while the original was fine, and nothing in the admin explained why. Deep-copied because the
    blob is nested and the two rows must not end up sharing a dict.

    ``suffix_field`` marks the copy in each language it has, matching the English title.
    """
    blob = copy.deepcopy(getattr(source, "i18n", None) or {})
    if suffix_field:
        for locale, values in blob.items():
            title = (values or {}).get(suffix_field)
            if isinstance(title, str) and title.strip():
                marker = COPY_SUFFIX.get(locale, COPY_SUFFIX[DEFAULT_LOCALE])
                values[suffix_field] = f"{title} {marker}"
    return blob


def read_translations(obj: Any) -> dict[str, dict[str, Any]]:
    """The ``translations`` half of an admin read response.

    Choice translations go back out as a bare label list, mirroring what
    :func:`apply_translations` accepts, so the editor form is symmetric with the write payload.
    """
    blob = dict(getattr(obj, "i18n", None) or {})
    out: dict[str, dict[str, Any]] = {}
    for locale, values in blob.items():
        bucket = dict(values or {})
        options = bucket.get("options")
        if isinstance(options, dict) and isinstance(options.get("choices"), list):
            options = dict(options)
            options["choices"] = [
                choice.get("label") if isinstance(choice, dict) else choice
                for choice in options["choices"]
            ]
            bucket["options"] = options
        out[locale] = bucket
    return out
