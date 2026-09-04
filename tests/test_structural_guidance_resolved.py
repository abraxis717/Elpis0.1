from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path

import pytest

from elpis_reference.structural_guidance import (
    ResolvedStructuralTopologyError,
    ResolvedStructuralTopologyV1,
    StructuralGuidanceAdmissionResult,
    admit_projection,
    build_resolved_structural_topology,
)
from elpis_reference.structural_guidance.admission import (
    build_envelope,
)
from elpis_reference.structural_guidance.hook import (
    ProjectAndAdmitResultV1,
)
from elpis_reference.structural_guidance import (
    receipt as receipt_module,
)
from elpis_reference.structural_guidance.receipt import (
    StructuralGuidanceReceiptV1,
)
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticEntityV1,
    SemanticOperationV1,
    build_semantic_request_v1,
)
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
    ProjectionInputV1,
)
from elpis_reference.structural_guidance._authority.c2r6p0.projector import (
    project,
)
from elpis_reference.structural_guidance._authority.c2r6p1_bridge.adapter import (
    adapt_projection_to_refiner_input,
)


def _projection():
    request = build_semantic_request_v1(
        request_id="resolved-topology-test",
        entities=(
            SemanticEntityV1(
                "in0",
                "input",
                "v.in0",
                "str",
            ),
            SemanticEntityV1(
                "out0",
                "output",
                "v.out0",
                "str",
            ),
        ),
        operations=(
            SemanticOperationV1(
                "op0",
                "step",
                input_entity_ids=("in0",),
                output_entity_ids=("out0",),
            ),
        ),
        output_entity_ids=("out0",),
    )

    projection = project(
        ProjectionInputV1.from_signed(
            request,
            request_id="resolved-topology-test",
            debug_tag="resolved-topology-test",
        )
    )

    assert projection.status == "PROJECTED"

    return projection


def _signed_receipt(
    *,
    projection,
    ri,
    envelope,
    best_cost=0,
    output_fingerprint=None,
):
    base = admit_projection(
        projection
    ).receipt

    unsigned = replace(
        base,
        outcome="ADMITTED",
        enabled=True,
        envelope_digest=(
            envelope.envelope_digest
        ),
        input_refinement_fingerprint=(
            ri.refinement_state_fingerprint
        ),
        output_refinement_fingerprint=(
            output_fingerprint
            if output_fingerprint is not None
            else ri.refinement_state_fingerprint
        ),
        checkpoint_sha256="a" * 64,
        seed=0,
        budget=8,
        restarts=1,
        plateau=0,
        iterations=0,
        best_cost=best_cost,
        applied_moves=0,
        authority_granted=0,
        error_code="",
        receipt_digest="",
    )

    digest = receipt_module._digest(
        unsigned.payload()
    )

    signed = replace(
        unsigned,
        receipt_digest=digest,
    )

    assert signed.validate_digest()

    return signed


def _admitted_result(
    *,
    best_cost=0,
    output_fingerprint=None,
):
    projection = _projection()

    ri = adapt_projection_to_refiner_input(
        projection
    )

    envelope = build_envelope(
        projection,
        ri,
    )

    receipt = _signed_receipt(
        projection=projection,
        ri=ri,
        envelope=envelope,
        best_cost=best_cost,
        output_fingerprint=output_fingerprint,
    )

    admission = StructuralGuidanceAdmissionResult(
        admitted=True,
        fallback_required=False,
        final_input=ri,
        envelope=envelope,
        receipt=receipt,
    )

    return ProjectAndAdmitResultV1(
        projection=projection,
        admission=admission,
    )


def test_build_resolved_topology_preserves_authority_zero():
    result = _admitted_result()

    topology = (
        build_resolved_structural_topology(
            result
        )
    )

    assert isinstance(
        topology,
        ResolvedStructuralTopologyV1,
    )

    assert topology.authority_granted == 0
    assert topology.best_cost == 0

    assert len(topology.grid81) == 81
    assert (
        len(topology.declared_features)
        == 529
    )
    assert (
        len(topology.active_residual)
        == 529
    )

    assert (
        topology.projection_digest
        == result.projection.projection_digest
    )

    assert (
        topology.refinement_state_fingerprint
        == result.admission.final_input
        .refinement_state_fingerprint
    )

    assert (
        topology.envelope_digest
        == result.admission.envelope
        .envelope_digest
    )

    assert (
        topology.receipt_digest
        == result.admission.receipt
        .receipt_digest
    )

    assert topology.validate_digest()


def test_resolved_topology_binds_p0_and_p1_schema_identities():
    result = _admitted_result()

    topology = build_resolved_structural_topology(
        result
    )

    p0_schema = result.projection.structural_schema
    final = result.admission.final_input
    p1_schema = final.structural_schema

    assert p0_schema is not None

    assert (
        topology.projection_structural_schema_digest
        == p0_schema.schema_digest
    )

    assert (
        topology.refiner_structural_schema_digest
        == p1_schema.schema_digest
    )

    assert (
        p1_schema.semantic_request_digest
        == p0_schema.semantic_request_digest
    )
    assert p1_schema.lanes == p0_schema.lanes
    assert p1_schema.initial_grid == p0_schema.initial_grid
    assert p1_schema.invariants == p0_schema.invariants

    assert (
        p1_schema.writable_mask
        == final.writable_mask
    )
    assert (
        final.writable_mask
        == result.projection.writable_mask
    )

    assert all(
        (not child) or parent
        for child, parent in zip(
            p1_schema.writable_mask,
            p0_schema.writable_mask,
        )
    )

    assert topology.validate_digest()


def test_bypassed_admission_cannot_materialize():
    projection = _projection()

    result = ProjectAndAdmitResultV1(
        projection=projection,
        admission=admit_projection(
            projection
        ),
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
        match="ADMITTED",
    ):
        build_resolved_structural_topology(
            result
        )


def test_fallback_required_cannot_materialize():
    result = _admitted_result()

    result = replace(
        result,
        admission=replace(
            result.admission,
            admitted=False,
            fallback_required=True,
            final_input=None,
            envelope=None,
        ),
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
    ):
        build_resolved_structural_topology(
            result
        )


def test_wrong_receipt_type_rejected():
    result = _admitted_result()

    result = replace(
        result,
        admission=replace(
            result.admission,
            receipt=object(),
        ),
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
        match="StructuralGuidanceReceiptV1",
    ):
        build_resolved_structural_topology(
            result
        )


def test_nonzero_guidance_authority_rejected():
    result = _admitted_result()

    receipt = result.admission.receipt

    object.__setattr__(
        receipt,
        "authority_granted",
        1,
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
        match="authority",
    ):
        build_resolved_structural_topology(
            result
        )


def test_receipt_contract_itself_forbids_authority_widening():
    result = _admitted_result()

    with pytest.raises(
        ValueError,
        match="never receive authority",
    ):
        replace(
            result.admission.receipt,
            authority_granted=1,
            receipt_digest="",
        )


def test_nonzero_frozen_objective_rejected():
    result = _admitted_result(
        best_cost=1,
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
        match="resolved",
    ):
        build_resolved_structural_topology(
            result
        )


def test_final_masks_are_projection_authority():
    result = _admitted_result()

    final = result.admission.final_input

    bad_mask = list(
        final.writable_mask
    )

    index = next(
        i
        for i, value in enumerate(
            bad_mask
        )
        if value == 1
    )

    bad_mask[index] = 0

    object.__setattr__(
        final,
        "writable_mask",
        tuple(bad_mask),
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
        match="writable mask",
    ):
        build_resolved_structural_topology(
            result
        )


def test_receipt_output_identity_must_match():
    result = _admitted_result(
        output_fingerprint="c" * 64,
    )

    with pytest.raises(
        ResolvedStructuralTopologyError,
        match="final-state identity",
    ):
        build_resolved_structural_topology(
            result
        )


def test_topology_digest_detects_tamper():
    topology = (
        build_resolved_structural_topology(
            _admitted_result()
        )
    )

    tampered_grid = list(
        topology.grid81
    )

    index = next(
        i
        for i, value in enumerate(
            tampered_grid
        )
        if value != 9
    )

    tampered_grid[index] = 9

    tampered = replace(
        topology,
        grid81=tuple(
            tampered_grid
        ),
    )

    assert not tampered.validate_digest()


def test_resolved_artifact_has_no_execution_surface():
    forbidden = (
        "apply",
        "decode",
        "execute",
        "invoke",
        "route",
        "run",
        "select",
        "solve",
    )

    public_callables = {
        name
        for name, value in inspect.getmembers(
            ResolvedStructuralTopologyV1
        )
        if not name.startswith("_")
        and callable(value)
    }

    assert public_callables == {
        "canonical_payload",
        "topology_digest_computed",
        "validate",
        "validate_digest",
    }

    for name in public_callables:
        assert not any(
            token in name
            for token in forbidden
        )


def test_resolved_module_has_no_runtime_consumer_imports():
    import elpis_reference.structural_guidance.resolved as resolved

    source = Path(
        resolved.__file__
    ).read_text().lower()

    forbidden = (
        "darwinianmatrix",
        "darwinian_matrix",
        "p01_materializer",
        "reference_solver",
        "sudoku",
        "p0controller",
        "p0controlprotocol",
        ".decoder",
    )

    for token in forbidden:
        assert token not in source
