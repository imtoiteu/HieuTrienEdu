# Development

## Requirements

- **Node 18.18+** (20+ recommended — see the Playwright note below)
- **Python 3.11+**
- Docker, optionally

No database server is needed for local development: the API falls back to a SQLite file at
`data/hietedu.db`.

## Setup

```bash
git clone <repo> && cd HieuTrienEdu

# API
cd services/api
uv venv .venv && uv pip install -e ".[dev]"
# or: python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m app.seed.seed --reset

# Web (from the repo root)
cd ../..
npm install
```

## Running

Two terminals:

```bash
# API — bind 0.0.0.0, not 127.0.0.1 (see "IPv6" below)
npm run api

# Web
npm run dev              # or: PORT=3100 npm run dev
```

- Web → <http://localhost:3000/en>
- API docs → <http://localhost:8000/docs>

### Demo accounts

Password `HietEdu2026!` for all:

| Role | Email | Lands on |
|---|---|---|
| Student | `student@hietrieneducation.vn` | `/en/dashboard` |
| Parent | `parent@hietrieneducation.vn` | `/en/parent` |
| Teacher | `hieu@hietrieneducation.vn` | `/en/teacher` |
| Admin | `admin@hietrieneducation.vn` | `/en/admin` |

The login page lists these and fills the form when you click one — it is a demo build, and a
reviewer who cannot get in is worse than an exposed demo password.

## Common tasks

```bash
npm run api:seed                  # reload content (idempotent, keeps student data)
npm run api:seed -- --reset       # drop everything and start over
npm run api:test                  # 218 backend tests
npm test                          # 46 frontend tests
npm run typecheck                 # tsc --noEmit
npm run lint

cd services/api && .venv/bin/ruff check app tests
cd services/api && .venv/bin/alembic revision --autogenerate -m "add x"
cd services/api && .venv/bin/alembic upgrade head
```

### End-to-end tests

Playwright needs the API and web app running **and seeded**:

```bash
# terminal 1
npm run api
# terminal 2
npm run dev
# terminal 3
npm run test:e2e
```

If the web app is on a non-default port, tell Playwright and make sure the API allows that origin:

```bash
E2E_BASE_URL=http://127.0.0.1:3100 npm run test:e2e
```

## Traps worth knowing about

These each cost real debugging time during development.

### CORS is the usual cause of "Cannot reach the server"

The browser reports a CORS rejection to JavaScript as an indistinguishable network error. If login
fails with "Cannot reach the server" while the API is plainly running, the cause is almost
certainly that the web app's origin is missing from `CORS_ORIGINS`.

This is easy to hit because the dev server falls back to another port when 3000 is taken. The API
allows 3000 and 3100 by default; anything else must be added:

```bash
CORS_ORIGINS="http://localhost:3200,http://127.0.0.1:3200" npm run api
```

The API client logs an explicit hint naming the origin in development.

### Serving to a browser on another machine needs *two* settings

The section above assumes the browser is on the same machine as the servers. Once it is not — a
demo box, a colleague testing over the LAN — a second default bites, and it produces the *same*
"Cannot reach the server":

| Setting | Default | Why it breaks |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | This is the address the **browser** calls. For a visitor, `127.0.0.1` is their own computer. |
| `CORS_ORIGINS` | localhost/127.0.0.1 only | The visitor's origin is missing, so the API answers 200 without the header and the browser discards the response. |

Two things make this easy to miss. `NEXT_PUBLIC_*` is **inlined into the client bundle at build
time**, so setting it and restarting is not enough — the app must be rebuilt. And only
*client-side* calls fail: server-rendered pages keep working, because the server really is on
`127.0.0.1`. Curl-based checks and any crawl of rendered HTML will therefore pass while login is
broken. Test with an `Origin` header, or a real browser.

`scripts/serve-demo.sh` sets both from `.env` (or `PUBLIC_HOST`), rebuilds, and starts the pair.

### `CORS_ORIGINS` accepts two formats

Comma-separated (`a,b`) or a JSON array (`["a","b"]`). Both work. This needed `NoDecode` on the
field, because pydantic-settings JSON-decodes complex types *before* validators run — without it, a
comma-separated value raises `SettingsError` at import and the API refuses to start.

### Bind the API to 0.0.0.0, not 127.0.0.1

Node's `fetch` resolves `localhost` to the IPv6 address `::1` first. A server bound only to IPv4
refuses that connection, which shows up as **every server-rendered page silently losing its data**
while the browser works fine. `npm run api` binds `0.0.0.0`, and `NEXT_PUBLIC_API_URL` defaults to
`127.0.0.1` rather than `localhost` for the same reason.

### `cn()` and the client boundary

`cn()` lives in `packages/ui/src/cn.ts` with **no** `'use client'` directive, and both server and
client components import it from there. Moving it into a `'use client'` module makes every
server-component call fail at runtime with "attempted to call a client function from the server".

### Playwright and Node 18

Playwright ≥ 1.46 requires Node 20. The dependency is pinned to `1.45.3` exactly (not `^1.45.3`) so
a fresh install does not silently pull a version that will not run. On Node 20+, feel free to
upgrade.

### Editing `next.config.mjs` restarts the dev server

Obvious in hindsight; less obvious when it happens mid-test-run and every test fails at once.

### "Unpublish" has to be checked on the *detail* endpoint, not just the listing

Filtering a listing on `is_published` is the obvious half. The half that gets forgotten is that
the row's own slug is a public address that survives in links and search results, so a detail
endpoint without the same filter keeps serving the draft to anyone who has the URL. `get_course`,
`get_unit`, `get_skill` and the public teacher endpoints each had this hole. Staff are let through
deliberately, so previewing before publishing still works — see `_visible_to` in
`api/v1/curriculum.py`.

### A read path without a matching write path looks like it works

If a public endpoint calls `localise` on a field but no admin endpoint accepts a translation for
it, `/vi` still shows Vietnamese — the seed put it there. It only breaks when someone edits the
row, after which the two languages disagree with no way to reconcile them from the CMS.
`tests/test_admin_user_sync.py` guards this for every model in `TRANSLATABLE`.

### Verify through the public API, not the admin response

An admin endpoint returning what you just sent it proves nothing about what the learner is
served. Every test in `test_admin_user_sync.py` writes through `/admin/…` and reads back through
the endpoint a browser calls, because that is the only shape that would have caught any of the
bugs it covers.

### A message key nobody reads is not a translated interface

The admin dictionaries once held **281 keys that no component referenced** — fully translated,
sitting beside components that still rendered the English literal. Nothing failed and nothing
warned, so the admin stayed half-English for as long as anyone looked at it.

`src/messages/messages.test.ts` now fails on any key that no source file mentions, alongside the
checks that both languages define the same keys with the same placeholders. If a key is unused,
either wire it up where the English is still hardcoded, or delete it.

### Enum values from the API go through `useEnumLabel`

Statuses, formats, question types, audit actions and record types all arrive as snake_case
strings and resolve through `admin.st.<value>`. `humanise()` is the *fallback* inside that helper,
for a value the backend invents after the build — calling it directly, as a dozen screens did,
renders "Pending review" in English whatever language the administrator is using.

### An async server component rendered from a client module never settles

`MarketingShell` fetches the site chrome once, on the server. Three public pages imported it into
a `'use client'` module, which turns it into a client component — and React re-renders an async
client component every time its promise resolves. On a healthy API that is only duplicate
requests; when the API is unreachable the two chrome requests repeat until the browser runs out of
sockets with `ERR_INSUFFICIENT_RESOURCES`, and the page never renders at all. The route stays a
server component; the interactive half moves into a client child beside it.

## Project layout

```
apps/web/src/
├── app/[locale]/          routes
├── components/
│   ├── site/              marketing chrome
│   ├── app/               signed-in shell, learning path
│   ├── exercise/          answer inputs
│   └── lesson/            block renderer
├── lib/                   api client, auth, i18n, utils
├── messages/              en.json, vi.json
└── test/                  vitest setup

services/api/app/
├── api/v1/                routers
├── core/                  config, db, security, deps
├── models/                SQLAlchemy
├── schemas/               Pydantic
├── exercise_engine/       generation + grading (no framework deps)
├── adaptive/              BKT + recommender
├── services/              practice, gamification, providers
├── content_io/            YAML loader, format converters
└── seed/
```

## Conventions

**No user-facing strings in components.** Use `t('some.key')` and add the key to
`src/messages/en.json`. A missing key renders as the key itself, which is visible and greppable.

**Server components for public pages, client for authenticated ones.** Public pages wrap API calls
in `safe()` so an API outage renders the page without its data rather than a 500. Fallbacks must be
structural (empty list, null) — never invented content.

**Comments explain why, not what.** If a line needs explaining, explain the reasoning or the
constraint, not the syntax.

**Tests assert behaviour, not implementation.** The most valuable test in the suite is
`test_learning_flow.py::test_full_journey`, which exercises the entire product claim end to end.

## Adding things

**A page** — create `apps/web/src/app/[locale]/your-page/page.tsx`, wrap in `MarketingShell` or
`AppShell`, add nav entries only for routes that exist.

**An endpoint** — add to the relevant router in `app/api/v1/`, define Pydantic schemas, add a typed
method to `apps/web/src/lib/api.ts`, write a test.

**A question type** — add to `QuestionType`, write a builder in `generator.py` and a grader in
`graders.py`, add a branch to `AnswerInput`, and extend `hasAnswer` / `initialAnswer`.

**Content** — see [CURRICULUM.md](CURRICULUM.md).

## Outstanding work

Known gaps, in rough priority order:

1. **A third language.** Both the interface and the content are fully localised for English and
   Vietnamese — see [LOCALISATION.md](LOCALISATION.md). Adding a third means adding a locale to
   `SUPPORTED_LOCALES`, a dictionary under `apps/web/src/messages/`, and translations in the
   `i18n` columns; no schema change.
2. **Rate limiting.** Redis is wired up but unused for throttling. Login and registration first.
3. **Parent-child link confirmation.** Currently anyone knowing a student's email can link to them.
4. **Refresh token revocation.** No denylist, so logout is client-side only.
5. **Background jobs.** Anything slow would block a request today.
