"""A deliberately small, whitelist-based expression evaluator.

Question templates contain author-written expressions (``distance / time``) and constraints
(``distance % time == 0``). Those are *data*, and data that reaches ``eval()`` is a remote code
execution bug waiting to happen — teachers can author templates, and eventually so will an AI.

So instead of ``eval``, we parse to an AST and walk it, rejecting any node type not on the
whitelist. Anything unrecognised raises rather than being silently skipped, which keeps the
failure mode "template is broken" instead of "template did something unexpected".
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable
from typing import Any

__all__ = ["ExpressionError", "evaluate", "evaluate_bool", "ALLOWED_FUNCTIONS"]


class ExpressionError(ValueError):
    """Raised when an expression is malformed, unsafe, or references an unknown name."""


# Guard against expressions that are cheap to write but expensive to evaluate, e.g. ``9**9**9``.
MAX_EXPONENT = 64
MAX_ABS_RESULT = 1e15


def _safe_pow(base: Any, exp: Any) -> Any:
    if isinstance(exp, (int, float)) and abs(exp) > MAX_EXPONENT:
        raise ExpressionError(f"Exponent {exp} exceeds the maximum of {MAX_EXPONENT}")
    return operator.pow(base, exp)


def _checked_div(a: Any, b: Any) -> Any:
    if b == 0:
        raise ExpressionError("Division by zero")
    return operator.truediv(a, b)


def _checked_floordiv(a: Any, b: Any) -> Any:
    if b == 0:
        raise ExpressionError("Division by zero")
    return operator.floordiv(a, b)


def _checked_mod(a: Any, b: Any) -> Any:
    if b == 0:
        raise ExpressionError("Modulo by zero")
    return operator.mod(a, b)


_BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _checked_div,
    ast.FloorDiv: _checked_floordiv,
    ast.Mod: _checked_mod,
    ast.Pow: _safe_pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARE_OPS: dict[type[ast.cmpop], Callable[[Any, Any], Any]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _int_sqrt_exact(value: float) -> bool:
    """True when ``value`` is a perfect square — handy in constraints."""
    if value < 0:
        return False
    root = math.isqrt(int(value))
    return root * root == int(value) and float(int(value)) == float(value)


ALLOWED_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": lambda values: sum(values),
    "len": len,
    "int": int,
    "float": float,
    "sqrt": math.sqrt,
    "floor": math.floor,
    "ceil": math.ceil,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "radians": math.radians,
    "degrees": math.degrees,
    "hypot": math.hypot,
    "is_square": _int_sqrt_exact,
    "sign": lambda x: (x > 0) - (x < 0),
}

ALLOWED_CONSTANTS: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "True": True,
    "False": False,
}


class _Evaluator(ast.NodeVisitor):
    def __init__(self, namespace: dict[str, Any]) -> None:
        self.namespace = namespace

    # Any node type without an explicit visitor lands here and is rejected.
    def generic_visit(self, node: ast.AST) -> Any:
        raise ExpressionError(f"Unsupported syntax: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float, bool, str)) or node.value is None:
            return node.value
        raise ExpressionError(f"Unsupported constant: {node.value!r}")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self.namespace:
            return self.namespace[node.id]
        if node.id in ALLOWED_CONSTANTS:
            return ALLOWED_CONSTANTS[node.id]
        raise ExpressionError(f"Unknown variable {node.id!r}")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        handler = _BIN_OPS.get(type(node.op))
        if handler is None:
            raise ExpressionError(f"Unsupported operator: {type(node.op).__name__}")
        result = handler(self.visit(node.left), self.visit(node.right))
        if isinstance(result, (int, float)) and abs(result) > MAX_ABS_RESULT:
            raise ExpressionError("Result magnitude is out of range")
        return result

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        handler = _UNARY_OPS.get(type(node.op))
        if handler is None:
            raise ExpressionError(f"Unsupported unary operator: {type(node.op).__name__}")
        return handler(self.visit(node.operand))

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        values = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comparator_node in zip(node.ops, node.comparators, strict=True):
            handler = _COMPARE_OPS.get(type(op))
            if handler is None:
                raise ExpressionError(f"Unsupported comparison: {type(op).__name__}")
            right = self.visit(comparator_node)
            if not handler(left, right):
                return False
            left = right
        return True

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        return self.visit(node.body) if self.visit(node.test) else self.visit(node.orelse)

    def visit_Call(self, node: ast.Call) -> Any:
        # Only bare names may be called — this blocks attribute access like ``().__class__``.
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only direct calls to allowed functions are permitted")
        func = ALLOWED_FUNCTIONS.get(node.func.id)
        if func is None:
            raise ExpressionError(f"Function {node.func.id!r} is not allowed")
        if node.keywords:
            raise ExpressionError("Keyword arguments are not supported")
        return func(*[self.visit(arg) for arg in node.args])

    def visit_List(self, node: ast.List) -> Any:
        return [self.visit(item) for item in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        return tuple(self.visit(item) for item in node.elts)


def evaluate(expression: str, namespace: dict[str, Any] | None = None) -> Any:
    """Evaluate ``expression`` against ``namespace``. Raises ``ExpressionError`` on anything odd."""
    if not isinstance(expression, str):
        raise ExpressionError(f"Expression must be a string, got {type(expression).__name__}")
    if len(expression) > 2000:
        raise ExpressionError("Expression is too long")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Could not parse {expression!r}: {exc.msg}") from exc

    try:
        return _Evaluator(namespace or {}).visit(tree)
    except ExpressionError:
        raise
    except ZeroDivisionError as exc:
        raise ExpressionError("Division by zero") from exc
    except (TypeError, ValueError, OverflowError) as exc:
        raise ExpressionError(f"Could not evaluate {expression!r}: {exc}") from exc


def evaluate_bool(expression: str, namespace: dict[str, Any] | None = None) -> bool:
    return bool(evaluate(expression, namespace))
