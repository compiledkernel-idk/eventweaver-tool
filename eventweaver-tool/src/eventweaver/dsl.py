from __future__ import annotations

import ast
from typing import Callable, Dict, Any

from .models import Event

ALLOWED_NAMES = {"timestamp", "source", "severity", "message", "metadata"}
ALLOWED_BINOPS = (ast.Add, ast.Sub)
ALLOWED_BOOL_OPS = (ast.And, ast.Or)
ALLOWED_UNARY_OPS = (ast.Not, ast.USub, ast.UAdd)
ALLOWED_CMP_OPS = (
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.In,
    ast.NotIn,
)


class ExpressionError(ValueError):
    """Raised when a query expression is invalid."""


def compile_expression(expr: str) -> Callable[[Event], bool]:
    if not expr or not expr.strip():
        raise ExpressionError("Expression may not be empty")

    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Invalid expression: {exc.msg}") from exc

    _validate_ast(parsed)

    def predicate(event: Event) -> bool:
        return bool(_evaluate(parsed.body, event))

    return predicate


def _validate_ast(node: ast.AST) -> None:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            raise ExpressionError("Function calls are not allowed in expressions")
        if isinstance(child, ast.Attribute):
            raise ExpressionError("Attribute access is not allowed in expressions")
        if isinstance(child, ast.Compare):
            for op in child.ops:
                if not isinstance(op, ALLOWED_CMP_OPS):
                    raise ExpressionError(f"Comparator {type(op).__name__} is not allowed")
        if isinstance(child, ast.BinOp) and not isinstance(child.op, ALLOWED_BINOPS):
            raise ExpressionError(f"Binary operator {type(child.op).__name__} is not allowed")
        if isinstance(child, ast.BoolOp) and not isinstance(child.op, ALLOWED_BOOL_OPS):
            raise ExpressionError(f"Boolean operator {type(child.op).__name__} is not allowed")
        if isinstance(child, ast.UnaryOp) and not isinstance(child.op, ALLOWED_UNARY_OPS):
            raise ExpressionError(f"Unary operator {type(child.op).__name__} is not allowed")
        if isinstance(child, ast.Name) and child.id not in ALLOWED_NAMES:
            raise ExpressionError(f"Unknown identifier '{child.id}' in expression")
        if isinstance(child, ast.Subscript):
            if not isinstance(child.value, ast.Name) or child.value.id != "metadata":
                raise ExpressionError("Subscripting is only allowed on metadata")


def _evaluate(node: ast.AST, event: Event) -> Any:
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_evaluate(value, event) for value in node.values)
        return any(_evaluate(value, event) for value in node.values)
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, event)
        right = _evaluate(node.right, event)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        raise ExpressionError(f"Unsupported binary operator {type(node.op).__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand, event)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ExpressionError(f"Unsupported unary operator {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, event)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            right = _evaluate(comparator, event)
            if isinstance(op, ast.Eq):
                result = result and (left == right)
            elif isinstance(op, ast.NotEq):
                result = result and (left != right)
            elif isinstance(op, ast.Gt):
                result = result and (left > right)
            elif isinstance(op, ast.GtE):
                result = result and (left >= right)
            elif isinstance(op, ast.Lt):
                result = result and (left < right)
            elif isinstance(op, ast.LtE):
                result = result and (left <= right)
            elif isinstance(op, ast.In):
                result = result and (left in right)
            elif isinstance(op, ast.NotIn):
                result = result and (left not in right)
            else:
                raise ExpressionError(f"Unsupported comparator {type(op).__name__}")
            left = right
        return result
    if isinstance(node, ast.Name):
        return _resolve_name(node.id, event)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Subscript):
        collection = _evaluate(node.value, event)
        key = _evaluate(node.slice, event) if isinstance(node.slice, ast.AST) else node.slice
        return collection[key]
    if isinstance(node, ast.Index):  # pragma: no cover - legacy AST node
        return _evaluate(node.value, event)
    raise ExpressionError(f"Unsupported syntax node {type(node).__name__}")


def _resolve_name(name: str, event: Event) -> Any:
    if name == "timestamp":
        return event.timestamp
    if name == "source":
        return event.source
    if name == "severity":
        return event.severity
    if name == "message":
        return event.message
    if name == "metadata":
        return event.metadata
    raise ExpressionError(f"Unknown identifier '{name}'")
