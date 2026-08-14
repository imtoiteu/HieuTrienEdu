"""Check that translated lesson blocks change prose and nothing else.

A lesson translation is a positional overlay: entry *i* replaces fields on block *i*. Prose
fields are meant to change. Everything else must not — and two of them are only carried along
because the overlay replaces a whole field at a time:

* ``example.steps`` is a list of ``{text, math}``. Translating ``text`` means resupplying the
  list, which means resupplying every ``math`` string. One typo there and a Vietnamese student
  sees a different formula from an English one.
* ``interactive.config`` holds plot ``expression`` values alongside the ``label`` and
  ``axisLabels`` that genuinely need translating. Same exposure.

So this asserts every non-prose value is byte-identical across locales, and that the overlay
length matches the block count (a short overlay silently leaves trailing blocks in English).

    python scripts/check_lesson_overlays.py [content_dir]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

PROSE = {"markdown", "title", "text", "prompt", "points", "headers", "rows", "caption", "label",
         "axisLabels", "summary", "objectives"}

# A `math` value is LaTeX, which is *mostly* language-neutral — but \text{...} inside it holds
# real prose ("wasted", "drag") that must be translated like any other. So maths is compared
# with the contents of every \text{} blanked out: the numbers, operators and symbols have to
# match exactly, the words inside \text{} are free to differ.
_TEXT_MACRO = re.compile(r"\\text\{[^{}]*\}")


def _maths_skeleton(value):
    return _TEXT_MACRO.sub(r"\\text{}", value) if isinstance(value, str) else value


def _sidecar_lessons(subject_dir: Path) -> dict:
    out: dict = {}
    i18n = subject_dir / "i18n"
    if not i18n.is_dir():
        return out
    paths = []
    for entry in sorted(i18n.iterdir()):
        if entry.is_file() and entry.suffix == ".yaml":
            paths.append((entry.stem, entry))
        elif entry.is_dir():
            paths += [(entry.name, p) for p in sorted(entry.glob("*.yaml"))]
    for locale, path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for slug, values in (data.get("lessons") or {}).items():
            out.setdefault(slug, {}).setdefault(locale, {}).update(values)
    return out


def _structural(node, path="") -> dict:
    """Flatten every value that is NOT prose, keyed by its path."""
    found = {}
    if isinstance(node, dict):
        for key, value in node.items():
            if key in PROSE:
                continue
            found.update(_structural(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.update(_structural(value, f"{path}[{index}]"))
    else:
        found[path] = _maths_skeleton(node) if path.endswith(".math") else node
    return found


def main(content_dir: Path) -> int:
    errors: list[str] = []
    checked = 0

    for subject_dir in sorted(p for p in content_dir.iterdir() if p.is_dir()):
        translations = _sidecar_lessons(subject_dir)
        for path in sorted((subject_dir / "lessons").glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for lesson in data.get("lessons") or []:
                slug = lesson["slug"]
                blocks = lesson.get("blocks") or []
                if not translations.get(slug):
                    errors.append(f"{slug}: no translation at all — the lesson stays English")
                    continue
                for locale, bucket in (translations.get(slug) or {}).items():
                    checked += 1
                    overlays = bucket.get("blocks")
                    if overlays is None:
                        errors.append(f"{slug} [{locale}]: no block overlay — body stays English")
                        continue
                    if len(overlays) != len(blocks):
                        errors.append(
                            f"{slug} [{locale}]: overlay has {len(overlays)} entries for "
                            f"{len(blocks)} blocks — the extra blocks stay English"
                        )
                        continue
                    for index, (block, overlay) in enumerate(zip(blocks, overlays, strict=True)):
                        if not overlay:
                            continue
                        merged = {**block, **overlay}
                        before, after = _structural(block), _structural(merged)
                        for key in sorted(set(before) | set(after)):
                            if before.get(key) != after.get(key):
                                errors.append(
                                    f"{slug} [{locale}] block {index} ({block.get('type')}): "
                                    f"non-prose value{key} changed — "
                                    f"{before.get(key)!r} -> {after.get(key)!r}"
                                )

    print(f"{checked} lesson/locale overlays checked")
    for error in errors:
        print(f"  FAIL {error}")
    print("OK" if not errors else f"{len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[3] / "content"
    raise SystemExit(main(root))
