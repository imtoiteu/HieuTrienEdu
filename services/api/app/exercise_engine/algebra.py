"""Symbolic answer checking, backed by SymPy.

This is the piece that lets a student type ``2(x+3)`` and be marked correct against ``2x + 6``.
Khan Academy solves the same problem with their own CAS (``kas``); we use SymPy because it is
mature, Python-native and BSD-licensed.

**Security note.** ``sympy.parse_expr`` is *not* safe on untrusted input — it ultimately calls
``eval`` on a transformed token stream, and inputs such as ``exec('...')`` or attribute access have
historically been exploitable. Student answers are untrusted by definition, so every input passes a
strict character/token whitelist *before* SymPy sees it.
"""

from __future__ import annotations

import re
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

__all__ = [
    "AlgebraError",
    "parse_student_expression",
    "expressions_equivalent",
    "to_latex",
]


class AlgebraError(ValueError):
    """Raised when input cannot be safely parsed as a mathematical expression."""


# Only these characters may appear in a student's algebraic answer. Note the absence of
# '_', '[', ']', '.', quotes and ';' — the building blocks of dunder access and statements.
_ALLOWED_CHARS = re.compile(r"^[0-9a-zA-Z+\-*/^().,√πθ\s|!<>=]*$")

# Function/symbol names a student is allowed to reference. Anything alphabetic that is not on
# this list must be a single character (a variable such as x, y, n, t).
_ALLOWED_WORDS = {
    "sqrt", "cbrt", "abs", "log", "ln", "exp", "sin", "cos", "tan",
    "asin", "acos", "atan", "sinh", "cosh", "tanh", "pi", "e",
    "floor", "ceiling", "max", "min", "gcd", "lcm", "factorial",
}

_WORD_RE = re.compile(r"[A-Za-z]+")

# The namespace SymPy is allowed to resolve names from.
#
# It must contain more than the student-facing functions: SymPy's own transformations rewrite the
# token stream into calls like ``Symbol('x')`` and ``Integer(2)``, so those constructors have to be
# resolvable or parsing fails outright. Everything here is a pure symbolic constructor — the
# namespace still excludes builtins, so ``__import__`` and friends remain unreachable, and the
# character/word whitelist in ``_sanitize`` has already rejected them anyway.
def _build_global_dict() -> dict[str, Any]:
    namespace: dict[str, Any] = {
        "Symbol": sympy.Symbol,
        "Integer": sympy.Integer,
        "Float": sympy.Float,
        "Rational": sympy.Rational,
        "Function": sympy.Function,
    }
    aliases = {"ln": sympy.log, "cbrt": sympy.cbrt}
    for name in _ALLOWED_WORDS:
        if name in aliases:
            namespace[name] = aliases[name]
        elif (attribute := getattr(sympy, name, None)) is not None:
            namespace[name] = attribute
    return namespace


_GLOBAL_DICT = _build_global_dict()

_TRANSFORMATIONS = (
    *standard_transformations,
    # Lets students write "2x" and "3(x+1)" rather than forcing explicit "*".
    implicit_multiplication_application,
    # Accepts "x^2" as well as "x**2" — middle schoolers write the former.
    convert_xor,
)

# Friendly input the parser would otherwise reject.
_SUBSTITUTIONS = [
    ("√", "sqrt"),
    ("π", "pi"),
    ("×", "*"),
    ("·", "*"),
    ("÷", "/"),
    ("−", "-"),   # U+2212 minus sign, produced by some keyboards and copy-paste
    ("–", "-"),   # en dash
    ("—", "-"),   # em dash
    (",", ""),    # thousands separators; decimal commas are handled in numeric grading
]


def _sanitize(text: str) -> str:
    if not isinstance(text, str):
        raise AlgebraError("Expression must be text")
    cleaned = text.strip()
    if not cleaned:
        raise AlgebraError("Expression is empty")
    if len(cleaned) > 500:
        raise AlgebraError("Expression is too long")

    for needle, replacement in _SUBSTITUTIONS:
        cleaned = cleaned.replace(needle, replacement)

    if not _ALLOWED_CHARS.match(cleaned):
        bad = sorted({c for c in cleaned if not _ALLOWED_CHARS.match(c)})
        raise AlgebraError(f"Expression contains unsupported characters: {''.join(bad)}")

    for word in _WORD_RE.findall(cleaned):
        if len(word) > 1 and word.lower() not in _ALLOWED_WORDS:
            raise AlgebraError(f"Unknown function or symbol: {word}")

    return cleaned


def parse_student_expression(text: str) -> sympy.Expr:
    """Parse untrusted text into a SymPy expression, or raise ``AlgebraError``."""
    cleaned = _sanitize(text)
    try:
        expr = parse_expr(
            cleaned,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
            # Restricting global_dict stops SymPy resolving names out of its full namespace.
            local_dict={},
            global_dict=dict(_GLOBAL_DICT),
        )
    except AlgebraError:
        raise
    except Exception as exc:  # SymPy raises a wide variety of exception types
        raise AlgebraError(f"Could not understand {text!r}") from exc

    if expr is None:
        raise AlgebraError(f"Could not understand {text!r}")
    return expr


def parse_author_expression(text: str) -> sympy.Expr:
    """Parse a trusted, author-written expression. Still sanitised — authors make typos too."""
    return parse_student_expression(text)


def expressions_equivalent(
    student: str | sympy.Expr,
    expected: str | sympy.Expr,
    *,
    symbols: list[str] | None = None,
) -> bool:
    """Are two expressions mathematically equal?

    Uses ``simplify(a - b) == 0`` as the primary test. Because ``simplify`` can fail to reach zero
    for awkward but genuinely-equal expressions, we fall back to numeric sampling at several random
    points — if two expressions agree everywhere we test, they are equal for our purposes.
    """
    left = parse_student_expression(student) if isinstance(student, str) else student
    right = parse_author_expression(expected) if isinstance(expected, str) else expected

    difference = sympy.simplify(left - right)
    if difference == 0:
        return True

    # Numeric fallback. Evaluate at a spread of points, avoiding 0 and 1 where many wrong
    # expressions coincidentally agree with the right one.
    free = sorted(left.free_symbols | right.free_symbols, key=str)
    if symbols:
        free = [sympy.Symbol(s) for s in symbols] or free
    if not free:
        try:
            return bool(abs(complex(left) - complex(right)) < 1e-9)
        except (TypeError, ValueError):
            return False

    probes = [2.3, 3.7, 5.1, 7.9, 11.3]
    agreements = 0
    for index, probe in enumerate(probes):
        substitution = {sym: probe + 0.37 * position + 0.11 * index
                        for position, sym in enumerate(free)}
        try:
            lhs = complex(left.evalf(subs=substitution))
            rhs = complex(right.evalf(subs=substitution))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if any(map(lambda v: v != v, (lhs.real, rhs.real))):  # NaN check
            continue
        scale = max(1.0, abs(lhs), abs(rhs))
        if abs(lhs - rhs) / scale < 1e-9:
            agreements += 1
        else:
            return False

    return agreements >= 3


def to_latex(expression: str | sympy.Expr) -> str:
    """Render an expression as LaTeX for display. Falls back to the raw text on failure."""
    try:
        expr = parse_author_expression(expression) if isinstance(expression, str) else expression
        return sympy.latex(expr)
    except (AlgebraError, TypeError, ValueError):
        return str(expression)


def format_number(value: Any, decimals: int | None = None) -> str:
    """Format a computed answer for display, trimming pointless trailing zeros."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if decimals is not None:
            return f"{value:.{decimals}f}"
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)
