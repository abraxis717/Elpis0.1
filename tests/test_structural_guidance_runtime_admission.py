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
        is True
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


def test_live_public_hook_flag():
    from elpis_reference.structural_guidance import (
        STRUCTURAL_GUIDANCE_LIVE_HOOK_ACTIVE,
    )

    assert (
        STRUCTURAL_GUIDANCE_LIVE_HOOK_ACTIVE
        is True
    )


def test_project_and_admit_calls_projector_then_gate(
    monkeypatch,
):
    import elpis_reference.structural_guidance.hook as hook

    from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
        ProjectionInputV1,
        ProjectionResultV1,
    )

    pin = object.__new__(
        ProjectionInputV1
    )

    projection = object.__new__(
        ProjectionResultV1
    )

    object.__setattr__(
        projection,
        "projection_digest",
        "7" * 64,
    )

    object.__setattr__(
        projection,
        "structural_input_fingerprint",
        "8" * 64,
    )

    observed = []

    def fake_project(value):
        observed.append(
            ("project", value)
        )
        return projection

    monkeypatch.setattr(
        hook,
        "project",
        fake_project,
    )

    result = hook.project_and_admit(
        pin
    )

    assert observed == [
        ("project", pin),
    ]

    assert result.projection is projection

    assert (
        result.admission.receipt.outcome
        == "BYPASSED"
    )

    assert (
        result.admission.receipt.projection_digest
        == projection.projection_digest
    )

    assert result.admitted is False
    assert result.fallback_required is False


def test_project_and_admit_enabled_failure_is_explicit(
    monkeypatch,
):
    import elpis_reference.structural_guidance.hook as hook

    from elpis_reference.structural_guidance import (
        StructuralGuidanceAdmissionConfig,
    )

    from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
        ProjectionInputV1,
        ProjectionResultV1,
    )

    pin = object.__new__(
        ProjectionInputV1
    )

    projection = object.__new__(
        ProjectionResultV1
    )

    object.__setattr__(
        projection,
        "projection_digest",
        "9" * 64,
    )

    object.__setattr__(
        projection,
        "structural_input_fingerprint",
        "a" * 64,
    )

    monkeypatch.setattr(
        hook,
        "project",
        lambda value: projection,
    )

    result = hook.project_and_admit(
        pin,
        StructuralGuidanceAdmissionConfig(
            enabled=True,
            checkpoint_path="",
        ),
    )

    assert result.admitted is False
    assert result.fallback_required is True

    assert (
        result.admission.receipt.outcome
        == "FALLBACK_REQUIRED"
    )

    assert (
        result.admission.receipt.error_code
        == "ValueError"
    )

    assert (
        result.admission.receipt.authority_granted
        == 0
    )


def test_semantic_request_public_wrapper(
    monkeypatch,
):
    import elpis_reference.structural_guidance.hook as hook

    from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
        ProjectionInputV1,
    )

    from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
        P0SemanticRequestV1,
    )

    request = object.__new__(
        P0SemanticRequestV1
    )

    sentinel = object()
    observed = {}

    def fake_project_and_admit(
        projection_input,
        config,
    ):
        observed["input"] = (
            projection_input
        )
        observed["config"] = config
        return sentinel

    monkeypatch.setattr(
        hook,
        "project_and_admit",
        fake_project_and_admit,
    )

    result = (
        hook.project_semantic_request_and_admit(
            request,
            request_id="hook-test",
            debug_tag="runtime-r0",
        )
    )

    assert result is sentinel

    pin = observed["input"]

    assert isinstance(
        pin,
        ProjectionInputV1,
    )

    assert pin.semantic_graph is request

    assert pin.request_id == "hook-test"
    assert pin.debug_tag == "runtime-r0"


def test_project_hook_rejects_wrong_input_type():
    import pytest

    from elpis_reference.structural_guidance import (
        project_and_admit,
    )

    with pytest.raises(
        TypeError,
        match="ProjectionInputV1",
    ):
        project_and_admit(
            object(),  # type: ignore[arg-type]
        )
