"""Load authored YAML content into the database.

The content directory is the source of truth for curriculum, lessons and questions; the database
is a projection of it. Loading is **idempotent and upsert-based**, keyed on slugs, so re-running
the seed after editing a YAML file updates rows in place rather than duplicating them — and
crucially without destroying student attempt history that references those rows.

File layout::

    content/<subject>/curriculum/<course>.yaml   subject, course, units, topics, skills
    content/<subject>/lessons/<course>.yaml      lessons (reference topic/skill slugs)
    content/<subject>/questions/<course>.yaml    question templates (reference skill slugs)
    content/<subject>/i18n/<locale>.yaml         translations, keyed by entity kind and slug

Translations live in their own files rather than as ``vi:`` blocks inside the authored English,
for three reasons: the English files carry explanatory comments that a YAML round-trip would
destroy, a translator can work on one file without touching content authoring, and adding a third
language is a new file rather than an edit to every existing one. An entity may still declare an
inline per-locale block; the sidecar wins where both exist.

Every question is validated by generating a variant before it is written. A template that cannot
generate is reported and skipped rather than being stored, because a broken template in the bank
becomes a 500 in front of a student mid-practice.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES
from app.exercise_engine import GenerationError, QuestionTemplate, generate_variant
from app.models import (
    Course,
    Lesson,
    Question,
    ReviewStatus,
    Skill,
    SkillPrerequisite,
    SkillRelation,
    Subject,
    Topic,
    Unit,
    Video,
)

__all__ = ["ContentLoader", "LoadReport", "load_all"]


@dataclass
class LoadReport:
    subjects: int = 0
    courses: int = 0
    units: int = 0
    topics: int = 0
    skills: int = 0
    prerequisites: int = 0
    lessons: int = 0
    questions: int = 0
    videos: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: LoadReport) -> None:
        for name in ("subjects", "courses", "units", "topics", "skills", "prerequisites",
                     "lessons", "questions", "videos"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.errors.extend(other.errors)

    def summary(self) -> str:
        return (
            f"{self.subjects} subjects, {self.courses} courses, {self.units} units, "
            f"{self.topics} topics, {self.skills} skills, {self.prerequisites} prerequisite "
            f"edges, {self.lessons} lessons, {self.questions} questions, {self.videos} videos"
            + (f", {len(self.errors)} errors" if self.errors else "")
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class ContentLoader:
    def __init__(self, db: Session, content_dir: Path) -> None:
        self.db = db
        self.content_dir = content_dir
        self.report = LoadReport()
        # {kind: {slug: {locale: {field: value}}}}, populated per subject before its content
        # files are read.
        self._sidecar: dict[str, dict[str, dict[str, Any]]] = {}

    def _load_sidecar(self, subject_dir: Path) -> None:
        """Read ``<subject>/i18n/<locale>.yaml`` into the translation lookup."""
        self._sidecar = {}
        i18n_dir = subject_dir / "i18n"
        if not i18n_dir.is_dir():
            return
        for path in sorted(i18n_dir.glob("*.yaml")):
            locale = path.stem
            if locale not in SUPPORTED_LOCALES or locale == DEFAULT_LOCALE:
                continue
            data = _read_yaml(path) or {}
            for kind, entries in data.items():
                if not isinstance(entries, dict):
                    continue
                bucket = self._sidecar.setdefault(kind, {})
                for slug, values in entries.items():
                    if isinstance(values, dict):
                        bucket.setdefault(slug, {})[locale] = values

    def _sidecar_for(self, kind: str, slug: str) -> dict[str, Any]:
        """Translations declared for one entity, as ``{locale: {field: value}}``."""
        return self._sidecar.get(kind, {}).get(slug, {})

    # ---- helpers -------------------------------------------------------------------

    def _upsert(self, model, slug: str, **fields):
        """Fetch by slug and update, or create. Returns the instance."""
        instance = self.db.scalar(select(model).where(model.slug == slug))
        if instance is None:
            instance = model(slug=slug, **fields)
            self.db.add(instance)
            self.db.flush()
            return instance, True
        for key, value in fields.items():
            setattr(instance, key, value)
        return instance, False

    def _translations(
        self,
        data: dict[str, Any],
        fields: tuple[str, ...],
        kind: str | None = None,
        slug: str | None = None,
    ) -> dict[str, Any] | None:
        """Collect per-locale overrides declared on a YAML entity.

        An entity may carry a block per non-default locale::

            title: Mathematics — Grade 6
            vi:
              title: Toán học — Lớp 6
              summary: …

        Returns ``None`` when nothing is translated, so the caller can leave an existing ``i18n``
        blob alone rather than wiping translations an administrator entered through the CMS.
        """
        sidecar = self._sidecar_for(kind, slug) if kind and slug else {}

        blob: dict[str, Any] = {}
        for locale in SUPPORTED_LOCALES:
            if locale == DEFAULT_LOCALE:
                continue
            inline = data.get(locale)
            merged: dict[str, Any] = {}
            if isinstance(inline, dict):
                merged.update(inline)
            # Sidecar wins: it is the file a translator maintains.
            merged.update(sidecar.get(locale) or {})

            values = {
                field: merged[field]
                for field in fields
                if merged.get(field) not in (None, "", [], {})
            }
            if values:
                blob[locale] = values
        return blob or None

    @staticmethod
    def _merge_block_overlays(
        translations: dict[str, Any] | None, base_blocks: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Overlay translated text onto lesson blocks, position by position.

        A translation supplies only the prose fields of each block — ``markdown``, ``title``,
        ``text``, ``points``, ``steps``, table ``headers``/``rows`` — as a list matching the
        original order. Everything else (block ``type``, interactive widget ``config``, the
        ``skill`` a practice block points at) is copied from the English block untouched, so a
        translation cannot accidentally detach a lesson from the skill it practises or break a
        plot.
        """
        if not translations or not base_blocks:
            return translations

        for bucket in translations.values():
            overlays = bucket.get("blocks")
            if not overlays:
                continue
            merged = []
            for index, block in enumerate(base_blocks):
                copy = dict(block)
                if index < len(overlays) and isinstance(overlays[index], dict):
                    copy.update(overlays[index])
                merged.append(copy)
            bucket["blocks"] = merged
        return translations

    @staticmethod
    def _merge_choice_labels(
        translations: dict[str, Any] | None, base_options: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Fold a ``choices: [label, …]`` list into a full translated ``options`` blob.

        A translation supplies only the visible labels, in the original order. It deliberately
        cannot restate ``correct`` — duplicating the answer key in a second file is how a
        translated question ends up marking a different option right from the English one. The
        base choice objects are copied and only their ``label`` replaced.
        """
        if not translations:
            return translations

        base_choices = base_options.get("choices") or []
        for bucket in translations.values():
            labels = bucket.pop("choices", None)
            if not labels or not base_choices:
                continue
            merged_choices = []
            for index, choice in enumerate(base_choices):
                copy = dict(choice) if isinstance(choice, dict) else {"label": choice}
                if index < len(labels):
                    copy["label"] = labels[index]
                merged_choices.append(copy)
            options = dict(bucket.get("options") or {})
            options["choices"] = merged_choices
            bucket["options"] = options
        # Drop any locale left with nothing after the pop.
        return {locale: values for locale, values in translations.items() if values} or None

    @staticmethod
    def _with_i18n(fields: dict[str, Any], translations: dict[str, Any] | None) -> dict[str, Any]:
        if translations is not None:
            fields["i18n"] = translations
        return fields

    # ---- curriculum ----------------------------------------------------------------

    def load_curriculum_file(self, path: Path) -> None:
        data = _read_yaml(path)

        subject_data = data.get("subject") or {}
        if not subject_data.get("slug"):
            self.report.errors.append(f"{path.name}: missing subject.slug")
            return

        subject, created = self._upsert(
            Subject,
            subject_data["slug"],
            **self._with_i18n(
                {
                    "name": subject_data.get("name", subject_data["slug"].title()),
                    "description": subject_data.get("description"),
                    "icon": subject_data.get("icon"),
                    "color": subject_data.get("color"),
                    "position": subject_data.get("position", 0),
                },
                self._translations(
                    subject_data, ("name", "description"), "subjects", subject_data["slug"]
                ),
            ),
        )
        if created:
            self.report.subjects += 1

        course_data = data.get("course") or {}
        if not course_data.get("slug"):
            self.report.errors.append(f"{path.name}: missing course.slug")
            return

        course, created = self._upsert(
            Course,
            course_data["slug"],
            **self._with_i18n(
                {
                    "subject_id": subject.id,
                    "title": course_data.get("title", course_data["slug"]),
                    "grade": course_data.get("grade", 6),
                    "summary": course_data.get("summary"),
                    "description": course_data.get("description"),
                    "estimated_hours": course_data.get("estimated_hours", 0),
                    "is_published": course_data.get("is_published", True),
                    "position": course_data.get("position", course_data.get("grade", 0)),
                },
                self._translations(
                    course_data,
                    ("title", "summary", "description"),
                    "courses",
                    course_data["slug"],
                ),
            ),
        )
        if created:
            self.report.courses += 1

        # Prerequisites are resolved in a second pass, because a skill may depend on one
        # declared later in the file or in another grade's file entirely.
        pending_prerequisites: list[tuple[str, Any]] = []
        pending_relations: list[tuple[str, str]] = []

        for unit_index, unit_data in enumerate(data.get("units") or []):
            unit, created = self._upsert(
                Unit,
                unit_data["slug"],
                **self._with_i18n(
                    {
                        "course_id": course.id,
                        "title": unit_data.get("title", unit_data["slug"]),
                        "summary": unit_data.get("summary"),
                        "icon": unit_data.get("icon"),
                        "position": unit_data.get("position", unit_index),
                    },
                    self._translations(
                        unit_data, ("title", "summary"), "units", unit_data["slug"]
                    ),
                ),
            )
            if created:
                self.report.units += 1

            for topic_index, topic_data in enumerate(unit_data.get("topics") or []):
                topic, created = self._upsert(
                    Topic,
                    topic_data["slug"],
                    **self._with_i18n(
                        {
                            "unit_id": unit.id,
                            "title": topic_data.get("title", topic_data["slug"]),
                            "summary": topic_data.get("summary"),
                            "position": topic_data.get("position", topic_index),
                        },
                        self._translations(
                            topic_data, ("title", "summary"), "topics", topic_data["slug"]
                        ),
                    ),
                )
                if created:
                    self.report.topics += 1

                for skill_index, skill_data in enumerate(topic_data.get("skills") or []):
                    fields = {
                        "topic_id": topic.id,
                        "name": skill_data.get("name", skill_data["slug"]),
                        "description": skill_data.get("description"),
                        "difficulty": skill_data.get("difficulty", 2),
                        "position": skill_data.get("position", skill_index),
                        "tags": skill_data.get("tags", []),
                    }
                    for param in ("bkt_p_init", "bkt_p_transit", "bkt_p_slip", "bkt_p_guess"):
                        if param in skill_data:
                            fields[param] = skill_data[param]

                    self._with_i18n(
                        fields,
                        self._translations(
                            skill_data, ("name", "description"), "skills", skill_data["slug"]
                        ),
                    )
                    skill, created = self._upsert(Skill, skill_data["slug"], **fields)
                    if created:
                        self.report.skills += 1

                    for prerequisite in skill_data.get("prerequisites") or []:
                        pending_prerequisites.append((skill_data["slug"], prerequisite))
                    for related in skill_data.get("related") or []:
                        pending_relations.append((skill_data["slug"], related))

        self.db.flush()
        self._link_prerequisites(pending_prerequisites, path.name)
        self._link_relations(pending_relations, path.name)

    def _link_prerequisites(self, pending: list[tuple[str, Any]], source: str) -> None:
        for skill_slug, prerequisite in pending:
            if isinstance(prerequisite, dict):
                prerequisite_slug = prerequisite.get("slug")
                strength = float(prerequisite.get("strength", 1.0))
            else:
                prerequisite_slug = prerequisite
                strength = 1.0

            skill = self.db.scalar(select(Skill).where(Skill.slug == skill_slug))
            target = self.db.scalar(select(Skill).where(Skill.slug == prerequisite_slug))

            if skill is None or target is None:
                self.report.errors.append(
                    f"{source}: prerequisite '{prerequisite_slug}' for '{skill_slug}' not found"
                )
                continue
            if skill.id == target.id:
                self.report.errors.append(f"{source}: '{skill_slug}' lists itself as prerequisite")
                continue

            existing = self.db.scalar(
                select(SkillPrerequisite).where(
                    SkillPrerequisite.skill_id == skill.id,
                    SkillPrerequisite.prerequisite_id == target.id,
                )
            )
            if existing is None:
                self.db.add(
                    SkillPrerequisite(
                        skill_id=skill.id, prerequisite_id=target.id, strength=strength
                    )
                )
                self.report.prerequisites += 1
            else:
                existing.strength = strength
        self.db.flush()

    def _link_relations(self, pending: list[tuple[str, str]], source: str) -> None:
        for skill_slug, related_slug in pending:
            skill = self.db.scalar(select(Skill).where(Skill.slug == skill_slug))
            related = self.db.scalar(select(Skill).where(Skill.slug == related_slug))
            if skill is None or related is None:
                self.report.errors.append(
                    f"{source}: related skill '{related_slug}' for '{skill_slug}' not found"
                )
                continue
            existing = self.db.scalar(
                select(SkillRelation).where(
                    SkillRelation.skill_id == skill.id,
                    SkillRelation.related_skill_id == related.id,
                )
            )
            if existing is None:
                self.db.add(SkillRelation(skill_id=skill.id, related_skill_id=related.id))
        self.db.flush()

    # ---- lessons -------------------------------------------------------------------

    def load_lessons_file(self, path: Path) -> None:
        data = _read_yaml(path)

        for index, lesson_data in enumerate(data.get("lessons") or []):
            topic = self.db.scalar(select(Topic).where(Topic.slug == lesson_data.get("topic", "")))
            if topic is None:
                self.report.errors.append(
                    f"{path.name}: lesson '{lesson_data.get('slug')}' references unknown topic "
                    f"'{lesson_data.get('topic')}'"
                )
                continue

            skill = None
            if lesson_data.get("skill"):
                skill = self.db.scalar(select(Skill).where(Skill.slug == lesson_data["skill"]))
                if skill is None:
                    self.report.errors.append(
                        f"{path.name}: lesson '{lesson_data.get('slug')}' references unknown "
                        f"skill '{lesson_data['skill']}'"
                    )

            video_id = None
            video_data = lesson_data.get("video")
            if video_data:
                video = self.db.scalar(
                    select(Video).where(
                        Video.provider == video_data.get("provider", "youtube"),
                        Video.external_id == video_data.get("external_id", ""),
                    )
                )
                if video is None:
                    video = Video(
                        title=video_data.get("title", lesson_data.get("title", "")),
                        provider=video_data.get("provider", "youtube"),
                        external_id=video_data.get("external_id", ""),
                        duration_seconds=video_data.get("duration_seconds", 0),
                        chapters=video_data.get("chapters", []),
                        captions=video_data.get("captions", []),
                        license=video_data.get("license"),
                        attribution=video_data.get("attribution"),
                    )
                    self.db.add(video)
                    self.db.flush()
                    self.report.videos += 1
                video_id = video.id

            _, created = self._upsert(
                Lesson,
                lesson_data["slug"],
                **self._with_i18n(
                    {
                        "title": lesson_data.get("title", lesson_data["slug"]),
                        "topic_id": topic.id,
                        "skill_id": skill.id if skill else None,
                        "summary": lesson_data.get("summary"),
                        "objectives": lesson_data.get("objectives", []),
                        "estimated_minutes": lesson_data.get("estimated_minutes", 15),
                        "position": lesson_data.get("position", index),
                        "blocks": lesson_data.get("blocks", []),
                        # A freshly loaded lesson has no unpublished edits; the draft mirrors the
                        # live body so opening the admin editor shows the real lesson.
                        "draft_blocks": lesson_data.get("blocks", []),
                        "video_id": video_id,
                        "status": lesson_data.get("status", ReviewStatus.PUBLISHED),
                        "source": lesson_data.get("source"),
                        "license": lesson_data.get("license"),
                        "attribution": lesson_data.get("attribution"),
                    },
                    self._merge_block_overlays(
                        self._translations(
                            lesson_data,
                            ("title", "summary", "objectives", "blocks"),
                            "lessons",
                            lesson_data["slug"],
                        ),
                        lesson_data.get("blocks", []),
                    ),
                ),
            )
            if created:
                self.report.lessons += 1
        self.db.flush()

    # ---- questions -----------------------------------------------------------------

    def load_questions_file(self, path: Path) -> None:
        data = _read_yaml(path)
        defaults = data.get("defaults") or {}

        for question_data in data.get("questions") or []:
            merged = {**defaults, **question_data}
            slug = merged.get("slug")
            skill_slug = merged.get("skill")

            skill = self.db.scalar(select(Skill).where(Skill.slug == skill_slug))
            if skill is None:
                self.report.errors.append(
                    f"{path.name}: question '{slug}' references unknown skill '{skill_slug}'"
                )
                continue

            question_type = merged.get("type") or merged.get("question_type")
            template = QuestionTemplate(
                slug=slug or "unnamed",
                question_type=question_type,
                prompt=merged.get("prompt", ""),
                variables=merged.get("variables") or {},
                constraints=merged.get("constraints") or [],
                answer_spec=merged.get("answer") or merged.get("answer_spec") or {},
                options=merged.get("options") or {},
                hints=merged.get("hints") or [],
                solution=merged.get("solution") or [],
                difficulty=merged.get("difficulty", 2),
            )

            # Validate across several seeds: a template can pass on seed 1 and fail on seed 2 if
            # its constraints are only sometimes satisfiable.
            try:
                for seed in (1, 2, 17, 999):
                    generate_variant(template, seed)
            except GenerationError as exc:
                self.report.errors.append(f"{path.name}: question '{slug}' is invalid — {exc}")
                continue

            # Translations are templates too — they carry the same {{ placeholders }} and go
            # through the same renderer. Validating them here is what stops a mistyped Vietnamese
            # prompt from failing mid-practice for a student instead of at load time.
            translations = self._translations(
                merged, ("prompt", "hints", "solution", "options", "choices"), "questions", slug
            )
            translations = self._merge_choice_labels(translations, template.options)
            if translations:
                bad = False
                for locale, bucket in translations.items():
                    localised = replace(
                        template,
                        prompt=bucket.get("prompt", template.prompt),
                        hints=bucket.get("hints", template.hints),
                        solution=bucket.get("solution", template.solution),
                        options={**template.options, **(bucket.get("options") or {})},
                    )
                    try:
                        for seed in (1, 2, 17, 999):
                            generate_variant(localised, seed)
                    except GenerationError as exc:
                        self.report.errors.append(
                            f"{path.name}: question '{slug}' [{locale}] is invalid — {exc}"
                        )
                        bad = True
                if bad:
                    continue

            topic = skill.topic
            course = topic.unit.course
            subject = course.subject

            _, created = self._upsert(
                Question,
                slug,
                i18n=translations if translations is not None else {},
                skill_id=skill.id,
                subject_slug=subject.slug if subject else "",
                grade=course.grade,
                topic_slug=topic.slug,
                question_type=question_type,
                difficulty=merged.get("difficulty", 2),
                prompt=merged.get("prompt", ""),
                variables=template.variables,
                constraints=template.constraints,
                answer_spec=template.answer_spec,
                options=template.options,
                hints=template.hints,
                solution=template.solution,
                tags=merged.get("tags", []),
                estimated_seconds=merged.get("estimated_seconds", 60),
                status=merged.get("status", ReviewStatus.PUBLISHED),
                is_parametric=bool(template.variables),
                source=merged.get("source"),
                license=merged.get("license"),
                attribution=merged.get("attribution"),
            )
            if created:
                self.report.questions += 1
        self.db.flush()

    # ---- orchestration -------------------------------------------------------------

    def load_all(self) -> LoadReport:
        if not self.content_dir.exists():
            self.report.errors.append(f"Content directory not found: {self.content_dir}")
            return self.report

        subject_dirs = sorted(p for p in self.content_dir.iterdir() if p.is_dir())

        # Order matters: curriculum first (creates skills), then lessons and questions which
        # reference them. Curriculum is loaded for *all* subjects before questions so that a
        # cross-subject prerequisite (physics leaning on a maths skill) resolves.
        for subject_dir in subject_dirs:
            # Translations are per subject, so they are reloaded as each subject's turn comes up.
            self._load_sidecar(subject_dir)
            for path in sorted((subject_dir / "curriculum").glob("*.yaml")):
                self.load_curriculum_file(path)

        for subject_dir in subject_dirs:
            self._load_sidecar(subject_dir)
            for path in sorted((subject_dir / "lessons").glob("*.yaml")):
                self.load_lessons_file(path)
            for path in sorted((subject_dir / "questions").glob("*.yaml")):
                self.load_questions_file(path)

        return self.report


def load_all(db: Session, content_dir: Path) -> LoadReport:
    loader = ContentLoader(db, content_dir)
    report = loader.load_all()
    db.commit()
    return report
