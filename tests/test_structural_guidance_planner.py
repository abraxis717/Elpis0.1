from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import inspect

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DETERMINISTIC_STRUCTURAL_PLANNER_ID,
    DETERMINISTIC_STRUCTURAL_PLANNER_VERSION,
    DeterministicStructuralPlannerV1,
    DigestBoundResolvedTopologyObserverV1,
    PLANNING_AUTHORITY,
    ResolvedStructuralTopologyV1,
    StructuralPlanningArtifactV1,
    StructuralPlanningError,
    build_planning_input,
)
from elpis_reference.structural_guidance.materialization_authority import (
    _new_resolved_topology_materialization_authority,
)
from elpis_reference.structural_guidance.planning_authority import (
    _new_planning_authority,
)


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


def _planning_input(
    *,
    entrypoint="solve problem",
    body="return None",
):
    return build_planning_input(
        _materialization(),
        request_id="request-1",
        prompt="write typed tests",
        domain="python",
        entrypoint=entrypoint,
        parameters=(
            "input value",
            "second-value",
        ),
        decoder_hints=(
            (
                "body",
                body,
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


def _authorize(planning_input):
    authority = _new_planning_authority()

    intent = authority._precommit_from_owner(
        planning_input,
        planner_id=(
            DETERMINISTIC_STRUCTURAL_PLANNER_ID
        ),
        planner_version=(
            DETERMINISTIC_STRUCTURAL_PLANNER_VERSION
        ),
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    return authority._consume_from_owner(
        authorized
    )


def test_planner_produces_non_executable_planning_artifact():
    planning_input = _planning_input()
    consumption = _authorize(
        planning_input
    )

    artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            consumption,
        )
    )

    assert isinstance(
        artifact,
        StructuralPlanningArtifactV1,
    )

    assert artifact.authority == PLANNING_AUTHORITY
    assert artifact.planning_authorized is True
    assert artifact.decoding_authorized is False
    assert artifact.execution_authorized is False

    assert artifact.validate_digest()


def test_planner_preserves_raw_identifiers_without_decoding():
    planning_input = _planning_input(
        entrypoint="solve problem",
    )

    artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            _authorize(planning_input),
        )
    )

    assert (
        artifact.requested_entrypoint
        == "solve problem"
    )

    assert artifact.requested_parameters == (
        "input value",
        "second-value",
    )


def test_planner_matches_legacy_body_line_segmentation_only():
    planning_input = _planning_input(
        body="x = 1\nreturn x",
    )

    artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            _authorize(planning_input),
        )
    )

    assert artifact.body_lines == (
        "x = 1",
        "return x",
    )


def test_empty_body_has_safe_structural_default():
    planning_input = _planning_input(
        body="",
    )

    artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            _authorize(planning_input),
        )
    )

    assert artifact.body_lines == (
        "return None",
    )


def test_consumption_cannot_be_retargeted_to_other_input():
    first = _planning_input(
        entrypoint="first",
    )
    second = _planning_input(
        entrypoint="second",
    )

    consumption = _authorize(
        first
    )

    with pytest.raises(
        StructuralPlanningError,
        match="planning_input_digest mismatch",
    ):
        (
            DeterministicStructuralPlannerV1()
            .plan(
                second,
                consumption,
            )
        )


def test_consumption_is_bound_to_planner_identity():
    planning_input = _planning_input()

    consumption = _authorize(
        planning_input
    )

    other = (
        DeterministicStructuralPlannerV1(
            planner_id="other.planner",
        )
    )

    with pytest.raises(
        StructuralPlanningError,
        match="planner identity mismatch",
    ):
        other.plan(
            planning_input,
            consumption,
        )


def test_planning_is_deterministically_replayable():
    planning_input = _planning_input()

    consumption = _authorize(
        planning_input
    )

    planner = (
        DeterministicStructuralPlannerV1()
    )

    first = planner.plan(
        planning_input,
        consumption,
    )

    second = planner.plan(
        planning_input,
        consumption,
    )

    assert first == second
    assert (
        first.planning_artifact_digest
        == second.planning_artifact_digest
    )


def test_planning_artifact_tamper_is_detected():
    planning_input = _planning_input()

    artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            _authorize(planning_input),
        )
    )

    object.__setattr__(
        artifact,
        "max_tokens",
        999,
    )

    assert not artifact.validate_digest()


def test_planner_public_surface_is_plan_only():
    methods = {
        name
        for name, value
        in inspect.getmembers(
            DeterministicStructuralPlannerV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "plan",
    }


def test_planning_artifact_has_no_execution_surface():
    methods = {
        name
        for name, value
        in inspect.getmembers(
            StructuralPlanningArtifactV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "payload",
        "planning_artifact_digest_computed",
        "validate",
        "validate_digest",
    }

    for forbidden in (
        "decode",
        "execute",
        "invoke",
        "run",
        "solve",
        "compile",
    ):
        assert forbidden not in methods


@pytest.mark.parametrize(
    "field",
    (
        "decoding_authorized",
        "execution_authorized",
    ),
)
def test_downstream_authority_widening_breaks_artifact(
    field,
):
    planning_input = _planning_input()

    artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            _authorize(planning_input),
        )
    )

    object.__setattr__(
        artifact,
        field,
        True,
    )

    assert not artifact.validate_digest()
