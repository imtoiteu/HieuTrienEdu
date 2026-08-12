"""Bayesian Knowledge Tracing.

BKT (Corbett & Anderson, 1995) models a student's knowledge of one skill as a hidden binary state
— *known* or *not known* — that we can only observe indirectly through right and wrong answers.
Four parameters describe the skill:

===============  ===========================================================================
``p_init``       P(the student already knows the skill before any practice)
``p_transit``    P(the skill is learned on this practice opportunity, given it was not known)
``p_slip``       P(a wrong answer despite knowing the skill) — a careless error
``p_guess``      P(a right answer despite not knowing the skill) — a lucky guess
===============  ===========================================================================

Each answer updates the belief in two steps.

**1. Condition on the observation** (Bayes' rule). Writing :math:`L` for P(known before this
answer):

    correct:    posterior = L(1 - slip) / [ L(1 - slip) + (1 - L)·guess ]
    incorrect:  posterior = L·slip      / [ L·slip      + (1 - L)(1 - guess) ]

**2. Account for learning.** Even a wrong answer is a practice opportunity, so the student may
have learned the skill from it:

    P(known next) = posterior + (1 - posterior)·transit

Why BKT rather than something simpler or fancier:

* A running percentage cannot distinguish a lucky guess from real knowledge, and it treats a
  wrong answer after ten right ones as heavily as the first one.
* Deep-knowledge-tracing models need far more data than a new tutoring centre has, and cannot
  explain *why* a student was recommended a skill. BKT's state is one interpretable number.

**Guessing correction.** The classic model uses a single ``p_guess`` per skill, but the real
guess probability depends on the question: a 4-option multiple choice is guessable one time in
four, while a free-response numeric answer is not. We therefore adjust ``p_guess`` per attempt
based on question type — see ``effective_guess_probability``. This is a documented deviation from
textbook BKT, and it matters: without it, a student clicking randomly through multiple choice
converges to "mastered".
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import QuestionType

__all__ = [
    "BKTParameters",
    "BKTUpdate",
    "update_mastery",
    "effective_guess_probability",
    "MASTERY_THRESHOLD",
    "STRUGGLING_THRESHOLD",
]

# A skill counts as mastered at this posterior. 0.95 is the value used across the BKT literature
# and by OATutor; it typically corresponds to 4-6 consecutive correct answers from a cold start.
MASTERY_THRESHOLD = 0.95

# Below this, the student needs support rather than more of the same practice.
STRUGGLING_THRESHOLD = 0.40

# Learning credit applied after an incorrect attempt, as a fraction of the skill's transit rate.
# See the comment in update_mastery for why this is not 1.0.
INCORRECT_TRANSIT_FACTOR = 0.5

# Clamp the posterior away from the asymptotes. At exactly 0 or 1 the Bayes update becomes a
# fixed point — no future evidence could ever move the estimate again, so a student who got
# unlucky early would be permanently stuck.
_MIN_P = 0.001
_MAX_P = 0.999

# Roughly 1/(number of options) for the guessable types. Free-response types keep the skill's own
# (low) guess parameter, since guessing a numeric answer is essentially impossible.
_GUESS_FLOOR_BY_TYPE = {
    QuestionType.MULTIPLE_CHOICE: 0.25,
    QuestionType.TRUE_FALSE: 0.50,
    QuestionType.MULTIPLE_SELECT: 0.10,
    QuestionType.ORDERING: 0.15,
    QuestionType.MATCHING: 0.10,
}


@dataclass(frozen=True)
class BKTParameters:
    p_init: float = 0.10
    p_transit: float = 0.08
    p_slip: float = 0.15
    p_guess: float = 0.28

    def validated(self) -> BKTParameters:
        """Clamp parameters into a sane range.

        ``slip + guess >= 1`` makes the model degenerate — evidence would push the estimate the
        wrong way — so we also guard against that, which is easy to trip when hand-tuning a skill.
        """
        p_slip = min(max(self.p_slip, 0.001), 0.45)
        p_guess = min(max(self.p_guess, 0.001), 0.45)
        return BKTParameters(
            p_init=min(max(self.p_init, _MIN_P), _MAX_P),
            p_transit=min(max(self.p_transit, 0.001), 0.9),
            p_slip=p_slip,
            p_guess=p_guess,
        )

    @classmethod
    def from_skill(cls, skill) -> BKTParameters:  # noqa: ANN001 - avoids a circular import
        return cls(
            p_init=skill.bkt_p_init,
            p_transit=skill.bkt_p_transit,
            p_slip=skill.bkt_p_slip,
            p_guess=skill.bkt_p_guess,
        ).validated()


@dataclass(frozen=True)
class BKTUpdate:
    prior: float
    posterior: float          # after conditioning on the observation, before the learning step
    mastery: float            # after the learning step — the value to persist
    is_mastered: bool
    guess_used: float


def effective_guess_probability(
    base_guess: float,
    question_type: str | None,
    *,
    choice_count: int | None = None,
) -> float:
    """Raise ``p_guess`` to at least the floor implied by the question format."""
    if not question_type:
        return base_guess
    try:
        resolved = QuestionType(question_type)
    except ValueError:
        return base_guess

    floor = _GUESS_FLOOR_BY_TYPE.get(resolved)
    if floor is None:
        return base_guess
    if resolved is QuestionType.MULTIPLE_CHOICE and choice_count and choice_count > 1:
        floor = 1.0 / choice_count
    # Never exceed 0.45, or the model stops being able to learn from correct answers at all.
    return min(max(base_guess, floor), 0.45)


def update_mastery(
    prior: float,
    is_correct: bool,
    parameters: BKTParameters,
    *,
    question_type: str | None = None,
    choice_count: int | None = None,
    hints_used: int = 0,
) -> BKTUpdate:
    """Apply one BKT update and return the full trace.

    ``hints_used`` discounts the evidential value of a correct answer: getting there after three
    hints is not the same as getting there unaided. We model that by inflating the guess
    probability, which is the mathematically natural place for "they may have got this right
    without knowing it".
    """
    params = parameters.validated()
    prior = min(max(prior, _MIN_P), _MAX_P)

    guess = effective_guess_probability(params.p_guess, question_type, choice_count=choice_count)
    if is_correct and hints_used > 0:
        guess = min(0.45, guess + 0.12 * min(hints_used, 3))

    slip = params.p_slip

    if is_correct:
        numerator = prior * (1.0 - slip)
        denominator = numerator + (1.0 - prior) * guess
    else:
        numerator = prior * slip
        denominator = numerator + (1.0 - prior) * (1.0 - guess)

    # Defensive: denominator is only zero if the parameters were degenerate, which validated()
    # should already prevent. Falling back to the prior is the neutral choice.
    posterior = prior if denominator <= 0 else numerator / denominator

    # Textbook BKT applies the full learning term after *any* attempt, on the reasoning that the
    # attempt was itself a practice opportunity. At low mastery that term outweighs the negative
    # evidence: a student sitting at 0.100 who answers incorrectly comes out at 0.101.
    #
    # That is defensible as a model and indefensible as a product. Telling a student their mastery
    # went *up* after getting a question wrong destroys trust in the number, and a parent reading
    # the same figure would rightly call it nonsense.
    #
    # So we apply a reduced learning rate on an incorrect attempt. The student did have a practice
    # opportunity and will read the worked solution, so some learning credit is right — but less
    # than for an attempt they actually got right. The clamp underneath then guarantees the
    # property outright, including at the very bottom of the range where the reduced rate alone
    # would not. Both are deliberate, documented deviations — see docs/ADAPTIVE_LEARNING.md.
    transit = params.p_transit if is_correct else params.p_transit * INCORRECT_TRANSIT_FACTOR
    mastery = posterior + (1.0 - posterior) * transit

    if not is_correct:
        mastery = min(mastery, prior)

    mastery = min(max(mastery, _MIN_P), _MAX_P)

    return BKTUpdate(
        prior=prior,
        posterior=posterior,
        mastery=mastery,
        is_mastered=mastery >= MASTERY_THRESHOLD,
        guess_used=guess,
    )


def decay_mastery(mastery: float, days_since_practice: float, *, half_life_days: float = 45.0)\
        -> float:
    """Apply forgetting.

    Standard BKT has no forgetting term — once learned, always learned — which is plainly wrong
    for a student who last touched fractions four months ago. We decay the *excess* mastery above
    ``p_init`` on an exponential half-life, so a long-idle skill drifts back toward "needs review"
    without ever falling below the baseline a fresh student would start at.
    """
    if days_since_practice <= 0:
        return mastery
    baseline = 0.15
    if mastery <= baseline:
        return mastery
    retained = 0.5 ** (days_since_practice / half_life_days)
    return baseline + (mastery - baseline) * retained
