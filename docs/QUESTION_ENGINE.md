# Question Engine

Implementation: `services/api/app/exercise_engine/`.

## The idea

A question in HieuTrienEducation is a **template**, not a fixed item. One template generates
thousands of distinct, mathematically valid variants:

```yaml
prompt: "A car travels {{distance}} km in {{time}} hours. What is its average speed?"
variables:
  time:     {type: int, min: 2, max: 8}
  distance: {type: int, min: 20, max: 400, step: 10}
constraints:
  - "distance % time == 0"          # keeps the answer a whole number
answer: {expression: "distance / time", unit: "km/h"}
```

A student cannot memorise the answer, so the only way through is the method. It also means the
question bank is 186 templates rather than 186 questions.

A template with no `variables` is simply a static question — the same code path, so there is never
a "parametric version" and a "normal version" of anything to keep in sync.

## The contract everything rests on

```
same (template, seed)  →  byte-identical variant
```

Sampling is driven by `random.Random(seed)`, so the server can regenerate exactly what a student
saw from `(question_id, seed)` alone. That is what makes it safe to send a question without its
answer: grading regenerates rather than trusting anything the client returns.

This idea came from studying OpenStax Exercises, whose `LogicVariable` model blacklists `seedrandom`
as a variable name — revealing that their variants are seeded too. It was the single most valuable
finding of the open-source research.

## Pipeline

```
QuestionTemplate
      │
      ├─ sample_variables()   draw variables, reject draws failing constraints
      │
      ├─ render_template()    resolve {{ … }} placeholders in prompt, hints, solution
      │
      ├─ builder per type     produce the student-facing payload and the answer
      │
      └─▶ GeneratedVariant { rendered, answer, hints, solution }
```

`rendered` and `answer` are **separate dictionaries**, not one dictionary with a "do not send this
key" rule. A mistake in a serialiser therefore cannot leak the answer — the student-facing schema
simply has no field for it.

## Variable types

| Type | Fields | Notes |
|---|---|---|
| `int` | `min`, `max`, `step`, `exclude` | Draws over the number of steps so `step` is honoured exactly |
| `float` | `min`, `max`, `step`, `decimals` | |
| `choice` | `choices` | Picks one |
| `derived` | `expression` | Computed from variables declared **before** it |

Declaration order is evaluation order, which both YAML and JSON preserve.

### Constraints

Boolean expressions every draw must satisfy:

```yaml
constraints:
  - "distance % time == 0"
  - "gcd(numerator, denominator) == 1"
  - "a + b < d"
```

Rejection sampling with a budget of 400 attempts. A template that exhausts it is almost certainly
mis-authored, so it raises loudly at seed time rather than silently producing a bad question. A
broken *derived* expression fails immediately — no amount of resampling fixes a typo.

## Placeholder syntax

`{{ expression }}`, optionally with a decimal count: `{{ distance/time : 2 }}`.

Double braces rather than `str.format`, because question text is full of LaTeX and LaTeX is full of
single braces — `\frac{a}{b}` would make `str.format` throw or silently misinterpret.

The regex requires the placeholder body to contain **no braces at all**, which has a pleasant side
effect: in `\frac{{{distance}}}{{{time}}}` the engine matches the *inner* `{{distance}}` and leaves
the outer LaTeX braces intact, so authors write nested LaTeX naturally.

## Question types

All nine, each with its own builder and grader:

| Type | Student payload | Answer | Partial credit |
|---|---|---|---|
| `multiple_choice` | `choices[]` | `choice_id` | — |
| `multiple_select` | `choices[]` | `choice_ids[]` | Yes |
| `numeric` | `unit`, `decimals` | `value`, `tolerance` | — |
| `expression` | `symbols` | `expression` | — |
| `fill_blank` | `blanks[]` | per-blank answers | Yes |
| `true_false` | — | `value` | — |
| `matching` | `left[]`, shuffled `right[]` | `mapping` | Yes |
| `ordering` | shuffled `items[]` | `order[]` | Yes |
| `short_answer` | `placeholder` | `accepted[]`, `keywords` | Keyword mode |

Choice order is shuffled with a **seeded** shuffle, so a student who reloads sees the same order —
otherwise "the third one" changes meaning mid-question and looks broken.

For `ordering`, the presented order is guaranteed to differ from the answer, or the question is free.

## Distractors

A multiple-choice question is only as good as its wrong answers. Random noise around the correct
value teaches nothing — a student eliminates it by estimation. Distractors that encode the mistakes
students *actually make* turn each question into a diagnostic: which option they pick tells you
which misconception they hold.

Priority order:

1. **Author-supplied expressions.** `distractors: ["time / distance"]` on a speed question encodes
   "inverted the formula" — exactly the error worth detecting.
2. **Structural mistakes** inferred from the answer expression: swapping the operands of a
   non-commutative operation (`a / b` → `b / a`), or using the inverse operation.
3. **Magnitude and arithmetic slips**: factor of ten, off-by-one, sign flip, doubling. Weakest, used
   only to top up a short list.

Duplicates and the correct value are excluded, and the list is never short — a UI rendering three
options when it expected four is a bug the student sees.

## Grading

Every grader is a pure function `(answer, user_answer, rendered) -> GradeResult`. This shape is
borrowed from Perseus's `perseus-score` package, whose separation of scoring from rendering is the
best idea in that codebase — and the reason grading here needs no UI.

### Numeric input

Tolerant but unambiguous. The decimal-separator problem is handled **structurally** rather than by
guessing from a locale header the student may not match:

| Input | Reading | Rule |
|---|---|---|
| `1,5` | 1.5 | only commas, not in groups of three → decimal separator |
| `1,000` | 1000 | only commas, in groups of three → thousands |
| `1.234,56` | 1234.56 | both present, comma last → comma is decimal |
| `1,234.56` | 1234.56 | both present, dot last → dot is decimal |
| `3/4` | 0.75 | fractions are a legitimate numeric answer |
| `45%` | 45 | a question asking for a percentage wants the number |

Tolerance is **relative by default** so it scales with magnitude, with an absolute floor so answers
near zero still work.

Feedback names the mistake where it can: a factor-of-ten error is the most common numeric slip, and
"your answer is ten times too large — check your units or decimal point" is far more useful than
"incorrect".

### Algebraic expressions

SymPy, so `2(x+3)` is accepted against `2x + 6`. Primary test is `simplify(a - b) == 0`, with a
numeric-sampling fallback at several probe points for expressions `simplify` cannot reduce.

### Partial credit

Awarded wherever a question has independently checkable parts — "you got 3 of 4 pairs right" is
better feedback than a flat wrong, and it gives the mastery model a more honest signal.

- **Multiple select**: `(hits − false_positives) / expected`, floored at zero. Without the penalty,
  selecting every option would score 100%.
- **Ordering**: adjacent-pair agreement, not exact position. A student whose sequence is right but
  shifted by one has understood the ordering; position matching would score that zero.
- **Matching / fill-blank**: fraction correct.

`is_correct` is then derived from the score (≥ 0.999), so the flag the mastery model reads can never
disagree with the score the student sees.

## Security

Templates are data. They come from the database, teachers can author them, and eventually so will an
AI. Data that reaches `eval()` is a remote code execution bug waiting to happen.

### Author expressions: AST whitelist

`safe_eval.py` parses to an AST and walks it, rejecting any node type not on the whitelist.
Anything unrecognised raises rather than being skipped, so the failure mode is "template is broken"
rather than "template did something unexpected".

Rejected, with tests for each: `__import__('os').system(...)`, `().__class__.__bases__`, `open(...)`,
lambdas, comprehensions, `exec`, `eval`, `globals()`, attribute access. Only bare names may be
called, which blocks the entire attribute-traversal family. Exponents are capped at 64 and results at
1e15, so `9**9**9` cannot hang a worker.

### Student expressions: character whitelist before SymPy

`sympy.parse_expr` is **not** safe on untrusted input — it ultimately calls `eval` on a transformed
token stream. Student answers are untrusted by definition, so every input passes a strict
character and word whitelist first. Notably absent from the allowed characters: `_`, `[`, `]`, `.`,
quotes and `;` — the building blocks of dunder access and statements.

SymPy's namespace is also restricted to symbolic constructors plus the allowed function names, so
even a bypass of the character filter has nothing useful to reach.

## Authoring

Content lives in `content/<subject>/questions/<course>.yaml`:

```yaml
defaults:
  license: proprietary
  source: HieuTrienEducation
  status: published

questions:
  - slug: m7-two-step-equation
    skill: math-7-two-step-equations
    type: numeric
    difficulty: 2
    prompt: "Solve for x:   {{a}}x + {{b}} = {{c}}"
    variables:
      a: {type: int, min: 2, max: 12}
      x: {type: int, min: -8, max: 15}
      b: {type: int, min: -20, max: 20, exclude: [0]}
      c: {type: derived, expression: "a*x + b"}
    answer: {expression: "(c - b) / a"}
    options:
      distractors: ["(c + b) / a", "c / a - b"]
    hints:
      - text: "First undo the {{b}} by subtracting it from both sides."
      - text: "Then divide both sides by {{a}}."
    solution:
      - text: "{{a}}x = {{c}} - ({{b}}) = {{c - b}}."
      - text: "x = {{c-b}} ÷ {{a}} = {{(c-b)/a}}."
```

Note the pattern of working backwards from the answer: draw `x` and `b`, then *derive* `c`. That
guarantees a clean solution rather than hoping constraints produce one.

The loader validates every template across **four different seeds** before writing it, because a
template can pass on seed 1 and fail on seed 2 if its constraints are only sometimes satisfiable.
Invalid templates are reported and skipped — a broken template in the bank becomes a 500 in front of
a student mid-session.

Teachers authoring through the API get the same validation: `POST /teacher/questions` generates a
variant before saving and returns 422 with the reason if it fails.

## Import and export

`scripts/` contains converters for other formats:

| Format | Status |
|---|---|
| Moodle GIFT | Import and export — multiple choice, true/false, numeric, short answer, matching |
| IMS QTI 2.1 | Partial import — `choiceInteraction` and `textEntryInteraction` only |
| Perseus JSON | Mapper for `radio`, `numeric-input` and `expression` widgets |
| OpenStax API | Mapper written, **no content shipped** — requires a live pull the operator initiates |

`scripts/import_open_content.py` enforces a licence allowlist (`CC-BY-4.0`, `CC-BY-SA-4.0`,
`CC0-1.0`, `PUBLIC-DOMAIN`) and **refuses** anything outside it. Imported rows keep their `source`,
`license` and `attribution`.

No third-party content is bundled in this repository — see [CONTENT_LICENSES.md](CONTENT_LICENSES.md).

## Testing

69 of the 111 backend tests target the engine directly, with no database: determinism, constraint
satisfaction, LaTeX survival through templating, mathematical correctness of generated answers
across many seeds, every grader, partial-credit arithmetic, the decimal-separator matrix, and a
parametrised suite of injection attempts against both evaluators.
