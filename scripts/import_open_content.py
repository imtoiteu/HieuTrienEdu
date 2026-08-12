#!/usr/bin/env python3
"""Import openly-licensed question content into the HieuTrienEducation question bank.

    python scripts/import_open_content.py --format gift --file questions.txt \
        --skill math-7-two-step-equations --license CC-BY-4.0 \
        --attribution "Example Author, CC BY 4.0"

    python scripts/import_open_content.py --format qti --dir ./qti-items \
        --skill physics-8-ohms-law --license CC-BY-4.0 --dry-run

Supported formats: ``gift``, ``qti``, ``perseus``. See docs/QUESTION_ENGINE.md for the coverage
of each.

**Licence enforcement is not advisory.** Content offered under a licence outside the allowlist is
refused, and `--license` is required, because a file that does not state its licence is a file we
cannot legally redistribute. Imported rows keep their `source`, `license` and `attribution`.

Nothing is imported by default: this script exists so the operator can bring in content they have
established the rights to, not so the repository can ship someone else's material.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from sqlalchemy import select  # noqa: E402

from app.content_io.formats import (  # noqa: E402
    ALLOWED_LICENSES,
    ImportedQuestion,
    LicenseError,
    parse_gift,
    parse_perseus_item,
    parse_qti,
)
from app.core.db import SessionLocal  # noqa: E402
from app.exercise_engine import (  # noqa: E402
    GenerationError,
    QuestionTemplate,
    generate_variant,
)
from app.models import Question, ReviewStatus, Skill  # noqa: E402


def slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:120]
    return slug or fallback


def collect(args: argparse.Namespace) -> list[ImportedQuestion]:
    paths: list[Path] = []
    if args.file:
        paths.append(Path(args.file))
    if args.dir:
        pattern = {"gift": "*.txt", "qti": "*.xml", "perseus": "*.json"}[args.format]
        paths.extend(sorted(Path(args.dir).glob(pattern)))

    if not paths:
        raise SystemExit("Nothing to import: pass --file or --dir")

    questions: list[ImportedQuestion] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        if args.format == "gift":
            questions.extend(
                parse_gift(source, license=args.license, attribution=args.attribution)
            )
        elif args.format == "qti":
            parsed = parse_qti(source, license=args.license, attribution=args.attribution)
            if parsed is None:
                print(f"  skipped (unsupported QTI interaction): {path.name}", file=sys.stderr)
            else:
                questions.append(parsed)
        else:
            payload = json.loads(source)
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                parsed = parse_perseus_item(
                    item, license=args.license, attribution=args.attribution
                )
                if parsed is None:
                    print(f"  skipped (unsupported widget): {path.name}", file=sys.stderr)
                else:
                    questions.append(parsed)
    return questions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", required=True, choices=["gift", "qti", "perseus"])
    parser.add_argument("--file", help="a single file to import")
    parser.add_argument("--dir", help="a directory of files to import")
    parser.add_argument("--skill", required=True, help="slug of the skill to attach questions to")
    parser.add_argument(
        "--license",
        required=True,
        help=f"licence of the content. One of: {', '.join(sorted(ALLOWED_LICENSES))}",
    )
    parser.add_argument("--attribution", help="attribution text to store on every question")
    parser.add_argument("--difficulty", type=int, default=2, choices=range(1, 6))
    parser.add_argument(
        "--publish",
        action="store_true",
        help="publish immediately instead of importing as pending_review",
    )
    parser.add_argument("--dry-run", action="store_true", help="parse and validate, write nothing")
    args = parser.parse_args()

    questions = collect(args)
    print(f"Parsed {len(questions)} questions from {args.format.upper()}.")
    if not questions:
        return 1

    # Refuse the whole batch on a licence problem rather than importing part of it.
    for question in questions:
        try:
            question.validate_license()
        except LicenseError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    db = SessionLocal()
    try:
        skill = db.scalar(select(Skill).where(Skill.slug == args.skill))
        if skill is None:
            print(f"ERROR: no skill with slug '{args.skill}'", file=sys.stderr)
            return 2

        course = skill.topic.unit.course
        subject_slug = course.subject.slug if course.subject else ""

        imported = 0
        skipped = 0
        for index, question in enumerate(questions, start=1):
            template = QuestionTemplate(
                slug="pending",
                question_type=question.question_type,
                prompt=question.prompt,
                answer_spec=question.answer_spec,
                options=question.options,
                hints=question.hints,
                solution=question.solution,
                difficulty=args.difficulty,
            )
            # Never write a template that cannot generate — it would become a 500 in front of a
            # student mid-session.
            try:
                generate_variant(template, seed=1)
            except GenerationError as exc:
                print(f"  skipped (invalid): {question.prompt[:60]}… — {exc}", file=sys.stderr)
                skipped += 1
                continue

            slug = f"{args.skill}-import-{slugify(question.prompt[:40], str(index))}"
            if db.scalar(select(Question).where(Question.slug == slug)) is not None:
                print(f"  skipped (already imported): {slug}", file=sys.stderr)
                skipped += 1
                continue

            if not args.dry_run:
                db.add(
                    Question(
                        slug=slug,
                        skill_id=skill.id,
                        subject_slug=subject_slug,
                        grade=course.grade,
                        topic_slug=skill.topic.slug,
                        question_type=question.question_type,
                        difficulty=args.difficulty,
                        prompt=question.prompt,
                        answer_spec=question.answer_spec,
                        options=question.options,
                        hints=question.hints,
                        solution=question.solution,
                        tags=question.tags,
                        # Imported content lands as pending_review unless explicitly published,
                        # so a human sees it before a student does.
                        status=ReviewStatus.PUBLISHED if args.publish
                        else ReviewStatus.PENDING_REVIEW,
                        is_parametric=False,
                        source=question.source,
                        license=question.license,
                        attribution=question.attribution,
                    )
                )
            imported += 1

        if args.dry_run:
            db.rollback()
            print(f"\nDry run: {imported} would be imported, {skipped} skipped.")
        else:
            db.commit()
            state = "published" if args.publish else "pending review"
            print(f"\nImported {imported} questions as {state}; skipped {skipped}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
