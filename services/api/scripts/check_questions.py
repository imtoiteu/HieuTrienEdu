"""Generate every variant of every authored question, in every language, without a database.

The loader already refuses to store a template that cannot generate, but it only finds out at
seed time — after a migration, against a real database, with the failure buried in a report of a
few hundred lines. This does the same check straight from the YAML, so an author gets the error
while the file is still open.

It also does something the loader does not: it compares the *answers* of the English and
Vietnamese variants at the same seed. A translated template is still a template, and a
mistranslated placeholder or a changed number would silently produce a question whose right
answer differs between languages.

    python scripts/check_questions.py [content_dir]
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.exercise_engine import (  # noqa: E402
    GenerationError,
    QuestionTemplate,
    generate_variant,
)

SEEDS = (1, 2, 17, 101, 999)


def _sidecar(subject_dir: Path) -> dict:
    """Merge every translation file for a subject into {kind: {slug: {locale: {...}}}}."""
    out: dict = {}
    i18n = subject_dir / "i18n"
    if not i18n.is_dir():
        return out
    for entry in sorted(i18n.iterdir()):
        locale = entry.stem if entry.is_file() else entry.name
        paths = [entry] if entry.is_file() and entry.suffix == ".yaml" else (
            sorted(entry.glob("*.yaml")) if entry.is_dir() else []
        )
        for path in paths:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for kind, entries in (data or {}).items():
                if not isinstance(entries, dict):
                    continue
                for slug, values in entries.items():
                    if isinstance(values, dict):
                        out.setdefault(kind, {}).setdefault(slug, {}).setdefault(
                            locale, {}
                        ).update(values)
    return out


def _merge_choice_labels(bucket: dict, base_options: dict) -> dict:
    """Mirror the loader: translated choices are labels only, merged onto the English ones."""
    labels = bucket.pop("choices", None)
    base = base_options.get("choices") or []
    if not labels or not base:
        return bucket
    merged = []
    for index, choice in enumerate(base):
        copy = dict(choice) if isinstance(choice, dict) else {"label": choice}
        if index < len(labels):
            copy["label"] = labels[index]
        merged.append(copy)
    options = dict(bucket.get("options") or {})
    options["choices"] = merged
    bucket["options"] = options
    return bucket


def main(content_dir: Path) -> int:
    errors: list[str] = []
    checked = pairs = 0

    for subject_dir in sorted(p for p in content_dir.iterdir() if p.is_dir()):
        sidecar = _sidecar(subject_dir)
        for path in sorted((subject_dir / "questions").glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            defaults = data.get("defaults") or {}
            for raw in data.get("questions") or []:
                merged = {**defaults, **raw}
                slug = merged.get("slug", "?")
                template = QuestionTemplate(
                    slug=slug,
                    question_type=merged.get("type") or merged.get("question_type"),
                    prompt=merged.get("prompt", ""),
                    variables=merged.get("variables") or {},
                    constraints=merged.get("constraints") or [],
                    answer_spec=merged.get("answer") or merged.get("answer_spec") or {},
                    options=merged.get("options") or {},
                    hints=merged.get("hints") or [],
                    solution=merged.get("solution") or [],
                    difficulty=merged.get("difficulty", 2),
                )
                checked += 1

                english = {}
                for seed in SEEDS:
                    try:
                        english[seed] = generate_variant(template, seed)
                    except GenerationError as exc:
                        errors.append(f"{path.name}: '{slug}' [en] seed {seed} — {exc}")

                translations = (sidecar.get("questions") or {}).get(slug) or {}
                for locale, values in translations.items():
                    bucket = _merge_choice_labels(dict(values), template.options)
                    localised = replace(
                        template,
                        prompt=bucket.get("prompt", template.prompt),
                        hints=bucket.get("hints", template.hints),
                        solution=bucket.get("solution", template.solution),
                        options={**template.options, **(bucket.get("options") or {})},
                    )
                    for seed in SEEDS:
                        try:
                            variant = generate_variant(localised, seed)
                        except GenerationError as exc:
                            errors.append(f"{path.name}: '{slug}' [{locale}] seed {seed} — {exc}")
                            continue
                        if seed not in english:
                            continue
                        pairs += 1
                        # The whole point of translating the template rather than the output:
                        # same seed, same numbers, same answer, different prose.
                        if variant.answer != english[seed].answer:
                            errors.append(
                                f"{path.name}: '{slug}' seed {seed} — answer differs between "
                                f"en ({english[seed].answer!r}) and {locale} "
                                f"({variant.answer!r})"
                            )
                        rendered = variant.rendered.get("prompt")
                        if rendered and rendered == english[seed].rendered.get("prompt"):
                            errors.append(
                                f"{path.name}: '{slug}' seed {seed} — {locale} prompt is "
                                f"identical to the English one"
                            )

    print(f"{checked} templates, {len(SEEDS)} seeds each, {pairs} en/translated answer pairs")
    for error in errors:
        print(f"  FAIL {error}")
    print("OK" if not errors else f"{len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[3] / "content"
    raise SystemExit(main(root))
