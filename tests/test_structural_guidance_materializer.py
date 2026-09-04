from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import inspect
from pathlib import Path

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralMaterializationError,
    ResolvedStructuralMaterializationV1,
    ResolvedStructuralTopologyV1,
)
from elpis_reference.structural_guidance.materialization_authority import (
    _new_resolved_topology_materialization_authority,
)


def _sha(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


@dataclass(frozen=True)
class _Schema:
    schema_digest: str


def _topology():
    unsigned = ResolvedStructuralTopologyV1(
        schema=(
            "elpis.structural-guidance."
            "resolved-topology.v1"
        ),
        grid81=(0,) * 81,
        frozen_mask=(0,) * 81,
        writable_mask=(1,) * 81,
        invariants=(),
        lane_bindings=(),
        structural_schema=_Schema(
            schema_digest="1" * 64,
        ),
        declared_features=(0,) * 529,
        active_residual=(0,) * 529,
        residual_ids=(),
        structural_bindings_json="{}",
        structural_bindings_digest=_sha(
            b"{}"
        ),
        semantic_input_digest="2" * 64,
        rule_set_digest="3" * 64,
        projection_structural_schema_digest="4" * 64,
        refiner_structural_schema_digest="5" * 64,
        projection_digest="6" * 64,
        projection_trace_digest="7" * 64,
        projection_fingerprint="8" * 64,
        refinement_state_fingerprint="9" * 64,
        refiner_input_digest="a" * 64,
        envelope_digest="b" * 64,
        receipt_digest="c" * 64,
        checkpoint_sha256="d" * 64,
        best_cost=0,
        iterations=0,
        applied_moves=0,
        authority_granted=0,
        topology_digest="",
    )

    signed = replace(
        unsigned,
        topology_digest=(
            unsigned.topology_digest_computed()
        ),
    )

    signed.validate()

    return signed


def _consumption(topology):
    observation = (
        DigestBoundResolvedTopologyObserverV1()
        .observe(topology)
    )

    authority = (
        _new_resolved_topology_materialization_authority()
    )

    intent = authority._precommit_from_owner(
        topology,
        observation,
        materializer_id=(
            CANONICAL_STRUCTURAL_MATERIALIZER_ID
        ),
        materializer_version=(
            CANONICAL_STRUCTURAL_MATERIALIZER_VERSION
        ),
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    return authority._consume_from_owner(
        authorized
    )


def test_real_materializer_produces_canonical_nonexecuting_artifact():
    topology = _topology()
    consumption = _consumption(
        topology
    )

    materializer = (
        CanonicalResolvedTopologyMaterializerV1()
    )

    artifact = materializer.materialize(
        topology,
        consumption,
    )

    assert isinstance(
        artifact,
        ResolvedStructuralMaterializationV1,
    )

    assert (
        artifact.topology_digest
        == topology.topology_digest
    )

    assert (
        artifact.materialization_consumption_digest
        == consumption.consumption_digest
    )

    assert artifact.materialization_authorized is True
    assert artifact.decoding_authorized is False
    assert artifact.execution_authorized is False

    assert (
        artifact.structural_payload()
        == topology.canonical_payload()
    )

    assert artifact.validate_digest()


def test_materializer_rejects_consumption_for_other_topology():
    first = _topology()

    second = replace(
        _topology(),
        semantic_input_digest="e" * 64,
        topology_digest="",
    )

    second = replace(
        second,
        topology_digest=(
            second.topology_digest_computed()
        ),
    )

    second.validate()

    consumption = _consumption(
        first
    )

    with pytest.raises(
        ResolvedStructuralMaterializationError,
        match="identity mismatch",
    ):
        (
            CanonicalResolvedTopologyMaterializerV1()
            .materialize(
                second,
                consumption,
            )
        )


def test_materializer_identity_is_bound_by_capability():
    topology = _topology()
    consumption = _consumption(
        topology
    )

    other = (
        CanonicalResolvedTopologyMaterializerV1(
            materializer_id="other.materializer",
        )
    )

    with pytest.raises(
        ResolvedStructuralMaterializationError,
        match="identity mismatch",
    ):
        other.materialize(
            topology,
            consumption,
        )


def test_materialized_payload_tamper_is_detected():
    topology = _topology()

    artifact = (
        CanonicalResolvedTopologyMaterializerV1()
        .materialize(
            topology,
            _consumption(topology),
        )
    )

    object.__setattr__(
        artifact,
        "structural_payload_json",
        "{}",
    )

    assert not artifact.validate_digest()


def test_materializer_public_surface_is_materialize_only():
    methods = {
        name
        for name, value in inspect.getmembers(
            CanonicalResolvedTopologyMaterializerV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "materialize",
    }


def test_materialized_artifact_has_no_execution_surface():
    methods = {
        name
        for name, value in inspect.getmembers(
            ResolvedStructuralMaterializationV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "materialization_digest_computed",
        "payload",
        "structural_payload",
        "validate",
        "validate_digest",
    }

    forbidden = (
        "execute",
        "decode",
        "invoke",
        "route",
        "select",
        "solve",
        "apply",
    )

    for name in methods:
        assert not any(
            token in name
            for token in forbidden
        )


def test_materializer_has_no_domain_or_decoder_dependencies():
    import elpis_reference.structural_guidance.materializer as module

    source = Path(
        module.__file__
    ).read_text().lower()

    forbidden = (
        "sudoku",
        "darwinianmatrix",
        "darwinian_matrix",
        "p01_materializer",
        "reference_solver",
        "elpis_p0",
        "artifactcandidate",
        "decodercontrolplan",
        "torch",
        "subprocess",
        "runpy",
        "importlib",
    )

    for token in forbidden:
        assert token not in source
