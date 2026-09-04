from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect

import pytest

from elpis_reference.structural_guidance import (
    DECODING_AUTHORITY,
    STRUCTURAL_PYTHON_AST_VALIDATOR_ID,
    STRUCTURAL_PYTHON_AST_VALIDATOR_VERSION,
    VALIDATION_AUTHORITY,
    DecodedSourceArtifactV1,
    DecoderSpecificPlanV1,
    StructuralPythonASTValidatorV1,
    StructuralValidationError,
)
from elpis_reference.structural_guidance.validation_authority import (
    _new_validation_authority,
)


def _plan(
    *,
    function_name: str = "solution",
) -> DecoderSpecificPlanV1:
    unsigned = DecoderSpecificPlanV1(
        schema=(
            "elpis.structural-guidance."
            "decoder-specific-plan.v1"
        ),
        planning_artifact_digest="1" * 64,
        decoding_consumption_digest="2" * 64,
        planning_input_digest="3" * 64,
        materialization_digest="4" * 64,
        topology_digest="5" * 64,
        semantic_input_digest="6" * 64,
        request_id="validation-test",
        decoder_adapter_id=(
            "elpis.structural-guidance."
            "deterministic-decoder-adapter"
        ),
        decoder_adapter_version="v1",
        backend=(
            "deterministic-python-template-v1"
        ),
        language="python",
        temperature=0.0,
        max_tokens=512,
        selected_experts=(
            "python.ast",
        ),
        function_name=function_name,
        parameters=(),
        body_lines=(
            "return 1",
        ),
        authority_applied=DECODING_AUTHORITY,
        authority_granted=0,
        planning_authorized=False,
        decoding_authorized=False,
        source_emission_authorized=False,
        execution_authorized=False,
        decoder_plan_digest="",
    )

    plan = replace(
        unsigned,
        decoder_plan_digest=(
            unsigned.decoder_plan_digest_computed()
        ),
    )

    plan.validate()
    return plan


def _artifact(
    plan: DecoderSpecificPlanV1,
    source: str,
) -> DecodedSourceArtifactV1:
    if not source.endswith("\n"):
        source += "\n"

    unsigned = DecodedSourceArtifactV1(
        schema=(
            "elpis.structural-guidance."
            "decoded-source-artifact.v1"
        ),
        decoder_plan_digest=(
            plan.decoder_plan_digest
        ),
        source_input_digest="7" * 64,
        source_emission_consumption_digest=(
            "8" * 64
        ),
        planning_input_digest=(
            plan.planning_input_digest
        ),
        materialization_digest=(
            plan.materialization_digest
        ),
        topology_digest=(
            plan.topology_digest
        ),
        semantic_input_digest=(
            plan.semantic_input_digest
        ),
        request_id=(
            plan.request_id
        ),
        source_emitter_id=(
            "elpis.structural-guidance."
            "deterministic-source-emitter"
        ),
        source_emitter_version="v1",
        language="python",
        source=source,
        source_sha256=hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest(),
        authority_applied=DECODING_AUTHORITY,
        authority_granted=0,
        planning_authorized=False,
        decoding_authorized=False,
        source_emission_authorized=False,
        execution_authorized=False,
        source_artifact_digest="",
    )

    artifact = replace(
        unsigned,
        source_artifact_digest=(
            unsigned.source_artifact_digest_computed()
        ),
    )

    artifact.validate()
    return artifact


def _consumption(
    artifact: DecodedSourceArtifactV1,
):
    authority = (
        _new_validation_authority()
    )

    intent = authority._precommit_from_owner(
        artifact,
        validator_id=(
            STRUCTURAL_PYTHON_AST_VALIDATOR_ID
        ),
        validator_version=(
            STRUCTURAL_PYTHON_AST_VALIDATOR_VERSION
        ),
    )

    return authority._consume_from_owner(
        authority._reveal_from_owner(
            intent
        )
    )


@pytest.mark.parametrize(
    (
        "source",
        "expected_code",
    ),
    (
        (
            "def solution():\n"
            "    return 1\n",
            "AST_VALID",
        ),
        (
            "def solution(:\n"
            "    pass\n",
            "SYNTAX_ERROR",
        ),
        (
            "def other():\n"
            "    return 1\n",
            "ENTRYPOINT_MISSING",
        ),
        (
            "import os\n\n"
            "def solution():\n"
            "    return 1\n",
            "IMPORT_FORBIDDEN",
        ),
        (
            "x = 0\n\n"
            "def solution():\n"
            "    global x\n"
            "    x = 1\n",
            "SCOPE_MUTATION_FORBIDDEN",
        ),
        (
            "def solution():\n"
            "    return eval('1')\n",
            "BANNED_CALL",
        ),
    ),
)
def test_native_validator_uses_canonical_policy(
    source: str,
    expected_code: str,
) -> None:
    plan = _plan()
    artifact = _artifact(
        plan,
        source,
    )

    evidence = (
        StructuralPythonASTValidatorV1()
        .validate(
            plan,
            artifact,
            _consumption(
                artifact
            ),
        )
    )

    assert evidence.code == expected_code

    assert (
        evidence.passed
        is (
            expected_code
            == "AST_VALID"
        )
    )

    assert evidence.validate_digest()


def test_valid_evidence_is_authority_zero() -> None:
    plan = _plan()

    artifact = _artifact(
        plan,
        (
            "def solution():\n"
            "    return 1\n"
        ),
    )

    evidence = (
        StructuralPythonASTValidatorV1()
        .validate(
            plan,
            artifact,
            _consumption(
                artifact
            ),
        )
    )

    assert (
        evidence.authority_applied
        == VALIDATION_AUTHORITY
    )

    assert evidence.authority_granted == 0
    assert evidence.planning_authorized is False
    assert evidence.decoding_authorized is False
    assert (
        evidence.source_emission_authorized
        is False
    )
    assert evidence.validation_authorized is False
    assert evidence.execution_authorized is False


def test_decoder_plan_identity_is_required() -> None:
    first = _plan(
        function_name="solution"
    )
    second = _plan(
        function_name="other"
    )

    artifact = _artifact(
        first,
        (
            "def solution():\n"
            "    return 1\n"
        ),
    )

    with pytest.raises(
        StructuralValidationError,
        match="decoder_plan_digest mismatch",
    ):
        (
            StructuralPythonASTValidatorV1()
            .validate(
                second,
                artifact,
                _consumption(
                    artifact
                ),
            )
        )


def test_validation_consumption_is_bound_to_exact_artifact() -> None:
    plan = _plan()

    first = _artifact(
        plan,
        (
            "def solution():\n"
            "    return 1\n"
        ),
    )

    second = _artifact(
        plan,
        (
            "def solution():\n"
            "    return 2\n"
        ),
    )

    consumption = _consumption(
        first
    )

    with pytest.raises(
        StructuralValidationError,
        match="source_artifact_digest mismatch",
    ):
        (
            StructuralPythonASTValidatorV1()
            .validate(
                plan,
                second,
                consumption,
            )
        )


def test_evidence_tamper_is_detected() -> None:
    plan = _plan()

    artifact = _artifact(
        plan,
        (
            "def solution():\n"
            "    return 1\n"
        ),
    )

    evidence = (
        StructuralPythonASTValidatorV1()
        .validate(
            plan,
            artifact,
            _consumption(
                artifact
            ),
        )
    )

    object.__setattr__(
        evidence,
        "code",
        "RETARGETED",
    )

    assert not evidence.validate_digest()


def test_structural_validator_has_no_legacy_or_ast_implementation() -> None:
    import elpis_reference.structural_guidance.structural_validator as module

    source = inspect.getsource(
        module
    )

    assert "elpis_p0" not in source
    assert "ArtifactCandidate" not in source
    assert "RequestContext" not in source
    assert "P0Result" not in source

    assert "import ast" not in source
    assert "ast.parse" not in source
    assert "ast.walk" not in source

    assert (
        "evaluate_python_ast_policy"
        in source
    )
