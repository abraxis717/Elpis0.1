from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import inspect
from pathlib import Path

import pytest

from elpis_reference.structural_guidance import (
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralTopologyV1,
    ResolvedTopologyConsumerPort,
    ResolvedTopologyObservationError,
)


def _digest_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


@dataclass(frozen=True)
class _DummyStructuralSchema:
    schema_digest: str


def _topology() -> ResolvedStructuralTopologyV1:
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
        structural_schema=(
            _DummyStructuralSchema(
                schema_digest="1" * 64,
            )
        ),
        declared_features=(0,) * 529,
        active_residual=(0,) * 529,
        residual_ids=(),
        structural_bindings_json="{}",
        structural_bindings_digest=(
            _digest_bytes(b"{}")
        ),
        semantic_input_digest="2" * 64,
        rule_set_digest="3" * 64,
        projection_structural_schema_digest=(
            "4" * 64
        ),
        refiner_structural_schema_digest=(
            "5" * 64
        ),
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

    unsigned.validate()

    signed = replace(
        unsigned,
        topology_digest=(
            unsigned.topology_digest_computed()
        ),
    )

    signed.validate()

    return signed


def test_observer_satisfies_consumer_port():
    observer = (
        DigestBoundResolvedTopologyObserverV1()
    )

    assert isinstance(
        observer,
        ResolvedTopologyConsumerPort,
    )


def test_observer_emits_digest_bound_authority_zero_receipt():
    observer = (
        DigestBoundResolvedTopologyObserverV1()
    )
    topology = _topology()

    receipt = observer.observe(
        topology
    )

    assert receipt.outcome == "OBSERVED"
    assert (
        receipt.topology_digest
        == topology.topology_digest
    )

    assert receipt.authority_granted == 0
    assert receipt.execution_authorized is False
    assert receipt.decoding_authorized is False
    assert (
        receipt.materialization_authorized
        is False
    )

    assert receipt.validate_digest()


def test_observer_rejects_tampered_topology():
    observer = (
        DigestBoundResolvedTopologyObserverV1()
    )
    topology = _topology()

    object.__setattr__(
        topology,
        "semantic_input_digest",
        "e" * 64,
    )

    with pytest.raises(
        ResolvedTopologyObservationError,
    ):
        observer.observe(
            topology
        )


def test_observer_rejects_wrong_type():
    observer = (
        DigestBoundResolvedTopologyObserverV1()
    )

    with pytest.raises(
        TypeError,
        match="ResolvedStructuralTopologyV1",
    ):
        observer.observe(
            object()
        )


def test_observer_identity_is_fail_closed():
    with pytest.raises(
        ResolvedTopologyObservationError,
        match="consumer_id",
    ):
        DigestBoundResolvedTopologyObserverV1(
            consumer_id="",
        )

    with pytest.raises(
        ResolvedTopologyObservationError,
        match="consumer_version",
    ):
        DigestBoundResolvedTopologyObserverV1(
            consumer_version="",
        )


def test_observer_public_method_surface_is_observe_only():
    public_methods = {
        name
        for name, value in inspect.getmembers(
            DigestBoundResolvedTopologyObserverV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert public_methods == {
        "observe",
    }


def test_observer_has_no_authority_bearing_imports():
    import elpis_reference.structural_guidance.observer as observer_module

    source = Path(
        observer_module.__file__
    ).read_text().lower()

    forbidden = (
        "darwinianmatrix",
        "darwinian_matrix",
        "p01_materializer",
        "reference_solver",
        "elpis_p0",
        "artifactcandidate",
        "decodercontrolplan",
        "p0result",
        "torch",
        "subprocess",
        "runpy",
        "importlib",
    )

    for token in forbidden:
        assert token not in source
