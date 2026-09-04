from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect

import pytest

from elpis_reference.structural_guidance import (
    FULL_ELPIS_RUNTIME_ADMISSION,
    RUNTIME_STATUS_VALIDATED_SOURCE,
    RUNTIME_STATUS_VALIDATION_REJECTED,
    STRUCTURAL_GUIDANCE_RUNTIME_RESULT_SCHEMA,
    StructuralGuidanceAdmissionConfig,
    StructuralGuidanceRuntimeResultV1,
    run_structural_guidance_runtime,
)


def _result(
    *,
    passed: bool = True,
) -> StructuralGuidanceRuntimeResultV1:
    source = (
        "def solution():\n"
        "    return 1\n"
    )

    unsigned = StructuralGuidanceRuntimeResultV1(
        schema=STRUCTURAL_GUIDANCE_RUNTIME_RESULT_SCHEMA,
        status=(
            RUNTIME_STATUS_VALIDATED_SOURCE
            if passed
            else RUNTIME_STATUS_VALIDATION_REJECTED
        ),
        request_id="runtime-test",
        semantic_input_digest="1" * 64,
        topology_digest="2" * 64,
        checkpoint_sha256="3" * 64,
        materialization_digest="4" * 64,
        planning_input_digest="5" * 64,
        planning_artifact_digest="6" * 64,
        decoder_plan_digest="7" * 64,
        source_input_digest="8" * 64,
        source_artifact_digest="9" * 64,
        source_sha256=hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest(),
        validation_evidence_digest="a" * 64,
        validation_code=(
            "AST_VALID"
            if passed
            else "BANNED_CALL"
        ),
        validation_passed=passed,
        source=source,
        authority_granted=0,
        validation_authorized=False,
        execution_authorized=False,
        runtime_result_digest="",
    )

    signed = replace(
        unsigned,
        runtime_result_digest=(
            unsigned.runtime_result_digest_computed()
        ),
    )

    signed.validate()

    return signed


def test_full_validated_source_runtime_is_admitted() -> None:
    assert FULL_ELPIS_RUNTIME_ADMISSION is True
    assert callable(
        run_structural_guidance_runtime
    )


def test_request_guidance_gate_remains_default_off() -> None:
    assert (
        StructuralGuidanceAdmissionConfig()
        .enabled
        is False
    )


@pytest.mark.parametrize(
    "passed",
    (
        True,
        False,
    ),
)
def test_terminal_result_is_authority_zero(
    passed: bool,
) -> None:
    result = _result(
        passed=passed
    )

    assert result.validate_digest()
    assert result.authority_granted == 0
    assert result.validation_authorized is False
    assert result.execution_authorized is False


def test_terminal_source_tamper_fails_digest() -> None:
    result = _result()

    object.__setattr__(
        result,
        "source",
        result.source + "x = 1\n",
    )

    assert not result.validate_digest()


def test_terminal_status_cannot_forge_validation_success() -> None:
    result = _result(
        passed=False
    )

    object.__setattr__(
        result,
        "status",
        RUNTIME_STATUS_VALIDATED_SOURCE,
    )

    assert not result.validate_digest()


def test_runtime_owns_no_source_execution() -> None:
    import elpis_reference.structural_guidance.runtime as runtime

    source = inspect.getsource(
        runtime
    )

    for forbidden in (
        "subprocess",
        "importlib",
        "os.system",
        "ArtifactCandidate",
        "RequestContext",
        "P0Result",
    ):
        assert forbidden not in source

    assert (
        "StructuralPythonASTValidatorV1"
        in source
    )
