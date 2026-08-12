# Open Source Research

**Project:** HieuTrienEducation
**Research date:** 2026-08-12
**Method:** Shallow clones (`git clone --depth 1`) of each upstream repository into a throwaway
research directory, followed by direct inspection of `LICENSE`, data models, exercise/question
subsystems, scoring code, and content formats. Clones were deleted after inspection; nothing from
them was copied into this repository except where explicitly recorded below.

## Purpose of this document

HieuTrienEducation is a **commercial** tutoring platform (it sells 1-to-1 sessions, group classes and
recorded courses). That single fact drives almost every decision below, because it rules out:

- **AGPL-3.0** code, unless we are willing to publish the whole platform's source to every user over
  the network. We are not.
- **Non-commercial-only** assets and services (CC BY-NC-SA, GeoGebra's web materials).
- **CC BY-SA** content mixed into proprietary lesson material without share-alike consequences.

So the rule adopted for this project is:

> **Permissive-licensed (MIT/BSD/Apache-2.0/EUPL-compatible) code may be depended on or adapted with
> attribution. Copyleft projects are read for architecture only — no code, no schema dumps, no content.
> Anything ambiguous is reimplemented from first principles.**

Every reimplementation below is genuinely independent: the algorithms used (Bayesian Knowledge
Tracing, CAS-backed answer equivalence, prerequisite-gated recommendation) are published academic
methods, not any one project's proprietary work.

---

## Summary table

| Project | License | Verdict | What we actually took |
|---|---|---|---|
| Khan Academy **Perseus** | MIT | ✅ Reusable | Architectural model: widget-per-answer-type, separation of *render* from *score*, hint arrays on items |
| **OATutor** | MIT | ✅ Reusable | BKT update formula + mastery-threshold problem-selection heuristic (both are published methods; reimplemented in Python) |
| **GeoGebra** | EUPL-1.2 source / **non-commercial** web materials | ⚠️ Restricted | Nothing. Integration built but **disabled by default** — see below |
| **Frappe Learning (frappe/lms)** | AGPL-3.0 | 🚫 Inspiration only | Course→Chapter→Lesson IA, batch/live-class model, quiz-per-lesson pattern |
| **ClassroomIO** | AGPL-3.0 | 🚫 Inspiration only | Multi-tenant org model, lesson/exercise separation, marketing-site-plus-LMS layout |
| **OpenStax Exercises** | AGPL-3.0 (code); content CC BY | 🚫 Code / ⚠️ Content | `Logic` + `LogicVariable` parametric-variable concept (idea only). No content imported yet |
| **Moodle GIFT / IMS QTI** | Format specs (open) | ✅ Reusable | Import/export format targets — specs, not code |

---

## 1. Khan Academy Perseus

- **URL:** https://github.com/Khan/perseus
- **License:** MIT (`Copyright 2022 Khan Academy`), confirmed in `LICENSE` and `package.json`.
- **Stack:** TypeScript monorepo. Packages: `perseus`, `perseus-core`, `perseus-score`,
  `perseus-editor`, `perseus-linter`, `kas`, `kmath`, `math-input`, `simple-markdown`,
  `pure-markdown`, `keypad-context`.

### What is genuinely interesting

1. **Widget architecture.** `packages/perseus/src/widgets/` holds ~30 widget types (`radio`,
   `numeric-input`, `expression`, `orderer`, `sorter`, `matcher`, `interactive-graphs`, `grapher`,
   `plotter`, `categorizer`, `table`, `label-image`, …). A question is markdown with `[[☃ widget-id]]`
   placeholders; each widget owns its own rendering *and* its own scoring.
2. **`perseus-score` is a separate package** from the renderer (`score.ts`, `validate.ts`,
   `has-empty-diner-widgets.ts`). Scoring is a pure function over `(userInput, scoringData)`. This is
   the single best idea in the codebase: **grading does not require React**, so it can run anywhere.
3. **`PerseusItem` schema** (`perseus-core/src/data-schema.ts`): `{ question: PerseusRenderer, hints:
   Hint[], answerArea, ... }`. Hints are a first-class ordered array on the item, not an afterthought.
4. **`kas`** — Khan's computer algebra system for checking algebraic equivalence of student input.

### Integration decision

**Adopted as architecture, not as a dependency.** Reasons:

- Perseus is a large React 18 client bundle tightly coupled to Khan's Wonder Blocks design system. It
  would visually dominate our own design language and directly contradicts the product principle that
  this must not feel like "open-source projects glued together."
- Its scoring is client-side by design. For a platform where mastery drives paid recommendations, we
  need **authoritative server-side grading** that a student cannot inspect or tamper with.
- Perseus items are static JSON. We need *parametric* templates that generate thousands of variants.

**What we did instead:** `services/api/app/exercise_engine/` reimplements the good ideas in Python —
a registry of question-type graders, each a pure function `(question, user_answer) -> GradeResult`,
completely decoupled from rendering. `packages/exercise-engine/` holds the TypeScript *types and
renderers* only. We use **SymPy** where Perseus uses `kas`.

**Attribution required:** none for architectural influence. If we later vendor any Perseus source, the
MIT notice must be reproduced — a placeholder for that lives in `docs/CONTENT_LICENSES.md`.

---

## 2. OATutor

- **URL:** https://github.com/CAHLR/OATutor (UC Berkeley CAHLR)
- **License:** MIT.
- **Stack:** React (CRA). Content lives in a separate submodule, `CAHLR/OATutor-Content`.

### What is genuinely interesting

`src/models/BKT/BKT-brain.js` is a compact, correct Bayesian Knowledge Tracing posterior update:

```js
// (paraphrased) P(L_t | obs), then P(L_{t+1}) = posterior + (1 - posterior) * P(T)
```

and `problem-select-heuristics/defaultHeuristic.js` selects the *lowest-mastery* skill still below
`MASTERY_THRESHOLD`, breaking ties at random.

### Integration decision

**Reimplemented in Python.** The BKT update is the standard Corbett & Anderson (1995) formulation —
it is a published algorithm, not OATutor's invention, and our implementation is written directly from
the model definition in `services/api/app/adaptive/bkt.py` with the derivation documented in
`docs/ADAPTIVE_LEARNING.md`.

We deliberately went **beyond** OATutor's heuristic: their selector picks the single weakest skill,
which strands students on a skill whose prerequisites they lack. Our recommender is
**prerequisite-gated** — a skill is only recommended once its prerequisites clear a mastery floor —
and it blends four signals (mastery gap, prerequisite readiness, recency, and recent error rate).

**Attribution:** MIT permits reuse; since we reimplemented rather than copied, no notice is legally
required, but OATutor is credited in `docs/ADAPTIVE_LEARNING.md` as the prior art that informed the
design. That felt like the right thing to do.

---

## 3. GeoGebra ⚠️ (the important one)

- **URL:** https://github.com/geogebra/geogebra
- **License:** **source code EUPL-1.2**; **installers and web services under GeoGebra's own terms**;
  **language files CC BY-NC-SA 4.0**.
- **Verified at:** https://www.geogebra.org/license

### The constraint

GeoGebra's own license page states that the materials may be used "**for non-commercial purposes**"
only, and that "**any use of GeoGebra for a commercial purpose is subject to and requires a special
license**" — explicitly including *charging course fees for courses that incorporate GeoGebra
resources*.

**HieuTrienEducation charges course fees.** Embedding `deployggb.js` and shipping it to paying
students would therefore require a License and Collaboration Agreement with GeoGebra
(office@geogebra.org). This is a commercial/legal decision, not an engineering one.

### Integration decision

Implemented, but **off by default and fail-closed**:

- `GeoGebraEmbed` (`apps/web/src/components/interactive/geogebra-embed.tsx`) loads `deployggb.js`
  from GeoGebra's CDN **only** when `NEXT_PUBLIC_GEOGEBRA_ENABLED=true`.
- The flag defaults to `false`. With it off, the component renders a clear notice explaining that a
  commercial GeoGebra licence is required, rather than silently breaking.
- **Because we could not rely on GeoGebra, interactive math is not dependent on it.** We built our own
  dependency-free SVG **function plotter** (`function-plot.tsx`) and **geometry figure** renderer, both
  of which are used throughout the seeded lessons. GeoGebra is an *enhancement*, never a requirement.

This is flagged for the platform owners in `docs/CONTENT_LICENSES.md` as an action item to resolve
before commercial launch if GeoGebra activities are wanted.

---

## 4. Frappe Learning (`frappe/lms`)

- **URL:** https://github.com/frappe/lms
- **License:** **AGPL-3.0** (`license.txt`).
- **Stack:** Frappe Framework (Python/MariaDB) backend + Vue 3 frontend (`frontend/`, `frappe-ui/`).

### What is genuinely interesting

- IA: `Course → Chapter → Lesson`, with `Batch` (cohort) as an orthogonal enrollment concept, plus
  `Batch → LiveClass` for scheduled sessions. That separation of **content structure** from
  **cohort/enrollment** is correct and we adopted it.
- Quizzes attach to lessons rather than being a separate silo.
- Instructor/evaluator role split, and a batch-scheduling model with timeslots.

### Integration decision

**🚫 Inspiration only — zero code, zero schema copied.** AGPL-3.0's network clause would require us to
offer the entire platform's source to every student who uses it. Additionally the Frappe Framework is
a whole-application runtime; adopting it would mean adopting Frappe's ORM, admin, and deployment
model, which conflicts with our chosen FastAPI + Next.js stack.

What we took is the *idea* that content structure and cohort structure are different axes. Our schema
expresses that as `Course/Unit/Topic/Skill/Lesson` (content) vs `ClassGroup/Enrollment/Attendance/
LiveSession` (cohort). Written from scratch.

---

## 5. ClassroomIO

- **URL:** https://github.com/classroomio/classroomio
- **License:** **AGPL-3.0**.
- **Stack:** SvelteKit + Supabase, pnpm monorepo (`apps/`, `packages/`).

### What is genuinely interesting

- A single repo containing **both** the marketing website and the LMS, which is exactly our shape.
- Multi-tenant organisation model (an org owns courses, teachers and students).
- Clean `apps/` + `packages/` split with shared UI.

### Integration decision

**🚫 Inspiration only.** Same AGPL reasoning as Frappe. The monorepo layout convergence is
independent — it is the obvious structure for this problem, and our version is npm workspaces +
Next.js rather than pnpm + SvelteKit.

We deliberately **did not** adopt multi-tenancy: HieuTrienEducation is a single tutoring centre
(Thầy Hiếu & Cô Triền), and premature multi-tenancy would add a tenant foreign key to every table for
no current benefit. Noted as a future migration in `docs/ARCHITECTURE.md`.

---

## 6. OpenStax Exercises

- **URL:** https://github.com/openstax/exercises
- **License:** **AGPL-3.0** for the code (`GNU-AGPL-3.0`, `LICENSING`, `COPYRIGHT` — Rice University).
  The `LICENSING` file explicitly invites organisations concerned about copyleft to negotiate other
  terms. Published OpenStax *content* is generally **CC BY 4.0**, which is a separate matter.
- **Stack:** Ruby on Rails + PostgreSQL.

### What is genuinely interesting

The data model in `app/models/` is the most carefully-thought-through question schema of everything
surveyed:

- `Exercise → Question → Stem → Answer`, with `Stem` separating the prompt from the response slot.
- `Hint`, `CollaboratorSolution`, `CommunitySolution` as first-class rows.
- `QuestionDependency` for multi-part questions where part (b) depends on part (a).
- **`Logic` + `LogicVariable` + `LogicVariableValue`** — a parametric-question system. `Logic` stores
  a `code` blob in a `language`; `LogicVariable` names the variables it exposes (with a reserved-word
  blacklist that includes `seedrandom`, revealing that variants are **seeded** for reproducibility).
- `License`, `LicenseCompatibility`, `CopyrightHolder`, `Author` — provenance modelled properly.

### Integration decision

**🚫 No code. ⚠️ Content deferred.**

- The Rails code is AGPL and in the wrong language for us.
- **The seeded-variant insight was the single most valuable finding of this research** and directly
  shaped our design: every generated variant in HieuTrienEducation carries a `variant_seed`, so the
  server can deterministically regenerate the exact question a student saw in order to grade it,
  without trusting anything the client sends back. See `docs/QUESTION_ENGINE.md`.
- We also copied the *discipline* of provenance: every `Question` row carries `source`, `license` and
  `attribution` columns, so CC BY OpenStax content **can** be imported later without laundering its
  attribution.
- `scripts/import_open_content.py` implements the importer with an explicit licence allowlist
  (`CC-BY-4.0`, `CC-BY-SA-4.0`, `CC0-1.0`, `PUBLIC-DOMAIN`) that **refuses** to import anything
  outside it. No third-party content is bundled in this repository today — all seeded content is
  original work written for this project.

---

## 7. Question interchange formats

| Format | Status | Decision |
|---|---|---|
| **Moodle GIFT** | Simple line-based text format, widely supported | ✅ **Implemented** — import and export in `scripts/`, covers MC, T/F, numeric, short answer, matching |
| **IMS QTI 2.1/3.0** | XML, complex, the interoperability standard | ⚠️ **Partial** — import of the common `choiceInteraction` / `textEntryInteraction` subset. Full QTI is a multi-month project; the limitation is documented rather than faked |
| **Khan Academy Perseus JSON** | MIT tooling, static items | ⚠️ **Mapper written** for `radio` / `numeric-input` / `expression` widgets → our schema |
| **OpenStax API v1 JSON** | AGPL code, CC BY content | ⏳ Mapper written, **no content shipped** — requires a live pull the operator must initiate |

---

## What we owe whom

| Obligation | Status |
|---|---|
| Reproduce MIT notice if Perseus/OATutor source is vendored | N/A — no source vendored |
| Credit OATutor as prior art for BKT | ✅ `docs/ADAPTIVE_LEARNING.md` |
| Do not ship AGPL code | ✅ verified — no Frappe/ClassroomIO/OpenStax code present |
| Do not ship GeoGebra materials commercially without a licence | ✅ integration disabled by default, notice rendered |
| Preserve attribution/licence on any imported content | ✅ enforced by schema columns + importer allowlist |
| Keep all shipped educational content originally authored | ✅ see `docs/CONTENT_LICENSES.md` |

## Honest limitations of this research

- GeoGebra's `apiterms` page returned HTTP 403 to automated fetching; the licensing summary above is
  taken from https://www.geogebra.org/license. **A human should confirm the exact commercial terms
  with GeoGebra before enabling the integration.**
- We inspected only the default branch at clone time. Licences can change; they should be re-verified
  before any future decision to vendor code.
- Neither `CAHLR/OATutor-Content` nor OpenStax's live content API was pulled, so no judgement is
  offered here on the quality or per-item licensing of their actual question content.
