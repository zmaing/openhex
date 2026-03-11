"""
Row filter expression engine.

Supports a constrained, C-like expression syntax for evaluating row data.
Expressions use ``data[index]`` to access bytes within the current row.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass


class FilterSyntaxError(ValueError):
    """Raised when a filter expression cannot be parsed safely."""


def _normalize_expression(expression: str) -> str:
    """Convert a C-like expression into a Python-compatible subset."""
    normalized = expression.strip()
    normalized = normalized.replace("&&", " and ")
    normalized = normalized.replace("||", " or ")
    normalized = re.sub(r"(?<![=!<>])!(?!=)", " not ", normalized)
    return normalized


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
    ast.Not: operator.not_,
}

_COMPARE_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


@dataclass(slots=True)
class CompiledRowFilter:
    """Compiled row filter expression."""

    source: str
    normalized: str
    tree: ast.Expression
    code: object

    def matches(self, data: bytes) -> bool:
        """Return whether the current row satisfies this filter."""
        try:
            result = eval(self.code, {"__builtins__": {}}, {"data": data})
        except (IndexError, TypeError, ValueError, ZeroDivisionError):
            return False
        return bool(result)


def compile_row_filter(expression: str) -> CompiledRowFilter:
    """Parse and validate a row filter expression."""
    source = (expression or "").strip()
    if not source:
        raise FilterSyntaxError("Filter expression is empty.")

    normalized = _normalize_expression(source)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise FilterSyntaxError(str(exc)) from exc

    _validate_node(tree)
    code = compile(tree, "<row-filter>", "eval")
    return CompiledRowFilter(source=source, normalized=normalized, tree=tree, code=code)


def evaluate_row_filter(expression: str, data: bytes) -> bool:
    """Compile and evaluate a row filter in one call."""
    return compile_row_filter(expression).matches(data)


def _validate_node(node: ast.AST) -> None:
    """Ensure the AST only contains supported syntax."""
    if isinstance(node, ast.Expression):
        _validate_node(node.body)
        return

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            raise FilterSyntaxError("Unsupported boolean operator.")
        for value in node.values:
            _validate_node(value)
        return

    if isinstance(node, ast.BinOp):
        if type(node.op) not in _BINARY_OPERATORS:
            raise FilterSyntaxError("Unsupported binary operator.")
        _validate_node(node.left)
        _validate_node(node.right)
        return

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARY_OPERATORS:
            raise FilterSyntaxError("Unsupported unary operator.")
        _validate_node(node.operand)
        return

    if isinstance(node, ast.Compare):
        if not node.ops:
            raise FilterSyntaxError("Invalid comparison.")
        _validate_node(node.left)
        for op in node.ops:
            if type(op) not in _COMPARE_OPERATORS:
                raise FilterSyntaxError("Unsupported comparison operator.")
        for comparator in node.comparators:
            _validate_node(comparator)
        return

    if isinstance(node, ast.Subscript):
        if not isinstance(node.value, ast.Name) or node.value.id != "data":
            raise FilterSyntaxError("Only data[index] access is supported.")
        if isinstance(node.slice, ast.Slice):
            raise FilterSyntaxError("Slices are not supported.")
        _validate_node(node.slice)
        return

    if isinstance(node, ast.Name):
        if node.id != "data":
            raise FilterSyntaxError("Only the data symbol is available.")
        return

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, bool)):
            raise FilterSyntaxError("Only integer and boolean constants are supported.")
        return

    raise FilterSyntaxError(f"Unsupported syntax: {type(node).__name__}")
