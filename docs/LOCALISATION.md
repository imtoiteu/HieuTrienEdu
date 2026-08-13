# Localisation

The platform teaches Vietnamese students. Vietnamese is the language that matters most, English is
the language the source content was authored in, and both have to work — a Vietnamese student must
never see an English question prompt, and the English site must not regress as Vietnamese improves.

There are two separate problems here, and conflating them is the usual reason a "translated" site
still shows English where it counts:

| | Interface text | Content |
|---|---|---|
| Examples | "Save", "Your progress", "Grade" | Course titles, lesson bodies, question prompts, hints, testimonials |
| Lives in | `apps/web/src/messages/{en,vi}.json` | The database, in an `i18n` JSON column |
| Authored by | Developers | Teachers and administrators, through the admin CMS |
| Changes with | A deploy | A save in the CMS |

Translating only the first is what makes a site look Vietnamese while every course, lesson and
exercise on it is still English.

## Content: the `i18n` column

Every translatable model carries one JSON column:

```python
class Course(Base, TimestampMixin, TranslatableMixin):
    title: Mapped[str]          # English — the source of truth
    # i18n: {"vi": {"title": "Toán học — Lớp 6", "summary": "…"}}
```

Reads go through `app.core.i18n.localise`, which falls back to the English column whenever a
translation is missing or empty. That fallback is why `/en` cannot break and a half-translated
`/vi` degrades to readable English rather than to blank fields.

**Why a JSON column** rather than `title_vi` columns or a translations table:

* A third language, or a newly translatable field, is a data change rather than a migration. The
  set of translatable fields differs per model — a question has `prompt`, `hints`, `solution` and
  `options`; a course has `title`, `summary`, `description` — and parallel columns would mean a
  wide, mostly-null schema.
* Translations are always read with their row and never queried on their own, so the one thing a
  join table would buy, indexing translated text, is not needed.

Fourteen models are translatable. `app/api/v1/admin/_translations.py` holds the whitelist of which
fields on each, and it is the enforcement point, not documentation: the admin API rejects anything
not on it with a 422.

### What is deliberately *not* translatable

* **`answer_spec`.** A translation must never be able to change what counts as a correct answer.
  The one exception is the display-only `unit` ("degrees C" → "độ C"), which is shown to the
  student but never compared against.
* **Choice `correct` flags.** Translated multiple-choice options supply labels only; they are
  merged onto the English choices *by position*, so the correct option is carried over from the
  source and cannot be moved by a careless translation.
* **BKT parameters, prices, capacities, grades, positions, publish flags.** Facts, not prose.
* **People's names.** A testimonial's `author_name` and a teacher's `full_name` are the same in
  every language. Translating them would be wrong, not merely unnecessary.

## Questions are templates, so translations are templates

A parametric question is a template with `{{ }}` placeholders that generates thousands of distinct
exercises. Translating the *rendered output* would be far too late — there is nothing to translate
until a variant exists, and each variant is different.

Instead `QuestionTemplate.from_model(question, locale)` localises the **template**, and generation
runs on the translated one:

```
prompt      : "What is {{a}} + {{b}}?"
i18n.vi     : "Giá trị của {{a}} + {{b}} là bao nhiêu?"
seed 42, en : "What is 7 + 4?"          answer 11
seed 42, vi : "Giá trị của 7 + 4 là bao nhiêu?"   answer 11
```

Same seed, same variables, same answer, different prose. `tests/test_localisation.py` asserts that
property directly, and the admin API refuses to save a question whose Vietnamese template fails to
generate — a mistyped placeholder fails at save time rather than in front of a student.

## Grading feedback

The sentence a student reads after submitting is content too: *"your answer is ten times too large
— check your decimal point"* is the most useful line on the page, and it is worthless to a
Vietnamese student in English.

Graders stay pure and language-free. Each emits a stable **key** plus the numbers that go into the
sentence, and `app/exercise_engine/feedback.py` turns the key into prose once, at the edge:

```python
GradeResult(is_correct=False, message_key="ten_times_too_large")
# en: "Close — your answer is ten times too large. Check your units or decimal point."
# vi: "Gần đúng rồi — kết quả của em lớn gấp mười lần. Hãy kiểm tra lại đơn vị…"
```

The same table covers submission-format errors ("Select an option before submitting") and the
recommender's reasons ("A new skill you are ready to start"). The machine-readable `reason` code
never changes with language, so anything downstream keying off it is unaffected.

Stored attempts keep `message_key` and `message_params` alongside the rendered message, so a
graded attempt can be re-rendered in either language years later.

## How a request picks its language

`app.core.deps.get_locale` resolves, in order:

1. **`?locale=vi`** — the query parameter.
2. **`X-Locale: vi`** — the header the web client sets on every request.
3. **`Accept-Language`** — for direct API callers.
4. English.

The query parameter comes first, and exists at all, because **a header alone leaves both languages
sharing one URL**. Anything that caches by URL — a CDN, a browser, Next.js's build-time fetch cache
— will then serve one language's response for the other. That is not hypothetical: it baked the
English footer into the prerendered Vietnamese pages until the parameter was added. Two languages
are two resources, so they get two URLs. `apiFetch` appends it to every request.

Server components must pass the locale **explicitly**. One Next.js process serves both languages,
so there is no ambient "current locale" to read on the server; the module-level `clientLocale` is
only correct in the browser.

## Where the Vietnamese lives

| Content | Source |
|---|---|
| Curriculum (subjects, courses, units, topics, skills, questions, lessons) | `content/<subject>/i18n/vi.yaml` |
| Marketing (tutoring products, classes, testimonials, blog, teachers, site settings) | `services/api/app/seed/marketing_vi.py` |
| Interface | `apps/web/src/messages/vi.json` |
| Grading feedback and recommender reasons | `services/api/app/exercise_engine/feedback.py` |

The curriculum sidecars are keyed by slug and mirror the authored English YAML, so the English
files keep their hand-written comments and structure. Lesson bodies use a **positional overlay**:
the translation supplies only prose fields, and everything structural — block type, interactive
widget config, which skill a practice block points at — is copied from the original. An empty `{}`
leaves a block untouched.

Both are applied by the seed and land in the `i18n` column, after which they are ordinary
translations an administrator can edit.

## Authoring in the admin CMS

Administrators type Vietnamese **directly**. There is no machine translation anywhere in this
system, at save time or at request time.

Every admin write endpoint for a translatable model accepts a `translations` object beside the
English fields, and every read returns the same shape, so one form round-trips both languages:

```json
{
  "title": "Mathematics — Grade 6",
  "translations": {"vi": {"title": "Toán học — Lớp 6", "summary": "…"}}
}
```

Rules the API enforces rather than trusting the UI:

* Omitting `translations` leaves existing translations alone — a PATCH of one field must not wipe
  the Vietnamese.
* `null` clears a field, and a locale left with no fields is dropped entirely, so clearing falls
  back to English rather than showing an empty string.
* `translations.en` is rejected: English lives in the columns, and a shadow copy `localise` never
  reads would mean silently discarded edits.
* An unknown locale or a non-whitelisted field is a 422, not a silent no-op. A typo in the
  translation form must fail loudly rather than leave a page mysteriously in English.

Lesson translations follow the same draft/publish split as the English body: a translator editing a
live lesson writes to `i18n.vi.draft_blocks`, and publishing promotes every language at once.

The question editor can preview a variant in either language at the same seed, which is the only
way to check that Vietnamese prose still reads well with real numbers substituted in.

## Adding a language

1. Add the code to `SUPPORTED_LOCALES` in `app/core/i18n.py`.
2. Add a dictionary at `apps/web/src/messages/<code>.json`.
3. Add a column to the tables in `app/exercise_engine/feedback.py`.
4. Translate content through the CMS, or add `content/<subject>/i18n/<code>.yaml`.

No migration, and no change to any grader, generator or read path.

## Tests

`services/api/tests/test_localisation.py` covers the primitives, the public read path, the
authoring API and the properties that matter most: that a translated question keeps the same
answer, that a translated multiple-choice question cannot move which option is correct, that
clearing a translation falls back to English, and that `/en` is unchanged throughout. The English
assertion sits next to the Vietnamese one in nearly every test, because a localisation change that
breaks English is a regression rather than a trade-off.
