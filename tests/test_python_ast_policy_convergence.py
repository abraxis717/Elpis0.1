from __future__ import annotations

import ast

import pytest

from elpis.python_ast_policy import (
    PYTHON_AST_BANNED_CALLS,
    evaluate_python_ast_policy,
    python_call_name,
)
from elpis_p0.contracts import (
    ArtifactCandidate,
    RequestContext,
)
from elpis_p0.validators import (
    PythonASTValidator,
)


def _context(
    *,
    entrypoint: str = "solution",
) -> RequestContext:
    return RequestContext(
        request_id="validator-policy-convergence",
        prompt="policy convergence fixture",
        entrypoint=entrypoint,
    )


def _artifact(
    source: str,
    *,
    language: str = "python",
) -> ArtifactCandidate:
    return ArtifactCandidate(
        language=language,
        source=source,
        digest="",
    )


@pytest.mark.parametrize(
    (
        "language",
        "source",
        "entrypoint",
        "expected_code",
    ),
    (
        (
            "text",
            "not python",
            "solution",
            "LANGUAGE_MISMATCH",
        ),
        (
            "python",
            "def solution(:\n    pass\n",
            "solution",
            "SYNTAX_ERROR",
        ),
        (
            "python",
            "def other():\n    return 1\n",
            "solution",
            "ENTRYPOINT_MISSING",
        ),
        (
            "python",
            "import os\n\ndef solution():\n    return 1\n",
            "solution",
            "IMPORT_FORBIDDEN",
        ),
        (
            "python",
            "x = 0\n\ndef solution():\n    global x\n    x = 1\n",
            "solution",
            "SCOPE_MUTATION_FORBIDDEN",
        ),
        (
            "python",
            "def solution():\n    return eval('1')\n",
            "solution",
            "BANNED_CALL",
        ),
        (
            "python",
            "def solution():\n    return 1\n",
            "solution",
            "AST_VALID",
        ),
    ),
)
def test_legacy_validator_delegates_to_neutral_policy_without_decision_drift(
    language: str,
    source: str,
    entrypoint: str,
    expected_code: str,
) -> None:
    decision = evaluate_python_ast_policy(
        language=language,
        source=source,
        entrypoint=entrypoint,
        banned_calls=frozenset(
            PythonASTValidator.banned_calls
        ),
    )

    evidence = PythonASTValidator().validate(
        _context(
            entrypoint=entrypoint
        ),
        _artifact(
            source,
            language=language,
        ),
    )

    assert decision.code == expected_code
    assert evidence.code == expected_code
    assert evidence.passed is decision.passed

    details = dict(evidence.details)

    if expected_code == "SYNTAX_ERROR":
        assert evidence.message == decision.syntax_message
        assert details == {
            "lineno": decision.lineno,
            "offset": decision.offset,
        }

    elif expected_code == "ENTRYPOINT_MISSING":
        assert details == {
            "functions": decision.functions,
        }

    elif expected_code in {
        "IMPORT_FORBIDDEN",
        "SCOPE_MUTATION_FORBIDDEN",
        "BANNED_CALL",
    }:
        assert details == {
            "lineno": decision.lineno,
        }

    elif expected_code == "AST_VALID":
        assert details == {
            "entrypoint": entrypoint,
            "node_count": decision.node_count,
        }


def test_exact_legacy_messages_remain_stable() -> None:
    validator = PythonASTValidator()
    context = _context()

    evidence = validator.validate(
        context,
        _artifact(
            "def other():\n    return 1\n"
        ),
    )
    assert evidence.message == (
        "expected function 'solution' "
        "was not defined"
    )

    evidence = validator.validate(
        context,
        _artifact(
            "import os\n\n"
            "def solution():\n"
            "    return 1\n"
        ),
    )
    assert evidence.message == (
        "P0 template artifacts may not import modules"
    )

    evidence = validator.validate(
        context,
        _artifact(
            "x = 0\n\n"
            "def solution():\n"
            "    global x\n"
            "    x = 1\n"
        ),
    )
    assert evidence.message == (
        "global/nonlocal mutation is forbidden in P0"
    )

    evidence = validator.validate(
        context,
        _artifact(
            "def solution():\n"
            "    return eval('1')\n"
        ),
    )
    assert evidence.message == (
        "call to 'eval' is forbidden in P0"
    )

    evidence = validator.validate(
        context,
        _artifact(
            "def solution():\n"
            "    return 1\n"
        ),
    )
    assert evidence.message == (
        "artifact parsed and passed P0 static policy"
    )


def test_legacy_mutable_banned_call_surface_is_preserved() -> None:
    validator = PythonASTValidator()
    validator.banned_calls = {
        "print",
    }

    evidence = validator.validate(
        _context(),
        _artifact(
            "def solution():\n"
            "    print('x')\n"
        ),
    )

    assert evidence.passed is False
    assert evidence.code == "BANNED_CALL"
    assert evidence.message == (
        "call to 'print' is forbidden in P0"
    )


def test_neutral_policy_has_no_authority_or_execution_surface() -> None:
    import elpis.python_ast_policy as policy

    names = set(dir(policy))

    forbidden = {
        "AuthorityCapability",
        "CapabilityRegistry",
        "subprocess",
        "torch",
        "execute",
        "decode",
        "emit",
    }

    assert names.isdisjoint(
        forbidden
    )


def test_banned_call_set_matches_legacy_policy() -> None:
    assert PYTHON_AST_BANNED_CALLS == frozenset(
        PythonASTValidator.banned_calls
    )


def test_call_name_compatibility_surface_is_preserved() -> None:
    tree = ast.parse(
        "obj.method()\n",
        mode="exec",
    )

    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )

    assert python_call_name(
        call.func
    ) == "method"

    assert PythonASTValidator._call_name(
        call.func
    ) == "method"
