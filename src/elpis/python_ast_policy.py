"""Neutral deterministic Python AST policy.

This module owns only syntax/static-policy inspection. It does not own
artifact lineage, validation authority, semantic interpretation, decoding,
execution, or repair authority.
"""

from __future__ import annotations

import ast
from typing import AbstractSet
from dataclasses import dataclass


PYTHON_AST_BANNED_CALLS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "breakpoint",
    }
)


@dataclass(frozen=True, slots=True)
class PythonASTPolicyDecisionV1:
    passed: bool
    code: str
    lineno: int = -1
    offset: int = -1
    functions: tuple[str, ...] = ()
    call_name: str = ""
    node_count: int = 0
    syntax_message: str = ""


def python_call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return node.attr

    return None


def evaluate_python_ast_policy(
    *,
    language: str,
    source: str,
    entrypoint: str,
    banned_calls: AbstractSet[str] = PYTHON_AST_BANNED_CALLS,
) -> PythonASTPolicyDecisionV1:
    if language != "python":
        return PythonASTPolicyDecisionV1(
            passed=False,
            code="LANGUAGE_MISMATCH",
        )

    try:
        tree = ast.parse(
            source,
            mode="exec",
        )

    except SyntaxError as exc:
        return PythonASTPolicyDecisionV1(
            passed=False,
            code="SYNTAX_ERROR",
            lineno=exc.lineno or -1,
            offset=exc.offset or -1,
            syntax_message=str(exc),
        )

    functions = tuple(
        sorted(
            {
                node.name
                for node in ast.walk(tree)
                if isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
            }
        )
    )

    if entrypoint not in functions:
        return PythonASTPolicyDecisionV1(
            passed=False,
            code="ENTRYPOINT_MISSING",
            functions=functions,
        )

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
            ),
        ):
            return PythonASTPolicyDecisionV1(
                passed=False,
                code="IMPORT_FORBIDDEN",
                lineno=getattr(
                    node,
                    "lineno",
                    -1,
                ),
            )

        if isinstance(
            node,
            (
                ast.Global,
                ast.Nonlocal,
            ),
        ):
            return PythonASTPolicyDecisionV1(
                passed=False,
                code="SCOPE_MUTATION_FORBIDDEN",
                lineno=getattr(
                    node,
                    "lineno",
                    -1,
                ),
            )

        if isinstance(node, ast.Call):
            name = python_call_name(node.func)

            if name in banned_calls:
                return PythonASTPolicyDecisionV1(
                    passed=False,
                    code="BANNED_CALL",
                    lineno=getattr(
                        node,
                        "lineno",
                        -1,
                    ),
                    call_name=name or "",
                )

    return PythonASTPolicyDecisionV1(
        passed=True,
        code="AST_VALID",
        node_count=sum(
            1
            for _ in ast.walk(tree)
        ),
    )
