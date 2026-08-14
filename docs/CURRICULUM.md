# Curriculum

## The hierarchy

```
Subject          Mathematics · Physics
  └── Course     one per grade — "Mathematics — Grade 7"
      └── Unit   "Fractions and Decimals"
          └── Topic   "Fraction Operations"
              └── Skill   "Adding and subtracting fractions"
                  ├── Lesson    explanation, worked examples, practice
                  └── Question  templates that test this skill
```

The hierarchy is **strict**: every question hangs off exactly one skill, and every skill off
exactly one topic. That is what lets the system always answer the question the whole adaptive
model depends on — *which skill does this question test?*

## What is built

| | Mathematics | Physics | Total |
|---|---|---|---|
| Courses (grades 6–9) | 4 | 4 | **8** |
| Units | 18 | 16 | **34** |
| Topics | 36 | 26 | **62** |
| Skills | 89 | 72 | **161** |
| Prerequisite edges | — | — | **195** |
| Question templates | 106 | 80 | **186** |
| Lessons | 7 | 7 | **14** |

**Every one of the 161 skills has at least one question template**, so practice never dead-ends —
there is a test asserting this.

### Mathematics

| Grade | Units |
|---|---|
| 6 | The Number System · Fractions and Decimals · Ratios, Rates and Percentages · Expressions and Equations · Geometry, Measurement and Data |
| 7 | Rational Numbers · Proportional Relationships · Expressions and Equations · Geometry · Probability and Statistics |
| 8 | Real Numbers and Indices · Linear Functions · Geometry and Pythagoras · Statistics |
| 9 | Algebraic Techniques · Quadratic Relationships · Trigonometry · Measurement and Statistics |

### Physics

| Grade | Units |
|---|---|
| 6 | Measurement · Matter · Forces and Motion · Energy |
| 7 | Motion · Pressure · Heat and Temperature · Light |
| 8 | Forces and Newton's Laws · Work, Energy and Power · Electricity · Waves and Sound |
| 9 | Motion and Momentum · Thermal Physics · Electromagnetism · Atomic and Nuclear Physics |

## The skill graph

Prerequisites are directed edges with a `strength`:

- **1.0** — a hard prerequisite. Gates the dependent skill.
- **below 0.75** — helpful but not blocking.

```
Equivalent fractions ──┐
                       ├──▶ Common denominators ──▶ Adding fractions ──▶ Mixed numbers
GCF and LCM ───────────┘
```

### Cross-subject edges

Physics skills declare prerequisites **into Mathematics**, which is one of the more useful things
the graph does:

```
physics-6-density-calc      requires  math-6-decimal-operations
physics-7-pressure-calc     requires  math-6-area-rectangles-triangles
physics-8-second-law        requires  math-7-two-step-equations
physics-9-specific-heat     requires  math-7-multi-step-equations
physics-9-suvat             requires  math-9-quadratic-formula
```

So when a student stalls on Newton's second law, the platform can tell whether the problem is the
physics or the algebra underneath it — and send them to the right place.

This is why the loader processes *all* subjects' curriculum files before any questions: a physics
skill's prerequisite may live in a mathematics file that has not been read yet.

## Authoring

Content lives in `content/` as YAML and is loaded by `app/content_io/loader.py`. Loading is
**idempotent and upsert-based**, keyed on slugs — re-running the seed after editing a file updates
rows in place rather than duplicating them, and crucially without destroying student attempt
history that references those rows.

```
content/
├── mathematics/
│   ├── curriculum/math-6.yaml …          subject, course, units, topics, skills
│   ├── lessons/math-lessons.yaml
│   ├── questions/math-6.yaml …
│   ├── resources/math-upper.yaml         further-reading links, by topic or lesson
│   ├── i18n/vi.yaml                      translations, keyed by entity kind and slug
│   └── i18n/vi/upper-*.yaml              the same, split across files and merged
└── physics/
    └── …
```

Files are read in sorted order within each directory, which is **not** curriculum order —
`math-10.yaml` sorts before `math-6.yaml`. Nothing may depend on that order: prerequisite edges
are therefore resolved in a final pass, once every skill in every subject and grade exists.

### Curriculum file

```yaml
subject:
  slug: mathematics
  name: Mathematics
  icon: sigma
  color: "#6D4AFF"

course:
  slug: math-7
  title: Mathematics — Grade 7
  grade: 7
  summary: Rational numbers, proportional reasoning and multi-step equations.
  estimated_hours: 75

units:
  - slug: math-7-algebra
    title: Expressions and Equations
    icon: variable
    topics:
      - slug: math-7-solving-equations
        title: Solving Equations and Inequalities
        skills:
          - slug: math-7-two-step-equations
            name: Two-step equations
            description: Solve equations of the form ax + b = c.
            difficulty: 2
            prerequisites: [math-6-one-step-add, math-6-one-step-multiply]
            related: [math-7-multi-step-equations]
            tags: [algebra, equations, core]
            # Optional per-skill BKT overrides
            # bkt_p_slip: 0.18
```

Slugs are the identity of everything. They must be globally unique per entity type and stable —
changing a slug creates a new row rather than renaming the old one.

A prerequisite may also be written as an object to set its strength:

```yaml
prerequisites:
  - math-6-one-step-add                       # strength 1.0, gates
  - {slug: math-6-order-of-operations, strength: 0.5}   # helpful, does not gate
```

Prerequisites are resolved in a **second pass**, so a skill may depend on one declared later in the
file or in another grade entirely. Unresolvable references are reported as errors rather than
skipped silently.

### Lesson file

A lesson is an ordered list of typed blocks. Blocks rather than one HTML blob, because the student
UI treats an `interactive` block very differently from a `text` block, and because a JSON array can
be reordered by a teacher editor without an HTML parser.

```yaml
lessons:
  - slug: lesson-math-8-gradient
    title: Gradient of a Straight Line
    topic: math-8-linear-graphs
    skill: math-8-gradient
    estimated_minutes: 22
    summary: Measuring steepness with a single number.
    objectives:
      - Calculate gradient from two points
      - Interpret positive, negative and zero gradients
    blocks:
      - {type: text, markdown: "The **gradient** measures how steep a line is.\n\n$$m = \\frac{y_2 - y_1}{x_2 - x_1}$$"}
      - {type: callout, variant: tip, title: Remember, text: "Rise over run."}
      - type: example
        title: Finding the gradient through (1, 3) and (5, 11)
        steps:
          - {text: "Rise: the change in y.", math: "11 - 3 = 8"}
          - {text: "Gradient.", math: "m = \\frac{8}{4} = 2"}
      - type: interactive
        widget: function-plot
        config:
          functions:
            - {expression: "2*x + 1", label: "y = 2x + 1", color: primary}
          xRange: [-6, 6]
          yRange: [-6, 8]
      - {type: table, headers: [Gradient, Meaning], rows: [["Positive", "Rises left to right"]]}
      - {type: practice, skill: math-8-gradient}
      - {type: summary, points: ["Gradient = rise ÷ run"]}
```

#### Block types

| Type | Fields |
|---|---|
| `text` | `markdown` — headings, bold, inline code, lists, `$…$` and `$$…$$` maths |
| `math` | `latex`, `caption` |
| `callout` | `variant` (`tip` / `warning` / `note`), `title`, `text` |
| `example` | `title`, `steps[]` of `{text, math}` |
| `table` | `headers[]`, `rows[][]` |
| `figure` | `shape` (`right-triangle`), `config` |
| `interactive` | `widget` (`function-plot`, `fraction-bars`, `number-line`, `geogebra`), `config` |
| `practice` | `skill`, `prompt` |
| `summary` | `points[]` |

An unknown block type renders nothing rather than crashing the lesson — content is data, and a
block type deployed before the frontend that understands it must degrade quietly.

Maths uses `$…$` for inline and `$$…$$` for display, rendered by KaTeX.

### Question file

See [QUESTION_ENGINE.md](QUESTION_ENGINE.md) for the full template format, which is the most
involved part of authoring.

## Loading

```bash
cd services/api
.venv/bin/python -m app.seed.seed            # upsert content + demo data
.venv/bin/python -m app.seed.seed --reset    # drop everything first
.venv/bin/python -m app.seed.seed --no-simulate   # skip the fake practice history
```

The loader:

1. Loads **all** subjects' curriculum first, so cross-subject prerequisites resolve.
2. Then lessons and questions, which reference skills by slug.
3. Validates every question template across **four seeds** before writing it. A template can pass
   on seed 1 and fail on seed 2 if its constraints are only sometimes satisfiable.
4. Reports every error with the file and slug, and exits non-zero if any occurred.

## Design decisions

**Why one course per grade rather than a continuous curriculum?**
Vietnamese schools organise by grade, parents ask "which grade is this for?", and a student
enrolling wants to see their grade. The skill graph then cuts across grades freely — a grade 8
student weak on fractions is sent to grade 6 skills without anything in the model objecting.

**Why difficulty 1–5 per skill *and* per question?**
The skill's difficulty is editorial — how hard the topic is in the curriculum. The question's is
operational — the adaptive engine picks a difficulty just above the student's current mastery, so
each skill needs questions spanning a range.

**Why are BKT parameters on the skill?**
A fiddly skill like dividing fractions genuinely has a higher slip rate than a mechanical one like
reading a thermometer. Defaults cover almost everything; overrides are there for the exceptions.

## Extending

**Adding a grade** — create `content/<subject>/curriculum/<course>.yaml` with the right
`course.grade`, declare prerequisites into the grade below, add questions, re-seed. Grades 6–12
exist for both subjects; nothing in the code assumes a particular range.

**Adding a subject** — create `content/chemistry/` with the same subdirectories. The loader
discovers subjects by directory. You will want to add a colour to `SUBJECT_THEME` in
`apps/web/src/lib/utils.ts`.

**Adding further reading** — put curated external links in `content/<subject>/resources/*.yaml`,
attached to a `topic` or a `lesson`. They appear under the lesson body, with their licence and
attribution shown, because most open sources are licensed on the condition that they are
credited. Record the licence you actually verified rather than the one you assume.

**Translating content** — both the interface *and* the content are internationalised. See
[LOCALISATION.md](LOCALISATION.md): translations live in `content/<subject>/i18n/`, are merged
into each row's `i18n` column at load time, and fall back to English field by field.
