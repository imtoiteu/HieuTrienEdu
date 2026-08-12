# Adaptive Learning

Implementation: `services/api/app/adaptive/bkt.py` and `recommender.py`.

## The model

We use **Bayesian Knowledge Tracing** (Corbett & Anderson, 1995). It models a student's knowledge
of one skill as a hidden binary state — *known* or *not known* — observable only indirectly through
right and wrong answers.

Four parameters describe each skill:

| Parameter | Meaning | Default |
|---|---|---|
| `p_init` | P(the student already knows it before any practice) | 0.10 |
| `p_transit` | P(it is learned on this practice opportunity, given it was not known) | 0.08 |
| `p_slip` | P(a wrong answer despite knowing it) — a careless error | 0.15 |
| `p_guess` | P(a right answer despite not knowing it) — a lucky guess | 0.28 |

They are stored per skill (`skills.bkt_*`), so a fiddly skill like dividing fractions can carry a
higher slip probability than a mechanical one like reading a thermometer.

### The update

Each answer updates the belief in two steps. Writing $L$ for P(known before this answer):

**1. Condition on the observation** (Bayes' rule):

$$P(L \mid \text{correct}) = \frac{L(1 - P_{\text{slip}})}{L(1 - P_{\text{slip}}) + (1 - L)P_{\text{guess}}}$$

$$P(L \mid \text{incorrect}) = \frac{L \cdot P_{\text{slip}}}{L \cdot P_{\text{slip}} + (1 - L)(1 - P_{\text{guess}})}$$

**2. Account for learning during the attempt:**

$$P(L_{t+1}) = P(L \mid \text{obs}) + \bigl(1 - P(L \mid \text{obs})\bigr) \cdot P_{\text{transit}}$$

### Why BKT

- **A running percentage cannot tell a lucky guess from knowledge.** It also treats a wrong answer
  after ten right ones as heavily as the first one.
- **Deep knowledge tracing** needs far more data than a new tutoring centre has, and cannot explain
  *why* a student was recommended a skill. BKT's state is one interpretable number, which matters
  when a parent asks what it means.

## Our three deviations, and why

Each is a deliberate departure from the textbook model. They are listed here because a model you
cannot audit is a model nobody should trust.

### 1. Guess probability depends on question type

The classic model uses one `p_guess` per skill. But a four-option multiple choice is guessable one
time in four, while a free-response numeric answer essentially is not.

```
multiple_choice   floor 1/(number of options), typically 0.25
true_false        floor 0.50
ordering          floor 0.15
multiple_select   floor 0.10
matching          floor 0.10
numeric, expression, short_answer, fill_blank   the skill's own (low) value
```

Without this, a student clicking randomly through multiple choice converges to "mastered". The
floor is capped at 0.45, above which correct answers stop being able to raise the estimate at all.

### 2. Hints discount a correct answer

Reaching the answer after three hints is not the same as reaching it unaided. We model that by
inflating the guess probability (`+0.12` per hint, up to three), which is the mathematically
natural place for "they may have got this right without knowing it".

There is a test asserting a hinted correct answer moves mastery less than an unhinted one.

### 3. A wrong answer never increases mastery

This one is a product decision as much as a modelling one.

Textbook BKT applies the full learning term after *any* attempt, on the reasoning that the attempt
was itself a practice opportunity. At low mastery that term outweighs the negative evidence: a
student sitting at 0.100 who answers **incorrectly** comes out at **0.101**.

That is defensible as a model and indefensible as a product. Telling a student their mastery went
*up* after getting a question wrong destroys trust in the number, and a parent reading the same
figure would rightly call it nonsense.

So:

- an incorrect attempt applies learning at **half** the transit rate (`INCORRECT_TRANSIT_FACTOR`),
  since the student did have a practice opportunity and will read the worked solution;
- and the result is clamped so it can never exceed the prior, which guarantees the property at the
  very bottom of the range where the reduced rate alone would not.

### Forgetting

Standard BKT has no forgetting term — once learned, always learned — which is plainly wrong for a
student who last touched fractions four months ago.

`decay_mastery()` decays the *excess* mastery above a 0.15 baseline on a 45-day exponential
half-life. A long-idle skill drifts back toward "needs review" without ever falling below where a
fresh student would start.

## Mastery threshold

A skill is **mastered** at posterior ≥ **0.95** — the value used across the BKT literature and by
OATutor. With our defaults that is about **five consecutive correct answers** from a cold start:

```
start  0.100
  #1   0.312
  #2   0.613
  #3   0.842
  #4   0.946
  #5   0.983  ← mastered
```

Below **0.40** (`STRUGGLING_THRESHOLD`) a student needs support rather than more of the same.

## Recommendation engine

`recommend_next()` scores every in-scope skill and returns the top N.

### Prerequisite gating

The rule that shapes everything: **never recommend a skill whose prerequisites are demonstrably
missing.** OATutor's heuristic picks the single lowest-mastery skill, which is a good idea taken one
step too far — the lowest-mastery skill is very often the one the student is not ready for.

When a skill is blocked, we walk *down* the graph and recommend the weakest missing prerequisite
instead, with `reason: prerequisite_gap`.

Crucially, we distinguish two cases:

| Prerequisite state | Effect |
|---|---|
| Attempted, mastery < 0.60 | **Blocks.** Real evidence the student is not ready |
| Never attempted | **Does not block.** Small score penalty only |

Treating both as blocking was a genuine bug found by running the seeded data: every skill in the
curriculum ultimately depends on some grade 6 foundation, so a new grade 8 student found
*everything* locked and was recommended nothing but the most elementary skills on the platform. A
grade 8 student has almost certainly met grade 6 place value at school, even though our database has
no record of it.

### Scoring

For an unblocked, unmastered skill:

```
score  = 1.20 × (0.95 − mastery)          mastery gap — the dominant term
       + 0.35 × readiness                 prefer skills they are equipped for
       + 0.45 × recent_error_rate         recent mistakes jump the queue
       + 0.20 if already started          finishing beats starting something new
       + 0.15 × (5 − difficulty)/4        when struggling, prefer easier skills
       − 0.08 × unassessed_prerequisites  mild penalty, capped at 3
```

Mastered skills are excluded unless they have gone stale (14+ days), in which case they resurface
with `reason: review_due` and a lower score.

Reason codes returned to the UI: `prerequisite_gap`, `weak_skill`, `in_progress`, `new_skill`,
`review_due`.

## Learning path

`build_learning_path()` returns the skills of one unit tagged `mastered`, `in_progress`,
`available` or `locked`.

The locking rule mirrors the recommender with one addition: an unassessed prerequisite **inside the
same unit** still locks, so the path reads as a sequence a student works through. An unassessed
prerequisite from another grade does not, because locking it would make a freshly opened course look
broken.

## Question selection

`_target_difficulty()` picks a level just above current mastery — practising at the edge of ability
is where learning happens, and questions that are far too easy or far too hard both waste time:

| Mastery | Target difficulty |
|---|---|
| < 0.25 | 1 |
| < 0.50 | 2 |
| < 0.75 | 3 |
| < 0.90 | 4 |
| ≥ 0.90 | 5 |

The search widens outward (0, −1, +1, −2, +2, any) until a question is found, and templates already
seen in the current session are excluded.

## Prior art

The BKT update formula and the mastery-threshold selection heuristic were informed by
[OATutor](https://github.com/CAHLR/OATutor) (UC Berkeley CAHLR, MIT licensed). The update itself is
the standard Corbett & Anderson formulation rather than OATutor's invention, and our implementation
is written from the model definition — but the project is credited here as the prior art that shaped
the design.

## What is not implemented

- **No per-skill parameter fitting.** The BKT parameters are hand-set defaults, not learned from
  data. With enough attempts, expectation-maximisation over the attempt log would fit them per
  skill. The `attempts` table already records everything needed.
- **No item response theory.** Question difficulty is an author-assigned 1–5 integer, not a fitted
  IRT parameter. `questions.times_served` / `times_correct` are accumulating the data that would be
  needed.
- **No spaced-repetition scheduling.** Forgetting is modelled, but nothing proactively schedules a
  review session; stale skills only resurface when the student asks for a recommendation.
