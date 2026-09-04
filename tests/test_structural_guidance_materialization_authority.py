from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

import pytest

from elpis_reference.structural_guidance import (
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralTopologyV1,
    ResolvedTopologyMaterializationAuthorityError,
    STRUCTURAL_MATERIALIZATION_AUTHORITY,
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

    signed = replace(
        unsigned,
        topology_digest=(
            unsigned.topology_digest_computed()
        ),
    )

    signed.validate()

    return signed


def _observation(topology):
    return (
        DigestBoundResolvedTopologyObserverV1()
        .observe(topology)
    )


def _precommit(authority):
    topology = _topology()
    observation = _observation(
        topology
    )

    intent = authority._precommit_from_owner(
        topology,
        observation,
        materializer_id="test.materializer",
        materializer_version="v1",
    )

    return topology, observation, intent


def test_precommit_itself_grants_no_capability():
    authority = (
        _new_resolved_topology_materialization_authority()
    )

    topology, observation, intent = _precommit(
        authority
    )

    assert (
        intent.topology_digest
        == topology.topology_digest
    )
    assert (
        intent.observation_receipt_digest
        == observation.receipt_digest
    )

    assert not hasattr(
        intent,
        "capability_id",
    )
    assert not hasattr(
        intent,
        "authority",
    )

    intent.validate()


def test_reveal_is_materialization_only():
    authority = (
        _new_resolved_topology_materialization_authority()
    )

    _, _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    receipt = authorized.receipt

    assert (
        receipt.authority
        == STRUCTURAL_MATERIALIZATION_AUTHORITY
    )
    assert (
        receipt.materialization_authorized
        is True
    )
    assert receipt.decoding_authorized is False
    assert receipt.execution_authorized is False

    receipt.validate()


def test_intent_reveal_is_one_shot():
    authority = (
        _new_resolved_topology_materialization_authority()
    )

    _, _, intent = _precommit(
        authority
    )

    authority._reveal_from_owner(
        intent
    )

    with pytest.raises(
        ResolvedTopologyMaterializationAuthorityError,
        match="precommitted",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_capability_consumption_is_one_shot():
    authority = (
        _new_resolved_topology_materialization_authority()
    )

    _, _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    consumption = authority._consume_from_owner(
        authorized
    )

    assert (
        consumption.authority
        == STRUCTURAL_MATERIALIZATION_AUTHORITY
    )
    assert (
        consumption.materialization_authorized
        is True
    )
    assert (
        consumption.decoding_authorized
        is False
    )
    assert (
        consumption.execution_authorized
        is False
    )

    consumption.validate()

    with pytest.raises(
        ResolvedTopologyMaterializationAuthorityError,
        match="not active",
    ):
        authority._consume_from_owner(
            authorized
        )


def test_cross_instance_consumption_rejected():
    issuer = (
        _new_resolved_topology_materialization_authority()
    )
    other = (
        _new_resolved_topology_materialization_authority()
    )

    _, _, intent = _precommit(
        issuer
    )

    authorized = issuer._reveal_from_owner(
        intent
    )

    with pytest.raises(
        ResolvedTopologyMaterializationAuthorityError,
        match="another",
    ):
        other._consume_from_owner(
            authorized
        )


def test_observation_must_bind_same_topology():
    authority = (
        _new_resolved_topology_materialization_authority()
    )

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

    observation = _observation(
        first
    )

    with pytest.raises(
        ResolvedTopologyMaterializationAuthorityError,
        match="identity mismatch",
    ):
        authority._precommit_from_owner(
            second,
            observation,
            materializer_id="test.materializer",
            materializer_version="v1",
        )


def test_tampered_intent_rejected_before_reveal():
    authority = (
        _new_resolved_topology_materialization_authority()
    )

    _, _, intent = _precommit(
        authority
    )

    object.__setattr__(
        intent,
        "materializer_version",
        "v2",
    )

    with pytest.raises(
        ResolvedTopologyMaterializationAuthorityError,
        match="digest mismatch",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_public_package_does_not_export_authority_constructor():
    import elpis_reference.structural_guidance as sg

    assert not hasattr(
        sg,
        "_ResolvedTopologyMaterializationAuthority",
    )
    assert not hasattr(
        sg,
        "_new_resolved_topology_materialization_authority",
    )
