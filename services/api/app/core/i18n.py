"""Content localisation.

The platform teaches Vietnamese students, so Vietnamese is the language that matters most — but
the authored source content is English and must keep working. Rather than duplicate every row per
language, each content model carries one ``i18n`` JSON column holding the translations::

    {"vi": {"title": "Toán học — Lớp 6", "summary": "…"}}

Why a JSON column rather than ``title_vi``/``summary_vi`` columns or a translations table:

* A third language, or a newly translatable field, is a data change rather than a migration. The
  set of translatable fields differs per model (a question has ``prompt``, ``hints``, ``solution``
  and ``options``; a course has ``title``, ``summary``, ``description``) and would otherwise mean
  a wide, mostly-null schema.
* Translations are always read together with their row and never queried on their own, so the one
  thing a join table would buy — indexing translated text — is not needed here.

Reads go through :func:`localise`, which falls back to the English column whenever a translation
is missing. That fallback is the reason ``/en`` cannot break and a half-translated ``/vi`` degrades
to readable English rather than to blank fields.
"""

from __future__ import annotations

from typing import Any, TypeVar

__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "localise",
    "localise_many",
    "merge_translation",
    "normalise_locale",
    "set_translation",
]

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "vi")

T = TypeVar("T")


def normalise_locale(value: str | None) -> str:
    """Reduce an arbitrary locale string to one we support.

    Accepts the regional forms a browser sends (``vi-VN``) as well as bare codes, and falls back
    to English for anything unrecognised so a malformed header can never blank a page.
    """
    if not value:
        return DEFAULT_LOCALE
    code = value.strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LOCALES else DEFAULT_LOCALE


def localise(obj: Any, field: str, locale: str, default: T = None) -> Any | T:
    """Read ``field`` from ``obj`` in ``locale``, falling back to the base column.

    A translation counts only if it is actually present *and* non-empty: an empty string or list
    in the ``i18n`` blob means "not translated yet", not "deliberately blank", and showing nothing
    would be worse than showing the English.
    """
    if obj is None:
        return default

    if locale != DEFAULT_LOCALE:
        translations = getattr(obj, "i18n", None) or {}
        bucket = translations.get(locale) or {}
        if field in bucket:
            value = bucket[field]
            if value not in (None, "", [], {}):
                return value

    value = getattr(obj, field, None)
    return default if value is None else value


def localise_many(obj: Any, fields: tuple[str, ...], locale: str) -> dict[str, Any]:
    """Localise several fields at once. Convenience for building a response dict."""
    return {field: localise(obj, field, locale) for field in fields}


def merge_translation(
    blob: dict[str, Any] | None, locale: str, values: dict[str, Any]
) -> dict[str, Any]:
    """Merge ``values`` into an ``i18n`` blob for ``locale`` and return the new blob.

    Returns a *new* dict rather than mutating in place: SQLAlchemy tracks JSON columns by
    identity, so mutating the existing dict would not mark the row dirty and the change would
    silently never be written.

    A ``None`` value removes that field, and a locale left with no fields is dropped entirely —
    so clearing a translation leaves ``{}`` rather than ``{"vi": {}}``, and ``localise`` falls
    straight back to English.
    """
    existing = dict(blob or {})
    bucket = dict(existing.get(locale) or {})
    for key, value in values.items():
        if value is None:
            bucket.pop(key, None)
        else:
            bucket[key] = value
    if bucket:
        existing[locale] = bucket
    else:
        existing.pop(locale, None)
    return existing


def set_translation(obj: Any, locale: str, values: dict[str, Any]) -> dict[str, Any]:
    """Merge ``values`` into ``obj``'s translations for ``locale`` and return the new blob."""
    return merge_translation(getattr(obj, "i18n", None), locale, values)
