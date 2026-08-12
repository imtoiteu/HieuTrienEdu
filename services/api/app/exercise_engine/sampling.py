"""Deterministic sampling of template variables under constraints.

The contract that everything else depends on:

    same (question template, seed)  ->  byte-identical variable draw

That is what makes it safe to send a student a question with only its ``seed``, and regenerate the
correct answer server-side at grading time. The client never holds the answer, and never needs to
send anything back except its own input and the seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.exercise_engine.safe_eval import ExpressionError, evaluate, evaluate_bool

__all__ = ["SamplingError", "VariableSpec", "sample_variables", "MAX_SAMPLING_ATTEMPTS"]

# Rejection sampling budget. A template whose constraints are satisfiable by, say, 1 in 50 draws
# will succeed comfortably; a template that exhausts this budget is almost certainly mis-authored,
# and we want that to surface as a loud error at seed time rather than a silent bad question.
MAX_SAMPLING_ATTEMPTS = 400


class SamplingError(RuntimeError):
    """Raised when no variable assignment satisfying the constraints could be found."""


@dataclass(frozen=True)
class VariableSpec:
    """One entry of a template's ``variables`` map."""

    name: str
    kind: str = "int"  # int | float | choice | derived
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    decimals: int | None = None
    choices: list[Any] = field(default_factory=list)
    exclude: list[Any] = field(default_factory=list)
    expression: str | None = None  # for kind == "derived"

    @classmethod
    def from_dict(cls, name: str, raw: dict[str, Any]) -> VariableSpec:
        if not isinstance(raw, dict):
            raise SamplingError(f"Variable {name!r} must be defined by an object")
        kind = str(raw.get("type", "int")).lower()
        if kind not in {"int", "float", "choice", "derived"}:
            raise SamplingError(f"Variable {name!r} has unsupported type {kind!r}")

        spec = cls(
            name=name,
            kind=kind,
            minimum=raw.get("min"),
            maximum=raw.get("max"),
            step=raw.get("step"),
            decimals=raw.get("decimals"),
            choices=list(raw.get("choices", []) or []),
            exclude=list(raw.get("exclude", []) or []),
            expression=raw.get("expression") or raw.get("expr"),
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        if self.kind == "choice":
            if not self.choices:
                raise SamplingError(f"Variable {self.name!r} of type 'choice' needs 'choices'")
        elif self.kind == "derived":
            if not self.expression:
                raise SamplingError(f"Variable {self.name!r} of type 'derived' needs 'expression'")
        else:
            if self.minimum is None or self.maximum is None:
                raise SamplingError(f"Variable {self.name!r} needs both 'min' and 'max'")
            if self.minimum > self.maximum:
                raise SamplingError(f"Variable {self.name!r} has min greater than max")
            if self.step is not None and self.step <= 0:
                raise SamplingError(f"Variable {self.name!r} has a non-positive step")

    def draw(self, rng: random.Random) -> Any:
        if self.kind == "choice":
            return rng.choice(self.choices)

        if self.kind == "int":
            low, high = int(self.minimum), int(self.maximum)  # type: ignore[arg-type]
            step = int(self.step) if self.step else 1
            # Draw over the number of steps rather than the raw range so that `step` is honoured
            # exactly — randrange with a step can drift when the range isn't a multiple of it.
            steps = (high - low) // step
            return low + step * rng.randint(0, max(steps, 0))

        low_f, high_f = float(self.minimum), float(self.maximum)  # type: ignore[arg-type]
        if self.step:
            steps = int((high_f - low_f) / float(self.step))
            value = low_f + float(self.step) * rng.randint(0, max(steps, 0))
        else:
            value = rng.uniform(low_f, high_f)
        return round(value, self.decimals if self.decimals is not None else 2)


def parse_specs(variables: dict[str, Any]) -> list[VariableSpec]:
    """Parse the raw ``variables`` map, preserving declaration order.

    Order matters: a ``derived`` variable may reference any variable declared before it.
    Python dicts preserve insertion order, and both YAML and JSON loading preserve document order,
    so declaration order in the content file is the evaluation order here.
    """
    return [VariableSpec.from_dict(name, raw) for name, raw in (variables or {}).items()]


def sample_variables(
    variables: dict[str, Any],
    constraints: list[str] | None = None,
    *,
    seed: int,
) -> dict[str, Any]:
    """Return one constraint-satisfying assignment, deterministic in ``seed``."""
    specs = parse_specs(variables)
    if not specs:
        return {}

    constraints = [c for c in (constraints or []) if str(c).strip()]
    rng = random.Random(seed)
    last_error: str | None = None

    for _ in range(MAX_SAMPLING_ATTEMPTS):
        namespace: dict[str, Any] = {}
        rejected = False

        for spec in specs:
            if spec.kind == "derived":
                try:
                    value = evaluate(spec.expression or "", namespace)
                except ExpressionError as exc:
                    # A broken derived expression is an authoring bug, not bad luck — no amount
                    # of resampling will fix it, so fail immediately with a useful message.
                    raise SamplingError(
                        f"Derived variable {spec.name!r} failed to evaluate: {exc}"
                    ) from exc
            else:
                value = spec.draw(rng)

            if spec.exclude and value in spec.exclude:
                rejected = True
                break
            namespace[spec.name] = value

        if rejected:
            continue

        try:
            if all(evaluate_bool(constraint, namespace) for constraint in constraints):
                return namespace
        except ExpressionError as exc:
            # Constraints can legitimately fail on some draws (e.g. a division inside the
            # constraint hitting zero), so record and resample rather than aborting.
            last_error = str(exc)
            continue

    detail = f" Last error: {last_error}" if last_error else ""
    raise SamplingError(
        f"Could not satisfy constraints {constraints} within {MAX_SAMPLING_ATTEMPTS} attempts."
        f"{detail} Check that the ranges and constraints are compatible."
    )
