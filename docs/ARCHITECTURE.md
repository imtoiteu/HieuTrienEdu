# Architecture

## Shape of the system

```
                    ┌──────────────────────────────────────────┐
   browser  ───────▶│  apps/web — Next.js 15 (App Router)      │
                    │  marketing site · student · teacher ·    │
                    │  parent · admin                          │
                    └───────────────┬──────────────────────────┘
                                    │  JSON over HTTPS, JWT bearer
                    ┌───────────────▼──────────────────────────┐
                    │  services/api — FastAPI                  │
                    │  ┌────────────────────────────────────┐  │
                    │  │ exercise_engine  (pure, testable)  │  │
                    │  │ adaptive         (BKT, recommender)│  │
                    │  │ services         (providers)       │  │
                    │  └────────────────────────────────────┘  │
                    └──────┬───────────────────────┬───────────┘
                           │                       │
                  ┌────────▼────────┐     ┌────────▼─────────┐
                  │  PostgreSQL     │     │  Redis (optional)│
                  └─────────────────┘     └──────────────────┘

  content/  ──── loaded at seed time ────▶ PostgreSQL
```

## Decisions worth explaining

### One web app, not four

The brief suggested `apps/web`, `apps/student`, `apps/teacher`, `apps/admin`. We used **one**
Next.js application with route groups instead.

Four applications would mean four copies of the authentication flow, four builds of the design
system, four dev servers to run, and four places for a shared component to drift. The audiences
also overlap more than the split implies: an admin needs teacher tools, and a teacher browsing a
lesson wants the same lesson viewer a student sees.

Route groups give the same separation of concerns with none of that cost:

```
app/[locale]/
  page.tsx, about/, mathematics/, physics/, courses/, teachers/,
  learning-methods/, tutoring/[format]/, pricing/, testimonials/, blog/, contact/
  login/, register/
  dashboard/, practice/[skill]/, progress/, achievements/, lessons/[slug]/
  teacher/, teacher/questions/
  admin/
  parent/, parent/payments/
```

If one audience ever needs an independent deploy cadence, splitting later is a directory move —
far cheaper than merging four apps that have already diverged.

### FastAPI rather than adopting an existing LMS

Frappe Learning and ClassroomIO are both capable, and both are AGPL-3.0. For a commercial platform
that would mean publishing all of our source to every user over the network. Beyond the licence,
adopting Frappe means adopting its whole application runtime — ORM, admin, deployment model — for
a product whose distinctive part (the exercise engine and mastery model) it does not provide.

FastAPI gives us Pydantic validation, generated OpenAPI docs, and direct access to SymPy, which
the exercise engine depends on. See [OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md).

### The exercise engine has no framework dependencies

`app/exercise_engine/` imports nothing from FastAPI or SQLAlchemy — only the `QuestionType` enum.
Its input is a `QuestionTemplate` dataclass and its output is a `GeneratedVariant`.

That makes it directly unit-testable (69 of the 111 backend tests hit it with no database), and it
means a content-authoring script can validate a template without spinning up the app. The seed
loader uses exactly this: it generates every question across four seeds before writing it.

### Grading is server-side, always

The student-facing payload from `/practice/sessions/{id}/next` contains no answer field. The
correct answer lives in `question_variants.answer`, and grading happens in
`app/services/practice.py`.

This is not paranoia about cheating so much as data integrity: mastery drives recommendations,
progress reports to parents, and eventually paid tutoring decisions. A mastery figure a student
could influence from the browser would be worthless.

The `variant_seed` design means we could go further and store nothing at all — `(question_id, seed)`
regenerates the variant deterministically. We persist variants anyway so a teacher can see exactly
what a student was shown when reviewing a disputed answer.

### Providers are abstracted, and honest when unconfigured

Live classes, payments, video storage and AI all sit behind an interface with a working default:

| Concern | Default | Status |
|---|---|---|
| Live class | `ManualProvider` | Complete — the teacher pastes a link, which is how the centre works today |
| Payment | `ManualProvider` | Complete — bank transfer/cash, reconciled by an admin |
| Storage | URL resolution | Complete for playback; **no upload endpoint** |
| AI | `DisabledProvider` | **Deliberately not implemented** — see [AI.md](AI.md) |

Each unconfigured provider reports that clearly rather than failing at call time. `get_provider()`
falls back to manual if Zoom credentials are missing, so a misconfiguration cannot stop a teacher
scheduling a class.

### Single tenant, on purpose

ClassroomIO is multi-tenant; we are not. HieuTrienEducation is one tutoring centre. Adding an
`organisation_id` to all 44 tables for a second customer that does not exist would be paying today
for a maybe. If a second centre is ever onboarded, the migration is mechanical.

## Data model

44 tables in seven groups. The full definitions are in `services/api/app/models/`.

**Identity** — `users` (one row per login) plus a role-specific profile: `student_profiles`,
`teacher_profiles`, `parent_profiles`, joined by `parent_student_links`. One users table means one
implementation of authentication, password reset and sessions.

**Curriculum** — `subjects → courses → units → topics → skills`, with `skill_prerequisites` (a
directed graph) and `skill_relations` (undirected). Every question hangs off exactly one skill.
That strictness is what makes the whole adaptive system possible: it can always answer *which
skill does this question test?*

**Content** — `lessons` (typed JSON blocks), `videos` (metadata only, never bytes), `resources`.

**Questions** — `questions` are always templates; a template with no `variables` is simply a static
question, which keeps one code path instead of two. `question_variants` records concrete renderings.

**Progress** — `attempts` is the append-only event log everything else derives from.
`student_skill_mastery` holds current BKT state, `practice_sessions` groups attempts,
`lesson_progress` tracks reading, and `xp_events` is an append-only ledger with a denormalised
total on the profile for fast dashboard reads.

**Tutoring** — `tutoring_products`, `class_groups`, `schedule_slots`, `class_enrollments`,
`live_sessions`, `attendance`, `tutoring_requests`, `assignments`.

**Commerce and site** — `orders`, `order_items`, `payments`, `subscriptions`, plus
`testimonials`, `blog_posts`, `contact_leads` so the marketing site is admin-editable rather than
a wall of hard-coded strings.

### Modelling choices

- **Money is integer VND.** The đồng has no minor unit, so there is no cents column, and floats for
  currency are a known source of drift.
- **Enums are strings, not native database enums.** Adding a value to a PostgreSQL enum needs a
  migration and locks the type; a string column with a Python-side `StrEnum` gives validation where
  it matters and no migration friction where it does not.
- **Order items snapshot their description and price.** If a product's price changes later,
  historical orders must not.
- **Provenance on every question and lesson** — `source`, `license`, `attribution` — so open
  content can be imported later without laundering its attribution.
- **Explicit constraint naming conventions** on the metadata, so Alembic autogenerate produces
  stable, reversible migrations.

## Request flow: answering a question

1. `GET /practice/sessions/{id}/next` → `serve_question()` picks a difficulty just above the
   student's mastery, chooses a template they have not seen this session, draws a cryptographically
   random seed, generates the variant, persists it, and returns the student-safe payload.
2. The student answers. `POST /practice/submit` sends `{variant_id, answer, hints_used, ...}`.
3. `record_attempt()` runs the whole consequence chain in one transaction: grade → BKT update →
   persist the attempt → update rolling statistics → award XP → extend the streak → check
   achievements.
4. The response carries the grade, the mastery movement, the rewards and — only now — the worked
   solution.

Everything in step 3 lives in one function on purpose. Mastery must never be updated from two
places with slightly different rules.

## Frontend

- **Server components** for marketing pages (SEO), wrapped in `safe()` so an API outage renders the
  page without its data rather than a 500. Fallbacks are always structural — an empty list, a null
  — never invented content.
- **Client components** for anything authenticated, since JWTs live in `localStorage` and these
  pages are not indexed anyway.
- **i18n by construction.** Components call `t('some.key')`; there are no user-facing literals.
  Missing keys fall back to English and then to the key itself, so a partial locale degrades
  visibly rather than blankly.
- **`cn()` lives in its own module** with no `'use client'` directive. It is used by both server and
  client components, and exporting it from a client module makes server-side calls fail at runtime
  — which is exactly the bug that broke the homepage during development.

## Known gaps

- **Parent-child linking has no confirmation step.** Anyone who knows a student's email can link to
  them. The centre creates family accounts during onboarding today, so this is a convenience path —
  but it needs an email or admin confirmation before it is exposed more widely.
- **No rate limiting.** Redis is wired up but not used for throttling. Login and registration in
  particular should be limited before public launch.
- **No background job runner.** Anything slow (an emailed report, AI generation) would currently
  block a request. Celery or arq should land alongside the first such feature.
- **Refresh tokens are not revocable.** There is no denylist, so logging out clears the client but
  does not invalidate an already-issued token until it expires.
