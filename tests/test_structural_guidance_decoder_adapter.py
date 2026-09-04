from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import inspect

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DECODING_AUTHORITY,
    DETERMINISTIC_DECODER_ADAPTER_ID,
    DETERMINISTIC_DECODER_ADAPTER_VERSION,
    DETERMINISTIC_STRUCTURAL_PLANNER_ID,
    DETERMINISTIC_STRUCTURAL_PLANNER_VERSION,
    DecoderAdapterError,
    DecoderSpecificPlanV1,
    DeterministicDecoderAdapterV1,
    DeterministicStructuralPlannerV1,
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralTopologyV1,
    build_planning_input,
)
from elpis_reference.structural_guidance.decoding_authority import (
    _new_decoding_authority,
)
from elpis_reference.structural_guidance.materialization_authority import (
    _new_resolved_topology_materialization_authority,
)
from elpis_reference.structural_guidance.planning_authority import (
    _new_planning_authority,
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


def _planning_artifact(
    *,
    entrypoint="solve problem",
    parameters=("input value",),
):
    topology = _topology()

    observation = (
        DigestBoundResolvedTopologyObserverV1()
        .observe(topology)
    )

    ma = (
        _new_resolved_topology_materialization_authority()
    )

    mi = ma._precommit_from_owner(
        topology,
        observation,
        materializer_id=(
            CANONICAL_STRUCTURAL_MATERIALIZER_ID
        ),
        materializer_version=(
            CANONICAL_STRUCTURAL_MATERIALIZER_VERSION
        ),
    )

    mc = ma._consume_from_owner(
        ma._reveal_from_owner(mi)
    )

    materialization = (
        CanonicalResolvedTopologyMaterializerV1()
        .materialize(
            topology,
            mc,
        )
    )

    planning_input = build_planning_input(
        materialization,
        request_id="request-1",
        prompt="write typed tests",
        domain="python",
        entrypoint=entrypoint,
        parameters=parameters,
        decoder_hints=(
            (
                "body",
                "x = 1\nreturn x",
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
        ),
        max_tokens=512,
    )

    pa = _new_planning_authority()

    pi = pa._precommit_from_owner(
        planning_input,
        planner_id=(
            DETERMINISTIC_STRUCTURAL_PLANNER_ID
        ),
        planner_version=(
            DETERMINISTIC_STRUCTURAL_PLANNER_VERSION
        ),
    )

    pc = pa._consume_from_owner(
        pa._reveal_from_owner(pi)
    )

    return (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            pc,
        )
    )


def _decode_consumption(
    artifact,
):
    authority = (
        _new_decoding_authority()
    )

    intent = authority._precommit_from_owner(
        artifact,
        decoder_adapter_id=(
            DETERMINISTIC_DECODER_ADAPTER_ID
        ),
        decoder_adapter_version=(
            DETERMINISTIC_DECODER_ADAPTER_VERSION
        ),
    )

    return authority._consume_from_owner(
        authority._reveal_from_owner(
            intent
        )
    )


def test_adapter_emits_authority_zero_decoder_plan():
    artifact = _planning_artifact()

    consumption = _decode_consumption(
        artifact
    )

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            consumption,
        )
    )

    assert isinstance(
        plan,
        DecoderSpecificPlanV1,
    )

    assert (
        plan.authority_applied
        == DECODING_AUTHORITY
    )

    assert plan.authority_granted == 0
    assert plan.planning_authorized is False
    assert plan.decoding_authorized is False
    assert plan.source_emission_authorized is False
    assert plan.execution_authorized is False

    assert plan.validate_digest()


def test_identifier_normalization_matches_established_semantics():
    artifact = _planning_artifact(
        entrypoint="solve problem",
        parameters=(
            "good_name",
            "bad-name",
            "class",
            " spaced ",
        ),
    )

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            _decode_consumption(
                artifact
            ),
        )
    )

    assert plan.function_name == "solution"

    assert plan.parameters == (
        "good_name",
        "arg_1",
        "arg_2",
        "spaced",
    )


def test_valid_requested_function_name_is_preserved():
    artifact = _planning_artifact(
        entrypoint="solve_problem",
    )

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            _decode_consumption(
                artifact
            ),
        )
    )

    assert (
        plan.function_name
        == "solve_problem"
    )


def test_structural_lineage_uses_explicit_new_fields():
    artifact = _planning_artifact()

    consumption = _decode_consumption(
        artifact
    )

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            consumption,
        )
    )

    assert (
        plan.planning_artifact_digest
        == artifact.planning_artifact_digest
    )

    assert (
        plan.decoding_consumption_digest
        == consumption.consumption_digest
    )

    assert (
        plan.topology_digest
        == artifact.topology_digest
    )

    assert not hasattr(
        plan,
        "structural_digest",
    )

    assert not hasattr(
        plan,
        "structural_proposal_digest",
    )


def test_plan_contains_no_source_artifact():
    artifact = _planning_artifact()

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            _decode_consumption(
                artifact
            ),
        )
    )

    assert not hasattr(
        plan,
        "source",
    )

    assert not hasattr(
        plan,
        "artifact",
    )


def test_adapter_is_deterministic():
    artifact = _planning_artifact()

    consumption = _decode_consumption(
        artifact
    )

    adapter = (
        DeterministicDecoderAdapterV1()
    )

    first = adapter.adapt(
        artifact,
        consumption,
    )

    second = adapter.adapt(
        artifact,
        consumption,
    )

    assert first == second

    assert (
        first.decoder_plan_digest
        == second.decoder_plan_digest
    )


def test_consumption_cannot_be_retargeted():
    first = _planning_artifact(
        entrypoint="first",
    )

    second = _planning_artifact(
        entrypoint="second",
    )

    consumption = _decode_consumption(
        first
    )

    with pytest.raises(
        DecoderAdapterError,
        match="planning_artifact_digest mismatch",
    ):
        (
            DeterministicDecoderAdapterV1()
            .adapt(
                second,
                consumption,
            )
        )


def test_adapter_identity_is_bound():
    artifact = _planning_artifact()

    consumption = _decode_consumption(
        artifact
    )

    other = (
        DeterministicDecoderAdapterV1(
            decoder_adapter_id="other.adapter",
        )
    )

    with pytest.raises(
        DecoderAdapterError,
        match="adapter identity mismatch",
    ):
        other.adapt(
            artifact,
            consumption,
        )


def test_duplicate_normalized_parameters_fail_closed():
    artifact = _planning_artifact(
        parameters=(
            "bad-one",
            "bad-two",
        ),
    )

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            _decode_consumption(
                artifact
            ),
        )
    )

    assert plan.parameters == (
        "arg_0",
        "arg_1",
    )


def test_plan_tamper_is_detected():
    artifact = _planning_artifact()

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            _decode_consumption(
                artifact
            ),
        )
    )

    object.__setattr__(
        plan,
        "function_name",
        "retargeted",
    )

    assert not plan.validate_digest()


def test_adapter_public_surface_is_adapt_only():
    methods = {
        name
        for name, value
        in inspect.getmembers(
            DeterministicDecoderAdapterV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "adapt",
    }


def test_decoder_plan_has_no_active_surface():
    methods = {
        name
        for name, value
        in inspect.getmembers(
            DecoderSpecificPlanV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "decoder_plan_digest_computed",
        "payload",
        "validate",
        "validate_digest",
    }

    for forbidden in (
        "decode",
        "execute",
        "invoke",
        "run",
        "emit",
    ):
        assert forbidden not in methods


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
            "source_emission_authorized",
            True,
        ),
        (
            "execution_authorized",
            True,
        ),
    ),
)
def test_output_authority_widening_is_detected(
    field,
    value,
):
    artifact = _planning_artifact()

    plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            artifact,
            _decode_consumption(
                artifact
            ),
        )
    )

    object.__setattr__(
        plan,
        field,
        value,
    )

    assert not plan.validate_digest()
