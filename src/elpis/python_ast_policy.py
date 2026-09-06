"""Neutral deterministic Python AST policy.

This module owns only syntax/static-policy inspection. It does not own
artifact lineage, validation authority, semantic interpretation, decoding,
execution, or repair authority. This restricted syntax is not a Python sandbox;
passing source must never be executed with ambient capabilities.
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


# These names can recover or manufacture references to otherwise forbidden
# capabilities without naming the eventual callable in ast.Call.func.
#
# Core restrictions are invariant; caller restrictions are additive.
_PYTHON_AST_ALWAYS_BANNED_REFERENCES = frozenset(
    {
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "globals",
        "locals",
        "__builtins__",
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


# Data operations required by generated templates. Attributes are admissible
# only as direct method calls, never as recoverable values. Unknown attributes
# fail closed, including all frame/code/traceback and suspension internals.
_DATA_METHODS = frozenset("""
append extend insert pop remove clear copy count index reverse sort
get keys values items setdefault update add discard union intersection difference
strip lstrip rstrip split rsplit splitlines join replace lower upper casefold
startswith endswith find rfind isdigit isalpha isalnum isspace
""".split())
_BUILTIN_CALLS = frozenset("""
abs all any bool dict divmod enumerate filter float frozenset int isinstance
issubclass iter len list map max min next pow range reversed round set slice
sorted str sum tuple zip chr ord bin hex oct repr
ValueError TypeError IndexError KeyError RuntimeError Exception
""".split())


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

    banned_calls = PYTHON_AST_BANNED_CALLS | frozenset(banned_calls)
    callable_names = _BUILTIN_CALLS | set(functions)
    method_nodes = {id(node.func) for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}

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

        reference_name = None
        if isinstance(node, ast.Name) and (
            node.id in banned_calls or node.id in _PYTHON_AST_ALWAYS_BANNED_REFERENCES
        ):
            reference_name = node.id
        elif isinstance(node, ast.Attribute) and (
            node.attr in banned_calls or node.attr not in _DATA_METHODS
            or id(node) not in method_nodes
        ):
            reference_name = node.attr
        elif isinstance(node, ast.Call) and (
            not isinstance(node.func, (ast.Name, ast.Attribute))
            or isinstance(node.func, ast.Name) and node.func.id not in callable_names
        ):
            reference_name = python_call_name(node.func) or "<indirect>"

        if reference_name is not None:
            return PythonASTPolicyDecisionV1(
                passed=False,
                code="BANNED_CALL",
                lineno=getattr(
                    node,
                    "lineno",
                    -1,
                ),
                call_name=reference_name,
            )

    return PythonASTPolicyDecisionV1(
        passed=True,
        code="AST_VALID",
        node_count=sum(
            1
            for _ in ast.walk(tree)
        ),
    )
