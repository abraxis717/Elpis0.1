from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DigestBoundResolvedTopologyObserverV1,
    PLANNING_AUTHORITY,
    PlanningAuthorityError,
    ResolvedStructuralTopologyV1,
    build_planning_input,
)
from elpis_reference.structural_guidance.materialization_authority import (
    _new_resolved_topology_materialization_authority,
)
from elpis_reference.structural_guidance.planning_authority import (
    _new_planning_authority,
)


PLANNER_ID = (
    "elpis.structural-guidance.deterministic-planner"
)
PLANNER_VERSION = "v1"


def _sha(value: bytes) -> str:
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


def _planning_input():
    topology = _topology()

    observation = (
        DigestBoundResolvedTopologyObserverV1()
        .observe(topology)
    )

    materialization_authority = (
        _new_resolved_topology_materialization_authority()
    )

    intent = (
        materialization_authority
        ._precommit_from_owner(
            topology,
            observation,
            materializer_id=(
                CANONICAL_STRUCTURAL_MATERIALIZER_ID
            ),
            materializer_version=(
                CANONICAL_STRUCTURAL_MATERIALIZER_VERSION
            ),
        )
    )

    authorized = (
        materialization_authority
        ._reveal_from_owner(
            intent
        )
    )

    consumption = (
        materialization_authority
        ._consume_from_owner(
            authorized
        )
    )

    materialization = (
        CanonicalResolvedTopologyMaterializerV1()
        .materialize(
            topology,
            consumption,
        )
    )

    return build_planning_input(
        materialization,
        request_id="request-1",
        prompt="write typed tests",
        domain="python",
        entrypoint="solve",
        parameters=("value",),
        decoder_hints=(
            ("body", "return None"),
        ),
        allowed_experts=(
            "python.codegen",
            "python.ast",
            "python.tests",
            "python.typing",
        ),
        selected_experts=(
            "python.ast",
            "python.codegen",
            "python.tests",
            "python.typing",
        ),
        max_tokens=512,
    )


def _precommit(authority):
    planning = _planning_input()

    intent = authority._precommit_from_owner(
        planning,
        planner_id=PLANNER_ID,
        planner_version=PLANNER_VERSION,
    )

    return planning, intent


def test_precommit_grants_no_capability():
    authority = _new_planning_authority()

    planning, intent = _precommit(
        authority
    )

    assert (
        intent.planning_input_digest
        == planning.planning_input_digest
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


def test_reveal_grants_planning_only():
    authority = _new_planning_authority()

    _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    receipt = authorized.receipt

    assert receipt.authority == PLANNING_AUTHORITY
    assert receipt.planning_authorized is True
    assert receipt.decoding_authorized is False
    assert receipt.execution_authorized is False

    assert receipt.planner_id == PLANNER_ID
    assert receipt.planner_version == PLANNER_VERSION

    receipt.validate()


def test_reveal_is_one_shot():
    authority = _new_planning_authority()

    _, intent = _precommit(
        authority
    )

    authority._reveal_from_owner(
        intent
    )

    with pytest.raises(
        PlanningAuthorityError,
        match="precommitted",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_consumption_is_one_shot():
    authority = _new_planning_authority()

    _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    consumption = authority._consume_from_owner(
        authorized
    )

    assert consumption.authority == PLANNING_AUTHORITY
    assert consumption.planning_authorized is True
    assert consumption.decoding_authorized is False
    assert consumption.execution_authorized is False

    consumption.validate()

    with pytest.raises(
        PlanningAuthorityError,
        match="not active",
    ):
        authority._consume_from_owner(
            authorized
        )


def test_cross_instance_consumption_rejected():
    issuer = _new_planning_authority()
    other = _new_planning_authority()

    _, intent = _precommit(
        issuer
    )

    authorized = issuer._reveal_from_owner(
        intent
    )

    with pytest.raises(
        PlanningAuthorityError,
        match="another",
    ):
        other._consume_from_owner(
            authorized
        )


def test_planner_identity_is_bound():
    authority = _new_planning_authority()

    _, intent = _precommit(
        authority
    )

    assert intent.planner_id == PLANNER_ID
    assert intent.planner_version == PLANNER_VERSION

    object.__setattr__(
        intent,
        "planner_version",
        "v2",
    )

    with pytest.raises(
        PlanningAuthorityError,
        match="digest mismatch",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_tampered_planning_input_rejected_before_precommit():
    planning = _planning_input()

    object.__setattr__(
        planning,
        "entrypoint",
        "retargeted",
    )

    authority = _new_planning_authority()

    with pytest.raises(
        Exception,
    ):
        authority._precommit_from_owner(
            planning,
            planner_id=PLANNER_ID,
            planner_version=PLANNER_VERSION,
        )


def test_public_package_does_not_export_private_authority():
    import elpis_reference.structural_guidance as sg

    assert not hasattr(
        sg,
        "_PlanningAuthority",
    )

    assert not hasattr(
        sg,
        "_new_planning_authority",
    )
