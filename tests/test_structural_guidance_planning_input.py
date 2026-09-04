from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DigestBoundResolvedTopologyObserverV1,
    PlanningInputContractError,
    PlanningInputV1,
    ResolvedStructuralTopologyV1,
    build_planning_input,
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


def _materialization():
    topology = _topology()

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

    consumption = authority._consume_from_owner(
        authorized
    )

    return (
        CanonicalResolvedTopologyMaterializerV1()
        .materialize(
            topology,
            consumption,
        )
    )


def _planning_input():
    return build_planning_input(
        _materialization(),
        request_id="request-1",
        prompt="write typed tests",
        domain="python",
        entrypoint="solve problem",
        parameters=("input value",),
        decoder_hints=(
            (
                "body",
                "return None",
            ),
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


def test_planning_input_is_signed_and_authority_zero():
    planning = _planning_input()

    assert isinstance(
        planning,
        PlanningInputV1,
    )

    assert planning.authority_granted == 0
    assert planning.planning_authorized is False
    assert planning.decoding_authorized is False
    assert planning.execution_authorized is False
    assert planning.validate_digest()


def test_prompt_content_is_not_stored():
    planning = _planning_input()

    assert not hasattr(
        planning,
        "prompt",
    )

    assert len(
        planning.prompt_digest
    ) == 64


def test_code_shaping_fields_change_request_identity():
    first = _planning_input()

    materialization = _materialization()

    second = build_planning_input(
        materialization,
        request_id="request-1",
        prompt="write typed tests",
        domain="python",
        entrypoint="different",
        parameters=("input value",),
        decoder_hints=(
            (
                "body",
                "return None",
            ),
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

    assert (
        first.request_sidecar_digest
        != second.request_sidecar_digest
    )

    assert (
        first.planning_input_digest
        != second.planning_input_digest
    )


def test_expert_selection_is_bound_separately():
    materialization = _materialization()

    first = build_planning_input(
        materialization,
        request_id="request-1",
        prompt="x",
        allowed_experts=(
            "python.ast",
            "python.codegen",
        ),
        selected_experts=(
            "python.ast",
        ),
    )

    second = build_planning_input(
        materialization,
        request_id="request-1",
        prompt="x",
        allowed_experts=(
            "python.ast",
            "python.codegen",
        ),
        selected_experts=(
            "python.codegen",
        ),
    )

    assert (
        first.expert_selection_digest
        != second.expert_selection_digest
    )
    assert (
        first.planning_input_digest
        != second.planning_input_digest
    )


def test_selected_experts_must_be_allowed():
    with pytest.raises(
        PlanningInputContractError,
        match="not allowed",
    ):
        build_planning_input(
            _materialization(),
            request_id="request-1",
            prompt="x",
            allowed_experts=(
                "python.ast",
            ),
            selected_experts=(
                "python.codegen",
            ),
        )


def test_duplicate_hint_keys_are_rejected():
    with pytest.raises(
        PlanningInputContractError,
        match="duplicate",
    ):
        build_planning_input(
            _materialization(),
            request_id="request-1",
            prompt="x",
            decoder_hints=(
                ("body", "a"),
                ("body", "b"),
            ),
        )


def test_post_construction_tamper_breaks_digest():
    planning = _planning_input()

    object.__setattr__(
        planning,
        "entrypoint",
        "retargeted",
    )

    assert not planning.validate_digest()


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    (
        (
            "authority_granted",
            1,
        ),
        (
            "planning_authorized",
            True,
        ),
        (
            "decoding_authorized",
            True,
        ),
        (
            "execution_authorized",
            True,
        ),
    ),
)
def test_authority_widening_is_rejected(
    field,
    value,
):
    planning = _planning_input()

    object.__setattr__(
        planning,
        field,
        value,
    )

    assert not planning.validate_digest()
