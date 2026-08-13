<div align="center">

# HieuTrienEducation

**Mathematics & Physics for grades 6–9 — an adaptive learning platform and tutoring centre.**

Built for Thầy Hiếu & Cô Triền.

</div>

---

## What this is

A single, coherent product with two halves that share one database:

1. **A learning platform.** A mapped curriculum of 161 skills across Mathematics and Physics for
   grades 6–9, an exercise engine that generates unlimited unique questions from parametric
   templates, server-side grading, and a Bayesian mastery model that decides what each student
   should do next.
2. **A tutoring-centre website.** A marketing site with 1-to-1, group, online, live and recorded
   learning formats, a working enquiry and enrollment flow, and dashboards for teachers, parents
   and administrators.

It is not a demo. The core journey — register → log in → choose a course → open a lesson →
practise → submit → get feedback → mastery updates → get a recommendation — works end to end, and
there is a test that proves it.

## Features

### Learning

- **161 skills** with **195 prerequisite edges** forming a directed skill graph across
  Mathematics and Physics, grades 6–9.
- **186 parametric question templates** covering **every skill**, so practice never dead-ends.
  Each template generates thousands of distinct, mathematically valid variants.
- **Nine question types**: multiple choice, multiple select, numeric, algebraic expression, fill
  in the blank, true/false, matching, ordering, short answer.
- **Server-side grading** with partial credit, and algebraic equivalence via SymPy — a student can
  answer `2(x+3)` where the model answer is `2x + 6`.
- **Bayesian Knowledge Tracing** per student and skill, adjusted for how guessable each question
  type is, with forgetting over time.
- **Prerequisite-gated recommendations** and a visual learning path.
- **Progressive hints**, worked solutions released only after answering, XP, streaks, levels and
  achievements.
- **Lessons** built from typed content blocks, with KaTeX notation and dependency-free interactive
  SVG figures (function plots, fraction bars, geometry, number lines).

### Tutoring centre

- Five learning formats with real pricing, class schedules and open-place counts.
- An enquiry flow that works without an account, because requiring one loses enquiries.
- Class enrollment producing an order, held for 48 hours and confirmed by an admin.
- Teacher dashboard: class analytics, weakest skills, hardest questions, and the mistakes students
  actually make.
- A question bank browser that regenerates live variants with answers and worked solutions.
- Parent dashboard: per-child progress, weak skills, attendance and payment history.

### Engineering

- **Internationalised from the first commit.** No user-facing string is hard-coded; English is
  complete and Vietnamese is substantially translated, falling back per key.
- **Accessible**: semantic HTML, keyboard-operable everywhere (including the ordering question,
  which uses buttons rather than drag-and-drop), visible focus rings, `prefers-reduced-motion`
  respected, ARIA on every progress bar and live region.
- **Responsive**: a sidebar on desktop, a bottom bar on mobile, because students use phones.
- **148 automated tests** — 111 backend (pytest), 37 frontend (vitest) — plus a Playwright
  end-to-end suite covering the full journey.

## Quick start

### Docker (everything at once)

```bash
cp .env.example .env          # optional; every value has a working default
docker compose up --build
docker compose run --rm seed  # load curriculum + demo data
```

- Web app → <http://localhost:3000>
- API docs → <http://localhost:8000/docs>

### Without Docker

Requires **Node 18.18+** and **Python 3.11+**. No database server needed — it falls back to a
SQLite file.

```bash
# 1. API
cd services/api
uv venv .venv && uv pip install -e ".[dev]"     # or: python -m venv .venv && pip install -e ".[dev]"
.venv/bin/python -m app.seed.seed --reset       # load content + demo data
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. Web (from the repo root, in a second terminal)
npm install
npm run dev                                     # PORT=3100 npm run dev if 3000 is taken
```

Open <http://localhost:3000/en>.

### Demo accounts

All use the password `HietEdu2026!`:

| Role | Email |
|---|---|
| Student | `student@hietrieneducation.vn` |
| Parent | `parent@hietrieneducation.vn` |
| Teacher | `hieu@hietrieneducation.vn` |
| Admin | `admin@hietrieneducation.vn` |

The seeded student has 220 simulated attempts behind them, so the dashboard, mastery bars,
recommendations and activity heatmap all open with real data rather than zeros.

## Architecture

```
apps/web/            Next.js 15 App Router — public site + all four dashboards
packages/            ui · localization · curriculum · exercise-engine · analytics · ai
services/api/        FastAPI — models, exercise engine, adaptive learning, content loader
content/             Authored YAML: curriculum, lessons, question templates
docs/                Architecture, licensing, curriculum, engine, adaptive model, deployment
docker/              Dockerfiles for api and web
```

The web app is a single Next.js application with route groups rather than four separate apps.
That keeps one auth flow, one design system and one dev server — the rationale is in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Stack:** Next.js 15 · React 18 · TypeScript · Tailwind CSS · FastAPI · SQLAlchemy 2 · Alembic ·
PostgreSQL (SQLite for local dev) · Redis (optional) · SymPy · KaTeX.

## Environment variables

Every variable has a working default; see [`.env.example`](.env.example) for the full list. The
ones that matter:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | insecure dev value | **Change before deploying.** JWT signing key |
| `DATABASE_URL` | SQLite file | PostgreSQL connection string |
| `REDIS_URL` | unset | Optional; degrades to an in-process cache |
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | API address **as the browser sees it** |
| `AI_PROVIDER` | `disabled` | AI Assist is deliberately deferred — see below |
| `LIVE_CLASS_PROVIDER` | `manual` | `zoom` once credentials are set |
| `PAYMENT_PROVIDER` | `manual` | Bank transfer / cash, reconciled by an admin |
| `GEOGEBRA_ENABLED` | `false` | Requires a commercial GeoGebra licence — see below |

## Testing

```bash
npm run api:test     # 111 backend tests (pytest)
npm test             # 37 frontend tests (vitest)
npm run test:e2e     # Playwright — needs the API and web app running and seeded
```

The end-to-end suite covers the full journey plus role boundaries (a student is bounced out of the
teacher area), the language switch, lesson rendering, the tutoring enquiry, and 404 handling.

## What is deliberately not finished

Being straight about this matters more than a longer feature list.

- **AI Assist is architecture only.** Per the project brief, model integration is deferred to a
  later phase. The interfaces, database schema, audit tables, permission model and UI are all in
  place; `AI_PROVIDER=disabled` is the default and every endpoint returns an honest "not enabled"
  response rather than fabricating tutoring content. See [docs/AI.md](docs/AI.md).
- **GeoGebra is integrated but switched off.** GeoGebra's licence restricts its materials to
  non-commercial use, and this platform charges course fees. Enabling it requires a licence
  agreement with GeoGebra first, so the component renders a clear notice instead. Nothing in the
  curriculum depends on it — interactive maths uses our own SVG widgets.
- **No online payment gateway.** `manual` (bank transfer or cash at the centre, confirmed by an
  admin) is fully implemented because it is how the centre actually operates. VNPay/MoMo/Stripe
  are interface-ready but not written, and no checkout button pretends otherwise.
- **Zoom is implemented but unverified.** The Server-to-Server OAuth flow follows Zoom's
  documented v2 API but has never run against real credentials. The manual provider is the
  default and works completely.
- **No video upload endpoint.** Video metadata and playback-URL resolution work across five
  providers; uploading needs signed multipart URLs and a transcoding pipeline that would be
  dishonest to stub.
- **Vietnamese is partial.** Navigation, authentication, the whole student experience and the
  marketing shell are translated. Teacher, admin and long-form marketing copy fall back to
  English per key — visibly, not blankly.

## Documentation

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data model, and the decisions behind both |
| [OPEN_SOURCE_RESEARCH.md](docs/OPEN_SOURCE_RESEARCH.md) | Every upstream project surveyed, its licence, and what we did or did not take |
| [CONTENT_LICENSES.md](docs/CONTENT_LICENSES.md) | Provenance of every piece of shipped content |
| [CURRICULUM.md](docs/CURRICULUM.md) | The hierarchy, the skill graph, and how to author content |
| [QUESTION_ENGINE.md](docs/QUESTION_ENGINE.md) | Template format, sampling, grading, security model |
| [ADAPTIVE_LEARNING.md](docs/ADAPTIVE_LEARNING.md) | The BKT model, its parameters, and our deviations from it |
| [AI.md](docs/AI.md) | The AI abstraction, and exactly what is and is not implemented |
| [LOCALISATION.md](docs/LOCALISATION.md) | How interface *and* content are translated, and what must never be |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup, workflows, testing, troubleshooting |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production checklist, scaling notes, open risks |

## Licence

Application code is proprietary to HieuTrienEducation. All shipped educational content is
originally authored for this project. No third-party educational content is bundled — see
[docs/CONTENT_LICENSES.md](docs/CONTENT_LICENSES.md).
