"""Text helpers shared by every module that has to turn a human title into a URL.

The important one is ``slugify``. A naive ``[^a-z0-9]+ -> '-'`` implementation is actively wrong
for this platform: the content is Vietnamese, so "Thầy Hiếu" becomes "th-y-hi-u" — unreadable, and
worse, "Toán" and "Tuấn" both collapse toward the same shape, so distinct titles start colliding
on a unique index. Decomposing to NFD and dropping the combining marks gives "thay-hieu", which is
both readable and collision-free.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable

__all__ = ["slugify", "unique_slug"]

# đ/Đ is a distinct letter rather than d-plus-a-diacritic, so NFD leaves it untouched and it has
# to be mapped explicitly. Every other Vietnamese vowel is handled by the combining-mark strip.
_SPECIAL_CHARS = str.maketrans({"đ": "d", "Đ": "D", "ð": "d", "ß": "ss"})


def slugify(value: str, *, max_length: int = 120, fallback: str = "item") -> str:
    """Turn arbitrary text into a lowercase, hyphen-separated ASCII slug."""
    text = (value or "").translate(_SPECIAL_CHARS)
    # NFD splits "ế" into "e" + combining acute + combining circumflex; category "Mn" is exactly
    # those combining marks, so dropping it leaves the base letters intact.
    decomposed = unicodedata.normalize("NFD", text)
    ascii_text = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    ascii_text = unicodedata.normalize("NFC", ascii_text)

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    slug = slug[:max_length].strip("-")
    return slug or fallback


def unique_slug(
    value: str,
    exists: Callable[[str], bool],
    *,
    max_length: int = 120,
    fallback: str = "item",
    reserved: Iterable[str] = (),
) -> str:
    """Slugify ``value``, then append ``-2``, ``-3`` … until ``exists`` says it is free.

    Counting up is preferred over appending a timestamp: slugs are user-visible URLs, and
    "dai-so-lop-8-2" is a great deal more meaningful to an administrator than
    "dai-so-lop-8-1786636000".
    """
    taken = set(reserved)
    base = slugify(value, max_length=max_length, fallback=fallback)
    candidate = base
    suffix = 2
    while candidate in taken or exists(candidate):
        # Keep room for the numeric suffix so the result never exceeds the column width.
        trimmed = base[: max_length - len(str(suffix)) - 1].rstrip("-")
        candidate = f"{trimmed}-{suffix}"
        suffix += 1
    return candidate
