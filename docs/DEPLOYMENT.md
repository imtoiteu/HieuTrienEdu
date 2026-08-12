# Deployment

## Docker Compose

```bash
cp .env.example .env      # then edit — see the checklist below
docker compose up --build -d
docker compose run --rm seed
```

Four services: `db` (PostgreSQL 16), `redis`, `api` and `web`. `api` waits on healthy `db` and
`redis`; `web` waits on healthy `api`. Migrations run automatically on API start, so a fresh volume
comes up with the right schema.

Seeding is a **separate one-off service** (`profiles: ["tools"]`) rather than part of `up`, because
re-seeding on every restart would be surprising.

## Before going live

### Must do

- [ ] **Set `SECRET_KEY` to a real random value.** Tokens signed with the default are trivially
      forgeable by anyone who has read this repository. `openssl rand -hex 32`.
- [ ] **Change `POSTGRES_PASSWORD`.**
- [ ] **Delete or change every demo account.** They are created by the seed with a published
      password, and one of them is an admin.
- [ ] **Remove the demo-account panel from the login page**
      (`apps/web/src/app/[locale]/login/page.tsx`).
- [ ] **Set `ENVIRONMENT=production` and `DEBUG=false`.** Debug mode returns exception messages in
      500 responses.
- [ ] **Set `CORS_ORIGINS` to your real domain only.**
- [ ] **Terminate TLS in front of both services.** Neither serves HTTPS.
- [ ] **Replace the fictional testimonials and teacher biographies** — see
      [CONTENT_LICENSES.md](CONTENT_LICENSES.md).

### Should do

- [ ] Add rate limiting on `/auth/login` and `/auth/register`. Redis is available and unused for
      this.
- [ ] Set up automated database backups. All student progress lives in one Postgres volume.
- [ ] Add error tracking (Sentry or equivalent). There is none.
- [ ] Add a parent-child link confirmation step — currently anyone knowing a student's email can
      link to them.
- [ ] Decide the GeoGebra licensing question, or leave `GEOGEBRA_ENABLED=false`.
- [ ] Review `docs/AI.md` before enabling any AI provider — safety filtering and a privacy policy
      are prerequisites, not nice-to-haves, when minors are involved.

## Environment

Full list in [`.env.example`](../.env.example). Production-relevant values:

| Variable | Production value |
|---|---|
| `SECRET_KEY` | 32+ random bytes. **Rotating it logs everyone out.** |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/hietedu` |
| `REDIS_URL` | `redis://host:6379/0` — optional, degrades to in-process |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `CORS_ORIGINS` | Your web origin(s), comma-separated |
| `NEXT_PUBLIC_API_URL` | The API URL **as the browser sees it** — public, not internal |
| `PUBLIC_API_URL` | Same; used as a Docker build arg |

`NEXT_PUBLIC_*` values are **inlined at build time**, not read at runtime. Changing
`NEXT_PUBLIC_API_URL` requires rebuilding the web image, which is why Compose passes it as a build
arg.

## Migrations

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec api alembic downgrade -1
```

The initial migration has been verified to upgrade and downgrade cleanly. SQLite uses batch mode
(`render_as_batch`) because it cannot `ALTER` most things in place.

**Take a backup before any migration on production data.** Alembic will happily drop a column.

## Scaling

The API is stateless — no session storage, JWTs carry identity — so it scales horizontally behind
any load balancer.

Likely bottlenecks in order:

1. **Question generation.** SymPy parsing on the `expression` type is the slowest path. Cacheable
   in Redis by `(question_id, seed)`, which is a pure function; not yet done.
2. **The dashboard query.** ~8 queries per load. Fine to thousands of students; add a materialised
   summary table beyond that.
3. **`question_variants` growth.** One row per question served, forever. At 1,000 students × 20
   questions/day that is ~7M rows/year. Variants are regenerable from `(question_id, seed)`, so
   old rows can be pruned once the audit window passes.

Sensible indexes are in place: `attempts(student_id, skill_id)`, `questions(skill_id, difficulty)`,
and unique constraints on every natural key.

## Providers

### Live classes

`LIVE_CLASS_PROVIDER=manual` (default) is complete — a teacher pastes the meeting link, which is how
the centre works today.

`zoom` activates the Server-to-Server OAuth integration once `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID` and
`ZOOM_CLIENT_SECRET` are all set. ⚠️ **This has never been run against real Zoom credentials.** The
request and response shapes follow Zoom's documented v2 API, but treat the first production run as a
smoke test. Meetings are created with waiting room on and mute-on-entry, which matters when the
participants are minors.

If Zoom is misconfigured, `get_provider()` falls back to manual rather than failing — a broken
integration must not stop a teacher scheduling a class.

### Payments

`PAYMENT_PROVIDER=manual` is complete: an order is created, the place is held 48 hours, and an admin
marks it paid, which activates the enrollment.

**No online gateway is implemented.** VNPay, MoMo and Stripe would each implement `PaymentProvider`
plus a signed callback endpoint. Their classes are deliberately absent rather than stubbed, so
nothing in the UI can offer a payment method that would fail.

### Video

Playback URL resolution works for `youtube`, `vimeo`, `cloudflare_stream`, `s3`/`r2` and a plain
`external` passthrough. YouTube uses the `youtube-nocookie` domain so students are not tracked
before consenting.

**There is no upload endpoint.** Uploading needs signed multipart URLs and a transcoding pipeline
that would be dishonest to stub. Upload out of band and record `(provider, external_id)`.

## Monitoring

`GET /health` returns status, environment, database backend and which integrations are configured.
Both Compose services have healthchecks wired to it.

Not implemented: structured request logging, metrics, tracing, alerting.

## Backup and restore

```bash
docker compose exec db pg_dump -U hietedu hietedu | gzip > backup-$(date +%F).sql.gz
gunzip -c backup-2026-01-01.sql.gz | docker compose exec -T db psql -U hietedu hietedu
```

Curriculum content is reproducible from `content/` via the seed, so the irreplaceable data is
users, attempts, mastery, enrollments and orders. Back up the database, not the content directory.

## Security posture

**Implemented:** bcrypt password hashing (rejecting rather than truncating over 72 bytes),
short-lived JWTs with type checking so a refresh token cannot be used as an access token, role
guards on every privileged route, login timing equalised so response time does not reveal which
emails are registered, AST-whitelisted expression evaluation, character-whitelisted student input
before SymPy, no answers in student-facing payloads, non-root container users.

**Not implemented:** rate limiting, refresh-token revocation, MFA, audit logging of admin actions,
CSP headers, account lockout. Add these before a public launch.

## Known risks

| Risk | Severity | Mitigation |
|---|---|---|
| Default `SECRET_KEY` shipped | **Critical** | Change it. Anyone can forge admin tokens otherwise |
| Demo accounts with a published password | **Critical** | Delete before launch |
| No rate limiting on auth | High | Add before public launch |
| Parent-child linking unconfirmed | High | Add a confirmation step |
| No refresh-token revocation | Medium | Logout is client-side only |
| Zoom integration unverified | Medium | Manual provider is the default and works |
| `question_variants` grows unbounded | Low | Prune old rows; they are regenerable |
