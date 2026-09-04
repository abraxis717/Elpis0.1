from __future__ import annotations

from types import SimpleNamespace

import pytest

from elpis_reference.structural_guidance import (
    FULL_ELPIS_RUNTIME_ADMISSION,
    STRUCTURAL_GUIDANCE_COMPONENT_ADMITTED,
    STRUCTURAL_GUIDANCE_LIVE_HOOK_ACTIVE,
    TRM_AUTHORITY_GRANTED,
    StructuralGuidanceAdmissionConfig,
    admit_projection,
)
from elpis_reference.structural_guidance.receipt import (
    StructuralGuidanceReceiptV1,
)
from elpis_reference.structural_guidance._authority.core import (
    TRM0GuidedRefiner,
)


def test_component_scope_flags():
    assert (
        STRUCTURAL_GUIDANCE_COMPONENT_ADMITTED
        is True
    )

    assert (
        STRUCTURAL_GUIDANCE_LIVE_HOOK_ACTIVE
        is False
    )

    assert FULL_ELPIS_RUNTIME_ADMISSION is False

    assert TRM_AUTHORITY_GRANTED == 0


def test_request_gate_defaults_off():
    cfg = StructuralGuidanceAdmissionConfig()

    projection = SimpleNamespace(
        projection_digest="1" * 64,
        structural_input_fingerprint="2" * 64,
    )

    result = admit_projection(
        projection,  # type: ignore[arg-type]
        cfg,
    )

    assert result.admitted is False
    assert result.fallback_required is False

    assert result.final_input is None
    assert result.envelope is None

    assert result.receipt.outcome == "BYPASSED"
    assert result.receipt.enabled is False

    assert (
        result.receipt.authority_granted
        == 0
    )

    assert result.receipt.validate_digest()


def test_enabled_without_checkpoint_fails_closed():
    cfg = StructuralGuidanceAdmissionConfig(
        enabled=True,
        checkpoint_path="",
    )

    projection = SimpleNamespace(
        projection_digest="3" * 64,
        structural_input_fingerprint="4" * 64,
    )

    result = admit_projection(
        projection,  # type: ignore[arg-type]
        cfg,
    )

    assert result.admitted is False
    assert result.fallback_required is True

    assert (
        result.receipt.outcome
        == "FALLBACK_REQUIRED"
    )

    assert result.receipt.enabled is True

    assert (
        result.receipt.authority_granted
        == 0
    )

    assert result.receipt.error_code == "TypeError"

    assert result.receipt.validate_digest()


def test_receipt_is_deterministic():
    cfg = StructuralGuidanceAdmissionConfig()

    projection = SimpleNamespace(
        projection_digest="5" * 64,
        structural_input_fingerprint="6" * 64,
    )

    a = admit_projection(
        projection,  # type: ignore[arg-type]
        cfg,
    )

    b = admit_projection(
        projection,  # type: ignore[arg-type]
        cfg,
    )

    assert (
        a.receipt.receipt_digest
        == b.receipt.receipt_digest
    )


def test_receipt_rejects_authority():
    with pytest.raises(
        ValueError,
        match="authority",
    ):
        StructuralGuidanceReceiptV1(
            schema=(
                "elpis.structural-guidance."
                "runtime-receipt.v1"
            ),
            outcome="ADMITTED",
            enabled=True,
            projection_digest="",
            envelope_digest="",
            input_refinement_fingerprint="",
            output_refinement_fingerprint="",
            checkpoint_sha256="",
            seed=0,
            budget=1,
            restarts=1,
            plateau=0,
            iterations=0,
            best_cost=0,
            applied_moves=0,
            authority_granted=1,
        )


def test_frozen_refiner_constructor_surface():
    dummy_source = lambda ri: ri.grid81

    refiner = TRM0GuidedRefiner(
        proposal_source=dummy_source,
        seed=1,
        budget=1,
        restarts=1,
        plateau=0,
    )

    assert refiner is not None
